"""Vista gráfica de los resultados filtrados de reportes en Tkinter."""

import tkinter as tk
from tkinter import ttk

from backend.models.entidades import importe


GRAFICOS = {
    "ventas_ingresos": (0, ("local",), (("ventas_centavos", "Venta bruta"), ("neto_centavos", "Venta neta")), "$"),
    "ranking_margen": (0, ("local", "codigo"), (("margen_centavos", "Margen estimado"),), "$"),
    "existencias_minimos": (1, ("ubicacion", "codigo"), (("vendible", "Vendible"), ("minimo", "Mínimo")), "unidades"),
    "rechazos_precinto": (0, ("local",), (("evaluados", "Bultos evaluados"), ("rechazados", "Bultos rechazados")), "bultos"),
}


class GraficoReporte(ttk.Frame):
    COLORES = ("#206172", "#b45c25")

    def __init__(self, padre, reporte):
        super().__init__(padre, padding=8)
        seccion, etiquetas, self.series, self.unidad = GRAFICOS[reporte["tipo"]]
        filas = reporte["secciones"][seccion]["filas"]
        self.filas = [
            (" · ".join(str(fila[clave]) for clave in etiquetas), [fila[clave] for clave, _ in self.series])
            for fila in filas
        ]
        if not self.filas:
            ttk.Label(self, text="Sin datos para estos filtros.").pack(anchor="w")
            return

        leyenda = ttk.Frame(self)
        leyenda.pack(fill="x", pady=(0, 6))
        for color, (_, nombre) in zip(self.COLORES, self.series):
            ttk.Label(leyenda, text=f"■ {nombre}", foreground=color).pack(side="left", padx=(0, 16))
        ttk.Label(leyenda, text=f"Unidad: {self.unidad}").pack(side="left")

        self.lienzo = tk.Canvas(self, background="#ffffff", highlightthickness=0, height=260)
        vertical = ttk.Scrollbar(self, orient="vertical", command=self.lienzo.yview)
        horizontal = ttk.Scrollbar(self, orient="horizontal", command=self.lienzo.xview)
        self.lienzo.configure(xscrollcommand=horizontal.set, yscrollcommand=vertical.set)
        vertical.pack(side="right", fill="y")
        horizontal.pack(side="bottom", fill="x")
        self.lienzo.pack(fill="both", expand=True)
        self.lienzo.bind("<Configure>", self.dibujar)
        self.lienzo.bind("<MouseWheel>", lambda evento: self.lienzo.yview_scroll(-int(evento.delta / 120), "units"))

    def dibujar(self, evento):
        lienzo = self.lienzo
        lienzo.delete("all")
        valores = [valor for _, serie in self.filas for valor in serie]
        minimo, maximo = min(0, min(valores)), max(0, max(valores))
        ancho = max(620, evento.width)
        izquierda, derecha = 310, ancho - 100
        paso_fila = 18 * len(self.series) + 23
        alto = 26 + paso_fila * len(self.filas)
        escala = (derecha - izquierda) / (maximo - minimo or 1)
        cero = izquierda - minimo * escala
        lienzo.create_line(cero, 12, cero, alto - 8, fill="#849197")
        for indice, (etiqueta, serie) in enumerate(self.filas):
            y = 18 + indice * paso_fila
            lienzo.create_text(10, y, anchor="nw", text=etiqueta, width=210, fill="#17232a")
            for numero, (valor, color) in enumerate(zip(serie, self.COLORES)):
                centro = y + numero * 18 + 7
                extremo = cero + valor * escala
                if valor:
                    lienzo.create_rectangle(min(cero, extremo), centro - 5, max(cero, extremo), centro + 5,
                                            fill=color, outline="")
                texto = f"${importe(valor)}" if self.unidad == "$" else str(valor)
                lienzo.create_text(extremo + (-5 if valor < 0 else 5), centro, text=texto,
                                   anchor="e" if valor < 0 else "w", fill="#17232a")
        lienzo.configure(scrollregion=(0, 0, ancho, alto))
