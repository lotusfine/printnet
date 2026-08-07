// Configuración de servidores en tiempo de ejecución.
//
// Este archivo se lee al cargar la página, ANTES de la aplicación. Editarlo en
// el servidor (cPanel → Administrador de archivos) cambia a qué backend apunta
// el sitio SIN necesidad de recompilar ni volver a subir todo.
//
// Si un valor queda vacío, se usa el de las variables de entorno del build
// (VITE_API_URL / VITE_PRINTNET_API) y, en última instancia, localhost.
window.__PRINTNET_CONFIG__ = {
  // Backend del sitio institucional (horarios, novedades)
  API_URL: "",
  // Backend de PrintNet (pedidos, pagos) — el túnel hacia la notebook
  PRINTNET_API: "",
};
