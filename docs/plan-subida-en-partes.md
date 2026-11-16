# Plan: subida en partes (archivos de hasta 300 MB)

> Diseño acordado el 2026-11-16. Reemplaza la "Fase 2 — Una sola subida" de
> [`plan-conversion-de-formatos.md`](plan-conversion-de-formatos.md): esto la
> resuelve de paso.

## El problema

Cloudflare, en el plan gratuito, corta las peticiones de más de 100 MB. Por eso
el límite actual es 95 MB por pedido, y hay clientes con archivos más grandes
(tesis, libros escaneados).

El límite es **por petición**, no por archivo. Si el archivo viaja partido en
pedazos de 6 MB, cada uno en su propia petición, el techo de Cloudflare deja de
importar.

Además, hoy cada archivo **se sube dos veces**: una en `POST /orders/paginas`
para contar páginas y mostrar el precio, y otra en `POST /orders` al pagar. Con
300 MB eso es inaceptable.

## Qué se decidió

- **Límite nuevo: 300 MB sobre el total del pedido** (la regla de "sobre el
  total" ya estaba decidida en `plan-multiples-archivos.md`).
- **Subida en partes hecha por nosotros**, sin librerías nuevas. Se descartaron
  el protocolo tus (dependencias en los dos lados, librerías para FastAPI poco
  mantenidas, riesgo con PyInstaller) y subir a Cloudflare R2 (una pieza más en
  la nube que puede fallar sin avisar, contra la decisión de que todo viva en
  la notebook).
- **Solo para `/fotocopias`.** `/fotos` sigue como hoy: son imágenes, se cotizan
  a mano y no chocaron con el límite.
- Si se corta la conexión, la web **reintenta el pedazo** sola. Si el cliente
  cierra la pestaña, empieza de cero: no se reanudan subidas entre sesiones.

## Qué ve el cliente

1. Elige el archivo → barra de progreso: "Subiendo… 42 de 180 MB".
2. "Preparando el documento…" (el servidor junta, convierte si hace falta y
   cuenta páginas).
3. Aparecen las páginas y el precio.
4. Paga → va directo a MercadoPago, **sin volver a subir nada**.

## El protocolo

| Paso | Endpoint | Qué hace |
|---|---|---|
| 1 | `POST /uploads` | Recibe `{nombre, tamano_bytes, content_type}`. Valida formato y tamaño. Devuelve `{id, parte_bytes}`. |
| 2 | `PUT /uploads/{id}/partes/{n}` | Recibe el pedazo `n` (cuerpo crudo, ≤ `parte_bytes`). Idempotente: reintentar el mismo `n` lo pisa. |
| 3 | `POST /uploads/{id}/completar` | Contesta **al instante** `{estado: "preparando"}` y en segundo plano junta los pedazos, verifica el tamaño, convierte con LibreOffice si hace falta y cuenta páginas. |
| 4 | `GET /uploads/{id}` | `{estado: "subiendo" \| "preparando" \| "listo" \| "error", paginas, convertido, error}`. La web pregunta cada 2 s. |
| 5 | `POST /orders` | Acepta un campo de formulario `uploads` (JSON con la lista de ids, emparejados con `documentos` por posición, igual que hoy `files`). |

Ninguna petición pesa más de 6 MB ni tarda más de unos segundos, así que no
aparecen ni el límite de Cloudflare ni su corte de 100 s por respuesta.

### Detalles que importan

- **El tamaño del pedazo lo dicta el servidor** (`parte_bytes` en el paso 1).
  La web no lo tiene escrito: así no hay otro número duplicado.
- **El límite de 300 MB se controla tres veces:** en la web antes de subir; en
  `POST /uploads` sobre el tamaño anunciado; y al juntar, verificando que lo
  recibido pese exactamente lo anunciado. En `POST /orders` se valida además la
  **suma** de las subidas del pedido.
- **Directo a disco.** Cada pedazo se escribe como archivo propio
  (`partes/00007`) y al completar se concatenan. Nunca se tiene el archivo
  entero en memoria (hoy `_guardar_archivos` lo lee entero: con 95 MB pasaba,
  con 300 MB en la notebook no conviene).
- **Dónde vive:** `uploads/_subidas/{id}/` con un `meta.json` (nombre,
  tamaño, estado, páginas, rutas). Sin tabla nueva en la base: es estado
  temporal y se borra solo. Al crear el pedido, el original y el PDF se
  **mueven** a `uploads/{token}/` y el resto del flujo sigue igual que hoy.
- **Una subida, un pedido.** Al moverse deja de existir, así que no se puede
  usar dos veces. El id es un `uuid4`: conocerlo es lo único que da acceso,
  igual que el token de seguimiento.
- **Limpieza:** al arrancar el servidor y cada hora se borran las subidas con
  más de 24 h. **Tope de disco:** si `_subidas/` supera 3 GB, `POST /uploads`
  responde 503 ("probá en un rato") para que nadie pueda llenar el disco de la
  notebook.
- **Compatibilidad:** `POST /orders` sigue aceptando `files` como hoy, y
  `POST /orders/paginas` sigue existiendo. El orden del deploy no importa (web
  vieja + backend nuevo funciona). Mandar `files` y `uploads` a la vez es un
  error 422.

## Lo que la subida grande rompe más allá de la subida

### La impresión no puede seguir adentro del webhook

Hoy `webhook_mercadopago()` → `confirmar_pago()` → `despachar_pedido()`, que
normaliza el PDF y llama a SumatraPDF **sincrónicamente** (cada uno con hasta
120 s de timeout). Con un PDF de 300 MB el webhook pasa los 100 s, Cloudflare
lo corta, MercadoPago reintenta, y como `pagado = 1` recién se guarda al final,
**el reintento puede despachar el pedido otra vez: doble impresión.**

El arreglo: `confirmar_pago()` marca el pedido como pagado y **hace commit
antes de despachar**; el despacho corre en segundo plano (`BackgroundTasks`,
con su propia conexión a la base). La idempotencia pasa a ser real aun con
reintentos simultáneos. Esto aplica también al modo fantasma.

`reimprimir` queda sincrónico a propósito: el operador necesita ver en el
momento cuántos documentos entraron. Si la medición muestra que un PDF de
300 MB tarda más de 100 s, se documenta como trampa (Cloudflare corta la
respuesta pero la impresora sigue: mirar antes de volver a apretar).

### Timeouts de LibreOffice y SumatraPDF

`document_convert.TIMEOUT_SEG` y `SumatraDispatcher.TIMEOUT_SEG` son 120 s.
Puede que con 300 MB no alcancen. Se ajustan según lo que mida el paso 0.

## Orden de implementación

0. **Medir en la notebook, antes de escribir el resto.** Generar un PDF pesado
   (~300 MB, con imágenes, como un escaneo) y medir `pdf_normalize`, el conteo
   de páginas, LibreOffice con un `.docx` grande y SumatraPDF hasta la Ricoh:
   tiempo y memoria. Si `pdf_normalize` (pypdf) no da, se rediseña eso primero.
1. Sacar el despacho del webhook (commit antes de imprimir, despacho en
   segundo plano). Es independiente y reduce riesgo aunque nunca se suba nada
   grande.
2. Backend: `routers/uploads.py` + `test_uploads.py`.
3. Backend: `POST /orders` con `uploads`, límite total 300 MB.
4. Web: `subirArchivo(file, alProgresar)` en `api.js`, barra de progreso y
   "Preparando…" en `FileUpload.jsx`, `Fotocopias.jsx` manda ids.
5. Límites: `limites.js` y `orders.py` (300 MB para fotocopias por subida en
   partes; el camino viejo con `files` queda en 95 MB, porque ese sí pasa
   entero por Cloudflare). Comentarios cruzados como hoy.
6. Deploy: backend primero (compatible), después la web. `ESTADO.md` al día.

## Pruebas

`test_uploads.py`, script pelado con `check()`, sin pytest:

- pedazos en orden y fuera de orden; reintentar un pedazo lo pisa sin duplicar;
- falta un pedazo al completar → error claro;
- lo recibido no coincide con el tamaño anunciado → error;
- tamaño anunciado > 300 MB → 413; pedazo más grande que `parte_bytes` → 413;
- id inexistente o ya usado por un pedido → 404;
- limpieza borra lo de más de 24 h y no toca lo reciente; tope de 3 GB → 503;
- `POST /orders` con `uploads`: emparejamiento por posición, suma > 300 MB → 413,
  `files` y `uploads` juntos → 422, archivos movidos a `uploads/{token}/`.

`test_order_flow.py` suma: el pedido queda `pagado = 1` y commiteado antes de
despachar, y una segunda confirmación mientras el despacho corre no vuelve a
imprimir.

De punta a punta: en el navegador, con un PDF de 150 MB contra el backend
local (barra, reintentos, cancelar, pago en modo fantasma), y después en
producción con uno de más de 100 MB hasta llegar a MercadoPago.
`prueba_pedido.py` sigue probando el camino viejo, que tiene que seguir
andando mientras la web vieja esté publicada.
