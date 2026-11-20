# PrintNet — Librería Glaxara

**Antes de hacer o proponer cualquier cosa, leé [`ESTADO.md`](ESTADO.md).** Es
el traspaso entre sesiones: qué está terminado y verificado, qué falta y por
qué, las decisiones ya cerradas (no rediscutirlas) y las trampas que ya
costaron tiempo. El detalle técnico del backend está en
`backend-printnet/SPEC.md`.

**El sistema está en producción, cobrando con dinero real y en manos de gente
que atiende un mostrador.** Un cambio que rompe el formulario le aparece a un
cliente, no a un tester.

## Dónde está cada cosa

| Carpeta | Qué es |
|---|---|
| `backend-printnet/` | **El backend real.** FastAPI + SQLite, se compila a un `.exe` que corre como servicio en la notebook del local. |
| `frontend/` | La web (React + Vite). Se compila y se sube a cPanel. |
| `backend/` | **Sobra: proyecto Java/Maven de una versión anterior del sitio.** Nada que ver con PrintNet. No tocar. |
| `docs/` | Planes de las tandas de mejoras ya implementadas. |

## Convenciones del proyecto

**Todo en español, voseo.** Código, comentarios, mensajes de commit, mensajes
de error que ve el cliente y conversación.

**Los comentarios explican el *por qué*, no el *qué*.** El patrón del
repositorio es dejar escrito el motivo de las decisiones raras, sobre todo las
que costaron una vuelta de diagnóstico (ej.: por qué `print_dispatch.py` no
emite `paper=`). Si vas a sacar un comentario así, fijate primero qué problema
documenta.

**Los tests son scripts pelados, sin pytest y sin httpx.** Cada uno tiene un
helper `check()` y se corre directo. Esto es a propósito: la notebook del local
clona este repo y no queremos instalarle dependencias de desarrollo.

```bash
cd backend-printnet && .venv/bin/python test_pricing.py     # y el resto de test_*.py
cd backend-printnet && .venv/bin/python verificar_espejo_precios.py   # necesita Node
```

**Los precios están espejados entre `pricing.py` y `frontend/src/precio.js`.**
Si cambiás uno, cambiá el otro y corré `verificar_espejo_precios.py`, que corre
el motor JS con Node y compara contra Python caso por caso.

**En los `.ps1` nunca uses here-strings** y mantené CRLF + UTF-8 con BOM (ya
forzado por `.gitattributes`). PowerShell 5.1 —la que tiene la notebook— no
parsea here-strings en archivos con finales de línea de Unix, y falla con
errores de sintaxis que apuntan a líneas que son texto plano.

## Cómo se despliega (son dos caminos distintos)

**Backend:** `git pull` en la notebook (`C:\PrintNet\printnet`), recompilar si
cambió código Python, y copiar el `.exe` a `C:\PrintNet\servicio\` parando y
arrancando el servicio. Pasos exactos en `ESTADO.md`, punto 4.

**Frontend:** se compila y se sube **a mano** al Administrador de archivos de
cPanel. Ojo con dos cosas que ya fallaron: hay que **tildar "sobrescribir"** o
cPanel saltea el archivo sin avisar, y conviene subir **un archivo a la vez**.
Después de cada deploy hay que volver a poner la URL del backend en
`public_html/config.js`, porque la del repositorio está vacía.

## Trabajando con la notebook del local

El usuario está en una Mac y la notebook Windows está en la librería; relaya
los comandos a mano, a veces por WhatsApp. Entonces: **comandos de una sola
línea, uno por vez**, y esperar el resultado antes de mandar el siguiente.
Nada de here-strings ni de bloques de varias líneas.

## graphify

Herramienta de desarrollo interno, **solo en la Mac**: `graphify-out/` está en
`.gitignore` y nunca llega a la notebook del local. Es un grafo de conocimiento
que une el código (`backend-printnet/`, `frontend/`) con los documentos
(`ESTADO.md`, `SPEC.md`, `docs/`, `deploy/`), así una pregunta trae a la vez la
función y la decisión o la trampa documentada que la explica. `backend/` (el
Java viejo) quedó afuera a propósito.

Cómo usarlo:
- `ESTADO.md` se sigue leyendo primero; el grafo no lo reemplaza.
- Para ubicarte antes de tocar algo, `graphify query "<pregunta>"` (se puede
  preguntar en español). Para cómo se conectan dos cosas,
  `graphify path "<A>" "<B>"`; para un concepto puntual, `graphify explain "<X>"`.
  Devuelven un subgrafo chico, más barato que leer archivos enteros o grepear.
- **El grafo es un mapa, no la fuente de verdad.** Antes de editar, abrí el
  archivo real: las aristas `INFERRED`/`AMBIGUOUS` son inferencias, y los docs
  pueden estar viejos (ej.: `docs/plan-conversion-de-formatos.md` todavía llama
  "propuesto" a `document_convert.py`, que ya existe).
- `graphify-out/GRAPH_REPORT.md` solo para una mirada general de arquitectura.
- Los hooks de git actualizan el grafo solos en cada commit, pero **solo el
  código**. Si cambiaste `ESTADO.md`, `SPEC.md` o algún plan, corré
  `/graphify . --update` para que relea esos documentos.
- Si borraste código y `graphify update` se niega a achicar el grafo, es una
  protección: `graphify update . --force`.
