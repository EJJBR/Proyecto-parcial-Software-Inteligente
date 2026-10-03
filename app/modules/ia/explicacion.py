"""Redaccion de explicaciones basadas exclusivamente en resultados ya calculados."""
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import json
import re
import unicodedata
from typing import Any

import config
from app.modules.difusa import riesgo_merma, score_demanda
from app.modules.genetico import ResultadoGenetico, calcular_topes
from .cliente import ErrorIA, _solicitar_completado, crear_cliente_groq


@dataclass(frozen=True)
class Explicacion:
    texto: str
    usada_ia: bool


def _normalizar(texto: str) -> str:
    descompuesto = unicodedata.normalize("NFKD", texto.casefold())
    sin_tildes = "".join(c for c in descompuesto if not unicodedata.combining(c))
    return " ".join(sin_tildes.split())


def _datos_resultado(resultado: Any) -> tuple[Sequence[int], float, float]:
    if isinstance(resultado, Mapping):
        cromosoma = resultado.get("mejor_cromosoma", resultado.get("mejor_individuo"))
        costo = resultado.get("costo_total")
        fitness = resultado.get("fitness")
    else:
        cromosoma = getattr(resultado, "mejor_cromosoma", None)
        costo = getattr(resultado, "costo_total", None)
        fitness = getattr(resultado, "fitness", None)
    if cromosoma is None or costo is None or fitness is None:
        raise ValueError("El resultado debe incluir cromosoma, costo_total y fitness.")
    return cromosoma, float(costo), float(fitness)


def _construir_datos(
    solicitud: Mapping[str, Any],
    resultado: Any,
    catalogo: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    cromosoma, costo_total, fitness = _datos_resultado(resultado)
    if len(cromosoma) != len(catalogo):
        raise ValueError("El cromosoma debe tener un gen por producto del catálogo.")
    topes = calcular_topes(catalogo)
    productos = []
    for cantidad, tope, producto in zip(cromosoma, topes, catalogo):
        if cantidad <= 0:
            continue
        productos.append(
            {
                "nombre": producto["nombre"],
                "cantidad": int(cantidad),
                "precio_compra_unitario": producto["precio_compra"],
                "ventas_4sem": producto["ventas_4sem"],
                "score_demanda": score_demanda(producto["ventas_4sem"]),
                "dias_vida_util": producto["dias_vida_util"],
                "riesgo_merma": riesgo_merma(producto["dias_vida_util"]),
                "cantidad_maxima": tope,
                "categoria": producto["categoria"],
            }
        )
    return {
        "productos_comprados": productos,
        "costo_total": costo_total,
        "fitness": fitness,
        "presupuesto": solicitud["presupuesto"],
        "categorias_prioritarias": list(solicitud.get("categorias_prioritarias", [])),
        "incluir_forzado": list(solicitud.get("incluir_forzado", [])),
        "excluir": list(solicitud.get("excluir", [])),
    }


def _respaldo(datos: Mapping[str, Any]) -> str:
    presupuesto = datos["presupuesto"]
    productos = datos["productos_comprados"]
    if productos:
        compras = "; ".join(
            f"{producto['cantidad']} de {producto['nombre']}"
            for producto in productos
        )
    else:
        compras = "no se seleccionaron productos"
    categorias = datos["categorias_prioritarias"]
    texto = (
        f"Se recomienda comprar {compras}. El costo estimado es S/{datos['costo_total']:.2f}, "
        f"frente a un presupuesto de S/{presupuesto:.2f}."
    )
    if productos:
        demanda = "; ".join(
            f"{producto['nombre']} ({producto['score_demanda']:.2f})"
            for producto in productos
        )
        texto += " La demanda reciente considerada para cada producto tiene estos scores: " + demanda + "."
    if categorias:
        texto += " Se priorizaron las categorías: " + ", ".join(categorias) + "."
    cortos = [
        producto
        for producto in productos
        if producto["riesgo_merma"] >= 0.5
    ]
    if cortos:
        texto += (
            " Las cantidades de productos con vida útil más corta están limitadas para "
            "reducir el riesgo de merma: "
            + ", ".join(
                f"{producto['nombre']} (máximo {producto['cantidad_maxima']})"
                for producto in cortos
            )
            + "."
        )
    if datos["incluir_forzado"]:
        texto += " Se respetó la inclusión solicitada de: " + ", ".join(datos["incluir_forzado"]) + "."
    if datos["excluir"]:
        texto += " Se excluyeron: " + ", ".join(datos["excluir"]) + "."
    return texto


def _menciona_producto_no_comprado(texto: str, catalogo: Sequence[Mapping[str, Any]], comprados: set[str]) -> bool:
    normalizado = _normalizar(texto)
    productos_no_comprados = sorted(
        (
            str(producto["nombre"])
            for producto in catalogo
            if str(producto["nombre"]) not in comprados
        ),
        key=len,
        reverse=True,
    )
    for nombre in productos_no_comprados:
        canonico = _normalizar(nombre)
        if re.search(r"(?<!\w)" + re.escape(canonico) + r"(?!\w)", normalizado):
            return True
    return False


def redactar_explicacion(
    solicitud: Mapping[str, Any],
    resultado: ResultadoGenetico | Mapping[str, Any],
    catalogo: Sequence[Mapping[str, Any]],
    *,
    cliente: Any = None,
) -> Explicacion:
    """Solicita una explicación y usa una plantilla segura si falla o inventa compras."""
    datos = _construir_datos(solicitud, resultado, catalogo)
    respaldo = _respaldo(datos)
    mensajes = [
        {
            "role": "system",
            "content": (
                "Redacta en español una explicación clara y breve para el dueño de una bodega. "
                "Explica cantidades, costo frente al presupuesto, demanda, categorías priorizadas, "
                "límites de vida útil y reglas de inclusión/exclusión. Usa SOLO los datos del JSON; "
                "no inventes cifras ni productos y no digas que se compró un producto si no aparece "
                "en productos_comprados. Devuelve únicamente el texto, sin Markdown."
            ),
        },
        {"role": "user", "content": json.dumps(datos, ensure_ascii=False)},
    ]
    try:
        cliente_activo = cliente if cliente is not None else crear_cliente_groq()
        texto = _solicitar_completado(
            cliente_activo,
            mensajes,
            temperatura=config.GROQ_TEMPERATURA_EXPLICACION,
            max_tokens=config.GROQ_MAX_TOKENS_EXPLICACION,
        )
    except ErrorIA:
        return Explicacion(respaldo, False)

    comprados = {
        str(producto["nombre"])
        for producto in datos["productos_comprados"]
    }
    if _menciona_producto_no_comprado(texto, catalogo, comprados):
        return Explicacion(respaldo, False)
    return Explicacion(texto, True)
