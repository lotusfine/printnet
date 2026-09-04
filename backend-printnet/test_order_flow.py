"""Tests del flujo post-pago con varios documentos.

Correr:  .venv/bin/python test_order_flow.py

LO QUE PROTEGE ESTE ARCHIVO: un pedido donde un documento se imprimió y otro
no. El cliente ya pagó, así que no se puede "bloquear el pago" — el papel de
los que salieron ya se gastó. Lo único razonable es que el operador se entere
antes de entregarlo, o el cliente se lleva dos documentos de tres y se da
cuenta en su casa.

Por eso un despacho parcial marca el pedido como `requiere_manual`, que es el
mismo mecanismo que ya usan los pedidos con terminaciones.
"""

import json
import os
import sqlite3
import sys
import tempfile

os.environ["PRINTNET_DB"] = os.path.join(tempfile.mkdtemp(), "flujo.db")
os.environ["PRINTNET_UPLOADS"] = tempfile.mkdtemp()

import database  # noqa: E402
import print_dispatch  # noqa: E402
from order_flow import confirmar_pago  # noqa: E402

fallos: list[str] = []


def check(nombre: str, obtenido, esperado):
    if obtenido == esperado:
        print(f"  ok  {nombre}")
    else:
        print(f"  FALLA  {nombre}: esperado {esperado}, obtenido {obtenido}")
        fallos.append(nombre)


class DispatcherFalso(print_dispatch.PrintDispatcher):
    """Falla con los archivos cuyo nombre contenga 'roto'."""

    nombre = "falso"

    def dispatch(self, printer_nombre, file_path, options):
        if "roto" in file_path:
            return print_dispatch.DispatchResult(False, f"falló a propósito: {file_path}")
        return print_dispatch.DispatchResult(True, f"ok: {file_path}")


print_dispatch._DISPATCHERS["falso"] = DispatcherFalso
os.environ["PRINTNET_DISPATCH"] = "falso"

database.init_db()


_contador = [0]


def armar_pedido(archivos: list[str], documentos: list[dict] | None = None) -> int:
    """Crea un pedido pagado-pendiente con esos archivos. Devuelve su id."""
    _contador[0] += 1
    n = _contador[0]
    conn = database.get_conn()
    cur = conn.execute(
        "INSERT INTO customers (nombre, telefono, email) VALUES (?, ?, ?)",
        ("Ana", "+5492211234567", f"ana{n}@x.com"),
    )
    customer_id = cur.lastrowid
    opciones = {"opciones": {"color": "byn", "caras": "simple", "copias": 1, "tamano": "A4"},
                "rango": {"modo": "todas", "valor": ""}}
    if documentos:
        opciones["documentos"] = documentos
    cur = conn.execute(
        """INSERT INTO orders (token, tipo, customer_id, estado, pagado,
                               requiere_manual, precio_total, opciones)
           VALUES (?, 'fotocopias', ?, 'pendiente_pago', 0, 0, 1000, ?)""",
        (f"tok-{n}", customer_id, json.dumps(opciones)),
    )
    order_id = cur.lastrowid
    for a in archivos:
        conn.execute(
            """INSERT INTO files (order_id, filename_original, stored_path, pdf_path)
               VALUES (?, ?, ?, ?)""",
            (order_id, a, f"/tmp/{a}", f"/tmp/{a}"),
        )
    conn.commit()
    conn.close()
    return order_id


def leer(order_id: int) -> sqlite3.Row:
    conn = database.get_conn()
    row = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    despachos = conn.execute(
        "SELECT ok FROM dispatch_log WHERE order_id = ? ORDER BY id", (order_id,)
    ).fetchall()
    conn.close()
    return row, [d["ok"] for d in despachos]


# ─────────────────────────────────────────────
print("\n== Todos los documentos imprimen ==")

pid = armar_pedido(["a.pdf", "b.pdf", "c.pdf"])
conn = database.get_conn()
estado = confirmar_pago(conn, pid)
conn.commit(); conn.close()
row, despachos = leer(pid)

check("el pedido queda imprimiendo", estado, "imprimiendo")
check("se despachó uno por documento", len(despachos), 3)
check("los tres salieron bien", despachos, [1, 1, 1])
check("NO requiere atención manual", bool(row["requiere_manual"]), False)


print("\n== Uno de tres falla (el caso que importa) ==")

pid = armar_pedido(["a.pdf", "roto.pdf", "c.pdf"])
conn = database.get_conn()
estado = confirmar_pago(conn, pid)
conn.commit(); conn.close()
row, despachos = leer(pid)

check("el pedido igual queda imprimiendo: dos ya salieron", estado, "imprimiendo")
check("quedan registrados los tres intentos", len(despachos), 3)
check("con el del medio fallado", despachos, [1, 0, 1])
check("y el pedido REQUIERE atención manual", bool(row["requiere_manual"]), True)


print("\n== Fallan todos ==")

pid = armar_pedido(["roto1.pdf", "roto2.pdf"])
conn = database.get_conn()
estado = confirmar_pago(conn, pid)
conn.commit(); conn.close()
row, despachos = leer(pid)

check("no queda imprimiendo, porque no salió nada", estado, "pendiente")
check("requiere atención manual", bool(row["requiere_manual"]), True)
check("y el pedido igual queda pagado", bool(row["pagado"]), True)


print("\n== Un solo documento, como los pedidos de siempre ==")

pid = armar_pedido(["unico.pdf"])
conn = database.get_conn()
estado = confirmar_pago(conn, pid)
conn.commit(); conn.close()
row, despachos = leer(pid)

check("imprime normal", estado, "imprimiendo")
check("un solo despacho", len(despachos), 1)
check("sin atención manual", bool(row["requiere_manual"]), False)


print("\n== Idempotencia: el webhook de MP puede llegar dos veces ==")

pid = armar_pedido(["x.pdf", "y.pdf"])
conn = database.get_conn()
confirmar_pago(conn, pid)
conn.commit()
segundo = confirmar_pago(conn, pid)
conn.commit(); conn.close()
row, despachos = leer(pid)

check("la segunda vez devuelve el estado sin re-despachar", segundo, "imprimiendo")
check("no se duplicaron los despachos", len(despachos), 2)


# ─────────────────────────────────────────────
# ─────────────────────────────────────────────
print("\n== Reimprimir ==")
# El operador tiene que poder volver a mandar un pedido a la impresora. Sin
# esto, un pedido que falló quedaba muerto: la impresión se dispara una sola
# vez, al confirmar el pago, y esa función es idempotente a propósito.

from order_flow import reimprimir  # noqa: E402

pid = armar_pedido(["a.pdf", "roto.pdf"])
conn = database.get_conn()
confirmar_pago(conn, pid)
conn.commit()
row, despachos = leer(pid)
check("después del pago hay 2 intentos", len(despachos), 2)

# Reintento de TODO el pedido
r = reimprimir(conn, pid)
conn.commit(); conn.close()
row, despachos = leer(pid)
check("reimprimir todo agrega 2 intentos más", len(despachos), 4)
check("informa cuántos entraron", r["despachados"], 1)
check("y cuántos fallaron", r["fallados"], 1)

# Reintento de UN documento
conn = database.get_conn()
fid = conn.execute(
    "SELECT id FROM files WHERE order_id = ? AND filename_original = 'a.pdf'", (pid,)
).fetchone()["id"]
r = reimprimir(conn, pid, file_ids=[fid])
conn.commit(); conn.close()
row, despachos = leer(pid)
check("reimprimir uno solo agrega un intento", len(despachos), 5)
check("y despacha solo ese", r["despachados"], 1)

# Un pedido cancelado tiene que poder reimprimirse: era un callejón sin salida
conn = database.get_conn()
pid2 = armar_pedido(["x.pdf"])
confirmar_pago(conn, pid2)
conn.execute("UPDATE orders SET estado = 'cancelado' WHERE id = ?", (pid2,))
conn.commit()
r = reimprimir(conn, pid2)
conn.commit(); conn.close()
row, _ = leer(pid2)
check("un pedido cancelado se puede reimprimir", r["despachados"], 1)
check("y vuelve a estar en curso", row["estado"], "imprimiendo")

# Reimprimir lo que salió bien limpia la marca de atención manual
conn = database.get_conn()
pid3 = armar_pedido(["bien.pdf"])
confirmar_pago(conn, pid3)
conn.execute("UPDATE orders SET requiere_manual = 1 WHERE id = ?", (pid3,))
conn.commit()
reimprimir(conn, pid3)
conn.commit(); conn.close()
row, _ = leer(pid3)
check("si todo sale bien, deja de requerir atención", bool(row["requiere_manual"]), False)

# Errores
conn = database.get_conn()
try:
    reimprimir(conn, 99999)
    check("un pedido inexistente da error", "no falló", "ValueError")
except ValueError:
    check("un pedido inexistente da error", True, True)
conn.close()

print()
if fallos:
    print(f"✗ {len(fallos)} fallo(s): {', '.join(fallos)}")
    sys.exit(1)
print("✓ todos los tests del flujo post-pago pasaron")
