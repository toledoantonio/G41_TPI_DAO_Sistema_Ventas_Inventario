"""Persistencia de documentos de compra y reposición; no confirma transacciones."""

from backend.patterns.estados_bulto import ErrorDominio


class OperacionesDAO:
    def __init__(self, conexion):
        self.cx = conexion

    def crear_compra(self, referencia, proveedor_id, cd_id, fecha):
        return self.cx.execute("INSERT INTO compra (referencia, proveedor_id, cd_id, fecha) VALUES (?, ?, ?, ?)",
                               (referencia, proveedor_id, cd_id, fecha)).lastrowid

    def detalle_compra(self, compra_id, producto_id, cantidad, costo):
        self.cx.execute("INSERT INTO detalle_compra VALUES (?, ?, ?, ?)", (compra_id, producto_id, cantidad, costo))

    def crear_orden(self, cd_id, local_id, fecha):
        return self.cx.execute("INSERT INTO orden_reposicion (cd_id, local_id, fecha) VALUES (?, ?, ?)",
                               (cd_id, local_id, fecha)).lastrowid

    def detalle_reposicion(self, orden_id, producto_id, cantidad):
        self.cx.execute("INSERT INTO detalle_reposicion VALUES (?, ?, ?)", (orden_id, producto_id, cantidad))

    def obtener_orden(self, identificador):
        fila = self.cx.execute("SELECT * FROM orden_reposicion WHERE id = ?", (identificador,)).fetchone()
        if fila is None:
            raise ErrorDominio("Seleccione una orden registrada.")
        return fila

    def por_asignar(self, orden_id, producto_id):
        detalle = self.cx.execute("SELECT cantidad FROM detalle_reposicion WHERE orden_id = ? AND producto_id = ?",
                                  (orden_id, producto_id)).fetchone()
        if detalle is None:
            return 0
        asignado = self.cx.execute("""SELECT COALESCE(SUM(cb.cantidad), 0) FROM contenido_bulto cb
            JOIN bulto b ON b.id = cb.bulto_id JOIN remito r ON r.id = b.remito_id
            WHERE r.orden_id = ? AND cb.producto_id = ?""", (orden_id, producto_id)).fetchone()[0]
        return detalle["cantidad"] - asignado

    def crear_bulto_con_remito(self, orden_id, numero):
        remito_id = self.cx.execute("INSERT INTO remito (numero, orden_id) VALUES (?, ?)", (numero, orden_id)).lastrowid
        return self.cx.execute("INSERT INTO bulto (remito_id, estado) VALUES (?, 'Preparado')", (remito_id,)).lastrowid

    def contenido_bulto(self, bulto_id, producto_id, cantidad):
        self.cx.execute("INSERT INTO contenido_bulto VALUES (?, ?, ?)", (bulto_id, producto_id, cantidad))

    def cambiar_estado_remito(self, identificador, estado):
        self.cx.execute("UPDATE remito SET estado = ? WHERE id = ?", (estado, identificador))

    def estado_remito(self, identificador):
        return self.cx.execute("SELECT estado FROM remito WHERE id = ?", (identificador,)).fetchone()["estado"]
