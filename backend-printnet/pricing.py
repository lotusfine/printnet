"""Tabla de precios de PrintNet — Fase 1.

Hardcodeada a propósito: NO es editable desde ningún endpoint ni desde el
admin. Cambiar un precio = editar este archivo y redeployar.

La fórmula replica la de frontend/src/components/fotocopias/PrintOptions.jsx
(calcPrice), con una diferencia deliberada: el backend cobra por las páginas
del rango elegido, mientras que el frontend hoy muestra el precio del
documento completo aunque haya rango (discrepancia anotada en SPEC.md).

Los pedidos de /fotos NO tienen precio en esta fase: se cotizan manualmente
(precio_total = NULL).
"""

from math import ceil

# $ por página (hoja en realidad: doble faz divide por 2)
PRECIO_POR_PAGINA = {
    "byn": 10,
    "color": 25,
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


def precio_anillado(hojas_por_copia: int, copias: int) -> int:
    por_copia = (
        ANILLADO_HASTA_100_HOJAS
        if hojas_por_copia <= 100
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
    """Precio total en pesos (entero) para un pedido de /fotocopias.

    IMPORTANTE: esta fórmula debe mantenerse espejada con calcPrice en
    frontend/src/components/fotocopias/PrintOptions.jsx para que el precio
    pre-compra coincida con el post-compra.
    """
    hojas = ceil(paginas / 2) if caras == "doble" else paginas
    por_pagina = PRECIO_POR_PAGINA[color]
    multiplicador = RECARGO_A3 if tamano == "A3" else 1
    total = round(hojas * copias * por_pagina * multiplicador)
    if terminaciones and "Anillado" in terminaciones:
        total += precio_anillado(hojas, copias)
    return total
