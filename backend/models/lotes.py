"""Identificación de lotes y fechas civiles de vencimiento."""

from datetime import date

from backend.models.entidades import codigo, entero
from backend.patterns.estados_bulto import ErrorDominio


def fecha_vencimiento(valor):
    if valor in (None, ""):
        return None
    try:
        if not isinstance(valor, str) or date.fromisoformat(valor).isoformat() != valor:
            raise ValueError
    except ValueError as error:
        raise ErrorDominio("El vencimiento debe ser una fecha válida AAAA-MM-DD.") from error
    return valor


class Lote:
    def __init__(self, producto_id, identificacion, vencimiento=None):
        self._producto_id = entero(producto_id, "Producto")
        self._codigo = codigo(identificacion)
        self._vencimiento = fecha_vencimiento(vencimiento)

    @property
    def producto_id(self):
        return self._producto_id

    @property
    def codigo(self):
        return self._codigo

    @property
    def vencimiento(self):
        return self._vencimiento

    def esta_vencido(self, hoy):
        return self._vencimiento is not None and self._vencimiento < hoy

    def __str__(self):
        return f"{self._codigo} (vence {self._vencimiento or 'sin fecha'})"
