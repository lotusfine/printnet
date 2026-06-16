import { calcPrice } from './PrintOptions';

const LABEL = {
  color: { byn: 'Blanco y Negro', color: 'Color' },
  caras: { simple: 'Simple faz', doble: 'Doble faz' },
};

const Row = ({ label, value }) => (
  <div className="flex justify-between items-center py-1.5 border-b border-stone-100 last:border-0">
    <span className="text-xs font-bold uppercase tracking-widest text-stone-400">{label}</span>
    <span className="text-sm font-bold text-stone-700">{value}</span>
  </div>
);

const OrderSummary = ({ fileInfo, options }) => {
  const ready = !!fileInfo;
  const total = ready ? calcPrice(fileInfo.pages, options) : 0;

  const handlePay = () => {
    alert('Integración de pago próximamente');
  };

  return (
    <article className="p-6 md:p-8 bg-stone-50 shadow-xl rounded-sm relative overflow-hidden">
      <div className="absolute top-0 w-20 h-6 -translate-x-1/2 -translate-y-3 left-1/2 bg-white/60 rotate-2 md:w-24 md:h-8" />
      <h2 className="mb-6 text-[10px] font-black tracking-[0.3em] uppercase text-stone-500/60 text-center">
        Resumen del Pedido
      </h2>

      {!ready ? (
        <p className="text-sm text-center text-stone-400 italic py-6">
          Subí un PDF para ver el resumen
        </p>
      ) : (
        <div className="space-y-1 mb-6">
          <Row label="Archivo" value={<span className="truncate max-w-[160px] block text-right">{fileInfo.name}</span>} />
          <Row label="Páginas" value={fileInfo.pages} />
          <Row label="Color" value={LABEL.color[options.color]} />
          <Row label="Caras" value={LABEL.caras[options.caras]} />
          <Row label="Tamaño" value={options.tamano} />
          <Row label="Copias" value={options.copias} />
          {options.caras === 'doble' && (
            <Row label="Hojas a imprimir" value={Math.ceil(fileInfo.pages / 2)} />
          )}
        </div>
      )}

      <div className="pt-4 border-t border-stone-200 flex justify-between items-center mb-6">
        <span className="text-xs font-black uppercase tracking-widest text-stone-500">Total</span>
        <span className="text-3xl font-black text-amber-700">
          {ready ? `$${total.toLocaleString('es-AR')}` : '—'}
        </span>
      </div>

      <button
        onClick={handlePay}
        disabled={!ready}
        className={`
          w-full py-4 rounded-xl font-black text-sm uppercase tracking-widest transition-all duration-200 shadow-md
          ${ready
            ? 'bg-amber-500 hover:bg-amber-600 active:scale-95 text-white'
            : 'bg-stone-200 text-stone-400 cursor-not-allowed'}
        `}
      >
        Pagar con MercadoPago
      </button>
      {!ready && (
        <p className="text-[10px] text-center text-stone-400 mt-2">Subí un archivo para continuar</p>
      )}
    </article>
  );
};

export default OrderSummary;
