"""Modelos del dominio orientados a objetos (Caps. 7, 8, 9, 10, 11 y 16)."""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from backend.patterns.estados_bulto import ErrorDominio, EstadoBulto, recuperar_estado


def texto(valor, nombre):
    resultado = "" if valor is None else str(valor).strip()
    if not resultado:
        raise ErrorDominio(f"{nombre} es obligatorio.")
    return resultado


def codigo(valor):
    return texto(valor, "Código").upper()


def entero(valor, nombre="Cantidad", minimo=1):
    if isinstance(valor, bool):
        raise ErrorDominio(f"{nombre} debe ser un entero entre {minimo} y 1000000000.")
    try:
        numero = Decimal(str(valor))
        if not numero.is_finite() or numero != numero.to_integral_value() or numero < minimo:
            raise ValueError
        if numero > 1_000_000_000:
            raise ValueError
        return int(numero)
    except (InvalidOperation, ValueError):
        raise ErrorDominio(f"{nombre} debe ser un entero entre {minimo} y 1000000000.") from None


def centavos(valor):
    if isinstance(valor, bool):
        raise ErrorDominio("Importe inválido: use un valor no negativo con hasta dos decimales.")
    try:
        monto = Decimal(str(valor).replace(",", "."))
        if not monto.is_finite() or monto < 0 or monto > Decimal("1000000000"):
            raise ValueError
        resultado = monto * 100
        if resultado != resultado.to_integral_value():
            raise ValueError
        return int(resultado)
    except (InvalidOperation, ValueError):
        raise ErrorDominio("Importe inválido: use un valor no negativo con hasta dos decimales.") from None


def importe(valor_centavos):
    return f"{Decimal(valor_centavos) / 100:.2f}"


def calcular_costo_promedio(cantidad_actual, costo_actual_centavos, cantidad_ingreso, costo_ingreso_centavos):
    """Calcula el costo unitario promedio ponderado en centavos (D18)."""
    cant_actual = entero(cantidad_actual, "Cantidad actual", 0)
    costo_actual = entero(costo_actual_centavos, "Costo actual", 0)
    cant_nueva = entero(cantidad_ingreso, "Cantidad de ingreso", 1)
    costo_nuevo = entero(costo_ingreso_centavos, "Costo de ingreso", 0)
    total_unidades = cant_actual + cant_nueva
    total_valor = (cant_actual * costo_actual) + (cant_nueva * costo_nuevo)
    return int((Decimal(total_valor) / Decimal(total_unidades)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


class Categoria:
    """Representa una categoría de productos del catálogo."""

    def __init__(self, nombre, identificador=None):
        self._id = identificador
        self.nombre = nombre

    @property
    def id(self):
        return self._id

    @id.setter
    def id(self, valor):
        self._id = None if valor is None else entero(valor, "ID de categoría")

    @property
    def nombre(self):
        return self._nombre

    @nombre.setter
    def nombre(self, valor):
        self._nombre = texto(valor, "Nombre de categoría")

    def __str__(self):
        return self._nombre

    def __eq__(self, otro):
        if not isinstance(otro, Categoria):
            return False
        return self._id == otro._id and self._nombre.upper() == otro._nombre.upper()


class Proveedor:
    """Representa un proveedor que abastece al Centro de Distribución."""

    def __init__(self, cod, nombre, identificador=None):
        self._id = identificador
        self.codigo = cod
        self.nombre = nombre

    @property
    def id(self):
        return self._id

    @id.setter
    def id(self, valor):
        self._id = None if valor is None else entero(valor, "ID de proveedor")

    @property
    def codigo(self):
        return self._codigo

    @codigo.setter
    def codigo(self, valor):
        self._codigo = codigo(valor)

    @property
    def nombre(self):
        return self._nombre

    @nombre.setter
    def nombre(self, valor):
        self._nombre = texto(valor, "Nombre de proveedor")

    def __str__(self):
        return f"{self._codigo} - {self._nombre}"

    def __eq__(self, otro):
        if not isinstance(otro, Proveedor):
            return False
        return self._codigo == otro._codigo and self._nombre == otro._nombre


class Ubicacion:
    """Clase base para ubicaciones físicas de la red (Cap. 10: Herencia)."""

    TIPOS_VALIDOS = ("CD", "LOCAL")

    def __init__(self, cod, nombre, direccion, tipo, identificador=None):
        self._id = identificador
        self.codigo = cod
        self.nombre = nombre
        self.direccion = direccion
        self.tipo = tipo

    @classmethod
    def crear(cls, cod, nombre, direccion, tipo, identificador=None):
        if tipo == "CD":
            return CentroDistribucion(cod, nombre, direccion, identificador)
        if tipo == "LOCAL":
            return Local(cod, nombre, direccion, identificador)
        raise ErrorDominio("El tipo debe ser CD o LOCAL.")

    @property
    def id(self):
        return self._id

    @id.setter
    def id(self, valor):
        self._id = None if valor is None else entero(valor, "ID de ubicación")

    @property
    def codigo(self):
        return self._codigo

    @codigo.setter
    def codigo(self, valor):
        self._codigo = codigo(valor)

    @property
    def nombre(self):
        return self._nombre

    @nombre.setter
    def nombre(self, valor):
        self._nombre = texto(valor, "Nombre")

    @property
    def direccion(self):
        return self._direccion

    @direccion.setter
    def direccion(self, valor):
        self._direccion = texto(valor, "Dirección")

    @property
    def tipo(self):
        return self._tipo

    @tipo.setter
    def tipo(self, valor):
        if valor not in self.TIPOS_VALIDOS:
            raise ErrorDominio("El tipo debe ser CD o LOCAL.")
        self._tipo = valor

    def __str__(self):
        return f"[{self._tipo}] {self._codigo} - {self._nombre}"

    def __eq__(self, otro):
        if not isinstance(otro, Ubicacion):
            return False
        return (
            self._codigo == otro._codigo
            and self._nombre == otro._nombre
            and self._direccion == otro._direccion
            and self._tipo == otro._tipo
        )


class CentroDistribucion(Ubicacion):
    """Ubicación especializada que actúa como Centro de Distribución central."""

    def __init__(self, cod, nombre, direccion, identificador=None):
        super().__init__(cod, nombre, direccion, "CD", identificador)


class Local(Ubicacion):
    """Ubicación especializada que actúa como sucursal o local de venta."""

    def __init__(self, cod, nombre, direccion, identificador=None):
        super().__init__(cod, nombre, direccion, "LOCAL", identificador)


class Producto:
    """Representa un artículo comercializable con sus atributos encapsulados (Caps. 7 y 8)."""

    def __init__(self, codigo_prod, descripcion, categoria_id, precio_centavos, identificador=None):
        self._id = identificador
        self.codigo = codigo_prod
        self.descripcion = descripcion
        self.categoria_id = categoria_id
        self.precio_centavos = precio_centavos

    @property
    def id(self):
        return self._id

    @id.setter
    def id(self, valor):
        self._id = None if valor is None else entero(valor, "ID de producto")

    @property
    def codigo(self):
        return self._codigo

    @codigo.setter
    def codigo(self, valor):
        if not isinstance(valor, str) or not valor.strip():
            raise ErrorDominio("Datos de producto inválidos.")
        self._codigo = valor.strip().upper()

    @property
    def descripcion(self):
        return self._descripcion

    @descripcion.setter
    def descripcion(self, valor):
        if not isinstance(valor, str) or not valor.strip():
            raise ErrorDominio("Datos de producto inválidos.")
        self._descripcion = valor.strip()

    @property
    def categoria_id(self):
        return self._categoria_id

    @categoria_id.setter
    def categoria_id(self, valor):
        self._categoria_id = entero(valor, "Categoría")

    @property
    def precio_centavos(self):
        return self._precio_centavos

    @precio_centavos.setter
    def precio_centavos(self, valor):
        if isinstance(valor, bool) or not isinstance(valor, int) or valor < 0:
            raise ErrorDominio("Datos de producto inválidos.")
        self._precio_centavos = valor

    @property
    def precio(self):
        """Atributo calculado que expone el precio formateado en unidades monetarias."""
        return importe(self._precio_centavos)

    def __str__(self):
        return f"{self._codigo} - {self._descripcion} (${self.precio})"

    def __eq__(self, otro):
        if not isinstance(otro, Producto):
            return False
        return (
            self._codigo == otro._codigo
            and self._descripcion == otro._descripcion
            and self._categoria_id == otro._categoria_id
            and self._precio_centavos == otro._precio_centavos
        )


class DetalleCompra:
    """Renglón perteneciente a una Compra recibida en el CD."""

    def __init__(self, producto_id, cantidad, costo_centavos):
        self.producto_id = producto_id
        self.cantidad = cantidad
        self.costo_centavos = costo_centavos

    @property
    def producto_id(self):
        return self._producto_id

    @producto_id.setter
    def producto_id(self, valor):
        self._producto_id = entero(valor, "Producto")

    @property
    def cantidad(self):
        return self._cantidad

    @cantidad.setter
    def cantidad(self, valor):
        self._cantidad = entero(valor, "Cantidad")

    @property
    def costo_centavos(self):
        return self._costo_centavos

    @costo_centavos.setter
    def costo_centavos(self, valor):
        if isinstance(valor, bool) or not isinstance(valor, int) or valor < 0:
            raise ErrorDominio("Importe inválido: use un valor no negativo con hasta dos decimales.")
        self._costo_centavos = valor

    @property
    def subtotal_centavos(self):
        return self._cantidad * self._costo_centavos

    def __str__(self):
        return f"Producto #{self._producto_id}: {self._cantidad} u. x ${importe(self._costo_centavos)}"

    def __eq__(self, otro):
        if not isinstance(otro, DetalleCompra):
            return False
        return (
            self._producto_id == otro._producto_id
            and self._cantidad == otro._cantidad
            and self._costo_centavos == otro._costo_centavos
        )


class Compra:
    """Composición de detalles de compra ingresados al CD (Cap. 9.3)."""

    def __init__(self, referencia, proveedor_id, cd_id, fecha=None, identificador=None):
        self._id = identificador
        self.referencia = referencia
        self.proveedor_id = proveedor_id
        self.cd_id = cd_id
        self._fecha = fecha
        self._detalles = []

    @property
    def id(self):
        return self._id

    @property
    def referencia(self):
        return self._referencia

    @referencia.setter
    def referencia(self, valor):
        self._referencia = codigo(valor)

    @property
    def proveedor_id(self):
        return self._proveedor_id

    @proveedor_id.setter
    def proveedor_id(self, valor):
        self._proveedor_id = entero(valor, "Proveedor")

    @property
    def cd_id(self):
        return self._cd_id

    @cd_id.setter
    def cd_id(self, valor):
        self._cd_id = entero(valor, "CD")

    @property
    def fecha(self):
        return self._fecha

    @property
    def detalles(self):
        return list(self._detalles)

    @property
    def total_centavos(self):
        return sum(d.subtotal_centavos for d in self._detalles)

    def agregar_detalle(self, producto_id, cantidad, costo):
        prod_id = entero(producto_id, "Producto")
        cant = entero(cantidad, "Cantidad")
        costo_cent = centavos(costo)
        for detalle in self._detalles:
            if detalle.producto_id == prod_id:
                if detalle.costo_centavos != costo_cent:
                    raise ErrorDominio("Consolide cada producto de la compra con un mismo costo unitario.")
                detalle.cantidad = entero(detalle.cantidad + cant)
                return
        self._detalles.append(DetalleCompra(prod_id, cant, costo_cent))

    def validar_con_detalles(self):
        if not self._detalles:
            raise ErrorDominio("Debe agregar al menos un producto a la compra.")

    def __str__(self):
        return f"Compra {self._referencia} ({len(self._detalles)} productos)"


class DetalleReposicion:
    """Renglón solicitado dentro de una OrdenReposicion."""

    def __init__(self, producto_id, cantidad):
        self.producto_id = producto_id
        self.cantidad = cantidad

    @property
    def producto_id(self):
        return self._producto_id

    @producto_id.setter
    def producto_id(self, valor):
        self._producto_id = entero(valor, "Producto")

    @property
    def cantidad(self):
        return self._cantidad

    @cantidad.setter
    def cantidad(self, valor):
        self._cantidad = entero(valor, "Cantidad")

    def __str__(self):
        return f"Producto #{self._producto_id}: {self._cantidad} u."

    def __eq__(self, otro):
        if not isinstance(otro, DetalleReposicion):
            return False
        return self._producto_id == otro._producto_id and self._cantidad == otro._cantidad


class OrdenReposicion:
    """Orden de reposición de un local hacia el CD (Cap. 9.3: Composición)."""

    def __init__(self, cd_id, local_id, fecha=None, identificador=None):
        self._id = identificador
        self.cd_id = cd_id
        self.local_id = local_id
        self._fecha = fecha
        self._detalles = []

    @property
    def id(self):
        return self._id

    @property
    def cd_id(self):
        return self._cd_id

    @cd_id.setter
    def cd_id(self, valor):
        self._cd_id = entero(valor, "CD")

    @property
    def local_id(self):
        return self._local_id

    @local_id.setter
    def local_id(self, valor):
        self._local_id = entero(valor, "Local")

    @property
    def fecha(self):
        return self._fecha

    @property
    def detalles(self):
        return list(self._detalles)

    @property
    def cantidad_total(self):
        return sum(d.cantidad for d in self._detalles)

    def agregar_detalle(self, producto_id, cantidad):
        prod_id = entero(producto_id, "Producto")
        cant = entero(cantidad, "Cantidad")
        for detalle in self._detalles:
            if detalle.producto_id == prod_id:
                detalle.cantidad = entero(detalle.cantidad + cant)
                return
        self._detalles.append(DetalleReposicion(prod_id, cant))

    def validar_con_detalles(self):
        if not self._detalles:
            raise ErrorDominio("Debe agregar al menos un producto.")

    def __str__(self):
        return f"Orden #{self._id or 'nueva'} (CD {self._cd_id} -> Local {self._local_id})"


class Remito:
    """Remito logístico asociado a un bulto de despacho."""

    ESTADOS_VALIDOS = ("Pendiente", "Verificado", "Rechazado")

    def __init__(self, numero, orden_id, estado="Pendiente", identificador=None):
        self._id = identificador
        self.numero = numero
        self.orden_id = orden_id
        self.estado = estado

    @property
    def id(self):
        return self._id

    @property
    def numero(self):
        return self._numero

    @numero.setter
    def numero(self, valor):
        self._numero = codigo(valor)

    @property
    def orden_id(self):
        return self._orden_id

    @orden_id.setter
    def orden_id(self, valor):
        self._orden_id = entero(valor, "Orden")

    @property
    def estado(self):
        return self._estado

    @estado.setter
    def estado(self, valor):
        if valor not in self.ESTADOS_VALIDOS:
            raise ErrorDominio(f"Estado de remito inválido: {valor}.")
        self._estado = valor

    @property
    def esta_verificado(self):
        return self._estado == "Verificado"

    def __str__(self):
        return f"Remito {self._numero} ({self._estado})"

    def __eq__(self, otro):
        if not isinstance(otro, Remito):
            return False
        return self._numero == otro._numero and self._orden_id == otro._orden_id and self._estado == otro._estado


class ContenidoBulto:
    """Ítem de mercadería contenido dentro de un Bulto, conservando su costo de transferencia."""

    def __init__(self, producto_id, cantidad, costo_centavos=0):
        self.producto_id = producto_id
        self.cantidad = cantidad
        self.costo_centavos = costo_centavos

    @property
    def producto_id(self):
        return self._producto_id

    @producto_id.setter
    def producto_id(self, valor):
        self._producto_id = entero(valor, "Producto")

    @property
    def cantidad(self):
        return self._cantidad

    @cantidad.setter
    def cantidad(self, valor):
        self._cantidad = entero(valor, "Cantidad")

    @property
    def costo_centavos(self):
        return self._costo_centavos

    @costo_centavos.setter
    def costo_centavos(self, valor):
        self._costo_centavos = entero(valor, "Costo de transferencia", 0)

    def __str__(self):
        return f"Producto #{self._producto_id}: {self._cantidad} u."

    def __eq__(self, otro):
        if not isinstance(otro, ContenidoBulto):
            return False
        return self._producto_id == otro._producto_id and self._cantidad == otro._cantidad


class Bulto:
    """Contexto del patrón State y contenedor de ContenidoBulto (Caps. 8, 9 y 16)."""

    def __init__(self, identificador, estado="Preparado", precinto=None, remito=None):
        self._id = identificador
        self._precinto = None if precinto is None else codigo(precinto)
        self._remito = remito
        self._estado = None
        self._contenido = []
        self.cambiar_estado(estado)

    @property
    def id(self):
        return self._id

    @id.setter
    def id(self, valor):
        self._id = None if valor is None else entero(valor, "ID de bulto")

    @property
    def precinto(self):
        return self._precinto

    @precinto.setter
    def precinto(self, valor):
        self._precinto = None if valor is None else codigo(valor)

    @property
    def remito(self):
        return self._remito

    @property
    def estado(self):
        return self._estado.nombre

    @property
    def estado_actual(self):
        return self._estado

    @property
    def contenido(self):
        return list(self._contenido)

    def cambiar_estado(self, nuevo_estado):
        if not isinstance(nuevo_estado, EstadoBulto):
            nuevo_estado = recuperar_estado(nuevo_estado)
        self._estado = nuevo_estado

    def agregar_contenido(self, producto_id, cantidad, costo_centavos=0):
        prod_id = entero(producto_id, "Producto")
        cant = entero(cantidad, "Cantidad")
        costo = entero(costo_centavos, "Costo de transferencia", 0)
        for item in self._contenido:
            if item.producto_id == prod_id:
                item.cantidad = entero(item.cantidad + cant)
                return
        self._contenido.append(ContenidoBulto(prod_id, cant, costo))

    def validar_con_contenido(self):
        if not self._contenido:
            raise ErrorDominio("Debe agregar al menos un producto.")

    def precintar(self, valor):
        nuevo_precinto = codigo(valor)
        self._estado.precintar(self)
        self._precinto = nuevo_precinto

    def despachar(self):
        self._estado.despachar(self)

    def recibir(self):
        self._estado.recibir(self)

    def verificar(self, precinto_observado, roto):
        if not isinstance(roto, bool):
            raise ErrorDominio("Indique si el precinto está roto.")
        observado = codigo(precinto_observado)
        # Roto siempre implica rechazo. Un código distinto pero íntegro no se acepta.
        if not roto and observado != self._precinto:
            raise ErrorDominio("El precinto observado no coincide; el bulto permanece bloqueado.")
        self._estado.verificar(self, roto)

    def __str__(self):
        precinto_txt = f", precinto {self._precinto}" if self._precinto else ""
        return f"Bulto #{self._id} ({self.estado}{precinto_txt})"

    def __eq__(self, otro):
        if not isinstance(otro, Bulto):
            return False
        return (
            self._id == otro._id
            and self.estado == otro.estado
            and self._precinto == otro._precinto
        )


class DetalleVenta:
    """Renglón de una Venta con precio de venta y costo histórico aplicados (Caps. 7 y 8)."""

    def __init__(
        self,
        producto_id,
        cantidad,
        precio_unitario_centavos=0,
        costo_unitario_centavos=0,
        identificador=None,
    ):
        self._id = identificador
        self.producto_id = producto_id
        self.cantidad = cantidad
        self.precio_unitario_centavos = precio_unitario_centavos
        self.costo_unitario_centavos = costo_unitario_centavos

    @property
    def id(self):
        return self._id

    @id.setter
    def id(self, valor):
        self._id = None if valor is None else entero(valor, "ID de detalle de venta")

    @property
    def producto_id(self):
        return self._producto_id

    @producto_id.setter
    def producto_id(self, valor):
        self._producto_id = entero(valor, "Producto")

    @property
    def cantidad(self):
        return self._cantidad

    @cantidad.setter
    def cantidad(self, valor):
        self._cantidad = entero(valor, "Cantidad")

    @property
    def precio_unitario_centavos(self):
        return self._precio_unitario_centavos

    @precio_unitario_centavos.setter
    def precio_unitario_centavos(self, valor):
        self._precio_unitario_centavos = entero(valor, "Precio unitario", 0)

    @property
    def costo_unitario_centavos(self):
        return self._costo_unitario_centavos

    @costo_unitario_centavos.setter
    def costo_unitario_centavos(self, valor):
        self._costo_unitario_centavos = entero(valor, "Costo unitario", 0)

    @property
    def subtotal_centavos(self):
        """Atributo calculado: cantidad * precio unitario histórico."""
        return self._cantidad * self._precio_unitario_centavos

    @property
    def costo_total_centavos(self):
        """Atributo calculado: cantidad * costo unitario histórico."""
        return self._cantidad * self._costo_unitario_centavos

    @property
    def margen_centavos(self):
        """Atributo calculado: subtotal de venta menos costo histórico total."""
        return self.subtotal_centavos - self.costo_total_centavos

    def __str__(self):
        return (
            f"Producto #{self._producto_id}: {self._cantidad} u. x "
            f"${importe(self._precio_unitario_centavos)} = ${importe(self.subtotal_centavos)}"
        )

    def __eq__(self, otro):
        if not isinstance(otro, DetalleVenta):
            return False
        return (
            self._producto_id == otro._producto_id
            and self._cantidad == otro._cantidad
            and self._precio_unitario_centavos == otro._precio_unitario_centavos
            and self._costo_unitario_centavos == otro._costo_unitario_centavos
        )


class Cobro:
    """Cobro registrado para una venta mediante un medio de pago (Cap. 8)."""

    MEDIOS_SUGERIDOS = ("EFECTIVO", "DEBITO", "CREDITO", "TRANSFERENCIA")

    def __init__(self, medio_pago, importe_centavos, fecha=None, identificador=None):
        self._id = identificador
        self.medio_pago = medio_pago
        self.importe_centavos = importe_centavos
        self._fecha = fecha

    @property
    def id(self):
        return self._id

    @id.setter
    def id(self, valor):
        self._id = None if valor is None else entero(valor, "ID de cobro")

    @property
    def medio_pago(self):
        return self._medio_pago

    @medio_pago.setter
    def medio_pago(self, valor):
        self._medio_pago = texto(valor, "Medio de pago").upper()

    @property
    def importe_centavos(self):
        return self._importe_centavos

    @importe_centavos.setter
    def importe_centavos(self, valor):
        if isinstance(valor, bool) or not isinstance(valor, int) or valor <= 0:
            raise ErrorDominio("El importe del cobro debe ser mayor a cero.")
        self._importe_centavos = valor

    @property
    def fecha(self):
        return self._fecha

    @property
    def importe(self):
        return importe(self._importe_centavos)

    def __str__(self):
        return f"{self._medio_pago}: ${self.importe}"

    def __eq__(self, otro):
        if not isinstance(otro, Cobro):
            return False
        return self._medio_pago == otro._medio_pago and self._importe_centavos == otro._importe_centavos


class Comprobante:
    """Comprobante interno emitido al confirmar una venta (Cap. 8)."""

    def __init__(self, numero, venta_id, total_centavos, fecha=None, identificador=None):
        self._id = identificador
        self.numero = numero
        self.venta_id = venta_id
        self.total_centavos = total_centavos
        self._fecha = fecha

    @property
    def id(self):
        return self._id

    @id.setter
    def id(self, valor):
        self._id = None if valor is None else entero(valor, "ID de comprobante")

    @property
    def numero(self):
        return self._numero

    @numero.setter
    def numero(self, valor):
        self._numero = codigo(valor)

    @property
    def venta_id(self):
        return self._venta_id

    @venta_id.setter
    def venta_id(self, valor):
        self._venta_id = entero(valor, "Venta")

    @property
    def total_centavos(self):
        return self._total_centavos

    @total_centavos.setter
    def total_centavos(self, valor):
        self._total_centavos = entero(valor, "Total de comprobante", 0)

    @property
    def fecha(self):
        return self._fecha

    @property
    def total(self):
        return importe(self._total_centavos)

    def __str__(self):
        return f"Comprobante {self._numero} (Venta #{self._venta_id}) - ${self.total}"

    def __eq__(self, otro):
        if not isinstance(otro, Comprobante):
            return False
        return (
            self._numero == otro._numero
            and self._venta_id == otro._venta_id
            and self._total_centavos == otro._total_centavos
        )


class Venta:
    """Operación comercial en un local, compuesta de DetalleVenta, Cobro y Comprobante (Cap. 9.3)."""

    def __init__(self, local_id, fecha=None, identificador=None):
        self._id = identificador
        self.local_id = local_id
        self._fecha = fecha
        self._detalles = []
        self._cobros = []
        self._comprobante = None

    @property
    def id(self):
        return self._id

    @id.setter
    def id(self, valor):
        self._id = None if valor is None else entero(valor, "ID de venta")

    @property
    def local_id(self):
        return self._local_id

    @local_id.setter
    def local_id(self, valor):
        self._local_id = entero(valor, "Local")

    @property
    def fecha(self):
        return self._fecha

    @property
    def detalles(self):
        return list(self._detalles)

    @property
    def cobros(self):
        return list(self._cobros)

    @property
    def comprobante(self):
        return self._comprobante

    @property
    def cantidad_total(self):
        return sum(d.cantidad for d in self._detalles)

    @property
    def total_centavos(self):
        return sum(d.subtotal_centavos for d in self._detalles)

    @property
    def costo_total_centavos(self):
        return sum(d.costo_total_centavos for d in self._detalles)

    @property
    def margen_centavos(self):
        return self.total_centavos - self.costo_total_centavos

    @property
    def total_cobrado_centavos(self):
        return sum(c.importe_centavos for c in self._cobros)

    def agregar_detalle(self, producto_id, cantidad, precio_unitario_centavos=0, costo_unitario_centavos=0):
        prod_id = entero(producto_id, "Producto")
        cant = entero(cantidad, "Cantidad")
        for detalle in self._detalles:
            if detalle.producto_id == prod_id:
                detalle.cantidad = entero(detalle.cantidad + cant)
                return
        self._detalles.append(
            DetalleVenta(prod_id, cant, precio_unitario_centavos, costo_unitario_centavos)
        )

    def agregar_cobro(self, medio_pago, monto):
        importe_cent = centavos(monto)
        if importe_cent <= 0:
            raise ErrorDominio("El importe del cobro debe ser mayor a cero.")
        self._cobros.append(Cobro(medio_pago, importe_cent, self._fecha))

    def validar_con_detalles(self):
        if not self._detalles:
            raise ErrorDominio("Debe agregar al menos un producto a la venta.")

    def validar_operacion(self):
        self.validar_con_detalles()
        if not self._cobros:
            raise ErrorDominio("Debe registrar al menos un cobro para la venta.")
        if self.total_cobrado_centavos != self.total_centavos:
            raise ErrorDominio("La suma de los cobros debe coincidir exactamente con el total de la venta.")

    def emitir_comprobante(self, numero=None):
        if self._id is None:
            raise ErrorDominio("La venta debe tener identificador antes de emitir el comprobante.")
        codigo_comp = codigo(numero) if numero else f"COMP-{self._id:06d}"
        self._comprobante = Comprobante(codigo_comp, self._id, self.total_centavos, self._fecha)
        return self._comprobante

    def __str__(self):
        comp = f" [{self._comprobante.numero}]" if self._comprobante else ""
        return f"Venta #{self._id or 'nueva'}{comp} - Total: ${importe(self.total_centavos)}"

    def __eq__(self, otro):
        if not isinstance(otro, Venta):
            return False
        return (
            self._id == otro._id
            and self._local_id == otro._local_id
            and self.total_centavos == otro.total_centavos
        )


def consolidar(detalles):
    """Agrupar renglones repetidos antes de validar stock o cantidades pendientes."""
    resultado = {}
    for producto_id, cantidad in detalles:
        producto_id = entero(producto_id, "Producto")
        resultado[producto_id] = entero(resultado.get(producto_id, 0) + entero(cantidad))
    if not resultado:
        raise ErrorDominio("Debe agregar al menos un producto.")
    return resultado
