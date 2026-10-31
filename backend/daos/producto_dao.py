"""SQL del catálogo de productos."""

from backend.patterns.estados_bulto import ErrorDominio


class ProductoDAO:
    def __init__(self, conexion):
        self.cx = conexion

    def guardar(self, producto, identificador=None):
        datos = (producto.codigo, producto.descripcion, producto.categoria_id, producto.precio_centavos)
        if identificador is None:
            return self.cx.execute("""INSERT INTO producto
                (codigo, descripcion, categoria_id, precio_centavos) VALUES (?, ?, ?, ?)""", datos).lastrowid
        self.obtener(identificador)
        self.cx.execute("""UPDATE producto SET codigo = ?, descripcion = ?, categoria_id = ?,
                           precio_centavos = ? WHERE id = ?""", (*datos, identificador))
        return identificador

    def obtener(self, identificador):
        fila = self.cx.execute("SELECT * FROM producto WHERE id = ?", (identificador,)).fetchone()
        if fila is None:
            raise ErrorDominio("Seleccione un producto registrado.")
        return fila
