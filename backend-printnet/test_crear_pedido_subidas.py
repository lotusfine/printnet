"""Tests de crear_pedido con archivos que llegaron por la subida en partes.

Correr:  .venv/bin/python test_crear_pedido_subidas.py

Se llama a la función del endpoint directo, sin HTTP (no hay httpx a
propósito). Sin MP_ACCESS_TOKEN el backend está en modo fantasma: el pedido
nace pagado, que es lo que se necesita para probar sin MercadoPago.

LO QUE PROTEGE: que un pedido rechazado (por ejemplo, un rango de páginas que
no existe) NO consuma la subida. Con un archivo de 300 MB, perderla obliga al
cliente a esperar la subida entera de nuevo.
"""

import json
import os
import sys
import tempfile
import threading
from pathlib import Path

os.environ["PRINTNET_DB"] = os.path.join(tempfile.mkdtemp(), "pedidos.db")
os.environ["PRINTNET_UPLOADS"] = tempfile.mkdtemp()
os.environ.pop("MP_ACCESS_TOKEN", None)

import database  # noqa: E402
import payments  # noqa: E402
import subidas  # noqa: E402
from fastapi import BackgroundTasks, HTTPException  # noqa: E402
from generar_pdf_prueba import generar  # noqa: E402
from routers.orders import crear_pedido  # noqa: E402

database.init_db()
subidas.PARTE_BYTES = 1000

fallos: list[str] = []


def check(nombre: str, obtenido, esperado):
    if obtenido == esperado:
        print(f"  ok  {nombre}")
    else:
        print(f"  FALLA  {nombre}: esperado {esperado}, obtenido {obtenido}")
        fallos.append(nombre)


def subida_lista(paginas: int, nombre: str = "doc.pdf") -> str:
    datos = generar(paginas)
    s = subidas.abrir(nombre, len(datos), "application/pdf")
    for n in range(s["partes"]):
        subidas.guardar_parte(s["id"], n, datos[n * 1000:(n + 1) * 1000])
    subidas.completar(s["id"])
    subidas.preparar(s["id"])
    return s["id"]


def datos(cantidad: int, tipo: str = "fotocopias", rango=None) -> str:
    contacto = {"nombre": "Ana", "telefono": "+5492211234567", "email": "ana@x.com"}
    if tipo == "fotos":
        return json.dumps({"tipo": "fotos", "contacto": contacto, "material": "opalina"})
    doc = {
        "opciones": {"color": "byn", "caras": "simple", "copias": 1, "tamano": "A4"},
        "rango": rango or {"modo": "todas", "valor": ""},
        "terminaciones": [],
    }
    return json.dumps({"tipo": tipo, "contacto": contacto, "documentos": [doc] * cantidad})


def pedir(datos_json: str, uploads=None, files=None):
    """Llama al endpoint. Devuelve la respuesta, o el HTTPException si rechazó."""
    conn = database.get_conn()
    try:
        r = crear_pedido(background=BackgroundTasks(), datos=datos_json,
                         files=files, uploads=uploads, db=conn)
        conn.commit()
        return r
    except HTTPException as e:
        conn.rollback()
        return e
    finally:
        conn.close()


def status(r):
    return r.status_code if isinstance(r, HTTPException) else 201


# ─────────────────────────────────────────────
print("\n== Un pedido con dos documentos subidos en partes ==")

a, b = subida_lista(3, "a.pdf"), subida_lista(5, "b.pdf")
r = pedir(datos(2), uploads=json.dumps([a, b]))
check("se crea", status(r), 201)
check("cuenta las páginas del primero", r["paginas"], 3)
check("con los dos archivos", r["archivos"], ["a.pdf", "b.pdf"])
check("y tiene precio", r["precio_total"] > 0, True)
check("las subidas se consumieron", subidas.SUBIDAS_DIR.joinpath(a).exists(), False)

conn = database.get_conn()
filas = conn.execute(
    "SELECT f.stored_path, f.paginas FROM files f JOIN orders o ON o.id = f.order_id"
    " WHERE o.token = ? ORDER BY f.id", (r["token"],)
).fetchall()
conn.close()
check("quedan dos filas en files", len(filas), 2)
check("en la carpeta del pedido", all(Path(f["stored_path"]).parent.name == r["token"] for f in filas), True)
check("y los archivos existen", all(Path(f["stored_path"]).is_file() for f in filas), True)
check("con sus páginas", [f["paginas"] for f in filas], [3, 5])


print("\n== Un pedido rechazado NO consume la subida ==")

c = subida_lista(3)
r = pedir(datos(1, rango={"modo": "rango", "valor": "50-60"}), uploads=json.dumps([c]))
check("un rango que no existe se rechaza", status(r), 422)
check("y la subida sigue lista para reintentar", subidas.estado(c)["estado"], "listo")
r = pedir(datos(1), uploads=json.dumps([c]))
check("corrigiendo el rango, la misma subida sirve", status(r), 201)


print("\n== Lo que se rechaza ==")

d = subida_lista(2)
check("cantidad de subidas distinta de documentos → 422",
      status(pedir(datos(2), uploads=json.dumps([d]))), 422)
check("la misma subida dos veces → 422",
      status(pedir(datos(2), uploads=json.dumps([d, d]))), 422)
check("uploads que no es JSON → 422", status(pedir(datos(1), uploads="no-json")), 422)
check("uploads que no es una lista → 422", status(pedir(datos(1), uploads='{"a": 1}')), 422)
check("files y uploads juntos → 422",
      status(pedir(datos(1), uploads=json.dumps([d]), files=["algo"])), 422)
check("una subida inexistente → 404",
      status(pedir(datos(1), uploads=json.dumps(["0" * 32]))), 404)
check("fotos por subida en partes → 422",
      status(pedir(datos(1, tipo="fotos"), uploads=json.dumps([d]))), 422)

e = subidas.abrir("sin-terminar.pdf", 500, "application/pdf")["id"]
check("una subida que no terminó de prepararse → 409",
      status(pedir(datos(1), uploads=json.dumps([e]))), 409)

tope = subidas.MAX_PEDIDO_BYTES
f1, f2 = subida_lista(2), subida_lista(2)
subidas.MAX_PEDIDO_BYTES = subidas.estado(f1)["tamano_bytes"] + 1  # entra uno, no los dos
r = pedir(datos(2), uploads=json.dumps([f1, f2]))
check("si la suma pasa el máximo → 413", status(r), 413)
check("y las subidas no se tocaron", subidas.estado(f1)["estado"], "listo")
subidas.MAX_PEDIDO_BYTES = tope

check("sin archivos ni subidas, un pedido de fotocopias → 422",
      status(pedir(datos(1))), 422)




def en_paralelo(funcion, veces: int) -> list:
    resultados = [None] * veces
    largada = threading.Barrier(veces)

    def correr(i):
        largada.wait()
        resultados[i] = funcion(i)

    hilos = [threading.Thread(target=correr, args=(i,)) for i in range(veces)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    return resultados


def carpetas_de_pedidos() -> set[str]:
    return {p.name for p in database.UPLOADS_DIR.iterdir() if p.name != "_subidas"}


print("\n== MercadoPago caído: el cliente NO pierde lo que subió ==")

modo_real, crear_real = payments.modo_mercadopago, payments.crear_preferencia
payments.modo_mercadopago = lambda: True


def mp_caido(**kw):
    raise RuntimeError("MercadoPago no responde")


payments.crear_preferencia = mp_caido
g = subida_lista(3)
antes = carpetas_de_pedidos()
r = pedir(datos(1), uploads=json.dumps([g]))
check("el pago no arranca → 502", status(r), 502)
check("la subida sigue lista para reintentar", subidas.estado(g)["estado"], "listo")
check("no queda una carpeta de pedido huérfana", carpetas_de_pedidos(), antes)

payments.crear_preferencia = lambda **kw: {"preference_id": "pref-1", "init_point": "https://mp/ok"}
r = pedir(datos(1), uploads=json.dumps([g]))
check("reintentando con MercadoPago de vuelta, se crea", status(r), 201)
check("y va al pago", r["init_point"], "https://mp/ok")
check("recién ahí la subida se libera", subidas.SUBIDAS_DIR.joinpath(g).exists(), False)
payments.modo_mercadopago, payments.crear_preferencia = modo_real, crear_real


print("\n== Doble clic en pagar (la prueba hostil) ==")

a, b = subida_lista(2, "a.pdf"), subida_lista(2, "b.pdf")
r = en_paralelo(lambda i: status(pedir(datos(2), uploads=json.dumps([a, b]))), 6)
check("de 6 pedidos iguales a la vez, se crea uno", r.count(201), 1)
check("los demás reciben 409, ninguno 500", sorted(set(r) - {201}), [409])


print("\n== Dos pedidos cruzados con las mismas subidas ==")

c, d = subida_lista(2, "c.pdf"), subida_lista(2, "d.pdf")
orden = [[c, d], [d, c]]
r = en_paralelo(lambda i: status(pedir(datos(2), uploads=json.dumps(orden[i]))), 2)
check("como mucho uno se crea, y ninguno da 500", 500 in r, False)
if 201 not in r:
    check("si chocaron los dos, las subidas siguen sirviendo",
          (subidas.estado(c)["estado"], subidas.estado(d)["estado"]), ("listo", "listo"))
    check("y un pedido después anda", status(pedir(datos(2), uploads=json.dumps([c, d]))), 201)


print("\n== Una subida que quedó en error ==")

import document_convert  # noqa: E402

convertir_real = document_convert.convertir_a_pdf
document_convert.convertir_a_pdf = lambda o, c: document_convert.ConversionResult(
    ok=False, pdf_path=None, detalle="El documento está dañado.", del_documento=True)
w = subidas.abrir("roto.docx", 1500, "")["id"]
subidas.guardar_parte(w, 0, b"z" * 1000)
subidas.guardar_parte(w, 1, b"z" * 500)
subidas.completar(w)
subidas.preparar(w)
document_convert.convertir_a_pdf = convertir_real
r = pedir(datos(1), uploads=json.dumps([w]))
check("da 422, no 'todavía no terminó'", status(r), 422)
check("con el error de verdad", "dañado" in str(r.detail), True)


print("\n== uploads vacío junto con files ==")

r = pedir(datos(1), uploads="[]", files=[])
check("'[]' no cuenta como mandar las dos cosas", "no los dos" in str(getattr(r, "detail", "")), False)


print()
if fallos:
    print(f"✗ {len(fallos)} fallo(s): {', '.join(fallos)}")
    sys.exit(1)
print("✓ todo bien")
