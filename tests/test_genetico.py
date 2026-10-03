import random

import pytest

from app.db.catalogo_repo import cargar_catalogo
from app.db.solicitud_repo import obtener_solicitud
from app.modules.genetico import (
    calcular_topes,
    ejecutar_algoritmo_genetico,
    evaluar_cromosoma,
)


PADRE_1 = [20, 15, 5, 30, 10, 0, 0, 8, 2, 12, 6, 0, 18, 4, 9]
PADRE_2 = [5, 25, 15, 5, 3, 10, 20, 15, 8, 5, 12, 15, 3, 20, 15]


def _datos(conn):
    return cargar_catalogo(conn), obtener_solicitud(conn, 1)


def test_topes_por_gen_segun_riesgo(conn):
    catalogo, _ = _datos(conn)
    assert calcular_topes(catalogo) == [26, 16, 26, 26, 26, 16, 21, 26, 26, 21, 21, 16, 26, 26, 26]


@pytest.mark.parametrize(
    ("cromosoma", "costo_esperado", "fitness_esperado"),
    [
        (PADRE_1, 531.80, 546.89),
        (PADRE_2, 891.60, 747.38),
    ],
)
def test_evaluar_padres_del_informe(conn, cromosoma, costo_esperado, fitness_esperado):
    catalogo, solicitud = _datos(conn)
    costo, fitness = evaluar_cromosoma(cromosoma, catalogo, solicitud)
    assert costo == pytest.approx(costo_esperado, abs=0.01)
    assert fitness == pytest.approx(fitness_esperado, abs=0.01)


def test_penalizacion_presupuesto_solo_si_se_supera(conn):
    catalogo, solicitud = _datos(conn)
    cromosoma = PADRE_1
    solicitud_sin_penalizacion = {**solicitud, "presupuesto": 600}
    solicitud_con_penalizacion = {**solicitud, "presupuesto": 500}
    _, fitness_sin = evaluar_cromosoma(cromosoma, catalogo, solicitud_sin_penalizacion)
    _, fitness_con = evaluar_cromosoma(cromosoma, catalogo, solicitud_con_penalizacion)
    assert fitness_sin - fitness_con == pytest.approx(318.0)


def test_penaliza_cada_forzado_incumplido(conn):
    catalogo, solicitud = _datos(conn)
    solicitud = {**solicitud, "incluir_forzado": ["Arroz", "Aceite"]}
    costo, fitness = evaluar_cromosoma([0] * len(catalogo), catalogo, solicitud)
    assert costo == 0
    assert fitness == -1000


def test_penaliza_producto_excluido_incluido(conn):
    catalogo, solicitud = _datos(conn)
    cromosoma = [0] * len(catalogo)
    cromosoma[8] = 1
    sin_regla = {**solicitud, "incluir_forzado": [], "excluir": []}
    excluido = {**sin_regla, "excluir": ["Detergente"]}
    _, fitness_sin = evaluar_cromosoma(cromosoma, catalogo, sin_regla)
    _, fitness_con = evaluar_cromosoma(cromosoma, catalogo, excluido)
    assert fitness_sin - fitness_con == 500


def test_semilla_fija_reproduce_el_resultado(conn):
    catalogo, solicitud = _datos(conn)
    assert ejecutar_algoritmo_genetico(catalogo, solicitud, semilla=42) == (
        ejecutar_algoritmo_genetico(catalogo, solicitud, semilla=42)
    )


def test_mejor_cromosoma_respeta_topes_y_restricciones(conn):
    catalogo, solicitud = _datos(conn)
    solicitud = {**solicitud, "excluir": ["Detergente"]}
    resultado = ejecutar_algoritmo_genetico(catalogo, solicitud, semilla=42)
    topes = calcular_topes(catalogo)
    assert all(0 <= gen <= tope for gen, tope in zip(resultado.mejor_cromosoma, topes))
    assert resultado.mejor_cromosoma[0] >= 1
    assert resultado.mejor_cromosoma[8] == 0


def test_historial_del_mejor_fitness_no_decrece(conn):
    catalogo, solicitud = _datos(conn)
    resultado = ejecutar_algoritmo_genetico(catalogo, solicitud, semilla=42)
    assert all(
        actual >= anterior
        for anterior, actual in zip(
            resultado.historial_mejor_fitness, resultado.historial_mejor_fitness[1:]
        )
    )


def test_semilla_no_modifica_el_generador_aleatorio_global(conn):
    catalogo, solicitud = _datos(conn)
    random.seed(12345)
    estado = random.getstate()
    ejecutar_algoritmo_genetico(catalogo, solicitud, semilla=42)
    assert random.getstate() == estado


def test_corridas_sin_semilla_se_mantienen_cerca_del_presupuesto(conn):
    catalogo, solicitud = _datos(conn)
    for _ in range(3):
        resultado = ejecutar_algoritmo_genetico(catalogo, solicitud)
        assert resultado.costo_total <= solicitud["presupuesto"] * 1.05
