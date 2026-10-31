"""Devoluciones comerciales compuestas por detalles de la venta original."""

from backend.models.entidades import codigo, entero, texto
from backend.patterns.estados_bulto import ErrorDominio


class DetalleDevolucion:
    CONDICIONES = ("VENDIBLE", "NO_VENDIBLE")

    def __init__(self, original, cantidad, condicion):
        self._detalle_venta_id = entero(original["id"], "Detalle de venta")
        self._producto_id = original["producto_id"]
        self._cantidad = entero(cantidad)
        self._condicion = codigo(condicion)
        if self._condicion not in self.CONDICIONES:
            raise ErrorDominio("La condición debe ser VENDIBLE o NO_VENDIBLE.")
        self._precio = original["precio_unitario_centavos"]
        self._costo = original["costo_unitario_centavos"]

    @property
    def detalle_venta_id(self):
        return self._detalle_venta_id

    @property
    def producto_id(self):
        return self._producto_id

    @property
    def cantidad(self):
        return self._cantidad

    @property
    def condicion(self):
        return self._condicion

    @property
    def costo_unitario_centavos(self):
        return self._costo

    @property
    def reintegro_centavos(self):
        return self._cantidad * self._precio

    def __str__(self):
        return f"Detalle #{self._detalle_venta_id}: {self._cantidad} u. ({self._condicion})"


class Devolucion:
    def __init__(self, venta_id, local_id, referencia, motivo, medio_reintegro, fecha):
        self._venta_id = entero(venta_id, "Venta")
        self._local_id = entero(local_id, "Local")
        self._referencia = codigo(referencia)
        self._motivo = texto(motivo, "Motivo de devolución")
        self._medio_reintegro = codigo(medio_reintegro)
        self._fecha = fecha
        self._detalles = []

    @property
    def venta_id(self):
        return self._venta_id

    @property
    def local_id(self):
        return self._local_id

    @property
    def referencia(self):
        return self._referencia

    @property
    def motivo(self):
        return self._motivo

    @property
    def medio_reintegro(self):
        return self._medio_reintegro

    @property
    def fecha(self):
        return self._fecha

    @property
    def detalles(self):
        return list(self._detalles)

    @property
    def total_centavos(self):
        return sum(d.reintegro_centavos for d in self._detalles)

    def agregar_detalle(self, original, cantidad, condicion):
        self._detalles.append(DetalleDevolucion(original, cantidad, condicion))

    def validar(self):
        if not self._detalles:
            raise ErrorDominio("Agregue al menos un detalle a la devolución.")

    def __str__(self):
        return f"Devolución {self._referencia} de venta #{self._venta_id}"
