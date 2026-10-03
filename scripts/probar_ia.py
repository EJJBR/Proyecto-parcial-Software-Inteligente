"""Prueba manual de interpretacion y explicacion con la API real de Groq.

Ejecutar desde la raiz del proyecto:
    python scripts/probar_ia.py
"""
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
from app.db.catalogo_repo import cargar_catalogo  # noqa: E402
from app.db.conexion import conexion  # noqa: E402
from app.modules.genetico import ejecutar_algoritmo_genetico  # noqa: E402
from app.modules.ia import ErrorIA, interpretar_solicitud, redactar_explicacion  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Prueba manual de la integración con Groq.")
    parser.add_argument(
        "texto",
        nargs="?",
        help="texto de solicitud para interpretar (opcional)",
    )
    args = parser.parse_args()

    try:
        config.exigir_clave_groq()
    except RuntimeError:
        print("Falta configurar GROQ_API_KEY en .env o en el entorno antes de usar Groq.")
        return

    texto = args.texto
    if texto is None:
        texto = (
            "Tengo S/1500 para reponer esta semana, prioriza lácteos y abarrotes, "
            "asegúrate de incluir arroz"
        )
    try:
        with conexion() as conn:
            catalogo = cargar_catalogo(conn)

        interpretacion = interpretar_solicitud(texto, catalogo)
        print("Interpretación:", interpretacion)
        if interpretacion.faltantes:
            print("Datos faltantes:", ", ".join(interpretacion.faltantes))
        if interpretacion.no_reconocidos:
            print("Nombres no reconocidos:", ", ".join(interpretacion.no_reconocidos))
        if interpretacion.pregunta_aclaracion:
            print("Pregunta de aclaración:", interpretacion.pregunta_aclaracion)
        if (
            interpretacion.faltantes
            or interpretacion.no_reconocidos
            or interpretacion.pregunta_aclaracion
        ):
            return

        resultado = ejecutar_algoritmo_genetico(catalogo, interpretacion.solicitud)
        explicacion = redactar_explicacion(
            interpretacion.solicitud,
            resultado,
            catalogo,
        )
        print("Cromosoma:", resultado.mejor_cromosoma)
        print(f"Costo total: S/{resultado.costo_total:.2f}")
        print(f"Fitness: {resultado.fitness:.2f}")
        print("Explicación:", explicacion.texto)
        print("Origen de explicación:", "IA" if explicacion.usada_ia else "respaldo local")
        if explicacion.motivo_respaldo is not None:
            print("Motivo del respaldo:", explicacion.motivo_respaldo)
    except ErrorIA as error:
        print(f"No se pudo completar la operación con Groq: {error}")


if __name__ == "__main__":
    main()
