"""Optimizacion genetica con minimos forzados aplicados como paso final."""
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from math import ceil
import random
from typing import Any

import config
from app.modules.difusa import peso_categoria, riesgo_merma, score_demanda


Producto = Mapping[str, Any]
Solicitud = Mapping[str, Any]
TOLERANCIA_PRESUPUESTO = 1e-9


@dataclass(frozen=True)
class ResultadoGenetico:
    mejor_cromosoma: list[int]
    costo_total: float
    fitness: float
    historial_mejor_fitness: list[float]
    reparado: bool = False


class PresupuestoInviableError(ValueError):
    """El costo mínimo de los productos obligatorios supera el presupuesto."""


def _preparar_restricciones(
    catalogo: Sequence[Producto], solicitud: Solicitud
) -> tuple[set[int], set[int]]:
    indices_por_nombre: dict[str, int] = {}
    for indice, producto in enumerate(catalogo):
        nombre = producto["nombre"]
        if nombre in indices_por_nombre:
            raise ValueError(f"Nombre de producto duplicado en el catalogo: {nombre!r}.")
        indices_por_nombre[nombre] = indice

    try:
        forzados = solicitud["incluir_forzado"]
        excluidos = solicitud["excluir"]
        categorias_prioritarias = solicitud["categorias_prioritarias"]
        presupuesto = solicitud["presupuesto"]
    except KeyError as error:
        raise ValueError(f"Falta un campo requerido de la solicitud: {error.args[0]!r}.") from error

    if presupuesto is None or presupuesto <= 0:
        raise ValueError("El presupuesto debe ser mayor que 0.")

    nombres_forzados = set(forzados)
    nombres_excluidos = set(excluidos)
    if nombres_forzados & nombres_excluidos:
        raise ValueError("Un producto no puede estar forzado y excluido a la vez.")

    indices_forzados: set[int] = set()
    indices_excluidos: set[int] = set()
    for nombres, indices, tipo in (
        (forzados, indices_forzados, "forzado"),
        (excluidos, indices_excluidos, "excluido"),
    ):
        for nombre in nombres:
            if nombre not in indices_por_nombre:
                raise ValueError(f"Producto {tipo} desconocido: {nombre!r}.")
            indices.add(indices_por_nombre[nombre])

    if categorias_prioritarias is None:
        raise ValueError("categorias_prioritarias no puede ser None.")
    return indices_forzados, indices_excluidos


def calcular_topes(catalogo: Sequence[Producto]) -> list[int]:
    """Calcula los topes individuales de los genes en el orden del catalogo."""
    if len(catalogo) != config.NUM_GENES:
        raise ValueError(f"El catalogo debe tener {config.NUM_GENES} productos.")
    return [_tope_producto(producto) for producto in catalogo]


def _tope_producto(producto: Producto) -> int:
    """Calcula el tope de un producto a partir de su riesgo de merma."""
    return round(
        config.CANTIDAD_MAX
        * (1 - config.COEFICIENTE_RIESGO_CADENA * riesgo_merma(producto["dias_vida_util"]))
    )


def calcular_minimos_forzados(
    catalogo: Sequence[Producto], indices_forzados: set[int]
) -> dict[int, int]:
    """Calcula el mínimo de una semana de ventas para cada índice forzado."""
    return {
        indice: min(
            _tope_producto(catalogo[indice]),
            max(
                1,
                ceil(
                    float(catalogo[indice]["ventas_4sem"])
                    / config.SEMANAS_VENTANA_VENTAS
                ),
            ),
        )
        for indice in indices_forzados
    }


def _aplicar_minimos_forzados(
    cromosoma: Sequence[int], minimos: Mapping[int, int]
) -> list[int]:
    """Devuelve una copia del cromosoma elevando solo los forzados bajo su mínimo."""
    copia = list(cromosoma)
    for indice, minimo in minimos.items():
        copia[indice] = max(copia[indice], minimo)
    return copia


def evaluar_cromosoma(
    cromosoma: Sequence[int], catalogo: Sequence[Producto], solicitud: Solicitud
) -> tuple[float, float]:
    """Devuelve (costo_total, fitness); no recorta el cromosoma a los topes."""
    if len(cromosoma) != len(catalogo):
        raise ValueError("El cromosoma debe tener un gen por cada producto del catalogo.")
    indices_forzados, indices_excluidos = _preparar_restricciones(catalogo, solicitud)

    costo_total = 0.0
    parte_positiva = 0.0
    for cantidad, producto in zip(cromosoma, catalogo):
        costo_total += cantidad * producto["precio_compra"]
        parte_positiva += (
            cantidad
            * producto["precio_venta"]
            * score_demanda(producto["ventas_4sem"])
            * peso_categoria(producto["categoria"], solicitud["categorias_prioritarias"])
        )

    penalizacion_presupuesto = max(
        0.0, (costo_total - solicitud["presupuesto"]) * config.FACTOR_CASTIGO
    )
    penalizacion_restricciones = sum(
        config.PENALIZACION_RESTRICCION_DURA
        for indice in indices_forzados
        if cromosoma[indice] == 0
    ) + sum(
        config.PENALIZACION_RESTRICCION_DURA
        for indice in indices_excluidos
        if cromosoma[indice] > 0
    )
    fitness = parte_positiva - penalizacion_presupuesto - penalizacion_restricciones
    return costo_total, fitness


def _reparar_cromosoma(
    cromosoma: list[int],
    topes: Sequence[int],
    indices_forzados: set[int],
    indices_excluidos: set[int],
    rng: random.Random,
) -> list[int]:
    for indice, tope in enumerate(topes):
        cromosoma[indice] = min(max(cromosoma[indice], config.CANTIDAD_MIN), tope)
        if indice in indices_excluidos:
            cromosoma[indice] = 0
        elif indice in indices_forzados and cromosoma[indice] == 0:
            cromosoma[indice] = rng.randint(1, tope)
    return cromosoma


def _reparar_presupuesto(
    cromosoma: Sequence[int],
    catalogo: Sequence[Producto],
    solicitud: Solicitud,
    indices_forzados: set[int],
    indices_excluidos: set[int],
    minimos: Mapping[int, int] | None = None,
) -> tuple[list[int], float, float, bool]:
    """Reduce unidades para caber en el presupuesto sin bajar mínimos forzados."""
    copia = list(cromosoma)
    minimos_activos = (
        minimos
        if minimos is not None
        else calcular_minimos_forzados(catalogo, indices_forzados)
    )
    costo, fitness = evaluar_cromosoma(copia, catalogo, solicitud)
    if costo <= solicitud["presupuesto"] + TOLERANCIA_PRESUPUESTO:
        return copia, costo, fitness, False

    while costo > solicitud["presupuesto"] + TOLERANCIA_PRESUPUESTO:
        mejor_candidato: list[int] | None = None
        mejor_costo = costo
        mejor_fitness = float("-inf")
        for indice, cantidad in enumerate(copia):
            minimo = minimos_activos.get(indice, 0)
            if indice in indices_excluidos or cantidad <= minimo:
                continue
            candidato = copia[:]
            candidato[indice] -= 1
            costo_candidato, fitness_candidato = evaluar_cromosoma(
                candidato, catalogo, solicitud
            )
            if fitness_candidato > mejor_fitness:
                mejor_candidato = candidato
                mejor_costo = costo_candidato
                mejor_fitness = fitness_candidato
        if mejor_candidato is None:
            raise PresupuestoInviableError(
                "El costo mínimo de los productos obligatorios supera el presupuesto."
            )
        copia = mejor_candidato
        costo = mejor_costo
        fitness = mejor_fitness

    return copia, costo, fitness, True


def ejecutar_algoritmo_genetico(
    catalogo: Sequence[Producto], solicitud: Solicitud, semilla: int | None = None
) -> ResultadoGenetico:
    """Optimiza y aplica mínimos de una semana a forzados solo en el paso final."""
    if len(catalogo) != config.NUM_GENES:
        raise ValueError(f"El catalogo debe tener {config.NUM_GENES} productos.")
    indices_forzados, indices_excluidos = _preparar_restricciones(catalogo, solicitud)
    minimos_forzados = calcular_minimos_forzados(catalogo, indices_forzados)
    costo_minimo_forzados = sum(
        float(catalogo[indice]["precio_compra"]) * minimos_forzados[indice]
        for indice in indices_forzados
    )
    if costo_minimo_forzados > solicitud["presupuesto"] + TOLERANCIA_PRESUPUESTO:
        raise PresupuestoInviableError(
            "El costo mínimo de los productos obligatorios supera el presupuesto."
        )
    topes = calcular_topes(catalogo)
    rng = random.Random(semilla)

    poblacion = []
    for _ in range(config.TAMANO_POBLACION):
        cromosoma = [rng.randint(config.CANTIDAD_MIN, tope) for tope in topes]
        poblacion.append(
            _reparar_cromosoma(cromosoma, topes, indices_forzados, indices_excluidos, rng)
        )

    historial: list[float] = []
    mejor_cromosoma: list[int] | None = None
    mejor_fitness = float("-inf")
    mejor_costo = 0.0

    for _ in range(config.GENERACIONES):
        evaluada = [
            (cromosoma, *evaluar_cromosoma(cromosoma, catalogo, solicitud))
            for cromosoma in poblacion
        ]
        evaluada.sort(key=lambda elemento: elemento[2], reverse=True)
        actual, costo_actual, fitness_actual = evaluada[0]
        if fitness_actual > mejor_fitness:
            mejor_cromosoma = actual[:]
            mejor_costo = costo_actual
            mejor_fitness = fitness_actual
        historial.append(mejor_fitness)

        nueva_poblacion = [cromosoma[:] for cromosoma, _, _ in evaluada[:config.ELITISMO]]
        while len(nueva_poblacion) < config.TAMANO_POBLACION:
            torneo_a = rng.sample(evaluada, config.TAMANO_TORNEO)
            torneo_b = rng.sample(evaluada, config.TAMANO_TORNEO)
            padre_a = max(torneo_a, key=lambda elemento: elemento[2])[0]
            padre_b = max(torneo_b, key=lambda elemento: elemento[2])[0]
            if rng.random() < config.TASA_CROSSOVER:
                punto = rng.randint(1, len(catalogo) - 1)
                hijo_a = padre_a[:punto] + padre_b[punto:]
                hijo_b = padre_b[:punto] + padre_a[punto:]
            else:
                hijo_a, hijo_b = padre_a[:], padre_b[:]

            hijos = []
            for hijo in (hijo_a, hijo_b):
                for indice, tope in enumerate(topes):
                    if rng.random() < config.TASA_MUTACION:
                        hijo[indice] = rng.randint(config.CANTIDAD_MIN, tope)
                hijos.append(
                    _reparar_cromosoma(hijo, topes, indices_forzados, indices_excluidos, rng)
                )
            nueva_poblacion.extend(hijos[: config.TAMANO_POBLACION - len(nueva_poblacion)])
        poblacion = nueva_poblacion

    if mejor_cromosoma is None:
        raise RuntimeError("El algoritmo genetico no produjo ninguna generacion.")
    (
        cromosoma_final,
        costo_final,
        fitness_final,
        reparado,
    ) = _reparar_presupuesto(
        _aplicar_minimos_forzados(mejor_cromosoma, minimos_forzados),
        catalogo,
        solicitud,
        indices_forzados,
        indices_excluidos,
        minimos_forzados,
    )
    costo_final, fitness_final = evaluar_cromosoma(
        cromosoma_final, catalogo, solicitud
    )
    return ResultadoGenetico(
        cromosoma_final,
        costo_final,
        fitness_final,
        historial,
        reparado,
    )
