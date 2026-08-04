"""Tabla de precios de PrintNet.

Hardcodeada a propósito: NO es editable desde ningún endpoint ni desde el
admin. Cambiar un precio = editar este archivo y redeployar.

La fórmula debe mantenerse espejada con calcPrice en
frontend/src/components/fotocopias/PrintOptions.jsx para que el precio
pre-compra coincida con el post-compra.

Los pedidos de /fotos NO tienen precio acá: se cotizan manualmente
(precio_total = NULL). Escaneo, edición, fotocopia DNI y foto carnet se
cobran en el local y no pasan por este motor.
"""

from math import ceil

# ---------------------------------------------------------------------------
# Tramos por cantidad (bracket pricing PLANO, no marginal)
#
# El precio unitario se decide según en qué tramo cae la cantidad TOTAL de la
# línea, y ese precio se aplica a TODAS las unidades: no se cobran las
# primeras N a precio base y el resto con descuento.
#   Ej.: 300 copias B&N simple faz → 300 × $130 (no 19×200 + 80×150 + 201×130)
#
# Cada tramo es (tope_incluido, precio_unitario); None = "en adelante".
# Unidad de la cantidad: COPIAS en simple faz, HOJAS FÍSICAS en doble faz.
# ---------------------------------------------------------------------------
TRAMOS: dict[tuple[str, str], list[tuple[int | None, int]]] = {
    ("byn", "simple"): [(19, 200), (99, 150), (None, 130)],
    ("byn", "doble"): [(49, 200), (None, 150)],
    ("color", "simple"): [(19, 400), (None, 300)],
    ("color", "doble"): [(19, 600), (None, 450)],
}

RECARGO_A3 = 1.5

# Terminaciones. El anillado se cobra POR COPIA según las hojas físicas de
# cada copia. Plastificado y corte por ahora solo aplican a pedidos de /fotos
# (que se cotizan a mano); quedan acá como referencia de la tabla de precios.
ANILLADO_HASTA_100_HOJAS = 2000
ANILLADO_MAS_100_HOJAS = 3500
PLASTIFICADO_HOJA_A4 = 1400
PLASTIFICADO_MEDIA_HOJA = 700
CORTE_HOJA_A4 = 500


def hojas_por_copia(paginas: int, caras: str) -> int:
    """Hojas físicas de UNA copia.

    En doble faz entran 2 carillas por hoja, así que un documento de 96
    páginas son 48 hojas. El impar redondea para arriba (una carilla suelta
    igual consume una hoja).
    """
    return ceil(paginas / 2) if caras == "doble" else paginas


def precio_unitario(color: str, caras: str, cantidad: int) -> int:
    """Precio por unidad según el tramo en el que cae `cantidad`.

    `cantidad` es el total de la línea: copias en simple faz, hojas físicas
    en doble faz.
    """
    try:
        tramos = TRAMOS[(color, caras)]
    except KeyError:
        raise ValueError(f"combinación de precio desconocida: {color}/{caras}")

    for tope, precio in tramos:
        if tope is None or cantidad <= tope:
            return precio
    # Inalcanzable: el último tramo siempre tiene tope None.
    raise ValueError(f"sin tramo para cantidad {cantidad} en {color}/{caras}")


def precio_anillado(hojas_de_una_copia: int, copias: int) -> int:
    por_copia = (
        ANILLADO_HASTA_100_HOJAS
        if hojas_de_una_copia <= 100
        else ANILLADO_MAS_100_HOJAS
    )
    return por_copia * copias


def paginas_del_rango(rango_modo: str, rango_valor: str, total_paginas: int) -> int:
    """Cantidad de páginas a imprimir según el rango.

    El formato del valor ("N" o "N-M", N<=M, N>=1) ya viene validado por el
    modelo. Acá se valida contra la cantidad real de páginas del documento:
    esta es la validación que el frontend dejó explícitamente delegada al
    backend.
    """
    if rango_modo != "rango":
        return total_paginas

    partes = rango_valor.strip().split("-")
    inicio = int(partes[0])
    fin = int(partes[1]) if len(partes) == 2 else inicio

    if fin > total_paginas:
        raise ValueError(
            f"El rango {rango_valor} excede las {total_paginas} páginas del documento"
        )
    return fin - inicio + 1


def calcular_precio_fotocopias(
    paginas: int,
    copias: int,
    color: str,
    caras: str,
    tamano: str,
    terminaciones: list[str] | None = None,
) -> int:
    """Precio total en pesos (entero) de una línea de /fotocopias.

    El tramo se evalúa sobre la cantidad TOTAL de la línea (hojas de una
    copia × cantidad de copias): pedir 2 copias de 50 páginas simple faz son
    100 unidades y cae en el tramo de 100+.
    """
    hojas_copia = hojas_por_copia(paginas, caras)
    cantidad_total = hojas_copia * copias

    unitario = precio_unitario(color, caras, cantidad_total)
    multiplicador = RECARGO_A3 if tamano == "A3" else 1
    total = round(cantidad_total * unitario * multiplicador)

    if terminaciones and "Anillado" in terminaciones:
        total += precio_anillado(hojas_copia, copias)
    return total
