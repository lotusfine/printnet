import { useState, useRef } from 'react';
import { contarPaginas } from '../../api';
import { MAX_ARCHIVO_BYTES, MAX_ARCHIVO_MB, formatearTamano } from '../../limites';
import { ACCEPT, describirExtension, esAceptado, esConvertible } from '../../formatos';

// NO HAY VALOR POR DEFECTO PARA LAS PÁGINAS, A PROPÓSITO.
//
// Antes había uno: si el conteo fallaba, se asumía que el documento tenía 10
// páginas. Como el precio se calcula sobre ese número, un documento de 1
// página podía mostrarse al precio de 10. Pasó en producción.
//
// La regla ahora: si no sabemos cuántas páginas tiene, no mostramos precio y
// no dejamos avanzar. Es preferible un cliente que reintenta a uno al que le
// cobramos de más.

/** Traduce el error del backend a algo que una persona pueda accionar. */
const explicarError = (e) => {
  if (e?.status === 413) {
    return { mensaje: `El archivo supera el máximo de ${MAX_ARCHIVO_MB} MB.`, detalle: '' };
  }
  if (e?.status === 422) {
    return {
      mensaje: 'No pudimos leer este PDF. Puede estar dañado o protegido con contraseña.',
      detalle: e?.message || '',
    };
  }
  // Sin código HTTP = no llegó a haber respuesta: conexión, bloqueo del
  // navegador, o el servidor caído. Guardamos el detalle técnico para poder
  // diagnosticar casos como el de DuckDuckGo, donde todavía no sabemos la causa.
  return {
    mensaje: 'No pudimos conectarnos para leer el documento.',
    detalle: e?.message || 'sin detalle',
  };
};

// Valida solo el formato del rango ("3-16" o "5"). La validación contra la
// cantidad real de páginas del PDF la hará el backend más adelante.
export const validateRango = (valor) => {
  const v = valor.trim();
  if (!v) return 'Ingresá el rango de páginas';
  if (!/^\d+(-\d+)?$/.test(v)) return 'Formato inválido. Usá "3-16" o un solo número, ej: "5"';
  const [inicio, fin] = v.split('-').map(Number);
  if (inicio < 1 || (fin !== undefined && fin < 1)) return 'Las páginas empiezan en 1';
  if (fin !== undefined && inicio > fin) return 'El inicio del rango no puede ser mayor que el fin';
  return null;
};

const FileUpload = ({ onFileChange, pageRange, onPageRangeChange, rangeError }) => {
  const [file, setFile] = useState(null);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef(null);

  // 'vacio' | 'contando' | 'listo' | 'error'
  const [estado, setEstado] = useState('vacio');
  const [paginas, setPaginas] = useState(null);
  const [convertido, setConvertido] = useState(false);
  const [error, setError] = useState(null);

  const handleFile = async (f) => {
    if (!f) return;
    setFile(f);

    // Antes se ignoraba en silencio cualquier archivo que no fuera PDF: el
    // cliente lo elegía y no pasaba nada, sin saber por qué.
    if (!esAceptado(f.name)) {
      setEstado('error');
      setPaginas(null);
      setError({
        mensaje: `No aceptamos archivos ${describirExtension(f.name)}.`,
        detalle: '',
        reintentable: false,
        sugerencia: 'Podés subir un PDF, o un documento de Word, Excel o PowerPoint.',
      });
      onFileChange(null);
      return;
    }

    // El tamaño se valida ANTES de subir nada: el navegador ya lo sabe. Antes
    // el cliente esperaba toda la subida para enterarse recién al pagar.
    if (f.size > MAX_ARCHIVO_BYTES) {
      setEstado('error');
      setPaginas(null);
      setError({
        mensaje: `"${f.name}" pesa ${formatearTamano(f.size)} y el máximo es ${MAX_ARCHIVO_MB} MB.`,
        detalle: '',
        reintentable: false,
      });
      onFileChange(null);
      return;
    }

    setEstado('contando');
    setError(null);
    // Mientras no sepamos las páginas, el pedido no puede avanzar: mandar null
    // deja el botón de pago deshabilitado.
    onFileChange(null);

    try {
      const { paginas: reales, convertido: fueConvertido } = await contarPaginas(f);
      setPaginas(reales);
      setConvertido(Boolean(fueConvertido));
      setEstado('listo');
      onFileChange({ name: f.name, pages: reales, file: f });
    } catch (e) {
      setPaginas(null);
      setEstado('error');
      setError({ ...explicarError(e), reintentable: true });
      onFileChange(null);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    handleFile(e.dataTransfer.files[0]);
  };

  return (
    <article className="p-6 md:p-8 bg-yellow-50 shadow-xl rounded-sm relative overflow-hidden">
      <div className="absolute top-0 w-20 h-6 -translate-x-1/2 -translate-y-3 left-1/2 bg-white/60 rotate-1 md:w-24 md:h-8" />
      <h2 className="mb-6 text-[10px] font-black tracking-[0.3em] uppercase text-stone-500/60 text-center">
        Subir Archivo
      </h2>

      <div
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        className={`
          flex flex-col items-center justify-center gap-3 cursor-pointer
          border-2 border-dashed rounded-xl p-10 transition-colors duration-200
          ${dragging ? 'border-amber-500 bg-amber-100' : 'border-amber-300 bg-amber-50 hover:bg-amber-100'}
        `}
      >
        <svg xmlns="http://www.w3.org/2000/svg" className="w-12 h-12 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
        </svg>
        <p className="text-sm font-bold text-stone-600">
          {dragging ? 'Soltá el archivo acá' : 'Arrastrá tu documento o hacé click para elegir'}
        </p>
        <p className="text-xs text-stone-500 text-center max-w-xs">
          Subí tu PDF, o cualquier documento de Word, Excel o PowerPoint —
          lo convertimos a PDF automáticamente.
        </p>
        <p className="text-xs text-stone-400">Hasta {MAX_ARCHIVO_MB} MB</p>
      </div>

      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT}
        className="hidden"
        onChange={(e) => handleFile(e.target.files[0])}
      />

      {file && estado !== 'error' && (
        <div className="mt-5 flex items-center gap-3 bg-white/70 border border-amber-200 rounded-lg px-4 py-3 shadow-sm">
          <svg xmlns="http://www.w3.org/2000/svg" className="w-6 h-6 text-red-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
          </svg>
          <div className="min-w-0">
            <p className="text-sm font-bold text-stone-700 truncate">{file.name}</p>
            <p className="text-xs text-stone-400">
              {estado === 'contando'
                ? (esConvertible(file.name) ? 'Convirtiendo a PDF…' : 'Leyendo tu documento…')
                : `${paginas} ${paginas === 1 ? 'página' : 'páginas'}`}
            </p>
          </div>
        </div>
      )}

      {/* Solo si hubo conversión. LibreOffice es bueno pero no perfecto: un
          PowerPoint con tipografías raras puede salir con el texto corrido, y
          es mejor que el cliente lo sepa antes de pagar que cuando retira. */}
      {estado === 'listo' && convertido && (
        <div className="mt-3 flex items-start gap-2 bg-amber-100/60 border border-amber-300 rounded-lg px-3 py-2">
          <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" viewBox="0 0 24 24" fill="currentColor">
            <path fillRule="evenodd" d="M12 2.25c-5.385 0-9.75 4.365-9.75 9.75s4.365 9.75 9.75 9.75 9.75-4.365 9.75-9.75S17.385 2.25 12 2.25zM12.75 6a.75.75 0 00-1.5 0v6c0 .414.336.75.75.75h4.5a.75.75 0 000-1.5h-3.75V6z" clipRule="evenodd"/>
          </svg>
          <p className="text-[11px] leading-relaxed text-amber-800">
            Convertimos tu documento a PDF. El diseño puede moverse un poco
            respecto del original — si necesitás que salga exacto, subilo en PDF.
          </p>
        </div>
      )}

      {estado === 'error' && error && (
        <div className="mt-5 bg-red-50 border-2 border-red-200 rounded-lg px-4 py-3">
          <div className="flex items-start gap-3">
            <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5 text-red-500 shrink-0 mt-0.5" viewBox="0 0 24 24" fill="currentColor">
              <path fillRule="evenodd" d="M9.401 3.003c1.155-2 4.043-2 5.197 0l7.355 12.748c1.154 2-.29 4.5-2.599 4.5H4.645c-2.309 0-3.752-2.5-2.598-4.5L9.4 3.003zM12 8.25a.75.75 0 01.75.75v3.75a.75.75 0 01-1.5 0V9a.75.75 0 01.75-.75zm0 8.25a.75.75 0 100-1.5.75.75 0 000 1.5z" clipRule="evenodd"/>
            </svg>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-bold text-red-700">{error.mensaje}</p>
              <p className="mt-1 text-xs text-red-600/80">
                {error.sugerencia
                  ? error.sugerencia
                  : error.reintentable
                    ? 'No podemos calcular el precio sin saber cuántas páginas tiene.'
                    : 'Probá con un archivo más liviano, o dividilo en partes.'}
              </p>
              {error.detalle && (
                <p className="mt-1 text-[10px] text-red-400 break-words">
                  Detalle técnico: {error.detalle}
                </p>
              )}
              <div className="mt-3 flex gap-2">
                {error.reintentable && (
                  <button
                    type="button"
                    onClick={() => handleFile(file)}
                    className="px-3 py-1.5 rounded-lg bg-red-600 hover:bg-red-500 text-white text-xs font-bold uppercase tracking-wide transition-colors"
                  >
                    Reintentar
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => inputRef.current?.click()}
                  className="px-3 py-1.5 rounded-lg bg-white border border-red-300 hover:bg-red-100 text-red-700 text-xs font-bold uppercase tracking-wide transition-colors"
                >
                  Elegir otro archivo
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Páginas a imprimir */}
      <fieldset className="mt-6">
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
              aria-checked={pageRange.modo === value}
              onClick={() => onPageRangeChange({ ...pageRange, modo: value })}
              className={`flex-1 py-3 px-2 rounded-xl border-2 text-sm font-bold transition-all ${
                pageRange.modo === value
                  ? 'border-amber-500 bg-amber-200 text-amber-900'
                  : 'border-stone-200 bg-white text-stone-600 hover:border-amber-300'
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {pageRange.modo === 'rango' && (
          <div className="mt-3">
            <input
              type="text"
              value={pageRange.valor}
              onChange={(e) => onPageRangeChange({ ...pageRange, valor: e.target.value })}
              placeholder="Ej: 3-16"
              className={`w-full px-4 py-3 text-sm font-bold border-2 rounded-xl bg-white text-stone-700 focus:outline-none transition-colors ${
                rangeError ? 'border-red-400 focus:border-red-500' : 'border-stone-200 focus:border-amber-400'
              }`}
            />
            <p className="mt-1.5 text-xs italic text-stone-400">
              Indicá desde qué página hasta qué página querés imprimir.
            </p>
            {rangeError && (
              <p className="mt-1.5 text-xs font-bold text-red-500">{rangeError}</p>
            )}
          </div>
        )}
      </fieldset>
    </article>
  );
};

export default FileUpload;
