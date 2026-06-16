const PRICE = { byn: 10, color: 25 };
const A3_SURCHARGE = 1.5;

const PrintOptions = ({ pages, options, onChange }) => {
  const set = (key, value) => onChange({ ...options, [key]: value });

  return (
    <article className="p-6 md:p-8 bg-amber-50 shadow-xl rounded-sm relative overflow-hidden">
      <div className="absolute top-0 w-20 h-6 -translate-x-1/2 -translate-y-3 left-1/2 bg-white/60 -rotate-1 md:w-24 md:h-8" />
      <h2 className="mb-6 text-[10px] font-black tracking-[0.3em] uppercase text-stone-500/60 text-center">
        Opciones de Impresión
      </h2>

      <div className="space-y-5">
        {/* Color */}
        <fieldset>
          <legend className="mb-2 text-xs font-bold uppercase tracking-widest text-stone-500">Color</legend>
          <div className="flex gap-3">
            {[
              { value: 'byn', label: 'B/N', sub: '$10/pág' },
              { value: 'color', label: 'Color', sub: '$25/pág' },
            ].map(({ value, label, sub }) => (
              <button
                key={value}
                type="button"
                onClick={() => set('color', value)}
                className={`flex-1 py-3 rounded-xl border-2 text-sm font-bold transition-all ${
                  options.color === value
                    ? 'border-amber-500 bg-amber-200 text-amber-900'
                    : 'border-stone-200 bg-white text-stone-600 hover:border-amber-300'
                }`}
              >
                {label}
                <span className="block text-[10px] font-normal mt-0.5 opacity-70">{sub}</span>
              </button>
            ))}
          </div>
        </fieldset>

        {/* Caras */}
        <fieldset>
          <legend className="mb-2 text-xs font-bold uppercase tracking-widest text-stone-500">Caras</legend>
          <div className="flex gap-3">
            {[
              { value: 'simple', label: 'Simple faz' },
              { value: 'doble', label: 'Doble faz' },
            ].map(({ value, label }) => (
              <button
                key={value}
                type="button"
                onClick={() => set('caras', value)}
                className={`flex-1 py-3 rounded-xl border-2 text-sm font-bold transition-all ${
                  options.caras === value
                    ? 'border-amber-500 bg-amber-200 text-amber-900'
                    : 'border-stone-200 bg-white text-stone-600 hover:border-amber-300'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </fieldset>

        {/* Tamaño */}
        <fieldset>
          <legend className="mb-2 text-xs font-bold uppercase tracking-widest text-stone-500">Tamaño</legend>
          <div className="flex gap-3">
            {[
              { value: 'A4', label: 'A4', sub: 'estándar' },
              { value: 'A3', label: 'A3', sub: '+50% recargo' },
            ].map(({ value, label, sub }) => (
              <button
                key={value}
                type="button"
                onClick={() => set('tamano', value)}
                className={`flex-1 py-3 rounded-xl border-2 text-sm font-bold transition-all ${
                  options.tamano === value
                    ? 'border-amber-500 bg-amber-200 text-amber-900'
                    : 'border-stone-200 bg-white text-stone-600 hover:border-amber-300'
                }`}
              >
                {label}
                <span className="block text-[10px] font-normal mt-0.5 opacity-70">{sub}</span>
              </button>
            ))}
          </div>
        </fieldset>

        {/* Copias */}
        <div>
          <label className="block mb-2 text-xs font-bold uppercase tracking-widest text-stone-500">
            Cantidad de copias
          </label>
          <input
            type="number"
            min={1}
            value={options.copias}
            onChange={(e) => set('copias', Math.max(1, parseInt(e.target.value) || 1))}
            className="w-full px-4 py-3 text-sm font-bold border-2 border-stone-200 rounded-xl bg-white text-stone-700 focus:outline-none focus:border-amber-400 transition-colors"
          />
        </div>

        {/* Precio */}
        <div className="mt-2 pt-4 border-t border-amber-200">
          <div className="flex justify-between items-center">
            <span className="text-xs font-bold uppercase tracking-widest text-stone-400">Precio estimado</span>
            <span className="text-2xl font-black text-amber-700">
              ${calcPrice(pages, options).toLocaleString('es-AR')}
            </span>
          </div>
          <p className="text-[10px] text-stone-400 mt-1 text-right">
            {pages} págs · {options.caras === 'doble' ? `${Math.ceil(pages / 2)} hojas (doble faz)` : `${pages} hojas`} · {options.copias} cop. · {options.tamano}
          </p>
        </div>
      </div>
    </article>
  );
};

export const calcPrice = (pages, options) => {
  const pricePer = options.color === 'color' ? PRICE.color : PRICE.byn;
  const sheets = options.caras === 'doble' ? Math.ceil(pages / 2) : pages;
  const sizeMultiplier = options.tamano === 'A3' ? A3_SURCHARGE : 1;
  return Math.round(sheets * options.copias * pricePer * sizeMultiplier);
};

export default PrintOptions;
