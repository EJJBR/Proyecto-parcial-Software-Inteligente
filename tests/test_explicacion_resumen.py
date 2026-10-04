import json
import sqlite3
from types import SimpleNamespace

import pytest

import config
from app import create_app
from app.db.catalogo_repo import cargar_catalogo
from app.db.inicializar import crear_base
from app.db.solicitud_repo import obtener_solicitud
from app.modules.genetico import ResultadoGenetico
from app.modules.ia.explicacion import redactar_resumen_explicacion


RESUMEN_VALIDO = (
    "El presupuesto permitió atender la compra y sobró una pequeña parte. "
    "También se respetaron las prioridades indicadas."
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
        if isinstance(respuesta, tuple):
            texto, finish_reason = respuesta
        else:
            texto, finish_reason = respuesta, "stop"
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=texto),
                    finish_reason=finish_reason,
                )
            ]
        )


@pytest.fixture
def hechos(conn, monkeypatch):
    monkeypatch.setattr(config, "GROQ_MODEL", "modelo-falso")
    catalogo = cargar_catalogo(conn)
    solicitud = obtener_solicitud(conn, 1)
    cromosoma = [26, 16, 26, 26, 26, 16, 21, 26, 7, 21, 21, 16, 26, 26, 26]
    resultado = ResultadoGenetico(cromosoma, 1499.70, 1293.07, [1293.07])
    return solicitud, resultado, catalogo


def test_resumen_valido_se_acepta_y_envia_solo_hechos_cualitativos(hechos):
    solicitud, resultado, catalogo = hechos
    cliente = ClienteFalso([RESUMEN_VALIDO])

    explicacion = redactar_resumen_explicacion(
        solicitud, resultado, catalogo, cliente=cliente
    )

    assert explicacion.usada_ia is True
    assert explicacion.resumen_ia == RESUMEN_VALIDO
    assert explicacion.detalle_codigo in explicacion.texto
    hechos_enviados = json.loads(cliente.llamadas[0]["messages"][1]["content"])
    assert "presupuesto_fue_factor_limitante" in hechos_enviados
    assert "porcentaje_aproximado_del_presupuesto_usado" in hechos_enviados
    assert not any(
        producto["nombre"] in cliente.llamadas[0]["messages"][1]["content"]
        for producto in catalogo
    )
    assert not any(char.isdigit() for char in cliente.llamadas[0]["messages"][1]["content"])


def test_nombre_de_producto_se_reintenta_y_respaldo_no_revela_respuesta(hechos):
    solicitud, resultado, catalogo = hechos
    texto_secreto = "Arroz mantiene una buena salida. Clave de prueba CONFIDENCIAL."
    cliente = ClienteFalso([texto_secreto, texto_secreto])

    explicacion = redactar_resumen_explicacion(
        solicitud, resultado, catalogo, cliente=cliente
    )

    assert explicacion.usada_ia is False
    assert explicacion.resumen_ia is None
    assert len(cliente.llamadas) == 2
    assert explicacion.detalle_codigo in explicacion.texto
    assert texto_secreto not in (explicacion.motivo_respaldo or "")
    assert "CONFIDENCIAL" not in (explicacion.motivo_respaldo or "")


@pytest.mark.parametrize(
    "respuesta_invalida",
    [
        "El presupuesto usado fue de 80 por ciento. Se atendió lo pedido.",
        "El presupuesto alcanzó para cubrir lo esencial y se priorizó lo necesario. "
        + " ".join(["Se"] * 60)
        + ".",
        "El presupuesto permitió atender la compra. Quedó un saldo",
        (RESUMEN_VALIDO, "length"),
    ],
)
def test_resumen_invalido_se_reintenta(respuesta_invalida, hechos):
    solicitud, resultado, catalogo = hechos
    cliente = ClienteFalso([respuesta_invalida, RESUMEN_VALIDO])

    explicacion = redactar_resumen_explicacion(
        solicitud, resultado, catalogo, cliente=cliente
    )

    assert explicacion.usada_ia is True
    assert explicacion.resumen_ia == RESUMEN_VALIDO
    assert len(cliente.llamadas) == 2


def test_dos_fallos_conservan_detalle_y_motivo_seguro(hechos):
    solicitud, resultado, catalogo = hechos
    texto_secreto = "La recomendación salió bien. Código 918273."
    cliente = ClienteFalso([texto_secreto, texto_secreto])

    explicacion = redactar_resumen_explicacion(
        solicitud, resultado, catalogo, cliente=cliente
    )

    assert explicacion.usada_ia is False
    assert explicacion.detalle_codigo
    assert explicacion.texto == explicacion.detalle_codigo
    assert texto_secreto not in (explicacion.motivo_respaldo or "")
    assert "918273" not in (explicacion.motivo_respaldo or "")


@pytest.mark.parametrize(
    ("tipo", "campos"),
    [
        (
            "recomendacion",
            {
                "resumen_ia": RESUMEN_VALIDO,
                "detalle_explicacion": "Detalle calculado localmente.",
            },
        ),
        ("aclaracion", {}),
        ("error", {}),
    ],
)
def test_ruta_expone_resumen_y_detalle_solo_en_recomendacion(
    tmp_path, monkeypatch, tipo, campos
):
    db_path = tmp_path / "recomendacion.sqlite"
    conn = sqlite3.connect(str(db_path))
    crear_base(conn)
    conn.close()
    app = create_app(
        {
            "SECRET_KEY": "clave-de-prueba",
            "DB_PATH": db_path,
            "TESTING": True,
        }
    )
    if tipo == "recomendacion":
        resultado = SimpleNamespace(
            tipo=tipo,
            productos=[],
            costo_total=0.0,
            presupuesto=1500.0,
            fitness=0.0,
            explicacion=f"{RESUMEN_VALIDO}\n\nDetalle calculado localmente.",
            usada_ia=True,
            motivo_respaldo=None,
            id_solicitud=1,
            id_recomendacion=1,
            entendido={},
            **campos,
        )
    else:
        resultado = SimpleNamespace(
            tipo=tipo,
            mensaje="Se necesita más información.",
            codigo_error="interno" if tipo == "error" else None,
        )
    monkeypatch.setattr(
        "app.rutas.procesar_mensajes", lambda *args, **kwargs: resultado
    )

    response = app.test_client().post(
        "/api/solicitud", json={"mensaje": "Tengo S/ 1500"}
    )

    payload = response.get_json()
    if tipo == "recomendacion":
        assert payload["resumen_ia"] == RESUMEN_VALIDO
        assert payload["detalle_explicacion"] == "Detalle calculado localmente."
        assert payload["explicacion"].startswith(RESUMEN_VALIDO)
    else:
        assert "resumen_ia" not in payload
        assert "detalle_explicacion" not in payload
