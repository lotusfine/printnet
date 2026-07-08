// Anillado se movió a /fotocopias (donde tiene precio automático).
// Plastificado: $1.400 hoja A4, $700 media hoja · Corte: $500 hoja A4
// (precios de referencia — los pedidos de /fotos se cotizan a mano).
export const TERMINACIONES = ['Plastificado', 'Corte'];

const FinishOptions = ({ terminaciones, onToggle }) => (
  <article className="p-6 md:p-8 bg-purple-50 shadow-xl rounded-sm relative overflow-hidden">
    <div className="absolute top-0 w-20 h-6 -translate-x-1/2 -translate-y-3 left-1/2 bg-white/60 -rotate-1 md:w-24 md:h-8" />
    <h2 className="mb-2 text-[10px] font-black tracking-[0.3em] uppercase text-stone-500/60 text-center">
      Servicios de Terminación
    </h2>
    <p className="mb-6 text-xs italic text-stone-400 text-center">Opcionales</p>

    <div className="space-y-3">
      {TERMINACIONES.map((t) => {
        const active = terminaciones.includes(t);
        return (
          <button
            key={t}
            type="button"
            onClick={() => onToggle(t)}
            className={`
              w-full flex items-center gap-3 py-3 px-4 rounded-xl border-2 text-sm font-bold transition-all text-left
              ${active
                ? 'border-purple-500 bg-purple-200 text-purple-900'
                : 'border-stone-200 bg-white text-stone-600 hover:border-purple-300'}
            `}
          >
            <span
              className={`
                w-5 h-5 rounded-md border-2 flex items-center justify-center shrink-0 transition-colors
                ${active ? 'border-purple-600 bg-purple-600' : 'border-stone-300 bg-white'}
              `}
            >
              {active && (
                <svg xmlns="http://www.w3.org/2000/svg" className="w-3.5 h-3.5 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={3}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                </svg>
              )}
            </span>
            {t}
          </button>
        );
      })}
    </div>
  </article>
);

export default FinishOptions;
