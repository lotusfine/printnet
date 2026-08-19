"""Notificaciones por email vía SMTP simple.

Configuración por variables de entorno (ver .env.example). Si PRINTNET_SMTP_HOST
no está definida, el email se "simula": se loggea y se registra en la tabla
notifications con estado='simulado' — así se puede probar el flujo completo
sin un servidor SMTP real.

Emails de Fase 1:
  - "recibido": se dispara al crear el pedido.
  - "listo": hook preparado; se dispara cuando el admin pasa el pedido a
    estado "listo" (PATCH /admin/orders/{id}).
"""

import logging
import os
import smtplib
from email.message import EmailMessage

from database import get_conn

logger = logging.getLogger("printnet.notifications")


def _smtp_config() -> dict:
    return {
        "host": os.environ.get("PRINTNET_SMTP_HOST", ""),
        "port": int(os.environ.get("PRINTNET_SMTP_PORT", "587")),
        "user": os.environ.get("PRINTNET_SMTP_USER", ""),
        "password": os.environ.get("PRINTNET_SMTP_PASSWORD", ""),
        "from": os.environ.get("PRINTNET_SMTP_FROM", "pedidos@printnet.local"),
        "starttls": os.environ.get("PRINTNET_SMTP_STARTTLS", "1") == "1",
    }


def send_email(destinatario: str, asunto: str, cuerpo: str) -> tuple[str, str]:
    """Envía un email. Devuelve (estado, detalle) para registrar en la DB."""
    cfg = _smtp_config()
    if not cfg["host"]:
        detalle = f"SMTP no configurado; email simulado a {destinatario}: {asunto}"
        logger.info(detalle)
        return "simulado", detalle

    msg = EmailMessage()
    msg["From"] = cfg["from"]
    msg["To"] = destinatario
    msg["Subject"] = asunto
    msg.set_content(cuerpo)

    try:
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=20) as smtp:
            if cfg["starttls"]:
                smtp.starttls()
            if cfg["user"]:
                smtp.login(cfg["user"], cfg["password"])
            smtp.send_message(msg)
        return "enviado", ""
    except Exception as exc:  # noqa: BLE001 — el envío nunca debe tirar el request
        logger.error("Error enviando email a %s: %s", destinatario, exc)
        return "error", str(exc)


def _url_seguimiento(token: str) -> str:
    """Link a la página de seguimiento — la que ve el cliente.

    Va a `/estado/{token}` del SITIO, no a `/orders/status/{token}` del backend:
    ese segundo es la API y devuelve datos crudos, ilegibles para una persona.

    Este link es la única forma que tiene el cliente de volver a su pedido
    después de cerrar la pestaña.
    """
    base = os.environ.get("PRINTNET_FRONTEND_URL", "").rstrip("/")
    return f"{base}/estado/{token}" if base else f"(token de seguimiento: {token})"


def _cuerpo_recibido(pedido: dict) -> str:
    precio = (
        f"${pedido['precio_total']:,}".replace(",", ".")
        if pedido["precio_total"] else "a cotizar"
    )
    return (
        f"Hola {pedido['nombre']},\n\n"
        f"Recibimos tu pedido #{pedido['id']} ({pedido['tipo']}).\n"
        f"Total: {precio}\n\n"
        f"Podés seguir el estado de tu pedido en cualquier momento acá:\n"
        f"{_url_seguimiento(pedido['token'])}\n\n"
        f"Guardá este mail: es la forma de volver a encontrar tu pedido.\n\n"
        f"Librería Glaxara · PrintNet"
    )


def _cuerpo_listo(pedido: dict) -> str:
    return (
        f"Hola {pedido['nombre']},\n\n"
        f"¡Tu pedido #{pedido['id']} está listo para retirar!\n\n"
        f"Te esperamos en Librería Glaxara.\n\n"
        f"Detalle de tu pedido:\n"
        f"{_url_seguimiento(pedido['token'])}\n\n"
        f"Librería Glaxara · PrintNet"
    )


def _datos_pedido(order_id: int) -> dict | None:
    conn = get_conn()
    try:
        row = conn.execute(
            """SELECT o.id, o.token, o.tipo, o.estado, o.precio_total,
                      c.nombre, c.email
               FROM orders o JOIN customers c ON c.id = o.customer_id
               WHERE o.id = ?""",
            (order_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def _registrar(order_id: int, tipo: str, destinatario: str, estado: str, detalle: str) -> None:
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO notifications (order_id, tipo, destinatario, estado, detalle)"
            " VALUES (?, ?, ?, ?, ?)",
            (order_id, tipo, destinatario, estado, detalle),
        )
        conn.commit()
    finally:
        conn.close()


def notificar_pedido_recibido(order_id: int) -> None:
    """Email "pedido recibido" — se dispara al crear el pedido."""
    pedido = _datos_pedido(order_id)
    if not pedido:
        return
    estado, detalle = send_email(
        pedido["email"], f"Pedido #{pedido['id']} recibido", _cuerpo_recibido(pedido)
    )
    _registrar(order_id, "recibido", pedido["email"], estado, detalle)


def notificar_pedido_listo(order_id: int) -> None:
    """Email "pedido listo" — hook: lo dispara el PATCH del admin al pasar a 'listo'."""
    pedido = _datos_pedido(order_id)
    if not pedido:
        return
    estado, detalle = send_email(
        pedido["email"],
        f"Pedido #{pedido['id']} listo para retirar",
        _cuerpo_listo(pedido),
    )
    _registrar(order_id, "listo", pedido["email"], estado, detalle)
