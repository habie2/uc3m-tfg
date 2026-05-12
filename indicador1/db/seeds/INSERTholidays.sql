-- ═══════════════════════════════════════════════════════
-- BiciMAD · Festivos de Madrid
-- ═══════════════════════════════════════════════════════
-- Ejecutar DESPUÉS de CREATE.sql.
--
-- Uso:
--   psql -U casaos -d bicimad -f INSERTholidays.sql
--
-- Añade aquí los festivos de cada periodo que importes.
-- ON CONFLICT DO NOTHING evita duplicados si lo ejecutas
-- varias veces.
-- ═══════════════════════════════════════════════════════


-- ─── Mayo 2019 (tu dataset actual) ──────────────────────
INSERT INTO holidays (holiday_date) VALUES
    ('2019-05-01'),   -- Día del Trabajador (nacional)
    ('2019-05-02'),   -- Comunidad de Madrid (autonómico)
    ('2019-05-15')    -- San Isidro (Madrid capital)
ON CONFLICT DO NOTHING;


-- ─── 2019 completo ──────────────────────────────────────
-- Descomenta si importas datos del año entero.
/*
INSERT INTO holidays (holiday_date) VALUES
    ('2019-01-01'),   -- Año Nuevo
    ('2019-01-07'),   -- Lunes siguiente a Reyes (traslado)
    ('2019-04-18'),   -- Jueves Santo
    ('2019-04-19'),   -- Viernes Santo
    ('2019-05-01'),   -- Día del Trabajador
    ('2019-05-02'),   -- Comunidad de Madrid
    ('2019-05-15'),   -- San Isidro
    ('2019-08-15'),   -- Asunción de la Virgen
    ('2019-10-12'),   -- Fiesta Nacional
    ('2019-11-01'),   -- Todos los Santos
    ('2019-11-09'),   -- Almudena
    ('2019-12-06'),   -- Constitución
    ('2019-12-09'),   -- Lunes siguiente a Inmaculada (traslado)
    ('2019-12-25')    -- Navidad
ON CONFLICT DO NOTHING;
*/


-- ─── 2024 ────────────────────────────────────────────────
-- Descomenta si importas datos de 2024.
/*
INSERT INTO holidays (holiday_date) VALUES
    ('2024-01-01'),   -- Año Nuevo
    ('2024-01-06'),   -- Reyes
    ('2024-03-28'),   -- Jueves Santo
    ('2024-03-29'),   -- Viernes Santo
    ('2024-05-01'),   -- Día del Trabajador
    ('2024-05-02'),   -- Comunidad de Madrid
    ('2024-05-15'),   -- San Isidro
    ('2024-08-15'),   -- Asunción
    ('2024-10-12'),   -- Fiesta Nacional
    ('2024-11-01'),   -- Todos los Santos
    ('2024-11-09'),   -- Almudena
    ('2024-12-06'),   -- Constitución
    ('2024-12-09'),   -- Lunes siguiente a Inmaculada
    ('2024-12-25')    -- Navidad
ON CONFLICT DO NOTHING;
*/


-- ─── 2025 ────────────────────────────────────────────────
-- Descomenta si importas datos de 2025.
/*
INSERT INTO holidays (holiday_date) VALUES
    ('2025-01-01'),   -- Año Nuevo
    ('2025-01-06'),   -- Reyes
    ('2025-04-17'),   -- Jueves Santo
    ('2025-04-18'),   -- Viernes Santo
    ('2025-05-01'),   -- Día del Trabajador
    ('2025-05-02'),   -- Comunidad de Madrid
    ('2025-05-15'),   -- San Isidro
    ('2025-08-15'),   -- Asunción
    ('2025-10-12'),   -- Fiesta Nacional (domingo → no trasladan)
    ('2025-11-01'),   -- Todos los Santos
    ('2025-11-09'),   -- Almudena (domingo → no trasladan)
    ('2025-12-06'),   -- Constitución
    ('2025-12-08'),   -- Inmaculada
    ('2025-12-25')    -- Navidad
ON CONFLICT DO NOTHING;
*/