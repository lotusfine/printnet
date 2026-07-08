"""Endpoints públicos: creación de pedidos y consulta de estado por token."""

import json
import logging
import re
import sqlite3
import uuid
from pathlib import Path

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from pydantic import TypeAdapter, ValidationError

import notifications
import pricing
from database import UPLOADS_DIR, get_db
from models import Pedido, PedidoFotocopias, PedidoFotos
from print_dispatch import get_dispatcher

logger = logging.getLogger("printnet.orders")
router = APIRouter()

_pedido_adapter = TypeAdapter(Pedido)

MAX_FILE_BYTES = 50 * 1024 * 1024  # 50 MB por archivo

IMAGEN_CT = re.compile(r"^image/")


def _nombre_seguro(nombre: str) -> str:
    base = Path(nombre).name
    return re.sub(r"[^\w.\- ]", "_", base) or "archivo"


def _contar_paginas_pdf(path: Path) -> int | None:
    try:
        from pypdf import PdfReader

        return len(PdfReader(str(path)).pages)
    except Exception:
        return None


def _es_pdf(f: UploadFile) -> bool:
    return (f.content_type == "application/pdf") or f.filename.lower().endswith(".pdf")


def _es_imagen(f: UploadFile) -> bool:
    return bool(f.content_type and IMAGEN_CT.match(f.content_type))


def _guardar_archivos(token: str, files: list[UploadFile]) -> list[dict]:
    """Guarda los uploads en uploads/{token}/ y devuelve su metadata."""
    destino = UPLOADS_DIR / token
    destino.mkdir(parents=True, exist_ok=True)
    guardados = []
    usados: set[str] = set()

    for f in files:
        nombre = _nombre_seguro(f.filename or "archivo")
        # evitar colisiones si suben dos archivos con el mismo nombre
        candidato, i = nombre, 1
        while candidato in usados:
            stem, suffix = Path(nombre).stem, Path(nombre).suffix
            candidato = f"{stem}_{i}{suffix}"
            i += 1
        usados.add(candidato)

        path = destino / candidato
        data = f.file.read(MAX_FILE_BYTES + 1)
        if len(data) > MAX_FILE_BYTES:
            raise HTTPException(413, f"'{nombre}' supera el máximo de 50 MB")
        path.write_bytes(data)

        guardados.append(
            {
                "filename_original": f.filename or nombre,
                "stored_path": str(path),
                "content_type": f.content_type,
                "size_bytes": len(data),
                "paginas": _contar_paginas_pdf(path) if _es_pdf(f) else None,
            }
        )
    return guardados


def _upsert_customer(db: sqlite3.Connection, contacto) -> int:
    """Reutiliza el cliente por email (actualizando nombre/teléfono) o lo crea."""
    row = db.execute(
        "SELECT id FROM customers WHERE email = ?", (contacto.email,)
    ).fetchone()
    if row:
        db.execute(
            "UPDATE customers SET nombre = ?, telefono = ? WHERE id = ?",
            (contacto.nombre, contacto.telefono, row["id"]),
        )
        return row["id"]
    cur = db.execute(
        "INSERT INTO customers (nombre, telefono, email) VALUES (?, ?, ?)",
        (contacto.nombre, contacto.telefono, contacto.email),
    )
    return cur.lastrowid


@router.post("/orders", status_code=201)
def crear_pedido(
    background: BackgroundTasks,
    datos: str = Form(..., description="JSON del pedido (ver SPEC.md)"),
    files: list[UploadFile] = File(...),
    db: sqlite3.Connection = Depends(get_db),
):
    # 1) Validar el payload JSON contra el contrato
    try:
        pedido = _pedido_adapter.validate_python(json.loads(datos))
    except json.JSONDecodeError:
        raise HTTPException(422, "el campo 'datos' no es JSON válido")
    except ValidationError as e:
        errores = [
            {"campo": ".".join(str(p) for p in err["loc"]), "error": err["msg"]}
            for err in e.errors()
        ]
        raise HTTPException(422, errores)

    # 2) Validar archivos según el tipo de pedido
    if isinstance(pedido, PedidoFotocopias):
        if len(files) != 1:
            raise HTTPException(422, "un pedido de fotocopias lleva exactamente 1 archivo PDF")
        if not _es_pdf(files[0]):
            raise HTTPException(422, "el archivo debe ser un PDF")
    else:  # PedidoFotos
        if not files:
            raise HTTPException(422, "un pedido de fotos lleva al menos 1 archivo")
        for f in files:
            if not (_es_pdf(f) or _es_imagen(f)):
                raise HTTPException(422, f"'{f.filename}': solo se aceptan imágenes o PDF")

    # 3) Guardar archivos y contar páginas reales
    token = str(uuid.uuid4())
    archivos = _guardar_archivos(token, files)

    # 4) Precio + triage según tipo
    if isinstance(pedido, PedidoFotocopias):
        paginas_doc = archivos[0]["paginas"]
        if paginas_doc is None:
            raise HTTPException(422, "no se pudo leer el PDF para contar sus páginas")
        try:
            paginas_a_cobrar = pricing.paginas_del_rango(
                pedido.rango.modo, pedido.rango.valor, paginas_doc
            )
        except ValueError as e:
            raise HTTPException(422, str(e))
        precio_total = pricing.calcular_precio_fotocopias(
            paginas_a_cobrar,
            pedido.opciones.copias,
            pedido.opciones.color,
            pedido.opciones.caras,
            pedido.opciones.tamano,
        )
        requiere_manual = bool(pedido.terminaciones)
        opciones_json = {
            "opciones": pedido.opciones.model_dump(),
            "rango": pedido.rango.model_dump(),
            "terminaciones": pedido.terminaciones,
            "paginas_documento": paginas_doc,
            "paginas_a_imprimir": paginas_a_cobrar,
        }
    else:
        precio_total = None  # los pedidos especiales se cotizan manualmente
        requiere_manual = True
        opciones_json = {
            "material": pedido.material,
            "formato": pedido.formato,
            "gramaje": pedido.gramaje,
            "terminaciones": pedido.terminaciones,
        }

    # 5) Persistir cliente + pedido + archivos
    customer_id = _upsert_customer(db, pedido.contacto)
    cur = db.execute(
        """INSERT INTO orders (token, tipo, customer_id, estado, pagado,
                               requiere_manual, precio_total, opciones)
           VALUES (?, ?, ?, 'pendiente', 1, ?, ?, ?)""",
        (token, pedido.tipo, customer_id, int(requiere_manual), precio_total,
         json.dumps(opciones_json)),
    )
    order_id = cur.lastrowid

    file_ids = []
    for a in archivos:
        fcur = db.execute(
            """INSERT INTO files (order_id, filename_original, stored_path,
                                  content_type, size_bytes, paginas)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (order_id, a["filename_original"], a["stored_path"],
             a["content_type"], a["size_bytes"], a["paginas"]),
        )
        file_ids.append(fcur.lastrowid)

    # 6) Dispatch automático SOLO para fotocopias (decisión de arquitectura 2)
    estado = "pendiente"
    printer_id = None
    if isinstance(pedido, PedidoFotocopias):
        printer = db.execute(
            "SELECT id, nombre FROM printers WHERE estado = 'activa' ORDER BY id LIMIT 1"
        ).fetchone()
        if printer:
            dispatcher = get_dispatcher()
            resultado = dispatcher.dispatch(
                printer["nombre"], archivos[0]["stored_path"], opciones_json
            )
            db.execute(
                """INSERT INTO dispatch_log (order_id, printer_id, file_id,
                                             dispatcher, ok, detalle)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (order_id, printer["id"], file_ids[0], dispatcher.nombre,
                 int(resultado.ok), resultado.detalle),
            )
            if resultado.ok:
                estado = "imprimiendo"
                printer_id = printer["id"]
        else:
            logger.warning(
                "Pedido %s sin despachar: no hay impresoras activas", order_id
            )

    db.execute(
        "UPDATE orders SET estado = ?, printer_id = ?, updated_at = datetime('now') WHERE id = ?",
        (estado, printer_id, order_id),
    )

    # Commit explícito ANTES de responder: libera el lock de escritura para que
    # la tarea de fondo (email) pueda escribir en notifications sin bloquearse.
    db.commit()

    # 7) Email "pedido recibido" en background (no bloquea la respuesta)
    background.add_task(notifications.notificar_pedido_recibido, order_id)

    return {
        "id": order_id,
        "token": token,
        "tipo": pedido.tipo,
        "estado": estado,
        "pagado": True,
        "precio_total": precio_total,
        "requiere_manual": requiere_manual,
        "archivos": [a["filename_original"] for a in archivos],
        "paginas": archivos[0]["paginas"] if pedido.tipo == "fotocopias" else None,
    }


@router.get("/orders/status/{token}")
def estado_pedido(token: str, db: sqlite3.Connection = Depends(get_db)):
    """Consulta pública por token (UUID v4, no adivinable). Sin login."""
    row = db.execute(
        """SELECT o.token, o.tipo, o.estado, o.precio_total, o.requiere_manual,
                  o.created_at, o.updated_at
           FROM orders o WHERE o.token = ?""",
        (token,),
    ).fetchone()
    if not row:
        raise HTTPException(404, "pedido no encontrado")

    archivos = [
        r["filename_original"]
        for r in db.execute(
            "SELECT f.filename_original FROM files f"
            " JOIN orders o ON o.id = f.order_id WHERE o.token = ?",
            (token,),
        )
    ]
    return {
        "token": row["token"],
        "tipo": row["tipo"],
        "estado": row["estado"],
        "precio_total": row["precio_total"],
        "archivos": archivos,
        "creado": row["created_at"],
        "actualizado": row["updated_at"],
    }
