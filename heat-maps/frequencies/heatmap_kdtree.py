"""
Mapa de calor de calles de Madrid — BiciMAD
============================================
Requisitos:
    pip install geopandas pandas numpy matplotlib folium contextily shapely tqdm scipy

Uso:
    python mapa_calor_bici.py --jsonl viajes.jsonl --shp calles/calles_madrid.shp --out resultados/

Opciones:
    --radio   Radio máximo en metros para snap punto->calle (defecto: 30)
    --max     Máximo de viajes a leer, útil para pruebas rápidas (defecto: todos)
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import folium
from scipy.spatial import KDTree
from tqdm import tqdm


# ─────────────────────────────────────────────
# 1. LECTURA DEL JSONL  (streaming, línea a línea)
# ─────────────────────────────────────────────

def leer_puntos_jsonl(ruta: Path, max_lineas: int = None) -> gpd.GeoDataFrame:
    """Lee el JSONL de viajes y devuelve un GeoDataFrame con todos los puntos GPS."""
    registros = []
    errores   = 0

    print(f"\n[1/4] Leyendo puntos de {ruta.name} ...")
    # latin-1 acepta todos los bytes 0-255 sin error, ideal para datos espanoles
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

            features = viaje.get("track", {}).get("features", [])
            for feat in features:
                try:
                    coords = feat["geometry"]["coordinates"]
                    registros.append((float(coords[0]), float(coords[1])))
                except (KeyError, TypeError, ValueError, IndexError):
                    errores += 1

    if errores:
        print(f"  ⚠  {errores} registros con errores omitidos.")

    total_viajes = i + 1
    print(f"  ✓  {len(registros):,} puntos extraídos de {total_viajes:,} viajes.")

    lons, lats = zip(*registros)
    gdf = gpd.GeoDataFrame(
        geometry=gpd.points_from_xy(lons, lats),
        crs="EPSG:4326"
    )
    return gdf


# ─────────────────────────────────────────────
# 2. CARGA DEL SHAPEFILE DE CALLES
# ─────────────────────────────────────────────

def cargar_calles(ruta_shp: Path) -> gpd.GeoDataFrame:
    print(f"\n[2/4] Cargando shapefile de calles: {ruta_shp.name} ...")
    calles = gpd.read_file(ruta_shp)
    print(f"  ✓  {len(calles):,} segmentos cargados  |  CRS: {calles.crs}")
    return calles


# ─────────────────────────────────────────────
# 3. ASIGNACIÓN RÁPIDA con scipy KDTree
# ─────────────────────────────────────────────

def _muestrear_calles(calles_m: gpd.GeoDataFrame, paso_m: float = 15.0):
    """
    Extrae vertices directamente con numpy.array(line.coords) — sin bucle
    de interpolacion. Mucho mas rapido que interpolate().
    Devuelve (array Nx2 coords, array N indices de calle).
    """
    coords_list = []
    idx_list    = []

    for idx, geom in tqdm(calles_m["geometry"].items(),
                          total=len(calles_m),
                          desc="  Muestreando calles", unit=" seg"):
        if geom is None or geom.is_empty:
            continue
        if geom.geom_type == "LineString":
            lines = [geom]
        elif geom.geom_type == "MultiLineString":
            lines = list(geom.geoms)
        else:
            continue
        for line in lines:
            pts = np.array(line.coords, dtype=np.float32)
            coords_list.append(pts)
            idx_list.append(np.full(len(pts), idx, dtype=np.int32))

    return (
        np.vstack(coords_list),
        np.concatenate(idx_list)
    )


def asignar_puntos_a_calles(
    puntos:      gpd.GeoDataFrame,
    calles:      gpd.GeoDataFrame,
    radio_max_m: float = 30.0,
) -> tuple:
    """
    Reproyecta a EPSG:25830 (UTM 30N) y usa scipy KDTree sobre puntos
    muestreados de las calles. 10-20x mas rapido que sjoin_nearest.
    """
    CRS = "EPSG:25830"

    print(f"\n[3/4] Asignando {len(puntos):,} puntos a calles (KDTree) ...")

    puntos_m = puntos.to_crs(CRS)
    calles_m = calles.to_crs(CRS)

    # 3a. Muestrear geometria de calles
    print("  Muestreando calles ...", end=" ", flush=True)
    calle_pts, calle_idx = _muestrear_calles(calles_m, paso_m=10.0)
    print(f"{len(calle_pts):,} puntos de referencia.")

    # 3b. KDTree
    print("  Construyendo KDTree ...", end=" ", flush=True)
    tree = KDTree(calle_pts)
    print("listo.")

    # 3c. Coordenadas GPS como array
    xy = np.column_stack([
        puntos_m.geometry.x.values,
        puntos_m.geometry.y.values
    ]).astype(np.float32)

    # 3d. Query en lotes para no saturar RAM
    LOTE   = 500_000
    n      = len(xy)
    dists  = np.empty(n, dtype=np.float32)
    nn_idx = np.empty(n, dtype=np.int32)

    print(f"  Consultando KDTree en lotes de {LOTE:,} ...")
    for i in tqdm(range(0, n, LOTE), unit=" lote"):
        d, nn = tree.query(xy[i:i+LOTE], workers=-1)  # todos los nucleos
        dists [i:i+LOTE] = d
        nn_idx[i:i+LOTE] = nn

    # 3e. Filtrar radio y mapear a indice de calle
    ok          = dists <= radio_max_m
    descartados = int((~ok).sum())
    if descartados:
        print(f"  ⚠  {descartados:,} puntos descartados (>{radio_max_m} m de cualquier calle).")

    joined_idx = pd.Series(calle_idx[nn_idx[ok]], dtype=np.int32)
    print(f"  ✓  {len(joined_idx):,} puntos asignados.")
    return joined_idx, calles_m


# ─────────────────────────────────────────────
# 4. AGREGACIÓN por segmento de calle
# ─────────────────────────────────────────────

def agregar_por_calle(joined_idx: pd.Series, calles_m: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    conteo = (
        joined_idx
        .value_counts()
        .rename("n_puntos")
        .rename_axis("idx_calle")
        .reset_index()
    )
    calles_heat = (
        calles_m.copy()
        .reset_index(drop=False)
        .rename(columns={"index": "idx_calle"})
        .merge(conteo, on="idx_calle", how="left")
    )
    calles_heat["n_puntos"] = calles_heat["n_puntos"].fillna(0).astype(int)

    usadas = (calles_heat["n_puntos"] > 0).sum()
    total  = calles_heat["n_puntos"].sum()
    print(f"\n  ✓  {usadas:,} calles con puntos  |  {total:,} puntos totales asignados.")
    return calles_heat


# ─────────────────────────────────────────────
# 5a. MAPA ESTÁTICO PNG
# ─────────────────────────────────────────────

def guardar_png(calles_heat: gpd.GeoDataFrame, ruta_salida: Path):
    print("\n[4a/4] Generando mapa estatico PNG ...")

    try:
        import contextily as ctx
        usar_fondo = True
    except ImportError:
        usar_fondo = False
        print("  ⚠  contextily no instalado — sin fondo. Instala con: pip install contextily")

    calles_wm = calles_heat.to_crs("EPSG:3857") if usar_fondo else calles_heat.copy()

    n = calles_wm["n_puntos"].values.astype(float)

    # Escala logaritmica: evita que unas pocas calles muy usadas aplasten el resto
    log_n = np.where(n > 0, np.log1p(n), 0)
    calles_wm["log_n"] = log_n
    vmax_log = float(np.percentile(log_n[log_n > 0], 98)) if (log_n > 0).any() else 1.0

    fig, ax = plt.subplots(figsize=(20, 20), facecolor="black")
    ax.set_facecolor("black")

    # Fondo de calles en gris muy oscuro
    calles_wm[n == 0].plot(ax=ax, color="#1a1a1a", linewidth=0.4, alpha=0.8)

    # Calles con datos: grosor y color proporcional al uso (log)
    con = calles_wm[log_n > 0].copy()
    norm_val = (con["log_n"] / vmax_log).clip(0, 1)
    con["lw"] = (norm_val * 4.5 + 0.4).clip(0.4, 5.0)

    con.plot(
        ax=ax,
        column="log_n",
        cmap="inferno",          # mucho mas visible sobre fondo negro que YlOrRd
        linewidth=con["lw"],
        legend=True,
        legend_kwds={
            "label": "Intensidad de uso (escala log)",
            "orientation": "horizontal",
            "shrink": 0.45,
            "pad": 0.02,
            "labelcolor": "white",
        },
        vmin=0,
        vmax=vmax_log,
    )

    if usar_fondo:
        try:
            ctx.add_basemap(ax, source=ctx.providers.CartoDB.DarkMatter, zoom=13, alpha=0.35)
        except Exception as e:
            print(f"  ⚠  No se pudo añadir fondo: {e}")

    ax.set_axis_off()
    ax.set_title("Mapa de calor — Uso de calles BiciMAD\nSeptiembre 2018",
                 fontsize=20, pad=16, color="white")

    # Leyenda de valores reales (no log) en el titulo secundario
    if (n > 0).any():
        p50 = int(np.percentile(n[n > 0], 50))
        p95 = int(np.percentile(n[n > 0], 95))
        p99 = int(np.percentile(n[n > 0], 99))
        ax.set_xlabel(f"Percentiles de uso — p50: {p50}  p95: {p95}  p99: {p99} puntos GPS",
                      color="#aaaaaa", fontsize=11)

    ruta_png = ruta_salida / "mapa_calor_bici.png"
    fig.savefig(ruta_png, dpi=200, bbox_inches="tight", facecolor="black")
    plt.close(fig)
    print(f"  ✓  PNG guardado: {ruta_png}")


# ─────────────────────────────────────────────
# 5b. MAPA INTERACTIVO HTML (Folium)
# ─────────────────────────────────────────────

def guardar_html(calles_heat: gpd.GeoDataFrame, ruta_salida: Path):
    print("\n[4b/4] Generando mapa interactivo HTML ...")

    # Solo calles CON datos — reduce dramaticamente el tamano del HTML
    con_datos = calles_heat[calles_heat["n_puntos"] > 0].copy()
    print(f"  Exportando {len(con_datos):,} calles con datos (descartando las vacias) ...")

    # Simplificar geometrias para reducir peso (~50% menos vertices)
    con_datos = con_datos.copy()
    con_datos["geometry"] = con_datos.geometry.simplify(5, preserve_topology=True)
    con_datos = con_datos.to_crs("EPSG:4326")

    n    = con_datos["n_puntos"]
    vmax = float(np.percentile(n, 95)) if len(n) > 0 else 1.0
    # Log para colormap igual que en PNG
    log_n  = np.log1p(n)
    vmax_l = float(np.percentile(log_n, 98)) if len(log_n) > 0 else 1.0
    con_datos["log_n"] = log_n.values

    m = folium.Map(location=[40.4168, -3.7038], zoom_start=13,
                   tiles="CartoDB dark_matter")

    colormap = folium.LinearColormap(
        colors=["#400040", "#8b0057", "#e8472a", "#ffa500", "#ffff00"],
        vmin=0, vmax=vmax_l,
        caption="Intensidad de uso (escala logaritmica)"
    )
    colormap.add_to(m)

    def estilo(feature):
        v    = feature["properties"].get("log_n", 0)
        vraw = feature["properties"].get("n_puntos", 0)
        if v == 0:
            return {"color": "#333333", "weight": 0.5, "opacity": 0.3}
        ratio = min(v / vmax_l, 1.0)
        return {
            "color":   colormap(v),
            "weight":  0.8 + ratio * 4.5,
            "opacity": 0.7 + ratio * 0.25,
        }

    # Detectar columna con nombre de calle
    nombre_col = next(
        (c for c in con_datos.columns
         if c.lower() in ("nombre", "rotulo", "street", "name", "via_nombre")),
        None
    )
    tooltip_fields  = ([nombre_col, "n_puntos"] if nombre_col else ["n_puntos"])
    tooltip_aliases = (["Calle:", "Puntos GPS:"] if nombre_col else ["Puntos GPS:"])

    folium.GeoJson(
        con_datos.__geo_interface__,
        name="Calles por uso",
        style_function=estilo,
        tooltip=folium.GeoJsonTooltip(
            fields=tooltip_fields,
            aliases=tooltip_aliases,
            localize=True,
        ),
    ).add_to(m)

    folium.LayerControl().add_to(m)

    ruta_html = ruta_salida / "mapa_calor_bici.html"
    m.save(str(ruta_html))
    size_mb = ruta_html.stat().st_size / 1024 / 1024
    print(f"  ✓  HTML guardado: {ruta_html}  ({size_mb:.1f} MB)")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Mapa de calor BiciMAD")
    parser.add_argument("--jsonl", required=True,  help="Ruta al .jsonl de viajes")
    parser.add_argument("--shp",   required=True,  help="Ruta al .shp de calles")
    parser.add_argument("--out",   default=".",    help="Carpeta de salida")
    parser.add_argument("--radio", type=float, default=30.0,
                        help="Radio maximo en metros (defecto: 30)")
    parser.add_argument("--max",   type=int,   default=None,
                        help="Maximo de viajes a leer (para pruebas)")
    args = parser.parse_args()

    ruta_jsonl = Path(args.jsonl)
    ruta_shp   = Path(args.shp)
    ruta_out   = Path(args.out)
    ruta_out.mkdir(parents=True, exist_ok=True)

    for ruta, nombre in [(ruta_jsonl, "JSONL"), (ruta_shp, "shapefile")]:
        if not ruta.exists():
            print(f"ERROR: No se encuentra el {nombre}: {ruta}")
            sys.exit(1)

    puntos               = leer_puntos_jsonl(ruta_jsonl, max_lineas=args.max)
    calles               = cargar_calles(ruta_shp)
    joined_idx, calles_m = asignar_puntos_a_calles(puntos, calles, radio_max_m=args.radio)
    calles_heat          = agregar_por_calle(joined_idx, calles_m)

    # CSV de ranking
    cols_nombre = [c for c in calles_heat.columns
                   if c.lower() in ("nombre", "rotulo", "street", "name",
                                    "codieje", "objectid", "via_nombre")]
    ranking = (
        calles_heat[cols_nombre + ["n_puntos"]]
        .sort_values("n_puntos", ascending=False)
        .reset_index(drop=True)
    )
    ruta_csv = ruta_out / "ranking_calles.csv"
    ranking.to_csv(ruta_csv, index=False, encoding="utf-8-sig")
    print(f"\n  ✓  Ranking exportado: {ruta_csv}")

    guardar_png(calles_heat, ruta_out)
    guardar_html(calles_heat, ruta_out)

    print("\n✅ ¡Listo! Archivos en:", ruta_out.resolve())
    print("   mapa_calor_bici.png   — mapa estatico")
    print("   mapa_calor_bici.html  — mapa interactivo")
    print("   ranking_calles.csv    — ranking de calles por uso")


if __name__ == "__main__":
    main()