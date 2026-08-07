// Cliente del backend PrintNet (backend-printnet, FastAPI).
// La URL se resuelve en config.js: editable en el servidor sin recompilar.
export { PRINTNET_API } from './config';
import { PRINTNET_API } from './config';

const formatearError = (body) => {
  const d = body?.detail;
  if (!d) return 'No se pudo conectar con el servidor';
  if (typeof d === 'string') return d;
  if (Array.isArray(d)) return d.map((e) => e.error ?? e.msg ?? String(e)).join(' · ');
  return JSON.stringify(d);
};

const parse = async (res) => {
  const body = await res.json().catch(() => null);
  if (!res.ok) throw new Error(formatearError(body));
  return body;
};

/** Crea un pedido (fotocopias o fotos). `files` son objetos File reales. */
export async function crearPedido(datos, files) {
  const fd = new FormData();
  fd.append('datos', JSON.stringify(datos));
  for (const f of files) fd.append('files', f);
  return parse(await fetch(`${PRINTNET_API}/orders`, { method: 'POST', body: fd }));
}

/** Cuenta las páginas reales de un PDF sin crear pedido (para el precio previo). */
export async function contarPaginas(file) {
  const fd = new FormData();
  fd.append('file', file);
  return parse(await fetch(`${PRINTNET_API}/orders/paginas`, { method: 'POST', body: fd }));
}

/** Estado público de un pedido por token. */
export async function consultarEstado(token) {
  return parse(await fetch(`${PRINTNET_API}/orders/status/${token}`));
}

/** Listado de pedidos para el admin. */
export async function listarPedidosAdmin(estado) {
  const qs = estado ? `?estado=${estado}` : '';
  return parse(await fetch(`${PRINTNET_API}/admin/orders${qs}`));
}

/** Cambia el estado de un pedido (transiciones validadas por el backend). */
export async function cambiarEstadoPedido(id, estado) {
  return parse(
    await fetch(`${PRINTNET_API}/admin/orders/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ estado }),
    })
  );
}

/** Impresoras registradas en el backend. */
export async function listarImpresoras() {
  return parse(await fetch(`${PRINTNET_API}/admin/printers`));
}
