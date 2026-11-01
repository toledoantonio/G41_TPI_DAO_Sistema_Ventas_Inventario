"""Órdenes sugeridas; no crean stock hasta recibir una compra real."""

from backend.models.compras_sugeridas import NecesidadCompra
from backend.patterns.estados_bulto import ErrorDominio


class CompraSugeridaDAO:
    def __init__(self, conexion):
        self.cx = conexion

    def necesidades(self, cd, hoy):
        filas = self.cx.execute("""WITH util AS (
            SELECT e.ubicacion_id, l.producto_id, SUM(e.disponible) AS cantidad
            FROM existencia_lote e JOIN lote l ON l.id = e.lote_id
            WHERE l.vencimiento IS NULL OR l.vencimiento >= :hoy GROUP BY e.ubicacion_id, l.producto_id
        ), en_camino AS (
            SELECT o.local_id, l.producto_id, SUM(bl.cantidad) AS cantidad
            FROM bulto_lote bl JOIN lote l ON l.id = bl.lote_id JOIN bulto b ON b.id = bl.bulto_id
            JOIN remito r ON r.id = b.remito_id JOIN orden_reposicion o ON o.id = r.orden_id
            WHERE o.cd_id = :cd AND b.estado IN ('Preparado', 'Precintado', 'En tránsito', 'Recibido')
            AND (l.vencimiento IS NULL OR l.vencimiento >= :hoy) GROUP BY o.local_id, l.producto_id
        ), pedidos AS (
            SELECT o.local_id, d.producto_id, SUM(d.cantidad - COALESCE((
                SELECT SUM(cb.cantidad) FROM contenido_bulto cb JOIN bulto b ON b.id = cb.bulto_id
                JOIN remito r ON r.id = b.remito_id WHERE r.orden_id = o.id AND cb.producto_id = d.producto_id
            ), 0)) AS cantidad FROM detalle_reposicion d JOIN orden_reposicion o ON o.id = d.orden_id
            WHERE o.cd_id = :cd GROUP BY o.local_id, d.producto_id
        ), locales AS (
            SELECT p.id AS producto_id, SUM(MAX(
                MAX(0, COALESCE(e.minimo, 0) - COALESCE(u.cantidad, 0) - COALESCE(c.cantidad, 0)),
                COALESCE(pe.cantidad, 0))) AS necesidad
            FROM producto p CROSS JOIN ubicacion loc
            LEFT JOIN existencia e ON e.ubicacion_id = loc.id AND e.producto_id = p.id
            LEFT JOIN util u ON u.ubicacion_id = loc.id AND u.producto_id = p.id
            LEFT JOIN en_camino c ON c.local_id = loc.id AND c.producto_id = p.id
            LEFT JOIN pedidos pe ON pe.local_id = loc.id AND pe.producto_id = p.id
            WHERE loc.tipo = 'LOCAL' GROUP BY p.id
        ), compras AS (
            SELECT d.producto_id, SUM(d.cantidad) AS cantidad FROM detalle_compra_sugerida d
            JOIN orden_compra_sugerida o ON o.id = d.orden_id
            WHERE o.cd_id = :cd AND o.estado = 'SUGERIDA' GROUP BY d.producto_id
        ) SELECT p.id AS producto_id, p.codigo, p.descripcion,
            COALESCE(e.minimo, 0) AS minimo_cd, COALESCE(u.cantidad, 0) AS disponible_cd,
            COALESCE(l.necesidad, 0) AS necesidad_locales, COALESCE(c.cantidad, 0) AS compras_pendientes
            FROM producto p LEFT JOIN existencia e ON e.producto_id = p.id AND e.ubicacion_id = :cd
            LEFT JOIN util u ON u.producto_id = p.id AND u.ubicacion_id = :cd
            LEFT JOIN locales l ON l.producto_id = p.id LEFT JOIN compras c ON c.producto_id = p.id
            ORDER BY p.codigo""", {"cd": cd, "hoy": hoy}).fetchall()
        resultado = []
        for fila in filas:
            dato = dict(fila)
            necesidad = NecesidadCompra(dato["minimo_cd"], dato["disponible_cd"], dato["necesidad_locales"], dato["compras_pendientes"])
            dato["cantidad_sugerida"] = necesidad.cantidad_sugerida
            resultado.append(dato)
        return resultado

    def crear(self, referencia, cd, proveedor, fecha, detalles):
        orden = self.cx.execute("""INSERT INTO orden_compra_sugerida(referencia, cd_id, proveedor_id, fecha)
            VALUES (?, ?, ?, ?)""", (referencia, cd, proveedor, fecha)).lastrowid
        self.cx.executemany("INSERT INTO detalle_compra_sugerida VALUES (?, ?, ?)", [(orden, p, c) for p, c in detalles.items()])
        return orden

    def obtener(self, identificador):
        fila = self.cx.execute("SELECT * FROM orden_compra_sugerida WHERE id = ?", (identificador,)).fetchone()
        if fila is None:
            raise ErrorDominio("Seleccione una orden de compra sugerida registrada.")
        dato = dict(fila)
        dato["detalles"] = [dict(f) for f in self.cx.execute("""SELECT d.*, p.codigo, p.descripcion
            FROM detalle_compra_sugerida d JOIN producto p ON p.id = d.producto_id WHERE orden_id = ?
            ORDER BY p.codigo""", (identificador,))]
        return dato

    def validar_recepcion(self, orden_id, compra):
        orden = self.obtener(orden_id)
        if orden["estado"] != "SUGERIDA":
            raise ErrorDominio("La orden ya fue recibida o cancelada.")
        if orden["cd_id"] != compra.cd_id or orden["proveedor_id"] != compra.proveedor_id:
            raise ErrorDominio("La compra debe coincidir con el CD y proveedor de la orden sugerida.")
        esperados = {d["producto_id"]: d["cantidad"] for d in orden["detalles"]}
        recibidos = {d.producto_id: d.cantidad for d in compra.detalles}
        if recibidos != esperados:
            raise ErrorDominio("La recepción debe incluir exactamente los productos y cantidades de la orden sugerida.")

    def recibir(self, orden_id, compra_id):
        self.cx.execute("UPDATE orden_compra_sugerida SET estado = 'RECIBIDA', compra_id = ? WHERE id = ?", (compra_id, orden_id))

    def cancelar(self, orden_id):
        if self.obtener(orden_id)["estado"] != "SUGERIDA":
            raise ErrorDominio("Solo se puede cancelar una sugerencia pendiente.")
        self.cx.execute("UPDATE orden_compra_sugerida SET estado = 'CANCELADA' WHERE id = ?", (orden_id,))

    def listar(self):
        return [dict(f) for f in self.cx.execute("""SELECT o.*, p.nombre AS proveedor, u.nombre AS cd,
            (SELECT SUM(cantidad) FROM detalle_compra_sugerida WHERE orden_id = o.id) AS unidades
            FROM orden_compra_sugerida o JOIN proveedor p ON p.id = o.proveedor_id
            JOIN ubicacion u ON u.id = o.cd_id ORDER BY o.id DESC""")]
