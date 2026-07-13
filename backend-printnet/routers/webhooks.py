"""Webhook de MercadoPago.

Recibe las notificaciones de pago de Checkout Pro, valida la firma
(x-signature, HMAC-SHA256 con MP_WEBHOOK_SECRET) y consulta el estado real
del pago contra la API de MercadoPago antes de tocar el pedido.

- pago "approved"  → order_flow.confirmar_pago(): el MISMO flujo post-pago
  de siempre (triage, dispatch simulado, email "recibido").
- pago "rejected"/"cancelled" → estado 'pago_rechazado', sin disparar nada.

Responde 200 rápido en todos los casos válidos (límite de 22s de MercadoPago;
acá el único trabajo es un GET a MP + un UPDATE).
"""

import logging
import os
import sqlite3

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request

import notifications
import payments
from database import get_db
from order_flow import confirmar_pago

logger = logging.getLogger("printnet.webhooks")
router = APIRouter()

ESTADOS_RECHAZO = {"rejected", "cancelled"}


@router.post("/webhooks/mercadopago")
async def webhook_mercadopago(
    request: Request,
    background: BackgroundTasks,
    db: sqlite3.Connection = Depends(get_db),
):
    secret = os.environ.get("MP_WEBHOOK_SECRET", "")
    data_id = request.query_params.get("data.id", "")

    if not payments.validar_firma(
        request.headers.get("x-signature", ""),
        request.headers.get("x-request-id", ""),
        data_id,
        secret,
    ):
        logger.warning(
            "Webhook MP rechazado por firma inválida (data.id=%s, ip=%s, secret_configurado=%s)",
            data_id,
            request.client.host if request.client else "?",
            bool(secret),
        )
        raise HTTPException(401, "firma inválida")

    # Solo nos interesan las notificaciones de pago
    tipo = request.query_params.get("type", "")
    if not tipo:
        try:
            tipo = (await request.json()).get("type", "")
        except Exception:  # noqa: BLE001 — body vacío o no-JSON
            tipo = ""
    if tipo != "payment" or not data_id:
        return {"ok": True, "ignorado": tipo or "sin tipo"}

    # Estado real del pago según MercadoPago (nunca confiar en el body)
    try:
        pago = payments.obtener_pago(data_id)
    except Exception as exc:  # noqa: BLE001
        logger.error("No se pudo consultar el pago %s en MP: %s", data_id, exc)
        # 500 para que MercadoPago reintente la notificación
        raise HTTPException(500, "no se pudo consultar el pago")

    referencia = pago.get("external_reference") or ""
    status = pago.get("status") or ""

    order = db.execute(
        "SELECT id, estado, pagado FROM orders WHERE token = ?", (referencia,)
    ).fetchone()
    if not order:
        logger.warning("Webhook MP: pago %s sin pedido (ref=%s)", data_id, referencia)
        return {"ok": True, "ignorado": "pedido inexistente"}

    db.execute(
        "UPDATE orders SET mp_payment_id = ? WHERE id = ?", (data_id, order["id"])
    )

    if status == "approved":
        ya_pagado = bool(order["pagado"])
        estado = confirmar_pago(db, order["id"])  # idempotente ante reintentos
        db.commit()
        if not ya_pagado:
            background.add_task(notifications.notificar_pedido_recibido, order["id"])
        logger.info("Pago %s aprobado → pedido %s en '%s'", data_id, order["id"], estado)
        return {"ok": True, "estado": estado}

    if status in ESTADOS_RECHAZO:
        # Solo si todavía no estaba pagado (un rechazo posterior no des-paga)
        db.execute(
            "UPDATE orders SET estado = 'pago_rechazado', updated_at = datetime('now')"
            " WHERE id = ? AND pagado = 0",
            (order["id"],),
        )
        db.commit()
        logger.info("Pago %s rechazado → pedido %s", data_id, order["id"])
        return {"ok": True, "estado": "pago_rechazado"}

    # pending / in_process / etc.: no cambiar nada todavía
    logger.info("Pago %s en estado '%s': sin acción", data_id, status)
    return {"ok": True, "estado": status}
