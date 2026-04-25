"""
Mapa de calor de calles de Madrid — BiciMAD
============================================
Requisitos:
    pip install geopandas pandas numpy matplotlib folium contextily shapely tqdm

Uso:
    python mapa_calor_bici.py \
        --jsonl  viajes.jsonl \
        --shp    calles/calles_madrid.shp \
        --out    resultados/

El shapefile puede estar en cualquier CRS; el script lo reproyecta automáticamente.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import folium
from shapely.geometry import Point
from tqdm import tqdm


# ─────────────────────────────────────────────
# 1. LECTURA DEL JSONL  (streaming, línea a línea)
# ─────────────────────────────────────────────

def leer_puntos_jsonl(ruta: Path, max_lineas: int = None) -> gpd.GeoDataFrame:
    """
    Lee el JSONL de viajes y devuelve un GeoDataFrame con todos los puntos GPS.
    Cada fila = un punto de track.features.
    """
    registros = []
    errores = 0

    print(f"\n[1/4] Leyendo puntos de {ruta.name} ...")

    # latin-1 mapea todos los bytes 0-255 sin error, ideal para datos españoles mezclados
    with open(ruta, "r", encoding="latin-1") as f:
        for i, linea in enumerate(tqdm(f, unit=" viajes")):
            if max_lineas and i >= max_lineas:
                break
            linea = linea.strip()
            if not linea:
                continue
            try:
                viaje = json.loads(linea)
            except json.JSONDecodeError:
                errores += 1
                continue

            track = viaje.get("track", {})
            features = track.get("features", [])
            viaje_id = str(viaje.get("_id", {}).get("$oid", i))

            for feat in features:
                try:
                    coords = feat["geometry"]["coordinates"]
                    lon, lat = float(coords[0]), float(coords[1])
                    registros.append({"viaje_id": viaje_id, "lon": lon, "lat": lat})
                except (KeyError, TypeError, ValueError):
                    errores += 1

    if errores:
        print(f"  ⚠  {errores} registros con errores omitidos.")

    print(f"  ✓  {len(registros):,} puntos extraídos de {i+1:,} viajes.")

    df = pd.DataFrame(registros)
    geometry = gpd.points_from_xy(df["lon"], df["lat"])
    gdf = gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")
    return gdf


# ─────────────────────────────────────────────
# 2. CARGA DEL SHAPEFILE DE CALLES
# ─────────────────────────────────────────────

def cargar_calles(ruta_shp: Path) -> gpd.GeoDataFrame:
    print(f"\n[2/4] Cargando shapefile de calles: {ruta_shp.name} ...")
    calles = gpd.read_file(ruta_shp)
    print(f"  ✓  {len(calles):,} segmentos de calle cargados.")
    print(f"  CRS original: {calles.crs}")
    return calles


# ─────────────────────────────────────────────
# 3. SPATIAL JOIN — asignar cada punto a su calle más cercana
# ─────────────────────────────────────────────

def asignar_puntos_a_calles(
    puntos: gpd.GeoDataFrame,
    calles: gpd.GeoDataFrame,
    radio_max_m: float = 30.0
) -> gpd.GeoDataFrame:
    """
    Reproyecta ambas capas a UTM 30N (métrico) y hace sjoin_nearest.
    Descarta puntos que estén a más de `radio_max_m` metros de cualquier calle.
    """
    CRS_METRICO = "EPSG:25830"  # UTM zona 30N — Madrid

    print(f"\n[3/4] Proyectando a {CRS_METRICO} y asignando puntos a calles ...")
    print(f"  Radio máximo de snap: {radio_max_m} m")

    puntos_m  = puntos.to_crs(CRS_METRICO)
    calles_m  = calles.to_crs(CRS_METRICO)

    # sjoin_nearest añade la columna 'index_right' y 'geometry_right' (no la queremos)
    joined = gpd.sjoin_nearest(
        puntos_m,
        calles_m[["geometry"] + [c for c in calles_m.columns if c != "geometry"]],
        how="left",
        max_distance=radio_max_m,
        distance_col="dist_m"
    )

    antes  = len(joined)
    joined = joined.dropna(subset=["index_right"])
    descartados = antes - len(joined)
    if descartados:
        print(f"  ⚠  {descartados:,} puntos descartados (>{radio_max_m} m de cualquier calle).")

    print(f"  ✓  {len(joined):,} puntos asignados a calles.")
    return joined, calles_m


# ─────────────────────────────────────────────
# 4. AGREGACIÓN por segmento de calle
# ─────────────────────────────────────────────

def agregar_por_calle(joined: gpd.GeoDataFrame, calles_m: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    conteo = (
        joined.groupby("index_right")
        .size()
        .rename("n_puntos")
        .reset_index()
        .rename(columns={"index_right": "idx_calle"})
    )
    conteo["idx_calle"] = conteo["idx_calle"].astype(int)

    calles_m = calles_m.copy().reset_index(drop=False).rename(columns={"index": "idx_calle"})
    calles_heat = calles_m.merge(conteo, on="idx_calle", how="left")
    calles_heat["n_puntos"] = calles_heat["n_puntos"].fillna(0).astype(int)

    total = calles_heat["n_puntos"].sum()
    usadas = (calles_heat["n_puntos"] > 0).sum()
    print(f"\n  ✓  {usadas:,} calles con al menos 1 punto  |  {total:,} puntos totales asignados.")
    return calles_heat


# ─────────────────────────────────────────────
# 5a. MAPA ESTÁTICO (matplotlib)
# ─────────────────────────────────────────────

def guardar_png(calles_heat: gpd.GeoDataFrame, ruta_salida: Path):
    print("\n[4a/4] Generando mapa estático PNG ...")

    try:
        import contextily as ctx
        usar_fondo = True
    except ImportError:
        usar_fondo = False
        print("  ⚠  contextily no instalado — se generará sin mapa de fondo.")
        print("      Instala con:  pip install contextily")

    # Reproyectar a Web Mercator para contextily
    calles_wm = calles_heat.to_crs("EPSG:3857") if usar_fondo else calles_heat

    n = calles_wm["n_puntos"]
    vmax = np.percentile(n[n > 0], 95) if (n > 0).any() else 1  # escala al percentil 95

    fig, ax = plt.subplots(1, 1, figsize=(16, 16))

    # Calles sin puntos en gris claro
    calles_wm[calles_wm["n_puntos"] == 0].plot(
        ax=ax, color="#e0e0e0", linewidth=0.3, alpha=0.5
    )

    # Calles con puntos coloreadas por densidad
    calles_con = calles_wm[calles_wm["n_puntos"] > 0]
    calles_con.plot(
        ax=ax,
        column="n_puntos",
        cmap="YlOrRd",
        linewidth=calles_con["n_puntos"].apply(lambda x: min(0.4 + x / vmax * 3, 4)),
        legend=True,
        legend_kwds={
            "label": "Número de puntos GPS",
            "orientation": "horizontal",
            "shrink": 0.5,
            "pad": 0.02
        },
        vmin=1,
        vmax=vmax,
    )

    if usar_fondo:
        try:
            ctx.add_basemap(ax, source=ctx.providers.CartoDB.Positron, zoom=13)
        except Exception as e:
            print(f"  ⚠  No se pudo añadir fondo: {e}")

    ax.set_axis_off()
    ax.set_title("Mapa de calor — Uso de calles BiciMAD", fontsize=18, pad=14)

    ruta_png = ruta_salida / "mapa_calor_bici.png"
    fig.savefig(ruta_png, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"  ✓  PNG guardado en: {ruta_png}")


# ─────────────────────────────────────────────
# 5b. MAPA INTERACTIVO (Folium)
# ─────────────────────────────────────────────

def guardar_html(calles_heat: gpd.GeoDataFrame, ruta_salida: Path):
    print("\n[4b/4] Generando mapa interactivo HTML ...")

    # Reproyectar a WGS84 para Folium
    calles_4326 = calles_heat.to_crs("EPSG:4326")

    n = calles_4326["n_puntos"]
    vmax = float(np.percentile(n[n > 0], 95)) if (n > 0).any() else 1.0

    # Centrar el mapa en Madrid
    m = folium.Map(
        location=[40.4168, -3.7038],
        zoom_start=13,
        tiles="CartoDB positron"
    )

    # Paleta de colores
    colormap = folium.LinearColormap(
        colors=["#ffffb2", "#fecc5c", "#fd8d3c", "#f03b20", "#bd0026"],
        vmin=1,
        vmax=vmax,
        caption="Número de puntos GPS por segmento de calle"
    )
    colormap.add_to(m)

    def estilo(feature):
        v = feature["properties"].get("n_puntos", 0)
        if v == 0:
            return {"color": "#cccccc", "weight": 0.5, "opacity": 0.3}
        color = colormap(min(v, vmax))
        peso  = min(1.0 + v / vmax * 5, 6)
        return {"color": color, "weight": peso, "opacity": 0.85}

    # Detectar columna con nombre de calle (flexible)
    nombre_col = None
    for candidato in ["NOMBRE", "nombre", "ROTULO", "rotulo", "STREET", "street", "NAME", "name"]:
        if candidato in calles_4326.columns:
            nombre_col = candidato
            break

    def tooltip_fn(feature):
        props = feature["properties"]
        nombre = props.get(nombre_col, "Sin nombre") if nombre_col else "Sin nombre"
        puntos = props.get("n_puntos", 0)
        return f"<b>{nombre}</b><br>Puntos GPS: {puntos:,}"

    folium.GeoJson(
        calles_4326.__geo_interface__,
        style_function=estilo,
        tooltip=folium.GeoJsonTooltip(
            fields=[nombre_col, "n_puntos"] if nombre_col else ["n_puntos"],
            aliases=["Calle:", "Puntos GPS:"] if nombre_col else ["Puntos GPS:"],
            localize=True
        )
    ).add_to(m)

    # Capa extra: sólo calles con puntos encima para que sean más visibles
    folium.GeoJson(
        calles_4326[calles_4326["n_puntos"] > 0].__geo_interface__,
        name="Solo calles usadas",
        style_function=estilo,
        show=False
    ).add_to(m)

    folium.LayerControl().add_to(m)

    ruta_html = ruta_salida / "mapa_calor_bici.html"
    m.save(str(ruta_html))
    print(f"  ✓  HTML guardado en: {ruta_html}")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Mapa de calor de calles de Madrid con datos BiciMAD"
    )
    parser.add_argument("--jsonl",  required=True,  help="Ruta al archivo .jsonl de viajes")
    parser.add_argument("--shp",    required=True,  help="Ruta al .shp del shapefile de calles")
    parser.add_argument("--out",    default=".",     help="Carpeta de salida (se crea si no existe)")
    parser.add_argument("--radio",  type=float, default=30.0,
                        help="Radio máximo en metros para snap punto→calle (defecto: 30)")
    parser.add_argument("--max",    type=int,   default=None,
                        help="Máximo de viajes a leer (útil para pruebas rápidas)")
    args = parser.parse_args()

    ruta_jsonl = Path(args.jsonl)
    ruta_shp   = Path(args.shp)
    ruta_out   = Path(args.out)
    ruta_out.mkdir(parents=True, exist_ok=True)

    # Validaciones
    if not ruta_jsonl.exists():
        print(f"ERROR: No se encuentra el archivo JSONL: {ruta_jsonl}")
        sys.exit(1)
    if not ruta_shp.exists():
        print(f"ERROR: No se encuentra el shapefile: {ruta_shp}")
        sys.exit(1)

    # Pipeline
    puntos      = leer_puntos_jsonl(ruta_jsonl, max_lineas=args.max)
    calles      = cargar_calles(ruta_shp)
    joined, calles_m = asignar_puntos_a_calles(puntos, calles, radio_max_m=args.radio)
    calles_heat = agregar_por_calle(joined, calles_m)

    # Exportar CSV de ranking de calles (opcional, muy útil)
    cols_nombre = [c for c in calles_heat.columns
                   if c.lower() in ("nombre", "rotulo", "street", "name", "codieje", "objectid")]
    cols_csv = cols_nombre + ["n_puntos"]
    ranking = (
        calles_heat[cols_csv]
        .sort_values("n_puntos", ascending=False)
        .reset_index(drop=True)
    )
    ruta_csv = ruta_out / "ranking_calles.csv"
    ranking.to_csv(ruta_csv, index=False, encoding="utf-8-sig")
    print(f"\n  ✓  Ranking de calles exportado en: {ruta_csv}")

    guardar_png(calles_heat, ruta_out)
    guardar_html(calles_heat, ruta_out)

    print("\n✅ ¡Listo! Archivos generados en:", ruta_out.resolve())
    print("   - mapa_calor_bici.png   (mapa estático)")
    print("   - mapa_calor_bici.html  (mapa interactivo)")
    print("   - ranking_calles.csv    (ranking de calles por uso)")


if __name__ == "__main__":
    main()