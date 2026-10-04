"""Rutas JSON y página marcador para la aplicación de compras."""
from contextlib import contextmanager
from pathlib import Path
import threading
from typing import Any, Iterator

from flask import (
    Blueprint,
    abort,
    current_app,
    jsonify,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.exceptions import HTTPException

import config
from app.db.catalogo_repo import cargar_catalogo, listar_categorias
from app.db.conexion import abrir_conexion
from app.db.recomendacion_repo import obtener_recomendacion
from app.db.solicitud_repo import obtener_solicitud
from app.orquestador import procesar_mensajes


bp = Blueprint("principal", __name__)
_CLAVE_MENSAJES = "mensajes_usuario"
_MAX_MENSAJES = 5
_MAX_CARACTERES_SESION = 1800
_MAX_COOKIE_BYTES = 3800
_LOCK_CONFIG_GENETICO = threading.RLock()
_PARAMETROS_GENETICOS = (
    "TAMANO_POBLACION",
    "GENERACIONES",
    "TAMANO_TORNEO",
    "TASA_CROSSOVER",
    "TASA_MUTACION",
    "ELITISMO",
)


def _url_imagen(id_producto: int) -> str | None:
    carpeta_static = current_app.static_folder
    if not carpeta_static:
        return None
    ruta = Path(carpeta_static) / "img" / "productos" / f"{id_producto}.png"
    if not ruta.is_file():
        return None
    return url_for("static", filename=f"img/productos/{id_producto}.png")


def _abrir_conexion():
    return abrir_conexion(current_app.config["DB_PATH"])


def _medir_cookie_sesion() -> int:
    serializer = current_app.session_interface.get_signing_serializer(current_app)
    if serializer is None:
        return _MAX_COOKIE_BYTES + 1
    valor = serializer.dumps(dict(session))
    atributos = "; HttpOnly; Path=/; SameSite=Lax"
    if current_app.config.get("SESSION_COOKIE_SECURE"):
        atributos += "; Secure"
    return len(
        f"{current_app.config['SESSION_COOKIE_NAME']}={valor}{atributos}".encode(
            "utf-8"
        )
    )


def _guardar_mensajes(mensajes: list[str]) -> None:
    recientes = mensajes[-_MAX_MENSAJES:]
    while recientes and sum(len(mensaje) for mensaje in recientes) > _MAX_CARACTERES_SESION:
        recientes.pop(0)
    session[_CLAVE_MENSAJES] = recientes
    while recientes and _medir_cookie_sesion() > _MAX_COOKIE_BYTES:
        recientes.pop(0)
        session[_CLAVE_MENSAJES] = recientes


@contextmanager
def _parametros_geneticos_de_app() -> Iterator[None]:
    overrides = {
        nombre: current_app.config[nombre]
        for nombre in _PARAMETROS_GENETICOS
        if nombre in current_app.config
    }
    if not overrides:
        yield
        return
    with _LOCK_CONFIG_GENETICO:
        anteriores = {nombre: getattr(config, nombre) for nombre in overrides}
        try:
            for nombre, valor in overrides.items():
                setattr(config, nombre, valor)
            yield
        finally:
            for nombre, valor in anteriores.items():
                setattr(config, nombre, valor)


def _http_para_error(codigo_error: str | None) -> int:
    return {
        "limite_velocidad": 429,
        "ia_no_disponible": 503,
        "entrada_invalida": 400,
        "interno": 500,
    }.get(codigo_error, 500)


def _producto_recomendado(
    producto: dict[str, Any],
    por_id: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    producto_catalogo = por_id[producto["id_producto"]]
    precio_unitario = float(producto_catalogo["precio_compra"])
    cantidad = int(producto["cantidad"])
    return {
        "id_producto": int(producto["id_producto"]),
        "nombre": str(producto["nombre"]),
        "cantidad": cantidad,
        "precio_unitario": precio_unitario,
        "subtotal": precio_unitario * cantidad,
        "imagen": _url_imagen(int(producto["id_producto"])),
    }


@bp.get("/")
def inicio():
    return render_template("index.html")


@bp.post("/api/solicitud")
def solicitud():
    limite_contenido = current_app.config.get("MAX_CONTENT_LENGTH")
    if (
        limite_contenido is not None
        and request.content_length is not None
        and request.content_length > limite_contenido
    ):
        abort(413)
    if not request.is_json:
        return jsonify(tipo="error", mensaje="La solicitud debe enviarse como JSON."), 400
    try:
        datos = request.get_json()
    except (HTTPException, ValueError):
        datos = None
    if not isinstance(datos, dict) or not isinstance(datos.get("mensaje"), str):
        return jsonify(
            tipo="error",
            mensaje="El cuerpo debe incluir un mensaje de texto en formato JSON.",
        ), 400

    mensaje = datos["mensaje"].strip()
    if not mensaje:
        return jsonify(tipo="error", mensaje="El mensaje no puede estar vacío."), 400
    if len(mensaje) > 500:
        return jsonify(
            tipo="error",
            mensaje="El mensaje no puede superar los 500 caracteres.",
        ), 400

    mensajes_previos = session.get(_CLAVE_MENSAJES, [])
    if not isinstance(mensajes_previos, list) or any(
        not isinstance(item, str) for item in mensajes_previos
    ):
        mensajes_previos = []
    mensajes = [*mensajes_previos, mensaje][-_MAX_MENSAJES:]

    conn = None
    try:
        conn = _abrir_conexion()
        with _parametros_geneticos_de_app():
            resultado = procesar_mensajes(
                conn,
                mensajes,
                cliente=current_app.config.get("CLIENTE_IA"),
                semilla=current_app.config.get("SEMILLA"),
            )
        if resultado.tipo == "aclaracion":
            _guardar_mensajes(mensajes)
            return jsonify(tipo="aclaracion", pregunta=resultado.mensaje), 200
        if resultado.tipo == "error":
            return (
                jsonify(tipo="error", mensaje=resultado.mensaje),
                _http_para_error(resultado.codigo_error),
            )

        session.pop(_CLAVE_MENSAJES, None)
        catalogo = cargar_catalogo(conn)
        productos_catalogo = {
            int(producto["id_producto"]): producto for producto in catalogo
        }
        productos = [
            _producto_recomendado(producto, productos_catalogo)
            for producto in (resultado.productos or [])
            if int(producto["cantidad"]) > 0
        ]
        return jsonify(
            tipo="recomendacion",
            productos=productos,
            costo_total=resultado.costo_total,
            presupuesto=resultado.presupuesto,
            fitness=resultado.fitness,
            explicacion=resultado.explicacion,
            usada_ia=resultado.usada_ia,
            motivo_respaldo=resultado.motivo_respaldo,
            id_solicitud=resultado.id_solicitud,
            id_recomendacion=resultado.id_recomendacion,
            entendido=resultado.entendido,
        ), 200
    finally:
        if conn is not None:
            conn.close()


@bp.post("/api/reiniciar")
def reiniciar():
    session.pop(_CLAVE_MENSAJES, None)
    return jsonify(tipo="ok", mensaje="La conversación se reinició."), 200


@bp.get("/api/catalogo")
def catalogo():
    conn = None
    try:
        conn = _abrir_conexion()
        productos = [
            {
                "id_producto": int(producto["id_producto"]),
                "nombre": str(producto["nombre"]),
                "categoria": str(producto["categoria"]),
                "precio_venta": float(producto["precio_venta"]),
                "precio_compra": float(producto["precio_compra"]),
                "imagen": _url_imagen(int(producto["id_producto"])),
            }
            for producto in cargar_catalogo(conn)
        ]
        categorias = listar_categorias(conn)
        return jsonify(productos=productos, categorias=categorias), 200
    finally:
        if conn is not None:
            conn.close()


@bp.get("/api/recomendaciones/<int:id_solicitud>")
def recomendacion(id_solicitud: int):
    conn = None
    try:
        conn = _abrir_conexion()
        solicitud_guardada = obtener_solicitud(conn, id_solicitud)
        recomendacion_guardada = obtener_recomendacion(conn, id_solicitud)
        if solicitud_guardada is None or recomendacion_guardada is None:
            abort(404)
        return jsonify(
            tipo="recomendacion",
            solicitud=solicitud_guardada,
            recomendacion=recomendacion_guardada,
        ), 200
    finally:
        if conn is not None:
            conn.close()


@bp.app_errorhandler(HTTPException)
def manejar_error_http(error: HTTPException):
    mensajes = {
        400: "La solicitud no es válida.",
        404: "No se encontró el recurso solicitado.",
        405: "El método no está permitido para esta ruta.",
        413: "La solicitud supera el tamaño máximo permitido.",
    }
    return jsonify(
        tipo="error",
        mensaje=mensajes.get(error.code, "No se pudo procesar la solicitud."),
    ), error.code


@bp.app_errorhandler(Exception)
def manejar_error_interno(error: Exception):
    return jsonify(
        tipo="error",
        mensaje="Ocurrió un error interno. Inténtalo nuevamente más tarde.",
    ), 500
