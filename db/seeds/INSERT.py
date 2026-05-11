#!/usr/bin/env python3
"""
BiciMAD - Script de importación (station versionada + snapshot ligero)
=======================================================================
Lógica de station:
  - Cada combinación única de (source_id, number, name, address,
    latitude, longitude, total_bases) es una fila en station con
    su propio station_id (SERIAL).
  - Si alguno de esos campos cambia → INSERT de nueva versión.
  - ON CONFLICT DO NOTHING: si ya existe esa combinación exacta,
    se reutiliza el station_id existente.

Lógica de station_snapshot:
  - Filas con no_available = 1 → NO se insertan (se cuentan y reportan).
  - ON CONFLICT DO NOTHING: re-importar un fichero es seguro.

Resumen al final:
  - Total de filas procesadas
  - Filas saltadas por no_available = 1
  - Filas saltadas por otras causas (JSON inválido, campos ausentes, etc.)
  - Filas insertadas en station_snapshot

Uso:
    # Un fichero
    python INSERT.py --db-url "postgresql://user:pass@host/bicimad" 201905.json
    
    python .\db\seeds\INSERT.py --db-url "postgresql://:@/" "C:/Users/ajolote-casa-w/Downloads/bicimad_data/bicimad_2018\stations" "C:/Users/ajolote-casa-w/Downloads/bicimad_data/bicimad_2019/stations" "C:/Users/ajolote-casa-w/Downloads/bicimad_data/bicimad_2020/stations" "C:/Users/ajolote-casa-w/Downloads/bicimad_data/bicimad_2021/stations" "C:/Users/ajolote-casa-w/Downloads/bicimad_data/bicimad_2022/stations" 

    # Directorios (procesa todos los .json dentro)
    python INSERT.py --db-url "..." bicimad_2018/stations bicimad_2019/stations

    # Mezcla
    python INSERT.py --db-url "..." bicimad_2018/stations 201905.json

    # Silenciar warnings de campos ausentes
    python INSERT.py --db-url "..." --quiet bicimad_2019/stations
"""
import json
import argparse
import sys
import warnings
from datetime import datetime
from pathlib import Path

import psycopg2
import psycopg2.extras

ENCODING   = 'latin-1'
BATCH_SIZE = 1000


# ── Warnings personalizados ────────────────────────────────────────────────────

class MissingFieldWarning(UserWarning):
    pass


def warn_default(field, default, context):
    warnings.warn(
        f"Campo '{field}' ausente en {context} → valor por defecto: {repr(default)}",
        MissingFieldWarning,
        stacklevel=3,
    )


def get_with_warning(obj, field, default, context):
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
        return self.cur

    def executemany(self, sql, rows):
        psycopg2.extras.execute_values(self.cur, sql, rows)

    def fetchone(self):
        return self.cur.fetchone()

    def commit(self):
        self.conn.commit()

    def close(self):
        self.cur.close()
        self.conn.close()


# ── Caché de station_id ────────────────────────────────────────────────────────
# Clave: (source_id, number, name, address, lat_str, lon_str, total_bases)
# Valor: station_id (SERIAL de PostgreSQL)
_station_cache = {}


def _station_key(source_id, number, name, address, lat, lon, total_bases):
    """Clave de unicidad: misma lógica que el UNIQUE CONSTRAINT de la tabla."""
    return (
        int(source_id),
        str(number),
        str(name),
        address,                                      # puede ser None
        str(round(float(lat), 7)) if lat is not None else None,
        str(round(float(lon), 7)) if lon is not None else None,
        int(total_bases),
    )


def get_or_create_station(db, s, context):
    """
    Devuelve el station_id para esta combinación de metadatos.
    Si no existe en la BD la inserta; usa caché en memoria para
    evitar round-trips repetidos.
    """
    source_id   = int(s['id'])
    number      = get_with_warning(s, 'number',      '',   context)
    name        = get_with_warning(s, 'name',        '',   context)
    address     = s.get('address')
    total_bases = get_with_warning(s, 'total_bases', 0,    context)

    lat = s.get('latitude')
    lon = s.get('longitude')
    if lat is None: warn_default('latitude',  None, context)
    if lon is None: warn_default('longitude', None, context)

    key = _station_key(source_id, number, name, address, lat, lon, total_bases)

    if key in _station_cache:
        return _station_cache[key]

    # Intentar insertar; si ya existe (ON CONFLICT) recuperar el station_id
    db.execute("""
        INSERT INTO station (source_id, number, name, address, latitude, longitude, total_bases)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT ON CONSTRAINT uq_station_version DO NOTHING
        RETURNING station_id
    """, (
        source_id,
        str(number),
        str(name),
        address,
        float(lat) if lat is not None else None,
        float(lon) if lon is not None else None,
        int(total_bases),
    ))
    row = db.fetchone()

    if row:
        station_id = row[0]
    else:
        # Ya existía → recuperar su id
        db.execute("""
            SELECT station_id FROM station
            WHERE source_id  = %s
              AND number      = %s
              AND name        = %s
              AND address     IS NOT DISTINCT FROM %s
              AND latitude    IS NOT DISTINCT FROM %s
              AND longitude   IS NOT DISTINCT FROM %s
              AND total_bases = %s
        """, (
            source_id,
            str(number),
            str(name),
            address,
            float(lat) if lat is not None else None,
            float(lon) if lon is not None else None,
            int(total_bases),
        ))
        station_id = db.fetchone()[0]

    _station_cache[key] = station_id
    return station_id


# ── Construcción de fila de snapshot ──────────────────────────────────────────

def build_snapshot_row(captured_at, station_id, s, context):
    activate           = get_with_warning(s, 'activate',           1, context)
    light              = get_with_warning(s, 'light',              0, context)
    dock_bikes         = get_with_warning(s, 'dock_bikes',         0, context)
    free_bases         = get_with_warning(s, 'free_bases',         0, context)
    reservations_count = get_with_warning(s, 'reservations_count', 0, context)

    return (
        captured_at,
        station_id,
        int(activate),
        int(light),
        int(dock_bikes),
        int(free_bases),
        int(reservations_count),
    )


# ── Flush batch ────────────────────────────────────────────────────────────────

INSERT_SNAPSHOT = """
    INSERT INTO station_snapshot
        (captured_at, station_id, activate, light,
         dock_bikes, free_bases, reservations_count)
    VALUES %s
    ON CONFLICT (captured_at, station_id) DO NOTHING
"""

def flush(db, buf):
    if not buf:
        return
    db.executemany(INSERT_SNAPSHOT, buf)
    db.commit()


# ── Importar un fichero ────────────────────────────────────────────────────────

def import_file(db, path, global_stats):
    """Importa un único fichero JSONL. Actualiza global_stats in-place."""

    snap_buffer = []
    f_snaps     = 0
    f_rows      = 0
    f_skipped_na     = 0   # saltados por no_available = 1
    f_skipped_other  = 0   # saltados por otras causas

    print(f"\n→ {path}")

    with open(path, 'rb') as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            # ── Parsear línea JSON ──
            try:
                obj = json.loads(line.decode(ENCODING))
            except json.JSONDecodeError as e:
                print(f"  [ERROR] línea {lineno}: JSON inválido: {e}", file=sys.stderr)
                f_skipped_other += 1
                continue

            # ── Timestamp ──
            ts_str = obj.get('_id', '')
            if not ts_str:
                print(f"  [ERROR] línea {lineno}: falta '_id', snapshot omitido", file=sys.stderr)
                f_skipped_other += 1
                continue

            try:
                captured_at = datetime.fromisoformat(ts_str)
            except ValueError as e:
                print(f"  [ERROR] línea {lineno}: timestamp inválido '{ts_str}': {e}", file=sys.stderr)
                f_skipped_other += 1
                continue

            stations = obj.get('stations', [])
            f_snaps += 1

            for s in stations:
                try:
                    source_id = int(s['id'])
                except (KeyError, ValueError, TypeError) as e:
                    print(f"  [ERROR] línea {lineno}: estación sin 'id' válido: {e}", file=sys.stderr)
                    f_skipped_other += 1
                    continue

                context = f"file={path.name}, snap={ts_str}, source_id={source_id}"

                # ── Filtro no_available ──
                na = s.get('no_available', 0)
                try:
                    na = int(na)
                except (ValueError, TypeError):
                    na = 0

                if na == 1:
                    f_skipped_na += 1
                    continue

                # ── Obtener / crear station_id ──
                try:
                    station_id = get_or_create_station(db, s, context)
                except Exception as e:
                    print(f"  [ERROR] {context}: al resolver station: {e}", file=sys.stderr)
                    f_skipped_other += 1
                    db.conn.rollback()
                    continue

                # ── Construir fila de snapshot ──
                try:
                    row = build_snapshot_row(captured_at, station_id, s, context)
                    snap_buffer.append(row)
                    f_rows += 1
                except Exception as e:
                    print(f"  [ERROR] {context}: al construir snapshot: {e}", file=sys.stderr)
                    f_skipped_other += 1
                    continue

            if len(snap_buffer) >= BATCH_SIZE:
                flush(db, snap_buffer)
                snap_buffer.clear()
                print(f"  {f_snaps} snapshots / {f_rows} filas...", end='\r')

    flush(db, snap_buffer)

    print(f"  ✓ {f_snaps:>6} snapshots  "
          f"{f_rows:>8} filas  "
          f"{f_skipped_na:>6} saltadas (no_available)  "
          f"{f_skipped_other:>4} errores  "
          f"[{path.name}]")

    global_stats['snaps']        += f_snaps
    global_stats['rows']         += f_rows
    global_stats['skipped_na']   += f_skipped_na
    global_stats['skipped_other'] += f_skipped_other


# ── Resolución de rutas ────────────────────────────────────────────────────────

def resolve_paths(inputs):
    result = []
    for p in inputs:
        path = Path(p)
        if path.is_dir():
            found = sorted(path.glob('*.json'))
            if not found:
                print(f"  [WARN] Directorio sin .json: {p}", file=sys.stderr)
            result.extend(found)
        elif path.is_file():
            result.append(path)
        else:
            print(f"  [WARN] Ruta no encontrada, se omite: {p}", file=sys.stderr)
    return result


# ── Entrada ────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(
        description='Importar BiciMAD JSON a PostgreSQL (station versionada)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument('--db-url',  required=True,
                   help='DSN PostgreSQL (postgresql://user:pass@host/db)')
    p.add_argument('inputs', nargs='+',
                   help='Ficheros .json o directorios con .json')
    p.add_argument('--quiet', action='store_true',
                   help='Suprimir warnings de campos ausentes')
    return p.parse_args()


def main():
    args = parse_args()

    if args.quiet:
        warnings.filterwarnings('ignore', category=MissingFieldWarning)
    else:
        warnings.simplefilter('always', MissingFieldWarning)

    files = resolve_paths(args.inputs)
    if not files:
        print("ERROR: No se encontraron ficheros .json.", file=sys.stderr)
        sys.exit(1)

    print(f"Ficheros a procesar: {len(files)}")
    for f in files:
        print(f"  {f}")

    print("\nConectando a PostgreSQL...")
    db = PostgresConn(args.db_url)

    global_stats = {
        'snaps':         0,
        'rows':          0,
        'skipped_na':    0,
        'skipped_other': 0,
    }

    try:
        for path in files:
            import_file(db, path, global_stats)
    finally:
        db.close()

    total_seen = global_stats['rows'] + global_stats['skipped_na'] + global_stats['skipped_other']

    print()
    print("═" * 60)
    print("  RESUMEN DE IMPORTACIÓN")
    print("═" * 60)
    print(f"  Ficheros procesados        : {len(files):>10,}")
    print(f"  Snapshots leídos           : {global_stats['snaps']:>10,}")
    print(f"  Registros de estación vistos: {total_seen:>10,}")
    print(f"  ├─ Insertados en snapshot  : {global_stats['rows']:>10,}")
    print(f"  ├─ Saltados (no_available) : {global_stats['skipped_na']:>10,}")
    print(f"  └─ Saltados (otros errores): {global_stats['skipped_other']:>10,}")
    print(f"  Versiones únicas en station: {len(_station_cache):>10,}")
    print("═" * 60)


if __name__ == '__main__':
    main()