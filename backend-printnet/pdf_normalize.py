"""Normalización del tamaño de página de los PDF antes de imprimir.

POR QUÉ EXISTE ESTE MÓDULO
--------------------------
SumatraPDF **ignora** el tamaño de papel que se le pide por línea de comandos
y usa el tamaño de página del PDF. Verificado contra la Ricoh IM C4500: se
probaron `paper=A3`, `bin=2`, fijar A3 en la configuración de la cola y crear
una cola dedicada a A3 — las cuatro se ignoran en silencio. En cambio, un PDF
cuyas páginas SON A3 sale en A3 sin pedir nada.

Consecuencia, y es de plata: si el papel siempre sigue al documento, un
cliente que sube un PDF A3 y paga precio de A4 imprimiría en A3. Por eso se
normaliza SIEMPRE, no solo cuando el pedido es A3: es lo que garantiza que lo
que sale por la impresora coincida con lo que se cobró.

El contenido se escala proporcionalmente y se centra. No se recorta ni se
deforma: si las proporciones no coinciden exactamente (A4 y A3 sí coinciden;
una hoja carta no), queda un margen parejo.
"""

import logging
from dataclasses import dataclass

from pypdf import PageObject, PdfReader, PdfWriter, Transformation

logger = logging.getLogger("printnet.pdf")

# Medidas ISO exactas, en puntos PostScript (1/72 de pulgada), en vertical.
TAMANOS_PT = {
    "A4": (595.276, 841.890),   # 210 x 297 mm
    "A3": (841.890, 1190.551),  # 297 x 420 mm
}

# Los PDF suelen traer medidas redondeadas (595x842 en vez de 595.276x841.890).
# Sin esta tolerancia reescribiríamos páginas que ya están bien.
TOLERANCIA_PT = 1.0


@dataclass
class ResultadoNormalizacion:
    paginas: int
    convertidas: int


def _objetivo(ancho: float, alto: float, tamano: str) -> tuple[float, float]:
    """Tamaño destino, respetando la orientación de la página original.

    Una página apaisada tiene que ir a una hoja apaisada: si no, un plano o una
    presentación horizontal saldrían rotados o con márgenes enormes.
    """
    vertical_w, vertical_h = TAMANOS_PT[tamano]
    if ancho > alto:
        return vertical_h, vertical_w
    return vertical_w, vertical_h


def normalizar_pdf(origen: str, destino: str, tamano: str) -> ResultadoNormalizacion:
    """Reescribe `origen` en `destino` con todas sus páginas en `tamano`.

    Las páginas que ya están en el tamaño correcto se copian tal cual, sin
    reescalar: evita perder calidad en el caso más común, que es A4 → A4.
    """
    if tamano not in TAMANOS_PT:
        raise ValueError(
            f"Tamaño no soportado: {tamano!r}. Disponibles: {sorted(TAMANOS_PT)}"
        )

    lector = PdfReader(origen)
    escritor = PdfWriter()
    convertidas = 0

    for pagina in lector.pages:
        # Si la página trae /Rotate, sus medidas declaradas no son las que se
        # ven. Esto hornea la rotación en el contenido para que mediabox diga
        # la verdad y la decisión de orientación sea correcta.
        pagina.transfer_rotation_to_content()

        caja = pagina.mediabox
        ancho, alto = float(caja.width), float(caja.height)
        destino_ancho, destino_alto = _objetivo(ancho, alto, tamano)

        if (abs(ancho - destino_ancho) <= TOLERANCIA_PT
                and abs(alto - destino_alto) <= TOLERANCIA_PT):
            escritor.add_page(pagina)
            continue

        # min() en vez de max(): entra entera, no se recorta nada.
        escala = min(destino_ancho / ancho, destino_alto / alto)

        # El mediabox no siempre arranca en (0,0). Hay que restar su origen,
        # ya escalado, o el contenido queda corrido dentro de la hoja nueva.
        tx = -float(caja.left) * escala + (destino_ancho - ancho * escala) / 2
        ty = -float(caja.bottom) * escala + (destino_alto - alto * escala) / 2

        nueva = PageObject.create_blank_page(width=destino_ancho, height=destino_alto)
        nueva.merge_transformed_page(
            pagina, Transformation().scale(escala).translate(tx, ty)
        )
        escritor.add_page(nueva)
        convertidas += 1

    with open(destino, "wb") as f:
        escritor.write(f)

    total = len(lector.pages)
    if convertidas:
        logger.info(
            "Normalizado a %s: %d de %d páginas reescaladas (%s)",
            tamano, convertidas, total, origen,
        )
    return ResultadoNormalizacion(paginas=total, convertidas=convertidas)
