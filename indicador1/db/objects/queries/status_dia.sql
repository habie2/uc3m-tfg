SELECT
    ss.captured_at,
    st.name,
    ss.dock_bikes,
    ss.free_bases,
    ss.reservations_count,
    ss.no_available,
    ss.activate,
    ss.light
FROM station_status ss
JOIN station st ON st.id = ss.station_id
WHERE DATE(ss.captured_at) = '2019-05-01'
ORDER BY ss.captured_at, st.name;