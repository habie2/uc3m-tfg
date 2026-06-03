"""
Carga múltiples meses de viajes BiciMAD en la BBDD llamando a load_trips.py
una vez por fichero.

Edita FILES para dejar solo los meses que quieras. Las líneas comentadas con #
se ignoran. El primer mes (201801) ya está cargado, por eso va comentado.

Uso:
    python load_all.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# Ruta al loader existente. Ajusta si lo ejecutas desde otra carpeta.
LOAD_SCRIPT = "etl/load_trips.py"

# True = el primer fichero hace --truncate (BORRA lo ya cargado).
# Como ya tienes 201801 dentro, dejarlo en False.
TRUNCATE_FIRST = False

# Lista completa de ficheros .json disponibles. Comenta lo que no quieras.
# Los .csv (jul-2021 en adelante) los he dejado todos comentados porque
# load_trips.py espera el formato JSON de Mongo; ver nota al final.
FILES = [
    # ===== 2017 (solo abr-dic) =====
    # r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2017\trips\201704.json",
    # r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2017\trips\201705.json",
    # r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2017\trips\201706.json",
    # r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2017\trips\201707.json",
    # r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2017\trips\201708.json",
    # r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2017\trips\201709.json",
    # r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2017\trips\201710.json",
    # r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2017\trips\201711.json",
    # r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2017\trips\201712.json",

    # ===== 2018 =====
    # r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2018\trips\201801.json",  # ya cargado
    # r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2018\trips\201802.json",
    # r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2018\trips\201803.json",
    # r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2018\trips\201804.json",
    # r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2018\trips\201805.json",
    # r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2018\trips\201806.json",
    # r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2018\trips\201807.json",
    # r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2018\trips\201808.json",
    # r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2018\trips\201809.json",
    # r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2018\trips\201810.json",
    # r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2018\trips\201811.json",
    # r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2018\trips\201812.json",

    # ===== 2019 =====
    # r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2019\trips\201901.json",
    # r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2019\trips\201902.json",
    # r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2019\trips\201903.json",
    # r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2019\trips\201904.json",
    # r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2019\trips\201905.json",
    # r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2019\trips\201906.json",
    # r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2019\trips\201907.json",
    r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2019\trips\201908.json",
    r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2019\trips\201909.json",
    r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2019\trips\201910.json",
    r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2019\trips\201911.json",
    r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2019\trips\201912.json",

    # ===== 2020 =====
    r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2020\trips\202001.json",
    r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2020\trips\202002.json",
    # r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2020\trips\202003.json",
    # r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2020\trips\202004.json",
    r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2020\trips\202005.json",
    # r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2020\trips\202006.json",
    r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2020\trips\202007.json",
    r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2020\trips\202008.json",
    r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2020\trips\202009.json",
    r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2020\trips\202010.json",
    r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2020\trips\202011.json",
    r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2020\trips\202012.json",

    # ===== 2021 (solo ene-jun en .json) =====
    r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2021\trips\202101.json",
    r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2021\trips\202102.json",
    r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2021\trips\202103.json",
    r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2021\trips\202104.json",
    r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2021\trips\202105.json",
    r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2021\trips\202106.json",

    # ===== 2021-2023 (.csv — formato distinto, load_trips.py NO los soporta) =====
    # r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2021\trips\202107.csv",
    # r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2021\trips\202108.csv",
    # r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2021\trips\202109.csv",
    # r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2021\trips\202110.csv",
    # r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2021\trips\202111.csv",
    # r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2021\trips\202112.csv",
    # r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2022\trips\202201.csv",
    # r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2022\trips\202202.csv",
    # r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2022\trips\202203.csv",
    # r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2022\trips\202204.csv",
    # r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2022\trips\202205.csv",
    # r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2022\trips\202206.csv",
    # r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2022\trips\202207.csv",
    # r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2022\trips\202208.csv",
    # r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2022\trips\202209.csv",
    # r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2022\trips\202210.csv",
    # r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2022\trips\202211.csv",
    # r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2022\trips\202212.csv",
    # r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2023\trips\202301.csv",
    # r"C:\Users\ajolote-casa-w\Downloads\bicimad_data\bicimad_2023\trips\202302.csv",
]


def main():
    if not FILES:
        print("La lista FILES está vacía.")
        sys.exit(1)

    n = len(FILES)
    for i, path in enumerate(FILES, start=1):
        if not Path(path).exists():
            print(f"  AVISO: no existe {path}, saltando")
            continue

        args = [sys.executable, LOAD_SCRIPT, "--input", path]
        if i == 1 and TRUNCATE_FIRST:
            args.append("--truncate")

        print(f"\n=== [{i}/{n}] {Path(path).name} ===")
        result = subprocess.run(args)
        if result.returncode != 0:
            print(f"\nERROR cargando {path}. Abortando.")
            sys.exit(1)

    print("\n¡Carga de todos los meses completada!")
    print("Siguientes pasos:")
    print("  python etl/compute_routes.py --workers 8")
    print("  python etl/decompose_routes.py --refresh")


if __name__ == "__main__":
    main()
