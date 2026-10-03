# Asistente de Compras Inteligente para Bodegas

Proyecto del curso Software Inteligente (UNMSM). El sistema calcula una canasta de
reposición para una bodega a partir de un catálogo, ventas recientes, presupuesto y
preferencias del usuario.

## Estado del proyecto

Ya están implementados:

- Acceso a SQLite para catálogo, solicitudes y recomendaciones (`app/db/`).
- Lógica difusa de demanda y riesgo de merma (`app/modules/difusa/`).
- Algoritmo genético de optimización (`app/modules/genetico/`).
- Interpretación de solicitudes y redacción de explicaciones mediante Groq
  (`app/modules/ia/`), con validación local y una explicación de respaldo.
- Scripts de inicialización y comprobaciones manuales, además de pruebas automáticas.

Todavía no están implementados el orquestador de aplicación, las rutas/endpoints Flask
ni la interfaz gráfica. Aunque Flask y `FLASK_SECRET_KEY` están declarados para la
integración futura, no hay una aplicación web ejecutable en este estado.

## Requisitos

- Python 3.12 (el entorno de desarrollo del proyecto usa Python 3.12.7).
- Las dependencias fijadas en `requirements.txt`.
- Para usar las funciones de IA: una clave válida de Groq y un nombre de modelo vigente
  elegido desde la consola de Groq.

## Instalación en Windows

Desde la raíz del proyecto, crea y activa un entorno virtual e instala las dependencias:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Si PowerShell no permite activar el entorno, se puede usar el intérprete directamente:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Configuración local

1. Copia `.env.example` como `.env` en la raíz del proyecto.
2. Edita `.env` localmente y configura `GROQ_API_KEY`, `GROQ_MODEL` y, si corresponde,
   los demás valores.
3. Consulta la consola de Groq para escoger un modelo vigente; no se presupone que un
   modelo concreto esté disponible para todas las cuentas.
4. No compartas ni subas `.env`. `.gitignore` excluye ese archivo.

Variables configurables:

| Variable | Uso | Predeterminado |
|---|---|---|
| `GROQ_API_KEY` | Credencial para acceder a Groq. Se exige solo al crear el cliente real. | Sin configurar |
| `GROQ_MODEL` | Modelo elegido en la consola de Groq. | Sin configurar |
| `GROQ_TIMEOUT_SEGUNDOS` | Tiempo máximo de espera del cliente. | `30` |
| `FLASK_SECRET_KEY` | Clave secreta prevista para sesiones Flask. | Sin configurar |
| `BODEGA_DB_PATH` | Ruta alternativa a la base SQLite. | `data/bodega.db` |
| `GROQ_DEBUG` | Activa metadatos seguros de diagnóstico ante respuestas vacías o inválidas. | Desactivado |

La temperatura y los límites de tokens de interpretación/explicación se definen como
constantes en `config.py`.

## Base de datos

La base predeterminada está en `data/bodega.db`. El esquema se encuentra en
`data/schema.sql` y los datos de demostración en `data/seed.sql`.

Para crear una base en una ruta donde todavía no exista:

```powershell
.\.venv\Scripts\python.exe scripts\inicializar_bd.py
```

El script carga el esquema y los datos de prueba por defecto. Si el archivo de destino
ya existe, se detiene. La opción `--sin-datos` crea solo las tablas. **`--force`
elimina el archivo existente antes de recrearlo**, así que úsala únicamente después de
hacer una copia de seguridad y confirmar la ruta:

```powershell
.\.venv\Scripts\python.exe scripts\inicializar_bd.py --force
```

Se puede especificar una ubicación alternativa con `--ruta ruta\de\la\base.db`.

## Comprobaciones sin llamadas a Groq

Ejecuta la suite desde la raíz del proyecto:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Para comprobar que el catálogo, la solicitud de demostración y la lógica difusa
funcionan juntos:

```powershell
.\.venv\Scripts\python.exe scripts\probar_paso_1_2.py
```

Las pruebas de `tests/test_ia.py` usan un cliente falso y no llaman a la API.

## Prueba manual con Groq

`scripts/probar_ia.py` llama a la API real. Configura antes una clave válida y un modelo
vigente en `.env`; ejecútalo solo cuando quieras consumir la API:

```powershell
.\.venv\Scripts\python.exe scripts\probar_ia.py
```

Para activar temporalmente diagnósticos de metadatos no sensibles si Groq devuelve una
respuesta vacía o inválida:

```powershell
$env:GROQ_DEBUG = "1"
.\.venv\Scripts\python.exe scripts\probar_ia.py
Remove-Item Env:GROQ_DEBUG
```

El diagnóstico no imprime la clave, encabezados, contenido de la respuesta ni el prompt.
Sin la variable `GROQ_DEBUG`, no imprime metadatos adicionales.

## Flujo y lógica

El flujo previsto es:

1. Leer catálogo y solicitud mediante los repositorios de `app/db/`.
2. Interpretar texto natural con `interpretar_solicitud`, o proporcionar una solicitud ya
   estructurada.
3. Optimizar la canasta con `ejecutar_algoritmo_genetico`.
4. Redactar una explicación con `redactar_explicacion`.

La solicitud estructurada usa estos campos:

```python
{
    "presupuesto": 1500.0,
    "categorias_prioritarias": ["abarrotes", "lacteos"],
    "incluir_forzado": ["Arroz"],
    "excluir": [],
}
```

Los nombres de categorías y productos se identifican por su nombre canónico en el
catálogo. El módulo genético es determinista si se le pasa una semilla; por defecto usa
`semilla=None`. Sus parámetros están centralizados en `config.py`. El riesgo de merma
limita el máximo por producto, pero no se resta del fitness.

Las funciones públicas de IA y del algoritmo genético se exponen en los respectivos
`app/modules/ia/__init__.py` y `app/modules/genetico/__init__.py`.

## Notebooks de referencia

- `guia/algoritmo_genetico_prueba.ipynb` contiene la lógica vigente de referencia del
  algoritmo genético.
- `guia/proyecto_consolidado.ipynb` es una versión anterior y no debe usarse como
  referencia de la lógica vigente. La base actual se inicializa desde los archivos SQL,
  no ejecutando esa notebook.

## Estructura principal

```text
app/
  db/                 Repositorios y conexión SQLite
  modules/
    difusa/           Funciones de membresía y variables difusas
    genetico/         Optimización de la canasta
    ia/               Interpretación y explicación con Groq
data/
  schema.sql          Esquema de la base
  seed.sql            Datos iniciales de demostración
  bodega.db           Base de datos local predeterminada
guia/                 Notebooks de referencia
scripts/              Inicialización y pruebas manuales
tests/                Pruebas automáticas
config.py             Configuración central
requirements.txt      Dependencias fijadas
```
