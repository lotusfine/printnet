import { useState } from 'react';

// ─────────────────────────────────────────────
// DATOS MOCK
// ─────────────────────────────────────────────
const INIT_ORDERS = [
  {
    id: 42, cliente: 'Valentina García', archivo: 'tesis_final_v3.pdf',
    paginas: 48, copias: 2, color: false, doble: true, acabado: 'Anillado',
    precio: 830, estado: 'imprimiendo', hace: 3,
    contacto: { tel: '221-4523891', email: 'vgarcia@mail.com' },
  },
  {
    id: 41, cliente: 'Martín Rodríguez', archivo: 'resumen_clase.pdf',
    paginas: 12, copias: 1, color: true, doble: false, acabado: 'Retiro en local',
    precio: 360, estado: 'listo', hace: 8,
    contacto: { tel: '221-5678234', email: 'mrodriguez@mail.com' },
  },
  {
    id: 40, cliente: 'Sofía Méndez', archivo: 'formulario_inscripcion.pdf',
    paginas: 4, copias: 3, color: false, doble: false, acabado: null,
    precio: 240, estado: 'pendiente', hace: 14,
    contacto: { tel: '221-9012567', email: 'smendes@mail.com' },
  },
  {
    id: 39, cliente: 'Diego Herrera', archivo: 'apuntes_biologia.pdf',
    paginas: 22, copias: 1, color: false, doble: true, acabado: null,
    precio: 180, estado: 'entregado', hace: 47,
    contacto: { tel: '221-3456789', email: 'dherrera@mail.com' },
  },
];

const INIT_PRINTERS = [
  {
    id: 1, nombre: 'HP LaserJet 1', tipo: 'laser', estado: 'error',
    errorTipo: 'Tóner bajo', papel: 75, tonner: 15,
  },
  {
    id: 2, nombre: 'Epson L3250', tipo: 'tinta', estado: 'activa',
    errorTipo: null, papel: 90, tinta: 80,
  },
];

// ─────────────────────────────────────────────
// HELPERS
// ─────────────────────────────────────────────
const ars = (n) => `$${n.toLocaleString('es-AR')}`;

const BADGE = {
  pendiente:   'bg-yellow-500/15 text-yellow-300 border border-yellow-500/30',
  imprimiendo: 'bg-blue-500/15 text-blue-300 border border-blue-500/30',
  listo:       'bg-green-500/15 text-green-300 border border-green-500/30',
  entregado:   'bg-stone-500/20 text-stone-400 border border-stone-600/30',
  cancelado:   'bg-stone-700/40 text-stone-500 border border-stone-600/30',
};

const BADGE_LABEL = {
  pendiente: 'Pendiente', imprimiendo: 'Imprimiendo',
  listo: 'Listo', entregado: 'Entregado', cancelado: 'Cancelado',
};

const LEFT_BORDER = {
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
  const [error, setError] = useState(false);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (pass === 'admin123') {
      onLogin();
    } else {
      setError(true);
      setPass('');
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
              Contraseña
            </label>
            <input
              type="password"
              value={pass}
              onChange={(e) => { setPass(e.target.value); setError(false); }}
              autoFocus
              placeholder="••••••••"
              className={`w-full px-4 py-3 rounded-xl bg-stone-900 border text-sm text-white placeholder-stone-600 focus:outline-none transition-colors ${
                error ? 'border-red-500 focus:border-red-400' : 'border-stone-600 focus:border-amber-500'
              }`}
            />
            {error && (
              <p className="mt-2 text-xs font-bold text-red-400 flex items-center gap-1.5">
                <svg xmlns="http://www.w3.org/2000/svg" className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="currentColor">
                  <path fillRule="evenodd" d="M9.401 3.003c1.155-2 4.043-2 5.197 0l7.355 12.748c1.154 2-.29 4.5-2.599 4.5H4.645c-2.309 0-3.752-2.5-2.598-4.5L9.4 3.003zM12 8.25a.75.75 0 01.75.75v3.75a.75.75 0 01-1.5 0V9a.75.75 0 01.75-.75zm0 8.25a.75.75 0 100-1.5.75.75 0 000 1.5z" clipRule="evenodd"/>
                </svg>
                Contraseña incorrecta
              </p>
            )}
          </div>
          <button
            type="submit"
            className="w-full py-3 rounded-xl bg-amber-500 hover:bg-amber-400 active:scale-95 text-white font-black text-sm uppercase tracking-widest transition-all shadow-md shadow-amber-500/20"
          >
            Ingresar
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
  const ingresos    = orders.filter(o => o.estado !== 'cancelado').reduce((s, o) => s + o.precio, 0);
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
            <span className={`shrink-0 text-[10px] font-black uppercase tracking-widest px-2.5 py-1 rounded-full ${BADGE[order.estado]}`}>
              {BADGE_LABEL[order.estado]}
            </span>
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
              {order.paginas} pág × {order.copias} {order.copias > 1 ? 'copias' : 'copia'} · {order.color ? 'Color' : 'B/N'} · {order.doble ? 'Doble cara' : 'Una cara'}
              {order.acabado ? ` · ${order.acabado}` : ''}
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
// PRINTERS SECTION
// ─────────────────────────────────────────────
const PrintersSection = ({ printers, onResolve }) => (
  <section>
    <h2 className="text-[10px] font-black uppercase tracking-[0.3em] text-stone-400 mb-4">Estado de Impresoras</h2>
    <div className="grid gap-3 sm:grid-cols-2">
      {printers.map((p) => (
        <div
          key={p.id}
          className={`bg-stone-800 border rounded-xl p-4 shadow-sm ${
            p.estado === 'error' ? 'border-red-500/40' : 'border-stone-700'
          }`}
        >
          <div className="flex items-center justify-between mb-4">
            <div>
              <p className="text-sm font-black text-white">{p.nombre}</p>
              <p className="text-[10px] text-stone-500 uppercase tracking-widest mt-0.5">
                {p.tipo === 'laser' ? 'Láser' : 'Tinta'}
              </p>
            </div>
            <span className={`text-[10px] font-black uppercase tracking-widest px-2.5 py-1 rounded-full border ${
              p.estado === 'activa'
                ? 'bg-green-500/15 text-green-400 border-green-500/30'
                : 'bg-red-500/15 text-red-400 border-red-500/30'
            }`}>
              {p.estado === 'activa' ? 'Activa' : 'Error'}
            </span>
          </div>

          <div className="space-y-3 mb-4">
            <LevelBar label="Papel" value={p.papel} />
            {p.tipo === 'laser'
              ? <LevelBar label="Tóner" value={p.tonner} />
              : <LevelBar label="Tinta" value={p.tinta} />
            }
          </div>

          {p.estado === 'error' && (
            <div className="mt-2 space-y-3">
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
        </div>
      ))}
    </div>
  </section>
);

// ─────────────────────────────────────────────
// ADMIN PANEL
// ─────────────────────────────────────────────
const AdminPanel = ({ onLogout }) => {
  const [orders, setOrders] = useState(INIT_ORDERS);
  const [printers, setPrinters] = useState(INIT_PRINTERS);
  const [cancelTarget, setCancelTarget] = useState(null);

  const handleTransition = (id, newState) => {
    setOrders(prev => prev.map(o => o.id === id ? { ...o, estado: newState } : o));
  };

  const handleCancelRequest = (id) => setCancelTarget(id);

  const handleCancelConfirm = () => {
    setOrders(prev => prev.map(o => o.id === cancelTarget ? { ...o, estado: 'cancelado' } : o));
    setCancelTarget(null);
  };

  const handleResolve = (id) => {
    setPrinters(prev => prev.map(p => p.id === id ? { ...p, estado: 'activa', errorTipo: null } : p));
  };

  return (
    <div className="min-h-screen bg-stone-900 text-white">
      {/* Header */}
      <header className="sticky top-0 z-30 bg-stone-900/80 backdrop-blur border-b border-stone-800 px-4 py-3">
        <div className="max-w-3xl mx-auto flex items-center justify-between gap-4">
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

      {/* Contenido */}
      <main className="max-w-3xl mx-auto px-4 py-6 space-y-8">
        <StatsRow orders={orders} />
        <OrdersSection orders={orders} onTransition={handleTransition} onCancel={handleCancelRequest} />
        <PrintersSection printers={printers} onResolve={handleResolve} />
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
  const [authed, setAuthed] = useState(false);
  return authed
    ? <AdminPanel onLogout={() => setAuthed(false)} />
    : <LoginScreen onLogin={() => setAuthed(true)} />;
};

export default Admin;
