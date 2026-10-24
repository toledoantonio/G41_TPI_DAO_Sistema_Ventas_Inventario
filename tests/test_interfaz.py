from pathlib import Path
from tempfile import TemporaryDirectory
import tkinter as tk
import unittest
from unittest.mock import patch

from backend.demo import cargar_demo
from backend.services.sistema import Sistema
from frontend.app import Aplicacion


class InterfazTest(unittest.TestCase):
    def setUp(self):
        carpeta = Path(__file__).resolve().parents[1] / "tmp"
        carpeta.mkdir(exist_ok=True)
        self.temporal = TemporaryDirectory(dir=carpeta)
        self.addCleanup(self.temporal.cleanup)
        self.s = Sistema(Path(self.temporal.name) / "interfaz.sqlite3")
        cargar_demo(self.s)
        try:
            self.raiz = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f"Tk no está disponible: {error}")
        self.addCleanup(self.raiz.destroy)
        self.raiz.withdraw()
        self.app = Aplicacion(self.raiz, self.s)
        self.raiz.update()

    def test_formulario_producto_guarda_y_edita(self):
        editor = self.app.editores["productos"]
        categoria = self.s.listar("categorias")[0]["id"]
        editor.formulario.completar({"codigo": "P02", "descripcion": "Desde pantalla", "categoria_id": categoria,
                                     "precio_centavos": 321})
        editor.boton_guardar.invoke()
        producto = self.s.listar("productos")[1]
        self.assertEqual((producto["codigo"], producto["precio_centavos"]), ("P02", 321))
        iid = next(i for i, fila in editor.tabla.filas.items() if fila["id"] == producto["id"])
        editor.tabla.arbol.selection_set(iid)
        editor.editar()
        editor.formulario.variables["precio_centavos"].set("4.56")
        editor.boton_guardar.invoke()
        self.assertEqual(self.s.listar("productos")[1]["precio_centavos"], 456)

    def test_callbacks_logistica_y_actualizacion_inventario(self):
        local = next(u["id"] for u in self.s.listar("ubicaciones") if u["tipo"] == "LOCAL")
        self.app.bultos.arbol.selection_set("0")
        with patch("frontend.app.messagebox.showerror") as error:
            for accion in ("despachar", "recibir"):
                self.assertTrue(self.app.ejecutar(lambda a=accion: self.app.operar_bulto(a)))
            self.app.logistica_form.variables["precinto"].set("PRECINTO-DEMO-01")
            self.assertTrue(self.app.ejecutar(lambda: self.app.operar_bulto("verificar")))
            error.assert_not_called()
            self.assertFalse(self.app.ejecutar(lambda: self.app.operar_bulto("verificar")))
            error.assert_called_once()
        fila = next(f for f in self.app.inventario.filas.values() if f["ubicacion_id"] == local)
        self.assertEqual((fila["disponible"], fila["pendiente"]), (10, 0))

    def test_demo_no_repite_compra_ni_bulto(self):
        self.assertFalse(cargar_demo(self.s))
        self.assertEqual(len(self.s.listar("compras")), 1)
        self.assertEqual(len(self.s.listar("bultos")), 1)


if __name__ == "__main__":
    unittest.main()
