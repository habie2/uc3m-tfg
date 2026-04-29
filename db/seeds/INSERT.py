#!/usr/bin/env python3
"""
BiciMAD - Script de importación
Convierte el JSONL de mayo 2019 a una base de datos PostgreSQL (o SQLite).

Uso:
    # PostgreSQL (por defecto)
    python 02_import.py --input 201905.json --db-url postgresql://user:pass@localhost/bicimad

    # SQLite (para pruebas rápidas sin servidor)
    python 02_import.py --input 201905.json --sqlite bicimad.db
"""
import json
import argparse
import sys
from datetime import datetime

ENCODING = 'latin-1'
BATCH_SIZE = 500  # Inserciones por lote


def parse_args():
    p = argparse.ArgumentParser(description='Importar BiciMAD JSON a BD relacional')
    p.add_argument('--input', required=True, help='Ruta al fichero 201905.json')
    p.add_argument('--db-url', default=None, help='PostgreSQL DSN (postgresql://...)')
    p.add_argument('--sqlite', default=None, help='Ruta fichero SQLite (alternativa a Postgres)')
    return p.parse_args()


# ── Adaptadores de BD ──────────────────────────────────────────────────────────

class PostgresConn:
    def __init__(self, url):
        import psycopg2
        self.conn = psycopg2.connect(url)
        self.cur  = self.conn.cursor()
        self.placeholder = '%s'

    def execute(self, sql, params=None):
        self.cur.execute(sql, params)

    def executemany(self, sql, rows):
        import psycopg2.extras
        psycopg2.extras.execute_values(self.cur, sql, rows)

    def commit(self):
        self.conn.commit()

    def fetchone(self):
        return self.cur.fetchone()

    def close(self):
        self.cur.close()
        self.conn.close()


class SQLiteConn:
    def __init__(self, path):
        import sqlite3
        self.conn = sqlite3.connect(path)
        self.cur  = self.conn.cursor()
        self.placeholder = '?'
        # Crear tablas SQLite (sin SERIAL ni DECIMAL avanzado)
        self.cur.executescript("""
        CREATE TABLE IF NOT EXISTS station (
            id          INTEGER PRIMARY KEY,
            number      TEXT NOT NULL,
            name        TEXT NOT NULL,
            address     TEXT,
            latitude    REAL,
            longitude   REAL,
            total_bases INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS snapshot (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            captured_at TEXT NOT NULL UNIQUE
        );
        CREATE INDEX IF NOT EXISTS idx_snap_ts ON snapshot(captured_at);
        CREATE TABLE IF NOT EXISTS station_status (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_id        INTEGER NOT NULL REFERENCES snapshot(id),
            station_id         INTEGER NOT NULL REFERENCES station(id),
            activate           INTEGER NOT NULL DEFAULT 1,
            light              INTEGER NOT NULL DEFAULT 0,
            dock_bikes         INTEGER NOT NULL DEFAULT 0,
            free_bases         INTEGER NOT NULL DEFAULT 0,
            reservations_count INTEGER NOT NULL DEFAULT 0,
            no_available       INTEGER NOT NULL DEFAULT 0,
            UNIQUE (snapshot_id, station_id)
        );
        CREATE INDEX IF NOT EXISTS idx_ss_snap    ON station_status(snapshot_id);
        CREATE INDEX IF NOT EXISTS idx_ss_station ON station_status(station_id);
        """)

    def execute(self, sql, params=None):
        self.cur.execute(sql, params or ())

    def executemany(self, sql, rows):
        self.cur.executemany(sql, rows)

    def commit(self):
        self.conn.commit()

    def fetchone(self):
        return self.cur.fetchone()

    def close(self):
        self.cur.close()
        self.conn.close()


# ── Lógica de importación ──────────────────────────────────────────────────────

def upsert_station(db, s):
    """Inserta o actualiza la estación maestra."""
    sql = """
    INSERT INTO station (id, number, name, address, latitude, longitude, total_bases)
    VALUES ({p},{p},{p},{p},{p},{p},{p})
    ON CONFLICT (id) DO UPDATE SET
        name        = EXCLUDED.name,
        address     = EXCLUDED.address,
        latitude    = EXCLUDED.latitude,
        longitude   = EXCLUDED.longitude,
        total_bases = EXCLUDED.total_bases
    """.replace('{p}', db.placeholder)

    db.execute(sql, (
        s['id'],
        str(s.get('number', '')),
        s.get('name', ''),
        s.get('address', ''),
        float(s['latitude'])  if s.get('latitude')  else None,
        float(s['longitude']) if s.get('longitude') else None,
        int(s.get('total_bases', 0)),
    ))


def insert_snapshot(db, ts_str):
    """Inserta el snapshot y devuelve su id."""
    try:
        dt = datetime.fromisoformat(ts_str)
    except ValueError:
        dt = ts_str  # lo pasamos tal cual si ya es cadena ISO

    if isinstance(db, SQLiteConn):
        sql = "INSERT OR IGNORE INTO snapshot (captured_at) VALUES (?)"
        db.execute(sql, (str(dt),))
        db.execute("SELECT id FROM snapshot WHERE captured_at = ?", (str(dt),))
    else:
        sql = ("INSERT INTO snapshot (captured_at) VALUES (%s) "
               "ON CONFLICT (captured_at) DO UPDATE SET captured_at=EXCLUDED.captured_at "
               "RETURNING id")
        db.execute(sql, (dt,))
    row = db.fetchone()
    return row[0]


def build_status_rows(snapshot_id, stations):
    rows = []
    for s in stations:
        rows.append((
            snapshot_id,
            int(s['id']),
            int(s.get('activate', 1)),
            int(s.get('light', 0)),
            int(s.get('dock_bikes', 0)),
            int(s.get('free_bases', 0)),
            int(s.get('reservations_count', 0)),
            int(s.get('no_available', 0)),
        ))
    return rows


def import_file(db, path):
    known_stations = set()
    status_buffer = []
    total_snaps = 0
    total_rows  = 0

    def flush(buf):
        if not buf:
            return
        if isinstance(db, SQLiteConn):
            sql = """INSERT OR IGNORE INTO station_status
                     (snapshot_id, station_id, activate, light, dock_bikes,
                      free_bases, reservations_count, no_available)
                     VALUES (?,?,?,?,?,?,?,?)"""
        else:
            sql = """INSERT INTO station_status
                     (snapshot_id, station_id, activate, light, dock_bikes,
                      free_bases, reservations_count, no_available)
                     VALUES %s
                     ON CONFLICT (snapshot_id, station_id) DO NOTHING"""
        db.executemany(sql, buf)
        db.commit()

    print(f"Leyendo {path} ...")
    with open(path, 'rb') as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line.decode(ENCODING))
            except json.JSONDecodeError as e:
                print(f"  [WARN] línea {lineno}: {e}", file=sys.stderr)
                continue

            ts_str   = obj.get('_id', '')
            stations = obj.get('stations', [])

            # Upsert estaciones nuevas o actualizadas
            for s in stations:
                sid = int(s['id'])
                if sid not in known_stations:
                    upsert_station(db, s)
                    known_stations.add(sid)

            snap_id = insert_snapshot(db, ts_str)
            total_snaps += 1

            status_buffer.extend(build_status_rows(snap_id, stations))
            total_rows += len(stations)

            if len(status_buffer) >= BATCH_SIZE:
                flush(status_buffer)
                status_buffer.clear()
                print(f"  {total_snaps} snapshots / {total_rows} filas de estado...", end='\r')

    flush(status_buffer)
    print(f"\nImportación completada.")
    print(f"  Estaciones únicas : {len(known_stations)}")
    print(f"  Snapshots         : {total_snaps}")
    print(f"  Filas station_status: {total_rows}")


def main():
    args = parse_args()

    if args.sqlite:
        print(f"Conectando a SQLite: {args.sqlite}")
        db = SQLiteConn(args.sqlite)
    elif args.db_url:
        print(f"Conectando a PostgreSQL: {args.db_url}")
        db = PostgresConn(args.db_url)
    else:
        print("ERROR: especifica --db-url o --sqlite", file=sys.stderr)
        sys.exit(1)

    try:
        import_file(db, args.input)
    finally:
        db.close()


if __name__ == '__main__':
    main()
