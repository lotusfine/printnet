"""Tests de los emails al cliente.

Correr:  .venv/bin/python test_notifications.py
(sin pytest a propósito, igual que el resto)

Lo que se prueba acá es el CONTENIDO de los mails, no el envío: armar el
cuerpo es lógica nuestra y se puede verificar sin servidor SMTP.

POR QUÉ IMPORTA EL LINK: el cliente cierra la pestaña y pierde el token. Si el
mail no trae un link usable, no tiene forma de volver a saber cómo va su
pedido — que fue exactamente el problema que apareció en producción.
"""

import logging
import os
import sys

logging.getLogger("printnet.notifications").setLevel(logging.CRITICAL)

from notifications import (
    _cuerpo_listo,
    _cuerpo_recibido,
    _smtp_config,
    _url_seguimiento,
    send_email,
)

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


print("\n== Cómo se conecta al servidor de correo ==")
# El hosting de Glaxara NO ofrece el puerto 587: solo 465 con SSL directo, o
# 9025 sin cifrar. STARTTLS (lo único que soportaba el código) no sirve acá.


def config(**env):
    for k in ("PRINTNET_SMTP_HOST", "PRINTNET_SMTP_PORT", "PRINTNET_SMTP_SSL",
              "PRINTNET_SMTP_STARTTLS"):
        os.environ.pop(k, None)
    for k, v in env.items():
        os.environ[k] = v
    return _smtp_config()


check("el puerto 465 usa SSL directo, sin que haya que declararlo",
      config(PRINTNET_SMTP_HOST="mail.x.com", PRINTNET_SMTP_PORT="465")["ssl"], True)
check("el puerto 587 NO usa SSL directo (va con STARTTLS)",
      config(PRINTNET_SMTP_HOST="mail.x.com", PRINTNET_SMTP_PORT="587")["ssl"], False)
check("el puerto 9025 (sin cifrar) tampoco",
      config(PRINTNET_SMTP_HOST="mail.x.com", PRINTNET_SMTP_PORT="9025")["ssl"], False)
check("se puede forzar SSL a mano",
      config(PRINTNET_SMTP_HOST="mail.x.com", PRINTNET_SMTP_PORT="587",
             PRINTNET_SMTP_SSL="1")["ssl"], True)
check("se puede desactivar a mano aunque sea 465",
      config(PRINTNET_SMTP_HOST="mail.x.com", PRINTNET_SMTP_PORT="465",
             PRINTNET_SMTP_SSL="0")["ssl"], False)


print("\n== El envío nunca puede tumbar un pedido ==")

config()  # sin host
estado, _ = send_email("a@b.c", "asunto", "cuerpo")
check("sin SMTP configurado el mail se simula, no falla", estado, "simulado")


def conexion_que_falla(cfg):
    raise OSError("el servidor no responde")


config(PRINTNET_SMTP_HOST="mail.x.com", PRINTNET_SMTP_PORT="465")
estado, detalle = send_email("a@b.c", "asunto", "cuerpo", conectar=conexion_que_falla)
check("si el servidor no responde devuelve error, no excepción", estado, "error")
check("el detalle dice qué pasó", "no responde" in detalle, True)


class SMTPFalso:
    def __init__(self):
        self.enviados = []
        self.logueado = None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def login(self, u, p):
        self.logueado = u

    def send_message(self, msg):
        self.enviados.append(msg)


falso = SMTPFalso()
config(PRINTNET_SMTP_HOST="mail.x.com", PRINTNET_SMTP_PORT="465")
os.environ["PRINTNET_SMTP_USER"] = "pedidos@glaxara.com"
os.environ["PRINTNET_SMTP_PASSWORD"] = "secreta"
os.environ["PRINTNET_SMTP_FROM"] = "pedidos@glaxara.com"
estado, _ = send_email("ana@ejemplo.com", "Pedido #42", "hola", conectar=lambda cfg: falso)
check("envío exitoso → 'enviado'", estado, "enviado")
check("se autentica con el usuario configurado", falso.logueado, "pedidos@glaxara.com")
check("manda un solo mensaje", len(falso.enviados), 1)
check("al destinatario correcto", falso.enviados[0]["To"], "ana@ejemplo.com")
check("con el remitente configurado", falso.enviados[0]["From"], "pedidos@glaxara.com")


# ─────────────────────────────────────────────
print()
if fallos:
    print(f"✗ {len(fallos)} fallo(s): {', '.join(fallos)}")
    sys.exit(1)
print("✓ todos los tests de notificaciones pasaron")
