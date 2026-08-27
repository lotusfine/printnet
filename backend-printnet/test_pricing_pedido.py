"""Tests del precio de un pedido con VARIOS documentos.

Correr:  .venv/bin/python test_pricing_pedido.py
(sin pytest a propósito, igual que test_pricing.py)

DECISIÓN DE NEGOCIO QUE ESTO IMPLEMENTA (2026-08-26): el tramo de descuento se
calcula sobre el TOTAL del pedido, sumando todos los documentos. Cada documento
usa después su propia tabla de precios según color y caras.

El motivo: si cada documento tuviera su propio tramo, quien trae su trabajo
partido en tres archivos pagaría más que quien lo trae en uno solo, por el
mismo trabajo. En cuanto un cliente lo nota, es un reclamo con razón.

LA GARANTÍA MÁS IMPORTANTE DE ESTE ARCHIVO es la primera sección: un pedido de
UN documento tiene que costar exactamente lo mismo que antes de este cambio.
Todos los pedidos que hoy existen son de un documento.
"""

import sys

import pricing
from pricing import Documento, calcular_precio_pedido

fallos: list[str] = []


def check(nombre: str, obtenido, esperado):
    if obtenido == esperado:
        print(f"  ok  {nombre}")
    else:
        print(f"  FALLA  {nombre}: esperado {esperado}, obtenido {obtenido}")
        fallos.append(nombre)


def doc(paginas, copias=1, color="byn", caras="simple", tamano="A4", terminaciones=None):
    return Documento(paginas=paginas, copias=copias, color=color, caras=caras,
                     tamano=tamano, terminaciones=terminaciones or [])


# ─────────────────────────────────────────────
print("\n== Un documento cuesta EXACTAMENTE lo mismo que antes ==")
# Barrido sobre toda la tabla: si alguien toca el motor y cambia el precio de
# un pedido de un solo documento, tiene que fallar acá.

difs = []
casos = 0
for paginas in (1, 5, 19, 20, 40, 49, 50, 99, 100, 250, 500):
    for copias in (1, 2, 3, 10):
        for color in ("byn", "color"):
            for caras in ("simple", "doble"):
                for tamano in ("A4", "A3"):
                    casos += 1
                    viejo = pricing.calcular_precio_fotocopias(
                        paginas, copias, color, caras, tamano
                    )
                    nuevo = calcular_precio_pedido(
                        [doc(paginas, copias, color, caras, tamano)]
                    ).total
                    if viejo != nuevo:
                        difs.append(f"{paginas}p×{copias} {color}/{caras}/{tamano}: "
                                    f"{viejo} vs {nuevo}")

check(f"{casos} combinaciones dan el mismo precio que el motor de siempre",
      difs, [])

check("con anillado también coincide",
      calcular_precio_pedido([doc(40, 2, terminaciones=["Anillado"])]).total,
      pricing.calcular_precio_fotocopias(40, 2, "byn", "simple", "A4", ["Anillado"]))


print("\n== El tramo se calcula sobre el total del pedido ==")

tres = [doc(10), doc(10), doc(10)]
check("3 documentos de 10 páginas suman 30 hojas y caen en el tramo 20-99",
      calcular_precio_pedido(tres).total, 30 * 150)
check("por separado costarían más (esa es la diferencia buscada)",
      3 * pricing.calcular_precio_fotocopias(10, 1, "byn", "simple", "A4"), 30 * 200)

check("dos documentos que juntos llegan a 100 usan el tramo de 100+",
      calcular_precio_pedido([doc(60), doc(40)]).total, 100 * 130)
check("y si juntos no llegan, se quedan en el tramo de abajo",
      calcular_precio_pedido([doc(60), doc(30)]).total, 90 * 150)

check("las copias cuentan para el tramo, no solo las páginas",
      calcular_precio_pedido([doc(5, copias=3), doc(5)]).total, 20 * 150)


print("\n== Cada documento usa su propia tabla ==")
# El tramo es global, pero un documento a color no se cobra a precio de B&N.

mixto = calcular_precio_pedido([doc(15, color="byn"), doc(15, color="color")])
check("30 hojas en total: el tramo 20-99 aplica a los dos",
      mixto.total, 15 * 150 + 15 * 300)
check("el desglose suma exactamente el total",
      sum(d.subtotal for d in mixto.documentos), mixto.total)
check("informa la cantidad global, que es de dónde sale el descuento",
      mixto.cantidad_total, 30)

check("doble faz y simple faz conviven, cada uno con su tabla",
      calcular_precio_pedido([doc(40, caras="doble"), doc(30, caras="simple")]).total,
      20 * 150 + 30 * 150)


print("\n== A3 y terminaciones son por documento ==")

check("el recargo de A3 se aplica solo al documento que lo pide",
      calcular_precio_pedido([doc(15, tamano="A3"), doc(15)]).total,
      round(15 * 150 * 1.5) + 15 * 150)

con_anillado = calcular_precio_pedido([doc(20, terminaciones=["Anillado"]), doc(20)])
check("el anillado se suma solo al documento que lo lleva",
      con_anillado.total, 20 * 150 + 2000 + 20 * 150)


print("\n== Bordes ==")

check("un pedido sin documentos vale 0", calcular_precio_pedido([]).total, 0)
check("y no explota al pedirle el desglose", calcular_precio_pedido([]).documentos, [])

muchos = calcular_precio_pedido([doc(1) for _ in range(25)])
check("25 documentos de 1 página llegan al tramo 20-99",
      muchos.total, 25 * 150)

check("el desglose trae una entrada por documento",
      len(calcular_precio_pedido([doc(5), doc(5), doc(5)]).documentos), 3)


# ─────────────────────────────────────────────
print()
if fallos:
    print(f"✗ {len(fallos)} fallo(s): {', '.join(fallos)}")
    sys.exit(1)
print("✓ todos los tests de precio por pedido pasaron")
