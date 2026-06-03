#!/usr/bin/env python3
"""
BiciMAD - Conteo exacto de registros y campo track + heatmap.
Ejecutar sobre los archivos reales.
Uso: python3 bicimad_count_exact.py /ruta/a/bicimad_data/
"""
import json
import csv
import os
import sys
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import seaborn as sns


def count_json_file(filepath):
    """Count records and track fields in a JSON file (one JSON object per line)."""
    total = 0
    with_track = 0
    with open(filepath, 'r', encoding='latin-1') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                total += 1
                if 'track' in record:
                    with_track += 1
            except json.JSONDecodeError:
                continue
    return total, with_track


def count_csv_file(filepath):
    """Count records in a CSV file (semicolon-separated, with empty separator lines)."""
    total = 0
    with open(filepath, 'r', encoding='latin-1') as f:
        reader = csv.reader(f, delimiter=';')
        header = next(reader, None)  # skip header
        for row in reader:
            if all(cell.strip() == '' for cell in row):
                continue
            total += 1
    return total, 0  # CSVs don't have track


def format_num(n):
    """Format a number as compact string (e.g. 1.2M, 345K, 6.3K)."""
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    elif n >= 100_000:
        return f"{n/1000:.0f}K"
    elif n >= 1_000:
        return f"{n/1000:.1f}K"
    else:
        return str(n)


def generate_heatmap(results, output_path):
    """Generate a heatmap PNG from the exact count results."""
    # Deduplicate: if both json and csv exist for same month, prefer json
    data_by_key = {}
    for year, month, fmt, total, with_track, size_bytes in results:
        key = (year, month)
        if key in data_by_key and data_by_key[key][2] == 'json' and fmt == 'csv':
            continue
        data_by_key[key] = (year, month, fmt, total, with_track, size_bytes)

    years = sorted(set(k[0] for k in data_by_key))
    months = list(range(1, 13))
    month_labels = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
                    'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
    n_months = 12
    n_years = len(years)

    # Build matrices
    records_matrix = np.full((n_months, n_years), np.nan)
    track_matrix = np.full((n_months, n_years), np.nan)
    fmt_matrix = [['' for _ in range(n_years)] for _ in range(n_months)]

    for (year, month), (_, _, fmt, total, with_track, _) in data_by_key.items():
        mi = month - 1
        yi = years.index(year)
        records_matrix[mi, yi] = total
        track_matrix[mi, yi] = with_track
        fmt_matrix[mi][yi] = fmt

    # ── Plot ──────────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(18, 13))

    cmap = sns.color_palette("YlGnBu", as_cmap=True)
    valid = records_matrix[~np.isnan(records_matrix)]
    vmin = valid.min() * 0.9
    vmax = valid.max() * 1.05
    norm = mcolors.Normalize(vmin=vmin, vmax=vmax)

    for mi in range(n_months):
        for yi in range(n_years):
            val = records_matrix[mi, yi]
            y_pos = n_months - 1 - mi  # flip so Ene is on top

            if np.isnan(val):
                rect = plt.Rectangle((yi, y_pos), 1, 1,
                                     facecolor='#d9d9d9', edgecolor='white', linewidth=2)
                ax.add_patch(rect)
                ax.text(yi + 0.5, y_pos + 0.5, '—',
                        ha='center', va='center', fontsize=13,
                        color='#999999', fontweight='bold')
            else:
                color = cmap(norm(val))
                rect = plt.Rectangle((yi, y_pos), 1, 1,
                                     facecolor=color, edgecolor='white', linewidth=2)
                ax.add_patch(rect)

                total = int(val)
                trk = int(track_matrix[mi, yi]) if not np.isnan(track_matrix[mi, yi]) else 0
                fmt = fmt_matrix[mi][yi]

                # Text color based on background brightness
                rgb = color[:3]
                brightness = 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]
                text_color = 'white' if brightness < 0.5 else '#1a1a2e'

                # Line 1: total records
                ax.text(yi + 0.5, y_pos + 0.62, format_num(total),
                        ha='center', va='center', fontsize=12, fontweight='bold',
                        color=text_color)

                # Line 2: track info with percentage
                if fmt == 'json':
                    pct = trk / total * 100 if total > 0 else 0
                    track_str = f"track: {format_num(trk)} ({pct:.0f}%)"
                    ax.text(yi + 0.5, y_pos + 0.38, track_str,
                            ha='center', va='center', fontsize=8,
                            color=text_color, alpha=0.85)
                elif fmt == 'csv':
                    ax.text(yi + 0.5, y_pos + 0.38, '(csv, sin track)',
                            ha='center', va='center', fontsize=8,
                            color=text_color, alpha=0.7)

    # Axes
    ax.set_xlim(0, n_years)
    ax.set_ylim(0, n_months)
    ax.set_xticks([j + 0.5 for j in range(n_years)])
    ax.set_xticklabels(years, fontsize=13)
    ax.set_yticks([i + 0.5 for i in range(n_months)])
    ax.set_yticklabels(month_labels[::-1], fontsize=13)
    ax.set_xlabel('Año', fontsize=14, fontweight='bold', labelpad=10)
    ax.set_ylabel('Mes', fontsize=14, fontweight='bold', labelpad=10)

    ax.set_title(
        'Cobertura temporal del dataset BiciMAD: registros (trips) por mes y año\n'
        '(se muestra total de trips y nº con track / % sobre total)',
        fontsize=14, fontweight='bold', pad=20)

    # Colorbar
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = plt.colorbar(sm, ax=ax, shrink=0.8, pad=0.02)
    cbar.set_label('Número de registros', fontsize=12, rotation=270, labelpad=20)

    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(length=0)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"\n✅ Heatmap guardado en: {output_path}")


def main():
    base_dir = sys.argv[1] if len(sys.argv) > 1 else '.'

    # Output image next to the script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(script_dir, 'bicimad_cobertura_temporal.png')

    results = []
    for root, dirs, files in sorted(os.walk(base_dir)):
        if 'trips' not in root:
            continue
        for fname in sorted(files):
            filepath = os.path.join(root, fname)

            match_name = fname.replace('.json', '').replace('.csv', '')
            if len(match_name) == 6 and match_name.isdigit():
                year = int(match_name[:4])
                month = int(match_name[4:6])
            else:
                continue

            fmt = 'json' if fname.endswith('.json') else 'csv'
            print(f"Procesando {filepath}...", end=' ', flush=True)

            total, with_track = count_json_file(filepath) if fmt == 'json' else count_csv_file(filepath)
            size_bytes = os.path.getsize(filepath)

            print(f"{total:,} registros, {with_track:,} con track")
            results.append((year, month, fmt, total, with_track, size_bytes))

    # ── Print summary table ───────────────────────────────────────────
    print("\n" + "=" * 90)
    print(f"{'Año':>6} {'Mes':>4} {'Fmt':>5} {'Total':>12} {'Con track':>12} {'% track':>10} {'MB':>10}")
    print("-" * 90)

    grand_total = 0
    grand_track = 0
    for year, month, fmt, total, with_track, size_bytes in results:
        pct = (with_track / total * 100) if total > 0 else 0
        grand_total += total
        grand_track += with_track
        print(f"{year:>6} {month:>4} {fmt:>5} {total:>12,} {with_track:>12,} {pct:>9.1f}% {size_bytes/1024/1024:>9.1f}")

    print("-" * 90)
    pct = (grand_track / grand_total * 100) if grand_total > 0 else 0
    print(f"{'TOTAL':>16} {grand_total:>12,} {grand_track:>12,} {pct:>9.1f}%")
    print("=" * 90)

    # ── Generate heatmap ──────────────────────────────────────────────
    generate_heatmap(results, output_path)


if __name__ == '__main__':
    main()