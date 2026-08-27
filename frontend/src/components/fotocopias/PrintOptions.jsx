import { calcPrecioPedido, paginasDelRango, precioUnitario } from '../../precio';
import { validateRango } from './FileUpload';

// Re-exportado para no romper a quien todavía importe calcPrice desde acá.
export { calcPrice } from '../../precio';

const OPCIONES = {
  color: [
    { valor: 'byn', etiqueta: 'Blanco y negro' },
    { valor: 'color', etiqueta: 'Color' },
  ],
  caras: [
    { valor: 'simple', etiqueta: 'Una faz' },
    { valor: 'doble', etiqueta: 'Doble faz' },
  ],
  tamano: [
    { valor: 'A4', etiqueta: 'A4' },
    { valor: 'A3', etiqueta: 'A3' },
  ],
};

const Grupo = ({ titulo, campo, opciones, valor, onElegir }) => (
  <fieldset>
    <legend className="mb-2 text-xs font-bold uppercase tracking-widest text-stone-500">
      {titulo}
    </legend>
    <div className="flex gap-3">
      {opciones.map(({ valor: v, etiqueta }) => (
        <button
          key={v}
          type="button"
          role="radio"
          aria-checked={valor === v}
          onClick={() => onElegir(campo, v)}
          className={`flex-1 py-3 px-2 rounded-xl border-2 text-sm font-bold transition-all ${
            valor === v
              ? 'border-amber-500 bg-amber-200 text-amber-900'
              : 'border-stone-200 bg-white text-stone-600 hover:border-amber-300'
          }`}
        >
          {etiqueta}
        </button>
      ))}
    </div>
  </fieldset>
);

const PrintOptions = ({ documento, cantidadDocumentos, onChange, onRangoChange, onAplicarATodos }) => {
  if (!documento) {
    return (
      <article className="p-6 md:p-8 bg-amber-50 shadow-xl rounded-sm relative overflow-hidden">
        <div className="absolute top-0 w-20 h-6 -translate-x-1/2 -translate-y-3 left-1/2 bg-white/60 rotate-1 md:w-24 md:h-8" />
        <h2 className="mb-6 text-[10px] font-black tracking-[0.3em] uppercase text-stone-500/60 text-center">
          Opciones de impresión
        </h2>
        <p className="text-sm text-center text-stone-400 italic py-6">
          Subí un documento para configurarlo.
        </p>
      </article>
    );
  }

  const { opciones, rango } = documento;
  const set = (campo, valor) => onChange({ ...opciones, [campo]: valor });

  const completo = opciones.color && opciones.caras && opciones.copias && opciones.tamano;
  const paginasACobrar = paginasDelRango(documento.paginas, rango);
  const rangoError = rango.modo === 'rango' ? validateRango(rango.valor) : null;

  // Precio de ESTE documento solo, como referencia. El total del pedido usa el
  // tramo de la suma y se muestra en el resumen: acá el número puede ser mayor.
  const suelto = completo && paginasACobrar != null
    ? calcPrecioPedido([{ paginas: paginasACobrar, opciones: { ...opciones, copias: Number(opciones.copias) } }])
    : null;

  return (
    <article className="p-6 md:p-8 bg-amber-50 shadow-xl rounded-sm relative overflow-hidden">
      <div className="absolute top-0 w-20 h-6 -translate-x-1/2 -translate-y-3 left-1/2 bg-white/60 rotate-1 md:w-24 md:h-8" />
      <h2 className="mb-1 text-[10px] font-black tracking-[0.3em] uppercase text-stone-500/60 text-center">
        Opciones de impresión
      </h2>
      <p className="mb-6 text-xs text-center text-stone-500 truncate" title={documento.name}>
        {documento.name}
      </p>

      {documento.estado === 'contando' ? (
        <p className="text-sm text-center text-stone-400 italic py-6">
          Esperando a que se lea el documento…
        </p>
      ) : (
        <div className="space-y-6">
          <Grupo titulo="Color" campo="color" opciones={OPCIONES.color} valor={opciones.color} onElegir={set} />
          <Grupo titulo="Caras" campo="caras" opciones={OPCIONES.caras} valor={opciones.caras} onElegir={set} />
          <Grupo titulo="Tamaño" campo="tamano" opciones={OPCIONES.tamano} valor={opciones.tamano} onElegir={set} />

          <fieldset>
            <legend className="mb-2 text-xs font-bold uppercase tracking-widest text-stone-500">
              Copias
            </legend>
            <input
              type="number"
              min="1"
              max="500"
              value={opciones.copias}
              placeholder="¿Cuántas?"
              onChange={(e) => set('copias', e.target.value)}
              className="w-full px-4 py-3 text-sm font-bold border-2 border-stone-200 rounded-xl bg-white text-stone-700 focus:outline-none focus:border-amber-400 transition-colors"
            />
          </fieldset>

          <fieldset>
            <legend className="mb-2 text-xs font-bold uppercase tracking-widest text-stone-500">
              Páginas a imprimir
            </legend>
            <div className="flex gap-3">
              {[
                { value: 'todas', label: 'Todas las páginas' },
                { value: 'rango', label: 'Rango específico' },
              ].map(({ value, label }) => (
                <button
                  key={value}
                  type="button"
                  role="radio"
                  aria-checked={rango.modo === value}
                  onClick={() => onRangoChange({ ...rango, modo: value })}
                  className={`flex-1 py-3 px-2 rounded-xl border-2 text-sm font-bold transition-all ${
                    rango.modo === value
                      ? 'border-amber-500 bg-amber-200 text-amber-900'
                      : 'border-stone-200 bg-white text-stone-600 hover:border-amber-300'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
            {rango.modo === 'rango' && (
              <div className="mt-3">
                <input
                  type="text"
                  value={rango.valor}
                  onChange={(e) => onRangoChange({ ...rango, valor: e.target.value })}
                  placeholder="Ej: 3-16"
                  className={`w-full px-4 py-3 text-sm font-bold border-2 rounded-xl bg-white text-stone-700 focus:outline-none transition-colors ${
                    rangoError ? 'border-red-400' : 'border-stone-200 focus:border-amber-400'
                  }`}
                />
                {rangoError && <p className="mt-1.5 text-xs font-bold text-red-500">{rangoError}</p>}
              </div>
            )}
          </fieldset>

          {cantidadDocumentos > 1 && (
            <button
              type="button"
              disabled={!completo}
              onClick={() => onAplicarATodos(opciones)}
              className="w-full py-3 rounded-xl border-2 border-amber-400 bg-white hover:bg-amber-100 disabled:opacity-40 disabled:cursor-not-allowed text-amber-800 text-xs font-bold uppercase tracking-widest transition-colors"
            >
              {completo
                ? `Aplicar esta configuración a los ${cantidadDocumentos} documentos`
                : 'Completá las opciones para aplicarlas a todos'}
            </button>
          )}

          <div className="pt-4 border-t border-amber-200">
            {!completo ? (
              <p className="text-xs text-stone-400 text-center py-2">
                Elegí las cuatro opciones para ver el precio.
              </p>
            ) : (
              <>
                <div className="flex justify-between items-center">
                  <span className="text-xs font-bold uppercase tracking-widest text-stone-400">
                    Este documento
                  </span>
                  <span className="text-xl font-black text-amber-700">
                    ${suelto.total.toLocaleString('es-AR')}
                  </span>
                </div>
                <p className="text-[10px] text-stone-400 mt-1 text-right">
                  {paginasACobrar} págs · {suelto.cantidadTotal}{' '}
                  {opciones.caras === 'doble' ? 'hojas' : 'copias'} ×{' '}
                  ${precioUnitario(opciones.color, opciones.caras, suelto.cantidadTotal).toLocaleString('es-AR')} c/u
                </p>
                {cantidadDocumentos > 1 && (
                  <p className="text-[10px] text-amber-700 mt-1 text-right">
                    Al juntarlo con los demás puede salir más barato — mirá el resumen.
                  </p>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </article>
  );
};

export default PrintOptions;
