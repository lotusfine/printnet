// Límite de carga de archivos, sobre el TOTAL del pedido.
//
// ESPEJADO EN backend-printnet/subidas.py (MAX_PEDIDO_MB). Si se cambia acá
// hay que cambiarlo allá, o la web va a dejar subir algo que el servidor
// después rechaza. Es la misma trampa que ya tienen los precios entre
// pricing.py y precio.js (ver ESTADO.md).
//
// Antes era 95 MB por el techo de 100 MB por petición de Cloudflare. Ya no
// aplica: los archivos viajan en pedazos de 6 MB (subirArchivo en api.js).
// 300 es lo que la notebook procesa con margen, medido con
// medir_archivo_grande.py.
export const MAX_ARCHIVO_MB = 300;
export const MAX_ARCHIVO_BYTES = MAX_ARCHIVO_MB * 1024 * 1024;

/** Tamaño legible para mostrarle a una persona: "62 MB", "840 KB". */
export const formatearTamano = (bytes) => {
  if (bytes >= 1024 * 1024) return `${Math.round(bytes / (1024 * 1024))} MB`;
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
};
