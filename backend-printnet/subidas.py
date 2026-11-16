"""Subida en partes: archivos de hasta 300 MB a pesar del límite de Cloudflare.

POR QUÉ EXISTE: Cloudflare, en el plan gratuito, corta las peticiones de más
de 100 MB. El límite es por PETICIÓN, no por archivo, así que el archivo
viaja partido en pedazos de 6 MB, cada uno en la suya, y se rearma acá.

De paso resuelve que el archivo se subía dos veces (una para contar páginas,
otra al pagar): ahora se sube una vez, se prepara, y el pedido lo referencia
por id. Ver docs/plan-subida-en-partes.md.

El estado vive en disco, sin tabla en la base: uploads/_subidas/{id}/meta.json.
Es temporal y se borra solo a las 24 h.

Sin FastAPI a propósito: routers/subidas.py solo traduce HTTP a estas
funciones, y esto se prueba con un script pelado (test_subidas.py).
"""

import json
import logging
import math
import os
import re
import shutil
import time
import uuid
from pathlib import Path

import document_convert
from database import UPLOADS_DIR

logger = logging.getLogger("printnet.subidas")

# Lo dicta el servidor (va en la respuesta de abrir): la web no lo tiene
# escrito, así no hay otro número duplicado entre los dos lados.
PARTE_BYTES = 6 * 1024 * 1024

# ESPEJADO EN frontend/src/limites.js (MAX_ARCHIVO_MB). Si se cambia acá hay
# que cambiarlo allá, o la web deja subir algo que después se rechaza. Es
# sobre el TOTAL del pedido: routers/orders.py suma las subidas al crearlo.
MAX_PEDIDO_MB = 300
MAX_PEDIDO_BYTES = MAX_PEDIDO_MB * 1024 * 1024

# Para que nadie pueda llenar el disco de la notebook abriendo subidas y
# abandonándolas: entre todas las que están en curso, no más de esto.
TOPE_DISCO_BYTES = 3 * 1024 * 1024 * 1024

# Una subida que no termina en pedido se borra pasado este tiempo.
VIDA_SEG = 24 * 3600

SUBIDAS_DIR = UPLOADS_DIR / "_subidas"

MENSAJE_FORMATO = (
    "No aceptamos ese formato. Podés subir un PDF, o un documento de Word, "
    "Excel, PowerPoint u OpenOffice — esos los convertimos a PDF nosotros."
)

# Cuando la conversión falla por un problema NUESTRO (LibreOffice caído, un
# timeout), el cliente no puede hacer nada con el detalle técnico — y ese
# detalle incluye rutas internas del servidor. Va al registro, no a la pantalla.
MENSAJE_CONVERSION_FALLIDA = (
    "No pudimos procesar tu documento. Probá subiéndolo en PDF, o escribinos "
    "y lo resolvemos."
)

# El id va en la URL y se usa como nombre de carpeta: sin esta validación,
# un id como "../../algo" escribiría fuera de uploads/.
_ID_VALIDO = re.compile(r"^[0-9a-f]{32}$")


class ErrorSubida(Exception):
    """Un rechazo con el código HTTP que le corresponde y un mensaje para el cliente."""

    def __init__(self, status: int, mensaje: str):
        super().__init__(mensaje)
        self.status = status
        self.mensaje = mensaje


def nombre_seguro(nombre: str) -> str:
    base = Path(nombre).name
    return re.sub(r"[^\w.\- ]", "_", base) or "archivo"


def contar_paginas_pdf(path: Path) -> int | None:
    try:
        from pypdf import PdfReader

        return len(PdfReader(str(path)).pages)
    except Exception:
        return None


def es_pdf(nombre: str, content_type: str) -> bool:
    return content_type == "application/pdf" or nombre.lower().endswith(".pdf")


def _cantidad_partes(tamano_bytes: int) -> int:
    return math.ceil(tamano_bytes / PARTE_BYTES)


def _parte(carpeta: Path, n: int) -> Path:
    return carpeta / "partes" / f"{n:05d}"


def _carpeta(id_: str) -> Path:
    if not _ID_VALIDO.match(id_ or ""):
        raise ErrorSubida(404, "subida inexistente")
    carpeta = SUBIDAS_DIR / id_
    if not (carpeta / "meta.json").is_file():
        raise ErrorSubida(404, "subida inexistente")
    return carpeta


def _leer(carpeta: Path) -> dict:
    return json.loads((carpeta / "meta.json").read_text("utf-8"))


def _escribir(carpeta: Path, meta: dict) -> None:
    # Escribir aparte y reemplazar: si el proceso muere a la mitad, el
    # meta.json viejo queda entero en vez de uno cortado que no se puede leer.
    tmp = carpeta / "meta.json.tmp"
    tmp.write_text(json.dumps(meta, ensure_ascii=False), "utf-8")
    os.replace(tmp, carpeta / "meta.json")


def _ocupado() -> int:
    if not SUBIDAS_DIR.exists():
        return 0
    return sum(p.stat().st_size for p in SUBIDAS_DIR.rglob("*") if p.is_file())


def abrir(nombre: str, tamano_bytes: int, content_type: str = "") -> dict:
    """Empieza una subida. Devuelve el id y cómo partir el archivo."""
    nombre = nombre or "archivo"
    if not (es_pdf(nombre, content_type) or document_convert.necesita_conversion(nombre)):
        raise ErrorSubida(422, MENSAJE_FORMATO)
    if tamano_bytes <= 0:
        raise ErrorSubida(422, f"'{nombre}' está vacío")
    if tamano_bytes > MAX_PEDIDO_BYTES:
        raise ErrorSubida(413, f"'{nombre}' supera el máximo de {MAX_PEDIDO_MB} MB")
    if _ocupado() + tamano_bytes > TOPE_DISCO_BYTES:
        logger.warning("Subidas en curso ocupan más del tope: se rechaza '%s'", nombre)
        raise ErrorSubida(503, "Estamos recibiendo muchos archivos. Probá de nuevo en un rato.")

    id_ = uuid.uuid4().hex
    carpeta = SUBIDAS_DIR / id_
    (carpeta / "partes").mkdir(parents=True)
    _escribir(carpeta, {
        "id": id_,
        "nombre": nombre,
        "tamano_bytes": tamano_bytes,
        "content_type": content_type or "",
        "estado": "subiendo",
        "creado": time.time(),
        "paginas": None,
        "convertido": None,
        "error": None,
    })
    return {"id": id_, "parte_bytes": PARTE_BYTES, "partes": _cantidad_partes(tamano_bytes)}


def guardar_parte(id_: str, n: int, datos: bytes) -> None:
    """Guarda el pedazo `n`. Mandarlo de nuevo lo pisa: así un reintento es seguro."""
    carpeta = _carpeta(id_)
    meta = _leer(carpeta)
    if meta["estado"] != "subiendo":
        raise ErrorSubida(409, "esta subida ya se completó")
    total = _cantidad_partes(meta["tamano_bytes"])
    if not 0 <= n < total:
        raise ErrorSubida(422, f"la parte {n} no existe: son {total}, de 0 a {total - 1}")
    if len(datos) > PARTE_BYTES:
        raise ErrorSubida(413, "la parte es más grande de lo permitido")

    destino = _parte(carpeta, n)
    tmp = destino.with_name(destino.name + ".tmp")
    tmp.write_bytes(datos)
    os.replace(tmp, destino)


def completar(id_: str) -> bool:
    """Cierra la subida. True si ESTA llamada la pasó a 'preparando'.

    Solo en ese caso hay que agendar `preparar`: si la web reintenta el
    "terminé", no se tienen que lanzar dos preparaciones sobre la misma carpeta.
    """
    carpeta = _carpeta(id_)
    meta = _leer(carpeta)
    if meta["estado"] != "subiendo":
        return False
    faltan = [n for n in range(_cantidad_partes(meta["tamano_bytes"]))
              if not _parte(carpeta, n).is_file()]
    if faltan:
        raise ErrorSubida(
            422, f"faltan {len(faltan)} parte(s) del archivo (la primera es la {faltan[0]})")
    meta["estado"] = "preparando"
    _escribir(carpeta, meta)
    return True


def preparar(id_: str) -> None:
    """Junta los pedazos, convierte si hace falta y cuenta páginas.

    Corre en segundo plano: nunca propaga. El resultado, bueno o malo, queda
    en meta.json y la web lo lee con `estado()`.
    """
    try:
        carpeta = _carpeta(id_)
        meta = _leer(carpeta)
    except ErrorSubida:
        return
    if meta["estado"] != "preparando":
        return
    try:
        meta.update(_preparar(carpeta, meta))
        meta["estado"] = "listo"
    except ErrorSubida as e:
        meta["estado"], meta["error"] = "error", e.mensaje
    except Exception:
        logger.exception("Subida %s: falló la preparación", id_)
        meta["estado"], meta["error"] = "error", MENSAJE_CONVERSION_FALLIDA
    _escribir(carpeta, meta)


def _preparar(carpeta: Path, meta: dict) -> dict:
    # "original" + extensión, y no el nombre del cliente: un archivo llamado
    # "meta.json" o "partes" pisaría lo nuestro. El nombre real se le pone
    # recién al moverlo a la carpeta del pedido, en tomar().
    original = carpeta / ("original" + Path(nombre_seguro(meta["nombre"])).suffix.lower())

    # De a un pedazo: nunca se tiene el archivo entero en memoria.
    with open(original, "wb") as salida:
        for n in range(_cantidad_partes(meta["tamano_bytes"])):
            with open(_parte(carpeta, n), "rb") as pedazo:
                shutil.copyfileobj(pedazo, salida)
    shutil.rmtree(carpeta / "partes")

    recibido = original.stat().st_size
    if recibido != meta["tamano_bytes"]:
        raise ErrorSubida(
            422,
            f"El archivo llegó incompleto ({recibido} de {meta['tamano_bytes']} bytes). "
            f"Subilo de nuevo.",
        )

    resultado = document_convert.convertir_a_pdf(str(original), str(carpeta))
    if not resultado.ok:
        if resultado.del_documento:
            raise ErrorSubida(422, resultado.detalle)
        logger.error("Conversión fallida (problema del sistema): %s", resultado.detalle)
        raise ErrorSubida(422, MENSAJE_CONVERSION_FALLIDA)

    paginas = contar_paginas_pdf(Path(resultado.pdf_path))
    if paginas is None:
        raise ErrorSubida(422, "no se pudo leer el documento para contar sus páginas")

    return {
        "original": str(original),
        "pdf": resultado.pdf_path,
        "paginas": paginas,
        "convertido": not es_pdf(meta["nombre"], meta["content_type"]),
    }


def estado(id_: str) -> dict:
    """Lo que la web necesita saber de una subida."""
    meta = _leer(_carpeta(id_))
    return {k: meta.get(k) for k in
            ("id", "nombre", "tamano_bytes", "estado", "paginas", "convertido", "error")}


def _unico(nombre: str, usados: set[str]) -> str:
    candidato, i = nombre, 1
    while candidato in usados:
        candidato = f"{Path(nombre).stem}_{i}{Path(nombre).suffix}"
        i += 1
    usados.add(candidato)
    return candidato


def tomar(id_: str, destino: Path, usados: set[str]) -> dict:
    """Mueve una subida lista a la carpeta del pedido y la borra.

    Devuelve lo mismo que `_guardar_archivos` en routers/orders.py, así el
    resto de la creación del pedido no se entera de por dónde llegó el
    archivo. `usados` son los nombres ya ocupados en `destino`, para que dos
    documentos con el mismo nombre no se pisen.
    """
    carpeta = _carpeta(id_)
    meta = _leer(carpeta)
    if meta["estado"] != "listo":
        raise ErrorSubida(409, f"'{meta['nombre']}' todavía no terminó de prepararse")

    destino.mkdir(parents=True, exist_ok=True)
    nombre = _unico(nombre_seguro(meta["nombre"]), usados)
    original = destino / nombre
    shutil.move(meta["original"], original)

    if meta["pdf"] == meta["original"]:
        pdf = original
    else:
        pdf = destino / _unico(Path(nombre).stem + ".pdf", usados)
        shutil.move(meta["pdf"], pdf)

    shutil.rmtree(carpeta)
    return {
        "filename_original": meta["nombre"],
        "stored_path": str(original),
        "pdf_path": str(pdf),
        "content_type": meta["content_type"] or None,
        "size_bytes": meta["tamano_bytes"],
        "paginas": meta["paginas"],
    }


def limpiar_viejas(ahora: float | None = None) -> int:
    """Borra las subidas de hace más de VIDA_SEG. Devuelve cuántas borró."""
    ahora = time.time() if ahora is None else ahora
    if not SUBIDAS_DIR.exists():
        return 0
    borradas = 0
    for carpeta in SUBIDAS_DIR.iterdir():
        if not carpeta.is_dir():
            continue
        try:
            creado = _leer(carpeta)["creado"]
        except Exception:
            # meta.json roto o a medio escribir: se usa la fecha de la carpeta
            creado = carpeta.stat().st_mtime
        if ahora - creado > VIDA_SEG:
            shutil.rmtree(carpeta, ignore_errors=True)
            borradas += 1
    return borradas
