"""Flujo post-pago: lo que pasa cuando un pedido queda efectivamente pagado.

Esta lógica vivía inline en routers/orders.py (creación con pago fantasma).
Se extrajo acá para que la disparen, SIN duplicarla:
  - la creación del pedido en modo fantasma (sin MP_ACCESS_TOKEN),
  - el webhook de MercadoPago cuando el pago queda "approved", y
  - el botón de reimprimir del panel de operador.

El email "pedido recibido" lo agenda el caller (necesita BackgroundTasks del
request).
"""

import json
import logging
import sqlite3

from print_dispatch import get_dispatcher

logger = logging.getLogger("printnet.order_flow")


def _archivos_del_pedido(conn, order_id, file_ids=None):
    """Archivos a imprimir, con el PDF ya resuelto.

    Se imprime el PDF, no el original: si el cliente subió un PowerPoint,
    pdf_path apunta al convertido. En archivos que ya venían en PDF las dos
    rutas coinciden; el COALESCE cubre las filas anteriores a esa columna.
    """
    sql = ("SELECT id, COALESCE(pdf_path, stored_path) AS ruta"
           " FROM files WHERE order_id = ?")
    params = [order_id]
    if file_ids:
        sql += f" AND id IN ({','.join('?' * len(file_ids))})"
        params += list(file_ids)
    return conn.execute(sql + " ORDER BY id", params).fetchall()


def despachar_pedido(conn: sqlite3.Connection, order_id: int, file_ids=None) -> dict:
    """Manda los documentos del pedido a la impresora.

    Lo usa tanto la confirmación de pago como el botón de reimprimir. Con
    `file_ids` se reimprime solo esos documentos — útil cuando de tres falló
    uno solo y no tiene sentido gastar papel en los otros dos.

    Devuelve {despachados, fallados, total}. Cada intento, salga bien o mal,
    queda en dispatch_log: si el cliente reclama, el historial muestra cuántas
    veces se intentó y cuándo.
    """
    order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if order is None:
        raise ValueError(f"pedido {order_id} inexistente")

    opciones = json.loads(order["opciones"])
    printer = conn.execute(
        "SELECT id, nombre FROM printers WHERE estado = 'activa' ORDER BY id LIMIT 1"
    ).fetchone()
    archivos = _archivos_del_pedido(conn, order_id, file_ids)

    if not printer or not archivos:
        if not printer:
            logger.warning("Pedido %s sin despachar: no hay impresoras activas", order_id)
        return {"despachados": 0, "fallados": 0, "total": 0}

    # Cada documento tiene su propia configuración. En pedidos anteriores a
    # varios documentos no existe la clave y hay una sola para todo el pedido.
    docs = opciones.get("documentos")
    # El índice tiene que ser el del documento dentro del PEDIDO, no dentro de
    # la selección: si se reimprime solo el tercero, le corresponde su propia
    # configuración y no la del primero.
    posicion = {f["id"]: i for i, f in enumerate(_archivos_del_pedido(conn, order_id))}

    dispatcher = get_dispatcher()
    despachados = 0
    for archivo in archivos:
        i = posicion.get(archivo["id"], 0)
        config = docs[i] if docs and i < len(docs) else opciones
        resultado = dispatcher.dispatch(printer["nombre"], archivo["ruta"], config)
        conn.execute(
            """INSERT INTO dispatch_log (order_id, printer_id, file_id,
                                         dispatcher, ok, detalle)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (order_id, printer["id"], archivo["id"], dispatcher.nombre,
             int(resultado.ok), resultado.detalle),
        )
        if resultado.ok:
            despachados += 1

    fallados = len(archivos) - despachados
    if fallados:
        logger.error(
            "Pedido %s: se despacharon %d de %d documentos — queda marcado "
            "para revisión del operador",
            order_id, despachados, len(archivos),
        )

    return {"despachados": despachados, "fallados": fallados, "total": len(archivos)}


def reimprimir(conn: sqlite3.Connection, order_id: int, file_ids=None) -> dict:
    """Vuelve a mandar un pedido a la impresora, desde cualquier estado.

    Incluido `cancelado`: sin esto, un pedido cancelado por error quedaba
    muerto para siempre, porque de ese estado no sale ninguna transición.

    Si después de reimprimir no quedó ningún documento fallado, se limpia la
    marca de atención manual — el problema que la había puesto ya se resolvió.
    """
    resultado = despachar_pedido(conn, order_id, file_ids)

    if resultado["despachados"]:
        pendientes = conn.execute(
            """SELECT COUNT(*) FROM files f
                WHERE f.order_id = ?
                  AND NOT EXISTS (SELECT 1 FROM dispatch_log d
                                   WHERE d.file_id = f.id AND d.ok = 1)""",
            (order_id,),
        ).fetchone()[0]
        conn.execute(
            "UPDATE orders SET estado = 'imprimiendo', requiere_manual = ?,"
            " updated_at = datetime('now') WHERE id = ?",
            (int(bool(pendientes)), order_id),
        )
    return resultado


def confirmar_pago(conn: sqlite3.Connection, order_id: int) -> str:
    """Marca el pedido como pagado y ejecuta el triage. Devuelve el estado final.

    Idempotente: si el pedido ya estaba pagado (webhook repetido de
    MercadoPago), no vuelve a despachar ni cambia nada. Para volver a imprimir
    a propósito está `reimprimir()`.
    """
    order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if order is None:
        raise ValueError(f"pedido {order_id} inexistente")
    if order["pagado"]:
        return order["estado"]

    estado = "pendiente"
    printer_id = None
    # Un despacho que falla después del pago no se puede "cancelar": el papel
    # de los documentos que sí salieron ya se gastó. Lo único razonable es que
    # el operador se entere antes de entregar el pedido.
    atencion_manual = False

    if order["tipo"] == "fotocopias":
        r = despachar_pedido(conn, order_id)
        if r["despachados"]:
            estado = "imprimiendo"
            printer = conn.execute(
                "SELECT id FROM printers WHERE estado = 'activa' ORDER BY id LIMIT 1"
            ).fetchone()
            printer_id = printer["id"] if printer else None
        atencion_manual = bool(r["fallados"])

    conn.execute(
        "UPDATE orders SET pagado = 1, estado = ?, printer_id = ?,"
        " requiere_manual = requiere_manual OR ?,"
        " updated_at = datetime('now') WHERE id = ?",
        (estado, printer_id, int(atencion_manual), order_id),
    )
    return estado
