-- ═══════════════════════════════════════════════════════
-- BiciMAD · Modelo Relacional Completo
-- ═══════════════════════════════════════════════════════
-- Incluye las tablas originales + holidays para el dashboard.
-- Ejecutar ANTES de importar datos con INSERT.py.
--
-- Uso:
--   psql -h host -U casaos -d bicimad -f CREATE.sql
-- ═══════════════════════════════════════════════════════

-- Borrar todo lo existente
DROP VIEW  IF EXISTS v_station_status CASCADE;
DROP TABLE IF EXISTS station_status   CASCADE;
DROP TABLE IF EXISTS holidays         CASCADE;
DROP TABLE IF EXISTS station          CASCADE;


-- ─── Estaciones (datos maestros) ─────────────────────────
CREATE TABLE station (
    id           INTEGER PRIMARY KEY,
    number       VARCHAR(10)  NOT NULL,
    name         VARCHAR(100) NOT NULL,
    address      VARCHAR(200),
    latitude     DECIMAL(10,7),
    longitude    DECIMAL(10,7),
    total_bases  INTEGER      NOT NULL
);


-- ─── Estado de cada estación en cada momento ─────────────
CREATE TABLE station_status (
    captured_at        TIMESTAMP NOT NULL,
    station_id         INTEGER   NOT NULL REFERENCES station(id),
    activate           SMALLINT  NOT NULL DEFAULT 1,
    light              SMALLINT  NOT NULL DEFAULT 0,
    dock_bikes         INTEGER   NOT NULL DEFAULT 0,
    free_bases         INTEGER   NOT NULL DEFAULT 0,
    reservations_count INTEGER   NOT NULL DEFAULT 0,
    no_available       SMALLINT  NOT NULL DEFAULT 0,
    PRIMARY KEY (captured_at, station_id)
);


-- ─── Festivos ────────────────────────────────────────────
CREATE TABLE holidays (
    holiday_date DATE PRIMARY KEY
);


-- ─── Índices ─────────────────────────────────────────────

-- Originales
CREATE INDEX idx_station_status_captured_at
    ON station_status(captured_at);

CREATE INDEX idx_station_status_station_id
    ON station_status(station_id);

-- Para el dashboard (queries agrupadas por hora y día de la semana)
CREATE INDEX idx_ss_date
    ON station_status ((captured_at::date));

CREATE INDEX idx_ss_isodow
    ON station_status ((EXTRACT(ISODOW FROM captured_at)::int));


-- ─── Vista de análisis ──────────────────────────────────
CREATE OR REPLACE VIEW v_station_status AS
SELECT
    ss.captured_at,
    st.id          AS station_id,
    st.number      AS station_number,
    st.name        AS station_name,
    st.address,
    st.latitude,
    st.longitude,
    st.total_bases,
    ss.activate,
    ss.light,
    ss.dock_bikes,
    ss.free_bases,
    ss.reservations_count,
    ss.no_available,
    ROUND(ss.dock_bikes::NUMERIC / NULLIF(st.total_bases, 0) * 100, 1) AS ocupacion_pct
FROM station_status ss
JOIN station st ON st.id = ss.station_id;