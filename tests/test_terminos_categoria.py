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
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self.create)
        )

    def create(self, **kwargs):
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


def _interpretar(conn, payload, texto="Tengo S/1000"):
    return interpretar_solicitud(
        texto,
        cargar_catalogo(conn),
        cliente=ClienteFalso(payload),
    )


def test_categoria_en_excluir_se_expande_a_todos_sus_productos(conn):
    resultado = _interpretar(
        conn,
        _payload(excluir=["snacks"]),
        "Tengo 1000 soles, sin snacks",
    )

    assert resultado.solicitud["excluir"] == ["Galletas Oreo", "Papas Lay's"]
    assert resultado.pregunta_aclaracion is None


def test_categoria_en_incluir_se_expande_a_todos_sus_productos(conn):
    resultado = _interpretar(
        conn,
        _payload(incluir_forzado=["bebidas"]),
    )

    assert resultado.solicitud["incluir_forzado"] == [
        "Gaseosa Coca-Cola 1.5L",
        "Inca Kola 1.5L",
    ]
    assert resultado.pregunta_aclaracion is None


def test_productos_que_cubren_categoria_completa_se_vuelven_prioridad(conn):
    resultado = _interpretar(
        conn,
        _payload(
            presupuesto=1500,
            categorias_prioritarias=[
                "Gaseosa Coca-Cola 1.5L",
                "Inca Kola 1.5L",
            ]
        ),
        "Tengo 1500, prioriza gaseosas",
    )

    assert resultado.solicitud["categorias_prioritarias"] == ["bebidas"]
    assert resultado.solicitud["incluir_forzado"] == []
    assert resultado.pregunta_aclaracion is None


def test_producto_suelto_en_prioridad_pasa_a_incluir_sin_duplicar(conn):
    resultado = _interpretar(
        conn,
        _payload(
            categorias_prioritarias=["Arroz", "arroz"],
            incluir_forzado=["Arroz"],
        ),
    )

    assert resultado.solicitud["categorias_prioritarias"] == []
    assert resultado.solicitud["incluir_forzado"] == ["Arroz"]
    assert resultado.pregunta_aclaracion is None


def test_desconocido_y_categorias_compuestas_conservan_su_resolucion(conn):
    desconocido = _interpretar(
        conn,
        _payload(incluir_forzado=["pizza congelada"]),
    )
    compuestas = _interpretar(
        conn,
        _payload(
            presupuesto=1350,
            categorias_prioritarias=["panadería y lácteos"],
        ),
        "Tengo S/1350, prioriza panadería y lácteos",
    )

    assert desconocido.no_reconocidos == ["pizza congelada"]
    assert compuestas.solicitud["categorias_prioritarias"] == [
        "panaderia",
        "lacteos",
    ]
    assert compuestas.no_reconocidos == []


def test_categoria_excluida_con_producto_incluido_genera_contradiccion(conn):
    resultado = _interpretar(
        conn,
        _payload(
            incluir_forzado=["Papas Lay's"],
            excluir=["snacks"],
        ),
    )

    assert resultado.pregunta_aclaracion is not None
    assert "Papas Lay's" in resultado.pregunta_aclaracion


def test_interfaz_mapea_etiquetas_y_usa_ejemplo_generico(tmp_path):
    from app import create_app

    app = create_app(
        {
            "SECRET_KEY": "solo-para-pruebas",
            "DB_PATH": tmp_path / "interfaz-categorias.sqlite",
            "TESTING": True,
        }
    )
    cliente = app.test_client()
    javascript = cliente.get("/static/js/app.js").get_data(as_text=True)
    html = cliente.get("/").get_data(as_text=True)

    assert "lacteos: \"lácteos\"" in javascript
    assert "panaderia: \"panadería\"" in javascript
    assert "excluye también las galletas" in html
    assert "innerHTML" not in javascript
    assert "eval(" not in javascript
    assert "document.write" not in javascript
