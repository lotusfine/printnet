// Formatos de documento que acepta el sistema.
//
// ESPEJADO EN backend-printnet/document_convert.py (FORMATOS_CONVERTIBLES).
// Si se agrega uno acá hay que agregarlo allá, o la web deja elegir un archivo
// que el servidor después rechaza. Misma trampa que los precios y el límite de
// tamaño (ver ESTADO.md).
//
// `.pps` está porque lo trajo un cliente real: es PowerPoint viejo, de los que
// abren directo en modo presentación.
export const FORMATOS_CONVERTIBLES = [
  '.doc', '.docx', '.odt', '.rtf', '.txt',
  '.xls', '.xlsx', '.ods', '.csv',
  '.ppt', '.pptx', '.pps', '.ppsx', '.odp',
];

export const EXTENSIONES_ACEPTADAS = ['.pdf', ...FORMATOS_CONVERTIBLES];

/** Valor del atributo `accept` del input de archivos. */
export const ACCEPT = EXTENSIONES_ACEPTADAS.join(',');

const extension = (nombre) => {
  const punto = nombre.lastIndexOf('.');
  return punto === -1 ? '' : nombre.slice(punto).toLowerCase();
};

export const esPdf = (nombre) => extension(nombre) === '.pdf';

/** ¿Hay que convertirlo antes de imprimir? */
export const esConvertible = (nombre) =>
  FORMATOS_CONVERTIBLES.includes(extension(nombre));

/** ¿Lo aceptamos, en PDF o para convertir? */
export const esAceptado = (nombre) =>
  EXTENSIONES_ACEPTADAS.includes(extension(nombre));

/** Cómo se le nombra el formato al cliente cuando no lo aceptamos. */
export const describirExtension = (nombre) => extension(nombre) || 'sin extensión';
