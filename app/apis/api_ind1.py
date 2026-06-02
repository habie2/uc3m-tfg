"""
Indicador 1 — Saturación de estaciones BiciMAD
================================================
Blueprint: /api/ind1/…

Fase 2: Agregado/Desagregado + filtros multi-select + años
"""

from flask import Blueprint, jsonify, request
from datetime import datetime
import psycopg2.extras
from db import get_conn

bp = Blueprint("ind1", __name__)

MONTH_NAMES = {
    1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
    5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
    9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre',
}


# ── Helpers ───────────────────────────────────────────────

def _parse_int_list(raw, lo, hi):
    """Parse comma-separated ints, validate range, return list or None."""
    if not raw:
        return None
    try:
        vals = [int(x) for x in raw.split(",") if x.strip()]
    except ValueError:
        return None
    return [v for v in vals if lo <= v <= hi] or None


def _build_sat_dict(rows):
    result = {}
    for source_id, hora, sat in rows:
        key = str(source_id)
        if key not in result:
            result[key] = [None] * 24
        result[key][int(hora)] = round(float(sat), 4) if sat is not None else None
    for key in result:
        arr = result[key]
        for i in range(24):
            if arr[i] is None:
                prev_val = next((arr[j] for j in range(i - 1, -1, -1) if arr[j] is not None), None)
                next_val = next((arr[j] for j in range(i + 1, 24)     if arr[j] is not None), None)
                if prev_val is not None and next_val is not None:
                    arr[i] = round((prev_val + next_val) / 2, 4)
                elif prev_val is not None:
                    arr[i] = prev_val
                elif next_val is not None:
                    arr[i] = next_val
                else:
                    arr[i] = 0.5
        result[key] = arr
    return result


# ── Endpoints ─────────────────────────────────────────────

@bp.route("/stations")
def api_stations():
    # Una estación física (source_id) puede tener varias versiones en `station`,
    # cada una con su propio station_id artificial. Los snapshots y la saturación
    # se agregan por source_id, así que aquí devolvemos UN punto por source_id,
    # usando los metadatos de la versión con el snapshot más reciente.
    sql = """
        SELECT DISTINCT ON (st.source_id)
               st.source_id AS id, st.source_id, st.name,
               st.latitude AS lat, st.longitude AS lng, st.total_bases AS cap
        FROM station st
        LEFT JOIN station_snapshot ss ON ss.station_id = st.station_id
        WHERE st.latitude IS NOT NULL AND st.longitude IS NOT NULL
        GROUP BY st.source_id, st.name,
                 st.latitude, st.longitude, st.total_bases
        ORDER BY st.source_id, MAX(ss.captured_at) DESC NULLS LAST
    """
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql)
            rows = cur.fetchall()
    for r in rows:
        r['lat'] = float(r['lat'])
        r['lng'] = float(r['lng'])
        r['cap'] = int(r['cap'])
    return jsonify(rows)


@bp.route("/saturation")
def api_saturation():
    """
    Modo AGREGADO — combina múltiples días según filtros.

    Query params (todos opcionales):
      days     — comma-separated ISO days (1=Mon … 7=Sun).  Empty = all.
      months   — comma-separated months (1–12).             Empty = all.
      years    — comma-separated years.                     Empty = all.
      holiday  — "only" | "exclude" | "all" (default "all").
      hour     — single int 0–23. If set, returns only that hour.
    """
    days_raw    = request.args.get("days", "")
    months_raw  = request.args.get("months", "")
    years_raw   = request.args.get("years", "")
    holiday     = request.args.get("holiday", "all")
    hour_raw    = request.args.get("hour", "")

    days   = _parse_int_list(days_raw,   1, 7)
    months = _parse_int_list(months_raw, 1, 12)
    years  = _parse_int_list(years_raw, 2000, 2099)

    hour = None
    if hour_raw:
        try:
            hour = int(hour_raw)
            if not (0 <= hour <= 23):
                return jsonify({"error": "hour debe estar entre 0 y 23"}), 400
        except ValueError:
            return jsonify({"error": "hour debe ser un entero"}), 400

    clauses = []
    params = {}

    if days:
        clauses.append("iso_dow = ANY(%(days)s)")
        params["days"] = days

    if months:
        clauses.append("month = ANY(%(months)s)")
        params["months"] = months

    if years:
        clauses.append("year = ANY(%(years)s)")
        params["years"] = years

    if holiday == "only":
        clauses.append("is_holiday = TRUE")
    elif holiday == "exclude":
        clauses.append("is_holiday = FALSE")

    if hour is not None:
        clauses.append("hora = %(hour)s")
        params["hour"] = hour

    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""

    # Leemos de la vista materializada pre-agregada (datos históricos fijos).
    # La media se reconstruye como SUM(sat_sum)/SUM(sat_cnt) sobre los buckets
    # que pasan el filtro — una media de medias sería incorrecta.
    sql = f"""
        SELECT source_id,
               hora,
               SUM(sat_sum) / NULLIF(SUM(sat_cnt), 0) AS sat
        FROM mv_ind1_sat_agg
        {where}
        GROUP BY source_id, hora
        ORDER BY source_id, hora
    """

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

    return jsonify(_build_sat_dict(rows))


@bp.route("/saturation-date")
def api_saturation_date():
    """Modo DESAGREGADO — un solo día concreto."""
    date_str = request.args.get("date", "")
    try:
        target = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"error": "Formato de fecha inválido. Usa YYYY-MM-DD"}), 400

    sql = """
        SELECT st.source_id, EXTRACT(HOUR FROM ss.captured_at)::int AS hora,
               AVG(ss.dock_bikes::float / NULLIF(ss.operative_bases, 0)) AS sat
        FROM station_snapshot ss
        JOIN station st ON st.station_id = ss.station_id
        WHERE ss.captured_at::date = %(target)s AND ss.activate = 1 AND ss.operative_bases > 0
        GROUP BY st.source_id, hora ORDER BY st.source_id, hora
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {"target": target})
            rows = cur.fetchall()
    return jsonify(_build_sat_dict(rows))


@bp.route("/is-holiday")
def api_is_holiday():
    date_str = request.args.get("date", "")
    try:
        target = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"error": "Formato inválido"}), 400
    sql = "SELECT COUNT(*) FROM holidays WHERE holiday_date = %(d)s"
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {"d": target})
            count = cur.fetchone()[0]
    return jsonify({"date": date_str, "holiday": count > 0})


@bp.route("/date-range")
def api_date_range():
    sql = """
        SELECT MIN(captured_at::date)::text AS min_date,
               MAX(captured_at::date)::text AS max_date
        FROM station_snapshot
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            row = cur.fetchone()
    return jsonify({"min": row[0], "max": row[1]})


@bp.route("/available-months")
def api_available_months():
    # Lee de la vista pre-agregada (columna month ya extraída) en lugar de
    # escanear station_snapshot entero.
    sql = """
        SELECT DISTINCT month
        FROM mv_ind1_sat_agg ORDER BY month
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
    months = [{"value": r[0], "label": MONTH_NAMES[r[0]]} for r in rows]
    return jsonify(months)


@bp.route("/available-years")
def api_available_years():
    # Lee de la vista pre-agregada (columna year ya extraída) en lugar de
    # escanear station_snapshot entero.
    sql = """
        SELECT DISTINCT year
        FROM mv_ind1_sat_agg ORDER BY year
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
    years = [{"value": r[0], "label": str(r[0])} for r in rows]
    return jsonify(years)


@bp.route("/station-versions")
def api_station_versions():
    try:
        source_id = int(request.args.get("source_id", 0))
    except ValueError:
        return jsonify({"error": "source_id debe ser un entero"}), 400
    if not source_id:
        return jsonify({"error": "Parámetro 'source_id' requerido"}), 400
    sql = """
        SELECT st.station_id, st.number, st.name, st.address,
               st.latitude, st.longitude, st.total_bases,
               MIN(ss.captured_at) AS first_seen,
               MAX(ss.captured_at) AS last_seen,
               COUNT(ss.captured_at) AS snapshot_count
        FROM station st
        LEFT JOIN station_snapshot ss ON ss.station_id = st.station_id
        WHERE st.source_id = %(sid)s
        GROUP BY st.station_id ORDER BY first_seen
    """
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, {"sid": source_id})
            rows = cur.fetchall()
    for r in rows:
        r['latitude']       = float(r['latitude'])  if r['latitude']  else None
        r['longitude']      = float(r['longitude']) if r['longitude'] else None
        r['total_bases']    = int(r['total_bases'])
        r['snapshot_count'] = int(r['snapshot_count'])
        r['first_seen']     = r['first_seen'].isoformat() if r['first_seen'] else None
        r['last_seen']      = r['last_seen'].isoformat()  if r['last_seen']  else None
    return jsonify(rows)