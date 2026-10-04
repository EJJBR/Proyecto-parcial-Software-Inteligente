import json
import sqlite3
from types import SimpleNamespace

import pytest

import config
from app import create_app
from app.db.inicializar import crear_base
import app.orquestador as orquestador


class ClienteFalso:
    def __init__(self, respuestas):
        self.respuestas = list(respuestas)
        self.llamadas = []
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self.create)
        )

    def create(self, **kwargs):
        self.llamadas.append(kwargs)
        respuesta = self.respuestas.pop(0)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=respuesta)
                )
            ]
        )


def _respuesta_interpretacion():
    return json.dumps(
        {
            "presupuesto": 1500,
            "categorias_prioritarias": ["panaderia", "lacteos"],
            "incluir_forzado": ["arroz"],
            "excluir": ["detergente"],
        }
    )


def test_orquestador_devuelve_entendido_con_nombres_canonicos(conn, monkeypatch):
    monkeypatch.setattr(config, "GROQ_MODEL", "modelo-falso")
    monkeypatch.setattr(config, "GENERACIONES", 3)
    monkeypatch.setattr(config, "TAMANO_POBLACION", 8)
    cliente = ClienteFalso(
        [_respuesta_interpretacion(), "Arroz es una buena opción para reponer."]
    )

    resultado = orquestador.procesar_mensajes(
        conn,
        [
            "Tengo S/1500, prioriza panadería y lácteos, incluye arroz "
            "y excluye detergente"
        ],
        cliente=cliente,
        semilla=42,
    )

    assert resultado.tipo == "recomendacion"
    assert resultado.entendido == {
        "presupuesto": 1500.0,
        "categorias_prioritarias": ["panaderia", "lacteos"],
        "incluir_forzado": ["Arroz"],
        "excluir": ["Detergente"],
    }


@pytest.fixture
def cliente_http(tmp_path):
    db_path = tmp_path / "entendido.sqlite"
    conn = sqlite3.connect(str(db_path))
    crear_base(conn)
    conn.close()
    app = create_app(
        {
            "SECRET_KEY": "secreto-solo-para-pruebas",
            "DB_PATH": db_path,
            "TESTING": True,
        }
    )
    return app.test_client()


def test_ruta_devuelve_entendido_solo_en_recomendacion(
    cliente_http, monkeypatch
):
    entendido = {
        "presupuesto": 1500.0,
        "categorias_prioritarias": ["panaderia", "lacteos"],
        "incluir_forzado": ["Arroz"],
        "excluir": ["Detergente"],
    }
    resultado_recomendacion = SimpleNamespace(
        tipo="recomendacion",
        productos=[],
        costo_total=0.0,
        presupuesto=1500.0,
        fitness=0.0,
        explicacion="Explicación de prueba.",
        usada_ia=True,
        motivo_respaldo=None,
        id_solicitud=1,
        id_recomendacion=1,
        entendido=entendido,
    )
    monkeypatch.setattr(
        "app.rutas.procesar_mensajes",
        lambda *args, **kwargs: resultado_recomendacion,
    )

    respuesta = cliente_http.post(
        "/api/solicitud", json={"mensaje": "Tengo S/1500"}
    )

    assert respuesta.status_code == 200
    assert respuesta.get_json()["entendido"] == entendido


@pytest.mark.parametrize(
    ("tipo", "codigo_error"),
    [("aclaracion", None), ("error", "ia_no_disponible")],
)
def test_ruta_no_devuelve_entendido_en_aclaracion_ni_error(
    cliente_http, monkeypatch, tipo, codigo_error
):
    resultado = SimpleNamespace(
        tipo=tipo,
        mensaje="Se necesita más información.",
        codigo_error=codigo_error,
        entendido=None,
    )
    monkeypatch.setattr(
        "app.rutas.procesar_mensajes",
        lambda *args, **kwargs: resultado,
    )

    respuesta = cliente_http.post(
        "/api/solicitud", json={"mensaje": "Tengo S/1500"}
    )

    assert "entendido" not in respuesta.get_json()
