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

print("\n== Migraciones ==")

import sqlite3  # noqa: E402
import tempfile  # noqa: E402

carpeta = tempfile.mkdtemp()
os.environ["PRINTNET_DB"] = os.path.join(carpeta, "nueva.db")
os.environ.pop("PRINTNET_IMPRESORA", None)
import database  # noqa: E402
importlib.reload(database)
database.init_db()

conn = sqlite3.connect(os.environ["PRINTNET_DB"])
version = conn.execute("PRAGMA user_version").fetchone()[0]
columnas = [c[1] for c in conn.execute("PRAGMA table_info(files)")]
conn.close()

check("una base nueva queda marcada en la última versión",
      version, database.MIGRACIONES[-1][0])
check("la tabla de archivos tiene la columna del PDF convertido",
      "pdf_path" in columnas, True)

# Volver a arrancar sobre la misma base no debe romper: es lo que pasa cada vez
# que se reinicia el backend.
database.init_db()
check("arrancar dos veces sobre la misma base no falla", True, True)

print("\n== Migrar una base vieja (el caso de la notebook) ==")
# La notebook tiene una base creada antes de que existiera pdf_path. Al
# actualizar, la migración tiene que agregar la columna sin perder los pedidos.

vieja = os.path.join(tempfile.mkdtemp(), "vieja.db")
conn = sqlite3.connect(vieja)
conn.executescript("""
CREATE TABLE files (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id          INTEGER NOT NULL,
    filename_original TEXT NOT NULL,
    stored_path       TEXT NOT NULL,
    content_type      TEXT,
    size_bytes        INTEGER,
    paginas           INTEGER,
    created_at        TEXT NOT NULL DEFAULT (datetime('now'))
);
INSERT INTO files (order_id, filename_original, stored_path, paginas)
    VALUES (1, 'apunte.pdf', 'C:/uploads/apunte.pdf', 12);
PRAGMA user_version = 1;
""")
conn.commit()
conn.close()

os.environ["PRINTNET_DB"] = vieja
importlib.reload(database)
database.init_db()

conn = sqlite3.connect(vieja)
columnas = [c[1] for c in conn.execute("PRAGMA table_info(files)")]
fila = conn.execute("SELECT stored_path, pdf_path, paginas FROM files").fetchone()
version = conn.execute("PRAGMA user_version").fetchone()[0]
conn.close()

check("se agrega la columna nueva", "pdf_path" in columnas, True)
check("no se pierde el archivo que ya estaba", fila[2], 12)
check("a los archivos viejos, el PDF es el mismo original", fila[1], fila[0])
check("y la base queda en la última versión", version, database.MIGRACIONES[-1][0])

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
