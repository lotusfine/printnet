// Resuelve las URLs de los backends con esta prioridad:
//   1. public/config.js  (editable en el servidor, sin recompilar)
//   2. variables de entorno del build (.env)
//   3. valores por defecto para desarrollo local
const runtime = (typeof window !== 'undefined' && window.__PRINTNET_CONFIG__) || {};

/** Backend institucional: horarios y novedades del sitio. */
export const API_URL =
  runtime.API_URL || import.meta.env.VITE_API_URL || '';

/** Backend de PrintNet: pedidos, precios y pagos. */
export const PRINTNET_API =
  runtime.PRINTNET_API || import.meta.env.VITE_PRINTNET_API || 'http://localhost:8000';
