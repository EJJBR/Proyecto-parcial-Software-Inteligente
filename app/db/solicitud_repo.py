"""Lectura y creacion de solicitudes del usuario (con categorias prioritarias y reglas duras)."""
import sqlite3
from datetime import date


def _armar_solicitud(conn: sqlite3.Connection, fila: sqlite3.Row) -> dict:
    id_sol = fila["id_solicitud"]
    categorias = [r[0] for r in conn.execute(
        """SELECT c.nombre FROM SOLICITUD_CATEGORIA_PRIORITARIA scp
           JOIN CATEGORIA c ON c.id_categoria = scp.id_categoria
           WHERE scp.id_solicitud = ? ORDER BY c.nombre""", (id_sol,))]

    def _reglas(tipo: str) -> list[str]:
        return [r[0] for r in conn.execute(
            """SELECT p.nombre FROM SOLICITUD_PRODUCTO_REGLA spr
               JOIN PRODUCTO p ON p.id_producto = spr.id_producto
               WHERE spr.id_solicitud = ? AND spr.tipo_regla = ? ORDER BY p.id_producto""",
            (id_sol, tipo))]

    return {
        "id_solicitud": id_sol,
        "id_usuario": fila["id_usuario"],
        "fecha": fila["fecha"],
        "texto_original": fila["texto_original"],
        # Las 4 claves siguientes tienen la misma forma que `solicitud_usuario` del notebook:
        "presupuesto": fila["presupuesto"],
        "categorias_prioritarias": categorias,
        "incluir_forzado": _reglas("incluir_forzado"),
        "excluir": _reglas("excluir"),
    }


def obtener_solicitud(conn: sqlite3.Connection, id_solicitud: int) -> dict | None:
    fila = conn.execute("SELECT * FROM SOLICITUD WHERE id_solicitud = ?", (id_solicitud,)).fetchone()
    return _armar_solicitud(conn, fila) if fila else None


def obtener_ultima_solicitud(conn: sqlite3.Connection) -> dict | None:
    fila = conn.execute("SELECT * FROM SOLICITUD ORDER BY id_solicitud DESC LIMIT 1").fetchone()
    return _armar_solicitud(conn, fila) if fila else None


def crear_solicitud(conn: sqlite3.Connection, *, id_usuario: int, presupuesto: float,
                    texto_original: str | None = None, categorias_prioritarias=(),
                    incluir_forzado=(), excluir=(), fecha: str | None = None) -> int:
    """Inserta una solicitud con sus categorias y reglas. No hace commit. Devuelve su id.

    Los nombres de categorias y productos deben coincidir con los de la BD; si alguno no existe
    lanza ValueError (con la lista de nombres validos) y no deja datos a medias si quien llama
    hace rollback.
    """
    if presupuesto is None or presupuesto <= 0:
        raise ValueError("El presupuesto debe ser mayor que 0.")
    repetidos = set(incluir_forzado) & set(excluir)
    if repetidos:
        raise ValueError(f"Productos en incluir_forzado y excluir a la vez: {sorted(repetidos)}")

    id_categorias = {}
    for nombre in categorias_prioritarias:
        fila = conn.execute("SELECT id_categoria FROM CATEGORIA WHERE nombre = ?", (nombre,)).fetchone()
        if fila is None:
            validas = [r[0] for r in conn.execute("SELECT nombre FROM CATEGORIA ORDER BY nombre")]
            raise ValueError(f"Categoria desconocida: {nombre!r}. Validas: {validas}")
        id_categorias[nombre] = fila[0]

    id_productos = []  # (id_producto, tipo_regla)
    for tipo, nombres in (("incluir_forzado", incluir_forzado), ("excluir", excluir)):
        for nombre in nombres:
            fila = conn.execute("SELECT id_producto FROM PRODUCTO WHERE nombre = ?", (nombre,)).fetchone()
            if fila is None:
                validos = [r[0] for r in conn.execute("SELECT nombre FROM PRODUCTO ORDER BY id_producto")]
                raise ValueError(f"Producto desconocido: {nombre!r}. Validos: {validos}")
            id_productos.append((fila[0], tipo))

    cur = conn.execute(
        "INSERT INTO SOLICITUD (id_usuario, fecha, presupuesto, texto_original) VALUES (?,?,?,?)",
        (id_usuario, fecha or date.today().isoformat(), presupuesto, texto_original))
    id_sol = cur.lastrowid
    for id_cat in id_categorias.values():
        conn.execute("INSERT INTO SOLICITUD_CATEGORIA_PRIORITARIA (id_solicitud, id_categoria) VALUES (?,?)",
                     (id_sol, id_cat))
    for id_prod, tipo in id_productos:
        conn.execute("INSERT INTO SOLICITUD_PRODUCTO_REGLA (id_solicitud, id_producto, tipo_regla) VALUES (?,?,?)",
                     (id_sol, id_prod, tipo))
    return id_sol
