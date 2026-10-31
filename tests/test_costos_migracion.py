"""Regresiones de reservas valorizadas, actualización de bases y configuración única."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
import sqlite3
from threading import Barrier
from tempfile import TemporaryDirectory

import pytest

from backend.database.config import BaseDatos
from backend.services.sistema import Sistema


@pytest.fixture
def tmp_path():
    carpeta = Path(__file__).resolve().parents[1] / "tmp"
    carpeta.mkdir(exist_ok=True)
    with TemporaryDirectory(dir=carpeta) as temporal:
        yield Path(temporal)


@pytest.fixture
def datos(tmp_path):
    BaseDatos.reset_for_testing()
    s = Sistema(tmp_path / "inventario.db")
    cd = s.guardar_ubicacion("CD", "Depósito", "Dirección", "CD")
    local = s.guardar_ubicacion("L", "Local", "Dirección", "LOCAL")
    categoria = s.guardar_categoria("Categoría")
    proveedor = s.guardar_proveedor("PR", "Proveedor")
    producto = s.guardar_producto("P", "Producto", categoria, "150")
    yield s, cd, local, proveedor, producto
    BaseDatos.reset_for_testing()


def saldo(s, ubicacion):
    return next(f for f in s.listar("inventario") if f["ubicacion_id"] == ubicacion)


def enviar(s, cd, local, producto, cantidad, numero):
    orden = s.crear_orden(cd, local, [(producto, cantidad)])
    bulto = s.preparar_bulto(orden, numero, [(producto, cantidad)])
    s.precintar(bulto, numero)
    return bulto


def convertir_a_base_anterior(s):
    """Simula el esquema previo a ventas/costos, manteniendo los documentos reales."""
    ruta = s.db.ruta
    BaseDatos.reset_for_testing()
    with closing(sqlite3.connect(ruta)) as cx, cx:
        cx.execute("ALTER TABLE existencia DROP COLUMN costo_centavos")
        cx.execute("ALTER TABLE contenido_bulto DROP COLUMN costo_centavos")
        for tabla in ("movimiento_caja", "comprobante", "cobro", "detalle_venta", "venta"):
            cx.execute(f"DROP TABLE {tabla}")
        cx.execute("PRAGMA user_version = 0")
    return ruta


def test_compra_con_todo_reservado_y_venta_conservan_valor(datos):
    s, cd, local, proveedor, producto = datos
    s.registrar_compra("C1", proveedor, cd, [(producto, 10, "60")])
    bulto = enviar(s, cd, local, producto, 10, "R1")
    s.registrar_compra("C2", proveedor, cd, [(producto, 10, "100")])
    assert saldo(s, cd)["costo_centavos"] == 10000
    # Antes de despachar: $1000 disponibles + $600 reservados = $1600 comprados.
    reservado = s.contenido_bulto(bulto)[0]
    assert saldo(s, cd)["valor_disponible_centavos"] + reservado["cantidad"] * reservado["costo_centavos"] == 160000
    s.despachar(bulto)
    s.recibir(bulto, local)
    s.verificar(bulto, local, "R1")
    venta = s.registrar_venta(local, [(producto, 4)], [("EFECTIVO", "600")])
    assert sum(f["valor_disponible_centavos"] for f in s.listar("inventario")) + s.obtener_venta(venta).costo_total_centavos == 160000


def test_migracion_reconstruye_compras_reservas_y_verificacion(datos):
    s, cd, local, proveedor, producto = datos
    s.registrar_compra("C1", proveedor, cd, [(producto, 20, "70")])
    bulto = enviar(s, cd, local, producto, 10, "R1")
    s.registrar_compra("C2", proveedor, cd, [(producto, 10, "100")])
    s.despachar(bulto)
    s.recibir(bulto, local)
    s.verificar(bulto, local, "R1")
    historial = s.historial_bulto(bulto)
    ruta = convertir_a_base_anterior(s)
    s = Sistema(ruta)
    assert saldo(s, cd)["costo_centavos"] == 8500
    assert saldo(s, local)["costo_centavos"] == 7000
    assert s.contenido_bulto(bulto)[0]["costo_centavos"] == 7000
    assert s.historial_bulto(bulto) == historial
    assert sum(f["valor_disponible_centavos"] for f in s.listar("inventario")) == 240000
    with s.db.conectar() as cx:
        assert cx.execute("PRAGMA user_version").fetchone()[0] == 2
    # La segunda apertura no vuelve a migrar ni modifica los costos históricos.
    BaseDatos.reset_for_testing()
    s = Sistema(ruta)
    assert saldo(s, cd)["costo_centavos"] == 8500
    venta = s.registrar_venta(local, [(producto, 1)], [("EFECTIVO", "150")])
    assert s.obtener_venta(venta).costo_total_centavos == 7000


@pytest.mark.parametrize("rechazar", [False, True])
def test_migracion_no_habilita_stock_pendiente_ni_rechazado(datos, rechazar):
    s, cd, local, proveedor, producto = datos
    s.registrar_compra("C1", proveedor, cd, [(producto, 10, "60")])
    bulto = enviar(s, cd, local, producto, 10, "R1")
    s.despachar(bulto)
    s.recibir(bulto, local)
    if rechazar:
        s.verificar(bulto, local, "R1", roto=True, observacion="Precinto roto")
    ruta = convertir_a_base_anterior(s)
    s = Sistema(ruta)
    assert saldo(s, local)["disponible"] == 0
    assert saldo(s, local)["rechazado" if rechazar else "pendiente"] == 10
    assert s.contenido_bulto(bulto)[0]["costo_centavos"] == 6000
    if not rechazar:
        s.verificar(bulto, local, "R1")
        assert saldo(s, local)["costo_centavos"] == 6000


def test_migracion_fallida_revierte_columnas_y_permite_reintento(datos):
    s, cd, local, proveedor, producto = datos
    s.registrar_compra("C1", proveedor, cd, [(producto, 10, "60")])
    ruta = convertir_a_base_anterior(s)
    with closing(sqlite3.connect(ruta)) as cx, cx:
        cx.execute("UPDATE existencia SET disponible = 11")
    with pytest.raises(ValueError, match="stock no coincide"):
        Sistema(ruta)
    with closing(sqlite3.connect(ruta)) as cx, cx:
        assert "costo_centavos" not in {f[1] for f in cx.execute("PRAGMA table_info(existencia)")}
        assert cx.execute("PRAGMA user_version").fetchone()[0] == 0
        assert cx.execute("SELECT name FROM sqlite_master WHERE name = 'venta'").fetchone() is None
        cx.execute("UPDATE existencia SET disponible = 10")
    s = Sistema(ruta)
    assert saldo(s, cd)["costo_centavos"] == 6000


def test_migracion_respeta_costos_historicos_de_ventas_existentes(datos):
    s, cd, local, proveedor, producto = datos
    s.registrar_compra("C1", proveedor, cd, [(producto, 10, "60")])
    bulto = enviar(s, cd, local, producto, 10, "R1")
    s.despachar(bulto)
    s.recibir(bulto, local)
    s.verificar(bulto, local, "R1")
    venta = s.registrar_venta(local, [(producto, 2)], [("EFECTIVO", "300")])
    comprobante = s.comprobante_venta(venta)
    with s.db.transaccion() as cx:
        cx.execute("PRAGMA user_version = 0")
    ruta = s.db.ruta
    BaseDatos.reset_for_testing()
    s = Sistema(ruta)
    assert s.comprobante_venta(venta) == comprobante
    assert saldo(s, local)["disponible"] == 8
    assert saldo(s, local)["costo_centavos"] == 6000


def test_migracion_conserva_bultos_ya_costeados_y_concilia_remanente(datos):
    s, cd, local, proveedor, producto = datos
    s.registrar_compra("C1", proveedor, cd, [(producto, 20, "70")])
    b1 = enviar(s, cd, local, producto, 10, "R1")
    s.registrar_compra("C2", proveedor, cd, [(producto, 10, "100")])
    s.despachar(b1)
    s.recibir(b1, local)
    s.verificar(b1, local, "R1")
    b2 = enviar(s, cd, local, producto, 10, "R2")
    s.despachar(b2)
    s.recibir(b2, local)
    s.verificar(b2, local, "R2")
    # Datos producidos por la versión anterior: promediaba también la reserva.
    with s.db.transaccion() as cx:
        cx.execute("UPDATE contenido_bulto SET costo_centavos = 8000 WHERE bulto_id = ?", (b2,))
        cx.execute("UPDATE existencia SET costo_centavos = 8000 WHERE ubicacion_id = ?", (cd,))
        cx.execute("UPDATE existencia SET costo_centavos = 7500 WHERE ubicacion_id = ?", (local,))
        cx.execute("PRAGMA user_version = 0")
    ruta = s.db.ruta
    BaseDatos.reset_for_testing()
    s = Sistema(ruta)
    assert s.contenido_bulto(b2)[0]["costo_centavos"] == 8000
    assert saldo(s, cd)["costo_centavos"] == 9000
    assert saldo(s, local)["costo_centavos"] == 7500
    assert sum(f["valor_disponible_centavos"] for f in s.listar("inventario")) == 240000


def test_migracion_no_inventa_ajuste_sin_stock_remanente(datos):
    s, cd, local, proveedor, producto = datos
    s.registrar_compra("C1", proveedor, cd, [(producto, 10, "60")])
    bulto = enviar(s, cd, local, producto, 10, "R1")
    with s.db.transaccion() as cx:
        cx.execute("UPDATE contenido_bulto SET costo_centavos = 5000 WHERE bulto_id = ?", (bulto,))
        cx.execute("PRAGMA user_version = 0")
    ruta = s.db.ruta
    BaseDatos.reset_for_testing()
    with pytest.raises(ValueError, match="sin stock remanente"):
        Sistema(ruta)
    with closing(sqlite3.connect(ruta)) as cx:
        assert cx.execute("PRAGMA user_version").fetchone()[0] == 0
        assert cx.execute("SELECT costo_centavos FROM contenido_bulto").fetchone()[0] == 5000


def test_singleton_rechaza_otra_ruta_sin_afectar_sistema(datos, tmp_path):
    s, cd, local, proveedor, producto = datos
    with pytest.raises(ValueError, match="otra ruta"):
        Sistema(tmp_path / "otra.db")
    assert not (tmp_path / "otra.db").exists()
    assert len(s.listar("ubicaciones")) == 2
    assert BaseDatos(s.db.ruta.relative_to(Path.cwd())) is s.db


def test_inicializaciones_concurrentes_comparten_gestor(tmp_path):
    BaseDatos.reset_for_testing()
    barrera = Barrier(4)
    ruta = tmp_path / "concurrente.db"

    def abrir(_):
        barrera.wait(timeout=5)
        db = BaseDatos(ruta)
        with db.conectar() as cx:
            assert cx.execute("PRAGMA user_version").fetchone()[0] == 2
        return db

    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            gestores = list(pool.map(abrir, range(4)))
        assert all(db is gestores[0] for db in gestores)
    finally:
        BaseDatos.reset_for_testing()
