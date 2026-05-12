"""
02_catalogo_estaciones.py

Extrae el catálogo único de estaciones BiciMad recorriendo los snapshots y
generando un dataset tabular con las estaciones y sus atributos. Aplica
fg-data-profiling sobre el catálogo y genera gráficos adicionales.

Uso:
    python 02_catalogo_estaciones.py
"""
import json
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from collections import defaultdict

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
OUTPUT_DIR = Path("output/catalogo")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Estilo
sns.set_theme(style="whitegrid", context="paper")
plt.rcParams['figure.dpi'] = 300
plt.rcParams['savefig.dpi'] = 300
plt.rcParams['font.size'] = 10

ENCODINGS = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]

# Umbrales de comparación para considerar dos valores "el mismo"
UMBRAL_SIMILITUD_TEXTO = 100  # 100% de similitud
UMBRAL_DISTANCIA_COORDS_M = 0  # 0 metros de tolerancia

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


# ---------- NORMALIZACIÓN PARA COMPARAR ----------
def normalizar_texto(texto):
    """
    Normaliza un texto para comparación robusta:
    - Sustituye caracteres de reemplazo (�, ?) por nada
    - Quita acentos y diacríticos
    - Pasa a minúsculas
    - Colapsa espacios múltiples
    Devuelve None si la entrada es None.
    """
    if texto is None:
        return None
    s = str(texto)
    # Eliminar caracteres de reemplazo Unicode (los que aparecen como �)
    s = s.replace("\ufffd", "").replace("?", "")
    # Normalizar acentos: descomponer y quedarse solo con ASCII
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    # Pasar a minúsculas y limpiar espacios
    s = s.lower().strip()
    s = re.sub(r"\s+", " ", s)
    return s


def texto_sin_reemplazos(texto):
    """Versión del texto sin los caracteres de reemplazo, para comparar longitudes."""
    if texto is None:
        return ""
    return str(texto).replace("\ufffd", "").replace("?", "")


def textos_son_equivalentes(a, b, umbral=UMBRAL_SIMILITUD_TEXTO):
    """
    Comprueba si dos textos son razonablemente equivalentes.
    Aplica varias heurísticas:
    1. Igualdad estricta -> equivalentes
    2. Tras normalizar (quitar caracteres raros, acentos, mayúsculas) -> iguales
    3. Si uno tenía caracteres de reemplazo y al quitarlos cabe dentro del otro -> equivalentes
    4. Si la similitud supera el umbral -> equivalentes
    """
    if a == b:
        return True
    if a is None or b is None:
        return False

    # Normalizamos ambos
    na = normalizar_texto(a)
    nb = normalizar_texto(b)
    if na == nb:
        return True
    if not na or not nb:
        return False

    # Si uno de los originales tenía caracteres de reemplazo (�),
    # comparamos las longitudes esperadas. Si difieren solo en los caracteres
    # ausentes, casi seguro son el mismo texto corrupto.
    a_str = str(a)
    b_str = str(b)
    a_tenia_reemplazos = "\ufffd" in a_str or "?" in a_str
    b_tenia_reemplazos = "\ufffd" in b_str or "?" in b_str

    if a_tenia_reemplazos or b_tenia_reemplazos:
        # Si la versión "limpia" del corrupto cabe en el otro, los consideramos iguales
        a_limpio = normalizar_texto(texto_sin_reemplazos(a))
        b_limpio = normalizar_texto(texto_sin_reemplazos(b))
        if a_limpio and b_limpio:
            # ¿Uno está contenido en el otro tras normalizar?
            if a_limpio in nb or b_limpio in na:
                return True
            # ¿Tienen la misma longitud aproximada y similitud razonable?
            if abs(len(na) - len(nb)) <= 3:  # diferencia pequeña en longitud
                similitud = SequenceMatcher(None, na, nb).ratio()
                if similitud >= 0.75:  # umbral más laxo si hubo corrupción
                    return True

    # Comparación estándar por similitud
    return SequenceMatcher(None, na, nb).ratio() >= umbral


def coordenadas_a_metros(lat1, lon1, lat2, lon2):
    """
    Calcula la distancia aproximada entre dos coordenadas en metros usando
    la fórmula de Haversine simplificada. Suficiente para distinguir
    cambios reales de cambios de precisión.
    """
    try:
        lat1, lon1 = float(lat1), float(lon1)
        lat2, lon2 = float(lat2), float(lon2)
    except (TypeError, ValueError):
        return float("inf")
    R = 6_371_000  # radio de la Tierra en metros
    phi1 = np.radians(lat1)
    phi2 = np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlambda = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2)**2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlambda / 2)**2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
    return R * c


def coordenadas_son_equivalentes(coord_a, coord_b, umbral_m=UMBRAL_DISTANCIA_COORDS_M):
    """Comprueba si dos pares de coordenadas representan el mismo punto."""
    if coord_a == coord_b:
        return True
    if coord_a is None or coord_b is None:
        return False
    lat1, lon1 = coord_a
    lat2, lon2 = coord_b
    if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
        return False
    distancia = coordenadas_a_metros(lat1, lon1, lat2, lon2)
    return distancia <= umbral_m


def valores_son_equivalentes(a, b, tipo):
    """Dispatcher: aplica la comparación adecuada según el tipo de campo."""
    if tipo in ("nombre", "direccion"):
        return textos_son_equivalentes(a, b)
    if tipo == "coordenadas":
        return coordenadas_son_equivalentes(a, b)
    # Capacidad y otros campos: comparación estricta
    return a == b


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


def listar_archivos(data_dir: Path):
    archivos = []
    for year_dir in sorted(data_dir.glob("bicimad_*")):
        stations_dir = year_dir / "stations"
        if stations_dir.exists():
            for f in sorted(stations_dir.glob("*.json")):
                archivos.append(f)
    return archivos


def cargar_primer_snapshot(path: Path):
    """Devuelve solo el primer snapshot de un archivo, soportando varios formatos."""
    try:
        content = leer_archivo_robusto(path)
        content = normalizar_mongo_json(content)
        content_strip = content.lstrip()

        if content_strip.startswith("["):
            data = json.loads(content)
            return data[0] if data else None
        elif content_strip.startswith("{"):
            # Probar NDJSON
            primera_linea = content_strip.splitlines()[0]
            if primera_linea.endswith("}"):
                try:
                    return json.loads(primera_linea)
                except json.JSONDecodeError:
                    pass
            # Probar como objetos concatenados pretty-printed
            decoder = json.JSONDecoder()
            pos = 0
            while pos < len(content):
                while pos < len(content) and content[pos] in " \t\r\n":
                    pos += 1
                if pos >= len(content):
                    break
                try:
                    obj, _ = decoder.raw_decode(content, pos)
                    return obj
                except json.JSONDecodeError:
                    break
        return None
    except Exception as e:
        print(f"  Error leyendo {path.name}: {e}")
        return None


def extraer_catalogo(archivos):
    """
    Recorre los archivos y construye un catálogo de estaciones donde, para cada
    estación, guardamos sus atributos junto con la primera y última fecha en
    que la hemos visto. Además, registra todas las variantes observadas de
    nombre, dirección, capacidad y coordenadas con su timestamp para poder
    analizar los cambios a lo largo del tiempo.
    """
    catalogo = defaultdict(lambda: {
        "id": None, "name": None, "address": None, "number": None,
        "latitude": None, "longitude": None, "total_bases": None,
        "primer_visto": None, "ultimo_visto": None,
        "veces_vista": 0,
        # Lista de (timestamp, valor) para poder reconstruir el orden temporal
        "nombres_historico": [],
        "direcciones_historico": [],
        "capacidades_historico": [],
        "coordenadas_historico": [],
    })

    for path in tqdm(archivos):
        snap = cargar_primer_snapshot(path)
        if not snap:
            continue
        ts = snap.get("_id")
        for st in snap.get("stations", []):
            sid = st.get("id")
            if sid is None:
                continue
            entry = catalogo[sid]
            entry["id"] = sid
            entry["name"] = st.get("name")
            entry["address"] = st.get("address")
            entry["number"] = st.get("number")
            entry["latitude"] = st.get("latitude")
            entry["longitude"] = st.get("longitude")
            entry["total_bases"] = st.get("total_bases")
            entry["veces_vista"] += 1
            if ts:
                if entry["primer_visto"] is None or ts < entry["primer_visto"]:
                    entry["primer_visto"] = ts
                if entry["ultimo_visto"] is None or ts > entry["ultimo_visto"]:
                    entry["ultimo_visto"] = ts
            entry["nombres_historico"].append((ts, st.get("name")))
            entry["direcciones_historico"].append((ts, st.get("address")))
            entry["capacidades_historico"].append((ts, st.get("total_bases")))
            entry["coordenadas_historico"].append(
                (ts, (st.get("latitude"), st.get("longitude")))
            )

    return catalogo


def detectar_cambios(historico, tipo):
    """
    Dado un histórico [(timestamp, valor), ...] y el tipo de campo, detecta los
    cambios reales (cuando el valor cambia respecto al anterior aplicando una
    comparación tolerante según el tipo). Devuelve transiciones (timestamp,
    valor_anterior, valor_nuevo).
    """
    if not historico:
        return []
    historico_ordenado = sorted([h for h in historico if h[0]], key=lambda x: x[0])
    cambios = []
    valor_actual = None
    for i, (ts, valor) in enumerate(historico_ordenado):
        if i == 0:
            valor_actual = valor
            continue
        if not valores_son_equivalentes(valor, valor_actual, tipo):
            cambios.append((ts, valor_actual, valor))
            valor_actual = valor
    return cambios


def contar_valores_unicos_inteligente(historico, tipo):
    """
    Cuenta cuántos valores realmente distintos hay en un histórico,
    aplicando la comparación tolerante. Por ejemplo, "Malasaña" y "Malasa�a"
    se cuentan como un único valor.
    """
    valores_canonicos = []
    for _, valor in historico:
        ya_visto = False
        for canonico in valores_canonicos:
            if valores_son_equivalentes(valor, canonico, tipo):
                ya_visto = True
                break
        if not ya_visto:
            valores_canonicos.append(valor)
    return len(valores_canonicos)


def construir_dataframe_catalogo(catalogo):
    """A partir del catálogo en bruto, construye el DataFrame resumen."""
    rows = []
    for entry in catalogo.values():
        rows.append({
            "id": entry["id"],
            "number": entry["number"],
            "name": entry["name"],
            "address": entry["address"],
            "latitude": entry["latitude"],
            "longitude": entry["longitude"],
            "total_bases": entry["total_bases"],
            "primer_visto": entry["primer_visto"],
            "ultimo_visto": entry["ultimo_visto"],
            "veces_vista": entry["veces_vista"],
            "nombres_distintos": contar_valores_unicos_inteligente(
                entry["nombres_historico"], "nombre"
            ),
            "direcciones_distintas": contar_valores_unicos_inteligente(
                entry["direcciones_historico"], "direccion"
            ),
            "capacidades_distintas": contar_valores_unicos_inteligente(
                entry["capacidades_historico"], "capacidad"
            ),
            "coordenadas_distintas": contar_valores_unicos_inteligente(
                entry["coordenadas_historico"], "coordenadas"
            ),
        })
    return pd.DataFrame(rows)


def construir_dataframe_cambios(catalogo):
    """
    Construye un DataFrame detallado con TODOS los cambios reales observados,
    aplicando comparación tolerante según el tipo de campo.
    """
    filas = []
    tipos = [
        ("nombre", "nombres_historico"),
        ("direccion", "direcciones_historico"),
        ("capacidad", "capacidades_historico"),
        ("coordenadas", "coordenadas_historico"),
    ]
    for entry in catalogo.values():
        sid = entry["id"]
        nombre_actual = entry["name"]
        for tipo, campo in tipos:
            cambios = detectar_cambios(entry[campo], tipo)
            for ts, antes, despues in cambios:
                fila = {
                    "id_estacion": sid,
                    "nombre_referencia": nombre_actual,
                    "tipo_cambio": tipo,
                    "timestamp_cambio": ts,
                    "valor_anterior": str(antes),
                    "valor_nuevo": str(despues),
                }
                # Para coordenadas añadimos la distancia en metros
                if tipo == "coordenadas" and antes and despues:
                    try:
                        d = coordenadas_a_metros(antes[0], antes[1], despues[0], despues[1])
                        fila["distancia_m"] = round(d, 2)
                    except Exception:
                        fila["distancia_m"] = None
                filas.append(fila)
    return pd.DataFrame(filas)


# ---------- ANÁLISIS PRINCIPAL ----------
def main():
    print("=" * 70)
    print("EXTRACCIÓN Y ANÁLISIS DEL CATÁLOGO DE ESTACIONES")
    print("=" * 70)

    archivos = listar_archivos(DATA_DIR)

    # ----- 1a. ESTRUCTURA DEL JSON ORIGINAL -----
    print(f"\n[1/5] Analizando estructura de los datos originales...")

    # Leer un snapshot representativo para mostrar la estructura
    snap_ejemplo = None
    archivo_ejemplo = None
    for a in archivos:
        snap_ejemplo = cargar_primer_snapshot(a)
        if snap_ejemplo and snap_ejemplo.get("stations"):
            archivo_ejemplo = a
            break

    if snap_ejemplo:
        print(f"\n   Archivo de referencia: {archivo_ejemplo.name}")
        print(f"\n   ESTRUCTURA DE UN SNAPSHOT:")
        print(f"   ┌─ _id (timestamp del snapshot)")
        print(f"   │    Ejemplo: \"{snap_ejemplo.get('_id')}\"")
        print(f"   │    Tipo: string (formato ISO 8601)")
        print(f"   │")
        print(f"   └─ stations (array de estaciones)")
        print(f"        Ejemplo de primer snapshot: {len(snap_ejemplo.get('stations', []))} estaciones")

        # Analizar la primera estación para mostrar cada campo
        estacion_ejemplo = snap_ejemplo["stations"][0]
        print(f"\n   ESTRUCTURA DE CADA ESTACIÓN:")
        print(f"   {'Campo':<25} {'Tipo':<15} {'Ejemplo'}")
        print(f"   " + "-" * 75)

        # Clasificar campos por función para documentar mejor
        campos_info = []
        for campo, valor in estacion_ejemplo.items():
            tipo_python = type(valor).__name__
            # Determinar tipo semántico
            if isinstance(valor, int):
                tipo_sem = "entero"
            elif isinstance(valor, float):
                tipo_sem = "decimal"
            elif isinstance(valor, str):
                # Detectar si es numérico guardado como string
                try:
                    float(valor)
                    tipo_sem = "string (numérico)"
                except (ValueError, TypeError):
                    tipo_sem = "string"
            else:
                tipo_sem = tipo_python

            ejemplo_str = str(valor)
            if len(ejemplo_str) > 35:
                ejemplo_str = ejemplo_str[:32] + "..."

            campos_info.append({
                "campo": campo,
                "tipo": tipo_sem,
                "ejemplo": ejemplo_str,
                "valor_raw": valor,
            })
            print(f"   {campo:<25} {tipo_sem:<15} {ejemplo_str}")

        # Exportar estructura como CSV
        df_estructura = pd.DataFrame([{
            "Campo": c["campo"],
            "Tipo en JSON": c["tipo"],
            "Ejemplo": c["ejemplo"],
        } for c in campos_info])
        df_estructura.to_csv(OUTPUT_DIR / "estructura_json_estacion.csv", index=False)
        print(f"\n   -> estructura_json_estacion.csv")

        # Analizar valores de campos clave sobre varias estaciones
        print(f"\n   ANÁLISIS DE VALORES POR CAMPO:")
        estaciones = snap_ejemplo["stations"]

        # activate: ¿qué valores posibles?
        vals_activate = set(st.get("activate") for st in estaciones)
        print(f"   activate:             valores únicos = {sorted(vals_activate)}")

        # no_available
        vals_noavail = set(st.get("no_available") for st in estaciones)
        print(f"   no_available:         valores únicos = {sorted(vals_noavail)}")

        # light
        vals_light = set(st.get("light") for st in estaciones)
        print(f"   light:                valores únicos = {sorted(vals_light)}")

        # total_bases
        vals_bases = [st.get("total_bases") for st in estaciones if st.get("total_bases") is not None]
        if vals_bases:
            print(f"   total_bases:          min={min(vals_bases)}, max={max(vals_bases)}, "
                  f"media={sum(vals_bases)/len(vals_bases):.1f}")

        # dock_bikes
        vals_bikes = [st.get("dock_bikes") for st in estaciones if st.get("dock_bikes") is not None]
        if vals_bikes:
            print(f"   dock_bikes:           min={min(vals_bikes)}, max={max(vals_bikes)}, "
                  f"media={sum(vals_bikes)/len(vals_bikes):.1f}")

        # free_bases
        vals_free = [st.get("free_bases") for st in estaciones if st.get("free_bases") is not None]
        if vals_free:
            print(f"   free_bases:           min={min(vals_free)}, max={max(vals_free)}, "
                  f"media={sum(vals_free)/len(vals_free):.1f}")

        # reservations_count
        vals_res = [st.get("reservations_count") for st in estaciones if st.get("reservations_count") is not None]
        if vals_res:
            print(f"   reservations_count:   min={min(vals_res)}, max={max(vals_res)}, "
                  f"media={sum(vals_res)/len(vals_res):.1f}")

        # Comprobar tipos de lat/lon (¿string o numérico?)
        lat0 = estaciones[0].get("latitude")
        lon0 = estaciones[0].get("longitude")
        print(f"\n   NOTA: latitude y longitude se almacenan como {type(lat0).__name__}")
        print(f"         Ejemplo: lat=\"{lat0}\", lon=\"{lon0}\"")
        if isinstance(lat0, str):
            print(f"         ⚠ Son strings, habrá que convertirlos a float en la limpieza")

    else:
        print("   No se pudo leer ningún archivo para analizar la estructura.")

    # ----- 1b. EXTRACCIÓN DEL CATÁLOGO -----
    print(f"\n   Recorriendo {len(archivos)} archivos para extraer catálogo...")
    catalogo = extraer_catalogo(archivos)
    df = construir_dataframe_catalogo(catalogo)

    if df.empty:
        print("ERROR: no se pudo extraer ninguna estación.")
        return

    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    df["total_bases"] = pd.to_numeric(df["total_bases"], errors="coerce")

    df.to_csv(OUTPUT_DIR / "catalogo_estaciones.csv", index=False)
    print(f"   -> {OUTPUT_DIR / 'catalogo_estaciones.csv'} ({len(df)} estaciones)")

    # Construir DataFrame detallado con todos los cambios observados
    df_cambios = construir_dataframe_cambios(catalogo)
    df_cambios.to_csv(OUTPUT_DIR / "cambios_estaciones.csv", index=False)
    print(f"   -> {OUTPUT_DIR / 'cambios_estaciones.csv'} ({len(df_cambios)} cambios)")

    # ----- 2. RESUMEN EXPLORATORIO DEL CATÁLOGO -----
    print("\n[2/5] Generando resumen exploratorio del catálogo...")

    # 2.1 Tabla resumen de columnas (tipo, nulos, únicos, ejemplo)
    resumen_cols = []
    for col in df.columns:
        resumen_cols.append({
            "Columna": col,
            "Tipo": str(df[col].dtype),
            "No nulos": df[col].notna().sum(),
            "Nulos": df[col].isna().sum(),
            "% Nulos": round(df[col].isna().mean() * 100, 1),
            "Únicos": df[col].nunique(),
            "Ejemplo": str(df[col].dropna().iloc[0]) if df[col].notna().any() else "—",
        })
    df_resumen = pd.DataFrame(resumen_cols)
    df_resumen.to_csv(OUTPUT_DIR / "resumen_columnas.csv", index=False)
    print(f"   -> resumen_columnas.csv")

    # Imprimir tabla por consola
    print("\n   Estructura del catálogo de estaciones:")
    print(f"   {'Columna':<25} {'Tipo':<12} {'No nulos':>8} {'Nulos':>6} {'%':>6} {'Únicos':>7}")
    print("   " + "-" * 70)
    for _, r in df_resumen.iterrows():
        print(f"   {r['Columna']:<25} {r['Tipo']:<12} {r['No nulos']:>8} {r['Nulos']:>6} "
              f"{r['% Nulos']:>5.1f}% {r['Únicos']:>7}")

    # 2.2 Estadísticas descriptivas de las columnas numéricas
    cols_num = ["total_bases", "latitude", "longitude", "veces_vista",
                "nombres_distintos", "direcciones_distintas",
                "capacidades_distintas", "coordenadas_distintas"]
    cols_presentes = [c for c in cols_num if c in df.columns]
    if cols_presentes:
        df_desc = df[cols_presentes].describe().round(4)
        df_desc.to_csv(OUTPUT_DIR / "estadisticas_descriptivas.csv")
        print(f"\n   -> estadisticas_descriptivas.csv")

        # Gráfico: boxplots de las variables numéricas principales
        fig, axes = plt.subplots(1, 3, figsize=(14, 5))
        for ax, col, titulo in zip(axes,
                                    ["total_bases", "veces_vista", "coordenadas_distintas"],
                                    ["Capacidad (bases)", "Veces vista en el dataset",
                                     "Coordenadas distintas"]):
            if col in df.columns:
                sns.boxplot(y=df[col].dropna(), ax=ax,
                           color=sns.color_palette("YlGnBu", n_colors=3)[1])
                ax.set_title(titulo, pad=10)
                ax.set_ylabel("")
        plt.suptitle("Distribuciones de variables numéricas del catálogo", y=1.02)
        plt.tight_layout()
        plt.savefig(OUTPUT_DIR / "fig_boxplots_catalogo.png", bbox_inches="tight")
        plt.close()
        print(f"   -> fig_boxplots_catalogo.png")

    # 2.3 Tabla de valores únicos por campo categórico
    print("\n   Cardinalidad de campos categóricos:")
    for col in ["name", "address", "number"]:
        if col in df.columns:
            n = df[col].nunique()
            print(f"      {col}: {n} valores únicos")

    # ----- 3. GRÁFICOS GENERALES DEL CATÁLOGO -----
    print("\n[3/5] Generando gráficos del catálogo para la memoria...")

    # 3.1 Distribución de capacidad
    fig, ax = plt.subplots(figsize=(8, 5))
    sns.histplot(df["total_bases"].dropna(), bins=20, kde=True,
                 color=sns.color_palette("YlGnBu", n_colors=3)[1], ax=ax)
    ax.set_title("Distribución de capacidad de las estaciones (total de bases)", pad=15)
    ax.set_xlabel("Número de bases por estación")
    ax.set_ylabel("Número de estaciones")
    capacidad_media = df["total_bases"].mean()
    ax.axvline(capacidad_media, color="red", linestyle="--",
               label=f"Media: {capacidad_media:.1f}")
    ax.legend()
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "fig_distribucion_capacidad.png", bbox_inches="tight")
    plt.close()
    print(f"   -> fig_distribucion_capacidad.png")

    # 3.2 Mapa de estaciones
    df_geo = df.dropna(subset=["latitude", "longitude"])
    if not df_geo.empty:
        fig, ax = plt.subplots(figsize=(8, 8))
        sc = ax.scatter(df_geo["longitude"], df_geo["latitude"],
                        c=df_geo["total_bases"], cmap="YlGnBu",
                        s=40, alpha=0.8, edgecolors="white", linewidth=0.5)
        plt.colorbar(sc, ax=ax, label="Capacidad (bases)")
        ax.set_title("Distribución geográfica de las estaciones de BiciMad", pad=15)
        ax.set_xlabel("Longitud")
        ax.set_ylabel("Latitud")
        ax.set_aspect("equal", adjustable="datalim")
        plt.tight_layout()
        plt.savefig(OUTPUT_DIR / "fig_mapa_estaciones.png", bbox_inches="tight")
        plt.close()
        print(f"   -> fig_mapa_estaciones.png")

    # 3.3 Inconsistencias
    cols_inc = ["nombres_distintos", "direcciones_distintas",
                "capacidades_distintas", "coordenadas_distintas"]
    df_inc = df[cols_inc].apply(lambda c: (c > 1).sum())
    fig, ax = plt.subplots(figsize=(8, 4))
    df_inc.plot(kind="barh", ax=ax,
                color=sns.color_palette("YlGnBu", n_colors=4))
    ax.set_title("Estaciones con valores inconsistentes a lo largo del tiempo", pad=15)
    ax.set_xlabel("Número de estaciones afectadas")
    ax.set_yticklabels([
        "Cambios de nombre", "Cambios de dirección",
        "Cambios de capacidad", "Cambios de coordenadas",
    ])
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "fig_inconsistencias.png", bbox_inches="tight")
    plt.close()
    print(f"   -> fig_inconsistencias.png")

    # 3.4 Línea temporal de incorporación
    df["primer_visto_dt"] = pd.to_datetime(df["primer_visto"], errors="coerce")
    df_incorp = df.dropna(subset=["primer_visto_dt"]).copy()
    if not df_incorp.empty:
        df_incorp["mes_incorporacion"] = df_incorp["primer_visto_dt"].dt.to_period("M")
        incorporaciones = df_incorp.groupby("mes_incorporacion").size().cumsum()
        fig, ax = plt.subplots(figsize=(10, 4))
        incorporaciones.plot(ax=ax, marker="o",
                             color=sns.color_palette("YlGnBu", n_colors=3)[2])
        ax.set_title("Crecimiento del sistema BiciMad: estaciones acumuladas por mes", pad=15)
        ax.set_xlabel("Mes")
        ax.set_ylabel("Número total de estaciones")
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(OUTPUT_DIR / "fig_crecimiento_estaciones.png", bbox_inches="tight")
        plt.close()
        print(f"   -> fig_crecimiento_estaciones.png")

    # 3.5 Top estaciones
    df_top = df.nlargest(15, "total_bases")[["name", "total_bases"]]
    fig, ax = plt.subplots(figsize=(8, 6))
    sns.barplot(data=df_top, y="name", x="total_bases",
                hue="name", palette="YlGnBu", legend=False, ax=ax)
    ax.set_title("Top 15 estaciones con mayor capacidad", pad=15)
    ax.set_xlabel("Capacidad (bases)")
    ax.set_ylabel("")
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "fig_top_estaciones.png", bbox_inches="tight")
    plt.close()
    print(f"   -> fig_top_estaciones.png")

    # ----- 4. ANÁLISIS DETALLADO DE CAMBIOS -----
    print("\n[4/5] Analizando cambios observados en las estaciones...")

    if df_cambios.empty:
        print("   No se han detectado cambios.")
    else:
        # 4.1 Distribución del número de cambios por tipo
        cambios_por_tipo = df_cambios["tipo_cambio"].value_counts()
        fig, ax = plt.subplots(figsize=(8, 4))
        cambios_por_tipo.plot(kind="bar", ax=ax,
                              color=sns.color_palette("YlGnBu", n_colors=len(cambios_por_tipo)))
        ax.set_title("Total de cambios observados por tipo", pad=15)
        ax.set_xlabel("Tipo de cambio")
        ax.set_ylabel("Número de cambios")
        plt.xticks(rotation=0)
        for i, v in enumerate(cambios_por_tipo.values):
            ax.text(i, v + max(cambios_por_tipo) * 0.01, str(v),
                    ha="center", fontsize=9)
        plt.tight_layout()
        plt.savefig(OUTPUT_DIR / "fig_cambios_por_tipo.png", bbox_inches="tight")
        plt.close()
        print(f"   -> fig_cambios_por_tipo.png")

        # 4.2 Cambios a lo largo del tiempo
        df_cambios["timestamp_cambio_dt"] = pd.to_datetime(
            df_cambios["timestamp_cambio"], errors="coerce"
        )
        df_cambios_t = df_cambios.dropna(subset=["timestamp_cambio_dt"]).copy()
        if not df_cambios_t.empty:
            df_cambios_t["mes"] = df_cambios_t["timestamp_cambio_dt"].dt.to_period("M")
            cambios_por_mes_tipo = df_cambios_t.groupby(["mes", "tipo_cambio"]) \
                                               .size().unstack(fill_value=0)
            fig, ax = plt.subplots(figsize=(12, 5))
            cambios_por_mes_tipo.plot(kind="bar", stacked=True, ax=ax,
                                       colormap="YlGnBu")
            ax.set_title("Cambios observados a lo largo del tiempo", pad=15)
            ax.set_xlabel("Mes")
            ax.set_ylabel("Número de cambios")
            ax.legend(title="Tipo")
            plt.xticks(rotation=90, fontsize=7)
            plt.tight_layout()
            plt.savefig(OUTPUT_DIR / "fig_cambios_temporal.png", bbox_inches="tight")
            plt.close()
            print(f"   -> fig_cambios_temporal.png")

        # 4.3 Top estaciones con más cambios totales
        cambios_por_estacion = df_cambios.groupby(
            ["id_estacion", "nombre_referencia"]
        ).size().reset_index(name="num_cambios").sort_values(
            "num_cambios", ascending=False
        ).head(15)

        fig, ax = plt.subplots(figsize=(10, 6))
        # Etiquetas combinando nombre + id para distinguir estaciones repetidas
        labels = cambios_por_estacion.apply(
            lambda r: f"{r['nombre_referencia']} (#{r['id_estacion']})", axis=1
        )
        ax.barh(range(len(cambios_por_estacion)),
                cambios_por_estacion["num_cambios"],
                color=sns.color_palette("YlGnBu", n_colors=len(cambios_por_estacion)))
        ax.set_yticks(range(len(cambios_por_estacion)))
        ax.set_yticklabels(labels)
        ax.invert_yaxis()
        ax.set_title("Top 15 estaciones con mayor número de cambios", pad=15)
        ax.set_xlabel("Número de cambios totales")
        plt.tight_layout()
        plt.savefig(OUTPUT_DIR / "fig_top_estaciones_cambios.png", bbox_inches="tight")
        plt.close()
        print(f"   -> fig_top_estaciones_cambios.png")

        # 4.4 Heatmap de tipo de cambio x estación (solo top 20 estaciones)
        cambios_pivot = df_cambios.groupby(
            ["nombre_referencia", "tipo_cambio"]
        ).size().unstack(fill_value=0)
        # Ordenar por total y quedarnos con las 20 más afectadas
        cambios_pivot["_total"] = cambios_pivot.sum(axis=1)
        cambios_pivot = cambios_pivot.sort_values("_total", ascending=False).head(20)
        cambios_pivot = cambios_pivot.drop(columns=["_total"])

        fig, ax = plt.subplots(figsize=(9, 8))
        sns.heatmap(cambios_pivot, annot=True, fmt="d", cmap="YlGnBu",
                    linewidths=0.5, linecolor="white", ax=ax,
                    cbar_kws={"label": "Número de cambios"})
        ax.set_title("Tipos de cambio en las 20 estaciones más afectadas", pad=15)
        ax.set_xlabel("Tipo de cambio")
        ax.set_ylabel("")
        plt.tight_layout()
        plt.savefig(OUTPUT_DIR / "fig_heatmap_cambios.png", bbox_inches="tight")
        plt.close()
        print(f"   -> fig_heatmap_cambios.png")

        # 4.5 Imprimir TODOS los cambios detectados
        print("\n   =============================================")
        print("   LISTADO COMPLETO DE CAMBIOS DETECTADOS")
        print("   =============================================")
        for tipo in ["coordenadas", "nombre", "direccion", "capacidad"]:
            cambios_tipo = df_cambios[df_cambios["tipo_cambio"] == tipo]
            if cambios_tipo.empty:
                continue
            print(f"\n   >>> {tipo.upper()} ({len(cambios_tipo)} cambios)")
            print("   " + "-" * 60)
            for _, row in cambios_tipo.iterrows():
                ts = row["timestamp_cambio"][:10] if row["timestamp_cambio"] else "?"
                nombre = row["nombre_referencia"]
                sid = row["id_estacion"]
                antes = row["valor_anterior"]
                despues = row["valor_nuevo"]
                extra = ""
                if tipo == "coordenadas" and "distancia_m" in row and pd.notna(row.get("distancia_m")):
                    extra = f" ({row['distancia_m']:.1f}m)"
                print(f"      [{ts}] {nombre} (#{sid}):")
                print(f"          '{antes}' -> '{despues}'{extra}")

        # 4.6 Exportar cambios de coordenadas y capacidad a CSVs separados
        for tipo in ["coordenadas", "nombre", "direccion", "capacidad"]:
            cambios_tipo = df_cambios[df_cambios["tipo_cambio"] == tipo]
            if not cambios_tipo.empty:
                filename = f"cambios_{tipo}.csv"
                cambios_tipo.to_csv(OUTPUT_DIR / filename, index=False)
                print(f"\n   -> {filename} ({len(cambios_tipo)} registros)")
    # ----- 5. RESUMEN -----
    print("\n[5/5] Resumen del análisis del catálogo:")
    print("=" * 70)
    print(f"Total de estaciones únicas:           {len(df)}")
    print(f"Capacidad total del sistema:          {df['total_bases'].sum():.0f} bases")
    print(f"Capacidad media por estación:         {df['total_bases'].mean():.1f} bases")
    print(f"Capacidad mínima:                     {df['total_bases'].min():.0f} bases")
    print(f"Capacidad máxima:                     {df['total_bases'].max():.0f} bases")
    print(f"Estaciones con coordenadas inválidas: {df['latitude'].isna().sum()}")
    print(f"Estaciones con cambios de nombre:     {(df['nombres_distintos'] > 1).sum()}")
    print(f"Estaciones con cambios de dirección:  {(df['direcciones_distintas'] > 1).sum()}")
    print(f"Estaciones con cambios de capacidad:  {(df['capacidades_distintas'] > 1).sum()}")
    print(f"Estaciones con cambios de coordenadas:{(df['coordenadas_distintas'] > 1).sum()}")
    if not df_cambios.empty:
        print(f"\nTotal de cambios detectados:          {len(df_cambios)}")
        print(f"   - Cambios de nombre:               {(df_cambios['tipo_cambio'] == 'nombre').sum()}")
        print(f"   - Cambios de dirección:            {(df_cambios['tipo_cambio'] == 'direccion').sum()}")
        print(f"   - Cambios de capacidad:            {(df_cambios['tipo_cambio'] == 'capacidad').sum()}")
        print(f"   - Cambios de coordenadas:          {(df_cambios['tipo_cambio'] == 'coordenadas').sum()}")

    print(f"\nResultados en: {OUTPUT_DIR.resolve()}")
    print("\nFiguras generadas:")
    for fig_path in sorted(OUTPUT_DIR.glob("fig_*.png")):
        print(f"   - {fig_path.name}")


if __name__ == "__main__":
    main()