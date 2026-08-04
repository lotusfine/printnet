"""Tests del motor de precios.

Correr:  .venv/bin/python test_pricing.py
(sin pytest a propósito: el backend corre en una Raspberry Pi y no queremos
dependencias de desarrollo instaladas ahí)
"""

import sys

from pricing import (
    calcular_precio_fotocopias as precio,
    hojas_por_copia,
    precio_unitario,
)

fallos: list[str] = []


def check(nombre: str, obtenido, esperado):
    if obtenido == esperado:
        print(f"  ok  {nombre}")
    else:
        print(f"  FALLA  {nombre}: esperado {esperado}, obtenido {obtenido}")
        fallos.append(nombre)


print("\n== Tramos B&N simple faz (200 / 150 / 130) ==")
check("1 copia", precio(1, 1, "byn", "simple", "A4"), 200)
check("19 copias (borde alto tramo 1)", precio(19, 1, "byn", "simple", "A4"), 19 * 200)
check("20 copias (borde bajo tramo 2)", precio(20, 1, "byn", "simple", "A4"), 20 * 150)
check("99 copias (borde alto tramo 2)", precio(99, 1, "byn", "simple", "A4"), 99 * 150)
check("100 copias (borde bajo tramo 3)", precio(100, 1, "byn", "simple", "A4"), 100 * 130)
check("300 copias (ejemplo de la spec)", precio(300, 1, "byn", "simple", "A4"), 300 * 130)

print("\n== Tramos B&N doble faz (200 / 150), por HOJA ==")
check("ejemplo spec: 96 pág → 48 hojas", precio(96, 1, "byn", "doble", "A4"), 9600)
check("ejemplo spec: 120 pág → 60 hojas", precio(120, 1, "byn", "doble", "A4"), 9000)
check("98 pág → 49 hojas (borde alto)", precio(98, 1, "byn", "doble", "A4"), 49 * 200)
check("100 pág → 50 hojas (borde bajo)", precio(100, 1, "byn", "doble", "A4"), 50 * 150)

print("\n== Tramos Color simple faz (400 / 300) ==")
check("19 copias", precio(19, 1, "color", "simple", "A4"), 19 * 400)
check("20 copias", precio(20, 1, "color", "simple", "A4"), 20 * 300)

print("\n== Tramos Color doble faz (600 / 450), por HOJA ==")
check("ejemplo spec: 30 pág → 15 hojas", precio(30, 1, "color", "doble", "A4"), 9000)
check("ejemplo spec: 50 pág → 25 hojas", precio(50, 1, "color", "doble", "A4"), 11250)
check("38 pág → 19 hojas (borde alto)", precio(38, 1, "color", "doble", "A4"), 19 * 600)
check("40 pág → 20 hojas (borde bajo)", precio(40, 1, "color", "doble", "A4"), 20 * 450)

print("\n== Bracket PLANO, no marginal ==")
# Si fuera marginal daría 19*200 + 80*150 + 201*130 = 42.930
check("300 copias no se cobran por tramos acumulados",
      precio(300, 1, "byn", "simple", "A4"), 39000)

print("\n== Páginas impares en doble faz ==")
check("1 página → 1 hoja", hojas_por_copia(1, "doble"), 1)
check("3 páginas → 2 hojas", hojas_por_copia(3, "doble"), 2)
check("99 páginas → 50 hojas → tramo 50+", precio(99, 1, "byn", "doble", "A4"), 50 * 150)

print("\n== El tramo se evalúa sobre el total de la línea (hojas × copias) ==")
check("2 copias × 10 pág = 20 unidades → tramo 20-99",
      precio(10, 2, "byn", "simple", "A4"), 20 * 150)
check("1 copia × 10 pág = 10 unidades → tramo 1-19",
      precio(10, 1, "byn", "simple", "A4"), 10 * 200)
check("5 copias × 20 pág = 100 unidades → tramo 100+",
      precio(20, 5, "byn", "simple", "A4"), 100 * 130)

print("\n== Recargo A3 (50%) ==")
check("10 copias B&N simple A3", precio(10, 1, "byn", "simple", "A3"), round(10 * 200 * 1.5))

print("\n== Anillado (se suma al total, por copia) ==")
check("20 copias + anillado", precio(20, 1, "byn", "simple", "A4", ["Anillado"]),
      20 * 150 + 2000)
check("2 copias de 60 pág simple + anillado",
      precio(60, 2, "byn", "simple", "A4", ["Anillado"]), 120 * 130 + 2 * 2000)

print("\n== precio_unitario directo ==")
check("byn/simple 50", precio_unitario("byn", "simple", 50), 150)
check("color/doble 19", precio_unitario("color", "doble", 19), 600)
check("color/doble 20", precio_unitario("color", "doble", 20), 450)

print()
if fallos:
    print(f"RESULTADO: {len(fallos)} FALLA(S) → {', '.join(fallos)}")
    sys.exit(1)
print("RESULTADO: todos los tests pasaron")
sys.exit(0)
