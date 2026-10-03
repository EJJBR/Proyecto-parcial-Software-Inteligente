"""Lectura del catalogo de productos con sus ventas recientes."""
import sqlite3

import config

# Ventas de las ultimas N semanas: se toman las N semanas mas recientes registradas en
# VENTA_HISTORICA. Las semanas tienen formato 'AAAA-Sn'; se ordenan por anio y por el numero
# n como entero (asi '2026-S10' va despues de '2026-S2').
_SQL_CATALOGO = """
SELECT p.id_producto, p.nombre, c.nombre AS categoria, p.precio_compra,
       p.precio_venta, p.perecibilidad, p.dias_vida_util, p.stock_actual,
       COALESCE(SUM(v.cantidad_vendida), 0) AS ventas_4sem
FROM PRODUCTO p
JOIN CATEGORIA c ON c.id_categoria = p.id_categoria
LEFT JOIN VENTA_HISTORICA v
       ON v.id_producto = p.id_producto
      AND v.semana IN (
            SELECT semana FROM VENTA_HISTORICA
            GROUP BY semana
            ORDER BY substr(semana, 1, 4) DESC,
                     CAST(substr(semana, instr(semana, 'S') + 1) AS INTEGER) DESC
            LIMIT ?)
GROUP BY p.id_producto
ORDER BY p.id_producto
"""


def cargar_catalogo(conn: sqlite3.Connection, semanas: int = config.SEMANAS_VENTANA_VENTAS) -> list[dict]:
    """Devuelve los productos (ordenados por id_producto) como lista de diccionarios.

    Claves: id_producto, nombre, categoria, precio_compra, precio_venta, perecibilidad,
    dias_vida_util, stock_actual, ventas_4sem. El orden es el de los genes del cromosoma.
    """
    return [dict(fila) for fila in conn.execute(_SQL_CATALOGO, (semanas,))]


def listar_categorias(conn: sqlite3.Connection) -> list[str]:
    return [fila["nombre"] for fila in conn.execute("SELECT nombre FROM CATEGORIA ORDER BY nombre")]
