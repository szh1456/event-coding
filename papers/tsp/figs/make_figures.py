"""Figures of the manuscript that come from the model alone. Usage: python3 make_figures.py

fig_mechanism.pdf  One ramp seen by two pixels with different threshold phases: their level
                   lattices, their events, and the mean-time regeneration of Eq. (19).
"""
from __future__ import annotations

import pathlib

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
PIX = ("#2a78d6", "#d6542a")            # two categorical slots, checked for color-vision separation
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#c9c8c2"
plt.rcParams.update({"font.family": "serif", "font.size": 8, "axes.linewidth": 0.6, "pdf.fonttype": 42,
                     "mathtext.fontset": "cm"})


def mechanism():
    n, C = 3, 1.0                                      # events per pixel, threshold
    tau = 1.0                                          # event spacing, the time unit
    phases = (0.25, 0.80)                              # a_i / C of the two pixels
    t = np.linspace(-1.05, n * tau + 0.9, 600)
    ramp = np.clip(t / tau * C, 0.0, n * C)
    fig, (ax, bx) = plt.subplots(2, 1, figsize=(3.45, 3.0), sharex=True,
                                 gridspec_kw={"height_ratios": [2.1, 1.0], "hspace": 0.08})
    ax.plot(t, ramp, color=INK, lw=1.4, zorder=3)
    ax.set_ylabel("log intensity", labelpad=2)
    markers = ("o", "s")
    for a, col, mk, name, dy in zip(phases, PIX, markers, ("pixel 1", "pixel 2"), (-0.02, -0.02)):
        levels = a * C + C * np.arange(n)
        times = levels / C * tau
        for lv, tk in zip(levels, times):
            ax.plot([t[0], tk], [lv, lv], color=col, lw=0.7, ls=(0, (3, 2)), zorder=1)
            ax.plot([tk, tk], [lv, -0.45], color=col, lw=0.5, ls=(0, (1, 2)), zorder=1)
        ax.plot(times, levels, mk, color=col, ms=4.2, mec="white", mew=0.6, zorder=4)
        ax.text(0.9 * tau, levels[-1] + 0.07, f"levels of {name}", color=INK, fontsize=7, ha="right", va="bottom")
    # the phase of pixel 1, measured from the rest level
    box = dict(facecolor="white", edgecolor="none", pad=0.6)
    ax.annotate("", xy=(-0.55, phases[0] * C), xytext=(-0.55, 0.0),
                arrowprops=dict(arrowstyle="<->", lw=0.6, color=INK, shrinkA=0, shrinkB=0, mutation_scale=6))
    ax.text(-0.62, 0.56 * phases[0] * C, "$a_1$", fontsize=7, va="center", ha="right", color=INK)
    ax.annotate("", xy=(-0.85, phases[1] * C + C), xytext=(-0.85, phases[1] * C),
                arrowprops=dict(arrowstyle="<->", lw=0.6, color=INK, shrinkA=0, shrinkB=0, mutation_scale=6))
    ax.text(-0.78, phases[1] * C + 0.72 * C, "$C$", fontsize=7, va="center", ha="left", color=INK, bbox=box)
    ax.set_ylim(-0.45, n * C + 0.55)
    ax.set_yticks([0, n * C]); ax.set_yticklabels(["0", "$V$"])
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.tick_params(length=2, width=0.5)

    rows = [("pixel 1", phases[0] + np.arange(n), PIX[0], "o"),
            ("pixel 2", phases[1] + np.arange(n), PIX[1], "s"),
            ("regenerated", 0.5 + np.arange(n), INK, "D")]
    for r, (name, times, col, mk) in enumerate(rows):
        y = len(rows) - 1 - r
        bx.plot([t[0], t[-1]], [y, y], color=GRID, lw=0.5, zorder=1)
        bx.plot(times * tau, np.full(n, y), mk, color=col, ms=4.2, mec="white", mew=0.6, zorder=3)
    for k in range(n + 1):                             # one event spacing per cell
        bx.plot([k * tau, k * tau], [-0.45, len(rows) - 0.55], color=GRID, lw=0.5, zorder=0)
    bx.annotate("", xy=(2.0 * tau, -0.62), xytext=(1.0 * tau, -0.62),
                arrowprops=dict(arrowstyle="<->", lw=0.6, color=INK, shrinkA=0, shrinkB=0, mutation_scale=6),
                annotation_clip=False)
    bx.text(1.5 * tau, -0.72, r"$\tau_i$", fontsize=7, ha="center", va="top", color=INK)
    bx.set_ylim(-1.25, len(rows) - 0.4)
    bx.set_yticks(range(len(rows))); bx.set_yticklabels([r[0] for r in rows][::-1])
    bx.set_xticks([0, n * tau]); bx.set_xticklabels(["$t_i$", r"$t_i+n\tau_i$"])
    bx.set_xlabel("time", labelpad=1)
    for s in ("top", "right", "left"):
        bx.spines[s].set_visible(False)
    bx.tick_params(length=2, width=0.5); bx.tick_params(axis="y", length=0)
    fig.savefig(HERE / "fig_mechanism.pdf", bbox_inches="tight", pad_inches=0.02)
    fig.savefig(HERE / "fig_mechanism.png", dpi=220, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


if __name__ == "__main__":
    mechanism()
    print("wrote", HERE / "fig_mechanism.pdf")
