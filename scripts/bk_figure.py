"""Directive 008: total bits against fidelity, drawn from the report JSON of the block codec.

  python3 scripts/bk_figure.py REPORT.json OUT.pdf [STRATUM ...]

One panel per stratum of Table 2 of the report (``tables/2_headline``), by default every stratum
of the file, in its order. All values are the medians over recordings of that table, coder Q,
frozen configuration, working grid. Nothing is computed here. The plotted values are also written
next to the figure as JSON.

  circles   the codec with the affine map, one point per group length K: (bits, F)
  squares   the repeated key events without motion, same K: (bits, F)
  solid     the subset schemes at the fidelity of the codec: (bits_base, F), and the direct stream
            at fidelity one: (bits_direct at the largest K, 1)
  dashed    random thinning alone at the fidelity of the codec: (bits_thin, F), and the same end point

The horizontal distance between a circle and the solid line at its height is the gain of that
group length on the logarithmic axis.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker  # noqa: F401

BLUE, ORANGE = "#2a78d6", "#d6542a"       # the two categorical colors of Figs. 1 and 2 of the manuscript
INK, MUTED = "#0b0b0b", "#6f6e69"
GROUPS = ("K2", "K4", "K8", "K11")
plt.rcParams.update({"font.family": "serif", "font.size": 8, "axes.linewidth": 0.6, "pdf.fonttype": 42,
                     "mathtext.fontset": "cm"})


def draw(report, out_pdf, strata=None):
    table = report["tables"]["2_headline"]["Q"]
    strata = list(table) if not strata else list(strata)
    plotted = {}
    fig, axes = plt.subplots(len(strata), 1, figsize=(3.45, 0.35 + 1.95 * len(strata)), sharex=True, squeeze=False,
                             gridspec_kw={"hspace": 0.14})
    for ax, name in zip(axes[:, 0], strata):
        rows = table[name]
        med = lambda K, model, key: rows[K][model][key]["median"]
        F = [med(K, "affine", "F") for K in GROUPS]
        direct = med(GROUPS[-1], "affine", "bits_direct")
        ax.plot([med(K, "affine", "bits_thin") for K in GROUPS][::-1] + [direct], F[::-1] + [1.0], color=MUTED, lw=0.8,
                ls=(0, (3, 2)), zorder=1, label="random thinning")
        ax.plot([med(K, "affine", "bits_base") for K in GROUPS][::-1] + [direct], F[::-1] + [1.0], color=INK, lw=1.1,
                marker="o", ms=1.8, zorder=2, label="subset schemes")
        ax.plot([med(K, "static", "bits") for K in GROUPS], [med(K, "static", "F") for K in GROUPS], "s", color=ORANGE,
                ms=3.4, mec="white", mew=0.5, zorder=3, label="repeated key events")
        bits = [med(K, "affine", "bits") for K in GROUPS]
        ax.plot(bits, F, "-o", color=BLUE, lw=0.8, ms=3.8, mec="white", mew=0.5, zorder=4, label="codec")
        for K, b, f in zip(GROUPS, bits, F):
            last_K = K == GROUPS[-1]
            ax.annotate(f"$K={K[1:]}$", (b, f), xytext=(-3 if last_K else 0, 5), textcoords="offset points",
                        ha="right" if last_K else "center", va="bottom", fontsize=6.5, color=INK)
        plotted[name] = {"F": dict(zip(GROUPS, F)), "bits": dict(zip(GROUPS, bits)), "bits_direct": direct,
                         "bits_base": {K: med(K, "affine", "bits_base") for K in GROUPS},
                         "bits_thin": {K: med(K, "affine", "bits_thin") for K in GROUPS},
                         "static": {K: [med(K, "static", "bits"), med(K, "static", "F")] for K in GROUPS}}
        ax.set_xscale("log")
        ax.set_xlim(0.09, 2.6)
        ax.set_ylim(0.0, 1.04)
        ax.set_yticks([0.0, 0.25, 0.5, 0.75, 1.0])
        ax.set_ylabel("fidelity $F$", labelpad=2)
        ax.text(0.03, 0.93, name, transform=ax.transAxes, ha="left", va="top", fontsize=7.5, color=INK)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        ax.tick_params(length=2, width=0.5)
        ax.tick_params(which="minor", length=1.2, width=0.4)
    last = axes[-1, 0]
    last.set_xticks([0.1, 0.2, 0.5, 1.0, 2.0])
    last.set_xticklabels(["0.1", "0.2", "0.5", "1", "2"])
    last.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    last.set_xlabel("bits per event", labelpad=1)
    axes[0, 0].legend(loc="lower right", frameon=False, fontsize=6.5, handlelength=1.6, borderaxespad=0.2,
                      labelspacing=0.25)
    fig.savefig(out_pdf, bbox_inches="tight", pad_inches=0.02)
    fig.savefig(str(out_pdf)[:-4] + ".png", dpi=220, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)
    Path(str(out_pdf)[:-4] + ".json").write_text(json.dumps(plotted, indent=1) + "\n")


if __name__ == "__main__":
    if len(sys.argv) < 3 or not sys.argv[2].endswith(".pdf"):
        sys.exit("usage: python3 scripts/bk_figure.py REPORT.json OUT.pdf [STRATUM ...]")
    Path(sys.argv[2]).parent.mkdir(parents=True, exist_ok=True)
    draw(json.loads(Path(sys.argv[1]).read_text()), sys.argv[2], sys.argv[3:])
    print("wrote", sys.argv[2])
