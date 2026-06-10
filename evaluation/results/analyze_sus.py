"""
Analizador de cuestionarios SUS (System Usability Scale).

Lee todos los archivos .xlsx de un directorio (esperando la estructura de
Cuestionario_SUS_*.xlsx con hoja 'Respuesta') y genera:
  - Puntuación SUS por participante con línea de referencia en 68
  - Distribución Likert por ítem (barras horizontales apiladas)
  - SUS medio por perfil (si hay varios perfiles)
  - Distribución global de la puntuación SUS
  - CSV consolidado de todas las respuestas

Uso:
    python analyze_sus.py <directorio> [-o <salida>]

Ejemplo:
    python analyze_sus.py ./evaluation/results/3sus -o ./output_sus
"""

import argparse
import sys
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np


# ----------------------------------------------------------------------
# Configuración
# ----------------------------------------------------------------------
SUS_REFERENCE = 68          # Umbral aceptable según la literatura
SUS_MEAN = 68               # Media global de referencia
ITEM_COLS = [f'Item_{i:02d}' for i in range(1, 11)]

LIKERT_COLORS = {
    1: '#E24B4A',   # Muy en desacuerdo
    2: '#F09595',
    3: '#B4B2A9',
    4: '#97C459',
    5: '#639922',   # Muy de acuerdo
}

# Texto resumido de cada ítem SUS (corregido para mostrar de forma legible)
ITEMS_TEXT = [
    'Me gustaría usarlo con frecuencia',
    'Es innecesariamente complejo',
    'Es fácil de usar',
    'Necesitaría apoyo técnico',
    'Funciones bien integradas',
    'Hay demasiada inconsistencia',
    'La gente aprendería rápido',
    'Es muy complicado',
    'Me sentí seguro al usarlo',
    'Necesité aprender mucho',
]

# Grados SUS según referencia (Bangor, Kortum & Miller)
def grade_sus(score: float) -> str:
    if score >= 84.1:
        return 'A+ Excepcional'
    if score >= 80.8:
        return 'A Excelente'
    if score >= 74.1:
        return 'B Bueno'
    if score >= 65.0:
        return 'C Promedio'
    if score >= 51.7:
        return 'D Mediocre'
    return 'F Pobre'


plt.rcParams.update({
    'font.family': 'DejaVu Sans',
    'axes.spines.top': False,
    'axes.spines.right': False,
    'axes.titlesize': 13,
    'axes.titleweight': 'medium',
})


# ----------------------------------------------------------------------
# Carga
# ----------------------------------------------------------------------
def load_data(directory: Path) -> pd.DataFrame:
    files = sorted(directory.glob('*.xlsx'))
    if not files:
        print(f"ERROR: no se han encontrado archivos .xlsx en {directory}")
        sys.exit(1)

    print(f"Encontrados {len(files)} archivos en {directory}:")
    rows = []
    for f in files:
        try:
            df = pd.read_excel(f, sheet_name='Respuesta')
            print(f"  ✓ {f.name} ({len(df)} respuestas)")
            rows.append(df)
        except Exception as e:
            print(f"  ✗ {f.name}: {e}")

    if not rows:
        print("ERROR: no se ha podido leer ningún archivo.")
        sys.exit(1)

    return pd.concat(rows, ignore_index=True)


# ----------------------------------------------------------------------
# Gráficos
# ----------------------------------------------------------------------
def plot_sus_scores(df: pd.DataFrame, output_dir: Path) -> None:
    """Barras: SUS por participante, con línea de referencia y media."""
    df_sorted = df.sort_values('Puntuacion_SUS', ascending=False).reset_index(drop=True)

    fig, ax = plt.subplots(figsize=(max(8, len(df_sorted) * 0.9), 6))
    colors = ['#378ADD' if s >= SUS_REFERENCE else '#E24B4A'
              for s in df_sorted['Puntuacion_SUS']]
    bars = ax.bar(df_sorted['Participante'], df_sorted['Puntuacion_SUS'],
                  color=colors, edgecolor='white', linewidth=0.8)

    for bar, val in zip(bars, df_sorted['Puntuacion_SUS']):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1.5,
                f'{val:.0f}', ha='center', fontsize=10, fontweight='medium')

    ax.axhline(SUS_REFERENCE, color='#E24B4A', linestyle='--', linewidth=1.5,
               label=f'Referencia ({SUS_REFERENCE})')
    mean = df['Puntuacion_SUS'].mean()
    ax.axhline(mean, color='#0F6E56', linestyle=':', linewidth=1.5,
               label=f'Media muestra ({mean:.1f})')

    ax.set_ylim(0, 105)
    ax.set_ylabel('Puntuación SUS (0–100)')
    ax.set_title(f'Puntuación SUS por participante (n={len(df)})')
    ax.legend(loc='upper right', framealpha=0.9)
    plt.xticks(rotation=30, ha='right')

    out = output_dir / 'sus_scores.png'
    plt.tight_layout()
    plt.savefig(out, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  ✓ {out.name}")


def plot_likert(df: pd.DataFrame, output_dir: Path) -> None:
    """Barras horizontales apiladas: respuestas Likert por ítem."""
    counts = np.zeros((10, 5), dtype=int)
    for i, col in enumerate(ITEM_COLS):
        for val in [1, 2, 3, 4, 5]:
            counts[i, val - 1] = int((df[col] == val).sum())

    fig, ax = plt.subplots(figsize=(12, 7))
    y_pos = np.arange(10)
    left = np.zeros(10)
    for j, val in enumerate([1, 2, 3, 4, 5]):
        ax.barh(y_pos, counts[:, j], left=left, color=LIKERT_COLORS[val],
                label=str(val), edgecolor='white', linewidth=0.5)
        for i, c in enumerate(counts[:, j]):
            if c > 0:
                ax.text(left[i] + c / 2, i, int(c), ha='center', va='center',
                        fontsize=9, color='white' if val in (1, 5) else '#2C2C2A')
        left += counts[:, j]

    ax.set_yticks(y_pos)
    ax.set_yticklabels([f'SUS {i+1}. {ITEMS_TEXT[i]}' for i in range(10)],
                       fontsize=10)
    ax.set_xlabel('Número de respuestas')
    ax.set_title('Distribución de respuestas Likert por ítem SUS')
    ax.legend(title='Respuesta', loc='lower right', fontsize=9,
              ncol=5, framealpha=0.9)
    ax.invert_yaxis()

    out = output_dir / 'sus_likert.png'
    plt.tight_layout()
    plt.savefig(out, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  ✓ {out.name}")


def plot_by_profile(df: pd.DataFrame, output_dir: Path) -> None:
    """SUS medio por perfil con barra de error (std)."""
    if 'Perfil' not in df.columns or df['Perfil'].nunique() < 2:
        return

    grouped = df.groupby('Perfil')['Puntuacion_SUS'].agg(['mean', 'std', 'count'])
    grouped = grouped.sort_values('mean', ascending=False)

    fig, ax = plt.subplots(figsize=(max(8, len(grouped) * 2), 5.5))
    palette = ['#7F77DD', '#5DCAA5', '#EF9F27', '#378ADD', '#D85A30']
    colors = palette[:len(grouped)]

    bars = ax.bar(grouped.index, grouped['mean'],
                  yerr=grouped['std'].fillna(0),
                  color=colors, capsize=8, edgecolor='white',
                  linewidth=0.8, error_kw={'linewidth': 1.5, 'ecolor': '#2C2C2A'})

    for i, (_, row) in enumerate(grouped.iterrows()):
        ax.text(i, row['mean'] + (row['std'] or 0) + 2,
                f"{row['mean']:.1f}\n(n={int(row['count'])})",
                ha='center', fontsize=10, fontweight='medium')

    ax.axhline(SUS_REFERENCE, color='#E24B4A', linestyle='--', linewidth=1.5,
               label=f'Referencia ({SUS_REFERENCE})')
    ax.set_ylabel('Puntuación SUS media')
    ax.set_title('Puntuación SUS media por perfil de usuario')
    ax.set_ylim(0, 105)
    ax.legend()
    plt.xticks(rotation=15, ha='right')

    out = output_dir / 'sus_por_perfil.png'
    plt.tight_layout()
    plt.savefig(out, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  ✓ {out.name}")


def plot_item_means(df: pd.DataFrame, output_dir: Path) -> None:
    """Puntuación media convertida (0–4) por ítem para detectar puntos débiles."""
    converted = pd.DataFrame()
    for i, col in enumerate(ITEM_COLS, start=1):
        if i % 2 == 1:           # ítems positivos
            converted[col] = df[col] - 1
        else:                    # ítems negativos
            converted[col] = 5 - df[col]
    means = converted.mean()

    fig, ax = plt.subplots(figsize=(11, 5))
    # Color en función de la puntuación (verde alto, rojo bajo)
    colors = ['#639922' if v >= 3 else '#EF9F27' if v >= 2 else '#E24B4A'
              for v in means]
    bars = ax.bar(range(1, 11), means, color=colors, edgecolor='white',
                  linewidth=0.8)
    for i, v in enumerate(means):
        ax.text(i + 1, v + 0.08, f'{v:.2f}', ha='center', fontsize=10)

    ax.set_xticks(range(1, 11))
    ax.set_xticklabels([f'{i}.\n{ITEMS_TEXT[i-1][:20]}' for i in range(1, 11)],
                       fontsize=8)
    ax.set_ylim(0, 4.4)
    ax.set_ylabel('Puntuación convertida media (0–4)')
    ax.set_title('Puntuación media por ítem SUS (mayor = mejor)')
    ax.axhline(2, color='#2C2C2A', linestyle=':', linewidth=0.8, alpha=0.5)

    out = output_dir / 'sus_items_media.png'
    plt.tight_layout()
    plt.savefig(out, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  ✓ {out.name}")


def plot_sus_distribution(df: pd.DataFrame, output_dir: Path) -> None:
    """Histograma + boxplot de la puntuación SUS."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5),
                                   gridspec_kw={'width_ratios': [2, 1]})

    ax1.hist(df['Puntuacion_SUS'], bins=10, range=(0, 100),
             color='#378ADD', edgecolor='white')
    ax1.axvline(SUS_REFERENCE, color='#E24B4A', linestyle='--',
                linewidth=1.5, label=f'Referencia ({SUS_REFERENCE})')
    ax1.axvline(df['Puntuacion_SUS'].mean(), color='#0F6E56',
                linestyle=':', linewidth=1.5,
                label=f'Media ({df["Puntuacion_SUS"].mean():.1f})')
    ax1.set_xlabel('Puntuación SUS')
    ax1.set_ylabel('Número de participantes')
    ax1.set_title('Distribución de la puntuación SUS')
    ax1.legend()
    ax1.set_xlim(0, 100)

    bp = ax2.boxplot(df['Puntuacion_SUS'], vert=True, widths=0.5,
                     patch_artist=True,
                     boxprops=dict(facecolor='#85B7EB', edgecolor='#185FA5'),
                     medianprops=dict(color='#185FA5', linewidth=2))
    ax2.scatter([1] * len(df), df['Puntuacion_SUS'],
                color='#0C447C', alpha=0.6, zorder=3, s=40)
    ax2.axhline(SUS_REFERENCE, color='#E24B4A', linestyle='--', linewidth=1.5)
    ax2.set_ylim(0, 100)
    ax2.set_xticks([])
    ax2.set_title('Boxplot')

    out = output_dir / 'sus_distribucion.png'
    plt.tight_layout()
    plt.savefig(out, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  ✓ {out.name}")


# ----------------------------------------------------------------------
# Resumen
# ----------------------------------------------------------------------
def print_summary(df: pd.DataFrame) -> None:
    mean = df['Puntuacion_SUS'].mean()
    print("\n" + "=" * 60)
    print("  RESUMEN DEL CUESTIONARIO SUS")
    print("=" * 60)
    print(f"  Participantes: {len(df)}")
    if 'Perfil' in df.columns:
        for p, c in df['Perfil'].value_counts().items():
            print(f"    - {p}: {c}")
    print(f"\n  Puntuación SUS:")
    print(f"    Media:     {mean:.1f}  ({grade_sus(mean)})")
    print(f"    Mediana:   {df['Puntuacion_SUS'].median():.1f}")
    print(f"    Min/Max:   {df['Puntuacion_SUS'].min():.0f} / {df['Puntuacion_SUS'].max():.0f}")
    print(f"    Desv.est.: {df['Puntuacion_SUS'].std():.1f}")
    above = (df['Puntuacion_SUS'] >= SUS_REFERENCE).sum()
    print(f"    Por encima del umbral (≥{SUS_REFERENCE}): "
          f"{above}/{len(df)} ({100*above/len(df):.0f}%)")
    print()


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description='Analiza cuestionarios SUS de un directorio.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='Ejemplo:\n  python analyze_sus.py ./results/3sus -o ./out',
    )
    parser.add_argument('directory', type=Path,
                        help='Directorio con los archivos Cuestionario_SUS_*.xlsx')
    parser.add_argument('-o', '--output', type=Path, default=Path('output_sus'),
                        help='Directorio de salida (por defecto: output_sus)')
    args = parser.parse_args()

    if not args.directory.is_dir():
        print(f"ERROR: '{args.directory}' no es un directorio válido.")
        sys.exit(1)

    args.output.mkdir(parents=True, exist_ok=True)

    df = load_data(args.directory)
    print_summary(df)

    print("Generando gráficos:")
    plot_sus_scores(df, args.output)
    plot_likert(df, args.output)
    plot_by_profile(df, args.output)
    plot_item_means(df, args.output)
    plot_sus_distribution(df, args.output)

    csv_out = args.output / 'datos_consolidados.csv'
    df.to_csv(csv_out, index=False)
    print(f"\n✓ Datos consolidados: {csv_out}")
    print(f"✓ Salida en: {args.output.resolve()}")


if __name__ == '__main__':
    main()
