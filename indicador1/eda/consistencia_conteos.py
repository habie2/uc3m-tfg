"""
04_analisis_inconsistencias.py

Análisis en profundidad de las inconsistencias en los conteos de las
estaciones de BiciMad. Investiga los casos en los que:

    dock_bikes + free_bases + reservations_count ≠ total_bases

Genera gráficos y CSVs que explican cuándo, dónde y por qué ocurren.

Uso:
    python 04_analisis_inconsistencias.py
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
_DOCKER_DATA = Path('/data')
if _DOCKER_DATA.exists() and any(_DOCKER_DATA.iterdir()):
    DATA_DIR = _DOCKER_DATA
else:
    DATA_DIR = Path.home() / "Downloads" / "bicimad_data"

OUTPUT_DIR = Path("output/inconsistencias")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Meses a analizar (uno por año para tener visión temporal)
MESES_MUESTRA = [
    ("2018", "08"),
    ("2019", "05"),
    ("2020", "05"),
    ("2021", "05"),
    ("2022", "05"),
]

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


def normalizar_mongo_json(content):
    for patron, reemplazo in MONGO_PATTERNS:
        content = patron.sub(reemplazo, content)
    return content


def leer_archivo_robusto(path):
    for enc in ENCODINGS:
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    with open(path, "rb") as f:
        return f.read().decode("utf-8", errors="replace")


def parsear_objetos_concatenados(content):
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


def cargar_archivo_completo(path):
    try:
        content = leer_archivo_robusto(path)
        content = normalizar_mongo_json(content)
        content_strip = content.lstrip()
        if content_strip.startswith("["):
            return json.loads(content)
        elif content_strip.startswith("{"):
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
            return parsear_objetos_concatenados(content)
        return []
    except Exception as e:
        print(f"Error: {e}")
        return []


def aplanar_snapshots(snapshots):
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
            })
    df = pd.DataFrame(rows)
    if not df.empty:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        for col in ["activate", "no_available", "light", "total_bases",
                     "free_bases", "dock_bikes", "reservations_count"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df["suma"] = df["dock_bikes"] + df["free_bases"]  + df["reservations_count"]
        df["diff"] = df["suma"] - df["total_bases"]
        df["hora"] = df["timestamp"].dt.hour
        df["dia_semana"] = df["timestamp"].dt.dayofweek
        df["fecha"] = df["timestamp"].dt.date
        df["ocupacion"] = np.where(
            df["total_bases"] > 0,
            df["dock_bikes"] / df["total_bases"],
            np.nan
        )
    return df


def encontrar_archivo_mes(anio, mes):
    target = DATA_DIR / f"bicimad_{anio}" / "stations" / f"{anio}{mes}.json"
    return target if target.exists() else None


# ---------- ANÁLISIS PRINCIPAL ----------
def main():
    print("=" * 70)
    print("ANÁLISIS DE INCONSISTENCIAS EN LOS CONTEOS")
    print("=" * 70)
    print("\nLa ecuación esperada es:")
    print("   dock_bikes + free_bases + reservations_count = total_bases")
    print("   (bicis ancladas + huecos libres + reservas = capacidad total)")
    print("\nCuando no se cumple, algo raro está pasando.\n")

    # ----- 1. CARGAR MUESTRAS DE VARIOS AÑOS -----
    print("[1/6] Cargando muestras de varios años...")
    frames = []
    for anio, mes in MESES_MUESTRA:
        archivo = encontrar_archivo_mes(anio, mes)
        if not archivo:
            print(f"   {anio}-{mes}: archivo no encontrado, saltando")
            continue
        print(f"   Cargando {anio}-{mes}...")
        snaps = cargar_archivo_completo(archivo)
        # Muestrear 1 de cada 10 para no reventar memoria
        snaps_m = snaps[::10] if len(snaps) > 5000 else snaps
        df_mes = aplanar_snapshots(snaps_m)
        df_mes["periodo"] = f"{anio}-{mes}"
        frames.append(df_mes)

    if not frames:
        print("ERROR: no se pudo cargar ningún archivo.")
        return

    df = pd.concat(frames, ignore_index=True)
    print(f"\n   Total de registros cargados: {len(df):,}")

    # ----- 2. VISIÓN GENERAL -----
    print("\n[2/6] Visión general de inconsistencias...")

    total = len(df)
    consistentes = (df["diff"] == 0).sum()
    inconsistentes = (df["diff"] != 0).sum()
    pct = inconsistentes / total * 100

    print(f"\n   Registros totales:       {total:,}")
    print(f"   Consistentes (diff=0):   {consistentes:,} ({100 - pct:.2f}%)")
    print(f"   Inconsistentes (diff≠0): {inconsistentes:,} ({pct:.2f}%)")

    # Desglose por signo de la diferencia
    positivos = (df["diff"] > 0).sum()
    negativos = (df["diff"] < 0).sum()
    print(f"\n   Diferencia positiva (sobran bicis):   {positivos:,}")
    print(f"   Diferencia negativa (faltan bicis):   {negativos:,}")

    # Distribución de la diferencia
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Histograma de la diferencia
    ax = axes[0]
    sns.histplot(df["diff"].dropna(), bins=50, color="#d73027", ax=ax)
    ax.set_title(f"Distribución de la diferencia\n"
                 f"(bicis + libres + reservas) − capacidad\n"
                 f"Inconsistencias: {inconsistentes:,} ({pct:.2f}%)", pad=15)
    ax.set_xlabel("Diferencia")
    ax.set_ylabel("Frecuencia")
    ax.axvline(0, color="black", linestyle="-", linewidth=1)

    # Pie chart consistentes vs no
    ax = axes[1]
    labels = [f"Consistentes\n{consistentes:,} ({100-pct:.1f}%)",
              f"Inconsistentes\n{inconsistentes:,} ({pct:.1f}%)"]
    colors = ["#abdda4", "#d73027"]
    ax.pie([consistentes, inconsistentes], labels=labels, colors=colors,
           startangle=90, textprops={"fontsize": 10})
    ax.set_title("Proporción de registros consistentes", pad=15)

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "fig_vision_general.png", bbox_inches="tight")
    plt.close()
    print(f"   -> fig_vision_general.png")

    # ----- 3. ¿CUÁNDO OCURREN? -----
    print("\n[3/6] Analizando cuándo ocurren las inconsistencias...")

    # Por periodo (año-mes)
    inc_por_periodo = df.groupby("periodo").agg(
        total=("diff", "size"),
        inconsistentes=("diff", lambda x: (x != 0).sum()),
    )
    inc_por_periodo["pct"] = (inc_por_periodo["inconsistentes"] /
                               inc_por_periodo["total"] * 100).round(2)

    print("\n   Inconsistencias por periodo:")
    print(f"   {'Periodo':<12} {'Total':>10} {'Incons.':>10} {'%':>8}")
    print("   " + "-" * 42)
    for idx, row in inc_por_periodo.iterrows():
        print(f"   {idx:<12} {row['total']:>10,} {row['inconsistentes']:>10,} {row['pct']:>7.2f}%")

    fig, ax = plt.subplots(figsize=(10, 5))
    inc_por_periodo["pct"].plot(kind="bar", ax=ax,
                                color=sns.color_palette("YlGnBu", n_colors=len(inc_por_periodo)))
    ax.set_title("Porcentaje de registros inconsistentes por periodo", pad=15)
    ax.set_xlabel("Periodo")
    ax.set_ylabel("% inconsistentes")
    plt.xticks(rotation=45)
    for i, v in enumerate(inc_por_periodo["pct"]):
        ax.text(i, v + 0.3, f"{v:.1f}%", ha="center", fontsize=9)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "fig_inconsistencias_por_periodo.png", bbox_inches="tight")
    plt.close()
    print(f"   -> fig_inconsistencias_por_periodo.png")

    # Por hora del día
    df_inc = df[df["diff"] != 0].copy()
    if not df_inc.empty:
        inc_por_hora = df.groupby("hora").agg(
            total=("diff", "size"),
            inconsistentes=("diff", lambda x: (x != 0).sum()),
        )
        inc_por_hora["pct"] = (inc_por_hora["inconsistentes"] /
                                inc_por_hora["total"] * 100).round(2)

        fig, ax = plt.subplots(figsize=(10, 5))
        ax.bar(inc_por_hora.index, inc_por_hora["pct"],
               color=sns.color_palette("YlGnBu", n_colors=24))
        ax.set_title("Porcentaje de inconsistencias por hora del día", pad=15)
        ax.set_xlabel("Hora")
        ax.set_ylabel("% inconsistentes")
        ax.set_xticks(range(24))
        plt.tight_layout()
        plt.savefig(OUTPUT_DIR / "fig_inconsistencias_por_hora.png", bbox_inches="tight")
        plt.close()
        print(f"   -> fig_inconsistencias_por_hora.png")

    # ----- 4. ¿DÓNDE OCURREN? -----
    print("\n[4/6] Analizando en qué estaciones ocurren...")

    inc_por_estacion = df.groupby(["id_estacion", "name"]).agg(
        total=("diff", "size"),
        inconsistentes=("diff", lambda x: (x != 0).sum()),
        diff_media=("diff", lambda x: x[x != 0].mean() if (x != 0).any() else 0),
    ).reset_index()
    inc_por_estacion["pct"] = (inc_por_estacion["inconsistentes"] /
                                inc_por_estacion["total"] * 100).round(2)
    inc_por_estacion = inc_por_estacion.sort_values("pct", ascending=False)

    # Top 20 estaciones más problemáticas
    top20 = inc_por_estacion.head(20)
    print(f"\n   Top 20 estaciones con más inconsistencias:")
    print(f"   {'Estación':<30} {'ID':>5} {'Total':>8} {'Incons.':>8} {'%':>7} {'Diff media':>10}")
    print("   " + "-" * 72)
    for _, r in top20.iterrows():
        nombre = r["name"][:28] if isinstance(r["name"], str) else "?"
        print(f"   {nombre:<30} {r['id_estacion']:>5} {r['total']:>8,} "
              f"{r['inconsistentes']:>8,} {r['pct']:>6.1f}% {r['diff_media']:>9.1f}")

    fig, ax = plt.subplots(figsize=(10, 8))
    labels = top20.apply(
        lambda r: f"{r['name'][:25]} (#{r['id_estacion']})", axis=1
    )
    ax.barh(range(len(top20)), top20["pct"],
            color=sns.color_palette("YlOrRd", n_colors=len(top20)))
    ax.set_yticks(range(len(top20)))
    ax.set_yticklabels(labels, fontsize=8)
    ax.invert_yaxis()
    ax.set_title("Top 20 estaciones con mayor % de registros inconsistentes", pad=15)
    ax.set_xlabel("% de registros inconsistentes")
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "fig_top_estaciones_inconsistentes.png", bbox_inches="tight")
    plt.close()
    print(f"   -> fig_top_estaciones_inconsistentes.png")

    inc_por_estacion.to_csv(OUTPUT_DIR / "inconsistencias_por_estacion.csv", index=False)
    print(f"   -> inconsistencias_por_estacion.csv")

    # ----- 5. ¿QUÉ ESTÁ PASANDO EN LOS REGISTROS INCONSISTENTES? -----
    print("\n[5/6] Investigando los registros inconsistentes en detalle...")

    if df_inc.empty:
        print("   No hay registros inconsistentes. ¡Todo bien!")
    else:
        # 5.1 Relación con el estado de la estación
        print("\n   Relación con el estado de la estación:")

        # ¿Están las estaciones desactivadas?
        inc_activas = df_inc["activate"].value_counts()
        print(f"   activate=1 (activa):     {inc_activas.get(1, 0):,}")
        print(f"   activate=0 (inactiva):   {inc_activas.get(0, 0):,}")

        # ¿Están no disponibles?
        inc_noavail = df_inc["no_available"].value_counts()
        print(f"   no_available=0 (ok):     {inc_noavail.get(0, 0):,}")
        print(f"   no_available=1 (no disp):{inc_noavail.get(1, 0):,}")

        # ¿Qué valor de light tienen?
        inc_light = df_inc["light"].value_counts().sort_index()
        print(f"   light valores:           {dict(inc_light)}")

        # Tabla cruzada activate × no_available para inconsistentes vs consistentes
        df["es_inconsistente"] = df["diff"] != 0
        cross = pd.crosstab(
            [df["activate"], df["no_available"]],
            df["es_inconsistente"],
            margins=True,
        )
        cross.columns = ["Consistente", "Inconsistente", "Total"]
        cross.to_csv(OUTPUT_DIR / "cruce_activate_noavailable.csv")
        print(f"\n   -> cruce_activate_noavailable.csv")

        fig, axes = plt.subplots(1, 3, figsize=(16, 5))

        # Gráfico: activate en inconsistentes vs consistentes
        # Gráfico: activate en inconsistentes vs consistentes
        ax = axes[0]
        df_comp_activate = df.groupby(["activate", "es_inconsistente"]).size().unstack()
        df_comp_activate_pct = df_comp_activate.div(df_comp_activate.sum(axis=1), axis=0) * 100
        df_comp_activate_pct.plot(kind="bar", stacked=True, ax=ax,
                                  color=["#abdda4", "#d73027"])
        ax.set_title("¿Están activas las estaciones\ninconsistentes?", pad=10)
        ax.set_xlabel("activate")
        ax.set_ylabel("% de registros")
        ax.legend(["Consistente", "Inconsistente"], fontsize=8)
        
        # CORRECCIÓN PARA ACTIVATE
        labels_act = {0: "0 (inactiva)", 1: "1 (activa)"}
        ax.set_xticks(range(len(df_comp_activate_pct.index)))
        ax.set_xticklabels([labels_act.get(x, str(x)) for x in df_comp_activate_pct.index], rotation=0)

        # Gráfico: no_available en inconsistentes vs consistentes
        ax = axes[1]
        df_comp_noavail = df.groupby(["no_available", "es_inconsistente"]).size().unstack()
        df_comp_noavail_pct = df_comp_noavail.div(df_comp_noavail.sum(axis=1), axis=0) * 100
        df_comp_noavail_pct.plot(kind="bar", stacked=True, ax=ax,
                                 color=["#abdda4", "#d73027"])
        ax.set_title("¿Están disponibles las estaciones\ninconsistentes?", pad=10)
        ax.set_xlabel("no_available")
        ax.set_ylabel("% de registros")
        ax.legend(["Consistente", "Inconsistente"], fontsize=8)
        
        # CORRECCIÓN PARA NO_AVAILABLE
        labels_noavail = {0: "0 (disponible)", 1: "1 (no disponible)"}
        ax.set_xticks(range(len(df_comp_noavail_pct.index)))
        ax.set_xticklabels([labels_noavail.get(x, str(x)) for x in df_comp_noavail_pct.index], rotation=0)

        # Gráfico: light en inconsistentes vs consistentes
        ax = axes[2]
        df_comp_light = df.groupby(["light", "es_inconsistente"]).size().unstack()
        df_comp_light_pct = df_comp_light.div(df_comp_light.sum(axis=1), axis=0) * 100
        df_comp_light_pct.plot(kind="bar", stacked=True, ax=ax,
                                color=["#abdda4", "#d73027"])
        ax.set_title("Valor de 'light' en estaciones\ninconsistentes vs consistentes", pad=10)
        ax.set_xlabel("light")
        ax.set_ylabel("% de registros")
        ax.legend(["Consistente", "Inconsistente"], fontsize=8)
        
        # CORRECCIÓN PARA LIGHT
        ax.set_xticks(range(len(df_comp_light_pct.index)))
        ax.set_xticklabels([str(int(x)) for x in df_comp_light_pct.index], rotation=0)

        plt.tight_layout()
        plt.savefig(OUTPUT_DIR / "fig_estado_vs_inconsistencia.png", bbox_inches="tight")
        plt.close()
        print(f"   -> fig_estado_vs_inconsistencia.png")

        # 5.2 ¿Qué valores tienen dock_bikes y free_bases cuando hay inconsistencia?
        print("\n   Valores en registros inconsistentes:")
        print(f"   dock_bikes:  min={df_inc['dock_bikes'].min()}, "
              f"max={df_inc['dock_bikes'].max()}, "
              f"media={df_inc['dock_bikes'].mean():.1f}, "
              f"ceros={int((df_inc['dock_bikes'] == 0).sum())}")
        print(f"   free_bases:  min={df_inc['free_bases'].min()}, "
              f"max={df_inc['free_bases'].max()}, "
              f"media={df_inc['free_bases'].mean():.1f}, "
              f"ceros={int((df_inc['free_bases'] == 0).sum())}")
        print(f"   reservas:    min={df_inc['reservations_count'].min()}, "
              f"max={df_inc['reservations_count'].max()}, "
              f"media={df_inc['reservations_count'].mean():.1f}")
        print(f"   total_bases: min={df_inc['total_bases'].min()}, "
              f"max={df_inc['total_bases'].max()}, "
              f"media={df_inc['total_bases'].mean():.1f}")

        # ¿Cuántos tienen dock_bikes=0 Y free_bases=0?
        ambos_cero = ((df_inc["dock_bikes"] == 0) & (df_inc["free_bases"] == 0)).sum()
        print(f"\n   Con dock_bikes=0 Y free_bases=0: {ambos_cero:,} "
              f"({ambos_cero/len(df_inc)*100:.1f}% de inconsistentes)")

        # 5.3 Scatter de dock_bikes vs free_bases coloreando por inconsistencia
        fig, axes = plt.subplots(1, 2, figsize=(14, 6))

        # Consistentes
        ax = axes[0]
        df_cons = df[df["diff"] == 0].sample(n=min(5000, consistentes), random_state=42)
        ax.scatter(df_cons["dock_bikes"], df_cons["free_bases"],
                   alpha=0.1, s=5, color="#abdda4")
        ax.set_title(f"Registros CONSISTENTES (muestra)", pad=10)
        ax.set_xlabel("dock_bikes (bicis ancladas)")
        ax.set_ylabel("free_bases (huecos libres)")

        # Inconsistentes
        ax = axes[1]
        df_inc_sample = df_inc.sample(n=min(5000, len(df_inc)), random_state=42) if len(df_inc) > 5000 else df_inc
        sc = ax.scatter(df_inc_sample["dock_bikes"], df_inc_sample["free_bases"],
                        c=df_inc_sample["diff"], cmap="RdYlBu_r",
                        alpha=0.3, s=10, vmin=-10, vmax=10)
        plt.colorbar(sc, ax=ax, label="Diferencia (suma - total_bases)")
        ax.set_title(f"Registros INCONSISTENTES", pad=10)
        ax.set_xlabel("dock_bikes (bicis ancladas)")
        ax.set_ylabel("free_bases (huecos libres)")

        plt.suptitle("dock_bikes vs free_bases: consistentes vs inconsistentes", y=1.02)
        plt.tight_layout()
        plt.savefig(OUTPUT_DIR / "fig_scatter_bikes_bases.png", bbox_inches="tight")
        plt.close()
        print(f"   -> fig_scatter_bikes_bases.png")

        # 5.4 Ejemplos concretos de registros inconsistentes
        print("\n   Ejemplos de registros inconsistentes (10 primeros):")
        print(f"   {'Timestamp':<22} {'Estación':<25} {'Bicis':>6} {'Libres':>7} "
              f"{'Reserv':>7} {'Total':>6} {'Suma':>6} {'Diff':>6} {'Act':>4} {'NoAv':>5} {'Light':>6}")
        print("   " + "-" * 110)
        ejemplos = df_inc.head(10)
        for _, r in ejemplos.iterrows():
            ts = str(r["timestamp"])[:19] if pd.notna(r["timestamp"]) else "?"
            nombre = str(r["name"])[:23] if r["name"] else "?"
            print(f"   {ts:<22} {nombre:<25} {int(r['dock_bikes']):>6} {int(r['free_bases']):>7} "
                  f"{int(r['reservations_count']):>7} {int(r['total_bases']):>6} "
                  f"{int(r['suma']):>6} {int(r['diff']):>6} {int(r['activate']):>4} "
                  f"{int(r['no_available']):>5} {int(r['light']):>6}")

    # ----- 6. RESUMEN Y CONCLUSIÓN -----
    print("\n" + "=" * 70)
    print("[6/6] RESUMEN Y CONCLUSIONES")
    print("=" * 70)
    print(f"\n   Total registros analizados:          {total:,}")
    print(f"   Registros consistentes:              {consistentes:,} ({100-pct:.2f}%)")
    print(f"   Registros inconsistentes:            {inconsistentes:,} ({pct:.2f}%)")

    if not df_inc.empty:
        # Hipótesis automáticas
        pct_inactivas = (df_inc["activate"] == 0).mean() * 100
        pct_nodisponible = (df_inc["no_available"] == 1).mean() * 100
        pct_ambos_cero = ((df_inc["dock_bikes"] == 0) & (df_inc["free_bases"] == 0)).mean() * 100

        print(f"\n   De los inconsistentes:")
        print(f"     - {pct_inactivas:.1f}% tienen activate=0 (estación inactiva)")
        print(f"     - {pct_nodisponible:.1f}% tienen no_available=1 (no disponible)")
        print(f"     - {pct_ambos_cero:.1f}% tienen dock_bikes=0 y free_bases=0")

        if pct_inactivas > 50 or pct_nodisponible > 50:
            print(f"\n   CONCLUSIÓN PROBABLE: la mayoría de inconsistencias ocurren en")
            print(f"   estaciones inactivas o no disponibles. Es probable que cuando")
            print(f"   una estación se desactiva, los conteos no se actualicen")
            print(f"   correctamente (se ponen a 0 las bicis y huecos pero el total")
            print(f"   se mantiene). Este tipo de inconsistencia NO afecta al análisis")
            print(f"   si se filtran las estaciones inactivas/no disponibles.")
        elif pct_ambos_cero > 50:
            print(f"\n   CONCLUSIÓN PROBABLE: la mayoría de inconsistencias se dan cuando")
            print(f"   dock_bikes=0 y free_bases=0 (estación vacía de datos).")
            print(f"   Es probable que sean momentos de mantenimiento o reinicio del sistema.")
        else:
            print(f"\n   Las inconsistencias no siguen un patrón claro asociado al")
            print(f"   estado de la estación. Requiere investigación adicional.")

    # Exportar registros inconsistentes
    if not df_inc.empty:
        df_inc_export = df_inc[["timestamp", "id_estacion", "name", "dock_bikes",
                                 "free_bases", "reservations_count", "total_bases",
                                 "suma", "diff", "activate", "no_available", "light"]].copy()
        df_inc_export.to_csv(OUTPUT_DIR / "registros_inconsistentes.csv", index=False)
        print(f"\n   -> registros_inconsistentes.csv ({len(df_inc_export):,} registros)")

    print(f"\n   Todos los resultados en: {OUTPUT_DIR.resolve()}")
    print("\n   Figuras generadas:")
    for fig_path in sorted(OUTPUT_DIR.glob("fig_*.png")):
        print(f"   - {fig_path.name}")


if __name__ == "__main__":
    main()