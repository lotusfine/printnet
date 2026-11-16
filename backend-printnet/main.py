"""PrintNet backend — Fase 1 (pedidos fantasma).

Correr localmente:
    uvicorn main:app --reload --port 8000

Ver SPEC.md para el contrato completo de la API.
"""

import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Cargar .env antes de que los módulos lean os.environ. Congelado con
# PyInstaller, el .env vive junto al ejecutable (no en el temp de extracción).
_BASE = (
    Path(sys.executable).resolve().parent
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parent
)
load_dotenv(_BASE / ".env")

import subidas
from database import get_conn, init_db
from order_flow import marcar_despachos_interrumpidos
from routers import admin, orders, webhooks
from routers import subidas as subidas_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)


async def _limpiar_subidas_cada_hora():
    """Borra las subidas que nunca terminaron en pedido (ver subidas.VIDA_SEG)."""
    logger = logging.getLogger("printnet.subidas")
    while True:
        try:
            borradas = await asyncio.to_thread(subidas.limpiar_viejas)
            if borradas:
                logger.info("Limpieza: %d subida(s) abandonada(s) borrada(s)", borradas)
        except Exception:  # noqa: BLE001 — la limpieza nunca puede tirar el servidor
            logger.exception("Falló la limpieza de subidas")
        await asyncio.sleep(3600)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # Lo que un reinicio dejó a medias (ver cada función).
    conn = get_conn()
    try:
        marcar_despachos_interrumpidos(conn)
        conn.commit()
    finally:
        conn.close()
    subidas.marcar_interrumpidas()
    limpieza = asyncio.create_task(_limpiar_subidas_cada_hora())
    yield
    limpieza.cancel()


app = FastAPI(
    title="PrintNet",
    description="Backend de gestión de impresión — Fase 1 (pedidos fantasma)",
    version="0.1.0",
    lifespan=lifespan,
)

# Orígenes permitidos: local por defecto; producción vía env (coma-separados)
_origins = os.environ.get(
    "PRINTNET_CORS_ORIGINS", "http://localhost:5173,http://localhost:5174"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins if o.strip()],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(orders.router)
app.include_router(admin.router)
app.include_router(webhooks.router)
app.include_router(subidas_router.router)


@app.get("/")
def raiz():
    return {"app": "printnet-backend", "fase": 1, "docs": "/docs"}
