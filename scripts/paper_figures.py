"""Directives 010 to 015: the figures of the paper, drawn from committed files.

  python3 scripts/paper_figures.py --etram ETRAM_REPORT.json --dsec DSEC_REPORT.json --out OUTDIR
                                   [--recon RECON_DIR] [--tradeoff TRADEOFF.json] [--bridge BRIDGE.json]

ETRAM_REPORT is ``results/bk/report.json`` (directive 007), DSEC_REPORT is ``results/dt/report.json``
(directive 013). Three strata are drawn: ``day`` and ``night`` of the first and ``all`` of the second.
Values are medians over recordings, frozen configuration. Nothing is computed here but percentages.
Each figure is written as PDF and PNG, with its plotted values as JSON.

fig_bits_all   Bits against fidelity at one operating point per K, matched coder, working grid, from
               ``tables/2_headline/Q``. One panel per stratum and one row per group length K. In each
               row, at the fidelity F of REMAKE, a circle marks its bits and a ring the bits of the
               cheapest subset scheme at that fidelity (``bits_base``), both as a percentage of the bits
               of sending every event (``bits_direct``). The label is the gain G of the report.

fig_tradeoff   Drawn when TRADEOFF.json is given (directive 014, Section 6). One panel per stratum:
               bits as a percentage of the bits of every event against F, for K = 4 and K = 11, over
               the five thresholds. Solid with filled markers: REMAKE. Dashed with open markers: the
               cheapest subset scheme at the fidelity of each point. The threshold rises to the left.

fig_limits     Top: fidelity of a group of four windows against the time bin of the receiver grid,
               2 px blocks, affine map, from ``tables/6_grids`` (cells ``s2_k1``, ``s2_k3``,
               ``s2_k8``, ``s2_k32``, a window being 33,333 us). Middle: the gain of the transport coder
               on the same grids, from the same cells. Bottom: fidelity of window m against m on the
               working grid, from ``tables/5_windows``, affine map (solid) and translation (dashed).

fig_bits_pair  Drawn when TRADEOFF.json is given (directive 015). fig_bits_all and fig_tradeoff on one
               grid: one row per stratum, the panel of fig_bits_all on the left and that of
               fig_tradeoff on the right, rows aligned, each column with its legend at the top.

fig_recon      Drawn when RECON_DIR holds ``recon_images.npz`` and ``recon_selection.json``
               (directives 011 to 013). One row per stratum, three columns: the key events that are
               sent, the true events of window m, and the events that the receiver rebuilds for window
               m from the stream. Each image is the signed event count per pixel, positive polarity
               minus negative, clipped to [-2, 2].

fig_slices     Drawn when the npz also holds the zoom images of directive 014, Section 7. One row per
               stratum, six columns: the true and the rebuilt events of the zoom square in each third of
               window m, signed counts per pixel clipped to [-1, 1], with the fidelity of that third on
               the working grid inside the square.

fig_bridge     Drawn when BRIDGE.json is given (``ec.bridge``, directive 014). Top: timing error per
               event over D_A against the window m, for the regenerated events, moved events under the
               exact map (equal and growing spacings) and under the nearest whole-pixel map, with the
               prediction of Proposition 2 as open markers. Bottom: fidelity on one-pixel voxels
               against the bin over the event spacing, for the regenerated events, the moved events
               (exact map, and nearest whole-pixel map), and the moved events of the fitted map scored
               on whole windows as REMAKE is, with the predictions for bins up to half the spacing.
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
PURPLE = "#8a5cc2"
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


def _dumbbell(ax, rows):
    med = lambda K, key: rows[K]["affine"][key]["median"]
    plotted = {}
    for r, K in enumerate(GROUPS):
        y = len(GROUPS) - 1 - r
        direct = med(K, "bits_direct")
        codec, base = 100.0 * med(K, "bits") / direct, 100.0 * med(K, "bits_base") / direct
        F, G = med(K, "F"), med(K, "gain")
        ax.plot([codec, base], [y, y], color=MUTED, lw=1.0, zorder=1)
        ax.plot(base, y, "o", ms=4.6, mfc="white", mec=INK, mew=0.9, zorder=2)
        ax.plot(codec, y, "o", ms=4.6, color=BLUE, mec="white", mew=0.5, zorder=3)
        ax.text(max(codec, base) + 2.5, y, f"$\\times{G:.2f}$", va="center", ha="left", fontsize=7, color=INK)
        plotted[K] = {"F": F, "codec_percent": codec, "subset_percent": base, "gain": G}
    ax.set_yticks(range(len(GROUPS)))
    ax.set_yticklabels([f"$K={K[1:]}$, $F={plotted[K]['F']:.2f}$" for K in GROUPS][::-1], fontsize=7)
    ax.set_ylim(-0.6, len(GROUPS) - 0.4)
    ax.set_xlim(0, 100)
    _clean(ax)
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="x", color="#e4e3dd", lw=0.5, zorder=0)
    return plotted


def _dumbbell_legend():
    return [Line2D([], [], ls="", marker="o", ms=4.6, color=BLUE, mec="white", label="REMAKE"),
            Line2D([], [], ls="", marker="o", ms=4.6, mfc="white", mec=INK, mew=0.9,
                   label="cheapest subset scheme, same $F$")]


def fig_bits_all(reports, out):
    plotted = {}
    fig, axes = plt.subplots(len(STRATA), 1, figsize=(3.45, 0.45 + 1.2 * len(STRATA)), sharex=True,
                             gridspec_kw={"hspace": 0.32})
    for ax, (label, which, name, _, _) in zip(axes, STRATA):
        plotted[label] = _dumbbell(ax, reports[which]["tables"]["2_headline"]["Q"][name])
        ax.set_title(label, fontsize=7.5, loc="left", pad=2, color=INK)
    axes[-1].set_xlabel("bits sent, % of sending every event", labelpad=1)
    axes[0].legend(handles=_dumbbell_legend(), loc="upper center", bbox_to_anchor=(0.5, 1.42), ncol=2,
                   frameon=False, fontsize=6.5, handletextpad=0.3, columnspacing=1.2)
    _finish(fig, out, plotted)


def fig_limits(reports, out):
    plotted = {"bins_ms": [b for _, b in BINS], "group_fidelity_K4": {}, "gain_T_K4": {}, "window_fidelity": {}}
    fig, (ax, gx, bx) = plt.subplots(3, 1, figsize=(3.45, 5.7), gridspec_kw={"hspace": 0.5})
    for label, which, name, color, marker in STRATA:
        tables = reports[which]["tables"]
        F = [tables["6_grids"][name][cell]["F"]["median"] for cell, _ in BINS]
        ax.plot([b for _, b in BINS], F, "-", marker=marker, color=color, lw=0.9, ms=3.8, mec="white", mew=0.5, label=label)
        plotted["group_fidelity_K4"][label] = F
        Gt = [tables["6_grids"][name][cell]["gain"]["median"] for cell, _ in BINS]
        gx.plot([b for _, b in BINS], Gt, "-", marker=marker, color=color, lw=0.9, ms=3.8, mec="white", mew=0.5)
        plotted["gain_T_K4"][label] = Gt
        w = tables["5_windows"][name]
        m = list(range(1, 11))
        aff = [w[f"affine_s2_k3_m{j}"]["median"] for j in m]
        tra = [w[f"translation_s2_k3_m{j}"]["median"] for j in m]
        bx.plot(m, tra, color=color, lw=0.8, ls=(0, (3, 2)))
        bx.plot(m, aff, "-", marker=marker, color=color, lw=0.9, ms=3.4, mec="white", mew=0.5)
        plotted["window_fidelity"][label] = {"affine": aff, "translation": tra}
    for a in (ax, gx):
        a.set_xscale("log")
        a.set_xticks([b for _, b in BINS])
        a.set_xticklabels(["1.04", "4.17", "11.1", "33.3"])
        a.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
        a.minorticks_off()
        a.set_xlabel("time bin of the receiver grid (ms)", labelpad=1)
    ax.set_ylabel("fidelity, $K=4$", labelpad=2)
    ax.set_ylim(0.4, 0.8)
    gx.set_ylabel("gain $G_{\\mathrm{T}}$, $K=4$", labelpad=2)
    gx.axhline(1.0, color=MUTED, lw=0.5, ls=(0, (2, 2)), zorder=0)
    gx.set_ylim(0, 3.4)
    ax.legend(loc="lower right", frameon=False, fontsize=6.5, handlelength=1.8, borderaxespad=0.2, labelspacing=0.25)
    bx.set_xticks(range(1, 11))
    bx.set_xlabel("windows since the key window, $m$", labelpad=1)
    bx.set_ylabel("fidelity of window $m$", labelpad=2)
    bx.set_ylim(0.4, 0.7)
    bx.legend(handles=[Line2D([], [], color=INK, lw=0.9, label="affine map"),
                       Line2D([], [], color=INK, lw=0.8, ls=(0, (3, 2)), label="translation")],
              loc="upper right", frameon=False, fontsize=6.5, handlelength=1.8, borderaxespad=0.2, labelspacing=0.25)
    for a in (ax, gx, bx):
        _clean(a)
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


RHOS = (("B20_rho0.0625", "1/16"), ("B20_rho0.125", "1/8"), ("B20_rho0.25", "1/4"), ("B20_rho0.5", "1/2"),
        ("B20_rho1.0", "1"))
TRADE_K = (("K4", BLUE, "o"), ("K11", ORANGE, "s"))


def _tradeoff(ax, trade, name):
    plotted = {}
    for K, color, marker in TRADE_K:
        pts = [trade["strata"][name][K][rho] for rho, _ in RHOS]
        F = [p["F"] for p in pts]
        ax.plot(F, [p["bits_pct"] for p in pts], "-", marker=marker, color=color, lw=0.9, ms=3.6,
                mec="white", mew=0.5, zorder=3)
        ax.plot(F, [p["sub_pct"] for p in pts], ls=(0, (3, 2)), marker=marker, color=color, lw=0.8, ms=3.6,
                mfc="white", mec=color, mew=0.8, zorder=2)
        plotted[K] = {rho: pts[i] for i, (rho, _) in enumerate(RHOS)}
    ax.set_ylim(0, None)
    _clean(ax)
    ax.grid(color="#e4e3dd", lw=0.5, zorder=0)
    return plotted


def _tradeoff_legend():
    handles = [Line2D([], [], color=c, marker=mk, ms=3.6, lw=0.9, mec="white", mew=0.5, label=f"REMAKE, $K={K[1:]}$")
               for K, c, mk in TRADE_K]
    handles += [Line2D([], [], color=c, marker=mk, ms=3.6, lw=0.8, ls=(0, (3, 2)), mfc="white", mec=c, mew=0.8,
                       label=f"subset, $K={K[1:]}$") for K, c, mk in TRADE_K]
    return handles


def fig_tradeoff(trade, out):
    plotted = {}
    fig, axes = plt.subplots(len(STRATA), 1, figsize=(3.45, 0.5 + 1.55 * len(STRATA)), sharex=True,
                             gridspec_kw={"hspace": 0.3})
    for ax, (label, _, name, _, _) in zip(axes, STRATA):
        plotted[label] = _tradeoff(ax, trade, name)
        ax.set_title(label, fontsize=7.5, loc="left", pad=2, color=INK)
        ax.set_ylabel("bits, % of all", labelpad=2)
    axes[-1].set_xlabel("fidelity $F$", labelpad=1)
    axes[0].legend(handles=_tradeoff_legend(), loc="upper center", bbox_to_anchor=(0.5, 1.48), ncol=2, frameon=False,
                   fontsize=6.5, handlelength=2.2, columnspacing=1.0, labelspacing=0.3)
    _finish(fig, out, plotted)


def fig_bits_pair(reports, trade, out):
    plotted = {"bits": {}, "tradeoff": {}}
    fig, axes = plt.subplots(len(STRATA), 2, figsize=(7.0, 0.75 + 1.3 * len(STRATA)),
                             gridspec_kw={"hspace": 0.38, "wspace": 0.28, "width_ratios": [1.0, 1.0]})
    for r, (label, which, name, _, _) in enumerate(STRATA):
        plotted["bits"][label] = _dumbbell(axes[r, 0], reports[which]["tables"]["2_headline"]["Q"][name])
        plotted["tradeoff"][label] = _tradeoff(axes[r, 1], trade, name)
        axes[r, 0].set_title(label, fontsize=7.5, loc="left", pad=2, color=INK)
        axes[r, 1].set_title(label, fontsize=7.5, loc="left", pad=2, color=INK)
        axes[r, 1].set_ylabel("bits, % of all", labelpad=2)
        if r < len(STRATA) - 1:
            axes[r, 0].tick_params(labelbottom=False)
            axes[r, 1].tick_params(labelbottom=False)
    lo = min(min(p["F"] for p in plotted["tradeoff"][lab][K].values()) for lab in plotted["tradeoff"] for K in plotted["tradeoff"][lab])
    hi = max(max(p["F"] for p in plotted["tradeoff"][lab][K].values()) for lab in plotted["tradeoff"] for K in plotted["tradeoff"][lab])
    for r in range(len(STRATA)):
        axes[r, 1].set_xlim(lo - 0.01, hi + 0.01)
    axes[-1, 0].set_xlabel("bits sent, % of sending every event", labelpad=1)
    axes[-1, 1].set_xlabel("fidelity $F$", labelpad=1)
    axes[0, 0].legend(handles=_dumbbell_legend(), loc="lower center", bbox_to_anchor=(0.5, 1.14), ncol=1,
                      frameon=False, fontsize=6.5, handletextpad=0.3, labelspacing=0.3)
    axes[0, 1].legend(handles=_tradeoff_legend(), loc="lower center", bbox_to_anchor=(0.5, 1.14), ncol=2,
                      frameon=False, fontsize=6.5, handlelength=2.0, columnspacing=1.0, handletextpad=0.4,
                      labelspacing=0.3)
    _finish(fig, out, plotted)


def fig_slices(recon_dir, out):
    images = np.load(Path(recon_dir) / "recon_images.npz")
    sel = json.loads((Path(recon_dir) / "recon_selection.json").read_text())
    cmap = LinearSegmentedColormap.from_list("signed", [BLUE, "#ffffff", ORANGE])
    fig, axes = plt.subplots(len(STRATA), 6, figsize=(7.0, 0.35 + 1.18 * len(STRATA)),
                             gridspec_kw={"hspace": 0.1, "wspace": 0.05})
    plotted = {}
    for r, (label, _, name, _, _) in enumerate(STRATA):
        s = sel[name]
        plotted[label] = {"zoom": s["zoom"], "zoom_F_bins": s["zoom_F_bins"], "zoom_n_events": s["zoom_n_events"]}
        for b in range(3):
            for c, kind in enumerate(("true", "rec")):
                ax = axes[r, 2 * b + c]
                img = np.clip(images[f"{name}_zoom_{kind}_b{b}"], -1, 1)
                ax.imshow(img, cmap=cmap, vmin=-1, vmax=1, interpolation="nearest", aspect="equal")
                ax.set_xticks([]); ax.set_yticks([])
                for sp in ax.spines.values():
                    sp.set_linewidth(0.4); sp.set_color(MUTED)
                if kind == "rec":
                    ax.text(0.97, 0.04, f"$F={s['zoom_F_bins'][b]:.2f}$", transform=ax.transAxes, fontsize=6,
                            color=INK, ha="right", va="bottom",
                            bbox=dict(facecolor="white", edgecolor="none", pad=0.6, alpha=0.8))
                if r == 0:
                    t0, t1 = b * T0_MS / 3, (b + 1) * T0_MS / 3
                    ax.set_title(("true" if kind == "true" else "rebuilt") + f", {t0:.0f}$-${t1:.0f} ms",
                                 fontsize=6.8, pad=3)
                if c == 0 and b == 0:
                    ax.set_ylabel(label, fontsize=7.5, labelpad=3)
    _finish(fig, out, plotted)


def fig_bridge(br, out):
    cases = br["cases"]
    fig, (ax, bx) = plt.subplots(2, 1, figsize=(3.45, 4.6), gridspec_kw={"hspace": 0.62})
    plotted = {"timing": {}, "fidelity": {}}
    series = (("regenerated", cases["translation"], "regen", BLUE, "o"),
              ("moved, exact map", cases["translation"], "exact", ORANGE, "s"),
              ("moved, exact map, growing spacing", cases["scale"], "exact", PURPLE, "D"),
              ("moved, nearest whole pixel", cases["subpixel"], "round", AQUA, "^"))
    for label, c, key, color, marker in series:
        m = [row["m"] for row in c["per_m"]]
        y = [row[f"{key}_D_over_DA"] for row in c["per_m"]]
        ax.plot(m, y, "-", marker=marker, color=color, lw=0.9, ms=3.4, mec="white", mew=0.5, label=label, zorder=3)
        if key != "regen":
            pr = [row[f"{key}_pred_over_DA"] for row in c["per_m"]]
            ax.plot(m, pr, ls="", marker=marker, ms=5.2, mfc="none", mec=INK, mew=0.5, zorder=4)
        else:
            pr = None
        plotted["timing"][label] = {"m": m, "measured": y, "predicted": pr}
    ax.set_xticks(range(1, 11))
    ax.set_xlabel("windows since the key window, $m$", labelpad=1)
    ax.set_ylabel("timing error / $D_{A}$", labelpad=2)
    ax.set_ylim(0, None)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=2, frameon=False, fontsize=6.2, handlelength=1.8,
              borderaxespad=0.2, labelspacing=0.25, columnspacing=1.0)
    dts = cases["translation"]["dt_over_tau"]
    fseries = (("regenerated", cases["translation"]["fidelity"]["pixel"]["regen"], BLUE, "o", "-"),
               ("moved, exact map", cases["translation"]["fidelity"]["pixel"]["exact"], ORANGE, "s", "-"),
               ("moved, nearest whole pixel", cases["subpixel"]["fidelity"]["pixel"]["round"], AQUA, "^", "-"),
               ("moved, fitted map, whole windows", cases["subpixel"]["fidelity"]["window"]["fit"], INK, "v", "-"))
    for label, y, color, marker, ls in fseries:
        bx.plot(dts, y, ls=ls, marker=marker, color=color, lw=0.9, ms=3.4, mec="white", mew=0.5, label=label, zorder=3)
        plotted["fidelity"][label] = y
    th = cases["translation"]["fidelity_theory"]
    xs = [d for d in dts if d <= 0.5]
    bx.plot(xs, [th["regen"][dts.index(d)] for d in xs], color=BLUE, lw=0.5, ls=(0, (1, 1.5)), zorder=2)
    bx.plot(xs, [th["moved"][dts.index(d)] for d in xs], color=ORANGE, lw=0.5, ls=(0, (1, 1.5)), zorder=2)
    plotted["fidelity"]["dt_over_tau"] = dts
    plotted["fidelity"]["theory"] = th
    bx.set_xscale("log")
    bx.set_xlabel("time bin / event spacing, $\\Delta_t/\\tau$", labelpad=1)
    bx.set_ylabel("fidelity, 1-pixel voxels", labelpad=2)
    bx.set_ylim(0, 1.0)
    bx.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}"))
    bx.legend(loc="upper left", frameon=False, fontsize=6.2, handlelength=1.8, borderaxespad=0.2, labelspacing=0.25)
    for a in (ax, bx):
        _clean(a)
    _finish(fig, out, plotted)


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--etram", required=True)
    ap.add_argument("--dsec", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--recon")
    ap.add_argument("--tradeoff")
    ap.add_argument("--bridge")
    a = ap.parse_args(argv)
    reports = [json.loads(Path(p).read_text()) for p in (a.etram, a.dsec)]
    outdir = Path(a.out)
    outdir.mkdir(parents=True, exist_ok=True)
    fig_bits_all(reports, outdir / "fig_bits_all")
    fig_limits(reports, outdir / "fig_limits")
    if a.recon:
        fig_recon(a.recon, outdir / "fig_recon")
        if "day_zoom_true_b0" in np.load(Path(a.recon) / "recon_images.npz").files:
            fig_slices(a.recon, outdir / "fig_slices")
    if a.tradeoff:
        trade = json.loads(Path(a.tradeoff).read_text())
        fig_tradeoff(trade, outdir / "fig_tradeoff")
        fig_bits_pair(reports, trade, outdir / "fig_bits_pair")
    if a.bridge:
        fig_bridge(json.loads(Path(a.bridge).read_text()), outdir / "fig_bridge")
    print("wrote the figures under", outdir)


if __name__ == "__main__":
    main()
