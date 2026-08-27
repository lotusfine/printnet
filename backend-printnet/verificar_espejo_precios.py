"""Compara el motor de precios del backend con el de la web, caso por caso.

Correr:  .venv/bin/python verificar_espejo_precios.py
Necesita Node instalado (solo para esta verificación, no para el servidor).

POR QUÉ EXISTE: la fórmula de precios está escrita dos veces —en pricing.py y
en frontend/src/precio.js— porque la web muestra el precio antes de comprar y
el backend lo recalcula al crear el pedido. Si los dos se desincronizan, el
cliente ve un número y se le cobra otro.

Está anotado en ESTADO.md como trampa conocida desde el principio del proyecto,
pero hasta ahora dependía de que alguien se acordara. Esto lo verifica.
"""

import json
import subprocess
import sys
from pathlib import Path

import pricing

PRECIO_JS = Path(__file__).resolve().parent.parent / "frontend" / "src" / "precio.js"

# Casos: cada uno es una lista de documentos (paginas, copias, color, caras, tamano)
CASOS: list[list[tuple]] = []
for paginas in (1, 5, 19, 20, 49, 50, 99, 100, 250):
    for copias in (1, 2, 5):
        for color in ("byn", "color"):
            for caras in ("simple", "doble"):
                for tamano in ("A4", "A3"):
                    CASOS.append([(paginas, copias, color, caras, tamano)])

# Pedidos con varios documentos, incluidos los que mezclan configuraciones
CASOS += [
    [(10, 1, "byn", "simple", "A4")] * 3,
    [(10, 1, "byn", "simple", "A4"), (10, 1, "color", "simple", "A4")],
    [(60, 1, "byn", "simple", "A4"), (40, 1, "byn", "simple", "A4")],
    [(15, 1, "byn", "simple", "A3"), (15, 1, "byn", "simple", "A4")],
    [(40, 1, "byn", "doble", "A4"), (30, 1, "byn", "simple", "A4")],
    [(5, 3, "color", "doble", "A3"), (7, 2, "byn", "simple", "A4"), (1, 1, "byn", "doble", "A4")],
    [(1, 1, "byn", "simple", "A4")] * 25,
]


def como_dict(caso):
    return [
        {"paginas": p, "opciones": {"color": c, "caras": ca, "copias": co, "tamano": t}}
        for (p, co, c, ca, t) in caso
    ]


def precio_python(caso) -> int:
    docs = [
        pricing.Documento(paginas=p, copias=co, color=c, caras=ca, tamano=t)
        for (p, co, c, ca, t) in caso
    ]
    return pricing.calcular_precio_pedido(docs).total


def precios_js(casos) -> list[int]:
    script = f"""
      import {{ calcPrecioPedido }} from {json.dumps(str(PRECIO_JS))};
      const casos = {json.dumps([como_dict(c) for c in casos])};
      console.log(JSON.stringify(casos.map(c => calcPrecioPedido(c).total)));
    """
    r = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        capture_output=True, text=True, timeout=60,
    )
    if r.returncode != 0:
        print("No se pudo ejecutar el motor de la web:")
        print(r.stderr.strip()[:600])
        sys.exit(2)
    return json.loads(r.stdout)


def main() -> int:
    if not PRECIO_JS.is_file():
        print(f"No encuentro {PRECIO_JS}")
        return 2

    js = precios_js(CASOS)
    difs = []
    for caso, precio_web in zip(CASOS, js):
        precio_backend = precio_python(caso)
        if precio_backend != precio_web:
            difs.append((caso, precio_backend, precio_web))

    print(f"{len(CASOS)} casos comparados entre pricing.py y precio.js")
    if difs:
        print(f"\n✗ {len(difs)} DIFIEREN — el cliente vería un precio y se le cobraría otro:\n")
        for caso, backend, web in difs[:15]:
            print(f"  {caso}")
            print(f"    backend: ${backend}   web: ${web}")
        return 1
    print("✓ los dos motores dan exactamente el mismo precio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
