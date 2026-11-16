# Subida en partes — plan de implementación

> **Para agentes:** SUB-SKILL REQUERIDA: usar superpowers:subagent-driven-development
> (recomendado) o superpowers:executing-plans para implementar este plan tarea
> por tarea. Los pasos usan casillas (`- [ ]`) para el seguimiento.

**Objetivo:** que un cliente pueda mandar a imprimir hasta 300 MB por pedido a
pesar del techo de 100 MB por petición de Cloudflare, subiendo cada archivo
una sola vez.

**Arquitectura:** el navegador parte el archivo en pedazos de 6 MB y los manda
uno por uno a endpoints nuevos (`/uploads`). La notebook los rearma en disco,
prepara el documento en segundo plano (convierte y cuenta páginas) y el pedido
referencia la subida por id. Antes de eso, la impresión sale del webhook de
MercadoPago, porque con archivos grandes un reintento del webhook podía
imprimir el pedido dos veces.

**Stack:** FastAPI + SQLite (Python 3.11, compilado con PyInstaller), React +
Vite. **Sin dependencias nuevas.**

Diseño: [`plan-subida-en-partes.md`](plan-subida-en-partes.md).

## Restricciones globales

- Todo en español, voseo: código, comentarios, mensajes al cliente y commits.
- Los comentarios explican el *por qué*. No borrar comentarios que documentan
  una trampa sin entender qué trampa documentan.
- Tests: scripts pelados con `check()`, sin pytest y sin httpx. Se corren con
  `cd backend-printnet && .venv/bin/python test_X.py` y terminan con
  `sys.exit(1)` si algo falla.
- Sin dependencias nuevas, ni en el backend (rompen el `.exe` de PyInstaller)
  ni en la web.
- Pedazo: **6 MB** (`6 * 1024 * 1024`), lo dicta el servidor.
- Límite: **300 MB sobre el total del pedido** para la subida en partes. El
  camino viejo (`files` en `POST /orders`, `POST /orders/paginas`) queda en
  **95 MB**, porque ese sí viaja entero por Cloudflare.
- Las subidas que no terminan en pedido se borran a las **24 h**. Tope de
  disco para subidas en curso: **3 GB**.
- `/fotos` no cambia.
- Compatibilidad: backend nuevo + web vieja tiene que funcionar. Se despliega
  primero el backend.
- Los comandos para la notebook van **de a uno, en una sola línea**: el
  usuario los relaya a mano.

## Mapa de archivos

| Archivo | Qué hace | Tarea |
|---|---|---|
| `backend-printnet/medir_archivo_grande.py` (nuevo) | Genera un PDF pesado y mide conteo, normalización e impresión de una hoja | 0 |
| `backend-printnet/order_flow.py` | `confirmar_pago` solo marca; `despachar_tras_pago` imprime con conexión propia | 1 |
| `backend-printnet/routers/webhooks.py`, `routers/orders.py` | Agendan el despacho en segundo plano | 1 |
| `backend-printnet/test_order_flow.py` | Adaptado al flujo nuevo + idempotencia real | 1 |
| `backend-printnet/subidas.py` (nuevo) | Toda la lógica de la subida en partes, sin FastAPI | 2 |
| `backend-printnet/test_subidas.py` (nuevo) | Tests de `subidas.py` | 2 |
| `backend-printnet/routers/subidas.py` (nuevo) | Los 4 endpoints, finitos: traducen a `subidas.py` | 3 |
| `backend-printnet/main.py` | Registra el router y la limpieza cada hora | 3 |
| `backend-printnet/routers/orders.py` | `POST /orders` acepta `uploads` | 4 |
| `backend-printnet/test_crear_pedido_subidas.py` (nuevo) | Tests de `crear_pedido` con subidas | 4 |
| `frontend/src/api.js` | `subirArchivo()` y `crearPedidoConSubidas()` | 5 |
| `frontend/src/limites.js` | 95 → 300 MB | 5 |
| `frontend/src/components/fotocopias/FileUpload.jsx` | Barra de progreso, "Preparando…" | 5 |
| `frontend/src/pages/Fotocopias.jsx` | Estado `subiendo`, cancelar al quitar, manda ids | 5 |
| `ESTADO.md`, `backend-printnet/SPEC.md` | Al día | 6 |

---

### Tarea 0: Medir en la notebook antes de construir

Es una **compuerta**: si `pdf_normalize` o SumatraPDF no aguantan un PDF de
300 MB, el resto del plan se frena y se rediseña esa parte primero.

**Archivos:**
- Crear: `backend-printnet/medir_archivo_grande.py`

**Interfaces:**
- Consume: `pdf_normalize.normalizar_pdf(origen, destino, tamano)`,
  `print_dispatch.SumatraDispatcher().dispatch(impresora, ruta, opciones)`,
  `document_convert.convertir_a_pdf(origen, carpeta)`.
- Produce: nada que usen otras tareas. Es una herramienta de diagnóstico.

- [ ] **Paso 1: escribir el script**

```python
"""Mide cuánto tarda la notebook con un PDF pesado, antes de aceptarlos.

Por qué existe: la subida en partes deja llegar archivos de hasta 300 MB, pero
subirlos es la parte fácil. Después hay que contar sus páginas, normalizarlos
al tamaño de papel (pdf_normalize reescribe el PDF entero con pypdf) y
mandarlos a SumatraPDF, y todo eso corre en la notebook del local. Esto mide
cada paso con un archivo del peor tamaño, para saber si aguanta ANTES de abrir
la puerta. Ver docs/plan-subida-en-partes.md.

    .venv\\Scripts\\python medir_archivo_grande.py
    .venv\\Scripts\\python medir_archivo_grande.py --megas 300 --memoria
    .venv\\Scripts\\python medir_archivo_grande.py --imprimir-una-hoja
    .venv\\Scripts\\python medir_archivo_grande.py --documento C:\\PrintNet\\grande.docx

--imprimir-una-hoja manda a la Ricoh SOLO la página 1 (una hoja), pero
SumatraPDF igual tiene que abrir el archivo entero: mide lo mismo que un
pedido real sin gastar 100 hojas.

Herramienta de diagnóstico, no parte del servidor.
"""

import argparse
import math
import os
import sys
import tempfile
import time
import tracemalloc

from document_convert import convertir_a_pdf
from pdf_normalize import normalizar_pdf
from print_dispatch import SumatraDispatcher
from pypdf import PdfReader

TAMANOS = {"A4": (595, 842), "A3": (842, 1191)}

# Imagen de ruido sin comprimir: 1000 x 1000 RGB = ~2,9 MB por página. Ruido
# porque no se comprime, así el archivo pesa lo que dice; un escaneo real es
# JPEG, pero lo que cuesta acá es la cantidad de bytes que pypdf mueve.
LADO = 1000
BYTES_IMAGEN = LADO * LADO * 3

# Contra qué comparar. Cloudflare corta una respuesta que tarda más de 100 s;
# SumatraDispatcher y document_convert cortan a los 120 s.
LIMITE_CLOUDFLARE_SEG = 100
TIMEOUT_SUMATRA_SEG = SumatraDispatcher.TIMEOUT_SEG


def generar_pesado(ruta: str, megas: int, tamano: str = "A4") -> int:
    """Escribe un PDF de ~`megas` MB directo a disco. Devuelve las páginas.

    Se escribe objeto por objeto para no tener 300 MB en memoria: eso mediría
    al generador, no a la notebook.
    """
    paginas = max(1, math.ceil(megas * 1024 * 1024 / BYTES_IMAGEN))
    ancho, alto = TAMANOS[tamano]
    offsets: dict[int, int] = {}

    with open(ruta, "wb") as f:
        def objeto(numero: int, *partes: bytes) -> None:
            offsets[numero] = f.tell()
            f.write(f"{numero} 0 obj\n".encode())
            for p in partes:
                f.write(p)
            f.write(b"\nendobj\n")

        f.write(b"%PDF-1.4\n")
        # 1: catálogo, 2: árbol de páginas. Por página i: 3+3i la página,
        # 4+3i su contenido, 5+3i su imagen.
        kids = " ".join(f"{3 + 3 * i} 0 R" for i in range(paginas))
        objeto(1, b"<< /Type /Catalog /Pages 2 0 R >>")
        objeto(2, f"<< /Type /Pages /Kids [{kids}] /Count {paginas} >>".encode())

        flujo = f"q {ancho} 0 0 {alto} 0 0 cm /Im0 Do Q".encode()
        for i in range(paginas):
            pagina, contenido, imagen = 3 + 3 * i, 4 + 3 * i, 5 + 3 * i
            objeto(pagina, (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {ancho} {alto}] "
                f"/Resources << /XObject << /Im0 {imagen} 0 R >> >> "
                f"/Contents {contenido} 0 R >>"
            ).encode())
            objeto(contenido, f"<< /Length {len(flujo)} >>\nstream\n".encode(),
                   flujo, b"\nendstream")
            objeto(imagen, (
                f"<< /Type /XObject /Subtype /Image /Width {LADO} /Height {LADO} "
                f"/ColorSpace /DeviceRGB /BitsPerComponent 8 "
                f"/Length {BYTES_IMAGEN} >>\nstream\n"
            ).encode(), os.urandom(BYTES_IMAGEN), b"\nendstream")

        total = 2 + 3 * paginas
        inicio_xref = f.tell()
        f.write(f"xref\n0 {total + 1}\n".encode())
        f.write(b"0000000000 65535 f \n")
        for numero in range(1, total + 1):
            f.write(f"{offsets[numero]:010d} 00000 n \n".encode())
        f.write((
            f"trailer\n<< /Size {total + 1} /Root 1 0 R >>\n"
            f"startxref\n{inicio_xref}\n%%EOF\n"
        ).encode())
    return paginas


def medir(nombre: str, funcion, memoria: bool):
    """Corre `funcion`, imprime cuánto tardó (y cuánta memoria pico usó)."""
    if memoria:
        tracemalloc.start()
    inicio = time.perf_counter()
    try:
        resultado = funcion()
    finally:
        segundos = time.perf_counter() - inicio
        pico = tracemalloc.get_traced_memory()[1] if memoria else None
        if memoria:
            tracemalloc.stop()
    extra = f", memoria pico {pico / 1024 / 1024:.0f} MB" if pico is not None else ""
    aviso = "   <-- PASA LOS 100 s DE CLOUDFLARE" if segundos > LIMITE_CLOUDFLARE_SEG else ""
    print(f"  {nombre}: {segundos:.1f} s{extra}{aviso}")
    return resultado, segundos


def main() -> int:
    p = argparse.ArgumentParser(description="Mide la notebook con un PDF pesado.")
    p.add_argument("--megas", type=int, default=300)
    p.add_argument("--memoria", action="store_true",
                   help="Mide la memoria pico de Python (hace todo ~2x más lento)")
    p.add_argument("--imprimir-una-hoja", action="store_true",
                   help="Manda la página 1 a la impresora real")
    p.add_argument("--impresora",
                   default=os.environ.get("PRINTNET_IMPRESORA", "RICOH IM C4500 PCL 6"))
    p.add_argument("--documento",
                   help="Un .docx/.pptx grande propio, para medir LibreOffice")
    args = p.parse_args()

    with tempfile.TemporaryDirectory(prefix="printnet-medicion-") as carpeta:
        pdf = os.path.join(carpeta, "pesado.pdf")
        print(f"\nGenerando un PDF de ~{args.megas} MB...")
        paginas, _ = medir("generar", lambda: generar_pesado(pdf, args.megas), False)
        print(f"  -> {paginas} páginas, {os.path.getsize(pdf) / 1024 / 1024:.0f} MB")

        print("\nPasos del servidor:")
        medir("contar páginas (pypdf)", lambda: len(PdfReader(pdf).pages), args.memoria)
        medir("normalizar A4 -> A4 (copia)",
              lambda: normalizar_pdf(pdf, os.path.join(carpeta, "a4.pdf"), "A4"),
              args.memoria)
        medir("normalizar A4 -> A3 (reescala)",
              lambda: normalizar_pdf(pdf, os.path.join(carpeta, "a3.pdf"), "A3"),
              args.memoria)

        if args.imprimir_una_hoja:
            opciones = {
                "opciones": {"color": "byn", "caras": "simple", "copias": 1, "tamano": "A4"},
                "rango": {"modo": "rango", "valor": "1"},
            }
            r, segundos = medir(
                f"normalizar + SumatraPDF a '{args.impresora}' (1 hoja)",
                lambda: SumatraDispatcher().dispatch(args.impresora, pdf, opciones),
                False,
            )
            print(f"  -> ok={r.ok}: {r.detalle}")
            if segundos > TIMEOUT_SUMATRA_SEG * 0.8:
                print(f"  OJO: cerca del timeout de SumatraDispatcher ({TIMEOUT_SUMATRA_SEG} s)")

        if args.documento:
            r, _ = medir("LibreOffice -> PDF",
                         lambda: convertir_a_pdf(args.documento, carpeta), False)
            print(f"  -> ok={r.ok}: {r.detalle}")

    print("\nListo. Pasale estos números a quien esté desarrollando.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Paso 2: correrlo en el Mac, chico, para ver que funciona**

Run: `cd backend-printnet && .venv/bin/python medir_archivo_grande.py --megas 30 --memoria`
Expected: las líneas `generar`, `contar páginas`, `normalizar A4 -> A4`,
`normalizar A4 -> A3` con sus segundos y memoria, ~11 páginas, ~30 MB, y
`Listo.` al final, sin traceback.

- [ ] **Paso 3: correrlo en el Mac con 300 MB**

Run: `cd backend-printnet && .venv/bin/python medir_archivo_grande.py --megas 300 --memoria`
Expected: ~106 páginas. Anotar los tiempos y la memoria pico: son la base de
comparación para la notebook.

- [ ] **Paso 4: commit**

```bash
git add backend-printnet/medir_archivo_grande.py
git commit -m "feat: script para medir la notebook con un PDF pesado

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Paso 5: correrlo en la notebook (lo relaya el usuario, de a un comando)**

1. `cd C:\PrintNet\printnet`
2. `git pull`
3. `cd backend-printnet`
4. `.venv\Scripts\python medir_archivo_grande.py --megas 300 --memoria`
5. `.venv\Scripts\python medir_archivo_grande.py --megas 300 --imprimir-una-hoja`
   (sale **una hoja** de ruido por la Ricoh, es esperable)

No hace falta parar el servicio: el script no toca la base ni `uploads\`.

- [ ] **Paso 6: decidir con los números**

| Resultado en la notebook | Qué se hace |
|---|---|
| Normalizar A4→A3 y SumatraPDF < 80 s, memoria pico < 1 GB | Seguir con la Tarea 1. |
| SumatraPDF entre 80 y 120 s | Seguir, y en la Tarea 1 subir `SumatraDispatcher.TIMEOUT_SEG` a 300 (el despacho ya no corre adentro de ningún request, así que no hay otro límite). |
| SumatraPDF > 120 s o falla | Igual que la fila anterior, y anotar en `ESTADO.md` que reimprimir un pedido así desde el panel puede mostrar error de tiempo aunque se haya impreso (ver nota de la Tarea 1). |
| Memoria pico > 1,5 GB o la notebook se cuelga | **Frenar.** Rediseñar `pdf_normalize` antes de seguir; no abrir la puerta a 300 MB. |

---

### Tarea 1: Sacar la impresión del webhook

Independiente de la subida: reduce riesgo aunque nadie suba nada grande. Hoy
`confirmar_pago()` despacha a la impresora **adentro** del webhook, y
`pagado = 1` recién se guarda al final. MercadoPago espera 22 s
(`routers/webhooks.py` lo dice) y Cloudflare corta a los 100 s: con un PDF
grande, MP reintenta mientras el primer intento sigue imprimiendo, y el
segundo no ve el pedido pagado → **lo imprime otra vez**.

**Archivos:**
- Modificar: `backend-printnet/order_flow.py` (`confirmar_pago`, nueva `despachar_tras_pago`, docstring del módulo)
- Modificar: `backend-printnet/routers/webhooks.py` (rama `approved`, docstring)
- Modificar: `backend-printnet/routers/orders.py` (modo fantasma en `crear_pedido`)
- Modificar: `backend-printnet/test_order_flow.py`

**Interfaces:**
- Produce: `confirmar_pago(conn, order_id) -> bool` — `True` si **esta**
  llamada marcó el pedido como pagado. No imprime. El caller hace commit y,
  si dio `True`, agenda `despachar_tras_pago`.
- Produce: `despachar_tras_pago(order_id: int) -> str` — abre su propia
  conexión, imprime, deja estado/impresora/atención manual y devuelve el
  estado final. Para fotos no hace nada.

- [ ] **Paso 1: adaptar los tests al flujo nuevo (van a fallar)**

En `test_order_flow.py`, cambiar el import:

```python
from order_flow import confirmar_pago, despachar_tras_pago  # noqa: E402
```

Agregar este helper debajo de `leer()`:

```python
def pagar(order_id: int) -> str:
    """El camino real: marcar pagado, commit, y recién después imprimir."""
    conn = database.get_conn()
    confirmar_pago(conn, order_id)
    conn.commit()
    conn.close()
    return despachar_tras_pago(order_id)
```

Reemplazar las **cuatro** apariciones de este bloque (secciones "Todos los
documentos imprimen", "Uno de tres falla", "Fallan todos", "Un solo
documento"):

```python
conn = database.get_conn()
estado = confirmar_pago(conn, pid)
conn.commit(); conn.close()
```

por:

```python
estado = pagar(pid)
```

Reemplazar la sección de idempotencia entera (desde
`print("\n== Idempotencia: ...` hasta el `check` de "no se duplicaron los
despachos") por:

```python
print("\n== Idempotencia: el webhook de MP puede llegar dos veces ==")

pid = armar_pedido(["x.pdf", "y.pdf"])
conn = database.get_conn()
primero = confirmar_pago(conn, pid)
conn.commit()
segundo = confirmar_pago(conn, pid)
conn.commit(); conn.close()
_, despachos = leer(pid)

check("la primera confirmación es la que cuenta", primero, True)
check("la segunda dice que ya estaba pagado", segundo, False)
check("confirmar NO imprime: eso va aparte", len(despachos), 0)

despachar_tras_pago(pid)
_, despachos = leer(pid)
check("se imprime una sola vez, la que agendó la primera", len(despachos), 2)


print("\n== El pago queda guardado ANTES de imprimir ==")
# Lo que evita la doble impresión: si MP reintenta mientras se imprime, el
# reintento tiene que ver el pedido ya pagado. Por eso el commit va antes del
# despacho, y otra conexión lo tiene que ver.

pid = armar_pedido(["z.pdf"])
conn = database.get_conn()
confirmar_pago(conn, pid)
conn.commit(); conn.close()
row, despachos = leer(pid)  # leer() abre otra conexión
check("otra conexión ya lo ve pagado", bool(row["pagado"]), True)
check("todavía sin imprimir", len(despachos), 0)
check("en 'pendiente' mientras espera la impresora", row["estado"], "pendiente")

conn = database.get_conn()
check("un reintento en ese momento no lo vuelve a tomar", confirmar_pago(conn, pid), False)
conn.close()


print("\n== Fotos: se paga pero no se imprime sola ==")

pid = armar_pedido(["foto.jpg"])
conn = database.get_conn()
conn.execute("UPDATE orders SET tipo = 'fotos' WHERE id = ?", (pid,))
conn.commit(); conn.close()
estado = pagar(pid)
_, despachos = leer(pid)
check("queda pendiente para el mostrador", estado, "pendiente")
check("sin despachos", len(despachos), 0)
```

En la sección "Reimprimir", reemplazar:

```python
pid = armar_pedido(["a.pdf", "roto.pdf"])
conn = database.get_conn()
confirmar_pago(conn, pid)
conn.commit()
row, despachos = leer(pid)
```

por:

```python
pid = armar_pedido(["a.pdf", "roto.pdf"])
pagar(pid)
conn = database.get_conn()
row, despachos = leer(pid)
```

Reemplazar:

```python
conn = database.get_conn()
pid2 = armar_pedido(["x.pdf"])
confirmar_pago(conn, pid2)
```

por:

```python
pid2 = armar_pedido(["x.pdf"])
pagar(pid2)
conn = database.get_conn()
```

Y reemplazar:

```python
conn = database.get_conn()
pid3 = armar_pedido(["bien.pdf"])
confirmar_pago(conn, pid3)
```

por:

```python
pid3 = armar_pedido(["bien.pdf"])
pagar(pid3)
conn = database.get_conn()
```

- [ ] **Paso 2: correr y ver que falla**

Run: `cd backend-printnet && .venv/bin/python test_order_flow.py`
Expected: `ImportError: cannot import name 'despachar_tras_pago'`.

- [ ] **Paso 3: implementar en `order_flow.py`**

Agregar el import:

```python
from database import get_conn
```

Reemplazar `confirmar_pago` entera por:

```python
def confirmar_pago(conn: sqlite3.Connection, order_id: int) -> bool:
    """Marca el pedido como pagado. Devuelve True si ESTA llamada lo marcó.

    NO imprime. El caller hace commit y, si dio True, agenda
    `despachar_tras_pago` en segundo plano.

    Antes imprimía acá adentro, o sea adentro del webhook de MercadoPago, y
    `pagado = 1` recién se guardaba al final. Con un PDF grande el webhook
    pasaba los 22 s de MP (y los 100 s de Cloudflare), MP reintentaba, y el
    reintento no veía el pedido pagado: lo imprimía OTRA VEZ. Ahora la marca
    es un UPDATE condicional y se guarda antes de imprimir: de dos
    confirmaciones, aunque lleguen juntas, gana una sola.
    """
    existe = conn.execute("SELECT 1 FROM orders WHERE id = ?", (order_id,)).fetchone()
    if existe is None:
        raise ValueError(f"pedido {order_id} inexistente")
    cur = conn.execute(
        "UPDATE orders SET pagado = 1, estado = 'pendiente',"
        " updated_at = datetime('now') WHERE id = ? AND pagado = 0",
        (order_id,),
    )
    return cur.rowcount == 1


def despachar_tras_pago(order_id: int) -> str:
    """Imprime un pedido recién pagado y deja su estado al día. Devuelve el estado.

    Corre en segundo plano, después de que el request ya respondió, así que
    abre su PROPIA conexión: la del request ya está cerrada.

    Los pedidos de fotos no se imprimen solos: se cotizan y se hacen en el
    mostrador, así que quedan en 'pendiente'.
    """
    conn = get_conn()
    try:
        order = conn.execute(
            "SELECT tipo, estado FROM orders WHERE id = ?", (order_id,)
        ).fetchone()
        if order is None:
            raise ValueError(f"pedido {order_id} inexistente")
        if order["tipo"] != "fotocopias":
            return order["estado"]

        r = despachar_pedido(conn, order_id)
        estado = "pendiente"
        printer_id = None
        if r["despachados"]:
            estado = "imprimiendo"
            printer = conn.execute(
                "SELECT id FROM printers WHERE estado = 'activa' ORDER BY id LIMIT 1"
            ).fetchone()
            printer_id = printer["id"] if printer else None

        # Solo si sigue en 'pendiente': mientras se imprimía, el operador pudo
        # haberlo cancelado o marcado listo, y eso no se pisa.
        conn.execute(
            "UPDATE orders SET estado = ?, printer_id = ?, updated_at = datetime('now')"
            " WHERE id = ? AND estado = 'pendiente'",
            (estado, printer_id, order_id),
        )
        # Un despacho que falla después del pago no se puede "cancelar": el
        # papel de los documentos que sí salieron ya se gastó. Lo único
        # razonable es que el operador se entere antes de entregar el pedido.
        if r["fallados"]:
            conn.execute(
                "UPDATE orders SET requiere_manual = 1 WHERE id = ?", (order_id,)
            )
        conn.commit()
        return estado
    except Exception:
        conn.rollback()
        logger.exception("Pedido %s: falló el despacho tras el pago", order_id)
        # El cliente ya pagó: que el panel lo muestre para reimprimirlo a mano.
        try:
            conn.execute("UPDATE orders SET requiere_manual = 1 WHERE id = ?", (order_id,))
            conn.commit()
        except Exception:
            logger.exception("Pedido %s: tampoco se pudo marcar para revisión", order_id)
        raise
    finally:
        conn.close()
```

En el docstring del módulo, reemplazar:

```
El email "pedido recibido" lo agenda el caller (necesita BackgroundTasks del
request).
```

por:

```
El despacho (`despachar_tras_pago`) y el email "pedido recibido" los agenda el
caller en segundo plano, DESPUÉS de hacer commit de `confirmar_pago`: así el
webhook responde enseguida y un reintento de MercadoPago ve el pedido pagado.
```

Si la Tarea 0 dio SumatraPDF por encima de 80 s, en `print_dispatch.py`
cambiar `TIMEOUT_SEG = 120` por `TIMEOUT_SEG = 300` en `SumatraDispatcher`,
con este comentario encima:

```python
    # 300 y no 120: con un PDF de 300 MB SumatraPDF tarda en abrirlo (medido
    # en la notebook con medir_archivo_grande.py). El despacho ya no corre
    # adentro de ningún request, así que no hay otro límite que respetar.
```

- [ ] **Paso 4: correr y ver que pasa**

Run: `cd backend-printnet && .venv/bin/python test_order_flow.py`
Expected: todas las líneas `ok`, sin `FALLA`, código de salida 0.

- [ ] **Paso 5: adaptar el webhook**

En `routers/webhooks.py`, cambiar el import:

```python
from order_flow import confirmar_pago, despachar_tras_pago
```

Reemplazar la rama `if status == "approved":` entera por:

```python
    if status == "approved":
        recien_pagado = confirmar_pago(db, order["id"])  # idempotente ante reintentos
        # Commit ANTES de imprimir: si MP reintenta mientras la impresora
        # trabaja, el reintento tiene que ver el pedido ya pagado.
        db.commit()
        if recien_pagado:
            background.add_task(despachar_tras_pago, order["id"])
            background.add_task(notifications.notificar_pedido_recibido, order["id"])
        logger.info(
            "Pago %s aprobado → pedido %s %s", data_id, order["id"],
            "a imprimir" if recien_pagado else "(ya estaba pagado)",
        )
        return {"ok": True, "estado": "pagado"}
```

En el docstring del módulo, reemplazar:

```
- pago "approved"  → order_flow.confirmar_pago(): el MISMO flujo post-pago
  de siempre (triage, dispatch simulado, email "recibido").
```

por:

```
- pago "approved"  → order_flow.confirmar_pago() marca el pedido pagado; la
  impresión y el email "recibido" se agendan en segundo plano, después del
  commit, para responder dentro de los 22 s aunque el PDF sea enorme.
```

- [ ] **Paso 6: adaptar el modo fantasma de `crear_pedido`**

En `routers/orders.py`, cambiar el import:

```python
from order_flow import confirmar_pago, despachar_tras_pago
```

Reemplazar:

```python
        estado = confirmar_pago(db, order_id)
        pagado = True
        db.commit()
        background.add_task(notifications.notificar_pedido_recibido, order_id)
```

por:

```python
        confirmar_pago(db, order_id)
        estado, pagado = "pendiente", True
        db.commit()
        # Igual que el webhook: se imprime en segundo plano, así el cliente no
        # espera a la impresora para ver su pedido confirmado.
        background.add_task(despachar_tras_pago, order_id)
        background.add_task(notifications.notificar_pedido_recibido, order_id)
```

Y en el comentario de la rama de MercadoPago, cambiar
`se disparan recién ahí (order_flow.confirmar_pago).` por
`se disparan recién ahí (webhook → confirmar_pago + despachar_tras_pago).`

- [ ] **Paso 7: correr todos los tests y verificar que el backend importa**

Run: `cd backend-printnet && for t in test_*.py; do .venv/bin/python $t > /dev/null || echo "FALLA $t"; done; .venv/bin/python -c "import main; print('ok')"`
Expected: ninguna línea `FALLA`, y `ok`.

- [ ] **Paso 8: probar el modo fantasma de punta a punta**

Run: `cd backend-printnet && (.venv/bin/uvicorn main:app --port 8077 &) && sleep 3 && .venv/bin/python prueba_pedido.py --url http://localhost:8077; pkill -f "uvicorn main:app --port 8077"`
Expected: el pedido se crea (estado `pendiente` en la respuesta) y el
seguimiento que hace `prueba_pedido.py` lo ve pasar a `imprimiendo` (con el
despachador simulado). Si el script espera ver `imprimiendo` en la respuesta
de creación, ajustar ese mensaje del script, no el backend.

- [ ] **Paso 9: commit**

```bash
git add backend-printnet/order_flow.py backend-printnet/routers/webhooks.py backend-printnet/routers/orders.py backend-printnet/test_order_flow.py backend-printnet/print_dispatch.py
git commit -m "fix: la impresión sale del webhook para que MP no imprima dos veces

confirmar_pago ahora solo marca el pedido (UPDATE condicional) y el despacho
corre en segundo plano después del commit. Con un PDF grande el webhook
pasaba los 22 s de MercadoPago y el reintento podía volver a imprimir.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

**Nota sobre reimprimir:** `POST /admin/orders/{id}/reimprimir` sigue
imprimiendo dentro del request, a propósito: el operador necesita ver en el
momento cuántos documentos entraron. Si la Tarea 0 mostró que un PDF de
300 MB tarda más de 100 s, Cloudflare va a cortar la respuesta aunque la
impresión siga: se anota en `ESTADO.md` (Tarea 6) como trampa, "si reimprimir
un pedido grande da error de tiempo, mirá la impresora antes de volver a
apretar".

---

### Tarea 2: `subidas.py` — la lógica de la subida en partes

Todo lo que importa vive acá, **sin FastAPI**, para poder probarlo con un
script pelado como el resto del repo (no hay httpx para tests de HTTP).

**Archivos:**
- Crear: `backend-printnet/subidas.py`
- Crear: `backend-printnet/test_subidas.py`

**Interfaces:**
- Produce (lo usan las Tareas 3 y 4):
  - Constantes: `PARTE_BYTES`, `MAX_PEDIDO_MB`, `MAX_PEDIDO_BYTES`,
    `TOPE_DISCO_BYTES`, `VIDA_SEG`, `SUBIDAS_DIR`, `MENSAJE_FORMATO`,
    `MENSAJE_CONVERSION_FALLIDA`.
  - `class ErrorSubida(Exception)` con `.status: int` y `.mensaje: str`.
  - `nombre_seguro(nombre: str) -> str`, `contar_paginas_pdf(path: Path) -> int | None`,
    `es_pdf(nombre: str, content_type: str) -> bool`.
  - `abrir(nombre: str, tamano_bytes: int, content_type: str = "") -> dict` →
    `{"id": str, "parte_bytes": int, "partes": int}`.
  - `guardar_parte(id_: str, n: int, datos: bytes) -> None`.
  - `completar(id_: str) -> bool` — `True` si esta llamada la pasó a
    `preparando` (solo entonces hay que agendar `preparar`).
  - `preparar(id_: str) -> None` — nunca propaga excepciones.
  - `estado(id_: str) -> dict` → `{"id", "nombre", "tamano_bytes", "estado",
    "paginas", "convertido", "error"}`; `estado` ∈ `subiendo | preparando |
    listo | error`.
  - `tomar(id_: str, destino: Path, usados: set[str]) -> dict` → el mismo
    formato que `_guardar_archivos` en `routers/orders.py`:
    `{"filename_original", "stored_path", "pdf_path", "content_type",
    "size_bytes", "paginas"}`. Mueve los archivos y borra la subida.
  - `limpiar_viejas(ahora: float | None = None) -> int`.

- [ ] **Paso 1: escribir los tests**

```python
"""Tests de la subida en partes (subidas.py).

Correr:  .venv/bin/python test_subidas.py

LO QUE PROTEGE ESTE ARCHIVO: que un archivo partido en pedazos se rearme
EXACTO. Un byte de menos o un pedazo fuera de lugar es un PDF roto que se
cobra mal o no se imprime, y el cliente ya pagó.

Los pedazos se achican a 1000 bytes para probar con archivos de pocos KB; la
lógica no depende del tamaño.
"""

import json
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ["PRINTNET_DB"] = os.path.join(tempfile.mkdtemp(), "subidas.db")
os.environ["PRINTNET_UPLOADS"] = tempfile.mkdtemp()

import document_convert  # noqa: E402
import subidas  # noqa: E402
from generar_pdf_prueba import generar  # noqa: E402

fallos: list[str] = []


def check(nombre: str, obtenido, esperado):
    if obtenido == esperado:
        print(f"  ok  {nombre}")
    else:
        print(f"  FALLA  {nombre}: esperado {esperado}, obtenido {obtenido}")
        fallos.append(nombre)


def status_de(funcion, *args):
    """El status del ErrorSubida que tira `funcion`, o 'no falló'."""
    try:
        funcion(*args)
    except subidas.ErrorSubida as e:
        return e.status
    return "no falló"


subidas.PARTE_BYTES = 1000
PDF = generar(12)  # unos KB: varios pedazos de 1000


def subir(datos: bytes, nombre="doc.pdf", content_type="application/pdf", orden=None) -> str:
    """Abre una subida y manda los pedazos (en `orden`, si se da). Devuelve el id."""
    s = subidas.abrir(nombre, len(datos), content_type)
    indices = list(range(s["partes"])) if orden is None else orden
    for n in indices:
        subidas.guardar_parte(s["id"], n, datos[n * 1000:(n + 1) * 1000])
    return s["id"]


def lista(datos: bytes = PDF, **kw) -> str:
    """Una subida completa y preparada."""
    id_ = subir(datos, **kw)
    subidas.completar(id_)
    subidas.preparar(id_)
    return id_


# ─────────────────────────────────────────────
print("\n== El camino normal ==")

s = subidas.abrir("tesis.pdf", len(PDF), "application/pdf")
check("dice cuántos pedazos mandar", s["partes"], -(-len(PDF) // 1000))
check("y de qué tamaño", s["parte_bytes"], 1000)
for n in range(s["partes"]):
    subidas.guardar_parte(s["id"], n, PDF[n * 1000:(n + 1) * 1000])
check("mientras sube, está 'subiendo'", subidas.estado(s["id"])["estado"], "subiendo")
check("completar la toma", subidas.completar(s["id"]), True)
check("y queda 'preparando'", subidas.estado(s["id"])["estado"], "preparando")
subidas.preparar(s["id"])
e = subidas.estado(s["id"])
check("después queda 'listo'", e["estado"], "listo")
check("con las páginas reales", e["paginas"], 12)
check("un PDF no se convierte", e["convertido"], False)

destino = Path(tempfile.mkdtemp())
a = subidas.tomar(s["id"], destino, set())
check("el archivo rearmado es idéntico al original", Path(a["stored_path"]).read_bytes(), PDF)
check("queda en la carpeta del pedido", Path(a["stored_path"]).parent, destino)
check("con su nombre", Path(a["stored_path"]).name, "tesis.pdf")
check("el PDF a imprimir es el mismo archivo", a["pdf_path"], a["stored_path"])
check("guarda el nombre original", a["filename_original"], "tesis.pdf")
check("y el tamaño", a["size_bytes"], len(PDF))
check("y las páginas", a["paginas"], 12)
check("la subida ya no existe: se usa una sola vez", status_de(subidas.estado, s["id"]), 404)


print("\n== Los pedazos pueden llegar en cualquier orden ==")

partes = -(-len(PDF) // 1000)
id_ = subir(PDF, orden=list(reversed(range(partes))))
subidas.completar(id_)
subidas.preparar(id_)
a = subidas.tomar(id_, Path(tempfile.mkdtemp()), set())
check("al revés también se rearma exacto", Path(a["stored_path"]).read_bytes(), PDF)


print("\n== Reintentar un pedazo lo pisa, no lo duplica ==")

s = subidas.abrir("r.pdf", len(PDF), "application/pdf")
subidas.guardar_parte(s["id"], 0, b"x" * 1000)  # llegó mal
for n in range(s["partes"]):
    subidas.guardar_parte(s["id"], n, PDF[n * 1000:(n + 1) * 1000])
subidas.completar(s["id"])
subidas.preparar(s["id"])
a = subidas.tomar(s["id"], Path(tempfile.mkdtemp()), set())
check("queda lo del último intento", Path(a["stored_path"]).read_bytes(), PDF)


print("\n== Lo que se rechaza al abrir ==")

check("más de 300 MB → 413",
      status_de(subidas.abrir, "g.pdf", subidas.MAX_PEDIDO_BYTES + 1, "application/pdf"), 413)
check("vacío → 422", status_de(subidas.abrir, "v.pdf", 0, "application/pdf"), 422)
check("un formato que no aceptamos → 422",
      status_de(subidas.abrir, "virus.exe", 100, "application/octet-stream"), 422)
check("un Word se acepta (se convierte)",
      status_de(subidas.abrir, "informe.docx", 100, ""), "no falló")


print("\n== Lo que se rechaza al mandar pedazos ==")

s = subidas.abrir("p.pdf", 2500, "application/pdf")  # 3 pedazos: 0, 1, 2
check("pedazo más grande que lo acordado → 413",
      status_de(subidas.guardar_parte, s["id"], 0, b"x" * 1001), 413)
check("pedazo que no existe → 422",
      status_de(subidas.guardar_parte, s["id"], 3, b"x"), 422)
check("número negativo → 422",
      status_de(subidas.guardar_parte, s["id"], -1, b"x"), 422)
check("un id inventado → 404",
      status_de(subidas.guardar_parte, "0" * 32, 0, b"x"), 404)
check("un id con ../ no sale de la carpeta → 404",
      status_de(subidas.guardar_parte, "../../etc", 0, b"x"), 404)


print("\n== Completar ==")

s = subidas.abrir("f.pdf", 2500, "application/pdf")
subidas.guardar_parte(s["id"], 0, b"x" * 1000)
subidas.guardar_parte(s["id"], 2, b"x" * 500)
check("si falta un pedazo → 422", status_de(subidas.completar, s["id"]), 422)
subidas.guardar_parte(s["id"], 1, b"x" * 1000)
check("con todos, completa", subidas.completar(s["id"]), True)
check("completar otra vez no la vuelve a tomar", subidas.completar(s["id"]), False)
check("ya no acepta pedazos → 409",
      status_de(subidas.guardar_parte, s["id"], 0, b"x"), 409)
check("todavía no se puede usar en un pedido → 409",
      status_de(subidas.tomar, s["id"], Path(tempfile.mkdtemp()), set()), 409)


print("\n== Llegó menos de lo anunciado ==")

s = subidas.abrir("corto.pdf", len(PDF), "application/pdf")
for n in range(s["partes"]):
    pedazo = PDF[n * 1000:(n + 1) * 1000]
    if n == s["partes"] - 1:
        pedazo = pedazo[:-10]  # al último le faltan 10 bytes
    subidas.guardar_parte(s["id"], n, pedazo)
subidas.completar(s["id"])
subidas.preparar(s["id"])
e = subidas.estado(s["id"])
check("queda en error", e["estado"], "error")
check("explicando que llegó incompleto", "incompleto" in (e["error"] or ""), True)


print("\n== Documentos que hay que convertir ==")

original_convertir = document_convert.convertir_a_pdf


def convertir_bien(origen, carpeta):
    pdf = Path(carpeta) / (Path(origen).stem + ".pdf")
    pdf.write_bytes(generar(2))
    return document_convert.ConversionResult(ok=True, pdf_path=str(pdf), detalle="convertido")


document_convert.convertir_a_pdf = convertir_bien
id_ = lista(b"PK" + b"z" * 3000, nombre="informe.docx", content_type="")
e = subidas.estado(id_)
check("un Word queda listo", e["estado"], "listo")
check("marcado como convertido", e["convertido"], True)
check("con las páginas del PDF convertido", e["paginas"], 2)
destino = Path(tempfile.mkdtemp())
a = subidas.tomar(id_, destino, set())
check("el original queda con su nombre", Path(a["stored_path"]).name, "informe.docx")
check("y el PDF al lado, con el mismo nombre", Path(a["pdf_path"]).name, "informe.pdf")
check("los dos en la carpeta del pedido", Path(a["pdf_path"]).parent, destino)


def convertir_roto(origen, carpeta):
    return document_convert.ConversionResult(
        ok=False, pdf_path=None, detalle="El documento está dañado.", del_documento=True)


document_convert.convertir_a_pdf = convertir_roto
e = subidas.estado(lista(b"PK" + b"z" * 3000, nombre="roto.docx", content_type=""))
check("un documento dañado queda en error", e["estado"], "error")
check("con el mensaje para el cliente", e["error"], "El documento está dañado.")


def convertir_caido(origen, carpeta):
    return document_convert.ConversionResult(
        ok=False, pdf_path=None, detalle="soffice: timeout en C:\\interno", del_documento=False)


document_convert.convertir_a_pdf = convertir_caido
e = subidas.estado(lista(b"PK" + b"z" * 3000, nombre="otro.docx", content_type=""))
check("si el problema es nuestro, mensaje genérico", e["error"], subidas.MENSAJE_CONVERSION_FALLIDA)
check("sin rutas internas a la vista", "C:\\" in e["error"], False)

document_convert.convertir_a_pdf = original_convertir


print("\n== Dos documentos con el mismo nombre en un pedido ==")

destino = Path(tempfile.mkdtemp())
usados: set[str] = set()
a1 = subidas.tomar(lista(), destino, usados)
a2 = subidas.tomar(lista(), destino, usados)
check("no se pisan", a1["stored_path"] != a2["stored_path"], True)
check("los dos existen", Path(a1["stored_path"]).is_file() and Path(a2["stored_path"]).is_file(), True)


print("\n== Un nombre que choca con los archivos internos ==")

a = subidas.tomar(lista(nombre="meta.json.pdf"), Path(tempfile.mkdtemp()), set())
check("se guarda igual, sin romper la subida", Path(a["stored_path"]).read_bytes(), PDF)


print("\n== Limpieza ==")

vieja = subir(PDF)
nueva = subir(PDF)
meta = subidas.SUBIDAS_DIR / vieja / "meta.json"
datos = json.loads(meta.read_text("utf-8"))
datos["creado"] = time.time() - subidas.VIDA_SEG - 60
meta.write_text(json.dumps(datos), "utf-8")
borradas = subidas.limpiar_viejas()
check("borra la de hace más de 24 h", borradas, 1)
check("ya no existe", (subidas.SUBIDAS_DIR / vieja).exists(), False)
check("la reciente sigue", subidas.estado(nueva)["estado"], "subiendo")


print("\n== Tope de disco ==")

tope_original = subidas.TOPE_DISCO_BYTES
subidas.TOPE_DISCO_BYTES = 1
check("si las subidas en curso llenan el tope → 503",
      status_de(subidas.abrir, "x.pdf", 100, "application/pdf"), 503)
subidas.TOPE_DISCO_BYTES = tope_original


print()
if fallos:
    print(f"✗ {len(fallos)} fallo(s): {', '.join(fallos)}")
    sys.exit(1)
print("✓ todo bien")
```

- [ ] **Paso 2: correr y ver que falla**

Run: `cd backend-printnet && .venv/bin/python test_subidas.py`
Expected: `ModuleNotFoundError: No module named 'subidas'`.

- [ ] **Paso 3: implementar `subidas.py`**

```python
"""Subida en partes: archivos de hasta 300 MB a pesar del límite de Cloudflare.

POR QUÉ EXISTE: Cloudflare, en el plan gratuito, corta las peticiones de más
de 100 MB. El límite es por PETICIÓN, no por archivo, así que el archivo
viaja partido en pedazos de 6 MB, cada uno en la suya, y se rearma acá.

De paso resuelve que el archivo se subía dos veces (una para contar páginas,
otra al pagar): ahora se sube una vez, se prepara, y el pedido lo referencia
por id. Ver docs/plan-subida-en-partes.md.

El estado vive en disco, sin tabla en la base: uploads/_subidas/{id}/meta.json.
Es temporal y se borra solo a las 24 h.

Sin FastAPI a propósito: routers/subidas.py solo traduce HTTP a estas
funciones, y esto se prueba con un script pelado (test_subidas.py).
"""

import json
import logging
import math
import os
import re
import shutil
import time
import uuid
from pathlib import Path

import document_convert
from database import UPLOADS_DIR

logger = logging.getLogger("printnet.subidas")

# Lo dicta el servidor (va en la respuesta de abrir): la web no lo tiene
# escrito, así no hay otro número duplicado entre los dos lados.
PARTE_BYTES = 6 * 1024 * 1024

# ESPEJADO EN frontend/src/limites.js (MAX_ARCHIVO_MB). Si se cambia acá hay
# que cambiarlo allá, o la web deja subir algo que después se rechaza. Es
# sobre el TOTAL del pedido: routers/orders.py suma las subidas al crearlo.
MAX_PEDIDO_MB = 300
MAX_PEDIDO_BYTES = MAX_PEDIDO_MB * 1024 * 1024

# Para que nadie pueda llenar el disco de la notebook abriendo subidas y
# abandonándolas: entre todas las que están en curso, no más de esto.
TOPE_DISCO_BYTES = 3 * 1024 * 1024 * 1024

# Una subida que no termina en pedido se borra pasado este tiempo.
VIDA_SEG = 24 * 3600

SUBIDAS_DIR = UPLOADS_DIR / "_subidas"

MENSAJE_FORMATO = (
    "No aceptamos ese formato. Podés subir un PDF, o un documento de Word, "
    "Excel, PowerPoint u OpenOffice — esos los convertimos a PDF nosotros."
)

# Cuando la conversión falla por un problema NUESTRO (LibreOffice caído, un
# timeout), el cliente no puede hacer nada con el detalle técnico — y ese
# detalle incluye rutas internas del servidor. Va al registro, no a la pantalla.
MENSAJE_CONVERSION_FALLIDA = (
    "No pudimos procesar tu documento. Probá subiéndolo en PDF, o escribinos "
    "y lo resolvemos."
)

# El id va en la URL y se usa como nombre de carpeta: sin esta validación,
# un id como "../../algo" escribiría fuera de uploads/.
_ID_VALIDO = re.compile(r"^[0-9a-f]{32}$")


class ErrorSubida(Exception):
    """Un rechazo con el código HTTP que le corresponde y un mensaje para el cliente."""

    def __init__(self, status: int, mensaje: str):
        super().__init__(mensaje)
        self.status = status
        self.mensaje = mensaje


def nombre_seguro(nombre: str) -> str:
    base = Path(nombre).name
    return re.sub(r"[^\w.\- ]", "_", base) or "archivo"


def contar_paginas_pdf(path: Path) -> int | None:
    try:
        from pypdf import PdfReader

        return len(PdfReader(str(path)).pages)
    except Exception:
        return None


def es_pdf(nombre: str, content_type: str) -> bool:
    return content_type == "application/pdf" or nombre.lower().endswith(".pdf")


def _cantidad_partes(tamano_bytes: int) -> int:
    return math.ceil(tamano_bytes / PARTE_BYTES)


def _parte(carpeta: Path, n: int) -> Path:
    return carpeta / "partes" / f"{n:05d}"


def _carpeta(id_: str) -> Path:
    if not _ID_VALIDO.match(id_ or ""):
        raise ErrorSubida(404, "subida inexistente")
    carpeta = SUBIDAS_DIR / id_
    if not (carpeta / "meta.json").is_file():
        raise ErrorSubida(404, "subida inexistente")
    return carpeta


def _leer(carpeta: Path) -> dict:
    return json.loads((carpeta / "meta.json").read_text("utf-8"))


def _escribir(carpeta: Path, meta: dict) -> None:
    # Escribir aparte y reemplazar: si el proceso muere a la mitad, el
    # meta.json viejo queda entero en vez de uno cortado que no se puede leer.
    tmp = carpeta / "meta.json.tmp"
    tmp.write_text(json.dumps(meta, ensure_ascii=False), "utf-8")
    os.replace(tmp, carpeta / "meta.json")


def _ocupado() -> int:
    if not SUBIDAS_DIR.exists():
        return 0
    return sum(p.stat().st_size for p in SUBIDAS_DIR.rglob("*") if p.is_file())


def abrir(nombre: str, tamano_bytes: int, content_type: str = "") -> dict:
    """Empieza una subida. Devuelve el id y cómo partir el archivo."""
    nombre = nombre or "archivo"
    if not (es_pdf(nombre, content_type) or document_convert.necesita_conversion(nombre)):
        raise ErrorSubida(422, MENSAJE_FORMATO)
    if tamano_bytes <= 0:
        raise ErrorSubida(422, f"'{nombre}' está vacío")
    if tamano_bytes > MAX_PEDIDO_BYTES:
        raise ErrorSubida(413, f"'{nombre}' supera el máximo de {MAX_PEDIDO_MB} MB")
    if _ocupado() + tamano_bytes > TOPE_DISCO_BYTES:
        logger.warning("Subidas en curso ocupan más del tope: se rechaza '%s'", nombre)
        raise ErrorSubida(503, "Estamos recibiendo muchos archivos. Probá de nuevo en un rato.")

    id_ = uuid.uuid4().hex
    carpeta = SUBIDAS_DIR / id_
    (carpeta / "partes").mkdir(parents=True)
    _escribir(carpeta, {
        "id": id_,
        "nombre": nombre,
        "tamano_bytes": tamano_bytes,
        "content_type": content_type or "",
        "estado": "subiendo",
        "creado": time.time(),
        "paginas": None,
        "convertido": None,
        "error": None,
    })
    return {"id": id_, "parte_bytes": PARTE_BYTES, "partes": _cantidad_partes(tamano_bytes)}


def guardar_parte(id_: str, n: int, datos: bytes) -> None:
    """Guarda el pedazo `n`. Mandarlo de nuevo lo pisa: así un reintento es seguro."""
    carpeta = _carpeta(id_)
    meta = _leer(carpeta)
    if meta["estado"] != "subiendo":
        raise ErrorSubida(409, "esta subida ya se completó")
    total = _cantidad_partes(meta["tamano_bytes"])
    if not 0 <= n < total:
        raise ErrorSubida(422, f"la parte {n} no existe: son {total}, de 0 a {total - 1}")
    if len(datos) > PARTE_BYTES:
        raise ErrorSubida(413, "la parte es más grande de lo permitido")

    destino = _parte(carpeta, n)
    tmp = destino.with_name(destino.name + ".tmp")
    tmp.write_bytes(datos)
    os.replace(tmp, destino)


def completar(id_: str) -> bool:
    """Cierra la subida. True si ESTA llamada la pasó a 'preparando'.

    Solo en ese caso hay que agendar `preparar`: si la web reintenta el
    "terminé", no se tienen que lanzar dos preparaciones sobre la misma carpeta.
    """
    carpeta = _carpeta(id_)
    meta = _leer(carpeta)
    if meta["estado"] != "subiendo":
        return False
    faltan = [n for n in range(_cantidad_partes(meta["tamano_bytes"]))
              if not _parte(carpeta, n).is_file()]
    if faltan:
        raise ErrorSubida(
            422, f"faltan {len(faltan)} parte(s) del archivo (la primera es la {faltan[0]})")
    meta["estado"] = "preparando"
    _escribir(carpeta, meta)
    return True


def preparar(id_: str) -> None:
    """Junta los pedazos, convierte si hace falta y cuenta páginas.

    Corre en segundo plano: nunca propaga. El resultado, bueno o malo, queda
    en meta.json y la web lo lee con `estado()`.
    """
    try:
        carpeta = _carpeta(id_)
        meta = _leer(carpeta)
    except ErrorSubida:
        return
    if meta["estado"] != "preparando":
        return
    try:
        meta.update(_preparar(carpeta, meta))
        meta["estado"] = "listo"
    except ErrorSubida as e:
        meta["estado"], meta["error"] = "error", e.mensaje
    except Exception:
        logger.exception("Subida %s: falló la preparación", id_)
        meta["estado"], meta["error"] = "error", MENSAJE_CONVERSION_FALLIDA
    _escribir(carpeta, meta)


def _preparar(carpeta: Path, meta: dict) -> dict:
    # "original" + extensión, y no el nombre del cliente: un archivo llamado
    # "meta.json" o "partes" pisaría lo nuestro. El nombre real se le pone
    # recién al moverlo a la carpeta del pedido, en tomar().
    original = carpeta / ("original" + Path(nombre_seguro(meta["nombre"])).suffix.lower())

    # De a un pedazo: nunca se tiene el archivo entero en memoria.
    with open(original, "wb") as salida:
        for n in range(_cantidad_partes(meta["tamano_bytes"])):
            with open(_parte(carpeta, n), "rb") as pedazo:
                shutil.copyfileobj(pedazo, salida)
    shutil.rmtree(carpeta / "partes")

    recibido = original.stat().st_size
    if recibido != meta["tamano_bytes"]:
        raise ErrorSubida(
            422,
            f"El archivo llegó incompleto ({recibido} de {meta['tamano_bytes']} bytes). "
            f"Subilo de nuevo.",
        )

    resultado = document_convert.convertir_a_pdf(str(original), str(carpeta))
    if not resultado.ok:
        if resultado.del_documento:
            raise ErrorSubida(422, resultado.detalle)
        logger.error("Conversión fallida (problema del sistema): %s", resultado.detalle)
        raise ErrorSubida(422, MENSAJE_CONVERSION_FALLIDA)

    paginas = contar_paginas_pdf(Path(resultado.pdf_path))
    if paginas is None:
        raise ErrorSubida(422, "no se pudo leer el documento para contar sus páginas")

    return {
        "original": str(original),
        "pdf": resultado.pdf_path,
        "paginas": paginas,
        "convertido": not es_pdf(meta["nombre"], meta["content_type"]),
    }


def estado(id_: str) -> dict:
    """Lo que la web necesita saber de una subida."""
    meta = _leer(_carpeta(id_))
    return {k: meta.get(k) for k in
            ("id", "nombre", "tamano_bytes", "estado", "paginas", "convertido", "error")}


def _unico(nombre: str, usados: set[str]) -> str:
    candidato, i = nombre, 1
    while candidato in usados:
        candidato = f"{Path(nombre).stem}_{i}{Path(nombre).suffix}"
        i += 1
    usados.add(candidato)
    return candidato


def tomar(id_: str, destino: Path, usados: set[str]) -> dict:
    """Mueve una subida lista a la carpeta del pedido y la borra.

    Devuelve lo mismo que `_guardar_archivos` en routers/orders.py, así el
    resto de la creación del pedido no se entera de por dónde llegó el
    archivo. `usados` son los nombres ya ocupados en `destino`, para que dos
    documentos con el mismo nombre no se pisen.
    """
    carpeta = _carpeta(id_)
    meta = _leer(carpeta)
    if meta["estado"] != "listo":
        raise ErrorSubida(409, f"'{meta['nombre']}' todavía no terminó de prepararse")

    destino.mkdir(parents=True, exist_ok=True)
    nombre = _unico(nombre_seguro(meta["nombre"]), usados)
    original = destino / nombre
    shutil.move(meta["original"], original)

    if meta["pdf"] == meta["original"]:
        pdf = original
    else:
        pdf = destino / _unico(Path(nombre).stem + ".pdf", usados)
        shutil.move(meta["pdf"], pdf)

    shutil.rmtree(carpeta)
    return {
        "filename_original": meta["nombre"],
        "stored_path": str(original),
        "pdf_path": str(pdf),
        "content_type": meta["content_type"] or None,
        "size_bytes": meta["tamano_bytes"],
        "paginas": meta["paginas"],
    }


def limpiar_viejas(ahora: float | None = None) -> int:
    """Borra las subidas de hace más de VIDA_SEG. Devuelve cuántas borró."""
    ahora = time.time() if ahora is None else ahora
    if not SUBIDAS_DIR.exists():
        return 0
    borradas = 0
    for carpeta in SUBIDAS_DIR.iterdir():
        if not carpeta.is_dir():
            continue
        try:
            creado = _leer(carpeta)["creado"]
        except Exception:
            # meta.json roto o a medio escribir: se usa la fecha de la carpeta
            creado = carpeta.stat().st_mtime
        if ahora - creado > VIDA_SEG:
            shutil.rmtree(carpeta, ignore_errors=True)
            borradas += 1
    return borradas
```

- [ ] **Paso 4: correr y ver que pasa**

Run: `cd backend-printnet && .venv/bin/python test_subidas.py`
Expected: todas `ok`, `✓ todo bien`, código de salida 0.

- [ ] **Paso 5: commit**

```bash
git add backend-printnet/subidas.py backend-printnet/test_subidas.py
git commit -m "feat: lógica de la subida en partes (subidas.py)

Rearma en disco un archivo que llega en pedazos, lo prepara (convierte y
cuenta páginas) y lo entrega a la carpeta del pedido. Sin FastAPI, para
probarlo con un script pelado.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Tarea 3: Los endpoints y la limpieza

**Archivos:**
- Crear: `backend-printnet/routers/subidas.py`
- Modificar: `backend-printnet/main.py`

**Interfaces:**
- Consume: todo `subidas.py` de la Tarea 2.
- Produce (lo usa la web en la Tarea 5):
  - `POST /uploads` con JSON `{nombre, tamano_bytes, content_type}` → 201
    `{id, parte_bytes, partes}`.
  - `PUT /uploads/{id}/partes/{n}` con el pedazo crudo en el cuerpo → 200 `{ok: true}`.
  - `POST /uploads/{id}/completar` → 202 con el mismo cuerpo que `GET`.
  - `GET /uploads/{id}` → 200 `{id, nombre, tamano_bytes, estado, paginas, convertido, error}`.
  - Errores: `{detail: "mensaje para el cliente"}` con el status de `ErrorSubida`.

- [ ] **Paso 1: escribir el router**

```python
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
```

- [ ] **Paso 2: registrar el router y la limpieza en `main.py`**

Agregar `import asyncio` junto a los otros imports de la biblioteca estándar.

Cambiar:

```python
from database import init_db
from routers import admin, orders, webhooks
```

por:

```python
import subidas
from database import init_db
from routers import admin, orders, webhooks
from routers import subidas as subidas_router
```

Reemplazar la función `lifespan` por:

```python
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
    limpieza = asyncio.create_task(_limpiar_subidas_cada_hora())
    yield
    limpieza.cancel()
```

Y agregar después de `app.include_router(webhooks.router)`:

```python
app.include_router(subidas_router.router)
```

- [ ] **Paso 3: probar los endpoints contra el backend local**

Levantar: `cd backend-printnet && .venv/bin/uvicorn main:app --port 8077`
(en otra terminal) y correr:

```bash
cd backend-printnet && .venv/bin/python generar_pdf_prueba.py --paginas 5 --salida /tmp/p5.pdf
TAM=$(stat -f%z /tmp/p5.pdf)
ID=$(curl -s -X POST localhost:8077/uploads -H 'Content-Type: application/json' -d "{\"nombre\":\"p5.pdf\",\"tamano_bytes\":$TAM,\"content_type\":\"application/pdf\"}" | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])")
curl -s -X PUT localhost:8077/uploads/$ID/partes/0 -H 'Content-Type: application/octet-stream' --data-binary @/tmp/p5.pdf
curl -s -X POST localhost:8077/uploads/$ID/completar
sleep 1; curl -s localhost:8077/uploads/$ID
```

Expected: el `PUT` devuelve `{"ok":true}`, el `completar` devuelve
`"estado":"preparando"` (o ya `listo`), y el último `GET` devuelve
`"estado":"listo","paginas":5`. Un `curl -s -o /dev/null -w '%{http_code}' localhost:8077/uploads/noexiste`
da `404`. Parar el backend.

- [ ] **Paso 4: correr todos los tests e importar**

Run: `cd backend-printnet && for t in test_*.py; do .venv/bin/python $t > /dev/null || echo "FALLA $t"; done; .venv/bin/python -c "import main; print('ok')"`
Expected: ninguna `FALLA`, y `ok`.

- [ ] **Paso 5: commit**

```bash
git add backend-printnet/routers/subidas.py backend-printnet/main.py
git commit -m "feat: endpoints /uploads y limpieza horaria de subidas abandonadas

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Tarea 4: `POST /orders` acepta subidas

**Archivos:**
- Modificar: `backend-printnet/routers/orders.py`
- Crear: `backend-printnet/test_crear_pedido_subidas.py`

**Interfaces:**
- Consume: `subidas.estado`, `subidas.tomar`, `subidas.MAX_PEDIDO_BYTES`,
  `subidas.MAX_PEDIDO_MB`, `subidas.ErrorSubida`, `subidas.MENSAJE_FORMATO`,
  `subidas.MENSAJE_CONVERSION_FALLIDA`, `subidas.nombre_seguro`,
  `subidas.contar_paginas_pdf`.
- Produce: `POST /orders` con el campo de formulario `uploads` (JSON con una
  lista de ids, uno por documento, emparejados por posición). `files` pasa a
  ser opcional. Mandar los dos es 422.

- [ ] **Paso 1: escribir los tests**

```python
"""Tests de crear_pedido con archivos que llegaron por la subida en partes.

Correr:  .venv/bin/python test_crear_pedido_subidas.py

Se llama a la función del endpoint directo, sin HTTP (no hay httpx a
propósito). Sin MP_ACCESS_TOKEN el backend está en modo fantasma: el pedido
nace pagado, que es lo que se necesita para probar sin MercadoPago.

LO QUE PROTEGE: que un pedido rechazado (por ejemplo, un rango de páginas que
no existe) NO consuma la subida. Con un archivo de 300 MB, perderla obliga al
cliente a esperar la subida entera de nuevo.
"""

import json
import os
import sys
import tempfile
from pathlib import Path

os.environ["PRINTNET_DB"] = os.path.join(tempfile.mkdtemp(), "pedidos.db")
os.environ["PRINTNET_UPLOADS"] = tempfile.mkdtemp()
os.environ.pop("MP_ACCESS_TOKEN", None)

import database  # noqa: E402
import subidas  # noqa: E402
from fastapi import BackgroundTasks, HTTPException  # noqa: E402
from generar_pdf_prueba import generar  # noqa: E402
from routers.orders import crear_pedido  # noqa: E402

database.init_db()
subidas.PARTE_BYTES = 1000

fallos: list[str] = []


def check(nombre: str, obtenido, esperado):
    if obtenido == esperado:
        print(f"  ok  {nombre}")
    else:
        print(f"  FALLA  {nombre}: esperado {esperado}, obtenido {obtenido}")
        fallos.append(nombre)


def subida_lista(paginas: int, nombre: str = "doc.pdf") -> str:
    datos = generar(paginas)
    s = subidas.abrir(nombre, len(datos), "application/pdf")
    for n in range(s["partes"]):
        subidas.guardar_parte(s["id"], n, datos[n * 1000:(n + 1) * 1000])
    subidas.completar(s["id"])
    subidas.preparar(s["id"])
    return s["id"]


def datos(cantidad: int, tipo: str = "fotocopias", rango=None) -> str:
    contacto = {"nombre": "Ana", "telefono": "+5492211234567", "email": "ana@x.com"}
    if tipo == "fotos":
        return json.dumps({"tipo": "fotos", "contacto": contacto, "material": "opalina"})
    doc = {
        "opciones": {"color": "byn", "caras": "simple", "copias": 1, "tamano": "A4"},
        "rango": rango or {"modo": "todas", "valor": ""},
        "terminaciones": [],
    }
    return json.dumps({"tipo": tipo, "contacto": contacto, "documentos": [doc] * cantidad})


def pedir(datos_json: str, uploads=None, files=None):
    """Llama al endpoint. Devuelve la respuesta, o el HTTPException si rechazó."""
    conn = database.get_conn()
    try:
        r = crear_pedido(background=BackgroundTasks(), datos=datos_json,
                         files=files, uploads=uploads, db=conn)
        conn.commit()
        return r
    except HTTPException as e:
        conn.rollback()
        return e
    finally:
        conn.close()


def status(r):
    return r.status_code if isinstance(r, HTTPException) else 201


# ─────────────────────────────────────────────
print("\n== Un pedido con dos documentos subidos en partes ==")

a, b = subida_lista(3, "a.pdf"), subida_lista(5, "b.pdf")
r = pedir(datos(2), uploads=json.dumps([a, b]))
check("se crea", status(r), 201)
check("cuenta las páginas del primero", r["paginas"], 3)
check("con los dos archivos", r["archivos"], ["a.pdf", "b.pdf"])
check("y tiene precio", r["precio_total"] > 0, True)
check("las subidas se consumieron", subidas.SUBIDAS_DIR.joinpath(a).exists(), False)

conn = database.get_conn()
filas = conn.execute(
    "SELECT f.stored_path, f.paginas FROM files f JOIN orders o ON o.id = f.order_id"
    " WHERE o.token = ? ORDER BY f.id", (r["token"],)
).fetchall()
conn.close()
check("quedan dos filas en files", len(filas), 2)
check("en la carpeta del pedido", all(Path(f["stored_path"]).parent.name == r["token"] for f in filas), True)
check("y los archivos existen", all(Path(f["stored_path"]).is_file() for f in filas), True)
check("con sus páginas", [f["paginas"] for f in filas], [3, 5])


print("\n== Un pedido rechazado NO consume la subida ==")

c = subida_lista(3)
r = pedir(datos(1, rango={"modo": "rango", "valor": "50-60"}), uploads=json.dumps([c]))
check("un rango que no existe se rechaza", status(r), 422)
check("y la subida sigue lista para reintentar", subidas.estado(c)["estado"], "listo")
r = pedir(datos(1), uploads=json.dumps([c]))
check("corrigiendo el rango, la misma subida sirve", status(r), 201)


print("\n== Lo que se rechaza ==")

d = subida_lista(2)
check("cantidad de subidas distinta de documentos → 422",
      status(pedir(datos(2), uploads=json.dumps([d]))), 422)
check("la misma subida dos veces → 422",
      status(pedir(datos(2), uploads=json.dumps([d, d]))), 422)
check("uploads que no es JSON → 422", status(pedir(datos(1), uploads="no-json")), 422)
check("uploads que no es una lista → 422", status(pedir(datos(1), uploads='{"a": 1}')), 422)
check("files y uploads juntos → 422",
      status(pedir(datos(1), uploads=json.dumps([d]), files=["algo"])), 422)
check("una subida inexistente → 404",
      status(pedir(datos(1), uploads=json.dumps(["0" * 32]))), 404)
check("fotos por subida en partes → 422",
      status(pedir(datos(1, tipo="fotos"), uploads=json.dumps([d]))), 422)

e = subidas.abrir("sin-terminar.pdf", 500, "application/pdf")["id"]
check("una subida que no terminó de prepararse → 409",
      status(pedir(datos(1), uploads=json.dumps([e]))), 409)

tope = subidas.MAX_PEDIDO_BYTES
f1, f2 = subida_lista(2), subida_lista(2)
subidas.MAX_PEDIDO_BYTES = subidas.estado(f1)["tamano_bytes"] + 1  # entra uno, no los dos
r = pedir(datos(2), uploads=json.dumps([f1, f2]))
check("si la suma pasa el máximo → 413", status(r), 413)
check("y las subidas no se tocaron", subidas.estado(f1)["estado"], "listo")
subidas.MAX_PEDIDO_BYTES = tope

check("sin archivos ni subidas, un pedido de fotocopias → 422",
      status(pedir(datos(1))), 422)


print()
if fallos:
    print(f"✗ {len(fallos)} fallo(s): {', '.join(fallos)}")
    sys.exit(1)
print("✓ todo bien")
```

- [ ] **Paso 2: correr y ver que falla**

Run: `cd backend-printnet && .venv/bin/python test_crear_pedido_subidas.py`
Expected: `TypeError: crear_pedido() got an unexpected keyword argument 'uploads'`.

- [ ] **Paso 3: implementar en `routers/orders.py`**

Agregar `import subidas` junto a `import pricing`.

Reemplazar el bloque del límite:

```python
# ESPEJADO EN frontend/src/limites.js (MAX_ARCHIVO_MB). Si se cambia acá hay
# que cambiarlo allá, o la web deja subir algo que después se rechaza.
#
# 95 y no 100 porque Cloudflare, en el plan gratuito, corta las peticiones de
# más de 100 MB. Dejando el límite propio un poco abajo, el cliente recibe
# nuestro mensaje y no un error de Cloudflare que no podemos redactar.
MAX_FILE_MB = 95
```

por:

```python
# Límite del camino VIEJO: archivos mandados enteros en POST /orders y
# POST /orders/paginas. 95 y no 100 porque Cloudflare, en el plan gratuito,
# corta las peticiones de más de 100 MB; dejando el límite propio un poco
# abajo, el cliente recibe nuestro mensaje y no uno de Cloudflare.
#
# La web nueva ya no usa este camino: sube en partes (subidas.py, hasta
# subidas.MAX_PEDIDO_MB). Este queda para la web vieja durante el deploy y
# para /fotos.
MAX_FILE_MB = 95
```

Reemplazar las definiciones de `_MENSAJE_FORMATO`, `_MENSAJE_CONVERSION_FALLIDA`
(con su comentario), `_nombre_seguro` y `_contar_paginas_pdf` por:

```python
# Compartidos con la subida en partes: viven en subidas.py para que los dos
# caminos le digan lo mismo al cliente.
_MENSAJE_FORMATO = subidas.MENSAJE_FORMATO
_MENSAJE_CONVERSION_FALLIDA = subidas.MENSAJE_CONVERSION_FALLIDA
_nombre_seguro = subidas.nombre_seguro
_contar_paginas_pdf = subidas.contar_paginas_pdf
```

(`_fallo_conversion` sigue usando `_MENSAJE_CONVERSION_FALLIDA` por el alias.
Si se mueve el bloque de alias, tiene que quedar **antes** de
`_fallo_conversion`.)

Agregar estas tres funciones antes de `@router.post("/orders/paginas")`:

```python
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


def _archivos_de_subidas(ids: list[str]) -> list[dict]:
    """Lo que hace falta para cotizar, SIN mover nada todavía.

    Si el pedido se rechaza después (un rango de páginas que no existe), el
    cliente no pierde lo que subió: con 300 MB, perderlo es volver a esperar
    la subida entera. Los archivos se mueven recién en `_tomar_subidas`.
    """
    archivos = []
    for id_ in ids:
        try:
            e = subidas.estado(id_)
        except subidas.ErrorSubida as err:
            raise HTTPException(err.status, err.mensaje)
        if e["estado"] != "listo":
            raise HTTPException(409, f"'{e['nombre']}' todavía no terminó de prepararse")
        archivos.append({
            "filename_original": e["nombre"],
            "paginas": e["paginas"],
            "size_bytes": e["tamano_bytes"],
        })
    if sum(a["size_bytes"] for a in archivos) > subidas.MAX_PEDIDO_BYTES:
        raise HTTPException(
            413, f"el pedido supera el máximo de {subidas.MAX_PEDIDO_MB} MB en total")
    return archivos


def _tomar_subidas(token: str, ids: list[str]) -> list[dict]:
    destino = UPLOADS_DIR / token
    usados: set[str] = set()
    try:
        return [subidas.tomar(id_, destino, usados) for id_ in ids]
    except subidas.ErrorSubida as e:
        raise HTTPException(e.status, e.mensaje)
```

En la firma de `crear_pedido`, reemplazar:

```python
    files: list[UploadFile] = File(...),
```

por:

```python
    files: list[UploadFile] | None = File(None),
    uploads: str | None = Form(
        None, description="JSON: ids de subidas en partes, uno por documento"),
```

Reemplazar los pasos 2 y 3 (desde `# 2) Validar archivos según el tipo de
pedido` hasta `archivos = _guardar_archivos(token, files)` inclusive) por:

```python
    if files and uploads:
        raise HTTPException(422, "mandá 'files' o 'uploads', no los dos")

    token = str(uuid.uuid4())
    ids_subidas = None

    if uploads:
        # 2+3) Camino nuevo: los archivos ya están en el servidor, preparados.
        if not isinstance(pedido, PedidoFotocopias):
            raise HTTPException(422, "la subida en partes es solo para fotocopias")
        ids_subidas = _leer_ids_subidas(uploads, len(pedido.documentos))
        archivos = _archivos_de_subidas(ids_subidas)
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
```

Y justo antes de `# 5) Persistir cliente + pedido + archivos.`, agregar:

```python
    # Recién ahora, con el pedido ya validado y cotizado, se mueven las
    # subidas a la carpeta del pedido (ver _archivos_de_subidas).
    if ids_subidas:
        archivos = _tomar_subidas(token, ids_subidas)
```

- [ ] **Paso 4: correr y ver que pasa**

Run: `cd backend-printnet && .venv/bin/python test_crear_pedido_subidas.py`
Expected: todas `ok`, `✓ todo bien`.

- [ ] **Paso 5: correr todos los tests, importar, y la prueba de punta a punta del camino viejo**

Run: `cd backend-printnet && for t in test_*.py; do .venv/bin/python $t > /dev/null || echo "FALLA $t"; done; .venv/bin/python -c "import main; print('ok')"`
Expected: ninguna `FALLA`, y `ok`.

Run: `cd backend-printnet && (.venv/bin/uvicorn main:app --port 8077 &) && sleep 3 && .venv/bin/python prueba_pedido.py --url http://localhost:8077 --archivo a.pdf --archivo b.pdf; pkill -f "uvicorn main:app --port 8077"`
Expected: el pedido con `files` (el camino de la web vieja) se crea igual
que antes. Esto es lo que garantiza que el backend se puede desplegar antes
que la web.

- [ ] **Paso 6: commit**

```bash
git add backend-printnet/routers/orders.py backend-printnet/test_crear_pedido_subidas.py
git commit -m "feat: POST /orders acepta archivos subidos en partes (hasta 300 MB)

El pedido referencia las subidas por id. Se mueven a la carpeta del pedido
recién después de validarlo, para que un rechazo no le haga perder al
cliente lo que subió. El camino viejo con 'files' sigue andando.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Tarea 5: La web

No hay tests automáticos de la web en el repo; la verificación es compilar y
probar en el navegador contra el backend local.

**Archivos:**
- Modificar: `frontend/src/api.js`
- Modificar: `frontend/src/limites.js`
- Modificar: `frontend/src/components/fotocopias/FileUpload.jsx`
- Modificar: `frontend/src/pages/Fotocopias.jsx`

**Interfaces:**
- Consume: los endpoints de la Tarea 3 y `uploads` de la Tarea 4.
- Produce:
  - `subirArchivo(file, { alProgresar, signal }) -> Promise<{ id, paginas, convertido }>`.
    `alProgresar` recibe `{ fase: 'subiendo', enviado, total }` o `{ fase: 'preparando' }`.
    Un error trae `.status` si el servidor contestó (como los de `parse`).
  - `crearPedidoConSubidas(datos, uploads: string[]) -> Promise<pedido>`.
  - Documento en el estado de `Fotocopias`: suma `uploadId`, `progreso` y
    `cancelar` (un `AbortController`); `estado` ∈ `subiendo | contando | listo | error`.

- [ ] **Paso 1: `api.js`**

Reemplazar la función `contarPaginas` entera (ya no la usa nadie: el conteo
viene en la subida) por:

```js
/** Crea un pedido de fotocopias con archivos ya subidos en partes. */
export async function crearPedidoConSubidas(datos, uploads) {
  const fd = new FormData();
  fd.append('datos', JSON.stringify(datos));
  fd.append('uploads', JSON.stringify(uploads));
  return parse(await fetch(`${PRINTNET_API}/orders`, { method: 'POST', body: fd }));
}

// ─── Subida en partes ────────────────────────────────────────────────
// Cloudflare corta las peticiones de más de 100 MB, así que el archivo viaja
// en pedazos (de 6 MB, lo decide el servidor) y se rearma en la notebook.
// Ver docs/plan-subida-en-partes.md.

// Espera entre reintentos de un pedazo. Con una conexión mala, reintentar
// 6 MB no cuesta nada; reintentar el archivo entero sería volver a empezar.
const ESPERAS_REINTENTO_MS = [1000, 2000, 4000, 8000, 15000];
const CADA_CUANTO_PREGUNTAR_MS = 2000;
const MAXIMO_PREPARANDO_MS = 10 * 60 * 1000;

const dormir = (ms, signal) =>
  new Promise((resolve, reject) => {
    const t = setTimeout(resolve, ms);
    signal?.addEventListener('abort', () => {
      clearTimeout(t);
      reject(new DOMException('cancelado', 'AbortError'));
    }, { once: true });
  });

// Un 4xx es el servidor diciendo que no (formato, tamaño): reintentar no lo
// cambia. Sin status (se cortó la red) o 5xx, vale la pena otro intento.
const reintentable = (e) =>
  e?.name !== 'AbortError' && (!e?.status || e.status >= 500 || e.status === 408 || e.status === 429);

const conReintentos = async (intento, signal) => {
  for (let i = 0; ; i++) {
    try {
      return await intento();
    } catch (e) {
      if (!reintentable(e) || i >= ESPERAS_REINTENTO_MS.length) throw e;
      await dormir(ESPERAS_REINTENTO_MS[i], signal);
    }
  }
};

/**
 * Sube un archivo en partes y espera a que el servidor lo prepare.
 * Devuelve { id, paginas, convertido }; el id es lo que va en el pedido.
 */
export async function subirArchivo(file, { alProgresar, signal } = {}) {
  const { id, parte_bytes: parteBytes, partes } = await conReintentos(async () =>
    parse(await fetch(`${PRINTNET_API}/uploads`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nombre: file.name, tamano_bytes: file.size, content_type: file.type || '' }),
      signal,
    })), signal);

  // Un pedazo a la vez: en paralelo no acelera cuando el cuello de botella es
  // la conexión del cliente o la del local, y complica los reintentos.
  for (let n = 0; n < partes; n++) {
    const pedazo = file.slice(n * parteBytes, (n + 1) * parteBytes);
    await conReintentos(async () =>
      parse(await fetch(`${PRINTNET_API}/uploads/${id}/partes/${n}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/octet-stream' },
        body: pedazo,
        signal,
      })), signal);
    alProgresar?.({ fase: 'subiendo', enviado: Math.min((n + 1) * parteBytes, file.size), total: file.size });
  }

  await conReintentos(async () =>
    parse(await fetch(`${PRINTNET_API}/uploads/${id}/completar`, { method: 'POST', signal })), signal);
  alProgresar?.({ fase: 'preparando' });

  // Juntar, convertir y contar corre en segundo plano en el servidor (puede
  // tardar más de lo que Cloudflare espera una respuesta): se pregunta.
  const limite = Date.now() + MAXIMO_PREPARANDO_MS;
  for (;;) {
    await dormir(CADA_CUANTO_PREGUNTAR_MS, signal);
    const est = await conReintentos(async () =>
      parse(await fetch(`${PRINTNET_API}/uploads/${id}`, { signal })), signal);
    if (est.estado === 'listo') return { id, paginas: est.paginas, convertido: est.convertido };
    if (est.estado === 'error') {
      const error = new Error(est.error || 'No pudimos procesar tu documento.');
      error.status = 422;
      throw error;
    }
    if (Date.now() > limite) {
      throw new Error('Tu documento está tardando demasiado en prepararse. Probá de nuevo o escribinos.');
    }
  }
}
```

- [ ] **Paso 2: `limites.js`**

Reemplazar desde el comentario de arriba hasta `MAX_ARCHIVO_BYTES` por:

```js
// Límite de carga de archivos, sobre el TOTAL del pedido.
//
// ESPEJADO EN backend-printnet/subidas.py (MAX_PEDIDO_MB). Si se cambia acá
// hay que cambiarlo allá, o la web va a dejar subir algo que el servidor
// después rechaza. Es la misma trampa que ya tienen los precios entre
// pricing.py y precio.js (ver ESTADO.md).
//
// Antes era 95 MB por el techo de 100 MB por petición de Cloudflare. Ya no
// aplica: los archivos viajan en pedazos de 6 MB (subirArchivo en api.js).
// 300 es lo que la notebook procesa con margen, medido con
// medir_archivo_grande.py.
export const MAX_ARCHIVO_MB = 300;
export const MAX_ARCHIVO_BYTES = MAX_ARCHIVO_MB * 1024 * 1024;
```

- [ ] **Paso 3: `FileUpload.jsx`**

Cambiar el import:

```js
import { subirArchivo } from '../../api';
```

En `explicarError`, agregar después de la línea del 413:

```js
  // 503: el servidor está lleno de subidas en curso; el mensaje ya lo explica.
  if (e?.status === 503) return { mensaje: e.message, detalle: '' };
```

Reemplazar `procesar` por:

```js
  const procesar = async (doc) => {
    try {
      const { id, paginas, convertido } = await subirArchivo(doc.file, {
        signal: doc.cancelar.signal,
        alProgresar: (p) => onActualizar(doc.id, p.fase === 'preparando'
          ? { estado: 'contando', progreso: null }
          : { estado: 'subiendo', progreso: p }),
      });
      onActualizar(doc.id, {
        uploadId: id, paginas, convertido: Boolean(convertido), estado: 'listo', error: null, progreso: null,
      });
    } catch (e) {
      if (e?.name === 'AbortError') return;  // lo quitó el cliente: no hay nada que mostrar
      onActualizar(doc.id, { paginas: null, estado: 'error', error: explicarError(e), progreso: null });
    }
  };
```

Reemplazar el comentario del tope en `recibir`:

```js
      // El tope es sobre la SUMA: el límite lo pone Cloudflare por petición,
      // y el pedido entero viaja en una sola.
```

por:

```js
      // El tope es sobre la SUMA del pedido: el backend la vuelve a controlar
      // al crearlo (subidas.MAX_PEDIDO_BYTES).
```

En el `onReintentar` de `DocumentoFila`, reemplazar
`onActualizar(doc.id, { estado: 'contando', error: null });` por:

```js
onActualizar(doc.id, { estado: 'subiendo', error: null, progreso: { enviado: 0, total: doc.file.size } });
```

En `DocumentoFila`, reemplazar el `<p>` del estado (el que empieza con
`{doc.estado === 'contando'`) por:

```jsx
          <p className={`text-xs ${roto ? 'text-red-600' : 'text-stone-400'}`}>
            {doc.estado === 'subiendo'
              ? `Subiendo… ${formatearTamano(doc.progreso?.enviado || 0)} de ${formatearTamano(doc.progreso?.total || doc.file.size)}`
              : doc.estado === 'contando'
                ? (esConvertible(doc.name) ? 'Convirtiendo a PDF…' : 'Preparando tu documento…')
                : roto
                  ? doc.error?.mensaje
                  : `${doc.paginas} ${doc.paginas === 1 ? 'página' : 'páginas'}${doc.convertido ? ' · convertido a PDF' : ''}`}
          </p>

          {doc.estado === 'subiendo' && (
            <div className="mt-1.5 h-1.5 w-full rounded-full bg-stone-200 overflow-hidden">
              <div
                className="h-full bg-amber-500 transition-all duration-300"
                style={{ width: `${Math.round(100 * (doc.progreso?.enviado || 0) / (doc.progreso?.total || doc.file.size || 1))}%` }}
              />
            </div>
          )}
```

- [ ] **Paso 4: `Fotocopias.jsx`**

Cambiar el import:

```js
import { crearPedidoConSubidas } from '../api';
```

En `agregarDocs`, en el objeto de cada documento, reemplazar
`estado: 'contando',` por:

```js
      estado: 'subiendo',
      progreso: { enviado: 0, total: f.size },
      uploadId: null,
      // Para cortar la subida si el cliente quita el documento a la mitad:
      // con 300 MB, seguir subiendo algo que nadie va a usar es tiempo y disco.
      cancelar: new AbortController(),
```

En `quitarDoc`, antes del `setDocs`, agregar:

```js
    docs.find((d) => d.id === id)?.cancelar?.abort();
```

Reemplazar:

```js
  const contando = docs.some((d) => d.estado === 'contando');
```

por:

```js
  // Mientras haya algo subiendo o preparándose no se puede pagar: el pedido
  // necesita los ids de las subidas ya listas.
  const contando = docs.some((d) => d.estado === 'subiendo' || d.estado === 'contando');
```

En `handlePay`, reemplazar:

```js
      const pedido = await crearPedido(
```

por:

```js
      const pedido = await crearPedidoConSubidas(
```

y el segundo argumento `docs.map((d) => d.file)` por `docs.map((d) => d.uploadId)`.

- [ ] **Paso 5: compilar**

Run: `cd frontend && npm run build`
Expected: compila sin errores. Run: `cd frontend && npx eslint src/api.js src/limites.js src/components/fotocopias/FileUpload.jsx src/pages/Fotocopias.jsx`
Expected: sin errores (warnings que ya estaban antes, aceptables).

- [ ] **Paso 6: probar en el navegador contra el backend local**

1. `cd backend-printnet && .venv/bin/uvicorn main:app --port 8000`
2. `cd frontend && npm run dev` (con `frontend/public/config.js` apuntando a
   `http://localhost:8000`, como en desarrollo de siempre)
3. Generar un PDF grande: `cd backend-printnet && .venv/bin/python -c "from medir_archivo_grande import generar_pesado; print(generar_pesado('/tmp/grande.pdf', 150))"`
4. En `http://localhost:5173/fotocopias`, verificar:
   - subir `/tmp/grande.pdf` (150 MB): barra de progreso avanzando,
     "Preparando tu documento…", y después las páginas (~53);
   - el aviso dice "Hasta 300 MB en total" / "150 de 300 MB usados";
   - un segundo archivo que haga pasar de 300 MB se rechaza antes de subir;
   - quitar un documento a la mitad de la subida la corta (en la pestaña
     Red dejan de salir `PUT`);
   - con todo configurado, "Pagar" crea el pedido (modo fantasma) y en el
     panel de admin aparece con sus páginas;
   - parar el backend a la mitad de una subida y levantarlo antes de ~30 s:
     la subida sigue sola (reintentos);
   - en la pestaña Red, ningún request supera ~6 MB.

- [ ] **Paso 7: commit**

```bash
git add frontend/src/api.js frontend/src/limites.js frontend/src/components/fotocopias/FileUpload.jsx frontend/src/pages/Fotocopias.jsx
git commit -m "feat: la web sube los archivos en partes, hasta 300 MB por pedido

Barra de progreso, reintento automático de cada pedazo, y el archivo se
sube una sola vez: el pedido manda los ids de las subidas.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Tarea 6: Documentación y deploy

**Archivos:**
- Modificar: `ESTADO.md`
- Modificar: `backend-printnet/SPEC.md`
- Modificar: `docs/plan-subida-en-partes.md` (marcar implementado)

- [ ] **Paso 1: `SPEC.md`**

En `## Endpoints`, antes de `### POST /orders/paginas`, agregar:

```markdown
### Subida en partes (`routers/subidas.py`, lógica en `subidas.py`)

Para archivos de hasta 300 MB por pedido a pesar del límite de 100 MB por
petición de Cloudflare. Ver `docs/plan-subida-en-partes.md`.

- `POST /uploads` `{nombre, tamano_bytes, content_type}` → 201 `{id, parte_bytes, partes}`.
  413 si pasa de 300 MB, 422 si el formato no se acepta, 503 si las subidas
  en curso ocupan más de 3 GB.
- `PUT /uploads/{id}/partes/{n}` (cuerpo crudo, ≤ `parte_bytes`) → 200. Idempotente.
- `POST /uploads/{id}/completar` → 202. Junta, convierte y cuenta en segundo plano.
- `GET /uploads/{id}` → `{estado: subiendo|preparando|listo|error, paginas, convertido, error}`.

Estado en `uploads/_subidas/{id}/meta.json`, sin tabla. Se borra a las 24 h
(limpieza al arrancar y cada hora).
```

En `### POST /orders`, agregar:

```markdown
Acepta `files` (camino viejo, 95 MB, una sola petición) **o** `uploads`: un
JSON con los ids de subidas en partes, uno por documento, por posición. Solo
fotocopias. Las subidas se mueven a `uploads/{token}/` recién después de
validar y cotizar: un pedido rechazado no las consume.
```

En `### POST /webhooks/mercadopago`, agregar:

```markdown
El webhook ya no imprime: `confirmar_pago()` marca el pedido (UPDATE
condicional, commit) y `despachar_tras_pago()` corre en segundo plano. Antes
la impresión iba adentro y con un PDF grande el reintento de MP podía
imprimir dos veces.
```

- [ ] **Paso 2: `ESTADO.md`**

En la tabla de la tanda de mejoras, agregar la fila:

```markdown
| 6 | Archivos de hasta 300 MB (subida en partes) | ✅ hecho |
```

y debajo de "### Lo que cambió", agregar:

```markdown
**Archivos de hasta 300 MB por pedido.** Cloudflare corta las peticiones de
más de 100 MB, así que la web parte cada archivo en pedazos de 6 MB y la
notebook los rearma (`subidas.py`). De paso, el archivo se sube **una sola
vez**: antes se subía para contar páginas y otra vez al pagar. Las subidas
abandonadas se borran a las 24 h. `/fotos` sigue con el límite de 95 MB.

**El webhook de MercadoPago ya no imprime.** Marca el pedido pagado, responde,
y la impresión corre en segundo plano. Con archivos grandes, el webhook pasaba
los 22 s de MP y el reintento podía imprimir el pedido dos veces.
```

En "## Trampas conocidas", agregar:

```markdown
**El límite de tamaño está escrito dos veces.** `MAX_PEDIDO_MB` en
`backend-printnet/subidas.py` y `MAX_ARCHIVO_MB` en `frontend/src/limites.js`
tienen que coincidir. `MAX_FILE_MB` en `routers/orders.py` (95) es otro: el
del camino viejo, que sí pasa entero por Cloudflare.

**Un pedido recién pagado queda unos segundos en "pendiente".** Es el tiempo
que tarda en imprimirse en segundo plano. No es un pedido trabado.
```

Si la Tarea 0 mostró que SumatraPDF tarda más de 100 s con 300 MB, agregar
también:

```markdown
**Reimprimir un pedido muy pesado puede dar error de tiempo aunque se haya
impreso.** Cloudflare corta la respuesta a los 100 s, pero la impresora sigue.
Antes de volver a apretar, mirá si salió.
```

- [ ] **Paso 3: marcar el plan de diseño como implementado**

En `docs/plan-subida-en-partes.md`, debajo del título, agregar:

```markdown
> **Implementado** (ver `ESTADO.md`). Plan de implementación:
> [`plan-subida-en-partes-implementacion.md`](plan-subida-en-partes-implementacion.md).
```

- [ ] **Paso 4: commit**

```bash
git add ESTADO.md backend-printnet/SPEC.md docs/plan-subida-en-partes.md
git commit -m "docs: subida en partes y despacho fuera del webhook

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Paso 5: deploy del backend (primero; es compatible con la web vieja)**

`git push`, y en la notebook, **de a un comando**, esperando cada resultado:

1. `cd C:\PrintNet\printnet`
2. `git pull`
3. `cd backend-printnet`
4. `.venv\Scripts\python test_subidas.py`
5. `.venv\Scripts\python test_order_flow.py`
6. `.venv\Scripts\pyinstaller printnet.spec --noconfirm` (recompilar en `dist\`)
7. `Stop-Service PrintNetBackend` (PowerShell como administrador)
8. `Copy-Item C:\PrintNet\printnet\backend-printnet\dist\printnet-backend.exe C:\PrintNet\servicio\ -Force`
9. `Start-Service PrintNetBackend`

Verificar desde el Mac:
- `curl -s -o /dev/null -w '%{http_code}\n' https://api.libreriaglaxara.com.ar/admin/orders` → `401`
  (un `503` significa que no leyó el `.env`, ver `ESTADO.md` punto 4).
- `curl -s -o /dev/null -w '%{http_code}\n' https://api.libreriaglaxara.com.ar/uploads/noexiste` → `404`.
- La web vieja (todavía publicada) sigue tomando pedidos: hacer un pedido
  chico de prueba desde `www.libreriaglaxara.com.ar`.

- [ ] **Paso 6: deploy de la web**

1. `cd frontend && npm run build`
2. Subir `dist/` al Administrador de archivos de cPanel, **un archivo a la vez
   y tildando "sobrescribir"** (sin eso cPanel saltea el archivo sin avisar).
3. **Volver a poner la URL del backend en `public_html/config.js`**: la del
   repositorio está vacía y el deploy la pisa.
4. Probar en `www.libreriaglaxara.com.ar/fotocopias` con un PDF de más de
   100 MB: tiene que subir, mostrar las páginas y llegar a MercadoPago. Se
   puede cancelar en MP: no hace falta pagar para validar la subida.
```
