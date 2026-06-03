-- =============================================================================
-- SEED — 7 categorías de tipo de vía + mapeo desde tags OSM `highway`
-- =============================================================================
SET client_encoding = 'UTF8';

INSERT INTO highway_categories
    (category_code, display_name, display_order, color_hex)
VALUES
    ('cycleway',  'Vía ciclista',    1, '#9B59B6'),
    ('quiet',     'Calle tranquila', 2, '#2ECC71'),
    ('tertiary',  'Vía terciaria',   3, '#F1C40F'),
    ('secondary', 'Vía secundaria',  4, '#E67E22'),
    ('primary',   'Vía primaria',    5, '#E74C3C'),
    ('trunk',     'Vía rápida',      6, '#3498DB'),
    ('service',   'Servicio/Otros',  7, '#95A5A6')
ON CONFLICT (category_code) DO UPDATE SET
    color_hex    = EXCLUDED.color_hex,
    display_name = EXCLUDED.display_name;


INSERT INTO highway_mapping (osm_highway, category_code) VALUES
    -- Vías ciclistas dedicadas
    ('cycleway',         'cycleway'),
    ('path',             'cycleway'),

    -- Calles tranquilas
    ('residential',      'quiet'),
    ('living_street',    'quiet'),
    ('pedestrian',       'quiet'),

    -- Terciarias
    ('tertiary',         'tertiary'),
    ('tertiary_link',    'tertiary'),
    ('unclassified',     'tertiary'),

    -- Secundarias
    ('secondary',        'secondary'),
    ('secondary_link',   'secondary'),

    -- Primarias
    ('primary',          'primary'),
    ('primary_link',     'primary'),

    -- Vías rápidas
    ('trunk',            'trunk'),
    ('trunk_link',       'trunk'),
    ('motorway',         'trunk'),
    ('motorway_link',    'trunk'),

    -- Servicio y otros
    ('service',          'service'),
    ('track',            'service'),
    ('road',             'service')
ON CONFLICT (osm_highway) DO NOTHING;