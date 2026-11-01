"""Saldos y asignaciones por lote, dentro de la transacción de la operación."""

from backend.models.lotes import Lote
from backend.patterns.estados_bulto import ErrorDominio


class LoteDAO:
    def __init__(self, conexion):
        self.cx = conexion

    def registrar(self, producto_id, identificacion, vencimiento, hoy):
        lote = Lote(producto_id, identificacion, vencimiento)
        if lote.codigo == "LEGADO-SIN-IDENTIFICAR":
            raise ErrorDominio("El código LEGADO-SIN-IDENTIFICAR está reservado para la migración de stock anterior.")
        if lote.esta_vencido(hoy):
            raise ErrorDominio("No se puede recibir una compra con lote ya vencido.")
        fila = self.cx.execute("SELECT * FROM lote WHERE producto_id = ? AND codigo = ?", (lote.producto_id, lote.codigo)).fetchone()
        if fila:
            if fila["legado"] or fila["vencimiento"] != lote.vencimiento:
                raise ErrorDominio("El lote ya registrado tiene otro vencimiento o es un saldo legado.")
            return fila["id"]
        return self.cx.execute("INSERT INTO lote(producto_id, codigo, vencimiento) VALUES (?, ?, ?)",
                               (lote.producto_id, lote.codigo, lote.vencimiento)).lastrowid

    def mover(self, ubicacion, lote, causa, referencia, fecha, disponible=0, reservado=0, pendiente=0, rechazado=0):
        self.cx.execute("INSERT OR IGNORE INTO existencia_lote(ubicacion_id, lote_id) VALUES (?, ?)", (ubicacion, lote))
        saldo = self.cx.execute("SELECT * FROM existencia_lote WHERE ubicacion_id = ? AND lote_id = ?", (ubicacion, lote)).fetchone()
        deltas = (disponible, reservado, pendiente, rechazado)
        if any(saldo[campo] + delta < 0 for campo, delta in zip(("disponible", "reservado", "pendiente", "rechazado"), deltas)):
            raise ErrorDominio("El lote no tiene cantidad suficiente para esta operación.")
        self.cx.execute("""UPDATE existencia_lote SET disponible = disponible + ?, reservado = reservado + ?,
                        pendiente = pendiente + ?, rechazado = rechazado + ? WHERE ubicacion_id = ? AND lote_id = ?""",
                        (*deltas, ubicacion, lote))
        self.cx.execute("""INSERT INTO movimiento_lote
            (ubicacion_id, lote_id, disponible, reservado, pendiente, rechazado, causa, referencia_id, fecha)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""", (ubicacion, lote, *deltas, causa, referencia, fecha))

    def vendible(self, ubicacion, producto, hoy):
        return self.cx.execute("""SELECT COALESCE(SUM(e.disponible), 0) FROM existencia_lote e
            JOIN lote l ON l.id = e.lote_id WHERE e.ubicacion_id = ? AND l.producto_id = ?
            AND (l.vencimiento IS NULL OR l.vencimiento >= ?)""", (ubicacion, producto, hoy)).fetchone()[0]

    def seleccionar(self, ubicacion, producto, cantidad, hoy):
        filas = self.cx.execute("""SELECT l.id AS lote_id, e.disponible FROM existencia_lote e
            JOIN lote l ON l.id = e.lote_id WHERE e.ubicacion_id = ? AND l.producto_id = ?
            AND e.disponible > 0 AND (l.vencimiento IS NULL OR l.vencimiento >= ?)
            ORDER BY l.vencimiento IS NULL, l.vencimiento, l.id""", (ubicacion, producto, hoy)).fetchall()
        seleccion, pendiente = [], cantidad
        for fila in filas:
            tomar = min(pendiente, fila["disponible"])
            if tomar:
                seleccion.append((fila["lote_id"], tomar))
                pendiente -= tomar
        if pendiente:
            raise ErrorDominio("Existencia disponible insuficiente en lotes no vencidos.")
        return seleccion

    def comprar(self, compra_id, ubicacion, renglones, fecha):
        cantidades = {}
        for producto, cantidad, identificacion, vencimiento in renglones:
            lote = self.registrar(producto, identificacion or f"COMPRA-{compra_id}", vencimiento, fecha[:10])
            cantidades[lote] = cantidades.get(lote, 0) + cantidad
        for lote, cantidad in cantidades.items():
            self.cx.execute("INSERT INTO compra_lote VALUES (?, ?, ?)", (compra_id, lote, cantidad))
            self.mover(ubicacion, lote, "COMPRA", compra_id, fecha, disponible=cantidad)

    def preparar(self, bulto, ubicacion, producto, cantidad, fecha):
        for lote, unidades in self.seleccionar(ubicacion, producto, cantidad, fecha[:10]):
            self.cx.execute("INSERT INTO bulto_lote VALUES (?, ?, ?)", (bulto, lote, unidades))
            self.mover(ubicacion, lote, "PREPARACION", bulto, fecha, disponible=-unidades, reservado=unidades)

    def bulto(self, identificador):
        return [dict(f) for f in self.cx.execute("""SELECT bl.*, l.producto_id, l.codigo, l.vencimiento, l.legado
            FROM bulto_lote bl JOIN lote l ON l.id = bl.lote_id WHERE bl.bulto_id = ? ORDER BY l.id""", (identificador,))]

    def operar_bulto(self, bulto, accion, cd, local, fecha, habilitar=False):
        items = self.bulto(bulto)
        if accion == "despachar" or (accion == "verificar" and habilitar):
            if any(i["vencimiento"] and i["vencimiento"] < fecha[:10] for i in items):
                raise ErrorDominio("El bulto contiene lotes vencidos; no se puede despachar ni habilitar su stock.")
        for item in items:
            lote, cantidad = item["lote_id"], item["cantidad"]
            if accion == "despachar":
                self.mover(cd, lote, "DESPACHO", bulto, fecha, reservado=-cantidad)
            elif accion == "recibir":
                self.mover(local, lote, "RECEPCION", bulto, fecha, pendiente=cantidad)
            elif accion == "verificar":
                self.mover(local, lote, "VERIFICACION", bulto, fecha, pendiente=-cantidad,
                           disponible=cantidad if habilitar else 0, rechazado=0 if habilitar else cantidad)

    def vender(self, detalle_id, ubicacion, producto, cantidad, venta_id, fecha):
        for lote, unidades in self.seleccionar(ubicacion, producto, cantidad, fecha[:10]):
            self.cx.execute("INSERT INTO venta_lote VALUES (?, ?, ?)", (detalle_id, lote, unidades))
            self.mover(ubicacion, lote, "VENTA", venta_id, fecha, disponible=-unidades)

    def devolvibles(self, detalle_id):
        return [dict(f) for f in self.cx.execute("""SELECT vl.lote_id, l.codigo, l.vencimiento, l.legado,
            vl.cantidad AS vendida, vl.cantidad - COALESCE((SELECT SUM(dl.cantidad)
                FROM devolucion_lote dl JOIN detalle_devolucion dd ON dd.id = dl.detalle_devolucion_id
                WHERE dd.detalle_venta_id = vl.detalle_venta_id AND dl.lote_id = vl.lote_id), 0) AS restante
            FROM venta_lote vl JOIN lote l ON l.id = vl.lote_id WHERE vl.detalle_venta_id = ? ORDER BY l.id""", (detalle_id,))]

    def plan_devolucion(self, renglones, hoy):
        """Exige lote explícito cuando la venta tuvo más de un lote devolvible."""
        usados, resultado = {}, {}
        for detalle, cantidad, condicion, lote_id in renglones:
            disponibles = {f["lote_id"]: f for f in self.devolvibles(detalle) if f["restante"] > 0}
            if lote_id is None:
                if len(disponibles) != 1:
                    raise ErrorDominio("Indique el lote devuelto; el detalle tiene varios lotes o ya fue devuelto.")
                lote_id = next(iter(disponibles))
            lote = disponibles.get(lote_id)
            clave = (detalle, lote_id)
            usados[clave] = usados.get(clave, 0) + cantidad
            if lote is None or usados[clave] > lote["restante"]:
                raise ErrorDominio("El lote no pertenece a la venta o supera sus unidades devolvibles.")
            if condicion == "VENDIBLE" and lote["vencimiento"] and lote["vencimiento"] < hoy:
                raise ErrorDominio("Un lote vencido debe devolverse como NO_VENDIBLE.")
            grupo = resultado.setdefault((detalle, condicion), {})
            grupo[lote_id] = grupo.get(lote_id, 0) + cantidad
        return resultado

    def devolver(self, devolucion, ubicacion, detalles, fecha):
        cantidades = {}
        for detalle_id, condicion, lotes in detalles:
            for lote, cantidad in lotes.items():
                self.cx.execute("INSERT INTO devolucion_lote VALUES (?, ?, ?)", (detalle_id, lote, cantidad))
                saldo = cantidades.setdefault(lote, {"disponible": 0, "rechazado": 0})
                saldo["disponible" if condicion == "VENDIBLE" else "rechazado"] += cantidad
        for lote, saldo in cantidades.items():
            self.mover(ubicacion, lote, "DEVOLUCION", devolucion, fecha, **saldo)

    def listar(self, hoy, ubicacion=None):
        return [dict(f) for f in self.cx.execute("""SELECT l.id AS lote_id, l.producto_id, p.codigo AS producto,
            p.descripcion, l.codigo, l.vencimiento, l.legado, u.id AS ubicacion_id, u.nombre AS ubicacion,
            e.disponible, e.reservado, e.pendiente, e.rechazado,
            CASE WHEN l.vencimiento IS NOT NULL AND l.vencimiento < :hoy THEN e.disponible ELSE 0 END AS vencido,
            CASE WHEN l.vencimiento IS NULL OR l.vencimiento >= :hoy THEN e.disponible ELSE 0 END AS vendible,
            CASE WHEN l.vencimiento IS NOT NULL AND l.vencimiento < :hoy THEN 'Vencido'
                 WHEN l.legado = 1 THEN 'Origen sin identificar' ELSE 'Vigente / sin vencimiento' END AS condicion
            FROM existencia_lote e JOIN lote l ON l.id = e.lote_id JOIN producto p ON p.id = l.producto_id
            JOIN ubicacion u ON u.id = e.ubicacion_id WHERE (:ubicacion IS NULL OR u.id = :ubicacion)
            ORDER BY u.id, p.codigo, l.vencimiento IS NULL, l.vencimiento, l.id""", {"hoy": hoy, "ubicacion": ubicacion})]

    def traza(self, lote):
        if self.cx.execute("SELECT id FROM lote WHERE id = ?", (lote,)).fetchone() is None:
            raise ErrorDominio("Seleccione un lote registrado.")
        return [dict(f) for f in self.cx.execute("""SELECT m.*, u.nombre AS ubicacion FROM movimiento_lote m
            JOIN ubicacion u ON u.id = m.ubicacion_id WHERE lote_id = ? ORDER BY m.id""", (lote,))]
