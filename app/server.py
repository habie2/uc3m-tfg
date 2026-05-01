"""
BiciMAD · Saturación de Estaciones — Servidor Flask
====================================================
Adaptado al esquema real:
  - station(id, number, name, address, latitude, longitude, total_bases)
  - station_status(captured_at, station_id, dock_bikes, free_bases, ...)
  - holidays(holiday_date)

Requisitos:
    pip install flask psycopg2-binary

Uso:
    python server.py
    → http://localhost:5000
"""

from flask import Flask, jsonify, request, send_from_directory
from datetime import datetime
import psycopg2
import psycopg2.extras
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(
    __name__,
    static_folder="static",
    template_folder="templates",
)

# ─────────────────────────────────────────────────────────
# CONFIGURACIÓN DE BASE DE DATOS
# ─────────────────────────────────────────────────────────
DB_CONFIG = {
    "host":     os.environ.get("DB_HOST", "localhost"),
    "port":     int(os.environ.get("DB_PORT", 5432)),
    "dbname":   os.environ.get("DB_NAME", "bicimad"),
    "user":     os.environ.get("DB_USER", "user"),
    "password": os.environ.get("DB_PASS", "pass"),
}


def get_conn():
    return psycopg2.connect(**DB_CONFIG)


# ─────────────────────────────────────────────────────────
# ENDPOINT 1: Lista de estaciones
# GET /api/stations
# ─────────────────────────────────────────────────────────
@app.route("/api/stations")
def api_stations():
    sql = """
        SELECT
            id,
            name,
            latitude   AS lat,
            longitude  AS lng,
            total_bases AS cap
        FROM station
        WHERE latitude IS NOT NULL
          AND longitude IS NOT NULL
        ORDER BY id
    """
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql)
            rows = cur.fetchall()

    # Convertir Decimal a float para JSON
    for r in rows:
        r['lat'] = float(r['lat'])
        r['lng'] = float(r['lng'])
        r['cap'] = int(r['cap'])

    return jsonify(rows)


# ─────────────────────────────────────────────────────────
# ENDPOINT 2: Saturación por tipo de día
# GET /api/saturation?dayType=L&holiday=false
#
# Calcula: AVG(dock_bikes / total_bases) agrupado por
#          station_id y hora, filtrando por día de la semana.
# ─────────────────────────────────────────────────────────
@app.route("/api/saturation")
def api_saturation():
    day_type = request.args.get("dayType", "L")
    is_holiday = request.args.get("holiday", "false").lower() == "true"

    # L=1, M=2, X=3, J=4, V=5, S=6, D=7 (ISO)
    day_map = {"L": 1, "M": 2, "X": 3, "J": 4, "V": 5, "S": 6, "D": 7}
    iso_dow = day_map.get(day_type, 1)

    sql = """
        SELECT
            ss.station_id,
            EXTRACT(HOUR FROM ss.captured_at)::int AS hora,
            AVG(ss.dock_bikes::float / NULLIF(st.total_bases, 0)) AS sat
        FROM station_status ss
        JOIN station st ON st.id = ss.station_id
        LEFT JOIN holidays h
            ON h.holiday_date = ss.captured_at::date
        WHERE
            EXTRACT(ISODOW FROM ss.captured_at) = %(dow)s
            AND ss.activate = 1
            AND st.total_bases > 0
            AND (
                CASE
                    WHEN %(holiday)s THEN h.holiday_date IS NOT NULL
                    ELSE h.holiday_date IS NULL
                END
            )
        GROUP BY ss.station_id, hora
        ORDER BY ss.station_id, hora
    """
    params = {"dow": iso_dow, "holiday": is_holiday}

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

    result = _build_sat_dict(rows)
    return jsonify(result)


# ─────────────────────────────────────────────────────────
# ENDPOINT 3: Saturación por fecha concreta
# GET /api/saturation-date?date=2019-05-15
# ─────────────────────────────────────────────────────────
@app.route("/api/saturation-date")
def api_saturation_date():
    date_str = request.args.get("date", "")
    try:
        target = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"error": "Formato de fecha inválido. Usa YYYY-MM-DD"}), 400

    sql = """
        SELECT
            ss.station_id,
            EXTRACT(HOUR FROM ss.captured_at)::int AS hora,
            AVG(ss.dock_bikes::float / NULLIF(st.total_bases, 0)) AS sat
        FROM station_status ss
        JOIN station st ON st.id = ss.station_id
        WHERE ss.captured_at::date = %(target)s
          AND ss.activate = 1
          AND st.total_bases > 0
        GROUP BY ss.station_id, hora
        ORDER BY ss.station_id, hora
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {"target": target})
            rows = cur.fetchall()

    result = _build_sat_dict(rows)
    return jsonify(result)


# ─────────────────────────────────────────────────────────
# ENDPOINT 4: ¿Es festivo una fecha?
# GET /api/is-holiday?date=2019-05-01
# ─────────────────────────────────────────────────────────
@app.route("/api/is-holiday")
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


# ─────────────────────────────────────────────────────────
# ENDPOINT 5: Rango de fechas disponibles
# GET /api/date-range
# Para que el frontend sepa qué fechas puede seleccionar
# ─────────────────────────────────────────────────────────
@app.route("/api/date-range")
def api_date_range():
    sql = """
        SELECT
            MIN(captured_at::date)::text AS min_date,
            MAX(captured_at::date)::text AS max_date
        FROM station_status
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            row = cur.fetchone()

    return jsonify({"min": row[0], "max": row[1]})


# ─────────────────────────────────────────────────────────
# Helper: montar diccionario { stationId: [s0..s23] }
# ─────────────────────────────────────────────────────────
def _build_sat_dict(rows):
    result = {}
    for station_id, hora, sat in rows:
        key = str(station_id)
        if key not in result:
            result[key] = [None] * 24
        result[key][int(hora)] = round(float(sat), 4) if sat else None

    # Rellenar huecos con interpolación simple o 0.5
    for key in result:
        arr = result[key]
        for i in range(24):
            if arr[i] is None:
                # Buscar vecinos
                prev_val = next((arr[j] for j in range(i - 1, -1, -1) if arr[j] is not None), None)
                next_val = next((arr[j] for j in range(i + 1, 24) if arr[j] is not None), None)
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


# ─────────────────────────────────────────────────────────
# Servir el frontend
# ─────────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory("templates", "index.html")


if __name__ == "__main__":
    print("=" * 55)
    print("  BiciMAD · Saturación de Estaciones")
    print("  http://localhost:5000")
    print("=" * 55)
    app.run(debug=True, port=5000)
