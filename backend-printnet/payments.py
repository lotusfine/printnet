"""Integración con MercadoPago Checkout Pro.

HTTP directo con `requests` (sin SDK): es más liviano para la Raspberry Pi y
son solo dos llamadas (crear preferencia y consultar pago).

Variables de entorno (ver .env.example — NUNCA hardcodear credenciales):
  MP_ACCESS_TOKEN        token privado (TEST-... para credenciales de prueba)
  MP_WEBHOOK_SECRET      clave secreta para validar la firma x-signature
  BASE_URL_PUBLICA       URL pública del backend (Cloudflare Tunnel en dev);
                         con ella se construye la notification_url en runtime
  PRINTNET_FRONTEND_URL  URL del frontend, para las back_urls (/estado/{token})

Si MP_ACCESS_TOKEN no está definida, el sistema cae al modo "fantasma" de
Fase 1 (todo pedido nace pagado) — útil para desarrollo sin credenciales.
"""

import hashlib
import hmac
import logging
import os

import requests

logger = logging.getLogger("printnet.payments")

MP_API = "https://api.mercadopago.com"


def _access_token() -> str:
    return os.environ.get("MP_ACCESS_TOKEN", "")


def modo_mercadopago() -> bool:
    """True si hay credenciales de MercadoPago configuradas."""
    return bool(_access_token())


def crear_preferencia(order_id: int, token: str, titulo: str, monto: int) -> dict:
    """Crea la preferencia de Checkout Pro y devuelve init_point + ids.

    - external_reference = token del pedido (UUID interno, no adivinable)
    - back_urls → página de estado del frontend
    - notification_url → nuestro webhook, construida en runtime
    """
    frontend = os.environ.get("PRINTNET_FRONTEND_URL", "http://localhost:5173").rstrip("/")
    estado_url = f"{frontend}/estado/{token}"

    payload = {
        "items": [
            {
                "id": str(order_id),
                "title": titulo,
                "quantity": 1,
                "unit_price": float(monto),
                "currency_id": "ARS",
            }
        ],
        "external_reference": token,
        "back_urls": {
            "success": estado_url,
            "failure": estado_url,
            "pending": estado_url,
        },
        "auto_return": "approved",
    }

    base_publica = os.environ.get("BASE_URL_PUBLICA", "").rstrip("/")
    if base_publica:
        payload["notification_url"] = f"{base_publica}/webhooks/mercadopago"
    else:
        logger.warning(
            "BASE_URL_PUBLICA no configurada: la preferencia se crea sin "
            "notification_url y el webhook no va a recibir avisos"
        )

    resp = requests.post(
        f"{MP_API}/checkout/preferences",
        json=payload,
        headers={"Authorization": f"Bearer {_access_token()}"},
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()
    return {
        "preference_id": data["id"],
        "init_point": data["init_point"],
        "sandbox_init_point": data.get("sandbox_init_point"),
    }


def obtener_pago(payment_id: str) -> dict:
    """GET /v1/payments/{id}: el estado real del pago según MercadoPago."""
    resp = requests.get(
        f"{MP_API}/v1/payments/{payment_id}",
        headers={"Authorization": f"Bearer {_access_token()}"},
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()


def validar_firma(x_signature: str, x_request_id: str, data_id: str, secret: str) -> bool:
    """Valida el header x-signature del webhook (HMAC-SHA256).

    Esquema oficial de MercadoPago: el header trae "ts=...,v1=..." y la firma
    se calcula sobre el template "id:{data.id};request-id:{x-request-id};ts:{ts};"
    (data.id en minúsculas si es alfanumérico).
    """
    if not secret:
        return False

    partes = dict(
        p.strip().split("=", 1) for p in x_signature.split(",") if "=" in p
    )
    ts = partes.get("ts", "")
    v1 = partes.get("v1", "")
    if not ts or not v1:
        return False

    manifest = f"id:{data_id.lower()};request-id:{x_request_id};ts:{ts};"
    esperada = hmac.new(secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperada, v1)
