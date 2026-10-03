"""Crea data/bodega.db desde data/schema.sql y data/seed.sql.

Uso (desde la raiz del proyecto):
    python scripts/inicializar_bd.py            # crea la BD con datos de prueba
    python scripts/inicializar_bd.py --sin-datos
    python scripts/inicializar_bd.py --force    # sobrescribe una BD existente
"""
import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
from app.db.inicializar import crear_base  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ruta", default=str(config.DB_PATH))
    ap.add_argument("--sin-datos", action="store_true", help="solo crea las tablas")
    ap.add_argument("--force", action="store_true", help="sobrescribe si ya existe")
    args = ap.parse_args()

    ruta = Path(args.ruta)
    if ruta.exists():
        if not args.force:
            sys.exit(f"{ruta} ya existe. Usa --force para sobrescribirla.")
        ruta.unlink()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(ruta))
    crear_base(conn, con_datos=not args.sin_datos)
    conn.close()
    print(f"Base de datos creada en {ruta}")


if __name__ == "__main__":
    main()
