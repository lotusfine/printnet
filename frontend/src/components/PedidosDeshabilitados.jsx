const ACCENTS = {
  amber: { card: 'bg-orange-50', icon: 'text-amber-500', tape: 'rotate-2' },
  lila: { card: 'bg-purple-50', icon: 'text-purple-500', tape: '-rotate-2' },
};

/**
 * Aviso que reemplaza al formulario cuando el backend de pedidos todavía no
 * está configurado (ver PEDIDOS_HABILITADOS en config.js).
 */
const PedidosDeshabilitados = ({ accent = 'amber' }) => {
  const a = ACCENTS[accent];

  return (
    <article className={`w-full max-w-2xl mx-auto p-6 md:p-10 ${a.card} shadow-xl rounded-sm relative overflow-hidden text-center`}>
      <div className={`absolute top-0 w-20 h-6 -translate-x-1/2 -translate-y-3 left-1/2 bg-white/60 ${a.tape} md:w-24 md:h-8`} />

      <svg xmlns="http://www.w3.org/2000/svg" className={`w-14 h-14 mx-auto mb-5 ${a.icon}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M11.42 15.17L17.25 21A2.652 2.652 0 0021 17.25l-5.877-5.877M11.42 15.17l2.496-3.03c.317-.384.74-.626 1.208-.766M11.42 15.17l-4.655 5.653a2.548 2.548 0 11-3.586-3.586l6.837-5.63m5.108-.233c.55-.164 1.163-.188 1.743-.14a4.5 4.5 0 004.486-6.336l-3.276 3.277a3.004 3.004 0 01-2.25-2.25l3.276-3.276a4.5 4.5 0 00-6.336 4.486c.091 1.076-.071 2.264-.904 2.95l-.102.085m-1.745 1.437L5.909 7.5H4.5L2.25 3.75l1.5-1.5L7.5 4.5v1.409l4.26 4.26m-1.745 1.437l1.745-1.437m6.615 8.206L15.75 15.75M4.867 19.125h.008v.008h-.008v-.008z" />
      </svg>

      <h2 className="text-2xl font-chalk md:text-3xl text-stone-700 mb-3">
        Pedidos online en preparación
      </h2>
      <p className="text-sm text-stone-500 max-w-md mx-auto mb-6">
        Estamos terminando de poner a punto el sistema para que puedas hacer tus
        pedidos desde acá. Mientras tanto, escribinos y lo coordinamos.
      </p>

      <a
        href="https://wa.me/5492214633147?text=Hola%20Glaxara!%20Quería%20hacer%20un%20pedido%20de%20impresiones..."
        target="_blank"
        rel="noreferrer"
        className="inline-block px-8 py-3 text-xs font-bold text-white uppercase tracking-widest transition-all rounded-xl shadow-md bg-green-600 hover:bg-green-700 active:scale-95"
      >
        Consultar por WhatsApp
      </a>
    </article>
  );
};

export default PedidosDeshabilitados;
