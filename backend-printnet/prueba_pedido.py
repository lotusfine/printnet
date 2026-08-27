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
import os
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
    p.add_argument("--archivo", "--pdf", dest="archivos", action="append",
                   help="Documento a subir: PDF, Word, Excel o PowerPoint. "
                        "Se puede repetir para mandar varios en un mismo "
                        "pedido. Si no se pasa, se genera un PDF de prueba.")
    p.add_argument("--paginas", type=int, default=4, help="Páginas del PDF generado")
    p.add_argument("--pdf-tamano", choices=["A4", "A3"], default="A4",
                   help="Tamaño de página del PDF generado (distinto del pedido)")
    p.add_argument("--color", choices=["byn", "color"], default="byn")
    p.add_argument("--caras", choices=["simple", "doble"], default="simple")
    p.add_argument("--copias", type=int, default=1)
    p.add_argument("--tamano", choices=["A4", "A3"], default="A4",
                   help="Tamaño que pide el cliente (lo que se cobra)")
    p.add_argument("--rango", default="", help='Ej. "2-3". Vacío = todas')
    p.add_argument("--email", help="Dirección del cliente. Por defecto usa una "
                                   "inventada, que NO recibe nada: para probar "
                                   "el envío de mails hay que poner una real.")
    p.add_argument("--nombre", help="Nombre del cliente de prueba")
    args = p.parse_args()

    contacto = dict(CONTACTO_PRUEBA)
    if args.email:
        contacto["email"] = args.email
    if args.nombre:
        contacto["nombre"] = args.nombre

    if args.archivos:
        rutas = args.archivos
    else:
        f = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        f.write(generar(args.paginas, args.pdf_tamano))
        f.close()
        rutas = [f.name]
        print(f"PDF generado: {args.paginas} páginas {args.pdf_tamano} → {f.name}")

    documento = {
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
    # Con un solo documento se manda la forma VIEJA a propósito: es la que usa
    # la web hoy, y así esta prueba también verifica que siga funcionando.
    if len(rutas) == 1:
        datos = {"tipo": "fotocopias", "contacto": contacto, **documento}
    else:
        datos = {"tipo": "fotocopias", "contacto": contacto,
                 "documentos": [dict(documento) for _ in rutas]}

    print(f"\nPedido: {len(rutas)} documento(s) · {args.color}, {args.caras} faz, "
          f"{args.copias} copia(s), {args.tamano}, "
          f"{args.rango or 'todas las páginas'}")
    print(f"Contrato: forma {'vieja (1 documento)' if len(rutas) == 1 else 'nueva (varios)'}")
    for r in rutas:
        print(f"  · {os.path.basename(r)}")
    print(f"Cliente: {contacto['nombre']} <{contacto['email']}>")
    if not args.email:
        print("  (dirección inventada: no va a llegar ningún mail. "
              "Usá --email tu@correo.com para probar el envío)")
    print(f"Backend: {args.url}")

    try:
        # El nombre real importa: el backend decide por la extensión si hay
        # que convertir el documento antes de imprimirlo.
        abiertos = [open(r, "rb") for r in rutas]
        try:
            r = requests.post(
                f"{args.url}/orders",
                data={"datos": json.dumps(datos)},
                files=[("files", (os.path.basename(ruta), fh,
                                  "application/octet-stream"))
                       for ruta, fh in zip(rutas, abiertos)],
                timeout=180,
            )
        finally:
            for fh in abiertos:
                fh.close()
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
    # Se muestra todo lo que devuelva el backend: si algún día cambia el
    # contrato, se ve acá en vez de desaparecer en silencio.
    for campo, valor in pedido.items():
        print(f"  {campo:16}: {valor}")

    token = pedido.get("token")
    if token:
        s = requests.get(f"{args.url}/orders/status/{token}", timeout=30)
        if s.ok:
            print("\n--- Estado consultado ---")
            for campo, valor in s.json().items():
                print(f"  {campo:16}: {valor}")

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
