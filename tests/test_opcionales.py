"""Opcionales integrados: demanda neta, recepción real, FEFO y trazabilidad."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import sqlite3

import pytest

from backend.database.config import BaseDatos
from backend.patterns.estados_bulto import ErrorDominio
from backend.services.sistema import Sistema
from backend.daos.lote_dao import LoteDAO
from tests.test_costos_migracion import datos, tmp_path, quitar_esquema_lotes


def dia(monkeypatch, fecha):
    monkeypatch.setattr("backend.services.sistema.ahora", lambda: fecha + "T12:00:00-03:00")


def consistente(s):
    with s.db.conectar() as cx:
        assert cx.execute("PRAGMA foreign_key_check").fetchall() == []
        for f in cx.execute("SELECT * FROM existencia"):
            suma = cx.execute("""SELECT COALESCE(SUM(el.disponible), 0), COALESCE(SUM(el.reservado), 0),
                COALESCE(SUM(el.pendiente), 0), COALESCE(SUM(el.rechazado), 0)
                FROM existencia_lote el JOIN lote l ON l.id = el.lote_id
                WHERE el.ubicacion_id = ? AND l.producto_id = ?""", (f["ubicacion_id"], f["producto_id"])).fetchone()
            assert tuple(suma) == tuple(f[c] for c in ("disponible", "reservado", "pendiente", "rechazado"))
        for f in cx.execute("SELECT * FROM existencia_lote"):
            suma = cx.execute("""SELECT SUM(disponible), SUM(reservado), SUM(pendiente), SUM(rechazado)
                FROM movimiento_lote WHERE ubicacion_id = ? AND lote_id = ?""", (f["ubicacion_id"], f["lote_id"])).fetchone()
            assert tuple(v or 0 for v in suma) == tuple(f[c] for c in ("disponible", "reservado", "pendiente", "rechazado"))


def preparar(s, cd, local, p, cantidad, numero="R1"):
    orden = s.crear_orden(cd, local, [(p, cantidad)])
    b = s.preparar_bulto(orden, numero, [(p, cantidad)])
    s.precintar(b, numero)
    return b


def test_lotes_fefo_venta_devolucion_y_traza(datos, monkeypatch):
    s, cd, local, proveedor, p = datos
    dia(monkeypatch, "2030-01-01")
    s.registrar_compra("C1", proveedor, cd, [
        (p, 2, "60", "B", "2030-02-01"), (p, 3, "60", "A", "2030-01-20"),
        (p, 1, "60", "B", "2030-02-01"), (p, 2, "60"),
    ])
    b = preparar(s, cd, local, p, 5)
    assert [(f["codigo"], f["cantidad"]) for f in s.lotes_bulto(b)] == [("B", 2), ("A", 3)]
    s.despachar(b)
    s.recibir(b, local)
    s.verificar(b, local, "R1")
    venta = s.registrar_venta(local, [(p, 4)], [("EFECTIVO", "600")])
    detalle = s.detalle_venta(venta)[0]["id"]
    asignaciones = s.lotes_devolvibles(detalle)
    assert {f["codigo"]: f["vendida"] for f in asignaciones} == {"B": 1, "A": 3}
    with pytest.raises(ErrorDominio, match="Indique el lote"):
        s.registrar_devolucion(venta, local, [(detalle, 1, "VENDIBLE")], "EFECTIVO", "Retorno", "D1")
    a = next(f["lote_id"] for f in asignaciones if f["codigo"] == "A")
    s.registrar_devolucion(venta, local, [(detalle, 1, "VENDIBLE", a)], "EFECTIVO", "Retorno", "D1")
    dia(monkeypatch, "2030-01-21")
    with pytest.raises(ErrorDominio, match="NO_VENDIBLE"):
        s.registrar_devolucion(venta, local, [(detalle, 1, "VENDIBLE", a)], "EFECTIVO", "Retorno", "D2")
    s.registrar_devolucion(venta, local, [(detalle, 1, "NO_VENDIBLE", a)], "EFECTIVO", "Retorno vencido", "D2")
    causas = {f["causa"] for f in s.trazabilidad_lote(a)}
    assert causas == {"COMPRA", "PREPARACION", "DESPACHO", "RECEPCION", "VERIFICACION", "VENTA", "DEVOLUCION"}
    consistente(s)
    ruta = s.db.ruta
    BaseDatos.reset_for_testing()
    s = Sistema(ruta)
    assert s.trazabilidad_lote(a)[-1]["rechazado"] == 1
    consistente(s)


def test_vencido_no_vende_y_faltantes_usan_vendible(datos, monkeypatch):
    s, cd, local, proveedor, p = datos
    dia(monkeypatch, "2030-01-01")
    s.registrar_compra("C1", proveedor, cd, [(p, 5, "60", "A", "2030-01-01")])
    b = preparar(s, cd, local, p, 5)
    s.despachar(b)
    s.recibir(b, local)
    s.verificar(b, local, "R1")
    s.configurar_minimo(local, p, 4)
    dia(monkeypatch, "2030-01-02")
    with pytest.raises(ErrorDominio, match="insuficiente"):
        s.registrar_venta(local, [(p, 1)], [("EFECTIVO", "150")])
    saldo = next(f for f in s.listar("inventario") if f["ubicacion_id"] == local)
    assert (saldo["disponible"], saldo["vendible"], saldo["vencido"], saldo["faltante"]) == (5, 0, 5, 4)
    fila = s.generar_reporte("existencias_minimos", ubicacion_id=local)["secciones"][1]["filas"][0]
    assert (fila["vendible"], fila["vencido"], fila["faltante"]) == (0, 5, 4)
    assert s.sugerencias_compra(cd)[0]["cantidad_sugerida"] == 4
    consistente(s)


@pytest.mark.parametrize("etapa", ["despachar", "verificar"])
def test_vencimiento_durante_logistica_revierte_todo(datos, monkeypatch, etapa):
    s, cd, local, proveedor, p = datos
    dia(monkeypatch, "2030-01-01")
    s.registrar_compra("C1", proveedor, cd, [(p, 5, "60", "A", "2030-01-01")])
    b = preparar(s, cd, local, p, 5)
    if etapa == "verificar":
        s.despachar(b)
        s.recibir(b, local)
    dia(monkeypatch, "2030-01-02")
    antes = s.listar("inventario"), s.historial_bulto(b), s.listar("lotes")
    with pytest.raises(ErrorDominio, match="vencidos"):
        s.despachar(b) if etapa == "despachar" else s.verificar(b, local, "R1")
    assert (s.listar("inventario"), s.historial_bulto(b), s.listar("lotes")) == antes
    consistente(s)


@pytest.mark.parametrize("vence", ["2029-12-31", "2030-02-30", "01/02/2030"])
def test_compra_lote_invalido_no_deja_stock_ni_documentos(datos, monkeypatch, vence):
    s, cd, _, proveedor, p = datos
    dia(monkeypatch, "2030-01-01")
    with pytest.raises(ErrorDominio):
        s.registrar_compra("C1", proveedor, cd, [(p, 5, "60", "A", vence)])
    assert s.listar("compras") == [] and s.listar("lotes") == []
    assert all(f["disponible"] == 0 for f in s.listar("inventario"))


def test_lote_reutilizado_no_cambia_vencimiento(datos, monkeypatch):
    s, cd, _, proveedor, p = datos
    dia(monkeypatch, "2030-01-01")
    s.registrar_compra("C1", proveedor, cd, [(p, 5, "60", " A ", "2030-02-01")])
    with pytest.raises(ErrorDominio, match="otro vencimiento"):
        s.registrar_compra("C2", proveedor, cd, [(p, 5, "60", "a", "2030-03-01")])
    s.registrar_compra("C2", proveedor, cd, [(p, 5, "60", "a", "2030-02-01")])
    assert len(s.listar("lotes")) == 1 and s.listar("lotes")[0]["disponible"] == 10
    consistente(s)


def test_sugerencias_no_duplican_minimos_pedidos_ni_transito(datos):
    s, cd, local, proveedor, p = datos
    s.configurar_minimo(cd, p, 5)
    s.configurar_minimo(local, p, 10)
    s.registrar_compra("C1", proveedor, cd, [(p, 4, "60")])
    assert s.sugerencias_compra(cd)[0]["cantidad_sugerida"] == 11
    orden = s.crear_orden(cd, local, [(p, 12)])
    assert s.sugerencias_compra(cd)[0]["cantidad_sugerida"] == 13
    b = s.preparar_bulto(orden, "R1", [(p, 3)])
    s.precintar(b, "S1")
    for accion in (None, "despachar", "recibir", "verificar"):
        if accion == "despachar": s.despachar(b)
        if accion == "recibir": s.recibir(b, local)
        if accion == "verificar": s.verificar(b, local, "S1")
        assert s.sugerencias_compra(cd)[0]["cantidad_sugerida"] == 13
    consistente(s)


def test_sugerencia_recepcion_real_y_cancelacion(datos, monkeypatch):
    s, cd, local, proveedor, p = datos
    dia(monkeypatch, "2030-01-01")
    s.configurar_minimo(local, p, 10)
    orden = s.generar_orden_compra(cd, proveedor, "OC-1")
    assert s.sugerencias_compra(cd)[0]["cantidad_sugerida"] == 0
    assert all(f["disponible"] == 0 for f in s.listar("inventario"))
    with pytest.raises(ErrorDominio, match="No hay faltantes"):
        s.generar_orden_compra(cd, proveedor, "OC-2")
    with pytest.raises(ErrorDominio, match="exactamente"):
        s.registrar_compra("C1", proveedor, cd, [(p, 9, "60")], orden_sugerida_id=orden)
    assert s.obtener_orden_compra(orden)["estado"] == "SUGERIDA"
    compra = s.registrar_compra("C1", proveedor, cd, [(p, 4, "60", "A", "2030-02-01"), (p, 6, "60", "B", None)], orden_sugerida_id=orden)
    assert s.obtener_orden_compra(orden)["compra_id"] == compra
    assert s.obtener_orden_compra(orden)["estado"] == "RECIBIDA"
    with pytest.raises(ErrorDominio, match="ya fue"):
        s.registrar_compra("C2", proveedor, cd, [(p, 10, "60")], orden_sugerida_id=orden)
    with pytest.raises(ErrorDominio): s.cancelar_orden_compra(orden)
    s.configurar_minimo(local, p, 15)
    cancelada = s.generar_orden_compra(cd, proveedor, "OC-2")
    s.cancelar_orden_compra(cancelada)
    assert s.obtener_orden_compra(cancelada)["estado"] == "CANCELADA"
    assert s.sugerencias_compra(cd)[0]["cantidad_sugerida"] == 5
    consistente(s)


def test_sugerencias_concurrentes_no_duplican_compra(datos):
    s, cd, local, proveedor, p = datos
    s.configurar_minimo(local, p, 10)
    barrera = Barrier(2)

    def generar(n):
        barrera.wait(timeout=5)
        try:
            s.generar_orden_compra(cd, proveedor, f"OC-{n}")
            return True
        except ErrorDominio:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(generar, (1, 2))) == [False, True]
    assert len(s.listar("compras_sugeridas")) == 1


def test_migracion_v2_no_inventa_trazabilidad_y_conserva_saldos(datos):
    s, cd, local, proveedor, p = datos
    s.registrar_compra("C1", proveedor, cd, [(p, 10, "60")])
    b = preparar(s, cd, local, p, 5)
    saldos = s.listar("inventario")
    with s.db.transaccion() as cx:
        quitar_esquema_lotes(cx)
        cx.execute("PRAGMA user_version = 2")
    ruta = s.db.ruta
    BaseDatos.reset_for_testing()
    s = Sistema(ruta)
    assert s.listar("inventario") == saldos
    assert all(f["legado"] == 1 and f["vencimiento"] is None for f in s.listar("lotes"))
    assert s.lotes_bulto(b)[0]["legado"] == 1
    s.despachar(b)
    s.recibir(b, local)
    s.verificar(b, local, "R1")
    venta = s.registrar_venta(local, [(p, 1)], [("EFECTIVO", "150")])
    detalle = s.detalle_venta(venta)[0]["id"]
    s.registrar_devolucion(venta, local, [(detalle, 1, "VENDIBLE")], "EFECTIVO", "Retorno", "D1")
    consistente(s)


def test_fallo_en_movimiento_lote_revierte_compra_y_sugerencia(datos, monkeypatch):
    s, cd, local, proveedor, p = datos
    s.configurar_minimo(local, p, 10)
    orden = s.generar_orden_compra(cd, proveedor, "OC1")

    def fallar(*args, **kwargs):
        raise sqlite3.OperationalError("Fallo simulado del libro de lotes")

    monkeypatch.setattr(LoteDAO, "mover", fallar)
    with pytest.raises(sqlite3.OperationalError):
        s.registrar_compra("C1", proveedor, cd, [(p, 10, "60")], orden_sugerida_id=orden)
    assert s.obtener_orden_compra(orden)["estado"] == "SUGERIDA"
    assert s.listar("compras") == [] and s.listar("lotes") == []
    assert all(f["disponible"] == 0 for f in s.listar("inventario"))


def test_proveedor_y_cantidades_sugeridas_se_validan(datos):
    s, cd, local, proveedor, p = datos
    s.configurar_minimo(local, p, 10)
    with pytest.raises(ErrorDominio, match="supera"):
        s.generar_orden_compra(cd, proveedor, "OC1", [(p, 11)])
    parcial = s.generar_orden_compra(cd, proveedor, "OC1", [(p, 4)])
    assert s.sugerencias_compra(cd)[0]["cantidad_sugerida"] == 6
    otro = s.guardar_proveedor("PR2", "Otro proveedor")
    with pytest.raises(ErrorDominio, match="proveedor"):
        s.registrar_compra("C1", otro, cd, [(p, 4, "60")], orden_sugerida_id=parcial)
    s.registrar_compra("C1", proveedor, cd, [(p, 4, "60")], orden_sugerida_id=parcial)
    assert s.sugerencias_compra(cd)[0]["cantidad_sugerida"] == 6
    consistente(s)


def test_fefo_concurrente_no_duplica_lotes(datos):
    s, cd, local, proveedor, p = datos
    s.registrar_compra("C1", proveedor, cd, [(p, 10, "60")])
    orden = s.crear_orden(cd, local, [(p, 12)])
    barrera = Barrier(2)

    def reservar(n):
        barrera.wait(timeout=5)
        try:
            s.preparar_bulto(orden, f"R{n}", [(p, 6)])
            return True
        except ErrorDominio:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(reservar, (1, 2))) == [False, True]
    fila = s.listar("lotes")[0]
    assert (fila["disponible"], fila["reservado"]) == (4, 6)
    consistente(s)


def test_libro_lotes_no_se_modifica_ni_borra(datos):
    s, cd, _, proveedor, p = datos
    s.registrar_compra("C1", proveedor, cd, [(p, 10, "60")])
    for sentencia in ("UPDATE movimiento_lote SET disponible = 999", "DELETE FROM movimiento_lote"):
        with pytest.raises(sqlite3.IntegrityError, match="inmutable"):
            with s.db.transaccion() as cx:
                cx.execute(sentencia)
    consistente(s)


def test_sugerencia_respeta_limite_de_cantidad_recepcion(datos):
    s, cd, local, proveedor, p = datos
    otro = s.guardar_ubicacion("L2", "Otro local", "Dirección", "LOCAL")
    s.configurar_minimo(local, p, 1_000_000_000)
    s.configurar_minimo(otro, p, 1_000_000_000)
    with pytest.raises(ErrorDominio, match="Cantidad"):
        s.generar_orden_compra(cd, proveedor, "OC1")
    assert s.listar("compras_sugeridas") == []
    s.generar_orden_compra(cd, proveedor, "OC1", [(p, 1_000_000_000)])
    assert s.sugerencias_compra(cd)[0]["cantidad_sugerida"] == 1_000_000_000
