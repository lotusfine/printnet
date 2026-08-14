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
            │                              (PENDIENTE de crear)
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

**Dominio migrado a Cloudflare** (2026-08-19). Se replicaron los 24 registros
de la zona; el DKIM se verificó carácter por carácter (409 caracteres,
idéntico) antes de delegar. Correo, sitio y servicios intactos.

**Configuración de servidores editable sin recompilar.** El archivo
`public_html/config.js` define a qué backend apunta la web. Se edita desde el
Administrador de archivos de cPanel y el cambio es inmediato.

---

## ⬜ Pendiente

### 1. Túnel de Cloudflare — *ya se puede hacer*

El dominio está en Cloudflare, así que el prerequisito está cumplido. Falta:

```bash
cloudflared tunnel login
cloudflared tunnel create printnet
cloudflared tunnel route dns printnet api.libreriaglaxara.com.ar
```

Hasta ahora se venían usando **túneles rápidos** (`trycloudflare.com`), cuya
URL **cambia en cada arranque** — eso obligaba a reconfigurar tres lugares cada
vez. Con el túnel nombrado la dirección queda fija para siempre.

### 2. La impresión no está programada ⚠️

**Esto es lo que más se subestima.** Hoy el sistema escribe en un registro
*"se despacharía este archivo"* y no manda nada a ninguna impresora.
`print_dispatch.py` solo tiene `SimulatedDispatcher`.

Falta escribir el despachador real que le habla a SumatraPDF. El mapeo de
nuestras opciones a sus parámetros es directo:

| Nuestra opción | SumatraPDF |
|---|---|
| `color: byn` / `color` | `monochrome` / `color` |
| `caras: simple` / `doble` | `simplex` / `duplexlong` |
| `copias: N` | `Nx` |
| `tamano: A4` / `A3` | `paper=A4` / `paper=A3` |
| `rango: "3-8"` | `3-8` |

Solo se puede probar en Windows con la impresora conectada.

### 3. El panel de admin no tiene seguridad ⚠️

La contraseña `admin123` **se valida en el navegador, no en el servidor**. Los
endpoints `/admin/*` responden a cualquiera que sepa la URL: se pueden leer
nombres, teléfonos y emails de clientes, y modificar pedidos.

Hoy está protegido por accidente (la URL del túnel es aleatoria), pero **con
`api.libreriaglaxara.com.ar` fija y pública deja de estarlo**. Hay datos reales
de clientes en la base.

**Resolver antes de abrir al público.**

### 4. Compilar el `.exe` e instalarlo como servicio

Todo preparado en `backend-printnet/deploy/` (spec de PyInstaller, scripts NSSM,
instalador Inno Setup). PyInstaller **no cross-compila**: hay que hacerlo en la
notebook Windows.

**Orden importante:** primero correr el backend con Python suelto y probar la
impresión; recién cuando funcione, compilar. Depurar un `.exe` es mucho más
lento.

### 5. Activar los pedidos en la web

Hoy `/fotocopias` y `/fotos` muestran un aviso de "pedidos en preparación" con
botón de WhatsApp, en vez del formulario. Es a propósito: sin túnel, el
formulario no tendría a dónde enviar.

Para activarlos: editar `config.js` en cPanel y poner la URL del túnel en
`PRINTNET_API`. Nada más.

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

1. Crear el túnel nombrado (el dominio ya está listo)
2. Escribir el despachador de impresión
3. Resolver la seguridad del admin
4. Llevar todo a la notebook, probar con Python suelto
5. Compilar el `.exe` e instalar como servicio
6. Activar los pedidos en `config.js`
