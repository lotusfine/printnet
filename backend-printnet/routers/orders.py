"""Endpoints públicos: creación de pedidos y consulta de estado por token."""

import json
import logging
import re
import shutil
import sqlite3
import tempfile
import uuid
from pathlib import Path

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from pydantic import TypeAdapter, ValidationError

import document_convert
import notifications
import payments
import pricing
import subidas
from database import UPLOADS_DIR, get_db
from models import Pedido, PedidoFotocopias, PedidoFotos
from order_flow import confirmar_pago, despachar_tras_pago

logger = logging.getLogger("printnet.orders")
router = APIRouter()

_pedido_adapter = TypeAdapter(Pedido)

# Límite del camino VIEJO: archivos mandados enteros en POST /orders y
# POST /orders/paginas. 95 y no 100 porque Cloudflare, en el plan gratuito,
# corta las peticiones de más de 100 MB; dejando el límite propio un poco
# abajo, el cliente recibe nuestro mensaje y no uno de Cloudflare.
#
# La web nueva ya no usa este camino: sube en partes (subidas.py, hasta
# subidas.MAX_PEDIDO_MB). Este queda para la web vieja durante el deploy y
# para /fotos.
MAX_FILE_MB = 95
MAX_FILE_BYTES = MAX_FILE_MB * 1024 * 1024

IMAGEN_CT = re.compile(r"^image/")

# Compartidos con la subida en partes: viven en subidas.py para que los dos
# caminos le digan lo mismo al cliente.
_MENSAJE_FORMATO = subidas.MENSAJE_FORMATO
_MENSAJE_CONVERSION_FALLIDA = subidas.MENSAJE_CONVERSION_FALLIDA
_nombre_seguro = subidas.nombre_seguro
_contar_paginas_pdf = subidas.contar_paginas_pdf


def _fallo_conversion(resultado) -> HTTPException:
    """Traduce un fallo de conversión a lo que corresponde mostrarle al cliente."""
    if resultado.del_documento:
        return HTTPException(422, resultado.detalle)
    logger.error("Conversión fallida (problema del sistema): %s", resultado.detalle)
    return HTTPException(422, _MENSAJE_CONVERSION_FALLIDA)


def _es_pdf(f: UploadFile) -> bool:
    return (f.content_type == "application/pdf") or f.filename.lower().endswith(".pdf")


def _es_imagen(f: UploadFile) -> bool:
    return bool(f.content_type and IMAGEN_CT.match(f.content_type))


def _guardar_archivos(token: str, files: list[UploadFile]) -> list[dict]:
    """Guarda los uploads en uploads/{token}/ y devuelve su metadata."""
    destino = UPLOADS_DIR / token
    destino.mkdir(parents=True, exist_ok=True)
    guardados = []
    usados: set[str] = set()

    for f in files:
        nombre = _nombre_seguro(f.filename or "archivo")
        # evitar colisiones si suben dos archivos con el mismo nombre
        candidato, i = nombre, 1
        while candidato in usados:
            stem, suffix = Path(nombre).stem, Path(nombre).suffix
            candidato = f"{stem}_{i}{suffix}"
            i += 1
        usados.add(candidato)

        path = destino / candidato
        data = f.file.read(MAX_FILE_BYTES + 1)
        if len(data) > MAX_FILE_BYTES:
            raise HTTPException(413, f"'{nombre}' supera el máximo de {MAX_FILE_MB} MB")
        path.write_bytes(data)

        # Lo que se imprime es siempre un PDF. Si el cliente subió un Word o un
        # PowerPoint, se convierte acá; el original se conserva igual, porque es
        # lo que él mandó y lo que hay que poder mostrarle si reclama.
        resultado = document_convert.convertir_a_pdf(str(path), str(destino))
        if not resultado.ok:
            raise _fallo_conversion(resultado)

        guardados.append(
            {
                "filename_original": f.filename or nombre,
                "stored_path": str(path),
                "pdf_path": resultado.pdf_path,
                "content_type": f.content_type,
                "size_bytes": len(data),
                "paginas": _contar_paginas_pdf(Path(resultado.pdf_path)),
            }
        )
    return guardados


def _upsert_customer(db: sqlite3.Connection, contacto) -> int:
    """Reutiliza el cliente por email (actualizando nombre/teléfono) o lo crea."""
    row = db.execute(
        "SELECT id FROM customers WHERE email = ?", (contacto.email,)
    ).fetchone()
    if row:
        db.execute(
            "UPDATE customers SET nombre = ?, telefono = ? WHERE id = ?",
            (contacto.nombre, contacto.telefono, row["id"]),
        )
        return row["id"]
    cur = db.execute(
        "INSERT INTO customers (nombre, telefono, email) VALUES (?, ?, ?)",
        (contacto.nombre, contacto.telefono, contacto.email),
    )
    return cur.lastrowid


def _leer_ids_subidas(crudo: str, cantidad: int) -> list[str]:
    try:
        ids = json.loads(crudo)
    except json.JSONDecodeError:
        raise HTTPException(422, "el campo 'uploads' no es JSON válido")
    if not isinstance(ids, list) or not all(isinstance(i, str) for i in ids):
        raise HTTPException(422, "'uploads' tiene que ser una lista de ids")
    if len(ids) != cantidad:
        raise HTTPException(
            422,
            f"llegaron {len(ids)} subida(s) y {cantidad} configuración(es): "
            f"tiene que haber una por documento",
        )
    if len(set(ids)) != len(ids):
        raise HTTPException(422, "la misma subida aparece dos veces")
    return ids


def _reservar_subidas(ids: list[str]) -> list[dict]:
    """Aparta las subidas para este pedido. Todo o nada.

    La reserva es lo que hace seguro un doble clic en "pagar": el segundo
    POST /orders recibe 409 en vez de pisarse con el primero (antes daba 500
    y podía hacer perder las subidas). Si una no se puede reservar, se
    devuelven las que ya se habían apartado.

    Devuelve lo que hace falta para cotizar. Los archivos todavía no se tocan:
    eso es `_tomar_subidas`, con el pedido ya validado.
    """
    reservadas, archivos = [], []
    try:
        for id_ in ids:
            e = subidas.reservar(id_)
            reservadas.append(id_)
            archivos.append({
                "filename_original": e["nombre"],
                "paginas": e["paginas"],
                "size_bytes": e["tamano_bytes"],
            })
        if sum(a["size_bytes"] for a in archivos) > subidas.MAX_PEDIDO_BYTES:
            raise HTTPException(
                413, f"el pedido supera el máximo de {subidas.MAX_PEDIDO_MB} MB en total")
    except subidas.ErrorSubida as err:
        for id_ in reservadas:
            subidas.devolver(id_)
        raise HTTPException(err.status, err.mensaje)
    except BaseException:
        for id_ in reservadas:
            subidas.devolver(id_)
        raise
    return archivos


def _tomar_subidas(token: str, ids: list[str]) -> list[dict]:
    destino = UPLOADS_DIR / token
    usados: set[str] = set()
    try:
        return [subidas.tomar(id_, destino, usados) for id_ in ids]
    except subidas.ErrorSubida as e:
        raise HTTPException(e.status, e.mensaje)


@router.post("/orders/paginas")
def contar_paginas(file: UploadFile = File(...)):
    """Cuenta las páginas de un PDF SIN crear pedido.

    Lo usa el frontend apenas se sube el archivo, para que el precio que se
    muestra ANTES de comprar se calcule con las páginas reales (misma base
    que el precio final del pedido).
    """
    nombre = file.filename or "archivo"
    if not (_es_pdf(file) or document_convert.necesita_conversion(nombre)):
        raise HTTPException(422, _MENSAJE_FORMATO)

    data = file.file.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(413, f"el archivo supera el máximo de {MAX_FILE_MB} MB")

    # Se trabaja sobre una copia temporal: este endpoint no crea pedido, así
    # que no debe dejar nada en uploads/.
    with tempfile.TemporaryDirectory(prefix="printnet-conteo-") as tmp:
        origen = Path(tmp) / _nombre_seguro(nombre)
        origen.write_bytes(data)

        resultado = document_convert.convertir_a_pdf(str(origen), tmp)
        if not resultado.ok:
            raise _fallo_conversion(resultado)

        paginas = _contar_paginas_pdf(Path(resultado.pdf_path))

    if paginas is None:
        raise HTTPException(422, "no se pudo leer el documento para contar sus páginas")
    return {"paginas": paginas, "convertido": not _es_pdf(file)}


@router.post("/orders", status_code=201)
def crear_pedido(
    background: BackgroundTasks,
    datos: str = Form(..., description="JSON del pedido (ver SPEC.md)"),
    files: list[UploadFile] | None = File(None),
    uploads: str | None = Form(
        None, description="JSON: ids de subidas en partes, uno por documento"),
    db: sqlite3.Connection = Depends(get_db),
):
    # 1) Validar el payload JSON contra el contrato
    try:
        pedido = _pedido_adapter.validate_python(json.loads(datos))
    except json.JSONDecodeError:
        raise HTTPException(422, "el campo 'datos' no es JSON válido")
    except ValidationError as e:
        errores = [
            {"campo": ".".join(str(p) for p in err["loc"]), "error": err["msg"]}
            for err in e.errors()
        ]
        raise HTTPException(422, errores)

    if files and uploads and uploads.strip() != "[]":
        raise HTTPException(422, "mandá 'files' o 'uploads', no los dos")

    token = str(uuid.uuid4())
    ids_subidas = None

    if uploads:
        # 2+3) Camino nuevo: los archivos ya están en el servidor, preparados.
        if not isinstance(pedido, PedidoFotocopias):
            raise HTTPException(422, "la subida en partes es solo para fotocopias")
        ids_subidas = _leer_ids_subidas(uploads, len(pedido.documentos))
        archivos = _reservar_subidas(ids_subidas)
    else:
        files = files or []
        # 2) Validar archivos según el tipo de pedido
        if isinstance(pedido, PedidoFotocopias):
            # Un archivo por documento: cada uno trae su propia configuración y el
            # emparejamiento es por posición.
            if len(files) != len(pedido.documentos):
                raise HTTPException(
                    422,
                    f"llegaron {len(files)} archivo(s) y {len(pedido.documentos)} "
                    f"configuración(es): tiene que haber una por documento",
                )
            for f in files:
                nombre = f.filename or "archivo"
                if not (_es_pdf(f) or document_convert.necesita_conversion(nombre)):
                    raise HTTPException(422, f"'{nombre}': {_MENSAJE_FORMATO}")
        else:  # PedidoFotos
            if not files:
                raise HTTPException(422, "un pedido de fotos lleva al menos 1 archivo")
            for f in files:
                if not (_es_pdf(f) or _es_imagen(f)):
                    raise HTTPException(422, f"'{f.filename}': solo se aceptan imágenes o PDF")

        # 3) Guardar archivos y contar páginas reales
        archivos = _guardar_archivos(token, files)

    if not ids_subidas:
        return _cotizar_y_guardar(background, pedido, token, archivos, None, db)

    # Si el pedido no llega a guardarse —un rango que no existe, MercadoPago
    # caído, cualquier cosa— las subidas se devuelven intactas y se borra lo
    # que se haya armado en la carpeta del pedido. Antes se perdían: el cliente
    # tenía que volver a subir hasta 300 MB para reintentar el pago.
    try:
        respuesta = _cotizar_y_guardar(background, pedido, token, archivos, ids_subidas, db)
    except BaseException:
        for id_ in ids_subidas:
            subidas.devolver(id_)
        shutil.rmtree(UPLOADS_DIR / token, ignore_errors=True)
        raise
    for id_ in ids_subidas:
        subidas.liberar(id_)
    return respuesta


def _cotizar_y_guardar(background, pedido, token, archivos, ids_subidas, db) -> dict:
    """Pasos 4 a 6 de crear_pedido: cotizar, guardar y arrancar el pago."""
    # 4) Precio + triage según tipo
    if isinstance(pedido, PedidoFotocopias):
        cotizables = []
        detalle_docs = []
        for doc, archivo in zip(pedido.documentos, archivos):
            paginas_doc = archivo["paginas"]
            if paginas_doc is None:
                raise HTTPException(
                    422,
                    f"no se pudo leer '{archivo['filename_original']}' para "
                    f"contar sus páginas",
                )
            try:
                paginas_a_cobrar = pricing.paginas_del_rango(
                    doc.rango.modo, doc.rango.valor, paginas_doc
                )
            except ValueError as e:
                raise HTTPException(422, f"'{archivo['filename_original']}': {e}")

            cotizables.append(pricing.Documento(
                paginas=paginas_a_cobrar,
                copias=doc.opciones.copias,
                color=doc.opciones.color,
                caras=doc.opciones.caras,
                tamano=doc.opciones.tamano,
                terminaciones=list(doc.terminaciones),
            ))
            detalle_docs.append({
                "archivo": archivo["filename_original"],
                "opciones": doc.opciones.model_dump(),
                "rango": doc.rango.model_dump(),
                "terminaciones": doc.terminaciones,
                "paginas_documento": paginas_doc,
                "paginas_a_imprimir": paginas_a_cobrar,
            })

        # El tramo de descuento sale de la suma de todos los documentos.
        cotizacion = pricing.calcular_precio_pedido(cotizables)
        precio_total = cotizacion.total
        requiere_manual = any(d.terminaciones for d in pedido.documentos)

        for detalle, linea in zip(detalle_docs, cotizacion.documentos):
            detalle["subtotal"] = linea.subtotal
            detalle["precio_unitario"] = linea.unitario

        primero = detalle_docs[0]
        opciones_json = {
            "documentos": detalle_docs,
            "cantidad_total": cotizacion.cantidad_total,
            # Espejo de la forma vieja, con el primer documento. El panel de
            # operador y la página de seguimiento todavía leen estas claves;
            # se pueden sacar cuando dejen de usarlas.
            "opciones": primero["opciones"],
            "rango": primero["rango"],
            "terminaciones": primero["terminaciones"],
            "paginas_documento": primero["paginas_documento"],
            "paginas_a_imprimir": primero["paginas_a_imprimir"],
        }
    else:
        precio_total = None  # los pedidos especiales se cotizan manualmente
        requiere_manual = True
        opciones_json = {
            "material": pedido.material,
            "formato": pedido.formato,
            "gramaje": pedido.gramaje,
            "terminaciones": pedido.terminaciones,
        }

    # Recién ahora, con el pedido ya validado y cotizado, las subidas pasan
    # a la carpeta del pedido.
    if ids_subidas:
        archivos = _tomar_subidas(token, ids_subidas)

    # 5) Persistir cliente + pedido + archivos. El pedido nace SIN pagar,
    #    en 'pendiente_pago'; el pago define el paso 6.
    customer_id = _upsert_customer(db, pedido.contacto)
    cur = db.execute(
        """INSERT INTO orders (token, tipo, customer_id, estado, pagado,
                               requiere_manual, precio_total, opciones)
           VALUES (?, ?, ?, 'pendiente_pago', 0, ?, ?, ?)""",
        (token, pedido.tipo, customer_id, int(requiere_manual), precio_total,
         json.dumps(opciones_json)),
    )
    order_id = cur.lastrowid

    for a in archivos:
        db.execute(
            """INSERT INTO files (order_id, filename_original, stored_path,
                                  pdf_path, content_type, size_bytes, paginas)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (order_id, a["filename_original"], a["stored_path"],
             a.get("pdf_path") or a["stored_path"],
             a["content_type"], a["size_bytes"], a["paginas"]),
        )

    # 6) Pago
    init_point = None
    if isinstance(pedido, PedidoFotocopias) and payments.modo_mercadopago():
        # MercadoPago real (Checkout Pro): el pedido queda en pendiente_pago
        # hasta que el webhook confirme el pago aprobado. El triage/dispatch
        # y el email "recibido" se disparan recién ahí (webhook → confirmar_pago + despachar_tras_pago).
        try:
            pref = payments.crear_preferencia(
                order_id=order_id,
                token=token,
                titulo=f"PrintNet — Pedido #{order_id}",
                monto=precio_total,
            )
        except Exception as exc:  # noqa: BLE001 — MP caído no debe dejar basura
            logger.error("No se pudo crear la preferencia de MercadoPago: %s", exc)
            raise HTTPException(502, "no se pudo iniciar el pago con MercadoPago")
        db.execute(
            "UPDATE orders SET mp_preference_id = ? WHERE id = ?",
            (pref["preference_id"], order_id),
        )
        estado, pagado = "pendiente_pago", False
        init_point = pref["init_point"]
        # Commit explícito antes de responder (libera el lock de escritura)
        db.commit()
    else:
        # Modo fantasma (sin MP_ACCESS_TOKEN configurado) o pedido de /fotos
        # (sin precio online: se cotiza y cobra en el local) → mismo flujo
        # que Fase 1: pago inmediato + triage + email.
        confirmar_pago(db, order_id)
        estado, pagado = "pendiente", True
        db.commit()
        # Igual que el webhook: se imprime en segundo plano, así el cliente no
        # espera a la impresora para ver su pedido confirmado.
        background.add_task(despachar_tras_pago, order_id)
        background.add_task(notifications.notificar_pedido_recibido, order_id)

    return {
        "id": order_id,
        "token": token,
        "tipo": pedido.tipo,
        "estado": estado,
        "pagado": pagado,
        "init_point": init_point,
        "precio_total": precio_total,
        "requiere_manual": requiere_manual,
        "archivos": [a["filename_original"] for a in archivos],
        "paginas": archivos[0]["paginas"] if pedido.tipo == "fotocopias" else None,
    }


@router.get("/orders/status/{token}")
def estado_pedido(token: str, db: sqlite3.Connection = Depends(get_db)):
    """Consulta pública por token (UUID v4, no adivinable). Sin login."""
    row = db.execute(
        """SELECT o.token, o.tipo, o.estado, o.precio_total, o.requiere_manual,
                  o.created_at, o.updated_at
           FROM orders o WHERE o.token = ?""",
        (token,),
    ).fetchone()
    if not row:
        raise HTTPException(404, "pedido no encontrado")

    archivos = [
        r["filename_original"]
        for r in db.execute(
            "SELECT f.filename_original FROM files f"
            " JOIN orders o ON o.id = f.order_id WHERE o.token = ?",
            (token,),
        )
    ]
    return {
        "token": row["token"],
        "tipo": row["tipo"],
        "estado": row["estado"],
        "precio_total": row["precio_total"],
        "archivos": archivos,
        "creado": row["created_at"],
        "actualizado": row["updated_at"],
    }
