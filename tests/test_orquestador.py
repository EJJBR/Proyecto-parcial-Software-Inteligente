import json
from types import SimpleNamespace

import pytest

import config
import app.orquestador as orquestador
from app.db.catalogo_repo import cargar_catalogo
from app.db.recomendacion_repo import obtener_recomendacion
from app.modules.ia import ErrorIA


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
def configuracion_rapida(monkeypatch):
    monkeypatch.setattr(config, "GROQ_MODEL", "modelo-falso")
    monkeypatch.setattr(config, "GENERACIONES", 3)
    monkeypatch.setattr(config, "TAMANO_POBLACION", 8)


def _json_interpretacion(**campos):
    datos = {
        "presupuesto": 1500,
        "categorias_prioritarias": ["abarrotes"],
        "incluir_forzado": ["Arroz"],
        "excluir": [],
    }
    datos.update(campos)
    return json.dumps(datos, ensure_ascii=False)


def _respuesta_valida():
    return "Arroz es una buena opción para reponer."


def _conteos(conn):
    solicitud = conn.execute("SELECT COUNT(*) FROM SOLICITUD").fetchone()[0]
    recomendacion = conn.execute("SELECT COUNT(*) FROM RECOMENDACION").fetchone()[0]
    return solicitud, recomendacion


def test_flujo_completo_guarda_y_devuelve_recomendacion(conn):
    conteos_iniciales = _conteos(conn)
    resumen_valido = (
        "La planificación consideró el presupuesto disponible y las prioridades "
        "indicadas. También equilibró las necesidades de reposición."
    )
    cliente = ClienteFalso([_json_interpretacion(), resumen_valido])

    resultado = orquestador.procesar_mensajes(
        conn, ["Tengo S/ 1500, incluye Arroz"], cliente=cliente, semilla=42
    )

    assert resultado.tipo == "recomendacion"
    assert resultado.id_recomendacion is not None
    assert resultado.presupuesto == 1500
    assert resultado.costo_total is not None
    assert resultado.fitness is not None
    assert resultado.usada_ia is True
    assert resultado.resumen_ia == resumen_valido
    assert resultado.detalle_explicacion
    assert resultado.explicacion == (
        f"{resultado.resumen_ia}\n\n{resultado.detalle_explicacion}"
    )
    assert resultado.motivo_respaldo is None
    assert any(p["nombre"] == "Arroz" and p["cantidad"] > 0 for p in resultado.productos)
    assert _conteos(conn) == (
        conteos_iniciales[0] + 1,
        conteos_iniciales[1] + 1,
    )
    guardada = obtener_recomendacion(conn, 2)
    assert guardada is not None
    assert guardada["explicacion_texto"] == resultado.explicacion


@pytest.mark.parametrize(
    "respuesta",
    [
        _json_interpretacion(presupuesto=None),
        _json_interpretacion(no_catalogo=["pizza congelada"]),
    ],
)
def test_aclaracion_no_ejecuta_genetico_ni_escribe(
    conn, monkeypatch, respuesta
):
    conteos_iniciales = _conteos(conn)
    def no_debe_ejecutarse(*args, **kwargs):
        pytest.fail("El genético no debe ejecutarse si se necesita aclaración.")

    monkeypatch.setattr(orquestador, "ejecutar_algoritmo_genetico", no_debe_ejecutarse)
    resultado = orquestador.procesar_mensajes(
        conn,
        ["Tengo 1500 soles, incluye pizza congelada"],
        cliente=ClienteFalso([respuesta]),
    )

    assert resultado.tipo == "aclaracion"
    assert resultado.mensaje
    assert _conteos(conn) == conteos_iniciales


def test_error_ia_en_interpretacion_no_escribe_ni_ejecuta_genetico(
    conn, monkeypatch
):
    conteos_iniciales = _conteos(conn)
    def no_debe_ejecutarse(*args, **kwargs):
        pytest.fail("El genético no debe ejecutarse tras ErrorIA.")

    monkeypatch.setattr(orquestador, "ejecutar_algoritmo_genetico", no_debe_ejecutarse)
    resultado = orquestador.procesar_mensajes(
        conn,
        ["Tengo S/ 1500"],
        cliente=ClienteFalso([TimeoutError("detalle privado")]),
    )

    assert resultado.tipo == "error"
    assert "Groq" in resultado.mensaje
    assert _conteos(conn) == conteos_iniciales


def test_respaldo_de_explicacion_se_guarda_con_motivo(conn):
    conteos_iniciales = _conteos(conn)
    cliente = ClienteFalso(
        [_json_interpretacion(), "La demanda es score.", "La demanda es score."]
    )

    resultado = orquestador.procesar_mensajes(
        conn, ["Tengo S/ 1500, incluye Arroz"], cliente=cliente, semilla=42
    )

    assert resultado.tipo == "recomendacion"
    assert resultado.usada_ia is False
    assert resultado.motivo_respaldo
    assert "Primer intento" in resultado.motivo_respaldo
    assert _conteos(conn) == (
        conteos_iniciales[0] + 1,
        conteos_iniciales[1] + 1,
    )
    guardada = obtener_recomendacion(conn, 2)
    assert guardada is not None
    assert guardada["explicacion_texto"] == resultado.explicacion


def test_fallo_al_guardar_hace_rollback_de_solicitud(
    conn, monkeypatch
):
    conteos_iniciales = _conteos(conn)
    def falla_al_guardar(*args, **kwargs):
        raise ValueError("detalle que no debe exponerse")

    monkeypatch.setattr(orquestador, "guardar_recomendacion", falla_al_guardar)
    resultado = orquestador.procesar_mensajes(
        conn,
        ["Tengo S/ 1500, incluye Arroz"],
        cliente=ClienteFalso([_json_interpretacion(), _respuesta_valida()]),
        semilla=42,
    )

    assert resultado.tipo == "error"
    assert resultado.mensaje == "No se pudo guardar la recomendación."
    assert _conteos(conn) == conteos_iniciales


def test_usa_solo_los_cinco_mensajes_mas_recientes(conn):
    mensajes = [
        "mensaje antiguo que debe descartarse",
        "Tengo S/ 1500",
        "prioriza abarrotes",
        "considera las ventas recientes",
        "incluye Arroz",
        "no excluyas productos",
    ]
    cliente = ClienteFalso([_json_interpretacion(), _respuesta_valida()])

    resultado = orquestador.procesar_mensajes(
        conn, mensajes, cliente=cliente, semilla=42
    )

    assert resultado.tipo == "recomendacion"
    texto_prompt = cliente.llamadas[0]["messages"][1]["content"]
    assert "mensaje antiguo que debe descartarse" not in texto_prompt
    assert "prioriza abarrotes" in texto_prompt
    assert "no excluyas productos" in texto_prompt


def test_dos_corridas_misma_frase_guardan_dos_pares(conn):
    conteos_iniciales = _conteos(conn)
    frase = "Tengo S/ 1500, incluye Arroz"
    resumen_valido = (
        "La planificación consideró el presupuesto disponible y las prioridades "
        "indicadas. También equilibró las necesidades de reposición."
    )
    cliente = ClienteFalso(
        [
            _json_interpretacion(),
            resumen_valido,
            _json_interpretacion(),
            resumen_valido,
        ]
    )

    primero = orquestador.procesar_mensajes(
        conn, [frase], cliente=cliente, semilla=42
    )
    segundo = orquestador.procesar_mensajes(
        conn, [frase], cliente=cliente, semilla=42
    )

    assert primero.tipo == segundo.tipo == "recomendacion", (primero, segundo)
    assert primero.id_recomendacion != segundo.id_recomendacion
    assert _conteos(conn) == (
        conteos_iniciales[0] + 2,
        conteos_iniciales[1] + 2,
    )


@pytest.mark.parametrize("mensajes", [[], [""], ["Tengo S/1500", " "]])
def test_mensajes_vacios_dan_error_sin_llamar_ia(conn, mensajes):
    resultado = orquestador.procesar_mensajes(
        conn, mensajes, cliente=ClienteFalso([])
    )

    assert resultado.tipo == "error"
    assert resultado.mensaje
