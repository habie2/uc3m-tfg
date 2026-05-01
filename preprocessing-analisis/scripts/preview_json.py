import pandas as pd
import sys
import chardet

if len(sys.argv) < 2:
    print("Uso: python script.py archivo.json [num_filas]")
    sys.exit(1)

archivo = sys.argv[1]
num_filas = int(sys.argv[2]) if len(sys.argv) > 2 else 5

# Detectar el encoding del archivo
print("🔍 Detectando encoding del archivo...")
with open(archivo, 'rb') as f:
    resultado = chardet.detect(f.read(100000))  # Lee los primeros 100KB
    encoding = resultado['encoding']
    confianza = resultado['confidence']
    print(f"✅ Encoding detectado: {encoding} (confianza: {confianza:.0%})")

try:
    # Lee solo las primeras filas para mostrar
    df = pd.read_json(archivo, lines=True, nrows=num_filas, encoding=encoding)
    
    print(f"\n=== Mostrando las primeras {num_filas} filas ===")
    print(df.head(num_filas))
    print("\n=== Columnas y tipos ===")
    print(df.dtypes)
    print(f"\n=== Ejemplo del primer registro completo ===")
    print(df.iloc[0].to_dict())
    
    # Contar el total de filas
    print("\n⏳ Contando total de filas en el archivo...")
    total_filas = sum(1 for _ in open(archivo, 'r', encoding=encoding))
    print(f"✅ TOTAL DE FILAS: {total_filas:,}")
    
except ValueError as e:
    print(f"\nError con lines=True: {e}")
    print("Intentando como array JSON normal...")
    
    # Si falla, intenta como array normal
    df = pd.read_json(archivo, encoding=encoding)
    print(f"\n=== Mostrando las primeras {num_filas} filas ===")
    print(df.head(num_filas))
    print("\n=== Columnas y tipos ===")
    print(df.dtypes)
    print(f"\n✅ TOTAL DE FILAS: {len(df):,}")
    
except Exception as e:
    print(f"Error inesperado: {e}")