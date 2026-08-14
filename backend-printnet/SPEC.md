# PrintNet Backend — SPEC (contrato vivo)

> Este archivo es el contrato técnico del backend. Para el estado general del
> proyecto y qué falta hacer, ver **`ESTADO.md`** en la raíz del repositorio.
> Última actualización: 2026-08-19 · **MercadoPago en producción verificado con
> dinero real. Dominio migrado a Cloudflare. Falta el túnel nombrado, el
> despachador de impresión real y la autenticación del admin.**

## Fase actual: pagos reales (Checkout Pro)

- **Pago**: integración real con MercadoPago Checkout Pro para pedidos de
  /fotocopias. El pedido nace en `pendiente_pago`; el webhook confirma el pago
  y recién ahí se dispara el flujo post-pago (triage, dispatch, email).
  - **Modo fantasma de respaldo**: si `MP_ACCESS_TOKEN` no está configurada, el
    sistema se comporta como Fase 1 (todo pedido nace pagado) — para desarrollo
    local sin credenciales.
  - **Pedidos de /fotos**: NO pasan por MercadoPago (no tienen precio online;
    se cotizan y cobran en el local). Siguen el flujo de Fase 1.
- **Impresión**: `SumatraDispatcher` (Windows) ya está escrito y cubierto por
  `test_dispatch.py`, pero **todavía no se probó contra la Ricoh IM C4500**.
  El default sigue siendo `SimulatedDispatcher`, que registra en `dispatch_log`
  la intención sin tocar hardware; para imprimir de verdad hay que poner
  `PRINTNET_DISPATCH=sumatra` en la notebook.
- **Fuera de alcance**: reembolsos/cancelaciones/contracargos de MP, impresora
  física, WhatsApp.

## Flujo de pago real

```
cliente confirma pedido
  → POST /orders crea el pedido en 'pendiente_pago' (pagado=0)
  → backend crea la preferencia de Checkout Pro
      items: monto de pricing.py · external_reference: token del pedido
      back_urls: {FRONTEND}/estado/{token} · notification_url: {BASE_URL_PUBLICA}/webhooks/mercadopago
  → responde init_point → el frontend redirige al cliente a MercadoPago
cliente paga en MP
  → MP notifica POST /webhooks/mercadopago (firma x-signature validada)
  → backend consulta GET /v1/payments/{id} (nunca confía en el body)
  → "approved" → order_flow.confirmar_pago(): EXACTAMENTE el flujo post-pago
     de Fase 1 (pagado=1, triage, dispatch simulado, email "recibido")
  → "rejected"/"cancelled" → estado 'pago_rechazado', sin disparar nada
```

La lógica post-pago vive en **`order_flow.confirmar_pago(conn, order_id)`**
(extraída de la creación inline de Fase 1). Es **idempotente**: los reintentos
de webhook de MP no despachan dos veces. La disparan el webhook (modo MP) o la
creación del pedido (modo fantasma y pedidos /fotos).

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
├── payments.py        # MercadoPago: preferencia, consulta de pago, firma HMAC
├── order_flow.py      # confirmar_pago(): flujo post-pago único (triage+dispatch)
├── print_dispatch.py  # Interfaz abstracta de impresión + SimulatedDispatcher
├── notifications.py   # Email SMTP (env vars); simula si no hay config
├── routers/
│   ├── orders.py      # POST /orders, POST /orders/paginas, GET /orders/status/{token}
│   ├── admin.py       # GET/PATCH /admin/orders, GET /admin/printers
│   └── webhooks.py    # POST /webhooks/mercadopago
├── run_server.py      # entrypoint del ejecutable congelado (uvicorn embebido)
├── printnet.spec      # PyInstaller: build del .exe standalone
├── deploy/            # instalación permanente en Windows (ver deploy/README.md)
│   ├── install-services.ps1    # registro de servicios con NSSM
│   ├── uninstall-services.ps1
│   ├── printnet-installer.iss  # instalador Inno Setup
│   └── README.md               # build + config manual de Windows
├── SPEC.md            # este archivo
├── requirements.txt
└── .env.example
```

### Despliegue en la notebook del local (Windows)

El backend se empaqueta con PyInstaller en un `.exe` standalone y corre como
servicio de Windows junto a `cloudflared` (túnel nombrado `printnet`), ambos
con arranque y reinicio automáticos. Paso a paso en **`deploy/README.md`**.

Dos detalles del diseño que conviene no romper:
- `database.py::_base_dir()` y `main.py` resuelven `.env`, `printnet.db` y
  `uploads/` **junto al ejecutable** cuando corre congelado (`sys.frozen`), no
  en el temporal de extracción de PyInstaller — que se borra al cerrar.
- Los servicios corren como `LocalSystem`, cuyo perfil NO es el del usuario:
  por eso las credenciales del túnel se copian a la carpeta de instalación y
  se pasan con `--config` y `TUNNEL_ORIGIN_CERT` absolutos.

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
- **orders** `(id, token UUID4 UNIQUE, tipo 'fotocopias'|'fotos', customer_id FK, estado, pagado=0, requiere_manual, precio_total NULL para fotos, opciones JSON, printer_id FK NULL, mp_preference_id, mp_payment_id, created_at, updated_at)`.
  Migración v1 (`user_version=1`): recrea la tabla para sumar los estados de pago al CHECK y las columnas `mp_*` (SQLite no permite alterar CHECKs).
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

```
pendiente_pago ──(webhook approved)──→ [confirmar_pago] → pendiente | imprimiendo
      │                                                        │
      ├──(webhook rejected)──→ pago_rechazado                  ▼
      │                              │              imprimiendo → listo → entregado
      └──(admin)──→ cancelado ←──────┘                    (admin, PATCH)
```

- `pendiente_pago` y `pago_rechazado` los maneja **solo el flujo de pago**
  (webhook); el admin únicamente puede cancelarlos.
- El resto igual que antes: `pendiente → imprimiendo → listo → entregado`,
  `cancelado` desde pendiente/imprimiendo/listo. `entregado` y `cancelado`
  finales. Transición inválida → `409`.
- Los pedidos con `pagado=1` nunca vuelven atrás (un webhook de rechazo
  posterior no "des-paga").

Triage al crear (decisión de arquitectura 2):
- **fotocopias**: dispatch simulado automático a la primera impresora `activa` → nace en `imprimiendo` (si no hay impresora activa queda `pendiente`). `requiere_manual = true` solo si trae terminaciones (complementa el dispatch, no lo reemplaza).
- **fotos**: nunca se despachan; nacen `pendiente` con `requiere_manual = true` y `precio_total = null` (se cotizan a mano).

## Precios (`pricing.py` — hardcodeado, sin endpoint de edición)

**Tramos por cantidad, PLANOS (no marginales)**: el precio del tramo en el que
cae la cantidad total de la línea se aplica a *todas* las unidades. 300 copias
B&N simple = 300 × $130 (no 19×200 + 80×150 + 201×130).

| Combinación | Tramos (unidad → $ c/u) |
|---|---|
| B&N simple | 1–19 → $200 · 20–99 → $150 · 100+ → $130 |
| B&N doble | 1–49 → $200 · 50+ → $150 |
| Color simple | 1–19 → $400 · 20+ → $300 |
| Color doble | 1–19 → $600 · 20+ → $450 |

- **Unidad**: copias en simple faz, **hojas físicas** en doble faz
  (`hojas = ceil(carillas / 2)`; el tramo y el total se calculan sobre hojas,
  no sobre carillas). Ej.: 96 págs doble faz = 48 hojas → $9.600.
- **Ámbito del tramo**: la línea completa, o sea `hojas_por_copia × copias`.
  2 copias de 10 págs simple = 20 unidades → cae en el tramo 20–99.
- **A3**: recargo del 50% sobre el total (dimensión aparte de los tramos).
- **Terminaciones**: Anillado (solo /fotocopias, automático) $2.000 por copia
  hasta 100 hojas, $3.500 con más de 100 — se suma al total.
  Plastificado ($1.400 A4 / $700 media hoja) y Corte ($500 A4) quedan como
  referencia: los pedidos de /fotos se cotizan a mano.

Fuera del motor de precios (se cobran en el local): escaneo $100, edición
$2.000, fotocopia DNI $400, foto carnet $2.000.

Tests: `.venv/bin/python test_pricing.py` — cubre los bordes de cada tramo
(19/20, 49/50, 99/100, 19/20 en color), los ejemplos de la spec de precios,
páginas impares en doble faz y el carácter plano del bracket.
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
- Respuesta: `{ id, token, tipo, estado, pagado, init_point, precio_total, requiere_manual, archivos: [nombres], paginas }`
  - **Modo MercadoPago** (fotocopias con `MP_ACCESS_TOKEN` configurada): `estado: "pendiente_pago"`, `pagado: false`, `init_point` = URL de Checkout Pro **a la que el frontend debe redirigir**. El dispatch y el email quedan para el webhook.
  - **Modo fantasma o pedido /fotos**: `estado` final directo (imprimiendo/pendiente), `pagado: true`, `init_point: null` — igual que Fase 1.
- Errores: 422 validación (formato `[{campo, error}]`), 413 archivo grande, 502 si MercadoPago no responde al crear la preferencia.

### `POST /webhooks/mercadopago` → 200
Notificaciones de pago de MercadoPago (server-to-server).
1. Valida la firma del header `x-signature` (HMAC-SHA256 con `MP_WEBHOOK_SECRET`
   sobre el template `id:{data.id};request-id:{x-request-id};ts:{ts};`).
   Firma inválida o secret sin configurar → **401** + log del intento.
2. Ignora (200) notificaciones que no sean `type=payment`.
3. Consulta `GET /v1/payments/{data.id}` con `MP_ACCESS_TOKEN` — nunca confía
   en el body de la notificación. Si MP no responde → 500 (MP reintenta).
4. Busca el pedido por `external_reference` (= token interno):
   `approved` → `confirmar_pago()` (idempotente) + email "recibido";
   `rejected`/`cancelled` → `pago_rechazado` (solo si aún no estaba pagado);
   otros estados → sin acción.
5. Responde 200 en menos de 1s (límite de MP: 22s).

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

## print_dispatch

`PrintDispatcher.dispatch(printer_nombre, file_path, options) → DispatchResult(ok, detalle)`.
Implementados: `SimulatedDispatcher` (default) y `SumatraDispatcher` (Windows).
Pendiente, si el backend se muda a una Pi: `CupsDispatcher` (Linux, `lp`).
Selección por env `PRINTNET_DISPATCH` (default `simulated`). Atajo funcional: `dispatch_print(...)`.

### SumatraDispatcher (Windows)

Env: `PRINTNET_DISPATCH=sumatra` y `PRINTNET_SUMATRA` = ruta al `SumatraPDF.exe`
(default `C:\PrintNet\SumatraPDF.exe`).

Comando que arma `construir_comando()`:

```
SumatraPDF.exe -print-to "RICOH IM C4500 PCL 6"
               -print-settings "3-8,monochrome,duplexlong,2x,fit"
               -silent -exit-when-done  temporal-ya-normalizado.pdf
```

| Nuestra opción | Token de `-print-settings` |
|---|---|
| `color: byn` / `color` | `monochrome` / `color` |
| `caras: simple` / `doble` | `simplex` / `duplexlong` |
| `copias: N` | `Nx` |
| `rango: {modo: "rango", valor: "3-8"}` | `3-8`, antepuesto |
| `rango: {modo: "todas"}` | (no se emite token) |
| — siempre — | `fit` |
| `tamano: A4` / `A3` | **no se emite** — ver abajo |

### El tamaño de papel NO se pide por línea de comandos

Verificado empíricamente contra la Ricoh IM C4500 (2026-08-14). Se probaron
cuatro caminos y **los cuatro se ignoran en silencio**:

1. `paper=A3` en `-print-settings` (también en minúscula, `paper=a3`)
2. `bin=2`, apuntando a la bandeja que tiene el A3 cargado
3. `Set-PrintConfiguration -PaperSize A3` sobre la cola
4. Una segunda cola de Windows (`RICOH IM C4500 A3`) con A3 fijado a mano en
   el driver, tanto en *Preferencias de impresión* como en *Valores
   predeterminados*

En la misma prueba, el resto de los tokens del bloque **sí** se respetaban
(rango, color, faz, copias) — no era que SumatraPDF descartara la lista
entera. Y un PDF cuyas páginas **son** A3 sale en A3 sin pedir nada.

Conclusión: SumatraPDF toma el tamaño del papel del **tamaño de página del
PDF**. Por eso el tamaño se resuelve en `pdf_normalize.py`, reescribiendo el
documento antes de imprimir, y `construir_comando()` no emite `paper=`.

(El driver **sí** hace A3 correctamente cuando se elige a mano en su diálogo
de impresión: el problema es del canal por línea de comandos, no del equipo.)

Las tres opciones de impresión se emiten **siempre explícitas**: el driver de
la Ricoh tiene dúplex activado en sus preferencias por defecto, así que omitir
un token no significa "como venga" sino "como esté ese diálogo".

`fit` escala al tamaño de hoja elegido por el cliente (decisión tomada: un A4
pedido en A3 debe llenar la hoja A3, no salir chico y centrado).

**`ok=True` significa "se encoló", no "salió el papel".** SumatraPDF entrega
el trabajo al spooler de Windows y vuelve enseguida; si la impresora se traba
o se queda sin toner, el pedido igual figura despachado. Verificar la cola de
Windows está fuera de alcance por ahora.

Ningún camino de error propaga excepciones (ejecutable ausente, PDF ausente,
opciones inválidas, timeout de 120 s, código de salida ≠ 0): todos devuelven
`DispatchResult(ok=False)`. Es deliberado — esto corre dentro del webhook de
MercadoPago, y una excepción haría que MP reintentara el pago.

Tests: `test_dispatch.py` (sin Windows ni impresora — inyecta un ejecutor
falso, verifica el comando armado y mide el PDF que recibiría SumatraPDF).

## pdf_normalize

`normalizar_pdf(origen, destino, tamano) → ResultadoNormalizacion(paginas, convertidas)`.

Reescribe el PDF con todas sus páginas en el tamaño pedido, escalando el
contenido proporcionalmente y centrándolo. Lo llama `SumatraDispatcher` antes
de cada impresión, sobre un temporal que se borra solo.

**Se normaliza siempre, no solo cuando el pedido es A3.** Si el papel sigue al
documento, un cliente que sube un PDF A3 y paga precio de A4 imprimiría en A3.
Normalizar en las dos direcciones es lo que hace que lo impreso coincida con
lo cobrado.

Detalles: la orientación de cada página se conserva (una A4 apaisada va a A3
apaisada); un documento con páginas de tamaños mezclados sale entero en el
tamaño pedido; las páginas que ya están bien se copian sin reescalar; se usa
`min()` al escalar, así que entra todo y no se recorta nada — un tamaño de
proporción distinta (carta) queda centrado con margen parejo. Las páginas con
`/Rotate` se resuelven con `transfer_rotation_to_content()` antes de medir.

Tests: `test_pdf_normalize.py` (16 casos).

## Variables de entorno de MercadoPago

Ver `.env.example`. **Nunca commitear ni loggear los valores reales.**

| Variable | Qué es |
|---|---|
| `MP_ACCESS_TOKEN` | Token privado (empezar con credenciales de prueba `TEST-...`). Sin ella → modo fantasma. |
| `MP_WEBHOOK_SECRET` | Clave secreta del webhook (se genera en el panel de MP al configurar la notificación). |
| `BASE_URL_PUBLICA` | URL pública del backend (Cloudflare Tunnel en dev); arma la `notification_url` en runtime. |
| `PRINTNET_FRONTEND_URL` | URL del frontend para las `back_urls` (`/estado/{token}`). Default `http://localhost:5173`. |

## Cómo probar con credenciales de prueba de MercadoPago

1. En https://www.mercadopago.com.ar/developers crear una aplicación y, en
   "Cuentas de prueba", crear **dos cuentas test**: una vendedora y una compradora.
2. Con la cuenta vendedora, copiar el **Access Token de prueba** (`TEST-...`)
   → `MP_ACCESS_TOKEN`.
3. Exponer el backend local con Cloudflare Tunnel:
   `cloudflared tunnel --url http://localhost:8000` → copiar la URL a `BASE_URL_PUBLICA`.
4. En el panel de la aplicación → Webhooks, configurar la URL
   `{BASE_URL_PUBLICA}/webhooks/mercadopago` (evento: Pagos) y copiar la
   **clave secreta** que genera MP → `MP_WEBHOOK_SECRET`.
5. Levantar el backend con esas env vars y crear un pedido de /fotocopias:
   la respuesta trae `init_point`. Abrirlo, loguearse con la **cuenta
   compradora de prueba** y pagar con las tarjetas de test de MP
   (ej. Mastercard `5031 7557 3453 0604`, cualquier vencimiento futuro,
   CVV `123`, nombre `APRO` para aprobar / `OTHE` para rechazar).
6. Verificar: el webhook llega (log del server), el pedido pasa a
   `imprimiendo` (`GET /orders/status/{token}`), hay fila en `dispatch_log`
   y el email "recibido" queda en `notifications`.

> El flujo completo también está verificado sin credenciales con la API de MP
> mockeada (19 chequeos: firma inválida→401, aprobado→dispatch+email,
> idempotencia de reintentos, rechazo→pago_rechazado, referencia inexistente).

### Circuito de frontend ✔ completo
- /fotocopias redirige a `init_point` cuando la respuesta lo trae.
- Página `/estado/{token}` (destino de las `back_urls`): badge de estado,
  descripción, archivos, total; se refresca sola cada 10s.
- Badges en /admin para `pendiente_pago` y `pago_rechazado`.

### Setup Vercel + Cloudflare Tunnel (dev con pagos reales)
- El frontend en Vercel (https://printnet.vercel.app) usa la env
  `VITE_PRINTNET_API` (variable de build: cambiarla requiere redeploy).
- El backend local se expone con `cloudflared tunnel --url http://localhost:8000`.
  **La URL del quick tunnel cambia en cada arranque** → al reiniciar el tunnel
  hay que actualizar: `BASE_URL_PUBLICA` en `.env`, `VITE_PRINTNET_API` en
  Vercel (+ redeploy) y la URL del webhook en el panel de MercadoPago.
- El backend carga `backend-printnet/.env` automáticamente (python-dotenv).

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
- ~~Fase 3a: MercadoPago real (Checkout Pro + webhook)~~ ✔ hecho (quedan los
  pendientes de frontend listados arriba; reembolsos/contracargos fuera de alcance).
- Fase 3b: impresión real (CUPS en la Pi / SumatraPDF en Windows).
- Fase 4: WhatsApp, endpoints de mutación de impresoras (hoy el sidebar usa estado local).
