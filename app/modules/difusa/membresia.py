"""Funciones de membresia.

    mu(x) = 0                    si x <= a  o  x >= d
          = (x - a) / (b - a)    si a < x < b
          = 1                    si b <= x <= c
          = (d - x) / (d - c)    si c < x < d

Un triangulo es un trapecio con b = c.
"""


def membresia_trapezoidal(x: float, a: float, b: float, c: float, d: float) -> float:
    if a == b and x == a:
        return 1.0
    if c == d and x >= c:
        return 1.0
    if x <= a or x >= d:
        return 0.0
    if b <= x <= c:
        return 1.0
    if a < x < b:
        return (x - a) / (b - a)
    return (d - x) / (d - c)


def membresia_triangular(x: float, a: float, b: float, c: float) -> float:
    return membresia_trapezoidal(x, a, b, b, c)
