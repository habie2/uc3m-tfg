# Indicador 2 — Tránsito por tipo de vía

Pipeline completo. Ejecutar en el orden indicado.

## Pre-requisitos

- PostgreSQL 14+ con PostGIS 3.1+
- Extracto OSM de Madrid (`madrid.osm.pbf`) → recortado con:
  ```bash
  osmium extract -b -3.89,40.30,-3.52,40.55 spain-latest.osm.pbf -o madrid.osm.pbf
  ```
- OpenRouteService en Docker, con el mismo PBF montado:
  ```bash
  docker run -d -p 8080:8080 \
    -v $(pwd)/madrid.osm.pbf:/home/ors/ors-core/data/osm_file.pbf \
    -e ors.engine.profiles.cycling-regular.enabled=true \
    openrouteservice/openrouteservice
  ```
  ```PowerShell
  docker run -d -p 8080:8080 `
    -v "${PWD}/osm-docker/madrid.osm.pbf:/home/ors/ors-core/data/osm_file.pbf" `
    -e "ors.engine.profiles.cycling-regular.enabled=true" `
    openrouteservice/openrouteservice
  ```
- Python 3.11+ con: `psycopg2-binary`, `requests`, `shapely`

## Orden de ejecución

```bash
# 1) Crear esquema, tablas e índices
psql -f sql/01_schema.sql

# 2) Sembrar dimensiones (categorías de vía y mapeo OSM)
psql -f sql/02_seed_highway_categories.sql

# 3) Cargar el catálogo oficial de estaciones (GeoJSON de EMT)
python etl/load_stations.py --input data/stations.geojson

# 4) Cargar viajes del JSON de BiciMAD
python etl/load_trips.py --input data/trips.json --truncate

# 5) Cargar red viaria desde el PBF
osm2pgsql --slim --hstore -d bicimad madrid.osm.pbf

# 6) Poblar osm_ways etiquetadas + generar grid 500x500m
psql -f sql/03_generate_grid.sql

# 7) Calcular rutas óptimas con ORS (una por par OD único)
python etl/compute_routes.py --workers 8

# 8) Descomponer rutas en (celda, tipo) -> metros y refrescar matviews
python etl/decompose_routes.py --refresh
```

A partir de aquí, el visualizador consulta:
- `cell_traffic` — tránsito por celda y tipo
- `cell_intensity` — intensidad total por celda
- `category_intensity` — intensidad total por tipo
- `get_cell_distribution(cell_id)` — para el panel de detalle
- `get_cell_ways(cell_id)` — geometrías para dibujar las vías en colores
