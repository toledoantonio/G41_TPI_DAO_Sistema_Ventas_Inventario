"""Pruebas unitarias y de integración del dominio, patrones, logística y ventas con pytest (Cap. 12)."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from threading import Barrier
import pytest

from backend.database.config import BaseDatos
from backend.models.entidades import (
    Bulto,
    Categoria,
    CentroDistribucion,
    Cobro,
    Compra,
    Comprobante,
    DetalleCompra,
    DetalleReposicion,
    DetalleVenta,
    Local,
    OrdenReposicion,
    Producto,
    Proveedor,
    Remito,
    Ubicacion,
    Venta,
    calcular_costo_promedio,
    centavos,
    consolidar,
)
from backend.patterns.estados_bulto import (
    EnTransito,
    ErrorDominio,
    EstadoBulto,
    Precintado,
    Preparado,
    Recibido,
    Rechazado,
    Verificado,
)
from backend.services.sistema import Sistema


class TestModelosDominioYPatrones:
    """Pruebas unitarias de clases, encapsulamiento, composición, herencia, ABC y Singleton."""

    def test_patron_singleton_base_datos(self):
        """Verifica que BaseDatos garantice una única instancia y soporte reset_for_testing (Cap. 15)."""
        carpeta = Path(__file__).resolve().parents[1] / "tmp"
        carpeta.mkdir(exist_ok=True)
        with TemporaryDirectory(dir=carpeta) as temp_dir:
            BaseDatos.reset_for_testing()
            with pytest.raises(ValueError, match="primera inicialización"):
                BaseDatos()

            ruta = Path(temp_dir) / "singleton.sqlite3"
            db1 = BaseDatos(ruta)
            db2 = BaseDatos(ruta)
            db3 = BaseDatos.obtener_instancia()

            assert db1 is db2
            assert db1 is db3
            assert id(db1) == id(db2)
            assert db1.ruta == ruta
        BaseDatos.reset_for_testing()

    def test_estado_bulto_es_clase_abstracta(self):
        """Verifica que EstadoBulto(ABC) no pueda instanciarse directamente (Cap. 11.2)."""
        with pytest.raises(TypeError):
            EstadoBulto()

    def test_herencia_ubicacion_cd_y_local(self):
        """Verifica la jerarquía de herencia Ubicacion -> CentroDistribucion / Local (Cap. 10)."""
        cd = Ubicacion.crear("cd01", "Depósito Central", "Av. Principal 100", "CD")
        local = Ubicacion.crear("loc01", "Sucursal Norte", "Calle 200", "LOCAL")

        assert isinstance(cd, CentroDistribucion)
        assert isinstance(cd, Ubicacion)
        assert isinstance(local, Local)
        assert isinstance(local, Ubicacion)
        assert cd.codigo == "CD01"
        assert cd.tipo == "CD"
        assert local.codigo == "LOC01"
        assert local.tipo == "LOCAL"
        assert "[CD] CD01 - Depósito Central" in str(cd)

    def test_encapsulamiento_y_metodos_magicos_producto(self):
        """Verifica propiedades (@property / setter), __str__ y __eq__ en Producto (Cap. 8)."""
        p1 = Producto("p01", "Teclado Mecánico", 1, 15000)
        p2 = Producto("P01", "Teclado Mecánico", 1, 15000)

        assert p1 == p2
        assert p1.codigo == "P01"
        assert p1.precio == "150.00"
        assert str(p1) == "P01 - Teclado Mecánico ($150.00)"

        p1.precio_centavos = 20000
        assert p1.precio == "200.00"
        assert p1 != p2

        with pytest.raises(ErrorDominio, match="Datos de producto inválidos"):
            p1.precio_centavos = -10

        with pytest.raises(ErrorDominio, match="Datos de producto inválidos"):
            p1.codigo = "   "

    def test_composicion_compra_y_orden_reposicion(self):
        """Verifica que Compra y OrdenReposicion inicien con colección vacía y consoliden ítems (Cap. 9.3)."""
        compra = Compra("comp-01", 1, 1)
        assert compra.detalles == []
        assert compra.total_centavos == 0

        compra.agregar_detalle(10, 3, "50.00")
        compra.agregar_detalle(10, 2, "50.00")
        assert len(compra.detalles) == 1
        assert compra.detalles[0] == DetalleCompra(10, 5, 5000)
        assert compra.total_centavos == 25000

        with pytest.raises(ErrorDominio, match="mismo costo unitario"):
            compra.agregar_detalle(10, 1, "60.00")

        orden = OrdenReposicion(1, 2)
        assert orden.detalles == []
        orden.agregar_detalle(10, 4)
        orden.agregar_detalle(10, 6)
        assert orden.detalles == [DetalleReposicion(10, 10)]
        assert orden.cantidad_total == 10

    def test_composicion_venta_cobros_y_comprobante(self):
        """Verifica la composición en Venta con DetalleVenta, Cobro y Comprobante (Caps. 8 y 9)."""
        venta = Venta(2, "2026-10-27T10:00:00-03:00", identificador=7)
        assert venta.detalles == []
        assert venta.cobros == []
        assert venta.comprobante is None

        venta.agregar_detalle(1, 2, 10000, 6000)
        venta.agregar_detalle(1, 1, 10000, 6000)
        assert len(venta.detalles) == 1
        assert venta.detalles[0] == DetalleVenta(1, 3, 10000, 6000)
        assert venta.total_centavos == 30000
        assert venta.costo_total_centavos == 18000
        assert venta.margen_centavos == 12000

        venta.agregar_cobro("efectivo", "100.00")
        with pytest.raises(ErrorDominio, match="coincidir exactamente"):
            venta.validar_operacion()

        venta.agregar_cobro("debito", "200.00")
        venta.validar_operacion()
        assert venta.cobros == [Cobro("EFECTIVO", 10000), Cobro("DEBITO", 20000)]

        comp = venta.emitir_comprobante()
        assert comp == Comprobante("COMP-000007", 7, 30000)
        assert "COMP-000007" in str(venta)

    def test_patron_state_transiciones_en_bulto(self):
        """Verifica que los estados concretos cambien el estado del contexto Bulto (Cap. 16.2)."""
        remito = Remito("r-01", 1)
        bulto = Bulto(1, "Preparado", remito=remito)
        assert bulto.estado_actual == Preparado()

        bulto.precintar("sello-1")
        assert bulto.estado_actual == Precintado()
        assert bulto.precinto == "SELLO-1"

        bulto.despachar()
        assert bulto.estado_actual == EnTransito()

        bulto.recibir()
        assert bulto.estado_actual == Recibido()

        bulto.verificar("SELLO-1", False)
        assert bulto.estado_actual == Verificado()
        assert bulto.estado_actual != Rechazado()


class TestFlujoLogisticoYVentas:
    """Suite de pruebas para catálogo, compras, logística, costos históricos y ventas."""

    def setup_method(self):
        BaseDatos.reset_for_testing()
        carpeta = Path(__file__).resolve().parents[1] / "tmp"
        carpeta.mkdir(exist_ok=True)
        self.temporal = TemporaryDirectory(dir=carpeta)
        self.ruta = Path(self.temporal.name) / "prueba.sqlite3"
        self.s = Sistema(self.ruta)
        self.cd = self.s.guardar_ubicacion("CD", "Depósito", "Dirección CD", "CD")
        self.local = self.s.guardar_ubicacion("L1", "Local 1", "Dirección L1", "LOCAL")
        self.categoria = self.s.guardar_categoria("Categoría")
        self.proveedor = self.s.guardar_proveedor("PR", "Proveedor")
        self.p = self.s.guardar_producto("P", "Producto", self.categoria, "100.00")
        self.q = self.s.guardar_producto("Q", "Otro producto", self.categoria, "50.00")

    def teardown_method(self):
        BaseDatos.reset_for_testing()
        self.temporal.cleanup()

    def saldo(self, ubicacion, producto=None):
        return next(
            f
            for f in self.s.listar("inventario")
            if f["ubicacion_id"] == ubicacion and f["producto_id"] == (producto or self.p)
        )

    def consultar(self, sql):
        with self.s.db.conectar() as cx:
            return cx.execute(sql).fetchall()

    def preparar(self, cantidad=10):
        self.s.registrar_compra("C1", self.proveedor, self.cd, [(self.p, 20, "60.00")])
        orden = self.s.crear_orden(self.cd, self.local, [(self.p, cantidad)])
        return self.s.preparar_bulto(orden, "R1", [(self.p, cantidad)])

    def recibir(self):
        bulto = self.preparar()
        self.s.precintar(bulto, "S1")
        self.s.despachar(bulto)
        self.s.recibir(bulto, self.local)
        return bulto

    def habilitar_en_local(self, cantidad=10):
        bulto = self.recibir() if cantidad == 10 else None
        if bulto is None:
            bulto = self.preparar(cantidad)
            self.s.precintar(bulto, "S1")
            self.s.despachar(bulto)
            self.s.recibir(bulto, self.local)
        self.s.verificar(bulto, self.local, "S1")
        return bulto

    def test_recorrido_persistencia_historial_y_reconciliacion(self):
        """Verifica el ciclo completo del bulto, persistencia, historial y saldos."""
        bulto = self.preparar()
        assert (self.saldo(self.cd)["disponible"], self.saldo(self.cd)["reservado"]) == (10, 10)

        self.s.precintar(bulto, "S1")
        self.s.despachar(bulto)
        assert (self.saldo(self.cd)["disponible"], self.saldo(self.cd)["reservado"]) == (10, 0)
        assert self.saldo(self.local)["disponible"] == 0

        self.s.recibir(bulto, self.local)
        assert (self.saldo(self.local)["pendiente"], self.saldo(self.local)["disponible"]) == (10, 0)

        self.s.verificar(bulto, self.local, "s1")
        self.s = Sistema(self.ruta)
        assert (self.saldo(self.local)["pendiente"], self.saldo(self.local)["disponible"]) == (0, 10)

        fila = self.s.listar("bultos")[0]
        assert (fila["estado"], fila["estado_remito"]) == ("Verificado", "Verificado")
        assert [h["nuevo"] for h in self.s.historial_bulto(bulto)] == [
            "Preparado",
            "Precintado",
            "En tránsito",
            "Recibido",
            "Verificado",
        ]

        for ubicacion in (self.cd, self.local):
            sumas = self.consultar(
                f"""SELECT SUM(disponible), SUM(reservado), SUM(pendiente), SUM(rechazado)
                FROM movimiento_inventario WHERE ubicacion_id = {ubicacion} AND producto_id = {self.p}"""
            )[0]
            assert tuple(sumas) == tuple(
                self.saldo(ubicacion)[k] for k in ("disponible", "reservado", "pendiente", "rechazado")
            )

    def test_costo_promedio_ponderado_y_conservacion_en_transferencia(self):
        """Verifica el cálculo de costo promedio ponderado en CD y su transferencia al local (D18)."""
        # Compra 1: 10 u. a $60.00 (6000 centavos)
        self.s.registrar_compra("C1", self.proveedor, self.cd, [(self.p, 10, "60.00")])
        assert self.saldo(self.cd)["costo_centavos"] == 6000

        # Compra 2: 10 u. a $80.00 (8000 centavos) -> CPP en CD = $70.00 (7000 centavos)
        self.s.registrar_compra("C2", self.proveedor, self.cd, [(self.p, 10, "80.00")])
        assert self.saldo(self.cd)["costo_centavos"] == 7000

        # Se prepara primer bulto de 10 u. (conserva costo 7000)
        orden = self.s.crear_orden(self.cd, self.local, [(self.p, 20)])
        b1 = self.s.preparar_bulto(orden, "R1", [(self.p, 10)])
        assert self.s.contenido_bulto(b1)[0]["costo_centavos"] == 7000

        # Antes de verificar b1 en el local, el CD compra 10 u. más a $100.00 (10000 centavos)
        # Solo promedian 10 disponibles a 7000 + 10 nuevas a 10000 = 8500.
        # Las 10 reservadas conservan su costo de 7000 en el bulto.
        self.s.registrar_compra("C3", self.proveedor, self.cd, [(self.p, 10, "100.00")])
        assert self.saldo(self.cd)["costo_centavos"] == 8500

        # Al verificar b1 en el local, el local recibe el costo histórico del bulto b1 (7000)
        self.s.precintar(b1, "S1")
        self.s.despachar(b1)
        self.s.recibir(b1, self.local)
        self.s.verificar(b1, self.local, "S1")
        assert self.saldo(self.local)["costo_centavos"] == 7000

        # Segundo bulto a 8500; el local promedia 10 a 7000 + 10 a 8500 = 7750.
        b2 = self.s.preparar_bulto(orden, "R2", [(self.p, 10)])
        self.s.precintar(b2, "S2")
        self.s.despachar(b2)
        self.s.recibir(b2, self.local)
        self.s.verificar(b2, self.local, "S2")
        assert self.saldo(self.local)["disponible"] == 20
        assert self.saldo(self.local)["costo_centavos"] == 7750
        # Compras por $2400 = CD (10 * $85) + local (20 * $77,50).
        assert sum(f["valor_disponible_centavos"] for f in self.s.listar("inventario")) == 240000

    def test_venta_con_varios_productos_cobro_mixto_caja_y_comprobante(self):
        """Verifica registro de venta, descuento de stock, cobro mixto, caja, comprobante e historial de precios."""
        self.s.registrar_compra("C1", self.proveedor, self.cd, [(self.p, 10, "60.00"), (self.q, 10, "20.00")])
        orden = self.s.crear_orden(self.cd, self.local, [(self.p, 10), (self.q, 10)])
        bulto = self.s.preparar_bulto(orden, "R1", [(self.p, 10), (self.q, 10)])
        self.s.precintar(bulto, "S1")
        self.s.despachar(bulto)
        self.s.recibir(bulto, self.local)
        self.s.verificar(bulto, self.local, "S1")

        # Venta en local: 2 u. de P (a $100.00 = $200.00) + 1 u. más de P consolidada + 2 u. de Q (a $50.00 = $100.00)
        # Total = 3 * $100.00 + 2 * $50.00 = $400.00 (40000 centavos)
        # Costo histórico = 3 * $60.00 + 2 * $20.00 = $220.00 (22000 centavos) -> Margen = $180.00 (18000 centavos)
        venta_id = self.s.registrar_venta(
            self.local,
            [(self.p, 2), (self.p, 1), (self.q, 2)],
            [("EFECTIVO", "150.00"), ("DEBITO", "250.00")],
        )

        # Modificar catálogo después de la venta no debe alterar precios ni costos históricos de la venta
        self.s.guardar_producto("P", "Producto", self.categoria, "180.00", self.p)

        assert self.saldo(self.local, self.p)["disponible"] == 7
        assert self.saldo(self.local, self.q)["disponible"] == 8

        ventas = self.s.listar("ventas")
        assert len(ventas) == 1
        assert ventas[0]["id"] == venta_id
        assert ventas[0]["comprobante"] == f"COMP-{venta_id:06d}"
        assert ventas[0]["unidades"] == 5
        assert ventas[0]["total_centavos"] == 40000
        assert ventas[0]["costo_total_centavos"] == 22000
        assert ventas[0]["margen_centavos"] == 18000

        comp = self.s.comprobante_venta(venta_id)
        assert comp["numero"] == f"COMP-{venta_id:06d}"
        assert len(comp["detalles"]) == 2
        assert comp["detalles"][0]["precio_unitario_centavos"] == 10000
        assert comp["detalles"][0]["costo_unitario_centavos"] == 6000
        assert comp["detalles"][0]["cantidad"] == 3

        caja = self.s.listar("caja")
        assert len(caja) == 2
        assert sum(m["importe_centavos"] for m in caja) == 40000
        assert {m["medio_pago"] for m in caja} == {"EFECTIVO", "DEBITO"}

        venta_reconstruida = self.s.obtener_venta(venta_id)
        assert venta_reconstruida.total_centavos == 40000
        assert venta_reconstruida.comprobante.numero == f"COMP-{venta_id:06d}"

    def test_venta_rechaza_sobreventa_cobro_inexacto_y_stock_no_verificado(self):
        """Verifica que no se pueda vender más de lo disponible ni con cobros distintos al total."""
        bulto = self.recibir()
        # En estado Recibido el stock está Pendiente (10), pero Disponible es 0
        with pytest.raises(ErrorDominio, match="Existencia disponible insuficiente"):
            self.s.registrar_venta(self.local, [(self.p, 1)], [("EFECTIVO", "100.00")])

        # Habilitar las 10 unidades verificando el bulto
        self.s.verificar(bulto, self.local, "S1")

        # Intentar vender 6 + 5 = 11 unidades (supera las 10 disponibles al consolidar renglones)
        with pytest.raises(ErrorDominio, match="Existencia disponible insuficiente"):
            self.s.registrar_venta(self.local, [(self.p, 6), (self.p, 5)], [("EFECTIVO", "1100.00")])

        # Intentar cobrar de menos o de más respecto del total ($200.00)
        with pytest.raises(ErrorDominio, match="coincidir exactamente"):
            self.s.registrar_venta(self.local, [(self.p, 2)], [("EFECTIVO", "199.99")])

        with pytest.raises(ErrorDominio, match="coincidir exactamente"):
            self.s.registrar_venta(self.local, [(self.p, 2)], [("EFECTIVO", "200.01")])

        # No se puede registrar venta comercial en el CD
        with pytest.raises(ErrorDominio, match="de tipo LOCAL"):
            self.s.registrar_venta(self.cd, [(self.p, 1)], [("EFECTIVO", "100.00")])

        # Ninguno de los intentos fallidos debe haber afectado el stock ni la caja
        assert self.saldo(self.local)["disponible"] == 10
        assert self.s.listar("ventas") == []
        assert self.s.listar("caja") == []

    def test_fallo_en_comprobante_revierte_venta_stock_y_caja(self):
        """Verifica que la venta, detalles, stock, cobros y comprobante sean atómicos."""
        self.habilitar_en_local(10)
        self.s.registrar_venta(self.local, [(self.p, 1)], [("EFECTIVO", "100.00")], "COMP-UNICO-01")
        assert self.saldo(self.local)["disponible"] == 9

        # Intentar otra venta reutilizando el mismo número de comprobante dispara rollback completo
        with pytest.raises(ErrorDominio):
            self.s.registrar_venta(self.local, [(self.p, 2)], [("EFECTIVO", "200.00")], "COMP-UNICO-01")

        assert self.saldo(self.local)["disponible"] == 9
        assert len(self.s.listar("ventas")) == 1
        assert len(self.s.listar("caja")) == 1

    def test_precinto_roto_no_habilita_ni_retorna_cd(self):
        """Verifica que un precinto roto rechace el bulto y bloquee el stock."""
        bulto = self.recibir()
        self.s.verificar(bulto, self.local, "S1", True, "Sello cortado")
        assert (self.saldo(self.local)["disponible"], self.saldo(self.local)["rechazado"]) == (0, 10)
        assert self.saldo(self.local)["costo_centavos"] == 0
        assert self.saldo(self.cd)["disponible"] == 10
        assert self.s.listar("bultos")[0]["estado_remito"] == "Rechazado"
        assert "Sello cortado" in self.s.historial_bulto(bulto)[-1]["observacion"]

    def test_codigo_precinto_distinto_sigue_pendiente(self):
        """Verifica que un código de precinto distinto mantenga el bulto en estado Recibido."""
        bulto = self.recibir()
        with pytest.raises(ErrorDominio, match="no coincide"):
            self.s.verificar(bulto, self.local, "OTRO")
        assert self.s.listar("bultos")[0]["estado"] == "Recibido"
        assert self.saldo(self.local)["pendiente"] == 10
        assert len(self.s.historial_bulto(bulto)) == 4

    def test_rechazo_requiere_motivo(self):
        """Verifica que el rechazo por precinto roto exija registrar un motivo."""
        bulto = self.recibir()
        with pytest.raises(ErrorDominio, match="Motivo de rechazo"):
            self.s.verificar(bulto, self.local, "S1", True)
        assert self.s.listar("bultos")[0]["estado_remito"] == "Pendiente"

    def test_state_rechaza_saltos_y_operaciones_duplicadas(self):
        """Verifica que el patrón State impida saltar etapas o repetir transiciones."""
        bulto = self.preparar()
        for operacion in (
            lambda: self.s.despachar(bulto),
            lambda: self.s.recibir(bulto, self.local),
            lambda: self.s.verificar(bulto, self.local, "S1"),
        ):
            with pytest.raises(ErrorDominio):
                operacion()
        assert len(self.s.historial_bulto(bulto)) == 1

        self.s.precintar(bulto, "S1")
        self.s.despachar(bulto)
        with pytest.raises(ErrorDominio):
            self.s.despachar(bulto)

        self.s.recibir(bulto, self.local)
        with pytest.raises(ErrorDominio):
            self.s.recibir(bulto, self.local)

        self.s.verificar(bulto, self.local, "S1")
        with pytest.raises(ErrorDominio):
            self.s.verificar(bulto, self.local, "S1")

        assert self.saldo(self.local)["disponible"] == 10
        assert len(self.s.historial_bulto(bulto)) == 5

    def test_destino_equivocado_no_registra_llegada(self):
        """Verifica que un local distinto al destinatario no pueda recibir el bulto."""
        bulto = self.preparar()
        otro = self.s.guardar_ubicacion("L2", "Local 2", "Dirección 2", "LOCAL")
        self.s.precintar(bulto, "S1")
        self.s.despachar(bulto)
        with pytest.raises(ErrorDominio, match="no coincide con el destino"):
            self.s.recibir(bulto, otro)
        assert self.s.listar("bultos")[0]["estado"] == "En tránsito"
        assert self.saldo(otro)["pendiente"] == 0

    def test_historial_no_se_modifica_ni_borra(self):
        """Verifica la inmutabilidad del historial de estados del bulto en la base."""
        self.preparar()
        for sql in ("UPDATE historial_bulto SET nuevo = 'Verificado'", "DELETE FROM historial_bulto"):
            with pytest.raises(sqlite3.IntegrityError):
                with self.s.db.transaccion() as cx:
                    cx.execute(sql)
        assert self.consultar("SELECT COUNT(*) FROM historial_bulto")[0][0] == 1

    def test_fallo_en_historial_revierte_estado_remito_y_stock(self):
        """Verifica que un fallo dentro de la transacción revierta todos los cambios."""
        bulto = self.recibir()
        with self.s.db.transaccion() as cx:
            cx.execute(
                """CREATE TRIGGER fallo_prueba BEFORE INSERT ON historial_bulto
                WHEN NEW.nuevo = 'Verificado' BEGIN SELECT RAISE(ABORT, 'fallo simulado'); END"""
            )
        with pytest.raises(ErrorDominio):
            self.s.verificar(bulto, self.local, "S1")
        fila = self.s.listar("bultos")[0]
        assert (fila["estado"], fila["estado_remito"]) == ("Recibido", "Pendiente")
        assert (self.saldo(self.local)["disponible"], self.saldo(self.local)["pendiente"]) == (0, 10)
        assert self.consultar("SELECT COUNT(*) FROM movimiento_inventario WHERE causa = 'VERIFICACION'")[0][0] == 0

    def test_sin_stock_revierte_bulto_remito_reservas_y_detalles(self):
        """Verifica que preparar sin existencia suficiente revierta toda la operación."""
        self.s.registrar_compra("C1", self.proveedor, self.cd, [(self.p, 20, "60")])
        orden = self.s.crear_orden(self.cd, self.local, [(self.p, 10), (self.q, 5)])
        with pytest.raises(ErrorDominio, match="Existencia insuficiente"):
            self.s.preparar_bulto(orden, "R1", [(self.p, 10), (self.q, 5)])
        assert self.saldo(self.cd)["disponible"] == 20
        assert self.saldo(self.cd)["reservado"] == 0
        assert self.s.listar("bultos") == []
        assert self.consultar("SELECT COUNT(*) FROM remito")[0][0] == 0

    def test_consolidacion_y_despachos_parciales(self):
        """Verifica la consolidación de renglones y la atención parcial en varios bultos."""
        self.s.registrar_compra("C1", self.proveedor, self.cd, [(self.p, 20, "60")])
        orden = self.s.crear_orden(self.cd, self.local, [(self.p, 4), (self.p, 6)])
        b1 = self.s.preparar_bulto(orden, "R1", [(self.p, 3), (self.p, 2)])
        b2 = self.s.preparar_bulto(orden, "R2", [(self.p, 5)])
        assert b1 != b2
        assert self.s.detalle_orden(orden)[0]["pendiente"] == 0
        with pytest.raises(ErrorDominio, match="supera lo pendiente"):
            self.s.preparar_bulto(orden, "R3", [(self.p, 1)])
        assert len(self.s.listar("bultos")) == 2

    def test_cada_bulto_tiene_remito_y_rechazo_no_bloquea_otro(self):
        """Verifica que el rechazo de un bulto no impida verificar otro bulto válido."""
        b1 = self.preparar(5)
        orden = self.s.crear_orden(self.cd, self.local, [(self.p, 5)])
        b2 = self.s.preparar_bulto(orden, "R2", [(self.p, 5)])
        for bulto, precinto in ((b1, "S1"), (b2, "S2")):
            self.s.precintar(bulto, precinto)
            self.s.despachar(bulto)
            self.s.recibir(bulto, self.local)
        self.s.verificar(b1, self.local, "S1", True, "Rotura")
        self.s.verificar(b2, self.local, "S2")
        assert (self.saldo(self.local)["disponible"], self.saldo(self.local)["rechazado"]) == (5, 5)

    def test_precinto_unico_global(self):
        """Verifica que no se pueda reutilizar un mismo código de precinto."""
        b1 = self.preparar(5)
        orden = self.s.crear_orden(self.cd, self.local, [(self.p, 5)])
        b2 = self.s.preparar_bulto(orden, "R2", [(self.p, 5)])
        self.s.precintar(b1, "s1")
        with pytest.raises(ErrorDominio):
            self.s.precintar(b2, " S1 ")
        assert self.s.historial_bulto(b2)[-1]["nuevo"] == "Preparado"

    def test_compra_repetida_no_duplica_stock_y_costos_son_exactos(self):
        """Verifica el rechazo de compras duplicadas y la precisión en centavos."""
        self.s.registrar_compra("C1", self.proveedor, self.cd, [(self.p, 3, "0,10")])
        assert self.s.listar("compras")[0]["total_centavos"] == 30
        with pytest.raises(ErrorDominio):
            self.s.registrar_compra(" c1 ", self.proveedor, self.cd, [(self.p, 3, "0.10")])
        assert self.saldo(self.cd)["disponible"] == 3

    def test_referencias_y_roles(self):
        """Verifica las restricciones de roles entre CD, locales y claves foráneas."""
        with pytest.raises(ErrorDominio):
            self.s.registrar_compra("C1", self.proveedor, self.local, [(self.p, 1, "1")])
        with pytest.raises(ErrorDominio):
            self.s.crear_orden(self.local, self.cd, [(self.p, 1)])
        with pytest.raises(ErrorDominio):
            self.s.guardar_producto("X", "Inexistente", 999, "1")
        with pytest.raises(ErrorDominio):
            self.s.guardar_ubicacion("CD2", "Otro CD", "Dirección", "CD")

    def test_identificadores_normalizados_y_actualizacion(self):
        """Verifica que los códigos duplicados se rechacen y las ediciones actualicen datos."""
        with pytest.raises(ErrorDominio):
            self.s.guardar_producto(" p ", "Duplicado", self.categoria, "2")
        with pytest.raises(ErrorDominio):
            self.s.guardar_proveedor("pr", "Duplicado")
        self.s.guardar_producto("P", "Descripción actualizada", self.categoria, "123.45", self.p)
        assert self.s.listar("productos")[0]["precio_centavos"] == 12345
        with pytest.raises(ErrorDominio):
            self.s.guardar_ubicacion("L1", "Local 1", "Dirección", "CD", self.local)

    def test_minimos_incluyen_saldo_cero(self):
        """Verifica el cálculo de faltantes cuando el saldo disponible es cero."""
        self.s.configurar_minimo(self.local, self.p, 7)
        assert (self.saldo(self.local)["disponible"], self.saldo(self.local)["faltante"]) == (0, 7)
        with pytest.raises(ErrorDominio):
            self.s.configurar_minimo(self.local, self.p, -1)

    def test_entradas_invalidas(self):
        """Verifica que se rechacen cantidades e importes fuera de formato."""
        for cantidad in (0, -1, "1.5", "NaN", "Infinity", True):
            with pytest.raises(ErrorDominio):
                self.s.crear_orden(self.cd, self.local, [(self.p, cantidad)])
        for valor in ("1.001", "-1", "NaN", "Infinity", "", False):
            with pytest.raises(ErrorDominio):
                centavos(valor)
        with pytest.raises(ErrorDominio):
            consolidar([])

    def test_dos_preparaciones_concurrentes_no_sobreasignan(self):
        """Verifica que dos hilos simultáneos no reserven más stock del disponible."""
        self.s.registrar_compra("C1", self.proveedor, self.cd, [(self.p, 10, "60")])
        orden = self.s.crear_orden(self.cd, self.local, [(self.p, 20)])
        barrera = Barrier(2)

        def preparar(numero):
            barrera.wait(timeout=5)
            try:
                self.s.preparar_bulto(orden, f"R{numero}", [(self.p, 6)])
                return True
            except ErrorDominio:
                return False

        with ThreadPoolExecutor(max_workers=2) as pool:
            resultados = list(pool.map(preparar, (1, 2)))
        assert sorted(resultados) == [False, True]
        assert (self.saldo(self.cd)["disponible"], self.saldo(self.cd)["reservado"]) == (4, 6)
