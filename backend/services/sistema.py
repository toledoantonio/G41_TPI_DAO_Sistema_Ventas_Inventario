"""Servicios de aplicación: catálogo, compras, logística verificada, costos y ventas."""

from contextlib import contextmanager
from datetime import datetime
import sqlite3

from backend.daos.bulto_dao import BultoDAO
from backend.daos.catalogo_dao import CatalogoDAO
from backend.daos.consultas_dao import ConsultasDAO
from backend.daos.operaciones_dao import OperacionesDAO
from backend.daos.producto_dao import ProductoDAO
from backend.daos.venta_dao import VentaDAO
from backend.database.config import BaseDatos
from backend.models.entidades import (
    Bulto,
    Categoria,
    Compra,
    OrdenReposicion,
    Producto,
    Proveedor,
    Remito,
    Ubicacion,
    Venta,
    centavos,
    codigo,
    entero,
    texto,
)
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
                raise ErrorDominio(
                    "Ya existe ese código, nombre, referencia, comprobante o precinto; solo se admite un CD."
                ) from error
            if "FOREIGN KEY" in mensaje:
                raise ErrorDominio("Hay una referencia inexistente; actualice los datos y vuelva a seleccionar.") from error
            raise ErrorDominio(f"La operación no se pudo confirmar: {mensaje}.") from error

    def listar(self, consulta):
        with self.db.conectar() as cx:
            return ConsultasDAO(cx).listar(consulta)

    def guardar_ubicacion(self, cod, nombre, direccion, tipo, identificador=None):
        ubicacion = Ubicacion.crear(cod, nombre, direccion, tipo, identificador)
        with self._operacion() as cx:
            if ubicacion.id is not None:
                anterior = CatalogoDAO(cx).ubicacion(ubicacion.id)
                if anterior["tipo"] != ubicacion.tipo:
                    raise ErrorDominio("No se puede cambiar la función de una ubicación registrada.")
            return CatalogoDAO(cx).guardar_ubicacion(
                ubicacion.codigo, ubicacion.nombre, ubicacion.direccion, ubicacion.tipo, ubicacion.id
            )

    def guardar_categoria(self, nombre, identificador=None):
        categoria = Categoria(nombre, identificador)
        with self._operacion() as cx:
            return CatalogoDAO(cx).guardar_categoria(categoria.nombre, categoria.id)

    def guardar_proveedor(self, cod, nombre, identificador=None):
        proveedor = Proveedor(cod, nombre, identificador)
        with self._operacion() as cx:
            return CatalogoDAO(cx).guardar_proveedor(proveedor.codigo, proveedor.nombre, proveedor.id)

    def guardar_producto(self, cod, descripcion, categoria_id, precio, identificador=None):
        producto = Producto(
            codigo(cod),
            texto(descripcion, "Descripción"),
            entero(categoria_id, "Categoría"),
            centavos(precio),
            identificador,
        )
        with self._operacion() as cx:
            return ProductoDAO(cx).guardar(producto, producto.id)

    def configurar_minimo(self, ubicacion_id, producto_id, minimo):
        minimo = entero(minimo, "Mínimo", 0)
        with self._operacion() as cx:
            dao = CatalogoDAO(cx)
            dao.ubicacion(ubicacion_id)
            ProductoDAO(cx).obtener(producto_id)
            dao.configurar_minimo(ubicacion_id, producto_id, minimo)

    def registrar_compra(self, referencia, proveedor_id, cd_id, detalles):
        """Detalles: (producto_id, cantidad entera, costo unitario decimal)."""
        compra = Compra(referencia, proveedor_id, cd_id, ahora())
        for producto_id, cantidad, costo in detalles:
            compra.agregar_detalle(producto_id, cantidad, costo)
        compra.validar_con_detalles()
        with self._operacion() as cx:
            dao = CatalogoDAO(cx)
            dao.proveedor(compra.proveedor_id)
            dao.ubicacion(compra.cd_id, "CD")
            documentos = OperacionesDAO(cx)
            compra_id = documentos.crear_compra(compra.referencia, compra.proveedor_id, compra.cd_id, compra.fecha)
            for detalle in compra.detalles:
                ProductoDAO(cx).obtener(detalle.producto_id)
                documentos.detalle_compra(compra_id, detalle.producto_id, detalle.cantidad, detalle.costo_centavos)
                dao.mover(
                    compra.cd_id,
                    detalle.producto_id,
                    "COMPRA",
                    compra_id,
                    compra.fecha,
                    disponible=detalle.cantidad,
                    costo_ingreso_centavos=detalle.costo_centavos,
                )
            return compra_id

    def crear_orden(self, cd_id, local_id, detalles):
        orden = OrdenReposicion(cd_id, local_id, ahora())
        for producto_id, cantidad in detalles:
            orden.agregar_detalle(producto_id, cantidad)
        orden.validar_con_detalles()
        with self._operacion() as cx:
            dao = CatalogoDAO(cx)
            dao.ubicacion(orden.cd_id, "CD")
            dao.ubicacion(orden.local_id, "LOCAL")
            documentos = OperacionesDAO(cx)
            orden_id = documentos.crear_orden(orden.cd_id, orden.local_id, orden.fecha)
            for detalle in orden.detalles:
                ProductoDAO(cx).obtener(detalle.producto_id)
                documentos.detalle_reposicion(orden_id, detalle.producto_id, detalle.cantidad)
            return orden_id

    def detalle_orden(self, identificador):
        with self.db.conectar() as cx:
            return ConsultasDAO(cx).detalle_orden(identificador)

    def preparar_bulto(self, orden_id, numero_remito, detalles):
        remito = Remito(numero_remito, orden_id)
        bulto = Bulto(None, "Preparado", remito=remito)
        for producto_id, cantidad in detalles:
            bulto.agregar_contenido(producto_id, cantidad)
        bulto.validar_con_contenido()
        with self._operacion() as cx:
            documentos = OperacionesDAO(cx)
            orden = documentos.obtener_orden(remito.orden_id)
            bulto.id = documentos.crear_bulto_con_remito(remito.orden_id, remito.numero)
            dao, fecha = CatalogoDAO(cx), ahora()
            for item in bulto.contenido:
                if item.cantidad > documentos.por_asignar(remito.orden_id, item.producto_id):
                    raise ErrorDominio("El contenido supera lo pendiente o incluye un producto ajeno a la orden.")
                saldo_cd = dao.existencia(orden["cd_id"], item.producto_id)
                item.costo_centavos = saldo_cd["costo_centavos"]
                dao.mover(
                    orden["cd_id"],
                    item.producto_id,
                    "PREPARACION",
                    bulto.id,
                    fecha,
                    disponible=-item.cantidad,
                    reservado=item.cantidad,
                )
                documentos.contenido_bulto(bulto.id, item.producto_id, item.cantidad, item.costo_centavos)
            BultoDAO(cx).registrar_estado(bulto, None, fecha, "Preparación y reserva en CD")
            return bulto.id

    def precintar(self, bulto_id, precinto):
        self._operar_bulto(bulto_id, "precintar", precinto=precinto)

    def despachar(self, bulto_id):
        self._operar_bulto(bulto_id, "despachar")

    def recibir(self, bulto_id, local_id):
        self._operar_bulto(bulto_id, "recibir", local_id=local_id)

    def verificar(self, bulto_id, local_id, precinto_observado, roto=False, observacion=""):
        self._operar_bulto(
            bulto_id, "verificar", local_id=local_id, precinto=precinto_observado, roto=roto, observacion=observacion
        )

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
                    inventario.mover(
                        local_id,
                        producto_id,
                        "VERIFICACION",
                        bulto_id,
                        fecha,
                        pendiente=-cantidad,
                        disponible=cantidad if habilitar else 0,
                        rechazado=cantidad if bulto.estado == "Rechazado" else 0,
                        costo_ingreso_centavos=item["costo_centavos"] if habilitar else None,
                    )
            bultos.registrar_estado(bulto, anterior, fecha, observacion)

    def historial_bulto(self, identificador):
        with self.db.conectar() as cx:
            return ConsultasDAO(cx).historial_bulto(identificador)

    def contenido_bulto(self, identificador):
        with self.db.conectar() as cx:
            return ConsultasDAO(cx).contenido_bulto(identificador)

    def registrar_venta(self, local_id, detalles, cobros, numero_comprobante=None):
        """Registra una venta en un local con sus detalles, cobros, stock, caja y comprobante interno.

        Detalles: secuencia de (producto_id, cantidad).
        Cobros: secuencia de (medio_pago, importe_decimal).
        """
        fecha = ahora()
        venta = Venta(local_id, fecha)
        for producto_id, cantidad in detalles:
            venta.agregar_detalle(producto_id, cantidad)
        venta.validar_con_detalles()
        for medio_pago, monto in cobros:
            venta.agregar_cobro(medio_pago, monto)
        with self._operacion() as cx:
            catalogo = CatalogoDAO(cx)
            catalogo.ubicacion(venta.local_id, "LOCAL")
            productos_dao = ProductoDAO(cx)
            for detalle in venta.detalles:
                prod = productos_dao.obtener(detalle.producto_id)
                existencia = catalogo.existencia(venta.local_id, detalle.producto_id)
                if detalle.cantidad > existencia["disponible"]:
                    raise ErrorDominio(f"Existencia disponible insuficiente para el producto {prod['codigo']}.")
                detalle.precio_unitario_centavos = prod["precio_centavos"]
                detalle.costo_unitario_centavos = existencia["costo_centavos"]
            venta.validar_operacion()
            ventas_dao = VentaDAO(cx)
            venta.id = ventas_dao.crear_venta(venta)
            for detalle in venta.detalles:
                ventas_dao.guardar_detalle(venta.id, detalle)
                catalogo.mover(
                    venta.local_id,
                    detalle.producto_id,
                    "VENTA",
                    venta.id,
                    fecha,
                    disponible=-detalle.cantidad,
                )
            for cobro in venta.cobros:
                cobro.id = ventas_dao.guardar_cobro(venta.id, cobro, fecha)
                ventas_dao.registrar_movimiento_caja(
                    venta.local_id,
                    "INGRESO",
                    cobro.medio_pago,
                    cobro.importe_centavos,
                    "VENTA",
                    cobro.id,
                    fecha,
                )
            comprobante = venta.emitir_comprobante(numero_comprobante)
            ventas_dao.guardar_comprobante(comprobante)
            return venta.id

    def obtener_venta(self, identificador):
        with self.db.conectar() as cx:
            return VentaDAO(cx).obtener(identificador)

    def detalle_venta(self, identificador):
        with self.db.conectar() as cx:
            return ConsultasDAO(cx).detalle_venta(identificador)

    def cobros_venta(self, identificador):
        with self.db.conectar() as cx:
            return ConsultasDAO(cx).cobros_venta(identificador)

    def comprobante_venta(self, identificador):
        with self.db.conectar() as cx:
            return ConsultasDAO(cx).comprobante_venta(identificador)
