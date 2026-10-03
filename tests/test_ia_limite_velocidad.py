import json
import sys
from types import ModuleType
from types import SimpleNamespace

import pytest

import config
import app.orquestador as orquestador
from app.db.solicitud_repo import obtener_solicitud
from app.modules.genetico import ResultadoGenetico
from app.modules.ia import ErrorIA, redactar_explicacion
from app.modules.ia.cliente import (
    ErrorLimiteVelocidad,
    _solicitar_completado,
    crear_cliente_groq,
)
from app.db.catalogo_repo import cargar_catalogo


class Error429(Exception):
    def __init__(self, retry_after=None):
        super().__init__("datos externos que no deben mostrarse")
        headers = {} if retry_after is None else {"retry-after": retry_after}
        self.status_code = 429
        self.response = SimpleNamespace(
            status_code=429,
            headers=headers,
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
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=respuesta))]
        )


@pytest.fixture(autouse=True)
def configurar_modelo(monkeypatch):
    monkeypatch.setattr(config, "GROQ_MODEL", "modelo-falso")


def _solicitar(cliente, sleep_fn):
    return _solicitar_completado(
        cliente,
        [{"role": "user", "content": "texto de prueba"}],
        temperatura=0.0,
        max_tokens=20,
        sleep_fn=sleep_fn,
    )


def test_429_una_vez_y_luego_respuesta_valida_reintenta():
    esperas = []
    cliente = ClienteFalso([Error429("4"), "respuesta válida"])

    resultado = _solicitar(cliente, esperas.append)

    assert resultado == "respuesta válida"
    assert len(cliente.llamadas) == 2
    assert esperas == [4.0]


def test_cliente_groq_desactiva_reintentos_internos_sdk(monkeypatch):
    argumentos = {}
    modulo_groq = ModuleType("groq")

    def groq_falso(**kwargs):
        argumentos.update(kwargs)
        return object()

    modulo_groq.Groq = groq_falso
    monkeypatch.setitem(sys.modules, "groq", modulo_groq)
    monkeypatch.setattr(config, "GROQ_API_KEY", "clave_falsa_de_test")

    crear_cliente_groq()

    assert argumentos["max_retries"] == 0


def test_429_repetido_falla_con_error_especifico_y_esperas_de_respaldo():
    esperas = []
    cliente = ClienteFalso([Error429(), Error429(), Error429()])

    with pytest.raises(ErrorLimiteVelocidad) as error:
        _solicitar(cliente, esperas.append)

    assert str(error.value) == (
        "Hay muchas solicitudes a la IA en este momento. "
        "Espera unos segundos e intenta de nuevo."
    )
    assert len(cliente.llamadas) == 3
    assert esperas == [3.0, 6.0]


def test_retry_after_mayor_al_tope_no_espera_y_falla_de_inmediato():
    esperas = []
    cliente = ClienteFalso([Error429("86400")])

    with pytest.raises(ErrorLimiteVelocidad):
        _solicitar(cliente, esperas.append)

    assert esperas == []
    assert len(cliente.llamadas) == 1


def test_otro_error_api_no_se_reintenta_y_mantiene_mensaje_seguro():
    esperas = []
    cliente = ClienteFalso([TimeoutError("texto privado")])

    with pytest.raises(ErrorIA, match="tiempo máximo") as error:
        _solicitar(cliente, esperas.append)

    assert type(error.value) is ErrorIA
    assert len(cliente.llamadas) == 1
    assert esperas == []
    assert "texto privado" not in str(error.value)


def test_rate_limit_con_tipo_sin_codigo_http_conserva_manejo_anterior():
    FakeRateLimitError = type("RateLimitError", (Exception,), {})
    cliente = ClienteFalso([FakeRateLimitError("mensaje privado")])

    with pytest.raises(ErrorIA, match="límite de uso") as error:
        _solicitar(cliente, lambda _: pytest.fail("No se esperaba reintento."))

    assert type(error.value) is ErrorIA
    assert len(cliente.llamadas) == 1


def _interpretacion_json():
    return json.dumps(
        {
            "presupuesto": 1500,
            "categorias_prioritarias": ["abarrotes"],
            "incluir_forzado": ["Arroz"],
            "excluir": [],
        }
    )


def _explicacion_valida():
    return "Arroz es una buena opción para reponer."


def _rate_limit_repetido():
    return [Error429(), Error429(), Error429()]


def _conteos(conn):
    return (
        conn.execute("SELECT COUNT(*) FROM SOLICITUD").fetchone()[0],
        conn.execute("SELECT COUNT(*) FROM RECOMENDACION").fetchone()[0],
    )


def test_orquestador_en_interpretacion_devuelve_error_sin_escritura(conn):
    conteos_iniciales = _conteos(conn)
    esperas = []
    resultado = orquestador.procesar_mensajes(
        conn,
        ["Tengo S/ 1500, incluye Arroz"],
        cliente=ClienteFalso(_rate_limit_repetido()),
        sleep_fn=esperas.append,
    )

    assert resultado.tipo == "error"
    assert resultado.mensaje == str(ErrorLimiteVelocidad())
    assert _conteos(conn) == conteos_iniciales
    assert esperas == [3.0, 6.0]


def test_orquestador_en_explicacion_guarda_respaldo_y_motivo(conn):
    conteos_iniciales = _conteos(conn)
    esperas = []
    cliente = ClienteFalso(
        [_interpretacion_json(), *_rate_limit_repetido()]
    )

    resultado = orquestador.procesar_mensajes(
        conn,
        ["Tengo S/ 1500, incluye Arroz"],
        cliente=cliente,
        semilla=42,
        sleep_fn=esperas.append,
    )

    assert resultado.tipo == "recomendacion"
    assert resultado.usada_ia is False
    assert "límite de velocidad de la api" in resultado.motivo_respaldo.casefold()
    assert "Hay muchas solicitudes a la IA" in resultado.motivo_respaldo
    assert _conteos(conn) == (
        conteos_iniciales[0] + 1,
        conteos_iniciales[1] + 1,
    )
    assert esperas == [3.0, 6.0]


def test_explicacion_guarda_motivo_sin_clave_de_entorno(conn, monkeypatch):
    clave_prueba = "CLAVE_API_DE_PRUEBA_NO_MOSTRAR"
    monkeypatch.setenv("GROQ_API_KEY", clave_prueba)
    catalogo = cargar_catalogo(conn)
    solicitud = obtener_solicitud(conn, 1)
    resultado_genetico = ResultadoGenetico(
        [1] + [0] * 14, 3.5, 2.0, [2.0]
    )
    esperas = []

    resultado = redactar_explicacion(
        solicitud,
        resultado_genetico,
        catalogo,
        cliente=ClienteFalso(_rate_limit_repetido()),
        sleep_fn=esperas.append,
    )

    assert resultado.usada_ia is False
    assert clave_prueba not in resultado.motivo_respaldo
    assert "límite de velocidad" in resultado.motivo_respaldo.casefold()
    assert esperas == [3.0, 6.0]
