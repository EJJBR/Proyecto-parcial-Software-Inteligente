"""Prueba manual del flujo del orquestador con una copia temporal de la base."""
import argparse
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path


RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
RUTA_BASE_ORIGINAL = RAIZ_PROYECTO / "data" / "bodega.db"


def _crear_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        description=(
            "Prueba el orquestador con Groq usando una copia temporal de la base de datos."
        ),
        usage=(
            "python scripts\\probar_orquestador.py [--conservar] "
            "FRASE [FRASE ...]"
        ),
    )


def _contar_registros(conn: sqlite3.Connection) -> tuple[int, int]:
    solicitudes = conn.execute("SELECT COUNT(*) FROM SOLICITUD").fetchone()[0]
    recomendaciones = conn.execute(
        "SELECT COUNT(*) FROM RECOMENDACION"
    ).fetchone()[0]
    return solicitudes, recomendaciones


def _imprimir_conteos(
    conn: sqlite3.Connection, momento: str
) -> None:
    solicitudes, recomendaciones = _contar_registros(conn)
    print(
        f"{momento}: SOLICITUD={solicitudes}, "
        f"RECOMENDACION={recomendaciones}"
    )


def _imprimir_recomendacion(resultado: object) -> None:
    productos = getattr(resultado, "productos", None) or []
    print("Productos recomendados:")
    for producto in productos:
        print(f"  {producto['nombre']}: {producto['cantidad']}")
    costo = getattr(resultado, "costo_total", None)
    presupuesto = getattr(resultado, "presupuesto", None)
    if costo is not None:
        print(f"Costo total: S/ {costo:,.2f}")
    if presupuesto is not None:
        print(f"Presupuesto: S/ {presupuesto:,.2f}")
    fitness = getattr(resultado, "fitness", None)
    if fitness is not None:
        print(f"Fitness: {fitness:.2f}")
    print("Explicación:", getattr(resultado, "explicacion", None))
    usada_ia = getattr(resultado, "usada_ia", False)
    print("Origen de explicación:", "IA" if usada_ia else "respaldo local")
    motivo = getattr(resultado, "motivo_respaldo", None)
    if motivo is not None:
        print("Motivo del respaldo:", motivo)
    print("ID de recomendación guardada:", getattr(resultado, "id_recomendacion", None))


def main(argv: list[str] | None = None) -> int:
    parser = _crear_parser()
    parser.add_argument(
        "--conservar",
        action="store_true",
        help="conserva la copia temporal e imprime su ruta",
    )
    parser.add_argument(
        "frases",
        nargs="*",
        metavar="FRASE",
        help="mensajes sucesivos de la conversación",
    )
    args = parser.parse_args(argv)
    if not args.frases:
        parser.print_usage(sys.stderr)
        print(
            "Error: indique al menos una frase para iniciar la conversación.",
            file=sys.stderr,
        )
        return 2

    if not RUTA_BASE_ORIGINAL.is_file():
        print(
            "No se encontró data\\bodega.db. No se creó ninguna base de datos.",
            file=sys.stderr,
        )
        return 1

    carpeta_temporal = Path(
        tempfile.mkdtemp(prefix="probar_orquestador_")
    )
    ruta_copia = carpeta_temporal / "bodega.db"
    conn: sqlite3.Connection | None = None
    conservar = args.conservar

    try:
        shutil.copy2(RUTA_BASE_ORIGINAL, ruta_copia)

        sys.path.insert(0, str(RAIZ_PROYECTO))
        from app.orquestador import procesar_mensajes

        conn = sqlite3.connect(str(ruta_copia))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        _imprimir_conteos(conn, "Antes de la conversación")

        for indice in range(1, len(args.frases) + 1):
            resultado = procesar_mensajes(conn, args.frases[:indice])
            print(f"Paso {indice}: tipo={resultado.tipo}")
            if resultado.tipo == "aclaracion":
                print("Pregunta de aclaración:", resultado.mensaje)
                if indice == len(args.frases):
                    print(
                        "La conversación terminó con una aclaración pendiente."
                    )
                    break
                continue
            if resultado.tipo == "recomendacion":
                _imprimir_recomendacion(resultado)
            else:
                print("Mensaje:", resultado.mensaje)
            break

        _imprimir_conteos(conn, "Después de la conversación")
    except Exception:
        print(
            "No se pudo completar la prueba del orquestador. "
            "Revisa la configuración y la copia temporal de la base.",
            file=sys.stderr,
        )
        return 1
    finally:
        if conn is not None:
            conn.close()
        if conservar:
            print("Copia temporal conservada en:", ruta_copia)
        else:
            shutil.rmtree(carpeta_temporal, ignore_errors=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
