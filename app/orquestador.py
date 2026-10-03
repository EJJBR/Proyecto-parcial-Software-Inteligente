"""Coordina la interpretación, optimización, explicación y persistencia de compras."""
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import sqlite3
import time
from typing import Any, Callable, Literal

from app.db.catalogo_repo import cargar_catalogo
from app.db.recomendacion_repo import guardar_recomendacion
from app.db.solicitud_repo import crear_solicitud
from app.modules.genetico import (
    PresupuestoInviableError,
    ejecutar_algoritmo_genetico,
)
from app.modules.ia import (
    ErrorIA,
    Explicacion,
    InterpretacionSolicitud,
    interpretar_solicitud,
    redactar_explicacion,
)
from app.modules.ia.cliente import ErrorLimiteVelocidad


ID_USUARIO_POR_DEFECTO = 1
MAX_MENSAJES_CONVERSACION = 5


@dataclass(frozen=True)
class ResultadoOrquestacion:
    tipo: Literal["recomendacion", "aclaracion", "error"]
    mensaje: str | None = None
    productos: list[dict[str, Any]] | None = None
    costo_total: float | None = None
    presupuesto: float | None = None
    fitness: float | None = None
    explicacion: str | None = None
    usada_ia: bool | None = None
    motivo_respaldo: str | None = None
    id_recomendacion: int | None = None


def _resultado_error(mensaje: str) -> ResultadoOrquestacion:
    return ResultadoOrquestacion(tipo="error", mensaje=mensaje)


def _validar_mensajes(mensajes: Sequence[str]) -> list[str]:
    if isinstance(mensajes, (str, bytes)) or not mensajes:
        raise ValueError("Debe proporcionar al menos un mensaje de usuario.")
    if any(not isinstance(mensaje, str) or not mensaje.strip() for mensaje in mensajes):
        raise ValueError("Los mensajes de usuario no pueden estar vacíos.")
    return [mensaje.strip() for mensaje in mensajes[-MAX_MENSAJES_CONVERSACION:]]


def _interpretar(
    mensajes: Sequence[str],
    catalogo: Sequence[Mapping[str, Any]],
    cliente: Any,
    sleep_fn: Callable[[float], None] | None,
) -> InterpretacionSolicitud:
    # The interpreter treats its first argument as the latest utterance and its
    # history argument as context; keeping that contract avoids changing IA/tests.
    return interpretar_solicitud(
        mensajes[-1],
        catalogo,
        historial=list(mensajes[:-1]),
        cliente=cliente,
        sleep_fn=sleep_fn or time.sleep,
    )


def procesar_mensajes(
    conn: sqlite3.Connection,
    mensajes: Sequence[str],
    *,
    cliente: Any = None,
    semilla: int | None = None,
    id_usuario: int = ID_USUARIO_POR_DEFECTO,
    sleep_fn: Callable[[float], None] | None = None,
) -> ResultadoOrquestacion:
    """Procesa una conversación; solo persiste recomendaciones completas."""
    try:
        mensajes_validos = _validar_mensajes(mensajes)
    except ValueError as error:
        return _resultado_error(str(error))

    try:
        if conn.execute(
            "SELECT 1 FROM USUARIO WHERE id_usuario = ?", (id_usuario,)
        ).fetchone() is None:
            return _resultado_error("No se encontró el usuario de bodega configurado.")
        catalogo = cargar_catalogo(conn)
    except sqlite3.Error:
        return _resultado_error("No se pudo cargar la información de la bodega.")

    try:
        interpretacion = _interpretar(
            mensajes_validos, catalogo, cliente, sleep_fn
        )
    except ErrorLimiteVelocidad as error:
        return _resultado_error(str(error))
    except ErrorIA as error:
        return _resultado_error(f"No se pudo interpretar la solicitud: {error}")

    if (
        interpretacion.faltantes
        or interpretacion.pregunta_aclaracion
        or interpretacion.no_reconocidos
    ):
        pregunta = interpretacion.pregunta_aclaracion or (
            "Necesito más información para procesar la solicitud."
        )
        return ResultadoOrquestacion(tipo="aclaracion", mensaje=pregunta)

    try:
        resultado_genetico = ejecutar_algoritmo_genetico(
            catalogo, interpretacion.solicitud, semilla=semilla
        )
        explicacion: Explicacion = redactar_explicacion(
            interpretacion.solicitud,
            resultado_genetico,
            catalogo,
            cliente=cliente,
            sleep_fn=sleep_fn,
        )
    except PresupuestoInviableError:
        if conn.in_transaction:
            conn.rollback()
        return ResultadoOrquestacion(
            tipo="aclaracion",
            mensaje=(
                "Los productos que pediste incluir suman más que tu presupuesto. "
                "Aumenta el presupuesto o quita algún producto obligatorio."
            ),
        )
    except ValueError:
        if conn.in_transaction:
            conn.rollback()
        return _resultado_error(
            "No se pudo calcular la recomendación con los datos proporcionados."
        )

    if conn.in_transaction:
        return _resultado_error(
            "No se pudo guardar la recomendación porque la conexión ya tiene una transacción activa."
        )

    texto_original = "\n".join(mensajes_validos)
    cantidades = {
        int(producto["id_producto"]): int(cantidad)
        for producto, cantidad in zip(
            catalogo, resultado_genetico.mejor_cromosoma
        )
    }
    productos = [
        {
            "id_producto": int(producto["id_producto"]),
            "nombre": str(producto["nombre"]),
            "cantidad": int(cantidad),
        }
        for producto, cantidad in zip(catalogo, resultado_genetico.mejor_cromosoma)
        if cantidad > 0
    ]

    try:
        conn.execute("BEGIN")
        id_solicitud = crear_solicitud(
            conn,
            id_usuario=id_usuario,
            presupuesto=interpretacion.solicitud["presupuesto"],
            texto_original=texto_original,
            categorias_prioritarias=interpretacion.solicitud[
                "categorias_prioritarias"
            ],
            incluir_forzado=interpretacion.solicitud["incluir_forzado"],
            excluir=interpretacion.solicitud["excluir"],
        )
        id_recomendacion = guardar_recomendacion(
            conn,
            id_solicitud=id_solicitud,
            fitness_final=resultado_genetico.fitness,
            costo_total=resultado_genetico.costo_total,
            explicacion_texto=explicacion.texto,
            cantidades=cantidades,
        )
        conn.commit()
    except (ValueError, sqlite3.Error):
        conn.rollback()
        return _resultado_error("No se pudo guardar la recomendación.")
    except Exception:
        conn.rollback()
        raise

    return ResultadoOrquestacion(
        tipo="recomendacion",
        productos=productos,
        costo_total=resultado_genetico.costo_total,
        presupuesto=float(interpretacion.solicitud["presupuesto"]),
        fitness=resultado_genetico.fitness,
        explicacion=explicacion.texto,
        usada_ia=explicacion.usada_ia,
        motivo_respaldo=explicacion.motivo_respaldo,
        id_recomendacion=id_recomendacion,
    )
