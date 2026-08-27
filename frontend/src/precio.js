// Motor de precios del lado del cliente.
//
// ESPEJO DE backend-printnet/pricing.py — mantener sincronizados. El backend
// recalcula el precio al crear el pedido; si los dos no coinciden, el cliente
// ve un número y se le cobra otro. Es la trampa conocida más vieja del
// proyecto (ver ESTADO.md).
//
// Hay un script que compara los dos motores caso por caso:
//   backend-printnet/verificar_espejo_precios.py

// Tramos por cantidad, PLANOS (no marginales): el precio del tramo en el que
// cae la cantidad se aplica a TODAS las unidades.
// Cada tramo es [tope incluido (null = en adelante), precio unitario].
const TRAMOS = {
  'byn|simple': [[19, 200], [99, 150], [null, 130]],
  'byn|doble': [[49, 200], [null, 150]],
  'color|simple': [[19, 400], [null, 300]],
  'color|doble': [[19, 600], [null, 450]],
};

const A3_RECARGO = 1.5;
const ANILLADO_HASTA_100 = 2000;
const ANILLADO_MAS_100 = 3500;

export const precioUnitario = (color, caras, cantidad) => {
  const tramos = TRAMOS[`${color}|${caras}`];
  return tramos.find(([tope]) => tope === null || cantidad <= tope)[1];
};

/** Hojas físicas de UNA copia: en doble faz entran 2 carillas por hoja. */
export const hojasPorCopia = (paginas, caras) =>
  caras === 'doble' ? Math.ceil(paginas / 2) : paginas;

const precioAnillado = (hojasDeUnaCopia, copias) =>
  (hojasDeUnaCopia <= 100 ? ANILLADO_HASTA_100 : ANILLADO_MAS_100) * copias;

/** Páginas que se van a imprimir según el rango elegido. */
export const paginasDelRango = (paginas, rango) => {
  if (paginas == null) return null;
  if (!rango || rango.modo !== 'rango') return paginas;
  const v = (rango.valor || '').trim();
  if (!/^\d+(-\d+)?$/.test(v)) return paginas;
  const [inicio, fin = inicio] = v.split('-').map(Number);
  if (inicio < 1 || inicio > fin) return paginas;
  return Math.min(fin, paginas) - inicio + 1;
};

/**
 * Precio de un pedido completo.
 *
 * DECISIÓN DE NEGOCIO: el tramo de descuento sale de la suma de TODOS los
 * documentos; cada documento usa después su propia tabla según color y caras.
 * Si cada uno tuviera su propio tramo, quien trae el trabajo partido en tres
 * archivos pagaría más que quien lo trae en uno solo.
 *
 * `documentos` = [{ paginas, opciones: {color, caras, copias, tamano},
 *                   terminaciones? }]
 * Los documentos sin páginas conocidas se ignoran: nunca se inventa un número.
 */
export const calcPrecioPedido = (documentos) => {
  const validos = (documentos || []).filter((d) => d && d.paginas != null);
  if (!validos.length) {
    return { total: 0, cantidadTotal: 0, unitario: null, lineas: [] };
  }

  const cantidades = validos.map((d) =>
    hojasPorCopia(d.paginas, d.opciones.caras) * d.opciones.copias
  );
  const cantidadTotal = cantidades.reduce((a, b) => a + b, 0);

  const lineas = validos.map((d, i) => {
    const unitario = precioUnitario(d.opciones.color, d.opciones.caras, cantidadTotal);
    const multiplicador = d.opciones.tamano === 'A3' ? A3_RECARGO : 1;
    let subtotal = Math.round(cantidades[i] * unitario * multiplicador);
    if (d.terminaciones?.includes('Anillado')) {
      subtotal += precioAnillado(
        hojasPorCopia(d.paginas, d.opciones.caras), d.opciones.copias
      );
    }
    return { cantidad: cantidades[i], unitario, subtotal };
  });

  return {
    total: lineas.reduce((s, l) => s + l.subtotal, 0),
    cantidadTotal,
    // Solo tiene sentido mostrar "el" precio unitario si todos comparten tabla.
    unitario: lineas.every((l) => l.unitario === lineas[0].unitario)
      ? lineas[0].unitario
      : null,
    lineas,
  };
};

/** Precio de un solo documento. Se conserva para el panel de una sola línea. */
export const calcPrice = (paginas, opciones) =>
  calcPrecioPedido([{ paginas, opciones }]).total;
