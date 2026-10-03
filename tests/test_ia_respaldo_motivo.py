import json
from types import SimpleNamespace

import config
from app.db.catalogo_repo import cargar_catalogo
from app.db.solicitud_repo import obtener_solicitud
from app.modules.genetico import ResultadoGenetico
from app.modules.ia import interpretar_solicitud, redactar_explicacion


class ClienteFalso:
    def __init__(self, respuestas):
        self.respuestas = list(respuestas)
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self.create)
        )

    def create(self, **kwargs):
        respuesta = self.respuestas.pop(0)
        if isinstance(respuesta, Exception):
            raise respuesta
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=respuesta))]
        )


def _interpretacion_json(**sobrescrituras):
    valores = {
        "presupuesto": 1500,
        "categorias_prioritarias": [],
        "incluir_forzado": [],
        "excluir": [],
    }
    valores.update(sobrescrituras)
    return json.dumps(valores, ensure_ascii=False)


def test_termino_resuelto_no_catalogo_no_se_reporta_como_desconocido(
    conn, monkeypatch
):
    monkeypatch.setattr(config, "GROQ_MODEL", "modelo-falso")
    cliente = ClienteFalso(
        [_interpretacion_json(incluir_forzado=["leche"], no_catalogo=["leche"])]
    )

    resultado = interpretar_solicitud(
        "Tengo 1500 para reponer, incluye leche",
        cargar_catalogo(conn),
        cliente=cliente,
    )

    assert resultado.solicitud["incluir_forzado"] == ["Leche Gloria 1L"]
    assert resultado.no_reconocidos == []
    assert resultado.pregunta_aclaracion is None


def test_termino_resuelto_sin_no_catalogo_no_genera_aclaracion(conn, monkeypatch):
    monkeypatch.setattr(config, "GROQ_MODEL", "modelo-falso")
    cliente = ClienteFalso(
        [_interpretacion_json(incluir_forzado=["leche"])]
    )

    resultado = interpretar_solicitud(
        "Tengo 1500 para reponer, incluye leche",
        cargar_catalogo(conn),
        cliente=cliente,
    )

    assert resultado.solicitud["incluir_forzado"] == ["Leche Gloria 1L"]
    assert resultado.no_reconocidos == []
    assert resultado.pregunta_aclaracion is None


def test_producto_inexistente_sigue_en_no_reconocidos(conn, monkeypatch):
    monkeypatch.setattr(config, "GROQ_MODEL", "modelo-falso")
    resultado = interpretar_solicitud(
        "Tengo 1500 para reponer",
        cargar_catalogo(conn),
        cliente=ClienteFalso(
            [_interpretacion_json(no_catalogo=["pizza congelada"])]
        ),
    )

    assert resultado.no_reconocidos == ["pizza congelada"]
    assert "pizza congelada" in resultado.pregunta_aclaracion


def _parametros_explicacion(conn):
    catalogo = cargar_catalogo(conn)
    solicitud = obtener_solicitud(conn, 1)
    resultado = ResultadoGenetico(
        [1] + [0] * (len(catalogo) - 1),
        catalogo[0]["precio_compra"],
        1.0,
        [1.0],
    )
    return solicitud, resultado, catalogo


def test_motivo_validacion_incluye_reglas_e_intentos(conn, monkeypatch):
    monkeypatch.setattr(config, "GROQ_MODEL", "modelo-falso")
    solicitud, resultado, catalogo = _parametros_explicacion(conn)
    explicacion = redactar_explicacion(
        solicitud,
        resultado,
        catalogo,
        cliente=ClienteFalso(["El total es $1.", "El total es $1."]),
    )

    assert explicacion.usada_ia is False
    assert explicacion.motivo_respaldo is not None
    assert "símbolo de dólar" in explicacion.motivo_respaldo
    assert "Primer intento" in explicacion.motivo_respaldo
    assert "Reintento" in explicacion.motivo_respaldo


def test_motivo_api_es_error_seguro_y_no_incluye_clave(conn, monkeypatch):
    monkeypatch.setattr(config, "GROQ_MODEL", "modelo-falso")
    clave_prueba = "CLAVE_DE_PRUEBA_NO_MOSTRAR"
    monkeypatch.setenv("GROQ_API_KEY", clave_prueba)
    solicitud, resultado, catalogo = _parametros_explicacion(conn)
    explicacion = redactar_explicacion(
        solicitud,
        resultado,
        catalogo,
        cliente=ClienteFalso([TimeoutError(f"fallo {clave_prueba}")]),
    )

    assert explicacion.usada_ia is False
    assert explicacion.motivo_respaldo == (
        "La solicitud a Groq superó el tiempo máximo de espera."
    )
    assert clave_prueba not in explicacion.motivo_respaldo


def test_explicacion_valida_no_tiene_motivo(conn, monkeypatch):
    monkeypatch.setattr(config, "GROQ_MODEL", "modelo-falso")
    solicitud, resultado, catalogo = _parametros_explicacion(conn)
    explicacion = redactar_explicacion(
        solicitud,
        resultado,
        catalogo,
        cliente=ClienteFalso(["Compra recomendada."]),
    )

    assert explicacion.usada_ia is True
    assert explicacion.motivo_respaldo is None
