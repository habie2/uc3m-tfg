"""
Exporta los datos del Indicador 3 (captura intermodal) a CSV.

Uso:
    python export_ind3.py                          # usa http://localhost:5000
    python export_ind3.py --base-url http://mi-servidor:8080

Genera:
    ind3_capture_<radio>m.csv   — detalle por nodo de metro (uno por radio)
    ind3_stats.csv              — resumen agregado (una fila por radio)
"""

import argparse, csv, json, sys, urllib.request, pathlib
from datetime import datetime

def fetch_json(url):
    with urllib.request.urlopen(url) as r:
        return json.loads(r.read())

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://localhost:5000")
    ap.add_argument("--prefix", default="api/ind3")
    ap.add_argument("--out-dir", default=".")
    args = ap.parse_args()

    base = f"{args.base_url.rstrip('/')}/{args.prefix.strip('/')}"
    out = pathlib.Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    # 1. Obtener radios disponibles
    cfg = fetch_json(f"{base}/config")
    radii = cfg["radii"]
    print(f"Radios configurados: {radii}")

    # 2. Para cada radio, exportar capture
    capture_header = [
        "id", "name", "lat", "lon", "lines", "is_hub",
        "out", "in", "captured", "bicimad_stations"
    ]

    for r in radii:
        data = fetch_json(f"{base}/capture?radius={r}")
        fname = out / f"ind3_capture_{r}m.csv"
        with open(fname, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(capture_header)
            for n in data["nodes"]:
                bici_names = "; ".join(
                    f"{s['name']} ({s['number']}, {s['dist']}m)"
                    for s in n.get("stations", [])
                )
                w.writerow([
                    n["id"], n["name"], n["lat"], n["lon"],
                    n["lines"], n["is_hub"],
                    n["out"], n["in"], n["captured"],
                    bici_names,
                ])
        print(f"  → {fname}  ({len(data['nodes'])} nodos)")

    # 3. Exportar stats (una fila por radio)
    stats_header = [
        "radius_m", "total_intermodal", "historic_trips", "share_pct",
        "top_node_name", "top_node_captured",
        "metro_with_bici", "metro_total", "metro_coverage_pct"
    ]
    stats_fname = out / "ind3_stats.csv"
    with open(stats_fname, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(stats_header)
        for r in radii:
            s = fetch_json(f"{base}/stats?radius={r}")
            top = s.get("top_node") or {}
            w.writerow([
                s["radius"], s["total_intermodal"], s["historic_trips"],
                s["share_pct"],
                top.get("name", ""), top.get("captured", ""),
                s["metro_with_bici"], s["metro_total"], s["metro_coverage_pct"],
            ])
    print(f"  → {stats_fname}  ({len(radii)} filas)")

    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"\nExportación completada ({ts})")

if __name__ == "__main__":
    main()