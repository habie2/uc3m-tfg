import geopandas as gpd

# Definimos la ruta apuntando específicamente al archivo .shp. 
# GeoPandas se encargará de leer el resto de archivos (.dbf, .prj, etc.) automáticamente en segundo plano.
ruta_archivo = 'C:\\Users\\ajolote-casa-w\\Downloads\\bikestationbicimad_shp'

# Leer el shapefile (crea un GeoDataFrame)
bicimad_gdf = gpd.read_file(ruta_archivo)

# Mostrar las primeras 5 filas para verificar que se ha cargado bien
print("Datos cargados correctamente:")
print(bicimad_gdf.head())

# Mostrar el Sistema de Referencia de Coordenadas (CRS)
print("\nSistema de coordenadas (CRS):")
print(bicimad_gdf.crs)

# Si quieres ver un gráfico rápido de las estaciones:
bicimad_gdf.plot()