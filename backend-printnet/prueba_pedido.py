"""Prueba de punta a punta: crea un pedido contra el backend y lo sigue.

Recorre el camino completo que hace un cliente real —subir el PDF, elegir
opciones, que se calcule el precio, que se despache a la impresora— pero sin
MercadoPago y sin túnel.

Funciona porque el backend, si no encuentra MP_ACCESS_TOKEN, entra en "modo
fantasma": todo pedido nace pagado y se despacha en el acto. Es el modo de
desarrollo de siempre; acá lo usamos para aislar la impresión de los pagos.

    # En una ventana, el backend:
    .venv\\Scripts\\python run_server.py

    # En otra, la prueba:
    .venv\\Scripts\\python prueba_pedido.py
    .venv\\Scripts\\python prueba_pedido.py --tamano A3 --color color --caras doble

OJO: esto crea pedidos de verdad en la base y manda a imprimir de verdad si
el backend está en PRINTNET_DISPATCH=sumatra. Los pedidos de prueba quedan
guardados; se ven en el panel de admin.

Herramienta de diagnóstico, no parte del servidor.
"""

import argparse
import json
import sys
import tempfile

import requests

from generar_pdf_prueba import generar

CONTACTO_PRUEBA = {
    "nombre": "Prueba PrintNet",
    "telefono": "+5492211234567",
    "email": "prueba@printnet.local",
}


def main() -> int:
    p = argparse.ArgumentParser(description="Crea un pedido de prueba de punta a punta.")
    p.add_argument("--url", default="http://localhost:8000", help="Backend")
    p.add_argument("--pdf", help="PDF a subir (si no, se genera uno)")
    p.add_argument("--paginas", type=int, default=4, help="Páginas del PDF generado")
    p.add_argument("--pdf-tamano", choices=["A4", "A3"], default="A4",
                   help="Tamaño de página del PDF generado (distinto del pedido)")
    p.add_argument("--color", choices=["byn", "color"], default="byn")
    p.add_argument("--caras", choices=["simple", "doble"], default="simple")
    p.add_argument("--copias", type=int, default=1)
    p.add_argument("--tamano", choices=["A4", "A3"], default="A4",
                   help="Tamaño que pide el cliente (lo que se cobra)")
    p.add_argument("--rango", default="", help='Ej. "2-3". Vacío = todas')
    args = p.parse_args()

    if args.pdf:
        ruta = args.pdf
    else:
        f = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        f.write(generar(args.paginas, args.pdf_tamano))
        f.close()
        ruta = f.name
        print(f"PDF generado: {args.paginas} páginas {args.pdf_tamano} → {ruta}")

    datos = {
        "tipo": "fotocopias",
        "contacto": CONTACTO_PRUEBA,
        "opciones": {
            "color": args.color,
            "caras": args.caras,
            "copias": args.copias,
            "tamano": args.tamano,
        },
        "rango": ({"modo": "rango", "valor": args.rango} if args.rango.strip()
                  else {"modo": "todas", "valor": ""}),
        "terminaciones": [],
    }

    print(f"\nPedido: {args.color}, {args.caras} faz, {args.copias} copia(s), "
          f"{args.tamano}, {args.rango or 'todas las páginas'}")
    print(f"Backend: {args.url}")

    try:
        with open(ruta, "rb") as fh:
            r = requests.post(
                f"{args.url}/orders",
                data={"datos": json.dumps(datos)},
                files=[("files", ("prueba.pdf", fh, "application/pdf"))],
                timeout=60,
            )
    except requests.exceptions.ConnectionError:
        print(f"\nNo hay nadie escuchando en {args.url}.")
        print("¿Levantaste el backend?  .venv\\Scripts\\python run_server.py")
        return 1

    if r.status_code != 201:
        print(f"\nEl backend rechazó el pedido (HTTP {r.status_code}):")
        print(r.text)
        return 1

    pedido = r.json()
    print("\n--- Pedido creado ---")
    for campo in ("id", "token", "estado", "pagado", "precio", "init_point"):
        if campo in pedido:
            print(f"  {campo:12}: {pedido[campo]}")

    token = pedido.get("token")
    if token:
        s = requests.get(f"{args.url}/orders/status/{token}", timeout=30)
        if s.ok:
            estado = s.json()
            print("\n--- Estado consultado ---")
            for campo in ("estado", "pagado", "paginas", "copias", "tamano", "precio"):
                if campo in estado:
                    print(f"  {campo:12}: {estado[campo]}")

    estado_final = pedido.get("estado")
    print()
    if estado_final == "imprimiendo":
        print("El pedido se despachó. Andá a mirar la impresora.")
    elif estado_final == "pendiente":
        print("Quedó en 'pendiente': no se despachó.")
        print("Suele ser que no hay ninguna impresora en estado 'activa' en la base.")
    elif estado_final == "pendiente_pago":
        print("Quedó esperando el pago: el backend TIENE credenciales de MercadoPago.")
        print("Para esta prueba conviene levantarlo sin MP_ACCESS_TOKEN.")
    else:
        print(f"Estado inesperado: {estado_final}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
