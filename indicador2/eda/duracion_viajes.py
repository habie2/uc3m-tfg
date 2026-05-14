#!/usr/bin/env python3
"""
BiciMAD - Análisis de distribución de duración de viajes.
Genera histograma + estadísticas de travel_time/trip_minutes.
Uso: python3 bicimad_duracion.py /ruta/a/bicimad_data/
"""
import json
import csv
import os
import sys
import numpy as np
import matplotlib.pyplot as plt


def read_json_durations(filepath):
    """Extract travel_time (seconds) and origin==dest flag from JSON file."""
    durations = []
    same_station = 0
    total = 0
    with open(filepath, 'r', encoding='latin-1') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                total += 1
                tt = record.get('travel_time')
                if tt is not None:
                    durations.append(float(tt))  # seconds
                orig = record.get('idunplug_station')
                dest = record.get('idplug_station')
                if orig is not None and dest is not None and orig == dest:
                    same_station += 1
            except (json.JSONDecodeError, ValueError):
                continue
    return durations, same_station, total


def read_csv_durations(filepath):
    """Extract trip_minutes and origin==dest flag from CSV file."""
    durations = []
    same_station = 0
    total = 0
    with open(filepath, 'r', encoding='latin-1') as f:
        reader = csv.DictReader(f, delimiter=';')
        for row in reader:
            # Skip empty/separator rows
            if all(v.strip() == '' for v in row.values()):
                continue
            total += 1
            tm = row.get('trip_minutes', '').strip()
            if tm:
                try:
                    durations.append(float(tm) * 60)  # convert minutes -> seconds
                except ValueError:
                    pass
            orig = row.get('station_unlock', '').strip()
            dest = row.get('station_lock', '').strip()
            if orig and dest and orig == dest:
                same_station += 1
    return durations, same_station, total


def main():
    base_dir = sys.argv[1] if len(sys.argv) > 1 else '.'
    script_dir = os.path.dirname(os.path.abspath(__file__))

    all_durations = []
    total_same_station = 0
    total_records = 0

    for root, dirs, files in sorted(os.walk(base_dir)):
        if 'trips' not in root:
            continue
        for fname in sorted(files):
            filepath = os.path.join(root, fname)
            match_name = fname.replace('.json', '').replace('.csv', '')
            if len(match_name) != 6 or not match_name.isdigit():
                continue

            fmt = 'json' if fname.endswith('.json') else 'csv'
            # Skip duplicate csv if json exists for same month
            json_twin = filepath.replace('.csv', '.json')
            if fmt == 'csv' and os.path.exists(json_twin):
                continue

            print(f"Procesando {filepath}...", flush=True)
            if fmt == 'json':
                durations, same_st, total = read_json_durations(filepath)
            else:
                durations, same_st, total = read_csv_durations(filepath)

            all_durations.extend(durations)
            total_same_station += same_st
            total_records += total

    durations = np.array(all_durations)
    durations_min = durations / 60  # convert to minutes for display

    # ── Statistics ────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("ESTADÍSTICAS DE DURACIÓN DE VIAJES")
    print("=" * 70)
    print(f"   Total de viajes:                  {len(durations):>12,}")
    print(f"   Viajes misma estación orig=dest:  {total_same_station:>12,} ({total_same_station/total_records*100:.1f}%)")
    print()
    print(f"   Media:                            {np.mean(durations_min):>12.1f} min")
    print(f"   Mediana:                          {np.median(durations_min):>12.1f} min")
    print(f"   Desviación típica:                {np.std(durations_min):>12.1f} min")
    print(f"   Mínimo:                           {np.min(durations_min):>12.1f} min")
    print(f"   Máximo:                           {np.max(durations_min):>12.1f} min ({np.max(durations_min)/60:.1f} h)")
    print()

    # Percentiles
    percentiles = [1, 5, 10, 25, 50, 75, 90, 95, 99]
    print("   Percentiles:")
    for p in percentiles:
        val = np.percentile(durations_min, p)
        print(f"     P{p:<3}  {val:>10.1f} min")
    print()

    # Duration ranges
    ranges = [
        ("< 1 min (posible error)", durations_min < 1),
        ("1-5 min", (durations_min >= 1) & (durations_min < 5)),
        ("5-15 min", (durations_min >= 5) & (durations_min < 15)),
        ("15-30 min", (durations_min >= 15) & (durations_min < 30)),
        ("30-60 min", (durations_min >= 30) & (durations_min < 60)),
        ("1-2 horas", (durations_min >= 60) & (durations_min < 120)),
        ("2-4 horas", (durations_min >= 120) & (durations_min < 240)),
        ("4-8 horas", (durations_min >= 240) & (durations_min < 480)),
        ("8-24 horas", (durations_min >= 480) & (durations_min < 1440)),
        ("> 24 horas", durations_min >= 1440),
    ]

    print("   Distribución por rangos:")
    for label, mask in ranges:
        count = np.sum(mask)
        pct = count / len(durations_min) * 100
        print(f"     {label:<35} {count:>10,}  ({pct:>5.1f}%)")
    print()

    # Negative or zero
    neg_or_zero = np.sum(durations <= 0)
    print(f"   Viajes con duración <= 0 seg:     {neg_or_zero:>12,} ({neg_or_zero/len(durations)*100:.2f}%)")
    print("=" * 70)

    # ── Histogram ─────────────────────────────────────────────────────
    data_pos = durations_min[durations_min > 0]
    max_val = np.max(data_pos)
    mean_val = np.mean(durations_min)
    median_val = np.median(durations_min)

    # Count outliers
    n_over_120 = int(np.sum(data_pos > 120))
    n_over_1440 = int(np.sum(data_pos > 1440))

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6),
                                    gridspec_kw={'width_ratios': [3, 1]})

    # ── Left: 0-120 min (bulk of data) ──
    d1 = data_pos[data_pos <= 120]
    ax1.hist(d1, bins=120, color='#2b8cbe', edgecolor='white', linewidth=0.3)
    ax1.set_yscale('log')
    ax1.axvline(mean_val, color='#e31a1c', linestyle='--', linewidth=1.5,
                label=f'Media: {mean_val:.1f} min')
    ax1.axvline(median_val, color='#ff7f00', linestyle='--', linewidth=1.5,
                label=f'Mediana: {median_val:.1f} min')
    ax1.axvline(60, color='#2ca02c', linestyle=':', linewidth=1.5,
                label='60 min (penalización)')
    ax1.set_xlabel('Duración (minutos)')
    ax1.set_ylabel('Frecuencia (escala log)')
    ax1.set_title(f'Viajes de 0 a 120 min\n({len(d1):,} viajes)')
    ax1.legend(fontsize=9)
    ax1.set_xlim(0, 120)
    ax1.set_ylim(bottom=1)

    # ── Right: 120 min - 24h (cola larga, mismos bins de 1 min) ──
    d2 = data_pos[(data_pos > 120) & (data_pos <= 1440)]
    ax2.hist(d2, bins=int(1440 - 120), color='#e34a33', edgecolor='#e34a33', linewidth=0.2)
    ax2.set_yscale('log')
    ax2.set_xlabel('Duración (minutos)')
    ax2.set_title(f'Viajes de 2h a 24h\n({len(d2):,} viajes)')
    ax2.set_xlim(120, 1440)
    ax2.set_ylim(bottom=1)

    fig.suptitle(
        f'Distribución de la duración de los viajes — N={len(data_pos):,}\n'
        f'Máx: {max_val:,.0f} min ({max_val/60:.0f}h) · '
        f'{n_over_120:,} viajes >2h · {n_over_1440:,} viajes >24h (posibles errores)',
        fontsize=12, fontweight='bold', y=1.04)

    plt.tight_layout()
    output_path = os.path.join(script_dir, 'bicimad_duracion_viajes.png')
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"\n✅ Histograma guardado en: {output_path}")


if __name__ == '__main__':
    main()