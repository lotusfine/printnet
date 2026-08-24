# Plan — carga de archivos: páginas, tamaño y navegadores

> Estado: **propuesta, pendiente de confirmación**. No se escribió código todavía.
> Fecha: 2026-08-20
>
> Complementa a [plan-conversion-de-formatos.md](plan-conversion-de-formatos.md).
> Los dos tocan el mismo recuadro de carga, así que conviene leerlos juntos antes
> de decidir el orden.

## Los tres temas

| # | Tema | Urgencia | Tamaño |
|---|---|---|---|
| A | Que la web no invente la cantidad de páginas | **alta — toca la plata** | chico |
| B | Límite de tamaño: avisarlo y subirlo a 100 MB | media | chico |
| C | Contar páginas en el navegador | baja | mediano |

---

## A — Que la web no invente páginas

### El problema

En `frontend/src/components/fotocopias/FileUpload.jsx`:

```js
const FALLBACK_PAGES = 10;
```

Cuando la consulta al servidor para contar páginas falla —por el motivo que
sea— la web **asume que el documento tiene 10 páginas** y calcula el precio
sobre ese número.

Casos reales observados:

- Un documento de 1 página figuró como 10 en un celular con DuckDuckGo.
- Un archivo de más de 50 MB hace fallar la consulta → también da 10.

### Por qué es lo más urgente

Ese número **determina el precio que ve el cliente**. Hoy, en producción, alguien
con un documento de 1 página puede estar viendo el precio de 10.

### El arreglo

Sacar el valor por defecto. El recuadro de carga pasa a tener tres estados
explícitos:

| Estado | Qué muestra | ¿Se puede pagar? |
|---|---|---|
| Contando | "Leyendo tu documento…" | no |
| Listo | cantidad de páginas y precio | sí |
| **No se pudo leer** | mensaje claro + botón "Reintentar" | **no** |

La regla de fondo: **si no sabemos cuántas páginas tiene, no mostramos un precio
y no dejamos avanzar.** Es preferible un cliente que reintenta a un cliente al
que le cobramos de más.

### Un problema relacionado que conviene mirar

El precio que muestra la web es solo una vista previa: **el backend recalcula el
precio al crear el pedido**, con su propio conteo. Hoy los dos coinciden porque
cuentan igual. Pero si llegaran a diferir, el cliente vería un precio y se le
cobraría otro, sin aviso.

Sacar el valor inventado elimina el caso grave. La solución de fondo —que el
precio mostrado **sea** el precio cobrado, calculado una sola vez— sale gratis
si se hace la Fase 2 del plan de conversión, donde el archivo se prepara una vez
y el backend devuelve el precio definitivo.

---

## B — Límite de tamaño

### Situación actual

- El backend rechaza archivos de más de **50 MB** (`MAX_FILE_BYTES`).
- **La web no valida el tamaño en ningún momento.**

O sea que hoy un cliente con un archivo de 60 MB: espera toda la subida, ve un
precio inventado (por el tema A), completa sus datos, aprieta pagar, y **recién
ahí** se entera de que el archivo era muy grande. Dos esperas largas para nada.

### El techo real

**100 MB**, y no es nuestro: es el máximo que Cloudflare deja pasar en el plan
gratuito. Subir nuestro límite por encima de eso no serviría — la petición
moriría antes de llegar al backend, con un error de Cloudflare que no podemos
personalizar.

Por eso el límite propio conviene ponerlo **un poco por debajo** (95 MB), para
que salte nuestro mensaje claro y no el de Cloudflare.

### El arreglo

1. **Validar en la web apenas se elige el archivo**, antes de subir un solo byte.
   El navegador conoce el tamaño al instante.
2. **Avisar el límite en el recuadro de carga**, junto a los formatos aceptados
   — tal como sugerió Lucas: mejor avisar antes que hacer esperar para fallar.
   Propuesta: `Hasta 95 MB`.
3. **Subir `MAX_FILE_BYTES` a 95 MB** en el backend.
4. **Mensaje de error concreto** cuando se pasa: nombre del archivo, cuánto pesa
   y cuál es el máximo. No un "archivo demasiado grande" a secas.

### Cuidado con el número duplicado

El límite va a quedar escrito en dos lugares: el backend y la web. Es la misma
trampa que ya tiene el proyecto con los precios (`pricing.py` y
`PrintOptions.jsx`, anotada en `ESTADO.md`): si se cambia uno y no el otro, la
web deja subir algo que el servidor después rechaza.

Se resuelve con un comentario en cada lado apuntando al otro, y una línea en las
trampas conocidas de `ESTADO.md`.

---

## C — Contar páginas en el navegador

### La idea

Contar las páginas con una librería que corre en el navegador (pdf.js), sin
consultarle al servidor. El archivo ya está en la computadora del cliente.

Ventajas: elimina de raíz esta familia de fallas, y funciona aunque la conexión
sea mala.

### Por qué lo dejo último, y con una advertencia

**El diagnóstico de DuckDuckGo no está confirmado.** La hipótesis era que su
protección antirrastreo bloquea las consultas a `api.libreriaglaxara.com.ar` por
ser un subdominio distinto al del sitio.

Pero si eso fuera cierto, **también fallaría el envío del pedido**, que va al
mismo lugar — y el cliente no habría podido comprar en absoluto. Por lo que
contaste, sí podía. Así que probablemente la consulta falló por otra cosa: una
demora, un archivo grande, un error pasajero.

**Construir pdf.js sobre una hipótesis sin confirmar sería repetir el error del
tamaño de papel**, donde dimos por buena una suposición heredada y perdimos
tiempo.

### Lo que propongo en su lugar

1. Hacer el arreglo A, que **corrige el síntoma sea cual sea la causa**.
2. Que el mensaje de error registre **por qué** falló, y que ese motivo se pueda
   ver. Con dos o tres casos reales sabremos si es el navegador, la conexión o
   el tamaño.
3. **Recién ahí** decidir si vale la pena pdf.js.

### Una interacción importante con el otro plan

Si se acepta cualquier formato (plan de conversión), los Word y PowerPoint
**tienen que ir al servidor igual**, porque solo ahí se pueden convertir y
contar. Contar en el navegador serviría únicamente para los PDF.

Sigue teniendo valor —el PDF es el caso más común— pero es menos ganancia de la
que parecía cuando lo propuse.

---

## Orden sugerido

```
A (no inventar páginas)  ──►  B (límite y aviso)  ──►  [conversión de formatos]  ──►  C (si hace falta)
```

A y B son chicos, tocan los mismos archivos y conviene hacerlos juntos. C queda
después de la conversión de formatos, y solo si los errores reales confirman que
hace falta.
