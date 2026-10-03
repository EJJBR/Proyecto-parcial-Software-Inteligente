"""Configuracion central del proyecto.

Todo parametro que antes estaba suelto en el notebook vive aqui, para que los modulos
(difusa, genetico, ia) no tengan numeros magicos repartidos.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# python-dotenv es opcional: si esta instalado se lee .env, si no se usan variables del sistema.
try:
    from dotenv import load_dotenv

    _ARCHIVO_ENV = BASE_DIR / ".env"
    if _ARCHIVO_ENV.is_file():
        load_dotenv(_ARCHIVO_ENV)
except ImportError:  # pragma: no cover
    pass

# --- Base de datos --------------------------------------------------------------------
DB_PATH = Path(os.getenv("BODEGA_DB_PATH", BASE_DIR / "data" / "bodega.db"))
SCHEMA_SQL = BASE_DIR / "data" / "schema.sql"
SEED_SQL = BASE_DIR / "data" / "seed.sql"
SEMANAS_VENTANA_VENTAS = 4  # score_demanda se calcula con las ventas de las ultimas 4 semanas

# --- IA generativa (se usa a partir del paso 5) ---------------------------------------
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip() or None
GROQ_MODEL = os.getenv("GROQ_MODEL") or None
GROQ_TIMEOUT_SEGUNDOS = int(os.getenv("GROQ_TIMEOUT_SEGUNDOS", "30"))
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY") or None
GROQ_TEMPERATURA_INTERPRETACION = 0.1
GROQ_TEMPERATURA_EXPLICACION = 0.3
GROQ_MAX_REINTENTOS_JSON = 1
GROQ_MAX_TOKENS_INTERPRETACION = 2000
GROQ_MAX_TOKENS_EXPLICACION = 2000


def exigir_clave_groq() -> str:
    """Devuelve la clave de Groq o falla solo cuando se solicita."""
    if GROQ_API_KEY is None:
        raise RuntimeError(
            "Falta configurar GROQ_API_KEY mediante una variable de entorno o el archivo .env."
        )
    return GROQ_API_KEY

# --- Algoritmo genetico (valores de la version vigente del notebook; NO cambiar) --------
TAMANO_POBLACION = 40
GENERACIONES = 1500
TAMANO_TORNEO = 3
TASA_CROSSOVER = 0.8
TASA_MUTACION = 0.08  # por gen
ELITISMO = 1
NUM_GENES = 15

# --- Cromosoma y fitness ---------------------------------------------------------------
CANTIDAD_MIN = 0
CANTIDAD_MAX = 30
COEFICIENTE_RIESGO_CADENA = 0.6  # cantidad_max_i = round(CANTIDAD_MAX * (1 - coef * riesgo_merma_i))
FACTOR_CASTIGO = 10  # penalizacion de presupuesto = (costo - presupuesto) * FACTOR_CASTIGO
PENALIZACION_RESTRICCION_DURA = 500

# Semilla del AG: None en produccion (resultado distinto en cada corrida); 42 en pruebas.
SEMILLA_AG = None
