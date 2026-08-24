# Plan — aceptar cualquier formato de documento

> Estado: **propuesta, pendiente de confirmación**. No se escribió código todavía.
> Fecha: 2026-08-20

## Qué se quiere lograr

Que un cliente pueda subir un Word, un PowerPoint, un Excel o una imagen, y que
el sistema lo convierta a PDF, lo cotice y lo imprima — sin que tenga que
convertirlo él por su cuenta.

Hoy la web solo acepta PDF (`accept="application/pdf"` en el navegador, y un
rechazo con código 422 en el backend).

## Herramienta elegida: LibreOffice

```
soffice --headless --convert-to pdf --outdir <carpeta> <archivo>
```

**Por qué LibreOffice y no PDF24 Creator**, que fue la otra opción evaluada:

| | LibreOffice | PDF24 Creator |
|---|---|---|
| Línea de comandos | documentada, un comando | `-processJob` con un JSON no documentado |
| Pensado para | correr sin escritorio, en servidores | que una persona haga clic |
| Soporte de este uso | 15+ años, miles de servidores | [consulta sin responder desde 2015](https://help.pdf24.org/en/forums/topic/command-line-conversion/) |
| Procesa localmente | sí | sí |
| Gratis uso comercial | sí | sí |

El factor decisivo es que el backend va a correr como **servicio de Windows**,
sin sesión de usuario ni escritorio. Los programas de interfaz gráfica fallan en
ese contexto, y fallan en silencio.

Ambos comparten una limitación que no es de la herramienta sino del problema:
**la fidelidad no está garantizada.** Un PowerPoint con tipografías poco comunes
puede salir con el texto corrido. De ahí sale el requisito de la vista previa.

---

## Fase 0 — Verificar antes de programar (sin código)

**Esto va primero y puede cancelar todo lo demás.** Es barato y evita construir
sobre una suposición.

En la notebook:

1. Instalar LibreOffice.
2. Convertir a mano un `.pptx` real —de los que traen los clientes, no uno de
   prueba— y mirar el PDF resultante.
3. Medir cuánto tarda: la primera conversión y las siguientes.
4. Probar también un `.docx` y un `.xlsx`.

**Qué decide:** si la fidelidad es inaceptable para lo que imprime el negocio, o
si tarda demasiado, hay que replantear antes de escribir nada.

---

## Fase 1 — Conversión en el backend

**`document_convert.py`** (módulo nuevo), con la misma forma que
`print_dispatch.py`: un ejecutor inyectable para poder testear sin LibreOffice
instalado.

- `convertir_a_pdf(origen, destino) -> ResultadoConversion`
- Ningún camino de error propaga excepciones: LibreOffice ausente, formato no
  soportado, archivo corrupto, timeout. Todos devuelven un resultado con
  `ok=False` y un motivo legible.
- **Timeout obligatorio.** Un `soffice` colgado bloquearía el pedido; hay que
  matarlo y devolver error.
- **Un perfil propio por conversión.** LibreOffice no admite dos instancias
  compartiendo perfil: dos pedidos simultáneos se pisarían. Se resuelve con
  `-env:UserInstallation=file:///<carpeta temporal única>`.

**Formatos a aceptar** (los que LibreOffice maneja bien):
`.pdf` (sin convertir), `.doc`, `.docx`, `.odt`, `.rtf`, `.txt`, `.xls`,
`.xlsx`, `.ods`, `.csv`, `.ppt`, `.pptx`, `.odp`, y las imágenes que ya se
aceptan en `/fotos`.

**Base de datos:** la tabla `files` guarda hoy un solo `stored_path`. Hay que
agregar el archivo convertido sin perder el original —el cliente subió eso y hay
que poder mostrárselo o reimprimirlo—. Se hace con una migración nueva en
`MIGRACIONES` (el mecanismo ya existe).

**Tests:** cubrir la traducción de formatos, cada camino de error, el timeout, y
que un PDF no se convierta al pedazo (pasa derecho).

---

## Fase 2 — Una sola subida

Hoy **el archivo se sube dos veces**: una en `POST /orders/paginas` para contar
páginas y otra en `POST /orders` al crear el pedido. Hoy se nota poco; con
archivos de 100 MB y una conversión de por medio, el cliente esperaría dos veces
lo mismo.

Se reemplaza por un paso de **preparación**:

1. El cliente elige el archivo → se sube **una vez**.
2. El backend lo guarda, lo convierte si hace falta, cuenta las páginas y
   devuelve: cantidad de páginas, precio, y un link a la vista previa del PDF.
3. Al pagar, el pedido **referencia** ese archivo ya preparado, sin volver a
   subirlo.

Esto además es lo que hace posible la vista previa: el PDF convertido tiene que
existir en algún lado antes de que el cliente decida pagar.

**Requiere limpieza:** los archivos preparados que nunca se convierten en pedido
quedan ocupando disco. Hay que borrarlos pasado un plazo (por ejemplo 24 horas).

---

## Fase 3 — La web

1. **Aceptar cualquier archivo** en el recuadro de carga (hoy `accept="application/pdf"`).
2. **Aviso de formatos**, dentro del recuadro. Propuesta de texto:
   > Subí tu PDF, o cualquier documento de Word, Excel o PowerPoint —
   > lo convertimos a PDF automáticamente.
3. **Indicador de progreso** con los pasos reales, porque la espera puede ser de
   varios segundos: *Subiendo… → Convirtiendo a PDF… → Listo*.
4. **Vista previa del PDF convertido**, con un aviso:
   > Revisá que se vea bien antes de pagar. Las conversiones desde Word o
   > PowerPoint pueden mover el diseño.
5. **Errores claros**: si el formato no se puede convertir, decirlo con el
   nombre del archivo y sugerir que suba un PDF.

---

## Fase 4 — Que funcione como servicio

Cuando el backend corra como servicio de Windows (bajo `LocalSystem`, sin
escritorio ni carpeta de usuario), LibreOffice necesita:

- Una carpeta de perfil donde pueda escribir, indicada explícitamente. Sin eso
  no arranca y el error no dice por qué.
- Permisos de escritura sobre la carpeta temporal que se le pase.

Es la misma clase de problema que ya nos costó tiempo dos veces: con los
archivos del túnel de Cloudflare y con la configuración de SumatraPDF. Se
resuelve de entrada, no cuando falle.

---

## Riesgos y decisiones abiertas

**Seguridad.** LibreOffice va a abrir documentos que manda cualquiera por
internet. Es una superficie de ataque real: hay que **desactivar las macros** y
mantenerlo actualizado. No es motivo para no hacerlo, pero sí para hacerlo bien.

**Tiempo de espera.** Si una conversión tarda 20 segundos, el cliente se puede
ir. Hay que medirlo en la Fase 0 y, si es lento, avisar con el indicador de
progreso.

**Dos decisiones que faltan confirmar:**

1. **¿Vista previa antes de pagar?** Recomiendo que sí, enfáticamente: si la
   conversión corrió el diseño, es mejor que el cliente se entere antes de pagar
   y no cuando retira las hojas. Cuesta trabajo extra y obliga a la Fase 2.
2. **¿Qué pasa si la conversión falla?** Dos opciones:
   - **Rechazar** con un mensaje claro pidiendo que suba un PDF. Más simple, y
     el cliente resuelve solo.
   - **Aceptar como "requiere atención manual"**, para que lo resuelvan en el
     mostrador. No se pierde la venta, pero genera trabajo manual y el pedido no
     se puede cotizar automáticamente (sin páginas no hay precio).

---

## Orden y dependencias

```
Fase 0 (verificar)  ──►  Fase 1 (backend)  ──►  Fase 2 (una subida)  ──►  Fase 3 (web)
                                                                              │
                                              Fase 4 (servicio)  ◄────────────┘
```

La Fase 2 es la que habilita la vista previa. Si se decide **no** hacer vista
previa, la Fase 2 se puede saltear y el trabajo se reduce bastante — a costa de
que el cliente suba el archivo dos veces y pague sin ver el resultado.

---

## Fuera de alcance de este plan

Lo hablado en la misma sesión y pendiente aparte:

- Que la web deje de inventar "10 páginas" cuando no puede contarlas
  (`FALLBACK_PAGES` en `FileUpload.jsx`). **Es un error que hoy puede cobrar de
  más, y es más urgente que esto.**
- Validar el tamaño del archivo en la web antes de subirlo, y subir el límite de
  50 MB a 100 MB (techo de Cloudflare en el plan gratuito).
- Contar las páginas en el navegador, que resolvería el caso de DuckDuckGo.
