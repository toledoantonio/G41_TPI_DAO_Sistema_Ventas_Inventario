"""SQLite 3 con Patrón Singleton (Cap. 15): gestor único de base de datos y transacciones."""

from contextlib import contextmanager
from pathlib import Path
import sqlite3
from threading import RLock

from backend.database.migraciones import migrar_costos


class BaseDatos:
    """Gestor de conexiones y transacciones SQLite implementado como Singleton (Cap. 15.3).

    Garantiza una única instancia del gestor de base de datos en el sistema,
    controlando su creación mediante __new__ y evitando reinicializaciones
    redundantes mediante la bandera _initialized.
    """

    _instance = None
    _initialized = False
    _lock = RLock()

    def __new__(cls, ruta=None):
        """Sobrescribe __new__ para controlar la creación de la única instancia (GoF)."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(BaseDatos, cls).__new__(cls)
        return cls._instance

    def __init__(self, ruta=None):
        """Inicializa la configuración y el esquema solo en la primera creación."""
        with BaseDatos._lock:
            ruta_normalizada = Path(ruta).expanduser().resolve() if ruta is not None else None
            if BaseDatos._initialized:
                if ruta_normalizada is not None and self._ruta != ruta_normalizada:
                    raise ValueError("La base de datos ya está configurada con otra ruta; reinicie la aplicación para cambiarla.")
                return
            if ruta_normalizada is None:
                raise ValueError("Debe proporcionar la ruta de la base de datos en la primera inicialización.")
            self._ruta = ruta_normalizada
            self._ruta.parent.mkdir(parents=True, exist_ok=True)
            with self.conectar() as conexion:
                try:
                    esquema = Path(__file__).with_name("esquema.sql").read_text(encoding="utf-8")
                    conexion.executescript("BEGIN IMMEDIATE;\n" + esquema)
                    migrar_costos(conexion)
                    conexion.commit()
                except Exception:
                    conexion.rollback()
                    raise
            BaseDatos._initialized = True

    @property
    def ruta(self):
        return self._ruta

    @classmethod
    def obtener_instancia(cls, ruta=None):
        """Método de clase para acceder a la instancia única del gestor."""
        return cls(ruta)

    @classmethod
    def reset_for_testing(cls):
        """Resetea el estado del Singleton para ambientes de testing (Cap. 15.5.2)."""
        with cls._lock:
            cls._instance = None
            cls._initialized = False

    @contextmanager
    def conectar(self):
        conexion = sqlite3.connect(self._ruta, timeout=10)
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
