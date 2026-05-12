import mapaImg from '../assets/mapa-glaxara.png';

const Home = ({ infoGeneral }) => {
  const cardBase = "p-6 md:p-8 shadow-xl transition-all duration-500 hover:scale-[1.02] w-full";

  return (
    <section className="flex flex-col items-center space-y-10 md:space-y-16">
      <header className="px-2 text-center">
        <h1 className="mb-4 text-5xl leading-tight font-chalk md:text-7xl text-stone-800/90">Librería Glaxara</h1>
        <p className="text-xl italic font-chalk md:text-2xl text-stone-500">Un mundo de cosas útiles</p>
      </header>

      {infoGeneral ? (
        <div className="grid w-full max-w-5xl gap-8 md:gap-12 md:grid-cols-2">
          {/* TARJETA 1: HORARIOS */}
          <article className={`${cardBase} bg-yellow-100 rotate-0 md:-rotate-2 flex flex-col min-h-[300px] md:min-h-[350px] relative overflow-hidden rounded-sm`}>
            <div className="absolute top-0 w-20 h-6 -translate-x-1/2 -translate-y-3 left-1/2 bg-white/60 rotate-3 md:w-24 md:h-8"></div>
            <h2 className="mb-6 text-[10px] font-black tracking-[0.3em] uppercase text-stone-500/60 text-center md:mb-8 md:text-xs">
              Horarios de Atención
            </h2>
            <div className="flex flex-col justify-center flex-grow space-y-4 md:space-y-6">
              {infoGeneral.horarios.split('.').map((frase, i) => (
                frase.trim() && (
                  <p key={i} className="text-2xl leading-snug font-chalk md:text-4xl text-stone-700/90">
                    {frase.trim()}.
                  </p>
                )
              ))}
            </div>
          </article>
          
          {/* TARJETA 2: MAPA */}
          <article className={`${cardBase} bg-rose-100 rotate-0 md:rotate-2 flex flex-col min-h-[300px] md:min-h-[350px] relative rounded-sm`}>
            <div className="absolute top-0 w-20 h-6 -translate-x-1/2 -translate-y-3 left-1/2 bg-white/40 -rotate-2 md:w-24 md:h-8"></div>
            <h2 className="mb-4 text-[10px] font-black tracking-[0.3em] uppercase text-stone-500/60 text-center md:mb-6 md:text-xs">
              Dónde Estamos
            </h2>
            <figure className="flex items-center justify-center flex-grow p-1 overflow-hidden border rounded-lg shadow-inner bg-white/50 border-rose-200">
              <img src={mapaImg} alt="Mapa" className="object-contain w-full h-48 transition-all md:h-64" />
            </figure>
            <div className="mt-6 text-center md:mt-8">
              <a href={infoGeneral.direccion} target="_blank" rel="noreferrer" className="inline-block px-6 py-3 text-xs font-bold text-white uppercase transition-all rounded-lg shadow-md bg-stone-700 hover:bg-stone-900 md:text-sm md:px-8">
                Abrir Mapa
              </a>
            </div>
          </article>
        </div>
      ) : (
        <div className="grid w-full gap-8 md:grid-cols-2">
          <div className="h-64 bg-stone-200/50 rounded-xl animate-pulse"></div>
          <div className="h-64 bg-stone-200/50 rounded-xl animate-pulse"></div>
        </div>
      )}
    </section>
  );
};

export default Home;