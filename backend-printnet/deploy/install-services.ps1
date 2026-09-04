<#
    PrintNet — registro de servicios de Windows con NSSM.

    Registra dos servicios con arranque automático y reinicio ante caída:
      PrintNetBackend : el .exe de FastAPI (uvicorn embebido)
      PrintNetTunnel  : cloudflared corriendo el túnel nombrado 'printnet'

    Lo ejecuta automáticamente el instalador de Inno Setup al finalizar, pero
    también se puede correr a mano desde una PowerShell COMO ADMINISTRADOR:

      powershell -ExecutionPolicy Bypass -File install-services.ps1

    Requiere: NSSM (https://nssm.cc/release/nssm-2.24.zip → win64\nssm.exe)
              cloudflared instalado y el túnel 'printnet' ya creado.

    OJO, dos cosas del archivo en sí (no del código):
      - NO usar here-strings (arroba-comilla). Windows PowerShell 5.1 no los
        reconoce si el archivo tiene finales de línea de Unix, y en vez de
        fallar con un mensaje claro empieza a interpretar el texto del
        mensaje como código. Para varias líneas, varios Write-Host.
      - El archivo va en UTF-8 CON BOM y con finales CRLF (ver
        .gitattributes en la raíz). Sin BOM, PowerShell 5.1 lo lee como
        ANSI y los acentos salen rotos: "túnel" imprime "tÃºnel".
#>

[CmdletBinding()]
param(
    # Carpeta donde quedó instalado todo (por defecto, la de este script)
    [string]$InstallDir = $PSScriptRoot,
    # Ruta a nssm.exe. Si no se pasa, se busca en la carpeta de instalación y en el PATH.
    [string]$NssmPath = "",
    # Ruta a cloudflared.exe. Si no se pasa, se busca en el PATH y en Program Files.
    [string]$CloudflaredPath = "",
    [string]$TunnelName = "printnet",
    [string]$BackendService = "PrintNetBackend",
    [string]$TunnelService = "PrintNetTunnel"
)

$ErrorActionPreference = "Stop"

function Write-Paso($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "    OK: $msg" -ForegroundColor Green }
function Write-Falla($msg){ Write-Host "    ERROR: $msg" -ForegroundColor Red }

# --- 0. Verificaciones previas -------------------------------------------------
$esAdmin = ([Security.Principal.WindowsPrincipal] `
    [Security.Principal.WindowsIdentity]::GetCurrent()
    ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $esAdmin) {
    Write-Falla "Este script necesita permisos de Administrador."
    exit 1
}

Write-Paso "Ubicando herramientas"

if (-not $NssmPath) {
    $candidatos = @(
        (Join-Path $InstallDir "nssm.exe"),
        (Join-Path $InstallDir "tools\nssm.exe")
    ) + @(Get-Command nssm.exe -ErrorAction SilentlyContinue | ForEach-Object { $_.Source })
    $NssmPath = $candidatos | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
}
if (-not $NssmPath -or -not (Test-Path $NssmPath)) {
    Write-Falla "No encontré nssm.exe."
    Write-Host "    Descargalo de https://nssm.cc/release/nssm-2.24.zip, sacá win64\nssm.exe"
    Write-Host "    y copialo junto a este script, o volvé a ejecutar con:"
    Write-Host '        -NssmPath "C:\ruta\a\nssm.exe"'
    exit 1
}
Write-Ok "NSSM: $NssmPath"

if (-not $CloudflaredPath) {
    $candidatos = @(Get-Command cloudflared.exe -ErrorAction SilentlyContinue |
                    ForEach-Object { $_.Source }) + @(
        "$env:ProgramFiles\cloudflared\cloudflared.exe",
        "${env:ProgramFiles(x86)}\cloudflared\cloudflared.exe",
        "$env:LOCALAPPDATA\Microsoft\WinGet\Links\cloudflared.exe"
    )
    $CloudflaredPath = $candidatos | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
}
if (-not $CloudflaredPath -or -not (Test-Path $CloudflaredPath)) {
    Write-Falla "No encontré cloudflared.exe. Pasá la ruta con -CloudflaredPath."
    exit 1
}
Write-Ok "cloudflared: $CloudflaredPath"

$BackendExe = Join-Path $InstallDir "printnet-backend.exe"
if (-not (Test-Path $BackendExe)) {
    Write-Falla "No encontré $BackendExe"
    exit 1
}
Write-Ok "Backend: $BackendExe"

if (-not (Test-Path (Join-Path $InstallDir ".env"))) {
    Write-Host "    AVISO: no hay .env en $InstallDir — el backend va a arrancar" -ForegroundColor Yellow
    Write-Host "    en modo fantasma (sin MercadoPago) hasta que lo completes." -ForegroundColor Yellow
}

# --- 1. Config del túnel accesible para LocalSystem -----------------------------
# Los servicios corren como LocalSystem: su %USERPROFILE% es
# C:\Windows\System32\config\systemprofile, NO tu carpeta de usuario. Por eso
# cloudflared no encontraría ~\.cloudflared\ y hay que pasarle --config con
# rutas absolutas a los archivos que el instalador copió acá.
$TunnelConfig = Join-Path $InstallDir "cloudflared\config.yml"
if (-not (Test-Path $TunnelConfig)) {
    Write-Falla "Falta $TunnelConfig"
    Write-Host "    El instalador debe copiar a $InstallDir\cloudflared\:"
    Write-Host "      - config.yml            (con tunnel, credentials-file e ingress)"
    Write-Host "      - <UUID-del-tunel>.json (credenciales del túnel)"
    Write-Host "      - cert.pem              (certificado de origen)"
    Write-Host "    Ver README.md para el contenido esperado de config.yml."
    exit 1
}
Write-Ok "Config del túnel: $TunnelConfig"

$LogDir = Join-Path $InstallDir "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

# --- 2. Helpers ---------------------------------------------------------------
function Remove-ServicioSiExiste($nombre) {
    if (Get-Service -Name $nombre -ErrorAction SilentlyContinue) {
        Write-Host "    (servicio $nombre ya existía: lo reinstalo)"
        & $NssmPath stop $nombre confirm | Out-Null
        Start-Sleep -Seconds 2
        & $NssmPath remove $nombre confirm | Out-Null
        Start-Sleep -Seconds 2
    }
}

function Set-ReinicioAutomatico($nombre) {
    # Reiniciar siempre que el proceso termine, esperando 5s entre intentos,
    # sin límite de reintentos (throttle 0 = no marcar como "fallo rápido").
    & $NssmPath set $nombre AppExit Default Restart      | Out-Null
    & $NssmPath set $nombre AppRestartDelay 5000         | Out-Null
    & $NssmPath set $nombre AppThrottle 5000             | Out-Null
    & $NssmPath set $nombre Start SERVICE_AUTO_START     | Out-Null
    # Que Windows también lo reinicie si el servicio falla (además de NSSM)
    & sc.exe failure $nombre reset= 86400 actions= restart/5000/restart/5000/restart/5000 | Out-Null
}

function Set-Logs($nombre, $archivo) {
    & $NssmPath set $nombre AppStdout $archivo            | Out-Null
    & $NssmPath set $nombre AppStderr $archivo            | Out-Null
    & $NssmPath set $nombre AppRotateFiles 1              | Out-Null
    & $NssmPath set $nombre AppRotateOnline 1             | Out-Null
    & $NssmPath set $nombre AppRotateBytes 10485760       | Out-Null  # 10 MB
}

# --- 3. Servicio del backend --------------------------------------------------
Write-Paso "Instalando servicio $BackendService"
Remove-ServicioSiExiste $BackendService

& $NssmPath install $BackendService $BackendExe | Out-Null
# AppDirectory es CRÍTICO: el exe resuelve .env, printnet.db y uploads\
# relativos a su carpeta de trabajo.
& $NssmPath set $BackendService AppDirectory $InstallDir | Out-Null
& $NssmPath set $BackendService DisplayName "PrintNet Backend" | Out-Null
& $NssmPath set $BackendService Description "API de PrintNet (FastAPI) para Libreria Glaxara" | Out-Null
Set-ReinicioAutomatico $BackendService
Set-Logs $BackendService (Join-Path $LogDir "backend.log")
Write-Ok "$BackendService registrado"

# --- 4. Servicio del túnel ----------------------------------------------------
Write-Paso "Instalando servicio $TunnelService"
Remove-ServicioSiExiste $TunnelService

& $NssmPath install $TunnelService $CloudflaredPath | Out-Null
& $NssmPath set $TunnelService AppParameters `
    "--no-autoupdate --config `"$TunnelConfig`" tunnel run $TunnelName" | Out-Null
& $NssmPath set $TunnelService AppDirectory $InstallDir | Out-Null
& $NssmPath set $TunnelService DisplayName "PrintNet Cloudflare Tunnel" | Out-Null
& $NssmPath set $TunnelService Description "Tunel de Cloudflare que publica el backend de PrintNet" | Out-Null
# TUNNEL_ORIGIN_CERT: cloudflared busca cert.pem en el home del usuario, que
# para LocalSystem no es el tuyo. Se lo indicamos explícitamente.
& $NssmPath set $TunnelService AppEnvironmentExtra `
    "TUNNEL_ORIGIN_CERT=$(Join-Path $InstallDir 'cloudflared\cert.pem')" | Out-Null
Set-ReinicioAutomatico $TunnelService
Set-Logs $TunnelService (Join-Path $LogDir "tunnel.log")
Write-Ok "$TunnelService registrado"

# --- 5. Arranque y verificación -----------------------------------------------
Write-Paso "Arrancando servicios"
Start-Service $BackendService -ErrorAction SilentlyContinue
Start-Service $TunnelService  -ErrorAction SilentlyContinue
Start-Sleep -Seconds 6

$fallo = $false
foreach ($svc in @($BackendService, $TunnelService)) {
    $s = Get-Service -Name $svc -ErrorAction SilentlyContinue
    if ($s -and $s.Status -eq "Running") {
        Write-Ok "$svc está corriendo"
    } else {
        $estado = if ($s) { $s.Status } else { "no instalado" }
        Write-Falla "$svc NO está corriendo (estado: $estado). Revisá $LogDir"
        $fallo = $true
    }
}

# Verificación real: que el backend responda HTTP, no solo que el proceso viva
Write-Paso "Verificando que el backend responda"
$puerto = 8000
$envFile = Join-Path $InstallDir ".env"
if (Test-Path $envFile) {
    $linea = Select-String -Path $envFile -Pattern '^\s*PRINTNET_PORT\s*=\s*(\d+)' -ErrorAction SilentlyContinue
    if ($linea) { $puerto = [int]$linea.Matches[0].Groups[1].Value }
}
$respondio = $false
foreach ($i in 1..10) {
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:$puerto/" -UseBasicParsing -TimeoutSec 3
        if ($r.StatusCode -eq 200) { $respondio = $true; break }
    } catch { Start-Sleep -Seconds 2 }
}
if ($respondio) {
    Write-Ok "El backend responde en http://127.0.0.1:$puerto/"
} else {
    Write-Falla "El backend no respondió en el puerto $puerto. Revisá $LogDir\backend.log"
    $fallo = $true
}

Write-Host ""
if ($fallo) {
    Write-Host "Instalacion INCOMPLETA — revisá los errores de arriba." -ForegroundColor Red
    exit 1
}
Write-Host "Listo: PrintNet quedó corriendo y va a arrancar solo con Windows." -ForegroundColor Green
Write-Host "Logs en: $LogDir" -ForegroundColor Gray
exit 0
