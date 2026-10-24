"""Consultas de lectura con SQL centralizado fuera de los servicios."""
from backend.patterns.estados_bulto import ErrorDominio

CONSULTAS = {
    "ubicaciones": "SELECT * FROM ubicacion ORDER BY tipo, codigo",
    "categorias": "SELECT * FROM categoria ORDER BY nombre",
    "proveedores": "SELECT * FROM proveedor ORDER BY codigo",
    "productos": """SELECT p.*, c.nombre AS categoria FROM producto p
                     JOIN categoria c ON c.id = p.categoria_id ORDER BY p.codigo""",
    "compras": """SELECT c.id, c.referencia, c.fecha, p.nombre AS proveedor, u.nombre AS cd,
                  SUM(d.cantidad * d.costo_centavos) AS total_centavos
                  FROM compra c JOIN proveedor p ON p.id = c.proveedor_id
                  JOIN ubicacion u ON u.id = c.cd_id JOIN detalle_compra d ON d.compra_id = c.id
                  GROUP BY c.id ORDER BY c.id DESC""",
    "ordenes": """SELECT o.*, c.nombre AS cd, l.nombre AS local,
                  (SELECT SUM(cantidad) FROM detalle_reposicion WHERE orden_id = o.id) AS solicitada,
                  COALESCE((SELECT SUM(cb.cantidad) FROM contenido_bulto cb
                    JOIN bulto b ON b.id = cb.bulto_id JOIN remito r ON r.id = b.remito_id
                    WHERE r.orden_id = o.id), 0) AS asignada
                  FROM orden_reposicion o JOIN ubicacion c ON c.id = o.cd_id
                  JOIN ubicacion l ON l.id = o.local_id ORDER BY o.id DESC""",
    "bultos": """SELECT b.id, r.orden_id, r.numero AS remito, b.precinto, b.estado,
                 r.estado AS estado_remito, c.nombre AS origen, l.nombre AS destino
                 FROM bulto b JOIN remito r ON r.id = b.remito_id
                 JOIN orden_reposicion o ON o.id = r.orden_id
                 JOIN ubicacion c ON c.id = o.cd_id JOIN ubicacion l ON l.id = o.local_id
                 ORDER BY b.id DESC""",
    "inventario": """SELECT u.id AS ubicacion_id, p.id AS producto_id, u.nombre AS ubicacion,
                    u.tipo, p.codigo, p.descripcion,
                    COALESCE(e.disponible, 0) AS disponible, COALESCE(e.reservado, 0) AS reservado,
                    COALESCE(e.pendiente, 0) AS pendiente, COALESCE(e.rechazado, 0) AS rechazado,
                    COALESCE(e.minimo, 0) AS minimo,
                    MAX(0, COALESCE(e.minimo, 0) - COALESCE(e.disponible, 0)) AS faltante
                    FROM ubicacion u CROSS JOIN producto p LEFT JOIN existencia e
                    ON e.ubicacion_id = u.id AND e.producto_id = p.id ORDER BY u.codigo, p.codigo""",
}


class ConsultasDAO:
    def __init__(self, conexion):
        self.cx = conexion

    def listar(self, consulta):
        if consulta not in CONSULTAS:
            raise ErrorDominio("Consulta desconocida.")
        return [dict(fila) for fila in self.cx.execute(CONSULTAS[consulta])]

    def detalle_orden(self, identificador):
        return [dict(fila) for fila in self.cx.execute("""SELECT d.producto_id, p.codigo, p.descripcion,
            d.cantidad AS solicitada, d.cantidad - COALESCE((SELECT SUM(cb.cantidad)
            FROM contenido_bulto cb JOIN bulto b ON b.id = cb.bulto_id
            JOIN remito r ON r.id = b.remito_id
            WHERE r.orden_id = d.orden_id AND cb.producto_id = d.producto_id), 0) AS pendiente
            FROM detalle_reposicion d JOIN producto p ON p.id = d.producto_id WHERE d.orden_id = ?
            ORDER BY p.codigo""", (identificador,))]


    def historial_bulto(self, identificador):
        return [dict(fila) for fila in self.cx.execute("SELECT * FROM historial_bulto WHERE bulto_id = ? ORDER BY id",
                                                 (identificador,))]


    def contenido_bulto(self, identificador):
        return [dict(fila) for fila in self.cx.execute("""SELECT p.codigo, p.descripcion, c.cantidad
            FROM contenido_bulto c JOIN producto p ON p.id = c.producto_id WHERE c.bulto_id = ?
            ORDER BY p.codigo""", (identificador,))]

