# Asistente de Compras Inteligente para Bodegas

Proyecto del curso Software Inteligente (UNMSM). El dueño de una bodega escribe su
solicitud en lenguaje natural. La IA la interpreta; un algoritmo genético, apoyado por
lógica difusa, decide qué productos comprar y en qué cantidades; y la IA redacta una
explicación. Si falla la generación de esa explicación, el sistema ofrece una explicación
de respaldo local.

## Estado del proyecto

El sistema incluye acceso a SQLite, lógica difusa, algoritmo genético, integración con
Groq, orquestador, rutas Flask e interfaz web. La interfaz tiene catálogo, chat y panel
de recomendación. También hay scripts de inicialización y pruebas automáticas.

La interpretación de la solicitud sí necesita la integración con Groq. El respaldo local
se usa para la explicación de la recomendación cuando la IA no puede redactarla.

## Requisitos

- Python 3.12.
- Git.
- Una cuenta gratuita de Groq para obtener una clave de API personal. Cada integrante
  debe crear su propia clave desde la consola de Groq; no la comparta ni la suba a Git.

## Correr la aplicación

Ejecuta estos pasos desde una terminal.

1. **Clona el repositorio y entra a la carpeta.**

   ```text
   git clone https://github.com/EJJBR/Proyecto-parcial-Software-Inteligente.git
   cd Proyecto-parcial-Software-Inteligente
   ```

2. **Crea y activa un entorno virtual e instala las dependencias.**

   Windows (PowerShell):

   ```powershell
   py -3.12 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   ```

   Si PowerShell bloquea la activación, permite scripts solo en la ventana actual y
   vuelve a activar el entorno:

   ```powershell
   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
   .\.venv\Scripts\Activate.ps1
   ```

   También puedes omitir la activación y usar directamente el intérprete del entorno:

   ```powershell
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

   macOS/Linux:

   ```bash
   python3.12 -m venv .venv
   source .venv/bin/activate
   python -m pip install -r requirements.txt
   ```

3. **Crea tu archivo local de configuración.**

   Windows (PowerShell):

   ```powershell
   Copy-Item .env.example .env
   ```

   macOS/Linux:

   ```bash
   cp .env.example .env
   ```

4. **Configura las variables dentro de `.env`.**

   - `GROQ_API_KEY`: tu clave personal creada en la consola de Groq.
   - `GROQ_MODEL`: el modelo con el que se probó el proyecto es
     `openai/gpt-oss-120b`. Comprueba en tu consola de Groq que esté disponible para tu
     cuenta antes de usarlo.
   - `FLASK_SECRET_KEY`: texto aleatorio local para firmar la sesión de Flask. No es la
     clave de Groq. Genéralo con este comando y copia el resultado únicamente a tu `.env`:

     ```bash
     python -c "import secrets; print(secrets.token_hex(32))"
     ```

   Si falta `FLASK_SECRET_KEY`, la aplicación no arranca y muestra un mensaje claro. Si
   falta `GROQ_API_KEY` o `GROQ_MODEL`, la aplicación web puede arrancar, pero las
   operaciones que necesitan interpretar texto con Groq fallarán al usarlas con un
   mensaje en español. Nunca compartas el contenido de `.env`: `.gitignore` lo excluye.

5. **Revisa la base de datos.**

   `data/bodega.db` está incluida y versionada en el repositorio. Si el archivo no existe
   al iniciar la aplicación, Flask lo crea automáticamente con `data/schema.sql` y
   `data/seed.sql`. Si ya existe, la aplicación no lo reinicializa.

   Para devolver la base a su estado inicial, primero haz una copia de seguridad. Luego,
   desde la raíz del proyecto y con el entorno virtual activo, ejecuta:

   ```bash
   python scripts/inicializar_bd.py --force
   ```

   La opción `--force` elimina la base existente y la vuelve a crear con el esquema y los
   datos iniciales; por tanto, también borra las solicitudes y recomendaciones guardadas.
   El script se detiene si la base existe y no se especifica `--force`. `--sin-datos`
   crea solo las tablas, y `--ruta RUTA` permite elegir otra ubicación.

6. **Inicia el servidor y abre la interfaz.**

   ```bash
   python run.py
   ```

   En el navegador abre <http://127.0.0.1:5000>. Para detener el servidor, vuelve a la
   terminal y presiona `Ctrl+C`.

   La página debe mostrar tres columnas: productos disponibles, chat y recomendación.
   También puedes comprobar el catálogo en
   <http://127.0.0.1:5000/api/catalogo>: devuelve 15 productos y 6 categorías.

## Probar la interfaz

Puedes probar estas solicitudes desde el chat:

- `Tengo S/1500, prioriza lácteos`: debe generar una recomendación completa. El algoritmo
  genético puede tardar aproximadamente entre 10 y 15 segundos.
- `Prioriza lácteos` y luego `Tengo 1500 soles`: primero debe pedir el presupuesto y,
  cuando respondas, continuar con la recomendación usando el contexto de la conversación.
- `Incluye pizza congelada, tengo 1500 soles`: debe pedir una aclaración porque ese
  producto no está en el catálogo.

La etiqueta **Basado en IA** indica que la IA redactó la explicación. **Respaldo local**
indica que se presentó la explicación local porque Groq no pudo generarla; es un
comportamiento previsto, no un error de la recomendación.

## Problemas frecuentes

| Situación | Qué significa y qué hacer |
|---|---|
| Falta `FLASK_SECRET_KEY` | Flask no inicia. Configura la variable en `.env` y vuelve a ejecutar `python run.py`. |
| Falta `GROQ_API_KEY` o es inválida | La interpretación necesita Groq y devuelve un error en español. Configura una clave propia válida en `.env`. |
| Falta `GROQ_MODEL` o no está disponible | La operación de IA falla al usarse. Selecciona en la consola un modelo vigente habilitado para tu cuenta. |
| “Hay muchas solicitudes a la IA en este momento” | Se alcanzó el límite de velocidad de Groq. Espera unos segundos antes de volver a intentarlo. |
| El puerto 5000 está ocupado | Cierra la otra aplicación que lo está usando y vuelve a ejecutar `python run.py`. |
| El navegador muestra una versión anterior | Fuerza la recarga con `Ctrl+F5`. |
| La explicación dice “Respaldo local” | La IA no redactó la explicación y se usó el respaldo previsto. La recomendación sigue disponible. |

## Notas para quienes prueben

- Las recomendaciones se guardan en la base SQLite local y no se envían a otros
  integrantes. Sin embargo, `data/bodega.db` está versionada: los cambios locales pueden
  aparecer en `git status`. No agregues ni subas ese archivo con datos de prueba.
- Las imágenes opcionales van en `app/static/img/productos/<id>.png`. Actualmente esa
  carpeta solo contiene `.gitkeep`; no hay imágenes PNG de productos. En el catálogo se
  muestra un emoji correspondiente a la categoría cuando falta la imagen. La respuesta
  de recomendación no incluye la categoría, por lo que en ese panel se usa un icono
  genérico cuando falta la imagen.
- No subas `.env`. Antes de crear un commit, revisa `git status` y asegúrate de no incluir
  credenciales ni datos locales.
- Envía tus comentarios a: [completar]

## Pruebas automáticas

Desde la raíz del repositorio y con el entorno virtual activo:

```bash
python -m pytest -q
```

La suite usa clientes falsos para las pruebas de IA; no llama a Groq. En la versión
actual pasan 186 pruebas y la ejecución tarda aproximadamente un par de minutos.

Para una comprobación manual del catálogo, la solicitud de demostración y la lógica difusa
(sin llamar a Groq):

```bash
python scripts/probar_paso_1_2.py
```

## Scripts manuales que consumen la API

Estos scripts hacen llamadas reales a Groq y pueden consumir el límite de tu cuenta.
Úsalos solo después de configurar tus variables y cuando quieras probar la API:

```bash
python scripts/probar_ia.py
python scripts/probar_orquestador.py "Tengo S/1500, prioriza lácteos"
```

`probar_orquestador.py` trabaja sobre una copia temporal de la base; `--conservar`
mantiene esa copia para inspeccionarla. Para activar temporalmente el diagnóstico seguro
de `probar_ia.py` en PowerShell:

```powershell
$env:GROQ_DEBUG = "1"
python scripts\probar_ia.py
Remove-Item Env:GROQ_DEBUG
```

El diagnóstico no imprime la clave, encabezados, contenido de la respuesta ni el prompt.

## Flujo y lógica

El flujo de una recomendación es:

1. Leer catálogo e historial mediante los repositorios de `app/db/`.
2. Interpretar el texto con `interpretar_solicitud`.
3. Optimizar la canasta con `ejecutar_algoritmo_genetico`.
4. Redactar la explicación con `redactar_explicacion`, o usar el respaldo local si no se
   puede generar.
5. Guardar la solicitud y recomendación desde el orquestador.

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
catálogo. El algoritmo genético es determinista si se le pasa una semilla; en producción
usa `semilla=None`. Sus parámetros están centralizados en `config.py`. El riesgo de
merma limita la cantidad máxima por producto, pero no se resta del fitness.

Las funciones públicas de IA y del algoritmo genético se exponen en sus respectivos
`app/modules/ia/__init__.py` y `app/modules/genetico/__init__.py`.

## Notebooks de referencia

- `guia/algoritmo_genetico_prueba.ipynb` contiene la lógica vigente de referencia del
  algoritmo genético.
- `guia/proyecto_consolidado.ipynbproyecto_consolidado_OBSOLETO.ipynb` es una notebook
  anterior y no debe usarse como referencia de la lógica vigente. La base se inicializa
  desde los archivos SQL, no ejecutando una notebook.

## Variables de entorno

| Variable | Uso | Comportamiento |
|---|---|---|
| `GROQ_API_KEY` | Clave personal para la API de Groq. | Necesaria al usar la interpretación; no es requisito para que Flask arranque. |
| `GROQ_MODEL` | Modelo habilitado en la cuenta de Groq. | Necesario al hacer una operación de IA. |
| `GROQ_TIMEOUT_SEGUNDOS` | Tiempo máximo de espera de cada solicitud a Groq. | Opcional; predeterminado `30`. |
| `FLASK_SECRET_KEY` | Firma y protege la sesión de Flask. | Obligatoria para iniciar la aplicación web. |
| `BODEGA_DB_PATH` | Ruta alternativa a la base SQLite. | Opcional; predeterminado `data/bodega.db`. |
| `SESSION_COOKIE_SECURE` | Marca la cookie de sesión como segura para HTTPS. | Opcional; desactivada si no se configura. |
| `GROQ_DEBUG` | Metadatos de diagnóstico seguros en la prueba manual de IA. | Desactivado si no se configura. |

La temperatura, los límites de tokens de interpretación/explicación y los parámetros del
algoritmo genético están definidos en `config.py`.

## Estructura principal

```text
app/
  db/                         Repositorios, conexión e inicialización SQLite
  modules/
    difusa/                   Funciones de membresía y variables difusas
    genetico/                 Optimización de la canasta
    ia/                       Cliente Groq, interpretación y explicación
  orquestador.py              Coordinación entre módulos y persistencia
  rutas.py                    Rutas Flask y respuestas JSON
  static/
    css/style.css             Estilos de la interfaz
    img/productos/.gitkeep    Carpeta para imágenes opcionales
    js/app.js                 Comportamiento de la interfaz
  templates/index.html        Página principal
data/
  bodega.db                   Base inicial versionada (datos locales al trabajar)
  schema.sql                  Esquema SQLite
  seed.sql                    Datos iniciales de demostración
guia/                         Notebooks de referencia
scripts/
  inicializar_bd.py           Inicialización o reinicio explícito de la base
  probar_ia.py                Prueba manual que consume la API de Groq
  probar_orquestador.py       Prueba manual que consume la API de Groq
  probar_paso_1_2.py          Comprobación local sin Groq
tests/                        Pruebas automáticas
config.py                     Configuración central
requirements.txt              Dependencias fijadas
run.py                        Entrada para iniciar Flask
```
