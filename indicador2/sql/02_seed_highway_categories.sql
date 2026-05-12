-- =============================================================================
-- SEED — 7 categorías de tipo de vía + mapeo desde tags OSM `highway`
-- =============================================================================

INSERT INTO highway_categories
    (category_code, display_name, display_order, color_hex)
VALUES
    ('cycleway',  'Vía ciclista',    1, '#2E8B57'),
    ('quiet',     'Calle tranquila', 2, '#7FB069'),
    ('tertiary',  'Vía terciaria',   3, '#E1B16A'),
    ('secondary', 'Vía secundaria',  4, '#D98E48'),
    ('primary',   'Vía primaria',    5, '#C25A3C'),
    ('trunk',     'Vía rápida',      6, '#8C3A2D'),
    ('service',   'Servicio/Otros',  7, '#9C9387')
ON CONFLICT (category_code) DO NOTHING;


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
