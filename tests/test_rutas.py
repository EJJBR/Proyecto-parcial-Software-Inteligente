import json
import sqlite3
from types import SimpleNamespace

import pytest

import config
from app import create_app
from app.db.inicializar import crear_base
from app.modules.ia.cliente import ErrorLimiteVelocidad


class RateLimitFalso(Exception):
    status_code = 429

    def __init__(self):
        super().__init__("detalle privado")
        self.response = SimpleNamespace(status_code=429, headers={})


class ClienteFalso:
    def __init__(self, respuestas=()):
        self.respuestas = list(respuestas)
        self.llamadas = []

    @property
    def chat(self):
        return SimpleNamespace(
            completions=SimpleNamespace(create=self.create)
        )

    def create(self, **kwargs):
        self.llamadas.append(kwargs)
        if not self.respuestas:
            respuesta = json.dumps(
                {
                    "presupuesto": 1500,
                    "categorias_prioritarias": ["abarrotes"],
                    "incluir_forzado": ["Arroz"],
                    "excluir": [],
                }
            )
        else:
            respuesta = self.respuestas.pop(0)
        if isinstance(respuesta, Exception):
            raise respuesta
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=respuesta))]
        )


class ClienteAclaraciones(ClienteFalso):
    def create(self, **kwargs):
        self.llamadas.append(kwargs)
        contenido = json.loads(kwargs["messages"][1]["content"])
        self.respuestas.append(
            json.dumps(
                {
                    "presupuesto": 1500,
                    "categorias_prioritarias": [],
                    "incluir_forzado": [],
                    "excluir": [],
                    "no_catalogo": ["producto no catalogado"],
                }
            )
        )
        return super().create(**kwargs)


def _respuesta_interpretacion(**campos):
    datos = {
        "presupuesto": 1500,
        "categorias_prioritarias": ["abarrotes"],
        "incluir_forzado": ["Arroz"],
        "excluir": [],
    }
    datos.update(campos)
    return json.dumps(datos, ensure_ascii=False)


def _recomendacion_cliente(respuestas_explicacion=()):
    return ClienteFalso(
        [_respuesta_interpretacion(), *respuestas_explicacion]
    )


@pytest.fixture
def entorno(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "GROQ_MODEL", "modelo-falso")
    db_path = tmp_path / "bodega.sqlite"
    conn = sqlite3.connect(str(db_path))
    crear_base(conn)
    conn.close()
    static_path = tmp_path / "static"
    static_path.mkdir()
    app = create_app(
        {
            "SECRET_KEY": "secreto-de-prueba-no-es-real",
            "DB_PATH": db_path,
            "STATIC_FOLDER": static_path,
            "TAMANO_POBLACION": 8,
            "GENERACIONES": 3,
            "TAMANO_TORNEO": 3,
            "cliente_ia": ClienteFalso(),
            "semilla": 42,
            "TESTING": True,
        }
    )
    return app, app.test_client(), db_path, static_path


def _conteos(db_path):
    conn = sqlite3.connect(str(db_path))
    try:
        return (
            conn.execute("SELECT COUNT(*) FROM SOLICITUD").fetchone()[0],
            conn.execute("SELECT COUNT(*) FROM RECOMENDACION").fetchone()[0],
        )
    finally:
        conn.close()


def test_solicitud_completa_devuelve_costos_y_limpia_sesion(entorno):
    _, cliente_http, db_path, _ = entorno
    app = cliente_http.application
    app.config["CLIENTE_IA"] = _recomendacion_cliente(
        ["Arroz es una buena opción para reponer."]
    )
    conteos_iniciales = _conteos(db_path)

    respuesta = cliente_http.post(
        "/api/solicitud",
        json={"mensaje": "Tengo S/ 1500, incluye arroz"},
    )

    datos = respuesta.get_json()
    assert respuesta.status_code == 200
    assert datos["tipo"] == "recomendacion"
    assert datos["productos"]
    assert all(
        {"precio_unitario", "subtotal", "imagen"} <= producto.keys()
        for producto in datos["productos"]
    )
    assert sum(producto["subtotal"] for producto in datos["productos"]) == pytest.approx(
        datos["costo_total"], abs=1e-9
    )
    assert datos["id_solicitud"] is not None
    with cliente_http.session_transaction() as sesion:
        assert sesion.get("mensajes_usuario") is None
    assert _conteos(db_path) == (conteos_iniciales[0] + 1, conteos_iniciales[1] + 1)


def test_aclaracion_y_segundo_mensaje_reinterpreta_historial(entorno):
    _, cliente_http, _, _ = entorno
    cliente = ClienteFalso(
        [
            _respuesta_interpretacion(presupuesto=None),
            _respuesta_interpretacion(),
            "Arroz es una buena opción.",
        ]
    )
    cliente_http.application.config["CLIENTE_IA"] = cliente

    primero = cliente_http.post(
        "/api/solicitud", json={"mensaje": "Quiero reponer arroz"}
    )
    segundo = cliente_http.post(
        "/api/solicitud", json={"mensaje": "Tengo 1500 soles"}
    )

    assert primero.status_code == 200
    assert primero.get_json()["tipo"] == "aclaracion"
    assert segundo.status_code == 200
    assert segundo.get_json()["tipo"] == "recomendacion"
    contexto = json.loads(cliente.llamadas[1]["messages"][1]["content"])
    assert contexto["historial"] == ["Quiero reponer arroz"]


@pytest.mark.parametrize(
    ("contenido", "content_type"),
    [
        ({"mensaje": ""}, "application/json"),
        ({"mensaje": "   "}, "application/json"),
        ({"mensaje": "x" * 501}, "application/json"),
        ("{ JSON roto", "application/json"),
        ({"mensaje": 12}, "application/json"),
        ("mensaje=hola", "application/x-www-form-urlencoded"),
    ],
)
def test_entradas_invalidas_responden_400_sin_llamar_ia(
    entorno, contenido, content_type
):
    _, cliente_http, _, _ = entorno
    fake = ClienteFalso()
    cliente_http.application.config["CLIENTE_IA"] = fake
    if content_type == "application/json":
        respuesta = cliente_http.post(
            "/api/solicitud",
            data=contenido if isinstance(contenido, str) else json.dumps(contenido),
            content_type=content_type,
        )
    else:
        respuesta = cliente_http.post(
            "/api/solicitud", data=contenido, content_type=content_type
        )

    assert respuesta.status_code == 400
    assert respuesta.get_json()["tipo"] == "error"
    assert fake.llamadas == []


def test_aclaraciones_recortan_mensajes_y_cookie(entorno):
    _, cliente_http, _, _ = entorno
    cliente = ClienteAclaraciones()
    cliente_http.application.config["CLIENTE_IA"] = cliente

    mensajes = [f"mensaje-{i}" for i in range(7)]
    ultima_respuesta = None
    for mensaje in mensajes:
        ultima_respuesta = cliente_http.post(
            "/api/solicitud", json={"mensaje": mensaje}
        )
        assert ultima_respuesta.status_code == 200
        assert ultima_respuesta.get_json()["tipo"] == "aclaracion"

    contexto = json.loads(cliente.llamadas[-1]["messages"][1]["content"])
    assert contexto["texto_usuario"] == mensajes[-1]
    assert contexto["historial"] == mensajes[-5:-1]
    set_cookie = ultima_respuesta.headers["Set-Cookie"]
    assert len(set_cookie.encode("utf-8")) <= 3800


def test_cookie_se_mantiene_acotada_con_mensajes_unicode_largos(entorno):
    _, cliente_http, _, _ = entorno
    cliente_http.application.config["CLIENTE_IA"] = ClienteAclaraciones()
    for _ in range(5):
        respuesta = cliente_http.post(
            "/api/solicitud", json={"mensaje": "ñáéíóú" * 83 + "ñ"}
        )
        assert respuesta.status_code == 200
        assert len(respuesta.headers["Set-Cookie"].encode("utf-8")) <= 3800


def test_limite_velocidad_en_interpretacion_no_guarda_mensaje(entorno):
    _, cliente_http, db_path, _ = entorno
    cliente = ClienteFalso([RateLimitFalso(), RateLimitFalso(), RateLimitFalso()])
    cliente_http.application.config["CLIENTE_IA"] = cliente
    inicial = _conteos(db_path)

    respuesta = cliente_http.post(
        "/api/solicitud", json={"mensaje": "texto que falla"}
    )

    assert respuesta.status_code == 429
    assert "Hay muchas solicitudes a la IA" in respuesta.get_json()["mensaje"]
    with cliente_http.session_transaction() as sesion:
        assert sesion.get("mensajes_usuario") is None
    assert _conteos(db_path) == inicial


def test_otro_error_ia_devuelve_503_y_conserva_sesion(entorno):
    _, cliente_http, _, _ = entorno
    cliente = ClienteFalso(
        [
            _respuesta_interpretacion(presupuesto=None),
            TimeoutError("detalle privado"),
        ]
    )
    cliente_http.application.config["CLIENTE_IA"] = cliente
    cliente_http.post("/api/solicitud", json={"mensaje": "mensaje anterior"})

    respuesta = cliente_http.post(
        "/api/solicitud", json={"mensaje": "nuevo mensaje"}
    )

    assert respuesta.status_code == 503
    with cliente_http.session_transaction() as sesion:
        assert sesion["mensajes_usuario"] == ["mensaje anterior"]
    assert "detalle privado" not in respuesta.get_data(as_text=True)


def test_excepcion_interna_devuelve_500_sin_detalles(entorno, monkeypatch):
    _, cliente_http, _, _ = entorno

    def fallo_privado(*args, **kwargs):
        raise RuntimeError("CLAVE_DE_PRUEBA_NO_REVELAR traceback privado")

    monkeypatch.setattr("app.rutas.procesar_mensajes", fallo_privado)
    respuesta = cliente_http.post(
        "/api/solicitud", json={"mensaje": "Tengo 1500 soles"}
    )

    assert respuesta.status_code == 500
    cuerpo = respuesta.get_data(as_text=True)
    assert "CLAVE_DE_PRUEBA_NO_REVELAR" not in cuerpo
    assert "traceback" not in cuerpo.casefold()


def test_explicacion_con_rate_limit_guarda_respaldo_y_motivo(entorno):
    _, cliente_http, _, _ = entorno
    cliente_http.application.config["CLIENTE_IA"] = ClienteFalso(
        [
            _respuesta_interpretacion(),
            RateLimitFalso(),
            RateLimitFalso(),
            RateLimitFalso(),
        ]
    )

    respuesta = cliente_http.post(
        "/api/solicitud",
        json={"mensaje": "Tengo S/ 1500, incluye arroz"},
    )

    resultado = respuesta.get_json()
    assert respuesta.status_code == 200
    assert resultado["tipo"] == "recomendacion"
    assert resultado["usada_ia"] is False
    assert "límite de velocidad" in resultado["motivo_respaldo"].casefold()


def test_presupuesto_inviable_se_devuelve_como_aclaracion(entorno):
    _, cliente_http, _, _ = entorno
    cliente_http.application.config["CLIENTE_IA"] = ClienteFalso(
        [
            _respuesta_interpretacion(
                presupuesto=5,
                incluir_forzado=["Arroz", "Aceite"],
            )
        ]
    )

    respuesta = cliente_http.post(
        "/api/solicitud",
        json={"mensaje": "Tengo S/5, incluye arroz y aceite"},
    )

    assert respuesta.status_code == 200
    assert respuesta.get_json()["tipo"] == "aclaracion"
    assert "Aumenta el presupuesto" in respuesta.get_json()["pregunta"]


def test_reiniciar_vacia_conversacion(entorno):
    _, cliente_http, _, _ = entorno
    cliente_http.application.config["CLIENTE_IA"] = ClienteFalso(
        [_respuesta_interpretacion(presupuesto=None)]
    )
    cliente_http.post("/api/solicitud", json={"mensaje": "mensaje anterior"})

    respuesta = cliente_http.post("/api/reiniciar")

    assert respuesta.status_code == 200
    with cliente_http.session_transaction() as sesion:
        assert sesion.get("mensajes_usuario") is None


def test_catalogo_devuelve_quince_productos_y_seis_categorias(entorno):
    _, cliente_http, _, static_path = entorno
    (static_path / "img" / "productos").mkdir(parents=True)
    (static_path / "img" / "productos" / "1.png").write_bytes(b"imagen")

    respuesta = cliente_http.get("/api/catalogo")

    datos = respuesta.get_json()
    assert respuesta.status_code == 200
    assert len(datos["productos"]) == 15
    assert len(datos["categorias"]) == 6
    arroz = next(item for item in datos["productos"] if item["id_producto"] == 1)
    assert arroz["imagen"] == "/static/img/productos/1.png"
    otro = next(item for item in datos["productos"] if item["id_producto"] == 2)
    assert otro["imagen"] is None


def test_consulta_recomendacion_guardada_y_404(entorno):
    _, cliente_http, _, _ = entorno
    cliente_http.application.config["CLIENTE_IA"] = _recomendacion_cliente(
        ["Arroz recomendado."]
    )
    guardado = cliente_http.post(
        "/api/solicitud", json={"mensaje": "Tengo S/1500, incluye arroz"}
    ).get_json()

    respuesta = cliente_http.get(
        f"/api/recomendaciones/{guardado['id_solicitud']}"
    )
    inexistente = cliente_http.get("/api/recomendaciones/999999")

    assert respuesta.status_code == 200
    assert respuesta.get_json()["solicitud"]["id_solicitud"] == guardado["id_solicitud"]
    assert respuesta.get_json()["recomendacion"]["detalle"]
    assert respuesta.get_json()["recomendacion"]["detalle"][0]["nombre"]
    assert inexistente.status_code == 404
    assert "No se encontró" in inexistente.get_json()["mensaje"]


def test_respuestas_no_exponen_clave_api(entorno, monkeypatch):
    _, cliente_http, _, _ = entorno
    clave = "API_KEY_FALSA_NO_MOSTRAR"
    monkeypatch.setenv("GROQ_API_KEY", clave)
    cliente_http.application.config["CLIENTE_IA"] = ClienteFalso(
        [TimeoutError(f"fallo privado: {clave}")]
    )

    respuesta = cliente_http.post(
        "/api/solicitud", json={"mensaje": "Tengo S/1500"}
    )

    assert respuesta.status_code == 503
    assert clave not in respuesta.get_data(as_text=True)


def test_create_app_requiere_secret_sin_override(monkeypatch):
    monkeypatch.setattr(config, "FLASK_SECRET_KEY", None)

    with pytest.raises(RuntimeError, match="FLASK_SECRET_KEY"):
        create_app()


def test_create_app_permite_secret_de_override(tmp_path):
    db_path = tmp_path / "sin_db.sqlite"

    app = create_app(
        {
            "SECRET_KEY": "solo-para-pruebas",
            "DB_PATH": db_path,
            "GENERACIONES": 2,
            "TAMANO_POBLACION": 6,
        }
    )

    assert app.secret_key == "solo-para-pruebas"
    assert db_path.is_file()
    conn = sqlite3.connect(str(db_path))
    try:
        assert conn.execute("SELECT COUNT(*) FROM PRODUCTO").fetchone()[0] == 15
    finally:
        conn.close()


def test_imagen_de_producto_recomendado_se_resuelve_en_static_temporal(entorno):
    _, cliente_http, _, static_path = entorno
    (static_path / "img" / "productos").mkdir(parents=True)
    (static_path / "img" / "productos" / "1.png").write_bytes(b"imagen")
    cliente_http.application.config["CLIENTE_IA"] = _recomendacion_cliente(
        ["Arroz recomendado."]
    )

    respuesta = cliente_http.post(
        "/api/solicitud",
        json={"mensaje": "Tengo S/1500, incluye arroz"},
    )

    arroz = next(
        producto
        for producto in respuesta.get_json()["productos"]
        if producto["id_producto"] == 1
    )
    assert arroz["imagen"] == "/static/img/productos/1.png"
    assert all(
        producto["imagen"] is None
        for producto in respuesta.get_json()["productos"]
        if producto["id_producto"] != 1
    )


def test_rutas_y_manejadores_de_error_json(entorno):
    _, cliente_http, _, _ = entorno

    assert cliente_http.get("/").status_code == 200
    assert cliente_http.get("/inexistente").status_code == 404
    assert cliente_http.get("/api/reiniciar").status_code == 405
    body_too_large = cliente_http.post(
        "/api/solicitud",
        data=b"x" * (17 * 1024),
        content_type="application/json",
    )
    assert body_too_large.status_code == 413
    assert all(
        respuesta.is_json
        for respuesta in (
            cliente_http.get("/inexistente"),
            cliente_http.get("/api/reiniciar"),
            body_too_large,
        )
    )
