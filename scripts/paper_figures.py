"""Directives 010 and 011: the figures of the recorded experiments, drawn from committed files.

  python3 scripts/paper_figures.py ETRAM_REPORT.json DSEC_REPORT.json OUTDIR [RECON_DIR]

ETRAM_REPORT is ``results/bk/report.json`` (directive 007), DSEC_REPORT is ``results/ds/report.json``
(directive 009). Three strata are drawn: ``day`` and ``night`` of the first and ``all`` of the second.
All values are the medians over recordings of the reports, frozen configuration. Nothing is computed
here but percentages and the images of Section 5 of directive 011. Each figure is written as PDF and
PNG, with its plotted values as JSON.

fig_bits_all   Bits against fidelity, matched coder, working grid, from ``tables/2_headline/Q``. One
               panel per stratum and one row per group length K. In each row, at the fidelity F of
               the codec, a circle marks the bits of the codec and a ring the bits of the cheapest
               subset scheme at that fidelity (``bits_base``), both as a percentage of the bits of
               sending every event (``bits_direct``). The label is the gain G of the report.

fig_limits     Top: fidelity of a group of four windows against the time bin of the receiver grid,
               2 px blocks, affine map, from ``tables/6_grids`` (cells ``s2_k1``, ``s2_k3``, ``s2_k8``,
               ``s2_k32``, a window being 33,333 us). Bottom: fidelity of window m against m on the
               working grid, from ``tables/5_windows``, for the affine map (solid) and the
               translation (dashed).

fig_recon      Drawn only when RECON_DIR holds ``recon_images.npz`` and ``recon_selection.json``
               (directive 011, Section 5). One row per stratum, three columns: the key events that
               are sent, the true events of window m, and the events that the receiver rebuilds for
               window m from the stream. Each image is the signed event count per pixel, positive
               polarity minus negative, clipped to [-2, 2].
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker  # noqa: F401
import numpy as np
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.lines import Line2D

BLUE, ORANGE, AQUA = "#2a78d6", "#d6542a", "#1baf7a"      # checked together for color-vision separation
INK, MUTED = "#0b0b0b", "#6f6e69"
GROUPS = ("K2", "K4", "K8", "K11")
T0_MS = 33.333
BINS = (("s2_k32", T0_MS / 32), ("s2_k8", T0_MS / 8), ("s2_k3", T0_MS / 3), ("s2_k1", T0_MS))
STRATA = (("eTraM, day", 0, "day", BLUE, "o"), ("eTraM, night", 0, "night", AQUA, "^"), ("DSEC", 1, "all", ORANGE, "s"))
COLUMNS = (("key", "sent: key events"), ("true", "true, window $m$"), ("rec", "rebuilt, window $m$"))
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
    fig, axes = plt.subplots(len(STRATA), 1, figsize=(3.45, 0.45 + 1.2 * len(STRATA)), sharex=True,
                             gridspec_kw={"hspace": 0.32})
    for ax, (label, which, name, _, _) in zip(axes, STRATA):
        rows = reports[which]["tables"]["2_headline"]["Q"][name]
        med = lambda K, key: rows[K]["affine"][key]["median"]
        plotted[label] = {}
        for r, K in enumerate(GROUPS):
            y = len(GROUPS) - 1 - r
            direct = med(K, "bits_direct")
            codec, base = 100.0 * med(K, "bits") / direct, 100.0 * med(K, "bits_base") / direct
            F, G = med(K, "F"), med(K, "gain")
            ax.plot([codec, base], [y, y], color=MUTED, lw=1.0, zorder=1)
            ax.plot(base, y, "o", ms=4.6, mfc="white", mec=INK, mew=0.9, zorder=2)
            ax.plot(codec, y, "o", ms=4.6, color=BLUE, mec="white", mew=0.5, zorder=3)
            ax.text(max(codec, base) + 2.5, y, f"$\\times{G:.2f}$", va="center", ha="left", fontsize=7, color=INK)
            plotted[label][K] = {"F": F, "codec_percent": codec, "subset_percent": base, "gain": G}
        ax.set_yticks(range(len(GROUPS)))
        ax.set_yticklabels([f"$K={K[1:]}$, $F={plotted[label][K]['F']:.2f}$" for K in GROUPS][::-1], fontsize=7)
        ax.set_ylim(-0.6, len(GROUPS) - 0.4)
        ax.set_xlim(0, 100)
        ax.set_title(label, fontsize=7.5, loc="left", pad=2, color=INK)
        _clean(ax)
        ax.tick_params(axis="y", length=0)
        ax.grid(axis="x", color="#e4e3dd", lw=0.5, zorder=0)
    axes[-1].set_xlabel("bits sent, % of sending every event", labelpad=1)
    axes[0].legend(handles=[Line2D([], [], ls="", marker="o", ms=4.6, color=BLUE, mec="white", label="codec"),
                            Line2D([], [], ls="", marker="o", ms=4.6, mfc="white", mec=INK, mew=0.9,
                                   label="cheapest subset scheme, same $F$")],
                   loc="upper center", bbox_to_anchor=(0.5, 1.42), ncol=2, frameon=False, fontsize=6.5,
                   handletextpad=0.3, columnspacing=1.2)
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


def fig_recon(recon_dir, out):
    images = np.load(Path(recon_dir) / "recon_images.npz")
    sel = json.loads((Path(recon_dir) / "recon_selection.json").read_text())
    cmap = LinearSegmentedColormap.from_list("signed", [BLUE, "#ffffff", ORANGE])
    fig, axes = plt.subplots(len(STRATA), len(COLUMNS), figsize=(7.0, 0.3 + 1.45 * len(STRATA)),
                             gridspec_kw={"hspace": 0.08, "wspace": 0.04})
    plotted = {}
    for r, (label, _, name, _, _) in enumerate(STRATA):
        s = sel[name]
        plotted[label] = {k: s[k] for k in ("recording", "w", "m", "crop", "n_events", "F_window", "F_window_median")}
        for c, (panel, title) in enumerate(COLUMNS):
            ax = axes[r, c]
            img = np.clip(images[f"{name}_{panel}"], -2, 2)
            ax.imshow(img, cmap=cmap, vmin=-2, vmax=2, interpolation="nearest", aspect="equal")
            ax.set_xticks([]); ax.set_yticks([])
            for sp in ax.spines.values():
                sp.set_linewidth(0.4); sp.set_color(MUTED)
            ax.text(0.02, 0.03, f"{s['n_events'][panel]:,} events", transform=ax.transAxes, fontsize=6, color=INK,
                    ha="left", va="bottom", bbox=dict(facecolor="white", edgecolor="none", pad=0.8, alpha=0.8))
            if panel == "rec":
                ax.text(0.98, 0.03, f"$F={s['F_window']:.2f}$", transform=ax.transAxes, fontsize=6.5, color=INK,
                        ha="right", va="bottom", bbox=dict(facecolor="white", edgecolor="none", pad=0.8, alpha=0.8))
            if r == 0:
                ax.set_title(title.replace("$m$", f"$m={s['m']}$"), fontsize=7.5, pad=3)
            if c == 0:
                ax.set_ylabel(label, fontsize=7.5, labelpad=3)
    _finish(fig, out, plotted)


if __name__ == "__main__":
    if len(sys.argv) not in (4, 5):
        sys.exit("usage: python3 scripts/paper_figures.py ETRAM_REPORT.json DSEC_REPORT.json OUTDIR [RECON_DIR]")
    reports = [json.loads(Path(p).read_text()) for p in sys.argv[1:3]]
    outdir = Path(sys.argv[3])
    outdir.mkdir(parents=True, exist_ok=True)
    fig_bits_all(reports, outdir / "fig_bits_all")
    fig_limits(reports, outdir / "fig_limits")
    if len(sys.argv) == 5:
        fig_recon(sys.argv[4], outdir / "fig_recon")
    print("wrote the figures under", outdir)
