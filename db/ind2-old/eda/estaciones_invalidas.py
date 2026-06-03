#!/usr/bin/env python3
"""
BiciMAD - Validación de IDs de estaciones en trips.
Compara los IDs de estación usados en los viajes contra las estaciones
conocidas del dataset de snapshots (stations).

Uso: python3 bicimad_estaciones_invalidas.py /ruta/a/bicimad_data/

El script busca:
  - trips/    -> archivos de viajes (JSON y CSV)
  - stations/ -> archivos de snapshots de estaciones (JSON o CSV)

Si no tienes los snapshots de estaciones, el script igualmente te saca
todos los IDs únicos de estación usados en trips y marca los que solo
aparecen muy pocas veces (posibles errores).
"""
import json
import csv
import os
import sys
from collections import defaultdict
import matplotlib.pyplot as plt
import numpy as np


def extract_station_ids_from_snapshots(base_dir):
    """Extract known station IDs from ALL stations/snapshots files."""
    known_stations = {}  # id -> name
    files_read = []

    for root, dirs, files in sorted(os.walk(base_dir)):
        if 'stations' not in root.lower() and 'snapshots' not in root.lower():
            continue
        for fname in sorted(files):
            filepath = os.path.join(root, fname)

            if fname.endswith('.json'):
                try:
                    count_before = len(known_stations)
                    with open(filepath, 'r', encoding='latin-1') as f:
                        for line in f:
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                record = json.loads(line)
                                stations = record.get('stations', [])
                                if isinstance(stations, list):
                                    for st in stations:
                                        sid = st.get('id')
                                        sname = st.get('name', '')
                                        if sid is not None:
                                            known_stations[int(sid)] = sname
                                elif 'id' in record and 'name' in record:
                                    known_stations[int(record['id'])] = record.get('name', '')
                            except (json.JSONDecodeError, ValueError):
                                continue
                    new_ids = len(known_stations) - count_before
                    files_read.append((filepath, new_ids))
                    print(f"   {filepath} → {len(known_stations)} estaciones ({new_ids} nuevas)", flush=True)
                except Exception as e:
                    print(f"   Error en {filepath}: {e}")

            elif fname.endswith('.csv'):
                try:
                    count_before = len(known_stations)
                    with open(filepath, 'r', encoding='latin-1') as f:
                        reader = csv.DictReader(f, delimiter=';')
                        for row in reader:
                            if all(v.strip() == '' for v in row.values()):
                                continue
                            sid = row.get('id', row.get('station_id', row.get('number', ''))).strip()
                            sname = row.get('name', row.get('station_name', '')).strip()
                            if sid:
                                try:
                                    known_stations[int(sid)] = sname
                                except ValueError:
                                    pass
                    new_ids = len(known_stations) - count_before
                    files_read.append((filepath, new_ids))
                    print(f"   {filepath} → {len(known_stations)} estaciones ({new_ids} nuevas)", flush=True)
                except Exception as e:
                    print(f"   Error en {filepath}: {e}")

    return known_stations, files_read


def extract_trip_station_ids(base_dir, known_ids=None, max_samples=5):
    """Extract all station IDs used in trips with their counts.
    Also collects sample records for unknown station IDs."""
    # station_id -> {'as_origin': count, 'as_dest': count}
    station_usage = defaultdict(lambda: {'as_origin': 0, 'as_dest': 0})
    total_trips = 0
    missing_origin = 0
    missing_dest = 0
    # station_id -> [list of sample records]
    samples = defaultdict(list)

    for root, dirs, files in sorted(os.walk(base_dir)):
        if 'trips' not in root:
            continue
        for fname in sorted(files):
            filepath = os.path.join(root, fname)
            match_name = fname.replace('.json', '').replace('.csv', '')
            if len(match_name) != 6 or not match_name.isdigit():
                continue

            fmt = 'json' if fname.endswith('.json') else 'csv'
            # Skip csv duplicate if json exists
            json_twin = filepath.replace('.csv', '.json')
            if fmt == 'csv' and os.path.exists(json_twin):
                continue

            print(f"Procesando {filepath}...", flush=True)

            if fmt == 'json':
                with open(filepath, 'r', encoding='latin-1') as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            record = json.loads(line)
                            total_trips += 1
                            orig = record.get('idunplug_station')
                            dest = record.get('idplug_station')
                            if orig is not None:
                                orig_int = int(orig)
                                station_usage[orig_int]['as_origin'] += 1
                                # Save sample if unknown
                                if known_ids is not None and orig_int not in known_ids and len(samples[orig_int]) < max_samples:
                                    sample = {k: v for k, v in record.items() if k != 'track'}
                                    sample['_source_file'] = fname
                                    samples[orig_int].append(sample)
                            else:
                                missing_origin += 1
                            if dest is not None:
                                dest_int = int(dest)
                                station_usage[dest_int]['as_dest'] += 1
                                if known_ids is not None and dest_int not in known_ids and len(samples[dest_int]) < max_samples:
                                    sample = {k: v for k, v in record.items() if k != 'track'}
                                    sample['_source_file'] = fname
                                    samples[dest_int].append(sample)
                            else:
                                missing_dest += 1
                        except (json.JSONDecodeError, ValueError):
                            continue
            else:  # csv
                with open(filepath, 'r', encoding='latin-1') as f:
                    reader = csv.DictReader(f, delimiter=';')
                    for row in reader:
                        if all(v.strip() == '' for v in row.values()):
                            continue
                        total_trips += 1
                        orig = row.get('station_unlock', '').strip()
                        dest = row.get('station_lock', '').strip()
                        if orig:
                            try:
                                orig_int = int(orig)
                                station_usage[orig_int]['as_origin'] += 1
                                if known_ids is not None and orig_int not in known_ids and len(samples[orig_int]) < max_samples:
                                    sample = dict(row)
                                    sample['_source_file'] = fname
                                    samples[orig_int].append(sample)
                            except ValueError:
                                missing_origin += 1
                        else:
                            missing_origin += 1
                        if dest:
                            try:
                                dest_int = int(dest)
                                station_usage[dest_int]['as_dest'] += 1
                                if known_ids is not None and dest_int not in known_ids and len(samples[dest_int]) < max_samples:
                                    sample = dict(row)
                                    sample['_source_file'] = fname
                                    samples[dest_int].append(sample)
                            except ValueError:
                                missing_dest += 1
                        else:
                            missing_dest += 1

    return station_usage, total_trips, missing_origin, missing_dest, samples


def main():
    base_dir = sys.argv[1] if len(sys.argv) > 1 else '.'

    # ── 1. Try to load known stations from snapshots ──────────────────
    print("=" * 80)
    print("FASE 1: Buscando estaciones conocidas en TODOS los archivos de snapshots...")
    print("=" * 80)
    known_stations, files_read = extract_station_ids_from_snapshots(base_dir)

    if known_stations:
        print(f"\n   ✅ {len(known_stations)} estaciones únicas encontradas en {len(files_read)} archivo(s)")
        print(f"   IDs: {sorted(known_stations.keys())[:20]}{'...' if len(known_stations) > 20 else ''}")
        print(f"\n   Archivos de snapshots utilizados:")
        for fpath, new_ids in files_read:
            print(f"     {os.path.basename(fpath)} ({new_ids} IDs nuevos)")
        print(f"\n   → Un ID de estación se considera INVÁLIDO si no aparece en")
        print(f"     ninguno de estos {len(files_read)} archivos de snapshots.")
    else:
        print("\n   ⚠️  No se encontraron archivos de estaciones/snapshots.")
        print("   Se analizarán los IDs de trips de forma independiente.")

    # ── 2. Extract station IDs from trips ─────────────────────────────
    print("\n" + "=" * 80)
    print("FASE 2: Extrayendo IDs de estaciones de los viajes...")
    print("=" * 80)
    known_ids_set = set(known_stations.keys()) if known_stations else None
    station_usage, total_trips, missing_orig, missing_dest, samples = \
        extract_trip_station_ids(base_dir, known_ids=known_ids_set)

    trip_station_ids = set(station_usage.keys())

    # ── 3. Analysis ───────────────────────────────────────────────────
    print("\n" + "=" * 80)
    print("RESULTADOS")
    print("=" * 80)

    print(f"\n   Total de viajes analizados:       {total_trips:>12,}")
    print(f"   Viajes sin estación origen:       {missing_orig:>12,} ({missing_orig/total_trips*100:.2f}%)")
    print(f"   Viajes sin estación destino:      {missing_dest:>12,} ({missing_dest/total_trips*100:.2f}%)")
    print(f"   IDs de estación únicos en trips:  {len(trip_station_ids):>12,}")

    if known_stations:
        known_ids = set(known_stations.keys())
        print(f"   IDs de estación en snapshots:     {len(known_ids):>12,}")

        # IDs in trips but not in stations
        unknown_ids = trip_station_ids - known_ids
        # IDs in stations but never used in trips
        unused_ids = known_ids - trip_station_ids

        print(f"\n   IDs en trips NO encontrados en snapshots:   {len(unknown_ids)}")
        if unknown_ids:
            print()
            print(f"   {'ID':>6}  {'Como origen':>14}  {'Como destino':>14}  {'Total usos':>14}")
            print(f"   {'-'*6}  {'-'*14}  {'-'*14}  {'-'*14}")
            for sid in sorted(unknown_ids):
                usage = station_usage[sid]
                total_use = usage['as_origin'] + usage['as_dest']
                print(f"   {sid:>6}  {usage['as_origin']:>14,}  {usage['as_dest']:>14,}  {total_use:>14,}")

            # Total trips affected
            affected = sum(station_usage[sid]['as_origin'] + station_usage[sid]['as_dest']
                          for sid in unknown_ids)
            print(f"\n   Total de usos de estaciones desconocidas: {affected:,}")
            print(f"   (esto NO significa {affected:,} viajes afectados, un viaje puede")
            print(f"    tener origen Y destino desconocido)")

        print(f"\n   IDs en snapshots NO usados en ningún viaje: {len(unused_ids)}")
        if unused_ids:
            for sid in sorted(unused_ids):
                name = known_stations.get(sid, '?')
                print(f"     ID {sid}: {name}")

    else:
        # Without known stations, flag IDs with very few uses
        print("\n   Estaciones con muy pocos usos (posibles IDs erróneos):")
        print(f"\n   {'ID':>6}  {'Como origen':>14}  {'Como destino':>14}  {'Total usos':>14}")
        print(f"   {'-'*6}  {'-'*14}  {'-'*14}  {'-'*14}")

        rare_count = 0
        for sid in sorted(station_usage.keys()):
            usage = station_usage[sid]
            total_use = usage['as_origin'] + usage['as_dest']
            if total_use < 10:
                print(f"   {sid:>6}  {usage['as_origin']:>14,}  {usage['as_dest']:>14,}  {total_use:>14,}")
                rare_count += 1

        if rare_count == 0:
            print("   (ninguna estación con menos de 10 usos)")
        print(f"\n   Total de estaciones con < 10 usos: {rare_count}")

    # ── 4. Full station usage summary ─────────────────────────────────
    print("\n" + "=" * 80)
    print("RESUMEN DE USO POR ESTACIÓN (top 20 más usadas)")
    print("=" * 80)
    print(f"\n   {'ID':>6}  {'Nombre':<40}  {'Origen':>10}  {'Destino':>10}  {'Total':>10}")
    print(f"   {'-'*6}  {'-'*40}  {'-'*10}  {'-'*10}  {'-'*10}")

    sorted_stations = sorted(station_usage.items(),
                             key=lambda x: x[1]['as_origin'] + x[1]['as_dest'],
                             reverse=True)

    for sid, usage in sorted_stations[:20]:
        name = known_stations.get(sid, '') if known_stations else ''
        total_use = usage['as_origin'] + usage['as_dest']
        print(f"   {sid:>6}  {name:<40}  {usage['as_origin']:>10,}  {usage['as_dest']:>10,}  {total_use:>10,}")

    print("=" * 80)

    # ── 5. Chart: proportion of valid vs invalid stations ─────────────
    script_dir = os.path.dirname(os.path.abspath(__file__))

    if known_stations:
        known_ids = set(known_stations.keys())
        unknown_ids = trip_station_ids - known_ids

        # Count trips by category
        # A trip has origin + destination = 2 station references
        valid_origin = 0
        invalid_origin = 0
        valid_dest = 0
        invalid_dest = 0
        for sid, usage in station_usage.items():
            if sid in known_ids:
                valid_origin += usage['as_origin']
                valid_dest += usage['as_dest']
            else:
                invalid_origin += usage['as_origin']
                invalid_dest += usage['as_dest']

        # ── Chart ──────────────────────────────────────────────────────
        fig, ax = plt.subplots(figsize=(12, 5))

        categories = ['Válida', 'Inválida', 'Sin estación']
        origin_vals = [valid_origin, invalid_origin, missing_orig]
        dest_vals = [valid_dest, invalid_dest, missing_dest]
        total = valid_origin + invalid_origin + missing_orig

        y = np.arange(len(categories))
        h = 0.35

        bars1 = ax.barh(y + h/2, origin_vals, h, label='Origen', color='#2b8cbe')
        bars2 = ax.barh(y - h/2, dest_vals, h, label='Destino', color='#e07b54')

        ax.set_xscale('log')
        ax.set_yticks(y)
        ax.set_yticklabels(categories, fontsize=12)
        ax.set_xlabel('Nº de viajes (escala log)', fontsize=11)
        ax.legend(fontsize=11)

        # Add count + percentage labels
        for bars, vals in [(bars1, origin_vals), (bars2, dest_vals)]:
            for bar, val in zip(bars, vals):
                if val > 0:
                    pct = val / total * 100
                    ax.text(bar.get_width() * 1.15, bar.get_y() + bar.get_height() / 2,
                            f'{val:,} ({pct:.2f}%)', va='center', fontsize=9)

        ax.set_title(f'Validez de estaciones en los viajes (N={total:,})',
                     fontsize=13, fontweight='bold')

        plt.tight_layout()
        output_path = os.path.join(script_dir, 'bicimad_estaciones_validez.png')
        plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
        plt.close()
        print(f"\n✅ Gráfico guardado en: {output_path}")


if __name__ == '__main__':
    main()