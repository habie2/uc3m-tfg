#!/usr/bin/env python3
"""
BiciMAD - Extractor de estructura de registros de trips.
Analiza archivos JSON y CSV para mostrar la estructura de los datos.
Uso: python3 bicimad_structure.py /ruta/a/bicimad_data/
"""
import json
import csv
import os
import sys
from pathlib import Path
from collections import OrderedDict


def get_type_name(value):
    """Return a human-readable Spanish type name."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "booleano"
    if isinstance(value, int):
        return "entero"
    if isinstance(value, float):
        return "decimal"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "objeto"
    return type(value).__name__


def truncate(val, max_len=45):
    """Truncate a value string for display."""
    s = str(val)
    if len(s) > max_len:
        return s[:max_len - 3] + "..."
    return s


def analyze_json_record(record, prefix="", depth=0):
    """Recursively analyze a JSON record and return structure lines."""
    lines = []
    keys = list(record.keys())
    for i, key in enumerate(keys):
        value = record[key]
        is_last = (i == len(keys) - 1)
        connector = "└─" if is_last else "├─"
        continuation = "   " if is_last else "│  "

        if isinstance(value, dict):
            # Check if it's a special MongoDB type
            if "$oid" in value:
                lines.append((depth, connector, key, "string (ObjectId)", truncate(value["$oid"])))
            elif "$date" in value:
                lines.append((depth, connector, key, "string (ISO 8601)", truncate(value["$date"])))
            elif value.get("type") == "FeatureCollection":
                lines.append((depth, connector, key, "GeoJSON FeatureCollection", ""))
                # Analyze features structure
                features = value.get("features", [])
                if features:
                    feat = features[0]
                    lines.append((depth + 1, "├─", "type", "string", "FeatureCollection"))
                    lines.append((depth + 1, "└─", f"features (array, {len(features)} elementos)", "", ""))
                    # Show structure of a single feature
                    lines.append((depth + 2, "├─", "type", "string", "Feature"))
                    geom = feat.get("geometry", {})
                    lines.append((depth + 2, "├─", "geometry", "objeto", ""))
                    lines.append((depth + 3, "├─", "type", "string", truncate(geom.get("type", ""))))
                    coords = geom.get("coordinates", [])
                    lines.append((depth + 3, "└─", "coordinates", "array [lon, lat]", truncate(coords)))
                    props = feat.get("properties", {})
                    lines.append((depth + 2, "└─", "properties", "objeto", ""))
                    prop_keys = list(props.keys())
                    for pi, pk in enumerate(prop_keys):
                        pc = "└─" if pi == len(prop_keys) - 1 else "├─"
                        lines.append((depth + 3, pc, pk, get_type_name(props[pk]), truncate(props[pk])))
            elif value.get("type") == "Point":
                coords = value.get("coordinates", [])
                lines.append((depth, connector, key, "GeoJSON Point", truncate(coords)))
            else:
                lines.append((depth, connector, key, "objeto", ""))
                sub = analyze_json_record(value, prefix + continuation, depth + 1)
                lines.extend(sub)
        elif isinstance(value, list):
            lines.append((depth, connector, key, f"array ({len(value)} elementos)", truncate(value[:2]) if len(value) <= 2 else truncate(value[:2]) + "..."))
        else:
            lines.append((depth, connector, key, get_type_name(value), truncate(value)))
    return lines


def render_tree(lines, title):
    """Render the analyzed structure as a nice tree."""
    output = []
    output.append("")
    output.append("=" * 90)
    output.append(title)
    output.append("=" * 90)
    output.append("")

    # Calculate column widths
    name_parts = []
    for depth, connector, name, tipo, ejemplo in lines:
        indent = "   " * depth
        full_name = f"{indent}{connector} {name}"
        name_parts.append(full_name)

    max_name = max(len(n) for n in name_parts) if name_parts else 30
    max_name = max(max_name, 30)

    header_fmt = f"   {'Campo':<{max_name}}  {'Tipo'}"
    sep = "   " + "-" * (max_name + 30)
    output.append(header_fmt)
    output.append(sep)

    for idx, (depth, connector, name, tipo, ejemplo) in enumerate(lines):
        indent = "   " * depth
        full_name = f"{indent}{connector} {name}"
        output.append(f"   {full_name:<{max_name}}  {tipo}")
    output.append("")
    return "\n".join(output)


def analyze_csv_structure(filepath):
    """Analyze the structure of a CSV file by reading a few records."""
    records = []
    with open(filepath, 'r', encoding='latin-1') as f:
        reader = csv.reader(f, delimiter=';')
        header = next(reader, None)
        if not header:
            return None, None
        for row in reader:
            if all(cell.strip() == '' for cell in row):
                continue
            if len(row) == len(header):
                record = dict(zip(header, row))
                records.append(record)
                if len(records) >= 5:
                    break
    return header, records


def infer_csv_type(values):
    """Infer the type of a CSV column from sample values."""
    non_empty = [v for v in values if v.strip()]
    if not non_empty:
        return "string (vacío)"

    # Check if it's a GeoJSON-like dict string
    sample = non_empty[0]
    if sample.startswith("{") and "'type'" in sample:
        if "'Point'" in sample:
            return "string (GeoJSON Point)"
        return "string (objeto)"

    # Check int
    try:
        all(int(v) for v in non_empty)
        return "entero (como string)"
    except (ValueError, TypeError):
        pass

    # Check float
    try:
        all(float(v) for v in non_empty)
        return "decimal (como string)"
    except (ValueError, TypeError):
        pass

    # Check date-like
    if any('T' in v and '-' in v for v in non_empty):
        return "string (ISO 8601)"

    return "string"


def main():
    base_dir = sys.argv[1] if len(sys.argv) > 1 else '.'

    # Find files
    json_files = []
    csv_files = []

    for root, dirs, files in sorted(os.walk(base_dir)):
        if 'trips' not in root:
            continue
        for fname in sorted(files):
            filepath = os.path.join(root, fname)
            if fname.endswith('.json'):
                json_files.append(filepath)
            elif fname.endswith('.csv'):
                csv_files.append(filepath)

    # ─── Analyze JSON structure ───────────────────────────────────────
    if json_files:
        # Pick first file and read a few records to find one with track and one without
        sample_with_track = None
        sample_without_track = None

        for jf in json_files[:3]:  # check up to 3 files
            print(f"Analizando estructura JSON: {jf}...")
            with open(jf, 'r', encoding='latin-1') as f:
                for line_num, line in enumerate(f):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        if 'track' in record and sample_with_track is None:
                            sample_with_track = record
                        if 'track' not in record and sample_without_track is None:
                            sample_without_track = record
                        if sample_with_track and sample_without_track:
                            break
                    except json.JSONDecodeError:
                        continue
                if sample_with_track and sample_without_track:
                    break

        # Render structure for record WITHOUT track
        if sample_without_track:
            lines = analyze_json_record(sample_without_track)
            print(render_tree(lines, "ESTRUCTURA DE UN REGISTRO JSON (sin campo track)"))

        # Render structure for record WITH track
        if sample_with_track:
            lines = analyze_json_record(sample_with_track)
            print(render_tree(lines, "ESTRUCTURA DE UN REGISTRO JSON (con campo track)"))

        # Show which fields differ
        if sample_with_track and sample_without_track:
            keys_with = set(sample_with_track.keys())
            keys_without = set(sample_without_track.keys())
            only_with_track = keys_with - keys_without
            only_without_track = keys_without - keys_with
            common = keys_with & keys_without

            print("=" * 90)
            print("COMPARACIÓN: campos en registros CON vs SIN track")
            print("=" * 90)
            print(f"   Campos comunes ({len(common)}): {', '.join(sorted(common))}")
            if only_with_track:
                print(f"   Solo CON track ({len(only_with_track)}): {', '.join(sorted(only_with_track))}")
            if only_without_track:
                print(f"   Solo SIN track ({len(only_without_track)}): {', '.join(sorted(only_without_track))}")
            print()

    # ─── Analyze CSV structure ────────────────────────────────────────
    if csv_files:
        # Pick first CSV
        csv_file = csv_files[0]
        print(f"Analizando estructura CSV: {csv_file}...")
        header, records = analyze_csv_structure(csv_file)

        if header and records:
            lines = []
            for i, col in enumerate(header):
                is_last = (i == len(header) - 1)
                connector = "└─" if is_last else "├─"
                values = [r.get(col, '') for r in records]
                tipo = infer_csv_type(values)
                ejemplo = truncate(values[0]) if values else ""
                lines.append((0, connector, col, tipo, ejemplo))

            print(render_tree(lines,
                f"ESTRUCTURA DE UN REGISTRO CSV\n"
                f"   Archivo: {os.path.basename(csv_file)}\n"
                f"   Separador: punto y coma (;)"))

    # ─── Field descriptions ──────────────────────────────────────────
    print("=" * 90)
    print("DICCIONARIO DE CAMPOS (JSON)")
    print("=" * 90)
    descriptions = OrderedDict([
        ("_id",              "Identificador único del registro (MongoDB ObjectId)"),
        ("user_day_code",    "Hash anonimizado del usuario + día (SHA-256)"),
        ("idplug_base",      "Número del anclaje donde se devolvió la bici"),
        ("idplug_station",   "ID de la estación donde se devolvió la bici"),
        ("idunplug_base",    "Número del anclaje donde se cogió la bici"),
        ("idunplug_station", "ID de la estación donde se cogió la bici"),
        ("unplug_hourTime",  "Fecha/hora de desanclaje (inicio del viaje)"),
        ("travel_time",      "Duración del viaje en segundos"),
        ("user_type",        "Tipo de usuario (1=anual, 2=ocasional, 3=empresa)"),
        ("ageRange",         "Rango de edad (0=desconocido, 1=<25, 2=25-40, 3=40-55, 4=55-65, 5=>65)"),
        ("zip_code",         "Código postal del usuario (puede estar vacío)"),
        ("track",            "Trayectoria GPS del viaje (GeoJSON FeatureCollection, NO siempre presente)"),
    ])

    for field, desc in descriptions.items():
        print(f"   {field:<22} {desc}")
    print()


if __name__ == '__main__':
    main()