import json
from types import SimpleNamespace

import pytest

import config
from app.db.catalogo_repo import cargar_catalogo
from app.db.solicitud_repo import obtener_solicitud
from app.modules.genetico import ResultadoGenetico
from app.modules.ia import interpretar_solicitud, redactar_explicacion
from app.modules.ia.cliente import RespuestaIATruncada


def _respuesta_valida():
    return (
        "Se recomienda reponer arroz, leche, aceite, fideos, atún, pan, yogurt, "
        "gaseosa, detergente, galletas, huevos, queso, azúcar, papas e Inca Kola. "
        "El costo total es S/ 1,499.70 frente al presupuesto de S/ 1,500.00, "
        "con un sobrante de S/ 0.30. Las categorías de abarrotes y lácteos reciben "
        "prioridad según la solicitud. Los artículos más perecibles se manejan con "
        "cantidades cuidadas por su duración. El presupuesto fue el factor que "
        "limitó la compra y algunos productos quedaron por debajo de su límite."
    )


def _interpretacion_valida():
    return json.dumps(
        {
            "presupuesto": 1500,
            "categorias_prioritarias": ["lacteos"],
            "incluir_forzado": ["Arroz"],
            "excluir": [],
        }
    )


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
        if isinstance(respuesta, Exception):
            raise respuesta
        if isinstance(respuesta, tuple):
            contenido, finish_reason = respuesta
        else:
            contenido, finish_reason = respuesta, "stop"
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=contenido),
                    finish_reason=finish_reason,
                )
            ]
        )


@pytest.fixture
def datos_explicacion(conn, monkeypatch):
    monkeypatch.setattr(config, "GROQ_MODEL", "modelo-falso")
    catalogo = cargar_catalogo(conn)
    solicitud = obtener_solicitud(conn, 1)
    resultado = ResultadoGenetico(
        [26, 16, 26, 26, 26, 16, 21, 26, 7, 21, 21, 16, 26, 26, 26],
        1499.70,
        1293.07,
        [1293.07],
    )
    return solicitud, resultado, catalogo


def test_explicacion_reintenta_finish_reason_length_y_acepta_completa(
    datos_explicacion,
):
    solicitud, resultado, catalogo = datos_explicacion
    cliente = ClienteFalso(
        [
            ("Se recomienda comprar arroz porque la demanda", "length"),
            (_respuesta_valida(), "stop"),
        ]
    )

    explicacion = redactar_explicacion(
        solicitud, resultado, catalogo, cliente=cliente
    )

    assert explicacion.usada_ia is True
    assert explicacion.texto == _respuesta_valida()
    assert len(cliente.llamadas) == 2
    assert "Corrige además" in cliente.llamadas[1]["messages"][0]["content"]


def test_dos_respuestas_length_usan_respaldo_con_motivo_seguro(
    datos_explicacion,
):
    solicitud, resultado, catalogo = datos_explicacion
    texto_parcial = "TEXTO_PARCIAL_PRIVADO_API_KEY_FALSA"
    cliente = ClienteFalso(
        [(texto_parcial, "length"), (texto_parcial + " más", "length")]
    )

    explicacion = redactar_explicacion(
        solicitud, resultado, catalogo, cliente=cliente
    )

    assert explicacion.usada_ia is False
    assert explicacion.motivo_respaldo == (
        "La respuesta de la IA se cortó por límite de tokens"
    )
    assert texto_parcial not in explicacion.motivo_respaldo
    assert "API_KEY_FALSA" not in explicacion.motivo_respaldo
    assert len(cliente.llamadas) == 2


def test_explicacion_sin_puntuacion_final_se_rechaza(datos_explicacion):
    solicitud, resultado, catalogo = datos_explicacion
    texto_incompleto = _respuesta_valida().rstrip(".")
    cliente = ClienteFalso([texto_incompleto, texto_incompleto])

    explicacion = redactar_explicacion(
        solicitud, resultado, catalogo, cliente=cliente
    )

    assert explicacion.usada_ia is False
    assert "no termina con puntuación final" in explicacion.motivo_respaldo
    assert len(cliente.llamadas) == 2


def test_finish_reason_stop_acepta_respuesta_valida(datos_explicacion):
    solicitud, resultado, catalogo = datos_explicacion
    cliente = ClienteFalso([(_respuesta_valida(), "stop")])

    explicacion = redactar_explicacion(
        solicitud, resultado, catalogo, cliente=cliente
    )

    assert explicacion.usada_ia is True
    assert explicacion.texto == _respuesta_valida()
    assert len(cliente.llamadas) == 1


def test_finish_reason_length_tambien_rechaza_interpretacion(conn, monkeypatch):
    monkeypatch.setattr(config, "GROQ_MODEL", "modelo-falso")
    catalogo = cargar_catalogo(conn)
    cliente = ClienteFalso([('{"presupuesto":1500', "length")])

    with pytest.raises(RespuestaIATruncada):
        interpretar_solicitud(
            "Tengo S/1500", catalogo, cliente=cliente
        )

    assert len(cliente.llamadas) == 1


def test_reasoning_effort_se_envia_solo_en_explicacion(
    datos_explicacion,
):
    solicitud, resultado, catalogo = datos_explicacion
    cliente = ClienteFalso(
        [_interpretacion_valida(), _respuesta_valida()]
    )

    interpretar_solicitud(
        "Tengo S/1500, prioriza lácteos e incluye arroz",
        catalogo,
        cliente=cliente,
    )
    redactar_explicacion(
        solicitud, resultado, catalogo, cliente=cliente
    )

    assert "reasoning_effort" not in cliente.llamadas[0]
    assert cliente.llamadas[1]["reasoning_effort"] == "low"


def test_reasoning_effort_none_no_se_envia(datos_explicacion, monkeypatch):
    solicitud, resultado, catalogo = datos_explicacion
    monkeypatch.setattr(config, "GROQ_REASONING_EFFORT_EXPLICACION", None)
    cliente = ClienteFalso([_respuesta_valida()])

    redactar_explicacion(
        solicitud, resultado, catalogo, cliente=cliente
    )

    assert "reasoning_effort" not in cliente.llamadas[0]
