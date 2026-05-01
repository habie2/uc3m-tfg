@echo off
REM Script para convertir shapefiles a GeoJSON en Windows
REM Uso: setup_windows.bat

cls
echo.
echo ╔════════════════════════════════════════════════════════╗
echo ║  VISOR DE SHAPEFILES - WINDOWS SETUP                  ║
echo ╚════════════════════════════════════════════════════════╝
echo.

REM Verificar si Python está instalado
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python no encontrado en el PATH
    echo.
    echo Descarga Python desde: https://www.python.org/downloads/
    echo Asegúrate de marcar "Add Python to PATH" durante la instalación
    echo.
    pause
    exit /b 1
)

echo ✅ Python encontrado
python --version

REM Instalar dependencias
echo.
echo ╔════════════════════════════════════════════════════════╗
echo ║  Instalando dependencias...                            ║
echo ╚════════════════════════════════════════════════════════╝
echo.

python -m pip install --upgrade pip
python -m pip install geopandas pyproj

if errorlevel 1 (
    echo.
    echo ⚠️  Hubo problemas instalando algunas dependencias
    echo.
    echo Intenta estas soluciones:
    echo 1. conda install geopandas (si tienes Anaconda)
    echo 2. pip install --only-binary :all: geopandas
    echo 3. Descargar wheels de: https://www.lfd.uci.edu/~gohlke/pythonlibs/
    echo.
    pause
    exit /b 1
)

echo.
echo ✅ Dependencias instaladas correctamente
echo.
echo ╔════════════════════════════════════════════════════════╗
echo ║  SIGUIENTES PASOS                                     ║
echo ╚════════════════════════════════════════════════════════╝
echo.
echo 1. Coloca tus shapefiles en una carpeta
echo.
echo 2. Ejecuta en línea de comandos:
echo    python shapefile_converter.py C:\ruta\a\tus\shapefiles
echo.
echo 3. Se crearán archivos .geojson en la carpeta geojson_output
echo.
echo 4. Abre "shapefile_viewer.html" con tu navegador
echo.
echo 5. Carga los archivos GeoJSON en la aplicación
echo.
pause
