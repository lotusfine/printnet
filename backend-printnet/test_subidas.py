"""Tests de la subida en partes (subidas.py).

Correr:  .venv/bin/python test_subidas.py

LO QUE PROTEGE ESTE ARCHIVO: que un archivo partido en pedazos se rearme
EXACTO. Un byte de menos o un pedazo fuera de lugar es un PDF roto que se
cobra mal o no se imprime, y el cliente ya pagó.

Los pedazos se achican a 1000 bytes para probar con archivos de pocos KB; la
lógica no depende del tamaño.
"""

import json
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ["PRINTNET_DB"] = os.path.join(tempfile.mkdtemp(), "subidas.db")
os.environ["PRINTNET_UPLOADS"] = tempfile.mkdtemp()

import document_convert  # noqa: E402
import subidas  # noqa: E402
from generar_pdf_prueba import generar  # noqa: E402

fallos: list[str] = []


def check(nombre: str, obtenido, esperado):
    if obtenido == esperado:
        print(f"  ok  {nombre}")
    else:
        print(f"  FALLA  {nombre}: esperado {esperado}, obtenido {obtenido}")
        fallos.append(nombre)


def status_de(funcion, *args):
    """El status del ErrorSubida que tira `funcion`, o 'no falló'."""
    try:
        funcion(*args)
    except subidas.ErrorSubida as e:
        return e.status
    return "no falló"


subidas.PARTE_BYTES = 1000
PDF = generar(12)  # unos KB: varios pedazos de 1000


def subir(datos: bytes, nombre="doc.pdf", content_type="application/pdf", orden=None) -> str:
    """Abre una subida y manda los pedazos (en `orden`, si se da). Devuelve el id."""
    s = subidas.abrir(nombre, len(datos), content_type)
    indices = list(range(s["partes"])) if orden is None else orden
    for n in indices:
        subidas.guardar_parte(s["id"], n, datos[n * 1000:(n + 1) * 1000])
    return s["id"]


def lista(datos: bytes = PDF, **kw) -> str:
    """Una subida completa y preparada."""
    id_ = subir(datos, **kw)
    subidas.completar(id_)
    subidas.preparar(id_)
    return id_


# ─────────────────────────────────────────────
print("\n== El camino normal ==")

s = subidas.abrir("tesis.pdf", len(PDF), "application/pdf")
check("dice cuántos pedazos mandar", s["partes"], -(-len(PDF) // 1000))
check("y de qué tamaño", s["parte_bytes"], 1000)
for n in range(s["partes"]):
    subidas.guardar_parte(s["id"], n, PDF[n * 1000:(n + 1) * 1000])
check("mientras sube, está 'subiendo'", subidas.estado(s["id"])["estado"], "subiendo")
check("completar la toma", subidas.completar(s["id"]), True)
check("y queda 'preparando'", subidas.estado(s["id"])["estado"], "preparando")
subidas.preparar(s["id"])
e = subidas.estado(s["id"])
check("después queda 'listo'", e["estado"], "listo")
check("con las páginas reales", e["paginas"], 12)
check("un PDF no se convierte", e["convertido"], False)

destino = Path(tempfile.mkdtemp())
a = subidas.tomar(s["id"], destino, set())
check("el archivo rearmado es idéntico al original", Path(a["stored_path"]).read_bytes(), PDF)
check("queda en la carpeta del pedido", Path(a["stored_path"]).parent, destino)
check("con su nombre", Path(a["stored_path"]).name, "tesis.pdf")
check("el PDF a imprimir es el mismo archivo", a["pdf_path"], a["stored_path"])
check("guarda el nombre original", a["filename_original"], "tesis.pdf")
check("y el tamaño", a["size_bytes"], len(PDF))
check("y las páginas", a["paginas"], 12)
check("la subida ya no existe: se usa una sola vez", status_de(subidas.estado, s["id"]), 404)


print("\n== Los pedazos pueden llegar en cualquier orden ==")

partes = -(-len(PDF) // 1000)
id_ = subir(PDF, orden=list(reversed(range(partes))))
subidas.completar(id_)
subidas.preparar(id_)
a = subidas.tomar(id_, Path(tempfile.mkdtemp()), set())
check("al revés también se rearma exacto", Path(a["stored_path"]).read_bytes(), PDF)


print("\n== Reintentar un pedazo lo pisa, no lo duplica ==")

s = subidas.abrir("r.pdf", len(PDF), "application/pdf")
subidas.guardar_parte(s["id"], 0, b"x" * 1000)  # llegó mal
for n in range(s["partes"]):
    subidas.guardar_parte(s["id"], n, PDF[n * 1000:(n + 1) * 1000])
subidas.completar(s["id"])
subidas.preparar(s["id"])
a = subidas.tomar(s["id"], Path(tempfile.mkdtemp()), set())
check("queda lo del último intento", Path(a["stored_path"]).read_bytes(), PDF)


print("\n== Lo que se rechaza al abrir ==")

check("más de 300 MB → 413",
      status_de(subidas.abrir, "g.pdf", subidas.MAX_PEDIDO_BYTES + 1, "application/pdf"), 413)
check("vacío → 422", status_de(subidas.abrir, "v.pdf", 0, "application/pdf"), 422)
check("un formato que no aceptamos → 422",
      status_de(subidas.abrir, "virus.exe", 100, "application/octet-stream"), 422)
check("un Word se acepta (se convierte)",
      status_de(subidas.abrir, "informe.docx", 100, ""), "no falló")


print("\n== Lo que se rechaza al mandar pedazos ==")

s = subidas.abrir("p.pdf", 2500, "application/pdf")  # 3 pedazos: 0, 1, 2
check("pedazo más grande que lo acordado → 413",
      status_de(subidas.guardar_parte, s["id"], 0, b"x" * 1001), 413)
check("pedazo que no existe → 422",
      status_de(subidas.guardar_parte, s["id"], 3, b"x"), 422)
check("número negativo → 422",
      status_de(subidas.guardar_parte, s["id"], -1, b"x"), 422)
check("un id inventado → 404",
      status_de(subidas.guardar_parte, "0" * 32, 0, b"x"), 404)
check("un id con ../ no sale de la carpeta → 404",
      status_de(subidas.guardar_parte, "../../etc", 0, b"x"), 404)


print("\n== Completar ==")

s = subidas.abrir("f.pdf", 2500, "application/pdf")
subidas.guardar_parte(s["id"], 0, b"x" * 1000)
subidas.guardar_parte(s["id"], 2, b"x" * 500)
check("si falta un pedazo → 422", status_de(subidas.completar, s["id"]), 422)
subidas.guardar_parte(s["id"], 1, b"x" * 1000)
check("con todos, completa", subidas.completar(s["id"]), True)
check("completar otra vez no la vuelve a tomar", subidas.completar(s["id"]), False)
check("ya no acepta pedazos → 409",
      status_de(subidas.guardar_parte, s["id"], 0, b"x"), 409)
check("todavía no se puede usar en un pedido → 409",
      status_de(subidas.tomar, s["id"], Path(tempfile.mkdtemp()), set()), 409)


print("\n== Llegó menos de lo anunciado ==")

s = subidas.abrir("corto.pdf", len(PDF), "application/pdf")
for n in range(s["partes"]):
    pedazo = PDF[n * 1000:(n + 1) * 1000]
    if n == s["partes"] - 1:
        pedazo = pedazo[:-10]  # al último le faltan 10 bytes
    subidas.guardar_parte(s["id"], n, pedazo)
subidas.completar(s["id"])
subidas.preparar(s["id"])
e = subidas.estado(s["id"])
check("queda en error", e["estado"], "error")
check("explicando que llegó incompleto", "incompleto" in (e["error"] or ""), True)


print("\n== Documentos que hay que convertir ==")

original_convertir = document_convert.convertir_a_pdf


def convertir_bien(origen, carpeta):
    pdf = Path(carpeta) / (Path(origen).stem + ".pdf")
    pdf.write_bytes(generar(2))
    return document_convert.ConversionResult(ok=True, pdf_path=str(pdf), detalle="convertido")


document_convert.convertir_a_pdf = convertir_bien
id_ = lista(b"PK" + b"z" * 3000, nombre="informe.docx", content_type="")
e = subidas.estado(id_)
check("un Word queda listo", e["estado"], "listo")
check("marcado como convertido", e["convertido"], True)
check("con las páginas del PDF convertido", e["paginas"], 2)
destino = Path(tempfile.mkdtemp())
a = subidas.tomar(id_, destino, set())
check("el original queda con su nombre", Path(a["stored_path"]).name, "informe.docx")
check("y el PDF al lado, con el mismo nombre", Path(a["pdf_path"]).name, "informe.pdf")
check("los dos en la carpeta del pedido", Path(a["pdf_path"]).parent, destino)


def convertir_roto(origen, carpeta):
    return document_convert.ConversionResult(
        ok=False, pdf_path=None, detalle="El documento está dañado.", del_documento=True)


document_convert.convertir_a_pdf = convertir_roto
e = subidas.estado(lista(b"PK" + b"z" * 3000, nombre="roto.docx", content_type=""))
check("un documento dañado queda en error", e["estado"], "error")
check("con el mensaje para el cliente", e["error"], "El documento está dañado.")


def convertir_caido(origen, carpeta):
    return document_convert.ConversionResult(
        ok=False, pdf_path=None, detalle="soffice: timeout en C:\\interno", del_documento=False)


document_convert.convertir_a_pdf = convertir_caido
e = subidas.estado(lista(b"PK" + b"z" * 3000, nombre="otro.docx", content_type=""))
check("si el problema es nuestro, mensaje genérico", e["error"], subidas.MENSAJE_CONVERSION_FALLIDA)
check("sin rutas internas a la vista", "C:\\" in e["error"], False)

document_convert.convertir_a_pdf = original_convertir


print("\n== Dos documentos con el mismo nombre en un pedido ==")

destino = Path(tempfile.mkdtemp())
usados: set[str] = set()
a1 = subidas.tomar(lista(), destino, usados)
a2 = subidas.tomar(lista(), destino, usados)
check("no se pisan", a1["stored_path"] != a2["stored_path"], True)
check("los dos existen", Path(a1["stored_path"]).is_file() and Path(a2["stored_path"]).is_file(), True)


print("\n== Un nombre que choca con los archivos internos ==")

a = subidas.tomar(lista(nombre="meta.json.pdf"), Path(tempfile.mkdtemp()), set())
check("se guarda igual, sin romper la subida", Path(a["stored_path"]).read_bytes(), PDF)


print("\n== Limpieza ==")

vieja = subir(PDF)
nueva = subir(PDF)
meta = subidas.SUBIDAS_DIR / vieja / "meta.json"
datos = json.loads(meta.read_text("utf-8"))
datos["creado"] = time.time() - subidas.VIDA_SEG - 60
meta.write_text(json.dumps(datos), "utf-8")
borradas = subidas.limpiar_viejas()
check("borra la de hace más de 24 h", borradas, 1)
check("ya no existe", (subidas.SUBIDAS_DIR / vieja).exists(), False)
check("la reciente sigue", subidas.estado(nueva)["estado"], "subiendo")


print("\n== Tope de disco ==")

tope_original = subidas.TOPE_DISCO_BYTES
subidas.TOPE_DISCO_BYTES = 1
check("si las subidas en curso llenan el tope → 503",
      status_de(subidas.abrir, "x.pdf", 100, "application/pdf"), 503)
subidas.TOPE_DISCO_BYTES = tope_original


print()
if fallos:
    print(f"✗ {len(fallos)} fallo(s): {', '.join(fallos)}")
    sys.exit(1)
print("✓ todo bien")
