"""Tests de la normalización de tamaño de página.

Correr:  .venv/bin/python test_pdf_normalize.py
(sin pytest a propósito, igual que el resto)

POR QUÉ EXISTE ESTO: SumatraPDF ignora el tamaño de papel que se le pide por
línea de comandos y usa el tamaño de página del PDF. Comprobado contra la
Ricoh IM C4500: paper=, bin=, la config de la cola y una cola dedicada a A3,
las cuatro se ignoran en silencio; un PDF A3 sale en A3 sin pedir nada.

Consecuencia de plata: si no normalizamos, un cliente que sube un PDF A3 y
paga precio de A4 imprime en A3. Por eso se normaliza SIEMPRE, no solo cuando
el pedido es A3.
"""

import logging
import os
import sys
import tempfile

logging.getLogger("printnet.pdf").setLevel(logging.CRITICAL)

from pypdf import PageObject, PdfReader, PdfWriter

from generar_pdf_prueba import generar
from pdf_normalize import TAMANOS_PT, normalizar_pdf

fallos: list[str] = []
temporales: list[str] = []


def check(nombre: str, obtenido, esperado):
    if obtenido == esperado:
        print(f"  ok  {nombre}")
    else:
        print(f"  FALLA  {nombre}: esperado {esperado}, obtenido {obtenido}")
        fallos.append(nombre)


def temporal(sufijo=".pdf") -> str:
    f = tempfile.NamedTemporaryFile(suffix=sufijo, delete=False)
    f.close()
    temporales.append(f.name)
    return f.name


def pdf_de_prueba(paginas=2, tamano="A4") -> str:
    """PDF con contenido real (números grandes), del generador del proyecto."""
    ruta = temporal()
    with open(ruta, "wb") as f:
        f.write(generar(paginas, tamano))
    return ruta


def pdf_con_tamanos(tamanos: list[tuple[float, float]]) -> str:
    """PDF de páginas en blanco con los tamaños pedidos, para casos raros."""
    ruta = temporal()
    w = PdfWriter()
    for ancho, alto in tamanos:
        w.add_page(PageObject.create_blank_page(width=ancho, height=alto))
    with open(ruta, "wb") as f:
        w.write(f)
    return ruta


def medidas(ruta: str) -> list[tuple[int, int]]:
    """Tamaño redondeado de cada página, en puntos."""
    r = PdfReader(ruta)
    return [(round(float(p.mediabox.width)), round(float(p.mediabox.height)))
            for p in r.pages]


A4 = (595, 842)
A3 = (842, 1191)
A4_APAISADA = (842, 595)
A3_APAISADA = (1191, 842)


# ─────────────────────────────────────────────
print("\n== Conversión entre tamaños ==")

destino = temporal()
r = normalizar_pdf(pdf_de_prueba(4, "A4"), destino, "A3")
check("A4 → A3: todas las páginas quedan A3", medidas(destino), [A3] * 4)
check("A4 → A3: no se pierde ninguna página", r.paginas, 4)
check("A4 → A3: informa las 4 como convertidas", r.convertidas, 4)

destino = temporal()
normalizar_pdf(pdf_de_prueba(3, "A3"), destino, "A4")
check("A3 → A4: todas las páginas quedan A4", medidas(destino), [A4] * 3)

destino = temporal()
r = normalizar_pdf(pdf_de_prueba(2, "A4"), destino, "A4")
check("A4 → A4: el tamaño no cambia", medidas(destino), [A4] * 2)
check("A4 → A4: informa 0 convertidas", r.convertidas, 0)


print("\n== Orientación ==")

destino = temporal()
normalizar_pdf(pdf_con_tamanos([A4_APAISADA]), destino, "A3")
check("una A4 apaisada va a A3 apaisada, no a A3 vertical",
      medidas(destino), [A3_APAISADA])

destino = temporal()
normalizar_pdf(pdf_con_tamanos([A3_APAISADA]), destino, "A4")
check("una A3 apaisada va a A4 apaisada", medidas(destino), [A4_APAISADA])

destino = temporal()
normalizar_pdf(pdf_con_tamanos([A4, A4_APAISADA]), destino, "A3")
check("cada página conserva su propia orientación",
      medidas(destino), [A3, A3_APAISADA])


print("\n== Documentos con tamaños mezclados ==")

destino = temporal()
r = normalizar_pdf(pdf_con_tamanos([A4, A3, A4]), destino, "A4")
check("un documento mezclado sale todo en el tamaño pedido",
      medidas(destino), [A4, A4, A4])
check("solo cuenta como convertida la que realmente cambió", r.convertidas, 1)

destino = temporal()
normalizar_pdf(pdf_con_tamanos([(612, 792)]), destino, "A4")  # tamaño carta
check("un tamaño que no es ni A4 ni A3 (carta) también se normaliza",
      medidas(destino), [A4])


print("\n== El contenido sobrevive ==")

destino = temporal()
normalizar_pdf(pdf_de_prueba(3, "A4"), destino, "A3")
textos = [p.extract_text() for p in PdfReader(destino).pages]
check("el texto sigue estando después de convertir",
      all(str(i + 1) in t for i, t in enumerate(textos)), True)
check("no se mezclaron las páginas entre sí",
      [t.split("\n")[0] for t in textos], ["1", "2", "3"])


print("\n== Errores ==")

try:
    normalizar_pdf(pdf_de_prueba(1, "A4"), temporal(), "A5")
    check("tamaño no soportado → ValueError", "no falló", "ValueError")
except ValueError as e:
    check("tamaño no soportado → ValueError", "A5" in str(e), True)

try:
    normalizar_pdf("/no/existe/nada.pdf", temporal(), "A4")
    check("archivo inexistente → error", "no falló", "error")
except (FileNotFoundError, OSError):
    check("archivo inexistente → error", True, True)


# ─────────────────────────────────────────────
for t in temporales:
    try:
        os.unlink(t)
    except OSError:
        pass

print()
if fallos:
    print(f"✗ {len(fallos)} fallo(s): {', '.join(fallos)}")
    sys.exit(1)
print("✓ todos los tests de normalización pasaron")
