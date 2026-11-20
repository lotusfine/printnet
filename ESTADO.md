# PrintNet — Estado del proyecto

> **Leé este archivo primero.** Es el traspaso entre sesiones de trabajo: dice
> qué está terminado, qué falta y por qué se tomó cada decisión. El detalle
> técnico del backend está en `backend-printnet/SPEC.md`; el de la instalación
> en Windows, en `backend-printnet/deploy/README.md`.
>
> Última actualización: **2026-11-20**
>
> **El sistema está en producción y corriendo solo.** Backend y túnel son
> servicios de Windows que arrancan con la notebook. Ver el punto 4.

---

## Qué es PrintNet

Sistema de pedidos de impresión para Librería Glaxara (La Plata). El cliente
sube un PDF desde la web, elige opciones, paga con MercadoPago, y el pedido
llega a una notebook en el local que lo imprime.

```
Cliente
  │
  ├─→ www.libreriaglaxara.com.ar          la web (archivos estáticos en cPanel)
  │
  └─→ api.libreriaglaxara.com.ar          el backend, vía túnel de Cloudflare
            │                              (✅ funcionando)
            ▼
      notebook en el local  ──→  Ricoh IM C4500
```

Tres piezas separadas, cada una en su lugar:

| Pieza | Qué es | Dónde vive |
|---|---|---|
| **Web** | React compilado a archivos estáticos | cPanel (servidoraweb, `167.250.5.3`) |
| **Backend** | FastAPI + SQLite, compilado a `.exe` | Notebook Windows del local, como servicio (`C:\PrintNet\servicio`) |
| **Impresora** | Ricoh IM C4500 (color, A3, dúplex) | Local |

El hosting **no puede correr Python** (lo verifiqué: no tiene "Setup Python
App"), por eso el backend va sí o sí en la notebook y por eso hace falta el
túnel.

---

## ✅ Terminado y verificado

**Web publicada en el dominio propio.** Se dejó de usar Vercel. Los archivos
compilados están en `public_html` de cPanel. Se arregló de paso un bug que el
sitio arrastraba: los links directos (`/novedades`, etc.) daban 404 por falta
del `.htaccess` de React Router.

**Motor de precios por tramos** con los valores reales del negocio (ver la
tabla en `SPEC.md`). Espejado entre backend (`pricing.py`) y frontend
(`PrintOptions.jsx`) — **si se cambia uno hay que cambiar el otro**. Cubierto
por `backend-printnet/test_pricing.py` (27 casos, incluidos los bordes de cada
tramo).

**MercadoPago en producción, probado con dinero real.** Un pago de $200 el
2026-08-12: aprobado, webhook validado por firma, pedido pasado a
"imprimiendo", despacho registrado. Neto recibido $191,39 (comisión de MP
$8,61).

**El circuito completo, en producción y de punta a punta (2026-08-19).** Un
pedido hecho desde la web pública, pagado con dinero real, notificado por el
webhook a través del túnel definitivo, impreso en la Ricoh, y despachado desde
el panel de operador (`imprimiendo → listo → entregado`). Es el sistema entero
funcionando como lo va a usar un cliente y el mostrador.

**Dominio migrado a Cloudflare** (2026-08-19). Se replicaron los 24 registros
de la zona; el DKIM se verificó carácter por carácter (409 caracteres,
idéntico) antes de delegar. Correo, sitio y servicios intactos.

**Configuración de servidores editable sin recompilar.** El archivo
`public_html/config.js` define a qué backend apunta la web. Se edita desde el
Administrador de archivos de cPanel y el cambio es inmediato.

---

## ⬜ Pendiente

### 0. El `.env` de la notebook — ✅ completo (2026-08-19)

Está en `C:\PrintNet\printnet\backend-printnet\.env`, con MercadoPago activo,
`BASE_URL_PUBLICA=https://api.libreriaglaxara.com.ar`, el token del admin y el
despachador apuntando a SumatraPDF.

Trampa al copiar el archivo: Windows le saca el punto inicial y lo deja como
`env`. Hay que renombrarlo a `.env` con `Rename-Item`, porque el Explorador no
deja crear nombres que empiecen con punto.

Otra trampa, que ya nos costó una vuelta: **el servidor lee el `.env` una sola
vez, al arrancar.** Después de tocarlo hay que reiniciarlo. Lo mismo vale
después de un `git pull`: el código viejo sigue en memoria.

### 1. Túnel de Cloudflare — ✅ creado y funcionando (2026-08-19)

`https://api.libreriaglaxara.com.ar` responde desde internet. Verificado desde
otra máquina y otra red: la raíz devuelve 200, y `/admin/*` devuelve 401 tanto
sin token como con uno inventado.

| Dato | Valor |
|---|---|
| Nombre del túnel | `printnet` |
| ID | `b34cbdf0-01d6-47e6-b73d-2c5851b9e37f` |
| Credenciales | `C:\PrintNet\servicio\cloudflared\b34cbdf0-...json` |
| Configuración | `C:\PrintNet\servicio\cloudflared\config.yml` |
| Certificado de origen | `C:\PrintNet\servicio\cloudflared\cert.pem` |
| Usuario de Windows | **marcelo** |

Corre como el servicio `PrintNetTunnel` (ver punto 4). Los archivos de arriba
se copiaron desde `C:\Users\marcelo\.cloudflared\` a la carpeta del servicio a
propósito: **el servicio corre como LocalSystem, cuyo `%USERPROFILE%` es
`C:\Windows\System32\config\systemprofile`, no la carpeta de `marcelo`.** Por
eso `install-services.ps1` le pasa `--config` con ruta absoluta y la variable
`TUNNEL_ORIGIN_CERT`. Si en el futuro se regeneran las credenciales, hay que
copiarlas de nuevo a la carpeta del servicio, no solo a la del usuario.

**Pendiente menor:** `/docs` y `/openapi.json` quedaron públicos. No filtran
datos, pero publican la lista completa de endpoints, incluidos los de admin.
Conviene desactivarlos en producción.

### 2. La impresión: ✅ probada de punta a punta y funcionando

**El circuito completo anda (2026-08-19)**, incluido el pago real: un pedido
hecho desde la web se cotiza, se cobra, se despacha solo y sale en papel.

Antes, el 2026-08-14, se había verificado la impresión sola contra la Ricoh:
blanco y negro, color, doble faz, copias múltiples, rango de páginas y ambos
tamaños, uno por uno — incluido A4→A3 y A3→A4, que son los que garantizan que
lo impreso coincida con lo cobrado.

**El entorno de la notebook:** Python 3.11.9 (la misma que el Mac), repo en
`C:\PrintNet\printnet`, SumatraPDF en `C:\PrintNet\SumatraPDF.exe`, y el
`.env` ya puesto (ver punto 0). La impresora se llama exactamente
`RICOH IM C4500 PCL 6` y está en la red.

**Cómo repetir la prueba**, en dos ventanas de PowerShell:

```
cd C:\PrintNet\printnet\backend-printnet
.venv\Scripts\python run_server.py          # ventana 1: queda ocupada
.venv\Scripts\python prueba_pedido.py       # ventana 2
```

Y para probar la impresora sin levantar el backend:

```
python generar_pdf_prueba.py --paginas 4 --tamano A3 --salida C:\PrintNet\p.pdf
python prueba_impresion.py C:\PrintNet\p.pdf --tamano A3 --simular
```

El tamaño de papel fue lo que más costó: SumatraPDF ignora `paper=`, `bin=` y
la configuración de la cola, y toma el tamaño del **PDF**. Se resolvió
normalizando el documento antes de imprimir (`pdf_normalize.py`) y quedó
verificado en las dos direcciones contra la impresora.

**Ojo:** `ok=True` significa *"se encoló"*, no *"salió el papel"*. Si la
impresora se traba, el pedido igual figura despachado. Verificar la cola de
Windows quedó fuera de alcance a propósito.

### 3. Seguridad del panel de admin — ✅ hecha (2026-08-19)

`/admin/*` exige el header `X-Admin-Token` contra `PRINTNET_ADMIN_TOKEN` del
`.env`. Antes, la única "contraseña" era `admin123` comparada en el navegador:
los endpoints respondían a cualquiera que supiera la URL, con nombres,
teléfonos y emails de clientes reales adentro.

El token ya está puesto en el `.env` de la notebook, y quedó **verificado
contra la dirección pública**: `/admin/*` devuelve 401 desde internet, sin
token y con uno inventado.

Se falla cerrado: si `PRINTNET_ADMIN_TOKEN` falta o tiene menos de 16
caracteres, `/admin/*` responde 503 en vez de abrirse. Para generar otro:

```
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

**El panel de operador ya usa el token** (`frontend/src/adminAuth.js`). Se pega
una vez por navegador, en la pantalla de ingreso, y queda guardado en
`localStorage`. Se valida contra el backend antes de dejar entrar, así un token
mal pegado se detecta en el momento.

El `admin123` que se validaba en el navegador ya no existe.

Aclaración, porque el comentario del código decía lo contrario y costó una
confusión: **el panel nunca fue una maqueta**. Los pedidos vienen del backend y
se refrescan cada 15 s; los botones de estado llaman a `PATCH /admin/orders/{id}`.
Lo único de relleno es la lista de impresoras cuando `/admin/printers` no
responde — si ves "HP LaserJet 1", el backend no contestó.

**El token no va en `config.js`:** ese archivo lo sirve la web y lo puede leer
cualquiera.

**No hay usuarios ni cuentas: el token *es* la contraseña, una sola para todo
el sistema.** El backend no registra quién entra ni desde dónde. Consecuencias
prácticas:

- **Agregar una computadora no requiere tocar el servidor.** Se entra al panel
  desde esa máquina y se pega el mismo token.
- Queda guardado en el `localStorage` **de ese navegador en esa máquina**. Misma
  PC con otro navegador = lo vuelve a pedir.
- Una máquina que deja el local tiene que salir con **Cerrar sesión**, o el
  token se va guardado adentro.
- **Para rotarlo:** cambiar `PRINTNET_ADMIN_TOKEN` en
  `C:\PrintNet\servicio\.env` y `Restart-Service PrintNetBackend` (como
  administrador). Eso invalida todas las sesiones y hay que volver a pegarlo en
  cada máquina.

Hoy entran las **dos computadoras fijas de la librería**.

### 4. Compilar el `.exe` e instalarlo como servicio — ✅ hecho (2026-11-16)

El backend y el túnel ya **no** dependen de ventanas abiertas a mano. Son dos
servicios de Windows con arranque automático y reinicio ante caída:

| Servicio | Qué corre | Logs |
|---|---|---|
| `PrintNetBackend` | `C:\PrintNet\servicio\printnet-backend.exe` | `C:\PrintNet\servicio\logs\backend.log` |
| `PrintNetTunnel` | `cloudflared --config ... tunnel run printnet` | `C:\PrintNet\servicio\logs\tunnel.log` |

Registrados con NSSM por `deploy/install-services.ps1`, que se corre desde una
PowerShell **como administrador**:

```
powershell -ExecutionPolicy Bypass -File C:\PrintNet\printnet\backend-printnet\deploy\install-services.ps1 -InstallDir C:\PrintNet\servicio
```

**Verificado después de reiniciar la notebook**: los dos servicios levantaron
solos, sin abrir nada, y desde internet `https://api.libreriaglaxara.com.ar/`
devolvió 200 y `/admin/orders` devolvió 401.

**Por qué la carpeta del servicio NO es `dist\`.** El ejecutable crea
`printnet.db` y `uploads\` al lado suyo. Si el servicio corriera desde `dist`,
el día que se recompile con `--noconfirm` se estaría tocando la carpeta donde
viven los pedidos reales. Por eso el servicio vive en `C:\PrintNet\servicio\`,
que es una copia: `printnet-backend.exe`, `.env`, `nssm.exe` y `cloudflared\`.

**Qué hay que recordar al actualizar el backend:** recompilar en `dist`, parar
el servicio, copiar el `.exe` nuevo a `C:\PrintNet\servicio\` y arrancarlo. La
base y los archivos de los clientes quedan donde están.

```
Stop-Service PrintNetBackend
Copy-Item C:\PrintNet\printnet\backend-printnet\dist\printnet-backend.exe C:\PrintNet\servicio\ -Force
Start-Service PrintNetBackend
```

**`AppDirectory` es crítico** y `install-services.ps1` lo setea: el `.exe`
resuelve `.env`, `printnet.db` y `uploads\` relativos a su carpeta de trabajo.
Si estuviera mal, el backend arrancaría igual pero **sin MercadoPago y sin
token de admin**, y no nos enteraríamos hasta que un cliente intentara pagar.
La forma rápida de descartarlo: `/admin/orders` tiene que dar **401**, no 503.
Un 503 significa que no leyó el `.env`.

La base arrancó limpia: los pedidos de prueba de agosto quedaron en la base
vieja de `dist\`, que sigue ahí por si alguna vez hace falta mirarla. Cuando el
`.exe` no encuentra `printnet.db` la crea y da de alta la Ricoh como impresora
activa solo (`database.py`, `SEED_PRINTERS`), así que no hubo que cargar nada
a mano.

PyInstaller **no cross-compila**: la compilación se hace en la notebook Windows.

### 5. Activar los pedidos en la web — ✅ hecho (2026-08-19)

`public_html/config.js` tiene `PRINTNET_API: "https://api.libreriaglaxara.com.ar"`.
El formulario de `/fotocopias` reemplazó al aviso de "pedidos en preparación".
Verificado en el navegador: la página carga la configuración correcta, muestra
el formulario y no tira errores de consola. El CORS del backend acepta los dos
dominios (con y sin `www`) y rechaza cualquier otro.

**El sitio está tomando pedidos reales.**

---

## Decisiones tomadas (no volver a discutirlas)

**Precios por tramos planos, no marginales.** El precio del tramo se aplica a
todas las unidades. 300 copias = 300 × $130, no un cálculo acumulado.

**El tramo se evalúa sobre el total de la línea** (hojas × copias), no por
copia individual. 2 copias de 10 páginas = 20 unidades → tramo 20-99.

**Pedidos de `/fotos` sin precio online.** Se cotizan a mano en el local; nacen
como "requiere atención manual".

**Precios hardcodeados en `pricing.py`,** sin endpoint de edición ni interfaz en
el admin. Cambiar un precio = editar el archivo y redeployar.

**Backend en la notebook, no en la nube.** Tiene que estar físicamente al lado
de la impresora. Se evaluó la alternativa (backend en la nube + agente local
que consulta trabajos) y quedó descartada por ahora: costaría ~7 USD/mes y
requiere rearquitectura. Es la mejora natural si el volumen crece.

---

## Trampas conocidas (ya nos costaron tiempo)

**El límite de tamaño está escrito dos veces.** `MAX_PEDIDO_MB` en
`backend-printnet/subidas.py` y `MAX_ARCHIVO_MB` en `frontend/src/limites.js`
tienen que coincidir. `MAX_FILE_MB` en `routers/orders.py` (95) es otro: el
del camino viejo, que sí pasa entero por Cloudflare.

**Un pedido recién pagado queda unos segundos en "pendiente".** Es el tiempo
que tarda en imprimirse en segundo plano. No es un pedido trabado.

**`git pull` en la notebook no cambia lo que corre.** El servicio usa la copia
del `.exe` en `C:\PrintNet\servicio\`. Hasta recompilar y copiar, sigue el
código viejo.

**El hosting bloquea leer archivos ocultos desde cPanel.** El `.htaccess` no se
puede ver ni editar por el panel ("Prohibido el acceso desde su ubicación").
Para leerlo hay que sacarlo de un backup. Los archivos normales (como
`config.js`) sí se editan sin problema.

**MercadoPago rechaza `localhost` en las back_urls.** Con `auto_return`
activado devuelve `auto_return invalid`. El código ya lo contempla: solo envía
`auto_return` si la URL es https.

**MercadoPago manda las notificaciones por duplicado** (formato Webhooks y
formato IPN antiguo). Solo procesamos el primero; el IPN da 401 y ensucia las
estadísticas. Conviene desactivar IPN en el panel de MP.

**Un 404 al consultar un pago es permanente, no transitorio.** Devolver 500
hacía que MP reintentara infinitamente. Ya corregido: 400/404 → 200.

**El correo de la librería cuelga del registro raíz del dominio.** El MX apunta
a `libreriaglaxara.com.ar`, que apunta a `167.250.5.3`. Si algún día se mueve
la raíz a otro servidor, **el correo se rompe sin avisar**. La solución sería
crear un registro `mx.libreriaglaxara.com.ar` y apuntar el MX ahí. No es
urgente mientras la web siga en cPanel.

**El tamaño de papel no se puede pedir por línea de comandos.** SumatraPDF
ignora `paper=`, `bin=` y la configuración de la cola de Windows — las tres en
silencio, sin error. Usa el tamaño de página del PDF. Por eso existe
`pdf_normalize.py`: el documento se reescribe al tamaño pedido antes de
imprimir. **Consecuencia de plata:** hay que normalizar SIEMPRE, no solo los
pedidos A3, porque un cliente que sube un PDF A3 y paga A4 imprimiría en A3.

**Hay dos colas de la Ricoh instaladas en Windows** (`RICOH IM C4500 PCL 6` y
`RICOH IM C4500 A3`). La segunda se creó intentando resolver lo anterior y
**no sirvió**. Es inofensiva, pero se puede borrar: el código usa solo la
primera.

**Recompilar la web apaga los pedidos, en silencio.** El `config.js` que está
publicado en cPanel tiene la URL del backend, pero el del repositorio
(`frontend/public/config.js` y `frontend/dist/config.js`) la tiene **vacía**.
Si alguien recompila el frontend y sube todo, pisa el archivo del servidor,
`PEDIDOS_HABILITADOS` pasa a false y la web vuelve a mostrar "pedidos en
preparación" sin ningún error a la vista. Después de cada deploy hay que
volver a poner la URL en `public_html/config.js`.

**La impresora está en la red, no en el USB.** El puerto es
`IP_192.168.10.128`. Bueno: no depende de que esté enchufada a esa notebook en
particular. Malo: **si el router le cambia la IP por DHCP, la impresión se
corta sin avisar** y el pedido va a fallar con un error de SumatraPDF que no
dice eso. Hay que reservarle la IP en el router. Pendiente de verificar con
quien administre la red del local.

**En Cloudflare, todo en "DNS only" (nube gris).** El correo no funciona a
través del proxy de Cloudflare. Si alguien pone la raíz o `mail` en naranja,
se rompe el correo.

**Windows PowerShell 5.1 no soporta here-strings en archivos con finales de
línea de Unix.** Y no falla con un mensaje claro: empieza a interpretar el
texto del mensaje como código y tira una catarata de errores de sintaxis que
apuntan a líneas que son texto plano. Esto frenó la instalación del servicio.
Dos reglas, ya aplicadas:
- En los `.ps1`, para texto de varias líneas van varios `Write-Host`, nunca
  here-strings.
- `.gitattributes` fuerza CRLF en `.ps1`, `.bat`, `.cmd` e `.iss`, y los
  scripts se guardan en **UTF-8 con BOM** — sin BOM, 5.1 los lee como ANSI y
  "túnel" imprime "tÃºnel".

**No hay que hacer clic adentro de una consola de Windows que esté corriendo
algo.** El modo QuickEdit congela el proceso hasta que se presione una tecla, y
desde afuera se ve exactamente como un backend colgado: acepta la conexión TCP
y no responde nunca. Ya nos costó un rato de diagnóstico. Desde que son
servicios no aplica, pero sí a cualquier prueba manual.

**Hay dos `.env` y manda el de la carpeta desde donde se arranca.** Uno en
`backend-printnet\` (Python suelto), uno en `dist\` (el `.exe` recién
compilado) y uno en `C:\PrintNet\servicio\` (**el de producción**). Editar el
equivocado es silencioso.

---

## Accesos y credenciales

| Servicio | Dónde está | Notas |
|---|---|---|
| Repositorio | `github.com/lotusfine/printnet` | |
| Hosting | `cpanel.libreriaglaxara.com.ar` | usuario `glaxara` |
| DNS | Cloudflare (cuenta `lucasyalet94@gmail.com`) | |
| Registro del dominio | NIC.ar — CUIT del titular | requiere Clave Fiscal |
| MercadoPago | Cuenta `GLAXARAFEBRERA` | credenciales de **producción** |

**Las credenciales viven en `backend-printnet/.env`, que NO está en el
repositorio** (está en `.gitignore`). Para llevar el sistema a la notebook hay
que copiar ese archivo por fuera de git. Ver `.env.example` para la estructura.

**Backup del sitio anterior:** `/home4/glaxara/backup-sitio-anterior-2026-08-07.zip`
en el hosting, fuera de la carpeta pública.

---

## Próximo paso recomendado

La puesta en producción está **terminada**. Todo lo que sigue es mejora, no
bloqueante:

1. ~~Clonar el repo en la notebook~~ ✅
2. ~~Probar la impresión real~~ ✅ (2026-08-14)
3. ~~Pedido completo de punta a punta, con el backend levantado~~ ✅ (2026-08-19)
4. ~~Copiarle el `.env` a la notebook~~ ✅ (2026-08-19)
5. ~~Crear el túnel nombrado + la seguridad del admin~~ ✅ (2026-08-19)
6. ~~Probar un pedido con pago real de MercadoPago~~ ✅ (2026-08-19)
7. ~~Compilar el `.exe` e instalar como servicio~~ ✅ (2026-11-16)
8. ~~Activar los pedidos en `config.js`~~ ✅ (2026-08-19)

### Lo que queda, por orden de importancia

**1. Devolución del dinero al cancelar un pedido pagado** — *postergado a
propósito por el dueño del proyecto, no olvidado.* Hoy, cuando se cancela un
pedido ya pagado, **el cliente no recibe la plata de vuelta**: hay que
devolvérsela a mano por fuera del sistema. El diseño ya está pensado:

- Una acción **explícita**, no automática al cancelar — cancelar y devolver no
  siempre van juntos (el pedido ya puede estar impreso).
- Un aviso al cancelar un pedido pagado, para que nadie lo cancele sin saber
  que queda plata del cliente adentro.
- `POST https://api.mercadopago.com/v1/payments/{id}/refunds`, que exige el
  header `X-Idempotency-Key`. El `mp_payment_id` ya se guarda en la base, así
  que no falta ningún dato.
- **Dos preguntas abiertas antes de implementar:** ¿se permiten devoluciones
  parciales (por ejemplo si de tres documentos salió uno)? ¿y puede devolver
  cualquiera que tenga el token, o hace falta algo más?

**2. `/docs` y `/openapi.json` siguen públicos.** No filtran datos, pero
publican la lista completa de endpoints, incluidos los de admin. Conviene
desactivarlos en producción.

**3. Reservar la IP de la impresora en el router** (ver trampas). Si el DHCP le
cambia la IP, la impresión se corta sin avisar y el error de SumatraPDF no dice
eso. Depende de quien administre la red del local.

**4. Detalle menor:** `prueba_pedido.py` muestra un traceback en vez de un
mensaje claro cuando el archivo de prueba no existe.

---

## Tanda de mejoras (planificada el 2026-08-20, completada el 2026-11)

| # | Qué | Estado |
|---|---|---|
| 1 | Que la web no invente "10 páginas" | ✅ hecho |
| 2 | Avisar el límite de tamaño y subirlo a 95 MB | ✅ hecho |
| 3 | Aceptar Word, Excel y PowerPoint, y convertirlos a PDF | ✅ hecho |
| 4 | Pedidos con varios documentos | ✅ hecho |
| 5 | Contar páginas en el navegador | en pausa, a la espera de errores reales |
| 6 | Archivos de hasta 300 MB (subida en partes) | ✅ código hecho · ⬜ medir la notebook y desplegar |

Planes: [conversión de formatos](docs/plan-conversion-de-formatos.md) ·
[carga de archivos](docs/plan-carga-de-archivos.md) ·
[varios documentos](docs/plan-multiples-archivos.md)

### Lo que cambió

**Archivos de hasta 300 MB por pedido** — *código terminado y en `main`,
todavía NO desplegado* (2026-11-20). Cloudflare corta las peticiones de más de
100 MB, así que la web parte cada archivo en pedazos de 6 MB y la notebook los
rearma (`subidas.py`). De paso, el archivo se sube **una sola vez**: antes se
subía para contar páginas y otra vez al pagar. Las subidas abandonadas se
borran a las 24 h. `/fotos` sigue con el límite de 95 MB.

**Antes de desplegarlo falta medir la notebook** con un PDF de 300 MB
(`medir_archivo_grande.py`, Tarea 0 de
`docs/plan-subida-en-partes-implementacion.md`). Los timeouts de LibreOffice y
SumatraPDF siguen en 120 s; según lo que dé la medición se dejan, se suben, o
se frena todo si la memoria no aguanta. Después: backend primero (es
compatible con la web vieja) y la web después (Tarea 6, pasos 5 y 6).

**El webhook de MercadoPago ya no imprime.** Marca el pedido pagado, responde,
y la impresión corre en segundo plano. Con archivos grandes, el webhook pasaba
los 22 s de MP y el reintento podía imprimir el pedido dos veces.

**La web ya no inventa páginas.** Había un valor por defecto de 10 que se usaba
cuando el conteo fallaba, y el precio se calculaba sobre ese número: un
documento de 1 página podía cotizarse como 10. Ahora, si no se sabe cuántas
páginas tiene, no se muestra precio y no se deja pagar.

**El límite pasó de 50 a 95 MB**, y se valida en el navegador antes de subir
nada. 95 y no 100 porque el techo de Cloudflare en plan gratuito son 100 MB, y
conviene que salte nuestro mensaje y no el suyo.

**Se aceptan Word, Excel, PowerPoint y OpenOffice**, convertidos con LibreOffice
(`document_convert.py`). Incluye `.pps`, que apareció porque lo trajo un
cliente real y no figuraba en el plan.

### Decisiones tomadas

- **Los tramos de precio se calculan sobre el TOTAL del pedido**, sumando todos
  los documentos. Si la suma alcanza el tramo, se aplica el descuento. Con esto
  el punto 4 queda desbloqueado.
- **Si la conversión falla, se rechaza el pedido** con un mensaje pidiendo un
  PDF. Reversible: agregar después el camino de "cotizar en el mostrador" no
  rompe nada.
- **La vista previa del PDF convertido queda para más adelante.** Mientras
  tanto, la web avisa que el diseño puede moverse y sugiere subir un PDF si se
  necesita exactitud.

**Pedidos con varios documentos, cada uno con su propia configuración.** La
interfaz crece con los archivos: la sección de opciones cambia según el
documento seleccionado, y **no hay opciones por defecto** (`OPCIONES_VACIAS`),
para que nadie pague una configuración que no miró. El backend acepta el
formato viejo (un documento) y el nuevo, así que el orden del deploy no
importa. El espejo de precios entre `pricing.py` y `precio.js` está verificado
automáticamente por `verificar_espejo_precios.py`, que corre el motor JS con
Node y compara contra Python: **223 casos, cero diferencias**.

**Botón de reimprimir en el panel de operador** (`POST
/admin/orders/{id}/reimprimir`, opcionalmente con `?file_id=`). Antes, un
pedido que fallaba quedaba muerto: la impresión se dispara una sola vez, al
confirmar el pago, y esa función es idempotente a propósito para que
MercadoPago no imprima dos veces. Funciona **desde cualquier estado, incluido
`cancelado`** — de ese estado no sale ninguna transición, así que un pedido
cancelado por error no tenía ninguna salida.

### Resuelto: qué pasa si de varios documentos uno imprime y otro no

El pedido queda en `imprimiendo` con `requiere_manual = 1`, y el panel muestra
**qué documento falló** (`documentos_fallados`), no solo que "requiere
atención". Con varios documentos eso no alcanzaba: el operador tiene que saber
cuál reimprimir antes de entregar. Reimprimir solo ese documento limpia la
marca si no queda ninguno pendiente.

### Entorno de la notebook

LibreOffice instalado y verificado con `.ppt` y `.pps` reales. Si no quedara en
la ruta por defecto, se configura con `PRINTNET_SOFFICE` en el `.env`.

**Ojo con los `.env`: ahora son tres** y el de producción es el de
`C:\PrintNet\servicio\`. Ver la trampa correspondiente más arriba.
