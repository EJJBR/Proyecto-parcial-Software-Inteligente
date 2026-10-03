"""Prueba manual de interpretacion y explicacion con la API real de Groq.

Ejecutar desde la raiz del proyecto:
    python scripts/probar_ia.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
from app.db.catalogo_repo import cargar_catalogo  # noqa: E402
from app.db.conexion import conexion  # noqa: E402
from app.modules.genetico import ejecutar_algoritmo_genetico  # noqa: E402
from app.modules.ia import ErrorIA, interpretar_solicitud, redactar_explicacion  # noqa: E402


def main() -> None:
    try:
        config.exigir_clave_groq()
    except RuntimeError:
        print("Falta configurar GROQ_API_KEY en .env o en el entorno antes de usar Groq.")
        return

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
            print("Faltan datos:", interpretacion.pregunta_aclaracion)
            return
        if interpretacion.no_reconocidos:
            print("Revisa los nombres no reconocidos:", interpretacion.no_reconocidos)
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
    except ErrorIA as error:
        print(f"No se pudo completar la operación con Groq: {error}")


if __name__ == "__main__":
    main()
