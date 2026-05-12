"""
ETL paso 1 — Carga de viajes BiciMAD desde JSON a PostgreSQL.

Lee el dump de Mongo (un documento por línea) y lo inserta en `trips`.

Punto clave: el JSON trae `idunplug_station` / `idplug_station`, que son
station_id. La tabla `trips` enlaza por `number` (clave conceptual estable).
Los campos `idunplug_station` / `idplug_station` del JSON se corresponden con
`source_id` en la tabla `public.station` (sin 's'). La traducción a `number`
se hace mediante join con esa tabla durante la promoción del staging.

Usamos `public.station` directamente (NO stations_dedup) para aceptar también
los source_id que la dedup descarta: todos los duplicados de un mismo number
comparten el mismo source_id conceptual.

Estrategia:
  1. Cargar todos los viajes en una tabla staging temporal con source_id crudo.
  2. INSERT INTO trips ... SELECT ... JOIN public.station s ON s.source_id ...
     traduciendo a number.

Uso:
    python load_trips.py --input trips.json --truncate
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# Permite ejecutar el script desde cualquier directorio
sys.path.insert(0, str(Path(__file__).parent))

import psycopg2
from psycopg2.extras import execute_batch

from config import DB_DSN

log = logging.getLogger("load_trips")


STAGING_DDL = """
CREATE TEMP TABLE trips_staging (
    user_day_code     TEXT,
    idunplug_station  INTEGER,
    idplug_station    INTEGER,
    idunplug_base     INTEGER,
    idplug_base       INTEGER,
    user_type         SMALLINT,
    age_range         SMALLINT,
    zip_code          TEXT,
    travel_time       INTEGER,
    unplug_hourtime   TIMESTAMPTZ,
    raw_track         JSONB
) ON COMMIT DROP;
"""

STAGING_INSERT_SQL = """
INSERT INTO trips_staging (
    user_day_code, idunplug_station, idplug_station,
    idunplug_base, idplug_base, user_type, age_range,
    zip_code, travel_time, unplug_hourtime, raw_track
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""

# Traducción station_id → number usando la tabla cruda (cualquier station_id
# duplicado mapea al mismo number).
PROMOTE_SQL = """
INSERT INTO trips (
    user_day_code, origin_number, dest_number,
    idunplug_base, idplug_base, user_type, age_range,
    zip_code, travel_time, unplug_hourtime, raw_track
)
SELECT DISTINCT ON (st.trip_row)
    st.user_day_code,
    s1.number::text   AS origin_number,
    s2.number::text   AS dest_number,
    st.idunplug_base, st.idplug_base, st.user_type, st.age_range,
    st.zip_code, st.travel_time, st.unplug_hourtime, st.raw_track
FROM (
    SELECT *, ctid AS trip_row FROM trips_staging
) st
JOIN public.station s1 ON s1.source_id = st.idunplug_station
JOIN public.station s2 ON s2.source_id = st.idplug_station;
"""


def parse_doc(doc: dict) -> tuple | None:
    """Convierte un documento Mongo en fila para staging. None si descartable."""
    try:
        origin = int(doc["idunplug_station"])
        dest   = int(doc["idplug_station"])
    except (KeyError, TypeError, ValueError):
        return None

    ts_raw = doc.get("unplug_hourTime", {}).get("$date")
    if not ts_raw:
        return None
    ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))

    track = doc.get("track")

    return (
        doc.get("user_day_code"),
        origin,
        dest,
        doc.get("idunplug_base"),
        doc.get("idplug_base"),
        doc.get("user_type"),
        doc.get("ageRange"),
        doc.get("zip_code") or None,
        doc.get("travel_time"),
        ts,
        json.dumps(track) if track else None,
    )


def iter_docs(path: Path):
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                log.warning("Línea %d malformada: %s", line_no, exc)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--batch-size", type=int, default=5000)
    parser.add_argument("--truncate", action="store_true",
                        help="Vaciar trips antes de cargar")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")

    with psycopg2.connect(DB_DSN) as conn, conn.cursor() as cur:
        if args.truncate:
            cur.execute("TRUNCATE trips RESTART IDENTITY CASCADE")
            log.info("Tabla trips truncada.")

        cur.execute(STAGING_DDL)

        batch, total, skipped = [], 0, 0
        for doc in iter_docs(args.input):
            row = parse_doc(doc)
            if row is None:
                skipped += 1
                continue
            batch.append(row)
            if len(batch) >= args.batch_size:
                execute_batch(cur, STAGING_INSERT_SQL, batch,
                              page_size=args.batch_size)
                total += len(batch)
                log.info("Staging: %d viajes (acum %d)", len(batch), total)
                batch.clear()

        if batch:
            execute_batch(cur, STAGING_INSERT_SQL, batch, page_size=len(batch))
            total += len(batch)

        log.info("Cargados %d viajes en staging (%d descartados).",
                 total, skipped)

        log.info("Promoviendo a trips con traducción station_id → number...")
        cur.execute(PROMOTE_SQL)
        promoted = cur.rowcount
        conn.commit()
        log.info("Insertados %d viajes en trips. "
                 "(%d en staging quedaron sin estación válida.)",
                 promoted, total - promoted)


if __name__ == "__main__":
    main()