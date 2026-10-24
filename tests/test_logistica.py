from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from threading import Barrier
import unittest

from backend.models.entidades import centavos, consolidar
from backend.patterns.estados_bulto import ErrorDominio
from backend.services.sistema import Sistema


class FlujoLogisticoTest(unittest.TestCase):
    def setUp(self):
        carpeta = Path(__file__).resolve().parents[1] / "tmp"
        carpeta.mkdir(exist_ok=True)
        self.temporal = TemporaryDirectory(dir=carpeta)
        self.addCleanup(self.temporal.cleanup)
        self.ruta = Path(self.temporal.name) / "prueba.sqlite3"
        self.s = Sistema(self.ruta)
        self.cd = self.s.guardar_ubicacion("CD", "Depósito", "Dirección CD", "CD")
        self.local = self.s.guardar_ubicacion("L1", "Local 1", "Dirección L1", "LOCAL")
        self.categoria = self.s.guardar_categoria("Categoría")
        self.proveedor = self.s.guardar_proveedor("PR", "Proveedor")
        self.p = self.s.guardar_producto("P", "Producto", self.categoria, "100.00")
        self.q = self.s.guardar_producto("Q", "Otro producto", self.categoria, "50.00")

    def saldo(self, ubicacion, producto=None):
        return next(f for f in self.s.listar("inventario") if f["ubicacion_id"] == ubicacion
                    and f["producto_id"] == (producto or self.p))

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

    def test_recorrido_persistencia_historial_y_reconciliacion(self):
        bulto = self.preparar()
        self.assertEqual((self.saldo(self.cd)["disponible"], self.saldo(self.cd)["reservado"]), (10, 10))
        self.s.precintar(bulto, "S1")
        self.s.despachar(bulto)
        self.assertEqual((self.saldo(self.cd)["disponible"], self.saldo(self.cd)["reservado"]), (10, 0))
        self.assertEqual(self.saldo(self.local)["disponible"], 0)
        self.s.recibir(bulto, self.local)
        self.assertEqual((self.saldo(self.local)["pendiente"], self.saldo(self.local)["disponible"]), (10, 0))
        self.s.verificar(bulto, self.local, "s1")
        self.s = Sistema(self.ruta)
        self.assertEqual((self.saldo(self.local)["pendiente"], self.saldo(self.local)["disponible"]), (0, 10))
        fila = self.s.listar("bultos")[0]
        self.assertEqual((fila["estado"], fila["estado_remito"]), ("Verificado", "Verificado"))
        self.assertEqual([h["nuevo"] for h in self.s.historial_bulto(bulto)],
                         ["Preparado", "Precintado", "En tránsito", "Recibido", "Verificado"])
        for ubicacion in (self.cd, self.local):
            sumas = self.consultar(f"""SELECT SUM(disponible), SUM(reservado), SUM(pendiente), SUM(rechazado)
                FROM movimiento_inventario WHERE ubicacion_id = {ubicacion} AND producto_id = {self.p}""")[0]
            self.assertEqual(tuple(sumas), tuple(self.saldo(ubicacion)[k]
                             for k in ("disponible", "reservado", "pendiente", "rechazado")))

    def test_precinto_roto_no_habilita_ni_retorna_cd(self):
        bulto = self.recibir()
        self.s.verificar(bulto, self.local, "S1", True, "Sello cortado")
        self.assertEqual((self.saldo(self.local)["disponible"], self.saldo(self.local)["rechazado"]), (0, 10))
        self.assertEqual(self.saldo(self.cd)["disponible"], 10)
        self.assertEqual(self.s.listar("bultos")[0]["estado_remito"], "Rechazado")
        self.assertIn("Sello cortado", self.s.historial_bulto(bulto)[-1]["observacion"])

    def test_codigo_precinto_distinto_sigue_pendiente(self):
        bulto = self.recibir()
        with self.assertRaises(ErrorDominio):
            self.s.verificar(bulto, self.local, "OTRO")
        self.assertEqual(self.s.listar("bultos")[0]["estado"], "Recibido")
        self.assertEqual(self.saldo(self.local)["pendiente"], 10)
        self.assertEqual(len(self.s.historial_bulto(bulto)), 4)

    def test_rechazo_requiere_motivo(self):
        bulto = self.recibir()
        with self.assertRaises(ErrorDominio):
            self.s.verificar(bulto, self.local, "S1", True)
        self.assertEqual(self.s.listar("bultos")[0]["estado_remito"], "Pendiente")

    def test_state_rechaza_saltos_y_operaciones_duplicadas(self):
        bulto = self.preparar()
        for operacion in (lambda: self.s.despachar(bulto), lambda: self.s.recibir(bulto, self.local),
                          lambda: self.s.verificar(bulto, self.local, "S1")):
            with self.assertRaises(ErrorDominio):
                operacion()
        self.assertEqual(len(self.s.historial_bulto(bulto)), 1)
        self.s.precintar(bulto, "S1")
        self.s.despachar(bulto)
        with self.assertRaises(ErrorDominio):
            self.s.despachar(bulto)
        self.s.recibir(bulto, self.local)
        with self.assertRaises(ErrorDominio):
            self.s.recibir(bulto, self.local)
        self.s.verificar(bulto, self.local, "S1")
        with self.assertRaises(ErrorDominio):
            self.s.verificar(bulto, self.local, "S1")
        self.assertEqual(self.saldo(self.local)["disponible"], 10)
        self.assertEqual(len(self.s.historial_bulto(bulto)), 5)

    def test_destino_equivocado_no_registra_llegada(self):
        bulto = self.preparar()
        otro = self.s.guardar_ubicacion("L2", "Local 2", "Dirección 2", "LOCAL")
        self.s.precintar(bulto, "S1")
        self.s.despachar(bulto)
        with self.assertRaises(ErrorDominio):
            self.s.recibir(bulto, otro)
        self.assertEqual(self.s.listar("bultos")[0]["estado"], "En tránsito")
        self.assertEqual(self.saldo(otro)["pendiente"], 0)

    def test_historial_no_se_modifica_ni_borra(self):
        self.preparar()
        for sql in ("UPDATE historial_bulto SET nuevo = 'Verificado'", "DELETE FROM historial_bulto"):
            with self.assertRaises(sqlite3.IntegrityError):
                with self.s.db.transaccion() as cx:
                    cx.execute(sql)
        self.assertEqual(self.consultar("SELECT COUNT(*) FROM historial_bulto")[0][0], 1)

    def test_fallo_en_historial_revierte_estado_remito_y_stock(self):
        bulto = self.recibir()
        with self.s.db.transaccion() as cx:
            cx.execute("""CREATE TRIGGER fallo_prueba BEFORE INSERT ON historial_bulto
                WHEN NEW.nuevo = 'Verificado' BEGIN SELECT RAISE(ABORT, 'fallo simulado'); END""")
        with self.assertRaises(ErrorDominio):
            self.s.verificar(bulto, self.local, "S1")
        fila = self.s.listar("bultos")[0]
        self.assertEqual((fila["estado"], fila["estado_remito"]), ("Recibido", "Pendiente"))
        self.assertEqual((self.saldo(self.local)["disponible"], self.saldo(self.local)["pendiente"]), (0, 10))
        self.assertEqual(self.consultar("SELECT COUNT(*) FROM movimiento_inventario WHERE causa = 'VERIFICACION'")[0][0], 0)

    def test_sin_stock_revierte_bulto_remito_reservas_y_detalles(self):
        self.s.registrar_compra("C1", self.proveedor, self.cd, [(self.p, 20, "60")])
        orden = self.s.crear_orden(self.cd, self.local, [(self.p, 10), (self.q, 5)])
        with self.assertRaises(ErrorDominio):
            self.s.preparar_bulto(orden, "R1", [(self.p, 10), (self.q, 5)])
        self.assertEqual(self.saldo(self.cd)["disponible"], 20)
        self.assertEqual(self.saldo(self.cd)["reservado"], 0)
        self.assertEqual(self.s.listar("bultos"), [])
        self.assertEqual(self.consultar("SELECT COUNT(*) FROM remito")[0][0], 0)

    def test_consolidacion_y_despachos_parciales(self):
        self.s.registrar_compra("C1", self.proveedor, self.cd, [(self.p, 20, "60")])
        orden = self.s.crear_orden(self.cd, self.local, [(self.p, 4), (self.p, 6)])
        b1 = self.s.preparar_bulto(orden, "R1", [(self.p, 3), (self.p, 2)])
        b2 = self.s.preparar_bulto(orden, "R2", [(self.p, 5)])
        self.assertNotEqual(b1, b2)
        self.assertEqual(self.s.detalle_orden(orden)[0]["pendiente"], 0)
        with self.assertRaises(ErrorDominio):
            self.s.preparar_bulto(orden, "R3", [(self.p, 1)])
        self.assertEqual(len(self.s.listar("bultos")), 2)

    def test_cada_bulto_tiene_remito_y_rechazo_no_bloquea_otro(self):
        b1 = self.preparar(5)
        orden = self.s.crear_orden(self.cd, self.local, [(self.p, 5)])
        b2 = self.s.preparar_bulto(orden, "R2", [(self.p, 5)])
        for bulto, precinto in ((b1, "S1"), (b2, "S2")):
            self.s.precintar(bulto, precinto)
            self.s.despachar(bulto)
            self.s.recibir(bulto, self.local)
        self.s.verificar(b1, self.local, "S1", True, "Rotura")
        self.s.verificar(b2, self.local, "S2")
        self.assertEqual((self.saldo(self.local)["disponible"], self.saldo(self.local)["rechazado"]), (5, 5))

    def test_precinto_unico_global(self):
        b1 = self.preparar(5)
        orden = self.s.crear_orden(self.cd, self.local, [(self.p, 5)])
        b2 = self.s.preparar_bulto(orden, "R2", [(self.p, 5)])
        self.s.precintar(b1, "s1")
        with self.assertRaises(ErrorDominio):
            self.s.precintar(b2, " S1 ")
        self.assertEqual(self.s.historial_bulto(b2)[-1]["nuevo"], "Preparado")

    def test_compra_repetida_no_duplica_stock_y_costos_son_exactos(self):
        self.s.registrar_compra("C1", self.proveedor, self.cd, [(self.p, 3, "0,10")])
        self.assertEqual(self.s.listar("compras")[0]["total_centavos"], 30)
        with self.assertRaises(ErrorDominio):
            self.s.registrar_compra(" c1 ", self.proveedor, self.cd, [(self.p, 3, "0.10")])
        self.assertEqual(self.saldo(self.cd)["disponible"], 3)

    def test_referencias_y_roles(self):
        with self.assertRaises(ErrorDominio):
            self.s.registrar_compra("C1", self.proveedor, self.local, [(self.p, 1, "1")])
        with self.assertRaises(ErrorDominio):
            self.s.crear_orden(self.local, self.cd, [(self.p, 1)])
        with self.assertRaises(ErrorDominio):
            self.s.guardar_producto("X", "Inexistente", 999, "1")
        with self.assertRaises(ErrorDominio):
            self.s.guardar_ubicacion("CD2", "Otro CD", "Dirección", "CD")

    def test_identificadores_normalizados_y_actualizacion(self):
        with self.assertRaises(ErrorDominio):
            self.s.guardar_producto(" p ", "Duplicado", self.categoria, "2")
        with self.assertRaises(ErrorDominio):
            self.s.guardar_proveedor("pr", "Duplicado")
        self.s.guardar_producto("P", "Descripción actualizada", self.categoria, "123.45", self.p)
        self.assertEqual(self.s.listar("productos")[0]["precio_centavos"], 12345)
        with self.assertRaises(ErrorDominio):
            self.s.guardar_ubicacion("L1", "Local 1", "Dirección", "CD", self.local)

    def test_minimos_incluyen_saldo_cero(self):
        self.s.configurar_minimo(self.local, self.p, 7)
        self.assertEqual((self.saldo(self.local)["disponible"], self.saldo(self.local)["faltante"]), (0, 7))
        with self.assertRaises(ErrorDominio):
            self.s.configurar_minimo(self.local, self.p, -1)

    def test_entradas_invalidas(self):
        for cantidad in (0, -1, "1.5", "NaN", "Infinity"):
            with self.subTest(cantidad=cantidad), self.assertRaises(ErrorDominio):
                self.s.crear_orden(self.cd, self.local, [(self.p, cantidad)])
        for valor in ("1.001", "-1", "NaN", "Infinity", ""):
            with self.subTest(valor=valor), self.assertRaises(ErrorDominio):
                centavos(valor)
        with self.assertRaises(ErrorDominio):
            consolidar([])

    def test_dos_preparaciones_concurrentes_no_sobreasignan(self):
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
        self.assertEqual(sorted(resultados), [False, True])
        self.assertEqual((self.saldo(self.cd)["disponible"], self.saldo(self.cd)["reservado"]), (4, 6))


if __name__ == "__main__":
    unittest.main()
