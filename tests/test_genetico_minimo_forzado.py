import pytest

from app.db.catalogo_repo import cargar_catalogo
from app.db.solicitud_repo import obtener_solicitud
from app.modules.genetico import (
    PresupuestoInviableError,
    calcular_minimos_forzados,
    calcular_topes,
    evaluar_cromosoma,
    ejecutar_algoritmo_genetico,
)
from app.modules.genetico.algoritmo import _aplicar_minimos_forzados


MINIMOS_ESPERADOS = [
    ("Arroz", 8),
    ("Leche Gloria 1L", 7),
    ("Aceite", 3),
    ("Fideos", 6),
    ("Atún", 5),
    ("Pan de molde", 4),
    ("Yogurt Gloria", 4),
    ("Gaseosa Coca-Cola 1.5L", 7),
    ("Detergente", 2),
    ("Galletas Oreo", 5),
    ("Huevos (docena)", 4),
    ("Queso fresco", 3),
    ("Azúcar", 3),
    ("Papas Lay's", 6),
    ("Inca Kola 1.5L", 5),
]

INDIVIDUO_REFERENCIA = [
    26, 16, 26, 26, 26, 16, 21, 26, 7, 21, 21, 16, 26, 26, 26
]


def _datos(conn):
    return cargar_catalogo(conn), obtener_solicitud(conn, 1)


def _solicitud(solicitud, presupuesto, forzados):
    return {
        **solicitud,
        "presupuesto": presupuesto,
        "incluir_forzado": forzados,
        "excluir": [],
    }


def test_minimos_por_producto_forzado_y_limites(conn):
    catalogo, _ = _datos(conn)
    minimos = calcular_minimos_forzados(catalogo, set(range(len(catalogo))))
    topes = calcular_topes(catalogo)

    assert [
        (producto["nombre"], minimos[indice])
        for indice, producto in enumerate(catalogo)
    ] == MINIMOS_ESPERADOS
    assert all(minimos[indice] <= tope for indice, tope in enumerate(topes))


def test_aplica_minimos_sin_modificar_otros_genes():
    cromosoma = [0, 2, 1, 4]
    minimos = {2: 3}

    aplicado = _aplicar_minimos_forzados(cromosoma, minimos)

    assert aplicado == [0, 2, 3, 4]
    assert cromosoma == [0, 2, 1, 4]
    assert _aplicar_minimos_forzados([0, 2, 3, 4], minimos) == [0, 2, 3, 4]


def test_semilla_42_preserva_referencia_sin_reparacion(conn):
    catalogo, solicitud = _datos(conn)

    resultado = ejecutar_algoritmo_genetico(catalogo, solicitud, semilla=42)

    assert resultado.mejor_cromosoma == INDIVIDUO_REFERENCIA
    assert resultado.costo_total == pytest.approx(1499.70, abs=0.01)
    assert resultado.fitness == pytest.approx(1293.07, abs=0.01)
    assert resultado.reparado is False


def test_presupuesto_800_aplica_minimos_y_cabe(conn):
    catalogo, solicitud = _datos(conn)
    solicitud = _solicitud(solicitud, 800.0, ["Arroz", "Aceite"])

    resultado = ejecutar_algoritmo_genetico(catalogo, solicitud, semilla=42)

    assert resultado.mejor_cromosoma[0] >= 8
    assert resultado.mejor_cromosoma[2] >= 3
    assert resultado.costo_total <= 800


def test_presupuesto_60_cubre_el_minimo_forzado(conn):
    catalogo, solicitud = _datos(conn)
    solicitud = _solicitud(solicitud, 60.0, ["Arroz", "Aceite"])

    resultado = ejecutar_algoritmo_genetico(catalogo, solicitud, semilla=42)

    assert resultado.mejor_cromosoma[0] >= 8
    assert resultado.mejor_cromosoma[2] >= 3
    assert resultado.costo_total <= 60


def test_presupuesto_50_es_inviable_para_minimos_forzados(conn):
    catalogo, solicitud = _datos(conn)
    solicitud = _solicitud(solicitud, 50.0, ["Arroz", "Aceite"])

    with pytest.raises(PresupuestoInviableError):
        ejecutar_algoritmo_genetico(catalogo, solicitud, semilla=42)


def test_evaluacion_no_penaliza_forzado_positivo_bajo_el_minimo(conn):
    catalogo, solicitud = _datos(conn)
    aceite = next(
        indice
        for indice, producto in enumerate(catalogo)
        if producto["nombre"] == "Aceite"
    )
    cromosoma = [0] * len(catalogo)
    cromosoma[aceite] = 1
    forzado = _solicitud(solicitud, 1000.0, ["Aceite"])
    sin_forzado = _solicitud(solicitud, 1000.0, [])

    _, fitness_forzado = evaluar_cromosoma(cromosoma, catalogo, forzado)
    _, fitness_sin_forzado = evaluar_cromosoma(cromosoma, catalogo, sin_forzado)

    assert fitness_forzado == fitness_sin_forzado


def test_producto_forzado_sin_ventas_tiene_minimo_uno(conn):
    catalogo, _ = _datos(conn)
    catalogo_sin_ventas = [dict(producto) for producto in catalogo]
    catalogo_sin_ventas[0]["ventas_4sem"] = 0

    assert calcular_minimos_forzados(catalogo_sin_ventas, {0}) == {0: 1}
