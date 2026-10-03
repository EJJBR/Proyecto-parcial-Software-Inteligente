"""Variables difusas del modelo (identicas a la version vigente del notebook).

- score_demanda: entrada = ventas de las ultimas 4 semanas.
- riesgo_merma:  entrada = dias de vida util restante del producto (columna dias_vida_util).
- Defuzzificacion: promedio ponderado por la membresia, estilo Sugeno.

Nota de diseno: riesgo_merma NO participa en el fitness; se usa para limitar la cantidad maxima
de cada gen (ver el modulo genetico). score_demanda es el unico termino difuso del fitness.
"""
from .membresia import membresia_trapezoidal

# Conjuntos difusos: (a, b, c, d). El 999 representa "sin limite" en el hombro derecho.
DEMANDA_CONJUNTOS = {"baja": (0, 0, 5, 15), "media": (5, 15, 15, 25), "alta": (15, 25, 999, 999)}
DEMANDA_VALORES = {"baja": 0.2, "media": 0.5, "alta": 0.9}

RIESGO_CONJUNTOS = {"alto": (0, 0, 3, 7), "medio": (3, 7, 7, 15), "bajo": (7, 15, 999, 999)}
RIESGO_VALORES = {"alto": 0.8, "medio": 0.5, "bajo": 0.2}

PESO_CATEGORIA_PRIORITARIA = 1.3
PESO_CATEGORIA_NORMAL = 1.0
VALOR_NEUTRO = 0.5  # caso borde: si ninguna membresia se activa


def _fuzzificar(x: float, conjuntos: dict) -> dict:
    return {nombre: membresia_trapezoidal(x, *params) for nombre, params in conjuntos.items()}


def _defuzzificar_sugeno(mu: dict, valores: dict) -> float:
    suma = sum(mu.values())
    if suma == 0:
        return VALOR_NEUTRO
    return sum(mu[nombre] * valores[nombre] for nombre in mu) / suma


def fuzzificar_demanda(ventas: float) -> dict:
    """Grados de membresia {'baja','media','alta'} para unas ventas de 4 semanas."""
    return _fuzzificar(ventas, DEMANDA_CONJUNTOS)


def fuzzificar_riesgo(dias_vida_util: float) -> dict:
    """Grados de membresia {'alto','medio','bajo'} para unos dias de vida util."""
    return _fuzzificar(dias_vida_util, RIESGO_CONJUNTOS)


def score_demanda(ventas: float) -> float:
    return _defuzzificar_sugeno(fuzzificar_demanda(ventas), DEMANDA_VALORES)


def riesgo_merma(dias_vida_util: float) -> float:
    return _defuzzificar_sugeno(fuzzificar_riesgo(dias_vida_util), RIESGO_VALORES)


def peso_categoria(categoria: str, categorias_prioritarias) -> float:
    """1.3 si la categoria es prioritaria para el usuario, 1.0 en caso contrario."""
    return PESO_CATEGORIA_PRIORITARIA if categoria in categorias_prioritarias else PESO_CATEGORIA_NORMAL
