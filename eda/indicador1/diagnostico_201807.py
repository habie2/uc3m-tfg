"""
diagnostico_201807.py

Script de diagnóstico para entender por qué falla el archivo 201807.json.
Inspecciona los primeros bytes en distintas codificaciones y trata de
identificar el problema.
"""
from pathlib import Path

DATA_DIR = Path.home() / "Downloads" / "bicimad_data"
ARCHIVO = DATA_DIR / "bicimad_2018" / "stations" / "201807.json"

print(f"Diagnóstico de: {ARCHIVO}")
print(f"Existe: {ARCHIVO.exists()}")
if not ARCHIVO.exists():
    print("ERROR: archivo no encontrado")
    exit(1)

print(f"Tamaño: {ARCHIVO.stat().st_size:,} bytes")
print()

# Leer los primeros bytes en binario
print("=" * 70)
print("PRIMEROS 600 BYTES (en hexadecimal):")
print("=" * 70)
with open(ARCHIVO, "rb") as f:
    primeros_bytes = f.read(600)
print(primeros_bytes.hex(" ", 1)[:1500])
print()

print("=" * 70)
print("PRIMEROS 600 BYTES (representación):")
print("=" * 70)
print(repr(primeros_bytes))
print()

# Probar varios encodings
print("=" * 70)
print("INTENTANDO LEER CON DISTINTAS CODIFICACIONES:")
print("=" * 70)
for enc in ["utf-8", "utf-8-sig", "latin-1", "cp1252", "iso-8859-15"]:
    try:
        with open(ARCHIVO, "r", encoding=enc) as f:
            content = f.read(500)
        print(f"\n[{enc}] LEÍDO OK. Primeros 500 caracteres:")
        print(content[:500])
        print(f"\n[{enc}] OK")
        break
    except UnicodeDecodeError as e:
        print(f"\n[{enc}] ERROR: {e}")

# Detectar BOM o cosas raras al inicio
print("\n" + "=" * 70)
print("BYTES INICIALES (¿BOM?):")
print("=" * 70)
print(f"Primeros 4 bytes: {primeros_bytes[:4].hex()}")
if primeros_bytes[:3] == b"\xef\xbb\xbf":
    print("  -> BOM UTF-8 detectado")
elif primeros_bytes[:2] == b"\xff\xfe":
    print("  -> BOM UTF-16 LE detectado")
elif primeros_bytes[:2] == b"\xfe\xff":
    print("  -> BOM UTF-16 BE detectado")
else:
    print("  -> Sin BOM evidente")

# Buscar posición exacta del byte 0xba problemático
print("\n" + "=" * 70)
print("BUSCANDO BYTE 0xBA EN LOS PRIMEROS 1000 BYTES:")
print("=" * 70)
with open(ARCHIVO, "rb") as f:
    bloque = f.read(1000)
posiciones = [i for i, b in enumerate(bloque) if b == 0xba]
print(f"Posiciones encontradas: {posiciones}")
if posiciones:
    pos = posiciones[0]
    inicio = max(0, pos - 30)
    fin = min(len(bloque), pos + 30)
    print(f"\nContexto alrededor de la posición {pos}:")
    print(f"Bytes: {bloque[inicio:fin].hex(' ', 1)}")
    print(f"Latin-1: {bloque[inicio:fin].decode('latin-1', errors='replace')}")

# Probar si el contenido es JSON array o NDJSON
print("\n" + "=" * 70)
print("FORMATO DEL ARCHIVO:")
print("=" * 70)
import json
try:
    with open(ARCHIVO, "r", encoding="latin-1") as f:
        contenido = f.read()
    contenido_strip = contenido.lstrip()
    if contenido_strip.startswith("["):
        print("Parece un JSON array")
        try:
            data = json.loads(contenido)
            print(f"  Parseado OK. {len(data)} snapshots.")
            if data:
                print(f"  Claves del primer snapshot: {list(data[0].keys())}")
        except json.JSONDecodeError as e:
            print(f"  Error parseando JSON array: {e}")
    elif contenido_strip.startswith("{"):
        print("Parece NDJSON o un solo JSON")
        primera_linea = contenido.split("\n", 1)[0]
        try:
            obj = json.loads(primera_linea)
            print(f"  Primera línea parseada OK. Claves: {list(obj.keys())}")
            num_lineas = len([l for l in contenido.split("\n") if l.strip()])
            print(f"  Total de líneas no vacías: {num_lineas}")
        except json.JSONDecodeError as e:
            print(f"  Error parseando primera línea: {e}")
            print(f"  Primera línea: {primera_linea[:200]}")
    else:
        print(f"Formato inesperado. Empieza con: {contenido_strip[:100]!r}")
except Exception as e:
    print(f"Error leyendo: {e}")
