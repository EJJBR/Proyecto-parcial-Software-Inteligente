"""Cliente Groq y conversion de errores externos a mensajes seguros en espanol."""
import os
import time
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import config


class ErrorIA(RuntimeError):
    """Error de IA con mensaje seguro que nunca expone credenciales."""


class ErrorLimiteVelocidad(ErrorIA):
    """Groq rechazó la solicitud por límite de velocidad tras reintentos."""

    def __init__(self) -> None:
        super().__init__(
            "Hay muchas solicitudes a la IA en este momento. "
            "Espera unos segundos e intenta de nuevo."
        )


_MAX_REINTENTOS_429 = 2
_ESPERAS_REINTENTO_429 = (3.0, 6.0)
_MAX_ESPERA_RETRY_AFTER = 10.0


def _depuracion_activa() -> bool:
    return os.getenv("GROQ_DEBUG", "").strip().casefold() in {"1", "true", "yes", "on"}


def _nombres_campos_message(message: Any) -> list[str]:
    campos = getattr(message, "model_fields_set", None)
    if campos is not None:
        return sorted(str(campo) for campo in campos)
    if isinstance(message, dict):
        return sorted(str(campo) for campo in message)
    atributos = getattr(message, "__dict__", {})
    return sorted(
        str(campo)
        for campo in atributos
        if isinstance(campo, str) and not campo.startswith("_")
    )


def _valor_finish_reason(respuesta: Any) -> str | int | float | bool | None:
    try:
        valor = respuesta.choices[0].finish_reason
    except (AttributeError, IndexError, KeyError, TypeError):
        return None
    if isinstance(valor, (str, int, float, bool)) or valor is None:
        return valor[:80] if isinstance(valor, str) else valor
    return type(valor).__name__


def _conteo_tokens(usage: Any) -> dict[str, int | float]:
    if usage is None:
        return {}
    campos = ("prompt_tokens", "completion_tokens", "total_tokens")
    conteos: dict[str, int | float] = {}
    for campo in campos:
        valor = usage.get(campo) if isinstance(usage, dict) else getattr(usage, campo, None)
        if isinstance(valor, (int, float)) and not isinstance(valor, bool):
            conteos[campo] = valor
    return conteos


def _imprimir_diagnostico_respuesta(
    respuesta: Any,
    message: Any,
    contenido: Any,
) -> None:
    """Imprime solo metadatos no sensibles de una respuesta no válida."""
    try:
        usage = respuesta.usage
    except (AttributeError, TypeError):
        usage = None
    longitud = len(contenido) if isinstance(contenido, str) else None
    print("Diagnóstico Groq (sin contenido sensible):")
    print(f"  modelo: {config.GROQ_MODEL}")
    print(f"  finish_reason: {_valor_finish_reason(respuesta)!r}")
    print(f"  message.content: tipo={type(contenido).__name__}, longitud={longitud!r}")
    print(f"  campos de message: {_nombres_campos_message(message)}")
    print(f"  tokens de uso: {_conteo_tokens(usage)}")


def crear_cliente_groq() -> Any:
    """Crea el cliente real solo cuando una operacion lo necesita."""
    try:
        clave = config.exigir_clave_groq()
    except RuntimeError:
        raise ErrorIA(
            "Falta configurar GROQ_API_KEY antes de usar la integración con Groq."
        ) from None
    try:
        from groq import Groq
    except ImportError:
        raise ErrorIA("Falta instalar la dependencia groq en el entorno del proyecto.") from None
    return Groq(
        api_key=clave,
        timeout=config.GROQ_TIMEOUT_SEGUNDOS,
        max_retries=0,
    )


def _mensaje_error_groq(error: Exception) -> str:
    """Traduce fallos conocidos del SDK sin incorporar el texto original del error."""
    tipo = type(error).__name__
    if isinstance(error, TimeoutError) or tipo == "APITimeoutError":
        return "La solicitud a Groq superó el tiempo máximo de espera."
    if isinstance(error, ConnectionError) or tipo == "APIConnectionError":
        return "No se pudo establecer conexión con Groq."
    if tipo == "RateLimitError":
        return "Groq alcanzó el límite de uso. Inténtalo nuevamente más tarde."
    if tipo == "AuthenticationError":
        return "Groq rechazó la autenticación. Verifica la configuración de la clave."
    if tipo == "APIStatusError" and getattr(error, "status_code", None) in (401, 403):
        return "Groq rechazó la autenticación. Verifica la configuración de la clave."
    return "Ocurrió un error al comunicarse con el servicio de Groq."


def _codigo_estado(error: Exception) -> int | None:
    codigo = getattr(error, "status_code", None)
    if codigo is None:
        respuesta = getattr(error, "response", None)
        codigo = getattr(respuesta, "status_code", None)
    return codigo if isinstance(codigo, int) else None


def _retry_after(error: Exception) -> float | None:
    respuesta = getattr(error, "response", None)
    headers = getattr(respuesta, "headers", None)
    if not isinstance(headers, Mapping):
        return None
    valor = headers.get("retry-after")
    if valor is None:
        return None
    try:
        return float(valor)
    except (TypeError, ValueError):
        try:
            fecha = parsedate_to_datetime(str(valor))
            if fecha.tzinfo is None:
                fecha = fecha.replace(tzinfo=timezone.utc)
            return (fecha - datetime.now(timezone.utc)).total_seconds()
        except (TypeError, ValueError, OverflowError):
            return None


def _solicitar_completado(
    cliente: Any,
    mensajes: list[dict[str, str]],
    *,
    temperatura: float,
    max_tokens: int,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> str:
    """Ejecuta chat.completions.create, aplicando la traduccion de errores."""
    if not config.GROQ_MODEL or config.GROQ_MODEL == "elige_un_modelo_vigente":
        raise ErrorIA(
            "Falta configurar GROQ_MODEL con un modelo vigente desde la consola de Groq."
        )
    for intento in range(_MAX_REINTENTOS_429 + 1):
        try:
            respuesta = cliente.chat.completions.create(
                model=config.GROQ_MODEL,
                messages=mensajes,
                temperature=temperatura,
                max_tokens=max_tokens,
            )
            break
        except Exception as error:
            if _codigo_estado(error) != 429:
                raise ErrorIA(_mensaje_error_groq(error)) from None
            if intento >= _MAX_REINTENTOS_429:
                raise ErrorLimiteVelocidad() from None

            retry_after = _retry_after(error)
            if retry_after is not None and retry_after > _MAX_ESPERA_RETRY_AFTER:
                raise ErrorLimiteVelocidad() from None
            espera = (
                retry_after
                if retry_after is not None and retry_after >= 0
                else _ESPERAS_REINTENTO_429[intento]
            )
            sleep_fn(espera)
    else:
        raise ErrorLimiteVelocidad() from None

    message = None
    try:
        message = respuesta.choices[0].message
        contenido = message.content
    except (AttributeError, IndexError, KeyError, TypeError):
        contenido = None
    if not isinstance(contenido, str) or not contenido.strip():
        if _depuracion_activa():
            _imprimir_diagnostico_respuesta(respuesta, message, contenido)
        raise ErrorIA("Groq devolvió una respuesta vacía o con un formato no válido.")
    return contenido.strip()
