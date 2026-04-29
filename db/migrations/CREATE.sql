-- ============================================================
-- BiciMAD - Modelo Relacional
-- Mayo 2019
-- ============================================================

-- Borrar todo lo existente
DROP VIEW  IF EXISTS v_station_status CASCADE;
DROP VIEW  IF EXISTS v_indicadores    CASCADE;
DROP TABLE IF EXISTS station_status   CASCADE;
DROP TABLE IF EXISTS snapshot         CASCADE;
DROP TABLE IF EXISTS station          CASCADE;

-- Tabla de estaciones (datos estáticos / maestros)
CREATE TABLE station (
    id           INTEGER PRIMARY KEY,
    number       VARCHAR(10)  NOT NULL,
    name         VARCHAR(100) NOT NULL,
    address      VARCHAR(200),
    latitude     DECIMAL(10,7),
    longitude    DECIMAL(10,7),
    total_bases  INTEGER      NOT NULL
);

-- Tabla de estado de cada estación en cada momento
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

CREATE INDEX idx_station_status_captured_at ON station_status(captured_at);
CREATE INDEX idx_station_status_station_id  ON station_status(station_id);

-- Vista de análisis
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