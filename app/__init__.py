"""Fábrica de la aplicación Flask."""
import os
from pathlib import Path
import sqlite3
from typing import Any

from flask import Flask

import config
from app.db.inicializar import crear_base


def _bool_entorno(nombre: str) -> bool:
    return os.getenv(nombre, "").strip().casefold() in {"1", "true", "yes", "on"}


def _inicializar_base_si_falta(db_path: str | Path) -> None:
    ruta = Path(db_path)
    if ruta.exists():
        return
    ruta.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(ruta))
    try:
        crear_base(conn)
    finally:
        conn.close()


def create_app(config_override: dict[str, Any] | None = None) -> Flask:
    """Crea la app, configura sesiones y prepara la base solo si aún no existe."""
    overrides = dict(config_override or {})
    secret_key = overrides.pop("SECRET_KEY", config.FLASK_SECRET_KEY)
    if not secret_key:
        raise RuntimeError(
            "Falta configurar FLASK_SECRET_KEY para proteger la sesión de la aplicación."
        )

    static_folder = overrides.pop(
        "STATIC_FOLDER", str(Path(__file__).resolve().parent / "static")
    )
    app = Flask(
        __name__,
        static_folder=static_folder,
        template_folder=str(Path(__file__).resolve().parent / "templates"),
    )
    app.config.update(
        SECRET_KEY=secret_key,
        DB_PATH=overrides.pop("DB_PATH", config.DB_PATH),
        CLIENTE_IA=overrides.pop("cliente_ia", None),
        SEMILLA=overrides.pop("semilla", None),
        MAX_CONTENT_LENGTH=16 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=_bool_entorno("SESSION_COOKIE_SECURE"),
    )

    parametros_geneticos = {
        "TAMANO_POBLACION",
        "GENERACIONES",
        "TAMANO_TORNEO",
        "TASA_CROSSOVER",
        "TASA_MUTACION",
        "ELITISMO",
    }
    for nombre in parametros_geneticos:
        if nombre in overrides:
            app.config[nombre] = overrides.pop(nombre)
    if "SESSION_COOKIE_SECURE" in overrides:
        app.config["SESSION_COOKIE_SECURE"] = bool(
            overrides.pop("SESSION_COOKIE_SECURE")
        )
    app.config.update(overrides)

    _inicializar_base_si_falta(app.config["DB_PATH"])

    from app.rutas import bp

    app.register_blueprint(bp)
    return app
