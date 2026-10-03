import json
from types import SimpleNamespace

import pytest

import config
from app.db.catalogo_repo import cargar_catalogo
from app.db.solicitud_repo import obtener_solicitud
from app.modules.genetico import ResultadoGenetico
from app.modules.ia import interpretar_solicitud, redactar_explicacion
from app.modules.ia.interpretacion import _parsear_presupuesto


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
            choices=[SimpleNamespace(message=SimpleNamespace(content=respuesta))]
        )


def _respuesta_solicitud(**sobrescrituras):
    datos = {
        "presupuesto": 1500,
        "categorias_prioritarias": [],
        "incluir_forzado": [],
        "excluir": [],
    }
    datos.update(sobrescrituras)
    return json.dumps(datos, ensure_ascii=False)


@pytest.fixture
def catalogo_solicitud(conn, monkeypatch):
    monkeypatch.setattr(config, "GROQ_MODEL", "modelo-falso")
    catalogo = cargar_catalogo(conn)
    solicitud = obtener_solicitud(conn, 1)
    return catalogo, solicitud


@pytest.mark.parametrize(
    "texto",
    [
        "Tengo S/. 1500",
        "Tengo S/.1,500",
        "Tengo 1,500 soles",
        "Tengo 1.500 soles",
        "tengo 1500 para reponer",
    ],
)
def test_presupuesto_reconoce_formatos_y_confirma_mismo_monto(
    catalogo_solicitud, texto
):
    catalogo, _ = catalogo_solicitud
    resultado = interpretar_solicitud(
        texto,
        catalogo,
        cliente=ClienteFalso([_respuesta_solicitud()]),
    )
    assert resultado.solicitud["presupuesto"] == 1500.0
    assert resultado.faltantes == []


def test_presupuesto_devuelto_no_presente_en_texto_es_faltante(catalogo_solicitud):
    catalogo, _ = catalogo_solicitud
    resultado = interpretar_solicitud(
        "Tengo 1400 soles para reponer",
        catalogo,
        cliente=ClienteFalso([_respuesta_solicitud(presupuesto=1500)]),
    )
    assert resultado.solicitud["presupuesto"] is None
    assert resultado.faltantes == ["presupuesto"]


@pytest.mark.parametrize("monto", [0, -1500])
def test_presupuesto_cero_o_negativo_sigue_siendo_faltante(
    catalogo_solicitud, monto
):
    catalogo, _ = catalogo_solicitud
    resultado = interpretar_solicitud(
        f"Tengo S/ {abs(monto) or 1500}",
        catalogo,
        cliente=ClienteFalso([_respuesta_solicitud(presupuesto=monto)]),
    )
    assert resultado.solicitud["presupuesto"] is None
    assert resultado.faltantes == ["presupuesto"]


def test_parsea_prefijo_s_punto_y_separador_de_miles():
    assert _parsear_presupuesto("S/. 1,500") == 1500.0
    assert _parsear_presupuesto("S/. 1500") == 1500.0


def test_presupuesto_escrito_en_palabras_sigue_reconociendose(catalogo_solicitud):
    catalogo, _ = catalogo_solicitud
    resultado = interpretar_solicitud(
        "Tengo mil quinientos soles para reponer",
        catalogo,
        cliente=ClienteFalso([_respuesta_solicitud()]),
    )
    assert resultado.solicitud["presupuesto"] == 1500.0
    assert resultado.faltantes == []


@pytest.mark.parametrize(
    ("termino", "canonico"),
    [
        ("leche", "Leche Gloria 1L"),
        ("huevos", "Huevos (docena)"),
        ("papas", "Papas Lay's"),
        ("queso", "Queso fresco"),
    ],
)
def test_coincidencia_parcial_de_productos(catalogo_solicitud, termino, canonico):
    catalogo, _ = catalogo_solicitud
    resultado = interpretar_solicitud(
        "Tengo S/ 1500",
        catalogo,
        cliente=ClienteFalso(
            [_respuesta_solicitud(incluir_forzado=[termino])]
        ),
    )
    assert resultado.solicitud["incluir_forzado"] == [canonico]
    assert resultado.no_reconocidos == []


def test_producto_parcial_ambiguo_pide_aclaracion(catalogo_solicitud):
    catalogo, _ = catalogo_solicitud
    segunda_leche = dict(catalogo[1])
    segunda_leche["id_producto"] = 16
    segunda_leche["nombre"] = "Leche sin lactosa"
    catalogo_ambiguo = [*catalogo, segunda_leche]
    resultado = interpretar_solicitud(
        "Tengo S/1500 e incluye leche",
        catalogo_ambiguo,
        cliente=ClienteFalso(
            [_respuesta_solicitud(incluir_forzado=["leche"])]
        ),
    )
    assert resultado.solicitud["incluir_forzado"] == []
    assert resultado.pregunta_aclaracion
    assert "Leche Gloria 1L" in resultado.pregunta_aclaracion
    assert "Leche sin lactosa" in resultado.pregunta_aclaracion


@pytest.mark.parametrize(
    "campos",
    [
        {"incluir_forzado": ["pizza congelada"]},
        {"no_catalogo": ["pizza congelada"]},
    ],
)
def test_pizza_no_se_descarta_sin_aviso(catalogo_solicitud, campos):
    catalogo, _ = catalogo_solicitud
    resultado = interpretar_solicitud(
        "Incluye pizza congelada, tengo 1500 soles",
        catalogo,
        cliente=ClienteFalso([_respuesta_solicitud(**campos)]),
    )
    assert resultado.solicitud["incluir_forzado"] == []
    assert "pizza congelada" in resultado.no_reconocidos
    assert resultado.pregunta_aclaracion


def test_no_catalogo_descarta_valores_que_no_sean_texto(catalogo_solicitud):
    catalogo, _ = catalogo_solicitud
    resultado = interpretar_solicitud(
        "Tengo 1500 soles",
        catalogo,
        cliente=ClienteFalso(
            [_respuesta_solicitud(no_catalogo=["pizza", 42, None, "  "])]
        ),
    )
    assert resultado.no_reconocidos == ["pizza"]


def test_prompt_pide_copiar_nombres_y_reportar_no_catalogo(catalogo_solicitud):
    catalogo, _ = catalogo_solicitud
    cliente = ClienteFalso(
        [_respuesta_solicitud(incluir_forzado=["pizza congelada"])]
    )
    interpretar_solicitud(
        "Incluye pizza congelada, tengo 1500 soles",
        catalogo,
        cliente=cliente,
    )
    prompt = cliente.llamadas[0]["messages"][0]["content"].casefold()
    assert "copia" in prompt
    assert "no_catalogo" in prompt
    assert "no los omitas" in prompt


def _datos_explicacion(catalogo_solicitud):
    catalogo, solicitud = catalogo_solicitud
    cromosoma = [26, 16, 26, 26, 26, 16, 21, 26, 7, 21, 21, 16, 26, 26, 26]
    resultado = ResultadoGenetico(
        cromosoma, 1499.70, 1293.07, [1293.07]
    )
    return catalogo, solicitud, resultado


def test_demanda_incorrecta_para_lista_mixta_se_rechaza_y_usa_respaldo(
    catalogo_solicitud
):
    catalogo, solicitud, resultado = _datos_explicacion(catalogo_solicitud)
    respuesta_erronea = (
        "Arroz, Aceite, Fideos, Atún, Azúcar y Gaseosa Coca-Cola 1.5L "
        "todas con demanda alta."
    )
    cliente = ClienteFalso([respuesta_erronea, respuesta_erronea])

    explicacion = redactar_explicacion(
        solicitud, resultado, catalogo, cliente=cliente
    )

    assert explicacion.usada_ia is False
    assert len(cliente.llamadas) == 2
    assert "Arroz" in explicacion.texto


def test_oracion_con_productos_de_la_misma_demanda_es_aceptada(
    catalogo_solicitud
):
    catalogo, solicitud, resultado = _datos_explicacion(catalogo_solicitud)
    respuesta = (
        "Arroz y Galletas Oreo tienen demanda alta. "
        "El costo total es S/ 1,499.70 frente al presupuesto S/ 1,500.00."
    )
    explicacion = redactar_explicacion(
        solicitud, resultado, catalogo, cliente=ClienteFalso([respuesta])
    )
    assert explicacion.usada_ia is True


def test_oracion_con_dos_etiquetas_no_activa_regla_de_consistencia(
    catalogo_solicitud
):
    catalogo, solicitud, resultado = _datos_explicacion(catalogo_solicitud)
    respuesta = (
        "Arroz tiene demanda media y Aceite tiene demanda alta. "
        "El costo total es S/ 1,499.70 frente al presupuesto S/ 1,500.00."
    )
    explicacion = redactar_explicacion(
        solicitud, resultado, catalogo, cliente=ClienteFalso([respuesta])
    )
    assert explicacion.usada_ia is True
