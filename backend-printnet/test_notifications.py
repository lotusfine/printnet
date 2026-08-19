"""Tests de los emails al cliente.

Correr:  .venv/bin/python test_notifications.py
(sin pytest a propósito, igual que el resto)

Lo que se prueba acá es el CONTENIDO de los mails, no el envío: armar el
cuerpo es lógica nuestra y se puede verificar sin servidor SMTP.

POR QUÉ IMPORTA EL LINK: el cliente cierra la pestaña y pierde el token. Si el
mail no trae un link usable, no tiene forma de volver a saber cómo va su
pedido — que fue exactamente el problema que apareció en producción.
"""

import os
import sys

from notifications import _cuerpo_listo, _cuerpo_recibido, _url_seguimiento

fallos: list[str] = []

SITIO = "https://www.libreriaglaxara.com.ar"
TOKEN = "abc123-def456"

PEDIDO = {
    "id": 42,
    "token": TOKEN,
    "tipo": "fotocopias",
    "estado": "imprimiendo",
    "precio_total": 3600,
    "nombre": "Ana",
    "email": "ana@ejemplo.com",
}


def check(nombre: str, obtenido, esperado):
    if obtenido == esperado:
        print(f"  ok  {nombre}")
    else:
        print(f"  FALLA  {nombre}:\n         esperado {esperado!r}\n         obtenido {obtenido!r}")
        fallos.append(nombre)


def con_sitio(valor: str | None):
    if valor is None:
        os.environ.pop("PRINTNET_FRONTEND_URL", None)
    else:
        os.environ["PRINTNET_FRONTEND_URL"] = valor


# ─────────────────────────────────────────────
print("\n== El link va a la página del cliente, no a la API ==")

con_sitio(SITIO)
check("apunta a /estado/{token}, que es la página que se puede leer",
      _url_seguimiento(TOKEN), f"{SITIO}/estado/{TOKEN}")
check("NO apunta a /orders/status, que devuelve datos crudos",
      "/orders/status/" in _url_seguimiento(TOKEN), False)

con_sitio(SITIO + "/")
check("una barra de más en la configuración no rompe el link",
      _url_seguimiento(TOKEN), f"{SITIO}/estado/{TOKEN}")

con_sitio(None)
check("sin sitio configurado, al menos da el token y no un link roto",
      TOKEN in _url_seguimiento(TOKEN), True)
check("sin sitio configurado no inventa una dirección",
      _url_seguimiento(TOKEN).startswith("http"), False)


print("\n== Email de pedido recibido ==")

con_sitio(SITIO)
cuerpo = _cuerpo_recibido(PEDIDO)
check("saluda por el nombre", "Ana" in cuerpo, True)
check("dice el número de pedido", "#42" in cuerpo, True)
check("trae el link de seguimiento", f"{SITIO}/estado/{TOKEN}" in cuerpo, True)
check("muestra el precio con separador de miles", "$3.600" in cuerpo, True)

sin_precio = dict(PEDIDO, precio_total=None)
check("un pedido sin precio dice 'a cotizar'",
      "a cotizar" in _cuerpo_recibido(sin_precio), True)


print("\n== Email de pedido listo ==")

cuerpo = _cuerpo_listo(PEDIDO)
check("saluda por el nombre", "Ana" in cuerpo, True)
check("dice que está listo", "listo" in cuerpo.lower(), True)
check("TAMBIÉN trae el link (antes no lo traía)",
      f"{SITIO}/estado/{TOKEN}" in cuerpo, True)
check("dice dónde retirarlo", "Glaxara" in cuerpo, True)


# ─────────────────────────────────────────────
print()
if fallos:
    print(f"✗ {len(fallos)} fallo(s): {', '.join(fallos)}")
    sys.exit(1)
print("✓ todos los tests de notificaciones pasaron")
