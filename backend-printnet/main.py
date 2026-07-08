"""PrintNet backend — Fase 1 (pedidos fantasma).

Correr localmente:
    uvicorn main:app --reload --port 8000

Ver SPEC.md para el contrato completo de la API.
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import init_db
from routers import admin, orders

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


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


@app.get("/")
def raiz():
    return {"app": "printnet-backend", "fase": 1, "docs": "/docs"}
