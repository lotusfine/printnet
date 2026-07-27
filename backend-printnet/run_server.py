"""Entrypoint para el ejecutable standalone (PyInstaller).

El CLI de uvicorn no funciona congelado (importa la app por string en un
subproceso); acá se importa la app directamente y se corre in-process.

Host/puerto configurables por env (PRINTNET_HOST / PRINTNET_PORT), con los
mismos defaults que usamos en desarrollo: 127.0.0.1:8000. El tunnel de
Cloudflare corre en la misma máquina, así que no hace falta exponer 0.0.0.0.
"""

import multiprocessing
import os

import uvicorn

from main import app

if __name__ == "__main__":
    # Obligatorio en Windows congelado: sin esto, cualquier subproceso
    # relanzaría el servidor entero en un loop infinito.
    multiprocessing.freeze_support()

    uvicorn.run(
        app,
        host=os.environ.get("PRINTNET_HOST", "127.0.0.1"),
        port=int(os.environ.get("PRINTNET_PORT", "8000")),
        log_level="info",
    )
