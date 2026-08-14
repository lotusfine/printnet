"""Interfaz de despacho de impresión.

Dos implementaciones:

  - SimulatedDispatcher: registra la intención sin tocar hardware. Es el
    default, y es lo que corre en el Mac de desarrollo.
  - SumatraDispatcher (Windows): imprime de verdad, vía el CLI de SumatraPDF.
    Pensado para la notebook del local con la Ricoh IM C4500.

Queda pendiente CupsDispatcher (Linux / Raspberry Pi, vía `lp`) si algún día
el backend se muda a una Pi.

El dispatcher activo se elige con la variable de entorno PRINTNET_DISPATCH
(default: "simulated").

IMPORTANTE — qué significa "ok" acá: SumatraPDF entrega el trabajo a la cola
de impresión de Windows y devuelve el control enseguida. Un DispatchResult
con ok=True quiere decir "el trabajo se encoló", NO "el papel salió". Si la
impresora se queda sin toner o se traba, el pedido igual figura como
despachado. Para saberlo de verdad habría que consultar la cola de Windows
después; está deliberadamente fuera de alcance por ahora.
"""

import logging
import os
import subprocess
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass

from pdf_normalize import normalizar_pdf

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


# Traducción de nuestras opciones a los tokens de -print-settings.
_COLOR = {"byn": "monochrome", "color": "color"}
_CARAS = {"simple": "simplex", "doble": "duplexlong"}

# "fit" escala el PDF al tamaño de hoja que eligió el cliente. Es a propósito:
# si sube un A4 y pide A3, queremos que llene la hoja A3, no que salga un A4
# chiquito en el medio.
_ESCALADO = "fit"


def construir_comando(exe_path: str, printer_nombre: str, file_path: str,
                      options: dict) -> list[str]:
    """Arma la línea de comandos de SumatraPDF para un pedido.

    `options` es el dict que guarda routers/orders.py:
        {"opciones": {color, caras, copias, tamano}, "rango": {modo, valor}, ...}

    Se devuelve una lista (no un string) para que el nombre de la impresora
    viaje como UN argumento: "RICOH IM C4500 PCL 6" tiene espacios y si se
    concatenara a mano habría que citarlo.

    Las tres opciones de impresión se mandan SIEMPRE explícitas. El driver de
    la Ricoh tiene dúplex activado en sus preferencias por defecto, así que
    omitir un token no significa "como venga" sino "como esté configurado ese
    diálogo" — que no controlamos.
    """
    op = options["opciones"]
    rango = options.get("rango") or {}

    partes = []
    if rango.get("modo") == "rango" and rango.get("valor", "").strip():
        partes.append(rango["valor"].strip())
    # OJO: acá NO va el tamaño de papel. SumatraPDF ignora `paper=` (y `bin=`,
    # y la configuración de la cola): usa el tamaño de página del PDF. El
    # tamaño se resuelve normalizando el documento antes de imprimir, en
    # pdf_normalize.py. Ver SPEC.md.
    partes += [
        _COLOR[op["color"]],
        _CARAS[op["caras"]],
        f"{op['copias']}x",
        _ESCALADO,
    ]

    return [
        exe_path,
        "-print-to", printer_nombre,
        "-print-settings", ",".join(partes),
        "-silent",           # sin diálogos de error: colgarían el servicio
        "-exit-when-done",   # sin esto queda un proceso vivo por pedido
        file_path,
    ]


class SumatraDispatcher(PrintDispatcher):
    """Impresión real en Windows vía el CLI de SumatraPDF."""

    nombre = "sumatra"
    TIMEOUT_SEG = 120

    def __init__(self, exe_path: str | None = None, runner=None):
        self.exe_path = exe_path or os.environ.get(
            "PRINTNET_SUMATRA", r"C:\PrintNet\SumatraPDF.exe"
        )
        # Inyectable para poder testear sin Windows ni impresora.
        self._run = runner or subprocess.run

    def dispatch(self, printer_nombre: str, file_path: str, options: dict) -> DispatchResult:
        if not os.path.isfile(self.exe_path):
            return self._error(
                f"SumatraPDF no encontrado en '{self.exe_path}'. Revisá la "
                f"variable de entorno PRINTNET_SUMATRA."
            )
        if not os.path.isfile(file_path):
            return self._error(f"El archivo a imprimir no existe: '{file_path}'")

        try:
            tamano = options["opciones"]["tamano"]
        except (KeyError, TypeError) as e:
            return self._error(f"Opciones de impresión inválidas ({e}) en {options}")

        # El tamaño de papel no se puede pedir por línea de comandos: hay que
        # entregarle a SumatraPDF un PDF que YA esté en el tamaño correcto.
        # El temporal se borra solo al salir del `with`.
        with tempfile.TemporaryDirectory(prefix="printnet-") as carpeta:
            listo = os.path.join(carpeta, "imprimir.pdf")
            try:
                normalizar_pdf(file_path, listo, tamano)
            except Exception as e:
                return self._error(
                    f"No se pudo preparar '{file_path}' para imprimir en {tamano} "
                    f"({type(e).__name__}: {e})"
                )

            try:
                cmd = construir_comando(self.exe_path, printer_nombre, listo, options)
            except (KeyError, TypeError) as e:
                return self._error(f"Opciones de impresión inválidas ({e}) en {options}")

            # Nada acá adentro puede propagar una excepción: esto corre dentro
            # del webhook de MercadoPago, y si revienta, MP reintenta el pago.
            try:
                proc = self._run(
                    cmd, capture_output=True, text=True, timeout=self.TIMEOUT_SEG
                )
            except Exception as e:
                return self._error(
                    f"Falló la ejecución de SumatraPDF ({type(e).__name__}: {e})"
                )

        if proc.returncode != 0:
            return self._error(
                f"SumatraPDF terminó con código {proc.returncode} al imprimir "
                f"en '{printer_nombre}': {proc.stderr}"
            )

        detalle = (
            f"Encolado '{file_path}' en '{printer_nombre}' "
            f"({tamano}, settings {cmd[cmd.index('-print-settings') + 1]})"
        )
        logger.info(detalle)
        return DispatchResult(ok=True, detalle=detalle)

    def _error(self, detalle: str) -> DispatchResult:
        logger.error(detalle)
        return DispatchResult(ok=False, detalle=detalle)


_DISPATCHERS = {
    "simulated": SimulatedDispatcher,
    "sumatra": SumatraDispatcher,
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
