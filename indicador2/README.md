# Indicador 2 — Tránsito por tipo de vía

Pipeline completo: SQL + ETL Python + API Flask + Visualizador.

## Pre-requisitos

- PostgreSQL 14+ con PostGIS 3.1+
- Tabla `public.stations` ya creada con columnas:
  `station_id, source_id, number, name, address, latitude, longitude, total_bases`
- Extracto OSM de Madrid:
  ```bash
  osmium extract -b -3.89,40.30,-3.52,40.55 spain-latest.osm.pbf -o madrid.osm.pbf
  ```
- OpenRouteService en Docker:
  ```bash
  docker run -d -p 8080:8080 \
    -v $(pwd)/madrid.osm.pbf:/home/ors/ors-core/data/osm_file.pbf \
    -e ors.engine.profiles.cycling-regular.enabled=true \
    openrouteservice/openrouteservice
  ```
- Python 3.11+: `psycopg2-binary`, `requests`, `shapely`, `flask`, `flask-cors`

## Estructura

```
sql/
  01_schema.sql                  # vista stations_dedup + tablas
  02_seed_highway_categories.sql # 7 categorías + mapeo OSM
  03_generate_grid.sql           # red viaria etiquetada + grid 500x500m
etl/
  config.py                      # DSN y URL de ORS por env
  load_trips.py                  # JSON Mongo → trips (traduce station_id→number)
  compute_routes.py              # rutas óptimas con ORS (1 por par OD único)
  decompose_routes.py            # cruce ruta × OSM × grid → metros por (celda, tipo)
api/
  app.py                         # API Flask
  requirements.txt
visualizador_indicador2.html     # frontend (Leaflet)
```

## Orden de ejecución

```bash
# 1) Crear vista de estaciones, tablas e índices
psql -d tu_bd -f sql/01_schema.sql

# 2) Sembrar categorías de tipo de vía
psql -d tu_bd -f sql/02_seed_highway_categories.sql

# 3) Cargar viajes desde el JSON
export BICIMAD_DSN="host=localhost dbname=tu_bd user=... password=..."
python etl/load_trips.py --input data/trips.json --truncate

# 4) Cargar red viaria con osm2pgsql
osm2pgsql --slim --hstore -d tu_bd madrid.osm.pbf

# 5) Poblar osm_ways y generar grid
psql -d tu_bd -f sql/03_generate_grid.sql

# 6) Calcular rutas con ORS (una por par OD)
export ORS_URL="http://localhost:8080/ors"
python etl/compute_routes.py --workers 8

# 7) Descomponer en (celda, tipo) → metros y refrescar matviews
python etl/decompose_routes.py --refresh
```

## Arrancar la API

```bash
cd api/
pip install -r requirements.txt
python app.py                              # dev en http://localhost:5000
# o en producción:
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

## Endpoints

| Método | Ruta                              | Descripción                                  |
|--------|-----------------------------------|----------------------------------------------|
| GET    | `/api/health`                     | Health check                                 |
| GET    | `/api/categories`                 | Catálogo de tipos de vía                     |
| GET    | `/api/categories/intensity`       | Intensidad agregada por tipo + porcentaje    |
| GET    | `/api/stats`                      | Total, celda más intensa, tipo dominante     |
| GET    | `/api/cells`                      | Grid completo con intensidad de cada celda   |
| GET    | `/api/cells/<id>`                 | Detalle de celda + distribución por tipo     |
| GET    | `/api/cells/<id>/ways`            | Vías OSM dentro de la celda (GeoJSON)        |

## Notas de diseño

- **Deduplicación de estaciones**: la vista `stations_dedup` aplica la regla
  pedida (1→única, 2→station_id menor, 3+→station_id mayor) sobre tu tabla
  `public.stations`. El resto del esquema referencia por `number`, la clave
  estable.
- **Traducción station_id → number** en `load_trips.py`: el JSON de BiciMAD
  trae station_id; se traduce a number durante la carga vía join con
  `public.stations` (no `stations_dedup`, para aceptar también los station_id
  duplicados que la dedup descarta).
- **Sin filtros temporales**: todas las consultas son agregado total.
- **Una llamada a ORS por par OD**: la huella geométrica se cachea en
  `od_pairs` + `od_pair_segments` y se reutiliza al sumar viajes.
