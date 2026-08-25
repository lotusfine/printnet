import { useState } from 'react';
import { Link } from 'react-router-dom';
import ContactForm, { validateContacto, composeTelefono, DEFAULT_CONTACTO } from '../components/ContactForm';
import FileUpload, { validateRango } from '../components/fotocopias/FileUpload';
import PrintOptions from '../components/fotocopias/PrintOptions';
import OrderSummary from '../components/fotocopias/OrderSummary';
import { crearPedido } from '../api';
import { PEDIDOS_HABILITADOS } from '../config';
import PedidosDeshabilitados from '../components/PedidosDeshabilitados';

const DEFAULT_OPTIONS = {
  color: 'byn',
  caras: 'simple',
  copias: 1,
  tamano: 'A4',
  anillado: false,
};

// Páginas que se van a imprimir según el rango (espejo de pricing.py).
// Devuelve null si todavía no sabemos cuántas páginas tiene el documento —
// null significa "no sé", y nunca hay que reemplazarlo por un número
// inventado: de ahí salía el precio equivocado que llegaba al cliente.
const paginasEfectivas = (totalPaginas, rango) => {
  if (totalPaginas == null) return null;
  if (rango.modo !== 'rango') return totalPaginas;
  const v = rango.valor.trim();
  if (!/^\d+(-\d+)?$/.test(v)) return totalPaginas;
  const [inicio, fin = inicio] = v.split('-').map(Number);
  if (inicio < 1 || inicio > fin) return totalPaginas;
  return fin - inicio + 1;
};

const DEFAULT_RANGO = { modo: 'todas', valor: '' };

const Fotocopias = () => {
  const [fileInfo, setFileInfo] = useState(null);
  const [options, setOptions] = useState(DEFAULT_OPTIONS);
  const [contacto, setContacto] = useState(DEFAULT_CONTACTO);
  const [rango, setRango] = useState(DEFAULT_RANGO);
  const [errors, setErrors] = useState({});
  // idle | enviando | exito | error
  const [envio, setEnvio] = useState({ estado: 'idle' });

  const handleContactoChange = (nuevo) => {
    setContacto(nuevo);
    setErrors({});
    setEnvio({ estado: 'idle' });
  };

  const handleRangoChange = (nuevo) => {
    setRango(nuevo);
    setErrors({});
    setEnvio({ estado: 'idle' });
  };

  const handlePay = async () => {
    if (envio.estado === 'enviando') return;

    const errs = validateContacto(contacto);
    if (rango.modo === 'rango') {
      const rangoError = validateRango(rango.valor);
      if (rangoError) errs.rango = rangoError;
    }
    setErrors(errs);
    if (Object.keys(errs).length > 0) return;

    setEnvio({ estado: 'enviando' });
    try {
      // anillado viaja como terminación, no como opción de impresión
      const { anillado, ...opcionesImpresion } = options;
      const pedido = await crearPedido(
        {
          tipo: 'fotocopias',
          contacto: {
            nombre: contacto.nombre.trim(),
            telefono: composeTelefono(contacto),
            email: contacto.email.trim(),
          },
          opciones: opcionesImpresion,
          rango,
          terminaciones: anillado ? ['Anillado'] : [],
        },
        [fileInfo.file]
      );
      if (pedido.init_point) {
        // Pago real: derivar al Checkout Pro de MercadoPago. Al terminar,
        // MP devuelve al cliente a /estado/{token} (back_urls).
        setEnvio({ estado: 'redirigiendo' });
        window.location.href = pedido.init_point;
        return;
      }
      setEnvio({ estado: 'exito', pedido });
    } catch (e) {
      setEnvio({ estado: 'error', mensaje: e.message });
    }
  };

  return (
    <section className="flex flex-col space-y-8 md:space-y-12">
      <header className="flex flex-col gap-4">
        <Link
          to="/"
          className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-widest text-stone-500 hover:text-amber-700 transition-colors w-fit"
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18" />
          </svg>
          Volver al inicio
        </Link>
        <div className="text-center">
          <h1 className="text-4xl font-chalk md:text-6xl text-stone-800/90 mb-2">Fotocopias</h1>
          <p className="text-base italic font-chalk text-stone-500 md:text-lg">
            Subí tu archivo y configurá tu pedido
          </p>
        </div>
      </header>

      {!PEDIDOS_HABILITADOS && <PedidosDeshabilitados accent="amber" />}

      <div className={`grid w-full gap-8 md:gap-10 md:grid-cols-2 ${PEDIDOS_HABILITADOS ? '' : 'hidden'}`}>
        <FileUpload
          onFileChange={(info) => { setFileInfo(info); setEnvio({ estado: 'idle' }); }}
          pageRange={rango}
          onPageRangeChange={handleRangoChange}
          rangeError={errors.rango}
        />
        <ContactForm
          contacto={contacto}
          errors={errors}
          onChange={handleContactoChange}
          accent="amber"
        />
        <PrintOptions
          pages={paginasEfectivas(fileInfo?.pages ?? null, rango)}
          options={options}
          onChange={(o) => { setOptions(o); setEnvio({ estado: 'idle' }); }}
        />
        <OrderSummary
          fileInfo={fileInfo}
          options={options}
          pageRange={rango}
          pagesACobrar={paginasEfectivas(fileInfo?.pages ?? null, rango)}
          onPay={handlePay}
          enviando={envio.estado === 'enviando' || envio.estado === 'redirigiendo'}
        />
      </div>

      {envio.estado === 'redirigiendo' && (
        <p className="text-sm font-bold text-stone-500 text-center">
          Redirigiendo a MercadoPago para completar el pago…
        </p>
      )}

      {envio.estado === 'error' && (
        <p className="text-sm font-bold text-red-500 text-center max-w-xl mx-auto">
          No pudimos crear el pedido: {envio.mensaje}
        </p>
      )}

      {envio.estado === 'exito' && (
        <article className="w-full max-w-2xl mx-auto p-6 md:p-8 bg-green-50 border-2 border-green-300 shadow-xl rounded-sm relative overflow-hidden">
          <div className="absolute top-0 w-20 h-6 -translate-x-1/2 -translate-y-3 left-1/2 bg-white/60 rotate-2 md:w-24 md:h-8" />
          <div className="flex items-center justify-center gap-2 mb-6">
            <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5 text-green-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <h2 className="text-[10px] font-black tracking-[0.3em] uppercase text-stone-500/60">
              Pedido #{envio.pedido.id} confirmado
            </h2>
          </div>
          <dl className="space-y-2">
            <div className="flex justify-between gap-4 py-1.5 border-b border-green-100">
              <dt className="text-xs font-bold uppercase tracking-widest text-stone-400">Estado</dt>
              <dd className="text-sm font-bold text-stone-700 capitalize">{envio.pedido.estado}</dd>
            </div>
            <div className="flex justify-between gap-4 py-1.5 border-b border-green-100">
              <dt className="text-xs font-bold uppercase tracking-widest text-stone-400">Páginas reales del PDF</dt>
              <dd className="text-sm font-bold text-stone-700">{envio.pedido.paginas}</dd>
            </div>
            <div className="flex justify-between gap-4 py-1.5 border-b border-green-100">
              <dt className="text-xs font-bold uppercase tracking-widest text-stone-400">Precio final</dt>
              <dd className="text-lg font-black text-amber-700">${envio.pedido.precio_total?.toLocaleString('es-AR')}</dd>
            </div>
            <div className="flex justify-between gap-4 py-1.5">
              <dt className="text-xs font-bold uppercase tracking-widest text-stone-400 shrink-0">Código de seguimiento</dt>
              <dd className="text-xs font-mono font-bold text-stone-600 break-all text-right">{envio.pedido.token}</dd>
            </div>
          </dl>
          <p className="mt-6 text-xs italic text-stone-400 text-center">
            Te enviamos un email con el detalle. Guardá el código para consultar el estado.
          </p>
        </article>
      )}
    </section>
  );
};

export default Fotocopias;
