"""Cuatro reportes agregados y exportación CSV, sin dependencias externas."""

import csv
from datetime import date
from pathlib import Path

from backend.models.entidades import entero, importe
from backend.daos.catalogo_dao import CatalogoDAO
from backend.daos.reportes_dao import ReportesDAO
from backend.patterns.estados_bulto import ErrorDominio


REPORTES = {
    "ventas_ingresos": "Ventas e ingresos",
    "ranking_margen": "Ranking de productos y margen",
    "existencias_minimos": "Existencias y mínimos actuales",
    "rechazos_precinto": "Rechazos por precinto",
}


def _fecha(valor):
    if valor in (None, ""):
        return None
    try:
        if not isinstance(valor, str) or date.fromisoformat(valor).isoformat() != valor:
            raise ValueError
    except ValueError as error:
        raise ErrorDominio("Use fechas válidas con formato AAAA-MM-DD.") from error
    return valor


class GeneradorReportes:
    def __init__(self, conexion):
        self.cx = conexion

    def generar(self, tipo, desde=None, hasta=None, ubicacion_id=None, medio_pago=None):
        if tipo not in REPORTES:
            raise ErrorDominio("Seleccione uno de los cuatro reportes disponibles.")
        desde, hasta = _fecha(desde), _fecha(hasta)
        if desde and hasta and desde > hasta:
            raise ErrorDominio("La fecha desde no puede ser posterior a hasta.")
        if tipo == "existencias_minimos" and (desde or hasta):
            raise ErrorDominio("El reporte de existencias es actual; no admite fechas históricas.")
        ubicacion = entero(ubicacion_id, "Ubicación") if ubicacion_id is not None else None
        if ubicacion is not None:
            fila = CatalogoDAO(self.cx).ubicacion(ubicacion)
            if tipo != "existencias_minimos" and fila["tipo"] != "LOCAL":
                raise ErrorDominio("Seleccione una ubicación válida para este reporte.")
        medio = str(medio_pago).strip().upper() if medio_pago else None
        if medio and tipo != "ventas_ingresos":
            raise ErrorDominio("El filtro de medio de pago solo corresponde a ventas e ingresos.")
        parametros = {"desde": desde, "hasta": hasta, "ubicacion": ubicacion, "medio": medio}
        secciones = ReportesDAO(self.cx).consultar(tipo, parametros)
        return {
            "titulo": REPORTES[tipo], "tipo": tipo, "filtros": parametros, "secciones": secciones,
            "notas": {
                "ventas_ingresos": "El medio filtra solo caja. El total comercial cuenta cada venta una vez. Devoluciones por su fecha real.",
                "ranking_margen": "Margen estimado, no utilidad contable. Solo la devolución vendible revierte costo; la no vendible conserva costo no recuperado. Eventos por su fecha real.",
                "existencias_minimos": "Foto actual, sin filtro temporal. Promedio solo del Disponible. Bloqueado no habilita venta. Valor unitario redondeado al centavo.",
                "rechazos_precinto": "Período de decisión final. Tasa = rechazados / (verificados + rechazados). Valor comprometido no equivale a pérdida. Tránsito: despacho a recepción.",
            }[tipo],
        }


def exportar_csv(reporte, ruta):
    """Exporta exactamente la consulta visible, con filtros y secciones identificadas."""
    def seguro(valor):
        if isinstance(valor, str) and valor.lstrip().startswith(("=", "+", "-", "@")):
            return "'" + valor
        return valor

    with Path(ruta).open("w", encoding="utf-8-sig", newline="") as archivo:
        writer = csv.writer(archivo, delimiter=";")
        writer.writerow([reporte["titulo"]])
        writer.writerow([seguro(reporte["notas"])])
        writer.writerow([f"{clave}: {valor or 'Todos'}" for clave, valor in reporte["filtros"].items()])
        for seccion in reporte["secciones"]:
            writer.writerow([])
            writer.writerow([seccion["nombre"]])
            writer.writerow([titulo for _, titulo in seccion["columnas"]])
            for fila in seccion["filas"]:
                writer.writerow([
                    importe(fila[clave]) if clave.endswith("_centavos") and fila.get(clave) is not None
                    else seguro(fila.get(clave, "")) for clave, _ in seccion["columnas"]
                ])
