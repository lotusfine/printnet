export const MATERIALES = [
  { value: 'hoja-foto', label: 'Hoja foto' },
  { value: 'vegetal', label: 'Papel vegetal' },
  { value: 'opalina', label: 'Opalina' },
  { value: 'autoadhesiva', label: 'Autoadhesiva' },
];

export const FORMATOS = [
  { value: '13x18', label: '13×18', desc: '2 copias de la misma imagen por hoja' },
  { value: '9x13', label: '9×13', desc: '4 copias por hoja' },
  { value: '6x9', label: '6×9', desc: '9 copias por hoja' },
];

export const GRAMAJES = [120, 150, 180, 240];

const selectedClass = (isSelected) => `
  rounded-xl border-2 text-sm font-bold transition-all
  ${isSelected
    ? 'border-purple-500 bg-purple-200 text-purple-900'
    : 'border-stone-200 bg-white text-stone-600 hover:border-purple-300'}
`;

const MaterialSelect = ({ material, formato, gramaje, onMaterial, onFormato, onGramaje, errors = {} }) => (
  <article className="p-6 md:p-8 bg-violet-50 shadow-xl rounded-sm relative overflow-hidden">
    <div className="absolute top-0 w-20 h-6 -translate-x-1/2 -translate-y-3 left-1/2 bg-white/60 rotate-2 md:w-24 md:h-8" />
    <h2 className="mb-6 text-[10px] font-black tracking-[0.3em] uppercase text-stone-500/60 text-center">
      Tipo de Material
    </h2>

    <div className="grid grid-cols-2 gap-3">
      {MATERIALES.map(({ value, label }) => (
        <button
          key={value}
          type="button"
          onClick={() => onMaterial(value)}
          className={`py-3 px-2 ${selectedClass(material === value)}`}
        >
          {label}
        </button>
      ))}
    </div>
    {errors.material && (
      <p className="mt-2 text-xs font-bold text-red-500 text-center">{errors.material}</p>
    )}

    {material === 'hoja-foto' && (
      <fieldset className="mt-6">
        <legend className="mb-2 text-xs font-bold uppercase tracking-widest text-stone-500">Formato</legend>
        <div className="space-y-2">
          {FORMATOS.map(({ value, label, desc }) => (
            <button
              key={value}
              type="button"
              onClick={() => onFormato(value)}
              className={`w-full py-3 px-4 text-left flex items-baseline gap-3 ${selectedClass(formato === value)}`}
            >
              <span className="shrink-0">{label}</span>
              <span className="text-xs font-normal opacity-70">{desc}</span>
            </button>
          ))}
        </div>
        {errors.formato && (
          <p className="mt-2 text-xs font-bold text-red-500">{errors.formato}</p>
        )}
      </fieldset>
    )}

    {material === 'opalina' && (
      <fieldset className="mt-6">
        <legend className="mb-2 text-xs font-bold uppercase tracking-widest text-stone-500">Gramaje</legend>
        <div className="grid grid-cols-4 gap-2">
          {GRAMAJES.map((g) => (
            <button
              key={g}
              type="button"
              onClick={() => onGramaje(g)}
              className={`py-3 ${selectedClass(gramaje === g)}`}
            >
              {g}
            </button>
          ))}
        </div>
        {errors.gramaje && (
          <p className="mt-2 text-xs font-bold text-red-500">{errors.gramaje}</p>
        )}
      </fieldset>
    )}
  </article>
);

export default MaterialSelect;
