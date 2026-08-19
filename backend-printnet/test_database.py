"""Tests del armado inicial de la base.

Correr:  .venv/bin/python test_database.py
(sin pytest a propósito, igual que el resto)

Lo que importa acá: en una base nueva tiene que quedar UNA impresora activa y
su nombre tiene que ser exactamente el que Windows le da a la Ricoh. El
despachador toma ese nombre de la base y se lo pasa a SumatraPDF, que compara
carácter por carácter — si no coincide, el pedido falla sin que el mensaje
diga que el problema es un nombre mal escrito.
"""

import importlib
import os
import sys
import tempfile

fallos: list[str] = []


def check(nombre: str, obtenido, esperado):
    if obtenido == esperado:
        print(f"  ok  {nombre}")
    else:
        print(f"  FALLA  {nombre}: esperado {esperado}, obtenido {obtenido}")
        fallos.append(nombre)


def base_nueva(impresora: str | None = None):
    """Crea una base desde cero y devuelve sus impresoras."""
    carpeta = tempfile.mkdtemp()
    os.environ["PRINTNET_DB"] = os.path.join(carpeta, "t.db")
    if impresora is None:
        os.environ.pop("PRINTNET_IMPRESORA", None)
    else:
        os.environ["PRINTNET_IMPRESORA"] = impresora

    # database.py lee las env vars al importarse: hay que recargarlo.
    import database
    importlib.reload(database)
    database.init_db()

    conn = database.get_conn()
    filas = conn.execute(
        "SELECT nombre, tipo, estado FROM printers ORDER BY id"
    ).fetchall()
    conn.close()
    return [tuple(f) for f in filas]


RICOH = "RICOH IM C4500 PCL 6"

print("\n== Impresora sembrada en una base nueva ==")

filas = base_nueva()
check("se siembra una sola impresora", len(filas), 1)
check("es la Ricoh, con el nombre exacto de Windows", filas[0][0], RICOH)
check("nace activa (si no, ningún pedido se despacha)", filas[0][2], "activa")
check("es láser", filas[0][1], "laser")

print("\n== El nombre se puede cambiar sin tocar el código ==")

filas = base_nueva("OTRA IMPRESORA X1")
check("PRINTNET_IMPRESORA manda sobre el default",
      filas[0][0], "OTRA IMPRESORA X1")

print("\n== Ya no quedan impresoras de mentira ==")

filas = base_nueva()
nombres = [f[0] for f in filas]
check("no está la HP de la maqueta", "HP LaserJet 1" in nombres, False)
check("no está la Epson de la maqueta", "Epson L3250" in nombres, False)

print()
if fallos:
    print(f"✗ {len(fallos)} fallo(s): {', '.join(fallos)}")
    sys.exit(1)
print("✓ todos los tests de base pasaron")
