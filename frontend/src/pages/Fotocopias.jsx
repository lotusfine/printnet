import { useState } from 'react';
import { Link } from 'react-router-dom';
import ContactForm, { validateContacto, composeTelefono, DEFAULT_CONTACTO } from '../components/ContactForm';
import FileUpload from '../components/fotocopias/FileUpload';
import PrintOptions from '../components/fotocopias/PrintOptions';
import OrderSummary from '../components/fotocopias/OrderSummary';
import { crearPedido } from '../api';
import { PEDIDOS_HABILITADOS } from '../config';
import { paginasDelRango } from '../precio';
import PedidosDeshabilitados from '../components/PedidosDeshabilitados';

// La configuración NO tiene valores por defecto, a propósito.
//
// Si los tuviera, un cliente distraído podría pagar un pedido configurado por
// nosotros sin haberlo mirado. Cada documento arranca sin configurar y la
// pantalla lo muestra atenuado hasta que el cliente decide.
const OPCIONES_VACIAS = { color: '', caras: '', copias: '', tamano: '' };
const RANGO_POR_DEFECTO = { modo: 'todas', valor: '' };

const configurado = (doc) =>
  doc.opciones.color && doc.opciones.caras && doc.opciones.copias && doc.opciones.tamano;

/** Documento listo para cotizar: páginas a imprimir según su rango. */
const paraCotizar = (doc) => {
  if (doc.estado !== 'listo' || !configurado(doc)) return null;
  return {
    paginas: paginasDelRango(doc.paginas, doc.rango),
    opciones: { ...doc.opciones, copias: Number(doc.opciones.copias) },
    terminaciones: [],
  };
};

let proximoId = 1;

const Fotocopias = () => {
  const [docs, setDocs] = useState([]);
  const [seleccionado, setSeleccionado] = useState(null);
  const [contacto, setContacto] = useState(DEFAULT_CONTACTO);
  const [errors, setErrors] = useState({});
  // idle | enviando | redirigiendo | exito | error
  const [envio, setEnvio] = useState({ estado: 'idle' });

  const limpiarEnvio = () => setEnvio({ estado: 'idle' });

  const actualizarDoc = (id, cambios) => {
    setDocs((prev) => prev.map((d) => (d.id === id ? { ...d, ...cambios } : d)));
    limpiarEnvio();
  };

  const agregarDocs = (archivos) => {
    const nuevos = archivos.map((f) => ({
      id: proximoId++,
      file: f,
      name: f.name,
      paginas: null,
      convertido: false,
      estado: 'contando',
      error: null,
      opciones: { ...OPCIONES_VACIAS },
      rango: { ...RANGO_POR_DEFECTO },
    }));
    setDocs((prev) => [...prev, ...nuevos]);
    setSeleccionado((actual) => actual ?? nuevos[0]?.id ?? null);
    limpiarEnvio();
    return nuevos;
  };

  const quitarDoc = (id) => {
    setDocs((prev) => {
      const restantes = prev.filter((d) => d.id !== id);
      setSeleccionado((sel) => (sel === id ? restantes[0]?.id ?? null : sel));
      return restantes;
    });
    limpiarEnvio();
  };

  const docSeleccionado = docs.find((d) => d.id === seleccionado) || null;

  const aplicarATodos = (opciones) => {
    setDocs((prev) => prev.map((d) =>
      d.estado === 'error' ? d : { ...d, opciones: { ...opciones } }
    ));
    limpiarEnvio();
  };

  const cotizables = docs.map(paraCotizar);
  const conError = docs.filter((d) => d.estado === 'error');
  const sinConfigurar = docs.filter((d) => d.estado === 'listo' && !configurado(d));
  const contando = docs.some((d) => d.estado === 'contando');

  const handlePay = async () => {
    if (envio.estado === 'enviando') return;

    if (!docs.length) {
      setEnvio({ estado: 'error', mensaje: 'Subí al menos un documento.' });
      return;
    }
    if (conError.length) {
      setEnvio({
        estado: 'error',
        mensaje: `Quitá ${conError.map((d) => `"${d.name}"`).join(', ')} para poder continuar.`,
      });
      return;
    }
    if (contando) return;
    if (sinConfigurar.length) {
      setSeleccionado(sinConfigurar[0].id);
      setEnvio({
        estado: 'error',
        mensaje: `Falta configurar ${sinConfigurar.map((d) => `"${d.name}"`).join(', ')}.`,
      });
      return;
    }

    const errs = validateContacto(contacto);
    setErrors(errs);
    if (Object.keys(errs).length > 0) return;

    setEnvio({ estado: 'enviando' });
    try {
      const documentos = docs.map((d) => ({
        opciones: { ...d.opciones, copias: Number(d.opciones.copias) },
        rango: d.rango,
        terminaciones: [],
      }));
      const pedido = await crearPedido(
        {
          tipo: 'fotocopias',
          contacto: {
            nombre: contacto.nombre.trim(),
            telefono: composeTelefono(contacto),
            email: contacto.email.trim(),
          },
          documentos,
        },
        docs.map((d) => d.file)
      );
      if (pedido.init_point) {
        setEnvio({ estado: 'redirigiendo' });
        window.location.href = pedido.init_point;
        return;
      }
      setEnvio({ estado: 'exito', pedido });
    } catch (e) {
      setEnvio({ estado: 'error', mensaje: e.message });
    }
  };

  if (!PEDIDOS_HABILITADOS) return <PedidosDeshabilitados servicio="fotocopias" />;

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
            Subí tus archivos y configurá tu pedido
          </p>
        </div>
      </header>

      <div className="grid gap-6 md:gap-8 md:grid-cols-2">
        <FileUpload
          documentos={docs}
          seleccionado={seleccionado}
          onSeleccionar={(id) => { setSeleccionado(id); limpiarEnvio(); }}
          onAgregar={agregarDocs}
          onActualizar={actualizarDoc}
          onQuitar={quitarDoc}
        />
        <ContactForm
          contacto={contacto}
          errors={errors}
          onChange={(nuevo) => { setContacto(nuevo); setErrors({}); limpiarEnvio(); }}
          accent="amber"
        />
        <PrintOptions
          documento={docSeleccionado}
          cantidadDocumentos={docs.length}
          onChange={(opciones) => actualizarDoc(docSeleccionado.id, { opciones })}
          onRangoChange={(rango) => actualizarDoc(docSeleccionado.id, { rango })}
          onAplicarATodos={aplicarATodos}
        />
        <OrderSummary
          documentos={docs}
          cotizables={cotizables}
          onPay={handlePay}
          enviando={envio.estado === 'enviando' || envio.estado === 'redirigiendo'}
          bloqueado={!docs.length || !!conError.length || !!sinConfigurar.length || contando}
        />
      </div>

      {envio.estado === 'redirigiendo' && (
        <p className="text-sm font-bold text-stone-500 text-center">
          Redirigiendo a MercadoPago para completar el pago…
        </p>
      )}

      {envio.estado === 'error' && (
        <p className="text-sm font-bold text-red-500 text-center max-w-xl mx-auto">
          {envio.mensaje}
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
              <dt className="text-xs font-bold uppercase tracking-widest text-stone-400">Documentos</dt>
              <dd className="text-sm font-bold text-stone-700">{docs.length}</dd>
            </div>
            <div className="flex justify-between gap-4 py-1.5">
              <dt className="text-xs font-bold uppercase tracking-widest text-stone-400">Seguimiento</dt>
              <dd className="text-sm font-bold text-stone-700">
                <Link to={`/estado/${envio.pedido.token}`} className="text-amber-700 underline">
                  Ver estado
                </Link>
              </dd>
            </div>
          </dl>
        </article>
      )}
    </section>
  );
};

export default Fotocopias;
