"""Conexion a SQLite y manejo de transacciones."""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

import config


def abrir_conexion(db_path=None) -> sqlite3.Connection:
    """Abre una conexion con filas tipo diccionario y claves foraneas activas.

    Si el archivo no existe lanza FileNotFoundError (sqlite3 crearia una BD vacia en silencio).
    Acepta ":memory:" para pruebas.
    """
    ruta = db_path if db_path is not None else config.DB_PATH
    if str(ruta) != ":memory:" and not Path(ruta).exists():
        raise FileNotFoundError(
            f"No se encontro la base de datos en {ruta}. "
            "Copia bodega.db a la carpeta data/ o ejecuta scripts/inicializar_bd.py."
        )
    conn = sqlite3.connect(str(ruta))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def conexion(db_path=None):
    """Context manager: commit si todo sale bien, rollback si hay error, y siempre cierra.

    Los repositorios NO hacen commit; la transaccion la controla quien llama (p. ej. el orquestador).
    """
    conn = abrir_conexion(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
