"""
ETL paso 3 — Descomposición de rutas OD en segmentos (celda, tipo de vía).

Cruza cada ruta de `od_pairs` con osm_ways y grid_cells y guarda en
`od_pair_segments` cuántos metros aporta cada combinación celda × categoría.

Todo el trabajo geométrico se hace en SQL (PostGIS). Python solo orquesta.

Uso:
    python decompose_routes.py            # todos los pendientes
    python decompose_routes.py --od-id N  # uno concreto
    python decompose_routes.py --refresh  # también refresca matviews
"""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import argparse
import logging

import psycopg2

from config import DB_DSN

log = logging.getLogger("decompose_routes")


DECOMPOSE_SQL = """
WITH route AS (
    SELECT od_id, geom_25830
    FROM od_pairs
    WHERE od_id = %(od_id)s
),
route_buf AS (
    SELECT od_id, ST_Buffer(geom_25830, 6) AS buf, geom_25830
    FROM route
),
matched_ways AS (
    SELECT
        r.od_id,
        w.category_code,
        ST_Intersection(w.geom_25830, r.buf) AS seg_geom
    FROM osm_ways w
    JOIN route_buf r
      ON w.geom_25830 && r.buf
     AND ST_Intersects(w.geom_25830, r.buf)
),
per_cell AS (
    SELECT
        m.od_id,
        c.cell_id,
        m.category_code,
        ST_Length(ST_Intersection(m.seg_geom, c.geom_25830)) AS length_m
    FROM matched_ways m
    JOIN grid_cells c
      ON c.geom_25830 && m.seg_geom
     AND ST_Intersects(c.geom_25830, m.seg_geom)
)
INSERT INTO od_pair_segments (od_id, cell_id, category_code, length_m)
SELECT od_id, cell_id, category_code, SUM(length_m)
FROM per_cell
WHERE length_m > 0
GROUP BY od_id, cell_id, category_code;
"""

FETCH_PENDING_SQL = """
SELECT p.od_id
FROM od_pairs p
LEFT JOIN od_pair_segments s ON s.od_id = p.od_id
WHERE p.geom_25830 IS NOT NULL
  AND s.od_id IS NULL
ORDER BY p.od_id;
"""

CLEAR_OD_SQL = "DELETE FROM od_pair_segments WHERE od_id = %s;"


def decompose_one(cur, od_id: int) -> int:
    cur.execute(CLEAR_OD_SQL, (od_id,))
    cur.execute(DECOMPOSE_SQL, {"od_id": od_id})
    return cur.rowcount


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--od-id", type=int, default=None)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")

    with psycopg2.connect(DB_DSN) as conn, conn.cursor() as cur:
        if args.od_id is not None:
            ids = [args.od_id]
        else:
            cur.execute(FETCH_PENDING_SQL)
            ids = [row[0] for row in cur.fetchall()]

        log.info("Pares OD a descomponer: %d", len(ids))

        for i, od_id in enumerate(ids, start=1):
            rows = decompose_one(cur, od_id)
            if i % 100 == 0 or i == len(ids):
                conn.commit()
                log.info("Procesados %d / %d (último: od=%d, %d segmentos)",
                         i, len(ids), od_id, rows)

        if args.refresh:
            log.info("Refrescando matviews...")
            cur.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY cell_traffic;")
            cur.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY cell_intensity;")
            cur.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY category_intensity;")
            conn.commit()
            log.info("Matviews refrescadas.")


if __name__ == "__main__":
    main()