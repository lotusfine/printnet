import { useState } from 'react';
import { Link } from 'react-router-dom';
import FileUpload from '../components/fotocopias/FileUpload';
import PrintOptions from '../components/fotocopias/PrintOptions';
import OrderSummary from '../components/fotocopias/OrderSummary';

const DEFAULT_OPTIONS = {
  color: 'byn',
  caras: 'simple',
  copias: 1,
  tamano: 'A4',
};

const Fotocopias = () => {
  const [fileInfo, setFileInfo] = useState(null);
  const [options, setOptions] = useState(DEFAULT_OPTIONS);

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

      <div className="grid w-full gap-8 md:gap-10 md:grid-cols-2 xl:grid-cols-3">
        <div className="xl:col-span-1">
          <FileUpload onFileChange={setFileInfo} />
        </div>
        <div className="xl:col-span-1">
          <PrintOptions
            pages={fileInfo?.pages ?? 10}
            options={options}
            onChange={setOptions}
          />
        </div>
        <div className="md:col-span-2 xl:col-span-1">
          <OrderSummary fileInfo={fileInfo} options={options} />
        </div>
      </div>
    </section>
  );
};

export default Fotocopias;
