const ACCENTS = {
  amber: {
    card: 'bg-orange-50',
    focus: 'focus:border-amber-400',
    tape: 'rotate-2',
  },
  lila: {
    card: 'bg-purple-50',
    focus: 'focus:border-purple-400',
    tape: '-rotate-2',
  },
};

export const validateContacto = (contacto) => {
  const errors = {};
  if (!contacto.nombre.trim()) {
    errors.nombre = 'Ingresá tu nombre';
  }
  if (!contacto.telefono.trim()) {
    errors.telefono = 'Ingresá un teléfono';
  } else if (!/^[0-9\s-]+$/.test(contacto.telefono.trim())) {
    errors.telefono = 'Solo se permiten números, espacios y guiones';
  }
  return errors;
};

const ContactForm = ({ contacto, errors = {}, onChange, accent = 'amber' }) => {
  const a = ACCENTS[accent];

  const inputClass = (hasError) => `
    w-full px-4 py-3 text-sm font-bold border-2 rounded-xl bg-white text-stone-700
    focus:outline-none transition-colors
    ${hasError ? 'border-red-400 focus:border-red-500' : `border-stone-200 ${a.focus}`}
  `;

  return (
    <article className={`p-6 md:p-8 ${a.card} shadow-xl rounded-sm relative overflow-hidden`}>
      <div className={`absolute top-0 w-20 h-6 -translate-x-1/2 -translate-y-3 left-1/2 bg-white/60 ${a.tape} md:w-24 md:h-8`} />
      <h2 className="mb-6 text-[10px] font-black tracking-[0.3em] uppercase text-stone-500/60 text-center">
        Datos de Contacto
      </h2>

      <div className="space-y-4">
        <div>
          <label className="block mb-2 text-xs font-bold uppercase tracking-widest text-stone-500">
            Nombre <span className="text-red-400">*</span>
          </label>
          <input
            type="text"
            value={contacto.nombre}
            onChange={(e) => onChange({ ...contacto, nombre: e.target.value })}
            placeholder="Tu nombre"
            className={inputClass(!!errors.nombre)}
          />
          {errors.nombre && (
            <p className="mt-1.5 text-xs font-bold text-red-500">{errors.nombre}</p>
          )}
        </div>

        <div>
          <label className="block mb-2 text-xs font-bold uppercase tracking-widest text-stone-500">
            Teléfono <span className="text-red-400">*</span>
          </label>
          <input
            type="tel"
            value={contacto.telefono}
            onChange={(e) => onChange({ ...contacto, telefono: e.target.value })}
            placeholder="221-1234567"
            className={inputClass(!!errors.telefono)}
          />
          {errors.telefono && (
            <p className="mt-1.5 text-xs font-bold text-red-500">{errors.telefono}</p>
          )}
        </div>
      </div>
    </article>
  );
};

export default ContactForm;
