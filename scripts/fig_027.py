"""Directive 027: figures of the manuscript after the third review, drawn from committed files only.

  python3 scripts/fig_027.py --pc results/pc --hd results/hd --hc results/hc --demo results/td2 \
      --paper results/paper --out results/paper

fig_moved2  (a) The controlled model of ``ec.phase_control``, n = 3: F of the counts moved along the true
            motion against dt / tau, for shared phases without jitter, independent phases without jitter and
            independent phases with jitter, from ``pc/report.json#/control``; lines: min(dt / tau, 1) and
            dt / tau - dt^2 / (3 n tau^2) where dt <= tau / 2. (b) As (b) of ``fig_moved`` (directive 023).

fig_phase3  (a) As ``fig_phase2`` (directive 026), from ``paper/fig_phase2.json``. (b) The histogram of u,
            centred on 0, as a density, for the pixels of moving blocks with 0.25 <= tau_i < 4 ms outside the
            flicker classes, per stratum, of the null pooled over strata, and of the model scenes with shared
            and with independent phases, from ``pc/report.json``; the legend gives the mean Rayleigh
            statistic per block of each stratum.

fig_tolerance_compact2
            As ``fig_tolerance_compact`` (directive 026), with column titles that name what each code sends,
            F on (1 px, T0 / 3) in the panel of the whole window, F on (1 px, T0 / 32) in the panel of the
            slice, and the pixel counts of the comparison in its panel.

fig_hevc2   As ``fig_hevc`` (directive 023), with row (c) the motion error of the P-picture decode,
            placement ``start``, median over recordings, from ``hd/frontier.json``.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

BLUE, ORANGE, AQUA = "#2a78d6", "#d6542a", "#1baf7a"
PURPLE = "#8a5cc2"
INK, MUTED, FAINT = "#0b0b0b", "#6f6e69", "#e4e3dd"
STRATA = (("eTraM, day", "day", BLUE, "o"), ("eTraM, night", "night", AQUA, "^"), ("DSEC", "all", ORANGE, "s"))
QPS = (12, 14, 16, 18, 20, 22, 24, 28)
CONDS = (("shared", "shared phases", INK, "s", INK), ("independent", "independent phases", BLUE, "o", BLUE),
         ("jitter", "independent phases, jitter", ORANGE, "^", "white"))
RECS = (("recorded", "recorded"), ("every", "all events"), ("pixel", "motion and one time\ncorrection per pixel"),
        ("motion", "motion only"))
BG, MATCH, MISSED, EXTRA = "#f6f6f4", "#9a9a96", "#6a3d9a", "#e8862a"
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
    ax.grid(color=FAINT, lw=0.5, zorder=0)


def _label(ax, s):
    ax.text(-0.16, 1.02, s, transform=ax.transAxes, fontsize=8, fontweight="bold", va="bottom")


def fig_moved2(pc, hc, out):
    fig, axes = plt.subplots(2, 1, figsize=(3.45, 4.3), constrained_layout=True)
    plotted = {"a": {}, "b": {}}
    ax = axes[0]
    for cond, lab, col, mk, face in CONDS:
        pts = sorted(((c["dt_over_tau"][k], c["F"][k]) for c in pc["control"] if c["condition"] == cond
                      for k in c["F"]), key=lambda p: p[0])
        r, f = np.array(pts).T
        ax.plot(r, f, mk, ms=3.0, mfc=face, mec=col, mew=0.7, ls="", zorder=3, label=lab)
        plotted["a"][cond] = {"dt_over_tau": r.tolist(), "F": f.tolist()}
    rr = np.geomspace(0.04, 200, 400)
    ax.plot(rr, np.minimum(rr, 1.0), color=MUTED, lw=0.9, ls=":", zorder=2, label=r"$\min(\Delta_t/\tau,1)$")
    rs = np.geomspace(0.04, 0.5, 100)
    ax.plot(rs, rs - rs ** 2 / 9.0, color=BLUE, lw=0.9, zorder=2,
            label=r"$\Delta_t/\tau-\Delta_t^2/(3n\tau^2)$")
    ax.set_xscale("log")
    ax.set_xlim(0.04, 200)
    ax.set_ylim(0, 1.05)
    ax.set_xlabel(r"$\Delta_t/\tau$")
    ax.set_ylabel(r"fidelity $F$, true motion")
    ax.legend(fontsize=6.5, frameon=False, loc="lower right")
    _clean(ax)
    _label(ax, "(a)")
    ax = axes[1]
    m5 = hc["tables"]["5_model"]
    keys = (("b_lossless_P", "x265, P pictures", BLUE, "o"), ("b_lossless_intra", "x265, intra only", ORANGE, "s"),
            ("b_sparse", "voxel list", INK, "^"))
    for tau, ls in ((1000, "-"), (4000, "--")):
        cells = sorted((c for c in m5.values() if c["n"] == 3 and c["s"] == 1 and c["tau"] == tau),
                       key=lambda c: c["dt_over_tau"])
        r = np.array([c["dt_over_tau"] for c in cells])
        for key, lab, col, mk in keys:
            y = np.array([c[key] for c in cells])
            ax.plot(r, y, color=col, ls=ls, lw=0.9, marker=mk, ms=2.6, mew=0, zorder=3,
                    label=lab if tau == 1000 else None)
            plotted["b"][f"tau{tau}_{key}"] = {"dt_over_tau": r.tolist(), "bits_per_event": y.tolist()}
    ax.plot([], [], color=MUTED, ls="-", lw=0.9, label=r"$\tau=1$ ms")
    ax.plot([], [], color=MUTED, ls="--", lw=0.9, label=r"$\tau=4$ ms")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(0.04, 200)
    ax.set_xlabel(r"$\Delta_t/\tau$")
    ax.set_ylabel("bits per event, lossless")
    ax.legend(fontsize=6.5, frameon=False, loc="upper right")
    _clean(ax)
    _label(ax, "(b)")
    _finish(fig, out / "fig_moved2", plotted)


def _centred(h):
    """A histogram over [0, 1) as a density over [-1/2, 1/2): bin centres and values."""
    h = np.asarray(h, dtype=np.float64)
    nb = len(h)
    d = h / h.sum() * nb if h.sum() else h
    c = (np.arange(nb) + 0.5) / nb
    c = np.where(c >= 0.5, c - 1.0, c)
    o = np.argsort(c)
    return c[o], d[o]


def fig_phase3(pc, p2, out):
    fig, axes = plt.subplots(2, 1, figsize=(3.45, 4.3), constrained_layout=True)
    plotted = {"a": p2["a"], "b": {}}
    ax = axes[0]
    ax.axvspan(8.0, 16.0, color=PURPLE, alpha=0.12, lw=0, zorder=0)
    ax.text(11.3, 0.55, "mains\nlighting", fontsize=6.5, color=PURPLE, ha="center")
    for i, (lab, key, col, mk) in enumerate(STRATA):
        a = p2["a"][key]
        x = np.array(a["tau_ms"]) * (1.0 + 0.06 * (i - 1))
        y, lo, hi = (np.array(a[k]) for k in ("cos", "lo", "hi"))
        ax.errorbar(x, y, yerr=[y - lo, hi - y], color=col, marker=mk, ms=3.2, lw=0.9, capsize=1.5,
                    elinewidth=0.6, label=lab, zorder=3)
        ax.plot(a["tau_ms"], a["null_cos"], color=MUTED, marker=mk, ms=2.2, lw=0, mfc="white", mew=0.5, zorder=2)
    ref = p2["a"]["shared_model_mean_cos"]
    ax.axhline(ref, color=INK, lw=0.8, ls="--", zorder=1)
    ax.text(0.14, ref - 0.03, "locked: shared phases (model)", fontsize=6.5, va="top", color=INK)
    ax.axhline(0.0, color=MUTED, lw=0.6, zorder=1)
    ax.text(0.14, 0.03, "uniform: independent phases", fontsize=6.5, va="bottom", color=MUTED)
    ax.set_xscale("log")
    ax.set_xlim(0.12, 33)
    ax.set_ylim(-0.08, 1.02)
    ax.set_xlabel(r"spacing $\tau_i$ of the target pixel (ms)")
    ax.set_ylabel(r"phase lock, mean $\cos 2\pi u$")
    ax.legend(fontsize=6.5, frameon=False, loc="center left", bbox_to_anchor=(0.0, 0.52))
    _clean(ax)
    _label(ax, "(a)")
    ax = axes[1]
    top = 3.4
    for cond, ls, lab in (("shared", "--", "model, shared"), ("independent", ":", "model, independent")):
        c, d = _centred(pc["model_phase"][cond]["hist"])
        ax.step(c, np.minimum(d, top), where="mid", color=INK, lw=0.9, ls=ls, label=lab, zorder=2)
        plotted["b"][f"model_{cond}"] = {"u": c.tolist(), "density": d.tolist()}
        if d.max() > top:
            ax.text(-0.13, top - 0.1, f"peak {d.max():.1f}", fontsize=6.5, va="top", ha="right")
    null = np.sum([pc["strata"][k]["hist"]["null"] for _, k, _, _ in STRATA], axis=0)
    c, d = _centred(null)
    ax.step(c, d, where="mid", color=MUTED, lw=1.6, alpha=0.5, label="random times", zorder=1)
    plotted["b"]["null"] = {"u": c.tolist(), "density": d.tolist()}
    for lab, key, col, mk in STRATA:
        c, d = _centred(pc["strata"][key]["hist"]["pred"])
        z = pc["strata"][key]["rayleigh"]["pred"]["mean_Z"]
        ax.step(c, d, where="mid", color=col, lw=1.0, label=fr"{lab.replace('eTraM, ', '')}, $\bar Z={z:.2f}$",
                zorder=3)
        plotted["b"][key] = {"u": c.tolist(), "density": d.tolist(), "mean_Z": z}
    ax.set_xlim(-0.5, 0.5)
    ax.set_ylim(0, top)
    ax.set_xlabel(r"position $u$ of moved events in the target train")
    ax.set_ylabel("density")
    ax.legend(fontsize=6.0, frameon=False, loc="upper right", ncol=1, handlelength=1.6)
    _clean(ax)
    _label(ax, "(b)")
    _finish(fig, out / "fig_phase3", plotted)


def compare(rec, true):
    """0 none, 1 both with the same sign, 2 recorded only (or opposite sign), 3 reconstruction only."""
    out = np.zeros(true.shape, dtype=np.int64)
    both = (rec != 0) & (true != 0)
    same = both & (np.sign(rec) == np.sign(true))
    out[same] = 1
    out[(true != 0) & ~same] = 2
    out[(rec != 0) & (true == 0)] = 3
    return out


def _tag(ax, s):
    ax.text(0.02, 0.03, s, transform=ax.transAxes, fontsize=6.5, ha="left", va="bottom",
            bbox=dict(boxstyle="square,pad=0.15", fc="white", ec="none", alpha=0.85))


def fig_tolerance_compact2(demo_dir, out, stratum="day", slc=2):
    meta = json.loads((Path(demo_dir) / "demo.json").read_text())[stratum]
    img = np.load(Path(demo_dir) / "demo.npz")
    starts = meta["frame_starts_us"]
    span = starts[1] - starts[0]
    t0 = starts[slc - 1]
    true_slice = img[f"{stratum}_recorded"][slc]
    h, w = true_slice.shape
    fig, axes = plt.subplots(3, len(RECS), figsize=(7.16, 3 * 7.16 / len(RECS) * h / w + 0.75),
                             constrained_layout=True)
    cmap = matplotlib.colormaps["RdBu_r"]
    cmap_d = ListedColormap([BG, MATCH, MISSED, EXTRA])
    plotted = {"stratum": stratum, "slice_us": [t0, t0 + span], "crop": meta["crop"], "recs": {}}
    for c, (name, title) in enumerate(RECS):
        rec = meta["recs"][name]
        fr = img[f"{stratum}_{name}"]
        for r, frame in ((0, fr[0]), (1, fr[slc])):
            axes[r, c].imshow(np.clip(frame, -1, 1), cmap=cmap, vmin=-1.6, vmax=1.6, interpolation="nearest")
        b = rec["bits_per_event"]
        axes[0, c].set_title(title + ("" if b is None else f"\n{b:.2f} bit/event"), fontsize=7)
        if name != "recorded":
            _tag(axes[0, c], fr"$F={rec['F']['k3']:.2f}$ on $T_0/3$")
            _tag(axes[1, c], fr"$F={rec['F']['k32']:.2f}$ on $T_0/32$")
        ax = axes[2, c]
        if name == "recorded":
            ax.axis("off")
            ax.legend(handles=[Patch(color=MATCH, label="event in both"), Patch(color=MISSED, label="missed"),
                               Patch(color=EXTRA, label="extra")], loc="center", frameon=False, fontsize=7)
            plotted["recs"][name] = {"bits_per_event": b, "F": rec["F"]}
        else:
            d = compare(fr[slc], true_slice)
            ax.imshow(d, cmap=cmap_d, vmin=-0.5, vmax=3.5, interpolation="nearest")
            n = {k: int((d == v).sum()) for k, v in (("both", 1), ("missed", 2), ("extra", 3))}
            _tag(ax, f"in both {n['both']}\nmissed {n['missed']}, extra {n['extra']}")
            plotted["recs"][name] = {"bits_per_event": b, "F": rec["F"], "pixels": n}
        for r in range(3):
            axes[r, c].set_xticks([]); axes[r, c].set_yticks([])
            for sp in axes[r, c].spines.values():
                sp.set_linewidth(0.4)
    axes[0, 0].set_ylabel("whole window", fontsize=7)
    axes[1, 0].set_ylabel(f"{t0 / 1000:.1f} to {(t0 + span) / 1000:.1f} ms", fontsize=7)
    axes[2, 1].set_ylabel("against the\nrecorded slice", fontsize=7)
    _finish(fig, Path(out) / "fig_tolerance_compact2", plotted)


def fig_hevc2(hc, fr, out):
    t1 = hc["tables"]["1_prediction_lossless"]
    t2 = hc["tables"]["2_prediction_lossy"]
    t3 = hc["tables"]["3_decode_errors"]
    grids = (("s1_k3", r"$\Delta_t=T_0/3$", "o"), ("s1_k64", r"$\Delta_t=T_0/64$", "s"))
    fig, axes = plt.subplots(3, 3, figsize=(7.16, 5.6), sharex=True, constrained_layout=True)
    plotted = {}
    for j, (lab, key, col, _) in enumerate(STRATA):
        plotted[key] = {}
        for g, glab, mk in grids:
            cell = t2[key][g]["qp"]
            bP = np.array([cell[f"qp{q}"]["b"]["median"] for q in QPS])
            FP = np.array([cell[f"qp{q}"]["F"]["median"] for q in QPS])
            bI = np.array([cell[f"qp{q}_intra"]["b"]["median"] for q in QPS])
            FI = np.array([cell[f"qp{q}_intra"]["F"]["median"] for q in QPS])
            shade = col if g == "s1_k64" else MUTED
            ax = axes[0, j]
            ax.plot(bP, FP, color=shade, marker=mk, ms=2.6, lw=1.0)
            ax.plot(bI, FI, color=shade, marker=mk, ms=2.6, lw=1.0, ls="--", mfc="white")
            bq = t1[key][g]["b_sparse"]["median"]
            ax.plot(bq, 1.0, marker="*", ms=6, color=shade, ls="", zorder=4)
            rem = np.array([t3[key][g][f"qp{q}"]["shares"]["removed1"]["median"] for q in QPS])
            axes[1, j].plot(bP, rem, color=shade, marker=mk, ms=2.6, lw=1.0)
            fq = fr[key][g]
            bF = np.array([fq[f"qp{q}"]["b"] for q in QPS])
            me = np.array([fq[f"qp{q}"]["tasks"]["start"]["motion_error_px"] for q in QPS])
            axes[2, j].plot(bF, me, color=shade, marker=mk, ms=2.6, lw=1.0)
            plotted[key][g] = {"qp": list(QPS), "b_P": bP.tolist(), "F_P": FP.tolist(), "b_intra": bI.tolist(),
                               "F_intra": FI.tolist(), "b_voxel_list": bq, "removed1": rem.tolist(),
                               "b_frontier": bF.tolist(), "motion_error_px": me.tolist()}
        axes[0, j].set_title(lab, fontsize=8)
    for i, ylab in enumerate(("fidelity $F$", "single events removed\n(share of input)",
                              "motion error\n(px per window)")):
        axes[i, 0].set_ylabel(ylab)
        for j in range(3):
            ax = axes[i, j]
            ax.set_xscale("log")
            _clean(ax)
            if i == 2:
                ax.set_xlabel("bits per event")
    for j in range(3):
        axes[0, j].set_ylim(0, 1.03)
        axes[1, j].set_ylim(-0.02, 1.0)
        axes[2, j].set_ylim(0, None)
    for i, s in enumerate("abc"):
        _label(axes[i, 0], f"({s})")
    handles = [Line2D([], [], color=MUTED, marker="o", ms=2.6, lw=1.0, label=r"$\Delta_t=T_0/3$"),
               Line2D([], [], color=INK, marker="s", ms=2.6, lw=1.0, label=r"$\Delta_t=T_0/64$ (stratum color)"),
               Line2D([], [], color=INK, lw=1.0, label="P pictures"),
               Line2D([], [], color=INK, lw=1.0, ls="--", label="intra only"),
               Line2D([], [], color=INK, marker="*", ms=6, ls="", label="voxel list, lossless")]
    fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=5, fontsize=7, frameon=False)
    _finish(fig, out / "fig_hevc2", plotted)


def main(argv=None):
    ap = argparse.ArgumentParser()
    for k in ("pc", "hd", "hc", "demo", "paper", "out"):
        ap.add_argument(f"--{k}", required=True)
    a = ap.parse_args(argv)
    load = lambda d, f: json.loads((Path(d) / f).read_text())
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    pc, hc = load(a.pc, "report.json"), load(a.hc, "report.json")
    fig_moved2(pc, hc, out)
    fig_phase3(pc, load(a.paper, "fig_phase2.json"), out)
    fig_tolerance_compact2(a.demo, out)
    fig_hevc2(hc, load(a.hd, "frontier.json"), out)


if __name__ == "__main__":
    main()
