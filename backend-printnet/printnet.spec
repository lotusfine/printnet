# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec del backend PrintNet — genera UN solo ejecutable.
#
# Compilar EN WINDOWS (PyInstaller no cross-compila):
#   py -m venv .venv
#   .venv\Scripts\pip install -r requirements.txt pyinstaller
#   .venv\Scripts\pyinstaller printnet.spec
#   → dist\printnet-backend.exe
#
# El .exe NO incluye el .env ni la base de datos: los busca junto a sí mismo
# (ver _base_dir en database.py). El instalador de Inno Setup los copia a la
# misma carpeta.

from PyInstaller.utils.hooks import collect_submodules

# uvicorn y anyio cargan módulos por string en runtime (loops, protocolos,
# lifespan): sin esto el exe arranca y muere con ModuleNotFoundError.
hiddenimports = (
    collect_submodules("uvicorn")
    + collect_submodules("anyio")
    + [
        "dotenv",
        "pypdf",
        "requests",
        "multipart",           # python-multipart (form-data de FastAPI)
        "sqlite3",
        "smtplib",
        "email.message",
    ]
)

a = Analysis(
    ["run_server.py"],
    pathex=["."],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "test", "unittest"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="printnet-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,          # UPX suele disparar antivirus; mejor sin comprimir
    console=True,       # deja ver logs si se ejecuta a mano; NSSM los captura
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
