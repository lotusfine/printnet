# PrintNet Backend — SPEC (contrato vivo)

> Este archivo es el contrato que se lee y actualiza en cada sesión de trabajo.
> Última actualización: 2026-07-08 · **Fase 1 completa y verificada de punta a punta.**

## Fase actual: 1 — "Pedidos fantasma"

- **Pago**: todo pedido nace con `pagado = true` automáticamente. NO hay MercadoPago real ni webhook.
- **Impresión**: simulada. `SimulatedDispatcher` registra en `dispatch_log` la intención ("se despacharía X a la impresora Y con opciones Z") sin tocar hardware.
- **Fuera de alcance**: MercadoPago real, impresora física, WhatsApp.

## Ubicación y stack

- Código en **`/backend-printnet`** (NO en `/backend`: esa carpeta la ocupa el backend Java/Spring Boot del sitio Glaxara que sirve `/informacion` y `/novedades` — no tocar).
- Python 3.11 + FastAPI + SQLite (sqlite3 stdlib, SQL crudo, sin ORM). Pensado para Raspberry Pi 3B+ (1GB RAM).
- Dependencias: `fastapi`, `uvicorn`, `python-multipart`, `pypdf` (conteo real de páginas, puro Python).

## Estructura

```
backend-printnet/
├── main.py            # FastAPI app, CORS, startup (init_db)
├── database.py        # SQLite: esquema idempotente + migraciones + seed impresoras
├── models.py          # Pydantic: contrato de entrada (espeja el frontend)
├── pricing.py         # Tabla de precios HARDCODEADA (no editable por API)
├── print_dispatch.py  # Interfaz abstracta de impresión + SimulatedDispatcher
├── notifications.py   # Email SMTP (env vars); simula si no hay config
├── routers/
│   ├── orders.py      # POST /orders, GET /orders/status/{token}
│   └── admin.py       # GET/PATCH /admin/orders, GET /admin/printers
├── SPEC.md            # este archivo
├── requirements.txt
└── .env.example
```

## Contrato con el frontend (extraído del código real)

El frontend arma estos objetos (verificado en `frontend/src/`):

- **Contacto** (`ContactForm.jsx`, compartido): `{ nombre, pais, area, numero, email }`.
  El teléfono viaja **compuesto** por `composeTelefono()`: `+{pais}9{area}{numero}` → ej. `+5492214567890`.
- **/fotocopias** (`Fotocopias.jsx`): `options { color: 'byn'|'color', caras: 'simple'|'doble', copias ≥1, tamano: 'A4'|'A3' }` + `rango { modo: 'todas'|'rango', valor: 'N-M'|'N' }` + 1 archivo PDF.
- **/fotos** (`Fotos.jsx`): `material: 'hoja-foto'|'vegetal'|'opalina'|'autoadhesiva'`; `formato: '13x18'|'9x13'|'6x9'` (obligatorio con hoja-foto); `gramaje: 120|150|180|240` (obligatorio con opalina); `terminaciones ⊆ ['Anillado','Plastificado','Corte']`; N archivos (imagen/PDF).
- **/admin** (`Admin.jsx`) espera pedidos con: `{ id, cliente, archivo, paginas, copias, color: bool, doble: bool, acabado: string|null, precio, estado, hace: minutos, contacto: {tel, email} }`.

### Estado de la conexión frontend ↔ backend

**El frontend YA está conectado** (cliente en `frontend/src/api.js`, base URL por
`VITE_PRINTNET_API`, default `http://localhost:8000`):
- `/fotocopias` y `/fotos` crean pedidos reales con `POST /orders` (multipart con
  los archivos de verdad) y muestran confirmación con id/token/precio del backend.
- `/admin` se hidrata con `GET /admin/orders` (poll cada 15s) + `GET /admin/printers`
  (carga inicial); las transiciones usan `PATCH /admin/orders/{id}`.

Pendientes conocidos:
1. ~~Precio con rango distinto pre/post~~ ✔ resuelto: conteo real vía
   `POST /orders/paginas` + `calcPrice` espejado con rango y anillado.
2. ~~Terminaciones en /fotocopias sin UI~~ ✔ resuelto: toggle de Anillado en
   /fotocopias (con precio automático); Plastificado y Corte quedaron en /fotos.
3. **Gestión de impresoras del admin** (renombrar, agregar, cargar papel, resolver
   error): sigue siendo estado local del navegador; el backend aún no tiene
   endpoints de mutación de impresoras.

## Modelo de datos (SQLite)

- **customers** `(id, nombre, telefono, email, created_at)` — upsert por email.
- **orders** `(id, token UUID4 UNIQUE, tipo 'fotocopias'|'fotos', customer_id FK, estado, pagado=1, requiere_manual, precio_total NULL para fotos, opciones JSON, printer_id FK NULL, created_at, updated_at)`.
- **files** `(id, order_id FK, filename_original, stored_path, content_type, size_bytes, paginas NULL si no es PDF)`. Los archivos viven en `uploads/{token}/`.
- **printers** `(id, nombre, tipo 'laser'|'tinta', estado 'activa'|'error', error_tipo, hojas, consumible %)`. Seed: HP LaserJet 1 (error, tóner bajo) y Epson L3250 (activa) — espejo del mock de /admin.
- **dispatch_log** `(id, order_id, printer_id, file_id, dispatcher, ok, detalle, created_at)`.
- **notifications** `(id, order_id, tipo 'recibido'|'listo', destinatario, estado 'enviado'|'simulado'|'error', detalle, created_at)`.

`orders.opciones` (JSON) guarda las opciones específicas del tipo:
- fotocopias: `{ opciones: {color, caras, copias, tamano}, rango: {modo, valor}, terminaciones: [], paginas_documento, paginas_a_imprimir }`
- fotos: `{ material, formato, gramaje, terminaciones }`

Migraciones: esquema idempotente (`CREATE TABLE IF NOT EXISTS`) + lista `MIGRACIONES` en `database.py` con `PRAGMA user_version`. WAL activado; `busy_timeout=5000`.

**Notas de concurrencia** (bugs encontrados y arreglados en esta sesión):
- Los handlers hacen `db.commit()` explícito ANTES de responder, porque las tareas de fondo (emails) abren su propia conexión y escribirían con el lock tomado.
- Las conexiones se abren con `check_same_thread=False`: FastAPI corre los endpoints sync en un threadpool y la conexión puede crearse y usarse en hilos distintos (cada una la usa un solo request a la vez, así que es seguro). Sin esto, requests concurrentes fallaban intermitentemente con 500.

## Estados y transiciones

`pendiente → imprimiendo → listo → entregado`, con `cancelado` alcanzable desde pendiente/imprimiendo/listo. `entregado` y `cancelado` son finales. Transición inválida → `409`.

Triage al crear (decisión de arquitectura 2):
- **fotocopias**: dispatch simulado automático a la primera impresora `activa` → nace en `imprimiendo` (si no hay impresora activa queda `pendiente`). `requiere_manual = true` solo si trae terminaciones (complementa el dispatch, no lo reemplaza).
- **fotos**: nunca se despachan; nacen `pendiente` con `requiere_manual = true` y `precio_total = null` (se cotizan a mano).

## Precios (`pricing.py` — hardcodeado, sin endpoint de edición)

```
byn $10/pág · color $25/pág · doble faz: ceil(pág/2) hojas · A3: ×1.5
total = round(hojas × copias × $ × mult) [+ anillado]

Terminaciones:
  Anillado (solo /fotocopias, automático): $2.000 por copia hasta 100 hojas,
    $3.500 por copia con más de 100 hojas
  Plastificado: $1.400 hoja A4 · $700 media hoja   (referencia, /fotos a cotizar)
  Corte: $500 hoja A4                              (referencia, /fotos a cotizar)
```
Las páginas se cuentan del PDF real con pypdf; el rango se valida contra ese total (la validación que el frontend delegó al backend). PDF ilegible → 422.

La fórmula está **espejada** en `frontend/src/components/fotocopias/PrintOptions.jsx`
(`calcPrice`) — si cambia una, cambiar la otra. Además el frontend usa
`POST /orders/paginas` al subir el archivo para que el precio previo se calcule
con las páginas reales: **precio pre-compra ≡ precio post-compra**.

## Endpoints

### `POST /orders/paginas` (multipart) → 200
Campo `file`: un PDF. Devuelve `{ paginas }` sin crear pedido. Lo usa el frontend
al subir el archivo para mostrar conteo y precio reales antes de comprar.
Errores: 422 (no es PDF / ilegible), 413 (>50 MB).

### `POST /orders` (multipart) → 201
- Campo `datos`: string JSON. Discriminado por `tipo`:

```json
{ "tipo": "fotocopias",
  "contacto": { "nombre": "Ana", "telefono": "+5492214567890", "email": "ana@mail.com" },
  "opciones": { "color": "color", "caras": "doble", "copias": 2, "tamano": "A4" },
  "rango": { "modo": "rango", "valor": "3-8" },
  "terminaciones": [] }
```
```json
{ "tipo": "fotos",
  "contacto": { ... },
  "material": "opalina", "gramaje": 180,
  "formato": null,
  "terminaciones": ["Corte"] }
```
- Campo `files`: fotocopias = exactamente 1 PDF; fotos = ≥1 (imagen o PDF). Máx 50 MB c/u.
- Respuesta: `{ id, token, tipo, estado, pagado: true, precio_total, requiere_manual, archivos: [nombres], paginas }`
- Efectos: guarda archivos, cuenta páginas, cobra (fotocopias), despacha (fotocopias), email "recibido" en background.
- Errores: 422 validación (formato `[{campo, error}]`), 413 archivo grande.

### `GET /orders/status/{token}` → 200 (público, sin login)
`{ token, tipo, estado, precio_total, archivos, creado, actualizado }` · 404 si no existe. Token = UUID v4, no adivinable.

### `GET /admin/orders[?estado=...]` → 200
Lista descendente por fecha. Cada ítem (superset de lo que pinta /admin):
`{ id, token, tipo, cliente, archivo, archivos, paginas, paginas_a_imprimir, copias, color: bool|null, doble: bool|null, tamano, rango, material, formato, gramaje, acabado, precio, estado, pagado, requiere_manual, hace: minutos, contacto: {tel, email}, creado, actualizado }`

### `PATCH /admin/orders/{id}` → 200
Body: `{ "estado": "listo" }`. Valida la transición (409 si es inválida), 404 si no existe. Al pasar a `listo` dispara el hook email "pedido listo". Devuelve el pedido actualizado (mismo shape del listado).

### `GET /admin/printers` → 200
Shape del sidebar de /admin: `{ id, nombre, tipo, estado, errorTipo, hojas, papel, tonner|tinta }`.

> **Auth**: los endpoints `/admin/*` NO tienen autenticación en Fase 1 (el login de /admin es client-side). Pendiente para fase futura.

## Notificaciones (email SMTP)

Config por env (ver `.env.example`): `PRINTNET_SMTP_HOST/PORT/USER/PASSWORD/FROM/STARTTLS`. **Sin `PRINTNET_SMTP_HOST` los emails se simulan**: se loggean y quedan en `notifications` con `estado='simulado'` — el flujo se prueba completo sin SMTP real.
- "recibido": al crear el pedido (background, no bloquea la respuesta).
- "listo": hook implementado, se dispara en `PATCH → listo`.

## print_dispatch (interfaz abstracta)

`PrintDispatcher.dispatch(printer_nombre, file_path, options) → DispatchResult(ok, detalle)`. Fase 1: `SimulatedDispatcher`. Futuras (sin tocar el resto del sistema): `SumatraDispatcher` (Windows, SumatraPDF CLI) y `CupsDispatcher` (Linux/Pi, `lp`). Selección por env `PRINTNET_DISPATCH` (default `simulated`). Atajo funcional: `dispatch_print(...)`.

## Cómo correr y probar localmente

```bash
cd backend-printnet
python3.11 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn main:app --reload --port 8000
# docs interactivas: http://localhost:8000/docs
```

Prueba de punta a punta (con cualquier PDF a mano):

```bash
# 1. Crear pedido de fotocopias → nace pagado y "imprimiendo" (dispatch simulado)
curl -s -X POST http://localhost:8000/orders \
  -F 'datos={"tipo":"fotocopias","contacto":{"nombre":"Ana","telefono":"+5492214567890","email":"ana@mail.com"},"opciones":{"color":"byn","caras":"simple","copias":1,"tamano":"A4"}}' \
  -F "files=@mi_archivo.pdf;type=application/pdf"
# → guardar el "token" de la respuesta

# 2. Verlo en el admin
curl -s http://localhost:8000/admin/orders

# 3. Email "recibido": sin SMTP configurado queda simulado — verlo en el log
#    del server o en la tabla: sqlite3 printnet.db 'SELECT * FROM notifications'

# 4. Pasarlo a listo (dispara el hook del email "listo")
curl -s -X PATCH http://localhost:8000/admin/orders/1 \
  -H "Content-Type: application/json" -d '{"estado":"listo"}'

# 5. Consultar estado por token (público)
curl -s http://localhost:8000/orders/status/<TOKEN>
```

## Roadmap (fases futuras)

- ~~Fase 2: conectar el frontend~~ ✔ hecho (queda: auth para `/admin/*`).
- Fase 3: MercadoPago real (webhook), impresión real (CUPS en la Pi / SumatraPDF en Windows).
- Fase 4: WhatsApp, endpoints de mutación de impresoras (hoy el sidebar usa estado local).
