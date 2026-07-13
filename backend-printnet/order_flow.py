"""Flujo post-pago: lo que pasa cuando un pedido queda efectivamente pagado.

Esta lógica vivía inline en routers/orders.py (creación con pago fantasma).
Se extrajo acá para que la disparen, SIN duplicarla:
  - la creación del pedido en modo fantasma (sin MP_ACCESS_TOKEN), y
  - el webhook de MercadoPago cuando el pago queda "approved".

Hace exactamente lo mismo que en Fase 1: triage (fotocopias → dispatch
simulado automático; fotos → manual), registro en dispatch_log y transición
de estado. El email "pedido recibido" lo agenda el caller (necesita
BackgroundTasks del request).
"""

import json
import logging
import sqlite3

from print_dispatch import get_dispatcher

logger = logging.getLogger("printnet.order_flow")


def confirmar_pago(conn: sqlite3.Connection, order_id: int) -> str:
    """Marca el pedido como pagado y ejecuta el triage. Devuelve el estado final.

    Idempotente: si el pedido ya estaba pagado (webhook repetido de
    MercadoPago), no vuelve a despachar ni cambia nada.
    """
    order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if order is None:
        raise ValueError(f"pedido {order_id} inexistente")
    if order["pagado"]:
        return order["estado"]

    opciones = json.loads(order["opciones"])
    estado = "pendiente"
    printer_id = None

    if order["tipo"] == "fotocopias":
        printer = conn.execute(
            "SELECT id, nombre FROM printers WHERE estado = 'activa' ORDER BY id LIMIT 1"
        ).fetchone()
        archivo = conn.execute(
            "SELECT id, stored_path FROM files WHERE order_id = ? ORDER BY id LIMIT 1",
            (order_id,),
        ).fetchone()
        if printer and archivo:
            dispatcher = get_dispatcher()
            resultado = dispatcher.dispatch(
                printer["nombre"], archivo["stored_path"], opciones
            )
            conn.execute(
                """INSERT INTO dispatch_log (order_id, printer_id, file_id,
                                             dispatcher, ok, detalle)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (order_id, printer["id"], archivo["id"], dispatcher.nombre,
                 int(resultado.ok), resultado.detalle),
            )
            if resultado.ok:
                estado = "imprimiendo"
                printer_id = printer["id"]
        else:
            logger.warning(
                "Pedido %s sin despachar: no hay impresoras activas", order_id
            )

    conn.execute(
        "UPDATE orders SET pagado = 1, estado = ?, printer_id = ?,"
        " updated_at = datetime('now') WHERE id = ?",
        (estado, printer_id, order_id),
    )
    return estado
