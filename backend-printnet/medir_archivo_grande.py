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
