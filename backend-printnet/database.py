"""Capa de datos de PrintNet: SQLite con SQL crudo.

Sin ORM a propósito: el backend corre en una Raspberry Pi 3B+ (1GB RAM)
y sqlite3 de la biblioteca estándar es suficiente y determinístico.
Las "migraciones" son el esquema idempotente (CREATE TABLE IF NOT EXISTS);
cambios futuros de esquema se agregan como sentencias ALTER numeradas
en MIGRACIONES.
"""

import os
import sqlite3
import sys
from pathlib import Path


def _base_dir() -> Path:
    """Directorio base de datos/uploads/.env.

    Congelado con PyInstaller: junto al ejecutable (NO en _MEIPASS, el
    directorio temporal de extracción, que se borra al cerrar el proceso).
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


BASE_DIR = _base_dir()
DB_PATH = Path(os.environ.get("PRINTNET_DB", BASE_DIR / "printnet.db"))
UPLOADS_DIR = Path(os.environ.get("PRINTNET_UPLOADS", BASE_DIR / "uploads"))

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS customers (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre     TEXT NOT NULL,
    telefono   TEXT NOT NULL,
    email      TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_customers_email ON customers(email);

CREATE TABLE IF NOT EXISTS printers (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre      TEXT NOT NULL,
    tipo        TEXT NOT NULL CHECK (tipo IN ('laser', 'tinta')),
    estado      TEXT NOT NULL DEFAULT 'activa' CHECK (estado IN ('activa', 'error')),
    error_tipo  TEXT,
    hojas       INTEGER NOT NULL DEFAULT 0,
    -- % de tóner (laser) o tinta (tinta), según tipo
    consumible  INTEGER NOT NULL DEFAULT 100,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS orders (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    token           TEXT NOT NULL UNIQUE,
    tipo            TEXT NOT NULL CHECK (tipo IN ('fotocopias', 'fotos')),
    customer_id     INTEGER NOT NULL REFERENCES customers(id),
    estado          TEXT NOT NULL DEFAULT 'pendiente'
                    CHECK (estado IN ('pendiente_pago', 'pago_rechazado', 'pendiente',
                                      'imprimiendo', 'listo', 'entregado', 'cancelado')),
    pagado          INTEGER NOT NULL DEFAULT 0,
    requiere_manual INTEGER NOT NULL DEFAULT 0,
    -- NULL para pedidos de /fotos: se cotizan manualmente
    precio_total    INTEGER,
    -- JSON con las opciones específicas del tipo de pedido (ver SPEC.md)
    opciones        TEXT NOT NULL,
    printer_id      INTEGER REFERENCES printers(id),
    -- MercadoPago Checkout Pro
    mp_preference_id TEXT,
    mp_payment_id    TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_orders_token ON orders(token);
CREATE INDEX IF NOT EXISTS idx_orders_estado ON orders(estado);

CREATE TABLE IF NOT EXISTS files (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id          INTEGER NOT NULL REFERENCES orders(id),
    filename_original TEXT NOT NULL,
    stored_path       TEXT NOT NULL,
    content_type      TEXT,
    size_bytes        INTEGER,
    -- páginas contadas con pypdf; NULL si no es PDF o no se pudo leer
    paginas           INTEGER,
    created_at        TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_files_order ON files(order_id);

CREATE TABLE IF NOT EXISTS dispatch_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id    INTEGER NOT NULL REFERENCES orders(id),
    printer_id  INTEGER REFERENCES printers(id),
    file_id     INTEGER REFERENCES files(id),
    dispatcher  TEXT NOT NULL,
    ok          INTEGER NOT NULL,
    detalle     TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS notifications (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id     INTEGER NOT NULL REFERENCES orders(id),
    tipo         TEXT NOT NULL CHECK (tipo IN ('recibido', 'listo')),
    destinatario TEXT NOT NULL,
    estado       TEXT NOT NULL CHECK (estado IN ('enviado', 'simulado', 'error')),
    detalle      TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

# Migraciones incrementales: lista de (version, sql). Se aplican en orden
# y se registra la última versión aplicada en user_version de SQLite.

# v1 — MercadoPago: nuevos estados (pendiente_pago, pago_rechazado) y columnas
# mp_preference_id / mp_payment_id. SQLite no permite modificar un CHECK, así
# que se recrea la tabla copiando los datos. Idempotente también en DBs recién
# creadas (copia sobre el mismo esquema).
_MIGRACION_1 = """
PRAGMA foreign_keys = OFF;

CREATE TABLE orders_v1 (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    token           TEXT NOT NULL UNIQUE,
    tipo            TEXT NOT NULL CHECK (tipo IN ('fotocopias', 'fotos')),
    customer_id     INTEGER NOT NULL REFERENCES customers(id),
    estado          TEXT NOT NULL DEFAULT 'pendiente'
                    CHECK (estado IN ('pendiente_pago', 'pago_rechazado', 'pendiente',
                                      'imprimiendo', 'listo', 'entregado', 'cancelado')),
    pagado          INTEGER NOT NULL DEFAULT 0,
    requiere_manual INTEGER NOT NULL DEFAULT 0,
    precio_total    INTEGER,
    opciones        TEXT NOT NULL,
    printer_id      INTEGER REFERENCES printers(id),
    mp_preference_id TEXT,
    mp_payment_id    TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

INSERT INTO orders_v1 (id, token, tipo, customer_id, estado, pagado,
                       requiere_manual, precio_total, opciones, printer_id,
                       created_at, updated_at)
    SELECT id, token, tipo, customer_id, estado, pagado,
           requiere_manual, precio_total, opciones, printer_id,
           created_at, updated_at
    FROM orders;

DROP TABLE orders;
ALTER TABLE orders_v1 RENAME TO orders;

CREATE INDEX IF NOT EXISTS idx_orders_token ON orders(token);
CREATE INDEX IF NOT EXISTS idx_orders_estado ON orders(estado);

PRAGMA foreign_keys = ON;
"""

MIGRACIONES: list[tuple[int, str]] = [
    (1, _MIGRACION_1),
]

# La impresora del local. El nombre tiene que ser EXACTAMENTE el que le da
# Windows: el despachador lo saca de acá y se lo pasa a SumatraPDF, que
# compara carácter por carácter. Si no coincide, el pedido falla con un error
# que no menciona que el problema sea el nombre.
#
# Configurable por si se cambia de equipo o se prueba en otra máquina.
IMPRESORA_LOCAL = os.environ.get("PRINTNET_IMPRESORA", "RICOH IM C4500 PCL 6")

SEED_PRINTERS = [
    (IMPRESORA_LOCAL, "laser", "activa", None, 0, 100),
]


def get_conn() -> sqlite3.Connection:
    # check_same_thread=False: FastAPI puede abrir la conexión y ejecutar el
    # handler en hilos distintos del threadpool. Cada conexión se usa por un
    # solo request a la vez, así que es seguro.
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    # Espera hasta 5s si otra conexión tiene el lock (requests + tareas de fondo)
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def get_db():
    """Dependencia FastAPI: una conexión por request, commit al salir."""
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    conn = get_conn()
    try:
        # WAL: lecturas concurrentes con la escritura; ideal para SQLite en la Pi
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(SCHEMA)

        version = conn.execute("PRAGMA user_version").fetchone()[0]
        for nueva_version, sql in MIGRACIONES:
            if nueva_version > version:
                conn.executescript(sql)
                conn.execute(f"PRAGMA user_version = {nueva_version}")

        if conn.execute("SELECT COUNT(*) FROM printers").fetchone()[0] == 0:
            conn.executemany(
                "INSERT INTO printers (nombre, tipo, estado, error_tipo, hojas, consumible)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                SEED_PRINTERS,
            )
        conn.commit()
    finally:
        conn.close()
