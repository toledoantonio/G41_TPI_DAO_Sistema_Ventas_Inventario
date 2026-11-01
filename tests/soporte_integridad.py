"""Conciliación independiente para pruebas; no altera datos ni forma parte de la UI."""

from collections import Counter, defaultdict


CAMPOS = ("disponible", "reservado", "pendiente", "rechazado")


def estado_persistido(s):
    with s.db.conectar() as cx:
        cx.execute("BEGIN")
        tablas = [f[0] for f in cx.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        datos = []
        for nombre in tablas:
            citado = '"' + nombre.replace('"', '""') + '"'
            datos.append((nombre, tuple(tuple(f) for f in cx.execute(f"SELECT * FROM {citado} ORDER BY rowid"))))
        return cx.execute("PRAGMA user_version").fetchone()[0], tuple(datos)


def auditar_integridad(s, compras_anteriores=()):
    with s.db.conectar() as cx:
        cx.execute("BEGIN")
        assert [f[0] for f in cx.execute("PRAGMA integrity_check")] == ["ok"]
        assert cx.execute("PRAGMA foreign_key_check").fetchall() == []
        nombres = ["producto", "ubicacion", "compra", "detalle_compra", "compra_lote", "lote", "existencia",
                   "existencia_lote", "movimiento_inventario", "movimiento_lote", "bulto", "contenido_bulto",
                   "bulto_lote", "historial_bulto", "remito", "venta", "detalle_venta", "venta_lote", "cobro",
                   "comprobante", "devolucion", "detalle_devolucion", "devolucion_lote", "movimiento_caja",
                   "orden_compra_sugerida", "detalle_compra_sugerida"]
        t = {nombre: [dict(f) for f in cx.execute(f"SELECT * FROM {nombre} ORDER BY rowid")] for nombre in nombres}

    lotes = {f["id"]: f for f in t["lote"]}
    saldos = {(f["ubicacion_id"], f["producto_id"]): tuple(f[c] for c in CAMPOS) for f in t["existencia"]}
    saldos_lote = {(f["ubicacion_id"], f["lote_id"]): tuple(f[c] for c in CAMPOS) for f in t["existencia_lote"]}

    def agregar(filas, clave):
        suma = defaultdict(lambda: [0, 0, 0, 0])
        for f in filas:
            for i, c in enumerate(CAMPOS):
                suma[clave(f)][i] += f[c]
        return {k: tuple(v) for k, v in suma.items()}

    def iguales(a, b):
        for clave in a.keys() | b.keys():
            assert a.get(clave, (0, 0, 0, 0)) == b.get(clave, (0, 0, 0, 0)), (clave, a.get(clave), b.get(clave))

    iguales(saldos, agregar(t["existencia_lote"], lambda f: (f["ubicacion_id"], lotes[f["lote_id"]]["producto_id"])))
    iguales(saldos, agregar(t["movimiento_inventario"], lambda f: (f["ubicacion_id"], f["producto_id"])))
    iguales(saldos_lote, agregar(t["movimiento_lote"], lambda f: (f["ubicacion_id"], f["lote_id"])))
    assert all(v >= 0 for fila in saldos.values() for v in fila)
    assert all(v >= 0 for fila in saldos_lote.values() for v in fila)

    # Cantidades por documento, con producto obtenido desde el lote y no desde el saldo agregado.
    def cantidades(filas, clave, campo="cantidad"):
        total = Counter()
        for f in filas:
            total[clave(f)] += f[campo]
        return total

    compras = cantidades(t["detalle_compra"], lambda f: (f["compra_id"], f["producto_id"]))
    compras_trazadas = cantidades(t["compra_lote"], lambda f: (f["compra_id"], lotes[f["lote_id"]]["producto_id"]))
    for clave, cantidad in compras.items():
        if clave[0] not in compras_anteriores:
            assert compras_trazadas[clave] == cantidad
    assert not (compras_trazadas.keys() - compras.keys())
    assert cantidades(t["contenido_bulto"], lambda f: (f["bulto_id"], f["producto_id"])) == cantidades(
        t["bulto_lote"], lambda f: (f["bulto_id"], lotes[f["lote_id"]]["producto_id"]))
    detalle_venta = {f["id"]: f for f in t["detalle_venta"]}
    detalle_devolucion = {f["id"]: f for f in t["detalle_devolucion"]}
    assert cantidades(t["detalle_venta"], lambda f: f["id"]) == cantidades(t["venta_lote"], lambda f: f["detalle_venta_id"])
    assert cantidades(t["detalle_devolucion"], lambda f: f["id"]) == cantidades(t["devolucion_lote"], lambda f: f["detalle_devolucion_id"])
    for f in t["venta_lote"]:
        assert lotes[f["lote_id"]]["producto_id"] == detalle_venta[f["detalle_venta_id"]]["producto_id"]
    por_lote = cantidades(t["venta_lote"], lambda f: (f["detalle_venta_id"], f["lote_id"]))
    retorno_lote = cantidades(t["devolucion_lote"], lambda f: (detalle_devolucion[f["detalle_devolucion_id"]]["detalle_venta_id"], f["lote_id"]))
    assert all(c <= por_lote[k] for k, c in retorno_lote.items())
    retorno_detalle = cantidades(t["detalle_devolucion"], lambda f: f["detalle_venta_id"])
    assert all(c <= detalle_venta[k]["cantidad"] for k, c in retorno_detalle.items())

    # Conservación física: incluir tránsito y devoluciones de ambas condiciones.
    fisico = cantidades(t["existencia"], lambda f: f["producto_id"], "disponible")
    for f in t["existencia"]:
        fisico[f["producto_id"]] += sum(f[c] for c in CAMPOS[1:])
    bultos = {f["id"]: f for f in t["bulto"]}
    for f in t["contenido_bulto"]:
        if bultos[f["bulto_id"]]["estado"] == "En tránsito":
            fisico[f["producto_id"]] += f["cantidad"]
    compras_producto = cantidades(t["detalle_compra"], lambda f: f["producto_id"])
    vendido_producto = cantidades(t["detalle_venta"], lambda f: f["producto_id"])
    devuelto_producto = cantidades(t["detalle_devolucion"], lambda f: detalle_venta[f["detalle_venta_id"]]["producto_id"])
    for p in {f["id"] for f in t["producto"]}:
        assert fisico[p] == compras_producto[p] - vendido_producto[p] + devuelto_producto[p]

    remitos = {f["id"]: f for f in t["remito"]}
    secuencia = ["Preparado", "Precintado", "En tránsito", "Recibido"]
    for b in t["bulto"]:
        historia = [h for h in t["historial_bulto"] if h["bulto_id"] == b["id"]]
        assert historia and historia[-1]["nuevo"] == b["estado"]
        esperada = secuencia[:secuencia.index(b["estado"]) + 1] if b["estado"] in secuencia else secuencia + [b["estado"]]
        assert [h["nuevo"] for h in historia] == esperada
        assert [h["anterior"] for h in historia] == [None] + esperada[:-1]
        assert remitos[b["remito_id"]]["estado"] == (b["estado"] if b["estado"] in ("Verificado", "Rechazado") else "Pendiente")

    ventas = {f["id"]: f for f in t["venta"]}
    devoluciones = {f["id"]: f for f in t["devolucion"]}
    for v in t["venta"]:
        detalles = [f for f in t["detalle_venta"] if f["venta_id"] == v["id"]]
        assert detalles and v["total_centavos"] == sum(f["cantidad"] * f["precio_unitario_centavos"] for f in detalles)
        assert v["total_centavos"] == sum(f["importe_centavos"] for f in t["cobro"] if f["venta_id"] == v["id"])
        comprobantes = [f for f in t["comprobante"] if f["venta_id"] == v["id"]]
        assert len(comprobantes) == 1 and comprobantes[0]["total_centavos"] == v["total_centavos"]
    for d in t["devolucion"]:
        detalles = [f for f in t["detalle_devolucion"] if f["devolucion_id"] == d["id"]]
        assert detalles and d["local_id"] == ventas[d["venta_id"]]["local_id"]
        assert all(detalle_venta[f["detalle_venta_id"]]["venta_id"] == d["venta_id"] for f in detalles)
        assert d["total_centavos"] == sum(f["cantidad"] * detalle_venta[f["detalle_venta_id"]]["precio_unitario_centavos"] for f in detalles)
        egresos = [f for f in t["movimiento_caja"] if f["causa"] == "DEVOLUCION" and f["referencia_id"] == d["id"]]
        assert len(egresos) == (1 if d["total_centavos"] else 0)
        if egresos:
            assert (egresos[0]["tipo"], egresos[0]["local_id"], egresos[0]["importe_centavos"], egresos[0]["medio_pago"]) == (
                "EGRESO", d["local_id"], d["total_centavos"], d["medio_reintegro"])
    for c in t["cobro"]:
        movimientos = [f for f in t["movimiento_caja"] if f["causa"] == "VENTA" and f["referencia_id"] == c["id"]]
        assert len(movimientos) == 1
        m = movimientos[0]
        assert (m["tipo"], m["local_id"], m["importe_centavos"], m["medio_pago"]) == (
            "INGRESO", ventas[c["venta_id"]]["local_id"], c["importe_centavos"], c["medio_pago"])
    assert len(t["movimiento_caja"]) == len(t["cobro"]) + sum(d["total_centavos"] > 0 for d in t["devolucion"])

    for o in t["orden_compra_sugerida"]:
        esperados = {f["producto_id"]: f["cantidad"] for f in t["detalle_compra_sugerida"] if f["orden_id"] == o["id"]}
        assert esperados
        if o["estado"] == "RECIBIDA":
            c = next(f for f in t["compra"] if f["id"] == o["compra_id"])
            assert (c["proveedor_id"], c["cd_id"]) == (o["proveedor_id"], o["cd_id"])
            assert esperados == {f["producto_id"]: f["cantidad"] for f in t["detalle_compra"] if f["compra_id"] == c["id"]}
        else:
            assert o["compra_id"] is None

    bruto = sum(v["total_centavos"] for v in t["venta"])
    reintegro = sum(d["total_centavos"] for d in t["devolucion"])
    comercial, caja = s.generar_reporte("ventas_ingresos")["secciones"]
    assert sum(f["ventas_centavos"] for f in comercial["filas"]) == bruto
    assert sum(f["reintegros_centavos"] for f in comercial["filas"]) == reintegro
    assert sum(f["ventas"] for f in comercial["filas"]) == len(t["venta"])
    assert sum(f["neto_centavos"] for f in caja["filas"]) == bruto - reintegro
    ranking = s.generar_reporte("ranking_margen")["secciones"][0]["filas"]
    assert sum(f["ingreso_neto_centavos"] for f in ranking) == bruto - reintegro
    costo = sum(f["cantidad"] * f["costo_unitario_centavos"] for f in t["detalle_venta"])
    costo -= sum(f["cantidad"] * detalle_venta[f["detalle_venta_id"]]["costo_unitario_centavos"]
                 for f in t["detalle_devolucion"] if f["condicion"] == "VENDIBLE")
    assert sum(f["margen_centavos"] for f in ranking) == bruto - reintegro - costo
    reporte = s.generar_reporte("existencias_minimos")["secciones"][1]["filas"]
    for fila in reporte:
        assert tuple(fila[c] for c in CAMPOS) == saldos.get((fila["ubicacion_id"], fila["producto_id"]), (0, 0, 0, 0))
        assert 0 <= fila["vendible"] <= fila["disponible"]
        assert fila["vencido"] == fila["disponible"] - fila["vendible"]
    rechazo = s.generar_reporte("rechazos_precinto")["secciones"][0]["filas"]
    assert sum(f["evaluados"] for f in rechazo) == sum(b["estado"] in ("Verificado", "Rechazado") for b in t["bulto"])
    assert sum(f["rechazados"] for f in rechazo) == sum(b["estado"] == "Rechazado" for b in t["bulto"])
    return {"compras": len(t["compra"]), "bultos": len(bultos), "ventas": len(ventas),
            "devoluciones": len(devoluciones), "lotes": len(lotes), "sugerencias": len(t["orden_compra_sugerida"])}
