"""Primer flujo: catálogo, compra recibida, reposición y logística verificada."""

from contextlib import contextmanager
from datetime import datetime
import sqlite3

from backend.daos.bulto_dao import BultoDAO
from backend.daos.catalogo_dao import CatalogoDAO
from backend.daos.producto_dao import ProductoDAO
from backend.daos.consultas_dao import ConsultasDAO
from backend.daos.operaciones_dao import OperacionesDAO
from backend.database.config import BaseDatos
from backend.models.entidades import Bulto, Producto, centavos, codigo, consolidar, entero, texto
from backend.patterns.estados_bulto import ErrorDominio


def ahora():
    return datetime.now().astimezone().isoformat(timespec="microseconds")


class Sistema:
    def __init__(self, ruta):
        self.db = BaseDatos(ruta)

    @contextmanager
    def _operacion(self):
        try:
            with self.db.transaccion() as cx:
                yield cx
        except sqlite3.IntegrityError as error:
            mensaje = str(error)
            if "UNIQUE" in mensaje:
                raise ErrorDominio("Ya existe ese código, nombre, referencia o precinto; solo se admite un CD.") from error
            if "FOREIGN KEY" in mensaje:
                raise ErrorDominio("Hay una referencia inexistente; actualice los datos y vuelva a seleccionar.") from error
            raise ErrorDominio(f"La operación no se pudo confirmar: {mensaje}.") from error

    def listar(self, consulta):
        with self.db.conectar() as cx:
            return ConsultasDAO(cx).listar(consulta)

    def guardar_ubicacion(self, cod, nombre, direccion, tipo, identificador=None):
        cod, nombre, direccion = codigo(cod), texto(nombre, "Nombre"), texto(direccion, "Dirección")
        if tipo not in ("CD", "LOCAL"):
            raise ErrorDominio("El tipo debe ser CD o LOCAL.")
        with self._operacion() as cx:
            if identificador is not None:
                anterior = CatalogoDAO(cx).ubicacion(identificador)
                if anterior["tipo"] != tipo:
                    raise ErrorDominio("No se puede cambiar la función de una ubicación registrada.")
            return CatalogoDAO(cx).guardar_ubicacion(cod, nombre, direccion, tipo, identificador)

    def guardar_categoria(self, nombre, identificador=None):
        nombre = texto(nombre, "Nombre de categoría")
        with self._operacion() as cx:
            return CatalogoDAO(cx).guardar_categoria(nombre, identificador)

    def guardar_proveedor(self, cod, nombre, identificador=None):
        cod, nombre = codigo(cod), texto(nombre, "Nombre de proveedor")
        with self._operacion() as cx:
            return CatalogoDAO(cx).guardar_proveedor(cod, nombre, identificador)

    def guardar_producto(self, cod, descripcion, categoria_id, precio, identificador=None):
        producto = Producto(codigo(cod), texto(descripcion, "Descripción"),
                            entero(categoria_id, "Categoría"), centavos(precio))
        with self._operacion() as cx:
            return ProductoDAO(cx).guardar(producto, identificador)

    def configurar_minimo(self, ubicacion_id, producto_id, minimo):
        minimo = entero(minimo, "Mínimo", 0)
        with self._operacion() as cx:
            dao = CatalogoDAO(cx)
            dao.ubicacion(ubicacion_id)
            ProductoDAO(cx).obtener(producto_id)
            dao.configurar_minimo(ubicacion_id, producto_id, minimo)

    def registrar_compra(self, referencia, proveedor_id, cd_id, detalles):
        """Detalles: (producto_id, cantidad entera, costo unitario decimal)."""
        referencia = codigo(referencia)
        items = {}
        for producto_id, cantidad, costo in detalles:
            producto_id, cantidad, costo = entero(producto_id, "Producto"), entero(cantidad), centavos(costo)
            if producto_id in items and items[producto_id][1] != costo:
                raise ErrorDominio("Consolide cada producto de la compra con un mismo costo unitario.")
            anterior = items.get(producto_id, (0, costo))[0]
            items[producto_id] = (entero(anterior + cantidad), costo)
        if not items:
            raise ErrorDominio("Debe agregar al menos un producto a la compra.")
        with self._operacion() as cx:
            dao, fecha = CatalogoDAO(cx), ahora()
            dao.proveedor(proveedor_id)
            dao.ubicacion(cd_id, "CD")
            documentos = OperacionesDAO(cx)
            compra_id = documentos.crear_compra(referencia, proveedor_id, cd_id, fecha)
            for producto_id, (cantidad, costo) in items.items():
                ProductoDAO(cx).obtener(producto_id)
                documentos.detalle_compra(compra_id, producto_id, cantidad, costo)
                dao.mover(cd_id, producto_id, "COMPRA", compra_id, fecha, disponible=cantidad)
            return compra_id

    def crear_orden(self, cd_id, local_id, detalles):
        items = consolidar(detalles)
        with self._operacion() as cx:
            dao = CatalogoDAO(cx)
            dao.ubicacion(cd_id, "CD")
            dao.ubicacion(local_id, "LOCAL")
            documentos = OperacionesDAO(cx)
            orden_id = documentos.crear_orden(cd_id, local_id, ahora())
            for producto_id, cantidad in items.items():
                ProductoDAO(cx).obtener(producto_id)
                documentos.detalle_reposicion(orden_id, producto_id, cantidad)
            return orden_id

    def detalle_orden(self, identificador):
        with self.db.conectar() as cx:
            return ConsultasDAO(cx).detalle_orden(identificador)

    def preparar_bulto(self, orden_id, numero_remito, detalles):
        numero_remito, items = codigo(numero_remito), consolidar(detalles)
        with self._operacion() as cx:
            documentos = OperacionesDAO(cx)
            orden = documentos.obtener_orden(orden_id)
            bulto_id = documentos.crear_bulto_con_remito(orden_id, numero_remito)
            dao, fecha = CatalogoDAO(cx), ahora()
            for producto_id, cantidad in items.items():
                if cantidad > documentos.por_asignar(orden_id, producto_id):
                    raise ErrorDominio("El contenido supera lo pendiente o incluye un producto ajeno a la orden.")
                dao.mover(orden["cd_id"], producto_id, "PREPARACION", bulto_id, fecha,
                          disponible=-cantidad, reservado=cantidad)
                documentos.contenido_bulto(bulto_id, producto_id, cantidad)
            BultoDAO(cx).registrar_estado(Bulto(bulto_id, "Preparado"), None, fecha, "Preparación y reserva en CD")
            return bulto_id

    def precintar(self, bulto_id, precinto):
        self._operar_bulto(bulto_id, "precintar", precinto=precinto)

    def despachar(self, bulto_id):
        self._operar_bulto(bulto_id, "despachar")

    def recibir(self, bulto_id, local_id):
        self._operar_bulto(bulto_id, "recibir", local_id=local_id)

    def verificar(self, bulto_id, local_id, precinto_observado, roto=False, observacion=""):
        self._operar_bulto(bulto_id, "verificar", local_id=local_id, precinto=precinto_observado,
                           roto=roto, observacion=observacion)

    def _operar_bulto(self, bulto_id, accion, local_id=None, precinto=None, roto=False, observacion=""):
        with self._operacion() as cx:
            bultos, inventario, fecha = BultoDAO(cx), CatalogoDAO(cx), ahora()
            bulto, fila = bultos.obtener(bulto_id)
            anterior = bulto.estado
            if accion in ("recibir", "verificar"):
                inventario.ubicacion(local_id, "LOCAL")
                if local_id != fila["local_id"]:
                    raise ErrorDominio("El local receptor no coincide con el destino del remito.")
            if accion == "precintar":
                bulto.precintar(precinto)
                observacion = f"Precinto asignado: {bulto.precinto}"
            elif accion == "despachar":
                bulto.despachar()
                observacion = "Salida física del CD"
            elif accion == "recibir":
                bulto.recibir()
                observacion = "Recepción en destino, mercadería pendiente de verificación"
            elif accion == "verificar":
                bulto.verificar(precinto, roto)
                evidencia = texto(observacion, "Motivo de rechazo") if roto else "Precinto íntegro y contenido conforme"
                observacion = f"Precinto observado: {codigo(precinto)}. {evidencia}"
                # Un remito por bulto: no hay casos mixtos ni habilitación parcial del documento.
                OperacionesDAO(cx).cambiar_estado_remito(fila["remito_id"], bulto.estado)
            else:
                raise ErrorDominio("Acción de bulto desconocida.")
            for item in bultos.contenido(bulto_id):
                producto_id, cantidad = item["producto_id"], item["cantidad"]
                if accion == "despachar":
                    inventario.mover(fila["cd_id"], producto_id, "DESPACHO", bulto_id, fecha, reservado=-cantidad)
                elif accion == "recibir":
                    inventario.mover(local_id, producto_id, "RECEPCION", bulto_id, fecha, pendiente=cantidad)
                elif accion == "verificar":
                    estado_remito = OperacionesDAO(cx).estado_remito(fila["remito_id"])
                    habilitar = bulto.estado == "Verificado" and estado_remito == "Verificado"
                    inventario.mover(local_id, producto_id, "VERIFICACION", bulto_id, fecha,
                                      pendiente=-cantidad, disponible=cantidad if habilitar else 0,
                                      rechazado=cantidad if bulto.estado == "Rechazado" else 0)
            bultos.registrar_estado(bulto, anterior, fecha, observacion)

    def historial_bulto(self, identificador):
        with self.db.conectar() as cx:
            return ConsultasDAO(cx).historial_bulto(identificador)

    def contenido_bulto(self, identificador):
        with self.db.conectar() as cx:
            return ConsultasDAO(cx).contenido_bulto(identificador)
