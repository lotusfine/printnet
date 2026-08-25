"""Tests de la conversión de documentos a PDF.

Correr:  .venv/bin/python test_document_convert.py
(sin pytest a propósito, igual que el resto)

Estos tests NO necesitan LibreOffice instalado: inyectan un ejecutor falso y
verifican el comando que se arma y el manejo de cada error. La prueba contra
LibreOffice real es manual (Fase 0 del plan, ya hecha con .pps y .ppt).

POR QUÉ EXISTE ESTE MÓDULO: la web solo aceptaba PDF. Un cliente que trae un
PowerPoint tenía que convertirlo por su cuenta, y en el mostrador se resolvía a
mano. Ahora el backend lo convierte.
"""

import logging
import os
import sys
import tempfile
from pathlib import Path

logging.getLogger("printnet.convert").setLevel(logging.CRITICAL)

from document_convert import (
    ConversionResult,
    construir_comando,
    convertir_a_pdf,
    necesita_conversion,
)

fallos: list[str] = []


def check(nombre: str, obtenido, esperado):
    if obtenido == esperado:
        print(f"  ok  {nombre}")
    else:
        print(f"  FALLA  {nombre}: esperado {esperado!r}, obtenido {obtenido!r}")
        fallos.append(nombre)


# Un archivo que existe, para hacer de soffice.exe en las pruebas
SOFFICE = os.path.abspath(__file__)


# ─────────────────────────────────────────────
print("\n== Qué hay que convertir y qué no ==")

check("un PDF no se convierte", necesita_conversion("apunte.pdf"), False)
check("un PDF en mayúsculas tampoco", necesita_conversion("APUNTE.PDF"), False)
check("un PowerPoint sí", necesita_conversion("clase.pptx"), True)
check("el PowerPoint viejo también", necesita_conversion("clase.ppt"), True)
check("el formato .pps (presentación) también — lo trajo un cliente real",
      necesita_conversion("clase.pps"), True)
check("Word", necesita_conversion("tesis.docx"), True)
check("Excel", necesita_conversion("planilla.xlsx"), True)
check("OpenOffice", necesita_conversion("apunte.odt"), True)
check("texto plano", necesita_conversion("notas.txt"), True)
check("un formato que no sabemos convertir", necesita_conversion("video.mp4"), False)
check("sin extensión", necesita_conversion("archivo"), False)


print("\n== El comando que se le arma a LibreOffice ==")

# El perfil tiene que ser una ruta absoluta real: se convierte a URL de archivo,
# y eso depende del sistema operativo. Los demás argumentos viajan como texto.
cmd = construir_comando(SOFFICE, r"C:\up\clase.pptx", r"C:\salida", tempfile.mkdtemp())

check("el ejecutable va primero", cmd[0], SOFFICE)
check("corre sin interfaz gráfica", "--headless" in cmd, True)
check("convierte a PDF", "pdf" in cmd[cmd.index("--convert-to") + 1], True)
check("la carpeta de salida es la pedida", cmd[cmd.index("--outdir") + 1], r"C:\salida")
check("el archivo de entrada va último", cmd[-1], r"C:\up\clase.pptx")

# Sin un perfil propio, dos conversiones simultáneas se pisan: LibreOffice no
# admite dos instancias compartiendo la configuración del usuario.
perfil = [a for a in cmd if a.startswith("-env:UserInstallation")]
check("lleva un perfil propio (si no, dos pedidos a la vez se pisan)",
      len(perfil), 1)
check("el perfil se pasa como URL de archivo, que es lo que espera",
      perfil[0].startswith("-env:UserInstallation=file://"), True)

# Sin esto, LibreOffice puede quedarse esperando que alguien cierre un diálogo.
check("no pide interacción", "--norestore" in cmd, True)


print("\n== Conversión exitosa ==")


class EjecutorFalso:
    """Reemplaza a subprocess.run. Opcionalmente crea el PDF de salida."""

    def __init__(self, returncode=0, stderr="", excepcion=None, crear_pdf=None):
        self.returncode = returncode
        self.stderr = stderr
        self.excepcion = excepcion
        # Un LibreOffice que falla no deja PDF: si no, los tests se contaminan
        # entre sí dejando archivos que el siguiente encuentra.
        self.crear_pdf = (returncode == 0) if crear_pdf is None else crear_pdf
        self.comando = None

    def __call__(self, cmd, **kwargs):
        self.comando = cmd
        if self.excepcion:
            raise self.excepcion
        if self.crear_pdf:
            origen = Path(cmd[-1])
            salida = Path(cmd[cmd.index("--outdir") + 1])
            salida.mkdir(parents=True, exist_ok=True)
            (salida / (origen.stem + ".pdf")).write_bytes(b"%PDF-1.4 convertido")

        class R:
            pass

        r = R()
        r.returncode = self.returncode
        r.stderr = self.stderr
        return r


def con_archivo(nombre: str, cuerpo=b"contenido"):
    carpeta = tempfile.mkdtemp()
    ruta = Path(carpeta) / nombre
    ruta.write_bytes(cuerpo)
    return str(ruta), tempfile.mkdtemp()


origen, salida = con_archivo("clase.pptx")
r = convertir_a_pdf(origen, salida, soffice_path=SOFFICE, runner=EjecutorFalso())
check("devuelve ok", r.ok, True)
check("devuelve un ConversionResult", isinstance(r, ConversionResult), True)
check("informa dónde quedó el PDF", Path(r.pdf_path).name, "clase.pdf")
check("y el PDF existe de verdad", os.path.isfile(r.pdf_path), True)

origen, salida = con_archivo("apunte.pdf", b"%PDF-1.4 ya era pdf")
r = convertir_a_pdf(origen, salida, soffice_path=SOFFICE, runner=EjecutorFalso())
check("un PDF pasa derecho, sin convertir", r.pdf_path, origen)
check("y no ejecuta LibreOffice al pedo", r.ok, True)


print("\n== Errores: ninguno puede tumbar el pedido ==")

origen, salida = con_archivo("clase.pptx")

r = convertir_a_pdf(origen, salida, soffice_path=r"C:\no\existe\soffice.exe",
                    runner=EjecutorFalso())
check("LibreOffice ausente → ok=False", r.ok, False)
check("el detalle dice qué falta", "LibreOffice" in r.detalle, True)

r = convertir_a_pdf(r"C:\no\existe\clase.pptx", salida, soffice_path=SOFFICE,
                    runner=EjecutorFalso())
check("archivo inexistente → ok=False", r.ok, False)

r = convertir_a_pdf(origen, salida, soffice_path=SOFFICE,
                    runner=EjecutorFalso(returncode=1, stderr="formato ilegible"))
check("código de salida != 0 → ok=False", r.ok, False)
check("el detalle incluye lo que dijo LibreOffice",
      "formato ilegible" in r.detalle, True)

# Caso real y traicionero: LibreOffice a veces termina con código 0 sin haber
# escrito nada. Si no lo verificamos, daríamos por convertido un archivo que
# no existe y el pedido fallaría más tarde, en la impresión.
r = convertir_a_pdf(origen, salida, soffice_path=SOFFICE,
                    runner=EjecutorFalso(returncode=0, crear_pdf=False),
                    espera_salida_seg=0.3)
check("termina bien pero no generó el PDF → ok=False", r.ok, False)
check("el detalle lo explica", "no generó" in r.detalle, True)

# En Windows, soffice suele lanzar el trabajo en segundo plano y devolver el
# control de inmediato — medido en la notebook: milésimas de segundo. O sea que
# cuando el proceso termina, el PDF puede no existir TODAVÍA. Hay que esperarlo
# un rato antes de darlo por fallado.
import threading  # noqa: E402


class EjecutorQueTarda(EjecutorFalso):
    """Vuelve enseguida y escribe el PDF un momento después, como hace soffice."""

    def __call__(self, cmd, **kwargs):
        self.comando = cmd
        origen_ = Path(cmd[-1])
        destino = Path(cmd[cmd.index("--outdir") + 1]) / (origen_.stem + ".pdf")
        destino.parent.mkdir(parents=True, exist_ok=True)
        threading.Timer(0.4, lambda: destino.write_bytes(b"%PDF-1.4 tarde")).start()

        class R:
            pass

        r = R()
        r.returncode = 0
        r.stderr = ""
        return r


origen3, salida3 = con_archivo("tarde.pptx")
r = convertir_a_pdf(origen3, salida3, soffice_path=SOFFICE,
                    runner=EjecutorQueTarda(), espera_salida_seg=5)
check("si el PDF aparece un momento después, lo espera y no falla", r.ok, True)

r = convertir_a_pdf(origen, salida, soffice_path=SOFFICE,
                    runner=EjecutorFalso(excepcion=TimeoutError("tardó demasiado")))
check("timeout → ok=False, no excepción", r.ok, False)

r = convertir_a_pdf(origen, salida, soffice_path=SOFFICE,
                    runner=EjecutorFalso(excepcion=OSError("acceso denegado")))
check("error del sistema → ok=False, no excepción", r.ok, False)

otro, salida2 = con_archivo("video.mp4")
r = convertir_a_pdf(otro, salida2, soffice_path=SOFFICE, runner=EjecutorFalso())
check("formato que no sabemos convertir → ok=False", r.ok, False)
check("el detalle nombra el formato", "mp4" in r.detalle.lower(), True)


# ─────────────────────────────────────────────
print()
if fallos:
    print(f"✗ {len(fallos)} fallo(s): {', '.join(fallos)}")
    sys.exit(1)
print("✓ todos los tests de conversión pasaron")
