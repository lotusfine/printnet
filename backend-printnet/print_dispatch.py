"""Interfaz de despacho de impresión.

Fase 1: solo existe SimulatedDispatcher, que registra la intención de
impresión sin tocar hardware. El diseño ya contempla las implementaciones
reales futuras, que se agregan como subclases sin cambiar el resto del
sistema:

  - SumatraDispatcher (Windows): SumatraPDF CLI, ej.
      SumatraPDF.exe -print-to "<printer>" -print-settings "..." archivo.pdf
  - CupsDispatcher (Linux / Raspberry Pi): CUPS vía `lp`, ej.
      lp -d <printer> -n <copias> -o sides=two-sided-long-edge archivo.pdf

El dispatcher activo se elige con la variable de entorno PRINTNET_DISPATCH
(default: "simulated").
"""

import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass

logger = logging.getLogger("printnet.dispatch")


@dataclass
class DispatchResult:
    ok: bool
    detalle: str


class PrintDispatcher(ABC):
    """Contrato único: el resto del sistema solo conoce esta interfaz."""

    nombre: str = "abstract"

    @abstractmethod
    def dispatch(self, printer_nombre: str, file_path: str, options: dict) -> DispatchResult:
        """Envía (o simula enviar) un archivo a imprimir con las opciones dadas."""


class SimulatedDispatcher(PrintDispatcher):
    """Fase 1: registra la intención de impresión, no imprime nada."""

    nombre = "simulated"

    def dispatch(self, printer_nombre: str, file_path: str, options: dict) -> DispatchResult:
        detalle = (
            f"[SIMULADO] Se despacharía '{file_path}' a la impresora "
            f"'{printer_nombre}' con opciones {options}"
        )
        logger.info(detalle)
        return DispatchResult(ok=True, detalle=detalle)


_DISPATCHERS = {
    "simulated": SimulatedDispatcher,
    # "sumatra": SumatraDispatcher,   # futuro, Windows
    # "cups": CupsDispatcher,         # futuro, Linux/Pi
}


def get_dispatcher() -> PrintDispatcher:
    modo = os.environ.get("PRINTNET_DISPATCH", "simulated")
    if modo not in _DISPATCHERS:
        raise ValueError(
            f"Dispatcher '{modo}' no implementado. Disponibles: {sorted(_DISPATCHERS)}"
        )
    return _DISPATCHERS[modo]()


def dispatch_print(printer_nombre: str, file_path: str, options: dict) -> DispatchResult:
    """Atajo funcional sobre el dispatcher configurado."""
    return get_dispatcher().dispatch(printer_nombre, file_path, options)
