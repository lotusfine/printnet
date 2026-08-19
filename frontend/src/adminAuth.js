// Token de acceso al panel de operador.
//
// El backend exige el header X-Admin-Token en /admin/*. Acá se guarda el que
// escribió el operador, para no pedírselo en cada visita.
//
// Vive en localStorage, o sea que queda atado al navegador y a la máquina: en
// la notebook del local se pega una vez y listo. Cerrar sesión lo borra.
//
// No se guarda en config.js a propósito: ese archivo lo sirve la web y lo
// puede leer cualquiera.

const CLAVE = 'printnet_admin_token';

export function leerToken() {
  try {
    return localStorage.getItem(CLAVE) || '';
  } catch {
    // Modo incógnito o almacenamiento bloqueado.
    return '';
  }
}

export function guardarToken(token) {
  try {
    localStorage.setItem(CLAVE, token.trim());
  } catch {
    // Si no se puede guardar, la sesión igual funciona hasta recargar.
  }
}

export function borrarToken() {
  try {
    localStorage.removeItem(CLAVE);
  } catch {
    /* nada que hacer */
  }
}
