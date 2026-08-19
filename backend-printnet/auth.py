"""Autenticación del panel de administración.

Los endpoints `/admin/*` exponen datos personales de clientes reales —nombre,
teléfono, email— y permiten cambiar el estado de los pedidos. Hasta que se
escribió esto, la única "contraseña" era `admin123` comparada en el navegador,
que no protege nada: los endpoints respondían a cualquiera que supiera la URL.

Mientras el backend vivía detrás de un túnel rápido con URL aleatoria y
rotativa, eso estaba tapado por accidente. Con `api.libreriaglaxara.com.ar`
fija y pública deja de estarlo, y por eso esto entra junto con el túnel.

DECISIÓN: se falla CERRADO. Sin token configurado, `/admin/*` no responde
(503). Un panel que no anda se nota en el momento; uno que quedó abierto no se
nota nunca.
"""

import logging
import os
import secrets

from fastapi import Header, HTTPException

logger = logging.getLogger("printnet.auth")

VAR_TOKEN = "PRINTNET_ADMIN_TOKEN"
NOMBRE_HEADER = "X-Admin-Token"

# Un token corto es adivinable a fuerza de intentos y da una falsa sensación de
# seguridad. Preferimos rechazarlo antes que aceptar otro "admin123".
LARGO_MINIMO = 16


def token_esperado() -> str:
    return os.environ.get(VAR_TOKEN, "").strip()


def verificar_admin(x_admin_token: str | None = Header(default=None)) -> None:
    """Dependencia de FastAPI: corta el request si el token no es el correcto.

    Se engancha una sola vez en el router de admin, así que cubre todos sus
    endpoints — incluidos los que se agreguen después, que es justamente lo
    que evita el olvido.
    """
    esperado = token_esperado()

    if not esperado:
        logger.error(
            "Alguien intentó entrar a /admin y %s no está configurada", VAR_TOKEN
        )
        raise HTTPException(
            503,
            f"El panel de administración no está configurado: falta {VAR_TOKEN} "
            f"en el .env del servidor.",
        )

    if len(esperado) < LARGO_MINIMO:
        logger.error("%s es demasiado corta (%d caracteres)", VAR_TOKEN, len(esperado))
        raise HTTPException(
            503,
            f"El panel de administración está mal configurado: {VAR_TOKEN} es "
            f"demasiado corta ({len(esperado)} caracteres, mínimo {LARGO_MINIMO}).",
        )

    recibido = (x_admin_token or "").strip()

    # compare_digest en vez de ==: compara en tiempo constante, así el tiempo
    # de respuesta no filtra cuántos caracteres del token acertó quien prueba.
    if not recibido or not secrets.compare_digest(recibido, esperado):
        logger.warning("Intento de acceso a /admin con token inválido o ausente")
        raise HTTPException(401, f"No autorizado: falta el header {NOMBRE_HEADER} o es incorrecto.")
