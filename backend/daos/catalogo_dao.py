"""Persistencia de catálogo e inventario. La transacción pertenece al servicio."""

from backend.models.entidades import calcular_costo_promedio
from backend.patterns.estados_bulto import ErrorDominio


class CatalogoDAO:
    def __init__(self, conexion):
        self.cx = conexion

    def ubicacion(self, identificador, tipo=None):
        fila = self.cx.execute("SELECT * FROM ubicacion WHERE id = ?", (identificador,)).fetchone()
        if fila is None or (tipo and fila["tipo"] != tipo):
            raise ErrorDominio(f"Seleccione una ubicación válida{(' de tipo ' + tipo) if tipo else ''}.")
        return fila

    def proveedor(self, identificador):
        fila = self.cx.execute("SELECT * FROM proveedor WHERE id = ?", (identificador,)).fetchone()
        if fila is None:
            raise ErrorDominio("Seleccione un proveedor registrado.")
        return fila

    def guardar_ubicacion(self, cod, nombre, direccion, tipo, identificador=None):
        if identificador is None:
            return self.cx.execute(
                "INSERT INTO ubicacion (codigo, nombre, direccion, tipo) VALUES (?, ?, ?, ?)",
                (cod, nombre, direccion, tipo),
            ).lastrowid
        self.cx.execute(
            "UPDATE ubicacion SET codigo = ?, nombre = ?, direccion = ? WHERE id = ?",
            (cod, nombre, direccion, identificador),
        )
        return identificador

    def guardar_categoria(self, nombre, identificador=None):
        if identificador is None:
            return self.cx.execute("INSERT INTO categoria (nombre) VALUES (?)", (nombre,)).lastrowid
        if self.cx.execute("UPDATE categoria SET nombre = ? WHERE id = ?", (nombre, identificador)).rowcount != 1:
            raise ErrorDominio("La categoría no existe.")
        return identificador

    def guardar_proveedor(self, cod, nombre, identificador=None):
        if identificador is None:
            return self.cx.execute("INSERT INTO proveedor (codigo, nombre) VALUES (?, ?)", (cod, nombre)).lastrowid
        if (
            self.cx.execute(
                "UPDATE proveedor SET codigo = ?, nombre = ? WHERE id = ?",
                (cod, nombre, identificador),
            ).rowcount
            != 1
        ):
            raise ErrorDominio("El proveedor no existe.")
        return identificador

    def configurar_minimo(self, ubicacion_id, producto_id, minimo):
        self.existencia(ubicacion_id, producto_id)
        self.cx.execute(
            "UPDATE existencia SET minimo = ? WHERE ubicacion_id = ? AND producto_id = ?",
            (minimo, ubicacion_id, producto_id),
        )

    def existencia(self, ubicacion_id, producto_id):
        self.cx.execute(
            "INSERT OR IGNORE INTO existencia (ubicacion_id, producto_id) VALUES (?, ?)",
            (ubicacion_id, producto_id),
        )
        return self.cx.execute(
            "SELECT * FROM existencia WHERE ubicacion_id = ? AND producto_id = ?",
            (ubicacion_id, producto_id),
        ).fetchone()

    def mover(
        self,
        ubicacion_id,
        producto_id,
        causa,
        referencia,
        fecha,
        disponible=0,
        reservado=0,
        pendiente=0,
        rechazado=0,
        costo_ingreso_centavos=None,
    ):
        saldo = self.existencia(ubicacion_id, producto_id)
        deltas = (disponible, reservado, pendiente, rechazado)
        if any(
            saldo[campo] + delta < 0
            for campo, delta in zip(("disponible", "reservado", "pendiente", "rechazado"), deltas)
        ):
            raise ErrorDominio(f"Existencia insuficiente para el producto {producto_id}.")
        nuevo_costo = saldo["costo_centavos"]
        if costo_ingreso_centavos is not None and disponible > 0:
            stock_valorizado = saldo["disponible"] + saldo["reservado"]
            nuevo_costo = calcular_costo_promedio(
                stock_valorizado, saldo["costo_centavos"], disponible, costo_ingreso_centavos
            )
        self.cx.execute(
            """UPDATE existencia SET disponible = disponible + ?, reservado = reservado + ?,
               pendiente = pendiente + ?, rechazado = rechazado + ?, costo_centavos = ?
               WHERE ubicacion_id = ? AND producto_id = ?""",
            (*deltas, nuevo_costo, ubicacion_id, producto_id),
        )
        self.cx.execute(
            """INSERT INTO movimiento_inventario
               (ubicacion_id, producto_id, disponible, reservado, pendiente, rechazado,
                causa, referencia_id, fecha) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (ubicacion_id, producto_id, *deltas, causa, referencia, fecha),
        )
