"""State: cada estado decide qué acciones admite y su estado siguiente."""


class ErrorDominio(ValueError):
    """Una operación no cumple las reglas del negocio."""


class EstadoBulto:
    nombre = ""

    def _rechazar(self, accion):
        raise ErrorDominio(f"No se puede {accion} un bulto {self.nombre}.")

    def precintar(self):
        return self._rechazar("precintar")

    def despachar(self):
        return self._rechazar("despachar")

    def recibir(self):
        return self._rechazar("recibir")

    def verificar(self, roto):
        return self._rechazar("verificar")


class Preparado(EstadoBulto):
    nombre = "Preparado"

    def precintar(self):
        return Precintado()


class Precintado(EstadoBulto):
    nombre = "Precintado"

    def despachar(self):
        return EnTransito()


class EnTransito(EstadoBulto):
    nombre = "En tránsito"

    def recibir(self):
        return Recibido()


class Recibido(EstadoBulto):
    nombre = "Recibido"

    def verificar(self, roto):
        return Rechazado() if roto else Verificado()


class Verificado(EstadoBulto):
    nombre = "Verificado"


class Rechazado(EstadoBulto):
    nombre = "Rechazado"


ESTADOS = {clase.nombre: clase for clase in (
    Preparado, Precintado, EnTransito, Recibido, Verificado, Rechazado
)}


def recuperar_estado(nombre):
    try:
        return ESTADOS[nombre]()
    except KeyError as error:
        raise ErrorDominio(f"Estado de bulto desconocido: {nombre}.") from error
