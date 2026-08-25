# PrintNet — Estado del proyecto

> **Leé este archivo primero.** Es el traspaso entre sesiones de trabajo: dice
> qué está terminado, qué falta y por qué se tomó cada decisión. El detalle
> técnico del backend está en `backend-printnet/SPEC.md`; el de la instalación
> en Windows, en `backend-printnet/deploy/README.md`.
>
> Última actualización: **2026-08-19**

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
| **Backend** | FastAPI + SQLite | Hoy: Mac de desarrollo · Destino: notebook Windows |
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
| Credenciales | `C:\Users\marcelo\.cloudflared\b34cbdf0-...json` |
| Configuración | `C:\Users\marcelo\.cloudflared\config.yml` |
| Usuario de Windows | **marcelo** |

Se levanta a mano con `cloudflared tunnel run printnet`, en su propia ventana.
Convertirlo en servicio es parte del punto 4.

**Trampa para cuando sea servicio:** las credenciales y el `cert.pem` viven en
la carpeta personal de `marcelo`. El servicio corre bajo otra cuenta que no la
ve — hay que pasarle `--config` y `TUNNEL_ORIGIN_CERT`. `deploy/install-services.ps1`
ya lo contempla.

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

### 4. Compilar el `.exe` e instalarlo como servicio — ⬅️ ES LO ÚNICO QUE FALTA

> Hoy el backend y el túnel corren en dos ventanas de PowerShell abiertas a
> mano. **El sitio está tomando pedidos reales en ese estado.** Si alguien
> cierra una ventana, o la notebook se reinicia o se suspende, el formulario
> deja de funcionar. No se pierde plata (sin backend no se crea ni se cobra el
> pedido), pero el cliente se topa con algo roto.


Todo preparado en `backend-printnet/deploy/` (spec de PyInstaller, scripts NSSM,
instalador Inno Setup). PyInstaller **no cross-compila**: hay que hacerlo en la
notebook Windows.

**Orden importante:** primero correr el backend con Python suelto y probar la
impresión; recién cuando funcione, compilar. Depurar un `.exe` es mucho más
lento.

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

1. ~~Clonar el repo en la notebook~~ ✅
2. ~~Probar la impresión real~~ ✅ (2026-08-14)
3. ~~Pedido completo de punta a punta, con el backend levantado~~ ✅ (2026-08-19)
4. ~~Copiarle el `.env` a la notebook~~ ✅ (2026-08-19)
5. ~~Crear el túnel nombrado + la seguridad del admin~~ ✅ (2026-08-19)
6. ~~Probar un pedido con pago real de MercadoPago~~ ✅ (2026-08-19)
7. Compilar el `.exe` e instalar como servicio
8. ~~Activar los pedidos en `config.js`~~ ✅ (2026-08-19)

---

## Tanda de mejoras (planificada el 2026-08-20, implementada el 2026-08-25)

| # | Qué | Estado |
|---|---|---|
| 1 | Que la web no invente "10 páginas" | ✅ hecho |
| 2 | Avisar el límite de tamaño y subirlo a 95 MB | ✅ hecho |
| 3 | Aceptar Word, Excel y PowerPoint, y convertirlos a PDF | ✅ hecho |
| 4 | Pedidos con varios documentos | ⬅️ **lo único que falta** |
| 5 | Contar páginas en el navegador | en pausa, a la espera de errores reales |

Planes: [conversión de formatos](docs/plan-conversion-de-formatos.md) ·
[carga de archivos](docs/plan-carga-de-archivos.md) ·
[varios documentos](docs/plan-multiples-archivos.md)

### Lo que cambió

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

### Sigue pendiente de decidir (solo afecta al punto 4)

- ¿Qué estado toma un pedido de varios documentos si uno imprime y otro no?

### Entorno de la notebook

LibreOffice instalado y verificado con `.ppt` y `.pps` reales. Si no quedara en
la ruta por defecto, se configura con `PRINTNET_SOFFICE` en el `.env`.

**Ojo con los dos `.env`:** hay uno en `backend-printnet\` (lo usa Python
suelto, que es como se trabaja) y otro en `dist\` (lo usa el `.exe`). Manda el
de la carpeta desde donde se arranca.
