"""
API Flask del indicador 2 — Tránsito por tipo de vía.

Endpoints:
    GET /api/health                    → estado del servicio
    GET /api/categories                → catálogo de tipos de vía
    GET /api/categories/intensity      → intensidad agregada por tipo
    GET /api/stats                     → estadísticas globales del sidebar
    GET /api/cells                     → grid + intensidad de cada celda
    GET /api/cells/<cell_id>           → detalle de una celda
    GET /api/cells/<cell_id>/ways      → vías OSM dentro de una celda

Diseño:
    * Conexión por pool (mejor latencia, sin abrir/cerrar en cada request).
    * Cursores con RealDictCursor → dict listos para jsonify.
    * Sin filtros temporales: todas las consultas son del agregado total.
    * CORS abierto al frontend en desarrollo.

Ejecutar:
    pip install flask flask-cors psycopg2-binary
    export BICIMAD_DSN="host=localhost dbname=bicimad user=... password=..."
    python app.py                                  # dev
    gunicorn -w 4 -b 0.0.0.0:5000 app:app          # prod
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from flask import Flask, jsonify, abort, send_file
from flask_cors import CORS
from psycopg2 import pool

# Carga .env desde la raíz del proyecto (un nivel arriba de /api)
load_dotenv(Path(__file__).parent.parent / ".env", override=False)
load_dotenv(Path(__file__).parent / ".env", override=False)

DB_DSN = (
    f"host={os.environ['DB_HOST']} "
    f"port={os.environ.get('DB_PORT', '5432')} "
    f"dbname={os.environ['DB_NAME']} "
    f"user={os.environ['DB_USER']} "
    f"password={os.environ['DB_PASS']}"
)

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("api")

db_pool: pool.ThreadedConnectionPool | None = None


def get_pool() -> pool.ThreadedConnectionPool:
    """Inicializa el pool perezosamente (la primera petición lo crea)."""
    global db_pool
    if db_pool is None:
        db_pool = pool.ThreadedConnectionPool(minconn=1, maxconn=10, dsn=DB_DSN)
    return db_pool


def query(sql: str, params: tuple | dict = (),
          *, one: bool = False) -> list[dict] | dict | None:
    """Ejecuta una consulta y devuelve dicts (o None si one=True y no hay fila)."""
    p = get_pool()
    conn = p.getconn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            if one:
                row = cur.fetchone()
                return dict(row) if row else None
            return [dict(r) for r in cur.fetchall()]
    finally:
        p.putconn(conn)


# --------------------------------------------------------------------------- #
# Flask app
# --------------------------------------------------------------------------- #
app = Flask(__name__)
CORS(app)   # permitir llamadas desde el visualizador en cualquier origen


@app.get("/")
def index():
    return send_file(Path(__file__).parent.parent / "visualizador_indicador2.html")


@app.get("/api/health")
def health():
    try:
        query("SELECT 1 AS ok", one=True)
        return jsonify(status="ok")
    except Exception as exc:
        log.error("health check failed: %s", exc)
        return jsonify(status="error", error=str(exc)), 500


# --------------------------------------------------------------------------- #
# Catálogo de tipos de vía
# --------------------------------------------------------------------------- #
@app.get("/api/categories")
def categories():
    """Devuelve las 7 categorías con orden y color."""
    rows = query("""
        SELECT category_code, display_name, display_order, color_hex
        FROM highway_categories
        ORDER BY display_order
    """)
    return jsonify(rows)


@app.get("/api/categories/intensity")
def categories_intensity():
    """Intensidad por tipo de vía (agregado total) + porcentaje sobre el total."""
    rows = query("""
        WITH base AS (
            SELECT ci.category_code, ci.total_meters
            FROM category_intensity ci
        ),
        total AS (SELECT NULLIF(SUM(total_meters), 0) AS t FROM base)
        SELECT
            hc.category_code,
            hc.display_name,
            hc.color_hex,
            hc.display_order,
            COALESCE(b.total_meters, 0)                     AS meters,
            CASE WHEN total.t IS NULL THEN 0
                 ELSE ROUND((COALESCE(b.total_meters,0)/total.t*100)::numeric, 2)
            END::float                                       AS pct
        FROM highway_categories hc
        LEFT JOIN base b USING (category_code)
        CROSS JOIN total
        ORDER BY hc.display_order
    """)
    return jsonify(rows)


# --------------------------------------------------------------------------- #
# Estadísticas globales (panel "Intensidad global" del sidebar)
# --------------------------------------------------------------------------- #
@app.get("/api/stats")
def stats():
    """Métricas resumen para el panel global."""
    total = query("""
        SELECT COALESCE(SUM(total_meters), 0)::float AS total_meters
        FROM cell_intensity
    """, one=True) or {"total_meters": 0}

    top_cell = query("""
        SELECT ci.cell_id, ci.total_meters::float AS meters, g.label
        FROM cell_intensity ci
        JOIN grid_cells g USING (cell_id)
        ORDER BY ci.total_meters DESC
        LIMIT 1
    """, one=True)

    dominant = query("""
        SELECT hc.category_code, hc.display_name, ci.total_meters::float AS meters
        FROM category_intensity ci
        JOIN highway_categories hc USING (category_code)
        ORDER BY ci.total_meters DESC
        LIMIT 1
    """, one=True)

    dominant_pct = 0.0
    if dominant and total["total_meters"]:
        dominant_pct = round(dominant["meters"] / total["total_meters"] * 100, 2)

    return jsonify({
        "total_meters": total["total_meters"],
        "top_cell":     top_cell,
        "dominant":     {**dominant, "pct": dominant_pct} if dominant else None,
    })


# --------------------------------------------------------------------------- #
# Grid de celdas
# --------------------------------------------------------------------------- #
@app.get("/api/cells")
def cells():
    """Todas las celdas con su intensidad total y bounds (lat/lon).

    Pensado para pintarse en Leaflet de una sola tacada.
    """
    rows = query("""
        SELECT
            g.cell_id,
            g.label,
            g.centroid_lat,
            g.centroid_lon,
            COALESCE(ci.total_meters, 0)::float AS total_meters,
            ST_YMin(g.geom_4326)::float AS south,
            ST_XMin(g.geom_4326)::float AS west,
            ST_YMax(g.geom_4326)::float AS north,
            ST_XMax(g.geom_4326)::float AS east
        FROM grid_cells g
        LEFT JOIN cell_intensity ci USING (cell_id)
        WHERE ci.total_meters > 0
        ORDER BY g.cell_id
    """)
    return jsonify(rows)


# --------------------------------------------------------------------------- #
# Detalle de una celda
# --------------------------------------------------------------------------- #
@app.get("/api/cells/<int:cell_id>")
def cell_detail(cell_id: int):
    """Información completa de una celda para el popup."""
    base = query("""
        SELECT
            g.cell_id, g.label,
            g.centroid_lat, g.centroid_lon,
            COALESCE(ci.total_meters, 0)::float AS total_meters,
            ST_YMin(g.geom_4326)::float AS south,
            ST_XMin(g.geom_4326)::float AS west,
            ST_YMax(g.geom_4326)::float AS north,
            ST_XMax(g.geom_4326)::float AS east
        FROM grid_cells g
        LEFT JOIN cell_intensity ci USING (cell_id)
        WHERE g.cell_id = %s
    """, (cell_id,), one=True)

    if not base:
        abort(404, description=f"Celda {cell_id} no encontrada")

    distribution = query(
        "SELECT * FROM get_cell_distribution(%s)",
        (cell_id,),
    )

    # Número estimado de viajes que cruzan la celda
    # (suma de num_trips de los pares OD cuyos segmentos pasan por la celda)
    num_trips_row = query("""
        SELECT COALESCE(SUM(p.num_trips), 0)::int AS num_trips
        FROM (
            SELECT DISTINCT od_id FROM od_pair_segments WHERE cell_id = %s
        ) s
        JOIN od_pairs p USING (od_id)
    """, (cell_id,), one=True) or {"num_trips": 0}

    return jsonify({
        **base,
        "num_trips":    num_trips_row["num_trips"],
        "distribution": [
            {**r, "meters": float(r["meters"]), "pct": float(r["pct"])}
            for r in distribution
        ],
    })


# --------------------------------------------------------------------------- #
# Vías OSM dentro de una celda
# --------------------------------------------------------------------------- #
@app.get("/api/cells/<int:cell_id>/ways")
def cell_ways(cell_id: int):
    """Geometrías de las vías OSM dentro de la celda, listas para Leaflet.

    Cada feature devuelve geometría GeoJSON ya recortada al polígono de la
    celda, junto con su categoría y color.
    """
    rows = query("SELECT * FROM get_cell_ways(%s)", (cell_id,))
    import json
    features = []
    for r in rows:
        if not r["geom_geojson"]:
            continue
        features.append({
            "type": "Feature",
            "geometry": json.loads(r["geom_geojson"]),
            "properties": {
                "osm_id":        r["osm_id"],
                "category_code": r["category_code"],
                "color_hex":     r["color_hex"],
                "name":          r["name"],
            },
        })
    return jsonify({"type": "FeatureCollection", "features": features})


# --------------------------------------------------------------------------- #
# Manejo de errores
# --------------------------------------------------------------------------- #
@app.get("/api/cells/<int:cell_id>/routes")
def cell_routes(cell_id: int):
    """Rutas OD que cruzan la celda, con su geometría y número de viajes.

    Devuelve un GeoJSON FeatureCollection donde cada feature es una ruta
    y su peso (num_trips) se usa para escalar grosor y opacidad en Leaflet.
    """
    rows = query("""
        SELECT
            p.od_id,
            p.num_trips,
            ST_AsGeoJSON(p.geom_4326)::text AS geom_geojson
        FROM od_pair_segments s
        JOIN od_pairs p USING (od_id)
        WHERE s.cell_id = %s
          AND p.geom_4326 IS NOT NULL
        GROUP BY p.od_id, p.num_trips, p.geom_4326
        ORDER BY p.num_trips DESC
        LIMIT 200
    """, (cell_id,))

    features = []
    for r in rows:
        if not r["geom_geojson"]:
            continue
        import json
        features.append({
            "type": "Feature",
            "geometry": json.loads(r["geom_geojson"]),
            "properties": {
                "od_id":     r["od_id"],
                "num_trips": r["num_trips"],
            },
        })
    return jsonify({"type": "FeatureCollection", "features": features})
def not_found(e):
    return jsonify(error="not_found", message=str(e.description)), 404


@app.errorhandler(500)
def server_error(e):
    log.exception("Error interno")
    return jsonify(error="internal", message=str(e)), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)