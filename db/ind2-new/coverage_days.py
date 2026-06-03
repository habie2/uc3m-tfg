"""
Cobertura diaria BiciMAD — heatmap mes × año con el porcentaje de días
del mes que tienen al menos un viaje registrado.

Espera la estructura:
    <root>/bicimad_YYYY/trips/YYYYMM.json     (formato Mongo, una línea = un doc)
    <root>/bicimad_YYYY/trips/YYYYMM.csv      (formato CSV con separador ';')

Uso:
    python coverage_days.py "C:\\Users\\...\\bicimad_data"
    python coverage_days.py "C:\\Users\\...\\bicimad_data" --output cobertura.png
    python coverage_days.py "C:\\Users\\...\\bicimad_data" --rescan   # ignora cache

Requiere: matplotlib, numpy.
"""
from __future__ import annotations

import argparse
import calendar
import csv
import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

# Regex para extraer la fecha (YYYY-MM-DD) de unplug_hourTime en líneas JSON.
# Acepta tanto `"unplug_hourTime": "2018-01-01..."` como
# `"unplug_hourTime": {"$date": "2018-01-01..."}`.
JSON_DATE_RE = re.compile(
    rb'"unplug_hourTime"\s*:\s*(?:\{\s*"\$date"\s*:\s*)?"(\d{4}-\d{2}-\d{2})'
)

MONTHS_ES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
             "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


def extract_days_json(path: Path) -> set[str]:
    """Días distintos (YYYY-MM-DD) con al menos un viaje en un .json de Mongo."""
    days: set[str] = set()
    # Modo binario + regex en bytes: evita problemas de codificación (la Ñ
    # de algunos nombres de estaciones rompe utf-8) y es más rápido.
    with open(path, "rb") as f:
        for line in f:
            m = JSON_DATE_RE.search(line)
            if m:
                days.add(m.group(1).decode("ascii"))
    return days


def extract_days_csv(path: Path) -> set[str]:
    """Días distintos del CSV (campo unlock_date o fecha)."""
    days: set[str] = set()
    with open(path, "r", encoding="utf-8", errors="replace", newline="") as f:
        # BiciMAD usa ';' como separador, pero auto-detectamos por si acaso.
        sample = f.read(8192)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=";,\t")
        except csv.Error:
            class D(csv.excel):
                delimiter = ";"
            dialect = D
        reader = csv.DictReader(f, dialect=dialect)
        # Buscamos la columna de fecha por nombre conocido.
        candidates = ("unlock_date", "fecha")
        date_col = None
        for col in reader.fieldnames or []:
            if col and col.lower().strip() in candidates:
                date_col = col
                break
        if date_col is None:
            return days
        for row in reader:
            v = row.get(date_col, "") or ""
            if len(v) >= 10:
                days.add(v[:10])
    return days


def scan(root: Path) -> dict:
    """Recorre todos los ficheros y devuelve {(year, month): n_dias_con_datos}."""
    files = []
    for year_dir in sorted(root.glob("bicimad_*")):
        trips_dir = year_dir / "trips"
        if not trips_dir.is_dir():
            continue
        for f in sorted(trips_dir.iterdir()):
            if f.suffix.lower() not in (".json", ".csv"):
                continue
            stem = f.stem
            if len(stem) != 6 or not stem.isdigit():
                continue
            files.append((int(stem[:4]), int(stem[4:]), f))

    if not files:
        print(f"No se han encontrado ficheros bajo {root}")
        sys.exit(1)

    print(f"Procesando {len(files)} ficheros...\n")
    coverage = {}
    for i, (year, month, path) in enumerate(files, 1):
        size_mb = path.stat().st_size / 1e6
        t0 = time.time()
        print(f"  [{i:>2}/{len(files)}] {path.name} ({size_mb:>6.0f} MB)... ",
              end="", flush=True)
        if path.suffix.lower() == ".json":
            days = extract_days_json(path)
        else:
            days = extract_days_csv(path)
        # Quedarnos solo con días que caen dentro de su año-mes (defensivo)
        prefix = f"{year}-{month:02d}-"
        days = {d for d in days if d.startswith(prefix)}
        # Si el mismo (year, month) tiene .csv y .json, unimos
        key = (year, month)
        prev = coverage.get(key, set())
        coverage[key] = prev | days
        dt = time.time() - t0
        print(f"{len(days):>2} días con datos  ({dt:.1f}s)")

    # Convertimos sets a listas para que sea serializable
    return {f"{y}-{m:02d}": sorted(d) for (y, m), d in coverage.items()}


def plot(coverage: dict, output: Path):
    """Heatmap mes × año con % de días con datos."""
    # Reconstruir tuplas (year, month) -> set
    parsed: dict[tuple[int, int], set[str]] = {}
    for k, v in coverage.items():
        y, m = k.split("-")
        parsed[(int(y), int(m))] = set(v)

    years = sorted({y for y, _ in parsed.keys()})
    matrix = np.full((12, len(years)), np.nan)
    annotations = [["" for _ in years] for _ in range(12)]

    for (year, month), days in parsed.items():
        col = years.index(year)
        days_in_month = calendar.monthrange(year, month)[1]
        pct = len(days) / days_in_month * 100 if days_in_month else 0
        matrix[month - 1, col] = pct
        annotations[month - 1][col] = f"{pct:.0f}%\n{len(days)}/{days_in_month} días"

    fig, ax = plt.subplots(figsize=(max(8, 1.4 * len(years)), 9))
    cmap = plt.cm.YlGnBu.copy()
    cmap.set_bad("#d9d9d9")
    masked = np.ma.masked_invalid(matrix)
    im = ax.imshow(masked, cmap=cmap, vmin=0, vmax=100, aspect="auto")

    ax.set_xticks(range(len(years)))
    ax.set_xticklabels(years)
    ax.set_yticks(range(12))
    ax.set_yticklabels(MONTHS_ES)
    ax.set_xlabel("Año")
    ax.set_ylabel("Mes")
    ax.set_title(
        "Cobertura temporal BiciMAD: % de días del mes con al menos un viaje",
        fontsize=12, fontweight="bold",
    )

    for i in range(12):
        for j in range(len(years)):
            val = matrix[i, j]
            if np.isnan(val):
                ax.text(j, i, "—", ha="center", va="center",
                        color="#666", fontsize=11)
            else:
                color = "white" if val > 55 else "black"
                ax.text(j, i, annotations[i][j], ha="center", va="center",
                        color=color, fontsize=8, fontweight="bold")

    cbar = plt.colorbar(im, ax=ax, label="% de días con datos")
    cbar.set_ticks([0, 25, 50, 75, 100])

    plt.tight_layout()
    plt.savefig(output, dpi=150, bbox_inches="tight")
    print(f"\nGráfica guardada en: {output}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", help="Carpeta raíz (la que contiene bicimad_YYYY/)")
    ap.add_argument("--output", default="coverage_days.png",
                    help="PNG de salida (por defecto: coverage_days.png)")
    ap.add_argument("--cache", default="coverage_days_cache.json",
                    help="JSON de caché del escaneo")
    ap.add_argument("--rescan", action="store_true",
                    help="Ignora la caché y vuelve a escanear todo")
    args = ap.parse_args()

    cache_path = Path(args.cache)
    if cache_path.exists() and not args.rescan:
        print(f"Cargando caché desde {cache_path} (usa --rescan para regenerar)")
        with open(cache_path, "r", encoding="utf-8") as f:
            coverage = json.load(f)
    else:
        coverage = scan(Path(args.root))
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(coverage, f, ensure_ascii=False, indent=2)
        print(f"\nCaché guardada en: {cache_path}")

    plot(coverage, Path(args.output))


if __name__ == "__main__":
    main()