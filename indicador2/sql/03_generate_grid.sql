-- =============================================================================
-- 03 — Generación de red viaria etiquetada y grid de celdas
-- =============================================================================
-- Pre-requisitos:
--   * osm2pgsql ha cargado el extracto en public.planet_osm_line
--   * Tablas trips, highway_categories, highway_mapping están pobladas
--   * La vista stations_dedup ya existe (script 01)
-- =============================================================================

-- ----------------------------------------------------------------------------
-- 3.1 Poblar osm_ways desde planet_osm_line
-- ----------------------------------------------------------------------------
TRUNCATE osm_ways;

INSERT INTO osm_ways (osm_id, osm_highway, category_code, name,
                      geom_4326, geom_25830, length_m)
SELECT
    l.osm_id,
    l.highway                                            AS osm_highway,
    m.category_code,
    l.name,
    ST_Transform(l.way, 4326)                            AS geom_4326,
    ST_Transform(l.way, 25830)                           AS geom_25830,
    ST_Length(ST_Transform(l.way, 25830))                AS length_m
FROM public.planet_osm_line l
JOIN highway_mapping m ON m.osm_highway = l.highway
WHERE l.highway IS NOT NULL;

ANALYZE osm_ways;


-- ----------------------------------------------------------------------------
-- 3.2 Generar grid 500×500 m sobre el bbox de las estaciones (+1 km margen)
-- ----------------------------------------------------------------------------
TRUNCATE grid_cells RESTART IDENTITY CASCADE;

WITH bbox AS (
    SELECT ST_Expand(ST_Extent(geom_25830)::geometry, 1000) AS env
    FROM stations_dedup
),
raw_grid AS (
    SELECT (ST_SquareGrid(500, env)).geom AS geom
    FROM bbox
),
-- Proxy de "celda relevante": contiene una estación o es atravesada por la
-- recta origen→destino de algún viaje. Las celdas que sobren se pueden borrar
-- después de calcular las rutas reales con ORS.
trip_lines AS (
    SELECT DISTINCT ST_MakeLine(s1.geom_25830, s2.geom_25830) AS line
    FROM trips t
    JOIN stations_dedup s1 ON s1.number::text = t.origin_number
    JOIN stations_dedup s2 ON s2.number::text = t.dest_number
    WHERE t.origin_number <> t.dest_number
),
candidates AS (
    SELECT DISTINCT g.geom
    FROM raw_grid g
    WHERE EXISTS (SELECT 1 FROM stations_dedup s
                  WHERE ST_Intersects(s.geom_25830, g.geom))
       OR EXISTS (SELECT 1 FROM trip_lines tl
                  WHERE ST_Intersects(tl.line, g.geom))
),
indexed AS (
    SELECT
        geom,
        ROW_NUMBER() OVER (ORDER BY ST_YMin(geom), ST_XMin(geom)) AS rn,
        MIN(ST_XMin(geom)) OVER () AS x0,
        MIN(ST_YMin(geom)) OVER () AS y0
    FROM candidates
)
INSERT INTO grid_cells (grid_x, grid_y, centroid_lat, centroid_lon,
                        geom_4326, geom_25830)
SELECT
    ROUND((ST_X(ST_Centroid(geom)) - x0) / 500)::int   AS grid_x,
    ROUND((ST_Y(ST_Centroid(geom)) - y0) / 500)::int   AS grid_y,
    ST_Y(ST_Transform(ST_Centroid(geom), 4326))        AS centroid_lat,
    ST_X(ST_Transform(ST_Centroid(geom), 4326))        AS centroid_lon,
    ST_Transform(geom, 4326),
    geom
FROM indexed;

ANALYZE grid_cells;


-- ----------------------------------------------------------------------------
-- 3.3 Etiqueta legible: estación más cercana al centroide
-- ----------------------------------------------------------------------------
UPDATE grid_cells c
SET label = sub.name
FROM (
    SELECT DISTINCT ON (c.cell_id) c.cell_id, s.name
    FROM grid_cells c
    JOIN stations_dedup s ON true
    ORDER BY c.cell_id, ST_Distance(c.geom_25830, s.geom_25830)
) sub
WHERE c.cell_id = sub.cell_id;