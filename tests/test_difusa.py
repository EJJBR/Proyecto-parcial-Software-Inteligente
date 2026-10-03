import pytest

from app.modules.difusa import (
    fuzzificar_demanda, fuzzificar_riesgo, membresia_trapezoidal, membresia_triangular,
    peso_categoria, riesgo_merma, score_demanda,
)

# Ventas de 4 semanas del catalogo y score_demanda esperado (tabla de validacion del notebook).
VENTAS_Y_SCORE = [(30, 0.900), (25, 0.900), (12, 0.410), (22, 0.780), (18, 0.620),
                  (15, 0.500), (14, 0.470), (28, 0.900), (8, 0.290), (20, 0.700),
                  (16, 0.540), (10, 0.350), (9, 0.320), (24, 0.860), (19, 0.660)]


@pytest.mark.parametrize("ventas, esperado", VENTAS_Y_SCORE)
def test_score_demanda_coincide_con_notebook(ventas, esperado):
    assert score_demanda(ventas) == pytest.approx(esperado, abs=5e-4)


def test_score_demanda_18_unidades():
    assert round(score_demanda(18), 2) == 0.62


@pytest.mark.parametrize("dias, esperado", [(3, 0.8), (7, 0.5), (20, 0.2)])
def test_riesgo_merma_niveles_del_catalogo(dias, esperado):
    assert riesgo_merma(dias) == pytest.approx(esperado)


def test_membresia_trapezoidal_tramos():
    assert membresia_trapezoidal(5, 5, 15, 15, 25) == 0.0   # x == a
    assert membresia_trapezoidal(10, 5, 15, 15, 25) == 0.5  # subida
    assert membresia_trapezoidal(15, 5, 15, 15, 25) == 1.0  # meseta
    assert membresia_trapezoidal(20, 5, 15, 15, 25) == 0.5  # bajada
    assert membresia_trapezoidal(25, 5, 15, 15, 25) == 0.0  # x == d


def test_membresia_triangular_es_trapecio_con_b_igual_c():
    assert membresia_triangular(10, 5, 15, 25) == membresia_trapezoidal(10, 5, 15, 15, 25)


def test_fuzzificar_demanda_en_zona_de_transicion():
    mu = fuzzificar_demanda(18)
    assert mu["baja"] == 0.0
    assert mu["media"] == pytest.approx(0.7)
    assert mu["alta"] == pytest.approx(0.3)


def test_peso_categoria():
    assert peso_categoria("lacteos", ["lacteos", "abarrotes"]) == 1.3
    assert peso_categoria("bebidas", ["lacteos", "abarrotes"]) == 1.0


def test_score_demanda_en_bordes_de_hombros():
    assert score_demanda(0) == 0.2
    assert score_demanda(1000) == 0.9


def test_riesgo_merma_en_bordes_de_hombros():
    assert riesgo_merma(0) == 0.8
    assert riesgo_merma(1000) == 0.2


@pytest.mark.parametrize("x", [0, 1, 5, 15, 25, 100, 1000])
@pytest.mark.parametrize("fuzzificar", [fuzzificar_demanda, fuzzificar_riesgo])
def test_alguna_membresia_se_activa_en_puntos_de_entrada(x, fuzzificar):
    assert any(grado > 0 for grado in fuzzificar(x).values())
