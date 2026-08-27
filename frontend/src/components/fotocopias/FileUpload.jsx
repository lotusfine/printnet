import { useRef, useState } from 'react';
import { contarPaginas } from '../../api';
import { MAX_ARCHIVO_BYTES, MAX_ARCHIVO_MB, formatearTamano } from '../../limites';
import { ACCEPT, describirExtension, esAceptado, esConvertible } from '../../formatos';

// NO HAY VALOR POR DEFECTO PARA LAS PÁGINAS, A PROPÓSITO.
//
// Antes había uno: si el conteo fallaba, se asumía que el documento tenía 10
// páginas, y como el precio sale de ese número, un documento de 1 página podía
// cotizarse como 10. Pasó en producción.
//
// La regla: si no sabemos cuántas páginas tiene, no hay precio y no se puede
// pagar.

const MAX_DOCUMENTOS = 20;  // espejo de MAX_DOCUMENTOS en backend-printnet/models.py

/** Valida solo el formato del rango ("3-16" o "5"). */
export const validateRango = (valor) => {
  const v = (valor || '').trim();
  if (!v) return 'Ingresá el rango de páginas';
  if (!/^\d+(-\d+)?$/.test(v)) return 'Formato inválido. Usá "3-16" o un solo número, ej: "5"';
  const [inicio, fin] = v.split('-').map(Number);
  if (inicio < 1 || (fin !== undefined && fin < 1)) return 'Las páginas empiezan en 1';
  if (fin !== undefined && inicio > fin) return 'El inicio del rango no puede ser mayor que el fin';
  return null;
};

const explicarError = (e) => {
  if (e?.status === 413) return { mensaje: `Supera el máximo de ${MAX_ARCHIVO_MB} MB.`, detalle: '' };
  if (e?.status === 422) {
    return { mensaje: e?.message || 'No pudimos leer este documento.', detalle: '' };
  }
  // Sin código HTTP = no hubo respuesta: conexión, bloqueo del navegador, o el
  // servidor caído. Se guarda el detalle técnico para poder diagnosticar.
  return {
    mensaje: 'No pudimos conectarnos para leer el documento.',
    detalle: e?.message || 'sin detalle',
  };
};

const FileUpload = ({ documentos, seleccionado, onSeleccionar, onAgregar, onActualizar, onQuitar }) => {
  const [dragging, setDragging] = useState(false);
  const [avisoCarga, setAvisoCarga] = useState(null);
  const inputRef = useRef(null);

  const pesoTotal = documentos.reduce((s, d) => s + (d.file?.size || 0), 0);

  const procesar = async (doc) => {
    try {
      const { paginas, convertido } = await contarPaginas(doc.file);
      onActualizar(doc.id, { paginas, convertido: Boolean(convertido), estado: 'listo', error: null });
    } catch (e) {
      onActualizar(doc.id, { paginas: null, estado: 'error', error: explicarError(e) });
    }
  };

  const recibir = (lista) => {
    const archivos = Array.from(lista || []);
    if (!archivos.length) return;

    const rechazos = [];
    const aceptados = [];
    let acumulado = pesoTotal;

    for (const f of archivos) {
      if (documentos.length + aceptados.length >= MAX_DOCUMENTOS) {
        rechazos.push(`No se pueden subir más de ${MAX_DOCUMENTOS} documentos.`);
        break;
      }
      if (!esAceptado(f.name)) {
        rechazos.push(`"${f.name}": no aceptamos archivos ${describirExtension(f.name)}.`);
        continue;
      }
      // El tope es sobre la SUMA: el límite lo pone Cloudflare por petición,
      // y el pedido entero viaja en una sola.
      if (acumulado + f.size > MAX_ARCHIVO_BYTES) {
        rechazos.push(
          `"${f.name}" (${formatearTamano(f.size)}) no entra: el total no puede pasar de ${MAX_ARCHIVO_MB} MB.`
        );
        continue;
      }
      acumulado += f.size;
      aceptados.push(f);
    }

    setAvisoCarga(rechazos.length ? rechazos : null);
    if (aceptados.length) onAgregar(aceptados).forEach(procesar);
  };

  const usadoMB = Math.round(pesoTotal / (1024 * 1024));

  return (
    <article className="p-6 md:p-8 bg-yellow-50 shadow-xl rounded-sm relative overflow-hidden">
      <div className="absolute top-0 w-20 h-6 -translate-x-1/2 -translate-y-3 left-1/2 bg-white/60 rotate-1 md:w-24 md:h-8" />
      <h2 className="mb-6 text-[10px] font-black tracking-[0.3em] uppercase text-stone-500/60 text-center">
        {documentos.length ? `Tus documentos (${documentos.length})` : 'Subir archivo'}
      </h2>

      <div
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => { e.preventDefault(); setDragging(false); recibir(e.dataTransfer.files); }}
        className={`flex flex-col items-center justify-center gap-3 cursor-pointer border-2 border-dashed rounded-xl transition-colors duration-200 ${
          documentos.length ? 'p-5' : 'p-10'
        } ${dragging ? 'border-amber-500 bg-amber-100' : 'border-amber-300 bg-amber-50 hover:bg-amber-100'}`}
      >
        <svg xmlns="http://www.w3.org/2000/svg" className={documentos.length ? 'w-7 h-7 text-amber-400' : 'w-12 h-12 text-amber-400'} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
        </svg>
        <p className="text-sm font-bold text-stone-600 text-center">
          {dragging
            ? 'Soltá los archivos acá'
            : documentos.length
              ? 'Agregar otro documento'
              : 'Arrastrá tus documentos o hacé click para elegir'}
        </p>
        {!documentos.length && (
          <p className="text-xs text-stone-500 text-center max-w-xs">
            Subí tu PDF, o cualquier documento de Word, Excel o PowerPoint —
            lo convertimos a PDF automáticamente.
          </p>
        )}
        <p className="text-xs text-stone-400">
          {documentos.length ? `${usadoMB} de ${MAX_ARCHIVO_MB} MB usados` : `Hasta ${MAX_ARCHIVO_MB} MB en total`}
        </p>
      </div>

      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT}
        multiple
        className="hidden"
        onChange={(e) => { recibir(e.target.files); e.target.value = ''; }}
      />

      {avisoCarga && (
        <div className="mt-4 bg-red-50 border-2 border-red-200 rounded-lg px-4 py-3">
          {avisoCarga.map((m, i) => (
            <p key={i} className="text-xs font-bold text-red-700">{m}</p>
          ))}
        </div>
      )}

      <div className="mt-5 space-y-2">
        {documentos.map((doc) => (
          <DocumentoFila
            key={doc.id}
            doc={doc}
            activo={doc.id === seleccionado}
            onSeleccionar={() => onSeleccionar(doc.id)}
            onQuitar={() => onQuitar(doc.id)}
            onReintentar={() => { onActualizar(doc.id, { estado: 'contando', error: null }); procesar(doc); }}
          />
        ))}
      </div>
    </article>
  );
};

const configurado = (doc) =>
  doc.opciones.color && doc.opciones.caras && doc.opciones.copias && doc.opciones.tamano;

const DocumentoFila = ({ doc, activo, onSeleccionar, onQuitar, onReintentar }) => {
  const roto = doc.estado === 'error';
  const listo = doc.estado === 'listo';
  const completo = listo && configurado(doc);

  // Los documentos sin configurar se ven atenuados: la pantalla muestra sola
  // lo que falta, sin que haga falta un cartel.
  const atenuado = listo && !completo && !activo;

  return (
    <div
      onClick={() => !roto && onSeleccionar()}
      className={`rounded-lg border-2 px-4 py-3 transition-all ${roto ? 'cursor-default' : 'cursor-pointer'} ${
        roto
          ? 'border-red-300 bg-red-50'
          : activo
            ? 'border-amber-500 bg-white'
            : 'border-stone-200 bg-white/70 hover:border-amber-300'
      } ${atenuado ? 'opacity-50' : 'opacity-100'}`}
    >
      <div className="flex items-start gap-3">
        <svg xmlns="http://www.w3.org/2000/svg" className={`w-5 h-5 shrink-0 mt-0.5 ${roto ? 'text-red-500' : completo ? 'text-green-600' : 'text-stone-400'}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
          {roto ? (
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
          ) : completo ? (
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          ) : (
            <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m6.75 12H8.25m6.75 3H8.25m-3.75-12h.008v.008H4.5V8.25z" />
          )}
        </svg>

        <div className="min-w-0 flex-1">
          <p className="text-sm font-bold text-stone-700 truncate">{doc.name}</p>
          <p className={`text-xs ${roto ? 'text-red-600' : 'text-stone-400'}`}>
            {doc.estado === 'contando'
              ? (esConvertible(doc.name) ? 'Convirtiendo a PDF…' : 'Leyendo tu documento…')
              : roto
                ? doc.error?.mensaje
                : `${doc.paginas} ${doc.paginas === 1 ? 'página' : 'páginas'}${doc.convertido ? ' · convertido a PDF' : ''}`}
          </p>

          {listo && (
            <p className={`mt-1 text-[11px] ${completo ? 'text-stone-500' : 'text-amber-700 font-bold'}`}>
              {completo ? resumenOpciones(doc.opciones) : 'Sin configurar'}
            </p>
          )}

          {roto && (
            <>
              {doc.error?.detalle && (
                <p className="mt-1 text-[10px] text-red-400 break-words">
                  Detalle técnico: {doc.error.detalle}
                </p>
              )}
              <div className="mt-2 flex gap-2">
                <button
                  type="button"
                  onClick={(e) => { e.stopPropagation(); onReintentar(); }}
                  className="px-3 py-1 rounded-lg bg-red-600 hover:bg-red-500 text-white text-[11px] font-bold uppercase tracking-wide transition-colors"
                >
                  Reintentar
                </button>
                <button
                  type="button"
                  onClick={(e) => { e.stopPropagation(); onQuitar(); }}
                  className="px-3 py-1 rounded-lg bg-white border border-red-300 hover:bg-red-100 text-red-700 text-[11px] font-bold uppercase tracking-wide transition-colors"
                >
                  Quitar
                </button>
              </div>
            </>
          )}
        </div>

        {!roto && (
          <button
            type="button"
            aria-label={`Quitar ${doc.name}`}
            onClick={(e) => { e.stopPropagation(); onQuitar(); }}
            className="shrink-0 p-1.5 rounded-lg text-stone-400 hover:text-red-600 hover:bg-red-50 transition-colors"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        )}
      </div>
    </div>
  );
};

const ETIQUETA = {
  color: { byn: 'B&N', color: 'Color' },
  caras: { simple: 'una faz', doble: 'doble faz' },
};

const resumenOpciones = (o) =>
  `${ETIQUETA.color[o.color]} · ${ETIQUETA.caras[o.caras]} · ${o.tamano} · ${o.copias} ${Number(o.copias) === 1 ? 'copia' : 'copias'}`;

export default FileUpload;
