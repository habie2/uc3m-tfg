"""
01_analisis_estructural.py

Análisis estructural del dataset BiciMad. Recorre los archivos JSON y extrae
metadatos sobre cobertura temporal, frecuencia de snapshots y consistencia
del esquema. Genera CSVs y gráficos listos para la memoria.

Uso:
    python 01_analisis_estructural.py

Configurar la ruta DATA_DIR si los datos están en otro sitio.
"""
import json
import os
import re
from pathlib import Path
from datetime import datetime
from collections import defaultdict

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from tqdm import tqdm

# ---------- CONFIGURACIÓN ----------
DATA_DIR = Path.home() / "Downloads" / "bicimad_data"  # ajusta si es necesario
OUTPUT_DIR = Path("output/01estructural")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Estilo gráficos
sns.set_theme(style="whitegrid", context="paper")
plt.rcParams['figure.dpi'] = 300
plt.rcParams['savefig.dpi'] = 300
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.size'] = 10

# Encodings a probar en orden
ENCODINGS = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]

# Patrones de MongoDB Extended JSON que aparecen en los archivos antiguos
# Ejemplos: NumberInt(1) -> 1, NumberLong(123) -> 123, NumberDecimal("1.5") -> 1.5
MONGO_PATTERNS = [
    (re.compile(r'NumberInt\((-?\d+)\)'), r'\1'),
    (re.compile(r'NumberLong\((-?\d+)\)'), r'\1'),
    (re.compile(r'NumberDecimal\("([^"]+)"\)'), r'\1'),
    (re.compile(r'NumberDouble\((-?[\d.]+)\)'), r'\1'),
    (re.compile(r'ObjectId\("([^"]+)"\)'), r'"\1"'),
    (re.compile(r'ISODate\("([^"]+)"\)'), r'"\1"'),
]


def normalizar_mongo_json(content: str) -> str:
    """Convierte MongoDB Extended JSON a JSON estándar."""
    for patron, reemplazo in MONGO_PATTERNS:
        content = patron.sub(reemplazo, content)
    return content


# ---------- UTILIDADES ----------
def leer_archivo_robusto(path: Path):
    """Lee un archivo probando varios encodings hasta que uno funcione."""
    for enc in ENCODINGS:
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read(), enc
        except UnicodeDecodeError:
            continue
    # Último recurso: leer en binario y decodificar con errores reemplazados
    with open(path, "rb") as f:
        return f.read().decode("utf-8", errors="replace"), "utf-8-replace"


def listar_archivos(data_dir: Path):
    """Devuelve la lista de archivos JSON ordenada cronológicamente."""
    archivos = []
    for year_dir in sorted(data_dir.glob("bicimad_*")):
        stations_dir = year_dir / "stations"
        if stations_dir.exists():
            for f in sorted(stations_dir.glob("*.json")):
                archivos.append(f)
    return archivos


def parsear_objetos_json_concatenados(content: str):
    """
    Parsea contenido que contiene múltiples objetos JSON concatenados,
    posiblemente en formato pretty-printed (con saltos de línea internos).
    Usa raw_decode para extraer un objeto a la vez.
    """
    decoder = json.JSONDecoder()
    snapshots = []
    errores = 0
    pos = 0
    longitud = len(content)
    while pos < longitud:
        # Saltar espacios en blanco
        while pos < longitud and content[pos] in " \t\r\n":
            pos += 1
        if pos >= longitud:
            break
        try:
            obj, end = decoder.raw_decode(content, pos)
            snapshots.append(obj)
            pos = end
        except json.JSONDecodeError:
            errores += 1
            # Avanzar al siguiente posible inicio de objeto
            siguiente = content.find("{", pos + 1)
            if siguiente == -1:
                break
            pos = siguiente
    return snapshots, errores


def parsear_snapshots(content: str):
    """
    Parsea el contenido detectando si es:
    - JSON array: [{...}, {...}]
    - NDJSON: un objeto por línea
    - Objetos JSON concatenados (pretty-printed o no)
    Aplica también normalización de MongoDB Extended JSON antes de parsear.
    """
    # Normalizar sintaxis de MongoDB
    content_norm = normalizar_mongo_json(content)
    content_strip = content_norm.lstrip()

    snapshots = []
    errores = 0

    if content_strip.startswith("["):
        # JSON array
        try:
            snapshots = json.loads(content_norm)
        except json.JSONDecodeError:
            errores += 1
    elif content_strip.startswith("{"):
        # Probar NDJSON primero (un objeto por línea)
        ndjson_intentado = False
        lineas = content_norm.splitlines()
        # Si la primera línea empieza por { y termina por }, es NDJSON
        primera_linea = lineas[0].strip() if lineas else ""
        if primera_linea.startswith("{") and primera_linea.endswith("}"):
            ndjson_intentado = True
            for line in lineas:
                line = line.strip()
                if not line:
                    continue
                try:
                    snapshots.append(json.loads(line))
                except json.JSONDecodeError:
                    errores += 1
        # Si no es NDJSON o falló, probar como objetos concatenados
        if not ndjson_intentado or not snapshots:
            snapshots, errores = parsear_objetos_json_concatenados(content_norm)
    return snapshots, errores


def analizar_archivo(path: Path, max_snapshots_inspect=200):
    """Analiza un archivo JSON y devuelve metadatos."""
    info = {
        "archivo": path.name,
        "ruta": str(path),
        "tamano_mb": round(path.stat().st_size / (1024 * 1024), 2),
        "encoding_detectado": None,
        "num_snapshots": 0,
        "primer_timestamp": None,
        "ultimo_timestamp": None,
        "min_estaciones": None,
        "max_estaciones": None,
        "campos_estacion": "",
        "num_estaciones_unicas_muestra": 0,
        "errores_parseo": 0,
    }

    try:
        content, enc = leer_archivo_robusto(path)
        info["encoding_detectado"] = enc
    except Exception as e:
        print(f"  Error abriendo {path.name}: {e}")
        return info

    snapshots, errores = parsear_snapshots(content)
    info["errores_parseo"] = errores
    info["num_snapshots"] = len(snapshots)

    if snapshots:
        timestamps = []
        for snap in snapshots:
            ts = snap.get("_id")
            if isinstance(ts, str):
                timestamps.append(ts)
        if timestamps:
            timestamps.sort()
            info["primer_timestamp"] = timestamps[0]
            info["ultimo_timestamp"] = timestamps[-1]

        sample = snapshots[:max_snapshots_inspect] if len(snapshots) > max_snapshots_inspect else snapshots
        n_est_lista = []
        campos = set()
        ids = set()
        for snap in sample:
            stations = snap.get("stations", [])
            n_est_lista.append(len(stations))
            for st in stations:
                campos.update(st.keys())
                if "id" in st:
                    ids.add(st["id"])
        if n_est_lista:
            info["min_estaciones"] = min(n_est_lista)
            info["max_estaciones"] = max(n_est_lista)

        info["campos_estacion"] = "|".join(sorted(campos))
        info["num_estaciones_unicas_muestra"] = len(ids)

    return info


def calcular_intervalos_snapshots(timestamps_iso):
    """Devuelve los intervalos en segundos entre snapshots consecutivos."""
    ts = []
    for t in timestamps_iso:
        if not t:
            continue
        try:
            ts.append(datetime.fromisoformat(t))
        except (ValueError, TypeError):
            continue
    ts.sort()
    intervalos = []
    for i in range(1, len(ts)):
        diff = (ts[i] - ts[i - 1]).total_seconds()
        intervalos.append(diff)
    return intervalos


def analizar_intervalos_archivo(path: Path):
    """Lee timestamps de un archivo y devuelve los intervalos entre snapshots."""
    try:
        content, _ = leer_archivo_robusto(path)
        snapshots, _ = parsear_snapshots(content)
        timestamps = [s.get("_id") for s in snapshots if isinstance(s.get("_id"), str)]
        return calcular_intervalos_snapshots(timestamps)
    except Exception:
        return []


# ---------- ANÁLISIS PRINCIPAL ----------
def main():
    print("=" * 70)
    print("ANÁLISIS ESTRUCTURAL DEL DATASET BICIMAD")
    print("=" * 70)

    archivos = listar_archivos(DATA_DIR)
    print(f"\nArchivos encontrados: {len(archivos)}")
    if not archivos:
        print(f"ERROR: no se encontraron archivos en {DATA_DIR}")
        return

    # ----- 1. METADATOS POR ARCHIVO -----
    print("\n[1/3] Analizando metadatos por archivo...")
    datos = []
    for f in tqdm(archivos):
        datos.append(analizar_archivo(f))
    df_archivos = pd.DataFrame(datos)

    # Asegurar tipo string en campos_estacion (por si algún row dejó set)
    df_archivos["campos_estacion"] = df_archivos["campos_estacion"].apply(
        lambda v: "|".join(sorted(v)) if isinstance(v, set) else (v if v else "")
    )

    df_archivos["anio"] = df_archivos["archivo"].apply(lambda s: int(Path(s).stem[:4]))
    df_archivos["mes"] = df_archivos["archivo"].apply(lambda s: int(Path(s).stem[4:6]))
    df_archivos.to_csv(OUTPUT_DIR / "metadatos_archivos.csv", index=False)
    print(f"   -> {OUTPUT_DIR / 'metadatos_archivos.csv'}")

    # Reporte de encodings detectados
    encodings_count = df_archivos["encoding_detectado"].value_counts()
    print(f"\n   Encodings detectados:")
    for enc, n in encodings_count.items():
        print(f"      {enc}: {n} archivos")

    # ----- 2. COBERTURA TEMPORAL -----
    print("\n[2/3] Construyendo matriz de cobertura temporal...")
    # Usamos NaN para los meses sin datos para diferenciarlos en el heatmap
    cobertura = pd.DataFrame(np.nan, index=range(1, 13), columns=range(2017, 2024))
    for _, row in df_archivos.iterrows():
        if row["num_snapshots"] > 0:
            cobertura.at[row["mes"], row["anio"]] = row["num_snapshots"]

    # Calcular la escala desde el mínimo no nulo
    valores_validos = cobertura.values[~np.isnan(cobertura.values)]
    if len(valores_validos) > 0:
        vmin = valores_validos.min()
        vmax = valores_validos.max()
    else:
        vmin, vmax = 0, 1

    fig, ax = plt.subplots(figsize=(10, 5))
    # Color para los NaN (meses sin datos)
    cmap = plt.cm.get_cmap("YlGnBu").copy()
    cmap.set_bad(color="#e0e0e0")  # gris claro
    sns.heatmap(
        cobertura,
        cmap=cmap,
        annot=True,
        fmt=".0f",
        vmin=vmin,
        vmax=vmax,
        cbar_kws={"label": "Número de snapshots"},
        linewidths=0.5,
        linecolor="white",
        ax=ax,
        mask=cobertura.isna(),
    )
    # Pintar a mano las celdas vacías como gris con etiqueta
    for i in range(cobertura.shape[0]):
        for j in range(cobertura.shape[1]):
            if pd.isna(cobertura.iloc[i, j]):
                ax.add_patch(plt.Rectangle((j, i), 1, 1,
                                           fill=True, color="#e0e0e0",
                                           edgecolor="white", linewidth=0.5))
                ax.text(j + 0.5, i + 0.5, "—",
                        ha="center", va="center",
                        color="#909090", fontsize=10)

    ax.set_title("Cobertura temporal del dataset: snapshots por mes y año\n"
                 "(las celdas grises indican meses sin datos)", pad=15)
    ax.set_xlabel("Año")
    ax.set_ylabel("Mes")
    meses_es = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
                "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
    ax.set_yticklabels(meses_es, rotation=0)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "fig_cobertura_temporal.png", bbox_inches="tight")
    plt.close()
    print(f"   -> {OUTPUT_DIR / 'fig_cobertura_temporal.png'}")

    # Tamaños de archivo
    fig, ax = plt.subplots(figsize=(12, 4))
    df_archivos_sorted = df_archivos.sort_values(["anio", "mes"])
    df_archivos_sorted["periodo"] = df_archivos_sorted["anio"].astype(str) + "-" + \
                                    df_archivos_sorted["mes"].astype(str).str.zfill(2)
    ax.bar(df_archivos_sorted["periodo"], df_archivos_sorted["tamano_mb"],
           color=sns.color_palette("YlGnBu", n_colors=1)[0])
    ax.set_title("Tamaño de cada archivo mensual (MB)", pad=15)
    ax.set_xlabel("Periodo")
    ax.set_ylabel("Tamaño (MB)")
    plt.xticks(rotation=90, fontsize=7)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "fig_tamanos_archivos.png", bbox_inches="tight")
    plt.close()
    print(f"   -> {OUTPUT_DIR / 'fig_tamanos_archivos.png'}")

    # Snapshots por mes
    fig, ax = plt.subplots(figsize=(12, 4))
    ax.plot(df_archivos_sorted["periodo"], df_archivos_sorted["num_snapshots"],
            marker="o", linewidth=1.5,
            color=sns.color_palette("YlGnBu", n_colors=1)[0])
    ax.set_title("Número de snapshots registrados por mes", pad=15)
    ax.set_xlabel("Periodo")
    ax.set_ylabel("Snapshots")
    plt.xticks(rotation=90, fontsize=7)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "fig_snapshots_por_mes.png", bbox_inches="tight")
    plt.close()
    print(f"   -> {OUTPUT_DIR / 'fig_snapshots_por_mes.png'}")

    # ----- 3. INTERVALOS ENTRE SNAPSHOTS -----
    print("\n[3/3] Analizando frecuencia de snapshots...")
    df_validos = df_archivos[df_archivos["num_snapshots"] > 0]
    if df_validos.empty:
        print("   No hay archivos válidos para analizar intervalos.")
    else:
        muestra_archivos = df_validos.groupby("anio").first().reset_index()
        todos_intervalos = []
        for _, row in muestra_archivos.iterrows():
            intervals = analizar_intervalos_archivo(Path(row["ruta"]))
            for v in intervals:
                todos_intervalos.append({"anio": row["anio"], "intervalo_seg": v})

        df_intervalos = pd.DataFrame(todos_intervalos)
        if not df_intervalos.empty:
            df_intervalos.to_csv(OUTPUT_DIR / "intervalos_snapshots.csv", index=False)
            fig, ax = plt.subplots(figsize=(9, 5))
            df_plot = df_intervalos[df_intervalos["intervalo_seg"] < 1800]
            sns.boxplot(data=df_plot, x="anio", y="intervalo_seg",
                        palette="YlGnBu", ax=ax)
            ax.set_title("Intervalo entre snapshots consecutivos por año", pad=15)
            ax.set_xlabel("Año")
            ax.set_ylabel("Intervalo (segundos)")
            plt.tight_layout()
            plt.savefig(OUTPUT_DIR / "fig_intervalos_snapshots.png", bbox_inches="tight")
            plt.close()
            print(f"   -> {OUTPUT_DIR / 'fig_intervalos_snapshots.png'}")

    # ----- RESUMEN -----
    print("\n" + "=" * 70)
    print("RESUMEN DE HALLAZGOS")
    print("=" * 70)
    print(f"Total de archivos analizados:         {len(df_archivos)}")
    archivos_con_datos = (df_archivos["num_snapshots"] > 0).sum()
    print(f"Archivos con datos válidos:           {archivos_con_datos}")
    print(f"Total de snapshots:                   {df_archivos['num_snapshots'].sum():,}")
    print(f"Tamaño total de los datos:            {df_archivos['tamano_mb'].sum():,.0f} MB")
    print(f"Periodo cubierto:                     {df_archivos['anio'].min()}-{df_archivos['mes'].min():02d}"
          f" a {df_archivos['anio'].max()}-{df_archivos['mes'].max():02d}")

    if archivos_con_datos > 0:
        df_v = df_archivos[df_archivos["num_snapshots"] > 0]
        print(f"Min estaciones por snapshot:          {df_v['min_estaciones'].min()}")
        print(f"Max estaciones por snapshot:          {df_v['max_estaciones'].max()}")

    # Meses faltantes
    print("\nMeses no presentes en el dataset (huecos en la cobertura):")
    meses_completos = set()
    for anio in range(2017, 2024):
        for mes in range(1, 13):
            meses_completos.add((anio, mes))
    meses_presentes = set(zip(df_archivos["anio"], df_archivos["mes"]))
    huecos = sorted(meses_completos - meses_presentes)
    huecos_filtrados = [h for h in huecos if 2017 <= h[0] <= 2022]
    if huecos_filtrados:
        print(f"   {len(huecos_filtrados)} huecos entre 2017 y 2022:")
        for anio, mes in huecos_filtrados[:30]:
            print(f"      {anio}-{mes:02d}")
        if len(huecos_filtrados) > 30:
            print(f"      ... y {len(huecos_filtrados) - 30} más")

    # Esquemas distintos
    esquemas = df_archivos["campos_estacion"].dropna().unique()
    esquemas_no_vacios = [e for e in esquemas if e]
    print(f"\nEsquemas distintos de estación detectados: {len(esquemas_no_vacios)}")
    if len(esquemas_no_vacios) > 1:
        print("   ATENCIÓN: hay archivos con esquemas distintos. Detalles:")
        for esq in esquemas_no_vacios:
            n = (df_archivos["campos_estacion"] == esq).sum()
            print(f"      [{n} archivos] Campos: {esq}")
    elif len(esquemas_no_vacios) == 1:
        print(f"   Esquema único: {esquemas_no_vacios[0]}")

    print(f"\nResultados guardados en: {OUTPUT_DIR.resolve()}")
    print("\nFiguras generadas para la memoria:")
    for fig_path in sorted(OUTPUT_DIR.glob("fig_*.png")):
        print(f"   - {fig_path.name}")


if __name__ == "__main__":
    main()