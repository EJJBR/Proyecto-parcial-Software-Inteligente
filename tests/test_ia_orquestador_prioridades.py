import json
from types import SimpleNamespace

import config
import app.orquestador as orquestador
from app.db.catalogo_repo import cargar_catalogo
from app.modules.genetico import PresupuestoInviableError
from app.modules.ia import interpretar_solicitud


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


def _respuesta(**campos):
    datos = {
        "presupuesto": 800,
        "categorias_prioritarias": [],
        "incluir_forzado": [],
        "excluir": [],
        "prioridad_productos": [],
        "obligatorios": [],
        "no_catalogo": [],
    }
    datos.update(campos)
    return json.dumps(datos, ensure_ascii=False)


def test_interpreta_prioridad_de_producto_y_garantiza_inclusion(conn, monkeypatch):
    monkeypatch.setattr(config, "GROQ_MODEL", "modelo_falso")
    catalogo = cargar_catalogo(conn)
    cliente = ClienteFalso(
        [_respuesta(prioridad_productos=["aceite"], incluir_forzado=[])]
    )

    resultado = interpretar_solicitud(
        "Tengo S/ 800, prioriza el aceite",
        catalogo,
        cliente=cliente,
    )

    assert resultado.solicitud["prioridad_productos"] == ["Aceite"]
    assert "Aceite" in resultado.solicitud["incluir_forzado"]
    assert resultado.no_reconocidos == []
    assert resultado.pregunta_aclaracion is None
    assert '"prioridad_productos": string[]' in cliente.llamadas[0]["messages"][0]["content"]
    assert '"obligatorios": string[]' in cliente.llamadas[0]["messages"][0]["content"]


def test_interpreta_obligatorios_con_coincidencia_parcial(conn, monkeypatch):
    monkeypatch.setattr(config, "GROQ_MODEL", "modelo_falso")
    cliente = ClienteFalso(
        [_respuesta(obligatorios=["arroz"], incluir_forzado=[])]
    )

    resultado = interpretar_solicitud(
        "Tengo S/ 800, que no falte arroz",
        cargar_catalogo(conn),
        cliente=cliente,
    )

    assert resultado.solicitud["obligatorios"] == ["Arroz"]
    assert "Arroz" in resultado.solicitud["incluir_forzado"]
    assert resultado.no_reconocidos == []
    assert resultado.pregunta_aclaracion is None


def test_orquestador_transmite_prioridad_y_obligatorios_al_genetico(
    conn, monkeypatch
):
    monkeypatch.setattr(config, "GROQ_MODEL", "modelo_falso")
    solicitudes_recibidas = []

    def capturar_solicitud(catalogo, solicitud, *, semilla=None):
        solicitudes_recibidas.append(dict(solicitud))
        raise PresupuestoInviableError("detener después de verificar el payload")

    monkeypatch.setattr(
        orquestador, "ejecutar_algoritmo_genetico", capturar_solicitud
    )
    cliente = ClienteFalso(
        [
            _respuesta(
                prioridad_productos=["Aceite"],
                obligatorios=["Arroz"],
            )
        ]
    )

    resultado = orquestador.procesar_mensajes(
        conn,
        ["Tengo S/ 800, prioriza aceite y que no falte arroz"],
        cliente=cliente,
    )

    assert resultado.tipo == "aclaracion"
    assert len(solicitudes_recibidas) == 1
    solicitud = solicitudes_recibidas[0]
    assert solicitud["prioridad_productos"] == ["Aceite"]
    assert solicitud["obligatorios"] == ["Arroz"]
    assert "Aceite" in solicitud["incluir_forzado"]
    assert "Arroz" in solicitud["incluir_forzado"]
