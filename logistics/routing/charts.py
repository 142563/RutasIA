"""Gráficas PNG de los experimentos (opcional: requiere matplotlib, ver requirements-dev.txt).

Paleta categórica validada (fondo blanco, apta para daltonismo):
Dijkstra = azul, A* = naranja, tercer método = aqua. El color sigue a la
entidad: Dijkstra siempre es azul y A* siempre naranja en todas las gráficas.
"""
from __future__ import annotations

import statistics
from collections import defaultdict
from pathlib import Path

from logistics.models import TrafficBand

BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK_SECONDARY, GRID = "#111113", "#6B6F76", "#ECECEA"


def available() -> bool:
    try:
        import matplotlib  # noqa: F401
    except ImportError:
        return False
    return True


def _pyplot():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({
        "figure.dpi": 150, "font.size": 9, "axes.edgecolor": GRID, "axes.labelcolor": INK_SECONDARY,
        "axes.titlecolor": INK, "axes.titlesize": 10, "axes.titleweight": "bold", "axes.titlelocation": "left",
        "xtick.color": INK_SECONDARY, "ytick.color": INK_SECONDARY, "axes.grid": True, "grid.color": GRID,
        "grid.linewidth": 0.8, "axes.axisbelow": True, "axes.spines.top": False, "axes.spines.right": False,
        "legend.frameon": False, "lines.linewidth": 2, "lines.markersize": 6,
    })
    return plt


def _save(fig, path: Path, source: str) -> Path:
    fig.text(0.01, 0.01, f"Fuente de datos: {source}", fontsize=7, color=INK_SECONDARY)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(path)
    fig.clf()
    return path


def e2_chart(rows: list[dict], out: Path) -> Path:
    plt = _pyplot()
    rows = [r for r in rows if r["profile"] == "sin_trafico"] or rows
    bins = defaultdict(lambda: ([], []))
    for r in rows:
        b = int(r["straight_km"] // 50) * 50
        bins[b][0].append(r["dijkstra_expanded"])
        bins[b][1].append(r["astar_expanded"])
    xs = sorted(bins)
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    ax.plot(xs, [statistics.mean(bins[x][0]) for x in xs], marker="o", color=BLUE, label="Dijkstra")
    ax.plot(xs, [statistics.mean(bins[x][1]) for x in xs], marker="s", color=ORANGE, label="A*")
    ax.set_title("E2 · Nodos expandidos según la distancia de la consulta")
    ax.set_xlabel("Distancia en línea recta entre origen y destino (km, grupos de 50)")
    ax.set_ylabel("Nodos expandidos (promedio)")
    ax.set_ylim(bottom=0)
    ax.legend(loc="upper left")
    return _save(fig, out / "e2_nodos_expandidos.png", rows[0]["data_source"])


def e3_chart(rows: list[dict], out: Path) -> Path:
    plt = _pyplot()
    bands = list(TrafficBand.values)
    labels = [TrafficBand(b).label.split(" (")[0] for b in bands]
    fig, ax = plt.subplots(figsize=(6.8, 3.6))
    width = 0.38
    for offset, (day, color, name) in enumerate([("weekday", BLUE, "Laboral"), ("weekend", ORANGE, "Fin de semana")]):
        means = []
        for band in bands:
            values = [r["minutes_saved"] for r in rows if r["band"] == band and r["day_type"] == day]
            means.append(statistics.mean(values) if values else 0)
        xs = [i + (offset - 0.5) * width for i in range(len(bands))]
        ax.bar(xs, means, width=width - 0.04, color=color, label=name)
    ax.grid(axis="x", visible=False)
    ax.set_xticks(range(len(bands)), labels, rotation=20)
    ax.set_title("E3 · Minutos que ahorra la ruta más rápida frente a la más corta")
    ax.set_ylabel("Minutos ahorrados (promedio por par)")
    ax.legend(loc="upper right")
    return _save(fig, out / "e3_ahorro_por_franja.png", rows[0]["data_source"])


def e5_chart(rows: list[dict], out: Path) -> Path:
    plt = _pyplot()
    sizes = sorted({r["stops"] for r in rows})
    series = [("capture_minutes", BLUE, "Orden de captura"), ("nearest_neighbor_minutes", ORANGE, "Vecino más cercano"),
              ("two_opt_minutes", AQUA, "Vecino más cercano + 2-opt")]
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    width = 0.26
    for k, (key, color, name) in enumerate(series):
        means = [statistics.mean(r[key] for r in rows if r["stops"] == s) for s in sizes]
        xs = [i + (k - 1) * width for i in range(len(sizes))]
        bars = ax.bar(xs, means, width=width - 0.03, color=color, label=name)
        ax.bar_label(bars, fmt="%.0f", fontsize=7, color=INK_SECONDARY, padding=2)
    ax.grid(axis="x", visible=False)
    ax.set_xticks(range(len(sizes)), [f"{s} paradas" for s in sizes])
    ax.set_title("E5 · Tiempo total de la ruta según el método de ordenar paradas")
    ax.set_ylabel("Minutos (promedio, pico mañana)")
    ax.legend(loc="upper left")
    return _save(fig, out / "e5_varias_paradas.png", rows[0]["data_source"])


def e7_chart(rows: list[dict], out: Path) -> Path:
    plt = _pyplot()
    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    for graph, style in (("synthetic-grid", "-"), ("synthetic-geometric", "--")):
        subset = [r for r in rows if r["graph"] == graph]
        sizes = sorted({r["nodes"] for r in subset})
        if not sizes:
            continue
        name = "cuadrícula" if graph.endswith("grid") else "geométrico"
        for key, color, marker, algo in (("dijkstra_expanded", BLUE, "o", "Dijkstra"),
                                         ("astar_expanded", ORANGE, "s", "A*")):
            means = [statistics.mean(r[key] for r in subset if r["nodes"] == n) for n in sizes]
            ax.plot(sizes, means, linestyle=style, marker=marker, color=color, label=f"{algo} · {name}")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_title("E7 · Escalabilidad en grafos sintéticos")
    ax.set_xlabel("Nodos del grafo (escala log)")
    ax.set_ylabel("Nodos expandidos, promedio (escala log)")
    ax.legend(loc="upper left", fontsize=8)
    return _save(fig, out / "e7_escalabilidad.png", "grafos sintéticos (docs/PLAN.md §2.10)")


# --- E4 y E6 -------------------------------------------------------------------

PURPLE = "#8a5fd0"
PAIR_COLORS = [BLUE, ORANGE, AQUA, PURPLE]


def _is_test_data(source: str) -> bool:
    return any(k in source for k in ("estimate", "synthetic", "none"))


def _title(text: str, source: str) -> str:
    """Con datos estimados/sintéticos el título advierte que no son resultados de tesis."""
    return f"{text}\n[DATOS DE PRUEBA · NO son resultados de tesis]" if _is_test_data(source) else text


def e6_chart(rows: list[dict], out: Path) -> Path:
    plt = _pyplot()
    bands = list(TrafficBand.values)
    labels = [TrafficBand(b).label.split(" (")[0] for b in bands]
    pairs = list(dict.fromkeys(r["pair"] for r in rows))
    source = rows[0]["data_source"]
    fig, axes = plt.subplots(1, 2, figsize=(9.6, 4.2), sharey=True)
    for ax, (day, name) in zip(axes, [("weekday", "Día laboral"), ("weekend", "Fin de semana")]):
        for k, pair in enumerate(pairs):
            by_band = {r["band"]: r["minutes"] for r in rows if r["pair"] == pair and r["day_type"] == day}
            xs = [i for i, b in enumerate(bands) if b in by_band]
            ax.plot(xs, [by_band[bands[i]] for i in xs], marker="o", color=PAIR_COLORS[k % len(PAIR_COLORS)],
                    label=pair.split(" -> ")[1].replace("-", " ").title())
        ax.set_xticks(range(len(bands)), labels, rotation=30, ha="right")
        ax.set_title(name)
        ax.set_xlabel("Franja de salida")
    axes[0].set_ylabel("Minutos desde Ciudad de Guatemala")
    fig.legend(*axes[0].get_legend_handles_labels(), loc="upper right", ncol=4, fontsize=8)
    fig.suptitle(_title("E6 · Tiempo del mismo viaje según la hora de salida", source), x=0.01, ha="left",
                 fontsize=10, fontweight="bold", color=INK)
    return _save(fig, out / "e6_hora_de_salida.png", source)


def e4_chart(rows: list[dict], out: Path) -> Path:
    plt = _pyplot()
    source = rows[0]["data_source"]
    mape = statistics.mean(r["error_pct"] for r in rows)
    top = max(max(r["engine_min"], r["google_min"]) for r in rows) * 1.05
    fig, ax = plt.subplots(figsize=(5.4, 5.2))
    ax.plot([0, top], [0, top], color=INK_SECONDARY, linestyle="--", linewidth=1, label="Coincidencia exacta")
    ax.scatter([r["google_min"] for r in rows], [r["engine_min"] for r in rows], color=BLUE, s=22,
               alpha=0.85, label=f"Viajes (n = {len(rows)})")
    ax.set_xlim(0, top)
    ax.set_ylim(0, top)
    ax.set_aspect("equal")
    ax.set_xlabel("Minutos según Google Routes API (con tráfico)")
    ax.set_ylabel("Minutos según nuestro motor")
    ax.text(0.04, 0.95, f"MAPE = {mape:.1f} %", transform=ax.transAxes, va="top", fontsize=9, color=INK)
    ax.legend(loc="lower right", fontsize=8)
    ax.set_title(_title("E4 · Estimado del motor vs Google", source), fontsize=9)
    return _save(fig, out / "e4_motor_vs_google.png", source)
