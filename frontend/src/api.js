// Cliente del backend PrintNet (backend-printnet, FastAPI).
// La URL se resuelve en config.js: editable en el servidor sin recompilar.
export { PRINTNET_API } from './config';
import { leerToken } from './adminAuth';
import { PRINTNET_API } from './config';

// Los endpoints /admin/* exigen este header. Sin él, el backend devuelve 401.
const cabecerasAdmin = () => {
  const token = leerToken();
  return token ? { 'X-Admin-Token': token } : {};
};

const formatearError = (body) => {
  const d = body?.detail;
  if (!d) return 'No se pudo conectar con el servidor';
  if (typeof d === 'string') return d;
  if (Array.isArray(d)) return d.map((e) => e.error ?? e.msg ?? String(e)).join(' · ');
  return JSON.stringify(d);
};

const parse = async (res) => {
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    // El código va en el error para que la UI distinga "no autorizado" de
    // "el servidor no responde": son problemas distintos y se arreglan
    // distinto, y confundirlos ya nos costó un rato de diagnóstico.
    const error = new Error(formatearError(body));
    error.status = res.status;
    throw error;
  }
  return body;
};

/** Crea un pedido (fotocopias o fotos). `files` son objetos File reales. */
export async function crearPedido(datos, files) {
  const fd = new FormData();
  fd.append('datos', JSON.stringify(datos));
  for (const f of files) fd.append('files', f);
  return parse(await fetch(`${PRINTNET_API}/orders`, { method: 'POST', body: fd }));
}

/** Crea un pedido de fotocopias con archivos ya subidos en partes. */
export async function crearPedidoConSubidas(datos, uploads) {
  const fd = new FormData();
  fd.append('datos', JSON.stringify(datos));
  fd.append('uploads', JSON.stringify(uploads));
  return parse(await fetch(`${PRINTNET_API}/orders`, { method: 'POST', body: fd }));
}

// ─── Subida en partes ────────────────────────────────────────────────
// Cloudflare corta las peticiones de más de 100 MB, así que el archivo viaja
// en pedazos (de 6 MB, lo decide el servidor) y se rearma en la notebook.
// Ver docs/plan-subida-en-partes.md.

// Espera entre reintentos de un pedazo. Con una conexión mala, reintentar
// 6 MB no cuesta nada; reintentar el archivo entero sería volver a empezar.
const ESPERAS_REINTENTO_MS = [1000, 2000, 4000, 8000, 15000];
const CADA_CUANTO_PREGUNTAR_MS = 2000;
const MAXIMO_PREPARANDO_MS = 10 * 60 * 1000;

const cancelado = () => new DOMException('cancelado', 'AbortError');

const dormir = (ms, signal) =>
  new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(cancelado());
      return;
    }
    const t = setTimeout(resolve, ms);
    signal?.addEventListener('abort', () => {
      clearTimeout(t);
      reject(cancelado());
    }, { once: true });
  });

// Un 4xx es el servidor diciendo que no (formato, tamaño): reintentar no lo
// cambia. Sin status (se cortó la red) o 5xx, vale la pena otro intento.
const reintentable = (e) =>
  e?.name !== 'AbortError' && (!e?.status || e.status >= 500 || e.status === 408 || e.status === 429);

const conReintentos = async (intento, signal) => {
  for (let i = 0; ; i++) {
    try {
      return await intento();
    } catch (e) {
      if (!reintentable(e) || i >= ESPERAS_REINTENTO_MS.length) throw e;
      await dormir(ESPERAS_REINTENTO_MS[i], signal);
    }
  }
};

// Un error cuyo mensaje ya está escrito para el cliente (no "Failed to fetch").
const errorParaCliente = (mensaje, status) => {
  const error = new Error(mensaje);
  error.status = status;
  error.paraCliente = true;
  return error;
};

/**
 * Sube un archivo en partes y espera a que el servidor lo prepare.
 * Devuelve { id, paginas, convertido }; el id es lo que va en el pedido.
 * `alAbrir(id)` avisa el id apenas existe, para poder borrar la subida si el
 * cliente quita el documento a la mitad.
 */
export async function subirArchivo(file, { alProgresar, alAbrir, signal } = {}) {
  const { id, parte_bytes: parteBytes, partes } = await conReintentos(async () =>
    parse(await fetch(`${PRINTNET_API}/uploads`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nombre: file.name, tamano_bytes: file.size, content_type: file.type || '' }),
      signal,
    })), signal);
  alAbrir?.(id);
  alProgresar?.({ fase: 'subiendo', enviado: 0, total: file.size });

  // Un pedazo a la vez: en paralelo no acelera cuando el cuello de botella es
  // la conexión del cliente o la del local, y complica los reintentos.
  for (let n = 0; n < partes; n++) {
    const pedazo = file.slice(n * parteBytes, (n + 1) * parteBytes);
    await conReintentos(async () =>
      parse(await fetch(`${PRINTNET_API}/uploads/${id}/partes/${n}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/octet-stream' },
        body: pedazo,
        signal,
      })), signal);
    alProgresar?.({ fase: 'subiendo', enviado: Math.min((n + 1) * parteBytes, file.size), total: file.size });
  }

  await conReintentos(async () =>
    parse(await fetch(`${PRINTNET_API}/uploads/${id}/completar`, { method: 'POST', signal })), signal);
  alProgresar?.({ fase: 'preparando' });

  // Juntar, convertir y contar corre en segundo plano en el servidor (puede
  // tardar más de lo que Cloudflare espera una respuesta): se pregunta.
  const limite = Date.now() + MAXIMO_PREPARANDO_MS;
  for (;;) {
    await dormir(CADA_CUANTO_PREGUNTAR_MS, signal);
    const est = await conReintentos(async () =>
      parse(await fetch(`${PRINTNET_API}/uploads/${id}`, { signal })), signal);
    if (est.estado === 'listo') return { id, paginas: est.paginas, convertido: est.convertido };
    if (est.estado === 'error') {
      throw errorParaCliente(est.error || 'No pudimos procesar tu documento.', 422);
    }
    if (Date.now() > limite) {
      throw errorParaCliente(
        'Tu documento está tardando demasiado en prepararse. Probá de nuevo o escribinos.', 408);
    }
  }
}

/** Estado de una subida: { estado, ... }, o null si ya no existe (venció). */
export async function estadoSubida(id) {
  const res = await fetch(`${PRINTNET_API}/uploads/${id}`);
  if (res.status === 404) return null;
  return parse(res);
}

/**
 * Le avisa al servidor que una subida ya no se va a usar, para que libere el
 * disco en el momento. Sin esperar respuesta ni fallar: si no llega, la
 * limpieza del servidor la borra igual más tarde.
 */
export function descartarSubida(id) {
  if (!id) return;
  fetch(`${PRINTNET_API}/uploads/${id}`, { method: 'DELETE' }).catch(() => {});
}

/** Estado público de un pedido por token. */
export async function consultarEstado(token) {
  return parse(await fetch(`${PRINTNET_API}/orders/status/${token}`));
}

/** Listado de pedidos para el admin. */
export async function listarPedidosAdmin(estado) {
  const qs = estado ? `?estado=${estado}` : '';
  return parse(
    await fetch(`${PRINTNET_API}/admin/orders${qs}`, { headers: cabecerasAdmin() })
  );
}

/** Cambia el estado de un pedido (transiciones validadas por el backend). */
export async function cambiarEstadoPedido(id, estado) {
  return parse(
    await fetch(`${PRINTNET_API}/admin/orders/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', ...cabecerasAdmin() },
      body: JSON.stringify({ estado }),
    })
  );
}

/** Vuelve a mandar un pedido a la impresora. Sin `fileId`, todos sus documentos. */
export async function reimprimirPedido(id, fileId) {
  const qs = fileId ? `?file_id=${fileId}` : '';
  return parse(
    await fetch(`${PRINTNET_API}/admin/orders/${id}/reimprimir${qs}`, {
      method: 'POST',
      headers: cabecerasAdmin(),
    })
  );
}

/** Impresoras registradas en el backend. */
export async function listarImpresoras() {
  return parse(
    await fetch(`${PRINTNET_API}/admin/printers`, { headers: cabecerasAdmin() })
  );
}
