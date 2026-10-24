"""SQLite 3: una conexión por operación, con confirmación o reversión conjunta."""

from contextlib import contextmanager
from pathlib import Path
import sqlite3


class BaseDatos:
    def __init__(self, ruta):
        self.ruta = Path(ruta)
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        with self.conectar() as conexion:
            conexion.executescript(Path(__file__).with_name("esquema.sql").read_text(encoding="utf-8"))

    @contextmanager
    def conectar(self):
        conexion = sqlite3.connect(self.ruta, timeout=10)
        conexion.row_factory = sqlite3.Row
        conexion.execute("PRAGMA foreign_keys = ON")
        try:
            yield conexion
        finally:
            conexion.close()

    @contextmanager
    def transaccion(self):
        with self.conectar() as conexion:
            try:
                # Validación y escritura ven los mismos saldos, incluso con dos ventanas.
                conexion.execute("BEGIN IMMEDIATE")
                yield conexion
                conexion.commit()
            except Exception:
                conexion.rollback()
                raise
