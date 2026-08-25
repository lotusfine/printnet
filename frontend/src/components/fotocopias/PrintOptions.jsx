// Espejo de backend-printnet/pricing.py — mantener sincronizados.
// Tramos por cantidad, PLANOS (no marginales): el precio del tramo en el que
// cae la cantidad total de la línea se aplica a todas las unidades.
// Cada tramo es [tope incluido (null = en adelante), precio unitario].
const TRAMOS = {
  'byn|simple': [[19, 200], [99, 150], [null, 130]],
  'byn|doble': [[49, 200], [null, 150]],
  'color|simple': [[19, 400], [null, 300]],
  'color|doble': [[19, 600], [null, 450]],
};
const A3_SURCHARGE = 1.5;
const ANILLADO_HASTA_100 = 2000;
const ANILLADO_MAS_100 = 3500;

const precioUnitario = (color, caras, cantidad) => {
  const tramos = TRAMOS[`${color}|${caras}`];
  const tramo = tramos.find(([tope]) => tope === null || cantidad <= tope);
  return tramo[1];
};

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
              { value: 'byn', label: 'B/N', sub: 'desde $130' },
              { value: 'color', label: 'Color', sub: 'desde $300' },
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

        {/* Anillado */}
        <fieldset>
          <legend className="mb-2 text-xs font-bold uppercase tracking-widest text-stone-500">Terminación</legend>
          <button
            type="button"
            onClick={() => set('anillado', !options.anillado)}
            className={`w-full flex items-center gap-3 py-3 px-4 rounded-xl border-2 text-sm font-bold transition-all text-left ${
              options.anillado
                ? 'border-amber-500 bg-amber-200 text-amber-900'
                : 'border-stone-200 bg-white text-stone-600 hover:border-amber-300'
            }`}
          >
            <span
              className={`w-5 h-5 rounded-md border-2 flex items-center justify-center shrink-0 transition-colors ${
                options.anillado ? 'border-amber-600 bg-amber-600' : 'border-stone-300 bg-white'
              }`}
            >
              {options.anillado && (
                <svg xmlns="http://www.w3.org/2000/svg" className="w-3.5 h-3.5 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={3}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                </svg>
              )}
            </span>
            <span>
              Anillado
              <span className="block text-[10px] font-normal mt-0.5 opacity-70">
                $2.000 hasta 100 hojas · $3.500 más de 100
              </span>
            </span>
          </button>
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

        {/* Precio — solo cuando sabemos cuántas páginas tiene el documento.
            Sin ese dato no hay precio posible, y mostrar uno inventado fue
            exactamente el error que llegaba al cliente. */}
        <div className="mt-2 pt-4 border-t border-amber-200">
          {pages == null ? (
            <p className="text-xs text-stone-400 text-center py-2">
              Subí tu documento para ver el precio.
            </p>
          ) : (
            <>
              <div className="flex justify-between items-center">
                <span className="text-xs font-bold uppercase tracking-widest text-stone-400">Precio estimado</span>
                <span className="text-2xl font-black text-amber-700">
                  ${calcPrice(pages, options).toLocaleString('es-AR')}
                </span>
              </div>
              <p className="text-[10px] text-stone-400 mt-1 text-right">
                {(() => {
                  const hojas = options.caras === 'doble' ? Math.ceil(pages / 2) : pages;
                  const pl = (n, sing, plur) => `${n} ${n === 1 ? sing : plur}`;
                  const detalleHojas = options.caras === 'doble'
                    ? `${pl(hojas, 'hoja', 'hojas')} (doble faz)`
                    : pl(hojas, 'hoja', 'hojas');
                  return `${pl(pages, 'página', 'páginas')} · ${detalleHojas} · ${pl(options.copias, 'copia', 'copias')} · ${options.tamano}`;
                })()}
              </p>
              <p className="text-[10px] text-stone-400 text-right">
                {(() => {
                  const hojas = options.caras === 'doble' ? Math.ceil(pages / 2) : pages;
                  const total = hojas * options.copias;
                  const unidad = options.caras === 'doble'
                    ? (total === 1 ? 'hoja' : 'hojas')
                    : (total === 1 ? 'copia' : 'copias');
                  return `${total} ${unidad} × $${precioUnitario(options.color, options.caras, total).toLocaleString('es-AR')} c/u`;
                })()}
              </p>
            </>
          )}
        </div>
      </div>
    </article>
  );
};

export const calcPrice = (pages, options) => {
  // Hojas físicas de UNA copia (en doble faz entran 2 carillas por hoja)
  const sheetsPerCopy = options.caras === 'doble' ? Math.ceil(pages / 2) : pages;
  // El tramo se evalúa sobre el total de la línea, no sobre una sola copia
  const totalUnits = sheetsPerCopy * options.copias;

  const unitPrice = precioUnitario(options.color, options.caras, totalUnits);
  const sizeMultiplier = options.tamano === 'A3' ? A3_SURCHARGE : 1;
  let total = Math.round(totalUnits * unitPrice * sizeMultiplier);

  if (options.anillado) {
    total += options.copias * (sheetsPerCopy <= 100 ? ANILLADO_HASTA_100 : ANILLADO_MAS_100);
  }
  return total;
};

export default PrintOptions;
