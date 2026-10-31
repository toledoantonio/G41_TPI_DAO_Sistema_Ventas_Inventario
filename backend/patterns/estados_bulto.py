"""Patrón State: clase base abstracta (ABC) y estados concretos del bulto."""

from abc import ABC, abstractmethod


class ErrorDominio(ValueError):
    """Una operación no cumple las reglas del negocio."""


class EstadoBulto(ABC):
    """Contrato común para los estados del bulto (Cap. 11.2 y Cap. 16.2).

    Cada estado concreto define su nombre y sobrescribe únicamente las
    transiciones permitidas, invocando cambiar_estado(...) sobre el contexto.
    """

    @property
    @abstractmethod
    def nombre(self):
        pass

    def _rechazar(self, accion):
        raise ErrorDominio(f"No se puede {accion} un bulto {self.nombre}.")

    def precintar(self, contexto):
        self._rechazar("precintar")

    def despachar(self, contexto):
        self._rechazar("despachar")

    def recibir(self, contexto):
        self._rechazar("recibir")

    def verificar(self, contexto, roto):
        self._rechazar("verificar")

    def __str__(self):
        return self.nombre

    def __eq__(self, otro):
        if not isinstance(otro, EstadoBulto):
            return False
        return self.nombre == otro.nombre


class Preparado(EstadoBulto):
    nombre = "Preparado"

    def precintar(self, contexto):
        contexto.cambiar_estado(Precintado())


class Precintado(EstadoBulto):
    nombre = "Precintado"

    def despachar(self, contexto):
        contexto.cambiar_estado(EnTransito())


class EnTransito(EstadoBulto):
    nombre = "En tránsito"

    def recibir(self, contexto):
        contexto.cambiar_estado(Recibido())


class Recibido(EstadoBulto):
    nombre = "Recibido"

    def verificar(self, contexto, roto):
        contexto.cambiar_estado(Rechazado() if roto else Verificado())


class Verificado(EstadoBulto):
    nombre = "Verificado"


class Rechazado(EstadoBulto):
    nombre = "Rechazado"


ESTADOS = {
    clase.nombre: clase
    for clase in (Preparado, Precintado, EnTransito, Recibido, Verificado, Rechazado)
}


def recuperar_estado(nombre):
    if isinstance(nombre, EstadoBulto):
        return nombre
    try:
        return ESTADOS[nombre]()
    except KeyError as error:
        raise ErrorDominio(f"Estado de bulto desconocido: {nombre}.") from error
