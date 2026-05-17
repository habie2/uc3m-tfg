"""
bici.mad · Indicador 3 — Índice de captura intermodal
=====================================================
API que cruza:
  - trips                (viajes BiciMAD)
  - stations_dedup       (estaciones BiciMAD, con geom_4326 PostGIS)
  - M4_Estaciones.geojson(bocas de metro/Cercanías del CRTM)

y expone los endpoints que consume el visualizador (indicador3.html).

Lógica del cálculo
------------------
1. El GeoJSON trae varias filas por estación (una boca por línea/empresa).
   Se agrupan por CODIGOCTMESTACIONREDMETRO -> "estación lógica".
2. Cada estación BiciMAD se asigna a la estación de metro lógica cuya
   BOCA más cercana esté dentro del radio (ST_DWithin sobre geography,
   metros reales). Asignación "a la más cercana" para no doblar conteos.
3. Los viajes se cuentan uniendo trips.origin_number / dest_number con
   stations_dedup.number -> estación de metro asignada.
       salidas  = viajes cuyo ORIGEN cae en el radio del nodo
       llegadas = viajes cuyo DESTINO cae en el radio del nodo
       total    = salidas + llegadas
"""

import json
import os
import pathlib

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import psycopg
from psycopg.rows import dict_row

# --------------------------------------------------------------------------- #
#  Configuración
# --------------------------------------------------------------------------- #
BASE_DIR = pathlib.Path(__file__).parent
load_dotenv(BASE_DIR / ".env")


def env(key, default=None):
    v = os.getenv(key)
    return v if v not in (None, "") else default


DB_SCHEMA = env("DB_SCHEMA", "public")
INFLUENCE_RADII = [int(x) for x in env("INFLUENCE_RADII", "150,300,500").split(",")]
DEFAULT_RADIUS = INFLUENCE_RADII[0]
METRO_GEOJSON = BASE_DIR / env("METRO_GEOJSON", "data/M4_Estaciones.geojson")
BICIMAD_HISTORIC_TRIPS = int(env("BICIMAD_HISTORIC_TRIPS", "0"))

CONNINFO = (
    f"host={env('PGHOST','localhost')} "
    f"port={env('PGPORT','5432')} "
    f"dbname={env('PGDATABASE','bicimad')} "
    f"user={env('PGUSER','postgres')} "
    f"password={env('PGPASSWORD','')}"
)

app = Flask(__name__)
CORS(app)


def get_conn():
    return psycopg.connect(CONNINFO, row_factory=dict_row)


# --------------------------------------------------------------------------- #
#  Carga del GeoJSON de metro -> estación lógica + sus bocas
# --------------------------------------------------------------------------- #
def load_metro_stations():
    """
    Devuelve dict: codigo_ctm -> {
        codigo, name, lines (set), accesses [(lon,lat), ...],
        lat, lon  (centroide para pintar la etiqueta)
    }
    """
    with open(METRO_GEOJSON, "r", encoding="utf-8") as f:
        gj = json.load(f)

    stations = {}
    for feat in gj["features"]:
        p = feat["properties"]
        geom = feat.get("geometry")
        if not geom or geom["type"] != "Point":
            continue
        lon, lat = geom["coordinates"]
        codigo = (
            str(p.get("CODIGOCTMESTACIONREDMETRO")
                or p.get("CODIGOESTACION"))
        )
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
        # MODOINTERCAMBIADOR != null  ->  intercambiador (Cercanías/bus/etc.)
        if p.get("MODOINTERCAMBIADOR") not in (None, "", "null"):
            st["is_hub"] = True

    # centroide de las bocas para la etiqueta del mapa
    for st in stations.values():
        n = len(st["accesses"])
        st["lat"] = sum(a[1] for a in st["accesses"]) / n
        st["lon"] = sum(a[0] for a in st["accesses"]) / n
        st["lines"] = sorted(st["lines"], key=lambda x: (len(x), x))
    return stations


METRO = load_metro_stations()


# --------------------------------------------------------------------------- #
#  Asignación estación BiciMAD -> estación de metro (en SQL, con PostGIS)
#
#  Construye una tabla temporal con TODAS las bocas de metro y resuelve,
#  por estación BiciMAD, la estación lógica de metro cuya boca esté más
#  cerca dentro del radio. Cacheado por radio.
# --------------------------------------------------------------------------- #
_assignment_cache = {}


def build_assignment(conn, radius):
    """
    Crea/actualiza una tabla temporal `bici_metro_map(number, codigo)`
    válida para la conexión actual. Devuelve también un dict
    codigo -> [ {name, number, dist_m, trips_out, trips_in} ] para el detalle.
    """
    # Tabla temporal con las bocas de metro
    rows = []
    for st in METRO.values():
        for (lon, lat) in st["accesses"]:
            rows.append((st["codigo"], lon, lat))

    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS _metro_access;")
        cur.execute("""
            CREATE TEMP TABLE _metro_access (
                codigo text,
                geog   geography(Point, 4326)
            );
        """)
        cur.executemany(
            "INSERT INTO _metro_access (codigo, geog) "
            "VALUES (%s, ST_SetSRID(ST_MakePoint(%s, %s),4326)::geography);",
            rows,
        )
        cur.execute("CREATE INDEX ON _metro_access USING gist (geog);")

        # Para cada estación BiciMAD, la estación de metro lógica más
        # cercana cuya boca esté dentro del radio (LATERAL + KNN).
        cur.execute("DROP TABLE IF EXISTS _bici_metro_map;")
        cur.execute(f"""
            CREATE TEMP TABLE _bici_metro_map AS
            SELECT s.number,
                   m.codigo,
                   m.dist_m
            FROM {DB_SCHEMA}.stations_dedup s
            CROSS JOIN LATERAL (
                SELECT a.codigo,
                       ST_Distance(s.geom_4326::geography, a.geog) AS dist_m
                FROM _metro_access a
                WHERE ST_DWithin(s.geom_4326::geography, a.geog, %s)
                ORDER BY s.geom_4326::geography <-> a.geog
                LIMIT 1
            ) m;
        """, (radius,))
        cur.execute("CREATE INDEX ON _bici_metro_map (number);")
        conn.commit()


def compute_capture(conn, radius):
    """
    Devuelve lista de nodos con sus métricas para el radio dado.
    """
    build_assignment(conn, radius)
    with conn.cursor() as cur:
        # salidas: el origen del viaje cae en el radio del nodo
        # llegadas: el destino del viaje cae en el radio del nodo
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
            SELECT
                COALESCE(s.codigo, l.codigo) AS codigo,
                COALESCE(s.n, 0)             AS out_trips,
                COALESCE(l.n, 0)             AS in_trips
            FROM salidas s
            FULL OUTER JOIN llegadas l ON s.codigo = l.codigo;
        """)
        agg = {r["codigo"]: r for r in cur.fetchall()}

        # estaciones BiciMAD asignadas a cada nodo (para el detalle)
        cur.execute("""
            SELECT mm.codigo, sd.number, sd.name, mm.dist_m
            FROM _bici_metro_map mm
            JOIN {schema}.stations_dedup sd ON sd.number = mm.number
            ORDER BY mm.codigo, mm.dist_m;
        """.format(schema=DB_SCHEMA))
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
        total = out_t + in_t
        nodes.append({
            "id": codigo,
            "name": st["name"],
            "lat": st["lat"],
            "lon": st["lon"],
            "lines": " · ".join(st["lines"]) if st["lines"] else "—",
            "is_hub": st["is_hub"],
            "out": out_t,
            "in": in_t,
            "captured": total,
            "stations": stations_by_node.get(codigo, []),
        })
    return nodes


# --------------------------------------------------------------------------- #
#  Endpoints
# --------------------------------------------------------------------------- #
@app.get("/")
def index():
    """Sirve el visualizador directamente desde Flask."""
    return send_from_directory(BASE_DIR, "indicador3.html")


@app.get("/api/config")
def api_config():
    return jsonify({
        "radii": INFLUENCE_RADII,
        "default_radius": DEFAULT_RADIUS,
    })


@app.get("/api/capture")
def api_capture():
    radius = int(request.args.get("radius", DEFAULT_RADIUS))
    if radius not in INFLUENCE_RADII:
        radius = DEFAULT_RADIUS
    with get_conn() as conn:
        nodes = compute_capture(conn, radius)
    nodes.sort(key=lambda n: n["captured"], reverse=True)
    return jsonify({"radius": radius, "nodes": nodes})


@app.get("/api/stats")
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
            with conn.cursor() as cur:
                cur.execute(f"SELECT COUNT(*) AS c FROM {DB_SCHEMA}.trips;")
                historic = cur.fetchone()["c"] or 1
    top = max(nodes, key=lambda n: n["captured"]) if nodes else None
    return jsonify({
        "radius": radius,
        "total_intermodal": total_intermodal,
        "historic_trips": historic,
        "share_pct": round(total_intermodal / historic * 100, 2),
        "top_node": {"name": top["name"], "captured": top["captured"]}
        if top else None,
    })


@app.get("/api/nodes/<codigo>")
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


@app.get("/api/health")
def api_health():
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1 AS ok;")
            cur.fetchone()
        db_ok = True
    except Exception as e:  # noqa: BLE001
        return jsonify({"db": False, "error": str(e)}), 500
    return jsonify({"db": db_ok, "metro_stations": len(METRO)})


if __name__ == "__main__":
    app.run(
        host=env("FLASK_HOST", "0.0.0.0"),
        port=int(env("FLASK_PORT", "5000")),
        debug=True,
    )