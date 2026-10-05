from pathlib import Path
import re

from app import create_app


def _app(tmp_path):
    return create_app(
        {
            "SECRET_KEY": "clave-de-prueba-de-interfaz",
            "DB_PATH": tmp_path / "interfaz.sqlite",
            "TESTING": True,
        }
    )


def test_pagina_principal_incluye_elementos_clave(tmp_path):
    respuesta = _app(tmp_path).test_client().get("/")

    assert respuesta.status_code == 200
    html = respuesta.get_data(as_text=True)
    for identificador in (
        "message-input",
        "send-button",
        "catalog-products",
        "recommendation-products",
    ):
        assert f'id="{identificador}"' in html


def test_recursos_estaticos_se_sirven(tmp_path):
    cliente = _app(tmp_path).test_client()

    assert cliente.get("/static/css/style.css").status_code == 200
    assert cliente.get("/static/js/app.js").status_code == 200


def test_javascript_no_usa_insercion_html_dinamica(tmp_path):
    respuesta = _app(tmp_path).test_client().get("/static/js/app.js")
    javascript = respuesta.get_data(as_text=True)

    assert respuesta.status_code == 200
    assert "innerHTML" not in javascript
    assert "eval(" not in javascript
    assert "document.write" not in javascript


def test_bloque_entendido_muestra_prioridades_de_producto(tmp_path):
    respuesta = _app(tmp_path).test_client().get("/static/js/app.js")
    javascript = respuesta.get_data(as_text=True)

    assert respuesta.status_code == 200
    assert "understood.prioridad_productos" in javascript
    assert "understood.obligatorios" in javascript
    assert "(prioridad)" in javascript
    assert "(sí o sí)" in javascript


def test_interfaz_no_carga_recursos_externos(tmp_path):
    cliente = _app(tmp_path).test_client()
    html = cliente.get("/").get_data(as_text=True)
    javascript = cliente.get("/static/js/app.js").get_data(as_text=True)
    referencias_html = re.findall(r"""(?:src|href)\s*=\s*["']([^"']+)["']""", html, re.I)

    assert not any(url.startswith(("http://", "https://")) for url in referencias_html)
    assert "http://" not in javascript
    assert "https://" not in javascript
