"""Valores y comportamiento del dominio, sin SQL ni controles gráficos."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from backend.patterns.estados_bulto import ErrorDominio, recuperar_estado


def texto(valor, nombre):
    resultado = "" if valor is None else str(valor).strip()
    if not resultado:
        raise ErrorDominio(f"{nombre} es obligatorio.")
    return resultado


def codigo(valor):
    return texto(valor, "Código").upper()


def entero(valor, nombre="Cantidad", minimo=1):
    try:
        numero = Decimal(str(valor))
        if not numero.is_finite() or numero != numero.to_integral_value() or numero < minimo:
            raise ValueError
        if numero > 1_000_000_000:
            raise ValueError
        return int(numero)
    except (InvalidOperation, ValueError):
        raise ErrorDominio(f"{nombre} debe ser un entero entre {minimo} y 1000000000.") from None


def centavos(valor):
    try:
        monto = Decimal(str(valor).replace(",", "."))
        if not monto.is_finite() or monto < 0 or monto > Decimal("1000000000"):
            raise ValueError
        resultado = monto * 100
        if resultado != resultado.to_integral_value():
            raise ValueError
        return int(resultado)
    except (InvalidOperation, ValueError):
        raise ErrorDominio("Importe inválido: use un valor no negativo con hasta dos decimales.") from None


def importe(valor_centavos):
    return f"{Decimal(valor_centavos) / 100:.2f}"


def consolidar(detalles):
    """Agrupar renglones repetidos antes de validar stock o cantidades pendientes."""
    resultado = {}
    for producto_id, cantidad in detalles:
        producto_id = entero(producto_id, "Producto")
        resultado[producto_id] = entero(resultado.get(producto_id, 0) + entero(cantidad))
    if not resultado:
        raise ErrorDominio("Debe agregar al menos un producto.")
    return resultado


@dataclass(frozen=True)
class Producto:
    codigo: str
    descripcion: str
    categoria_id: int
    precio_centavos: int

    def __post_init__(self):
        if self.precio_centavos < 0 or not self.codigo or not self.descripcion:
            raise ErrorDominio("Datos de producto inválidos.")


class Bulto:
    def __init__(self, identificador, estado, precinto=None):
        self.id = identificador
        self.precinto = precinto
        self._estado = recuperar_estado(estado)

    @property
    def estado(self):
        return self._estado.nombre

    def precintar(self, valor):
        precinto = codigo(valor)
        siguiente = self._estado.precintar()
        self.precinto = precinto
        self._estado = siguiente

    def despachar(self):
        self._estado = self._estado.despachar()

    def recibir(self):
        self._estado = self._estado.recibir()

    def verificar(self, precinto_observado, roto):
        if not isinstance(roto, bool):
            raise ErrorDominio("Indique si el precinto está roto.")
        observado = codigo(precinto_observado)
        # Roto siempre implica rechazo. Un código distinto pero íntegro no se acepta.
        if not roto and observado != self.precinto:
            raise ErrorDominio("El precinto observado no coincide; el bulto permanece bloqueado.")
        self._estado = self._estado.verificar(roto)
