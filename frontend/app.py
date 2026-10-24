"""Interfaz local: los formularios utilizan servicios, nunca SQL."""

import sqlite3
import tkinter as tk
from tkinter import messagebox, ttk

from backend.models.entidades import entero, importe
from backend.patterns.estados_bulto import ErrorDominio


class Tabla(ttk.Frame):
    def __init__(self, padre, columnas, alto=9):
        super().__init__(padre)
        self.columnas = columnas
        self.filas = {}
        self.arbol = ttk.Treeview(self, columns=[c[0] for c in columnas], show="headings", height=alto,
                                  selectmode="browse")
        for clave, titulo in columnas:
            self.arbol.heading(clave, text=titulo)
            self.arbol.column(clave, width=125, minwidth=65)
        vertical = ttk.Scrollbar(self, orient="vertical", command=self.arbol.yview)
        horizontal = ttk.Scrollbar(self, orient="horizontal", command=self.arbol.xview)
        self.arbol.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.arbol.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

    def cargar(self, filas):
        seleccion = self.arbol.selection()
        anterior = self.filas.get(seleccion[0]) if seleccion else None
        self.arbol.delete(*self.arbol.get_children())
        self.filas.clear()
        for indice, fila in enumerate(filas):
            iid = str(indice)
            valores = [importe(fila[clave]) if clave.endswith("_centavos") else fila.get(clave, "")
                       for clave, _ in self.columnas]
            self.arbol.insert("", "end", iid=iid, values=["—" if v is None else v for v in valores])
            self.filas[iid] = fila
            if anterior and fila.get("id") is not None and fila.get("id") == anterior.get("id"):
                self.arbol.selection_set(iid)

    def seleccionada(self):
        seleccion = self.arbol.selection()
        if not seleccion:
            raise ErrorDominio("Seleccione una fila de la tabla.")
        return self.filas[seleccion[0]]


class Formulario(ttk.Frame):
    """Campos en una cuadrícula: el origen opcional provee opciones (id, etiqueta)."""
    def __init__(self, padre, campos):
        super().__init__(padre)
        self.campos = campos
        self.variables = {}
        self.widgets = {}
        for indice, (clave, etiqueta, origen) in enumerate(campos):
            fila, columna = divmod(indice, 3)
            contenedor = ttk.Frame(self, padding=(0, 3, 15, 5))
            contenedor.grid(row=fila, column=columna, sticky="ew")
            ttk.Label(contenedor, text=etiqueta).pack(anchor="w")
            variable = tk.StringVar()
            widget = ttk.Combobox(contenedor, textvariable=variable, state="readonly", width=27) if origen else \
                ttk.Entry(contenedor, textvariable=variable, width=30)
            widget.pack(fill="x")
            self.variables[clave], self.widgets[clave] = variable, widget
        for columna in range(3):
            self.columnconfigure(columna, weight=1)
        self.actualizar()

    def actualizar(self):
        for clave, _, origen in self.campos:
            if origen:
                opciones = [f"{identificador} · {etiqueta}" for identificador, etiqueta in origen()]
                previo = self.variables[clave].get().split(" · ", 1)[0]
                self.widgets[clave]["values"] = opciones
                coincidencia = next((o for o in opciones if o.split(" · ", 1)[0] == previo), "")
                self.variables[clave].set(coincidencia or (opciones[0] if opciones else ""))

    def obtener(self, clave):
        valor = self.variables[clave].get()
        origen = next(c[2] for c in self.campos if c[0] == clave)
        if origen:
            if not valor:
                raise ErrorDominio("Faltan datos de catálogo; registre las opciones necesarias primero.")
            identificador = valor.split(" · ", 1)[0]
            return int(identificador) if identificador.isdigit() else identificador
        return valor

    def completar(self, datos):
        for clave, _, origen in self.campos:
            if origen:
                opciones = self.widgets[clave]["values"]
                self.variables[clave].set(next((o for o in opciones if o.split(" · ", 1)[0] == str(datos[clave])), ""))
            else:
                valor = datos.get(clave, "")
                self.variables[clave].set(importe(valor) if clave.endswith("_centavos") else valor)

    def limpiar(self):
        for clave, _, origen in self.campos:
            if not origen:
                self.variables[clave].set("")


class EditorCatalogo(ttk.Frame):
    def __init__(self, padre, app, consulta, campos, columnas, guardar):
        super().__init__(padre, padding=12)
        self.app, self.consulta, self.guardar = app, consulta, guardar
        self.identificador = None
        self.formulario = Formulario(self, campos)
        self.formulario.pack(fill="x")
        acciones = ttk.Frame(self, padding=(0, 8))
        acciones.pack(fill="x")
        self.boton_guardar = ttk.Button(acciones, text="Guardar", command=lambda: app.ejecutar(self.salvar))
        self.boton_guardar.pack(side="left")
        ttk.Button(acciones, text="Editar selección", command=lambda: app.ejecutar(self.editar)).pack(side="left", padx=8)
        ttk.Button(acciones, text="Nuevo / limpiar", command=self.nuevo).pack(side="left")
        self.modo = ttk.Label(acciones, text="Nuevo registro")
        self.modo.pack(side="left", padx=15)
        self.tabla = Tabla(self, columnas)
        self.tabla.pack(fill="both", expand=True)
        app.refrescadores.append(self.actualizar)

    def salvar(self):
        valores = [self.formulario.obtener(c[0]) for c in self.formulario.campos]
        resultado = self.guardar(*valores, self.identificador)
        self.nuevo()
        return f"Registro {resultado} guardado."

    def editar(self):
        fila = self.tabla.seleccionada()
        self.identificador = fila["id"]
        self.formulario.completar(fila)
        self.modo["text"] = f"Editando registro {self.identificador}"

    def nuevo(self):
        self.identificador = None
        self.formulario.limpiar()
        self.modo["text"] = "Nuevo registro"

    def actualizar(self):
        self.formulario.actualizar()
        self.tabla.cargar(self.app.sistema.listar(self.consulta))


class Renglones(ttk.LabelFrame):
    def __init__(self, padre, app, compra=False):
        super().__init__(padre, text="Productos de la operación", padding=8)
        self.items, self.compra, self.app = [], compra, app
        campos = [("producto", "Producto", app.opciones("productos")), ("cantidad", "Cantidad (unidades)", None)]
        if compra:
            campos.append(("costo", "Costo unitario", None))
        self.formulario = Formulario(self, campos)
        self.formulario.pack(fill="x")
        botones = ttk.Frame(self)
        botones.pack(fill="x", pady=5)
        ttk.Button(botones, text="Agregar renglón", command=lambda: app.ejecutar(self.agregar)).pack(side="left")
        ttk.Button(botones, text="Quitar selección", command=lambda: app.ejecutar(self.quitar)).pack(side="left", padx=8)
        columnas = [("producto_id", "ID producto"), ("producto", "Producto"), ("cantidad", "Cantidad")]
        if compra:
            columnas.append(("costo", "Costo unitario"))
        self.tabla = Tabla(self, columnas, alto=4)
        self.tabla.pack(fill="both", expand=True)
        app.refrescadores.append(self.formulario.actualizar)

    def agregar(self):
        producto_id = self.formulario.obtener("producto")
        cantidad = entero(self.formulario.obtener("cantidad"))
        costo = self.formulario.obtener("costo") if self.compra else None
        if self.compra:
            from backend.models.entidades import centavos
            costo = importe(centavos(costo))
        etiqueta = self.formulario.variables["producto"].get()
        self.items.append({"id": len(self.items), "producto_id": producto_id, "producto": etiqueta,
                           "cantidad": cantidad, "costo": costo})
        self.tabla.cargar(self.items)
        self.formulario.limpiar()

    def quitar(self):
        self.items.remove(self.tabla.seleccionada())
        for indice, item in enumerate(self.items):
            item["id"] = indice
        self.tabla.cargar(self.items)

    def detalles(self):
        return [(i["producto_id"], i["cantidad"], i["costo"]) if self.compra else
                (i["producto_id"], i["cantidad"]) for i in self.items]

    def limpiar(self):
        self.items.clear()
        self.tabla.cargar([])


class Aplicacion:
    def __init__(self, raiz, sistema):
        self.raiz, self.sistema = raiz, sistema
        self.refrescadores = []
        raiz.title("G41 · Ventas e inventario — Catálogo y logística")
        raiz.geometry("1180x800")
        raiz.minsize(1000, 700)
        estilo = ttk.Style(raiz)
        estilo.theme_use("clam")
        estilo.configure("Treeview", rowheight=25)
        encabezado = ttk.Frame(raiz, padding=12)
        encabezado.pack(fill="x")
        ttk.Label(encabezado, text="Centro de Distribución → Locales", font=("Segoe UI", 17, "bold")).pack(side="left")
        ttk.Button(encabezado, text="Actualizar datos", command=lambda: self.ejecutar(self.actualizar)).pack(side="right")
        self.pestanas = ttk.Notebook(raiz)
        self.pestanas.pack(fill="both", expand=True, padx=12)
        self.estado = tk.StringVar(value="Registre catálogo y una compra para comenzar, o use --demo en una base separada.")
        ttk.Label(raiz, textvariable=self.estado, padding=10, wraplength=1100).pack(fill="x")
        self.crear_catalogo()
        self.crear_compras()
        self.crear_reposicion()
        self.crear_logistica()
        self.crear_inventario()
        self.actualizar()

    def opciones(self, consulta, tipo=None):
        def obtener():
            filas = self.sistema.listar(consulta)
            return [(f["id"], (f.get("codigo", "") + " " + f.get("nombre", f.get("descripcion", ""))).strip())
                    for f in filas if tipo is None or f.get("tipo") == tipo]
        return obtener

    def panel(self, titulo):
        panel = ttk.Frame(self.pestanas, padding=10)
        self.pestanas.add(panel, text=titulo)
        return panel

    def ejecutar(self, accion):
        try:
            resultado = accion()
            self.actualizar()
            self.estado.set(resultado if isinstance(resultado, str) else "Operación completada.")
            return True
        except (ErrorDominio, sqlite3.Error, OSError) as error:
            self.estado.set(str(error))
            messagebox.showerror("No se pudo confirmar", str(error), parent=self.raiz)
            return False

    def actualizar(self):
        for refrescar in self.refrescadores:
            refrescar()

    def crear_catalogo(self):
        panel = self.panel("1. Administración")
        sub = ttk.Notebook(panel)
        sub.pack(fill="both", expand=True)
        especificaciones = [
            ("Ubicaciones", "ubicaciones", [("codigo", "Código único", None), ("nombre", "Nombre", None),
              ("direccion", "Dirección", None), ("tipo", "Función", lambda: [("CD", "Centro de Distribución"), ("LOCAL", "Local")])],
             [("id", "ID"), ("codigo", "Código"), ("nombre", "Nombre"), ("direccion", "Dirección"), ("tipo", "Función")],
             self.sistema.guardar_ubicacion),
            ("Categorías", "categorias", [("nombre", "Nombre", None)], [("id", "ID"), ("nombre", "Nombre")], self.sistema.guardar_categoria),
            ("Proveedores", "proveedores", [("codigo", "Código único", None), ("nombre", "Nombre", None)],
             [("id", "ID"), ("codigo", "Código"), ("nombre", "Nombre")], self.sistema.guardar_proveedor),
            ("Productos", "productos", [("codigo", "Código único", None), ("descripcion", "Descripción", None),
              ("categoria_id", "Categoría", self.opciones("categorias")), ("precio_centavos", "Precio de venta", None)],
             [("id", "ID"), ("codigo", "Código"), ("descripcion", "Descripción"), ("categoria", "Categoría"), ("precio_centavos", "Precio")],
             self.sistema.guardar_producto),
        ]
        self.editores = {}
        for titulo, consulta, campos, columnas, guardar in especificaciones:
            editor = EditorCatalogo(sub, self, consulta, campos, columnas, guardar)
            sub.add(editor, text=titulo)
            self.editores[consulta] = editor

    def crear_compras(self):
        panel = self.panel("2. Compras recibidas")
        ttk.Label(panel, text="Registrar mercadería recibida y aceptada en el CD. La referencia no puede repetirse.").pack(anchor="w")
        self.compra_form = Formulario(panel, [("referencia", "Referencia única", None),
            ("proveedor", "Proveedor", self.opciones("proveedores")), ("cd", "Destino CD", self.opciones("ubicaciones", "CD"))])
        self.compra_form.pack(fill="x")
        self.compra_items = Renglones(panel, self, compra=True)
        self.compra_items.pack(fill="both", expand=True)
        ttk.Button(panel, text="Confirmar compra recibida", command=lambda: self.ejecutar(self.confirmar_compra)).pack(anchor="w", pady=8)
        self.compras = Tabla(panel, [("id", "ID"), ("referencia", "Referencia"), ("fecha", "Fecha"),
                                    ("proveedor", "Proveedor"), ("cd", "CD"), ("total_centavos", "Total")], alto=4)
        self.compras.pack(fill="both", expand=True)
        self.refrescadores.extend([self.compra_form.actualizar, lambda: self.compras.cargar(self.sistema.listar("compras"))])

    def confirmar_compra(self):
        f = self.compra_form
        identificador = self.sistema.registrar_compra(f.obtener("referencia"), f.obtener("proveedor"), f.obtener("cd"), self.compra_items.detalles())
        self.compra_items.limpiar()
        f.limpiar()
        return f"Compra {identificador} registrada; stock del CD actualizado."

    def crear_reposicion(self):
        panel = self.panel("3. Reposición")
        self.orden_form = Formulario(panel, [("cd", "CD abastecedor", self.opciones("ubicaciones", "CD")),
                                            ("local", "Local solicitante / destino", self.opciones("ubicaciones", "LOCAL"))])
        self.orden_form.pack(fill="x")
        self.orden_items = Renglones(panel, self)
        self.orden_items.pack(fill="both", expand=True)
        ttk.Button(panel, text="Crear orden por local", command=lambda: self.ejecutar(self.confirmar_orden)).pack(anchor="w", pady=5)
        self.ordenes = Tabla(panel, [("id", "Orden"), ("cd", "CD"), ("local", "Destino"), ("solicitada", "Unidades pedidas"),
                                    ("asignada", "Unidades asignadas")], alto=4)
        self.ordenes.pack(fill="both", expand=True)
        botones = ttk.Frame(panel)
        botones.pack(fill="x", pady=5)
        ttk.Button(botones, text="Ver pendientes", command=lambda: self.ejecutar(self.ver_orden)).pack(side="left")
        ttk.Button(botones, text="Preparar bulto de la orden seleccionada…", command=lambda: self.ejecutar(self.dialogo_preparar)).pack(side="left", padx=8)
        self.refrescadores.extend([self.orden_form.actualizar, lambda: self.ordenes.cargar(self.sistema.listar("ordenes"))])

    def confirmar_orden(self):
        identificador = self.sistema.crear_orden(self.orden_form.obtener("cd"), self.orden_form.obtener("local"), self.orden_items.detalles())
        self.orden_items.limpiar()
        return f"Orden {identificador} creada; solicitar no cambia el stock."

    def ver_orden(self):
        orden = self.ordenes.seleccionada()
        self.mostrar_tabla(f"Pendientes de la orden {orden['id']}", self.sistema.detalle_orden(orden["id"]),
                           [("codigo", "Código"), ("descripcion", "Producto"), ("solicitada", "Solicitada"), ("pendiente", "Por asignar")])

    def dialogo_preparar(self):
        orden = self.ordenes.seleccionada()
        ventana = tk.Toplevel(self.raiz)
        ventana.title(f"Preparar bulto · Orden {orden['id']} → {orden['local']}")
        ventana.geometry("850x500")
        ventana.transient(self.raiz)
        ventana.grab_set()
        contenedor = ttk.Frame(ventana, padding=12)
        contenedor.pack(fill="both", expand=True)
        ttk.Label(contenedor, text="Un bulto por remito. Puede asignar parte de lo pendiente y preparar otro bulto después.").pack(anchor="w")
        formulario = Formulario(contenedor, [("remito", "Número único de remito", None)])
        formulario.pack(fill="x")
        renglones = Renglones(contenedor, self)
        renglones.pack(fill="both", expand=True)

        def confirmar():
            identificador = self.sistema.preparar_bulto(orden["id"], formulario.obtener("remito"), renglones.detalles())
            self.refrescadores.remove(renglones.formulario.actualizar)
            ventana.destroy()
            return f"Bulto {identificador} preparado: mercadería reservada en el CD."

        def cerrar():
            self.refrescadores.remove(renglones.formulario.actualizar)
            ventana.destroy()

        ventana.protocol("WM_DELETE_WINDOW", cerrar)
        ttk.Button(contenedor, text="Preparar y reservar", command=lambda: self.ejecutar(confirmar)).pack(anchor="w", pady=8)

    def crear_logistica(self):
        panel = self.panel("4. Bultos y remitos")
        ttk.Label(panel, text="Seleccione un bulto. Secuencia: Preparado → Precintado → En tránsito → Recibido → Verificado / Rechazado.").pack(anchor="w")
        self.bultos = Tabla(panel, [("id", "Bulto"), ("orden_id", "Orden"), ("remito", "Remito"),
            ("precinto", "Precinto"), ("estado", "Estado bulto"), ("estado_remito", "Estado remito"), ("destino", "Destino")])
        self.bultos.pack(fill="both", expand=True, pady=8)
        self.logistica_form = Formulario(panel, [("precinto", "Precinto asignado / observado", None),
            ("local", "Local receptor", self.opciones("ubicaciones", "LOCAL")), ("motivo", "Motivo si el precinto está roto", None)])
        self.logistica_form.pack(fill="x")
        self.roto = tk.BooleanVar(value=False)
        ttk.Checkbutton(panel, text="Precinto roto: rechazar y bloquear mercadería", variable=self.roto).pack(anchor="w", pady=5)
        botones = ttk.Frame(panel)
        botones.pack(fill="x", pady=8)
        for titulo, accion in [("1. Precintar", "precintar"), ("2. Despachar", "despachar"),
                               ("3. Recibir", "recibir"), ("4. Verificar / rechazar", "verificar")]:
            ttk.Button(botones, text=titulo, command=lambda a=accion: self.ejecutar(lambda: self.operar_bulto(a))).pack(side="left", padx=(0, 8))
        ttk.Button(panel, text="Consultar historial y contenido", command=lambda: self.ejecutar(self.ver_bulto)).pack(anchor="w")
        ttk.Label(panel, text="Recibir no habilita venta. Al verificar confirma que remito, contenido y precinto corresponden; si el código difiere, corrija la incidencia antes de aceptar.",
                  wraplength=1000).pack(anchor="w", pady=10)
        self.refrescadores.extend([self.logistica_form.actualizar, lambda: self.bultos.cargar(self.sistema.listar("bultos"))])

    def operar_bulto(self, accion):
        identificador = self.bultos.seleccionada()["id"]
        f = self.logistica_form
        if accion == "precintar":
            self.sistema.precintar(identificador, f.obtener("precinto"))
        elif accion == "despachar":
            self.sistema.despachar(identificador)
        elif accion == "recibir":
            self.sistema.recibir(identificador, f.obtener("local"))
        else:
            self.sistema.verificar(identificador, f.obtener("local"), f.obtener("precinto"), self.roto.get(), f.obtener("motivo"))
        return f"Bulto {identificador}: operación confirmada. Consulte el inventario y su historial."

    def mostrar_tabla(self, titulo, filas, columnas):
        ventana = tk.Toplevel(self.raiz)
        ventana.title(titulo)
        ventana.geometry("950x420")
        tabla = Tabla(ventana, columnas)
        tabla.pack(fill="both", expand=True, padx=12, pady=12)
        tabla.cargar(filas)

    def ver_bulto(self):
        identificador = self.bultos.seleccionada()["id"]
        self.mostrar_tabla(f"Historial del bulto {identificador}", self.sistema.historial_bulto(identificador),
                           [("anterior", "Anterior"), ("nuevo", "Nuevo"), ("fecha", "Fecha"), ("observacion", "Evidencia")])
        self.mostrar_tabla(f"Contenido del bulto {identificador}", self.sistema.contenido_bulto(identificador),
                           [("codigo", "Código"), ("descripcion", "Producto"), ("cantidad", "Cantidad")])

    def crear_inventario(self):
        panel = self.panel("5. Inventario y mínimos")
        self.minimo_form = Formulario(panel, [("ubicacion", "Ubicación", self.opciones("ubicaciones")),
            ("producto", "Producto", self.opciones("productos")), ("minimo", "Mínimo (unidades)", None)])
        self.minimo_form.pack(fill="x")
        ttk.Button(panel, text="Guardar mínimo", command=lambda: self.ejecutar(self.guardar_minimo)).pack(anchor="w", pady=8)
        self.inventario = Tabla(panel, [("ubicacion", "Ubicación"), ("codigo", "Producto"), ("disponible", "Disponible"),
            ("reservado", "Reservado"), ("pendiente", "Pendiente"), ("rechazado", "Rechazado"), ("minimo", "Mínimo"), ("faltante", "Faltante")])
        self.inventario.pack(fill="both", expand=True)
        ttk.Label(panel, text="Físico = disponible + reservado + pendiente + rechazado. En tránsito se consulta en Bultos; no se cuenta en origen ni destino.",
                  wraplength=1000).pack(anchor="w", pady=10)
        self.refrescadores.extend([self.minimo_form.actualizar, lambda: self.inventario.cargar(self.sistema.listar("inventario"))])

    def guardar_minimo(self):
        f = self.minimo_form
        self.sistema.configurar_minimo(f.obtener("ubicacion"), f.obtener("producto"), f.obtener("minimo"))
        return "Mínimo guardado. El faltante se calcula sobre la cantidad disponible."
