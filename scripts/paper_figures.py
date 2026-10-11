"""Directive 010: the two figures of the recorded experiments, drawn from the committed reports.

  python3 scripts/paper_figures.py ETRAM_REPORT.json DSEC_REPORT.json OUTDIR

ETRAM_REPORT is ``results/bk/report.json`` (directive 007), DSEC_REPORT is ``results/ds/report.json``
(directive 009). Three strata are drawn: ``day`` and ``night`` of the first and ``all`` of the second.
All values are the medians over recordings of the reports, frozen configuration. Nothing is computed
here. Each figure is written as PDF and PNG, with its plotted values as JSON.

fig_bits_all   Total bits against fidelity, coder Q, working grid, one panel per stratum, from
               ``tables/2_headline/Q``. Circles: the codec with the affine map for the four group
               lengths, (bits, F). Squares: the repeated key events, (bits, F). Solid: the subset
               schemes at the fidelity of the codec, (bits_base, F), ending at the direct stream,
               (bits_direct, 1). Dashed: random thinning alone, (bits_thin, F), same end point.

fig_limits     Top: fidelity of a group of four windows against the time bin of the receiver grid,
               2 px blocks, affine map, from ``tables/6_grids`` (cells ``s2_k1``, ``s2_k3``, ``s2_k8``,
               ``s2_k32``, a window being 33,333 us). Bottom: fidelity of window m against m on the
               working grid, from ``tables/5_windows``, for the affine map (solid) and the
               translation (dashed).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker  # noqa: F401
from matplotlib.lines import Line2D

BLUE, ORANGE, AQUA = "#2a78d6", "#d6542a", "#1baf7a"      # checked together for color-vision separation
INK, MUTED = "#0b0b0b", "#6f6e69"
GROUPS = ("K2", "K4", "K8", "K11")
T0_MS = 33.333
BINS = (("s2_k32", T0_MS / 32), ("s2_k8", T0_MS / 8), ("s2_k3", T0_MS / 3), ("s2_k1", T0_MS))
STRATA = (("eTraM, day", 0, "day", BLUE, "o"), ("eTraM, night", 0, "night", AQUA, "^"), ("DSEC", 1, "all", ORANGE, "s"))
plt.rcParams.update({"font.family": "serif", "font.size": 8, "axes.linewidth": 0.6, "pdf.fonttype": 42,
                     "mathtext.fontset": "cm"})


def _finish(fig, out, plotted):
    fig.savefig(str(out) + ".pdf", bbox_inches="tight", pad_inches=0.02)
    fig.savefig(str(out) + ".png", dpi=220, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)
    Path(str(out) + ".json").write_text(json.dumps(plotted, indent=1) + "\n")


def _clean(ax):
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.tick_params(length=2, width=0.5)
    ax.tick_params(which="minor", length=1.2, width=0.4)


def fig_bits_all(reports, out):
    plotted = {}
    fig, axes = plt.subplots(len(STRATA), 1, figsize=(3.45, 0.35 + 1.8 * len(STRATA)), sharex=True,
                             gridspec_kw={"hspace": 0.12})
    for ax, (label, which, name, _, _) in zip(axes, STRATA):
        rows = reports[which]["tables"]["2_headline"]["Q"][name]
        med = lambda K, model, key: rows[K][model][key]["median"]
        F = [med(K, "affine", "F") for K in GROUPS]
        bits = [med(K, "affine", "bits") for K in GROUPS]
        direct = med(GROUPS[-1], "affine", "bits_direct")
        ax.plot([med(K, "affine", "bits_thin") for K in GROUPS][::-1] + [direct], F[::-1] + [1.0], color=MUTED, lw=0.8,
                ls=(0, (3, 2)), zorder=1, label="random thinning")
        ax.plot([med(K, "affine", "bits_base") for K in GROUPS][::-1] + [direct], F[::-1] + [1.0], color=INK, lw=1.1,
                marker="o", ms=1.8, zorder=2, label="subset schemes")
        ax.plot([med(K, "static", "bits") for K in GROUPS], [med(K, "static", "F") for K in GROUPS], "s", color=ORANGE,
                ms=3.4, mec="white", mew=0.5, zorder=3, label="repeated key events")
        ax.plot(bits, F, "-o", color=BLUE, lw=0.8, ms=3.8, mec="white", mew=0.5, zorder=4, label="codec")
        for K, b, f in zip(GROUPS, bits, F):
            last_K = K == GROUPS[-1]
            ax.annotate(f"$K={K[1:]}$", (b, f), xytext=(-3 if last_K else 0, 5), textcoords="offset points",
                        ha="right" if last_K else "center", va="bottom", fontsize=6.5, color=INK)
        ax.set_xscale("log")
        ax.set_xlim(0.09, 2.6)
        ax.set_ylim(0.0, 1.04)
        ax.set_yticks([0.0, 0.25, 0.5, 0.75, 1.0])
        ax.set_ylabel("fidelity $F$", labelpad=2)
        ax.text(0.03, 0.93, label, transform=ax.transAxes, ha="left", va="top", fontsize=7.5, color=INK)
        _clean(ax)
        plotted[label] = {"F": dict(zip(GROUPS, F)), "bits": dict(zip(GROUPS, bits)), "bits_direct": direct,
                          "bits_base": {K: med(K, "affine", "bits_base") for K in GROUPS},
                          "bits_thin": {K: med(K, "affine", "bits_thin") for K in GROUPS},
                          "static": {K: [med(K, "static", "bits"), med(K, "static", "F")] for K in GROUPS}}
    axes[-1].set_xticks([0.1, 0.2, 0.5, 1.0, 2.0])
    axes[-1].set_xticklabels(["0.1", "0.2", "0.5", "1", "2"])
    axes[-1].xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    axes[-1].set_xlabel("bits per event", labelpad=1)
    axes[0].legend(loc="lower right", frameon=False, fontsize=6.5, handlelength=1.6, borderaxespad=0.2, labelspacing=0.25)
    _finish(fig, out, plotted)


def fig_limits(reports, out):
    plotted = {"bins_ms": [b for _, b in BINS], "group_fidelity_K4": {}, "window_fidelity": {}}
    fig, (ax, bx) = plt.subplots(2, 1, figsize=(3.45, 4.1), gridspec_kw={"hspace": 0.42})
    for label, which, name, color, marker in STRATA:
        tables = reports[which]["tables"]
        F = [tables["6_grids"][name][cell]["F"]["median"] for cell, _ in BINS]
        ax.plot([b for _, b in BINS], F, "-", marker=marker, color=color, lw=0.9, ms=3.8, mec="white", mew=0.5, label=label)
        plotted["group_fidelity_K4"][label] = F
        w = tables["5_windows"][name]
        m = list(range(1, 11))
        aff = [w[f"affine_s2_k3_m{j}"]["median"] for j in m]
        tra = [w[f"translation_s2_k3_m{j}"]["median"] for j in m]
        bx.plot(m, tra, color=color, lw=0.8, ls=(0, (3, 2)))
        bx.plot(m, aff, "-", marker=marker, color=color, lw=0.9, ms=3.4, mec="white", mew=0.5)
        plotted["window_fidelity"][label] = {"affine": aff, "translation": tra}
    ax.set_xscale("log")
    ax.set_xticks([b for _, b in BINS])
    ax.set_xticklabels(["1.04", "4.17", "11.1", "33.3"])
    ax.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    ax.minorticks_off()
    ax.set_xlabel("time bin of the receiver grid (ms)", labelpad=1)
    ax.set_ylabel("fidelity, $K=4$", labelpad=2)
    ax.set_ylim(0.4, 0.8)
    ax.legend(loc="lower right", frameon=False, fontsize=6.5, handlelength=1.8, borderaxespad=0.2, labelspacing=0.25)
    bx.set_xticks(range(1, 11))
    bx.set_xlabel("windows since the key window, $m$", labelpad=1)
    bx.set_ylabel("fidelity of window $m$", labelpad=2)
    bx.set_ylim(0.4, 0.7)
    bx.legend(handles=[Line2D([], [], color=INK, lw=0.9, label="affine map"),
                       Line2D([], [], color=INK, lw=0.8, ls=(0, (3, 2)), label="translation")],
              loc="upper right", frameon=False, fontsize=6.5, handlelength=1.8, borderaxespad=0.2, labelspacing=0.25)
    _clean(ax)
    _clean(bx)
    _finish(fig, out, plotted)


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit("usage: python3 scripts/paper_figures.py ETRAM_REPORT.json DSEC_REPORT.json OUTDIR")
    reports = [json.loads(Path(p).read_text()) for p in sys.argv[1:3]]
    outdir = Path(sys.argv[3])
    outdir.mkdir(parents=True, exist_ok=True)
    fig_bits_all(reports, outdir / "fig_bits_all")
    fig_limits(reports, outdir / "fig_limits")
    print("wrote", outdir / "fig_bits_all.pdf", "and", outdir / "fig_limits.pdf")
