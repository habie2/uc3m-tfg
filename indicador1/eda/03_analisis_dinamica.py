"""
03_analisis_dinamica.py

Analiza la dinámica del sistema BiciMad mediante un muestreo representativo.
Toma un mes representativo, lo aplana en formato tabular, genera un informe
fg-data-profiling y produce gráficos adicionales sobre patrones temporales y
comportamiento del sistema.

Uso:
    python 03_analisis_dinamica.py
"""
import json
import re
from pathlib import Path
from datetime import datetime

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from tqdm import tqdm

# ---------- CONFIGURACIÓN ----------
# Si está montado en /data (caso Docker), úsalo. Si no, ruta local.
_DOCKER_DATA = Path('/data')
if _DOCKER_DATA.exists() and any(_DOCKER_DATA.iterdir()):
    DATA_DIR = _DOCKER_DATA
else:
    DATA_DIR = Path.home() / 'Downloads' / 'bicimad_data'  # ajusta si es necesario
OUTPUT_DIR = Path("output/dinamica")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Mes representativo a analizar (puedes cambiarlo)
MES_REPRESENTATIVO = ("2022", "05")  # mayo 2022

sns.set_theme(style="whitegrid", context="paper")
plt.rcParams['figure.dpi'] = 300
plt.rcParams['savefig.dpi'] = 300
plt.rcParams['font.size'] = 10

ENCODINGS = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]

MONGO_PATTERNS = [
    (re.compile(r'NumberInt\((-?\d+)\)'), r'\1'),
    (re.compile(r'NumberLong\((-?\d+)\)'), r'\1'),
    (re.compile(r'NumberDecimal\("([^"]+)"\)'), r'\1'),
    (re.compile(r'NumberDouble\((-?[\d.]+)\)'), r'\1'),
    (re.compile(r'ObjectId\("([^"]+)"\)'), r'"\1"'),
    (re.compile(r'ISODate\("([^"]+)"\)'), r'"\1"'),
]


def normalizar_mongo_json(content: str) -> str:
    for patron, reemplazo in MONGO_PATTERNS:
        content = patron.sub(reemplazo, content)
    return content


# ---------- UTILIDADES ----------
def leer_archivo_robusto(path: Path):
    for enc in ENCODINGS:
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    with open(path, "rb") as f:
        return f.read().decode("utf-8", errors="replace")


def parsear_objetos_concatenados(content: str):
    """Parsea contenido con múltiples objetos JSON concatenados."""
    decoder = json.JSONDecoder()
    snapshots = []
    pos = 0
    while pos < len(content):
        while pos < len(content) and content[pos] in " \t\r\n":
            pos += 1
        if pos >= len(content):
            break
        try:
            obj, end = decoder.raw_decode(content, pos)
            snapshots.append(obj)
            pos = end
        except json.JSONDecodeError:
            siguiente = content.find("{", pos + 1)
            if siguiente == -1:
                break
            pos = siguiente
    return snapshots


def cargar_archivo_completo(path: Path):
    """Carga todos los snapshots de un archivo, soportando varios formatos."""
    try:
        content = leer_archivo_robusto(path)
        content = normalizar_mongo_json(content)
        content_strip = content.lstrip()

        if content_strip.startswith("["):
            return json.loads(content)
        elif content_strip.startswith("{"):
            # Probar NDJSON primero
            lineas = content.splitlines()
            primera = lineas[0].strip() if lineas else ""
            if primera.startswith("{") and primera.endswith("}"):
                snaps = []
                for line in lineas:
                    line = line.strip()
                    if line:
                        try:
                            snaps.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
                if snaps:
                    return snaps
            # Si no, probar como objetos concatenados (pretty-printed)
            return parsear_objetos_concatenados(content)
        return []
    except Exception as e:
        print(f"Error: {e}")
        return []


def aplanar_snapshots(snapshots):
    """Convierte la lista de snapshots en un DataFrame plano."""
    rows = []
    for snap in snapshots:
        ts = snap.get("_id")
        for st in snap.get("stations", []):
            rows.append({
                "timestamp": ts,
                "id_estacion": st.get("id"),
                "name": st.get("name"),
                "activate": st.get("activate"),
                "no_available": st.get("no_available"),
                "light": st.get("light"),
                "total_bases": st.get("total_bases"),
                "free_bases": st.get("free_bases"),
                "dock_bikes": st.get("dock_bikes"),
                "reservations_count": st.get("reservations_count"),
                "latitude": st.get("latitude"),
                "longitude": st.get("longitude"),
            })
    df = pd.DataFrame(rows)
    if not df.empty:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        for col in ["activate", "no_available", "light", "total_bases",
                    "free_bases", "dock_bikes", "reservations_count"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
        df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
        # Métrica derivada (evitar división por cero)
        df["ocupacion"] = np.where(
            df["total_bases"] > 0,
            df["dock_bikes"] / df["total_bases"],
            np.nan
        )
        df["dia_semana"] = df["timestamp"].dt.dayofweek
        df["hora"] = df["timestamp"].dt.hour
        df["fecha"] = df["timestamp"].dt.date
    return df


def encontrar_archivo_mes(anio: str, mes: str):
    target = DATA_DIR / f"bicimad_{anio}" / "stations" / f"{anio}{mes}.json"
    return target if target.exists() else None


# ---------- ANÁLISIS PRINCIPAL ----------
def main():
    print("=" * 70)
    print(f"ANÁLISIS DE DINÁMICA - {MES_REPRESENTATIVO[0]}-{MES_REPRESENTATIVO[1]}")
    print("=" * 70)

    archivo = encontrar_archivo_mes(*MES_REPRESENTATIVO)
    if not archivo:
        print(f"ERROR: no se encontró el archivo para {MES_REPRESENTATIVO}")
        return

    print(f"\n[1/5] Cargando archivo: {archivo.name}")
    snaps = cargar_archivo_completo(archivo)
    print(f"   {len(snaps)} snapshots cargados")

    if not snaps:
        print("ERROR: archivo vacío o no parseable")
        return

    snaps_muestreados = snaps[::10] if len(snaps) > 5000 else snaps
    print(f"   Aplanando {len(snaps_muestreados)} snapshots (1 de cada 10)...")
    df = aplanar_snapshots(snaps_muestreados)
    print(f"   DataFrame resultante: {len(df):,} filas")

    if df.empty:
        print("ERROR: DataFrame vacío después del aplanado.")
        return

    df.to_csv(OUTPUT_DIR / "muestra_dinamica.csv", index=False)

    # ----- 2. RESUMEN EXPLORATORIO DE LA MUESTRA -----
    print("\n[2/5] Generando resumen exploratorio de la muestra...")

    # 2.1 Tabla resumen de columnas
    resumen_cols = []
    for col in df.columns:
        info = {
            "Columna": col,
            "Tipo": str(df[col].dtype),
            "No nulos": df[col].notna().sum(),
            "Nulos": df[col].isna().sum(),
            "% Nulos": round(df[col].isna().mean() * 100, 2),
        }
        if df[col].dtype in ["float64", "int64", "Int64"]:
            info["Min"] = df[col].min()
            info["Max"] = df[col].max()
            info["Media"] = round(df[col].mean(), 4)
            info["Mediana"] = round(df[col].median(), 4)
            info["Desv. Std"] = round(df[col].std(), 4)
        else:
            info["Min"] = ""
            info["Max"] = ""
            info["Media"] = ""
            info["Mediana"] = ""
            info["Desv. Std"] = ""
        resumen_cols.append(info)
    df_resumen = pd.DataFrame(resumen_cols)
    df_resumen.to_csv(OUTPUT_DIR / "resumen_columnas_dinamica.csv", index=False)
    print(f"   -> resumen_columnas_dinamica.csv")

    # Imprimir tabla por consola
    print(f"\n   Estructura de la muestra ({len(df):,} filas):")
    print(f"   {'Columna':<22} {'Tipo':<12} {'No nulos':>8} {'Nulos':>6} {'%':>6} {'Min':>10} {'Max':>10} {'Media':>10}")
    print("   " + "-" * 90)
    for _, r in df_resumen.iterrows():
        nulos_str = f"{r['% Nulos']:.1f}%"
        min_str = f"{r['Min']}" if r['Min'] != "" else ""
        max_str = f"{r['Max']}" if r['Max'] != "" else ""
        media_str = f"{r['Media']}" if r['Media'] != "" else ""
        print(f"   {r['Columna']:<22} {r['Tipo']:<12} {r['No nulos']:>8} {r['Nulos']:>6} {nulos_str:>6} {min_str:>10} {max_str:>10} {media_str:>10}")

    # ----- 3. PATRONES TEMPORALES -----
    print("\n[3/5] Generando gráficos de patrones temporales...")

    # 3.1 Heatmap día/hora
    df_pivot = df.pivot_table(
        values="ocupacion", index="dia_semana", columns="hora",
        aggfunc="mean"
    )
    fig, ax = plt.subplots(figsize=(12, 4))
    sns.heatmap(df_pivot, cmap="YlGnBu", ax=ax,
                cbar_kws={"label": "Ocupación media (0-1)"},
                linewidths=0.3, linecolor="white")
    ax.set_title(f"Ocupación media de las estaciones por día y hora "
                 f"({MES_REPRESENTATIVO[0]}-{MES_REPRESENTATIVO[1]})", pad=15)
    ax.set_xlabel("Hora del día")
    ax.set_ylabel("Día de la semana")
    dias_es = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
    ax.set_yticklabels(dias_es, rotation=0)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "fig_heatmap_ocupacion.png", bbox_inches="tight")
    plt.close()
    print(f"   -> fig_heatmap_ocupacion.png")

    # 3.2 Distribución de ocupación
    fig, ax = plt.subplots(figsize=(8, 5))
    sns.histplot(df["ocupacion"].dropna(), bins=40,
                 color=sns.color_palette("YlGnBu", n_colors=3)[1], ax=ax)
    ax.set_title("Distribución de la ocupación de las estaciones", pad=15)
    ax.set_xlabel("Ocupación (bicis disponibles / capacidad total)")
    ax.set_ylabel("Frecuencia")
    media = df["ocupacion"].mean()
    ax.axvline(media, color="red", linestyle="--", label=f"Media: {media:.2f}")
    ax.legend()
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "fig_distribucion_ocupacion.png", bbox_inches="tight")
    plt.close()
    print(f"   -> fig_distribucion_ocupacion.png")

    # 3.3 Estados a lo largo del día
    df["estado"] = pd.cut(df["ocupacion"], bins=[-0.01, 0.01, 0.95, 1.01],
                          labels=["Vacía", "Operativa", "Llena"])
    df_estados = df.groupby(["hora", "estado"], observed=True).size().unstack(fill_value=0)
    df_estados_pct = df_estados.div(df_estados.sum(axis=1), axis=0) * 100

    fig, ax = plt.subplots(figsize=(10, 5))
    df_estados_pct.plot(kind="area", stacked=True, ax=ax,
                       color=["#d73027", "#abdda4", "#2c7bb6"], alpha=0.7)
    ax.set_title("Estado de las estaciones a lo largo del día", pad=15)
    ax.set_xlabel("Hora")
    ax.set_ylabel("Porcentaje de estaciones")
    ax.legend(title="Estado", loc="upper right")
    ax.set_xlim(0, 23)
    ax.set_ylim(0, 100)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "fig_estados_dia.png", bbox_inches="tight")
    plt.close()
    print(f"   -> fig_estados_dia.png")

    # 3.4 Disponibilidad
    df_disp = df.groupby("hora").agg(
        activas=("activate", "mean"),
        no_disponibles=("no_available", "mean"),
    )
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(df_disp.index, df_disp["activas"] * 100,
            marker="o", label="% estaciones activas",
            color=sns.color_palette("YlGnBu", n_colors=3)[2])
    ax.plot(df_disp.index, df_disp["no_disponibles"] * 100,
            marker="s", label="% estaciones no disponibles",
            color="#d73027")
    ax.set_title("Disponibilidad de las estaciones a lo largo del día", pad=15)
    ax.set_xlabel("Hora")
    ax.set_ylabel("Porcentaje de estaciones")
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "fig_disponibilidad.png", bbox_inches="tight")
    plt.close()
    print(f"   -> fig_disponibilidad.png")

    # ----- 4. CAMPO 'light' -----
    print("\n[4/5] Analizando campo 'light' (estado de la estación)...")
    light_counts = df["light"].value_counts().sort_index()
    fig, ax = plt.subplots(figsize=(7, 4))
    light_counts.plot(kind="bar", ax=ax,
                      color=sns.color_palette("YlGnBu", n_colors=len(light_counts)))
    ax.set_title("Distribución del campo 'light' (estado del semáforo de la estación)", pad=15)
    ax.set_xlabel("Valor de 'light'")
    ax.set_ylabel("Frecuencia")
    plt.xticks(rotation=0)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "fig_distribucion_light.png", bbox_inches="tight")
    plt.close()
    print(f"   -> fig_distribucion_light.png")

    df["bin_ocupacion"] = pd.cut(df["ocupacion"],
                                 bins=[-0.01, 0.01, 0.25, 0.5, 0.75, 0.95, 1.01],
                                 labels=["0%", "0-25%", "25-50%", "50-75%", "75-95%", "95-100%"])
    cross = pd.crosstab(df["light"], df["bin_ocupacion"])
    fig, ax = plt.subplots(figsize=(9, 4))
    sns.heatmap(cross, annot=True, fmt="d", cmap="YlGnBu", ax=ax,
                cbar_kws={"label": "Conteos"})
    ax.set_title("Relación entre el campo 'light' y la ocupación de la estación", pad=15)
    ax.set_xlabel("Bin de ocupación")
    ax.set_ylabel("Valor de 'light'")
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "fig_light_vs_ocupacion.png", bbox_inches="tight")
    plt.close()
    print(f"   -> fig_light_vs_ocupacion.png")

    # ----- 5. CONSISTENCIA -----
    print("\n[5/5] Comprobando consistencia de los conteos...")
    df["suma_componentes"] = df["dock_bikes"] + df["free_bases"] # + df["reservations_count"]
    df["diff"] = df["suma_componentes"] - df["total_bases"]
    inconsistencias = (df["diff"] != 0).sum()
    pct_inc = inconsistencias / len(df) * 100

    fig, ax = plt.subplots(figsize=(8, 4))
    sns.histplot(df["diff"].dropna(), bins=40, color="#d73027", ax=ax)
    ax.set_title("Diferencia: (bicis + libres) − capacidad total\n"
                 f"Inconsistencias: {inconsistencias:,} ({pct_inc:.2f}% de los registros)",
                 pad=15)
    ax.set_xlabel("Diferencia")
    ax.set_ylabel("Frecuencia")
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "fig_consistencia_conteos.png", bbox_inches="tight")
    plt.close()
    print(f"   -> fig_consistencia_conteos.png")

    # ----- RESUMEN -----
    print("\n" + "=" * 70)
    print("RESUMEN DE LA DINÁMICA")
    print("=" * 70)
    print(f"Periodo analizado:                    {MES_REPRESENTATIVO[0]}-{MES_REPRESENTATIVO[1]}")
    print(f"Snapshots procesados:                 {len(snaps_muestreados):,}")
    print(f"Filas en DataFrame:                   {len(df):,}")
    print(f"Estaciones distintas observadas:      {df['id_estacion'].nunique()}")
    print(f"Ocupación media:                      {df['ocupacion'].mean():.2%}")
    print(f"Ocupación mediana:                    {df['ocupacion'].median():.2%}")
    print(f"% snapshots con estación vacía:       "
          f"{(df['ocupacion'] == 0).mean():.2%}")
    print(f"% snapshots con estación llena:       "
          f"{(df['ocupacion'] >= 0.95).mean():.2%}")
    print(f"% estaciones desactivadas (media):    {(1 - df['activate']).mean():.2%}")
    print(f"Inconsistencias en los conteos:       {inconsistencias:,} ({pct_inc:.2f}%)")
    print(f"Valores únicos de 'light':            {sorted(df['light'].dropna().unique())}")

    print(f"\nResultados en: {OUTPUT_DIR.resolve()}")
    print("\nFiguras generadas:")
    for fig_path in sorted(OUTPUT_DIR.glob("fig_*.png")):
        print(f"   - {fig_path.name}")


if __name__ == "__main__":
    main()