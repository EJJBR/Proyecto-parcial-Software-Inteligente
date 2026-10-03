import pytest

from app.db import catalogo_repo, recomendacion_repo, solicitud_repo
from app.db.recomendacion_repo import RecomendacionYaExiste

NOMBRES = ["Arroz", "Leche Gloria 1L", "Aceite", "Fideos", "Atún", "Pan de molde", "Yogurt Gloria",
           "Gaseosa Coca-Cola 1.5L", "Detergente", "Galletas Oreo", "Huevos (docena)", "Queso fresco",
           "Azúcar", "Papas Lay's", "Inca Kola 1.5L"]
VENTAS = [30, 25, 12, 22, 18, 15, 14, 28, 8, 20, 16, 10, 9, 24, 19]


def test_catalogo_15_productos_en_orden_y_ventas(conn):
    cat = catalogo_repo.cargar_catalogo(conn)
    assert [p["nombre"] for p in cat] == NOMBRES
    assert [p["ventas_4sem"] for p in cat] == VENTAS
    assert cat[0]["categoria"] == "abarrotes" and cat[1]["dias_vida_util"] == 3


def test_catalogo_usa_solo_las_ultimas_semanas(conn):
    # Una 5.a semana (con S10 para probar el orden numerico): la ventana de 4 descarta la mas antigua.
    conn.execute("INSERT INTO VENTA_HISTORICA (id_producto, semana, cantidad_vendida) VALUES (1,'2026-S10',100)")
    arroz = catalogo_repo.cargar_catalogo(conn)[0]
    s1 = conn.execute("SELECT cantidad_vendida FROM VENTA_HISTORICA WHERE id_producto=1 AND semana='2026-S1'").fetchone()[0]
    assert arroz["ventas_4sem"] == 30 - s1 + 100


def test_categorias(conn):
    assert catalogo_repo.listar_categorias(conn) == ["abarrotes", "bebidas", "lacteos", "limpieza", "panaderia", "snacks"]


def test_solicitud_del_seed_tiene_la_forma_del_notebook(conn):
    s = solicitud_repo.obtener_ultima_solicitud(conn)
    assert s["presupuesto"] == 1500.0
    assert s["categorias_prioritarias"] == ["abarrotes", "lacteos"]
    assert s["incluir_forzado"] == ["Arroz"] and s["excluir"] == []


def test_crear_solicitud_y_leerla(conn):
    id_sol = solicitud_repo.crear_solicitud(
        conn, id_usuario=1, presupuesto=800, texto_original="prueba",
        categorias_prioritarias=["bebidas"], incluir_forzado=["Arroz"], excluir=["Queso fresco"])
    s = solicitud_repo.obtener_solicitud(conn, id_sol)
    assert (s["presupuesto"], s["categorias_prioritarias"], s["incluir_forzado"], s["excluir"]) == \
        (800, ["bebidas"], ["Arroz"], ["Queso fresco"])


@pytest.mark.parametrize("kwargs", [
    {"presupuesto": 0}, {"presupuesto": 100, "categorias_prioritarias": ["inexistente"]},
    {"presupuesto": 100, "incluir_forzado": ["Producto raro"]},
    {"presupuesto": 100, "incluir_forzado": ["Arroz"], "excluir": ["Arroz"]},
])
def test_crear_solicitud_invalida(conn, kwargs):
    with pytest.raises(ValueError):
        solicitud_repo.crear_solicitud(conn, id_usuario=1, **kwargs)


def test_guardar_leer_duplicado_y_reemplazo(conn):
    id_sol = solicitud_repo.obtener_ultima_solicitud(conn)["id_solicitud"]
    assert recomendacion_repo.obtener_recomendacion(conn, id_sol) is None
    recomendacion_repo.guardar_recomendacion(conn, id_sol, 10.5, 99.0, "texto", {1: 5, 2: 0, 3: 7})
    rec = recomendacion_repo.obtener_recomendacion(conn, id_sol)
    assert [(d["nombre"], d["cantidad_recomendada"]) for d in rec["detalle"]] == [("Arroz", 5), ("Aceite", 7)]

    with pytest.raises(RecomendacionYaExiste):
        recomendacion_repo.guardar_recomendacion(conn, id_sol, 1, 1, "otra", {1: 1})

    recomendacion_repo.guardar_recomendacion(conn, id_sol, 20.0, 50.0, "nueva", {4: 3}, reemplazar=True)
    rec = recomendacion_repo.obtener_recomendacion(conn, id_sol)
    assert rec["fitness_final"] == 20.0 and [d["nombre"] for d in rec["detalle"]] == ["Fideos"]
    assert conn.execute("SELECT COUNT(*) FROM RECOMENDACION").fetchone()[0] == 1

    assert recomendacion_repo.eliminar_recomendacion(conn, id_sol) is True
    assert recomendacion_repo.eliminar_recomendacion(conn, id_sol) is False


def test_guardar_recomendacion_solicitud_inexistente(conn):
    with pytest.raises(ValueError):
        recomendacion_repo.guardar_recomendacion(conn, 999, 1, 1, "x", {1: 1})
