"""Reconstrucción y almacenamiento de bultos e historial."""

from backend.models.entidades import Bulto
from backend.patterns.estados_bulto import ErrorDominio


class BultoDAO:
    def __init__(self, conexion):
        self.cx = conexion

    def obtener(self, identificador):
        fila = self.cx.execute("""SELECT b.*, r.orden_id, o.cd_id, o.local_id FROM bulto b
            JOIN remito r ON r.id = b.remito_id JOIN orden_reposicion o ON o.id = r.orden_id
            WHERE b.id = ?""", (identificador,)).fetchone()
        if fila is None:
            raise ErrorDominio("Seleccione un bulto registrado.")
        ultimo = self.cx.execute("SELECT nuevo FROM historial_bulto WHERE bulto_id = ? ORDER BY id DESC LIMIT 1",
                                 (identificador,)).fetchone()
        if ultimo is None or ultimo["nuevo"] != fila["estado"]:
            raise ErrorDominio("El estado del bulto no coincide con su historial.")
        return Bulto(fila["id"], fila["estado"], fila["precinto"]), fila

    def contenido(self, identificador):
        return self.cx.execute("SELECT * FROM contenido_bulto WHERE bulto_id = ? ORDER BY producto_id",
                               (identificador,)).fetchall()

    def registrar_estado(self, bulto, anterior, fecha, observacion):
        self.cx.execute("UPDATE bulto SET estado = ?, precinto = ? WHERE id = ?",
                        (bulto.estado, bulto.precinto, bulto.id))
        self.cx.execute("""INSERT INTO historial_bulto (bulto_id, anterior, nuevo, fecha, observacion)
                           VALUES (?, ?, ?, ?, ?)""", (bulto.id, anterior, bulto.estado, fecha, observacion))
