"""
Indicador 3 — Índice de captura intermodal
============================================
Blueprint: /api/ind3/…

Nota: requiere el GeoJSON de estaciones de metro en data/M4_Estaciones.geojson
y las variables de entorno PGHOST, PGDATABASE, PGUSER, PGPASSWORD (o DB_HOST…).
"""

import json
import os
import pathlib
from flask import Blueprint, jsonify, request
from db import get_conn

bp = Blueprint("ind3", __name__)

BASE_DIR = pathlib.Path(__file__).parent.parent
DB_SCHEMA = os.environ.get("DB_SCHEMA", "public")
INFLUENCE_RADII = [int(x) for x in os.environ.get("INFLUENCE_RADII", "150,300,500").split(",")]
DEFAULT_RADIUS = INFLUENCE_RADII[0]
METRO_GEOJSON = BASE_DIR / os.environ.get("METRO_GEOJSON", "data/M4_Estaciones.geojson")
BICIMAD_HISTORIC_TRIPS = int(os.environ.get("BICIMAD_HISTORIC_TRIPS", "0"))


# ── Carga del GeoJSON de metro ────────────────────────────
def load_metro_stations():
    with open(METRO_GEOJSON, "r", encoding="utf-8") as f:
        gj = json.load(f)
    stations = {}
    for feat in gj["features"]:
        p = feat["properties"]
        geom = feat.get("geometry")
        if not geom or geom["type"] != "Point":
            continue
        lon, lat = geom["coordinates"]
        codigo = str(p.get("CODIGOCTMESTACIONREDMETRO") or p.get("CODIGOESTACION"))
        name = (p.get("DENOMINACION") or "").strip().title()
        lineas = str(p.get("LINEAS") or "").strip()
        st = stations.setdefault(
            codigo,
            {"codigo": codigo, "name": name, "lines": set(),
             "accesses": [], "is_hub": False},
        )
        if not st["name"]:
            st["name"] = name
        for ln in [x.strip() for x in lineas.split(",") if x.strip()]:
            st["lines"].add(ln)
        st["accesses"].append((lon, lat))
        if p.get("MODOINTERCAMBIADOR") not in (None, "", "null"):
            st["is_hub"] = True
    for st in stations.values():
        n = len(st["accesses"])
        st["lat"] = sum(a[1] for a in st["accesses"]) / n
        st["lon"] = sum(a[0] for a in st["accesses"]) / n
        st["lines"] = sorted(st["lines"], key=lambda x: (len(x), x))
    return stations


try:
    METRO = load_metro_stations()
except Exception:
    METRO = {}


# ── Cálculo de captura ────────────────────────────────────
def build_assignment(conn, radius):
    rows = []
    for st in METRO.values():
        for (lon, lat) in st["accesses"]:
            rows.append((st["codigo"], lon, lat))
    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS _metro_access;")
        cur.execute("""
            CREATE TEMP TABLE _metro_access (
                codigo text, geog geography(Point, 4326)
            );
        """)
        cur.executemany(
            "INSERT INTO _metro_access (codigo, geog) "
            "VALUES (%s, ST_SetSRID(ST_MakePoint(%s, %s),4326)::geography);",
            rows,
        )
        cur.execute("CREATE INDEX ON _metro_access USING gist (geog);")
        cur.execute("DROP TABLE IF EXISTS _bici_metro_map;")
        cur.execute(f"""
            CREATE TEMP TABLE _bici_metro_map AS
            SELECT s.number, m.codigo, m.dist_m
            FROM {DB_SCHEMA}.stations_dedup s
            CROSS JOIN LATERAL (
                SELECT a.codigo,
                       ST_Distance(s.geom_4326::geography, a.geog) AS dist_m
                FROM _metro_access a
                WHERE ST_DWithin(s.geom_4326::geography, a.geog, %s)
                ORDER BY s.geom_4326::geography <-> a.geog LIMIT 1
            ) m;
        """, (radius,))
        cur.execute("CREATE INDEX ON _bici_metro_map (number);")
        conn.commit()


def compute_capture(conn, radius):
    import psycopg2.extras
    build_assignment(conn, radius)
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(f"""
            WITH salidas AS (
                SELECT mm.codigo, COUNT(*)::bigint AS n
                FROM {DB_SCHEMA}.trips t
                JOIN _bici_metro_map mm ON mm.number = t.origin_number
                GROUP BY mm.codigo
            ),
            llegadas AS (
                SELECT mm.codigo, COUNT(*)::bigint AS n
                FROM {DB_SCHEMA}.trips t
                JOIN _bici_metro_map mm ON mm.number = t.dest_number
                GROUP BY mm.codigo
            )
            SELECT COALESCE(s.codigo, l.codigo) AS codigo,
                   COALESCE(s.n, 0) AS out_trips,
                   COALESCE(l.n, 0) AS in_trips
            FROM salidas s
            FULL OUTER JOIN llegadas l ON s.codigo = l.codigo;
        """)
        agg = {r["codigo"]: r for r in cur.fetchall()}

        cur.execute(f"""
            SELECT mm.codigo, sd.number, sd.name, mm.dist_m
            FROM _bici_metro_map mm
            JOIN {DB_SCHEMA}.stations_dedup sd ON sd.number = mm.number
            ORDER BY mm.codigo, mm.dist_m;
        """)
        stations_by_node = {}
        for r in cur.fetchall():
            stations_by_node.setdefault(r["codigo"], []).append({
                "number": r["number"],
                "name": r["name"],
                "dist": round(r["dist_m"] or 0),
            })

    nodes = []
    for codigo, st in METRO.items():
        a = agg.get(codigo, {"out_trips": 0, "in_trips": 0})
        out_t = int(a["out_trips"])
        in_t = int(a["in_trips"])
        nodes.append({
            "id": codigo, "name": st["name"],
            "lat": st["lat"], "lon": st["lon"],
            "lines": " · ".join(st["lines"]) if st["lines"] else "—",
            "is_hub": st["is_hub"],
            "out": out_t, "in": in_t, "captured": out_t + in_t,
            "stations": stations_by_node.get(codigo, []),
        })
    return nodes


# ── Endpoints ─────────────────────────────────────────────
@bp.route("/config")
def api_config():
    return jsonify({"radii": INFLUENCE_RADII, "default_radius": DEFAULT_RADIUS})


@bp.route("/capture")
def api_capture():
    radius = int(request.args.get("radius", DEFAULT_RADIUS))
    if radius not in INFLUENCE_RADII:
        radius = DEFAULT_RADIUS
    with get_conn() as conn:
        nodes = compute_capture(conn, radius)
    nodes.sort(key=lambda n: n["captured"], reverse=True)
    return jsonify({"radius": radius, "nodes": nodes})


@bp.route("/stats")
def api_stats():
    radius = int(request.args.get("radius", DEFAULT_RADIUS))
    if radius not in INFLUENCE_RADII:
        radius = DEFAULT_RADIUS
    with get_conn() as conn:
        nodes = compute_capture(conn, radius)
        total_intermodal = sum(n["captured"] for n in nodes)
        if BICIMAD_HISTORIC_TRIPS > 0:
            historic = BICIMAD_HISTORIC_TRIPS
        else:
            import psycopg2.extras
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(f"SELECT COUNT(*) AS c FROM {DB_SCHEMA}.trips;")
                historic = cur.fetchone()["c"] or 1
    top = max(nodes, key=lambda n: n["captured"]) if nodes else None
    return jsonify({
        "radius": radius,
        "total_intermodal": total_intermodal,
        "historic_trips": historic,
        "share_pct": round(total_intermodal / historic * 100, 2),
        "top_node": {"name": top["name"], "captured": top["captured"]} if top else None,
    })


@bp.route("/nodes/<codigo>")
def api_node_detail(codigo):
    radius = int(request.args.get("radius", DEFAULT_RADIUS))
    if radius not in INFLUENCE_RADII:
        radius = DEFAULT_RADIUS
    with get_conn() as conn:
        nodes = compute_capture(conn, radius)
    node = next((n for n in nodes if n["id"] == str(codigo)), None)
    if not node:
        return jsonify({"error": "nodo no encontrado"}), 404
    return jsonify(node)


@bp.route("/health")
def api_health():
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 AS ok;")
                cur.fetchone()
        return jsonify({"db": True, "metro_stations": len(METRO)})
    except Exception as e:
        return jsonify({"db": False, "error": str(e)}), 500
