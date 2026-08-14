"""Prueba manual del despachador contra una impresora real.

Sirve para probar la impresión SOLA: sin backend, sin webhook, sin MercadoPago
y sin .env. Es el paso previo a levantar el sistema entero.

Uso típico (en la notebook, con el venv activado):

    # 1. Ver qué comando se ejecutaría, SIN imprimir:
    .venv\\Scripts\\python prueba_impresion.py documento.pdf --simular

    # 2. Imprimir de verdad, lo más simple posible:
    .venv\\Scripts\\python prueba_impresion.py documento.pdf

    # 3. Ir subiendo la apuesta:
    .venv\\Scripts\\python prueba_impresion.py documento.pdf --caras doble
    .venv\\Scripts\\python prueba_impresion.py documento.pdf --color color --tamano A3
    .venv\\Scripts\\python prueba_impresion.py documento.pdf --rango 2-3 --copias 2

Empezá SIEMPRE con --simular y mirá el comando antes de mandar papel.

Este archivo no es parte del servidor: es una herramienta de diagnóstico. La
lógica que ejerce (construir_comando) está cubierta por test_dispatch.py.
"""

import argparse
import os
import sys

from print_dispatch import SumatraDispatcher, construir_comando

RICOH = "RICOH IM C4500 PCL 6"
SUMATRA_DEFAULT = r"C:\PrintNet\SumatraPDF.exe"


def main() -> int:
    p = argparse.ArgumentParser(
        description="Manda un PDF a imprimir usando el mismo código que el backend.",
    )
    p.add_argument("pdf", help="Ruta al PDF a imprimir")
    p.add_argument("--color", choices=["byn", "color"], default="byn")
    p.add_argument("--caras", choices=["simple", "doble"], default="simple")
    p.add_argument("--copias", type=int, default=1)
    p.add_argument("--tamano", choices=["A4", "A3"], default="A4")
    p.add_argument("--rango", default="", help='Ej. "3-8". Vacío = todas las páginas')
    p.add_argument("--impresora", default=RICOH, help=f"Default: {RICOH}")
    p.add_argument("--sumatra", default=os.environ.get("PRINTNET_SUMATRA", SUMATRA_DEFAULT))
    p.add_argument("--simular", action="store_true",
                   help="Muestra el comando y NO imprime")
    args = p.parse_args()

    options = {
        "opciones": {
            "color": args.color,
            "caras": args.caras,
            "copias": args.copias,
            "tamano": args.tamano,
        },
        "rango": (
            {"modo": "rango", "valor": args.rango} if args.rango.strip()
            else {"modo": "todas", "valor": ""}
        ),
    }

    cmd = construir_comando(args.sumatra, args.impresora, args.pdf, options)

    print("\nOpciones del pedido:")
    print(f"  color   : {args.color}")
    print(f"  caras   : {args.caras}")
    print(f"  copias  : {args.copias}")
    print(f"  tamaño  : {args.tamano}")
    print(f"  rango   : {args.rango or 'todas las páginas'}")
    print(f"\nImpresora: {args.impresora}")
    print(f"SumatraPDF: {args.sumatra}")
    print("\nComando que se ejecuta:")
    print("  " + " ".join(f'"{a}"' if " " in a else a for a in cmd))

    if args.simular:
        print("\n[--simular] No se imprimió nada.")
        return 0

    print("\nDespachando...")
    resultado = SumatraDispatcher(exe_path=args.sumatra).dispatch(
        args.impresora, args.pdf, options
    )
    print(f"\nok = {resultado.ok}")
    print(f"detalle: {resultado.detalle}")

    if resultado.ok:
        print(
            "\nOJO: 'ok' quiere decir que el trabajo se encoló en Windows, no que\n"
            "el papel haya salido. Andá a mirar la impresora."
        )
    return 0 if resultado.ok else 1


if __name__ == "__main__":
    sys.exit(main())
