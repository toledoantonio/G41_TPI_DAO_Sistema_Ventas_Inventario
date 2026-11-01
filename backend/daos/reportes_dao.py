"""Consultas agregadas de reportes. Todas las secciones comparten la conexión de lectura."""

PERIODO = """(:desde IS NULL OR substr(fecha, 1, 10) >= :desde)
             AND (:hasta IS NULL OR substr(fecha, 1, 10) <= :hasta)
             AND (:ubicacion IS NULL OR local_id = :ubicacion)"""


class ReportesDAO:
    def __init__(self, conexion):
        self.cx = conexion

    def consultar(self, tipo, parametros):
        consultas = {
            "ventas_ingresos": self._ventas_ingresos,
            "ranking_margen": self._ranking_margen,
            "existencias_minimos": self._existencias_minimos,
            "rechazos_precinto": self._rechazos_precinto,
        }
        return consultas[tipo](parametros)

    def _seccion(self, nombre, columnas, sql, parametros):
        return {"nombre": nombre, "columnas": columnas,
                "filas": [dict(f) for f in self.cx.execute(sql, parametros)]}

    def _ventas_ingresos(self, p):
        comercial = self._seccion("Operaciones comerciales por local", [
            ("local", "Local"), ("ventas", "Ventas"), ("devoluciones", "Devoluciones"),
            ("ventas_centavos", "Venta bruta"), ("reintegros_centavos", "Reintegros"),
            ("neto_centavos", "Venta neta"),
        ], f"""WITH eventos AS (
            SELECT local_id, fecha, 1 AS ventas, 0 AS devoluciones, total_centavos AS bruto, 0 AS reintegro FROM venta
            UNION ALL
            SELECT local_id, fecha, 0, 1, 0, total_centavos FROM devolucion
        ) SELECT local_id, u.nombre AS local, SUM(ventas) AS ventas, SUM(devoluciones) AS devoluciones,
          SUM(bruto) AS ventas_centavos, SUM(reintegro) AS reintegros_centavos,
          SUM(bruto - reintegro) AS neto_centavos
          FROM eventos JOIN ubicacion u ON u.id = local_id WHERE {PERIODO}
          GROUP BY local_id ORDER BY local_id""", p)
        caja = self._seccion("Caja por local y medio", [
            ("local", "Local"), ("medio_pago", "Medio"), ("movimientos", "Movimientos"),
            ("ingresos_centavos", "Ingresos"), ("egresos_centavos", "Egresos"), ("neto_centavos", "Neto caja"),
        ], f"""SELECT local_id, u.nombre AS local, medio_pago, COUNT(*) AS movimientos,
            SUM(CASE WHEN mc.tipo = 'INGRESO' THEN importe_centavos ELSE 0 END) AS ingresos_centavos,
            SUM(CASE WHEN mc.tipo = 'EGRESO' THEN importe_centavos ELSE 0 END) AS egresos_centavos,
            SUM(CASE WHEN mc.tipo = 'INGRESO' THEN importe_centavos ELSE -importe_centavos END) AS neto_centavos
            FROM movimiento_caja mc JOIN ubicacion u ON u.id = local_id
            WHERE {PERIODO} AND (:medio IS NULL OR medio_pago = :medio)
            GROUP BY local_id, medio_pago ORDER BY local_id, medio_pago""", p)
        return [comercial, caja]

    def _ranking_margen(self, p):
        return [self._seccion("Ranking por unidades netas y margen histórico", [
            ("local", "Local"), ("codigo", "Producto"), ("descripcion", "Descripción"),
            ("vendidas", "U. vendidas"), ("devueltas", "U. devueltas"), ("netas", "U. netas"),
            ("ingreso_neto_centavos", "Ingreso neto"), ("costo_neto_centavos", "Costo neto"),
            ("costo_bloqueado_centavos", "Costo no recuperado"), ("margen_centavos", "Margen estimado"),
        ], f"""WITH eventos AS (
            SELECT v.local_id, v.fecha, dv.producto_id, dv.cantidad AS vendidas, 0 AS devueltas,
              dv.cantidad * dv.precio_unitario_centavos AS ingreso,
              dv.cantidad * dv.costo_unitario_centavos AS costo, 0 AS bloqueado
              FROM detalle_venta dv JOIN venta v ON v.id = dv.venta_id
            UNION ALL
            SELECT d.local_id, d.fecha, dv.producto_id, 0, dd.cantidad,
              -dd.cantidad * dv.precio_unitario_centavos,
              CASE WHEN dd.condicion = 'VENDIBLE' THEN -dd.cantidad * dv.costo_unitario_centavos ELSE 0 END,
              CASE WHEN dd.condicion = 'NO_VENDIBLE' THEN dd.cantidad * dv.costo_unitario_centavos ELSE 0 END
              FROM detalle_devolucion dd JOIN devolucion d ON d.id = dd.devolucion_id
              JOIN detalle_venta dv ON dv.id = dd.detalle_venta_id
        ) SELECT local_id, u.nombre AS local, producto_id, pr.codigo, pr.descripcion,
            SUM(vendidas) AS vendidas, SUM(devueltas) AS devueltas, SUM(vendidas - devueltas) AS netas,
            SUM(ingreso) AS ingreso_neto_centavos, SUM(costo) AS costo_neto_centavos,
            SUM(bloqueado) AS costo_bloqueado_centavos, SUM(ingreso - costo) AS margen_centavos
            FROM eventos JOIN ubicacion u ON u.id = local_id JOIN producto pr ON pr.id = producto_id
            WHERE {PERIODO} GROUP BY local_id, producto_id
            ORDER BY netas DESC, margen_centavos DESC, pr.codigo, local_id""", p)]

    def _existencias_minimos(self, p):
        # Agregar cada origen antes del JOIN evita multiplicar contenido por devoluciones.
        cte = """WITH logistica AS (
            SELECT o.cd_id AS ubicacion_id, cb.producto_id,
              SUM(cb.cantidad * cb.costo_centavos) AS reserva, 0 AS pendiente, 0 AS rechazo
              FROM contenido_bulto cb JOIN bulto b ON b.id = cb.bulto_id
              JOIN remito r ON r.id = b.remito_id JOIN orden_reposicion o ON o.id = r.orden_id
              WHERE b.estado IN ('Preparado', 'Precintado') GROUP BY o.cd_id, cb.producto_id
            UNION ALL
            SELECT o.local_id, cb.producto_id, 0,
              SUM(CASE WHEN b.estado = 'Recibido' THEN cb.cantidad * cb.costo_centavos ELSE 0 END),
              SUM(CASE WHEN b.estado = 'Rechazado' THEN cb.cantidad * cb.costo_centavos ELSE 0 END)
              FROM contenido_bulto cb JOIN bulto b ON b.id = cb.bulto_id
              JOIN remito r ON r.id = b.remito_id JOIN orden_reposicion o ON o.id = r.orden_id
              WHERE b.estado IN ('Recibido', 'Rechazado') GROUP BY o.local_id, cb.producto_id
            UNION ALL
            SELECT d.local_id, dv.producto_id, 0, 0, SUM(dd.cantidad * dv.costo_unitario_centavos)
              FROM detalle_devolucion dd JOIN devolucion d ON d.id = dd.devolucion_id
              JOIN detalle_venta dv ON dv.id = dd.detalle_venta_id
              WHERE dd.condicion = 'NO_VENDIBLE' GROUP BY d.local_id, dv.producto_id
        ), valores AS (
            SELECT ubicacion_id, producto_id, SUM(reserva) AS reserva, SUM(pendiente) AS pendiente,
              SUM(rechazo) AS rechazo FROM logistica GROUP BY ubicacion_id, producto_id
        ), util AS (
            SELECT e.ubicacion_id, l.producto_id, SUM(e.disponible) AS vendible
            FROM existencia_lote e JOIN lote l ON l.id = e.lote_id
            WHERE l.vencimiento IS NULL OR l.vencimiento >= :hoy GROUP BY e.ubicacion_id, l.producto_id
        ), detalle AS (
            SELECT u.id AS ubicacion_id, u.nombre AS ubicacion, pr.id AS producto_id, pr.codigo, pr.descripcion,
              COALESCE(e.disponible, 0) AS disponible, COALESCE(e.reservado, 0) AS reservado,
              COALESCE(e.pendiente, 0) AS pendiente, COALESCE(e.rechazado, 0) AS rechazado,
              COALESCE(e.minimo, 0) AS minimo,
              COALESCE(ut.vendible, 0) AS vendible,
              COALESCE(e.disponible, 0) - COALESCE(ut.vendible, 0) AS vencido,
              MAX(0, COALESCE(e.minimo, 0) - COALESCE(ut.vendible, 0)) AS faltante,
              COALESCE(e.disponible, 0) * COALESCE(e.costo_centavos, 0) AS valor_disponible_centavos,
              COALESCE(v.reserva, 0) AS valor_reservado_centavos, COALESCE(v.pendiente, 0) AS valor_pendiente_centavos,
              COALESCE(v.rechazo, 0) AS valor_bloqueado_centavos
              FROM ubicacion u CROSS JOIN producto pr
              LEFT JOIN existencia e ON e.ubicacion_id = u.id AND e.producto_id = pr.id
              LEFT JOIN valores v ON v.ubicacion_id = u.id AND v.producto_id = pr.id
              LEFT JOIN util ut ON ut.ubicacion_id = u.id AND ut.producto_id = pr.id
              WHERE (:ubicacion IS NULL OR u.id = :ubicacion)
        ) """
        detalle = self._seccion("Existencias, faltantes y valorización por producto", [
            ("ubicacion", "Ubicación"), ("codigo", "Producto"), ("descripcion", "Descripción"),
            ("disponible", "Disp. registrado"), ("reservado", "Reservado"), ("pendiente", "Pendiente"),
            ("vendible", "Vendible no vencido"), ("vencido", "Vencido sin vender"),
            ("rechazado", "Bloqueado"), ("minimo", "Mínimo"), ("faltante", "Faltante"),
            ("valor_disponible_centavos", "Valor disponible"), ("valor_reservado_centavos", "Valor reservado"),
            ("valor_pendiente_centavos", "Valor pendiente"), ("valor_bloqueado_centavos", "Valor bloqueado"),
        ], cte + "SELECT * FROM detalle ORDER BY ubicacion_id, codigo", p)
        resumen = self._seccion("Resumen de necesidades por ubicación", [
            ("ubicacion", "Ubicación"), ("productos", "Productos"), ("bajo_minimo", "Bajo mínimo"),
            ("unidades_faltantes", "U. faltantes"), ("valor_disponible_centavos", "Valor disponible"),
            ("valor_bloqueado_centavos", "Valor bloqueado"),
        ], cte + """SELECT ubicacion_id, ubicacion, COUNT(*) AS productos,
            SUM(CASE WHEN faltante > 0 THEN 1 ELSE 0 END) AS bajo_minimo,
            SUM(faltante) AS unidades_faltantes, SUM(valor_disponible_centavos) AS valor_disponible_centavos,
            SUM(valor_bloqueado_centavos) AS valor_bloqueado_centavos
            FROM detalle GROUP BY ubicacion_id ORDER BY ubicacion_id""", p)
        return [resumen, detalle]

    def _rechazos_precinto(self, p):
        cte = f"""WITH decisiones AS (
            SELECT h.bulto_id, h.nuevo AS resultado, h.fecha, o.local_id,
              (SELECT SUM(cb.cantidad) FROM contenido_bulto cb WHERE cb.bulto_id = h.bulto_id) AS unidades,
              (SELECT SUM(cb.cantidad * cb.costo_centavos) FROM contenido_bulto cb WHERE cb.bulto_id = h.bulto_id) AS valor,
              (julianday((SELECT fecha FROM historial_bulto WHERE bulto_id = h.bulto_id AND nuevo = 'Recibido'))
               - julianday((SELECT fecha FROM historial_bulto WHERE bulto_id = h.bulto_id AND nuevo = 'En tránsito'))) * 24 AS horas
              FROM historial_bulto h JOIN bulto b ON b.id = h.bulto_id
              JOIN remito r ON r.id = b.remito_id JOIN orden_reposicion o ON o.id = r.orden_id
              WHERE h.nuevo IN ('Verificado', 'Rechazado')
        ), filtradas AS (SELECT * FROM decisiones WHERE {PERIODO}) """
        resumen = self._seccion("Tasa de rechazo y tránsito por destino", [
            ("local", "Destino"), ("evaluados", "Bultos evaluados"), ("rechazados", "Rechazados"),
            ("tasa_porcentaje", "% rechazo"), ("unidades_rechazadas", "U. rechazadas"),
            ("valor_comprometido_centavos", "Valor comprometido"), ("horas_transito", "Tránsito medio (h)"),
        ], cte + """SELECT local_id, u.nombre AS local, COUNT(*) AS evaluados,
            SUM(CASE WHEN resultado = 'Rechazado' THEN 1 ELSE 0 END) AS rechazados,
            ROUND(100.0 * SUM(CASE WHEN resultado = 'Rechazado' THEN 1 ELSE 0 END) / COUNT(*), 2) AS tasa_porcentaje,
            SUM(CASE WHEN resultado = 'Rechazado' THEN unidades ELSE 0 END) AS unidades_rechazadas,
            SUM(CASE WHEN resultado = 'Rechazado' THEN valor ELSE 0 END) AS valor_comprometido_centavos,
            ROUND(AVG(horas), 2) AS horas_transito
            FROM filtradas JOIN ubicacion u ON u.id = local_id GROUP BY local_id ORDER BY local_id""", p)
        productos = self._seccion("Productos comprometidos en rechazos logísticos", [
            ("local", "Destino"), ("codigo", "Producto"), ("bultos", "Bultos"), ("unidades", "Unidades"),
            ("valor_comprometido_centavos", "Valor comprometido"),
        ], cte + """SELECT f.local_id, u.nombre AS local, cb.producto_id, pr.codigo,
            COUNT(DISTINCT f.bulto_id) AS bultos, SUM(cb.cantidad) AS unidades,
            SUM(cb.cantidad * cb.costo_centavos) AS valor_comprometido_centavos
            FROM filtradas f JOIN contenido_bulto cb ON cb.bulto_id = f.bulto_id
            JOIN producto pr ON pr.id = cb.producto_id JOIN ubicacion u ON u.id = f.local_id
            WHERE resultado = 'Rechazado' GROUP BY f.local_id, cb.producto_id ORDER BY f.local_id, pr.codigo""", p)
        return [resumen, productos]
