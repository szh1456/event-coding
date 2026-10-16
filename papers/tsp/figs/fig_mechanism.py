"""Fig. 1 schematic (drawn by the director, no data):

  python3 papers/tsp/figs/fig_mechanism.py

Pictorial version, pictorial version: an edge sweeps a row of pixels; each pixel has its own threshold
ladder. No data; drawn from the model with n = 3 levels per passage and no jitter."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import FancyArrowPatch, Rectangle

plt.rcParams.update({"font.family": "serif", "font.size": 8, "axes.linewidth": 0.6, "pdf.fonttype": 42,
                     "mathtext.fontset": "cm"})
OUT = str(__import__("pathlib").Path(__file__).resolve().parent / "fig_mechanism")
CT, CM = "#1f4fa8", "#e07b00"                 # true events, moved events
GRAD = LinearSegmentedColormap.from_list("g", ["#5a5a5a", "#f4f1e6"])
M, n, tau = 6, 3, 1.0                          # pixels, levels per passage, event spacing
dt = 0.75                                      # arrival delay between neighbouring pixels
phase = np.array([0.15, 0.62, 0.35, 0.88, 0.05, 0.50])   # own phases, fractions of the level step
shared = np.full(M, 0.30)

fig = plt.figure(figsize=(3.5, 3.75))
gs = fig.add_gridspec(2, 2, height_ratios=[1.0, 1.55], hspace=0.26, wspace=0.12)

# (a) the sensor row, the edge and the threshold ladder of every pixel
ax = fig.add_subplot(gs[0, :])
x = np.linspace(-0.5, M - 0.5, 600)
edge_x, width = 2.6, 2.4                       # bright behind the edge (left), dark ahead (right)
lum = np.clip((edge_x - x) / width + 0.5, 0, 1)
ax.imshow(lum[None, :], extent=(-0.5, M - 0.5, -0.5, 0.5), cmap=GRAD, vmin=0, vmax=1, aspect="auto")
for i in range(M):
    ax.add_patch(Rectangle((i - 0.5, -0.5), 1, 1, fill=False, lw=0.8, ec="k"))
    ax.text(i, -0.62, f"{i + 1}", ha="center", va="top", fontsize=7)
    # ladder: levels a_i + k, drawn in a box above the pixel
    base, h = 0.75, 1.25
    ax.plot([i - 0.22, i - 0.22], [base, base + h], color="0.4", lw=0.6)
    for k in range(-1, n + 1):
        lev = (phase[i] + k) / n
        if 0 <= lev <= 1:
            ax.plot([i - 0.32, i + 0.22], [base + lev * h] * 2, color=CT, lw=1.1)
ax.text(-0.62, 0.75 + 1.25 / 2, "levels", ha="right", va="center", fontsize=7, rotation=90)
ax.text(-0.62, 0.0, "pixel", ha="right", va="center", fontsize=7, rotation=90)
ax.add_patch(FancyArrowPatch((2.2, -1.25), (4.2, -1.25), arrowstyle="-|>", mutation_scale=8, lw=0.9, color="k",
                             clip_on=False))
ax.text(4.3, -1.25, "edge moves", ha="left", va="center", fontsize=7)
ax.set_xlim(-0.75, M - 0.4); ax.set_ylim(-1.4, 2.15)
ax.axis("off")
ax.set_title("(a) same step, own offset of the levels in every pixel", loc="left", fontsize=8)


def spacetime(ax, ph, title, show_gap):
    t = np.linspace(-0.6, (M - 1) * dt + n * tau + 0.6, 500)
    rows = np.arange(M)
    L = np.clip((t[None, :] - rows[:, None] * dt) / (n * tau), 0, 1)
    ax.imshow(L, extent=(t[0], t[-1], M - 0.5, -0.5), cmap=GRAD, vmin=0, vmax=1, aspect="auto",
              interpolation="bilinear")
    for i in range(M + 1):
        ax.axhline(i - 0.5, color="w", lw=0.6)
    ev = [i * dt + (ph[i] + np.arange(n)) * tau for i in range(M)]
    for i in range(M):
        ax.plot(ev[i], [i] * n, "o", color=CT, ms=4.2, zorder=3)
        if i > 0:
            mv = ev[i - 1] + dt
            ax.plot(mv, [i] * n, "o", mfc="none", mec=CM, mew=1.1, ms=6.8, zorder=4)
            if show_gap:
                for a, b in zip(mv, ev[i]):
                    ax.plot([a, b], [i + 0.3] * 2, color=CM, lw=0.9, zorder=2)
    ax.set_yticks(range(M)); ax.set_yticklabels([str(i + 1) for i in range(M)], fontsize=7)
    ax.set_xticks([]); ax.set_xlabel("time")
    ax.set_xlim(t[0], t[-1])
    ax.set_title(title, loc="left", fontsize=8)
    ax.tick_params(length=0)


ax_b = fig.add_subplot(gs[1, 0])
spacetime(ax_b, shared, "(b) shared offsets", False)
ax_b.set_ylabel("pixel")
ax_c = fig.add_subplot(gs[1, 1])
spacetime(ax_c, phase, "(c) own offsets", True)
ax_c.set_yticklabels([])

h1, = ax_b.plot([], [], "o", color=CT, ms=4.2, label="event")
h2, = ax_b.plot([], [], "o", mfc="none", mec=CM, mew=1.1, ms=6.8, label="event of the pixel above, moved with the edge")
fig.legend(handles=[h1, h2], loc="lower center", ncol=2, frameon=False, fontsize=7, bbox_to_anchor=(0.5, -0.04),
           handletextpad=0.3, columnspacing=1.0)
fig.savefig(OUT + ".pdf", bbox_inches="tight", pad_inches=0.02)
