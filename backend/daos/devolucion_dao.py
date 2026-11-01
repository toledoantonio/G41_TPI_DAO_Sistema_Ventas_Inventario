"""Documentos de devolución, consulta de originales y cantidades acumuladas."""

from backend.patterns.estados_bulto import ErrorDominio


class DevolucionDAO:
    def __init__(self, conexion):
        self.cx = conexion

    def originales(self, venta_id):
        return [dict(f) for f in self.cx.execute(
            """SELECT dv.*, p.codigo, p.descripcion,
               COALESCE((SELECT SUM(dd.cantidad) FROM detalle_devolucion dd
                         WHERE dd.detalle_venta_id = dv.id), 0) AS devuelta
               FROM detalle_venta dv JOIN producto p ON p.id = dv.producto_id
               WHERE dv.venta_id = ? ORDER BY dv.id""", (venta_id,)
        )]

    def crear(self, devolucion):
        return self.cx.execute(
            """INSERT INTO devolucion
               (referencia, venta_id, local_id, motivo, medio_reintegro, fecha, total_centavos)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (devolucion.referencia, devolucion.venta_id, devolucion.local_id, devolucion.motivo,
             devolucion.medio_reintegro, devolucion.fecha, devolucion.total_centavos),
        ).lastrowid

    def guardar_detalle(self, devolucion_id, detalle):
        return self.cx.execute(
            """INSERT INTO detalle_devolucion (devolucion_id, detalle_venta_id, cantidad, condicion)
               VALUES (?, ?, ?, ?)""",
            (devolucion_id, detalle.detalle_venta_id, detalle.cantidad, detalle.condicion),
        ).lastrowid

    def obtener(self, identificador):
        fila = self.cx.execute("SELECT * FROM devolucion WHERE id = ?", (identificador,)).fetchone()
        if fila is None:
            raise ErrorDominio("Seleccione una devolución registrada.")
        resultado = dict(fila)
        resultado["detalles"] = [dict(f) for f in self.cx.execute(
            """SELECT dd.*, dv.producto_id, p.codigo, p.descripcion,
               dv.precio_unitario_centavos, dv.costo_unitario_centavos,
               dd.cantidad * dv.precio_unitario_centavos AS reintegro_centavos
               FROM detalle_devolucion dd JOIN detalle_venta dv ON dv.id = dd.detalle_venta_id
               JOIN producto p ON p.id = dv.producto_id WHERE dd.devolucion_id = ? ORDER BY dd.id""",
            (identificador,),
        )]
        return resultado
