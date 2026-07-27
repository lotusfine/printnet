; ============================================================================
;  PrintNet — instalador para la notebook del local (Inno Setup 6)
;
;  Compilar con Inno Setup Compiler (https://jrsoftware.org/isdl.php):
;      abrir este archivo -> Build -> Compile
;      salida: Output\PrintNetSetup.exe
;
;  ANTES de compilar, armá la carpeta payload\ (NO se versiona en git):
;
;      deploy\payload\
;        printnet-backend.exe          <- de dist\ tras correr PyInstaller
;        .env                          <- tus credenciales reales (MP, SMTP...)
;        nssm.exe                      <- de nssm-2.24.zip, carpeta win64\
;        cloudflared\
;          config.yml                  <- ver README.md
;          <UUID-del-tunel>.json       <- credenciales del túnel 'printnet'
;          cert.pem                    <- certificado de origen de Cloudflare
;
;  Ningún valor de credenciales vive en este script: todo se copia desde
;  payload\, que está en .gitignore.
; ============================================================================

#define AppName        "PrintNet"
#define AppVersion     "1.0.0"
#define AppPublisher   "Libreria Glaxara"
#define BackendExe     "printnet-backend.exe"
#define PayloadDir     "payload"

[Setup]
AppId={{7B3A9C41-5E62-4E8D-9F17-PRINTNET0001}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=PrintNetSetup
Compression=lzma2
SolidCompression=yes
; Los servicios se instalan para toda la máquina: requiere elevación.
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible
; No hace falta reiniciar: los servicios arrancan al final de la instalación.
RestartIfNeededByRun=no
WizardStyle=modern
UninstallDisplayName={#AppName}

[Languages]
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"

[Files]
; --- Backend ---------------------------------------------------------------
Source: "{#PayloadDir}\{#BackendExe}"; DestDir: "{app}"; Flags: ignoreversion

; --- Configuración: NO se pisa si ya existe, NO se borra al desinstalar ----
;     (contiene credenciales de MercadoPago y SMTP)
Source: "{#PayloadDir}\.env"; DestDir: "{app}"; \
    Flags: onlyifdoesntexist uninsneveruninstall

; --- NSSM ------------------------------------------------------------------
Source: "{#PayloadDir}\nssm.exe"; DestDir: "{app}"; Flags: ignoreversion

; --- Credenciales y config del túnel de Cloudflare -------------------------
;     Van dentro de {app} porque los servicios corren como LocalSystem y no
;     pueden leer C:\Users\<vos>\.cloudflared\
Source: "{#PayloadDir}\cloudflared\*"; DestDir: "{app}\cloudflared"; \
    Flags: ignoreversion recursesubdirs uninsneveruninstall

; --- Scripts de servicios --------------------------------------------------
Source: "install-services.ps1";   DestDir: "{app}"; Flags: ignoreversion
Source: "uninstall-services.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "README.md";              DestDir: "{app}"; Flags: ignoreversion isreadme

[Dirs]
Name: "{app}\logs"
Name: "{app}\uploads"

[Icons]
Name: "{group}\Ver estado de PrintNet"; Filename: "powershell.exe"; \
    Parameters: "-NoExit -Command ""Get-Service PrintNetBackend,PrintNetTunnel"""
Name: "{group}\Carpeta de logs"; Filename: "{app}\logs"
Name: "{group}\Desinstalar {#AppName}"; Filename: "{uninstallexe}"

[Run]
; Registra y arranca ambos servicios. Ventana visible para ver el resultado.
Filename: "powershell.exe"; \
    Parameters: "-ExecutionPolicy Bypass -NoProfile -File ""{app}\install-services.ps1"" -InstallDir ""{app}"""; \
    StatusMsg: "Registrando los servicios de Windows..."; \
    Flags: waituntilterminated

[UninstallRun]
Filename: "powershell.exe"; \
    Parameters: "-ExecutionPolicy Bypass -NoProfile -File ""{app}\uninstall-services.ps1"" -InstallDir ""{app}"""; \
    Flags: waituntilterminated runhidden

[Code]
{ Detiene los servicios antes de copiar: si el backend está corriendo, el .exe
  queda bloqueado y la actualización falla. }
procedure DetenerServicios();
var
  Code: Integer;
begin
  Exec(ExpandConstant('{sys}\net.exe'), 'stop PrintNetBackend', '',
       SW_HIDE, ewWaitUntilTerminated, Code);
  Exec(ExpandConstant('{sys}\net.exe'), 'stop PrintNetTunnel', '',
       SW_HIDE, ewWaitUntilTerminated, Code);
  Sleep(2000);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  NeedsRestart := False;
  DetenerServicios();
  Result := '';
end;

{ Aviso si falta el .env en payload: se instalaría sin credenciales y el
  backend arrancaría en modo fantasma (sin MercadoPago). }
function InitializeSetup(): Boolean;
begin
  Result := True;
end;
