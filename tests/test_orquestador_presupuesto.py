from app.modules.genetico import PresupuestoInviableError
from app.modules.ia import InterpretacionSolicitud
import app.orquestador as orquestador


def test_presupuesto_inviable_devuelve_aclaracion_y_revierte(
    conn, monkeypatch
):
    conteo_inicial = conn.execute("SELECT COUNT(*) FROM SOLICITUD").fetchone()[0]
    monkeypatch.setattr(
        orquestador,
        "interpretar_solicitud",
        lambda *args, **kwargs: InterpretacionSolicitud(
            {
                "presupuesto": 3.0,
                "categorias_prioritarias": [],
                "incluir_forzado": ["Arroz", "Aceite"],
                "excluir": [],
            },
            [],
            None,
            [],
        ),
    )

    def genético_inviable(*args, **kwargs):
        raise PresupuestoInviableError("detalle interno")

    monkeypatch.setattr(
        orquestador, "ejecutar_algoritmo_genetico", genético_inviable
    )
    conn.execute("BEGIN")
    resultado = orquestador.procesar_mensajes(
        conn,
        ["Tengo S/ 3, incluye Arroz y Aceite"],
        cliente=object(),
    )

    assert resultado.tipo == "aclaracion"
    assert "Aumenta el presupuesto" in resultado.mensaje
    assert conn.execute("SELECT COUNT(*) FROM SOLICITUD").fetchone()[0] == conteo_inicial
    assert conn.execute("SELECT COUNT(*) FROM RECOMENDACION").fetchone()[0] == 0
    assert not conn.in_transaction
