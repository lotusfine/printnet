"""Subida en partes: archivos de hasta 300 MB a pesar del límite de Cloudflare.

POR QUÉ EXISTE: Cloudflare, en el plan gratuito, corta las peticiones de más
de 100 MB. El límite es por PETICIÓN, no por archivo, así que el archivo
viaja partido en pedazos de 6 MB, cada uno en la suya, y se rearma acá.

De paso resuelve que el archivo se subía dos veces (una para contar páginas,
otra al pagar): ahora se sube una vez, se prepara, y el pedido lo referencia
por id. Ver docs/plan-subida-en-partes.md.

El estado vive en disco, sin tabla en la base: uploads/_subidas/{id}/meta.json.
Es temporal y se borra solo.

Estados:  subiendo → preparando → listo → reservada → (se borra)
                         ↘ error        ↖ devolver()

CONCURRENCIA: todo lo que lee o cambia una subida pasa por su candado. Sin
eso, un doble clic en "pagar" o un "terminé" reintentado hacían que dos
requests se pisaran: dos preparaciones sobre la misma carpeta, dos pedidos
moviendo el mismo archivo, temporales compartidos (lo encontró la prueba
hostil, ver docs/plan-subida-en-partes.md). El backend corre en UN solo
proceso, así que un candado de threading alcanza.

Sin FastAPI a propósito: routers/subidas.py solo traduce HTTP a estas
funciones, y esto se prueba con un script pelado (test_subidas.py).
"""

import json
import logging
import math
import os
import re
import shutil
import threading
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
# abandonándolas: entre todas las que existen, no más de esto. Se cuenta lo
# ANUNCIADO, no lo ya escrito: si no, se podían abrir veinte de 300 MB antes
# de mandar un byte y todas pasaban el control.
TOPE_DISCO_BYTES = 3 * 1024 * 1024 * 1024

# Una subida que no termina en pedido se borra pasado este tiempo.
VIDA_SEG = 24 * 3600

# Una subida a medio mandar sin novedades en este tiempo está abandonada
# (pestaña cerrada, cliente que se fue). Se borra antes de las 24 h para que
# no ocupe el tope de disco y termine rechazando a los demás clientes.
INACTIVIDAD_SEG = 3600

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

MENSAJE_INTERRUMPIDA = (
    "Se interrumpió la preparación de tu documento. Subilo de nuevo, por favor."
)

# El id va en la URL y se usa como nombre de carpeta: sin esta validación,
# un id como "../../algo" escribiría fuera de uploads/.
_ID_VALIDO = re.compile(r"^[0-9a-f]{32}$")

# Windows no deja crear archivos con estos nombres (con cualquier extensión),
# y la notebook es Windows: "CON.pdf" fallaría recién al guardarlo.
_RESERVADOS_WINDOWS = {"CON", "PRN", "AUX", "NUL",
                       *(f"COM{i}" for i in range(1, 10)),
                       *(f"LPT{i}" for i in range(1, 10))}

_candados: dict[str, threading.Lock] = {}
_candado_de_candados = threading.Lock()
# Abrir mira el tope de disco y después crea la carpeta: sin esto, dos
# aperturas simultáneas podían pasar el control las dos.
_candado_abrir = threading.Lock()
# Subidas con un preparar() trabajando ahora mismo (se toca bajo su candado).
_en_preparacion: set[str] = set()


class ErrorSubida(Exception):
    """Un rechazo con el código HTTP que le corresponde y un mensaje para el cliente."""

    def __init__(self, status: int, mensaje: str):
        super().__init__(mensaje)
        self.status = status
        self.mensaje = mensaje


def _candado(id_: str) -> threading.Lock:
    with _candado_de_candados:
        return _candados.setdefault(id_, threading.Lock())


def nombre_seguro(nombre: str) -> str:
    """Un nombre que se puede guardar tal cual en la notebook.

    Recortado: con un nombre de 255 caracteres, agregarle "_1" para no pisar
    otro documento pasaba el límite del sistema de archivos y daba error.
    """
    base = Path((nombre or "").replace("\\", "/")).name
    limpio = re.sub(r"[^\w.\- ]", "_", base).strip(" ") or "archivo"
    stem, sufijo = Path(limpio).stem, Path(limpio).suffix
    if not sufijo and stem.startswith("."):
        # ".pdf" a secas: para Python es un nombre sin extensión, y la
        # conversión decide por la extensión.
        stem, sufijo = "archivo", stem
    if stem.upper() in _RESERVADOS_WINDOWS:
        stem = "_" + stem
    return (stem[:100] or "archivo") + sufijo[:10]


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


def _tamano_parte(tamano_bytes: int, n: int) -> int:
    return min(PARTE_BYTES, tamano_bytes - n * PARTE_BYTES)


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


def _reemplazar(destino: Path, escribir) -> None:
    # Temporal con nombre único y después reemplazar: dos escrituras nunca
    # comparten el temporal (antes sí, y una le borraba el suyo a la otra), y
    # quien lee ve el archivo viejo entero o el nuevo entero, nunca a medias.
    tmp = destino.with_name(f"{destino.name}.{uuid.uuid4().hex}.tmp")
    escribir(tmp)
    os.replace(tmp, destino)


def _escribir(carpeta: Path, meta: dict) -> None:
    datos = json.dumps(meta, ensure_ascii=False)
    _reemplazar(carpeta / "meta.json", lambda tmp: tmp.write_text(datos, "utf-8"))


def _ocupado() -> int:
    if not SUBIDAS_DIR.exists():
        return 0
    total = 0
    for carpeta in SUBIDAS_DIR.iterdir():
        if not carpeta.is_dir():
            continue
        try:
            total += _leer(carpeta)["tamano_bytes"]
        except Exception:
            total += sum(p.stat().st_size for p in carpeta.rglob("*") if p.is_file())
    return total


def abrir(nombre: str, tamano_bytes: int, content_type: str = "") -> dict:
    """Empieza una subida. Devuelve el id y cómo partir el archivo."""
    nombre = nombre or "archivo"
    # Por la extensión y no por el content_type: la conversión decide por la
    # extensión, y un "application/pdf" sin ".pdf" fallaba recién al final,
    # después de que el cliente esperó la subida entera.
    if not (nombre.lower().endswith(".pdf") or document_convert.necesita_conversion(nombre)):
        raise ErrorSubida(422, MENSAJE_FORMATO)
    if tamano_bytes <= 0:
        raise ErrorSubida(422, f"'{nombre}' está vacío")
    if tamano_bytes > MAX_PEDIDO_BYTES:
        raise ErrorSubida(413, f"'{nombre}' supera el máximo de {MAX_PEDIDO_MB} MB")

    with _candado_abrir:
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
    with _candado(id_):
        carpeta = _carpeta(id_)
        meta = _leer(carpeta)
        if meta["estado"] != "subiendo":
            raise ErrorSubida(409, "esta subida ya se completó")
        total = _cantidad_partes(meta["tamano_bytes"])
        if not 0 <= n < total:
            raise ErrorSubida(422, f"la parte {n} no existe: son {total}, de 0 a {total - 1}")
        if len(datos) > PARTE_BYTES:
            raise ErrorSubida(413, "la parte es más grande de lo permitido")
        # Exacto, no "hasta": un pedazo de otro tamaño es un archivo que no se
        # va a poder rearmar, y conviene decirlo ahora y no al final.
        esperado = _tamano_parte(meta["tamano_bytes"], n)
        if len(datos) != esperado:
            raise ErrorSubida(
                422, f"la parte {n} tiene que medir {esperado} bytes y llegaron {len(datos)}")
        _reemplazar(_parte(carpeta, n), lambda tmp: tmp.write_bytes(datos))


def completar(id_: str) -> bool:
    """Cierra la subida. True si ESTA llamada la pasó a 'preparando'.

    Solo en ese caso hay que agendar `preparar`: si la web reintenta el
    "terminé", no se tienen que lanzar dos preparaciones sobre la misma carpeta.
    """
    with _candado(id_):
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

    El trabajo pesado va FUERA del candado (convertir puede tardar minutos y
    la web pregunta el estado mientras tanto). Es seguro porque en
    'preparando' nadie más toca la carpeta: guardar_parte y completar lo
    rechazan, y tomar exige 'reservada'.
    """
    with _candado(id_):
        try:
            carpeta = _carpeta(id_)
            meta = _leer(carpeta)
        except ErrorSubida:
            return
        # El estado sigue en 'preparando' mientras se trabaja, así que eso solo
        # no alcanza: dos preparar() a la vez escribirían el mismo archivo y
        # uno podía terminar contando las páginas de un PDF a medio escribir.
        if meta["estado"] != "preparando" or id_ in _en_preparacion:
            return
        _en_preparacion.add(id_)
    try:
        resultado = {"estado": "listo", **_preparar(carpeta, meta)}
    except ErrorSubida as e:
        resultado = {"estado": "error", "error": e.mensaje}
    except Exception:
        logger.exception("Subida %s: falló la preparación", id_)
        resultado = {"estado": "error", "error": MENSAJE_CONVERSION_FALLIDA}

    with _candado(id_):
        _en_preparacion.discard(id_)
        try:
            carpeta = _carpeta(id_)
            meta = _leer(carpeta)
            if meta["estado"] == "preparando":
                meta.update(resultado)
                _escribir(carpeta, meta)
        except ErrorSubida:
            pass  # la borraron mientras se preparaba: no hay a quién avisarle


def _preparar(carpeta: Path, meta: dict) -> dict:
    # "original" + extensión, y no el nombre del cliente: un archivo llamado
    # "meta.json" o "partes" pisaría lo nuestro. El nombre real se le pone
    # recién al pasarlo a la carpeta del pedido, en tomar().
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
    with _candado(id_):
        meta = _leer(_carpeta(id_))
    return {k: meta.get(k) for k in
            ("id", "nombre", "tamano_bytes", "estado", "paginas", "convertido", "error")}


def reservar(id_: str) -> dict:
    """Aparta una subida lista para UN pedido. Devuelve su estado.

    Es lo que evita que dos pedidos usen el mismo archivo: un doble clic en
    "pagar" manda dos POST /orders casi juntos, y el segundo tiene que
    enterarse de que el primero ya la tomó. Si el pedido no se termina de
    crear, se devuelve con `devolver()`.
    """
    with _candado(id_):
        carpeta = _carpeta(id_)
        meta = _leer(carpeta)
        if meta["estado"] == "error":
            raise ErrorSubida(422, f"'{meta['nombre']}': {meta['error']}")
        if meta["estado"] == "reservada":
            raise ErrorSubida(409, f"'{meta['nombre']}' ya se está usando en otro pedido")
        if meta["estado"] != "listo":
            raise ErrorSubida(409, f"'{meta['nombre']}' todavía no terminó de prepararse")
        meta["estado"] = "reservada"
        _escribir(carpeta, meta)
    return {k: meta.get(k) for k in
            ("id", "nombre", "tamano_bytes", "estado", "paginas", "convertido", "error")}


def devolver(id_: str) -> None:
    """Deshace `reservar`: el pedido falló y la subida tiene que seguir sirviendo."""
    try:
        with _candado(id_):
            carpeta = _carpeta(id_)
            meta = _leer(carpeta)
            if meta["estado"] == "reservada":
                meta["estado"] = "listo"
                _escribir(carpeta, meta)
    except ErrorSubida:
        pass


def _unico(nombre: str, usados: set[str]) -> str:
    candidato, i = nombre, 1
    while candidato in usados:
        candidato = f"{Path(nombre).stem}_{i}{Path(nombre).suffix}"
        i += 1
    usados.add(candidato)
    return candidato


def _enlazar(origen: str, destino: Path) -> None:
    # Enlace y no mover: si el pedido falla después (MercadoPago caído), se
    # borra la carpeta del pedido y la subida sigue intacta para reintentar.
    # Un enlace no ocupa lugar ni tarda; si el disco no los soporta, se copia.
    try:
        os.link(origen, destino)
    except OSError:
        shutil.copy2(origen, destino)


def tomar(id_: str, destino: Path, usados: set[str]) -> dict:
    """Pone los archivos de una subida RESERVADA en la carpeta del pedido.

    Devuelve lo mismo que `_guardar_archivos` en routers/orders.py, así el
    resto de la creación del pedido no se entera de por dónde llegó el
    archivo. `usados` son los nombres ya ocupados en `destino`, para que dos
    documentos con el mismo nombre no se pisen.

    No borra la subida: eso lo hace `liberar()` cuando el pedido ya quedó
    guardado.
    """
    with _candado(id_):
        meta = _leer(_carpeta(id_))
    if meta["estado"] != "reservada":
        raise ErrorSubida(409, f"'{meta['nombre']}' no está reservada para este pedido")

    try:
        destino.mkdir(parents=True, exist_ok=True)
        nombre = _unico(nombre_seguro(meta["nombre"]), usados)
        original = destino / nombre
        _enlazar(meta["original"], original)

        if meta["pdf"] == meta["original"]:
            pdf = original
        else:
            pdf = destino / _unico(Path(nombre).stem + ".pdf", usados)
            _enlazar(meta["pdf"], pdf)
    except OSError as e:
        logger.error("Subida %s: no se pudo pasar al pedido: %s", id_, e)
        raise ErrorSubida(409, f"no pudimos usar '{meta['nombre']}'. Subilo de nuevo, por favor.")

    return {
        "filename_original": meta["nombre"],
        "stored_path": str(original),
        "pdf_path": str(pdf),
        "content_type": meta["content_type"] or None,
        "size_bytes": meta["tamano_bytes"],
        "paginas": meta["paginas"],
    }


def _borrar(id_: str, carpeta: Path) -> None:
    shutil.rmtree(carpeta, ignore_errors=True)
    with _candado_de_candados:
        _candados.pop(id_, None)


def liberar(id_: str) -> None:
    """Borra una subida que ya pasó a un pedido guardado."""
    try:
        with _candado(id_):
            _borrar(id_, _carpeta(id_))
    except ErrorSubida:
        pass


def eliminar(id_: str) -> None:
    """El cliente quitó el documento: se borra ya, sin esperar la limpieza."""
    with _candado(id_):
        carpeta = _carpeta(id_)
        if _leer(carpeta)["estado"] == "reservada":
            raise ErrorSubida(409, "esta subida se está usando en un pedido")
        _borrar(id_, carpeta)


def _ultima_actividad(carpeta: Path) -> float:
    rutas = [carpeta, carpeta / "meta.json", carpeta / "partes"]
    if (carpeta / "partes").is_dir():
        rutas += list((carpeta / "partes").iterdir())
    return max((p.stat().st_mtime for p in rutas if p.exists()), default=0)


def limpiar_viejas(ahora: float | None = None) -> int:
    """Borra las subidas vencidas o abandonadas. Devuelve cuántas borró.

    Vencida: más de VIDA_SEG desde que se abrió. Abandonada: a medio subir y
    sin novedades hace más de INACTIVIDAD_SEG. Las reservadas no se tocan:
    hay un pedido creándose con ellas.
    """
    ahora = time.time() if ahora is None else ahora
    if not SUBIDAS_DIR.exists():
        return 0
    borradas = 0
    for carpeta in SUBIDAS_DIR.iterdir():
        if not carpeta.is_dir():
            continue
        id_ = carpeta.name
        with _candado(id_):
            try:
                meta = _leer(carpeta)
                creado, estado_ = meta["creado"], meta["estado"]
            except Exception:
                # meta.json roto: se usa la fecha de la carpeta
                creado, estado_ = carpeta.stat().st_mtime, "roto"
            if estado_ == "reservada":
                continue
            vencida = ahora - creado > VIDA_SEG
            abandonada = (estado_ == "subiendo"
                          and ahora - _ultima_actividad(carpeta) > INACTIVIDAD_SEG)
            if vencida or abandonada:
                _borrar(id_, carpeta)
                borradas += 1
    return borradas


def marcar_interrumpidas() -> int:
    """Al arrancar: arregla lo que un reinicio dejó a medias. Devuelve cuántas.

    - 'preparando': la preparación murió con el proceso y nadie la va a
      retomar. Sin esto, la web esperaba 10 minutos para nada.
    - 'reservada': el pedido que la estaba usando murió con el proceso. Si
      llegó a guardarse, sus archivos ya están en su carpeta (son enlaces);
      la subida vuelve a 'listo' y la limpieza la borra a su tiempo.
    """
    if not SUBIDAS_DIR.exists():
        return 0
    arregladas = 0
    for carpeta in SUBIDAS_DIR.iterdir():
        try:
            meta = _leer(carpeta)
        except Exception:
            continue
        if meta["estado"] == "preparando":
            meta.update(estado="error", error=MENSAJE_INTERRUMPIDA)
        elif meta["estado"] == "reservada":
            meta["estado"] = "listo"
        else:
            continue
        _escribir(carpeta, meta)
        arregladas += 1
    return arregladas
