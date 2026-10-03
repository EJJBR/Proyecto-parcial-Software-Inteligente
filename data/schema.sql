-- Esquema de bodega.db (modelo MEER del avance 30%).
-- Generado a partir de la base de datos entregada; no cambia ninguna tabla ni restriccion.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS USUARIO (
    id_usuario      INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre_bodega   TEXT NOT NULL,
    ubicacion       TEXT
);

CREATE TABLE IF NOT EXISTS CATEGORIA (
    id_categoria    INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre          TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS PRODUCTO (
    id_producto     INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre          TEXT NOT NULL,
    id_categoria    INTEGER NOT NULL REFERENCES CATEGORIA(id_categoria),
    precio_compra   REAL NOT NULL,
    precio_venta    REAL NOT NULL,
    perecibilidad   TEXT NOT NULL CHECK (perecibilidad IN ('alto','medio','bajo')),
    dias_vida_util  INTEGER NOT NULL,
    stock_actual    INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS VENTA_HISTORICA (
    id_venta            INTEGER PRIMARY KEY AUTOINCREMENT,
    id_producto          INTEGER NOT NULL REFERENCES PRODUCTO(id_producto),
    semana               TEXT NOT NULL,
    cantidad_vendida     INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS SOLICITUD (
    id_solicitud     INTEGER PRIMARY KEY AUTOINCREMENT,
    id_usuario       INTEGER NOT NULL REFERENCES USUARIO(id_usuario),
    fecha            TEXT NOT NULL,
    presupuesto      REAL NOT NULL,
    texto_original   TEXT
);

CREATE TABLE IF NOT EXISTS SOLICITUD_CATEGORIA_PRIORITARIA (
    id_solicitud   INTEGER NOT NULL REFERENCES SOLICITUD(id_solicitud),
    id_categoria   INTEGER NOT NULL REFERENCES CATEGORIA(id_categoria),
    PRIMARY KEY (id_solicitud, id_categoria)
);

CREATE TABLE IF NOT EXISTS SOLICITUD_PRODUCTO_REGLA (
    id_solicitud   INTEGER NOT NULL REFERENCES SOLICITUD(id_solicitud),
    id_producto    INTEGER NOT NULL REFERENCES PRODUCTO(id_producto),
    tipo_regla     TEXT NOT NULL CHECK (tipo_regla IN ('incluir_forzado','excluir')),
    PRIMARY KEY (id_solicitud, id_producto)
);

CREATE TABLE IF NOT EXISTS RECOMENDACION (
    id_recomendacion   INTEGER PRIMARY KEY AUTOINCREMENT,
    id_solicitud       INTEGER NOT NULL UNIQUE REFERENCES SOLICITUD(id_solicitud),
    fecha              TEXT NOT NULL,
    fitness_final      REAL,
    costo_total        REAL,
    explicacion_texto  TEXT
);

CREATE TABLE IF NOT EXISTS DETALLE_RECOMENDACION (
    id_detalle             INTEGER PRIMARY KEY AUTOINCREMENT,
    id_recomendacion       INTEGER NOT NULL REFERENCES RECOMENDACION(id_recomendacion),
    id_producto             INTEGER NOT NULL REFERENCES PRODUCTO(id_producto),
    cantidad_recomendada    INTEGER NOT NULL
);
