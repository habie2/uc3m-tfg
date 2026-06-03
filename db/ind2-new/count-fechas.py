"""
Cuenta ocurrencias de cada valor distinto de unplug_hourTime
en un dump de MongoDB (un documento JSON por línea).

Uso:
    python count_unplug.py trips.json
    python count_unplug.py trips.json --top 20
"""
import json
import sys
import argparse
from collections import Counter


def main():
    parser = argparse.ArgumentParser(
        description="Cuenta valores distintos de unplug_hourTime en un JSON de BiciMAD"
    )
    parser.add_argument("input", help="Fichero JSON (un documento por línea)")
    parser.add_argument(
        "--top", type=int, default=0,
        help="Mostrar solo los N más frecuentes (0 = todos)"
    )
    args = parser.parse_args()

    counter = Counter()
    total_lines = 0
    errors = 0

    with open(args.input, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            total_lines += 1
            try:
                doc = json.loads(line)
                # El campo viene como {"$date": "2018-01-01T00:00:00.000+0100"}
                raw = doc.get("unplug_hourTime")
                if raw is None:
                    key = "(null)"
                elif isinstance(raw, dict) and "$date" in raw:
                    key = raw["$date"]
                else:
                    key = str(raw)
                counter[key] += 1
            except json.JSONDecodeError:
                errors += 1

    # Mostrar resultados ordenados por fecha
    items = sorted(counter.items(), key=lambda x: x[0])
    if args.top > 0:
        # Si piden top N, ordenar por frecuencia descendente
        items = counter.most_common(args.top)

    print(f"{'unplug_hourTime':<45} {'count':>8}")
    print("-" * 55)
    for value, count in items:
        print(f"{value:<45} {count:>8}")

    print("-" * 55)
    print(f"Valores distintos: {len(counter)}")
    print(f"Total documentos:  {total_lines}")
    if errors:
        print(f"Líneas con error:  {errors}")


if __name__ == "__main__":
    main()