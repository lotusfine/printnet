"""Genera un PDF de prueba con las páginas numeradas en grande.

Sirve para probar la impresión: con un número enorme en cada página se puede
verificar de un vistazo si el doble faz quedó bien, si el rango imprimió las
páginas correctas, y si el escalado a A3 funcionó.

    .venv\\Scripts\\python generar_pdf_prueba.py                 # 4 páginas
    .venv\\Scripts\\python generar_pdf_prueba.py --paginas 10
    .venv\\Scripts\\python generar_pdf_prueba.py --salida C:\\PrintNet\\prueba.pdf

Escribe el PDF a mano, sin librerías: solo necesita Python. Es una herramienta
de diagnóstico, no parte del servidor.
"""

import argparse

# A4 en puntos PostScript (1/72 pulgada): 210 x 297 mm
ANCHO, ALTO = 595, 842


def _contenido(numero: int, total: int) -> bytes:
    """Stream de dibujo de una página: el número grande y un pie de página."""
    return (
        f"BT /F1 300 Tf 1 0 0 1 {ANCHO / 2 - 90:.0f} {ALTO / 2 - 100:.0f} Tm "
        f"({numero}) Tj ET\n"
        f"BT /F1 24 Tf 1 0 0 1 60 80 Tm (pagina {numero} de {total}) Tj ET\n"
        f"BT /F1 14 Tf 1 0 0 1 60 {ALTO - 60:.0f} Tm "
        f"(PrintNet - PDF de prueba) Tj ET\n"
    ).encode("latin-1")


def generar(paginas: int) -> bytes:
    objetos: list[bytes] = []

    # 1: catálogo, 2: árbol de páginas, 3: fuente. Después, por cada página:
    # su objeto Page y su stream de contenido.
    ids_pagina = [4 + i * 2 for i in range(paginas)]
    kids = " ".join(f"{i} 0 R" for i in ids_pagina)

    objetos.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objetos.append(f"<< /Type /Pages /Kids [{kids}] /Count {paginas} >>".encode())
    objetos.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    for i in range(paginas):
        id_contenido = ids_pagina[i] + 1
        objetos.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {ANCHO} {ALTO}] "
            f"/Resources << /Font << /F1 3 0 R >> >> "
            f"/Contents {id_contenido} 0 R >>".encode()
        )
        flujo = _contenido(i + 1, paginas)
        objetos.append(
            f"<< /Length {len(flujo)} >>\nstream\n".encode() + flujo + b"endstream"
        )

    # Ensamblado con la tabla xref, que necesita el offset exacto de cada objeto.
    salida = bytearray(b"%PDF-1.4\n")
    offsets = []
    for numero, cuerpo in enumerate(objetos, start=1):
        offsets.append(len(salida))
        salida += f"{numero} 0 obj\n".encode() + cuerpo + b"\nendobj\n"

    inicio_xref = len(salida)
    salida += f"xref\n0 {len(objetos) + 1}\n".encode()
    salida += b"0000000000 65535 f \n"
    for off in offsets:
        salida += f"{off:010d} 00000 n \n".encode()
    salida += (
        f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\n"
        f"startxref\n{inicio_xref}\n%%EOF\n"
    ).encode()

    return bytes(salida)


def main() -> int:
    p = argparse.ArgumentParser(description="Genera un PDF de prueba numerado.")
    p.add_argument("--paginas", type=int, default=4)
    p.add_argument("--salida", default="prueba.pdf")
    args = p.parse_args()

    if args.paginas < 1:
        p.error("--paginas tiene que ser 1 o más")

    datos = generar(args.paginas)
    with open(args.salida, "wb") as f:
        f.write(datos)

    print(f"Escrito {args.salida}: {args.paginas} páginas, {len(datos)} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
