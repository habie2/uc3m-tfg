"""
BiciMAD · Plataforma de Indicadores — Servidor Flask unificado
===============================================================
Punto de entrada único. Registra un blueprint por cada indicador:

    api_saturacion.py   →  /api/ind1/…   (Indicador 1 – Saturación)
    api_transito.py     →  /api/ind2/…   (Indicador 2 – Tránsito por tipo de vía)
    api_captura.py      →  /api/ind3/…   (Indicador 3 – Captura intermodal)

Requisitos:
    pip install flask flask-cors psycopg2-binary python-dotenv

Uso:
    python server.py  →  http://localhost:5000
"""

from flask import Flask, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

app = Flask(
    __name__,
    static_folder="static",
    template_folder="templates",
)
CORS(app)

# ── Registrar blueprints ──────────────────────────────────
from apis.api_saturacion import bp as bp_saturacion
from apis.api_transito import bp as bp_transito
from apis.api_captura import bp as bp_captura

app.register_blueprint(bp_saturacion, url_prefix="/api/ind1")
app.register_blueprint(bp_transito,   url_prefix="/api/ind2")
app.register_blueprint(bp_captura,    url_prefix="/api/ind3")

# ── Servir el frontend ────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory("templates", "index.html")


# ── Errores ───────────────────────────────────────────────
@app.errorhandler(404)
def not_found(e):
    from flask import jsonify
    return jsonify(error="not_found", message=str(e)), 404


@app.errorhandler(500)
def server_error(e):
    from flask import jsonify
    return jsonify(error="internal", message=str(e)), 500


if __name__ == "__main__":
    print("=" * 55)
    print("  BiciMAD · Plataforma de Indicadores")
    print("  http://localhost:5000")
    print("=" * 55)
    app.run(debug=True, port=5000)
    