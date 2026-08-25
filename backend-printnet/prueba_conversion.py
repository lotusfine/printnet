"""Prueba manual de la conversión de documentos a PDF.

Verifica el módulo `document_convert` contra LibreOffice de verdad. Los tests
automáticos usan un ejecutor falso; esto es lo que confirma que el comando
funciona en la máquina real.

    .venv\\Scripts\\python prueba_conversion.py C:\\PrintNet\\prueba.pps
    .venv\\Scripts\\python prueba_conversion.py documento.docx --simular

Herramienta de diagnóstico, no parte del servidor.
"""

import argparse
import os
import sys
import tempfile
import time

from document_convert import (
    FORMATOS_CONVERTIBLES,
    _soffice_por_defecto,
    construir_comando,
    convertir_a_pdf,
    necesita_conversion,
)


def main() -> int:
    p = argparse.ArgumentParser(description="Convierte un documento a PDF.")
    p.add_argument("archivo", help="Documento a convertir")
    p.add_argument("--salida", help="Carpeta de salida (por defecto, una temporal)")
    p.add_argument("--soffice", default=_soffice_por_defecto())
    p.add_argument("--simular", action="store_true",
                   help="Muestra el comando y no convierte")
    args = p.parse_args()

    salida = args.salida or tempfile.mkdtemp(prefix="printnet-conv-")

    print(f"\nArchivo    : {args.archivo}")
    print(f"LibreOffice: {args.soffice}")
    print(f"Salida     : {salida}")
    print(f"\n¿Hay que convertirlo?  {'sí' if necesita_conversion(args.archivo) else 'no (o formato no soportado)'}")
    print(f"Formatos soportados: {', '.join(sorted(FORMATOS_CONVERTIBLES))}")

    perfil = tempfile.mkdtemp(prefix="printnet-lo-")
    cmd = construir_comando(args.soffice, args.archivo, salida, perfil)
    print("\nComando que se ejecuta:")
    print("  " + " ".join(f'"{a}"' if " " in a else a for a in cmd))

    if args.simular:
        print("\n[--simular] No se convirtió nada.")
        return 0

    print("\nConvirtiendo…")
    inicio = time.monotonic()
    r = convertir_a_pdf(args.archivo, salida, soffice_path=args.soffice)
    tardo = time.monotonic() - inicio

    print(f"\nok = {r.ok}   ({tardo:.1f} segundos)")
    print(f"detalle: {r.detalle}")

    if r.ok and r.pdf_path:
        tam = os.path.getsize(r.pdf_path)
        print(f"\nPDF generado: {r.pdf_path}")
        print(f"Tamaño: {tam:,} bytes".replace(",", "."))
        try:
            from pypdf import PdfReader
            print(f"Páginas: {len(PdfReader(r.pdf_path).pages)}")
        except Exception as e:
            print(f"No se pudo contar las páginas: {e}")
        print("\nAbrí ese PDF y compará contra el original: que estén todas las")
        print("páginas, que el texto no se haya corrido y que las imágenes estén.")

    return 0 if r.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
