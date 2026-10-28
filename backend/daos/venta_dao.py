"""Acceso a datos de ventas, detalles, cobros, comprobantes y movimientos de caja (Cap. 13.10)."""

from backend.models.entidades import Cobro, Comprobante, DetalleVenta, Venta
from backend.patterns.estados_bulto import ErrorDominio


class VentaDAO:
    """Encapsula las operaciones SQL sobre venta, detalle_venta, cobro, comprobante y movimiento_caja."""

    def __init__(self, conexion):
        self.cx = conexion

    def crear_venta(self, venta):
        return self.cx.execute(
            "INSERT INTO venta (local_id, fecha, total_centavos) VALUES (?, ?, ?)",
            (venta.local_id, venta.fecha, venta.total_centavos),
        ).lastrowid

    def guardar_detalle(self, venta_id, detalle):
        return self.cx.execute(
            """INSERT INTO detalle_venta
               (venta_id, producto_id, cantidad, precio_unitario_centavos, costo_unitario_centavos)
               VALUES (?, ?, ?, ?, ?)""",
            (
                venta_id,
                detalle.producto_id,
                detalle.cantidad,
                detalle.precio_unitario_centavos,
                detalle.costo_unitario_centavos,
            ),
        ).lastrowid

    def guardar_cobro(self, venta_id, cobro, fecha):
        return self.cx.execute(
            "INSERT INTO cobro (venta_id, medio_pago, importe_centavos, fecha) VALUES (?, ?, ?, ?)",
            (venta_id, cobro.medio_pago, cobro.importe_centavos, fecha),
        ).lastrowid

    def guardar_comprobante(self, comprobante):
        return self.cx.execute(
            "INSERT INTO comprobante (numero, venta_id, fecha, total_centavos) VALUES (?, ?, ?, ?)",
            (comprobante.numero, comprobante.venta_id, comprobante.fecha, comprobante.total_centavos),
        ).lastrowid

    def registrar_movimiento_caja(self, local_id, tipo, medio_pago, importe_centavos, causa, referencia_id, fecha):
        return self.cx.execute(
            """INSERT INTO movimiento_caja
               (local_id, tipo, medio_pago, importe_centavos, causa, referencia_id, fecha)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (local_id, tipo, medio_pago, importe_centavos, causa, referencia_id, fecha),
        ).lastrowid

    def obtener(self, identificador):
        fila = self.cx.execute("SELECT * FROM venta WHERE id = ?", (identificador,)).fetchone()
        if fila is None:
            raise ErrorDominio("Seleccione una venta registrada.")
        venta = Venta(fila["local_id"], fila["fecha"], fila["id"])
        detalles = self.cx.execute(
            "SELECT * FROM detalle_venta WHERE venta_id = ? ORDER BY id",
            (identificador,),
        ).fetchall()
        for det in detalles:
            venta._detalles.append(
                DetalleVenta(
                    det["producto_id"],
                    det["cantidad"],
                    det["precio_unitario_centavos"],
                    det["costo_unitario_centavos"],
                    det["id"],
                )
            )
        cobros = self.cx.execute(
            "SELECT * FROM cobro WHERE venta_id = ? ORDER BY id",
            (identificador,),
        ).fetchall()
        for cob in cobros:
            venta._cobros.append(Cobro(cob["medio_pago"], cob["importe_centavos"], cob["fecha"], cob["id"]))
        comp = self.cx.execute(
            "SELECT * FROM comprobante WHERE venta_id = ?",
            (identificador,),
        ).fetchone()
        if comp is not None:
            venta._comprobante = Comprobante(
                comp["numero"], comp["venta_id"], comp["total_centavos"], comp["fecha"], comp["id"]
            )
        return venta
