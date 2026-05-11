-- ═══════════════════════════════════════════════════════
-- BiciMAD · Modelo con tabla station versionada
-- ═══════════════════════════════════════════════════════
--
-- DISEÑO:
--   station        — una fila por versión de estación.
--                    Si cambia nombre, capacidad, dirección
--                    o coordenadas → nueva fila con nuevo
--                    station_id (SERIAL). El source_id es
--                    el id original del JSON (estable).
--
--   station_snapshot — solo estado operativo. FK a station.
--                    NO contiene metadatos (están en station).
--                    NO contiene filas con no_available = 1
--                    (filtradas en INSERT.py antes de entrar).
--
--   holidays       — fechas festivas para el dashboard.
--
-- CRITERIO DE SATURACIÓN:
--   dock_bikes / NULLIF(operative_bases, 0)
--   donde operative_bases = dock_bikes + free_bases (columna generada).
--
-- Uso:
--   psql -h host -U casaos -d bicimad -f CREATE.sql
-- ═══════════════════════════════════════════════════════

-- Borrar todo lo existente
DROP VIEW  IF EXISTS v_station_snapshot CASCADE;
DROP TABLE IF EXISTS station_snapshot   CASCADE;
DROP TABLE IF EXISTS station            CASCADE;
DROP TABLE IF EXISTS holidays           CASCADE;


-- ─── Estaciones (versionadas por cambio de metadatos) ────────────────────────
-- station_id : clave sintética autoincremental
-- source_id  : id original del JSON (puede repetirse si hay varias versiones)
--
-- La unicidad real es (source_id, number, name, address, latitude, longitude,
-- total_bases): si cualquiera de esos campos cambia → nueva fila.
CREATE TABLE station (
    station_id   SERIAL        PRIMARY KEY,
    source_id    INTEGER       NOT NULL,
    number       VARCHAR(10)   NOT NULL DEFAULT '',
    name         VARCHAR(100)  NOT NULL DEFAULT '',
    address      VARCHAR(200),
    latitude     DECIMAL(10,7),
    longitude    DECIMAL(10,7),
    total_bases  INTEGER       NOT NULL DEFAULT 0,

    -- el UNIQUE garantiza que no hay campos repetidos.
    CONSTRAINT uq_station_version UNIQUE (
        source_id, number, name, address, latitude, longitude, total_bases
    )
);

COMMENT ON COLUMN station.source_id  IS 'id original del JSON de BiciMAD. Puede tener varias filas si los metadatos cambiaron.';
COMMENT ON COLUMN station.station_id IS 'Clave sintética autoincremental. FK en station_snapshot.';

CREATE INDEX idx_station_source_id ON station (source_id);


-- ─── Snapshots de estado (tabla ligera, sin metadatos) ───────────────────────
-- Solo contiene estado operativo. Los metadatos están en station.
-- Filas con no_available = 1 NO entran (filtradas en INSERT.py).
CREATE TABLE station_snapshot (
    captured_at        TIMESTAMP NOT NULL,
    station_id         INTEGER   NOT NULL REFERENCES station(station_id),

    activate           SMALLINT  NOT NULL DEFAULT 1,
    light              SMALLINT  NOT NULL DEFAULT 0,
    dock_bikes         INTEGER   NOT NULL DEFAULT 0,
    free_bases         INTEGER   NOT NULL DEFAULT 0,
    reservations_count INTEGER   NOT NULL DEFAULT 0,

    -- Columna generada: evita recalcular en cada query de saturación
    operative_bases    INTEGER GENERATED ALWAYS AS (dock_bikes + free_bases) STORED,

    PRIMARY KEY (captured_at, station_id)
);

COMMENT ON COLUMN station_snapshot.operative_bases IS
    'dock_bikes + free_bases. Denominador correcto para el cálculo de saturación.';


-- ─── Festivos ────────────────────────────────────────────────────────────────
CREATE TABLE holidays (
    holiday_date DATE PRIMARY KEY
);


-- ─── Índices sobre station_snapshot ──────────────────────────────────────────

CREATE INDEX idx_ss_captured_at
    ON station_snapshot (captured_at);

CREATE INDEX idx_ss_station_id
    ON station_snapshot (station_id);

CREATE INDEX idx_ss_date
    ON station_snapshot ((captured_at::date));

CREATE INDEX idx_ss_isodow
    ON station_snapshot ((EXTRACT(ISODOW FROM captured_at)::int));

-- Cubre la query principal del dashboard: saturación por día de semana + mes
CREATE INDEX idx_ss_dow_month_station
    ON station_snapshot (
        (EXTRACT(ISODOW FROM captured_at)::int),
        (EXTRACT(MONTH  FROM captured_at)::int),
        station_id,
        (EXTRACT(HOUR   FROM captured_at)::int)
    )
    WHERE activate = 1 AND operative_bases > 0;


-- ─── Vista de análisis ───────────────────────────────────────────────────────
CREATE OR REPLACE VIEW v_station_snapshot AS
SELECT
    ss.captured_at,
    ss.station_id,
    st.source_id,
    st.number       AS station_number,
    st.name         AS station_name,
    st.address      AS station_address,
    st.latitude,
    st.longitude,
    st.total_bases,
    ss.activate,
    ss.light,
    ss.dock_bikes,
    ss.free_bases,
    ss.reservations_count,
    ss.operative_bases,
    ROUND(ss.dock_bikes::NUMERIC / NULLIF(ss.operative_bases, 0) * 100, 1) AS sat_operativa_pct,
    ROUND(ss.dock_bikes::NUMERIC / NULLIF(st.total_bases,      0) * 100, 1) AS sat_total_pct
FROM station_snapshot ss
JOIN station st ON st.station_id = ss.station_id;