import importlib

import pytest

import config


def test_clave_ausente_es_none_y_exigir_lanza_error(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    configuracion = importlib.reload(config)

    assert configuracion.GROQ_API_KEY is None
    with pytest.raises(RuntimeError, match="Falta configurar GROQ_API_KEY"):
        configuracion.exigir_clave_groq()


def test_clave_de_entorno_se_lee_y_se_devuelve(monkeypatch):
    clave_falsa = "clave_falsa_de_prueba"
    monkeypatch.setenv("GROQ_API_KEY", clave_falsa)
    configuracion = importlib.reload(config)

    assert configuracion.GROQ_API_KEY == clave_falsa
    assert configuracion.exigir_clave_groq() == clave_falsa


def test_error_de_clave_ausente_no_revela_valores(monkeypatch):
    clave_falsa = "no_debe_aparecer_en_el_error"
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    configuracion = importlib.reload(config)

    with pytest.raises(RuntimeError) as error:
        configuracion.exigir_clave_groq()

    assert clave_falsa not in str(error.value)
    assert "GROQ_API_KEY" in str(error.value)


def test_importar_config_sin_archivo_env_no_falla(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    configuracion = importlib.reload(config)

    assert configuracion.GROQ_API_KEY is None
