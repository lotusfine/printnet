import { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { consultarEstado } from '../api';

// Página pública de seguimiento. También es el destino de las back_urls de
// MercadoPago (success/failure/pending), así que puede llegar con query
// params de MP — el estado real siempre se lee del backend.
const ESTILO = {
  pendiente_pago: 'bg-yellow-100 text-yellow-800 border-yellow-300',
  pago_rechazado: 'bg-red-100 text-red-700 border-red-300',
  pendiente: 'bg-yellow-100 text-yellow-800 border-yellow-300',
  imprimiendo: 'bg-blue-100 text-blue-700 border-blue-300',
  listo: 'bg-green-100 text-green-700 border-green-300',
  entregado: 'bg-stone-100 text-stone-500 border-stone-300',
  cancelado: 'bg-stone-200 text-stone-500 border-stone-400',
};

const LABEL = {
  pendiente_pago: 'Esperando el pago',
  pago_rechazado: 'Pago rechazado',
  pendiente: 'Pendiente',
  imprimiendo: 'Imprimiendo',
  listo: '¡Listo para retirar!',
  entregado: 'Entregado',
  cancelado: 'Cancelado',
};

const DESCRIPCION = {
  pendiente_pago: 'Todavía no recibimos la confirmación del pago. Si ya pagaste, esta página se actualiza sola en unos segundos.',
  pago_rechazado: 'El pago no se pudo procesar. Podés volver a intentar creando el pedido de nuevo.',
  pendiente: 'Tu pedido está en cola y lo va a tomar un operador.',
  imprimiendo: 'Tu pedido se está imprimiendo.',
  listo: 'Te esperamos en Librería Glaxara para retirarlo.',
  entregado: 'Este pedido ya fue entregado. ¡Gracias!',
  cancelado: 'Este pedido fue cancelado.',
};

const Estado = () => {
  const { token } = useParams();
  const [pedido, setPedido] = useState(null);
  const [error, setError] = useState(null);

  const cargar = useCallback(() => {
    consultarEstado(token)
      .then((p) => { setPedido(p); setError(null); })
      .catch((e) => setError(e.message));
  }, [token]);

  useEffect(() => {
    cargar();
    const timer = setInterval(cargar, 10000);
    return () => clearInterval(timer);
  }, [cargar]);

  return (
    <section className="flex flex-col items-center space-y-8">
      <header className="text-center">
        <h1 className="text-4xl font-chalk md:text-6xl text-stone-800/90 mb-2">Tu Pedido</h1>
        <p className="text-base italic font-chalk text-stone-500 md:text-lg">
          Seguimiento en tiempo real
        </p>
      </header>

      {error && (
        <div className="w-full max-w-xl p-6 bg-red-50 border-2 border-red-200 rounded-sm shadow-xl text-center">
          <p className="text-sm font-bold text-red-600 mb-2">No encontramos el pedido</p>
          <p className="text-xs text-stone-500">{error}</p>
        </div>
      )}

      {!pedido && !error && (
        <div className="w-full max-w-xl h-48 bg-stone-200/50 rounded-xl animate-pulse" />
      )}

      {pedido && (
        <article className="w-full max-w-xl p-6 md:p-8 bg-yellow-50 shadow-xl rounded-sm relative overflow-hidden">
          <div className="absolute top-0 w-20 h-6 -translate-x-1/2 -translate-y-3 left-1/2 bg-white/60 rotate-2 md:w-24 md:h-8" />

          <div className="text-center mb-6">
            <span className={`inline-block px-4 py-2 rounded-full border-2 text-sm font-black uppercase tracking-widest ${ESTILO[pedido.estado] ?? ESTILO.pendiente}`}>
              {LABEL[pedido.estado] ?? pedido.estado}
            </span>
            <p className="mt-3 text-sm text-stone-500">{DESCRIPCION[pedido.estado] ?? ''}</p>
          </div>

          <dl className="space-y-2">
            <div className="flex justify-between gap-4 py-1.5 border-b border-yellow-100">
              <dt className="text-xs font-bold uppercase tracking-widest text-stone-400">Tipo</dt>
              <dd className="text-sm font-bold text-stone-700 capitalize">{pedido.tipo}</dd>
            </div>
            <div className="flex justify-between gap-4 py-1.5 border-b border-yellow-100">
              <dt className="text-xs font-bold uppercase tracking-widest text-stone-400 shrink-0">
                Archivo{pedido.archivos.length !== 1 ? 's' : ''}
              </dt>
              <dd className="text-sm font-bold text-stone-700 text-right min-w-0">
                {pedido.archivos.map((n) => (
                  <span key={n} className="block truncate">{n}</span>
                ))}
              </dd>
            </div>
            <div className="flex justify-between gap-4 py-1.5 border-b border-yellow-100">
              <dt className="text-xs font-bold uppercase tracking-widest text-stone-400">Total</dt>
              <dd className="text-lg font-black text-amber-700">
                {pedido.precio_total != null
                  ? `$${pedido.precio_total.toLocaleString('es-AR')}`
                  : 'A cotizar'}
              </dd>
            </div>
            <div className="flex justify-between gap-4 py-1.5">
              <dt className="text-xs font-bold uppercase tracking-widest text-stone-400 shrink-0">Código</dt>
              <dd className="text-xs font-mono font-bold text-stone-500 break-all text-right">{pedido.token}</dd>
            </div>
          </dl>
        </article>
      )}

      <Link
        to="/"
        className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-widest text-stone-500 hover:text-amber-700 transition-colors"
      >
        ← Volver al inicio
      </Link>
    </section>
  );
};

export default Estado;
