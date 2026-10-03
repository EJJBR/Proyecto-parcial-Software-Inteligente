import importlib
import sys
from types import ModuleType

import pytest

import config


@pytest.fixture
def config_without_dotenv(monkeypatch):
    dotenv_stub = ModuleType("dotenv")
    dotenv_stub.load_dotenv = lambda *args, **kwargs: None
    monkeypatch.setitem(sys.modules, "dotenv", dotenv_stub)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    configuracion = importlib.reload(config)
    yield configuracion
    monkeypatch.undo()
    importlib.reload(config)


def test_clave_ausente_es_none_y_exigir_lanza_error(config_without_dotenv):
    configuracion = config_without_dotenv

    assert configuracion.GROQ_API_KEY is None, "La clave debe quedar ausente."
    with pytest.raises(RuntimeError, match="Falta configurar GROQ_API_KEY"):
        configuracion.exigir_clave_groq()


def test_clave_de_entorno_se_lee_y_se_devuelve(monkeypatch):
    clave_falsa = "clave_falsa_de_prueba"
    monkeypatch.setenv("GROQ_API_KEY", clave_falsa)
    configuracion = importlib.reload(config)

    assert configuracion.GROQ_API_KEY == clave_falsa, "No se leyó la clave falsa esperada."
    assert configuracion.exigir_clave_groq() == clave_falsa, "No se devolvió la clave falsa esperada."


def test_error_de_clave_ausente_no_revela_valores(config_without_dotenv):
    configuracion = config_without_dotenv

    with pytest.raises(RuntimeError) as error:
        configuracion.exigir_clave_groq()

    assert "GROQ_API_KEY" in str(error.value), "El mensaje debe identificar la configuración faltante."


def test_importar_config_sin_archivo_env_no_falla(config_without_dotenv):
    configuracion = config_without_dotenv

    assert configuracion.GROQ_API_KEY is None, "La clave debe quedar ausente."
