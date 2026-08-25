// Límites de carga de archivos.
//
// ESPEJADO EN backend-printnet/routers/orders.py (MAX_FILE_BYTES).
// Si se cambia acá hay que cambiarlo allá, o la web va a dejar subir algo que
// el servidor después rechaza. Es la misma trampa que ya tienen los precios
// entre pricing.py y PrintOptions.jsx (ver ESTADO.md).
//
// POR QUÉ 95 Y NO 100: Cloudflare, en el plan gratuito, no deja pasar
// peticiones de más de 100 MB. Un archivo justo en el borde moriría en
// Cloudflare, con un error que no podemos redactar ni traducir. Dejando el
// límite propio un poco abajo, el cliente ve nuestro mensaje explicando qué
// pasó y qué hacer.
export const MAX_ARCHIVO_MB = 95;
export const MAX_ARCHIVO_BYTES = MAX_ARCHIVO_MB * 1024 * 1024;

/** Tamaño legible para mostrarle a una persona: "62 MB", "840 KB". */
export const formatearTamano = (bytes) => {
  if (bytes >= 1024 * 1024) return `${Math.round(bytes / (1024 * 1024))} MB`;
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
};
