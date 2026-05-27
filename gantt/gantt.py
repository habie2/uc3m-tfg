"""
Diagrama de Gantt interactivo con Plotly - Cronograma del proyecto 2026
Versión "bonita" con bandas por fase, paleta cuidada y barras redondeadas.
"""

from pathlib import Path
from datetime import datetime, timedelta
import plotly.graph_objects as go

OUT_DIR = Path(__file__).parent

# ---------- DATOS ----------
# (nombre, inicio, fin, fase)
# Las fases agrupan visualmente las tareas y definen el color
tasks = [
    ("Gestión de proyecto",                              "2026-01-19", "2026-05-22", "gestion"),
    ("Investigación trabajos previos",                   "2026-02-09", "2026-03-20", "investigacion"),
    ("Desarrollo",                                       "2026-03-23", "2026-05-28", "desarrollo"),
    ("    Recopilar datos",                              "2026-03-23", "2026-04-08", "desarrollo_sub"),
    ("    Limpieza datos",                               "2026-04-06", "2026-04-22", "desarrollo_sub"),
    ("    Procesamiento de los datos",                   "2026-04-20", "2026-05-15", "desarrollo_sub"),
    ("    Análisis de los resultados",                   "2026-05-04", "2026-05-15", "desarrollo_sub"),
    ("    Desarrollo de la herramienta de visualización","2026-05-04", "2026-05-28", "desarrollo_sub"),
    ("Documentación memoria",                            "2026-02-09", "2026-06-05", "documentacion"),
]

# Paleta cuidada — cada fase tiene su propio color, las subtareas comparten color con su fase pero más claro
PALETTE = {
    "gestion":         {"main": "#5B6CFF", "light": "#EEF0FF", "name": "Gestión"},
    "investigacion":   {"main": "#00B5A5", "light": "#E0F7F4", "name": "Investigación"},
    "desarrollo":      {"main": "#2E5EAA", "light": "#E8EFFA", "name": "Desarrollo"},
    "desarrollo_sub":  {"main": "#7FB3F0", "light": "#E8EFFA", "name": "Desarrollo"},
    "documentacion":   {"main": "#E07B39", "light": "#FCEFE3", "name": "Documentación"},
}

COLOR_TEXT      = "#1F2937"
COLOR_TEXT_SOFT = "#6B7280"
COLOR_BG        = "#FFFFFF"
COLOR_GRID      = "#EEF1F5"

# Plotly dibuja categóricos de abajo hacia arriba: invertimos
tasks_draw = list(reversed(tasks))

fig = go.Figure()

# ---------- 1) BANDAS DE COLOR POR FASE (fondo) ----------
# Pintamos una banda horizontal tenue detrás de cada fila para reforzar la agrupación
for i, (name, start, end, phase) in enumerate(tasks_draw):
    fig.add_shape(
        type="rect",
        xref="paper", yref="y",
        x0=0, x1=1,
        y0=i - 0.5, y1=i + 0.5,
        fillcolor=PALETTE[phase]["light"],
        line=dict(width=0),
        layer="below",
        opacity=0.55,
    )

# ---------- 2) BARRAS DE TAREAS ----------
legend_seen = set()

for i, (name, start, end, phase) in enumerate(tasks_draw):
    color    = PALETTE[phase]["main"]
    legend   = PALETTE[phase]["name"]
    is_sub   = phase.endswith("_sub")

    start_dt = datetime.strptime(start, "%Y-%m-%d")
    end_dt   = datetime.strptime(end,   "%Y-%m-%d")
    duration = (end_dt - start_dt).days

    show_legend = legend not in legend_seen
    legend_seen.add(legend)

    # Barra principal
    fig.add_trace(go.Bar(
        x=[duration * 86400000],
        y=[name],
        base=start_dt,
        orientation="h",
        marker=dict(
            color=color,
            line=dict(width=0),
        ),
        width=0.50 if not is_sub else 0.36,
        name=legend,
        legendgroup=legend,
        showlegend=show_legend,
        text=f"{duration}d",
        textposition="inside",
        insidetextanchor="middle",
        textfont=dict(color="white", size=10, family="Inter, Segoe UI, Arial"),
        hovertemplate=(
            f"<b>{name.strip()}</b><br>"
            f"<span style='color:#9CA3AF'>━━━━━━━━━━━</span><br>"
            f"📅 Inicio: <b>{start_dt.strftime('%d %b %Y')}</b><br>"
            f"🏁 Fin: <b>{end_dt.strftime('%d %b %Y')}</b><br>"
            f"⏱ Duración: <b>{duration} días</b><br>"
            f"📂 Fase: <b>{legend}</b>"
            "<extra></extra>"
        ),
    ))

# ---------- 3) LÍNEA "HOY" ----------
today = datetime(2026, 5, 28)
fig.add_shape(
    type="line",
    x0=today, x1=today, y0=-0.5, y1=len(tasks_draw) - 0.5,
    xref="x", yref="y",
    line=dict(color="#E55934", width=2, dash="dash"),
    layer="above",
)
fig.add_annotation(
    x=today, y=len(tasks_draw) - 0.5,
    xref="x", yref="y",
    text="<b>📍 Hoy</b>",
    showarrow=False,
    font=dict(color="#E55934", size=11),
    xanchor="left", yanchor="bottom",
    xshift=4, yshift=6,
    bgcolor="rgba(255,255,255,0.92)",
    borderpad=4,
    bordercolor="#E55934",
    borderwidth=1,
)

# ---------- 4) HITOS DE INICIO / FIN DEL PROYECTO ----------
project_start = datetime(2026, 1, 19)
project_end   = datetime(2026, 6, 5)

fig.add_annotation(
    x=project_start, y=1.06, xref="x", yref="paper",
    text=f"<b>Inicio</b><br><span style='font-size:10px;color:#6B7280'>{project_start.strftime('%d %b')}</span>",
    showarrow=False, font=dict(size=11, color=COLOR_TEXT), align="center",
)
fig.add_annotation(
    x=project_end, y=1.06, xref="x", yref="paper",
    text=f"<b>Entrega</b><br><span style='font-size:10px;color:#6B7280'>{project_end.strftime('%d %b')}</span>",
    showarrow=False, font=dict(size=11, color=COLOR_TEXT), align="center",
)

# ---------- 5) LAYOUT GENERAL ----------
fig.update_layout(
    title=dict(
        text=(
            "<span style='font-size:24px;color:#111827'><b>Cronograma del proyecto</b></span>"
            "<span style='font-size:24px;color:#9CA3AF'>  ·  2026</span>"
            "<br><span style='font-size:13px;color:#6B7280'>"
            "Planificación de tareas · vista interactiva</span>"
        ),
        x=0.02, xanchor="left", y=0.96,
    ),
    barmode="overlay",
    bargap=0.18,
    plot_bgcolor=COLOR_BG,
    paper_bgcolor=COLOR_BG,
    height=640,
    width=1320,
    margin=dict(l=320, r=50, t=140, b=80),
    font=dict(family="Inter, Segoe UI, system-ui, Arial", size=12, color=COLOR_TEXT),
    legend=dict(
        orientation="h",
        yanchor="bottom", y=-0.16,
        xanchor="center", x=0.5,
        bgcolor="rgba(0,0,0,0)",
        font=dict(size=11),
        itemsizing="constant",
    ),
    hoverlabel=dict(
        bgcolor="white",
        bordercolor="#E5E7EB",
        font=dict(family="Inter, Segoe UI, Arial", size=12, color=COLOR_TEXT),
    ),
    xaxis=dict(
        type="date",
        range=["2026-01-01", "2026-06-30"],
        tickformat="%b",
        dtick="M1",
        tickfont=dict(size=12, color=COLOR_TEXT, family="Inter, Segoe UI, Arial"),
        showgrid=True,
        gridcolor=COLOR_GRID,
        gridwidth=1,
        showline=True,
        linecolor="#E5E7EB",
        linewidth=1,
        ticks="outside",
        ticklen=6,
        tickcolor="#E5E7EB",
        zeroline=False,
    ),
    yaxis=dict(
        showgrid=False,
        showline=False,
        ticks="",
        tickfont=dict(size=11, color=COLOR_TEXT),
        automargin=True,
        zeroline=False,
    ),
)

# Footer discreto
fig.add_annotation(
    x=1.0, y=-0.22, xref="paper", yref="paper",
    text="<i>Generado con Plotly · pasa el cursor por las barras para más detalle</i>",
    showarrow=False,
    font=dict(size=10, color=COLOR_TEXT_SOFT),
    xanchor="right",
)

# ---------- 6) EXPORTAR ----------
html_path = OUT_DIR / "cronograma_proyecto.html"
fig.write_html(
    html_path,
    include_plotlyjs="cdn",
    config={"displaylogo": False, "modeBarButtonsToRemove": ["lasso2d", "select2d"]},
)
print(f"HTML guardado: {html_path}")

try:
    png_path = OUT_DIR / "cronograma_proyecto_plotly.png"
    fig.write_image(png_path, scale=2)
    print(f"PNG guardado:  {png_path}")
except Exception as e:
    print("\n(Para exportar PNG estático instala kaleido:  pip install 'kaleido==0.2.1')")
    print(f"Detalle: {e}")