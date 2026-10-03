"""Prueba aislada del diagnóstico optativo, usando una respuesta falsa."""
from types import SimpleNamespace

import pytest

import config
from app.modules.ia import ErrorIA
from app.modules.ia.cliente import _solicitar_completado


class ClienteFalsoRespuestaVacia:
    chat = SimpleNamespace(
        completions=SimpleNamespace(
            create=lambda **kwargs: SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        finish_reason="stop",
                        message=SimpleNamespace(
                            content=None,
                            model_fields_set={"content", "role"},
                        ),
                    )
                ],
                usage=SimpleNamespace(
                    prompt_tokens=12,
                    completion_tokens=0,
                    total_tokens=12,
                ),
            )
        )
    )


def test_debug_apagado_no_imprime_diagnostico(monkeypatch, capsys):
    monkeypatch.delenv("GROQ_DEBUG", raising=False)
    monkeypatch.setattr(config, "GROQ_MODEL", "modelo-falso")

    with pytest.raises(ErrorIA, match="respuesta vacía"):
        _solicitar_completado(
            ClienteFalsoRespuestaVacia(),
            [{"role": "user", "content": "texto ficticio"}],
            temperatura=0.1,
            max_tokens=10,
        )

    assert capsys.readouterr().out == ""
