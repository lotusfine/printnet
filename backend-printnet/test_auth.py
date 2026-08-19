"""Tests de la autenticación del panel de administración.

Correr:  .venv/bin/python test_auth.py
(sin pytest ni TestClient a propósito: TestClient necesita httpx, que no está
en requirements.txt y no queremos instalar en la notebook del local)

QUÉ PROTEGE ESTO: los endpoints /admin/* exponen nombres, teléfonos y emails
de clientes reales, y permiten modificar pedidos. Hasta ahora la única
contraseña era `admin123` validada en el navegador — o sea, ninguna. Con
`api.libreriaglaxara.com.ar` fija y pública, cualquiera que supiera la URL
entraba.

Se falla CERRADO: sin token configurado, /admin/* no responde. Es preferible
un panel que no anda a uno que quedó abierto sin que nadie se diera cuenta.
"""

import logging
import os
import sys

# Los tests de rechazo hacen que auth.py loguee a stderr a propósito.
logging.getLogger("printnet.auth").setLevel(logging.CRITICAL)

from fastapi import HTTPException

from auth import LARGO_MINIMO, VAR_TOKEN, verificar_admin

fallos: list[str] = []

TOKEN_OK = "un-token-largo-y-dificil-de-adivinar"


def check(nombre: str, obtenido, esperado):
    if obtenido == esperado:
        print(f"  ok  {nombre}")
    else:
        print(f"  FALLA  {nombre}: esperado {esperado}, obtenido {obtenido}")
        fallos.append(nombre)


def estado(token_env, header) -> int | str:
    """Corre la verificación y devuelve el código HTTP, o 'pasa' si autorizó."""
    if token_env is None:
        os.environ.pop(VAR_TOKEN, None)
    else:
        os.environ[VAR_TOKEN] = token_env
    try:
        verificar_admin(header)
        return "pasa"
    except HTTPException as e:
        return e.status_code


# ─────────────────────────────────────────────
print("\n== Sin token configurado: el panel no abre (falla cerrado) ==")

check("no hay variable de entorno → 503", estado(None, TOKEN_OK), 503)
check("variable vacía → 503", estado("", TOKEN_OK), 503)
check("variable con solo espacios → 503", estado("     ", TOKEN_OK), 503)

print("\n== Un token corto no es un token ==")

corto = "x" * (LARGO_MINIMO - 1)
check(f"menos de {LARGO_MINIMO} caracteres → 503", estado(corto, corto), 503)
check("'admin123' no alcanza", estado("admin123", "admin123"), 503)
try:
    estado(corto, corto)
except HTTPException:
    pass
try:
    os.environ[VAR_TOKEN] = corto
    verificar_admin(corto)
    check("el mensaje explica que es corto", "no falló", "503")
except HTTPException as e:
    check("el mensaje explica que es corta", "demasiado corta" in e.detail.lower(), True)

print("\n== Con token configurado ==")

check("header correcto → autoriza", estado(TOKEN_OK, TOKEN_OK), "pasa")
check("sin header → 401", estado(TOKEN_OK, None), 401)
check("header vacío → 401", estado(TOKEN_OK, ""), 401)
check("header incorrecto → 401", estado(TOKEN_OK, "otro-token-cualquiera"), 401)
check("un prefijo del token no alcanza", estado(TOKEN_OK, TOKEN_OK[:-1]), 401)
check("el token con basura al final no alcanza",
      estado(TOKEN_OK, TOKEN_OK + "x"), 401)
check("distingue mayúsculas", estado(TOKEN_OK, TOKEN_OK.upper()), 401)
check("tolera espacios alrededor (copiar y pegar)",
      estado(TOKEN_OK, f"  {TOKEN_OK}  "), "pasa")

print("\n== Está cableado a los tres endpoints de /admin ==")

os.environ[VAR_TOKEN] = TOKEN_OK
import main  # noqa: E402


def protegidas(ruta_prefijo: str) -> dict[str, bool]:
    """Por cada ruta con ese prefijo, si verificar_admin está en su cadena.

    Esta versión de FastAPI no aplana los routers incluidos en app.routes: los
    envuelve en _IncludedRouter, y las rutas reales cuelgan de original_router.
    """
    resultado = {}
    for envoltorio in main.app.routes:
        router = getattr(envoltorio, "original_router", None)
        if router is None:
            continue
        for r in router.routes:
            path = getattr(r, "path", "")
            if not path.startswith(ruta_prefijo):
                continue
            calls = [d.call for d in getattr(r.dependant, "dependencies", [])]
            for metodo in sorted((r.methods or set()) - {"HEAD", "OPTIONS"}):
                resultado[f"{metodo} {path}"] = verificar_admin in calls
    return resultado


admin = protegidas("/admin")
check("hay tres endpoints bajo /admin", len(admin), 3)
for nombre, protegida in sorted(admin.items()):
    check(f"protegido: {nombre}", protegida, True)

print("\n== No se rompió lo que tiene que seguir abierto ==")

publicas = protegidas("/orders")
check("los endpoints de pedidos siguen sin token",
      any(publicas.values()), False)
check("hay endpoints de pedidos que verificar", len(publicas) > 0, True)


# ─────────────────────────────────────────────
print()
if fallos:
    print(f"✗ {len(fallos)} fallo(s): {', '.join(fallos)}")
    sys.exit(1)
print("✓ todos los tests de autenticación pasaron")
