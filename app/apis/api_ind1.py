"""
Indicador 1 — Saturación de estaciones BiciMAD
================================================
Blueprint: /api/ind1/…

Fase 1: Agregado/Desagregado + filtros multi-select
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
    for station_id, hora, sat in rows:
        key = str(station_id)
        if key not in result:
            result[key] = [None] * 24
        result[key][int(hora)] = round(float(sat), 4) if sat else None
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
    sql = """
        SELECT station_id AS id, source_id, name,
               latitude AS lat, longitude AS lng, total_bases AS cap
        FROM station
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
        ORDER BY source_id, station_id
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
      holiday  — "only" | "exclude" | "all" (default "all").
      hour     — single int 0–23. If set, returns only that hour.
    """
    days_raw    = request.args.get("days", "")
    months_raw  = request.args.get("months", "")
    holiday     = request.args.get("holiday", "all")
    hour_raw    = request.args.get("hour", "")

    days   = _parse_int_list(days_raw,   1, 7)
    months = _parse_int_list(months_raw, 1, 12)

    hour = None
    if hour_raw:
        try:
            hour = int(hour_raw)
            if not (0 <= hour <= 23):
                return jsonify({"error": "hour debe estar entre 0 y 23"}), 400
        except ValueError:
            return jsonify({"error": "hour debe ser un entero"}), 400

    clauses = [
        "ss.activate = 1",
        "ss.operative_bases > 0",
    ]
    params = {}

    if days:
        clauses.append("EXTRACT(ISODOW FROM ss.captured_at)::int = ANY(%(days)s)")
        params["days"] = days

    if months:
        clauses.append("EXTRACT(MONTH FROM ss.captured_at)::int = ANY(%(months)s)")
        params["months"] = months

    if holiday == "only":
        clauses.append("h.holiday_date IS NOT NULL")
    elif holiday == "exclude":
        clauses.append("h.holiday_date IS NULL")

    if hour is not None:
        clauses.append("EXTRACT(HOUR FROM ss.captured_at)::int = %(hour)s")
        params["hour"] = hour

    where = " AND ".join(clauses)

    sql = f"""
        SELECT ss.station_id,
               EXTRACT(HOUR FROM ss.captured_at)::int AS hora,
               AVG(ss.dock_bikes::float / NULLIF(ss.operative_bases, 0)) AS sat
        FROM station_snapshot ss
        LEFT JOIN holidays h ON h.holiday_date = ss.captured_at::date
        WHERE {where}
        GROUP BY ss.station_id, hora
        ORDER BY ss.station_id, hora
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
        SELECT station_id, EXTRACT(HOUR FROM captured_at)::int AS hora,
               AVG(dock_bikes::float / NULLIF(operative_bases, 0)) AS sat
        FROM station_snapshot
        WHERE captured_at::date = %(target)s AND activate = 1 AND operative_bases > 0
        GROUP BY station_id, hora ORDER BY station_id, hora
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
    sql = """
        SELECT DISTINCT EXTRACT(MONTH FROM captured_at)::int AS month
        FROM station_snapshot ORDER BY month
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
    months = [{"value": r[0], "label": MONTH_NAMES[r[0]]} for r in rows]
    return jsonify(months)


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