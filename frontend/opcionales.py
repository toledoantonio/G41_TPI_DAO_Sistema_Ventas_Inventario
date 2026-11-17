"""Compras sugeridas y consulta de lotes con trazabilidad y vencimientos."""

from tkinter import ttk

from backend.patterns.estados_bulto import ErrorDominio
from frontend.app import Formulario, Tabla


class VistaOpcionales(ttk.Frame):
    def __init__(self, padre, app):
        super().__init__(padre)
        self.app, self.sistema = app, app.sistema
        secciones = ttk.Notebook(self)
        secciones.pack(fill="both", expand=True)
        compras, lotes = ttk.Frame(secciones), ttk.Frame(secciones)
        secciones.add(compras, text="Órdenes de compra sugeridas")
        secciones.add(lotes, text="Lotes y vencimientos")
        ttk.Label(compras, text="Calcula necesidad de locales y mínimo del CD, descontando stock no vencido, bultos en camino y sugerencias pendientes. Generar no ingresa mercadería.",
                  wraplength=1080).pack(anchor="w", pady=5)
        self.formulario = Formulario(compras, [
            ("cd", "CD receptor", app.opciones("ubicaciones", "CD")),
            ("proveedor", "Proveedor elegido para la compra", app.opciones("proveedores")),
            ("referencia", "Referencia única de orden sugerida", None),
        ])
        self.formulario.pack(fill="x")
        acciones = ttk.Frame(compras)
        acciones.pack(fill="x", pady=5)
        self.boton_previsualizar = ttk.Button(acciones, text="Consultar faltantes", command=lambda: app.ejecutar(self.previsualizar))
        self.boton_previsualizar.pack(side="left")
        self.boton_generar = ttk.Button(acciones, text="Generar orden por faltantes actuales", style="Principal.TButton",
                                       command=lambda: app.ejecutar(self.generar))
        self.boton_generar.pack(side="left", padx=8)
        self.necesidades = Tabla(compras, [
            ("codigo", "Producto"), ("minimo_cd", "Mínimo CD"), ("disponible_cd", "Vendible CD"),
            ("necesidad_locales", "Necesidad locales"), ("compras_pendientes", "Compras pendientes"),
            ("cantidad_sugerida", "Cantidad sugerida"),
        ], alto=4)
        self.necesidades.pack(fill="both", expand=True)
        self.ordenes = Tabla(compras, [
            ("id", "Orden"), ("referencia", "Referencia"), ("proveedor", "Proveedor"),
            ("estado", "Estado"), ("unidades", "Unidades"), ("compra_id", "Compra recibida"),
        ], alto=4)
        self.ordenes.pack(fill="both", expand=True, pady=6)
        botones = ttk.Frame(compras)
        botones.pack(fill="x")
        ttk.Button(botones, text="Ver productos y cantidades", command=lambda: app.ejecutar(self.ver_detalle)).pack(side="left")
        self.boton_recibir = ttk.Button(botones, text="Preparar recepción en Compras", style="Principal.TButton",
                                       command=lambda: app.ejecutar(self.preparar_recepcion))
        self.boton_recibir.pack(side="left", padx=8)
        ttk.Button(botones, text="Cancelar sugerencia pendiente", command=lambda: app.ejecutar(self.cancelar)).pack(side="left")
        ttk.Label(compras, text="La recepción es completa: registrar en Compras los productos, cantidades, costos y lotes reales. Cancelar libera la cobertura de compra pendiente; no borra la orden.",
                  wraplength=1080).pack(anchor="w", pady=8)
        ttk.Label(lotes, text="Alta de lotes al recibir compras. Se usa primero el vencimiento más próximo (FEFO); sin vencimiento al final. Disponible físico no implica vendible si el lote venció. Legado identifica origen desconocido.",
                  wraplength=1080).pack(anchor="w", pady=8)
        self.lotes = Tabla(lotes, [
            ("lote_id", "ID lote"), ("producto", "Producto"), ("codigo", "Lote"), ("vencimiento", "Vencimiento"),
            ("ubicacion", "Ubicación"), ("disponible", "Disponible"), ("vendible", "Vendible"), ("vencido", "Vencido"),
            ("reservado", "Reservado"), ("pendiente", "Pendiente"), ("rechazado", "Bloqueado"), ("condicion", "Condición"),
        ], alto=12)
        self.lotes.pack(fill="both", expand=True)
        ttk.Button(lotes, text="Ver trazabilidad del lote seleccionado", command=lambda: app.ejecutar(self.ver_traza)).pack(anchor="w", pady=8)
        app.refrescadores.extend([self.formulario.actualizar, self.refrescar])

    def previsualizar(self):
        self.necesidades.cargar(self.sistema.sugerencias_compra(self.formulario.obtener("cd")))
        return "Faltantes consultados. Al generar se validan nuevamente para evitar duplicar compras."

    def generar(self):
        f = self.formulario
        orden = self.sistema.generar_orden_compra(f.obtener("cd"), f.obtener("proveedor"), f.obtener("referencia"))
        self.formulario.limpiar()
        self.previsualizar()
        return f"Orden sugerida {orden} registrada; aún no modifica el inventario."

    def ver_detalle(self):
        orden = self.sistema.obtener_orden_compra(self.ordenes.seleccionada()["id"])
        self.app.mostrar_tabla(f"Orden {orden['referencia']} · {orden['estado']}", orden["detalles"],
                              [("codigo", "Producto"), ("descripcion", "Descripción"), ("cantidad", "Cantidad")])

    def preparar_recepcion(self):
        orden = self.sistema.obtener_orden_compra(self.ordenes.seleccionada()["id"])
        if orden["estado"] != "SUGERIDA":
            raise ErrorDominio("Solo se puede recibir una sugerencia pendiente.")
        if self.app.compra_items.items:
            raise ErrorDominio("Termine o limpie los renglones de la compra actual antes de cargar otra orden.")
        self.app.compra_form.completar({"referencia": orden["referencia"] + "-REC", "proveedor": orden["proveedor_id"], "cd": orden["cd_id"]})
        self.app.orden_compra_seleccionada = orden["id"]
        detalle = "; ".join(f"{d['codigo']}: {d['cantidad']} unidades" for d in orden["detalles"])
        self.app.contexto_compra.set(f"Recepción completa de {orden['referencia']}: {detalle}. Ingrese costos y lotes reales.")
        self.app.pestanas.select(self.app.compra_form.master)
        return "Orden vinculada a Compras. Agregue sus renglones y confirme la recepción real."

    def cancelar(self):
        self.sistema.cancelar_orden_compra(self.ordenes.seleccionada()["id"])
        self.previsualizar()
        return "Sugerencia cancelada; se conserva el documento y vuelve a calcularse la necesidad."

    def refrescar(self):
        self.ordenes.cargar(self.sistema.listar("compras_sugeridas"))
        filas = self.sistema.listar("lotes")
        self.lotes.cargar([dict(f, id=f"{f['lote_id']}:{f['ubicacion_id']}") for f in filas])

    def ver_traza(self):
        lote = self.lotes.seleccionada()
        self.app.mostrar_tabla(f"Trazabilidad · {lote['producto']} · {lote['codigo']}",
                              self.sistema.trazabilidad_lote(lote["lote_id"]), [
                                  ("fecha", "Fecha"), ("ubicacion", "Ubicación"), ("causa", "Operación"),
                                  ("referencia_id", "Documento"), ("disponible", "Δ disponible"),
                                  ("reservado", "Δ reservado"), ("pendiente", "Δ pendiente"), ("rechazado", "Δ bloqueado"),
                              ])
