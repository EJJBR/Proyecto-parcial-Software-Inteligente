import json
from types import SimpleNamespace

import pytest

import config
from app.db.catalogo_repo import cargar_catalogo
from app.modules.ia import interpretar_solicitud


@pytest.fixture(autouse=True)
def configurar_modelo(monkeypatch):
    monkeypatch.setattr(config, "GROQ_MODEL", "modelo-falso")


class ClienteFalso:
    def __init__(self, payload):
        self.payload = payload
        self.llamadas = []
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self.create)
        )

    def create(self, **kwargs):
        self.llamadas.append(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=json.dumps(self.payload, ensure_ascii=False)
                    )
                )
            ]
        )


def _payload(**campos):
    datos = {
        "presupuesto": 1000,
        "categorias_prioritarias": [],
        "incluir_forzado": [],
        "excluir": [],
        "no_catalogo": [],
    }
    datos.update(campos)
    return datos


def test_prompt_instruye_grupos_genericos_y_elementos_separados(conn):
    catalogo = cargar_catalogo(conn)
    cliente = ClienteFalso(_payload())

    interpretar_solicitud(
        "Con 1000 soles, sin gaseosas", catalogo, cliente=cliente
    )

    instrucciones = cliente.llamadas[0]["messages"][0]["content"].casefold()
    assert "todos los productos del catálogo" in instrucciones
    assert "gaseosa coca-cola 1.5l" in instrucciones
    assert "inca kola 1.5l" in instrucciones
    assert "categoría válida" in instrucciones
    assert "ignorar tildes y mayúsculas" in instrucciones
    assert "cada producto o categoría como un elemento separado" in instrucciones
    assert "nunca unas varios nombres con 'y', 'e' o comas" in instrucciones


def test_excluir_gaseosas_resuelve_todos_los_nombres_devuelto_por_modelo(conn):
    catalogo = cargar_catalogo(conn)
    cliente = ClienteFalso(
        _payload(excluir=["Gaseosa Coca-Cola 1.5L", "Inca Kola 1.5L"])
    )

    resultado = interpretar_solicitud(
        "Con 1000 soles quiero comprar sin gaseosas",
        catalogo,
        cliente=cliente,
    )

    assert resultado.solicitud["excluir"] == [
        "Gaseosa Coca-Cola 1.5L",
        "Inca Kola 1.5L",
    ]
    assert not resultado.no_reconocidos


def test_categorias_unidas_por_conjuncion_se_resuelven(conn):
    catalogo = cargar_catalogo(conn)
    cliente = ClienteFalso(
        _payload(
            presupuesto=1350,
            categorias_prioritarias=["panadería y lácteos"],
        )
    )

    resultado = interpretar_solicitud(
        "Tengo S/1350, prioriza panadería y lácteos",
        catalogo,
        cliente=cliente,
    )

    assert resultado.solicitud["categorias_prioritarias"] == [
        "panaderia",
        "lacteos",
    ]
    assert resultado.pregunta_aclaracion is None
    assert not resultado.no_reconocidos


def test_producto_inexistente_sigue_no_reconocido(conn):
    catalogo = cargar_catalogo(conn)
    cliente = ClienteFalso(
        _payload(incluir_forzado=["pizza congelada"])
    )

    resultado = interpretar_solicitud(
        "Incluye pizza congelada, tengo 1500 soles",
        catalogo,
        cliente=cliente,
    )

    assert resultado.no_reconocidos == ["pizza congelada"]
    assert resultado.pregunta_aclaracion is not None
