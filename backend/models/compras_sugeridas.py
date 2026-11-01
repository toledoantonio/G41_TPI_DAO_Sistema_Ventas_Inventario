"""Cálculo de faltantes de red sin duplicar necesidades y pedidos abiertos."""


class NecesidadCompra:
    def __init__(self, minimo_cd, disponible_cd, necesidad_locales, compras_pendientes):
        self.minimo_cd = minimo_cd
        self.disponible_cd = disponible_cd
        self.necesidad_locales = necesidad_locales
        self.compras_pendientes = compras_pendientes

    @property
    def cantidad_sugerida(self):
        return max(0, self.minimo_cd + self.necesidad_locales - self.disponible_cd - self.compras_pendientes)
