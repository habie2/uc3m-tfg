"""
ETL paso 2 — Cálculo de rutas óptimas con OpenRouteService.

Para cada par (origin_number, dest_number) realmente observado en `trips`,
llama a una instancia local de ORS (perfil cycling-regular) y guarda la
geometría resultante en `od_pairs`.

Optimización: una llamada por par OD único.
Reintentos: 3 con backoff exponencial.
Concurrencia: ThreadPoolExecutor.

Uso:
    python compute_routes.py --workers 8
"""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import argparse
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import psycopg2
import psycopg2.extras
import requests
from shapely.geometry import LineString

from config import DB_DSN, ORS_URL

log = logging.getLogger("compute_routes")


SELECT_PAIRS_SQL = """
SELECT
    t.origin_number,
    t.dest_number,
    COUNT(*)::int       AS num_trips,
    s1.longitude        AS lon_o, s1.latitude AS lat_o,
    s2.longitude        AS lon_d, s2.latitude AS lat_d
FROM trips t
JOIN stations_dedup s1 ON s1.number::text = t.origin_number
JOIN stations_dedup s2 ON s2.number::text = t.dest_number
LEFT JOIN od_pairs p
       ON p.origin_number = t.origin_number
      AND p.dest_number   = t.dest_number
WHERE t.origin_number <> t.dest_number
  AND p.od_id IS NULL
GROUP BY t.origin_number, t.dest_number,
         s1.longitude, s1.latitude, s2.longitude, s2.latitude;
"""

UPSERT_OD_SQL = """
INSERT INTO od_pairs (
    origin_number, dest_number, num_trips,
    route_distance_m, route_duration_s,
    geom_4326, geom_25830
) VALUES (
    %s, %s, %s, %s, %s,
    ST_GeomFromText(%s, 4326),
    ST_Transform(ST_GeomFromText(%s, 4326), 25830)
)
ON CONFLICT (origin_number, dest_number)
DO UPDATE SET
    num_trips        = EXCLUDED.num_trips,
    route_distance_m = EXCLUDED.route_distance_m,
    route_duration_s = EXCLUDED.route_duration_s,
    geom_4326        = EXCLUDED.geom_4326,
    geom_25830       = EXCLUDED.geom_25830,
    computed_at      = NOW();
"""


class ORSError(Exception):
    pass


def fetch_route(lon_o, lat_o, lon_d, lat_d, retries=3):
    body = {
        "coordinates": [[lon_o, lat_o], [lon_d, lat_d]],
        "instructions": False,
        "geometry": True,
    }
    url = f"{ORS_URL}/v2/directions/cycling-regular/geojson"

    for attempt in range(1, retries + 1):
        try:
            r = requests.post(url, json=body, timeout=30)
            r.raise_for_status()
            data = r.json()
            if not data.get("features"):
                raise ORSError("Respuesta sin features")
            return data["features"][0]
        except (requests.RequestException, ORSError) as exc:
            if attempt == retries:
                raise
            wait = 2 ** attempt
            log.warning("ORS error (intento %d/%d): %s — reintento en %ds",
                        attempt, retries, exc, wait)
            time.sleep(wait)
    raise ORSError("unreachable")


def process_pair(pair: dict):
    try:
        feat = fetch_route(float(pair["lon_o"]), float(pair["lat_o"]),
                           float(pair["lon_d"]), float(pair["lat_d"]))
    except Exception as exc:
        log.error("Par %s→%s falló: %s",
                  pair["origin_number"], pair["dest_number"], exc)
        return None

    coords = feat["geometry"]["coordinates"]
    if len(coords) < 2:
        return None

    wkt = LineString(coords).wkt
    summary = feat.get("properties", {}).get("summary", {})

    return (
        pair["origin_number"], pair["dest_number"], pair["num_trips"],
        summary.get("distance"), summary.get("duration"),
        wkt, wkt,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--commit-every", type=int, default=200)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")

    with psycopg2.connect(DB_DSN) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(SELECT_PAIRS_SQL)
            pairs = cur.fetchall()

        log.info("Pares OD pendientes: %d", len(pairs))
        if not pairs:
            return

        ok = fail = 0
        buffer = []

        with ThreadPoolExecutor(max_workers=args.workers) as pool, \
             conn.cursor() as cur:

            futures = {pool.submit(process_pair, p): p for p in pairs}
            for fut in as_completed(futures):
                result = fut.result()
                if result is None:
                    fail += 1
                    continue
                buffer.append(result)
                ok += 1

                if len(buffer) >= args.commit_every:
                    psycopg2.extras.execute_batch(cur, UPSERT_OD_SQL, buffer)
                    conn.commit()
                    log.info("Commit parcial: %d (ok=%d fail=%d)",
                             len(buffer), ok, fail)
                    buffer.clear()

            if buffer:
                psycopg2.extras.execute_batch(cur, UPSERT_OD_SQL, buffer)
                conn.commit()

        log.info("Rutas calculadas: ok=%d, fail=%d", ok, fail)


if __name__ == "__main__":
    main()