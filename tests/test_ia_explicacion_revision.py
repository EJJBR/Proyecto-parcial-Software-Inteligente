import json
from dataclasses import replace
from types import SimpleNamespace

import pytest

import config
from app.db.catalogo_repo import cargar_catalogo
from app.db.solicitud_repo import obtener_solicitud
from app.modules.genetico import ResultadoGenetico
from app.modules.ia import redactar_explicacion


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


@pytest.fixture
def datos_reales(conn):
    catalogo = cargar_catalogo(conn)
    solicitud = obtener_solicitud(conn, 1)
    cromosoma = [26, 16, 26, 26, 26, 16, 21, 26, 7, 21, 21, 16, 26, 26, 26]
    resultado = ResultadoGenetico(cromosoma, 1499.70, 1293.07, [1293.07])
    return solicitud, resultado, catalogo


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


def _respuesta_valida_sin_detergente():
    return (
        "Se recomienda reponer arroz, leche, aceite, fideos, atún, pan, yogurt, "
        "gaseosa, galletas, huevos, queso, azúcar, papas e Inca Kola. "
        "El costo total es S/ 1,454.20 frente al presupuesto de S/ 1,500.00, "
        "con un sobrante de S/ 45.80. Las categorías de abarrotes y lácteos reciben "
        "prioridad según la solicitud. Los artículos más perecibles se manejan con "
        "cantidades cuidadas por su duración. El presupuesto no fue el factor que "
        "limitó la compra y algunos productos quedaron por debajo de su límite."
    )


def _datos_enviados(cliente):
    return json.loads(cliente.llamadas[0]["messages"][1]["content"])


def _sin_producto(resultado, catalogo, nombre):
    indice = next(
        indice
        for indice, producto in enumerate(catalogo)
        if producto["nombre"] == nombre
    )
    cromosoma = resultado.mejor_cromosoma[:]
    cromosoma[indice] = 0
    return replace(resultado, mejor_cromosoma=cromosoma)


def test_calcula_etiquetas_y_datos_de_tope_y_presupuesto(datos_reales, monkeypatch):
    solicitud, resultado, catalogo = datos_reales
    monkeypatch.setattr(config, "GROQ_MODEL", "modelo-falso")
    cliente = ClienteFalso([_respuesta_valida()])
    redactar_explicacion(solicitud, resultado, catalogo, cliente=cliente)
    datos = _datos_enviados(cliente)
    articulos = {articulo["nombre"]: articulo for articulo in datos["articulos_recomendados"]}

    assert articulos["Arroz"]["demanda"] == "alta"
    assert articulos["Inca Kola 1.5L"]["demanda"] == "media"
    assert articulos["Galletas Oreo"]["demanda"] == "alta"
    assert articulos["Atún"]["demanda"] == "media"
    assert articulos["Azúcar"]["demanda"] == "baja"
    assert articulos["Detergente"]["demanda"] == "baja"
    assert articulos["Papas Lay's"]["vida_util"] == "larga duración (20 días)"
    assert articulos["Leche Gloria 1L"]["vida_util"] == "muy perecible (3 días)"
    assert articulos["Detergente"]["llego_al_limite"] is False
    assert articulos["Detergente"]["unidades"] == 7
    assert articulos["Detergente"]["limite_en_unidades"] == 26
    assert datos["presupuesto_limito_la_compra"] is True
    assert datos["balance"] == {"tipo": "sobrante", "monto": "S/ 0.30"}
    assert datos["costo_total"] == "S/ 1,499.70"
    assert datos["presupuesto"] == "S/ 1,500.00"


def test_prompt_solo_contiene_hechos_etiquetados(datos_reales, monkeypatch):
    solicitud, resultado, catalogo = datos_reales
    monkeypatch.setattr(config, "GROQ_MODEL", "modelo-falso")
    cliente = ClienteFalso([_respuesta_valida()])
    redactar_explicacion(solicitud, resultado, catalogo, cliente=cliente)
    prompt = cliente.llamadas[0]["messages"][1]["content"]

    assert "alta" in prompt and "media" in prompt and "baja" in prompt
    assert "muy perecible (3 días)" in prompt
    assert "larga duración (20 días)" in prompt
    def contains_float(value):
        if isinstance(value, dict):
            return any(contains_float(item) for item in value.values())
        if isinstance(value, list):
            return any(contains_float(item) for item in value)
        return isinstance(value, float)

    assert not contains_float(json.loads(prompt))
    for texto_interno in ("score", "fitness", "cromosoma", "cantidad_maxima"):
        assert texto_interno not in prompt.casefold()


@pytest.mark.parametrize(
    ("respuesta_invalida", "producto_no_comprado"),
    [
        ("Se recomienda comprar todos los artículos. El costo total es $1,499.70.", None),
        ("# Recomendación\nCompra de arroz.", None),
        ("El score de fitness del cromosoma usa cantidad_maxima.", None),
        ("También se recomienda comprar Gaseosa Coca-Cola 1.5L.", "Gaseosa Coca-Cola 1.5L"),
    ],
)
def test_respuesta_invalida_persistente_usa_respaldo(
    datos_reales, monkeypatch, respuesta_invalida, producto_no_comprado
):
    solicitud, resultado, catalogo = datos_reales
    if producto_no_comprado:
        resultado = _sin_producto(resultado, catalogo, producto_no_comprado)
    monkeypatch.setattr(config, "GROQ_MODEL", "modelo-falso")
    cliente = ClienteFalso([respuesta_invalida, respuesta_invalida])

    explicacion = redactar_explicacion(
        solicitud, resultado, catalogo, cliente=cliente
    )

    assert explicacion.usada_ia is False
    assert len(cliente.llamadas) == 2
    assert "$" not in explicacion.texto
    assert "score" not in explicacion.texto.casefold()
    assert "fitness" not in explicacion.texto.casefold()
    assert "cantidad_maxima" not in explicacion.texto.casefold()


@pytest.mark.parametrize(
    ("respuesta_invalida", "producto_no_comprado"),
    [
        ("Compra sugerida por demanda. El costo total es $1,499.70.", None),
        ("# Recomendación\nSe propone una compra.", None),
        ("El score calculado es favorable.", None),
        ("También se compró Detergente.", "Detergente"),
    ],
)
def test_respuesta_invalida_se_reintenta_con_aviso(
    datos_reales, monkeypatch, respuesta_invalida, producto_no_comprado
):
    solicitud, resultado, catalogo = datos_reales
    if producto_no_comprado:
        resultado = _sin_producto(resultado, catalogo, producto_no_comprado)
    monkeypatch.setattr(config, "GROQ_MODEL", "modelo-falso")
    respuesta_reintento = (
        _respuesta_valida_sin_detergente()
        if producto_no_comprado == "Detergente"
        else _respuesta_valida()
    )
    cliente = ClienteFalso([respuesta_invalida, respuesta_reintento])

    explicacion = redactar_explicacion(
        solicitud, resultado, catalogo, cliente=cliente
    )

    assert explicacion.usada_ia is True
    assert len(cliente.llamadas) == 2
    assert "Corrige además" in cliente.llamadas[1]["messages"][0]["content"]


def test_respuesta_valida_se_acepta(datos_reales, monkeypatch):
    solicitud, resultado, catalogo = datos_reales
    monkeypatch.setattr(config, "GROQ_MODEL", "modelo-falso")
    cliente = ClienteFalso([_respuesta_valida()])

    explicacion = redactar_explicacion(
        solicitud, resultado, catalogo, cliente=cliente
    )

    assert explicacion.usada_ia is True
    assert explicacion.texto == _respuesta_valida()


def test_respaldo_usa_dinero_soles_correcto_y_sin_terminos_internos(
    datos_reales, monkeypatch
):
    solicitud, resultado, catalogo = datos_reales
    monkeypatch.setattr(config, "GROQ_MODEL", "modelo-falso")
    cliente = ClienteFalso(["# inválido", "# inválido"])

    explicacion = redactar_explicacion(
        solicitud, resultado, catalogo, cliente=cliente
    )

    assert explicacion.usada_ia is False
    assert "S/ 1,499.70" in explicacion.texto
    assert "S/ 1,500.00" in explicacion.texto
    assert "S/ 0.30" in explicacion.texto
    assert "presupuesto fue el factor que limitó la compra" in explicacion.texto
    assert "$" not in explicacion.texto
    for termino in ("score", "fitness", "cromosoma", "cantidad_maxima"):
        assert termino not in explicacion.texto.casefold()
