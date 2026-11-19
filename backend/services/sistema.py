"""Servicios: catálogo, logística, ventas, devoluciones y consultas de reportes."""

from contextlib import contextmanager
from datetime import datetime
import sqlite3

from backend.daos.bulto_dao import BultoDAO
from backend.daos.catalogo_dao import CatalogoDAO
from backend.daos.consultas_dao import ConsultasDAO
from backend.daos.operaciones_dao import OperacionesDAO
from backend.daos.producto_dao import ProductoDAO
from backend.daos.venta_dao import VentaDAO
from backend.daos.devolucion_dao import DevolucionDAO
from backend.daos.lote_dao import LoteDAO
from backend.daos.compra_sugerida_dao import CompraSugeridaDAO
from backend.models.devoluciones import Devolucion
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
    consolidar,
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
            cx.execute("BEGIN")
            hoy = ahora()[:10]
            if consulta == "lotes":
                return LoteDAO(cx).listar(hoy)
            if consulta == "compras_sugeridas":
                return CompraSugeridaDAO(cx).listar()
            filas = ConsultasDAO(cx).listar(consulta)
            if consulta == "inventario":
                for fila in filas:
                    fila["vendible"] = LoteDAO(cx).vendible(fila["ubicacion_id"], fila["producto_id"], hoy)
                    fila["vencido"] = fila["disponible"] - fila["vendible"]
                    fila["faltante"] = max(0, fila["minimo"] - fila["vendible"])
            return filas

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

    def registrar_compra(self, referencia, proveedor_id, cd_id, detalles, orden_sugerida_id=None):
        """Detalles: (producto, cantidad, costo[, lote, vencimiento]); un costo por producto."""
        compra = Compra(referencia, proveedor_id, cd_id, ahora())
        lotes = []
        for renglon in detalles:
            if len(renglon) not in (3, 5):
                raise ErrorDominio("La compra requiere producto, cantidad y costo; lote y vencimiento son opcionales juntos.")
            producto_id, cantidad, costo = renglon[:3]
            compra.agregar_detalle(producto_id, cantidad, costo)
            lote, vencimiento = renglon[3:] if len(renglon) == 5 else (None, None)
            lotes.append((entero(producto_id, "Producto"), entero(cantidad), lote, vencimiento))
        compra.validar_con_detalles()
        with self._operacion() as cx:
            dao = CatalogoDAO(cx)
            dao.proveedor(compra.proveedor_id)
            dao.ubicacion(compra.cd_id, "CD")
            if orden_sugerida_id is not None:
                orden_sugerida_id = entero(orden_sugerida_id, "Orden sugerida")
                CompraSugeridaDAO(cx).validar_recepcion(orden_sugerida_id, compra)
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
            LoteDAO(cx).comprar(compra_id, compra.cd_id, lotes, compra.fecha)
            if orden_sugerida_id is not None:
                CompraSugeridaDAO(cx).recibir(orden_sugerida_id, compra_id)
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
                LoteDAO(cx).preparar(bulto.id, orden["cd_id"], item.producto_id, item.cantidad, fecha)
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
            LoteDAO(cx).operar_bulto(bulto_id, accion, fila["cd_id"], fila["local_id"], fecha,
                                    habilitar=bulto.estado == "Verificado")
            bultos.registrar_estado(bulto, anterior, fecha, observacion)

    def historial_bulto(self, identificador):
        with self.db.conectar() as cx:
            return ConsultasDAO(cx).historial_bulto(identificador)

    def contenido_bulto(self, identificador):
        with self.db.conectar() as cx:
            return ConsultasDAO(cx).contenido_bulto(identificador)

    def cantidad_vendible(self, local_id, producto_id):
        """Consulta las unidades vendibles actuales antes de cargar un renglón."""
        with self.db.conectar() as cx:
            return LoteDAO(cx).vendible(local_id, producto_id, ahora()[:10])

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
                if detalle.cantidad > LoteDAO(cx).vendible(venta.local_id, detalle.producto_id, fecha[:10]):
                    raise ErrorDominio(f"Existencia disponible insuficiente para el producto {prod['codigo']}.")
                detalle.precio_unitario_centavos = prod["precio_centavos"]
                detalle.costo_unitario_centavos = existencia["costo_centavos"]
            venta.validar_operacion()
            ventas_dao = VentaDAO(cx)
            venta.id = ventas_dao.crear_venta(venta)
            for detalle in venta.detalles:
                detalle_id = ventas_dao.guardar_detalle(venta.id, detalle)
                catalogo.mover(
                    venta.local_id,
                    detalle.producto_id,
                    "VENTA",
                    venta.id,
                    fecha,
                    disponible=-detalle.cantidad,
                )
                LoteDAO(cx).vender(detalle_id, venta.local_id, detalle.producto_id, detalle.cantidad, venta.id, fecha)
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

    def detalles_devolvibles(self, venta_id):
        with self.db.conectar() as cx:
            VentaDAO(cx).obtener(entero(venta_id, "Venta"))
            return DevolucionDAO(cx).originales(venta_id)

    def registrar_devolucion(self, venta_id, local_id, detalles, medio_reintegro, motivo, referencia):
        """Detalles: (detalle_venta_id, cantidad, VENDIBLE/NO_VENDIBLE[, lote_id]).

        La referencia identifica una operación y evita duplicar reintentos.
        La mercadería bloqueada ingresa a Rechazado, con causa DEVOLUCION.
        Con varios lotes en la venta se exige indicar el lote retornado.
        """
        devolucion = Devolucion(venta_id, local_id, referencia, motivo, medio_reintegro, ahora())
        cantidades, solicitudes = {}, []
        for renglon in detalles:
            if len(renglon) not in (3, 4):
                raise ErrorDominio("Indique detalle original, cantidad, condición y opcionalmente lote.")
            detalle_id, cantidad, condicion = renglon[:3]
            clave = (entero(detalle_id, "Detalle de venta"), codigo(condicion))
            cantidades[clave] = entero(cantidades.get(clave, 0) + entero(cantidad))
            lote = entero(renglon[3], "Lote") if len(renglon) == 4 and renglon[3] is not None else None
            solicitudes.append((clave[0], entero(cantidad), clave[1], lote))
        with self._operacion() as cx:
            venta = VentaDAO(cx).obtener(devolucion.venta_id)
            CatalogoDAO(cx).ubicacion(devolucion.local_id, "LOCAL")
            if venta.local_id != devolucion.local_id:
                raise ErrorDominio("La devolución debe realizarse en el mismo local de la venta.")
            dao = DevolucionDAO(cx)
            originales = {f["id"]: f for f in dao.originales(devolucion.venta_id)}
            acumuladas = {}
            for (detalle_id, condicion), cantidad in cantidades.items():
                original = originales.get(detalle_id)
                if original is None:
                    raise ErrorDominio("El detalle no pertenece a la venta original.")
                acumuladas[detalle_id] = acumuladas.get(detalle_id, 0) + cantidad
                if original["devuelta"] + acumuladas[detalle_id] > original["cantidad"]:
                    raise ErrorDominio("La devolución acumulada supera la cantidad vendida.")
                devolucion.agregar_detalle(original, cantidad, condicion)
            devolucion.validar()
            plan_lotes = LoteDAO(cx).plan_devolucion(solicitudes, devolucion.fecha[:10])
            identificador = dao.crear(devolucion)
            productos, retorno_lotes = {}, []
            for detalle in devolucion.detalles:
                detalle_id = dao.guardar_detalle(identificador, detalle)
                retorno_lotes.append((detalle_id, detalle.condicion, plan_lotes[detalle.detalle_venta_id, detalle.condicion]))
                saldo = productos.setdefault(detalle.producto_id, {
                    "disponible": 0, "rechazado": 0, "costo": detalle.costo_unitario_centavos,
                })
                campo = "disponible" if detalle.condicion == "VENDIBLE" else "rechazado"
                saldo[campo] += detalle.cantidad
            for producto_id, saldo in productos.items():
                CatalogoDAO(cx).mover(
                    devolucion.local_id, producto_id, "DEVOLUCION", identificador, devolucion.fecha,
                    disponible=saldo["disponible"], rechazado=saldo["rechazado"],
                    costo_ingreso_centavos=saldo["costo"] if saldo["disponible"] else None,
                )
            LoteDAO(cx).devolver(identificador, devolucion.local_id, retorno_lotes, devolucion.fecha)
            # Un producto de precio original cero se devuelve sin egreso ficticio.
            if devolucion.total_centavos:
                VentaDAO(cx).registrar_movimiento_caja(
                    devolucion.local_id, "EGRESO", devolucion.medio_reintegro, devolucion.total_centavos,
                    "DEVOLUCION", identificador, devolucion.fecha,
                )
            return identificador

    def obtener_devolucion(self, identificador):
        with self.db.conectar() as cx:
            return DevolucionDAO(cx).obtener(entero(identificador, "Devolución"))

    def generar_reporte(self, tipo, desde=None, hasta=None, ubicacion_id=None, medio_pago=None):
        from backend.reports.generador_reportes import GeneradorReportes

        with self.db.conectar() as cx:
            # Todas las secciones ven la misma instantánea, aun con otra ventana escribiendo.
            cx.execute("BEGIN")
            return GeneradorReportes(cx).generar(tipo, desde, hasta, ubicacion_id, medio_pago, hoy=ahora()[:10])

    def sugerencias_compra(self, cd_id):
        with self.db.conectar() as cx:
            cx.execute("BEGIN")
            CatalogoDAO(cx).ubicacion(entero(cd_id, "CD"), "CD")
            return CompraSugeridaDAO(cx).necesidades(cd_id, ahora()[:10])

    def generar_orden_compra(self, cd_id, proveedor_id, referencia, detalles=None):
        cd_id, proveedor_id = entero(cd_id, "CD"), entero(proveedor_id, "Proveedor")
        referencia = codigo(referencia)
        with self._operacion() as cx:
            CatalogoDAO(cx).ubicacion(cd_id, "CD")
            CatalogoDAO(cx).proveedor(proveedor_id)
            dao = CompraSugeridaDAO(cx)
            necesidades = {f["producto_id"]: f["cantidad_sugerida"] for f in dao.necesidades(cd_id, ahora()[:10])}
            items = consolidar(detalles) if detalles is not None else {p: c for p, c in necesidades.items() if c > 0}
            if not items:
                raise ErrorDominio("No hay faltantes sin cobertura para generar una orden sugerida.")
            # La sugerencia debe poder recibirse con los límites de cantidad de Compra.
            items = {producto: entero(cantidad) for producto, cantidad in items.items()}
            if any(cantidad > necesidades.get(producto, 0) for producto, cantidad in items.items()):
                raise ErrorDominio("La orden supera el faltante actual o incluye un producto sin necesidad de compra.")
            return dao.crear(referencia, cd_id, proveedor_id, ahora(), items)

    def obtener_orden_compra(self, identificador):
        with self.db.conectar() as cx:
            return CompraSugeridaDAO(cx).obtener(entero(identificador, "Orden sugerida"))

    def cancelar_orden_compra(self, identificador):
        with self._operacion() as cx:
            CompraSugeridaDAO(cx).cancelar(entero(identificador, "Orden sugerida"))

    def lotes_devolvibles(self, detalle_id):
        with self.db.conectar() as cx:
            return LoteDAO(cx).devolvibles(entero(detalle_id, "Detalle de venta"))

    def lotes_bulto(self, identificador):
        with self.db.conectar() as cx:
            BultoDAO(cx).obtener(entero(identificador, "Bulto"))
            return LoteDAO(cx).bulto(identificador)

    def trazabilidad_lote(self, identificador):
        with self.db.conectar() as cx:
            return LoteDAO(cx).traza(entero(identificador, "Lote"))
