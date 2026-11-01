"""Paso 2 → 3: saldos iniciales sin atribuir lotes desconocidos al pasado."""

from datetime import datetime


def migrar_lotes(cx):
    if cx.execute("PRAGMA user_version").fetchone()[0] >= 3:
        return
    if cx.execute("SELECT COUNT(*) FROM lote").fetchone()[0]:
        raise ValueError("La migración de lotes requiere una base anterior sin lotes registrados.")
    fecha = datetime.now().astimezone().isoformat(timespec="microseconds")
    for producto in cx.execute("SELECT id FROM producto").fetchall():
        producto_id = producto["id"]
        lote = cx.execute("INSERT INTO lote(producto_id, codigo, legado) VALUES (?, 'LEGADO-SIN-IDENTIFICAR', 1)", (producto_id,)).lastrowid
        for saldo in cx.execute("SELECT * FROM existencia WHERE producto_id = ?", (producto_id,)).fetchall():
            cantidades = tuple(saldo[c] for c in ("disponible", "reservado", "pendiente", "rechazado"))
            cx.execute("INSERT INTO existencia_lote VALUES (?, ?, ?, ?, ?, ?)", (saldo["ubicacion_id"], lote, *cantidades))
            if any(cantidades):
                cx.execute("""INSERT INTO movimiento_lote
                    (ubicacion_id, lote_id, disponible, reservado, pendiente, rechazado, causa, referencia_id, fecha)
                    VALUES (?, ?, ?, ?, ?, ?, 'MIGRACION', 0, ?)""", (saldo["ubicacion_id"], lote, *cantidades, fecha))
        cx.execute("INSERT INTO bulto_lote SELECT bulto_id, ?, cantidad FROM contenido_bulto WHERE producto_id = ?", (lote, producto_id))
        cx.execute("INSERT INTO venta_lote SELECT id, ?, cantidad FROM detalle_venta WHERE producto_id = ?", (lote, producto_id))
        cx.execute("""INSERT INTO devolucion_lote SELECT dd.id, ?, dd.cantidad FROM detalle_devolucion dd
                      JOIN detalle_venta dv ON dv.id = dd.detalle_venta_id WHERE dv.producto_id = ?""", (lote, producto_id))
    cx.execute("PRAGMA user_version = 3")
