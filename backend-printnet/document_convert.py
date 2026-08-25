"""Conversión de documentos a PDF con LibreOffice.

La web solo aceptaba PDF: un cliente con un PowerPoint tenía que convertirlo
por su cuenta, o resolverlo en el mostrador. Este módulo convierte cualquier
documento de oficina antes de cotizarlo e imprimirlo.

Se eligió LibreOffice sobre PDF24 Creator porque tiene una línea de comandos
documentada y corre sin escritorio — el backend va a ser un servicio de
Windows, sin sesión de usuario. Ver `docs/plan-conversion-de-formatos.md`.

Mismo patrón que `print_dispatch.py`: el ejecutor es inyectable, así los tests
corren sin LibreOffice instalado, y ningún camino de error propaga excepciones
— esto se ejecuta al crear un pedido y no puede tumbarlo.
"""

import logging
import os
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("printnet.convert")

# Formatos que LibreOffice convierte bien. `.pps` está porque lo trajo un
# cliente real: es PowerPoint viejo, de los que abren en modo presentación.
FORMATOS_CONVERTIBLES = {
    ".doc", ".docx", ".odt", ".rtf", ".txt",
    ".xls", ".xlsx", ".ods", ".csv",
    ".ppt", ".pptx", ".pps", ".ppsx", ".odp",
}

TIMEOUT_SEG = 120

# Cuánto esperar el PDF DESPUÉS de que el proceso termina. En Windows, soffice
# lanza el trabajo en segundo plano y devuelve el control casi de inmediato
# (medido en la notebook: milésimas de segundo), así que cuando volvemos el
# archivo puede no existir todavía.
ESPERA_SALIDA_SEG = 15


@dataclass
class ConversionResult:
    ok: bool
    pdf_path: str | None
    detalle: str


def necesita_conversion(nombre: str) -> bool:
    """¿Este archivo hay que convertirlo? Un PDF ya sirve tal cual."""
    return Path(nombre).suffix.lower() in FORMATOS_CONVERTIBLES


def _es_pdf(nombre: str) -> bool:
    return Path(nombre).suffix.lower() == ".pdf"


def construir_comando(soffice_path: str, origen: str, carpeta_salida: str,
                      perfil: str) -> list[str]:
    """Línea de comandos de LibreOffice para convertir un archivo a PDF.

    El perfil propio no es opcional: LibreOffice no admite dos instancias
    compartiendo la configuración del usuario, así que sin esto dos pedidos
    simultáneos se pisarían y uno de los dos fallaría.
    """
    return [
        soffice_path,
        f"-env:UserInstallation={Path(perfil).as_uri()}",
        "--headless",     # sin interfaz gráfica
        "--norestore",    # no ofrecer recuperar documentos de una caída previa
        "--convert-to", "pdf",
        "--outdir", carpeta_salida,
        origen,
    ]


def _soffice_por_defecto() -> str:
    return os.environ.get(
        "PRINTNET_SOFFICE", r"C:\Program Files\LibreOffice\program\soffice.exe"
    )


def _esperar_archivo(destino: Path, segundos: float) -> bool:
    """Espera a que aparezca el PDF, revisando cada poco."""
    limite = time.monotonic() + segundos
    while time.monotonic() < limite:
        if destino.is_file() and destino.stat().st_size > 0:
            return True
        time.sleep(0.1)
    return destino.is_file() and destino.stat().st_size > 0


def convertir_a_pdf(origen: str, carpeta_salida: str, soffice_path: str | None = None,
                    runner=None, espera_salida_seg: float = ESPERA_SALIDA_SEG
                    ) -> ConversionResult:
    """Convierte `origen` a PDF dentro de `carpeta_salida`.

    Un PDF se devuelve tal cual, sin ejecutar nada.
    """
    if _es_pdf(origen):
        if not os.path.isfile(origen):
            return _error(f"El archivo no existe: '{origen}'")
        return ConversionResult(ok=True, pdf_path=origen, detalle="ya era PDF")

    extension = Path(origen).suffix.lower() or "(sin extensión)"
    if not necesita_conversion(origen):
        return _error(
            f"No sabemos convertir archivos {extension}. "
            f"Formatos aceptados: PDF, Word, Excel, PowerPoint y OpenOffice."
        )

    if not os.path.isfile(origen):
        return _error(f"El archivo no existe: '{origen}'")

    soffice = soffice_path or _soffice_por_defecto()
    if not os.path.isfile(soffice):
        return _error(
            f"LibreOffice no encontrado en '{soffice}'. "
            f"Revisá la variable de entorno PRINTNET_SOFFICE."
        )

    destino = Path(carpeta_salida) / (Path(origen).stem + ".pdf")
    Path(carpeta_salida).mkdir(parents=True, exist_ok=True)

    # El perfil se borra solo al salir del `with`.
    with tempfile.TemporaryDirectory(prefix="printnet-lo-") as perfil:
        cmd = construir_comando(soffice, origen, carpeta_salida, perfil)
        try:
            proc = (runner or subprocess.run)(
                cmd, capture_output=True, text=True, timeout=TIMEOUT_SEG
            )
        except Exception as e:  # noqa: BLE001 — no puede tumbar el pedido
            return _error(f"Falló la ejecución de LibreOffice "
                          f"({type(e).__name__}: {e})")

        if proc.returncode != 0:
            return _error(
                f"LibreOffice terminó con código {proc.returncode} al convertir "
                f"'{Path(origen).name}': {proc.stderr}"
            )

        if not _esperar_archivo(destino, espera_salida_seg):
            return _error(
                f"LibreOffice terminó sin errores pero no generó el PDF de "
                f"'{Path(origen).name}'."
            )

    detalle = f"Convertido '{Path(origen).name}' a PDF"
    logger.info(detalle)
    return ConversionResult(ok=True, pdf_path=str(destino), detalle=detalle)


def _error(detalle: str) -> ConversionResult:
    logger.error(detalle)
    return ConversionResult(ok=False, pdf_path=None, detalle=detalle)
