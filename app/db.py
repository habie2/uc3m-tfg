"""
BiciMAD · Helpers comunes de base de datos
==========================================
Módulo compartido por los tres blueprints de indicadores.
"""

import os
import psycopg2
import psycopg2.extras
from psycopg2 import pool as pg_pool

DB_CONFIG = {
    "host":     os.environ.get("DB_HOST", "localhost"),
    "port":     int(os.environ.get("DB_PORT", 5432)),
    "dbname":   os.environ.get("DB_NAME", "bicimad"),
    "user":     os.environ.get("DB_USER", "user"),
    "password": os.environ.get("DB_PASS", "pass"),
}

DB_DSN = (
    f"host={DB_CONFIG['host']} "
    f"port={DB_CONFIG['port']} "
    f"dbname={DB_CONFIG['dbname']} "
    f"user={DB_CONFIG['user']} "
    f"password={DB_CONFIG['password']}"
)

# ── Conexión simple (indicador 1) ─────────────────────────
def get_conn():
    return psycopg2.connect(**DB_CONFIG)


# ── Pool de conexiones (indicadores 2 y 3) ────────────────
_pool = None

def get_pool():
    global _pool
    if _pool is None:
        _pool = pg_pool.ThreadedConnectionPool(
            minconn=1, maxconn=10, dsn=DB_DSN
        )
    return _pool


def query(sql, params=(), *, one=False):
    """Ejecuta una consulta y devuelve dicts."""
    p = get_pool()
    conn = p.getconn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            if one:
                row = cur.fetchone()
                return dict(row) if row else None
            return [dict(r) for r in cur.fetchall()]
    finally:
        p.putconn(conn)
