import { useState, useRef, useEffect } from 'react';
import { borrarToken, guardarToken, leerToken } from '../adminAuth';
import { listarPedidosAdmin, cambiarEstadoPedido, listarImpresoras } from '../api';

// ─────────────────────────────────────────────
// DATOS DE RELLENO (solo impresoras)
// ─────────────────────────────────────────────
// OJO: los pedidos NO son mock — vienen del backend (GET /admin/orders), se
// refrescan cada 15 s y los botones de estado llaman a PATCH /admin/orders/{id}.
// Lo único de mentira acá es esta lista, que se muestra si /admin/printers no
// responde. Si ves "HP LaserJet 1" en el panel, es que el backend no contestó.
const INIT_PRINTERS = [
  {
    id: 1, nombre: 'HP LaserJet 1', tipo: 'laser', estado: 'error',
    errorTipo: 'Tóner bajo', papel: 150, hojas: 150, tonner: 15,
  },
  {
    id: 2, nombre: 'Epson L3250', tipo: 'tinta', estado: 'activa',
    errorTipo: null, papel: 340, hojas: 340, tinta: 80,
  },
];

let nextPrinterId = 3;

// ─────────────────────────────────────────────
// HELPERS
// ─────────────────────────────────────────────
const ars = (n) => (n == null ? 'A cotizar' : `$${n.toLocaleString('es-AR')}`);

const BADGE = {
  pendiente_pago: 'bg-orange-500/15 text-orange-300 border border-orange-500/30',
  pago_rechazado: 'bg-red-500/15 text-red-300 border border-red-500/30',
  pendiente:   'bg-yellow-500/15 text-yellow-300 border border-yellow-500/30',
  imprimiendo: 'bg-blue-500/15 text-blue-300 border border-blue-500/30',
  listo:       'bg-green-500/15 text-green-300 border border-green-500/30',
  entregado:   'bg-stone-500/20 text-stone-400 border border-stone-600/30',
  cancelado:   'bg-stone-700/40 text-stone-500 border border-stone-600/30',
};

const BADGE_LABEL = {
  pendiente_pago: 'Esperando pago', pago_rechazado: 'Pago rechazado',
  pendiente: 'Pendiente', imprimiendo: 'Imprimiendo',
  listo: 'Listo', entregado: 'Entregado', cancelado: 'Cancelado',
};

const LEFT_BORDER = {
  pendiente_pago: 'border-l-4 border-l-orange-500',
  pago_rechazado: 'border-l-4 border-l-red-600',
  imprimiendo: 'border-l-4 border-l-blue-500',
  listo:       'border-l-4 border-l-green-500',
  pendiente:   'border-l-4 border-l-yellow-500',
  entregado:   'border-l-4 border-l-stone-600',
  cancelado:   'border-l-4 border-l-stone-700',
};

const LevelBar = ({ label, value }) => {
  const color = value > 50 ? 'bg-green-500' : value > 20 ? 'bg-yellow-400' : 'bg-red-500';
  return (
    <div>
      <div className="flex justify-between mb-1">
        <span className="text-[10px] font-bold uppercase tracking-widest text-stone-400">{label}</span>
        <span className="text-[10px] font-bold text-stone-300">{value}%</span>
      </div>
      <div className="h-2 rounded-full bg-stone-700">
        <div className={`h-2 rounded-full transition-all ${color}`} style={{ width: `${value}%` }} />
      </div>
    </div>
  );
};

// ─────────────────────────────────────────────
// MODAL BASE
// ─────────────────────────────────────────────
const Modal = ({ onClose, children }) => (
  <div
    className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm px-4"
    onClick={onClose}
  >
    <div
      className="bg-stone-800 border border-stone-700 rounded-2xl shadow-2xl w-full max-w-sm p-6"
      onClick={(e) => e.stopPropagation()}
    >
      {children}
    </div>
  </div>
);

// ─────────────────────────────────────────────
// LOGIN SCREEN
// ─────────────────────────────────────────────
const LoginScreen = ({ onLogin }) => {
  const [pass, setPass] = useState('');
  const [error, setError] = useState('');
  const [verificando, setVerificando] = useState(false);

  // El token no se valida acá: se guarda y se prueba contra el backend. Así
  // el operador se entera en el momento si está mal, en vez de entrar a un
  // panel vacío que no sabe explicar por qué no trae nada.
  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!pass.trim() || verificando) return;

    setVerificando(true);
    setError('');
    guardarToken(pass);
    try {
      await listarPedidosAdmin();
      onLogin();
    } catch (err) {
      borrarToken();
      setPass('');
      if (err.status === 401) {
        setError('Token incorrecto');
      } else if (err.status === 503) {
        setError('El servidor no tiene configurado el token de admin');
      } else {
        setError('No se pudo conectar con el servidor');
      }
    } finally {
      setVerificando(false);
    }
  };

  return (
    <div className="min-h-screen bg-stone-900 flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="text-center mb-10">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-amber-500 mb-4 shadow-lg shadow-amber-500/20">
            <span className="text-2xl font-black text-white">P</span>
          </div>
          <h1 className="text-2xl font-black text-white tracking-tight">PrintNet</h1>
          <p className="text-xs font-bold uppercase tracking-[0.3em] text-stone-500 mt-1">Panel de Administración</p>
        </div>

        <form onSubmit={handleSubmit} className="bg-stone-800 border border-stone-700 rounded-2xl p-6 shadow-xl space-y-4">
          <div>
            <label className="block text-[10px] font-black uppercase tracking-[0.25em] text-stone-400 mb-2">
              Token de acceso
            </label>
            <input
              type="password"
              value={pass}
              onChange={(e) => { setPass(e.target.value); setError(''); }}
              autoFocus
              placeholder="••••••••••••••••"
              className={`w-full px-4 py-3 rounded-xl bg-stone-900 border text-sm text-white placeholder-stone-600 focus:outline-none transition-colors ${
                error ? 'border-red-500 focus:border-red-400' : 'border-stone-600 focus:border-amber-500'
              }`}
            />
            {error && (
              <p className="mt-2 text-xs font-bold text-red-400 flex items-center gap-1.5">
                <svg xmlns="http://www.w3.org/2000/svg" className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="currentColor">
                  <path fillRule="evenodd" d="M9.401 3.003c1.155-2 4.043-2 5.197 0l7.355 12.748c1.154 2-.29 4.5-2.599 4.5H4.645c-2.309 0-3.752-2.5-2.598-4.5L9.4 3.003zM12 8.25a.75.75 0 01.75.75v3.75a.75.75 0 01-1.5 0V9a.75.75 0 01.75-.75zm0 8.25a.75.75 0 100-1.5.75.75 0 000 1.5z" clipRule="evenodd"/>
                </svg>
                {error}
              </p>
            )}
            <p className="mt-3 text-[11px] leading-relaxed text-stone-500">
              Es el valor de <span className="font-mono text-stone-400">PRINTNET_ADMIN_TOKEN</span>,
              del archivo <span className="font-mono text-stone-400">.env</span> del servidor.
              Queda guardado en este navegador.
            </p>
          </div>
          <button
            type="submit"
            disabled={verificando || !pass.trim()}
            className="w-full py-3 rounded-xl bg-amber-500 hover:bg-amber-400 active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed disabled:active:scale-100 text-white font-black text-sm uppercase tracking-widest transition-all shadow-md shadow-amber-500/20"
          >
            {verificando ? 'Verificando…' : 'Ingresar'}
          </button>
        </form>
      </div>
    </div>
  );
};

// ─────────────────────────────────────────────
// STATS ROW
// ─────────────────────────────────────────────
const StatsRow = ({ orders }) => {
  const pendientes  = orders.filter(o => o.estado === 'pendiente').length;
  const completados = orders.filter(o => o.estado === 'entregado').length;
  const ingresos    = orders.filter(o => o.estado !== 'cancelado').reduce((s, o) => s + (o.precio ?? 0), 0);
  const cola        = orders.filter(o => o.estado === 'imprimiendo').length;

  const stats = [
    { label: 'Pendientes', value: pendientes, unit: 'pedidos', color: 'text-yellow-400' },
    { label: 'Hoy',        value: completados, unit: 'completados', color: 'text-green-400' },
    { label: 'Ingresos',   value: ars(ingresos), unit: 'del día', color: 'text-amber-400' },
    { label: 'Cola',       value: cola, unit: 'imprimiendo', color: 'text-blue-400' },
  ];

  return (
    <div className="flex gap-3 overflow-x-auto pb-1 scrollbar-none">
      {stats.map(({ label, value, unit, color }) => (
        <div key={label} className="flex-none w-36 bg-stone-800 border border-stone-700 rounded-xl p-4 shadow-sm">
          <p className="text-[10px] font-black uppercase tracking-[0.2em] text-stone-500 mb-2">{label}</p>
          <p className={`text-2xl font-black ${color}`}>{value}</p>
          <p className="text-[10px] text-stone-500 mt-0.5">{unit}</p>
        </div>
      ))}
    </div>
  );
};

// ─────────────────────────────────────────────
// ORDER CARD
// ─────────────────────────────────────────────
const OrderCard = ({ order, onTransition, onCancel }) => {
  const [contactOpen, setContactOpen] = useState(false);

  const Btn = ({ onClick, children, variant = 'ghost' }) => {
    const base = 'px-3 py-1.5 rounded-lg text-xs font-bold uppercase tracking-wide transition-all active:scale-95 whitespace-nowrap';
    const styles = {
      ghost:    `${base} bg-stone-700/60 text-stone-300 hover:bg-stone-700`,
      primary:  `${base} bg-amber-500 text-white hover:bg-amber-400 shadow-sm shadow-amber-500/20`,
      danger:   `${base} bg-red-500/15 text-red-400 border border-red-500/30 hover:bg-red-500/25`,
      success:  `${base} bg-green-500/15 text-green-400 border border-green-500/30 hover:bg-green-500/25`,
    };
    return <button onClick={onClick} className={styles[variant]}>{children}</button>;
  };

  const actions = {
    pendiente: (
      <>
        <Btn onClick={() => alert(order.archivo)}>Ver archivo</Btn>
        <Btn onClick={() => setContactOpen(true)}>Ver contacto</Btn>
        <Btn variant="primary" onClick={() => onTransition(order.id, 'imprimiendo')}>Iniciar impresión</Btn>
        <Btn variant="danger" onClick={() => onCancel(order.id)}>Cancelar</Btn>
      </>
    ),
    imprimiendo: (
      <>
        <Btn onClick={() => alert(order.archivo)}>Ver archivo</Btn>
        <Btn onClick={() => setContactOpen(true)}>Ver contacto</Btn>
        <Btn variant="success" onClick={() => onTransition(order.id, 'listo')}>Marcar como listo</Btn>
        <Btn variant="danger" onClick={() => onCancel(order.id)}>Cancelar</Btn>
      </>
    ),
    listo: (
      <>
        <Btn onClick={() => alert(order.archivo)}>Ver archivo</Btn>
        <Btn onClick={() => setContactOpen(true)}>Ver contacto</Btn>
        <Btn variant="success" onClick={() => onTransition(order.id, 'entregado')}>Marcar como entregado</Btn>
      </>
    ),
  };

  return (
    <>
      <div className={`bg-stone-800 border border-stone-700 rounded-xl overflow-hidden shadow-sm ${LEFT_BORDER[order.estado]}`}>
        <div className="p-4">
          {/* Header de la card */}
          <div className="flex items-start justify-between gap-2 mb-3">
            <div>
              <span className="text-[10px] font-black text-stone-500">#{order.id} · hace {order.hace} min</span>
              <p className="text-base font-black text-white mt-0.5">{order.cliente}</p>
            </div>
            <div className="flex items-center gap-1.5 shrink-0">
              {order.requiere_manual && (
                <span className="text-[10px] font-black uppercase tracking-widest px-2.5 py-1 rounded-full bg-purple-500/15 text-purple-300 border border-purple-500/30">
                  Manual
                </span>
              )}
              <span className={`text-[10px] font-black uppercase tracking-widest px-2.5 py-1 rounded-full ${BADGE[order.estado]}`}>
                {BADGE_LABEL[order.estado]}
              </span>
            </div>
          </div>

          {/* Archivo */}
          <div className="flex items-center gap-2 mb-3">
            <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4 text-red-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
            </svg>
            <span className="text-xs text-stone-400 truncate">{order.archivo}</span>
          </div>

          {/* Specs */}
          <div className="flex items-center justify-between gap-2 flex-wrap">
            <span className="text-xs text-stone-400">
              {order.tipo === 'fotos' ? (
                <>
                  Especial: {order.material}
                  {order.formato ? ` ${order.formato}` : ''}
                  {order.gramaje ? ` ${order.gramaje}g` : ''}
                  {' · '}{(order.archivos ?? [order.archivo]).length} archivo{(order.archivos ?? [1]).length !== 1 ? 's' : ''}
                  {order.acabado ? ` · ${order.acabado}` : ''}
                </>
              ) : (
                <>
                  {order.paginas} pág × {order.copias} {order.copias > 1 ? 'copias' : 'copia'} · {order.color ? 'Color' : 'B/N'} · {order.doble ? 'Doble cara' : 'Una cara'}
                  {order.rango ? ` · Rango ${order.rango}` : ''}
                  {order.acabado ? ` · ${order.acabado}` : ''}
                </>
              )}
            </span>
            <span className="text-sm font-black text-amber-400 shrink-0">{ars(order.precio)}</span>
          </div>
        </div>

        {/* Acciones */}
        {actions[order.estado] && (
          <div className="px-4 pb-4 flex flex-wrap gap-2">
            {actions[order.estado]}
          </div>
        )}
      </div>

      {/* Modal contacto */}
      {contactOpen && (
        <Modal onClose={() => setContactOpen(false)}>
          <div className="flex items-center justify-between mb-5">
            <h3 className="text-sm font-black uppercase tracking-widest text-white">Datos de contacto</h3>
            <button onClick={() => setContactOpen(false)} className="text-stone-500 hover:text-stone-300 transition-colors">
              <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          <div className="space-y-3">
            <div>
              <p className="text-[10px] font-black uppercase tracking-widest text-stone-500 mb-1">Nombre</p>
              <p className="text-sm font-bold text-white">{order.cliente}</p>
            </div>
            <div>
              <p className="text-[10px] font-black uppercase tracking-widest text-stone-500 mb-1">Teléfono</p>
              <p className="text-sm font-bold text-white">{order.contacto.tel}</p>
            </div>
            <div>
              <p className="text-[10px] font-black uppercase tracking-widest text-stone-500 mb-1">Email</p>
              <p className="text-sm font-bold text-white">{order.contacto.email}</p>
            </div>
          </div>
          <button
            onClick={() => setContactOpen(false)}
            className="mt-6 w-full py-2.5 rounded-xl bg-stone-700 hover:bg-stone-600 text-stone-200 text-xs font-bold uppercase tracking-widest transition-all"
          >
            Cerrar
          </button>
        </Modal>
      )}
    </>
  );
};

// ─────────────────────────────────────────────
// ORDERS SECTION
// ─────────────────────────────────────────────
const FILTERS = [
  { key: 'todos', label: 'Todos' },
  { key: 'pendiente', label: 'Pendientes' },
  { key: 'imprimiendo', label: 'Imprimiendo' },
  { key: 'listo', label: 'Listos' },
];

const OrdersSection = ({ orders, onTransition, onCancel }) => {
  const [filter, setFilter] = useState('todos');

  const visible = filter === 'todos' ? orders : orders.filter(o => o.estado === filter);

  return (
    <section>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-[10px] font-black uppercase tracking-[0.3em] text-stone-400">Pedidos</h2>
        <span className="text-xs text-stone-600">{visible.length} resultado{visible.length !== 1 ? 's' : ''}</span>
      </div>

      {/* Filtros pill */}
      <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-none mb-5">
        {FILTERS.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setFilter(key)}
            className={`shrink-0 px-4 py-1.5 rounded-full text-xs font-bold uppercase tracking-widest transition-all ${
              filter === key
                ? 'bg-amber-500 text-white shadow-sm shadow-amber-500/20'
                : 'bg-stone-800 border border-stone-700 text-stone-400 hover:text-stone-200 hover:border-stone-500'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="space-y-3">
        {visible.length === 0 ? (
          <p className="text-sm text-stone-600 italic text-center py-8">Sin pedidos en este estado</p>
        ) : (
          visible.map(order => (
            <OrderCard
              key={order.id}
              order={order}
              onTransition={onTransition}
              onCancel={onCancel}
            />
          ))
        )}
      </div>
    </section>
  );
};

// ─────────────────────────────────────────────
// STATS DROPDOWN (header)
// ─────────────────────────────────────────────
const StatsDropdown = ({ orders }) => {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return;
    const handleClickOutside = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [open]);

  const pedidosHoy = orders.filter(o => o.estado === 'entregado' || o.estado === 'pendiente').length;
  const ingresos = orders.filter(o => o.estado !== 'cancelado').reduce((s, o) => s + (o.precio ?? 0), 0);
  const cancelados = orders.filter(o => o.estado === 'cancelado').length;

  const metrics = [
    { label: 'Pedidos hoy', value: pedidosHoy, color: 'text-yellow-400' },
    { label: 'Ingresos del día', value: ars(ingresos), color: 'text-amber-400' },
    { label: 'Cancelados hoy', value: cancelados, color: 'text-red-400' },
    { label: 'Tiempo promedio de entrega', value: '12 min', color: 'text-blue-400' },
    { label: 'Impresora más usada', value: 'HP LaserJet 1', color: 'text-green-400' },
  ];

  return (
    <div ref={ref} className="static md:relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className={`flex items-center gap-1.5 p-2 rounded-xl text-[10px] font-bold uppercase tracking-widest transition-all ${
          open ? 'text-amber-400 bg-stone-800' : 'text-stone-500 hover:text-stone-300 hover:bg-stone-800'
        }`}
        title="Estadísticas"
      >
        <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
        </svg>
        <span className="hidden sm:inline">Estadísticas</span>
      </button>

      {open && (
        <div className="absolute left-0 right-0 top-full md:left-auto md:right-0 md:w-80 bg-stone-800 border border-stone-700 rounded-b-2xl md:rounded-2xl md:mt-2 shadow-2xl p-4 z-40">
          <p className="mb-2 text-[10px] font-black uppercase tracking-[0.3em] text-stone-500">
            Estadísticas del día
          </p>
          <div>
            {metrics.map(({ label, value, color }) => (
              <div key={label} className="flex items-center justify-between gap-4 py-2.5 border-b border-stone-700/60 last:border-0">
                <span className="text-xs text-stone-400">{label}</span>
                <span className={`text-sm font-black ${color}`}>{value}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

// ─────────────────────────────────────────────
// PRINTERS SIDEBAR
// ─────────────────────────────────────────────
const PrinterCard = ({ p, onResolve, onRename, onLoadPaper }) => {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(p.nombre);
  const [carga, setCarga] = useState('');

  const startEdit = () => {
    setDraft(p.nombre);
    setEditing(true);
  };

  // Si el campo queda vacío, vuelve al nombre anterior sin guardar
  const saveName = () => {
    setEditing(false);
    const v = draft.trim();
    if (v) onRename(p.id, v);
  };

  const handleCargar = () => {
    const n = parseInt(carga, 10);
    if (!n || n <= 0) return;
    onLoadPaper(p.id, n);
    setCarga('');
  };

  return (
    <div>
      <div className="flex items-center justify-between gap-2 mb-1">
        {editing ? (
          <input
            autoFocus
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onBlur={saveName}
            onKeyDown={(e) => { if (e.key === 'Enter') e.currentTarget.blur(); }}
            className="flex-1 min-w-0 px-2 py-1 text-sm font-black bg-stone-900 border border-amber-500 rounded-lg text-white focus:outline-none"
          />
        ) : (
          <div className="flex items-center gap-1.5 min-w-0">
            <p className="text-sm font-black text-white truncate">{p.nombre}</p>
            <button
              onClick={startEdit}
              title="Editar nombre"
              className="shrink-0 p-1 text-stone-500 hover:text-stone-300 transition-colors"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10" />
              </svg>
            </button>
          </div>
        )}
        <span className={`shrink-0 text-[10px] font-black uppercase tracking-widest px-2.5 py-1 rounded-full border ${
          p.estado === 'activa'
            ? 'bg-green-500/15 text-green-400 border-green-500/30'
            : 'bg-red-500/15 text-red-400 border-red-500/30'
        }`}>
          {p.estado === 'activa' ? 'Activa' : 'Error'}
        </span>
      </div>
      <p className="text-[10px] text-stone-500 uppercase tracking-widest mb-3">
        {p.tipo === 'laser' ? 'Láser' : 'Tinta'}
      </p>

      {p.estado === 'error' && (
        <div className="mb-3 space-y-2">
          <div className="flex items-center gap-2 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
            <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4 text-red-400 shrink-0" viewBox="0 0 24 24" fill="currentColor">
              <path fillRule="evenodd" d="M9.401 3.003c1.155-2 4.043-2 5.197 0l7.355 12.748c1.154 2-.29 4.5-2.599 4.5H4.645c-2.309 0-3.752-2.5-2.598-4.5L9.4 3.003zM12 8.25a.75.75 0 01.75.75v3.75a.75.75 0 01-1.5 0V9a.75.75 0 01.75-.75zm0 8.25a.75.75 0 100-1.5.75.75 0 000 1.5z" clipRule="evenodd" />
            </svg>
            <span className="text-xs font-bold text-red-400">{p.errorTipo}</span>
          </div>
          <button
            onClick={() => onResolve(p.id)}
            className="w-full py-2 rounded-lg bg-stone-700 hover:bg-stone-600 text-stone-200 text-xs font-bold uppercase tracking-widest transition-all active:scale-95"
          >
            Marcar como resuelto
          </button>
        </div>
      )}

      <LevelBar
        label={p.tipo === 'laser' ? 'Tóner' : 'Tinta'}
        value={p.tipo === 'laser' ? p.tonner : p.tinta}
      />

      {/* Papel */}
      <div className="mt-3">
        <div className="flex justify-between mb-1.5">
          <span className="text-[10px] font-bold uppercase tracking-widest text-stone-400">Papel</span>
          <span className="text-[10px] font-bold text-stone-300">{p.hojas} hojas</span>
        </div>
        <div className="flex gap-2">
          <input
            type="number"
            min="0"
            value={carga}
            onChange={(e) => setCarga(e.target.value)}
            placeholder="0"
            className="w-20 px-2 py-1.5 text-xs font-bold bg-stone-900 border border-stone-600 rounded-lg text-white placeholder-stone-600 focus:outline-none focus:border-amber-500 transition-colors"
          />
          <button
            onClick={handleCargar}
            className="px-3 py-1.5 rounded-lg bg-stone-700/60 hover:bg-stone-700 text-stone-300 text-xs font-bold uppercase tracking-wide transition-all active:scale-95"
          >
            Cargar
          </button>
        </div>
      </div>
    </div>
  );
};

const PrintersSidebar = ({ printers, onResolve, onRename, onLoadPaper, onAdd }) => {
  const [formOpen, setFormOpen] = useState(false);
  const [nombre, setNombre] = useState('');

  const handleAgregar = () => {
    const v = nombre.trim();
    if (!v) return;
    onAdd(v);
    setNombre('');
    setFormOpen(false);
  };

  return (
    <section className="bg-stone-800/60 border border-stone-700 rounded-2xl p-4">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-[10px] font-black uppercase tracking-[0.3em] text-stone-400">Impresoras</h2>
        <button
          onClick={() => setFormOpen((o) => !o)}
          className="px-2.5 py-1 rounded-lg bg-stone-700/60 hover:bg-stone-700 text-stone-300 text-xs font-bold transition-all"
        >
          Conectar +
        </button>
      </div>

      {formOpen && (
        <div className="mb-4 p-3 bg-stone-900/60 border border-stone-700 rounded-xl">
          <label className="block mb-1.5 text-[10px] font-black uppercase tracking-widest text-stone-500">
            Nombre de impresora
          </label>
          <input
            autoFocus
            value={nombre}
            onChange={(e) => setNombre(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') handleAgregar(); }}
            placeholder="Ej: HP LaserJet 2"
            className="w-full px-3 py-2 mb-2 text-xs font-bold bg-stone-900 border border-stone-600 rounded-lg text-white placeholder-stone-600 focus:outline-none focus:border-amber-500 transition-colors"
          />
          <div className="flex gap-2">
            <button
              onClick={handleAgregar}
              className="flex-1 py-1.5 rounded-lg bg-amber-500 hover:bg-amber-400 text-white text-xs font-bold uppercase tracking-wide transition-all active:scale-95"
            >
              Agregar
            </button>
            <button
              onClick={() => { setFormOpen(false); setNombre(''); }}
              className="flex-1 py-1.5 rounded-lg bg-stone-700/60 hover:bg-stone-700 text-stone-300 text-xs font-bold uppercase tracking-wide transition-all"
            >
              Cancelar
            </button>
          </div>
        </div>
      )}

      <div className="divide-y divide-stone-700/60">
        {printers.map((p) => (
          <div key={p.id} className="py-4 first:pt-0 last:pb-0">
            <PrinterCard
              p={p}
              onResolve={onResolve}
              onRename={onRename}
              onLoadPaper={onLoadPaper}
            />
          </div>
        ))}
      </div>
    </section>
  );
};

// ─────────────────────────────────────────────
// ADMIN PANEL
// ─────────────────────────────────────────────
const AdminPanel = ({ onLogout }) => {
  const [orders, setOrders] = useState([]);
  const [printers, setPrinters] = useState(INIT_PRINTERS);
  const [cancelTarget, setCancelTarget] = useState(null);
  // 'cargando' | 'ok' | 'noauth' | 'error'
  const [conexion, setConexion] = useState('cargando');
  const [detalleError, setDetalleError] = useState('');

  const cargarPedidos = async () => {
    try {
      setOrders(await listarPedidosAdmin());
      setConexion('ok');
    } catch (e) {
      // "No autorizado" y "el servidor no responde" se arreglan distinto:
      // uno lo resuelve el operador acá, el otro es un problema del local.
      if (e.status === 401) {
        setConexion('noauth');
      } else {
        setConexion('error');
        setDetalleError(e.message);
      }
    }
  };

  useEffect(() => {
    cargarPedidos();
    // impresoras: solo carga inicial (la gestión del sidebar sigue siendo local)
    listarImpresoras().then(setPrinters).catch(() => {});
    const timer = setInterval(cargarPedidos, 15000);
    return () => clearInterval(timer);
  }, []);

  const handleTransition = async (id, newState) => {
    try {
      const actualizado = await cambiarEstadoPedido(id, newState);
      setOrders(prev => prev.map(o => o.id === id ? actualizado : o));
    } catch (e) {
      alert(`No se pudo cambiar el estado: ${e.message}`);
    }
  };

  const handleCancelRequest = (id) => setCancelTarget(id);

  const handleCancelConfirm = async () => {
    const id = cancelTarget;
    setCancelTarget(null);
    await handleTransition(id, 'cancelado');
  };

  const handleResolve = (id) => {
    setPrinters(prev => prev.map(p => p.id === id ? { ...p, estado: 'activa', errorTipo: null } : p));
  };

  const handleRenamePrinter = (id, nombre) => {
    setPrinters(prev => prev.map(p => p.id === id ? { ...p, nombre } : p));
  };

  const handleAddPrinter = (nombre) => {
    setPrinters(prev => [
      ...prev,
      {
        id: nextPrinterId++, nombre, tipo: 'laser', estado: 'activa',
        errorTipo: null, papel: 100, hojas: 100, tonner: 100,
      },
    ]);
  };

  const handleLoadPaper = (id, cantidad) => {
    setPrinters(prev => prev.map(p =>
      p.id === id ? { ...p, hojas: p.hojas + cantidad, papel: p.papel + cantidad } : p
    ));
  };

  return (
    <div className="min-h-screen bg-stone-900 text-white">
      {/* Header */}
      <header className="sticky top-0 z-30 bg-stone-900/80 backdrop-blur border-b border-stone-800 px-4 py-3">
        <div className="max-w-6xl mx-auto flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-amber-500 flex items-center justify-center shadow-md shadow-amber-500/20 shrink-0">
              <span className="text-sm font-black text-white">P</span>
            </div>
            <div>
              <p className="text-sm font-black text-white leading-none">Panel de operador</p>
              <p className="text-[10px] text-stone-400 flex items-center gap-1.5 mt-0.5">
                <span className="inline-block w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
                En línea · Librería Glaxara
              </p>
            </div>
          </div>
          <div className="flex items-center gap-1">
            {/* Estadísticas */}
            <StatsDropdown orders={orders} />
            {/* Campana */}
            <button className="p-2 rounded-xl text-stone-500 hover:text-stone-300 hover:bg-stone-800 transition-all" title="Notificaciones">
              <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0" />
              </svg>
            </button>
            {/* Engranaje */}
            <button className="p-2 rounded-xl text-stone-500 hover:text-stone-300 hover:bg-stone-800 transition-all" title="Configuración">
              <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 010 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.019-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281z" />
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
            </button>
            {/* Salir */}
            <button
              onClick={onLogout}
              className="ml-1 px-3 py-1.5 rounded-xl bg-stone-800 border border-stone-700 text-stone-400 hover:text-stone-200 hover:border-stone-500 text-xs font-bold uppercase tracking-widest transition-all"
              title="Salir"
            >
              Salir
            </button>
          </div>
        </div>
      </header>

      {/* Contenido: sidebar de impresoras (izq. en desktop, al final en mobile) + pedidos */}
      <main className="max-w-6xl mx-auto px-4 py-6 flex flex-col gap-6 md:flex-row md:items-start">
        <aside className="order-2 md:order-1 w-full md:w-[280px] md:shrink-0 md:sticky md:top-16 md:h-[calc(100vh-4rem)] md:overflow-y-auto md:pb-6">
          <PrintersSidebar
            printers={printers}
            onResolve={handleResolve}
            onRename={handleRenamePrinter}
            onLoadPaper={handleLoadPaper}
            onAdd={handleAddPrinter}
          />
        </aside>
        <div className="order-1 md:order-2 flex-1 min-w-0 space-y-8">
          {conexion === 'noauth' && (
            <div className="flex items-center justify-between gap-3 bg-amber-500/10 border border-amber-500/30 rounded-xl px-4 py-3">
              <p className="text-xs font-bold text-amber-300">
                El token de acceso ya no es válido. Volvé a ingresarlo.
              </p>
              <button
                onClick={onLogout}
                className="shrink-0 px-3 py-1.5 rounded-lg bg-stone-700/60 hover:bg-stone-700 text-stone-300 text-xs font-bold uppercase tracking-wide transition-all"
              >
                Ingresar de nuevo
              </button>
            </div>
          )}
          {conexion === 'error' && (
            <div className="flex items-center justify-between gap-3 bg-red-500/10 border border-red-500/30 rounded-xl px-4 py-3">
              <p className="text-xs font-bold text-red-400">
                No se pudo conectar con el servidor{detalleError ? `: ${detalleError}` : '.'}
              </p>
              <button
                onClick={cargarPedidos}
                className="shrink-0 px-3 py-1.5 rounded-lg bg-stone-700/60 hover:bg-stone-700 text-stone-300 text-xs font-bold uppercase tracking-wide transition-all"
              >
                Reintentar
              </button>
            </div>
          )}
          {conexion === 'cargando' && (
            <div className="h-24 bg-stone-800/60 border border-stone-700 rounded-xl animate-pulse" />
          )}
          <StatsRow orders={orders} />
          <OrdersSection orders={orders} onTransition={handleTransition} onCancel={handleCancelRequest} />
        </div>
      </main>

      {/* Modal cancelar */}
      {cancelTarget !== null && (
        <Modal onClose={() => setCancelTarget(null)}>
          <div className="text-center">
            <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-red-500/15 border border-red-500/30 mb-4">
              <svg xmlns="http://www.w3.org/2000/svg" className="w-6 h-6 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
              </svg>
            </div>
            <h3 className="text-base font-black text-white mb-1">¿Cancelar pedido?</h3>
            <p className="text-xs text-stone-400 mb-6">Esta acción no se puede deshacer.</p>
            <div className="flex gap-3">
              <button
                onClick={() => setCancelTarget(null)}
                className="flex-1 py-2.5 rounded-xl bg-stone-700 hover:bg-stone-600 text-stone-200 text-xs font-bold uppercase tracking-widest transition-all"
              >
                Volver
              </button>
              <button
                onClick={handleCancelConfirm}
                className="flex-1 py-2.5 rounded-xl bg-red-500 hover:bg-red-400 text-white text-xs font-bold uppercase tracking-widest transition-all active:scale-95"
              >
                Cancelar pedido
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};

// ─────────────────────────────────────────────
// PÁGINA PRINCIPAL
// ─────────────────────────────────────────────
const Admin = () => {
  // Si el navegador ya tiene el token, se entra directo: el operador del local
  // no debería tener que pegarlo cada vez que abre el panel.
  const [authed, setAuthed] = useState(() => Boolean(leerToken()));

  const salir = () => {
    borrarToken();
    setAuthed(false);
  };

  return authed
    ? <AdminPanel onLogout={salir} />
    : <LoginScreen onLogin={() => setAuthed(true)} />;
};

export default Admin;
