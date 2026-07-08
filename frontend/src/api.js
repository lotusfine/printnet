// Cliente del backend PrintNet (backend-printnet, FastAPI).
// En local no hace falta configurar nada: apunta a http://localhost:8000.
export const PRINTNET_API =
  import.meta.env.VITE_PRINTNET_API ?? 'http://localhost:8000';

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
