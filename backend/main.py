"""Ejecutar desde la raíz: python -m backend.main [--demo] [--db RUTA]."""

import argparse
from pathlib import Path
import tkinter as tk

from backend.demo import cargar_demo
from backend.services.sistema import Sistema
from frontend.app import Aplicacion


def main():
    parser = argparse.ArgumentParser(description="G41 · Catálogo y logística con SQLite 3")
    parser.add_argument("--db", type=Path, help="Archivo SQLite 3; por defecto se guarda en data/")
    parser.add_argument("--demo", action="store_true", help="Usar base separada con datos iniciales de demostración")
    argumentos = parser.parse_args()
    ruta = argumentos.db or Path(__file__).resolve().parents[1] / "data" / (
        "demo.sqlite3" if argumentos.demo else "inventario.sqlite3")
    sistema = Sistema(ruta)
    if argumentos.demo:
        cargar_demo(sistema)
    raiz = tk.Tk()
    Aplicacion(raiz, sistema)
    raiz.mainloop()


if __name__ == "__main__":
    main()
