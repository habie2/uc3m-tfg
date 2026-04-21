#!/usr/bin/env python3
"""
Conversor de Shapefiles a GeoJSON
Agrupa shapefiles por nombre base y convierte a GeoJSON
"""

import os
import json
import geopandas as gpd
from pathlib import Path
from collections import defaultdict
from pyproj import CRS
import sys

def get_shapefile_groups(directory):
    """
    Agrupa archivos shapefile por nombre base.
    Retorna un diccionario: {nombre_base: [lista de rutas .shp]}
    """
    groups = defaultdict(list)
    
    for file in os.listdir(directory):
        if file.endswith('.shp'):
            # Extraer nombre base sin extensión
            base_name = file[:-4]  # Quitar .shp
            full_path = os.path.join(directory, file)
            groups[base_name].append(full_path)
    
    return dict(sorted(groups.items()))

def detect_crs(gdf):
    """Detecta el CRS del GeoDataFrame y retorna info útil"""
    if gdf.crs is None:
        return "No definido"
    
    crs_string = str(gdf.crs)
    
    # Intentar detectar si es ETRS89 UTM (común en España)
    if 'ETRS' in crs_string and 'UTM' in crs_string:
        return f"{crs_string} (España - UTM)"
    elif 'ETRS' in crs_string:
        return f"{crs_string} (España)"
    elif 'WGS 84' in crs_string or 'WGS84' in crs_string:
        return "WGS 84 (Lat/Lon)"
    
    return crs_string

def shapefile_to_geojson(shp_path, force_wgs84=True):
    """
    Convierte un shapefile a GeoJSON.
    Si force_wgs84=True, reproyecta a WGS84.
    """
    try:
        gdf = gpd.read_file(shp_path)
        
        print(f"  Leyendo: {Path(shp_path).name}")
        print(f"    - Geometría: {gdf.geometry.type.iloc[0] if len(gdf) > 0 else 'desconocida'}")
        print(f"    - CRS detectado: {detect_crs(gdf)}")
        print(f"    - Registros: {len(gdf)}")
        
        # Reproyectar a WGS84 si es necesario
        if force_wgs84 and gdf.crs and gdf.crs != 'EPSG:4326':
            print(f"    - Reproyectando a WGS84...")
            gdf = gdf.to_crs('EPSG:4326')
        
        return gdf
    
    except Exception as e:
        print(f"  ❌ Error al leer {Path(shp_path).name}: {str(e)}")
        return None

def process_shapefile_group(base_name, shp_paths, output_dir):
    """
    Procesa un grupo de shapefiles y crea un archivo GeoJSON
    que contiene todos los archivos del grupo.
    """
    print(f"\n{'='*60}")
    print(f"Procesando: {base_name}")
    print(f"{'='*60}")
    
    all_features = []
    geometry_types = set()
    all_crs = []
    
    for shp_path in shp_paths:
        gdf = shapefile_to_geojson(shp_path)
        if gdf is not None:
            all_features.extend(json.loads(gdf.to_json())['features'])
            geometry_types.update(gdf.geometry.type.unique())
            all_crs.append(str(gdf.crs))
    
    if not all_features:
        print(f"  ⚠️  No se encontraron geometrías válidas")
        return False
    
    # Crear FeatureCollection
    feature_collection = {
        "type": "FeatureCollection",
        "features": all_features,
        "metadata": {
            "name": base_name,
            "geometry_types": list(geometry_types),
            "feature_count": len(all_features),
            "source_crs": list(set(all_crs)),
            "reprojected_to": "EPSG:4326 (WGS84)"
        }
    }
    
    # Guardar GeoJSON
    output_path = os.path.join(output_dir, f"{base_name}.geojson")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(feature_collection, f, ensure_ascii=False, indent=2)
    
    print(f"  ✅ Guardado: {base_name}.geojson ({len(all_features)} features)")
    print(f"     Tipos de geometría: {', '.join(geometry_types)}")
    
    return True

def main():
    if len(sys.argv) < 2:
        print("Uso: python shapefile_converter.py <ruta_carpeta_shapefiles>")
        print("Ejemplo: python shapefile_converter.py ./datos_shapefiles")
        sys.exit(1)
    
    input_dir = sys.argv[1]
    output_dir = os.path.join(input_dir, 'geojson_output')
    
    if not os.path.isdir(input_dir):
        print(f"❌ Error: La carpeta '{input_dir}' no existe")
        sys.exit(1)
    
    # Crear carpeta de salida
    os.makedirs(output_dir, exist_ok=True)
    
    # Obtener grupos de shapefiles
    groups = get_shapefile_groups(input_dir)
    
    if not groups:
        print(f"❌ No se encontraron archivos .shp en '{input_dir}'")
        sys.exit(1)
    
    print(f"\n📍 Encontrados {len(groups)} grupos de shapefiles\n")
    
    # Procesar cada grupo
    success_count = 0
    for base_name in groups:
        if process_shapefile_group(base_name, groups[base_name], output_dir):
            success_count += 1
    
    print(f"\n{'='*60}")
    print(f"✅ Conversión completada: {success_count}/{len(groups)} grupos procesados")
    print(f"📁 Archivos GeoJSON guardados en: {output_dir}")
    print(f"{'='*60}\n")

if __name__ == '__main__':
    main()
