"""Tests del contrato de un pedido con varios documentos.

Correr:  .venv/bin/python test_models_pedido.py

POR QUÉ ACEPTA DOS FORMAS: la web y el backend se despliegan por separado —el
backend por git en la notebook, la web subiendo archivos a cPanel—. Si el
contrato solo aceptara la forma nueva, habría una ventana en la que una de las
dos piezas está actualizada y la otra no, y los pedidos fallarían.

Forma vieja (un documento, la que usa la web hoy):
    {"tipo": "fotocopias", "contacto": {...},
     "opciones": {...}, "rango": {...}, "terminaciones": []}

Forma nueva (varios documentos):
    {"tipo": "fotocopias", "contacto": {...},
     "documentos": [{"opciones": {...}, "rango": {...}, "terminaciones": []}, ...]}
"""

import sys

from pydantic import ValidationError

from models import PedidoFotocopias

fallos: list[str] = []


def check(nombre: str, obtenido, esperado):
    if obtenido == esperado:
        print(f"  ok  {nombre}")
    else:
        print(f"  FALLA  {nombre}: esperado {esperado}, obtenido {obtenido}")
        fallos.append(nombre)


CONTACTO = {
    "nombre": "Ana Pérez",
    "telefono": "+5492211234567",
    "email": "ana@ejemplo.com",
}
OPCIONES = {"color": "byn", "caras": "simple", "copias": 1, "tamano": "A4"}


def viejo(**extra):
    return {"tipo": "fotocopias", "contacto": CONTACTO, "opciones": OPCIONES, **extra}


def nuevo(documentos):
    return {"tipo": "fotocopias", "contacto": CONTACTO, "documentos": documentos}


# ─────────────────────────────────────────────
print("\n== La forma vieja sigue entrando (la web de hoy) ==")

p = PedidoFotocopias.model_validate(viejo())
check("un pedido con 'opciones' se acepta", len(p.documentos), 1)
check("sus opciones quedan en el primer documento", p.documentos[0].opciones.color, "byn")
check("el rango por defecto es 'todas'", p.documentos[0].rango.modo, "todas")

p = PedidoFotocopias.model_validate(
    viejo(rango={"modo": "rango", "valor": "3-8"}, terminaciones=["Anillado"])
)
check("el rango de la forma vieja se conserva", p.documentos[0].rango.valor, "3-8")
check("las terminaciones también", p.documentos[0].terminaciones, ["Anillado"])


print("\n== La forma nueva ==")

p = PedidoFotocopias.model_validate(nuevo([
    {"opciones": OPCIONES},
    {"opciones": {**OPCIONES, "color": "color", "copias": 2}},
]))
check("dos documentos se aceptan", len(p.documentos), 2)
check("cada uno conserva su color", [d.opciones.color for d in p.documentos],
      ["byn", "color"])
check("y sus copias", [d.opciones.copias for d in p.documentos], [1, 2])

p = PedidoFotocopias.model_validate(nuevo([
    {"opciones": OPCIONES, "rango": {"modo": "rango", "valor": "2-5"}},
    {"opciones": OPCIONES},
]))
check("el rango es por documento", [d.rango.modo for d in p.documentos],
      ["rango", "todas"])


print("\n== Errores ==")


def rechaza(datos) -> bool:
    try:
        PedidoFotocopias.model_validate(datos)
        return False
    except ValidationError:
        return True


check("un pedido sin documentos ni opciones se rechaza",
      rechaza({"tipo": "fotocopias", "contacto": CONTACTO}), True)
check("una lista de documentos vacía se rechaza", rechaza(nuevo([])), True)
check("un documento sin opciones se rechaza", rechaza(nuevo([{}])), True)
check("un color inválido se rechaza",
      rechaza(nuevo([{"opciones": {**OPCIONES, "color": "sepia"}}])), True)
check("un rango mal escrito se rechaza",
      rechaza(nuevo([{"opciones": OPCIONES, "rango": {"modo": "rango", "valor": "8-3"}}])),
      True)

# Mandar las dos formas a la vez es ambiguo: no se sabe cuál gana.
check("mandar 'opciones' y 'documentos' juntos se rechaza",
      rechaza({"tipo": "fotocopias", "contacto": CONTACTO, "opciones": OPCIONES,
               "documentos": [{"opciones": OPCIONES}]}), True)


print("\n== Cuántos documentos se aceptan ==")

muchos = nuevo([{"opciones": OPCIONES} for _ in range(20)])
check("20 documentos entran", len(PedidoFotocopias.model_validate(muchos).documentos), 20)
check("21 se rechazan (tope para no colgar la impresora ni el pedido)",
      rechaza(nuevo([{"opciones": OPCIONES} for _ in range(21)])), True)


# ─────────────────────────────────────────────
print()
if fallos:
    print(f"✗ {len(fallos)} fallo(s): {', '.join(fallos)}")
    sys.exit(1)
print("✓ todos los tests del contrato pasaron")
