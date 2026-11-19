"""Interfaz local: los formularios utilizan servicios, nunca SQL."""

import sqlite3
import tkinter as tk
from datetime import date
from pathlib import Path
from tkinter import font, messagebox, ttk

from backend.models.entidades import centavos, entero, importe
from backend.patterns.estados_bulto import ErrorDominio
from frontend.estilos import aplicar_estilos


MEDIOS_PAGO = [
    ("EFECTIVO", "Efectivo"),
    ("DEBITO", "Tarjeta de débito"),
    ("CREDITO", "Tarjeta de crédito"),
    ("TRANSFERENCIA", "Transferencia"),
]


class Tabla(ttk.Frame):
    def __init__(self, padre, columnas, alto=9):
        super().__init__(padre)
        self.columnas = columnas
        self.filas = {}
        self.arbol = ttk.Treeview(
            self,
            columns=[c[0] for c in columnas],
            show="headings",
            height=alto,
            selectmode="browse",
        )
        self.arbol.tag_configure("alterna", background="#f2f7f9")
        fuente = font.Font(root=self, font=ttk.Style(self).lookup("Treeview.Heading", "font") or "TkHeadingFont")
        for clave, titulo in columnas:
            numerica = clave.endswith("_centavos") or clave in {
                "cantidad", "disponible", "vendible", "vencido", "reservado", "pendiente", "rechazado",
                "minimo", "faltante", "unidades", "solicitada", "asignada",
            }
            ancho = 195 if clave in {"descripcion", "observacion", "ubicacion", "destino", "local", "nombre"} else 100
            alineacion = "e" if numerica else "w"
            self.arbol.heading(clave, text=titulo, anchor=alineacion)
            self.arbol.column(clave, width=max(ancho, fuente.measure(titulo) + 24), minwidth=70, anchor=alineacion)
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
            valores = [
                importe(fila[clave]) if clave.endswith("_centavos") and fila.get(clave) is not None else fila.get(clave, "")
                for clave, _ in self.columnas
            ]
            self.arbol.insert("", "end", iid=iid, values=["—" if v is None else v for v in valores],
                              tags=("alterna",) if indice % 2 else ())
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

    def __init__(self, padre, campos, fechas=()):
        super().__init__(padre)
        self.campos = campos
        self.variables = {}
        self.widgets = {}
        self.etiquetas = {}
        self.bordes = {}
        self.fechas = fechas
        self.fondo = ttk.Style(self).lookup("TFrame", "background")
        for indice, (clave, etiqueta, origen) in enumerate(campos):
            fila, columna = divmod(indice, 3)
            contenedor = ttk.Frame(self, padding=(0, 3, 15, 5))
            contenedor.grid(row=fila, column=columna, sticky="ew")
            rotulo = ttk.Label(contenedor, text=etiqueta)
            rotulo.pack(anchor="w")
            borde = tk.Frame(contenedor, background=self.fondo)
            borde.pack(fill="x")
            variable = tk.StringVar()
            widget = (
                ttk.Combobox(borde, textvariable=variable, state="readonly", width=27)
                if origen
                else ttk.Entry(borde, textvariable=variable, width=30)
            )
            widget.pack(fill="x", padx=1, pady=1)
            self.variables[clave], self.widgets[clave] = variable, widget
            self.etiquetas[clave] = rotulo
            self.bordes[clave] = borde
            variable.trace_add("write", lambda *_, campo=clave: self.limpiar_error(campo))
            if clave in fechas:
                widget.configure(validate="key", validatecommand=(self.register(self.teclas_fecha), "%P"))
                widget.bind("<KeyRelease>", lambda evento, campo=clave: self.formatear_fecha(campo, evento))
        for columna in range(min(3, max(1, len(campos)))):
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
        if clave in self.fechas and valor:
            if len(valor) == 8 and valor.isascii() and valor.isdigit():
                valor = f"{valor[:4]}-{valor[4:6]}-{valor[6:]}"
            try:
                fecha = date.fromisoformat(valor).isoformat()
                if fecha == valor:
                    return fecha
            except ValueError:
                pass
            self.marcar_error(clave)
            raise ErrorDominio(f"{self.etiquetas[clave]['text']}: ingresá una fecha válida (AAAA-MM-DD).")
        return valor

    @staticmethod
    def teclas_fecha(propuesta):
        return len(propuesta) <= 10 and len(propuesta.replace("-", "")) <= 8 and all(
            caracter in "0123456789-" for caracter in propuesta
        )

    def formatear_fecha(self, clave, evento):
        widget = self.widgets[clave]
        if not evento.char or evento.char not in "0123456789" or widget.index("insert") != widget.index("end"):
            return
        valor = self.variables[clave].get().replace("-", "")
        partes = (valor[:4], valor[4:6], valor[6:8])
        self.variables[clave].set("-".join(parte for parte in partes if parte))
        widget.icursor("end")

    def marcar_error(self, *claves):
        for clave in claves:
            self.etiquetas[clave].configure(foreground="#a21b1b")
            self.bordes[clave].configure(background="#a21b1b")
        self.widgets[claves[0]].focus_set()

    def limpiar_error(self, clave):
        self.etiquetas[clave].configure(foreground="")
        self.bordes[clave].configure(background=self.fondo)

    def completar(self, datos):
        for clave, _, origen in self.campos:
            if origen:
                opciones = self.widgets[clave]["values"]
                self.variables[clave].set(
                    next((o for o in opciones if o.split(" · ", 1)[0] == str(datos[clave])), "")
                )
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
        self.boton_guardar = ttk.Button(acciones, text="Guardar", style="Principal.TButton",
                                       command=lambda: app.ejecutar(self.salvar))
        self.boton_guardar.pack(side="left")
        ttk.Button(acciones, text="Editar selección", command=lambda: app.ejecutar(self.editar)).pack(
            side="left", padx=8
        )
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
    def __init__(self, padre, app, compra=False, al_cambiar=None, opciones_productos=None, validar_cantidad=None):
        super().__init__(padre, text="Productos de la operación", padding=8)
        self.items, self.compra, self.app, self.al_cambiar = [], compra, app, al_cambiar
        self.validar_cantidad = validar_cantidad
        origen_productos = (lambda: opciones_productos(self.items)) if opciones_productos else app.opciones("productos")
        campos = [
            ("producto", "Producto", origen_productos),
            ("cantidad", "Cantidad (unidades)", None),
        ]
        if compra:
            campos.append(("costo", "Costo unitario", None))
            campos.extend([("lote", "Lote (vacío: automático por compra)", None),
                           ("vencimiento", "Vencimiento opcional AAAA-MM-DD", None)])
        self.formulario = Formulario(self, campos, fechas=("vencimiento",) if compra else ())
        self.formulario.pack(fill="x")
        botones = ttk.Frame(self)
        botones.pack(fill="x", pady=5)
        self.boton_agregar = ttk.Button(
            botones, text="Agregar renglón", command=lambda: app.ejecutar(self.agregar)
        )
        self.boton_agregar.pack(side="left")
        self.boton_agregar.state(["disabled"])
        self.formulario.variables["cantidad"].trace_add("write", self.actualizar_boton_agregar)
        if validar_cantidad:
            self.formulario.variables["producto"].trace_add("write", self.actualizar_boton_agregar)
        ttk.Button(botones, text="Quitar selección", command=lambda: app.ejecutar(self.quitar)).pack(
            side="left", padx=8
        )
        columnas = [("producto_id", "ID producto"), ("producto", "Producto"), ("cantidad", "Cantidad")]
        if compra:
            columnas.append(("costo", "Costo unitario"))
            columnas.extend([("lote", "Lote"), ("vencimiento", "Vencimiento")])
        self.tabla = Tabla(self, columnas, alto=3)
        self.tabla.pack(fill="both", expand=True)
        app.refrescadores.append(self.formulario.actualizar)

    def actualizar_boton_agregar(self, *_):
        cantidad = self.formulario.variables["cantidad"].get().strip()
        producto = self.formulario.variables["producto"].get()
        habilitado = cantidad and (producto or not self.validar_cantidad)
        self.boton_agregar.state(["!disabled" if habilitado else "disabled"])

    def agregar(self):
        producto_id = self.formulario.obtener("producto")
        try:
            cantidad = entero(self.formulario.obtener("cantidad"))
            if self.validar_cantidad:
                self.validar_cantidad(producto_id, cantidad)
        except ErrorDominio:
            self.formulario.marcar_error("cantidad")
            raise
        costo = self.formulario.obtener("costo") if self.compra else None
        if self.compra:
            costo = importe(centavos(costo))
        etiqueta = self.formulario.variables["producto"].get()
        if self.validar_cantidad:
            etiqueta = etiqueta.split(" · ", 2)[-1]
        self.items.append(
            {
                "id": len(self.items),
                "producto_id": producto_id,
                "producto": etiqueta,
                "cantidad": cantidad,
                "costo": costo,
                "lote": self.formulario.obtener("lote") if self.compra else None,
                "vencimiento": self.formulario.obtener("vencimiento") if self.compra else None,
            }
        )
        self.tabla.cargar(self.items)
        self.tabla.arbol.see(str(self.items[-1]["id"]))
        self.formulario.limpiar()
        if self.al_cambiar:
            self.al_cambiar()

    def quitar(self):
        item = self.tabla.seleccionada()
        if self.al_cambiar:
            self.app.venta_cobros.validar_quitar_producto(item)
        self.items.remove(item)
        for indice, item in enumerate(self.items):
            item["id"] = indice
        self.tabla.cargar(self.items)
        if self.al_cambiar:
            self.al_cambiar()

    def detalles(self):
        return [
            (i["producto_id"], i["cantidad"], i["costo"], i.get("lote"), i.get("vencimiento")) if self.compra else (i["producto_id"], i["cantidad"])
            for i in self.items
        ]

    def limpiar(self):
        self.items.clear()
        self.tabla.cargar([])
        if self.al_cambiar:
            self.al_cambiar()


class ContenidoBulto(ttk.LabelFrame):
    def __init__(self, padre, pendientes):
        super().__init__(padre, text="Productos pendientes de la orden", padding=8)
        self.cantidades = []
        fondo = ttk.Style(self).lookup("TFrame", "background")
        lienzo = tk.Canvas(self, height=230, background=fondo, highlightthickness=0)
        barra = ttk.Scrollbar(self, orient="vertical", command=lienzo.yview)
        lienzo.configure(yscrollcommand=barra.set)
        barra.pack(side="right", fill="y")
        lienzo.pack(side="left", fill="both", expand=True)
        tabla = ttk.Frame(lienzo)
        tabla.columnconfigure(1, weight=1)
        panel = lienzo.create_window(0, 0, anchor="nw", window=tabla)
        lienzo.bind("<Configure>", lambda evento: lienzo.itemconfigure(panel, width=evento.width))
        tabla.bind("<Configure>", lambda _: lienzo.configure(scrollregion=lienzo.bbox(panel)))
        self.winfo_toplevel().bind(
            "<MouseWheel>", lambda evento: lienzo.yview_scroll(-int(evento.delta / 120), "units")
        )

        for columna, titulo in enumerate(("Código", "Producto", "Por asignar", "En este bulto")):
            ttk.Label(tabla, text=titulo, font="TkHeadingFont").grid(
                row=0, column=columna, sticky="w", padx=8, pady=(0, 5)
            )
        for fila, producto in enumerate(pendientes, start=1):
            for columna, (clave, ancho) in enumerate((("codigo", 105), ("descripcion", 245), ("pendiente", 0))):
                ttk.Label(tabla, text=producto[clave], wraplength=ancho).grid(
                    row=fila, column=columna, sticky="e" if clave == "pendiente" else "w", padx=8
                )
            cantidad = ttk.Entry(tabla, width=12, justify="right")
            cantidad.grid(row=fila, column=3, sticky="ew", padx=8, pady=3)
            cantidad.bind("<FocusIn>", lambda _, campo=cantidad: self.mostrar_cantidad(lienzo, tabla, campo))
            self.cantidades.append((producto, cantidad))

    @staticmethod
    def mostrar_cantidad(lienzo, tabla, campo):
        arriba = lienzo.canvasy(0)
        abajo = arriba + lienzo.winfo_height()
        inicio, fin = campo.winfo_y(), campo.winfo_y() + campo.winfo_height()
        if inicio < arriba:
            lienzo.yview_moveto(inicio / tabla.winfo_height())
        elif fin > abajo:
            lienzo.yview_moveto((fin - lienzo.winfo_height()) / tabla.winfo_height())

    def cargar_pendientes(self):
        for producto, campo in self.cantidades:
            campo.delete(0, "end")
            campo.insert(0, producto["pendiente"])

    def detalles(self):
        detalles = []
        for producto, campo in self.cantidades:
            valor = campo.get().strip()
            if not valor:
                continue
            try:
                cantidad = entero(valor, f"Cantidad de {producto['codigo']}", minimo=0)
                if cantidad > producto["pendiente"]:
                    raise ErrorDominio(f"{producto['codigo']}: quedan {producto['pendiente']} unidades por asignar.")
            except ErrorDominio:
                campo.focus_set()
                campo.selection_range(0, "end")
                raise
            if cantidad:
                detalles.append((producto["producto_id"], cantidad))
        if not detalles:
            raise ErrorDominio("Ingresá la cantidad de al menos un producto para preparar el bulto.")
        return detalles


class RenglonesCobro(ttk.LabelFrame):
    """Componente de interfaz para registrar uno o varios cobros por medio de pago."""

    def __init__(self, padre, app, renglones_productos):
        super().__init__(padre, text="Cobros por medio de pago", padding=8)
        self.items = []
        self.app = app
        self.renglones_productos = renglones_productos
        campos = [
            ("medio_pago", "Medio de pago", lambda: MEDIOS_PAGO),
            ("importe", "Importe a cobrar", None),
        ]
        self.formulario = Formulario(self, campos)
        self.formulario.pack(fill="x")
        botones = ttk.Frame(self)
        botones.pack(fill="x", pady=5)
        self.boton_agregar = ttk.Button(
            botones, text="Agregar cobro", command=lambda: app.ejecutar(self.agregar)
        )
        self.boton_agregar.pack(side="left")
        self.boton_saldar = ttk.Button(
            botones,
            text="Saldar resto",
            command=lambda: app.ejecutar(self.saldar_resto),
        )
        self.boton_saldar.pack(side="left", padx=8)
        ttk.Button(botones, text="Quitar cobro", command=lambda: app.ejecutar(self.quitar)).pack(side="left")
        self.resumen = ttk.Label(self, text="Total venta: $0.00 · Cobrado: $0.00 · Restante: $0.00", style="Estado.TLabel")
        self.resumen.pack(fill="x", pady=(0, 4))
        self.tabla = Tabla(self, [("medio_pago", "Medio de pago"), ("importe_centavos", "Importe")], alto=3)
        self.tabla.pack(fill="both", expand=True)

    def total_venta_centavos(self, sin_item=None):
        precios = {p["id"]: p["precio_centavos"] for p in self.app.sistema.listar("productos")}
        return sum(
            precios.get(item["producto_id"], 0) * item["cantidad"]
            for item in self.renglones_productos.items if item is not sin_item
        )

    def total_cobrado_centavos(self):
        return sum(item["importe_centavos"] for item in self.items)

    def actualizar_resumen(self):
        total = self.total_venta_centavos()
        cobrado = self.total_cobrado_centavos()
        restante = total - cobrado
        saldo = f"Restante: ${importe(restante)}" if restante >= 0 else f"Excedente: ${importe(-restante)} · ajustá los cobros"
        self.resumen["text"] = (
            f"Total venta: ${importe(total)} · Cobrado: ${importe(cobrado)} · {saldo}"
        )
        estilo = "Error.Estado.TLabel" if restante < 0 else "Correcto.Estado.TLabel" if total and not restante else "Estado.TLabel"
        self.resumen.configure(style=estilo)
        self.boton_agregar.state(["!disabled" if restante > 0 else "disabled"])
        self.boton_saldar.state(["!disabled" if restante > 0 else "disabled"])

    def validar_quitar_producto(self, item):
        if self.total_cobrado_centavos() > self.total_venta_centavos(sin_item=item):
            raise ErrorDominio("Quitá o ajustá un cobro antes de retirar ese producto: los cobros superarían el nuevo total.")

    def agregar(self):
        medio = self.formulario.obtener("medio_pago")
        monto_cent = centavos(self.formulario.obtener("importe"))
        if monto_cent <= 0:
            raise ErrorDominio("El importe del cobro debe ser mayor a cero.")
        restante = self.total_venta_centavos() - self.total_cobrado_centavos()
        if monto_cent > restante:
            self.formulario.marcar_error("importe")
            raise ErrorDominio(f"El importe supera el saldo por cobrar de ${importe(max(0, restante))}.")
        self.items.append(
            {
                "id": len(self.items),
                "medio_pago": medio,
                "importe_centavos": monto_cent,
                "importe": importe(monto_cent),
            }
        )
        self.tabla.cargar(self.items)
        self.formulario.limpiar()
        self.actualizar_resumen()

    def saldar_resto(self):
        medio = self.formulario.obtener("medio_pago")
        restante = self.total_venta_centavos() - self.total_cobrado_centavos()
        if restante <= 0:
            raise ErrorDominio("No hay saldo pendiente por cobrar en la venta actual.")
        self.items.append(
            {
                "id": len(self.items),
                "medio_pago": medio,
                "importe_centavos": restante,
                "importe": importe(restante),
            }
        )
        self.tabla.cargar(self.items)
        self.formulario.limpiar()
        self.actualizar_resumen()

    def quitar(self):
        self.items.remove(self.tabla.seleccionada())
        for indice, item in enumerate(self.items):
            item["id"] = indice
        self.tabla.cargar(self.items)
        self.actualizar_resumen()

    def cobros(self):
        if not self.items:
            importe_escrito = self.formulario.variables["importe"].get().strip()
            if importe_escrito:
                restante = self.total_venta_centavos()
                if centavos(importe_escrito) > restante:
                    self.formulario.marcar_error("importe")
                    raise ErrorDominio(f"El importe supera el saldo por cobrar de ${importe(restante)}.")
                return [(self.formulario.obtener("medio_pago"), importe_escrito)]
        return [(i["medio_pago"], i["importe"]) for i in self.items]

    def limpiar(self):
        self.items.clear()
        self.tabla.cargar([])
        self.formulario.limpiar()
        self.actualizar_resumen()


class Aplicacion:
    def __init__(self, raiz, sistema):
        self.raiz, self.sistema = raiz, sistema
        self.refrescadores = []
        raiz.title("G41 · Ventas e inventario")
        icono = Path(__file__).with_name("icono.png")
        raiz.iconphoto(True, tk.PhotoImage(master=raiz, file=str(icono)))
        raiz.geometry("1220x820")
        raiz.minsize(1020, 720)
        aplicar_estilos(raiz)
        encabezado = ttk.Frame(raiz, padding=(18, 11), style="Encabezado.TFrame")
        encabezado.pack(fill="x")
        titulo = ttk.Frame(encabezado, style="Encabezado.TFrame")
        titulo.pack(side="left")
        ttk.Label(titulo, text="Ventas e inventario", style="Titulo.TLabel").pack(anchor="w")
        ttk.Label(titulo, text="Centro de distribución y locales", style="Subtitulo.TLabel").pack(anchor="w")
        ttk.Button(encabezado, text="Actualizar datos", command=lambda: self.ejecutar(self.actualizar)).pack(
            side="right"
        )
        self.pestanas = ttk.Notebook(raiz)
        self.pestanas.pack(fill="both", expand=True, padx=12, pady=(7, 0))
        self.estado = tk.StringVar(
            value="Registre catálogo y una compra para comenzar, o use --demo en una base separada."
        )
        self.barra_estado = ttk.Label(raiz, textvariable=self.estado, style="Estado.TLabel", wraplength=970)
        self.barra_estado.pack(fill="x")
        self.crear_catalogo()
        self.crear_compras()
        self.crear_reposicion()
        self.crear_logistica()
        self.crear_inventario()
        self.crear_ventas()
        from frontend.devoluciones_reportes import VistaDevoluciones, VistaReportes

        self.devoluciones_vista = VistaDevoluciones(self.panel("7. Devoluciones"), self)
        self.devoluciones_vista.pack(fill="both", expand=True)
        self.reportes_vista = VistaReportes(self.panel("8. Reportes"), self)
        self.reportes_vista.pack(fill="both", expand=True)
        from frontend.opcionales import VistaOpcionales

        self.opcionales_vista = VistaOpcionales(self.panel("9. Compras / lotes"), self)
        self.opcionales_vista.pack(fill="both", expand=True)
        self.actualizar()

    def opciones(self, consulta, tipo=None):
        def obtener():
            filas = self.sistema.listar(consulta)
            return [
                (f["id"], (f.get("codigo", "") + " " + f.get("nombre", f.get("descripcion", ""))).strip())
                for f in filas
                if tipo is None or f.get("tipo") == tipo
            ]

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
            self.barra_estado.configure(style="Correcto.Estado.TLabel")
            return True
        except (ErrorDominio, sqlite3.Error, OSError) as error:
            self.estado.set(str(error))
            self.barra_estado.configure(style="Error.Estado.TLabel")
            messagebox.showerror("No se pudo confirmar", str(error), parent=self.raiz)
            return False

    def actualizar(self):
        for refrescar in self.refrescadores:
            refrescar()

    def crear_catalogo(self):
        panel = self.panel("1. Catálogo")
        sub = ttk.Notebook(panel)
        sub.pack(fill="both", expand=True)
        especificaciones = [
            (
                "Ubicaciones",
                "ubicaciones",
                [
                    ("codigo", "Código único", None),
                    ("nombre", "Nombre", None),
                    ("direccion", "Dirección", None),
                    (
                        "tipo",
                        "Función",
                        lambda: [("CD", "Centro de Distribución"), ("LOCAL", "Local")],
                    ),
                ],
                [
                    ("id", "ID"),
                    ("codigo", "Código"),
                    ("nombre", "Nombre"),
                    ("direccion", "Dirección"),
                    ("tipo", "Función"),
                ],
                self.sistema.guardar_ubicacion,
            ),
            (
                "Categorías",
                "categorias",
                [("nombre", "Nombre", None)],
                [("id", "ID"), ("nombre", "Nombre")],
                self.sistema.guardar_categoria,
            ),
            (
                "Proveedores",
                "proveedores",
                [("codigo", "Código único", None), ("nombre", "Nombre", None)],
                [("id", "ID"), ("codigo", "Código"), ("nombre", "Nombre")],
                self.sistema.guardar_proveedor,
            ),
            (
                "Productos",
                "productos",
                [
                    ("codigo", "Código único", None),
                    ("descripcion", "Descripción", None),
                    ("categoria_id", "Categoría", self.opciones("categorias")),
                    ("precio_centavos", "Precio de venta", None),
                ],
                [
                    ("id", "ID"),
                    ("codigo", "Código"),
                    ("descripcion", "Descripción"),
                    ("categoria", "Categoría"),
                    ("precio_centavos", "Precio"),
                ],
                self.sistema.guardar_producto,
            ),
        ]
        self.editores = {}
        for titulo, consulta, campos, columnas, guardar in especificaciones:
            editor = EditorCatalogo(sub, self, consulta, campos, columnas, guardar)
            sub.add(editor, text=titulo)
            self.editores[consulta] = editor

    def crear_compras(self):
        panel = self.panel("2. Compras")
        ttk.Label(
            panel, text="Registrar mercadería recibida y aceptada en el CD. Actualiza el costo promedio ponderado."
        ).pack(anchor="w")
        self.compra_form = Formulario(
            panel,
            [
                ("referencia", "Referencia única", None),
                ("proveedor", "Proveedor", self.opciones("proveedores")),
                ("cd", "Destino CD", self.opciones("ubicaciones", "CD")),
            ],
        )
        self.compra_form.pack(fill="x")
        self.orden_compra_seleccionada = None
        contexto = ttk.Frame(panel)
        contexto.pack(fill="x")
        self.contexto_compra = tk.StringVar(value="Compra independiente")
        ttk.Label(contexto, textvariable=self.contexto_compra, wraplength=900).pack(side="left")
        ttk.Button(contexto, text="Usar compra independiente", command=self.compra_independiente).pack(side="right")
        self.compra_items = Renglones(panel, self, compra=True)
        self.compra_items.pack(fill="both", expand=True)
        ttk.Button(
            panel, text="Confirmar compra recibida", style="Principal.TButton",
            command=lambda: self.ejecutar(self.confirmar_compra)
        ).pack(anchor="w", pady=8)
        self.compras = Tabla(
            panel,
            [
                ("id", "ID"),
                ("referencia", "Referencia"),
                ("fecha", "Fecha"),
                ("proveedor", "Proveedor"),
                ("cd", "CD"),
                ("total_centavos", "Total"),
            ],
            alto=4,
        )
        self.compras.pack(fill="both", expand=True)
        self.refrescadores.extend(
            [self.compra_form.actualizar, lambda: self.compras.cargar(self.sistema.listar("compras"))]
        )

    def confirmar_compra(self):
        f = self.compra_form
        identificador = self.sistema.registrar_compra(
            f.obtener("referencia"), f.obtener("proveedor"), f.obtener("cd"), self.compra_items.detalles(),
            orden_sugerida_id=self.orden_compra_seleccionada,
        )
        self.compra_items.limpiar()
        f.limpiar()
        self.compra_independiente()
        return f"Compra {identificador} registrada; stock y costo promedio del CD actualizados."

    def compra_independiente(self):
        self.orden_compra_seleccionada = None
        self.contexto_compra.set("Compra independiente")

    def crear_reposicion(self):
        panel = self.panel("3. Reposición")
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(1, weight=1)
        panel.rowconfigure(3, weight=1)
        self.orden_form = Formulario(
            panel,
            [
                ("cd", "CD abastecedor", self.opciones("ubicaciones", "CD")),
                ("local", "Local solicitante / destino", self.opciones("ubicaciones", "LOCAL")),
            ],
        )
        self.orden_form.grid(row=0, column=0, sticky="ew")
        self.orden_items = Renglones(panel, self)
        self.orden_items.grid(row=1, column=0, sticky="nsew")
        ttk.Button(panel, text="Crear orden por local", style="Principal.TButton", command=lambda: self.ejecutar(self.confirmar_orden)).grid(
            row=2, column=0, sticky="w", pady=5
        )
        self.ordenes = Tabla(
            panel,
            [
                ("id", "Orden"),
                ("cd", "CD"),
                ("local", "Destino"),
                ("solicitada", "Unidades pedidas"),
                ("asignada", "Unidades asignadas"),
            ],
            alto=4,
        )
        self.ordenes.grid(row=3, column=0, sticky="nsew")
        botones = ttk.Frame(panel)
        botones.grid(row=4, column=0, sticky="ew", pady=5)
        ttk.Button(botones, text="Ver pendientes", command=lambda: self.ejecutar(self.ver_orden)).pack(side="left")
        ttk.Button(
            botones,
            text="Preparar bulto de la orden seleccionada…",
            command=lambda: self.ejecutar(self.dialogo_preparar),
        ).pack(side="left", padx=8)
        self.refrescadores.extend(
            [self.orden_form.actualizar, lambda: self.ordenes.cargar(self.sistema.listar("ordenes"))]
        )

    def confirmar_orden(self):
        identificador = self.sistema.crear_orden(
            self.orden_form.obtener("cd"), self.orden_form.obtener("local"), self.orden_items.detalles()
        )
        self.orden_items.limpiar()
        return f"Orden {identificador} creada; solicitar no cambia el stock."

    def ver_orden(self):
        orden = self.ordenes.seleccionada()
        self.mostrar_tabla(
            f"Pendientes de la orden {orden['id']}",
            self.sistema.detalle_orden(orden["id"]),
            [
                ("codigo", "Código"),
                ("descripcion", "Producto"),
                ("solicitada", "Solicitada"),
                ("pendiente", "Por asignar"),
            ],
        )

    def dialogo_preparar(self):
        orden = self.ordenes.seleccionada()
        pendientes = [producto for producto in self.sistema.detalle_orden(orden["id"]) if producto["pendiente"] > 0]
        if not pendientes:
            raise ErrorDominio("La orden seleccionada ya fue asignada por completo.")
        ventana = tk.Toplevel(self.raiz)
        ventana.title(f"Preparar bulto · Orden {orden['id']} → {orden['local']}")
        ventana.geometry("850x460")
        ventana.minsize(700, 350)
        ventana.transient(self.raiz)
        ventana.grab_set()
        contenedor = ttk.Frame(ventana, padding=12)
        contenedor.pack(fill="both", expand=True)
        formulario = Formulario(contenedor, [("remito", "Número único de remito", None)])
        formulario.pack(fill="x")
        ttk.Label(contenedor, text="Dejá vacíos o en 0 los productos que no van en este bulto.").pack(anchor="w", pady=(5, 8))
        contenido = ContenidoBulto(contenedor, pendientes)

        def confirmar():
            detalles = contenido.detalles()
            identificador = self.sistema.preparar_bulto(
                orden["id"], formulario.obtener("remito"), detalles
            )
            ventana.destroy()
            return f"Bulto {identificador} preparado: mercadería reservada en el CD."

        acciones = ttk.Frame(contenedor)
        acciones.pack(side="bottom", fill="x", pady=(8, 0))
        ttk.Button(acciones, text="Preparar y reservar", style="Principal.TButton",
                   command=lambda: self.ejecutar(confirmar)).pack(side="left")
        ttk.Button(acciones, text="Cargar todo lo pendiente", command=contenido.cargar_pendientes).pack(side="left", padx=8)
        ttk.Button(acciones, text="Cancelar", command=ventana.destroy).pack(side="right")
        contenido.pack(fill="both", expand=True)
        formulario.widgets["remito"].focus_set()

    def crear_logistica(self):
        panel = self.panel("4. Logística")
        self.ayuda_logistica = tk.StringVar()
        ttk.Label(panel, textvariable=self.ayuda_logistica, style="Estado.TLabel", wraplength=910).pack(fill="x")
        self.bultos = Tabla(
            panel,
            [
                ("id", "Bulto"),
                ("orden_id", "Orden"),
                ("remito", "Remito"),
                ("precinto", "Precinto"),
                ("estado", "Estado bulto"),
                ("estado_remito", "Estado remito"),
                ("destino", "Destino"),
            ],
        )
        self.bultos.pack(fill="both", expand=True, pady=8)
        self.logistica_form = Formulario(
            panel,
            [
                ("precinto", "Precinto asignado / observado", None),
                ("local", "Local receptor", self.opciones("ubicaciones", "LOCAL")),
                ("motivo", "Motivo si el precinto está roto", None),
            ],
        )
        self.logistica_form.pack(fill="x")
        self.roto = tk.BooleanVar(value=False)
        self.casilla_roto = ttk.Checkbutton(
            panel, text="Precinto roto: rechazar y bloquear mercadería", variable=self.roto,
            command=self.actualizar_controles_logistica,
        )
        self.casilla_roto.pack(anchor="w", pady=5)
        botones = ttk.Frame(panel)
        botones.pack(fill="x", pady=8)
        self.botones_logistica = {}
        for titulo, accion in [
            ("1. Precintar", "precintar"),
            ("2. Despachar", "despachar"),
            ("3. Recibir", "recibir"),
            ("4. Verificar / rechazar", "verificar"),
        ]:
            boton = ttk.Button(
                botones, text=titulo, style="Principal.TButton",
                command=lambda a=accion: self.ejecutar(lambda: self.operar_bulto(a))
            )
            boton.pack(side="left", padx=(0, 8))
            self.botones_logistica[accion] = boton
        self.boton_detalle_bulto = ttk.Button(
            panel, text="Consultar historial y contenido", command=lambda: self.ejecutar(self.ver_bulto)
        )
        self.boton_detalle_bulto.pack(anchor="w")
        self.seleccion_logistica = None
        self.ventana_bulto = None
        self.bultos.arbol.bind("<<TreeviewSelect>>", self.actualizar_controles_logistica)
        self.refrescadores.extend([self.logistica_form.actualizar, self.refrescar_bultos])
        self.actualizar_controles_logistica()

    def refrescar_bultos(self):
        self.bultos.cargar(self.sistema.listar("bultos"))
        self.actualizar_controles_logistica()

    def actualizar_controles_logistica(self, _evento=None):
        seleccion = self.bultos.arbol.selection()
        fila = self.bultos.filas.get(seleccion[0], {}) if seleccion else {}
        estado = fila.get("estado")
        accion = {"Preparado": "precintar", "Precintado": "despachar",
                  "En tránsito": "recibir", "Recibido": "verificar"}.get(estado)
        ayuda = {
            "Preparado": "Ingresá el código del precinto y pulsá Precintar.",
            "Precintado": "Pulsá Despachar cuando el bulto salga del centro de distribución.",
            "En tránsito": "Elegí el local receptor y pulsá Recibir cuando llegue el bulto.",
            "Recibido": "Ingresá el precinto observado y verificá el contenido. Si el precinto está roto, marcá la casilla e indicá el motivo.",
            "Verificado": "La recepción quedó verificada. El historial incluye las transiciones y el contenido recibido.",
            "Rechazado": "La mercadería quedó bloqueada. Consultá el historial para ver el motivo.",
        }
        self.ayuda_logistica.set(f"{estado} · {ayuda[estado]}" if estado in ayuda else "Seleccioná un bulto para ver qué acción sigue.")
        clave = (fila.get("id"), estado)
        form = self.logistica_form
        if clave != self.seleccion_logistica:
            self.seleccion_logistica = clave
            self.roto.set(False)
            form.variables["motivo"].set("")
            form.variables["precinto"].set("" if accion in ("precintar", "verificar") else fila.get("precinto") or "")
        for nombre, boton in self.botones_logistica.items():
            boton.state(["!disabled" if nombre == accion else "disabled"])
        self.boton_detalle_bulto.state(["!disabled" if fila else "disabled"])
        self.casilla_roto.state(["!disabled" if accion == "verificar" else "disabled"])
        form.etiquetas["precinto"]["text"] = "Precinto observado" if accion == "verificar" else "Precinto asignado"
        form.widgets["precinto"]["state"] = "normal" if accion in ("precintar", "verificar") else "readonly"
        form.widgets["local"]["state"] = "readonly" if accion in ("recibir", "verificar") else "disabled"
        form.widgets["motivo"]["state"] = "normal" if accion == "verificar" and self.roto.get() else "disabled"

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
            self.sistema.verificar(
                identificador,
                f.obtener("local"),
                f.obtener("precinto"),
                self.roto.get(),
                f.obtener("motivo"),
            )
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
        secciones = [
            ("Historial", self.sistema.historial_bulto(identificador), [
                ("anterior", "Anterior"), ("nuevo", "Nuevo"), ("fecha", "Fecha"), ("observacion", "Evidencia"),
            ]),
            ("Contenido", self.sistema.contenido_bulto(identificador), [
                ("codigo", "Código"),
                ("descripcion", "Producto"),
                ("cantidad", "Cantidad"),
                ("costo_centavos", "Costo unit. transf."),
            ]),
            ("Lotes", self.sistema.lotes_bulto(identificador), [
                ("codigo", "Lote"), ("producto_id", "Producto"), ("cantidad", "Unidades"), ("vencimiento", "Vencimiento"),
            ]),
        ]
        if self.ventana_bulto is not None and self.ventana_bulto.winfo_exists():
            self.ventana_bulto.destroy()
        ventana = self.ventana_bulto = tk.Toplevel(self.raiz)
        ventana.title(f"Detalle del bulto {identificador}")
        ventana.geometry("950x420")
        ventana.transient(self.raiz)
        pestanas = ttk.Notebook(ventana)
        pestanas.pack(fill="both", expand=True, padx=12, pady=12)
        for titulo, filas, columnas in secciones:
            tabla = Tabla(pestanas, columnas)
            pestanas.add(tabla, text=titulo)
            tabla.cargar(filas)

    def crear_inventario(self):
        panel = self.panel("5. Inventario")
        self.minimo_form = Formulario(
            panel,
            [
                ("ubicacion", "Ubicación", self.opciones("ubicaciones")),
                ("producto", "Producto", self.opciones("productos")),
                ("minimo", "Mínimo (unidades)", None),
            ],
        )
        self.minimo_form.pack(fill="x")
        acciones = ttk.Frame(panel)
        acciones.pack(fill="x", pady=8)
        ttk.Button(acciones, text="Guardar mínimo", style="Principal.TButton",
                   command=lambda: self.ejecutar(self.guardar_minimo)).pack(side="left")
        ttk.Button(acciones, text="Editar mínimo de la fila", command=lambda: self.ejecutar(self.editar_minimo)).pack(
            side="left", padx=8)

        filtros = ttk.Frame(panel)
        filtros.pack(fill="x", pady=(4, 8))
        ttk.Label(filtros, text="Buscar producto").pack(side="left")
        self.busqueda_inventario = tk.StringVar()
        ttk.Entry(filtros, textvariable=self.busqueda_inventario, width=28).pack(side="left", padx=8)
        self.ubicaciones_inventario = {}
        self.filtro_ubicaciones = ttk.Menubutton(filtros, text="Todas las ubicaciones", direction="below")
        self.menu_ubicaciones = tk.Menu(self.filtro_ubicaciones, tearoff=False)
        self.filtro_ubicaciones.configure(menu=self.menu_ubicaciones)
        self.filtro_ubicaciones.pack(side="left", padx=(4, 8))
        ttk.Button(filtros, text="Limpiar filtros", command=self.limpiar_filtros_inventario).pack(side="left")
        self.resultados_inventario = ttk.Label(filtros, style="Ayuda.TLabel")
        self.resultados_inventario.pack(side="right")
        self.inventario = Tabla(
            panel,
            [
                ("ubicacion", "Ubicación"),
                ("codigo", "Código"),
                ("descripcion", "Producto"),
                ("disponible", "Disp. registrado"),
                ("vendible", "Vendible"),
                ("vencido", "Vencido"),
                ("reservado", "Reservado"),
                ("pendiente", "Pendiente"),
                ("rechazado", "Rechazado"),
                ("minimo", "Mínimo"),
                ("faltante", "Faltante"),
                ("costo_centavos", "Costo prom. disp."),
                ("valor_disponible_centavos", "Valor disp."),
            ],
        )
        self.inventario.pack(fill="both", expand=True)
        ttk.Label(
            panel,
            text="Disponible es el saldo físico registrado; Vendible excluye lotes vencidos. Faltante usa Vendible. El costo promedio corresponde al saldo Disponible registrado; no se destruye stock por vencer.",
            wraplength=1000,
        ).pack(anchor="w", pady=10)
        self.filas_inventario = []
        self.busqueda_inventario.trace_add("write", self.filtrar_inventario)
        self.refrescadores.extend([self.minimo_form.actualizar, self.refrescar_inventario])

    def refrescar_inventario(self):
        self.filas_inventario = self.sistema.listar("inventario")
        ubicaciones = self.opciones("ubicaciones")()
        self.menu_ubicaciones.delete(0, "end")
        self.menu_ubicaciones.add_command(label="Todas las ubicaciones",
                                         command=lambda: self.limpiar_filtros_inventario(solo_ubicaciones=True))
        self.menu_ubicaciones.add_separator()
        anteriores = self.ubicaciones_inventario
        self.ubicaciones_inventario = {}
        for identificador, nombre in ubicaciones:
            variable = anteriores.get(identificador)
            if variable is None:
                variable = tk.BooleanVar(value=False)
            self.ubicaciones_inventario[identificador] = variable
            self.menu_ubicaciones.add_checkbutton(label=nombre, variable=variable, command=self.filtrar_inventario)
        self.filtrar_inventario()

    def filtrar_inventario(self, *_):
        seleccionadas = {id_ for id_, variable in self.ubicaciones_inventario.items() if variable.get()}
        palabras = self.busqueda_inventario.get().casefold().split()
        filas = []
        for fila in self.filas_inventario:
            ubicacion, producto = fila["ubicacion_id"], fila["producto_id"]
            if seleccionadas and ubicacion not in seleccionadas:
                continue
            etiqueta = f"{fila['codigo']} {fila['descripcion']}".casefold()
            if all(palabra in etiqueta for palabra in palabras):
                filas.append(dict(fila, id=(ubicacion, producto)))
        titulo = f"Ubicaciones ({len(seleccionadas)})" if seleccionadas else "Todas las ubicaciones"
        self.filtro_ubicaciones.configure(text=titulo)
        self.resultados_inventario.configure(text=f"Filas: {len(filas)} de {len(self.filas_inventario)}")
        self.inventario.cargar(filas)

    def limpiar_filtros_inventario(self, solo_ubicaciones=False):
        for variable in self.ubicaciones_inventario.values():
            variable.set(False)
        if solo_ubicaciones:
            self.filtrar_inventario()
        else:
            self.busqueda_inventario.set("")

    def editar_minimo(self):
        fila = self.inventario.seleccionada()
        self.minimo_form.completar({"ubicacion": fila["ubicacion_id"], "producto": fila["producto_id"], "minimo": fila["minimo"]})
        campo = self.minimo_form.widgets["minimo"]
        campo.focus_set()
        campo.selection_range(0, "end")
        return f"Editando mínimo de {fila['codigo']} en {fila['ubicacion']}."

    def guardar_minimo(self):
        f = self.minimo_form
        self.sistema.configurar_minimo(
            f.obtener("ubicacion"), f.obtener("producto"), f.obtener("minimo")
        )
        return "Mínimo guardado. El faltante se calcula sobre el stock vendible."

    def crear_ventas(self):
        panel = self.panel("6. Ventas y caja")
        secciones = ttk.Notebook(panel)
        secciones.pack(fill="both", expand=True)
        nueva = ttk.Frame(secciones, padding=8)
        historial = ttk.Frame(secciones, padding=8)
        secciones.add(nueva, text="Nueva venta")
        secciones.add(historial, text="Historial y caja")

        nueva.columnconfigure(0, weight=1, uniform="ventas")
        nueva.columnconfigure(1, weight=1, uniform="ventas")
        nueva.rowconfigure(2, weight=1)
        ttk.Label(
            nueva,
            text="Elegí el local para ver sus productos vendibles. Usá Saldar resto para cubrir el importe pendiente.",
            style="Ayuda.TLabel", wraplength=910,
        ).grid(row=0, column=0, columnspan=2, sticky="w")
        self.venta_form = Formulario(
            nueva,
            [
                ("local", "Local de venta", self.opciones("ubicaciones", "LOCAL")),
                ("comprobante", "N° comprobante (opcional)", None),
            ],
        )
        self.venta_form.grid(row=1, column=0, columnspan=2, sticky="ew")
        self.refrescadores.append(self.venta_form.actualizar)
        self.venta_items = Renglones(
            nueva, self, al_cambiar=lambda: self.venta_cobros.actualizar_resumen(),
            opciones_productos=self.opciones_productos_venta, validar_cantidad=self.validar_cantidad_venta,
        )
        self.venta_items.configure(text="Productos del local")
        self.venta_items.grid(row=2, column=0, sticky="nsew", padx=(0, 6), pady=4)
        self.ayuda_stock_venta = ttk.Label(nueva, style="Ayuda.TLabel", wraplength=920)
        self.ayuda_stock_venta.grid(row=3, column=0, columnspan=2, sticky="w")
        self.venta_form.widgets["local"].bind("<<ComboboxSelected>>", self.cambiar_local_venta)
        self.venta_cobros = RenglonesCobro(nueva, self, self.venta_items)
        self.venta_cobros.grid(row=2, column=1, sticky="nsew", padx=(6, 0), pady=4)
        acciones_nueva = ttk.Frame(nueva)
        acciones_nueva.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(5, 0))
        self.boton_confirmar_venta = ttk.Button(
            acciones_nueva,
            text="Confirmar venta y emitir comprobante",
            style="Principal.TButton",
            command=lambda: self.ejecutar(self.confirmar_venta),
        )
        self.boton_confirmar_venta.pack(side="left")
        ttk.Button(
            acciones_nueva,
            text="Ver movimientos de caja",
            command=lambda: self.ejecutar(self.ver_caja),
        ).pack(side="left", padx=8)

        acciones_hist = ttk.Frame(historial)
        acciones_hist.pack(fill="x", pady=(0, 6))
        ttk.Button(
            acciones_hist,
            text="Ver comprobante y detalle",
            command=lambda: self.ejecutar(self.ver_comprobante),
        ).pack(side="left")
        ttk.Button(
            acciones_hist,
            text="Ver movimientos de caja",
            command=lambda: self.ejecutar(self.ver_caja),
        ).pack(side="left", padx=8)
        self.ventas = Tabla(
            historial,
            [
                ("id", "Venta"),
                ("comprobante", "Comprobante"),
                ("fecha", "Fecha"),
                ("local", "Local"),
                ("unidades", "Unidades"),
                ("total_centavos", "Total venta"),
                ("costo_total_centavos", "Costo hist."),
                ("margen_centavos", "Margen"),
            ],
            alto=12,
        )
        self.ventas.pack(fill="both", expand=True)
        self.refrescadores.extend(
            [
                self.actualizar_controles_venta,
                self.venta_cobros.actualizar_resumen,
                lambda: self.ventas.cargar(self.sistema.listar("ventas")),
            ]
        )

    def opciones_productos_venta(self, items):
        if not self.venta_form.variables["local"].get():
            return []
        local_id = self.venta_form.obtener("local")
        agregadas = {}
        for item in items:
            producto_id = item["producto_id"]
            agregadas[producto_id] = agregadas.get(producto_id, 0) + item["cantidad"]
        opciones = []
        for fila in self.filas_inventario:
            producto_id = fila["producto_id"]
            disponible = fila["vendible"] - agregadas.get(producto_id, 0)
            if fila["ubicacion_id"] == local_id and disponible > 0:
                opciones.append((producto_id, f"{disponible} uds. · {fila['codigo']} {fila['descripcion']}"))
        return opciones

    def validar_cantidad_venta(self, producto_id, cantidad):
        local_id = self.venta_form.obtener("local")
        agregada = sum(unidades for id_, unidades in self.venta_items.detalles() if id_ == producto_id)
        restante = max(0, self.sistema.cantidad_vendible(local_id, producto_id) - agregada)
        if cantidad > restante:
            unidad = "unidad" if restante == 1 else "unidades"
            raise ErrorDominio(f"Podés agregar hasta {restante} {unidad} de ese producto en este local.")

    def cambiar_local_venta(self, _evento):
        self.venta_items.formulario.limpiar()
        self.venta_items.formulario.actualizar()
        self.actualizar_controles_venta()

    def actualizar_controles_venta(self):
        con_productos = bool(self.venta_items.items)
        self.venta_form.widgets["local"].configure(state="disabled" if con_productos else "readonly")
        tiene_opciones = bool(self.venta_items.formulario.variables["producto"].get())
        mensaje = "El selector indica cuántas unidades todavía podés agregar de cada producto."
        if not tiene_opciones:
            mensaje = "Este local no tiene más unidades vendibles para agregar."
        if not self.venta_form.variables["local"].get():
            mensaje = "Registrá un local para iniciar una venta."
        if con_productos:
            mensaje += " Para cambiar de local, quitá los productos de la venta."
        self.ayuda_stock_venta.configure(text=mensaje)

    def confirmar_venta(self):
        local_id = self.venta_form.obtener("local")
        numero_comp = self.venta_form.obtener("comprobante").strip() or None
        venta_id = self.sistema.registrar_venta(
            local_id,
            self.venta_items.detalles(),
            self.venta_cobros.cobros(),
            numero_comp,
        )
        comp = self.sistema.comprobante_venta(venta_id)
        self.venta_items.limpiar()
        self.venta_cobros.limpiar()
        self.venta_form.limpiar()
        return f"Venta {venta_id} confirmada con comprobante {comp['numero']}; stock y caja actualizados."

    def ver_comprobante(self):
        venta = self.ventas.seleccionada()
        comp = self.sistema.comprobante_venta(venta["id"])
        ventana = tk.Toplevel(self.raiz)
        ventana.title(f"Comprobante {comp['numero']} · Venta #{comp['venta_id']}")
        ventana.geometry("960x520")
        contenedor = ttk.Frame(ventana, padding=12)
        contenedor.pack(fill="both", expand=True)
        ttk.Label(
            contenedor,
            text=(
                f"Comprobante: {comp['numero']}   |   Local: {comp['local']}   |   "
                f"Fecha: {comp['fecha']}   |   Total: ${importe(comp['total_centavos'])}"
            ),
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor="w", pady=(0, 8))
        ttk.Label(contenedor, text="Detalles de la venta (precios y costos históricos conservados):").pack(anchor="w")
        tabla_detalles = Tabla(
            contenedor,
            [
                ("codigo", "Código"),
                ("descripcion", "Producto"),
                ("cantidad", "Cantidad"),
                ("precio_unitario_centavos", "Precio unit."),
                ("costo_unitario_centavos", "Costo unit."),
                ("subtotal_centavos", "Subtotal"),
                ("margen_centavos", "Margen"),
            ],
            alto=5,
        )
        tabla_detalles.pack(fill="both", expand=True, pady=(2, 8))
        tabla_detalles.cargar(comp["detalles"])
        ttk.Label(contenedor, text="Cobros registrados:").pack(anchor="w")
        tabla_cobros = Tabla(
            contenedor,
            [("id", "ID cobro"), ("medio_pago", "Medio de pago"), ("importe_centavos", "Importe"), ("fecha", "Fecha")],
            alto=3,
        )
        tabla_cobros.pack(fill="both", expand=True, pady=2)
        tabla_cobros.cargar(comp["cobros"])

    def ver_caja(self):
        self.mostrar_tabla(
            "Movimientos de caja registrados",
            self.sistema.listar("caja"),
            [
                ("id", "ID"),
                ("fecha", "Fecha"),
                ("local", "Local"),
                ("tipo", "Tipo"),
                ("medio_pago", "Medio de pago"),
                ("importe_centavos", "Importe"),
                ("causa", "Causa"),
                ("referencia_id", "Ref."),
            ],
        )
