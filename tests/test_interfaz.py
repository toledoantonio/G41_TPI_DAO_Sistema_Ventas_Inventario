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

    def test_doble_click_en_agregar_renglon_no_repite_ni_muestra_error(self):
        renglones = self.app.orden_items
        renglones.formulario.variables["cantidad"].set("2")
        with patch("frontend.app.messagebox.showerror") as error:
            renglones.boton_agregar.invoke()
            renglones.boton_agregar.invoke()
            error.assert_not_called()
        assert [item["cantidad"] for item in renglones.items] == [2]
        assert renglones.boton_agregar.instate(["disabled"])

    def test_logistica_habilita_solo_la_accion_del_estado_y_agrupa_el_detalle(self):
        self.app.bultos.arbol.selection_set("0")
        self.raiz.update()
        botones = self.app.botones_logistica
        assert [nombre for nombre, boton in botones.items() if boton.instate(["!disabled"])] == ["despachar"]
        assert self.app.logistica_form.widgets["precinto"].instate(["readonly"])
        self.app.boton_detalle_bulto.invoke()
        detalle = self.app.ventana_bulto
        assert len(detalle.winfo_children()[0].tabs()) == 3
        self.app.boton_detalle_bulto.invoke()
        assert not detalle.winfo_exists()
        botones["despachar"].invoke()
        botones["recibir"].invoke()
        assert [nombre for nombre, boton in botones.items() if boton.instate(["!disabled"])] == ["verificar"]
        assert self.app.logistica_form.obtener("precinto") == ""
        assert self.app.bultos.seleccionada()["precinto"] == "PRECINTO-DEMO-01"

    def test_cobro_excesivo_conserva_lo_ya_ingresado(self):
        renglones = self.app.venta_items
        renglones.formulario.variables["cantidad"].set("1")
        renglones.boton_agregar.invoke()
        cobros = self.app.venta_cobros
        cobros.formulario.variables["importe"].set("40.00")
        cobros.boton_agregar.invoke()
        cobros.formulario.variables["importe"].set("61.00")
        with patch("frontend.app.messagebox.showerror") as error:
            cobros.boton_agregar.invoke()
            assert "60.00" in error.call_args.args[1]
        assert cobros.total_cobrado_centavos() == 4000
        renglones.tabla.arbol.selection_set("0")
        with patch("frontend.app.messagebox.showerror") as error:
            assert not self.app.ejecutar(renglones.quitar)
            error.assert_called_once()
        assert len(renglones.items) == 1
        cobros.boton_saldar.invoke()
        assert cobros.total_cobrado_centavos() == 10000

    def test_fechas_aceptan_digitos_y_marcan_fecha_imposible(self):
        formulario = self.app.reportes_vista.formulario
        formulario.variables["desde"].set("20261116")
        assert formulario.obtener("desde") == "2026-11-16"
        formulario.variables["desde"].set("2026-02-30")
        with patch("frontend.app.messagebox.showerror") as error:
            self.app.reportes_vista.boton_generar.invoke()
            assert "Desde" in error.call_args.args[1]
        assert formulario.bordes["desde"].cget("background") == "#a21b1b"

    def test_demo_no_repite_compra_ni_bulto(self):
        """Verifica que la carga de demostración no duplique registros en una base poblada."""
        assert not cargar_demo(self.s)
        assert len(self.s.listar("compras")) == 1
        assert len(self.s.listar("bultos")) == 1

    def test_opcionales_sugerencia_recepcion_lote_y_reapertura(self):
        """La sugerencia no crea stock; su compra completa sí registra un lote trazable."""
        producto = self.s.listar("productos")[0]["id"]
        cd = next(u["id"] for u in self.s.listar("ubicaciones") if u["tipo"] == "CD")
        self.s.configurar_minimo(cd, producto, 20)  # CD demo tiene 10 disponibles + 10 reservadas.
        vista = self.app.opcionales_vista
        vista.formulario.variables["referencia"].set("OC-UI-01")
        with patch("frontend.app.messagebox.showerror") as error:
            vista.boton_previsualizar.invoke()
            vista.boton_generar.invoke()
            error.assert_not_called()
        assert self.s.listar("compras_sugeridas")[0]["unidades"] == 10
        assert len(self.s.listar("compras")) == 1
        vista.ordenes.arbol.selection_set("0")
        vista.boton_recibir.invoke()
        assert self.app.orden_compra_seleccionada is not None
        f = self.app.compra_items.formulario
        f.variables["cantidad"].set("10")
        f.variables["costo"].set("65")
        f.variables["lote"].set("LOTE-UI-01")
        f.variables["vencimiento"].set("2099-12-31")
        self.app.compra_items.boton_agregar.invoke()
        with patch("frontend.app.messagebox.showerror") as error:
            assert self.app.ejecutar(self.app.confirmar_compra)
            error.assert_not_called()
        assert self.s.listar("compras_sugeridas")[0]["estado"] == "RECIBIDA"
        assert any(l["codigo"] == "LOTE-UI-01" and l["disponible"] == 10 for l in self.s.listar("lotes"))
        assert self.app.orden_compra_seleccionada is None
        ruta = self.s.db.ruta
        BaseDatos.reset_for_testing()
        reabierta = Sistema(ruta)
        assert reabierta.listar("compras_sugeridas")[0]["estado"] == "RECIBIDA"
        lote = next(l for l in reabierta.listar("lotes") if l["codigo"] == "LOTE-UI-01")
        assert reabierta.trazabilidad_lote(lote["lote_id"])[0]["causa"] == "COMPRA"

    def test_devolucion_reportes_y_exportacion_desde_interfaz(self):
        """Compra demo → logística → venta → devolución → cuatro reportes → CSV → reapertura."""
        self.test_callbacks_logistica_venta_y_actualizacion_inventario()
        vista = self.app.devoluciones_vista
        vista.boton_cargar.invoke()
        vista.originales.arbol.selection_set("0")
        vista.detalle_form.variables["cantidad"].set("1")
        vista.boton_agregar.invoke()
        with patch("frontend.app.messagebox.showerror") as error:
            vista.boton_confirmar.invoke()
            assert "referencia única de devolución" in error.call_args.args[1]
        assert vista.formulario.bordes["referencia"].cget("background") == "#a21b1b"
        assert vista.formulario.bordes["motivo"].cget("background") == "#a21b1b"
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
            grafico = reportes.secciones.nametowidget(reportes.secciones.tabs()[0])
            assert reportes.secciones.tab(grafico, "text") == "Gráfico"
            if tipo != "rechazos_precinto":
                assert grafico.filas
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
