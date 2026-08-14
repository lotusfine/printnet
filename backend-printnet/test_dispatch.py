"""Tests del despachador de impresión.

Correr:  .venv/bin/python test_dispatch.py
(sin pytest a propósito, igual que test_pricing.py: el backend corre en la
notebook del local y no queremos dependencias de desarrollo instaladas ahí)

Estos tests NO imprimen nada ni necesitan Windows: verifican que el comando
que se le arma a SumatraPDF sea el correcto, inyectando un ejecutor falso en
lugar de subprocess.run. La prueba contra la Ricoh real es aparte y manual.
"""

import logging
import os
import sys
import tempfile

# Los tests de error hacen que el dispatcher loguee a stderr a propósito.
# Se silencia para que la salida del test se lea limpia.
logging.getLogger("printnet.dispatch").setLevel(logging.CRITICAL)

from pypdf import PdfReader

from generar_pdf_prueba import generar
from print_dispatch import (
    DispatchResult,
    SumatraDispatcher,
    construir_comando,
    get_dispatcher,
)

fallos: list[str] = []


def check(nombre: str, obtenido, esperado):
    if obtenido == esperado:
        print(f"  ok  {nombre}")
    else:
        print(f"  FALLA  {nombre}:\n         esperado {esperado}\n         obtenido {obtenido}")
        fallos.append(nombre)


def opciones(color="byn", caras="simple", copias=1, tamano="A4",
             modo_rango="todas", valor_rango=""):
    """Arma el dict de opciones tal como lo guarda routers/orders.py."""
    return {
        "opciones": {"color": color, "caras": caras, "copias": copias, "tamano": tamano},
        "rango": {"modo": modo_rango, "valor": valor_rango},
        "terminaciones": [],
        "paginas_documento": 10,
        "paginas_a_imprimir": 10,
    }


EXE = r"C:\PrintNet\SumatraPDF.exe"
PDF = r"C:\PrintNet\uploads\pedido-42.pdf"
RICOH = "RICOH IM C4500 PCL 6"


# ─────────────────────────────────────────────
print("\n== Traducción de opciones a -print-settings ==")


def settings(**kw):
    """Extrae el valor de -print-settings del comando armado."""
    cmd = construir_comando(EXE, RICOH, PDF, opciones(**kw))
    return cmd[cmd.index("-print-settings") + 1]


check("byn simple 1 copia A4",
      settings(), "monochrome,simplex,1x,fit")
check("color doble 3 copias A3",
      settings(color="color", caras="doble", copias=3, tamano="A3"),
      "color,duplexlong,3x,fit")
check("color simple",
      settings(color="color"), "color,simplex,1x,fit")
check("byn doble",
      settings(caras="doble"), "monochrome,duplexlong,1x,fit")
check("copias altas (500, el máximo del modelo)",
      settings(copias=500), "monochrome,simplex,500x,fit")

print("\n== Rango de páginas ==")
check("modo 'todas' no agrega token de rango",
      settings(modo_rango="todas"), "monochrome,simplex,1x,fit")
check("rango '3-8' se antepone",
      settings(modo_rango="rango", valor_rango="3-8"),
      "3-8,monochrome,simplex,1x,fit")
check("rango de una sola página",
      settings(modo_rango="rango", valor_rango="7"),
      "7,monochrome,simplex,1x,fit")
check("rango con espacios se normaliza",
      settings(modo_rango="rango", valor_rango="  3-8  "),
      "3-8,monochrome,simplex,1x,fit")

print("\n== Forma del comando completo ==")
cmd = construir_comando(EXE, RICOH, PDF, opciones())
check("el ejecutable va primero", cmd[0], EXE)
check("el PDF va último", cmd[-1], PDF)
check("el nombre de impresora es UN solo argumento (tiene espacios)",
      cmd[cmd.index("-print-to") + 1], RICOH)
check("corre en silencio (sin diálogos que cuelguen el servicio)",
      "-silent" in cmd, True)
check("cierra al terminar (si no, queda un proceso por pedido)",
      "-exit-when-done" in cmd, True)

print("\n== Registro en _DISPATCHERS ==")
os.environ["PRINTNET_DISPATCH"] = "sumatra"
os.environ["PRINTNET_SUMATRA"] = EXE
check("get_dispatcher() devuelve el de Sumatra",
      type(get_dispatcher()).__name__, "SumatraDispatcher")
check("se identifica como 'sumatra' en dispatch_log",
      get_dispatcher().nombre, "sumatra")
del os.environ["PRINTNET_DISPATCH"]


# ─────────────────────────────────────────────
print("\n== Errores: nunca deben tumbar el webhook ==")


class EjecutorFalso:
    """Reemplaza a subprocess.run: registra la llamada y devuelve lo pactado."""

    def __init__(self, returncode=0, stderr="", excepcion=None):
        self.returncode = returncode
        self.stderr = stderr
        self.excepcion = excepcion
        self.comando = None

    def __call__(self, cmd, **kwargs):
        self.comando = cmd
        if self.excepcion:
            raise self.excepcion

        class Resultado:
            pass

        r = Resultado()
        r.returncode = self.returncode
        r.stderr = self.stderr
        return r


# Un PDF válido de verdad: el despachador ahora lo abre para normalizarlo,
# así que un archivo con contenido inventado ya no sirve como fixture.
with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
    f.write(generar(1, "A4"))
    pdf_real = f.name

# Un archivo que sí existe, para hacer de SumatraPDF.exe en las pruebas
exe_real = os.path.abspath(__file__)

ok = EjecutorFalso(returncode=0)
d = SumatraDispatcher(exe_path=exe_real, runner=ok)
r = d.dispatch(RICOH, pdf_real, opciones())
check("éxito → ok=True", r.ok, True)
check("éxito → devuelve DispatchResult", isinstance(r, DispatchResult), True)
check("el detalle nombra la impresora", RICOH in r.detalle, True)

falla = EjecutorFalso(returncode=1, stderr="no se pudo abrir la impresora")
r = SumatraDispatcher(exe_path=exe_real, runner=falla).dispatch(RICOH, pdf_real, opciones())
check("código de salida != 0 → ok=False", r.ok, False)
check("el detalle incluye el stderr", "no se pudo abrir la impresora" in r.detalle, True)

r = SumatraDispatcher(exe_path=r"C:\no\existe\SumatraPDF.exe",
                      runner=EjecutorFalso()).dispatch(RICOH, pdf_real, opciones())
check("SumatraPDF ausente → ok=False, no excepción", r.ok, False)
check("el detalle dice qué falta", "SumatraPDF" in r.detalle, True)

r = SumatraDispatcher(exe_path=exe_real, runner=EjecutorFalso()).dispatch(
    RICOH, r"C:\no\existe\pedido.pdf", opciones())
check("PDF ausente → ok=False, no excepción", r.ok, False)

lento = EjecutorFalso(excepcion=TimeoutError("tardó demasiado"))
r = SumatraDispatcher(exe_path=exe_real, runner=lento).dispatch(RICOH, pdf_real, opciones())
check("timeout → ok=False, no excepción", r.ok, False)

roto = EjecutorFalso(excepcion=OSError("acceso denegado"))
r = SumatraDispatcher(exe_path=exe_real, runner=roto).dispatch(RICOH, pdf_real, opciones())
check("error del sistema operativo → ok=False, no excepción", r.ok, False)

os.unlink(pdf_real)


# ─────────────────────────────────────────────
print("\n== El PDF se normaliza al tamaño pedido antes de imprimir ==")
# SumatraPDF ignora el tamaño de papel que se le pide y usa el del documento
# (verificado contra la Ricoh). Así que el despachador tiene que entregarle un
# PDF que YA esté en el tamaño que el cliente pagó — incluido el caso de un
# cliente que sube un A3 y paga A4.

class EjecutorQueMide(EjecutorFalso):
    """Mide el PDF que recibiría SumatraPDF, para ver si llegó normalizado."""

    def __call__(self, cmd, **kwargs):
        self.ruta_impresa = cmd[-1]
        self.medidas = [
            (round(float(p.mediabox.width)), round(float(p.mediabox.height)))
            for p in PdfReader(self.ruta_impresa).pages
        ]
        return super().__call__(cmd, **kwargs)


def imprimir_midiendo(pdf_origen: str, tamano: str) -> EjecutorQueMide:
    eje = EjecutorQueMide(returncode=0)
    SumatraDispatcher(exe_path=exe_real, runner=eje).dispatch(
        RICOH, pdf_origen, opciones(tamano=tamano)
    )
    return eje


with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
    f.write(generar(3, "A4"))
    pdf_a4 = f.name
with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
    f.write(generar(2, "A3"))
    pdf_a3 = f.name

A4_PT, A3_PT = (595, 842), (842, 1191)

eje = imprimir_midiendo(pdf_a4, "A3")
check("pedido A3 sobre un PDF A4 → se imprime un PDF A3",
      eje.medidas, [A3_PT] * 3)
check("no se manda a imprimir el archivo original",
      eje.ruta_impresa != pdf_a4, True)
check("el temporal se borra después de imprimir",
      os.path.exists(eje.ruta_impresa), False)

eje = imprimir_midiendo(pdf_a3, "A4")
check("pedido A4 sobre un PDF A3 → se imprime un PDF A4 (esto es plata)",
      eje.medidas, [A4_PT] * 2)

eje = imprimir_midiendo(pdf_a4, "A4")
check("pedido A4 sobre un PDF A4 → sigue siendo A4",
      eje.medidas, [A4_PT] * 3)

with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
    f.write(b"esto no es un PDF")
    pdf_roto = f.name

r = SumatraDispatcher(exe_path=exe_real, runner=EjecutorFalso()).dispatch(
    RICOH, pdf_roto, opciones())
check("PDF ilegible → ok=False, no excepción", r.ok, False)
check("el detalle explica que no se pudo preparar", "preparar" in r.detalle.lower(), True)

for t in (pdf_a4, pdf_a3, pdf_roto):
    os.unlink(t)


# ─────────────────────────────────────────────
print()
if fallos:
    print(f"✗ {len(fallos)} fallo(s): {', '.join(fallos)}")
    sys.exit(1)
print("✓ todos los tests de despacho pasaron")
