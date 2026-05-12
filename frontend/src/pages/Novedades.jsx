const Novedades = ({ novedades }) => {
  return (
    <section className="px-2 space-y-10">
      <header className="inline-block border-b-4 border-rose-200">
        <h2 className="text-4xl md:text-5xl font-chalk text-stone-800">Novedades</h2>
      </header>
      <div className="grid gap-6 md:gap-8 md:grid-cols-2">
        {novedades.map((item, index) => (
          <article key={index} className="p-6 transition-shadow bg-white border shadow-sm border-stone-100 rounded-2xl hover:shadow-md md:p-8">
            <h3 className="text-xl font-bold md:text-2xl text-stone-800">{item.titulo}</h3>
            <p className="mt-3 text-sm font-medium leading-relaxed text-stone-600 md:text-base md:mt-4">{item.descripcion}</p>
          </article>
        ))}
      </div>
    </section>
  );
};

export default Novedades;