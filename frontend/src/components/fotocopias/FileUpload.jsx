import { useState, useRef } from 'react';

const SIMULATED_PAGES = 10;

const FileUpload = ({ onFileChange }) => {
  const [file, setFile] = useState(null);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef(null);

  const handleFile = (f) => {
    if (!f || f.type !== 'application/pdf') return;
    setFile(f);
    onFileChange({ name: f.name, pages: SIMULATED_PAGES });
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
          {dragging ? 'Soltá el archivo acá' : 'Arrastrá un PDF o hacé click para elegir'}
        </p>
        <p className="text-xs text-stone-400">Solo archivos .pdf</p>
      </div>

      <input
        ref={inputRef}
        type="file"
        accept="application/pdf"
        className="hidden"
        onChange={(e) => handleFile(e.target.files[0])}
      />

      {file && (
        <div className="mt-5 flex items-center gap-3 bg-white/70 border border-amber-200 rounded-lg px-4 py-3 shadow-sm">
          <svg xmlns="http://www.w3.org/2000/svg" className="w-6 h-6 text-red-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
          </svg>
          <div className="min-w-0">
            <p className="text-sm font-bold text-stone-700 truncate">{file.name}</p>
            <p className="text-xs text-stone-400">{SIMULATED_PAGES} páginas (simulado)</p>
          </div>
        </div>
      )}
    </article>
  );
};

export default FileUpload;
