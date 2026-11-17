"""Estilos compartidos de la aplicación de escritorio."""

from tkinter import ttk


FONDO = "#f0f5f7"
SUPERFICIE = "#ffffff"
TEXTO = "#193441"
SECUNDARIO = "#496875"
BORDE = "#c5d5dd"
PRINCIPAL = "#006956"
ENCABEZADO = "#173b4c"
SELECCION = "#d2ebe4"


def aplicar_estilos(raiz):
    raiz.configure(background=FONDO)
    estilo = ttk.Style(raiz)
    estilo.theme_use("clam")
    estilo.configure(".", font=("Segoe UI", 10), foreground=TEXTO, background=FONDO)
    estilo.configure("Encabezado.TFrame", background=ENCABEZADO)
    estilo.configure("Titulo.TLabel", background=ENCABEZADO, foreground=SUPERFICIE, font=("Segoe UI", 19, "bold"))
    estilo.configure("Subtitulo.TLabel", background=ENCABEZADO, foreground="#d6e7ed")
    estilo.configure("Ayuda.TLabel", foreground=SECUNDARIO)
    estilo.configure("Estado.TLabel", background="#e2eeef", foreground=TEXTO, padding=(12, 7))
    estilo.configure("Correcto.Estado.TLabel", background="#def2e9", foreground="#155540")
    estilo.configure("Error.Estado.TLabel", background="#fae4df", foreground="#842d21")

    estilo.configure("TNotebook", borderwidth=0, tabmargins=(0, 3, 0, 0))
    estilo.configure("TNotebook.Tab", padding=(11, 7), background="#e1ebef", foreground=SECUNDARIO)
    estilo.map("TNotebook.Tab", background=[("selected", PRINCIPAL), ("active", "#cfe1e7")],
               foreground=[("selected", SUPERFICIE)])
    estilo.configure("TLabelframe", bordercolor=BORDE, lightcolor=BORDE, darkcolor=BORDE)
    estilo.configure("TLabelframe.Label", font=("Segoe UI", 10, "bold"))

    estilo.configure("TButton", padding=(10, 5), background=SUPERFICIE, bordercolor=BORDE,
                     lightcolor=SUPERFICIE, darkcolor=SUPERFICIE)
    estilo.map("TButton", background=[("disabled", "#e6edf0"), ("pressed", "#cbdee5"), ("active", "#e3eff3")],
               foreground=[("disabled", "#617783")], bordercolor=[("focus", "#38798b")])
    estilo.configure("Principal.TButton", background=PRINCIPAL, foreground=SUPERFICIE,
                     bordercolor=PRINCIPAL, lightcolor=PRINCIPAL, darkcolor=PRINCIPAL)
    estilo.map("Principal.TButton", background=[("disabled", "#e6edf0"), ("pressed", "#004c3e"), ("active", "#087b66")],
               foreground=[("disabled", "#617783"), ("!disabled", SUPERFICIE)],
               bordercolor=[("disabled", BORDE), ("focus", "#429bab")],
               lightcolor=[("disabled", "#e6edf0")], darkcolor=[("disabled", "#e6edf0")])

    for control in ("TEntry", "TCombobox"):
        estilo.configure(control, padding=(6, 4), fieldbackground=SUPERFICIE, bordercolor=BORDE)
        estilo.map(control, fieldbackground=[("disabled", "#e8eef1"), ("readonly", SUPERFICIE)],
                   bordercolor=[("focus", "#38798b")])
    estilo.configure("Treeview", rowheight=28, background=SUPERFICIE, fieldbackground=SUPERFICIE,
                     bordercolor=BORDE, lightcolor=BORDE, darkcolor=BORDE)
    estilo.configure("Treeview.Heading", padding=(7, 5), background="#dce9ee", foreground=TEXTO,
                     font=("Segoe UI", 10, "bold"))
    estilo.map("Treeview", background=[("selected", SELECCION)], foreground=[("selected", TEXTO)])
