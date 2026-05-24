"""
Indicador 2 — Tránsito por tipo de vía
========================================
Blueprint: /api/ind2/…
"""

import json
from flask import Blueprint, jsonify, abort
from db import query

bp = Blueprint("ind2", __name__)


@bp.route("/health")
def health():
    try:
        query("SELECT 1 AS ok", one=True)
        return jsonify(status="ok")
    except Exception as exc:
        return jsonify(status="error", error=str(exc)), 500


@bp.route("/categories")
def categories():
    rows = query("""
        SELECT category_code, display_name, display_order, color_hex
        FROM highway_categories ORDER BY display_order
    """)
    return jsonify(rows)


@bp.route("/categories/intensity")
def categories_intensity():
    rows = query("""
        WITH base AS (
            SELECT ci.category_code, ci.total_meters
            FROM category_intensity ci
        ),
        total AS (SELECT NULLIF(SUM(total_meters), 0) AS t FROM base)
        SELECT hc.category_code, hc.display_name, hc.color_hex,
               hc.display_order,
               COALESCE(b.total_meters, 0) AS meters,
               CASE WHEN total.t IS NULL THEN 0
                    ELSE ROUND((COALESCE(b.total_meters,0)/total.t*100)::numeric, 2)
               END::float AS pct
        FROM highway_categories hc
        LEFT JOIN base b USING (category_code)
        CROSS JOIN total
        ORDER BY hc.display_order
    """)
    return jsonify(rows)


@bp.route("/stats")
def stats():
    total = query("""
        SELECT COALESCE(SUM(total_meters), 0)::float AS total_meters
        FROM cell_intensity
    """, one=True) or {"total_meters": 0}

    top_cell = query("""
        SELECT ci.cell_id, ci.total_meters::float AS meters, g.label
        FROM cell_intensity ci JOIN grid_cells g USING (cell_id)
        ORDER BY ci.total_meters DESC LIMIT 1
    """, one=True)

    dominant = query("""
        SELECT hc.category_code, hc.display_name, ci.total_meters::float AS meters
        FROM category_intensity ci JOIN highway_categories hc USING (category_code)
        ORDER BY ci.total_meters DESC LIMIT 1
    """, one=True)

    dominant_pct = 0.0
    if dominant and total["total_meters"]:
        dominant_pct = round(dominant["meters"] / total["total_meters"] * 100, 2)

    return jsonify({
        "total_meters": total["total_meters"],
        "top_cell":     top_cell,
        "dominant":     {**dominant, "pct": dominant_pct} if dominant else None,
    })


@bp.route("/cells")
def cells():
    rows = query("""
        SELECT g.cell_id, g.label, g.centroid_lat, g.centroid_lon,
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


@bp.route("/cells/<int:cell_id>")
def cell_detail(cell_id):
    base = query("""
        SELECT g.cell_id, g.label, g.centroid_lat, g.centroid_lon,
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

    distribution = query("SELECT * FROM get_cell_distribution(%s)", (cell_id,))

    num_trips_row = query("""
        SELECT COALESCE(SUM(p.num_trips), 0)::int AS num_trips
        FROM (SELECT DISTINCT od_id FROM od_pair_segments WHERE cell_id = %s) s
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


@bp.route("/cells/<int:cell_id>/ways")
def cell_ways(cell_id):
    rows = query("SELECT * FROM get_cell_ways(%s)", (cell_id,))
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


@bp.route("/cells/<int:cell_id>/routes")
def cell_routes(cell_id):
    rows = query("""
        SELECT p.od_id, p.num_trips,
               ST_AsGeoJSON(p.geom_4326)::text AS geom_geojson
        FROM od_pair_segments s
        JOIN od_pairs p USING (od_id)
        WHERE s.cell_id = %s AND p.geom_4326 IS NOT NULL
        GROUP BY p.od_id, p.num_trips, p.geom_4326
        ORDER BY p.num_trips DESC LIMIT 200
    """, (cell_id,))

    features = []
    for r in rows:
        if not r["geom_geojson"]:
            continue
        features.append({
            "type": "Feature",
            "geometry": json.loads(r["geom_geojson"]),
            "properties": {
                "od_id":     r["od_id"],
                "num_trips": r["num_trips"],
            },
        })
    return jsonify({"type": "FeatureCollection", "features": features})