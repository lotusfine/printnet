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

export const DEFAULT_CONTACTO = {
  nombre: '',
  pais: '54',
  area: '221',
  numero: '',
  email: '',
};

// Formato requerido por WhatsApp para celulares argentinos: el "9" se
// agrega automáticamente entre el código de país y el de área.
export const composeTelefono = (c) =>
  `+${c.pais.trim()}9${c.area.trim()}${c.numero.trim()}`;

export const validateContacto = (contacto) => {
  const errors = {};

  if (!contacto.nombre.trim()) {
    errors.nombre = 'Ingresá tu nombre';
  }

  const pais = contacto.pais.trim();
  const area = contacto.area.trim();
  const numero = contacto.numero.trim();

  if (!pais || !area || !numero) {
    errors.telefono = 'Completá los tres campos del teléfono';
  } else if (!/^\d+$/.test(pais) || !/^\d+$/.test(area) || !/^\d+$/.test(numero)) {
    errors.telefono = 'El teléfono solo puede contener dígitos';
  } else if (area.length < 2 || area.length > 4) {
    errors.telefono = 'El código de área debe tener entre 2 y 4 dígitos';
  } else if (numero.length < 6 || numero.length > 8) {
    errors.telefono = 'El número debe tener entre 6 y 8 dígitos';
  }

  const email = contacto.email.trim();
  if (!email) {
    errors.email = 'Ingresá tu email';
  } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    errors.email = 'Ingresá un email válido';
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

  const set = (key) => (e) => onChange({ ...contacto, [key]: e.target.value });

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
            onChange={set('nombre')}
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
          <div className="flex gap-2">
            <div className="w-20 shrink-0">
              <div className="relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-sm font-bold text-stone-400 pointer-events-none">+</span>
                <input
                  type="tel"
                  value={contacto.pais}
                  onChange={set('pais')}
                  aria-label="Código de país"
                  className={`${inputClass(!!errors.telefono)} !pl-7 !px-2 text-center`}
                />
              </div>
              <p className="mt-1 text-[10px] text-stone-400 text-center">País</p>
            </div>
            <div className="w-24 shrink-0">
              <input
                type="tel"
                value={contacto.area}
                onChange={set('area')}
                aria-label="Código de área"
                className={`${inputClass(!!errors.telefono)} !px-2 text-center`}
              />
              <p className="mt-1 text-[10px] text-stone-400 text-center">Área</p>
            </div>
            <div className="flex-1 min-w-0">
              <input
                type="tel"
                value={contacto.numero}
                onChange={set('numero')}
                placeholder="4567890"
                aria-label="Número"
                className={inputClass(!!errors.telefono)}
              />
              <p className="mt-1 text-[10px] text-stone-400 text-center">Número</p>
            </div>
          </div>
          <p className="mt-1.5 text-xs italic text-stone-400">
            Ingresá tu número sin 0 y sin 15. Si no sos de La Plata, cambiá el código de área.
          </p>
          {errors.telefono && (
            <p className="mt-1.5 text-xs font-bold text-red-500">{errors.telefono}</p>
          )}
        </div>

        <div>
          <label className="block mb-2 text-xs font-bold uppercase tracking-widest text-stone-500">
            Email <span className="text-red-400">*</span>
          </label>
          <input
            type="email"
            value={contacto.email}
            onChange={set('email')}
            placeholder="tu@email.com"
            className={inputClass(!!errors.email)}
          />
          <p className="mt-1.5 text-xs italic text-stone-400">
            Te enviaremos el seguimiento de tu pedido por email.
          </p>
          {errors.email && (
            <p className="mt-1.5 text-xs font-bold text-red-500">{errors.email}</p>
          )}
        </div>
      </div>
    </article>
  );
};

export default ContactForm;
