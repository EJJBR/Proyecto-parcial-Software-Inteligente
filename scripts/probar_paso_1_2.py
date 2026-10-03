"""Prueba rapida: BD -> catalogo -> logica difusa. Compara con la tabla del notebook.

Uso (desde la raiz del proyecto, con data/bodega.db en su sitio):
    python scripts/probar_paso_1_2.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.catalogo_repo import cargar_catalogo  # noqa: E402
from app.db.conexion import conexion  # noqa: E402
from app.db.solicitud_repo import obtener_ultima_solicitud  # noqa: E402
from app.modules.difusa import peso_categoria, riesgo_merma, score_demanda  # noqa: E402

with conexion() as conn:
    productos = cargar_catalogo(conn)
    solicitud = obtener_ultima_solicitud(conn)

print("Solicitud:", {k: solicitud[k] for k in ("presupuesto", "categorias_prioritarias", "incluir_forzado", "excluir")})
print(f"\n{'#':>2} {'Producto':<24}{'Ventas':>7}{'Dias':>6}{'Demanda':>9}{'Riesgo':>8}{'Peso':>6}")
print("-" * 64)
for i, p in enumerate(productos, 1):
    print(f"{i:>2} {p['nombre']:<24}{p['ventas_4sem']:>7}{p['dias_vida_util']:>6}"
          f"{score_demanda(p['ventas_4sem']):>9.3f}{riesgo_merma(p['dias_vida_util']):>8.1f}"
          f"{peso_categoria(p['categoria'], solicitud['categorias_prioritarias']):>6.1f}")
