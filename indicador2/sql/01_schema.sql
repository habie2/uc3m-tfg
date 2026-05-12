-- =============================================================================
-- INDICADOR 2 — Tránsito por tipo de vía
-- Esquema PostgreSQL + PostGIS
-- =============================================================================
-- ASUME que ya existe public.station con columnas:
--   station_id, source_id, number, name, address, latitude, longitude, total_bases
-- NO la modificamos. Creamos una VISTA encima.
--
-- Convenciones:
--   * Todo vive en `public` (esquema por defecto).
--   * SRID 4326 (WGS84) para almacenamiento y servicio al cliente.
--   * SRID 25830 (ETRS89 / UTM 30N) para cálculos métricos sobre Madrid.
--   * `number` es la clave estable de estación: una estación conceptual = un number.
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS postgis;


-- =============================================================================
-- 1. ESTACIONES — vista deduplicada sobre tu tabla existente
-- =============================================================================
-- Regla de deduplicación por `number`:
--   * 1 fila   → se queda esa
--   * 2 filas  → station_id MÁS BAJO
--   * 3+ filas → station_id MÁS ALTO
-- =============================================================================

CREATE OR REPLACE VIEW stations_dedup AS
WITH counts AS (
    SELECT number, COUNT(*) AS n
    FROM public.station
    GROUP BY number
),
picked AS (
    SELECT
        s.*,
        c.n AS dup_count,
        ROW_NUMBER() OVER (
            PARTITION BY s.number
            ORDER BY
                CASE
                    WHEN c.n >= 3 THEN -s.station_id  -- 3+ → mayor station_id primero
                    ELSE             s.station_id     -- 1 o 2 → menor station_id primero
                END
        ) AS rk
    FROM public.station s
    JOIN counts c USING (number)
)
SELECT
    number,
    station_id,
    source_id,
    name,
    address,
    latitude,
    longitude,
    total_bases,
    ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)                AS geom_4326,
    ST_Transform(ST_SetSRID(ST_MakePoint(longitude, latitude), 4326),
                 25830)                                                AS geom_25830
FROM picked
WHERE rk = 1;

CREATE INDEX IF NOT EXISTS idx_stations_number ON public.station (number);


-- =============================================================================
-- 2. VIAJES
-- =============================================================================
-- Enlace por `number`, NO por station_id. Si en el futuro corriges duplicados
-- de estaciones y cambian los station_id, los viajes históricos no se rompen.
-- =============================================================================
CREATE TABLE IF NOT EXISTS trips (
    trip_id             BIGSERIAL PRIMARY KEY,
    user_day_code       TEXT,
    origin_number       TEXT NOT NULL,
    dest_number         TEXT NOT NULL,
    idunplug_base       INTEGER,
    idplug_base         INTEGER,
    user_type           SMALLINT,
    age_range           SMALLINT,
    zip_code            TEXT,
    travel_time         INTEGER,                    -- segundos
    unplug_hourtime     TIMESTAMPTZ NOT NULL,
    raw_track           JSONB
);

CREATE INDEX IF NOT EXISTS idx_trips_od ON trips (origin_number, dest_number);


-- =============================================================================
-- 3. TIPOS DE VÍA
-- =============================================================================
CREATE TABLE IF NOT EXISTS highway_categories (
    category_code   TEXT PRIMARY KEY,
    display_name    TEXT NOT NULL,
    display_order   SMALLINT NOT NULL,
    color_hex       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS highway_mapping (
    osm_highway     TEXT PRIMARY KEY,
    category_code   TEXT NOT NULL REFERENCES highway_categories(category_code)
);


-- =============================================================================
-- 4. RED VIARIA ETIQUETADA
-- =============================================================================
CREATE TABLE IF NOT EXISTS osm_ways (
    osm_id          BIGINT,
    osm_highway     TEXT NOT NULL,
    category_code   TEXT NOT NULL REFERENCES highway_categories(category_code),
    name            TEXT,
    geom_4326       GEOMETRY(LineString, 4326) NOT NULL,
    geom_25830      GEOMETRY(LineString, 25830) NOT NULL,
    length_m        DOUBLE PRECISION NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_osm_ways_geom_25830 ON osm_ways USING GIST (geom_25830);
CREATE INDEX IF NOT EXISTS idx_osm_ways_geom_4326  ON osm_ways USING GIST (geom_4326);
CREATE INDEX IF NOT EXISTS idx_osm_ways_category   ON osm_ways (category_code);


-- =============================================================================
-- 5. GRID 500×500 m
-- =============================================================================
CREATE TABLE IF NOT EXISTS grid_cells (
    cell_id         SERIAL PRIMARY KEY,
    grid_x          INTEGER NOT NULL,
    grid_y          INTEGER NOT NULL,
    centroid_lat    DOUBLE PRECISION NOT NULL,
    centroid_lon    DOUBLE PRECISION NOT NULL,
    label           TEXT,
    geom_4326       GEOMETRY(Polygon, 4326) NOT NULL,
    geom_25830      GEOMETRY(Polygon, 25830) NOT NULL,
    UNIQUE (grid_x, grid_y)
);

CREATE INDEX IF NOT EXISTS idx_cells_geom_4326  ON grid_cells USING GIST (geom_4326);
CREATE INDEX IF NOT EXISTS idx_cells_geom_25830 ON grid_cells USING GIST (geom_25830);


-- =============================================================================
-- 6. PARES OD
-- =============================================================================
CREATE TABLE IF NOT EXISTS od_pairs (
    od_id               SERIAL PRIMARY KEY,
    origin_number       TEXT NOT NULL,
    dest_number         TEXT NOT NULL,
    num_trips           INTEGER NOT NULL DEFAULT 0,
    route_distance_m    DOUBLE PRECISION,
    route_duration_s    DOUBLE PRECISION,
    geom_4326           GEOMETRY(LineString, 4326),
    geom_25830          GEOMETRY(LineString, 25830),
    computed_at         TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (origin_number, dest_number)
);

CREATE INDEX IF NOT EXISTS idx_od_geom_25830 ON od_pairs USING GIST (geom_25830);


-- =============================================================================
-- 7. SEGMENTOS OD (celda × tipo → metros)
-- =============================================================================
CREATE TABLE IF NOT EXISTS od_pair_segments (
    od_id           INTEGER NOT NULL REFERENCES od_pairs(od_id) ON DELETE CASCADE,
    cell_id         INTEGER NOT NULL REFERENCES grid_cells(cell_id),
    category_code   TEXT    NOT NULL REFERENCES highway_categories(category_code),
    length_m        DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (od_id, cell_id, category_code)
);

CREATE INDEX IF NOT EXISTS idx_segments_cell     ON od_pair_segments (cell_id);
CREATE INDEX IF NOT EXISTS idx_segments_category ON od_pair_segments (category_code);


-- =============================================================================
-- 8. AGREGADOS (matviews) — TOTAL AGREGADO, sin filtros temporales
-- =============================================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS cell_traffic AS
SELECT
    s.cell_id,
    s.category_code,
    SUM(s.length_m * p.num_trips) AS meters
FROM od_pair_segments s
JOIN od_pairs p USING (od_id)
GROUP BY s.cell_id, s.category_code;

CREATE UNIQUE INDEX IF NOT EXISTS idx_cell_traffic_pk
    ON cell_traffic (cell_id, category_code);
CREATE INDEX IF NOT EXISTS idx_cell_traffic_cell ON cell_traffic (cell_id);


CREATE MATERIALIZED VIEW IF NOT EXISTS cell_intensity AS
SELECT cell_id, SUM(meters) AS total_meters
FROM cell_traffic
GROUP BY cell_id;

CREATE UNIQUE INDEX IF NOT EXISTS idx_cell_intensity_pk ON cell_intensity (cell_id);


CREATE MATERIALIZED VIEW IF NOT EXISTS category_intensity AS
SELECT category_code, SUM(meters) AS total_meters
FROM cell_traffic
GROUP BY category_code;

CREATE UNIQUE INDEX IF NOT EXISTS idx_category_intensity_pk
    ON category_intensity (category_code);


-- =============================================================================
-- 9. FUNCIONES DE UTILIDAD
-- =============================================================================

CREATE OR REPLACE FUNCTION get_cell_distribution(p_cell_id INTEGER)
RETURNS TABLE (
    category_code TEXT,
    display_name  TEXT,
    color_hex     TEXT,
    meters        DOUBLE PRECISION,
    pct           DOUBLE PRECISION
) AS $$
    WITH base AS (
        SELECT ct.category_code, ct.meters
        FROM cell_traffic ct
        WHERE ct.cell_id = p_cell_id
    ),
    total AS (SELECT NULLIF(SUM(meters), 0) AS t FROM base)
    SELECT
        b.category_code,
        hc.display_name,
        hc.color_hex,
        b.meters,
        ROUND((b.meters / total.t * 100)::numeric, 2)::double precision AS pct
    FROM base b
    JOIN highway_categories hc USING (category_code)
    CROSS JOIN total
    ORDER BY hc.display_order;
$$ LANGUAGE SQL STABLE;


CREATE OR REPLACE FUNCTION get_cell_ways(p_cell_id INTEGER)
RETURNS TABLE (
    osm_id          BIGINT,
    category_code   TEXT,
    color_hex       TEXT,
    name            TEXT,
    geom_geojson    TEXT
) AS $$
    SELECT
        w.osm_id,
        w.category_code,
        hc.color_hex,
        w.name,
        ST_AsGeoJSON(ST_Intersection(w.geom_4326, c.geom_4326))::text
    FROM osm_ways w
    JOIN grid_cells c ON c.cell_id = p_cell_id
    JOIN highway_categories hc USING (category_code)
    WHERE ST_Intersects(w.geom_25830, c.geom_25830);
$$ LANGUAGE SQL STABLE;