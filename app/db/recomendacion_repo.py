"""Guardado y lectura de recomendaciones (RECOMENDACION + DETALLE_RECOMENDACION)."""
import sqlite3
from datetime import date
from typing import Mapping


class RecomendacionYaExiste(Exception):
    """RECOMENDACION.id_solicitud es unico: ya hay una recomendacion para esa solicitud."""


def existe_recomendacion(conn: sqlite3.Connection, id_solicitud: int) -> bool:
    return conn.execute("SELECT 1 FROM RECOMENDACION WHERE id_solicitud = ?", (id_solicitud,)).fetchone() is not None


def eliminar_recomendacion(conn: sqlite3.Connection, id_solicitud: int) -> bool:
    """Borra la recomendacion de una solicitud y su detalle. No hace commit. True si existia."""
    fila = conn.execute("SELECT id_recomendacion FROM RECOMENDACION WHERE id_solicitud = ?", (id_solicitud,)).fetchone()
    if fila is None:
        return False
    conn.execute("DELETE FROM DETALLE_RECOMENDACION WHERE id_recomendacion = ?", (fila[0],))
    conn.execute("DELETE FROM RECOMENDACION WHERE id_recomendacion = ?", (fila[0],))
    return True


def guardar_recomendacion(conn: sqlite3.Connection, id_solicitud: int, fitness_final: float,
                          costo_total: float, explicacion_texto: str | None,
                          cantidades: Mapping[int, int], fecha: str | None = None,
                          reemplazar: bool = False) -> int:
    """Guarda la recomendacion y el detalle (solo productos con cantidad > 0). No hace commit.

    cantidades: {id_producto: cantidad}. Si ya existe una recomendacion para la solicitud, lanza
    RecomendacionYaExiste, salvo que reemplazar=True (entonces borra la anterior y guarda la nueva).
    Devuelve id_recomendacion.
    """
    if conn.execute("SELECT 1 FROM SOLICITUD WHERE id_solicitud = ?", (id_solicitud,)).fetchone() is None:
        raise ValueError(f"No existe la solicitud {id_solicitud}.")
    if existe_recomendacion(conn, id_solicitud):
        if not reemplazar:
            raise RecomendacionYaExiste(f"La solicitud {id_solicitud} ya tiene una recomendacion guardada.")
        eliminar_recomendacion(conn, id_solicitud)

    cur = conn.execute(
        """INSERT INTO RECOMENDACION (id_solicitud, fecha, fitness_final, costo_total, explicacion_texto)
           VALUES (?,?,?,?,?)""",
        (id_solicitud, fecha or date.today().isoformat(), fitness_final, costo_total, explicacion_texto))
    id_rec = cur.lastrowid
    for id_producto, cantidad in sorted(cantidades.items()):
        if cantidad > 0:
            conn.execute(
                "INSERT INTO DETALLE_RECOMENDACION (id_recomendacion, id_producto, cantidad_recomendada) VALUES (?,?,?)",
                (id_rec, id_producto, int(cantidad)))
    return id_rec


def obtener_recomendacion(conn: sqlite3.Connection, id_solicitud: int) -> dict | None:
    """Devuelve la recomendacion de una solicitud con su detalle (nombre y cantidad por producto)."""
    fila = conn.execute("SELECT * FROM RECOMENDACION WHERE id_solicitud = ?", (id_solicitud,)).fetchone()
    if fila is None:
        return None
    detalle = [dict(r) for r in conn.execute(
        """SELECT d.id_producto, p.nombre, d.cantidad_recomendada
           FROM DETALLE_RECOMENDACION d JOIN PRODUCTO p ON p.id_producto = d.id_producto
           WHERE d.id_recomendacion = ? ORDER BY d.id_producto""", (fila["id_recomendacion"],))]
    return {**dict(fila), "detalle": detalle}
