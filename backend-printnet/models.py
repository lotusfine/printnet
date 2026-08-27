"""Modelos Pydantic: el contrato de la API.

Los nombres y valores replican EXACTAMENTE lo que arma el frontend
(ver SPEC.md, sección "Contrato con el frontend"):
  - /fotocopias: contacto + opciones + rango (+ terminaciones, aún sin UI)
  - /fotos: contacto + material/formato/gramaje + terminaciones
"""

import re
from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator

# Mismas reglas que el frontend (ContactForm.jsx / FileUpload.jsx)
TELEFONO_RE = re.compile(r"^\+\d{8,15}$")
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
RANGO_RE = re.compile(r"^\d+(-\d+)?$")

TERMINACIONES = Literal["Anillado", "Plastificado", "Corte"]


class Contacto(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    # Ya compuesto por el frontend con composeTelefono(): "+549{area}{numero}"
    telefono: str
    email: str = Field(max_length=254)

    @field_validator("nombre", "telefono", "email")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()

    @field_validator("telefono")
    @classmethod
    def _telefono_valido(cls, v: str) -> str:
        if not TELEFONO_RE.match(v):
            raise ValueError("teléfono inválido: se espera formato +549XXXXXXXXXX")
        return v

    @field_validator("email")
    @classmethod
    def _email_valido(cls, v: str) -> str:
        if not EMAIL_RE.match(v):
            raise ValueError("email inválido")
        return v


class OpcionesFotocopias(BaseModel):
    color: Literal["byn", "color"]
    caras: Literal["simple", "doble"]
    copias: int = Field(ge=1, le=500)
    tamano: Literal["A4", "A3"]


class Rango(BaseModel):
    modo: Literal["todas", "rango"] = "todas"
    valor: str = ""

    @model_validator(mode="after")
    def _rango_valido(self) -> "Rango":
        if self.modo != "rango":
            return self
        v = self.valor.strip()
        if not RANGO_RE.match(v):
            raise ValueError('rango inválido: se espera "N-M" o un número, ej. "3-16"')
        partes = v.split("-")
        inicio = int(partes[0])
        fin = int(partes[1]) if len(partes) == 2 else inicio
        if inicio < 1:
            raise ValueError("las páginas empiezan en 1")
        if inicio > fin:
            raise ValueError("el inicio del rango no puede ser mayor que el fin")
        return self


class DocumentoFotocopias(BaseModel):
    """Un documento del pedido, con su propia configuración de impresión."""

    opciones: OpcionesFotocopias
    rango: Rango = Field(default_factory=Rango)
    # La UI de /fotocopias todavía no ofrece terminaciones; el contrato ya
    # las acepta porque definen requiere_manual (decisión de arquitectura 2).
    terminaciones: list[TERMINACIONES] = Field(default_factory=list)


# Tope de documentos por pedido. No es una regla de negocio: es para que un
# pedido no encole 200 trabajos de impresión ni deje al backend convirtiendo
# archivos durante minutos mientras el cliente espera en la pantalla.
MAX_DOCUMENTOS = 20


class PedidoFotocopias(BaseModel):
    """Pedido de fotocopias con uno o varios documentos.

    ACEPTA DOS FORMAS, a propósito:

      1. La nueva:   {"documentos": [{"opciones": ..., "rango": ...}, ...]}
      2. La vieja:   {"opciones": ..., "rango": ..., "terminaciones": [...]}

    La vieja es la que manda la web hoy. Las dos piezas se despliegan por
    separado —el backend por git en la notebook, la web subiendo archivos a
    cPanel—, así que si el contrato solo aceptara la forma nueva habría una
    ventana con los pedidos rotos. Internamente todo se normaliza a
    `documentos`, así que el resto del sistema conoce una sola forma.
    """

    tipo: Literal["fotocopias"]
    contacto: Contacto
    documentos: list[DocumentoFotocopias] = Field(min_length=1, max_length=MAX_DOCUMENTOS)

    @model_validator(mode="before")
    @classmethod
    def _aceptar_forma_vieja(cls, datos):
        if not isinstance(datos, dict):
            return datos
        tiene_viejo = "opciones" in datos
        tiene_nuevo = "documentos" in datos

        if tiene_viejo and tiene_nuevo:
            raise ValueError(
                "mandá 'documentos' o 'opciones', no las dos: no se sabe cuál gana"
            )
        if tiene_viejo:
            datos = dict(datos)
            datos["documentos"] = [{
                "opciones": datos.pop("opciones"),
                "rango": datos.pop("rango", {}),
                "terminaciones": datos.pop("terminaciones", []),
            }]
        return datos


class PedidoFotos(BaseModel):
    tipo: Literal["fotos"]
    contacto: Contacto
    material: Literal["hoja-foto", "vegetal", "opalina", "autoadhesiva"]
    formato: Optional[Literal["13x18", "9x13", "6x9"]] = None
    gramaje: Optional[Literal[120, 150, 180, 240]] = None
    terminaciones: list[TERMINACIONES] = Field(default_factory=list)

    @model_validator(mode="after")
    def _subselectores(self) -> "PedidoFotos":
        if self.material == "hoja-foto" and self.formato is None:
            raise ValueError("hoja-foto requiere formato (13x18, 9x13 o 6x9)")
        if self.material == "opalina" and self.gramaje is None:
            raise ValueError("opalina requiere gramaje (120, 150, 180 o 240)")
        return self


Pedido = Annotated[Union[PedidoFotocopias, PedidoFotos], Field(discriminator="tipo")]

ESTADOS = (
    "pendiente_pago", "pago_rechazado",
    "pendiente", "imprimiendo", "listo", "entregado", "cancelado",
)


class CambioEstado(BaseModel):
    # pendiente_pago y pagado se manejan por el flujo de pago (webhook), no
    # por el admin; solo puede cancelar pedidos en esos estados.
    estado: Literal[
        "pendiente_pago", "pago_rechazado",
        "pendiente", "imprimiendo", "listo", "entregado", "cancelado",
    ]
