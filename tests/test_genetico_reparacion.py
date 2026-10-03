import pytest

from app.db.catalogo_repo import cargar_catalogo
from app.db.solicitud_repo import obtener_solicitud
from app.modules.genetico import (
    PresupuestoInviableError,
    ejecutar_algoritmo_genetico,
    evaluar_cromosoma,
)
from app.modules.genetico import algoritmo


INDIVIDUO_REFERENCIA = [
    26, 16, 26, 26, 26, 16, 21, 26, 7, 21, 21, 16, 26, 26, 26
]


def _datos(conn):
    return cargar_catalogo(conn), obtener_solicitud(conn, 1)


def test_exceso_se_repara_hasta_caber_y_metricas_se_recalculan(conn):
    catalogo, solicitud = _datos(conn)
    solicitud = {**solicitud, "presupuesto": 1000.0}
    resultado = algoritmo._reparar_presupuesto(
        INDIVIDUO_REFERENCIA,
        catalogo,
        solicitud,
        indices_forzados={0},
        indices_excluidos=set(),
    )
    cromosoma, costo, fitness, reparado = resultado

    assert reparado is True
    assert costo <= solicitud["presupuesto"] + algoritmo.TOLERANCIA_PRESUPUESTO
    assert cromosoma[0] >= 1
    assert (costo, fitness) == pytest.approx(
        evaluar_cromosoma(cromosoma, catalogo, solicitud)
    )


def test_si_cabe_cromosoma_y_metricas_quedan_iguales(conn):
    catalogo, solicitud = _datos(conn)
    costo_original, fitness_original = evaluar_cromosoma(
        INDIVIDUO_REFERENCIA, catalogo, solicitud
    )

    cromosoma, costo, fitness, reparado = algoritmo._reparar_presupuesto(
        INDIVIDUO_REFERENCIA,
        catalogo,
        solicitud,
        indices_forzados={0},
        indices_excluidos=set(),
    )

    assert cromosoma == INDIVIDUO_REFERENCIA
    assert costo == costo_original
    assert fitness == fitness_original
    assert reparado is False


def test_semilla_42_preserva_referencia_sin_reparacion(conn):
    catalogo, solicitud = _datos(conn)

    resultado = ejecutar_algoritmo_genetico(catalogo, solicitud, semilla=42)

    assert resultado.mejor_cromosoma == INDIVIDUO_REFERENCIA
    assert resultado.costo_total == pytest.approx(1499.70, abs=0.01)
    assert resultado.fitness == pytest.approx(1293.07, abs=0.01)
    assert resultado.reparado is False


def test_forzados_no_bajan_de_uno_y_excluidos_siguen_en_cero(conn):
    catalogo, solicitud = _datos(conn)
    cromosoma_inicial = INDIVIDUO_REFERENCIA[:]
    cromosoma_inicial[8] = 0
    solicitud = {**solicitud, "presupuesto": 1000.0, "excluir": ["Detergente"]}
    cromosoma, costo, _, reparado = algoritmo._reparar_presupuesto(
        cromosoma_inicial,
        catalogo,
        solicitud,
        indices_forzados={0, 2},
        indices_excluidos={8},
    )

    assert reparado
    assert cromosoma[0] >= 1
    assert cromosoma[2] >= 1
    assert cromosoma[8] == 0
    assert costo <= solicitud["presupuesto"] + algoritmo.TOLERANCIA_PRESUPUESTO


def test_reparacion_no_muta_cromosoma_ni_historial(conn):
    catalogo, solicitud = _datos(conn)
    solicitud = {**solicitud, "presupuesto": 1000.0}
    cromosoma_original = INDIVIDUO_REFERENCIA[:]
    historial_original = [1.0, 2.0, 3.0]
    copia_historial = historial_original[:]

    cromosoma_reparado, _, _, _ = algoritmo._reparar_presupuesto(
        cromosoma_original,
        catalogo,
        solicitud,
        indices_forzados={0},
        indices_excluidos=set(),
    )

    assert cromosoma_original == INDIVIDUO_REFERENCIA
    assert cromosoma_reparado is not cromosoma_original
    assert historial_original == copia_historial


def test_forzados_por_sobre_presupuesto_falla_antes_del_bucle(conn, monkeypatch):
    catalogo, solicitud = _datos(conn)
    solicitud = {
        **solicitud,
        "presupuesto": 3.0,
        "incluir_forzado": ["Arroz", "Aceite"],
    }

    def bucle_no_debe_iniciarse(*args, **kwargs):
        pytest.fail("La validación inviable debe ocurrir antes del bucle.")

    monkeypatch.setattr(algoritmo, "_reparar_cromosoma", bucle_no_debe_iniciarse)
    with pytest.raises(PresupuestoInviableError):
        ejecutar_algoritmo_genetico(catalogo, solicitud, semilla=42)


def test_exceso_de_centavos_se_resuelve_retirando_pocas_unidades(conn):
    catalogo, solicitud = _datos(conn)
    solicitud = {**solicitud, "presupuesto": 1499.60}
    costo_original, _ = evaluar_cromosoma(
        INDIVIDUO_REFERENCIA, catalogo, solicitud
    )

    cromosoma, costo, _, reparado = algoritmo._reparar_presupuesto(
        INDIVIDUO_REFERENCIA,
        catalogo,
        solicitud,
        indices_forzados={0},
        indices_excluidos=set(),
    )

    assert reparado
    assert costo_original - solicitud["presupuesto"] == pytest.approx(0.10)
    assert sum(INDIVIDUO_REFERENCIA) - sum(cromosoma) <= 1
    assert costo <= solicitud["presupuesto"] + algoritmo.TOLERANCIA_PRESUPUESTO
