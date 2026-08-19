"""Endpoints del panel de administración.

Protegidos por token: la dependencia va en el router, no endpoint por
endpoint, así cubre también los que se agreguen más adelante. Ver `auth.py`
para el porqué y para qué pasa si el token no está configurado.

El shape de respuesta de GET /admin/orders replica lo que la UI de /admin
ya espera para pintar sus OrderCards: cliente, archivo, paginas, copias,
color (bool), doble (bool), acabado, precio, estado, hace (minutos),
contacto {tel, email} — más los campos nuevos del backend (tipo, token,
requiere_manual, rango, material/formato/gramaje).
"""

import json
import sqlite3
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

import notifications
from auth import verificar_admin
from database import get_db
from models import ESTADOS, CambioEstado

router = APIRouter(prefix="/admin", dependencies=[Depends(verificar_admin)])

# Transiciones de estado permitidas. Las transiciones DE pago (pendiente_pago
# → pagado/pago_rechazado) las maneja exclusivamente el webhook de MercadoPago;
# el admin solo puede cancelar pedidos atascados en esos estados.
TRANSICIONES = {
    "pendiente_pago": {"cancelado"},
    "pago_rechazado": {"cancelado"},
    "pendiente": {"imprimiendo", "listo", "cancelado"},
    "imprimiendo": {"listo", "cancelado"},
    "listo": {"entregado", "cancelado"},
    "entregado": set(),
    "cancelado": set(),
}


def _minutos_desde(fecha_utc: str) -> int:
    creado = datetime.fromisoformat(fecha_utc).replace(tzinfo=timezone.utc)
    return max(0, int((datetime.now(timezone.utc) - creado).total_seconds() // 60))


def _shape_admin(db: sqlite3.Connection, order: sqlite3.Row) -> dict:
    opciones = json.loads(order["opciones"])
    archivos = [
        r["filename_original"]
        for r in db.execute(
            "SELECT filename_original FROM files WHERE order_id = ?", (order["id"],)
        )
    ]
    terminaciones = opciones.get("terminaciones") or []

    base = {
        "id": order["id"],
        "token": order["token"],
        "tipo": order["tipo"],
        "cliente": order["nombre"],
        "archivo": archivos[0] if archivos else None,
        "archivos": archivos,
        "precio": order["precio_total"],
        "estado": order["estado"],
        "pagado": bool(order["pagado"]),
        "requiere_manual": bool(order["requiere_manual"]),
        "hace": _minutos_desde(order["created_at"]),
        "acabado": " · ".join(terminaciones) if terminaciones else None,
        "contacto": {"tel": order["telefono"], "email": order["email"]},
        "creado": order["created_at"],
        "actualizado": order["updated_at"],
    }

    if order["tipo"] == "fotocopias":
        ops = opciones["opciones"]
        rango = opciones.get("rango") or {}
        base.update(
            {
                "paginas": opciones.get("paginas_documento"),
                "paginas_a_imprimir": opciones.get("paginas_a_imprimir"),
                "copias": ops["copias"],
                "color": ops["color"] == "color",
                "doble": ops["caras"] == "doble",
                "tamano": ops["tamano"],
                "rango": rango.get("valor") if rango.get("modo") == "rango" else None,
                "material": None,
                "formato": None,
                "gramaje": None,
            }
        )
    else:
        base.update(
            {
                "paginas": None,
                "paginas_a_imprimir": None,
                "copias": None,
                "color": None,
                "doble": None,
                "tamano": None,
                "rango": None,
                "material": opciones.get("material"),
                "formato": opciones.get("formato"),
                "gramaje": opciones.get("gramaje"),
            }
        )
    return base


_ORDER_QUERY = """
    SELECT o.*, c.nombre, c.telefono, c.email
    FROM orders o JOIN customers c ON c.id = o.customer_id
"""


@router.get("/orders")
def listar_pedidos(
    estado: str | None = Query(None, description="Filtrar por estado"),
    db: sqlite3.Connection = Depends(get_db),
):
    if estado is not None and estado not in ESTADOS:
        raise HTTPException(422, f"estado inválido; opciones: {', '.join(ESTADOS)}")

    sql, params = _ORDER_QUERY, []
    if estado:
        sql += " WHERE o.estado = ?"
        params.append(estado)
    sql += " ORDER BY o.created_at DESC, o.id DESC"

    return [_shape_admin(db, row) for row in db.execute(sql, params)]


@router.patch("/orders/{order_id}")
def cambiar_estado(
    order_id: int,
    cambio: CambioEstado,
    background: BackgroundTasks,
    db: sqlite3.Connection = Depends(get_db),
):
    row = db.execute(
        _ORDER_QUERY + " WHERE o.id = ?", (order_id,)
    ).fetchone()
    if not row:
        raise HTTPException(404, "pedido no encontrado")

    actual, nuevo = row["estado"], cambio.estado
    if nuevo == actual:
        return _shape_admin(db, row)
    if nuevo not in TRANSICIONES[actual]:
        raise HTTPException(
            409,
            f"transición inválida: {actual} → {nuevo}. "
            f"Permitidas desde '{actual}': {sorted(TRANSICIONES[actual]) or 'ninguna'}",
        )

    db.execute(
        "UPDATE orders SET estado = ?, updated_at = datetime('now') WHERE id = ?",
        (nuevo, order_id),
    )
    # Commit explícito antes de responder: libera el lock para la tarea de fondo
    db.commit()

    # Hook "pedido listo" (decisión de arquitectura 5)
    if nuevo == "listo":
        background.add_task(notifications.notificar_pedido_listo, order_id)

    actualizado = db.execute(_ORDER_QUERY + " WHERE o.id = ?", (order_id,)).fetchone()
    return _shape_admin(db, actualizado)


@router.get("/printers")
def listar_impresoras(db: sqlite3.Connection = Depends(get_db)):
    """Impresoras con el shape que espera el sidebar de /admin."""
    resultado = []
    for p in db.execute("SELECT * FROM printers ORDER BY id"):
        item = {
            "id": p["id"],
            "nombre": p["nombre"],
            "tipo": p["tipo"],
            "estado": p["estado"],
            "errorTipo": p["error_tipo"],
            "hojas": p["hojas"],
            "papel": p["hojas"],
        }
        # la UI usa la clave "tonner" para laser y "tinta" para tinta
        item["tonner" if p["tipo"] == "laser" else "tinta"] = p["consumible"]
        resultado.append(item)
    return resultado
