# PrintNet — instalación permanente en la notebook (Windows)

Deja el backend y el túnel de Cloudflare corriendo **como servicios de Windows**:
arrancan solos al prender la máquina, se reinician si se caen, y no necesitás
abrir ninguna terminal.

```
www.libreriaglaxara.com.ar (cPanel)
      │
      ▼
Cloudflare  ──túnel 'printnet'──►  notebook
   api.libreriaglaxara.com.ar        ├── servicio PrintNetTunnel  (cloudflared)
                                     └── servicio PrintNetBackend (FastAPI + SQLite)
```

---

## Parte 0 — Crear el túnel nombrado `printnet` — ✅ YA ESTÁ HECHO

> **Estado al 2026-08-19: esta parte entera está cumplida.** El túnel `printnet`
> existe, `api.libreriaglaxara.com.ar` responde desde internet, y el `.env` de
> la notebook ya apunta ahí. **Saltá directo a la Parte 1.**
>
> Datos del túnel ya creado:
>
> | Dato | Valor |
> |---|---|
> | Nombre | `printnet` |
> | UUID | `b34cbdf0-01d6-47e6-b73d-2c5851b9e37f` |
> | Credenciales | `C:\Users\marcelo\.cloudflared\b34cbdf0-...json` |
> | `cert.pem` | `C:\Users\marcelo\.cloudflared\cert.pem` |
> | Hostname | `api.libreriaglaxara.com.ar` |
>
> Lo que sigue queda como referencia por si alguna vez hay que rehacerlo.

Hay dos tipos de túnel y la diferencia importa mucho acá:

| | Túnel rápido (`--url`) | Túnel nombrado (`tunnel run`) |
|---|---|---|
| URL | `algo-random.trycloudflare.com` | tu dominio, fijo |
| Al reiniciar | **cambia la URL** | sigue igual |
| Necesita dominio | no | **sí** |
| Sirve para el local | no (habría que reconfigurar Vercel y el webhook de MP cada vez) | sí |

Para producción hace falta el **nombrado**, y eso exige un dominio propio
administrado por Cloudflare.

### 0.1 Dominio en Cloudflare

1. Comprar un dominio (Cloudflare Registrar, NIC.ar, Namecheap, el que sea).
2. Crear cuenta gratis en <https://dash.cloudflare.com> → **Add a site** →
   escribir el dominio → plan **Free**.
3. Cloudflare te da dos nameservers; cargalos en el panel de donde compraste el
   dominio, reemplazando los que tenga. La propagación tarda de minutos a
   ~24 hs; el panel avisa cuando el dominio queda **Active**.

### 0.2 Crear el túnel (en la notebook, PowerShell)

```powershell
# 1. Autenticar cloudflared con tu cuenta (abre el navegador; elegí el dominio)
cloudflared tunnel login
#    -> genera C:\Users\<vos>\.cloudflared\cert.pem

# 2. Crear el túnel
cloudflared tunnel create printnet
#    -> genera C:\Users\<vos>\.cloudflared\<UUID>.json  (anotá el UUID)

# 3. Apuntar un subdominio al túnel (elegí el que quieras)
cloudflared tunnel route dns printnet api.tudominio.com

# 4. Confirmar
cloudflared tunnel list
```

### 0.3 Probarlo a mano antes de instalar nada

Creá `C:\Users\<vos>\.cloudflared\config.yml`:

```yaml
tunnel: printnet
credentials-file: C:\Users\<vos>\.cloudflared\<UUID>.json

ingress:
  - hostname: api.tudominio.com
    service: http://127.0.0.1:8000
  - service: http_status:404
```

Con el backend corriendo en el puerto 8000, en otra terminal:

```powershell
cloudflared tunnel run printnet
```

Abrí `https://api.tudominio.com/docs`. Si carga, el túnel está listo y ya podés
seguir con la Parte 1. Cortá con `Ctrl+C` (el instalador lo va a dejar como
servicio).

### 0.4 Actualizar lo que apuntaba al túnel viejo

Al pasar del túnel rápido al nombrado cambia la URL pública, así que hay que
actualizar **tres lugares** (esta es la última vez: el dominio ya no cambia más):

1. **`.env`** → `BASE_URL_PUBLICA=https://api.tudominio.com`
2. **`public_html/config.js`** en cPanel → `PRINTNET_API: "https://api.tudominio.com"`.
   Se edita en el servidor y el cambio es inmediato, sin recompilar. (Antes el
   sitio estaba en Vercel y esto era una variable de build; ya no.)
3. **MercadoPago** → panel de la aplicación → Webhooks → URL
   `https://api.tudominio.com/webhooks/mercadopago`. Si MP regenera la firma
   secreta, actualizá también `MP_WEBHOOK_SECRET` en el `.env`.

---

## Parte 1 — Compilar el .exe (una sola vez, EN WINDOWS)

PyInstaller **no cross-compila**: el `.exe` hay que generarlo en la notebook
Windows, no en otra máquina.

```bat
cd C:\ruta\al\repo\backend-printnet
py -m venv .venv
.venv\Scripts\pip install -r requirements.txt pyinstaller
.venv\Scripts\pyinstaller printnet.spec
```

Queda `dist\printnet-backend.exe` (~20 MB, incluye Python y todas las
dependencias). Probalo suelto antes de seguir:

```bat
copy .env dist\
cd dist
printnet-backend.exe
```

Tiene que decir `Uvicorn running on http://127.0.0.1:8000`. Abrí
<http://127.0.0.1:8000/docs> para confirmar. Cortá con `Ctrl+C`.

> **Dónde guarda los datos**: el `.exe` busca `.env` y crea `printnet.db` y
> `uploads\` **en su propia carpeta**. Al instalarlo quedan en
> `C:\Program Files\PrintNet\`. No muevas el `.exe` sin llevarte la base.

### Antivirus

Windows Defender a veces marca ejecutables nuevos de PyInstaller como
sospechosos (falso positivo). Si pasa: Seguridad de Windows → Protección
antivirus → Administrar la configuración → Exclusiones → agregar la carpeta
`C:\Program Files\PrintNet`.

---

## Parte 2 — Armar la carpeta `payload\`

El instalador toma los archivos de `deploy\payload\`, que **no se versiona**
(tiene credenciales). Creala así:

```
deploy\payload\
  printnet-backend.exe        <- de dist\
  .env                        <- credenciales reales (ver abajo)
  nssm.exe                    <- de nssm-2.24.zip, carpeta win64\
  cloudflared\
    config.yml                <- ver plantilla abajo
    <UUID-del-tunel>.json     <- credenciales del túnel
    cert.pem                  <- certificado de origen
```

**NSSM**: descargar <https://nssm.cc/release/nssm-2.24.zip>, descomprimir y
copiar `win64\nssm.exe`.

**Archivos del túnel**: están en `C:\Users\<tu-usuario>\.cloudflared\`. Ahí vas
a encontrar `cert.pem` y un `<UUID>.json` (el UUID es el del túnel `printnet`;
lo confirmás con `cloudflared tunnel list`). Copiá **los dos**.

> **Por qué se copian y no se leen de tu carpeta de usuario**: los servicios de
> Windows corren como `LocalSystem`, cuyo perfil es
> `C:\Windows\System32\config\systemprofile`, no el tuyo. Si el servicio buscara
> `~\.cloudflared\` no encontraría nada y el túnel no levantaría. Por eso el
> instalador copia todo a `C:\Program Files\PrintNet\cloudflared\` y le pasa
> `--config` con rutas absolutas.

### `config.yml` del túnel

```yaml
tunnel: printnet
credentials-file: C:\Program Files\PrintNet\cloudflared\<UUID-del-tunel>.json

ingress:
  - hostname: <tu-subdominio>.<tu-dominio>.com
    service: http://127.0.0.1:8000
  - service: http_status:404
```

Reemplazá `<UUID-del-tunel>` y `<tu-subdominio>`. El `hostname` es el mismo que
figura en `BASE_URL_PUBLICA` del `.env` y en la URL del webhook de MercadoPago.

### `.env`

**No lo armes de cero: copiá el que ya funciona**, el de
`C:\PrintNet\printnet\backend-printnet\.env`. Está completo y probado en
producción, así que copiarlo evita olvidarse una variable.

Si aun así hay que rehacerlo, estas son las que no pueden faltar:

```
MP_ACCESS_TOKEN=...            credenciales de PRODUCCIÓN
MP_WEBHOOK_SECRET=...          firma secreta del webhook de ESA app
BASE_URL_PUBLICA=https://api.libreriaglaxara.com.ar
PRINTNET_FRONTEND_URL=https://www.libreriaglaxara.com.ar
PRINTNET_ADMIN_TOKEN=...       SIN ESTO EL PANEL DE ADMIN NO ABRE (503)
PRINTNET_DISPATCH=sumatra      sin esto NO IMPRIME (queda en modo simulado)
PRINTNET_SUMATRA=C:\PrintNet\SumatraPDF.exe
PRINTNET_CORS_ORIGINS=https://libreriaglaxara.com.ar,https://www.libreriaglaxara.com.ar
PRINTNET_SMTP_HOST=...         vacío = los mails se simulan y loguean
```

Las tres marcadas son las que se olvidan y fallan en silencio o con un error
que no dice cuál es la causa.

**Ojo con SumatraPDF:** el `.exe` del backend se instala en
`C:\Program Files\PrintNet\`, pero `PRINTNET_SUMATRA` sigue apuntando a
`C:\PrintNet\SumatraPDF.exe`. Esa carpeta tiene que seguir existiendo, y la
cuenta del servicio necesita permiso de **escritura** ahí, porque SumatraPDF
guarda su configuración al lado del ejecutable.

Con un túnel **nombrado** el dominio es fijo: ya no hay que actualizar la URL
cada vez que reinicia, como pasaba con los túneles rápidos.

---

## Parte 3 — Compilar y correr el instalador

1. Instalar Inno Setup 6: <https://jrsoftware.org/isdl.php>
2. Abrir `printnet-installer.iss` → **Build → Compile** → sale
   `Output\PrintNetSetup.exe`
3. Ejecutar `PrintNetSetup.exe` **como Administrador**

El instalador copia todo a `C:\Program Files\PrintNet\`, registra los dos
servicios, los arranca y verifica que el backend responda por HTTP.

**No hace falta reiniciar Windows**: los servicios quedan corriendo al terminar.

### Verificar a mano

```powershell
Get-Service PrintNetBackend, PrintNetTunnel     # ambos: Running
Invoke-WebRequest http://127.0.0.1:8000/        # 200
```

Y desde afuera: abrir `https://<tu-subdominio>.<tu-dominio>.com/docs`.

### Si algo falla

Los logs están en `C:\Program Files\PrintNet\logs\` (`backend.log` y
`tunnel.log`, rotan cada 10 MB).

| Síntoma | Causa habitual |
|---|---|
| `PrintNetBackend` no arranca | Falta el `.env` o el puerto 8000 ocupado → `backend.log` |
| `PrintNetTunnel` reinicia en loop | Ruta mal en `config.yml` o falta `cert.pem` → `tunnel.log` |
| Backend OK pero el sitio no lo ve | `hostname` del `ingress` ≠ `BASE_URL_PUBLICA` |
| Pagos quedan en "Esperando pago" | Webhook de MP apunta a otra URL, o `MP_WEBHOOK_SECRET` es de otra app |

Reinstalar servicios sin reinstalar todo:

```powershell
cd "C:\Program Files\PrintNet"
powershell -ExecutionPolicy Bypass -File install-services.ps1
```

---

## Parte 4 — Configuración manual de Windows (IMPORTANTE)

Esto **no se puede scriptear de forma confiable** y sin ello la notebook se
duerme o se reinicia sola, y el local queda sin sistema. Hacelo una vez.

### 4.1 Que no se suspenda ni apague la pantalla (enchufada)

**Configuración → Sistema → Inicio/apagado y suspensión**:

| Opción | Valor (con corriente alterna) |
|---|---|
| Apagar la pantalla | Nunca (o 10 min: no afecta al servicio) |
| Poner en suspensión | **Nunca** |

Equivalente por consola (PowerShell como Administrador):

```powershell
powercfg /change standby-timeout-ac 0      # nunca suspender enchufada
powercfg /change hibernate-timeout-ac 0    # nunca hibernar enchufada
powercfg /change monitor-timeout-ac 10     # pantalla a los 10 min (opcional)
powercfg /hibernate off                    # desactiva hibernación del todo
```

### 4.2 Que no se suspenda al cerrar la tapa

Este es el que más se olvida: si cerrás la notebook, se suspende y **se cae el
servicio**.

**Panel de control → Hardware y sonido → Opciones de energía → Elegir el
comportamiento del cierre de la tapa** → "Al cerrar la tapa: **No hacer nada**"
(en la columna *Conectado*).

```powershell
powercfg /setacvalueindex SCHEME_CURRENT 4f971e89-eebd-4455-a8de-9e59040e7347 5ca83367-6e45-459f-a27b-476b1d01c936 0
powercfg /setactive SCHEME_CURRENT
```

### 4.3 Que Windows Update no reinicie cuando quiere

**Configuración → Windows Update → Opciones avanzadas**:

- **Horas activas**: ponelas cubriendo todo el horario del local
  (ej. 08:00 a 22:00) — Windows no reinicia dentro de esa franja.
- Activar *"Notificarme cuando se requiera reiniciar para finalizar la
  actualización"*.
- **Pausar actualizaciones** cuando estés en temporada fuerte (máx. 5 semanas).

> No conviene desactivar Windows Update del todo: quedaría sin parches de
> seguridad y la notebook está expuesta a internet por el túnel. Con las horas
> activas bien puestas alcanza.

**Después de cada reinicio por Windows Update no hay que hacer nada**: ambos
servicios están en arranque automático y vuelven solos. Igual conviene mirar
`Get-Service PrintNetBackend, PrintNetTunnel` a la mañana siguiente.

### 4.4 Otras recomendaciones

- **Batería**: dejarla siempre enchufada. Si se corta la luz, la notebook sigue
  con batería pero el módem/router no — el túnel se cae hasta que vuelva.
  Un UPS chico para notebook + router resuelve los cortes cortos.
- **Inicio de sesión**: los servicios corren como `LocalSystem`, así que
  funcionan **con la sesión cerrada**. No hace falta dejar el usuario logueado.
- **Suspensión selectiva de USB / adaptador de red**: en Administrador de
  dispositivos → adaptador de red → Propiedades → Administración de energía →
  destildar *"Permitir que el equipo apague este dispositivo"*. Evita que la
  placa de red se duerma y corte el túnel.
- **Nombre del equipo / IP**: no importan, el túnel sale hacia afuera; no hay
  que abrir puertos en el router ni configurar IP fija.

---

## Operación diaria

No hay operación diaria: prendés la notebook y listo. Para chequear:

```powershell
Get-Service PrintNetBackend, PrintNetTunnel
```

Reiniciar el backend después de tocar el `.env` (los cambios se leen al
arrancar):

```powershell
Restart-Service PrintNetBackend
```

Backup de los pedidos (la base es un solo archivo):

```powershell
Copy-Item "C:\Program Files\PrintNet\printnet.db" "D:\backups\printnet-$(Get-Date -f yyyyMMdd).db"
```
