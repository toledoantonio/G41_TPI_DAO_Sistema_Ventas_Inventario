"""Pruebas de interfaz gráfica y colaboración con servicios usando pytest (Cap. 12)."""

from pathlib import Path
from tempfile import TemporaryDirectory
import tkinter as tk
from unittest.mock import patch
import pytest

from backend.database.config import BaseDatos
from backend.demo import cargar_demo
from backend.services.sistema import Sistema
from frontend.app import Aplicacion


class TestInterfaz:
    """Suite de pruebas para los formularios y manejadores de eventos de la pantalla."""

    @classmethod
    def setup_class(cls):
        try:
            cls.raiz = tk.Tk()
            cls.raiz.withdraw()
        except tk.TclError as error:
            cls.raiz = None
            cls.error_tk = error

    @classmethod
    def teardown_class(cls):
        if getattr(cls, "raiz", None) is not None:
            cls.raiz.update_idletasks()
            cls.raiz.destroy()
            cls.raiz = None

    def setup_method(self):
        BaseDatos.reset_for_testing()
        if self.raiz is None:
            pytest.skip(f"Tk no está disponible: {self.error_tk}")
        for widget in self.raiz.winfo_children():
            widget.destroy()
        carpeta = Path(__file__).resolve().parents[1] / "tmp"
        carpeta.mkdir(exist_ok=True)
        self.temporal = TemporaryDirectory(dir=carpeta)
        self.s = Sistema(Path(self.temporal.name) / "interfaz.sqlite3")
        cargar_demo(self.s)
        self.app = Aplicacion(self.raiz, self.s)
        self.raiz.update()

    def teardown_method(self):
        if hasattr(self, "app"):
            for widget in self.raiz.winfo_children():
                widget.destroy()
            del self.app
        BaseDatos.reset_for_testing()
        self.temporal.cleanup()

    def test_formulario_producto_guarda_y_edita(self):
        """Verifica el alta y la edición de un producto desde el formulario de catálogo."""
        editor = self.app.editores["productos"]
        categoria = self.s.listar("categorias")[0]["id"]
        editor.formulario.completar(
            {"codigo": "P02", "descripcion": "Desde pantalla", "categoria_id": categoria, "precio_centavos": 321}
        )
        editor.boton_guardar.invoke()
        producto = self.s.listar("productos")[1]
        assert (producto["codigo"], producto["precio_centavos"]) == ("P02", 321)

        iid = next(i for i, fila in editor.tabla.filas.items() if fila["id"] == producto["id"])
        editor.tabla.arbol.selection_set(iid)
        editor.editar()
        editor.formulario.variables["precio_centavos"].set("4.56")
        editor.boton_guardar.invoke()
        assert self.s.listar("productos")[1]["precio_centavos"] == 456

    def test_callbacks_logistica_venta_y_actualizacion_inventario(self):
        """Verifica logística, verificación de costo y registro de venta desde la pantalla."""
        local = next(u["id"] for u in self.s.listar("ubicaciones") if u["tipo"] == "LOCAL")
        self.app.bultos.arbol.selection_set("0")
        with patch("frontend.app.messagebox.showerror") as error:
            for accion in ("despachar", "recibir"):
                assert self.app.ejecutar(lambda a=accion: self.app.operar_bulto(a))
            self.app.logistica_form.variables["precinto"].set("PRECINTO-DEMO-01")
            assert self.app.ejecutar(lambda: self.app.operar_bulto("verificar"))
            error.assert_not_called()
            assert not self.app.ejecutar(lambda: self.app.operar_bulto("verificar"))
            error.assert_called_once()

        fila = next(f for f in self.app.inventario.filas.values() if f["ubicacion_id"] == local)
        assert (fila["disponible"], fila["pendiente"], fila["costo_centavos"]) == (10, 0, 6000)

        # Registrar una venta de 3 unidades desde la pestaña 6 de la interfaz
        self.app.venta_items.formulario.variables["cantidad"].set("3")
        self.app.venta_items.boton_agregar.invoke()
        self.app.venta_cobros.boton_saldar.invoke()
        self.app.boton_confirmar_venta.invoke()

        ventas = self.s.listar("ventas")
        assert len(ventas) == 1
        assert (ventas[0]["unidades"], ventas[0]["total_centavos"], ventas[0]["costo_total_centavos"]) == (
            3,
            30000,
            18000,
        )
        fila_post = next(f for f in self.app.inventario.filas.values() if f["ubicacion_id"] == local)
        assert fila_post["disponible"] == 7

    def test_demo_no_repite_compra_ni_bulto(self):
        """Verifica que la carga de demostración no duplique registros en una base poblada."""
        assert not cargar_demo(self.s)
        assert len(self.s.listar("compras")) == 1
        assert len(self.s.listar("bultos")) == 1

    def test_devolucion_reportes_y_exportacion_desde_interfaz(self):
        """Compra demo → logística → venta → devolución → cuatro reportes → CSV → reapertura."""
        self.test_callbacks_logistica_venta_y_actualizacion_inventario()
        vista = self.app.devoluciones_vista
        vista.boton_cargar.invoke()
        vista.originales.arbol.selection_set("0")
        vista.detalle_form.variables["cantidad"].set("1")
        vista.boton_agregar.invoke()
        vista.formulario.variables["referencia"].set("DEV-UI-01")
        vista.formulario.variables["motivo"].set("Retorno inspeccionado")
        with patch("frontend.app.messagebox.showerror") as error:
            vista.boton_confirmar.invoke()
            error.assert_not_called()
        devoluciones = self.s.listar("devoluciones")
        assert len(devoluciones) == 1 and devoluciones[0]["total_centavos"] == 10000
        assert next(f for f in self.app.inventario.filas.values() if f["ubicacion_id"] == devoluciones[0]["local_id"])["disponible"] == 8
        reportes = self.app.reportes_vista
        from backend.reports.generador_reportes import REPORTES

        for tipo in REPORTES:
            reportes.formulario.completar({"tipo": tipo, "desde": "", "hasta": "", "ubicacion": "TODAS", "medio": "TODOS"})
            reportes.ajustar_filtros()
            with patch("frontend.app.messagebox.showerror") as error:
                reportes.boton_generar.invoke()
                error.assert_not_called()
            assert reportes.resultado["tipo"] == tipo
            assert len(reportes.tablas) == len(reportes.resultado["secciones"])
            ruta_csv = Path(self.temporal.name) / f"{tipo}.csv"
            with patch("frontend.devoluciones_reportes.filedialog.asksaveasfilename", return_value=str(ruta_csv)):
                reportes.exportar()
            assert reportes.resultado["titulo"] in ruta_csv.read_text(encoding="utf-8-sig")
        ruta = self.s.db.ruta
        BaseDatos.reset_for_testing()
        reabierto = Sistema(ruta)
        assert reabierto.obtener_devolucion(devoluciones[0]["id"])["total_centavos"] == 10000
        fila = reabierto.generar_reporte("ventas_ingresos")["secciones"][0]["filas"][0]
        assert fila["neto_centavos"] == 20000
