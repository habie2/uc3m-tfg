-- ============================================================
-- BiciMAD - Consultas de ejemplo
-- ============================================================

-- 1. Número de snapshots y rango temporal
SELECT
    COUNT(*)                         AS total_snapshots,
    MIN(captured_at)                 AS primer_snapshot,
    MAX(captured_at)                 AS ultimo_snapshot
FROM snapshot;


-- 2. Estaciones con más bicis disponibles en promedio (mayo 2019)
SELECT
    st.name,
    st.address,
    ROUND(AVG(ss.dock_bikes), 1)     AS media_bicis,
    ROUND(AVG(ss.free_bases), 1)     AS media_bases_libres,
    st.total_bases
FROM station_status ss
JOIN station st ON st.id = ss.station_id
GROUP BY st.id, st.name, st.address, st.total_bases
ORDER BY media_bicis DESC
LIMIT 10;


-- 3. Ocupación por hora del día (perfil de uso diario)
SELECT
    EXTRACT(HOUR FROM sn.captured_at)  AS hora,
    ROUND(AVG(ss.dock_bikes)::NUMERIC, 2)   AS media_bicis_ancladas,
    ROUND(AVG(ss.free_bases)::NUMERIC, 2)   AS media_bases_libres
FROM station_status ss
JOIN snapshot sn ON sn.id = ss.snapshot_id
GROUP BY hora
ORDER BY hora;


-- 4. Snapshots en los que una estación concreta estuvo vacía (sin bicis)
SELECT
    sn.captured_at,
    st.name,
    ss.dock_bikes,
    ss.free_bases
FROM station_status ss
JOIN snapshot sn ON sn.id = ss.snapshot_id
JOIN station  st ON st.id  = ss.station_id
WHERE st.name = 'Puerta del Sol A'
  AND ss.dock_bikes = 0
ORDER BY sn.captured_at;


-- 5. Estaciones que más veces estuvieron completamente llenas (sin bases libres)
SELECT
    st.name,
    COUNT(*) AS veces_llena
FROM station_status ss
JOIN station st ON st.id = ss.station_id
WHERE ss.free_bases = 0
  AND ss.activate = 1
GROUP BY st.name
ORDER BY veces_llena DESC
LIMIT 10;


-- 6. Evolución de una estación a lo largo del día (1 mayo 2019)
SELECT
    sn.captured_at,
    ss.dock_bikes,
    ss.free_bases,
    ss.reservations_count
FROM station_status ss
JOIN snapshot sn ON sn.id = ss.snapshot_id
JOIN station  st ON st.id  = ss.station_id
WHERE st.name = 'Puerta del Sol A'
  AND DATE(sn.captured_at) = '2019-05-01'
ORDER BY sn.captured_at;


-- 7. Vista rápida de ocupación en un momento concreto (usando la vista)
SELECT station_name, station_number, dock_bikes, free_bases, occupancy_pct
FROM v_station_status
WHERE captured_at = (SELECT MAX(captured_at) FROM snapshot)
ORDER BY occupancy_pct DESC;


-- 8. estaciones totales
select * from station;
