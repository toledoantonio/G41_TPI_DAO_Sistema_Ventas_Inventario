"""Migración económica versionada, ejecutada dentro de la transacción de apertura."""

from decimal import Decimal, ROUND_HALF_UP

from backend.models.entidades import calcular_costo_promedio


def _redondear(valor, cantidad):
    return int((Decimal(valor) / Decimal(cantidad)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def migrar_costos(cx):
    """Reconstruye costos desde el libro de movimientos, sin alterar cantidades ni ventas.

    Las bases previas no tenían versión. Los movimientos tienen un id global que
    conserva el orden real de escritura, incluso si las fechas fueron iguales.
    El costo del disponible excluye reservas, pendientes y rechazados, cuyos
    costos se conservan en el contenido de cada bulto.
    """
    version = cx.execute("PRAGMA user_version").fetchone()[0]
    if version > 1:
        raise ValueError("La base pertenece a una versión más reciente de la aplicación.")
    if version == 1:
        return

    faltantes = set()
    for tabla in ("existencia", "contenido_bulto"):
        columnas = {fila["name"] for fila in cx.execute(f"PRAGMA table_info({tabla})")}
        if "costo_centavos" not in columnas:
            faltantes.add(tabla)
            cx.execute(
                f"ALTER TABLE {tabla} ADD COLUMN costo_centavos INTEGER NOT NULL DEFAULT 0 CHECK (costo_centavos >= 0)"
            )

    compras = {
        (f["compra_id"], f["producto_id"]): f
        for f in cx.execute("SELECT d.*, c.cd_id FROM detalle_compra d JOIN compra c ON c.id = d.compra_id")
    }
    contenidos = {
        (f["bulto_id"], f["producto_id"]): dict(f)
        for f in cx.execute(
            """SELECT cb.*, o.cd_id, o.local_id FROM contenido_bulto cb
               JOIN bulto b ON b.id = cb.bulto_id JOIN remito r ON r.id = b.remito_id
               JOIN orden_reposicion o ON o.id = r.orden_id"""
        )
    }
    ventas = {
        (f["venta_id"], f["producto_id"]): f
        for f in cx.execute("SELECT d.*, v.local_id FROM detalle_venta d JOIN venta v ON v.id = d.venta_id")
    }
    saldos = {}
    preparados = set()
    campos = ("disponible", "reservado", "pendiente", "rechazado")
    for mov in cx.execute("SELECT * FROM movimiento_inventario ORDER BY id"):
        clave = (mov["ubicacion_id"], mov["producto_id"])
        saldo = saldos.setdefault(clave, dict.fromkeys((*campos, "costo_centavos"), 0))
        documento = (mov["referencia_id"], mov["producto_id"])
        causa = mov["causa"]
        deltas = tuple(mov[campo] for campo in campos)
        entrada = None
        salida = None
        if causa == "COMPRA":
            compra = compras.get(documento)
            if compra is None or compra["cd_id"] != clave[0] or deltas != (compra["cantidad"], 0, 0, 0):
                raise ValueError("No se puede reconstruir el costo: compra sin respaldo consistente.")
            entrada = compra["costo_centavos"]
        elif causa in ("PREPARACION", "DESPACHO", "RECEPCION", "VERIFICACION"):
            contenido = contenidos.get(documento)
            if contenido is None:
                raise ValueError("No se puede reconstruir el costo: falta el contenido del bulto.")
            cantidad = contenido["cantidad"]
            esperados = {
                "PREPARACION": {(-cantidad, cantidad, 0, 0)},
                "DESPACHO": {(0, -cantidad, 0, 0)},
                "RECEPCION": {(0, 0, cantidad, 0)},
                "VERIFICACION": {(cantidad, 0, -cantidad, 0), (0, 0, -cantidad, cantidad)},
            }
            origen = "cd_id" if causa in ("PREPARACION", "DESPACHO") else "local_id"
            if clave[0] != contenido[origen] or deltas not in esperados[causa]:
                raise ValueError("No se puede reconstruir el costo: movimiento incompatible con el bulto.")
            if causa == "PREPARACION":
                if "contenido_bulto" in faltantes:
                    contenido["costo_centavos"] = saldo["costo_centavos"]
                preparados.add(documento)
                salida = contenido["costo_centavos"]
            elif documento not in preparados:
                raise ValueError("No se puede reconstruir el costo: bulto sin preparación registrada.")
            elif causa == "VERIFICACION" and mov["disponible"] > 0:
                entrada = contenido["costo_centavos"]
        elif causa == "VENTA":
            venta = ventas.get(documento)
            if venta is None or venta["local_id"] != clave[0] or deltas != (-venta["cantidad"], 0, 0, 0):
                raise ValueError("No se puede reconstruir el costo: venta sin respaldo consistente.")
            salida = venta["costo_unitario_centavos"]
        else:
            raise ValueError(f"No se puede reconstruir el costo: movimiento desconocido {causa}.")

        cantidad_anterior = saldo["disponible"]
        for campo in campos:
            saldo[campo] += mov[campo]
            if saldo[campo] < 0:
                raise ValueError("No se puede reconstruir el costo: movimientos con saldo negativo.")
        if entrada is not None:
            saldo["costo_centavos"] = calcular_costo_promedio(
                cantidad_anterior, saldo["costo_centavos"], mov["disponible"], entrada
            )
        elif salida is not None:
            # En bases que ya registraban costos se respetan los históricos.
            # Una diferencia con el promedio reconstruido queda en el remanente.
            valor_restante = cantidad_anterior * saldo["costo_centavos"] + mov["disponible"] * salida
            if saldo["disponible"] > 0:
                if valor_restante < 0:
                    raise ValueError("Los costos históricos requieren conciliación: valor restante negativo.")
                saldo["costo_centavos"] = _redondear(valor_restante, saldo["disponible"])
            elif abs(valor_restante) > cantidad_anterior:
                raise ValueError("Los costos históricos requieren conciliación: diferencia sin stock remanente.")

    for fila in cx.execute("SELECT * FROM existencia"):
        clave = (fila["ubicacion_id"], fila["producto_id"])
        saldo = saldos.pop(clave, dict.fromkeys((*campos, "costo_centavos"), 0))
        if any(fila[campo] != saldo[campo] for campo in campos):
            raise ValueError("No se puede reconstruir el costo: el stock no coincide con sus movimientos.")
        cx.execute(
            "UPDATE existencia SET costo_centavos = ? WHERE ubicacion_id = ? AND producto_id = ?",
            (saldo["costo_centavos"], *clave),
        )
    if saldos:
        raise ValueError("No se puede reconstruir el costo: faltan saldos de inventario.")
    if "contenido_bulto" in faltantes:
        if preparados != set(contenidos):
            raise ValueError("No se puede reconstruir el costo: falta la preparación de un bulto.")
        cx.executemany(
            "UPDATE contenido_bulto SET costo_centavos = ? WHERE bulto_id = ? AND producto_id = ?",
            [(c["costo_centavos"], *clave) for clave, c in contenidos.items()],
        )
    cx.execute("PRAGMA user_version = 1")
