"""Secuencias reproducibles y fallos tardíos antes de integrar los opcionales."""

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
import json
import os
import random
import sqlite3
import subprocess
import sys
from threading import Barrier

import pytest

import backend.database.config as configuracion
from backend.database.config import BaseDatos
from backend.daos.lote_dao import LoteDAO
from backend.daos.venta_dao import VentaDAO
from backend.daos.compra_sugerida_dao import CompraSugeridaDAO
from backend.models.entidades import importe
from backend.patterns.estados_bulto import ErrorDominio
from backend.services.sistema import Sistema
from tests.soporte_integridad import auditar_integridad, estado_persistido
from tests.test_costos_migracion import datos, tmp_path, quitar_esquema_lotes
from tests.test_opcionales import dia, preparar


@pytest.mark.parametrize("semilla", [41, 2026, 314159])
def test_secuencia_completa_con_conciliacion_tras_cada_paso(datos, monkeypatch, semilla):
    s, cd, local, proveedor, p = datos
    azar = random.Random(semilla)
    fecha = date(2030, 1, 1)
    dia(monkeypatch, fecha.isoformat())
    categoria = s.listar("productos")[0]["categoria_id"]
    s.guardar_producto("P", "Producto", categoria, "10", p)
    productos = [p, s.guardar_producto("Q", "Segundo", categoria, "20"), s.guardar_producto("R", "Tercero", categoria, "30")]
    precios = dict(zip(productos, (1000, 2000, 3000)))
    costos = dict(zip(productos, ("0.37", "5.00", "9.00")))
    locales = [local, s.guardar_ubicacion("L2", "Segundo local", "Dirección", "LOCAL")]
    cantidades = Counter()
    for producto in productos:
        s.configurar_minimo(cd, producto, 24)
        for loc in locales:
            s.configurar_minimo(loc, producto, 8)
    renglones = []
    for producto in productos:
        renglones.extend([(producto, 5, costos[producto], f"A-{producto}", "2030-01-05"),
                          (producto, 15, costos[producto], f"B-{producto}", "2030-01-20"),
                          (producto, 10, costos[producto])])
    s.registrar_compra("C-INICIAL", proveedor, cd, renglones)
    for loc in locales:
        orden = s.crear_orden(cd, loc, [(p, 8) for p in productos])
        b = s.preparar_bulto(orden, f"R-INICIAL-{loc}", [(p, 8) for p in productos])
        s.precintar(b, f"S-INICIAL-{loc}")
        s.despachar(b)
        s.recibir(b, loc)
        s.verificar(b, loc, f"S-INICIAL-{loc}")
        total = sum(2 * precios[p] for p in productos)
        s.registrar_venta(loc, [(p, 2) for p in productos], [("EFECTIVO", importe(total // 2)), ("DEBITO", importe(total - total // 2))])
    inicial = s.generar_orden_compra(cd, proveedor, "OC-INICIAL")
    orden = s.obtener_orden_compra(inicial)
    s.registrar_compra("C-SUGERIDA-INICIAL", proveedor, cd,
                       [(d["producto_id"], d["cantidad"], costos[d["producto_id"]]) for d in orden["detalles"]], orden_sugerida_id=inicial)
    auditar_integridad(s)

    for paso in range(72):
        fecha = date(2030, 1, 1) + timedelta(days=paso // 6)
        dia(monkeypatch, fecha.isoformat())
        accion = azar.choice(("compra", "bulto", "logistica", "logistica", "venta", "venta", "devolucion", "sugerencia", "invalida"))
        etiqueta = f"{semilla}-{paso}"
        if accion == "compra":
            producto = azar.choice(productos)
            s.registrar_compra("C-" + etiqueta, proveedor, cd, [(producto, azar.randint(1, 7), costos[producto], "L-" + etiqueta, (fecha + timedelta(days=7)).isoformat())])
            cantidades[accion] += 1
        elif accion == "bulto":
            opciones = [f for f in s.listar("inventario") if f["ubicacion_id"] == cd and f["vendible"] > 0]
            if opciones:
                f, loc = azar.choice(opciones), azar.choice(locales)
                preparar(s, cd, loc, f["producto_id"], azar.randint(1, min(5, f["vendible"])), "R-" + etiqueta)
                cantidades[accion] += 1
        elif accion == "logistica":
            opciones = [b for b in s.listar("bultos") if b["estado"] in ("Precintado", "En tránsito", "Recibido")]
            if opciones:
                b = azar.choice(opciones)
                destino = next(o["local_id"] for o in s.listar("ordenes") if o["id"] == b["orden_id"])
                antes = estado_persistido(s)
                try:
                    if b["estado"] == "Precintado": s.despachar(b["id"])
                    elif b["estado"] == "En tránsito": s.recibir(b["id"], destino)
                    else: s.verificar(b["id"], destino, b["precinto"], roto=azar.random() < 0.3, observacion="Inspección de prueba")
                    cantidades[accion] += 1
                except ErrorDominio:
                    assert estado_persistido(s) == antes
                    cantidades["rechazos_sin_efectos"] += 1
        elif accion == "venta":
            loc = azar.choice(locales)
            opciones = [f for f in s.listar("inventario") if f["ubicacion_id"] == loc and f["vendible"] > 0]
            if opciones:
                azar.shuffle(opciones)
                detalle = [(f["producto_id"], azar.randint(1, min(3, f["vendible"]))) for f in opciones[:2]]
                total = sum(precios[p] * c for p, c in detalle)
                s.registrar_venta(loc, detalle, [("EFECTIVO", importe(total // 2)), ("TRANSFERENCIA", importe(total - total // 2))])
                cantidades[accion] += 1
        elif accion == "devolucion":
            opciones = []
            for venta in s.listar("ventas"):
                for detalle in s.detalles_devolvibles(venta["id"]):
                    for lote in s.lotes_devolvibles(detalle["id"]):
                        if lote["restante"] > 0:
                            opciones.append((venta, detalle, lote))
            if opciones:
                venta, detalle, lote = azar.choice(opciones)
                condicion = "NO_VENDIBLE" if (lote["vencimiento"] and lote["vencimiento"] < fecha.isoformat()) or azar.random() < 0.3 else "VENDIBLE"
                s.registrar_devolucion(venta["id"], venta["local_id"], [(detalle["id"], 1, condicion, lote["lote_id"])],
                                       "EFECTIVO", "Inspección de prueba", "D-" + etiqueta)
                cantidades[accion] += 1
        elif accion == "sugerencia":
            abiertas = [o for o in s.listar("compras_sugeridas") if o["estado"] == "SUGERIDA"]
            if abiertas:
                orden = s.obtener_orden_compra(azar.choice(abiertas)["id"])
                if azar.random() < 0.5:
                    s.cancelar_orden_compra(orden["id"])
                    cantidades["cancelacion"] += 1
                else:
                    s.registrar_compra("C-" + etiqueta, proveedor, cd, [(d["producto_id"], d["cantidad"], costos[d["producto_id"]]) for d in orden["detalles"]], orden_sugerida_id=orden["id"])
                    cantidades["recepcion_sugerida"] += 1
            elif any(f["cantidad_sugerida"] > 0 for f in s.sugerencias_compra(cd)):
                s.generar_orden_compra(cd, proveedor, "OC-" + etiqueta)
                cantidades["generacion_sugerida"] += 1
        elif accion == "invalida":
            antes = estado_persistido(s)
            with pytest.raises(ErrorDominio):
                s.registrar_compra("C-INVALIDA-" + etiqueta, proveedor, cd, [(azar.choice(productos), 3, "5", "VENCIDO-" + etiqueta, "2029-12-31")])
            assert estado_persistido(s) == antes
            cantidades["rechazos_sin_efectos"] += 1
        auditar_integridad(s)
        if paso in (23, 47):
            ruta = s.db.ruta
            BaseDatos.reset_for_testing()
            s = Sistema(ruta)
            auditar_integridad(s)
    resultado = auditar_integridad(s)
    assert cantidades["compra"] > 0 and cantidades["venta"] > 0 and cantidades["devolucion"] > 0
    print(f"Semilla {semilla}: 72 pasos, {dict(cantidades)}, documentos finales {resultado}")


def test_migracion_falla_despues_de_crear_lotes_y_revierte_esquema(datos, monkeypatch):
    s, cd, local, proveedor, p = datos
    s.registrar_compra("C1", proveedor, cd, [(p, 10, "60")])
    b = preparar(s, cd, local, p, 5)
    s.despachar(b)
    s.recibir(b, local)
    with s.db.transaccion() as cx:
        quitar_esquema_lotes(cx)
        cx.execute("PRAGMA user_version = 2")
    ruta, antes = s.db.ruta, estado_persistido(s)
    migracion_original = configuracion.migrar_lotes

    def migracion_fallida(cx):
        migracion_original(cx)
        raise RuntimeError("Fallo posterior a la reconstrucción de lotes")

    monkeypatch.setattr(configuracion, "migrar_lotes", migracion_fallida)
    BaseDatos.reset_for_testing()
    with pytest.raises(RuntimeError, match="posterior"):
        Sistema(ruta)
    assert estado_persistido(s) == antes
    monkeypatch.setattr(configuracion, "migrar_lotes", migracion_original)
    s = Sistema(ruta)
    auditar_integridad(s, compras_anteriores={1})


def test_fallo_tardio_de_traza_revierte_venta_stock_cobros_y_comprobante(datos, monkeypatch):
    s, cd, local, proveedor, p = datos
    s.registrar_compra("C1", proveedor, cd, [(p, 10, "60")])
    b = preparar(s, cd, local, p, 10)
    s.despachar(b)
    s.recibir(b, local)
    s.verificar(b, local, "R1")
    original = LoteDAO.vender

    def vender_y_fallar(*args, **kwargs):
        original(*args, **kwargs)
        raise sqlite3.OperationalError("Fallo después de descontar lote")

    antes = estado_persistido(s)
    monkeypatch.setattr(LoteDAO, "vender", vender_y_fallar)
    with pytest.raises(sqlite3.OperationalError):
        s.registrar_venta(local, [(p, 3)], [("EFECTIVO", "450")])
    assert estado_persistido(s) == antes
    auditar_integridad(s)


def test_dos_recepciones_de_una_sugerencia_generan_una_sola_compra(datos):
    s, cd, local, proveedor, p = datos
    s.configurar_minimo(local, p, 10)
    orden = s.generar_orden_compra(cd, proveedor, "OC1")
    barrera = Barrier(2)

    def recibir(numero):
        barrera.wait(timeout=5)
        try:
            s.registrar_compra(f"C{numero}", proveedor, cd, [(p, 10, "60")], orden_sugerida_id=orden)
            return True
        except ErrorDominio:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(recibir, (1, 2))) == [False, True]
    assert len(s.listar("compras")) == 1
    auditar_integridad(s)


def test_dos_procesos_independientes_no_venden_el_mismo_stock(datos):
    s, cd, local, proveedor, p = datos
    s.registrar_compra("C1", proveedor, cd, [(p, 10, "60")])
    b = preparar(s, cd, local, p, 10)
    s.despachar(b)
    s.recibir(b, local)
    s.verificar(b, local, "R1")
    procesos = []
    try:
        for _ in range(2):
            procesos.append(subprocess.Popen(
                [sys.executable, "-m", "tests.worker_concurrencia", str(s.db.ruta), str(local), str(p)],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
            ))
        for proceso in procesos:
            assert proceso.stdout.readline().strip() == "LISTO"
        for proceso in procesos:
            proceso.stdin.write("VENDER\n")
            proceso.stdin.flush()
        resultados = []
        for proceso in procesos:
            salida, errores = proceso.communicate(timeout=20)
            assert proceso.returncode == 0, errores
            resultados.append(json.loads(salida)["confirmada"])
        assert sorted(resultados) == [False, True]
    finally:
        for proceso in procesos:
            if proceso.poll() is None:
                proceso.kill()
            proceso.communicate()
    assert s.listar("ventas")[0]["unidades"] == 6
    assert len(s.listar("ventas")) == 1
    auditar_integridad(s)


def test_devoluciones_simultaneas_respetan_el_lote_ademas_del_total(datos, monkeypatch):
    s, cd, local, proveedor, p = datos
    dia(monkeypatch, "2030-01-01")
    s.registrar_compra("C1", proveedor, cd, [(p, 2, "60", "A", "2030-01-20"), (p, 4, "60", "B", "2030-01-21")])
    b = preparar(s, cd, local, p, 6)
    s.despachar(b)
    s.recibir(b, local)
    s.verificar(b, local, "R1")
    venta = s.registrar_venta(local, [(p, 4)], [("EFECTIVO", "600")])
    detalle = s.detalle_venta(venta)[0]["id"]
    lote = next(l["lote_id"] for l in s.lotes_devolvibles(detalle) if l["codigo"] == "A")
    barrera = Barrier(2)

    def retornar(numero):
        barrera.wait(timeout=5)
        try:
            s.registrar_devolucion(venta, local, [(detalle, 2, "VENDIBLE", lote)], "EFECTIVO", "Inspección", f"D{numero}")
            return True
        except ErrorDominio:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(retornar, (1, 2))) == [False, True]
    assert len(s.listar("devoluciones")) == 1
    assert s.detalles_devolvibles(venta)[0]["devuelta"] == 2
    auditar_integridad(s)


def test_migracion_poblada_con_todos_los_estados_ventas_y_devoluciones(datos):
    s, cd, local, proveedor, p = datos
    compra = s.registrar_compra("C1", proveedor, cd, [(p, 50, "60")])
    bultos = []
    for etapa in range(6):
        orden = s.crear_orden(cd, local, [(p, 5)])
        b = s.preparar_bulto(orden, f"R{etapa}", [(p, 5)])
        bultos.append(b)
        if etapa >= 1: s.precintar(b, f"S{etapa}")
        if etapa >= 2: s.despachar(b)
        if etapa >= 3: s.recibir(b, local)
        if etapa >= 4: s.verificar(b, local, f"S{etapa}", roto=etapa == 5, observacion="Inspección")
    venta = s.registrar_venta(local, [(p, 3)], [("EFECTIVO", "200"), ("DEBITO", "250")])
    detalle = s.detalle_venta(venta)[0]["id"]
    s.registrar_devolucion(venta, local, [(detalle, 1, "VENDIBLE"), (detalle, 1, "NO_VENDIBLE")], "EFECTIVO", "Inspección", "D1")
    auditar_integridad(s)
    with s.db.transaccion() as cx:
        quitar_esquema_lotes(cx)
        cx.execute("PRAGMA user_version = 2")
    anteriores = dict(estado_persistido(s)[1])
    ruta = s.db.ruta
    BaseDatos.reset_for_testing()
    s = Sistema(ruta)
    posteriores = dict(estado_persistido(s)[1])
    for nombre, filas in anteriores.items():
        assert posteriores[nombre] == filas, nombre
    auditar_integridad(s, compras_anteriores={compra})

    assert all(l["legado"] == 1 for l in s.listar("lotes"))
    for etapa, b in enumerate(bultos[:4]):
        if etapa == 0: s.precintar(b, "S0")
        if etapa < 2: s.despachar(b)
        if etapa < 3: s.recibir(b, local)
        s.verificar(b, local, f"S{etapa}")
        auditar_integridad(s, compras_anteriores={compra})
    s.registrar_devolucion(venta, local, [(detalle, 1, "VENDIBLE")], "EFECTIVO", "Último retorno", "D2")
    auditar_integridad(s, compras_anteriores={compra})


def test_fallo_despues_del_egreso_revierte_devolucion_completa(datos, monkeypatch):
    s, cd, local, proveedor, p = datos
    s.registrar_compra("C1", proveedor, cd, [(p, 10, "60")])
    b = preparar(s, cd, local, p, 10)
    s.despachar(b)
    s.recibir(b, local)
    s.verificar(b, local, "R1")
    venta = s.registrar_venta(local, [(p, 4)], [("EFECTIVO", "600")])
    detalle = s.detalle_venta(venta)[0]["id"]
    original = VentaDAO.registrar_movimiento_caja

    def registrar_y_fallar(*args, **kwargs):
        original(*args, **kwargs)
        raise sqlite3.OperationalError("Fallo después del egreso")

    monkeypatch.setattr(VentaDAO, "registrar_movimiento_caja", registrar_y_fallar)
    antes = estado_persistido(s)
    with pytest.raises(sqlite3.OperationalError):
        s.registrar_devolucion(venta, local, [(detalle, 1, "VENDIBLE")], "EFECTIVO", "Inspección", "D1")
    assert estado_persistido(s) == antes
    auditar_integridad(s)


def test_fallo_despues_de_cerrar_sugerencia_revierte_compra_completa(datos, monkeypatch):
    s, cd, local, proveedor, p = datos
    s.configurar_minimo(local, p, 10)
    orden = s.generar_orden_compra(cd, proveedor, "OC1")
    original = CompraSugeridaDAO.recibir

    def recibir_y_fallar(*args, **kwargs):
        original(*args, **kwargs)
        raise sqlite3.OperationalError("Fallo después de cerrar sugerencia")

    monkeypatch.setattr(CompraSugeridaDAO, "recibir", recibir_y_fallar)
    antes = estado_persistido(s)
    with pytest.raises(sqlite3.OperationalError):
        s.registrar_compra("C1", proveedor, cd, [(p, 10, "60")], orden_sugerida_id=orden)
    assert estado_persistido(s) == antes
    auditar_integridad(s)


def test_codigo_legado_no_se_puede_usar_en_compra_nueva(datos):
    s, cd, _, proveedor, p = datos
    antes = estado_persistido(s)
    with pytest.raises(ErrorDominio, match="reservado para la migración"):
        s.registrar_compra("C1", proveedor, cd, [(p, 10, "60", " legado-sin-identificar ", None)])
    assert estado_persistido(s) == antes
    auditar_integridad(s)
