import pytest

import config
from app.db.catalogo_repo import cargar_catalogo
from app.db.solicitud_repo import obtener_solicitud
from app.modules.difusa import score_demanda
from app.modules.genetico import (
    PresupuestoInviableError,
    calcular_minimos_forzados,
    calcular_topes,
    evaluar_cromosoma,
    ejecutar_algoritmo_genetico,
)
from app.modules.genetico.algoritmo import (
    _aplicar_topes_obligatorios,
    _preparar_prioridades,
)


def _datos(conn):
    return cargar_catalogo(conn), obtener_solicitud(conn, 1)


def _solicitud(solicitud, **cambios):
    return {
        **solicitud,
        "categorias_prioritarias": [],
        "incluir_forzado": [],
        "excluir": [],
        **cambios,
    }


def _indice(catalogo, nombre):
    return next(
        indice
        for indice, producto in enumerate(catalogo)
        if producto["nombre"] == nombre
    )


def test_claves_nuevas_vacias_preservan_el_resultado_semilla_42(conn):
    catalogo, solicitud = _datos(conn)
    sin_claves = ejecutar_algoritmo_genetico(catalogo, solicitud, semilla=42)
    con_claves_vacias = ejecutar_algoritmo_genetico(
        catalogo,
        {**solicitud, "prioridad_productos": [], "obligatorios": []},
        semilla=42,
    )

    assert con_claves_vacias.mejor_cromosoma == sin_claves.mejor_cromosoma
    assert con_claves_vacias.costo_total == sin_claves.costo_total
    assert con_claves_vacias.fitness == sin_claves.fitness


def test_prioridad_de_producto_multiplica_entrada_del_score_demanda(conn):
    catalogo, solicitud = _datos(conn)
    aceite = _indice(catalogo, "Aceite")
    cromosoma = [0] * len(catalogo)
    cromosoma[aceite] = 4
    solicitud_base = _solicitud(solicitud)
    solicitud_prioritaria = _solicitud(
        solicitud, prioridad_productos=["Aceite"]
    )

    _, fitness_base = evaluar_cromosoma(cromosoma, catalogo, solicitud_base)
    _, fitness_prioritario = evaluar_cromosoma(
        cromosoma, catalogo, solicitud_prioritaria
    )
    esperado = (
        cromosoma[aceite]
        * catalogo[aceite]["precio_venta"]
        * (
            score_demanda(
                catalogo[aceite]["ventas_4sem"] * config.FACTOR_PRIORIDAD_PRODUCTO
            )
            - score_demanda(catalogo[aceite]["ventas_4sem"])
        )
        * 1.0
    )

    assert fitness_prioritario > fitness_base
    assert fitness_prioritario - fitness_base == pytest.approx(esperado)


def test_minimos_distinguen_forzado_normal_y_obligatorio(conn):
    catalogo, _ = _datos(conn)
    aceite = _indice(catalogo, "Aceite")
    arroz = _indice(catalogo, "Arroz")

    assert calcular_minimos_forzados(catalogo, {aceite, arroz}) == {
        aceite: 3,
        arroz: 8,
    }
    assert calcular_minimos_forzados(
        catalogo, {aceite, arroz}, frozenset({aceite, arroz})
    ) == {aceite: 6, arroz: 15}


def test_topes_obligatorios_se_elevan_sin_alterar_otros(conn):
    catalogo, _ = _datos(conn)
    leche = _indice(catalogo, "Leche Gloria 1L")
    topes = calcular_topes(catalogo)
    topes[0] = config.CANTIDAD_MAX
    ajustados = _aplicar_topes_obligatorios(topes, {leche})

    assert ajustados[leche] == config.CANTIDAD_MAX
    assert ajustados[0] == config.CANTIDAD_MAX
    assert all(
        ajustado == original
        for indice, (ajustado, original) in enumerate(zip(ajustados, topes))
        if indice != leche
    )
    assert topes[leche] < config.CANTIDAD_MAX


def test_obligatorio_cubre_minimo_y_presupuesto_800(conn):
    catalogo, solicitud = _datos(conn)
    solicitud = _solicitud(
        solicitud,
        presupuesto=800.0,
        incluir_forzado=["Arroz", "Aceite"],
        obligatorios=["Aceite"],
    )

    resultado = ejecutar_algoritmo_genetico(catalogo, solicitud, semilla=42)

    assert resultado.mejor_cromosoma[_indice(catalogo, "Aceite")] >= 6
    assert resultado.mejor_cromosoma[_indice(catalogo, "Arroz")] >= 8
    assert resultado.costo_total <= 800


def test_priorizar_aceite_no_reduce_su_cantidad(conn):
    catalogo, solicitud = _datos(conn)
    base = _solicitud(
        solicitud,
        presupuesto=800.0,
        incluir_forzado=["Arroz", "Aceite"],
    )
    prioritaria = {**base, "prioridad_productos": ["Aceite"]}

    resultado_base = ejecutar_algoritmo_genetico(catalogo, base, semilla=42)
    resultado_prioritario = ejecutar_algoritmo_genetico(
        catalogo, prioritaria, semilla=42
    )

    assert resultado_prioritario.mejor_cromosoma[_indice(catalogo, "Aceite")] >= (
        resultado_base.mejor_cromosoma[_indice(catalogo, "Aceite")]
    )


def test_obligatorio_puede_superar_tope_por_merma(conn):
    catalogo, solicitud = _datos(conn)
    leche = _indice(catalogo, "Leche Gloria 1L")
    solicitud = _solicitud(
        solicitud,
        presupuesto=1500.0,
        incluir_forzado=["Leche Gloria 1L"],
        obligatorios=["Leche Gloria 1L"],
    )

    resultado = ejecutar_algoritmo_genetico(catalogo, solicitud, semilla=42)

    assert 13 <= resultado.mejor_cromosoma[leche] <= config.CANTIDAD_MAX
    assert resultado.costo_total <= 1500


def test_prioridades_validan_obligatorio_forzado_y_nombre(conn):
    catalogo, solicitud = _datos(conn)

    with pytest.raises(ValueError, match="también debe estar en incluir_forzado"):
        _preparar_prioridades(
            catalogo,
            {**solicitud, "incluir_forzado": [], "obligatorios": ["Aceite"]},
        )
    with pytest.raises(ValueError, match="desconocido.*Producto ausente"):
        _preparar_prioridades(
            catalogo,
            {**solicitud, "prioridad_productos": ["Producto ausente"]},
        )


def test_presupuesto_menor_al_minimo_obligatorio_es_inviable(conn):
    catalogo, solicitud = _datos(conn)
    solicitud = _solicitud(
        solicitud,
        presupuesto=50.0,
        incluir_forzado=["Arroz"],
        obligatorios=["Arroz"],
    )

    with pytest.raises(PresupuestoInviableError):
        ejecutar_algoritmo_genetico(catalogo, solicitud, semilla=42)
