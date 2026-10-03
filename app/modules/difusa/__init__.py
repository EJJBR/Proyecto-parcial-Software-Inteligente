"""Logica difusa: score_demanda, riesgo_merma y peso_categoria."""
from .membresia import membresia_trapezoidal, membresia_triangular
from .variables import (
    fuzzificar_demanda,
    fuzzificar_riesgo,
    peso_categoria,
    riesgo_merma,
    score_demanda,
)

__all__ = [
    "membresia_trapezoidal", "membresia_triangular",
    "fuzzificar_demanda", "fuzzificar_riesgo",
    "score_demanda", "riesgo_merma", "peso_categoria",
]
