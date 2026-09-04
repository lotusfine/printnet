<#
    PrintNet — baja de los servicios de Windows.
    Lo ejecuta el desinstalador de Inno Setup; también sirve a mano:
      powershell -ExecutionPolicy Bypass -File uninstall-services.ps1
#>

[CmdletBinding()]
param(
    [string]$InstallDir = $PSScriptRoot,
    [string]$NssmPath = "",
    [string[]]$Servicios = @("PrintNetBackend", "PrintNetTunnel")
)

$ErrorActionPreference = "SilentlyContinue"

if (-not $NssmPath) {
    $candidatos = @(
        (Join-Path $InstallDir "nssm.exe"),
        (Join-Path $InstallDir "tools\nssm.exe")
    ) + @(Get-Command nssm.exe -ErrorAction SilentlyContinue | ForEach-Object { $_.Source })
    $NssmPath = $candidatos | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
}

foreach ($svc in $Servicios) {
    if (Get-Service -Name $svc -ErrorAction SilentlyContinue) {
        Write-Host "Quitando $svc..."
        if ($NssmPath -and (Test-Path $NssmPath)) {
            & $NssmPath stop $svc confirm | Out-Null
            Start-Sleep -Seconds 2
            & $NssmPath remove $svc confirm | Out-Null
        } else {
            # Sin NSSM a mano, sc.exe alcanza para dar de baja el servicio
            Stop-Service $svc -Force
            Start-Sleep -Seconds 2
            & sc.exe delete $svc | Out-Null
        }
    }
}

Write-Host "Servicios de PrintNet dados de baja."
Write-Host "NOTA: printnet.db, uploads\ y .env NO se borran (datos y credenciales)." -ForegroundColor Yellow
exit 0
