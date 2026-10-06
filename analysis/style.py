"""Shared chart style (reference palette from the dataviz guidance; one axis, thin marks, recessive grid)."""
import matplotlib.pyplot as plt

SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_2 = "#52514e"
GRID = "#e4e3df"
BLUE, ORANGE, AQUA, YELLOW, MAGENTA, GREEN, VIOLET, RED = (
    "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948")
NEUTRAL = "#a3a29c"
BAND = "#cde2fb"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "figure.dpi": 110, "savefig.dpi": 200, "savefig.bbox": "tight",
    "font.family": "sans-serif", "font.size": 10,
    "axes.edgecolor": GRID, "axes.labelcolor": TEXT_2, "axes.titlecolor": TEXT,
    "axes.titlesize": 12, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "axes.grid.axis": "y", "grid.color": GRID, "grid.linewidth": 0.8,
    "xtick.color": TEXT_2, "ytick.color": TEXT_2,
    "lines.linewidth": 2, "legend.frameon": False, "legend.labelcolor": TEXT_2,
})


def subtitle(ax, text):
    """Grey one-line subtitle above a chart."""
    ax.text(0, 1.02, text, transform=ax.transAxes, color=TEXT_2, fontsize=9, va="bottom")


def source(fig, text="Source: workspace.xplore_gold (synthetic data)", y=-0.02):
    """Source line at the bottom of a figure."""
    fig.text(0.01, y, text, color=TEXT_2, fontsize=7.5)
