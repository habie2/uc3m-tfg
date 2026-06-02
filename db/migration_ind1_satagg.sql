-- ════════════════════════════════════════════════════════════════
-- Indicador 1 — Vista materializada de saturación pre-agregada
-- ════════════════════════════════════════════════════════════════
-- esto se para que al llamar /api/ind1/saturation los datos no tarden tanto
-- sobre todo al principio
-- 
-- 
-- Datos históricos fijos: se calcula UNA vez. Después /saturation
-- lee de aquí (miles de filas) en lugar de recorrer station_snapshot
-- entero (millones) en cada petición.
--
-- Granularidad: una fila por (source_id, año, mes, día_iso, festivo, hora).
-- Guardamos SUMA y CONTEO de saturación, no la media, porque la media
-- se debe recomponer al filtrar:  AVG = SUM(sat_sum) / SUM(sat_cnt).
--
-- Ejecutar una sola vez:
--   psql -d tu_base -f migration_ind1_satagg.sql
-- ════════════════════════════════════════════════════════════════

DROP MATERIALIZED VIEW IF EXISTS mv_ind1_sat_agg;

CREATE MATERIALIZED VIEW mv_ind1_sat_agg AS
SELECT
    st.source_id                                            AS source_id,
    EXTRACT(YEAR   FROM ss.captured_at)::int                AS year,
    EXTRACT(MONTH  FROM ss.captured_at)::int                AS month,
    EXTRACT(ISODOW FROM ss.captured_at)::int                AS iso_dow,
    (h.holiday_date IS NOT NULL)                            AS is_holiday,
    EXTRACT(HOUR   FROM ss.captured_at)::int                AS hora,
    -- Suma y conteo de la saturación operativa por bucket.
    -- Cada snapshot aporta una observación; el AVG final se reconstruye
    -- como SUM(sat_sum)/SUM(sat_cnt) sobre los buckets seleccionados.
    SUM(ss.dock_bikes::float / NULLIF(ss.operative_bases, 0)) AS sat_sum,
    COUNT(*) FILTER (WHERE ss.operative_bases > 0)            AS sat_cnt
FROM station_snapshot ss
JOIN station st            ON st.station_id = ss.station_id
LEFT JOIN holidays h       ON h.holiday_date = ss.captured_at::date
WHERE ss.activate = 1
  AND ss.operative_bases > 0
GROUP BY
    st.source_id,
    EXTRACT(YEAR   FROM ss.captured_at)::int,
    EXTRACT(MONTH  FROM ss.captured_at)::int,
    EXTRACT(ISODOW FROM ss.captured_at)::int,
    (h.holiday_date IS NOT NULL),
    EXTRACT(HOUR   FROM ss.captured_at)::int;

-- Índice para acelerar los filtros del endpoint
CREATE INDEX IF NOT EXISTS idx_mv_ind1_sat_agg
    ON mv_ind1_sat_agg (year, month, iso_dow, is_holiday, hora, source_id);

ANALYZE mv_ind1_sat_agg;
