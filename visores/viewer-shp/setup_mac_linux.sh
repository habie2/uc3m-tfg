#!/bin/bash
# Script de setup para macOS/Linux

clear

echo ""
echo "╔════════════════════════════════════════════════════════╗"
echo "║   VISOR DE SHAPEFILES - SETUP MACOS/LINUX             ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""

# Verificar si Python está instalado
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 no encontrado"
    echo ""
    echo "Instala Python 3 con:"
    echo "  macOS: brew install python3"
    echo "  Linux: sudo apt-get install python3 python3-pip"
    exit 1
fi

echo "✅ Python encontrado:"
python3 --version

echo ""
echo "╔════════════════════════════════════════════════════════╗"
echo "║  Instalando dependencias...                            ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""

# Actualizar pip
python3 -m pip install --upgrade pip

# Instalar geopandas y pyproj
echo ""
echo "📦 Instalando geopandas..."
python3 -m pip install geopandas

echo ""
echo "📦 Instalando pyproj..."
python3 -m pip install pyproj

# Verificar instalación
echo ""
echo "╔════════════════════════════════════════════════════════╗"
echo "║  Verificando instalación...                            ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""

python3 -c "import geopandas; print('✅ geopandas OK')" 2>/dev/null || echo "❌ geopandas no instalado"
python3 -c "import pyproj; print('✅ pyproj OK')" 2>/dev/null || echo "❌ pyproj no instalado"

echo ""
echo "╔════════════════════════════════════════════════════════╗"
echo "║  SIGUIENTES PASOS                                     ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""
echo "1. Coloca tus shapefiles en una carpeta:"
echo "   mkdir mis_shapefiles"
echo "   cp *.shp *.dbf *.shx mis_shapefiles/"
echo ""
echo "2. Convierte a GeoJSON:"
echo "   python3 shapefile_converter.py mis_shapefiles"
echo ""
echo "3. Abre el visor en tu navegador:"
echo "   python3 -m http.server 8000"
echo "   Luego ve a: http://localhost:8000/shapefile_viewer.html"
echo ""
echo "4. Carga los archivos desde mis_shapefiles/geojson_output/"
echo ""
echo "✅ ¡Listo!"
