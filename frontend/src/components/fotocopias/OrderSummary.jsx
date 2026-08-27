import { calcPrecioPedido } from '../../precio';

const TRAMO = (cantidad) => {
  if (cantidad <= 19) return '1 a 19';
  if (cantidad <= 99) return '20 a 99';
  return '100 o más';
};

const OrderSummary = ({ documentos, cotizables, onPay, enviando = false, bloqueado = false }) => {
  // Solo se cotiza lo que está completo: nunca se muestra un precio basado en
  // un número que no conocemos.
  const listos = (cotizables || []).filter(Boolean);
  const precio = calcPrecioPedido(listos);
  const hayAlgo = listos.length > 0;

  const conError = documentos.filter((d) => d.estado === 'error');
  const contando = documentos.filter((d) => d.estado === 'contando');
  const sinConfigurar = documentos.length - listos.length - conError.length - contando.length;

  return (
    <article className="p-6 md:p-8 bg-stone-50 shadow-xl rounded-sm relative overflow-hidden">
      <div className="absolute top-0 w-20 h-6 -translate-x-1/2 -translate-y-3 left-1/2 bg-white/60 rotate-2 md:w-24 md:h-8" />
      <h2 className="mb-6 text-[10px] font-black tracking-[0.3em] uppercase text-stone-500/60 text-center">
        Resumen del pedido
      </h2>

      {!documentos.length ? (
        <p className="text-sm text-center text-stone-400 italic py-6">
          Subí tus documentos para ver el resumen
        </p>
      ) : (
        <>
          <div className="space-y-1 mb-4">
            {documentos.map((doc, i) => {
              const linea = precio.lineas[listos.indexOf(cotizables[i])];
              return (
                <div key={doc.id} className="flex justify-between items-start gap-3 py-1.5 border-b border-stone-100 last:border-0">
                  <span className="text-xs text-stone-500 truncate flex-1" title={doc.name}>
                    {doc.name}
                  </span>
                  <span className={`text-sm font-bold shrink-0 ${
                    doc.estado === 'error' ? 'text-red-500'
                      : cotizables[i] ? 'text-stone-700' : 'text-stone-400'
                  }`}>
                    {doc.estado === 'error'
                      ? 'con problema'
                      : doc.estado === 'contando'
                        ? 'leyendo…'
                        : cotizables[i]
                          ? `$${linea.subtotal.toLocaleString('es-AR')}`
                          : 'sin configurar'}
                  </span>
                </div>
              );
            })}
          </div>

          {hayAlgo && (
            <div className="mb-4 pt-3 border-t border-stone-200">
              <div className="flex justify-between items-center text-xs text-stone-500">
                <span>{precio.cantidadTotal} {precio.cantidadTotal === 1 ? 'hoja' : 'hojas'} en total</span>
                <span>tramo {TRAMO(precio.cantidadTotal)}</span>
              </div>
              {documentos.length > 1 && (
                <p className="mt-1 text-[10px] text-stone-400">
                  El descuento se calcula sobre el total del pedido, así que juntar
                  documentos sale más barato que pedirlos por separado.
                </p>
              )}
              <div className="flex justify-between items-baseline mt-3">
                <span className="text-xs font-bold uppercase tracking-widest text-stone-400">Total</span>
                <span className="text-3xl font-black text-stone-800">
                  ${precio.total.toLocaleString('es-AR')}
                </span>
              </div>
            </div>
          )}

          {(conError.length > 0 || sinConfigurar > 0 || contando.length > 0) && (
            <p className="mb-3 text-xs font-bold text-amber-700 text-center">
              {conError.length > 0
                ? `Quitá o reemplazá ${conError.length === 1 ? 'el documento con problema' : `los ${conError.length} documentos con problema`} para continuar.`
                : contando.length > 0
                  ? 'Esperando a que se lean los documentos…'
                  : `Falta configurar ${sinConfigurar} ${sinConfigurar === 1 ? 'documento' : 'documentos'}.`}
            </p>
          )}
        </>
      )}

      <button
        type="button"
        onClick={onPay}
        disabled={bloqueado || enviando || !documentos.length}
        className="w-full py-4 rounded-xl bg-amber-500 hover:bg-amber-400 active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed disabled:active:scale-100 text-white font-black text-sm uppercase tracking-widest transition-all shadow-md shadow-amber-500/20"
      >
        {enviando ? 'Enviando pedido…' : 'Pagar con MercadoPago'}
      </button>
    </article>
  );
};

export default OrderSummary;
