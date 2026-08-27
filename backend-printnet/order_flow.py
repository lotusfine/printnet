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
    # Un despacho que falla después del pago no se puede "cancelar": el papel
    # de los documentos que sí salieron ya se gastó. Lo único razonable es que
    # el operador se entere antes de entregar el pedido.
    atencion_manual = False

    if order["tipo"] == "fotocopias":
        printer = conn.execute(
            "SELECT id, nombre FROM printers WHERE estado = 'activa' ORDER BY id LIMIT 1"
        ).fetchone()
        # Se imprime el PDF, no el original: si el cliente subió un PowerPoint,
        # pdf_path apunta al convertido. En archivos que ya venían en PDF las
        # dos rutas coinciden; el COALESCE cubre las filas viejas, anteriores a
        # que existiera la columna.
        archivos = conn.execute(
            "SELECT id, COALESCE(pdf_path, stored_path) AS stored_path"
            " FROM files WHERE order_id = ? ORDER BY id",
            (order_id,),
        ).fetchall()

        # Cada documento tiene su propia configuración de impresión. En pedidos
        # viejos, opciones["documentos"] no existe y hay una sola configuración
        # para todo el pedido: el fallback la reusa para el único archivo.
        docs = opciones.get("documentos")

        if printer and archivos:
            dispatcher = get_dispatcher()
            despachados = 0
            for i, archivo in enumerate(archivos):
                config = docs[i] if docs and i < len(docs) else opciones
                resultado = dispatcher.dispatch(
                    printer["nombre"], archivo["stored_path"], config
                )
                conn.execute(
                    """INSERT INTO dispatch_log (order_id, printer_id, file_id,
                                                 dispatcher, ok, detalle)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (order_id, printer["id"], archivo["id"], dispatcher.nombre,
                     int(resultado.ok), resultado.detalle),
                )
                if resultado.ok:
                    despachados += 1

            # Basta con que uno haya entrado para que el pedido esté en curso.
            # Los que fallaron quedan en dispatch_log y el operador los ve ahí.
            if despachados:
                estado = "imprimiendo"
                printer_id = printer["id"]
            if despachados < len(archivos):
                atencion_manual = True
                logger.error(
                    "Pedido %s: se despacharon %d de %d documentos — queda "
                    "marcado para revisión del operador",
                    order_id, despachados, len(archivos),
                )
        else:
            logger.warning(
                "Pedido %s sin despachar: no hay impresoras activas", order_id
            )

    conn.execute(
        "UPDATE orders SET pagado = 1, estado = ?, printer_id = ?,"
        " requiere_manual = requiere_manual OR ?,"
        " updated_at = datetime('now') WHERE id = ?",
        (estado, printer_id, int(atencion_manual), order_id),
    )
    return estado
