#!/usr/bin/env python3
"""
BiciMAD - Script de importación
Convierte el JSONL de mayo 2019 a una base de datos PostgreSQL.

Uso:
    python 02_import.py --input 201905.json --db-url "postgresql://user:pass@host/bicimad"
"""
import json
import argparse
import sys
import warnings
from datetime import datetime

import psycopg2
import psycopg2.extras

ENCODING   = 'latin-1'
BATCH_SIZE = 500


# ── Warnings personalizados ────────────────────────────────────────────────────

class MissingFieldWarning(UserWarning):
    """Se lanza cuando un campo esperado no existe en el JSON y se usa un valor por defecto."""
    pass


def warn_default(field, default, context):
    warnings.warn(
        f"Campo '{field}' ausente en {context} → se usa valor por defecto: {repr(default)}",
        MissingFieldWarning,
        stacklevel=2
    )


def get_with_warning(obj, field, default, context):
    """Como dict.get() pero levanta un warning si el campo no está presente."""
    if field not in obj:
        warn_default(field, default, context)
        return default
    return obj[field]


# ── Conexión PostgreSQL ────────────────────────────────────────────────────────

class PostgresConn:
    def __init__(self, url):
        self.conn = psycopg2.connect(url)
        self.cur  = self.conn.cursor()

    def execute(self, sql, params=None):
        self.cur.execute(sql, params)

    def executemany(self, sql, rows):
        psycopg2.extras.execute_values(self.cur, sql, rows)

    def fetchone(self):
        return self.cur.fetchone()

    def commit(self):
        self.conn.commit()

    def close(self):
        self.cur.close()
        self.conn.close()


# ── Lógica de importación ──────────────────────────────────────────────────────

def upsert_station(db, s, context):
    """Inserta o actualiza la estación maestra."""

    number      = get_with_warning(s, 'number',      '',   context)
    name        = get_with_warning(s, 'name',        '',   context)
    address     = get_with_warning(s, 'address',     None, context)
    total_bases = get_with_warning(s, 'total_bases', 0,    context)

    lat = s.get('latitude')
    lon = s.get('longitude')
    if lat is None:
        warn_default('latitude', None, context)
    if lon is None:
        warn_default('longitude', None, context)

    db.execute("""
        INSERT INTO station (id, number, name, address, latitude, longitude, total_bases)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE SET
            name        = EXCLUDED.name,
            address     = EXCLUDED.address,
            latitude    = EXCLUDED.latitude,
            longitude   = EXCLUDED.longitude,
            total_bases = EXCLUDED.total_bases
    """, (
        int(s['id']),
        str(number),
        str(name),
        address,
        float(lat) if lat is not None else None,
        float(lon) if lon is not None else None,
        int(total_bases),
    ))


def build_status_row(captured_at, s, context):
    """Construye la tupla de station_status para una estación, con warnings si faltan campos."""

    activate           = get_with_warning(s, 'activate',           1, context)
    light              = get_with_warning(s, 'light',              0, context)
    dock_bikes         = get_with_warning(s, 'dock_bikes',         0, context)
    free_bases         = get_with_warning(s, 'free_bases',         0, context)
    reservations_count = get_with_warning(s, 'reservations_count', 0, context)
    no_available       = get_with_warning(s, 'no_available',       0, context)

    return (
        captured_at,
        int(s['id']),
        int(activate),
        int(light),
        int(dock_bikes),
        int(free_bases),
        int(reservations_count),
        int(no_available),
    )


def flush(db, buf):
    if not buf:
        return
    db.executemany("""
        INSERT INTO station_status
            (captured_at, station_id, activate, light,
             dock_bikes, free_bases, reservations_count, no_available)
        VALUES %s
        ON CONFLICT (captured_at, station_id) DO NOTHING
    """, buf)
    db.commit()


def import_file(db, path):
    # Activar warnings para que salgan por consola
    warnings.simplefilter('always', MissingFieldWarning)

    known_stations = set()
    status_buffer  = []
    total_snaps    = 0
    total_rows     = 0

    print(f"Leyendo {path} ...")

    with open(path, 'rb') as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            try:
                obj = json.loads(line.decode(ENCODING))
            except json.JSONDecodeError as e:
                print(f"  [ERROR] línea {lineno}: {e}", file=sys.stderr)
                continue

            # Extraer timestamp
            ts_str = obj.get('_id', '')
            if not ts_str:
                print(f"  [ERROR] línea {lineno}: falta campo '_id', se omite el snapshot", file=sys.stderr)
                continue

            try:
                captured_at = datetime.fromisoformat(ts_str)
            except ValueError as e:
                print(f"  [ERROR] línea {lineno}: timestamp inválido '{ts_str}': {e}", file=sys.stderr)
                continue

            stations = obj.get('stations', [])
            if not stations:
                print(f"  [WARN] línea {lineno}: snapshot {ts_str} sin estaciones", file=sys.stderr)

            for s in stations:
                sid     = int(s['id'])
                context = f"snapshot={ts_str}, station_id={sid}"

                if sid not in known_stations:
                    upsert_station(db, s, context)
                    known_stations.add(sid)

                status_buffer.append(build_status_row(captured_at, s, context))
                total_rows += 1

            total_snaps += 1

            if len(status_buffer) >= BATCH_SIZE:
                flush(db, status_buffer)
                status_buffer.clear()
                print(f"  {total_snaps} snapshots / {total_rows} filas procesadas...", end='\r')

    flush(db, status_buffer)

    print(f"\nImportación completada.")
    print(f"  Estaciones únicas    : {len(known_stations)}")
    print(f"  Snapshots            : {total_snaps}")
    print(f"  Filas station_status : {total_rows}")


# ── Entrada ────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description='Importar BiciMAD JSON a PostgreSQL')
    p.add_argument('--input',  required=True, help='Ruta al fichero 201905.json')
    p.add_argument('--db-url', required=True, help='DSN PostgreSQL (postgresql://user:pass@host/db)')
    return p.parse_args()


def main():
    args = parse_args()
    print(f"Conectando a PostgreSQL: {args.db_url}")
    db = PostgresConn(args.db_url)
    try:
        import_file(db, args.input)
    finally:
        db.close()


if __name__ == '__main__':
    main()