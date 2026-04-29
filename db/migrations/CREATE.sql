-- ============================================================
-- BiciMAD - Modelo Relacional
-- Mayo 2019
-- ============================================================

-- Tabla de estaciones (datos estáticos / maestros)
CREATE TABLE IF NOT EXISTS station (
    id           INTEGER PRIMARY KEY,
    number       VARCHAR(10)    NOT NULL,  -- Número de estación (ej: "1a", "1b", "2")
    name         VARCHAR(100)   NOT NULL,
    address      VARCHAR(200),
    latitude     DECIMAL(10,7),
    longitude    DECIMAL(10,7),
    total_bases  INTEGER        NOT NULL   -- Capacidad total de la estación
);

-- Tabla de snapshots temporales
CREATE TABLE IF NOT EXISTS snapshot (
    id           SERIAL PRIMARY KEY,
    captured_at  TIMESTAMP NOT NULL UNIQUE
);

CREATE INDEX IF NOT EXISTS idx_snapshot_captured_at ON snapshot(captured_at);

-- Tabla de estado de cada estación en cada snapshot
CREATE TABLE IF NOT EXISTS station_status (
    id                  SERIAL PRIMARY KEY,
    snapshot_id         INTEGER NOT NULL REFERENCES snapshot(id) ON DELETE CASCADE,
    station_id          INTEGER NOT NULL REFERENCES station(id),
    activate            SMALLINT NOT NULL DEFAULT 1, -- 0=inactiva, 1=activa
    light               SMALLINT NOT NULL DEFAULT 0, -- Indicador de disponibilidad (0,1,2)
    dock_bikes          INTEGER NOT NULL DEFAULT 0,  -- Bicis ancladas
    free_bases          INTEGER NOT NULL DEFAULT 0,  -- Bases libres
    reservations_count  INTEGER NOT NULL DEFAULT 0,  -- Reservas activas
    no_available        SMALLINT NOT NULL DEFAULT 0, -- 0=disponible, 1=no disponible
    UNIQUE (snapshot_id, station_id)
);

CREATE INDEX IF NOT EXISTS idx_station_status_snapshot ON station_status(snapshot_id);
CREATE INDEX IF NOT EXISTS idx_station_status_station  ON station_status(station_id);
CREATE INDEX IF NOT EXISTS idx_station_status_station_snap ON station_status(station_id, snapshot_id);

-- Vista útil: estado completo desnormalizado
CREATE OR REPLACE VIEW v_station_status AS
SELECT
    sn.captured_at,
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
    -- Ocupación calculada
    ROUND(ss.dock_bikes::NUMERIC / NULLIF(st.total_bases, 0) * 100, 1) AS occupancy_pct
FROM station_status ss
JOIN snapshot sn ON sn.id = ss.snapshot_id
JOIN station  st ON st.id = ss.station_id;
