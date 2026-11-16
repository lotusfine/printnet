"""Flujo post-pago: lo que pasa cuando un pedido queda efectivamente pagado.

Esta lógica vivía inline en routers/orders.py (creación con pago fantasma).
Se extrajo acá para que la disparen, SIN duplicarla:
  - la creación del pedido en modo fantasma (sin MP_ACCESS_TOKEN),
  - el webhook de MercadoPago cuando el pago queda "approved", y
  - el botón de reimprimir del panel de operador.

El despacho (`despachar_tras_pago`) y el email "pedido recibido" los agenda el
caller en segundo plano, DESPUÉS de hacer commit de `confirmar_pago`: así el
webhook responde enseguida y un reintento de MercadoPago ve el pedido pagado.
"""

import json
import logging
import sqlite3

from database import get_conn
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
        # Commit por documento, no al final. Si algo revienta en el tercero,
        # el historial de los dos que ya salieron queda (antes el rollback lo
        # borraba y reimprimir volvía a mandarlos). Y la base no queda trabada
        # para los demás pedidos mientras SumatraPDF abre un PDF de 300 MB.
        conn.commit()
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


def confirmar_pago(conn: sqlite3.Connection, order_id: int) -> bool:
    """Marca el pedido como pagado. Devuelve True si ESTA llamada lo marcó.

    NO imprime. El caller hace commit y, si dio True, agenda
    `despachar_tras_pago` en segundo plano.

    Antes imprimía acá adentro, o sea adentro del webhook de MercadoPago, y
    `pagado = 1` recién se guardaba al final. Con un PDF grande el webhook
    pasaba los 22 s de MP (y los 100 s de Cloudflare), MP reintentaba, y el
    reintento no veía el pedido pagado: lo imprimía OTRA VEZ. Ahora la marca
    es un UPDATE condicional y se guarda antes de imprimir: de dos
    confirmaciones, aunque lleguen juntas, gana una sola.
    """
    existe = conn.execute("SELECT 1 FROM orders WHERE id = ?", (order_id,)).fetchone()
    if existe is None:
        raise ValueError(f"pedido {order_id} inexistente")
    cur = conn.execute(
        "UPDATE orders SET pagado = 1, estado = 'pendiente',"
        " updated_at = datetime('now') WHERE id = ? AND pagado = 0",
        (order_id,),
    )
    return cur.rowcount == 1


def despachar_tras_pago(order_id: int) -> str:
    """Imprime un pedido recién pagado y deja su estado al día. Devuelve el estado.

    Corre en segundo plano, después de que el request ya respondió, así que
    abre su PROPIA conexión: la del request ya está cerrada.

    Los pedidos de fotos no se imprimen solos: se cotizan y se hacen en el
    mostrador, así que quedan en 'pendiente'.
    """
    conn = get_conn()
    try:
        order = conn.execute(
            "SELECT tipo, estado FROM orders WHERE id = ?", (order_id,)
        ).fetchone()
        if order is None:
            raise ValueError(f"pedido {order_id} inexistente")
        if order["tipo"] != "fotocopias":
            return order["estado"]

        r = despachar_pedido(conn, order_id)
        estado = "pendiente"
        printer_id = None
        if r["despachados"]:
            estado = "imprimiendo"
            printer = conn.execute(
                "SELECT id FROM printers WHERE estado = 'activa' ORDER BY id LIMIT 1"
            ).fetchone()
            printer_id = printer["id"] if printer else None

        # Solo si sigue en 'pendiente': mientras se imprimía, el operador pudo
        # haberlo cancelado o marcado listo, y eso no se pisa.
        conn.execute(
            "UPDATE orders SET estado = ?, printer_id = ?, updated_at = datetime('now')"
            " WHERE id = ? AND estado = 'pendiente'",
            (estado, printer_id, order_id),
        )
        # Un despacho que falla después del pago no se puede "cancelar": el
        # papel de los documentos que sí salieron ya se gastó. Lo único
        # razonable es que el operador se entere antes de entregar el pedido.
        if r["fallados"]:
            conn.execute(
                "UPDATE orders SET requiere_manual = 1 WHERE id = ?", (order_id,)
            )
        conn.commit()
        return estado
    except Exception:
        conn.rollback()
        logger.exception("Pedido %s: falló el despacho tras el pago", order_id)
        # El cliente ya pagó: que el panel lo muestre para reimprimirlo a mano.
        try:
            conn.execute("UPDATE orders SET requiere_manual = 1 WHERE id = ?", (order_id,))
            conn.commit()
        except Exception:
            logger.exception("Pedido %s: tampoco se pudo marcar para revisión", order_id)
        # Sin relanzar: corre como tarea de fondo, y Starlette corta las
        # tareas siguientes cuando una tira excepción. Relanzando, un despacho
        # fallido se llevaba puesto el email "pedido recibido" del cliente.
        return "pendiente"
    finally:
        conn.close()


def marcar_despachos_interrumpidos(conn: sqlite3.Connection) -> int:
    """Al arrancar: pedidos pagados que se quedaron sin imprimir. Devuelve cuántos.

    El pago se guarda y la impresión corre después, en segundo plano. Si el
    servicio se reinicia en ese intervalo (un deploy, un corte de luz), la
    impresión no corre nunca: MercadoPago ya recibió su 200 y no reintenta.
    El pedido quedaría en 'pendiente' igual que uno en cola, sin que nadie se
    entere.

    Se marcan para el operador en vez de reimprimirlos solos: si el proceso
    murió con SumatraPDF ya trabajando, el papel puede haber salido aunque el
    registro no, y reimprimir a ciegas sería cobrar una vez e imprimir dos.
    """
    cur = conn.execute(
        """UPDATE orders SET requiere_manual = 1, updated_at = datetime('now')
            WHERE tipo = 'fotocopias' AND pagado = 1 AND estado = 'pendiente'
              AND requiere_manual = 0
              AND NOT EXISTS (SELECT 1 FROM dispatch_log d WHERE d.order_id = orders.id)"""
    )
    if cur.rowcount:
        logger.warning(
            "%d pedido(s) pagado(s) se quedaron sin imprimir por un reinicio: "
            "quedan marcados para revisión en el panel", cur.rowcount,
        )
    return cur.rowcount
