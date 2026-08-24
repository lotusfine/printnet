# Plan — pedidos con varios documentos

> Estado: **propuesta, pendiente de decisiones**. No se escribió código todavía.
> Fecha: 2026-08-20
>
> Es el más grande de los tres planes abiertos. Ver también
> [plan-conversion-de-formatos.md](plan-conversion-de-formatos.md) y
> [plan-carga-de-archivos.md](plan-carga-de-archivos.md).

## Qué se quiere lograr

Que un cliente suba varios documentos en un mismo pedido y pueda configurar cada
uno por separado: uno a color, otro en blanco y negro, otro a doble faz.

## Qué hay hoy

**El sistema rechaza más de un archivo**, explícitamente:

```python
if len(files) != 1:
    raise HTTPException(422, "un pedido de fotocopias lleva exactamente 1 archivo PDF")
```

Y más de fondo: **las opciones pertenecen al pedido, no al documento.** El modelo
`PedidoFotocopias` tiene *un* `opciones` y *un* `rango` para todo el pedido.

La tabla `files` sí admite varios archivos por pedido (se usa en `/fotos`), pero
no tiene dónde guardar la configuración de cada uno.

O sea: esto no es una pantalla nueva. Es un cambio en **cómo está modelado un
pedido**, y de ahí se propaga al contrato de la API, la base, el precio, el
despacho a la impresora y el panel de operador.

---

## LA decisión que hay que tomar primero

**¿Los tramos de precio se calculan por documento o sobre el total del pedido?**

Los precios bajan por cantidad (1-19 páginas: $200 · 20-99: $150 · 100+: $130).
Con varios documentos hay que decidir si esa cantidad se cuenta por documento o
sumando todo.

Con números reales, tres documentos de 10 páginas en blanco y negro:

| Criterio | Precio |
|---|---|
| Cada documento con su propio tramo | **$6.000** |
| Sumando los tres en un solo tramo | **$4.500** |

**Una diferencia del 25%.** No es un detalle técnico: es una decisión de negocio,
y define cómo se escribe el motor de precios.

### Recomendación: sumar

Por dos razones:

1. **Es lo que el cliente espera.** Piensa "estoy imprimiendo 30 páginas", no
   "estoy haciendo tres pedidos".
2. **Si no, el precio depende de un detalle arbitrario.** Quien tenga su trabajo
   partido en tres archivos pagaría 25% más que quien lo tenga en uno solo, por
   el mismo trabajo. En cuanto un cliente lo note, es un reclamo con razón.

### La complicación: no todo se puede sumar

Los tramos dependen del color, las caras y el tamaño: un documento a color y uno
en blanco y negro usan **tablas de precios distintas**. No se pueden sumar entre
sí.

Propuesta: **sumar dentro de cada combinación de opciones.** Un pedido con dos
documentos B&N y uno a color se cotiza como dos líneas: las páginas B&N por un
lado, las de color por el otro, cada una con su tramo.

Es además la forma en que una imprenta cotiza a mano, y encaja con el concepto de
"línea" que el motor de precios ya tiene.

---

## Cambios en el backend

### Modelo y contrato

Las opciones pasan a ser **por documento**. El pedido tendría una lista:

```
documentos: [
  { archivo, opciones: {color, caras, copias, tamano}, rango },
  { archivo, opciones: {...}, rango },
]
```

Es un cambio incompatible con el contrato actual. Como la web y el backend se
despliegan por separado, **hay que soportar las dos formas durante la transición**
o coordinar los dos despliegues al mismo tiempo.

### Base de datos

La tabla `files` necesita guardar la configuración y las páginas de cada
documento. Migración nueva en `MIGRACIONES` (el mecanismo ya existe).

### Precio

`pricing.py` pasa a recibir varios documentos y agrupar por combinación de
opciones. Los 27 tests actuales siguen valiendo (un documento es el caso de uno
solo), y hay que sumar los casos de agrupación.

**Recordar:** el motor de precios está espejado en `PrintOptions.jsx`. Si cambia
uno hay que cambiar el otro — ya está anotado como trampa conocida en `ESTADO.md`.

### Despacho a la impresora

Hoy se despacha **solo el primer archivo**:

```python
"SELECT id, stored_path FROM files WHERE order_id = ? ORDER BY id LIMIT 1"
```

Pasa a recorrer todos, con un despacho por documento y sus propias opciones. Cada
uno deja su fila en `dispatch_log`, que ya tiene `file_id`.

**Caso a resolver:** si un documento se imprime bien y otro falla, el pedido no
está ni "impreso" ni "fallado". Hay que decidir qué estado toma y cómo se le
muestra al operador.

---

## La web

La idea de las solapas es buena: cada documento con su propia configuración,
visible de a una. Tres observaciones antes de dibujarla.

**1. En el celular, las solapas se rompen.** Con cinco o seis documentos, los
títulos no entran. Como la mayoría de los clientes entra desde el teléfono,
conviene una **lista donde cada documento se despliega** al tocarlo. En pantalla
grande puede verse como solapas; en chica, como lista. Misma información, dos
formas.

**2. Configurar cada documento a mano es tedioso.** Quien sube cinco apuntes
para la facultad los quiere todos igual. Propuesta: **una configuración general
que se aplica a todos por defecto, y la posibilidad de cambiar los que hagan
falta.** El caso común queda en un solo paso y el caso raro sigue siendo posible.
Esto además hace que la pantalla actual no cambie para quien sube un solo
archivo, que es lo que pedías.

**3. El resumen tiene que mostrar el desglose.** Si el precio sale de sumar
grupos de documentos, el cliente tiene que poder ver de dónde sale, o va a
desconfiar.

---

## El límite de tamaño, revisado

El techo de Cloudflare (100 MB en plan gratuito) aplica **a la petición
completa**, no a cada archivo. Así que con varios documentos el límite tiene que
ser sobre **la suma**, no sobre cada uno.

Eso cambia lo escrito en `plan-carga-de-archivos.md`: el aviso en la web pasa a
ser "hasta 95 MB en total", y la barra de progreso debería mostrar cuánto se está
usando a medida que se agregan documentos.

---

## El panel de operador

Hoy cada pedido muestra un documento. Con varios hay que mostrar la lista y la
configuración de cada uno, porque **es lo que el operador necesita para saber qué
está saliendo por la impresora**. Es trabajo adicional, chico comparado con el
resto, pero no se puede omitir: sin eso, quien atiende no sabe qué contiene el
pedido que está despachando.

---

## Tamaño y orden

Es el más grande de los tres planes. Toca modelo, contrato, base, precios,
despacho, web y panel de operador.

**Dependencias con los otros planes:**

- Conviene hacerlo **después** de la conversión de formatos: si no, habría que
  rehacer la pantalla de carga dos veces.
- El límite de tamaño hay que definirlo **sobre el total** desde el principio,
  así que ese detalle del otro plan conviene ajustarlo ya.

**Decisiones que faltan, en orden de importancia:**

1. **¿Los tramos se suman entre documentos o van por documento?** (25% de
   diferencia — bloquea el motor de precios)
2. ¿Configuración general aplicada a todos, con excepciones? (recomendado)
3. ¿Qué estado toma un pedido donde un documento imprimió y otro no?
