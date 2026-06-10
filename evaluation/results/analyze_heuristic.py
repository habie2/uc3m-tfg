"""
Analizador de evaluaciones heurísticas.

Lee todos los archivos .xlsx de un directorio (esperando la estructura de
Evaluacion_Heuristica_*.xlsx con hoja 'Problemas') y genera:
  - Distribución de severidad (donut)
  - Problemas por heurística apilados por severidad (barras horizontales)
  - Mapa de calor evaluadores × heurísticas (severidad media)
  - Problemas por indicador apilados por severidad
  - CSV consolidado de todos los problemas

Uso:
    python analyze_heuristic.py <directorio> [-o <salida>]

Ejemplo:
    python analyze_heuristic.py ./evaluation/results/1hueristicas -o ./output_heuristic
"""

import argparse
import sys
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np


# ----------------------------------------------------------------------
# Configuración visual
# ----------------------------------------------------------------------
SEVERITY_COLORS = {
    0: '#B4B2A9',  # No es un problema
    1: '#85B7EB',  # Cosmético
    2: '#EF9F27',  # Menor
    3: '#D85A30',  # Mayor
    4: '#E24B4A',  # Catastrófico
}

SEVERITY_LABELS = {
    0: 'No es problema',
    1: 'Cosmético',
    2: 'Menor',
    3: 'Mayor',
    4: 'Catastrófico',
}

plt.rcParams.update({
    'font.family': 'DejaVu Sans',
    'axes.spines.top': False,
    'axes.spines.right': False,
    'axes.titlesize': 13,
    'axes.titleweight': 'medium',
})


# ----------------------------------------------------------------------
# Carga de datos
# ----------------------------------------------------------------------
def load_data(directory: Path) -> pd.DataFrame:
    """Lee todos los .xlsx del directorio y concatena la hoja 'Problemas'."""
    files = sorted(directory.glob('*.xlsx'))
    if not files:
        print(f"ERROR: no se han encontrado archivos .xlsx en {directory}")
        sys.exit(1)

    print(f"Encontrados {len(files)} archivos en {directory}:")
    dfs = []
    for f in files:
        try:
            df = pd.read_excel(f, sheet_name='Problemas')
            print(f"  ✓ {f.name} ({len(df)} problemas)")
            dfs.append(df)
        except Exception as e:
            print(f"  ✗ {f.name}: {e}")

    if not dfs:
        print("ERROR: no se ha podido leer ningún archivo.")
        sys.exit(1)

    return pd.concat(dfs, ignore_index=True)


# ----------------------------------------------------------------------
# Gráficos
# ----------------------------------------------------------------------
def plot_severity_donut(df: pd.DataFrame, output_dir: Path) -> None:
    """Donut con la distribución de severidad."""
    counts = df['Severidad'].value_counts().sort_index()
    labels = [f'{SEVERITY_LABELS[s]} ({c})' for s, c in counts.items()]
    colors = [SEVERITY_COLORS[s] for s in counts.index]

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.pie(counts, labels=labels, colors=colors, autopct='%1.0f%%',
           startangle=90, wedgeprops=dict(width=0.42, edgecolor='white'),
           pctdistance=0.78)
    ax.set_title(f'Distribución por severidad (n={len(df)} problemas)')

    out = output_dir / 'severidad_distribucion.png'
    plt.tight_layout()
    plt.savefig(out, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  ✓ {out.name}")


def plot_heuristic_stacked(df: pd.DataFrame, output_dir: Path) -> None:
    """Barras horizontales apiladas: problemas por heurística × severidad."""
    pivot = df.pivot_table(index='Codigo_Heuristica', columns='Severidad',
                           values='ID_Problema', aggfunc='count', fill_value=0)
    for sev in [0, 1, 2, 3, 4]:
        if sev not in pivot.columns:
            pivot[sev] = 0
    pivot = pivot[[0, 1, 2, 3, 4]]
    # Ordenar por total de problemas (descendente)
    pivot = pivot.loc[pivot.sum(axis=1).sort_values(ascending=True).index]

    # Mapear códigos a nombres si están disponibles
    nombres = df.drop_duplicates('Codigo_Heuristica').set_index(
        'Codigo_Heuristica')['Nombre_Heuristica'].to_dict()
    y_labels = [f'{c} — {nombres.get(c, "")[:40]}' for c in pivot.index]

    fig, ax = plt.subplots(figsize=(11, max(4, len(pivot) * 0.5)))
    left = np.zeros(len(pivot))
    for sev in [0, 1, 2, 3, 4]:
        if pivot[sev].sum() == 0:
            continue
        ax.barh(range(len(pivot)), pivot[sev], left=left,
                color=SEVERITY_COLORS[sev],
                label=f'{sev}: {SEVERITY_LABELS[sev]}',
                edgecolor='white', linewidth=0.5)
        left += pivot[sev]

    ax.set_yticks(range(len(pivot)))
    ax.set_yticklabels(y_labels, fontsize=10)
    ax.set_xlabel('Número de problemas')
    ax.set_title('Problemas por heurística y severidad')
    ax.legend(loc='lower right', fontsize=9, framealpha=0.9)

    out = output_dir / 'heuristicas_severidad.png'
    plt.tight_layout()
    plt.savefig(out, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  ✓ {out.name}")


def plot_heatmap(df: pd.DataFrame, output_dir: Path) -> None:
    """Mapa de calor: evaluador × heurística con severidad media."""
    pivot = df.pivot_table(index='Evaluador', columns='Codigo_Heuristica',
                           values='Severidad', aggfunc='mean')
    # Conteo para anotar también
    count = df.pivot_table(index='Evaluador', columns='Codigo_Heuristica',
                           values='ID_Problema', aggfunc='count')

    fig, ax = plt.subplots(figsize=(max(8, len(pivot.columns) * 0.7),
                                    max(3, len(pivot) * 0.6)))
    im = ax.imshow(pivot.values, cmap='YlOrRd', aspect='auto', vmin=0, vmax=4)

    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=45, ha='right')
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index)

    for i in range(len(pivot.index)):
        for j in range(len(pivot.columns)):
            val = pivot.values[i, j]
            n = count.values[i, j] if not pd.isna(count.values[i, j]) else 0
            if not np.isnan(val):
                color = 'white' if val > 2.3 else '#2C2C2A'
                ax.text(j, i, f'{val:.1f}\n(n={int(n)})', ha='center',
                        va='center', color=color, fontsize=8)

    ax.set_title('Severidad media por evaluador y heurística')
    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label('Severidad media (0–4)')

    out = output_dir / 'heatmap_evaluadores.png'
    plt.tight_layout()
    plt.savefig(out, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  ✓ {out.name}")


def plot_by_indicator(df: pd.DataFrame, output_dir: Path) -> None:
    """Barras apiladas verticales: problemas por indicador × severidad."""
    pivot = df.pivot_table(index='Indicador', columns='Severidad',
                           values='ID_Problema', aggfunc='count', fill_value=0)
    for sev in [0, 1, 2, 3, 4]:
        if sev not in pivot.columns:
            pivot[sev] = 0
    pivot = pivot[[0, 1, 2, 3, 4]].sort_index()

    fig, ax = plt.subplots(figsize=(8, 5))
    bottom = np.zeros(len(pivot))
    for sev in [0, 1, 2, 3, 4]:
        if pivot[sev].sum() == 0:
            continue
        ax.bar(pivot.index, pivot[sev], bottom=bottom,
               color=SEVERITY_COLORS[sev],
               label=f'{sev}: {SEVERITY_LABELS[sev]}',
               edgecolor='white', linewidth=0.5)
        bottom += pivot[sev]

    # Etiquetas de total encima de cada barra
    totals = pivot.sum(axis=1)
    for i, t in enumerate(totals):
        ax.text(i, t + 0.3, str(int(t)), ha='center', fontsize=10,
                fontweight='medium')

    ax.set_ylabel('Número de problemas')
    ax.set_title('Problemas por indicador y severidad')
    ax.legend(fontsize=9, loc='upper right')

    out = output_dir / 'indicadores_severidad.png'
    plt.tight_layout()
    plt.savefig(out, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  ✓ {out.name}")


def plot_heuristic_type(df: pd.DataFrame, output_dir: Path) -> None:
    """Comparativa Nielsen vs Mapas con severidad media."""
    if 'Tipo_Heuristica' not in df.columns:
        return
    grouped = df.groupby('Tipo_Heuristica').agg(
        conteo=('ID_Problema', 'count'),
        sev_media=('Severidad', 'mean'),
        sev_max=('Severidad', 'max'),
    )

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5))

    # Conteo
    colors = ['#7F77DD', '#5DCAA5', '#EF9F27']
    ax1.bar(grouped.index, grouped['conteo'],
            color=colors[:len(grouped)], edgecolor='white')
    for i, v in enumerate(grouped['conteo']):
        ax1.text(i, v + 0.3, str(int(v)), ha='center', fontweight='medium')
    ax1.set_title('Conteo por tipo de heurística')
    ax1.set_ylabel('Número de problemas')

    # Severidad media
    ax2.bar(grouped.index, grouped['sev_media'],
            color=colors[:len(grouped)], edgecolor='white')
    for i, v in enumerate(grouped['sev_media']):
        ax2.text(i, v + 0.05, f'{v:.2f}', ha='center', fontweight='medium')
    ax2.set_title('Severidad media por tipo')
    ax2.set_ylabel('Severidad media (0–4)')
    ax2.set_ylim(0, 4)

    out = output_dir / 'tipo_heuristica.png'
    plt.tight_layout()
    plt.savefig(out, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  ✓ {out.name}")


# ----------------------------------------------------------------------
# Resumen por consola
# ----------------------------------------------------------------------
def print_summary(df: pd.DataFrame) -> None:
    print("\n" + "=" * 60)
    print("  RESUMEN DE LA EVALUACIÓN HEURÍSTICA")
    print("=" * 60)
    print(f"  Total de problemas: {len(df)}")
    print(f"  Evaluadores: {df['Evaluador'].nunique()}"
          f" ({', '.join(map(str, df['Evaluador'].unique()))})")
    print(f"  Heurísticas con problemas: {df['Codigo_Heuristica'].nunique()}")
    print(f"  Severidad media: {df['Severidad'].mean():.2f}")
    print(f"  Severidad máxima: {df['Severidad'].max()}")
    print(f"  Problemas críticos (sev=4): {(df['Severidad'] == 4).sum()}")
    print(f"  Problemas mayores (sev≥3):  {(df['Severidad'] >= 3).sum()}")

    print("\n  Distribución de severidad:")
    for sev in sorted(df['Severidad'].unique()):
        count = (df['Severidad'] == sev).sum()
        pct = 100 * count / len(df)
        bar = '█' * int(pct / 2)
        print(f"    {sev} {SEVERITY_LABELS[sev]:<15} {count:>3} ({pct:>4.1f}%) {bar}")
    print()


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description='Analiza evaluaciones heurísticas de un directorio.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='Ejemplo:\n  python analyze_heuristic.py ./results/1hueristicas -o ./out',
    )
    parser.add_argument('directory', type=Path,
                        help='Directorio con los archivos Evaluacion_Heuristica_*.xlsx')
    parser.add_argument('-o', '--output', type=Path, default=Path('output_heuristic'),
                        help='Directorio de salida (por defecto: output_heuristic)')
    args = parser.parse_args()

    if not args.directory.is_dir():
        print(f"ERROR: '{args.directory}' no es un directorio válido.")
        sys.exit(1)

    args.output.mkdir(parents=True, exist_ok=True)

    df = load_data(args.directory)
    print_summary(df)

    print("Generando gráficos:")
    plot_severity_donut(df, args.output)
    plot_heuristic_stacked(df, args.output)
    plot_heatmap(df, args.output)
    plot_by_indicator(df, args.output)
    plot_heuristic_type(df, args.output)

    csv_out = args.output / 'datos_consolidados.csv'
    df.to_csv(csv_out, index=False)
    print(f"\n✓ Datos consolidados: {csv_out}")
    print(f"✓ Salida en: {args.output.resolve()}")


if __name__ == '__main__':
    main()
