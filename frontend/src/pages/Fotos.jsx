import { useState } from 'react';
import { Link } from 'react-router-dom';
import ContactForm, { validateContacto } from '../components/ContactForm';
import FilesUpload from '../components/fotos/FilesUpload';
import MaterialSelect, { MATERIALES, FORMATOS } from '../components/fotos/MaterialSelect';
import FinishOptions from '../components/fotos/FinishOptions';

const DEFAULT_CONTACTO = { nombre: '', telefono: '' };

let nextFileId = 1;

const Fotos = () => {
  const [contacto, setContacto] = useState(DEFAULT_CONTACTO);
  const [files, setFiles] = useState([]);
  const [material, setMaterial] = useState(null);
  const [formato, setFormato] = useState(null);
  const [gramaje, setGramaje] = useState(null);
  const [terminaciones, setTerminaciones] = useState([]);
  const [errors, setErrors] = useState({});
  const [resumen, setResumen] = useState(null);

  // Cualquier cambio invalida el resumen mostrado y limpia errores
  const touch = (setter) => (value) => {
    setResumen(null);
    setErrors({});
    setter(value);
  };

  const handleAddFiles = (nuevos) => {
    setResumen(null);
    setErrors({});
    setFiles((prev) => [
      ...prev,
      ...nuevos.map((f) => ({ id: nextFileId++, name: f.name })),
    ]);
  };

  const handleRemoveFile = (id) => {
    setResumen(null);
    setFiles((prev) => prev.filter((f) => f.id !== id));
  };

  const handleToggleTerminacion = (t) => {
    setResumen(null);
    setTerminaciones((prev) =>
      prev.includes(t) ? prev.filter((x) => x !== t) : [...prev, t]
    );
  };

  const handleSubmit = () => {
    const errs = validateContacto(contacto);
    if (files.length === 0) errs.archivos = 'Agregá al menos un archivo';
    if (!material) {
      errs.material = 'Elegí un tipo de material';
    } else if (material === 'hoja-foto' && !formato) {
      errs.formato = 'Elegí un formato';
    } else if (material === 'opalina' && !gramaje) {
      errs.gramaje = 'Elegí un gramaje';
    }
    setErrors(errs);
    if (Object.keys(errs).length > 0) return;

    setResumen({
      contacto: { ...contacto },
      files: files.map((f) => f.name),
      material,
      formato: material === 'hoja-foto' ? formato : null,
      gramaje: material === 'opalina' ? gramaje : null,
      terminaciones: [...terminaciones],
    });
  };

  const materialLabel = (value) => MATERIALES.find((m) => m.value === value)?.label ?? value;
  const formatoLabel = (value) => FORMATOS.find((f) => f.value === value)?.label ?? value;

  return (
    <section className="flex flex-col space-y-8 md:space-y-12">
      <header className="flex flex-col gap-4">
        <Link
          to="/"
          className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-widest text-stone-500 hover:text-purple-700 transition-colors w-fit"
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18" />
          </svg>
          Volver al inicio
        </Link>
        <div className="text-center">
          <h1 className="text-4xl font-chalk md:text-6xl text-stone-800/90 mb-2">Fotos</h1>
          <p className="text-base italic font-chalk text-stone-500 md:text-lg">
            Impresiones especiales y fotos
          </p>
        </div>
      </header>

      <div className="grid w-full gap-8 md:gap-10 md:grid-cols-2">
        <ContactForm
          contacto={contacto}
          errors={errors}
          onChange={touch(setContacto)}
          accent="lila"
        />
        <FilesUpload
          files={files}
          onAdd={handleAddFiles}
          onRemove={handleRemoveFile}
          error={errors.archivos}
        />
        <MaterialSelect
          material={material}
          formato={formato}
          gramaje={gramaje}
          onMaterial={touch(setMaterial)}
          onFormato={touch(setFormato)}
          onGramaje={touch(setGramaje)}
          errors={errors}
        />
        <FinishOptions
          terminaciones={terminaciones}
          onToggle={handleToggleTerminacion}
        />
      </div>

      <div className="flex flex-col items-center gap-3">
        <button
          type="button"
          onClick={handleSubmit}
          className="w-full max-w-md py-4 rounded-xl bg-purple-500 hover:bg-purple-600 active:scale-95 text-white font-black text-sm uppercase tracking-widest transition-all duration-200 shadow-md"
        >
          Enviar Pedido
        </button>
        {Object.keys(errors).length > 0 && (
          <p className="text-xs font-bold text-red-500">
            Revisá los campos marcados antes de enviar
          </p>
        )}
      </div>

      {resumen && (
        <article className="w-full max-w-2xl mx-auto p-6 md:p-8 bg-purple-50 border-2 border-purple-300 shadow-xl rounded-sm relative overflow-hidden">
          <div className="absolute top-0 w-20 h-6 -translate-x-1/2 -translate-y-3 left-1/2 bg-white/60 rotate-2 md:w-24 md:h-8" />
          <div className="flex items-center justify-center gap-2 mb-6">
            <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5 text-green-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <h2 className="text-[10px] font-black tracking-[0.3em] uppercase text-stone-500/60">
              Resumen del Pedido
            </h2>
          </div>

          <dl className="space-y-3">
            <div className="flex justify-between gap-4 py-1.5 border-b border-purple-100">
              <dt className="text-xs font-bold uppercase tracking-widest text-stone-400">Nombre</dt>
              <dd className="text-sm font-bold text-stone-700 text-right">{resumen.contacto.nombre}</dd>
            </div>
            <div className="flex justify-between gap-4 py-1.5 border-b border-purple-100">
              <dt className="text-xs font-bold uppercase tracking-widest text-stone-400">Teléfono</dt>
              <dd className="text-sm font-bold text-stone-700 text-right">{resumen.contacto.telefono}</dd>
            </div>
            <div className="flex justify-between gap-4 py-1.5 border-b border-purple-100">
              <dt className="text-xs font-bold uppercase tracking-widest text-stone-400 shrink-0">
                Archivos ({resumen.files.length})
              </dt>
              <dd className="text-sm font-bold text-stone-700 text-right min-w-0">
                {resumen.files.map((name) => (
                  <span key={name} className="block truncate">{name}</span>
                ))}
              </dd>
            </div>
            <div className="flex justify-between gap-4 py-1.5 border-b border-purple-100">
              <dt className="text-xs font-bold uppercase tracking-widest text-stone-400">Material</dt>
              <dd className="text-sm font-bold text-stone-700 text-right">
                {materialLabel(resumen.material)}
                {resumen.formato && ` · ${formatoLabel(resumen.formato)}`}
                {resumen.gramaje && ` · ${resumen.gramaje} g`}
              </dd>
            </div>
            <div className="flex justify-between gap-4 py-1.5">
              <dt className="text-xs font-bold uppercase tracking-widest text-stone-400">Terminaciones</dt>
              <dd className="text-sm font-bold text-stone-700 text-right">
                {resumen.terminaciones.length > 0 ? resumen.terminaciones.join(' · ') : 'Sin terminaciones'}
              </dd>
            </div>
          </dl>

          <p className="mt-6 text-xs italic text-stone-400 text-center">
            Recibimos tu pedido. Te vamos a contactar al teléfono indicado para coordinar.
          </p>
        </article>
      )}
    </section>
  );
};

export default Fotos;
