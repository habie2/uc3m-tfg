"""
analizar_datos.py
-----------------
Analiza archivos JSON y CSV de un directorio y genera un reporte HTML detallado.

Uso:
    python analizar_datos.py                        # analiza carpeta actual
    python analizar_datos.py --dir /ruta/a/datos    # analiza carpeta específica
    python analizar_datos.py --dir ./datos --sample 2000  # muestra de 2000 filas
    python analizar_datos.py --dir ./datos --output mi_reporte.html
"""

import os
import sys
import json
import argparse
import warnings
from pathlib import Path
from datetime import datetime

import pandas as pd
import numpy as np

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────
# LECTURA DE ARCHIVOS
# ─────────────────────────────────────────────

ENCODINGS = ["utf-8", "latin-1", "cp1252", "iso-8859-1"]


def read_text(path: Path) -> tuple[str, str]:
    """Lee el contenido de un archivo probando varios encodings. Devuelve (texto, encoding)."""
    for enc in ENCODINGS:
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read(), enc
        except (UnicodeDecodeError, LookupError):
            continue
    # Último recurso: reemplazar bytes inválidos
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read(), "utf-8(replace)"


def flatten_record(record, prefix="", sep="__"):
    """Aplana recursivamente un dict anidado."""
    items = {}
    if not isinstance(record, dict):
        return {"value": record}
    for k, v in record.items():
        key = f"{prefix}{sep}{k}" if prefix else k
        if isinstance(v, dict):
            items.update(flatten_record(v, key, sep))
        elif isinstance(v, list):
            # Lista de dicts → serializar como string para no explotar columnas
            if v and isinstance(v[0], dict):
                items[key] = json.dumps(v, ensure_ascii=False)
            else:
                items[key] = json.dumps(v, ensure_ascii=False)
        else:
            items[key] = v
    return items


def records_to_df(records: list, sample: int) -> pd.DataFrame:
    """Convierte lista de registros a DataFrame, aplanando dicts anidados."""
    flat = [flatten_record(r) for r in records[:sample]]
    return pd.DataFrame(flat)


def load_json_file(path: Path, sample: int) -> pd.DataFrame:
    """Carga un JSON (array, JSON Lines, múltiples objetos, o dict raíz)."""
    text, enc = read_text(path)
    text = text.strip()

    # ── Intento 1: JSON estándar (array u objeto)
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return records_to_df(data, sample)
        elif isinstance(data, dict):
            for v in data.values():
                if isinstance(v, list) and v and isinstance(v[0], dict):
                    return records_to_df(v, sample)
            return records_to_df([data], sample)
    except json.JSONDecodeError:
        pass

    # ── Intento 2: JSON Lines (un objeto por línea)
    records = []
    errors = 0
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            records.append(obj)
            if len(records) >= sample:
                break
        except json.JSONDecodeError:
            errors += 1
            if errors > 10:
                break

    if records:
        return records_to_df(records, sample)

    # ── Intento 3: Múltiples JSONs concatenados (sin separador de línea)
    records = []
    decoder = json.JSONDecoder()
    pos = 0
    text_stripped = text.lstrip()
    offset = len(text) - len(text_stripped)
    pos = offset
    while pos < len(text) and len(records) < sample:
        try:
            obj, end_pos = decoder.raw_decode(text, pos)
            records.append(obj)
            pos = end_pos
            while pos < len(text) and text[pos] in " \t\n\r,":
                pos += 1
        except json.JSONDecodeError:
            break

    if records:
        return records_to_df(records, sample)

    raise ValueError(f"No se pudo parsear como JSON (encoding: {enc})")


def load_csv_file(path: Path, sample: int) -> pd.DataFrame:
    """Carga un CSV detectando separador y encoding."""
    for enc in ENCODINGS:
        try:
            df = pd.read_csv(path, nrows=sample, encoding=enc, sep=None, engine="python")
            return df
        except Exception:
            continue
    raise ValueError(f"No se pudo leer {path}")


def load_file(path: Path, sample: int) -> tuple[pd.DataFrame, str]:
    ext = path.suffix.lower()
    if ext in (".json", ".jsonl"):
        return load_json_file(path, sample), ext
    elif ext == ".csv":
        return load_csv_file(path, sample), ext
    else:
        raise ValueError(f"Formato no soportado: {ext}")


# ─────────────────────────────────────────────
# ANÁLISIS DE COLUMNAS
# ─────────────────────────────────────────────

def infer_semantic_type(series: pd.Series) -> str:
    """Intenta detectar el tipo semántico real del campo."""
    s = series.dropna()
    if len(s) == 0:
        return "vacío"
    if pd.api.types.is_bool_dtype(s):
        return "booleano"
    if pd.api.types.is_integer_dtype(s):
        return "entero"
    if pd.api.types.is_float_dtype(s):
        return "decimal"
    if pd.api.types.is_datetime64_any_dtype(s):
        return "fecha/hora"
    # Intentar parsear como fecha
    if s.dtype == object:
        sample_str = s.head(20).astype(str)
        try:
            pd.to_datetime(sample_str, infer_datetime_format=True)
            return "fecha (string)"
        except Exception:
            pass
        # Numérico disfrazado
        try:
            pd.to_numeric(s.head(50))
            return "numérico (string)"
        except Exception:
            pass
        avg_len = s.astype(str).str.len().mean()
        if avg_len > 100:
            return "texto largo"
        return "texto"
    return str(s.dtype)


def analyze_column(series: pd.Series) -> dict:
    total = len(series)
    null_count = series.isna().sum()
    # Contar vacíos explícitos en strings
    empty_count = 0
    if series.dtype == object:
        empty_count = (series.astype(str).str.strip().isin(["", "null", "None", "N/A", "na", "NaN"])).sum()

    non_null = series.dropna()
    unique_count = non_null.nunique()
    cardinality_pct = round(unique_count / total * 100, 1) if total > 0 else 0

    sem_type = infer_semantic_type(series)

    stats = {
        "tipo_pandas": str(series.dtype),
        "tipo_semantico": sem_type,
        "total_filas": total,
        "nulos": int(null_count),
        "pct_nulos": round(null_count / total * 100, 1) if total > 0 else 0,
        "vacios_explicitos": int(empty_count),
        "unicos": int(unique_count),
        "cardinalidad_pct": cardinality_pct,
        "muestra_valores": [],
        "min": None, "max": None, "media": None, "std": None,
        "min_len": None, "max_len": None, "avg_len": None,
    }

    # Muestra de valores frecuentes
    try:
        top = non_null.value_counts().head(5)
        stats["muestra_valores"] = [f"{v} ({c})" for v, c in top.items()]
    except Exception:
        pass

    # Stats numéricas
    if pd.api.types.is_numeric_dtype(non_null) and len(non_null) > 0:
        stats["min"] = round(float(non_null.min()), 4)
        stats["max"] = round(float(non_null.max()), 4)
        stats["media"] = round(float(non_null.mean()), 4)
        stats["std"] = round(float(non_null.std()), 4)

    # Stats de string
    if series.dtype == object and len(non_null) > 0:
        lens = non_null.astype(str).str.len()
        stats["min_len"] = int(lens.min())
        stats["max_len"] = int(lens.max())
        stats["avg_len"] = round(float(lens.mean()), 1)

    return stats


def analyze_dataframe(df: pd.DataFrame, filename: str, file_type: str, sample: int) -> dict:
    col_stats = {}
    for col in df.columns:
        col_stats[col] = analyze_column(df[col])

    # Duplicados
    try:
        dup_rows = int(df.duplicated().sum())
    except Exception:
        dup_rows = 0

    return {
        "filename": filename,
        "file_type": file_type,
        "rows_analyzed": len(df),
        "columns": list(df.columns),
        "n_columns": len(df.columns),
        "duplicate_rows": dup_rows,
        "col_stats": col_stats,
    }


# ─────────────────────────────────────────────
# GENERACIÓN DEL REPORTE HTML
# ─────────────────────────────────────────────

def badge_null(pct):
    if pct == 0:
        color = "#22c55e"
    elif pct < 25:
        color = "#f59e0b"
    elif pct < 50:
        color = "#ef4444"
    else:
        color = "#7f1d1d"
    return f'<span class="badge" style="background:{color}">{pct}% nulos</span>'


def badge_type(t):
    colors = {
        "entero": "#3b82f6", "decimal": "#6366f1", "texto": "#8b5cf6",
        "texto largo": "#a855f7", "booleano": "#10b981", "fecha/hora": "#f59e0b",
        "fecha (string)": "#f97316", "numérico (string)": "#06b6d4",
        "vacío": "#6b7280",
    }
    c = colors.get(t, "#64748b")
    return f'<span class="badge" style="background:{c}">{t}</span>'


def render_column_row(col, s):
    vals = "<br>".join(s["muestra_valores"][:3]) if s["muestra_valores"] else "—"
    num_stats = ""
    if s["min"] is not None:
        num_stats = f"min {s['min']} · max {s['max']} · media {s['media']}"
    elif s["min_len"] is not None:
        num_stats = f"len: {s['min_len']}–{s['max_len']} · avg {s['avg_len']}"

    card_class = "high-card" if s["cardinalidad_pct"] > 90 else ("low-card" if s["cardinalidad_pct"] < 5 else "")

    return f"""
    <tr>
      <td class="col-name">{col}</td>
      <td>{badge_type(s['tipo_semantico'])}</td>
      <td>{badge_null(s['pct_nulos'])}</td>
      <td class="{card_class}">{s['unicos']:,} <span class="dim">({s['cardinalidad_pct']}%)</span></td>
      <td class="dim small">{vals}</td>
      <td class="dim small">{num_stats}</td>
    </tr>"""


def render_file_section(info, idx):
    rows_html = "".join(render_column_row(c, info["col_stats"][c]) for c in info["columns"])
    dup_warn = f'<span class="badge" style="background:#ef4444">{info["duplicate_rows"]:,} filas duplicadas</span>' if info["duplicate_rows"] > 0 else ""
    ext_icon = "📋" if info["file_type"] == ".csv" else "📦"

    return f"""
    <section class="file-section" id="file-{idx}">
      <div class="file-header">
        <span class="file-icon">{ext_icon}</span>
        <div>
          <h2 class="file-title">{info['filename']}</h2>
          <div class="file-meta">
            <span class="meta-pill">{info['rows_analyzed']:,} filas analizadas</span>
            <span class="meta-pill">{info['n_columns']} columnas</span>
            <span class="meta-pill">{info['file_type']}</span>
            {dup_warn}
          </div>
        </div>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Campo</th><th>Tipo</th><th>Nulos</th>
              <th>Cardinalidad</th><th>Top valores</th><th>Stats</th>
            </tr>
          </thead>
          <tbody>{rows_html}</tbody>
        </table>
      </div>
    </section>"""


def generate_comparativa_html(results: list[dict], output_path: str):
    """Genera un dashboard comparativo entre archivos (uno por mes)."""
    now = datetime.now().strftime("%d/%m/%Y %H:%M")

    all_col_sets = [set(r["columns"]) for r in results]
    common_cols = sorted(set.intersection(*all_col_sets)) if all_col_sets else []
    all_cols = sorted(set.union(*all_col_sets)) if all_col_sets else []

    months = [r["filename"] for r in results]
    n = len(results)
    rows_data = [r["rows_analyzed"] for r in results]
    rows_max = max(rows_data) if rows_data else 1

    def null_cell(pct):
        if pct == 0: bg,fg = "#dcfce7","#166534"
        elif pct < 25: bg,fg = "#fef9c3","#854d0e"
        elif pct < 50: bg,fg = "#fee2e2","#991b1b"
        else: bg,fg = "#7f1d1d","#fecaca"
        return f'<td style="background:{bg};color:{fg};text-align:center;font-size:12px;padding:6px 4px">{pct}%</td>'

    def card_cell(pct):
        if pct > 90: bg,fg = "#fff7ed","#9a3412"
        elif pct < 5: bg,fg = "#f5f3ff","#5b21b6"
        else: bg,fg = "#f8fafc","#334155"
        return f'<td style="background:{bg};color:{fg};text-align:center;font-size:12px;padding:6px 4px">{pct}%</td>'

    month_headers = "".join(
        f'<th style="font-size:11px;font-weight:600;padding:6px 8px;text-align:center;white-space:nowrap;color:#475569;border-bottom:1px solid #e2e8f0">{m.replace(".json","").replace(".csv","")}</th>'
        for m in months)

    absent_cell = '<td style="background:#f1f5f9;color:#cbd5e1;text-align:center;font-size:12px;padding:6px 4px">—</td>'

    null_rows = ""
    for col in all_cols:
        is_common = col in common_cols
        row_style = "" if is_common else "background:#fafafa;"
        cells = ""
        for r in results:
            if col in r["col_stats"]:
                cells += null_cell(r["col_stats"][col].get("pct_nulos", 0))
            else:
                cells += absent_cell
        tipo = next((r["col_stats"][col].get("tipo_semantico","") for r in results if col in r["col_stats"]), "")
        mark = "" if is_common else ' <span style="font-size:10px;color:#94a3b8;font-weight:400">(parcial)</span>'
        null_rows += f'''<tr style="{row_style}">
          <td style="font-size:12px;padding:6px 10px;white-space:nowrap;font-weight:500;color:#1e293b;border-right:1px solid #e2e8f0">{col}{mark}</td>
          <td style="font-size:11px;padding:6px 8px;color:#94a3b8;border-right:1px solid #e2e8f0">{tipo}</td>
          {cells}</tr>'''

    card_rows = ""
    for col in all_cols:
        is_common = col in common_cols
        row_style = "" if is_common else "background:#fafafa;"
        cells = ""
        for r in results:
            if col in r["col_stats"]:
                cells += card_cell(r["col_stats"][col].get("cardinalidad_pct", 0))
            else:
                cells += absent_cell
        mark = "" if is_common else ' <span style="font-size:10px;color:#94a3b8;font-weight:400">(parcial)</span>'
        card_rows += f'''<tr style="{row_style}">
          <td style="font-size:12px;padding:6px 10px;white-space:nowrap;font-weight:500;color:#1e293b;border-right:1px solid #e2e8f0">{col}{mark}</td>
          {cells}</tr>'''

    exclusive_rows = ""
    for col in sorted(all_cols):
        present = [r["filename"] for r in results if col in r["col_stats"]]
        if len(present) < n:
            absent = [r["filename"] for r in results if col not in r["col_stats"]]
            exclusive_rows += f'''<tr>
              <td style="font-size:12px;padding:5px 10px;color:#1e293b;font-weight:500">{col}</td>
              <td style="font-size:11px;padding:5px 10px;color:#16a34a">{", ".join(p.replace(".json","").replace(".csv","") for p in present)}</td>
              <td style="font-size:11px;padding:5px 10px;color:#dc2626">{", ".join(a.replace(".json","").replace(".csv","") for a in absent)}</td></tr>'''

    exclusive_section = ""
    if exclusive_rows:
        exclusive_section = f'''<section class="section">
          <div class="section-title">Columnas no comunes</div>
          <div class="section-sub">Campos que no aparecen en todos los archivos</div>
          <div class="table-wrap"><table>
            <thead><tr><th style="width:200px">Campo</th><th style="color:#16a34a">Presente en</th><th style="color:#dc2626">Ausente en</th></tr></thead>
            <tbody>{exclusive_rows}</tbody></table></div></section>'''

    bar_items = ""
    for r in results:
        pct = round(r["rows_analyzed"] / rows_max * 100)
        label = r["filename"].replace(".json","").replace(".csv","")
        bar_items += f'''<div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">
          <span style="font-size:12px;color:#475569;width:80px;text-align:right;flex-shrink:0">{label}</span>
          <div style="flex:1;background:#f1f5f9;border-radius:4px;height:18px;overflow:hidden">
            <div style="width:{pct}%;background:#3b82f6;height:100%;border-radius:4px"></div></div>
          <span style="font-size:12px;color:#64748b;width:70px">{r["rows_analyzed"]:,} filas</span></div>'''

    dup_items = ""
    for r in results:
        label = r["filename"].replace(".json","").replace(".csv","")
        d = r["duplicate_rows"]
        color = "#dc2626" if d > 0 else "#16a34a"
        dup_items += f'<div style="display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid #f1f5f9"><span style="font-size:12px;color:#475569">{label}</span><span style="font-size:12px;font-weight:600;color:{color}">{d:,}</span></div>'

    common_count = len(common_cols)
    total_unique = len(all_cols)
    only_some = total_unique - common_count

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <title>Comparativa mensual</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:'Inter',sans-serif;background:#f8fafc;color:#1e293b}}
    header{{background:#fff;border-bottom:1px solid #e2e8f0;padding:0 2rem;height:56px;display:flex;align-items:center;gap:1rem;position:sticky;top:0;z-index:10}}
    .logo{{font-weight:600;font-size:15px}}.logo span{{color:#3b82f6}}
    .chip{{font-size:11px;background:#f1f5f9;color:#475569;padding:3px 10px;border-radius:99px;font-weight:500}}
    .container{{max-width:1200px;margin:0 auto;padding:2rem}}
    .grid-4{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin-bottom:2rem}}
    .stat-card{{background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:1rem 1.25rem}}
    .stat-label{{font-size:11px;color:#94a3b8;font-weight:500;text-transform:uppercase;letter-spacing:.05em;margin-bottom:6px}}
    .stat-value{{font-size:26px;font-weight:600;color:#0f172a;line-height:1}}
    .stat-sub{{font-size:12px;color:#64748b;margin-top:4px}}
    .section{{background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:1.5rem;margin-bottom:1.5rem}}
    .section-title{{font-size:14px;font-weight:600;color:#0f172a;margin-bottom:4px}}
    .section-sub{{font-size:12px;color:#94a3b8;margin-bottom:1.25rem}}
    .table-wrap{{overflow-x:auto;border:1px solid #e2e8f0;border-radius:8px}}
    table{{width:100%;border-collapse:collapse}}
    th{{font-size:11px;font-weight:600;color:#475569;padding:8px 10px;background:#f8fafc;text-align:left;border-bottom:1px solid #e2e8f0}}
    td{{border-bottom:1px solid #f1f5f9;vertical-align:middle}}
    tr:last-child td{{border-bottom:none}}
    .two-col{{display:grid;grid-template-columns:1fr 1fr;gap:1.5rem;margin-bottom:1.5rem}}
    .legend{{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:12px}}
    .leg-item{{display:flex;align-items:center;gap:5px;font-size:11px;color:#64748b}}
    .leg-dot{{width:10px;height:10px;border-radius:2px}}
    .tabs{{display:flex;gap:2px;margin-bottom:1rem;background:#f1f5f9;border-radius:8px;padding:3px;width:fit-content}}
    .tab{{padding:5px 14px;font-size:12px;font-weight:500;border-radius:6px;cursor:pointer;color:#64748b;border:none;background:none}}
    .tab.active{{background:#fff;color:#0f172a;box-shadow:0 1px 3px rgba(0,0,0,.08)}}
    .tab-content{{display:none}}.tab-content.active{{display:block}}
    footer{{text-align:center;color:#94a3b8;font-size:11px;padding:2rem}}
    @media(max-width:700px){{.two-col{{grid-template-columns:1fr}}}}
  </style>
</head>
<body>
<header>
  <div class="logo">data<span>/</span>comparativa</div>
  <div style="margin-left:auto;display:flex;gap:8px">
    <span class="chip">{n} archivos</span>
    <span class="chip">{common_count} cols comunes</span>
    <span class="chip">{now}</span>
  </div>
</header>
<div class="container">
  <div class="grid-4">
    <div class="stat-card"><div class="stat-label">Archivos</div><div class="stat-value">{n}</div><div class="stat-sub">analizados</div></div>
    <div class="stat-card"><div class="stat-label">Total filas</div><div class="stat-value">{sum(rows_data):,}</div><div class="stat-sub">suma de todos los meses</div></div>
    <div class="stat-card"><div class="stat-label">Cols comunes</div><div class="stat-value">{common_count}</div><div class="stat-sub">de {total_unique} columnas</div></div>
    <div class="stat-card"><div class="stat-label">Cols irregulares</div><div class="stat-value" style="color:{'#dc2626' if only_some > 0 else '#16a34a'}">{only_some}</div><div class="stat-sub">no en todos los meses</div></div>
  </div>
  <div class="two-col">
    <div class="section"><div class="section-title">Filas por archivo</div><div class="section-sub">Volumen mensual</div>{bar_items}</div>
    <div class="section"><div class="section-title">Filas duplicadas</div><div class="section-sub">Registros idénticos</div>{dup_items}</div>
  </div>
  <div class="section">
    <div class="section-title">Comparativa por columna</div>
    <div class="section-sub">Todos los campos ({total_unique} columnas · {common_count} comunes · {only_some} parciales) — <span style="color:#94a3b8">— = campo ausente en ese mes</span></div>
    <div class="tabs">
      <button class="tab active" onclick="switchTab('nulos',this)">% Nulos</button>
      <button class="tab" onclick="switchTab('cardinalidad',this)">Cardinalidad</button>
    </div>
    <div id="tab-nulos" class="tab-content active">
      <div class="legend">
        <div class="leg-item"><div class="leg-dot" style="background:#dcfce7"></div>0%</div>
        <div class="leg-item"><div class="leg-dot" style="background:#fef9c3"></div>&lt;10%</div>
        <div class="leg-item"><div class="leg-dot" style="background:#fee2e2"></div>&lt;50%</div>
        <div class="leg-item"><div class="leg-dot" style="background:#7f1d1d"></div>≥50%</div>
      </div>
      <div class="table-wrap"><table>
        <thead><tr><th style="width:180px">Campo</th><th style="width:90px;color:#94a3b8">Tipo</th>{month_headers}</tr></thead>
        <tbody>{null_rows}</tbody></table></div></div>
    <div id="tab-cardinalidad" class="tab-content">
      <div class="legend">
        <div class="leg-item"><div class="leg-dot" style="background:#f5f3ff"></div>&lt;5% enum/FK</div>
        <div class="leg-item"><div class="leg-dot" style="background:#f8fafc"></div>normal</div>
        <div class="leg-item"><div class="leg-dot" style="background:#fff7ed"></div>&gt;90% ID/hash</div>
      </div>
      <div class="table-wrap"><table>
        <thead><tr><th style="width:180px">Campo</th>{month_headers}</tr></thead>
        <tbody>{card_rows}</tbody></table></div></div>
  </div>
  {exclusive_section}
</div>
<footer>Generado el {now} · analizar_datos.py</footer>
<script>
function switchTab(name,btn){{
  document.querySelectorAll('.tab-content').forEach(el=>el.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(el=>el.classList.remove('active'));
  document.getElementById('tab-'+name).classList.add('active');
  btn.classList.add('active');
}}
</script>
</body></html>"""
    with open(output_path,"w",encoding="utf-8") as f:
        f.write(html)


def generate_html(results: list[dict], output_path: str, sample: int):
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    total_files = len(results)
    total_cols = sum(r["n_columns"] for r in results)

    # Sidebar index
    sidebar_items = "".join(
        f'<li><a href="#file-{i}" class="sidebar-link">'
        f'{"📋" if r["file_type"]==".csv" else "📦"} {r["filename"]}'
        f'<span class="sidebar-count">{r["n_columns"]} cols</span></a></li>'
        for i, r in enumerate(results)
    )

    # Alertas globales
    alerts = []
    for r in results:
        for col, s in r["col_stats"].items():
            if s["pct_nulos"] > 50:
                alerts.append(f"<li><strong>{r['filename']}</strong> › <code>{col}</code>: {s['pct_nulos']}% nulos</li>")
    alerts_html = ""
    if alerts:
        alerts_html = f"""
        <div class="alert-box">
          <div class="alert-title">⚠️ Columnas con más del 50% de nulos</div>
          <ul>{"".join(alerts[:10])}</ul>
        </div>"""

    sections = "".join(render_file_section(r, i) for i, r in enumerate(results))

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Análisis de Datos · {now}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=Syne:wght@400;700;800&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    :root {{
      --bg: #0d0f14;
      --surface: #141720;
      --border: #1f2535;
      --accent: #4fffb0;
      --accent2: #ff6b6b;
      --text: #e2e8f0;
      --dim: #64748b;
      --header-h: 60px;
      --sidebar-w: 260px;
    }}

    html {{ scroll-behavior: smooth; }}

    body {{
      font-family: 'IBM Plex Mono', monospace;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
    }}

    /* ── HEADER ── */
    header {{
      position: fixed; top: 0; left: 0; right: 0; z-index: 100;
      height: var(--header-h);
      background: rgba(13,15,20,0.95);
      border-bottom: 1px solid var(--border);
      backdrop-filter: blur(12px);
      display: flex; align-items: center; padding: 0 2rem; gap: 1rem;
    }}
    .header-logo {{
      font-family: 'Syne', sans-serif;
      font-weight: 800; font-size: 1.1rem;
      color: var(--accent);
      letter-spacing: -0.02em;
    }}
    .header-logo span {{ color: var(--dim); font-weight: 400; }}
    .header-stats {{ margin-left: auto; display: flex; gap: 1.5rem; }}
    .h-stat {{ font-size: 0.72rem; color: var(--dim); }}
    .h-stat strong {{ color: var(--text); }}

    /* ── LAYOUT ── */
    .layout {{
      display: flex;
      margin-top: var(--header-h);
      min-height: calc(100vh - var(--header-h));
    }}

    /* ── SIDEBAR ── */
    aside {{
      width: var(--sidebar-w);
      flex-shrink: 0;
      position: sticky;
      top: var(--header-h);
      height: calc(100vh - var(--header-h));
      overflow-y: auto;
      border-right: 1px solid var(--border);
      padding: 1.5rem 0;
    }}
    .sidebar-label {{
      font-size: 0.65rem; font-weight: 600;
      text-transform: uppercase; letter-spacing: 0.1em;
      color: var(--dim); padding: 0 1.25rem 0.75rem;
    }}
    aside ul {{ list-style: none; }}
    .sidebar-link {{
      display: flex; align-items: center; justify-content: space-between;
      padding: 0.55rem 1.25rem;
      color: var(--dim); text-decoration: none;
      font-size: 0.78rem;
      transition: all 0.15s;
      border-left: 2px solid transparent;
    }}
    .sidebar-link:hover {{
      color: var(--text);
      border-left-color: var(--accent);
      background: rgba(79,255,176,0.04);
    }}
    .sidebar-count {{
      font-size: 0.65rem;
      background: var(--border);
      padding: 1px 6px; border-radius: 99px;
    }}

    /* ── MAIN ── */
    main {{
      flex: 1; padding: 2rem 2.5rem; overflow: hidden;
    }}

    /* ── ALERT ── */
    .alert-box {{
      background: rgba(239,68,68,0.08);
      border: 1px solid rgba(239,68,68,0.3);
      border-radius: 8px;
      padding: 1rem 1.25rem;
      margin-bottom: 2rem;
    }}
    .alert-title {{
      font-weight: 600; margin-bottom: 0.5rem;
      color: #fca5a5; font-size: 0.85rem;
    }}
    .alert-box ul {{ list-style: none; }}
    .alert-box li {{ font-size: 0.78rem; color: var(--dim); padding: 2px 0; }}
    .alert-box code {{
      background: var(--border); padding: 1px 5px;
      border-radius: 3px; color: var(--text);
    }}

    /* ── FILE SECTION ── */
    .file-section {{
      margin-bottom: 3rem;
      animation: fadeUp 0.4s ease both;
    }}
    @keyframes fadeUp {{
      from {{ opacity: 0; transform: translateY(12px); }}
      to {{ opacity: 1; transform: translateY(0); }}
    }}
    .file-header {{
      display: flex; align-items: flex-start; gap: 1rem;
      margin-bottom: 1.25rem;
    }}
    .file-icon {{ font-size: 1.8rem; line-height: 1; margin-top: 3px; }}
    .file-title {{
      font-family: 'Syne', sans-serif;
      font-size: 1.2rem; font-weight: 700;
      color: var(--text);
      word-break: break-all;
    }}
    .file-meta {{ display: flex; flex-wrap: wrap; gap: 0.4rem; margin-top: 0.4rem; }}
    .meta-pill {{
      font-size: 0.7rem;
      background: var(--border);
      color: var(--dim);
      padding: 2px 10px; border-radius: 99px;
    }}

    /* ── TABLE ── */
    .table-wrap {{
      overflow-x: auto;
      border: 1px solid var(--border);
      border-radius: 8px;
    }}
    table {{
      width: 100%; border-collapse: collapse;
      font-size: 0.78rem;
    }}
    thead {{ background: var(--surface); }}
    th {{
      text-align: left;
      padding: 0.65rem 1rem;
      font-size: 0.65rem; font-weight: 600;
      text-transform: uppercase; letter-spacing: 0.08em;
      color: var(--dim);
      border-bottom: 1px solid var(--border);
      white-space: nowrap;
    }}
    td {{
      padding: 0.6rem 1rem;
      border-bottom: 1px solid var(--border);
      vertical-align: top;
    }}
    tr:last-child td {{ border-bottom: none; }}
    tr:hover td {{ background: rgba(255,255,255,0.02); }}

    .col-name {{
      font-weight: 600; color: var(--accent);
      white-space: nowrap; max-width: 200px;
      overflow: hidden; text-overflow: ellipsis;
    }}
    .dim {{ color: var(--dim); }}
    .small {{ font-size: 0.72rem; }}
    .high-card {{ color: #fb923c; }}
    .low-card {{ color: #a78bfa; }}

    /* ── BADGES ── */
    .badge {{
      display: inline-block;
      font-size: 0.65rem; font-weight: 600;
      padding: 2px 8px; border-radius: 4px;
      color: #fff; white-space: nowrap;
    }}

    /* ── FOOTER ── */
    footer {{
      border-top: 1px solid var(--border);
      padding: 1.5rem 2.5rem;
      color: var(--dim); font-size: 0.72rem;
      display: flex; justify-content: space-between;
    }}
  </style>
</head>
<body>

<header>
  <div class="header-logo">data<span>/</span>inspector</div>
  <div class="header-stats">
    <div class="h-stat"><strong>{total_files}</strong> archivos</div>
    <div class="h-stat"><strong>{total_cols}</strong> columnas</div>
    <div class="h-stat">muestra <strong>{sample:,}</strong> filas</div>
    <div class="h-stat">generado <strong>{now}</strong></div>
  </div>
</header>

<div class="layout">
  <aside>
    <div class="sidebar-label">Archivos analizados</div>
    <ul>{sidebar_items}</ul>
  </aside>

  <main>
    {alerts_html}
    {sections}
  </main>
</div>

<footer>
  <span>analizar_datos.py · pandas {pd.__version__}</span>
  <span>muestra máx: {sample:,} filas por archivo</span>
</footer>

</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def infer_group(path: Path) -> tuple[str, str]:
    """
    Infiere año y tipo (trips/stations/other) a partir de la ruta.
    Busca en las partes de la ruta palabras clave como 'trips', 'stations',
    y años con formato 4 dígitos (ej: bicimad_2017 → 2017).
    """
    parts = [p.lower() for p in path.parts]
    # Tipo: busca 'trips' o 'stations' en las carpetas padre
    tipo = "other"
    for p in parts:
        if "trips" in p:
            tipo = "trips"
            break
        if "station" in p:
            tipo = "stations"
            break
    # Año: busca carpeta que contenga 4 dígitos seguidos (ej: bicimad_2017, 2017, etc.)
    year = "unknown"
    for p in parts:
        import re
        m = re.search(r"(20\d{2}|19\d{2})", p)
        if m:
            year = m.group(1)
    return year, tipo


def main():
    parser = argparse.ArgumentParser(description="Análisis de columnas para JSON y CSV")
    parser.add_argument("--dir", default=".", help="Directorio raíz con los archivos (default: .)")
    parser.add_argument("--sample", type=int, default=5000, help="Máx filas a leer por archivo (default: 5000, 0 = todo)")
    parser.add_argument("--outdir", default="reportes", help="Carpeta donde guardar los reportes (default: reportes/)")
    args = parser.parse_args()

    base = Path(args.dir)
    all_files = sorted(
        [p for p in base.rglob("*") if p.suffix.lower() in (".json", ".jsonl", ".csv")],
        key=lambda p: (p.parts)
    )

    if not all_files:
        print(f"❌ No se encontraron archivos JSON o CSV en: {base.resolve()}")
        sys.exit(1)

    sample = args.sample if args.sample > 0 else 10_000_000
    label = "archivo completo" if args.sample == 0 else f"muestra de hasta {sample:,} filas"

    # Agrupar archivos por (año, tipo)
    from collections import defaultdict
    groups: dict[tuple, list[Path]] = defaultdict(list)
    for path in all_files:
        year, tipo = infer_group(path)
        groups[(year, tipo)].append(path)

    print(f"🔍 {len(all_files)} archivos en '{base.resolve()}'")
    print(f"📂 {len(groups)} grupos detectados: {sorted(groups.keys())}")
    print(f"📊 Analizando {label} por archivo...\n")

    # Crear carpeta de salida
    out_base = Path(args.outdir)
    out_base.mkdir(exist_ok=True)

    generated = []

    for (year, tipo), paths in sorted(groups.items()):
        group_label = f"{year}_{tipo}"
        print(f"\n── Grupo: {group_label} ({len(paths)} archivos) ──")

        results = []
        for path in paths:
            try:
                df, ftype = load_file(path, sample)
                info = analyze_dataframe(df, path.name, ftype, sample)
                # Guardar ruta relativa para contexto
                info["rel_path"] = str(path.relative_to(base))
                results.append(info)
                print(f"  ✅ {path.name} — {info['rows_analyzed']:,} filas · {info['n_columns']} columnas")
            except Exception as e:
                print(f"  ⚠️  {path.name} — ERROR: {e}")

        if not results:
            print(f"  ❌ Sin resultados para {group_label}, saltando.")
            continue

        # Reporte detallado
        det_path = out_base / f"{group_label}_detalle.html"
        generate_html(results, str(det_path), sample)

        # Reporte comparativo
        comp_path = out_base / f"{group_label}_comparativa.html"
        generate_comparativa_html(results, str(comp_path))

        generated.append((group_label, det_path, comp_path))

    print(f"\n{'═'*55}")
    print(f"✨ Reportes generados en: {out_base.resolve()}/\n")
    for label, det, comp in generated:
        print(f"  [{label}]")
        print(f"    detalle:     {det.name}")
        print(f"    comparativa: {comp.name}")
    print()


if __name__ == "__main__":
    main()