import { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';

// Importamos los componentes de las páginas
import Home from './pages/Home';
import Novedades from './pages/Novedades';
import Fotocopias from './pages/Fotocopias';

// Importamos assets
import logo from './assets/logo-glaxara.jpg';
import logoWsp from './assets/logo-wsp.png';

function App() {
  const [infoGeneral, setInfoGeneral] = useState(null);
  const [novedades, setNovedades] = useState([]);

  useEffect(() => {
    const apiUrl = import.meta.env.VITE_API_URL
    Promise.all([
      fetch(`${apiUrl}/informacion`).then(res => res.json()),
      fetch(`${apiUrl}/novedades`).then(res => res.json())
    ])
      .then(([dataInfo, dataNov]) => {
        setInfoGeneral(dataInfo);
        setNovedades(dataNov);
      })
      .catch(err => console.error('Error:', err));
  }, []);

  return (
    <Router>
      <div className="flex flex-col min-h-screen font-sans bg-orange-50/50 text-stone-800">
        
        <header className="sticky top-0 z-40 border-b shadow-sm bg-amber-100 border-amber-200">
          <nav className="flex items-center justify-between max-w-6xl px-4 py-3 mx-auto md:px-6 md:py-4">
            <Link to="/" className="flex items-center gap-2 transition md:gap-3 hover:opacity-80">
              <img src={logo} alt="Logo Glaxara" className="object-cover w-10 h-10 border-2 border-white rounded-full md:w-12 md:h-12" />
              <span className="text-xl font-black tracking-tighter md:text-2xl text-amber-900/80">Glaxara</span>
            </Link>
            <ul className="flex gap-4 text-xs font-bold tracking-widest uppercase md:gap-8 md:text-sm text-stone-600">
              <li><Link to="/" className="transition-colors hover:text-amber-700">Inicio</Link></li>
              <li><Link to="/novedades" className="transition-colors hover:text-amber-700">Novedades</Link></li>
              <li><Link to="/fotocopias" className="transition-colors hover:text-amber-700">Fotocopias</Link></li>
            </ul>
          </nav>
        </header>

        <main className="flex-grow w-full max-w-6xl px-4 py-10 mx-auto md:px-6 md:py-16">
          <Routes>
            {/* Pasamos los datos como "props" a cada componente */}
            <Route path="/" element={<Home infoGeneral={infoGeneral} />} />
            <Route path="/novedades" element={<Novedades novedades={novedades} />} />
            <Route path="/fotocopias" element={<Fotocopias />} />
          </Routes>
        </main>

        <footer className="py-10 border-t bg-stone-100 text-stone-500 border-stone-200">
          <div className="max-w-6xl px-6 mx-auto text-center">
            <p className="mb-2 text-xs font-bold tracking-widest uppercase md:text-sm text-stone-400">© LIBRERIA GLAXARA</p>
            <p className="text-xs italic text-stone-400">Reserva todos los derechos.</p>
          </div>
        </footer>

        {/* --- BURBUJA DE WHATSAPP --- */}
      <a
        href="https://wa.me/5492214633147?text=Hola%20Glaxara!%20Quería%20hacer%20una%20consulta..."
        target="_blank"
        rel="noreferrer"
        className="fixed z-50 bottom-6 right-6 md:bottom-8 md:right-8 group"
        aria-label="Contactar por WhatsApp"
      >
        <div className="relative transition-transform duration-300 group-hover:scale-110 group-active:scale-95">            
          <img 
            src={logoWsp} 
            alt="WhatsApp Glaxara" 
            className="object-contain w-14 h-14 md:w-16 md:h-16 drop-shadow-lg"
          />
          {/* Tooltip solo visible en desktop */}
          <span className="absolute hidden px-4 py-2 text-xs text-white transition-opacity duration-300 -translate-y-1/2 rounded-lg shadow-xl opacity-0 pointer-events-none md:block right-20 top-1/2 bg-stone-800 group-hover:opacity-100 whitespace-nowrap">
            ¡Consultanos por WhatsApp!
          </span>
        </div>
      </a>
      </div>
    </Router>
  );
}

export default App;