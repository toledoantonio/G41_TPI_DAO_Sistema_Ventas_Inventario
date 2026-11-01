"""Pantallas de devoluciones y reportes; toda regla de negocio queda en servicios."""

import tkinter as tk
from tkinter import filedialog, ttk

from backend.models.entidades import entero, importe
from backend.patterns.estados_bulto import ErrorDominio
from backend.reports.generador_reportes import REPORTES, exportar_csv
from frontend.app import Formulario, MEDIOS_PAGO, Tabla


class VistaDevoluciones(ttk.Frame):
    def __init__(self, padre, app):
        super().__init__(padre)
        self.app, self.sistema = app, app.sistema
        self.venta_cargada = None
        self.items = []
        ttk.Label(self, text="Seleccione y cargue una venta. El reintegro usa su precio original; la condición define si vuelve a Disponible.",
                  wraplength=1100).pack(anchor="w")
        documentos = ttk.Notebook(self)
        documentos.pack(fill="both", expand=True, pady=5)
        nuevo, historial = ttk.Frame(documentos), ttk.Frame(documentos)
        documentos.add(nuevo, text="Nueva devolución")
        documentos.add(historial, text="Historial y consulta")
        self.formulario = Formulario(nuevo, [
            ("venta", "Venta original", lambda: [(v["id"], f"{v['comprobante']} · {v['local']}") for v in self.sistema.listar("ventas")]),
            ("local", "Local de devolución", app.opciones("ubicaciones", "LOCAL")),
            ("referencia", "Referencia única de devolución", None),
            ("motivo", "Motivo", None),
            ("medio", "Medio de reintegro", lambda: MEDIOS_PAGO),
        ])
        self.formulario.pack(fill="x")
        self.boton_cargar = ttk.Button(nuevo, text="Cargar venta y cantidades devolvibles", command=lambda: app.ejecutar(self.cargar_venta))
        self.boton_cargar.pack(anchor="w", pady=4)
        self.originales = Tabla(nuevo, [
            ("id", "Detalle original"), ("codigo", "Producto"), ("cantidad", "Vendida"),
            ("devuelta", "Ya devuelta"), ("restante", "Devolvible"), ("precio_unitario_centavos", "Precio original"),
        ], alto=3)
        self.originales.pack(fill="both", expand=True)
        self.detalle_form = Formulario(nuevo, [
            ("cantidad", "Unidades del detalle seleccionado", None),
            ("condicion", "Condición inspeccionada", lambda: [("VENDIBLE", "Vendible"), ("NO_VENDIBLE", "No vendible / bloqueada")]),
            ("lote", "Lote retornado", self.opciones_lotes),
        ])
        self.originales.arbol.bind("<<TreeviewSelect>>", lambda _: self.detalle_form.actualizar())
        self.detalle_form.pack(fill="x")
        acciones = ttk.Frame(nuevo)
        acciones.pack(fill="x", pady=4)
        self.boton_agregar = ttk.Button(acciones, text="Agregar detalle seleccionado", command=lambda: app.ejecutar(self.agregar))
        self.boton_agregar.pack(side="left")
        ttk.Button(acciones, text="Quitar renglón", command=lambda: app.ejecutar(self.quitar)).pack(side="left", padx=8)
        self.resumen = tk.StringVar(value="Reintegro: 0.00")
        ttk.Label(acciones, textvariable=self.resumen).pack(side="left", padx=12)
        self.renglones = Tabla(nuevo, [
            ("detalle_id", "Detalle"), ("codigo", "Producto"), ("cantidad", "Cantidad"),
            ("condicion", "Condición"), ("reintegro_centavos", "Reintegro original"),
            ("lote", "Lote"),
        ], alto=3)
        self.renglones.pack(fill="both", expand=True)
        self.boton_confirmar = ttk.Button(nuevo, text="Confirmar devolución, stock y reintegro", command=lambda: app.ejecutar(self.confirmar))
        self.boton_confirmar.pack(anchor="w", pady=5)
        self.historial = Tabla(historial, [
            ("id", "Devolución"), ("referencia", "Referencia"), ("comprobante", "Venta original"),
            ("local", "Local"), ("fecha", "Fecha"), ("total_centavos", "Reintegro"),
        ], alto=3)
        self.historial.pack(fill="both", expand=True)
        ttk.Button(historial, text="Consultar detalle y motivo", command=lambda: app.ejecutar(self.ver_detalle)).pack(anchor="w", pady=4)
        app.refrescadores.extend([self.formulario.actualizar, lambda: self.historial.cargar(self.sistema.listar("devoluciones"))])

    def cargar_venta(self):
        self.venta_cargada = self.formulario.obtener("venta")
        venta = self.sistema.obtener_venta(self.venta_cargada)
        self.formulario.completar({
            "venta": self.venta_cargada, "local": venta.local_id, "referencia": "", "motivo": "",
            "medio": self.formulario.obtener("medio"),
        })
        self.items.clear()
        self.refrescar_detalles()
        self.refrescar_items()
        return "Venta cargada. Seleccione un detalle e indique cantidad y condición."

    def refrescar_detalles(self):
        filas = self.sistema.detalles_devolvibles(self.venta_cargada)
        self.originales.cargar([dict(f, restante=f["cantidad"] - f["devuelta"]) for f in filas])

    def validar_venta_cargada(self):
        if self.venta_cargada is None or self.formulario.obtener("venta") != self.venta_cargada:
            raise ErrorDominio("Cargue la venta seleccionada antes de agregar o confirmar detalles.")

    def opciones_lotes(self):
        if not self.originales.arbol.selection():
            return []
        return [(f["lote_id"], f"{f['codigo']} · devolvible {f['restante']} · vence {f['vencimiento'] or 'sin fecha'}")
                for f in self.sistema.lotes_devolvibles(self.originales.seleccionada()["id"]) if f["restante"] > 0]

    def agregar(self):
        self.validar_venta_cargada()
        original = self.originales.seleccionada()
        self.detalle_form.actualizar()
        cantidad = entero(self.detalle_form.obtener("cantidad"))
        agregada = sum(i["cantidad"] for i in self.items if i["detalle_id"] == original["id"])
        if cantidad + agregada > original["restante"]:
            raise ErrorDominio("Los renglones superan la cantidad devolvible del detalle.")
        self.items.append({
            "id": len(self.items), "detalle_id": original["id"], "codigo": original["codigo"],
            "cantidad": cantidad, "condicion": self.detalle_form.obtener("condicion"),
            "reintegro_centavos": cantidad * original["precio_unitario_centavos"],
            "lote_id": self.detalle_form.obtener("lote"), "lote": self.detalle_form.variables["lote"].get(),
        })
        self.detalle_form.limpiar()
        self.refrescar_items()

    def refrescar_items(self):
        for indice, item in enumerate(self.items):
            item["id"] = indice
        self.renglones.cargar(self.items)
        self.resumen.set(f"Reintegro al precio original: {importe(sum(i['reintegro_centavos'] for i in self.items))}")

    def quitar(self):
        self.items.remove(self.renglones.seleccionada())
        self.refrescar_items()

    def confirmar(self):
        self.validar_venta_cargada()
        f = self.formulario
        identificador = self.sistema.registrar_devolucion(
            self.venta_cargada, f.obtener("local"),
            [(i["detalle_id"], i["cantidad"], i["condicion"], i["lote_id"]) for i in self.items],
            f.obtener("medio"), f.obtener("motivo"), f.obtener("referencia"),
        )
        self.items.clear()
        self.formulario.limpiar()
        self.refrescar_items()
        self.refrescar_detalles()
        return f"Devolución {identificador} registrada; stock y reintegro confirmados juntos."

    def ver_detalle(self):
        dev = self.sistema.obtener_devolucion(self.historial.seleccionada()["id"])
        self.app.mostrar_tabla(
            f"Devolución {dev['referencia']} · {dev['motivo']} · Reintegro {dev['medio_reintegro']}",
            dev["detalles"], [("codigo", "Producto"), ("cantidad", "Unidades"), ("condicion", "Condición"),
                              ("precio_unitario_centavos", "Precio original"), ("reintegro_centavos", "Reintegro")],
        )


class VistaReportes(ttk.Frame):
    def __init__(self, padre, app):
        super().__init__(padre)
        self.app = app
        self.resultado = None
        self.tablas = []
        ttk.Label(self, text="Fechas inclusivas AAAA-MM-DD; vacías incluyen todo el historial. Existencias muestra la situación actual.",
                  wraplength=1100).pack(anchor="w")
        self.formulario = Formulario(self, [
            ("tipo", "Reporte", lambda: list(REPORTES.items())),
            ("desde", "Desde", None), ("hasta", "Hasta", None),
            ("ubicacion", "Ubicación / local", lambda: [("TODAS", "Todas")] + app.opciones("ubicaciones")()),
            ("medio", "Medio (solo sección caja)", lambda: [("TODOS", "Todos")] + [
                (m, m) for m in sorted({m[0] for m in MEDIOS_PAGO} | {f["medio_pago"] for f in app.sistema.listar("caja")})]),
        ])
        self.formulario.pack(fill="x")
        self.formulario.widgets["tipo"].bind("<<ComboboxSelected>>", lambda _: self.ajustar_filtros())
        acciones = ttk.Frame(self)
        acciones.pack(fill="x", pady=8)
        self.boton_generar = ttk.Button(acciones, text="Generar reporte", command=lambda: app.ejecutar(self.generar))
        self.boton_generar.pack(side="left")
        ttk.Button(acciones, text="Exportar resultado a CSV", command=lambda: app.ejecutar(self.exportar)).pack(side="left", padx=8)
        self.notas = tk.StringVar(value="Seleccione un reporte y pulse Generar. La exportación conserva los filtros del resultado generado.")
        ttk.Label(self, textvariable=self.notas, wraplength=1100).pack(anchor="w", pady=5)
        self.secciones = ttk.Notebook(self)
        self.secciones.pack(fill="both", expand=True)
        app.refrescadores.append(self.formulario.actualizar)
        self.ajustar_filtros()

    def ajustar_filtros(self):
        tipo = self.formulario.obtener("tipo")
        for campo in ("desde", "hasta"):
            if tipo == "existencias_minimos":
                self.formulario.variables[campo].set("")
            self.formulario.widgets[campo].configure(state="disabled" if tipo == "existencias_minimos" else "normal")
        if tipo != "ventas_ingresos":
            self.formulario.variables["medio"].set("TODOS · Todos")
        self.formulario.widgets["medio"].configure(state="readonly" if tipo == "ventas_ingresos" else "disabled")

    def generar(self):
        f = self.formulario
        ubicacion, medio = f.obtener("ubicacion"), f.obtener("medio")
        reporte = self.app.sistema.generar_reporte(
            f.obtener("tipo"), f.obtener("desde"), f.obtener("hasta"),
            None if ubicacion == "TODAS" else ubicacion, None if medio == "TODOS" else medio,
        )
        for identificador in self.secciones.tabs():
            self.secciones.nametowidget(identificador).destroy()
        self.tablas.clear()
        for seccion in reporte["secciones"]:
            panel = ttk.Frame(self.secciones)
            self.secciones.add(panel, text=seccion["nombre"])
            ttk.Label(panel, text=f"{len(seccion['filas'])} filas" if seccion["filas"] else "Sin datos para estos filtros.").pack(anchor="w")
            tabla = Tabla(panel, seccion["columnas"], alto=12)
            tabla.pack(fill="both", expand=True)
            tabla.cargar(seccion["filas"])
            self.tablas.append(tabla)
        self.resultado = reporte
        self.notas.set(reporte["notas"])
        return f"{reporte['titulo']} generado. Cambiar filtros requiere volver a generar."

    def exportar(self):
        if self.resultado is None:
            raise ErrorDominio("Genere un reporte antes de exportar.")
        ruta = filedialog.asksaveasfilename(parent=self.app.raiz, title="Exportar reporte",
                                          defaultextension=".csv", filetypes=[("CSV", "*.csv")],
                                          initialfile=f"{self.resultado['tipo']}.csv")
        if ruta:
            exportar_csv(self.resultado, ruta)
            return "Reporte exportado con sus filtros y secciones."
        return "Exportación cancelada."
