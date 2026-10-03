import pytest

from app.db.conexion import abrir_conexion
from app.db.inicializar import crear_base


@pytest.fixture
def conn():
    """BD en memoria creada desde schema.sql + seed.sql (no toca data/bodega.db)."""
    c = abrir_conexion(":memory:")
    crear_base(c)
    yield c
    c.close()
