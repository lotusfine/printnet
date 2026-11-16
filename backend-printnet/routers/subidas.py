"""Endpoints de la subida en partes. Ver subidas.py, que tiene toda la lógica.

Acá solo se traduce HTTP: cada ErrorSubida se convierte en el status y el
mensaje que corresponden. Son públicos como POST /orders: el id es un uuid4
y conocerlo es lo único que da acceso a una subida, igual que el token de
seguimiento de un pedido.
"""

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

import subidas

router = APIRouter()


class AbrirSubida(BaseModel):
    nombre: str = Field(min_length=1, max_length=255)
    tamano_bytes: int = Field(gt=0)
    content_type: str = ""


def _http(e: subidas.ErrorSubida) -> HTTPException:
    return HTTPException(e.status, e.mensaje)


@router.post("/uploads", status_code=201)
def abrir_subida(datos: AbrirSubida):
    try:
        return subidas.abrir(datos.nombre, datos.tamano_bytes, datos.content_type)
    except subidas.ErrorSubida as e:
        raise _http(e)


@router.put("/uploads/{id_}/partes/{n}")
async def subir_parte(id_: str, n: int, request: Request):
    # Se mira el largo declarado ANTES de leer el cuerpo: así un pedazo
    # gigante se rechaza sin cargarlo en memoria.
    largo = request.headers.get("content-length", "")
    if largo.isdigit() and int(largo) > subidas.PARTE_BYTES:
        raise HTTPException(413, "la parte es más grande de lo permitido")
    datos = await request.body()
    try:
        # Escribir a disco bloquea: fuera del loop, para no frenar los demás requests.
        await run_in_threadpool(subidas.guardar_parte, id_, n, datos)
    except subidas.ErrorSubida as e:
        raise _http(e)
    return {"ok": True}


@router.post("/uploads/{id_}/completar", status_code=202)
def completar_subida(id_: str, background: BackgroundTasks):
    try:
        if subidas.completar(id_):
            # Juntar, convertir y contar puede tardar más que los 100 s que
            # Cloudflare espera una respuesta: va en segundo plano y la web
            # pregunta con GET /uploads/{id}.
            background.add_task(subidas.preparar, id_)
        return subidas.estado(id_)
    except subidas.ErrorSubida as e:
        raise _http(e)


@router.get("/uploads/{id_}")
def estado_subida(id_: str):
    try:
        return subidas.estado(id_)
    except subidas.ErrorSubida as e:
        raise _http(e)
