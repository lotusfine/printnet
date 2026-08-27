# Mudanza a la notebook definitiva

> La notebook de desarrollo fue temporal. Esto lleva el sistema a la máquina
> que va a quedar andando en el local.
>
> **La base de datos arranca limpia**: no hay historial que migrar.

## El problema de las rutas

En la notebook de desarrollo, los archivos del túnel viven en
`C:\Users\marcelo\.cloudflared\`. Esa ruta **no existe en la máquina nueva**, y
además está escrita adentro del archivo de configuración del túnel.

La solución es sacar todo del perfil de usuario y ponerlo en **rutas fijas**
bajo `C:\PrintNet\`. Eso además resuelve un problema que íbamos a tener igual:
cuando el backend corra como servicio de Windows, va a hacerlo bajo una cuenta
del sistema que **no puede leer la carpeta de ningún usuario**.

Estructura destino, idéntica en cualquier máquina:

```
C:\PrintNet\
├── SumatraPDF.exe
├── cloudflared\
│   ├── config.yml
│   ├── cert.pem
│   └── b34cbdf0-01d6-47e6-b73d-2c5851b9e37f.json
└── printnet\              (el repositorio)
    └── backend-printnet\
        ├── .env
        └── dist\
            ├── printnet-backend.exe
            └── .env
```

---

## Parte 1 — En la notebook VIEJA: juntar lo que hay que llevar

Son tres archivos y no se pueden regenerar en la máquina nueva.

```powershell
New-Item -ItemType Directory -Force -Path C:\PrintNet\para-mudar
Copy-Item "$env:USERPROFILE\.cloudflared\cert.pem" C:\PrintNet\para-mudar\
Copy-Item "$env:USERPROFILE\.cloudflared\*.json" C:\PrintNet\para-mudar\
Copy-Item C:\PrintNet\printnet\backend-printnet\dist\.env C:\PrintNet\para-mudar\
Get-ChildItem C:\PrintNet\para-mudar -Force | Select-Object Name, Length
```

Tienen que aparecer tres archivos: `cert.pem`, un `.json` con un nombre largo, y
`.env`.

**Pasalos por pendrive.** Adentro van las credenciales de MercadoPago y del
correo: no van por mail ni por WhatsApp.

**Y apagá el túnel de esta máquina** (`Ctrl+C` en su ventana). El túnel no puede
correr en dos máquinas a la vez: Cloudflare reparte el tráfico entre las dos y
la mitad de los pedidos irían a la que no tiene impresora.

---

## Parte 2 — En la notebook NUEVA

### 2.1 Verificar lo que ya tiene

```powershell
Test-Path "C:\Program Files\LibreOffice\program\soffice.exe"
git --version
python --version
```

LibreOffice tiene que dar `True`. Python tiene que ser **3.11** — si es otra
versión, ver la sección de problemas al final.

### 2.2 La impresora

**El nombre tiene que coincidir carácter por carácter.** El sistema se lo pasa a
SumatraPDF, que compara exacto.

```powershell
Get-Printer | Where-Object { $_.Name -like "*RICOH*" } | Format-List Name, PortName
```

Tiene que decir exactamente `RICOH IM C4500 PCL 6`. Si dice otra cosa —Windows a
veces agrega "(Copia 1)"— hay dos caminos: renombrar la impresora en Windows, o
agregar al `.env` la línea `PRINTNET_IMPRESORA=` con el nombre real.

Y tiene que estar en la misma red que la impresora (`192.168.10.128`).

### 2.3 SumatraPDF

Que quede en `C:\PrintNet\SumatraPDF.exe`, con ese nombre exacto. La descarga
viene con la versión en el nombre (`SumatraPDF-3.6.1-64.exe`): hay que
renombrarla, o el día que se actualice deja de funcionar.

```powershell
Test-Path C:\PrintNet\SumatraPDF.exe
```

### 2.4 Clonar y compilar

```powershell
git clone https://github.com/lotusfine/printnet.git C:\PrintNet\printnet
cd C:\PrintNet\printnet\backend-printnet; py -3.11 -m venv .venv; .venv\Scripts\pip install -r requirements.txt pyinstaller
.venv\Scripts\pyinstaller printnet.spec --noconfirm
```

### 2.5 Los archivos del túnel, en ruta fija

```powershell
New-Item -ItemType Directory -Force -Path C:\PrintNet\cloudflared
Copy-Item <pendrive>\cert.pem C:\PrintNet\cloudflared\
Copy-Item <pendrive>\*.json C:\PrintNet\cloudflared\
```

Y el `config.yml`, con las rutas nuevas:

```powershell
@"
tunnel: b34cbdf0-01d6-47e6-b73d-2c5851b9e37f
credentials-file: C:\PrintNet\cloudflared\b34cbdf0-01d6-47e6-b73d-2c5851b9e37f.json

ingress:
  - hostname: api.libreriaglaxara.com.ar
    service: http://127.0.0.1:8000
  - service: http_status:404
"@ | Set-Content -Encoding ascii C:\PrintNet\cloudflared\config.yml
```

### 2.6 El `.env`

```powershell
Copy-Item <pendrive>\.env C:\PrintNet\printnet\backend-printnet\dist\.env
Copy-Item <pendrive>\.env C:\PrintNet\printnet\backend-printnet\.env
```

Verificar que estén todas las claves:

```powershell
Get-Content C:\PrintNet\printnet\backend-printnet\dist\.env | Where-Object { $_ -match '^#?[A-Z_]+=' } | ForEach-Object { $_.Split('=')[0] }
```

Tienen que estar: `MP_ACCESS_TOKEN`, `MP_WEBHOOK_SECRET`, `BASE_URL_PUBLICA`,
`PRINTNET_FRONTEND_URL`, `PRINTNET_CORS_ORIGINS`, `PRINTNET_DISPATCH`,
`PRINTNET_SUMATRA`, `PRINTNET_ADMIN_TOKEN` y las cinco de `PRINTNET_SMTP_*`.

---

## Parte 3 — Levantar y verificar

**Ventana 1:**

```powershell
cd C:\PrintNet\printnet\backend-printnet\dist; .\printnet-backend.exe
```

**Ventana 2** (ojo: `--config`, porque los archivos ya no están donde
`cloudflared` los busca por defecto):

```powershell
cloudflared --config C:\PrintNet\cloudflared\config.yml tunnel run printnet
```

**Ventana 3 — las pruebas**, en orden. Cada una verifica algo que las
anteriores no:

```powershell
cd C:\PrintNet\printnet\backend-printnet
.venv\Scripts\python prueba_impresion.py C:\PrintNet\prueba.pdf --simular
.venv\Scripts\python prueba_impresion.py C:\PrintNet\prueba.pdf
```

1. La impresora responde al nombre configurado.
2. Un pedido completo con varios documentos, formatos mezclados y correo real.
3. Que el mail llegue **y no caiga en spam**.
4. Desde afuera: que `api.libreriaglaxara.com.ar` responda y que `/admin/*`
   siga devolviendo 401 sin token.

---

## Si algo falla

| Síntoma | Causa habitual |
|---|---|
| El túnel no levanta | Falta `--config`, o el `.json` no está donde dice `config.yml` |
| Los pedidos dicen "imprimiendo" pero no sale papel | El nombre de la impresora no coincide, o `PRINTNET_DISPATCH` no es `sumatra` |
| Los Word y PowerPoint se rechazan | LibreOffice no está en la ruta por defecto → agregar `PRINTNET_SOFFICE` al `.env` |
| El panel de operador responde 503 | Falta `PRINTNET_ADMIN_TOKEN` en el `.env` de `dist` |
| El cliente paga y el pedido no se imprime | `BASE_URL_PUBLICA` apunta a otro lado, o el webhook de MercadoPago quedó apuntando al túnel viejo |
| No llegan los mails | Puerto distinto de 465, o la contraseña de `fotocopias@` cambió |
| PyInstaller falla | Python no es 3.11 → instalar 3.11 y rehacer el `.venv` |

**Después de tocar el `.env` hay que reiniciar**: se lee una sola vez, al
arrancar.

---

## Lo que queda pendiente después de la mudanza

Instalar el backend y el túnel como **servicios de Windows**, para que arranquen
solos y no dependan de dos ventanas abiertas. Ver `README.md` en esta misma
carpeta.

Las rutas fijas de esta guía ya dejan todo preparado para eso: el instalador
espera encontrar los archivos exactamente donde quedaron.
