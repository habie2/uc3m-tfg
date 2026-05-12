"""Configuración compartida del ETL y la API del indicador 2.

Lee las variables desde un fichero .env en el directorio de trabajo.
Formato esperado:

    DB_HOST=192.168.1.x
    DB_PORT=5432
    DB_NAME=bicimad
    DB_USER=postgres
    DB_PASS=secreto
    ORS_URL=http://localhost:8080/ors   # opcional
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# Carga el .env desde el directorio donde se ejecuta el script.
# Si no existe, las variables de entorno del sistema tienen prioridad igualmente.
load_dotenv(Path(__file__).parent.parent / ".env", override=False)
load_dotenv(Path(__file__).parent / ".env", override=False)

DB_DSN = (
    f"host={os.environ['DB_HOST']} "
    f"port={os.environ.get('DB_PORT', '5432')} "
    f"dbname={os.environ['DB_NAME']} "
    f"user={os.environ['DB_USER']} "
    f"password={os.environ['DB_PASS']}"
)

ORS_URL = os.environ.get("ORS_URL", "http://localhost:8080/ors")