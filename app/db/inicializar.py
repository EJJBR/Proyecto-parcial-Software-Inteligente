"""Crea la base de datos desde data/schema.sql y data/seed.sql."""
import sqlite3

import config


def crear_base(conn: sqlite3.Connection, con_datos: bool = True) -> None:
    """Ejecuta el esquema y, opcionalmente, los datos de prueba sobre una conexion."""
    conn.executescript(config.SCHEMA_SQL.read_text(encoding="utf-8"))
    if con_datos:
        conn.executescript(config.SEED_SQL.read_text(encoding="utf-8"))
    conn.commit()
