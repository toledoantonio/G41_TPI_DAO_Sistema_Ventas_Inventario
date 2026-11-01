"""Devoluciones transaccionales y reportes contrastados con importes conocidos."""

from concurrent.futures import ThreadPoolExecutor
import csv
import sqlite3
from threading import Barrier

import pytest

from backend.daos.venta_dao import VentaDAO
from backend.database.config import BaseDatos
from backend.patterns.estados_bulto import ErrorDominio
from backend.reports.generador_reportes import REPORTES, exportar_csv
from backend.services.sistema import Sistema
from tests.test_costos_migracion import datos, enviar, tmp_path, quitar_esquema_lotes


@pytest.fixture
def comercio(datos, monkeypatch):
    s, cd, local, proveedor, p = datos
    monkeypatch.setattr("backend.services.sistema.ahora", lambda: "2026-10-01T10:00:00-03:00")
    categoria = s.listar("productos")[0]["categoria_id"]
    s.guardar_producto("P", "Producto", categoria, "100", p)
    q = s.guardar_producto("Q", "Segundo", categoria, "50")
    s.registrar_compra("C1", proveedor, cd, [(p, 20, "60"), (q, 10, "20")])
    orden = s.crear_orden(cd, local, [(p, 10), (q, 5)])
    b = s.preparar_bulto(orden, "R1", [(p, 10), (q, 5)])
    s.precintar(b, "S1")
    s.despachar(b)
    monkeypatch.setattr("backend.services.sistema.ahora", lambda: "2026-10-02T10:00:00-03:00")
    s.recibir(b, local)
    s.verificar(b, local, "S1")
    monkeypatch.setattr("backend.services.sistema.ahora", lambda: "2026-10-03T10:00:00-03:00")
    venta = s.registrar_venta(local, [(p, 4), (q, 2)], [("EFECTIVO", "200"), ("DEBITO", "300")])
    detalles = {f["producto_id"]: f["id"] for f in s.detalle_venta(venta)}
    return s, cd, local, proveedor, p, q, venta, detalles


def devolver(comercio, referencia="D1"):
    s, _, local, _, p, q, venta, detalles = comercio
    return s.registrar_devolucion(venta, local, [
        (detalles[p], 1, "VENDIBLE"), (detalles[p], 1, "NO_VENDIBLE"), (detalles[q], 1, "VENDIBLE"),
    ], "TRANSFERENCIA", "Cambio y mercadería dañada", referencia)


def test_devolucion_precio_original_condicion_y_persistencia(comercio):
    s, _, local, _, p, q, venta, detalles = comercio
    original = s.comprobante_venta(venta)
    categoria = s.listar("productos")[0]["categoria_id"]
    s.guardar_producto("P", "Producto actualizado", categoria, "999", p)
    dev = devolver(comercio)
    assert s.obtener_devolucion(dev)["total_centavos"] == 25000
    assert s.comprobante_venta(venta) == dict(original, detalles=s.detalle_venta(venta))
    saldos = {f["producto_id"]: f for f in s.listar("inventario") if f["ubicacion_id"] == local}
    assert (saldos[p]["disponible"], saldos[p]["rechazado"], saldos[q]["disponible"]) == (7, 1, 4)
    assert saldos[p]["costo_centavos"] == 6000
    caja = s.listar("caja")
    assert len(caja) == 3
    assert caja[0]["tipo"] == "EGRESO" and caja[0]["importe_centavos"] == 25000
    ruta = s.db.ruta
    BaseDatos.reset_for_testing()
    s = Sistema(ruta)
    assert s.obtener_devolucion(dev)["detalles"][0]["precio_unitario_centavos"] == 10000
    assert s.detalles_devolvibles(venta)[0]["devuelta"] == 2


def test_acumulados_condiciones_y_reintento_no_duplican(comercio):
    s, _, local, _, p, _, venta, detalles = comercio
    devolver(comercio)
    with pytest.raises(ErrorDominio):
        devolver(comercio)
    assert len(s.listar("devoluciones")) == 1
    with pytest.raises(ErrorDominio, match="acumulada"):
        s.registrar_devolucion(venta, local, [(detalles[p], 1, "VENDIBLE"), (detalles[p], 2, "NO_VENDIBLE")], "EFECTIVO", "Motivo", "D2")
    s.registrar_devolucion(venta, local, [(detalles[p], 1, "VENDIBLE"), (detalles[p], 1, "VENDIBLE")], "EFECTIVO", "Resto", "D2")
    assert s.detalles_devolvibles(venta)[0]["devuelta"] == 4
    with pytest.raises(ErrorDominio, match="acumulada"):
        s.registrar_devolucion(venta, local, [(detalles[p], 1, "VENDIBLE")], "EFECTIVO", "Exceso", "D3")


@pytest.mark.parametrize("cantidad,condicion", [(0, "VENDIBLE"), (-1, "VENDIBLE"), (True, "VENDIBLE"), ("1.5", "VENDIBLE"), (1, "OTRA")])
def test_rechaza_cantidades_y_condiciones_invalidas(comercio, cantidad, condicion):
    s, _, local, _, p, _, venta, detalles = comercio
    with pytest.raises(ErrorDominio):
        s.registrar_devolucion(venta, local, [(detalles[p], cantidad, condicion)], "EFECTIVO", "Motivo", "D1")
    assert s.listar("devoluciones") == []


def test_origen_local_motivo_y_detalle_obligatorios(comercio):
    s, _, local, _, p, _, venta, detalles = comercio
    otro_local = s.guardar_ubicacion("L2", "Otro", "Dirección", "LOCAL")
    otra_venta = s.registrar_venta(local, [(p, 1)], [("EFECTIVO", "100")])
    ajeno = s.detalle_venta(otra_venta)[0]["id"]
    casos = [
        (venta, otro_local, [(detalles[p], 1, "VENDIBLE")], "Motivo"),
        (999, local, [(detalles[p], 1, "VENDIBLE")], "Motivo"),
        (venta, local, [(ajeno, 1, "VENDIBLE")], "Motivo"),
        (venta, local, [], "Motivo"),
        (venta, local, [(detalles[p], 1, "VENDIBLE")], ""),
    ]
    for venta_id, local_id, renglones, motivo in casos:
        with pytest.raises(ErrorDominio):
            s.registrar_devolucion(venta_id, local_id, renglones, "EFECTIVO", motivo, "D1")
    assert s.listar("devoluciones") == []


def test_fallo_de_caja_revierte_toda_la_devolucion(comercio, monkeypatch):
    s = comercio[0]
    saldos, caja = s.listar("inventario"), s.listar("caja")

    def fallar(*args, **kwargs):
        raise sqlite3.OperationalError("Fallo de caja simulado")

    monkeypatch.setattr(VentaDAO, "registrar_movimiento_caja", fallar)
    with pytest.raises(sqlite3.OperationalError):
        devolver(comercio)
    assert s.listar("devoluciones") == []
    assert s.listar("inventario") == saldos
    assert s.listar("caja") == caja
    assert all(f["devuelta"] == 0 for f in s.detalles_devolvibles(comercio[6]))


def test_devoluciones_concurrentes_no_superan_venta(comercio):
    s, _, local, _, p, _, venta, detalles = comercio
    barrera = Barrier(2)

    def registrar(numero):
        barrera.wait(timeout=5)
        try:
            s.registrar_devolucion(venta, local, [(detalles[p], 3, "VENDIBLE")], "EFECTIVO", "Motivo", f"D{numero}")
            return True
        except ErrorDominio:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(registrar, (1, 2))) == [False, True]
    assert s.detalles_devolvibles(venta)[0]["devuelta"] == 3


def test_retorno_gratuito_sin_egreso_ficticio(comercio):
    s, _, local, _, p, q, _, _ = comercio
    categoria = s.listar("productos")[0]["categoria_id"]
    s.guardar_producto("Q", "Gratis", categoria, "0", q)
    venta = s.registrar_venta(local, [(p, 1), (q, 1)], [("EFECTIVO", "100")])
    detalle = next(f for f in s.detalle_venta(venta) if f["producto_id"] == q)
    caja = s.listar("caja")
    dev = s.registrar_devolucion(venta, local, [(detalle["id"], 1, "VENDIBLE")], "EFECTIVO", "Retorno gratis", "D0")
    assert s.obtener_devolucion(dev)["total_centavos"] == 0
    assert s.listar("caja") == caja


def test_retorno_vendible_promedia_costo_original_con_stock_actual(comercio):
    s, cd, local, proveedor, p, _, venta, detalles = comercio
    s.registrar_compra("C2", proveedor, cd, [(p, 10, "100")])  # CD: 10 a 60 + 10 a 100 => 80.
    b = enviar(s, cd, local, p, 6, "R2")
    s.despachar(b)
    s.recibir(b, local)
    s.verificar(b, local, "R2")  # local: 6 a 60 + 6 a 80 => 70.
    s.registrar_devolucion(venta, local, [(detalles[p], 2, "VENDIBLE")], "EFECTIVO", "Retorno", "D1")
    fila = next(f for f in s.listar("inventario") if f["ubicacion_id"] == local and f["producto_id"] == p)
    assert fila["costo_centavos"] == 6857  # (12 * 70 + 2 * 60) / 14.


def test_reportes_comerciales_sin_duplicar_cobros_mixtos(comercio):
    s, _, local, _, p, q, _, _ = comercio
    devolver(comercio)
    reporte = s.generar_reporte("ventas_ingresos")
    fila = reporte["secciones"][0]["filas"][0]
    assert (fila["ventas"], fila["devoluciones"], fila["ventas_centavos"], fila["reintegros_centavos"], fila["neto_centavos"]) == (1, 1, 50000, 25000, 25000)
    caja = reporte["secciones"][1]["filas"]
    assert sum(f["neto_centavos"] for f in caja) == 25000
    filtrado = s.generar_reporte("ventas_ingresos", ubicacion_id=local, medio_pago="DEBITO")
    assert filtrado["secciones"][0]["filas"][0]["ventas_centavos"] == 50000
    assert filtrado["secciones"][1]["filas"][0]["neto_centavos"] == 30000
    ranking = s.generar_reporte("ranking_margen")["secciones"][0]["filas"]
    assert [f["producto_id"] for f in ranking] == [p, q]
    assert [f["netas"] for f in ranking] == [2, 1]
    assert [f["margen_centavos"] for f in ranking] == [2000, 3000]
    assert ranking[0]["costo_bloqueado_centavos"] == 6000


def test_reportes_por_fecha_real_inclusive_y_devolucion_otro_periodo(comercio, monkeypatch):
    s = comercio[0]
    monkeypatch.setattr("backend.services.sistema.ahora", lambda: "2026-11-01T00:00:00-03:00")
    devolver(comercio)
    octubre = s.generar_reporte("ventas_ingresos", "2026-10-03", "2026-10-03")
    assert octubre["secciones"][0]["filas"][0]["neto_centavos"] == 50000
    noviembre = s.generar_reporte("ventas_ingresos", "2026-11-01", "2026-11-01")
    fila = noviembre["secciones"][0]["filas"][0]
    assert (fila["ventas"], fila["devoluciones"], fila["neto_centavos"]) == (0, 1, -25000)
    ranking = s.generar_reporte("ranking_margen", "2026-11-01", "2026-11-01")["secciones"][0]["filas"]
    assert sum(f["ingreso_neto_centavos"] for f in ranking) == -25000


def test_existencias_agregadas_incluyen_cero_y_valoran_bloqueados(comercio):
    s, cd, local, _, p, q, _, _ = comercio
    devolver(comercio)
    categoria = s.listar("productos")[0]["categoria_id"]
    z = s.guardar_producto("Z", "Sin stock", categoria, "10")
    s.configurar_minimo(local, z, 3)
    s.configurar_minimo(local, p, 9)
    reporte = s.generar_reporte("existencias_minimos", ubicacion_id=local)
    resumen = reporte["secciones"][0]["filas"][0]
    assert (resumen["productos"], resumen["bajo_minimo"], resumen["unidades_faltantes"]) == (3, 2, 5)
    filas = {f["producto_id"]: f for f in reporte["secciones"][1]["filas"]}
    assert filas[z]["disponible"] == 0 and filas[z]["faltante"] == 3
    assert filas[p]["valor_bloqueado_centavos"] == 6000
    assert filas[p]["valor_disponible_centavos"] == 42000
    # Z no tiene fila de existencia en CD y también debe aparecer.
    cd_filas = s.generar_reporte("existencias_minimos", ubicacion_id=cd)["secciones"][1]["filas"]
    assert next(f for f in cd_filas if f["producto_id"] == z)["disponible"] == 0


def test_rechazos_dos_productos_no_multiplican_tasa_y_transito(comercio, monkeypatch):
    s, cd, local, _, p, q, _, _ = comercio
    monkeypatch.setattr("backend.services.sistema.ahora", lambda: "2026-10-04T10:00:00-03:00")
    orden = s.crear_orden(cd, local, [(p, 3), (q, 2)])
    b = s.preparar_bulto(orden, "R2", [(p, 3), (q, 2)])
    s.precintar(b, "S2")
    s.despachar(b)
    monkeypatch.setattr("backend.services.sistema.ahora", lambda: "2026-10-05T10:00:00-03:00")
    s.recibir(b, local)
    s.verificar(b, local, "S2", roto=True, observacion="Roto")
    reporte = s.generar_reporte("rechazos_precinto")
    fila = reporte["secciones"][0]["filas"][0]
    assert (fila["evaluados"], fila["rechazados"], fila["tasa_porcentaje"]) == (2, 1, 50.0)
    assert (fila["unidades_rechazadas"], fila["valor_comprometido_centavos"], fila["horas_transito"]) == (5, 22000, 24.0)
    assert len(reporte["secciones"][1]["filas"]) == 2
    filtrado = s.generar_reporte("rechazos_precinto", "2026-10-05", "2026-10-05", local)
    assert filtrado["secciones"][0]["filas"][0]["tasa_porcentaje"] == 100.0


@pytest.mark.parametrize("tipo,desde,hasta,ubicacion,medio", [
    ("otro", None, None, None, None), ("ranking_margen", "2026-02-30", None, None, None),
    ("ranking_margen", "2026-11-01", "2026-10-01", None, None),
    ("existencias_minimos", "2026-10-01", None, None, None),
    ("ranking_margen", None, None, 999, None), ("ranking_margen", None, None, None, "DEBITO"),
])
def test_filtros_invalidos(comercio, tipo, desde, hasta, ubicacion, medio):
    with pytest.raises(ErrorDominio):
        comercio[0].generar_reporte(tipo, desde, hasta, ubicacion, medio)


def test_reportes_vacios_y_exportacion_csv(tmp_path):
    BaseDatos.reset_for_testing()
    try:
        s = Sistema(tmp_path / "vacia.db")
        for tipo in REPORTES:
            resultado = s.generar_reporte(tipo)
            assert all(not seccion["filas"] for seccion in resultado["secciones"])
            ruta = tmp_path / f"{tipo}.csv"
            exportar_csv(resultado, ruta)
            with ruta.open(encoding="utf-8-sig", newline="") as archivo:
                filas = list(csv.reader(archivo, delimiter=";"))
            assert filas[0] == [resultado["titulo"]]
            assert [resultado["secciones"][0]["nombre"]] in filas
    finally:
        BaseDatos.reset_for_testing()


def test_actualizacion_base_version_uno_preserva_ventas_y_costos(comercio):
    s, _, _, _, _, _, venta, _ = comercio
    comprobante, saldos = s.comprobante_venta(venta), s.listar("inventario")
    with s.db.transaccion() as cx:
        quitar_esquema_lotes(cx)
        cx.execute("DROP TABLE detalle_devolucion")
        cx.execute("DROP TABLE devolucion")
        cx.execute("PRAGMA user_version = 1")
    ruta = s.db.ruta
    BaseDatos.reset_for_testing()
    s = Sistema(ruta)
    assert s.listar("devoluciones") == []
    assert s.comprobante_venta(venta) == comprobante
    assert s.listar("inventario") == saldos
    with s.db.conectar() as cx:
        assert cx.execute("PRAGMA user_version").fetchone()[0] == 3
        assert cx.execute("PRAGMA foreign_key_check").fetchall() == []


def test_sqlite_impide_sobredevolucion_aunque_se_omita_servicio(comercio):
    s, _, local, _, p, _, venta, detalles = comercio
    devolver(comercio)
    with pytest.raises(sqlite3.IntegrityError, match="supera"):
        with s.db.transaccion() as cx:
            dev = cx.execute(
                """INSERT INTO devolucion(referencia, venta_id, local_id, motivo, medio_reintegro, fecha, total_centavos)
                   VALUES ('D2', ?, ?, 'Prueba', 'EFECTIVO', '2026-10-04', 30000)""", (venta, local),
            ).lastrowid
            cx.execute("INSERT INTO detalle_devolucion(devolucion_id, detalle_venta_id, cantidad, condicion) VALUES (?, ?, 3, 'VENDIBLE')", (dev, detalles[p]))
    assert len(s.listar("devoluciones")) == 1


def test_existencias_valoran_reservado_pendiente_y_dos_origenes_bloqueados(comercio):
    s, cd, local, _, p, q, _, _ = comercio
    devolver(comercio)
    enviar(s, cd, local, p, 1, "R2")  # Reserva a costo fijo.
    pendiente = enviar(s, cd, local, p, 2, "R3")
    s.despachar(pendiente)
    s.recibir(pendiente, local)
    rechazo = enviar(s, cd, local, p, 1, "R4")
    s.despachar(rechazo)
    s.recibir(rechazo, local)
    s.verificar(rechazo, local, "R4", roto=True, observacion="Roto")
    filas = {(f["ubicacion_id"], f["producto_id"]): f for f in s.generar_reporte("existencias_minimos")["secciones"][1]["filas"]}
    assert filas[cd, p]["valor_reservado_centavos"] == 6000
    assert filas[local, p]["valor_pendiente_centavos"] == 12000
    assert filas[local, p]["valor_bloqueado_centavos"] == 12000  # 1 retorno + 1 rechazo logístico.
    rechazo_filas = s.generar_reporte("rechazos_precinto")["secciones"][0]["filas"]
    assert rechazo_filas[0]["evaluados"] == 2  # No incluye los bultos reservado ni pendiente.


def test_filtro_local_y_totales_de_varios_locales(comercio):
    s, cd, local, _, p, _, _, _ = comercio
    local2 = s.guardar_ubicacion("L2", "Otro local", "Dirección", "LOCAL")
    b = enviar(s, cd, local2, p, 2, "R2")
    s.despachar(b)
    s.recibir(b, local2)
    s.verificar(b, local2, "R2")
    s.registrar_venta(local2, [(p, 1)], [("EFECTIVO", "100")])
    todas = s.generar_reporte("ventas_ingresos")["secciones"][0]["filas"]
    assert len(todas) == 2 and sum(f["ventas_centavos"] for f in todas) == 60000
    uno = s.generar_reporte("ranking_margen", ubicacion_id=local2)["secciones"][0]["filas"]
    assert len(uno) == 1 and uno[0]["ingreso_neto_centavos"] == 10000
    with pytest.raises(ErrorDominio, match="ubicación válida"):
        s.generar_reporte("ventas_ingresos", ubicacion_id=cd)


def test_csv_preserva_importes_y_exporta_codigos_como_texto(comercio, tmp_path):
    s, _, local, _, p, _, _, _ = comercio
    categoria = s.listar("productos")[0]["categoria_id"]
    s.guardar_producto("=1+1", "Producto", categoria, "100", p)
    resultado = s.generar_reporte("existencias_minimos", ubicacion_id=local)
    ruta = tmp_path / "reporte.csv"
    exportar_csv(resultado, ruta)
    contenido = ruta.read_text(encoding="utf-8-sig")
    assert "'=1+1" in contenido
    assert "360.00" in contenido  # Disponible P: 6 unidades a 60.
