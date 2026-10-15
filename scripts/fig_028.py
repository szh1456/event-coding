"""Directive 028: the figures of the restructured manuscript, drawn from committed files only.

  python3 scripts/fig_028.py --pc results/pc --pc2 results/pc2 --hc results/hc --paper results/paper \
      --out results/paper

fig_control     The controlled model of directive 027, one panel: F of the counts moved along the true motion
                against dt / tau for shared phases, independent phases and independent phases with jitter,
                from ``pc/report.json#/control``; lines: min(dt / tau, 1) and dt / tau - dt^2 / (3 n tau^2), n = 3,
                where dt <= tau / 2.

fig_recordings  Recordings, three panels in a row. (a) The phase lock against the spacing of the target pixel,
                as ``fig_phase2`` (directive 026). (b) The histogram of u, centred on 0, per stratum, with
                random times and the two model kinds (the shared-phase peak clipped at the top of the axis), and the mean per-block Rayleigh statistic per stratum
                in the legend, from ``pc/report.json``. (c) The fidelity of the moved counts against
                dt / tau_reg, per stratum, on (1 px, T0 / 32) (filled) and (1 px, T0 / 64) (open), with 95%
                intervals and the null in grey, from ``pc2/binned_fidelity.json``; the band between
                r - r^2 / 3 and r for r <= 1/2 (Eq. (binfidmoved) for n = 1 and n -> infinity) and the line
                min(r, 1). Bins enter with at least MIN_EVENTS true events and MIN_RECORDINGS recordings.

fig_coding      x265 as a case, two rows and four columns. Column 1: the model of directive 021, lossless bits
                per event against dt / tau for n = 3, tau = 1 ms (solid) and 4 ms (dashed): P pictures, intra
                pictures only and the voxel list (``hc/report.json#/tables/5_model``). Columns 2 to 4, eTraM by
                day, at night and DSEC. Row (a): F against bits per event, P pictures (solid) and intra only
                (dashed), on (1 px, T0 / 3) (grey) and (1 px, T0 / 64) (stratum color), with the voxel list
                at F = 1 (star) (``hc/report.json#/tables/1_prediction_lossless`` and ``2_prediction_lossy``).
                Row (b): the share of squares whose motion the P-picture decode recovers within 1 px per
                window, failures counted as not recovered, against bits per event, with 95% intervals, and the
                uncoded representation on the same grid as a horizontal line, from ``pc2/motion_task.json``.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D

BLUE, ORANGE, AQUA = "#2a78d6", "#d6542a", "#1baf7a"
PURPLE = "#8a5cc2"
INK, MUTED, FAINT = "#0b0b0b", "#6f6e69", "#e4e3dd"
STRATA = (("eTraM, day", "day", BLUE, "o"), ("eTraM, night", "night", AQUA, "^"), ("DSEC", "all", ORANGE, "s"))
QPS = (12, 14, 16, 18, 20, 22, 24, 28)
CONDS = (("shared", "shared phases", INK, "s", INK), ("independent", "independent phases", BLUE, "o", BLUE),
         ("jitter", "independent phases, jitter", ORANGE, "^", "white"))
MIN_EVENTS, MIN_RECORDINGS = 10_000, 5
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


def _label(ax, s, x=-0.16):
    ax.text(x, 1.02, s, transform=ax.transAxes, fontsize=8, fontweight="bold", va="bottom")


def _theory(ax, xmin=0.04, xmax=200, band=False):
    rr = np.geomspace(xmin, xmax, 400)
    ax.plot(rr, np.minimum(rr, 1.0), color=MUTED, lw=0.9, ls=":", zorder=2, label=r"$\min(\Delta_t/\tau,1)$")
    rs = np.geomspace(xmin, 0.5, 100)
    if band:
        ax.fill_between(rs, rs - rs ** 2 / 3.0, rs, color=PURPLE, alpha=0.18, lw=0, zorder=1,
                        label=r"$\Delta_t/\tau-\Delta_t^2/(3n\tau^2)$, $n\geq1$")
    else:
        ax.plot(rs, rs - rs ** 2 / 9.0, color=BLUE, lw=0.9, zorder=2, label=r"$\Delta_t/\tau-\Delta_t^2/(3n\tau^2)$")


def fig_control(pc, out):
    fig, ax = plt.subplots(1, 1, figsize=(3.45, 2.3), constrained_layout=True)
    plotted = {}
    for cond, lab, col, mk, face in CONDS:
        pts = sorted(((c["dt_over_tau"][k], c["F"][k]) for c in pc["control"] if c["condition"] == cond
                      for k in c["F"]), key=lambda p: p[0])
        r, f = np.array(pts).T
        ax.plot(r, f, mk, ms=3.0, mfc=face, mec=col, mew=0.7, ls="", zorder=3, label=lab)
        plotted[cond] = {"dt_over_tau": r.tolist(), "F": f.tolist()}
    _theory(ax)
    ax.set_xscale("log")
    ax.set_xlim(0.04, 200)
    ax.set_ylim(0, 1.05)
    ax.set_xlabel(r"$\Delta_t/\tau$")
    ax.set_ylabel(r"fidelity $F$, true motion")
    ax.legend(fontsize=6.5, frameon=False, loc="lower right")
    _clean(ax)
    _finish(fig, out / "fig_control", plotted)


def _centred(h):
    h = np.asarray(h, dtype=np.float64)
    nb = len(h)
    d = h / h.sum() * nb if h.sum() else h
    c = (np.arange(nb) + 0.5) / nb
    c = np.where(c >= 0.5, c - 1.0, c)
    o = np.argsort(c)
    return c[o], d[o]


def fig_recordings(pc, p2, bf, out):
    fig, axes = plt.subplots(1, 3, figsize=(7.16, 2.75), constrained_layout=True)
    plotted = {"a": p2["a"], "b": {}, "c": {}}
    ax = axes[0]
    ax.axvspan(8.0, 16.0, color=PURPLE, alpha=0.12, lw=0, zorder=0)
    ax.text(11.3, 0.55, "mains\nlighting", fontsize=6.5, color=PURPLE, ha="center")
    for i, (lab, key, col, mk) in enumerate(STRATA):
        a = p2["a"][key]
        x = np.array(a["tau_ms"]) * (1.0 + 0.06 * (i - 1))
        y, lo, hi = (np.array(a[k]) for k in ("cos", "lo", "hi"))
        ax.errorbar(x, y, yerr=[y - lo, hi - y], color=col, marker=mk, ms=3.0, lw=0.9, capsize=1.5,
                    elinewidth=0.6, label=lab, zorder=3)
        ax.plot(a["tau_ms"], a["null_cos"], color=MUTED, marker=mk, ms=2.2, lw=0, mfc="white", mew=0.5, zorder=2)
    ref = p2["a"]["shared_model_mean_cos"]
    ax.axhline(ref, color=INK, lw=0.8, ls="--", zorder=1)
    ax.text(0.14, ref - 0.03, "shared phases (model)", fontsize=6.5, va="top", color=INK)
    ax.axhline(0.0, color=MUTED, lw=0.6, zorder=1)
    ax.set_xscale("log")
    ax.set_xlim(0.12, 33)
    ax.set_ylim(-0.08, 1.02)
    ax.set_xlabel(r"spacing $\tau_i$ of the target pixel (ms)")
    ax.set_ylabel(r"mean $\cos 2\pi u$")
    ax.legend(fontsize=6.0, frameon=False, loc="center left", bbox_to_anchor=(0.0, 0.55))
    _clean(ax)
    _label(ax, "(a)")
    ax = axes[1]
    top = 3.4
    hm = []
    for cond, ls, lab in (("shared", "--", "model, shared"), ("independent", ":", "model, independent")):
        c, d = _centred(pc["model_phase"][cond]["hist"])
        hm += ax.step(c, np.minimum(d, top), where="mid", color=INK, lw=0.9, ls=ls, label=lab, zorder=2)
        plotted["b"][f"model_{cond}"] = {"u": c.tolist(), "density": d.tolist(), "clipped_at": top}
    null = np.sum([pc["strata"][k]["hist"]["null"] for _, k, _, _ in STRATA], axis=0)
    c, d = _centred(null)
    hm += ax.step(c, d, where="mid", color=MUTED, lw=1.6, alpha=0.5, label="random times", zorder=1)
    plotted["b"]["null"] = {"u": c.tolist(), "density": d.tolist()}
    hs = []
    for lab, key, col, mk in STRATA:
        c, d = _centred(pc["strata"][key]["hist"]["pred"])
        z = pc["strata"][key]["rayleigh"]["pred"]["mean_Z"]
        hs.append(ax.step(c, d, where="mid", color=col, lw=1.0,
                          label=fr"{lab.replace('eTraM, ', '')}, $\bar Z={z:.2f}$", zorder=3)[0])
        plotted["b"][key] = {"u": c.tolist(), "density": d.tolist(), "mean_Z": z}
    ax.set_xlim(-0.5, 0.5)
    ax.set_ylim(0, top)
    ax.set_xlabel(r"position $u$ in the target train")
    ax.set_ylabel("density")
    ax.legend(handles=hs + hm, fontsize=6.0, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.24),
              ncol=2, handlelength=1.4, columnspacing=0.8)
    _clean(ax)
    _label(ax, "(b)")
    ax = axes[2]
    _theory(ax, 1 / 64, 8, band=True)
    for i, (lab, key, col, mk) in enumerate(STRATA):
        plotted["c"][key] = {}
        for g, face in (("s1_k32", col), ("s1_k64", "white")):
            rows = [r for r in bf["strata"][key]["grids"][g]
                    if r["N"] >= MIN_EVENTS and r["n_recordings"] >= MIN_RECORDINGS and np.isfinite(r["F"])]
            if not rows:
                continue
            x = np.array([r["r_centre"] for r in rows]) * (1.0 + 0.05 * (i - 1))
            y = np.array([r["F"] for r in rows])
            lo, hi = np.array([r["F_ci95"] for r in rows]).T
            ax.errorbar(x, y, yerr=[y - lo, hi - y], color=col, marker=mk, ms=3.0, mfc=face, mew=0.7, lw=0,
                        elinewidth=0.6, capsize=1.2, zorder=3, label=lab if g == "s1_k32" else None)
            ax.plot(x, [r["F0"] for r in rows], color=MUTED, marker=mk, ms=2.0, lw=0, mfc="white", mew=0.5,
                    zorder=2)
            plotted["c"][key][g] = {"r_centre": [r["r_centre"] for r in rows], "F": y.tolist(),
                                    "F_ci95": [r["F_ci95"] for r in rows], "F0": [r["F0"] for r in rows],
                                    "N": [r["N"] for r in rows]}
        plotted["c"][key]["coverage"] = bf["strata"][key]["coverage"]
    ax.set_xscale("log")
    ax.set_xlim(1 / 64, 8)
    ax.set_ylim(0, 1.05)
    ax.set_xlabel(r"$\Delta_t/\tau_i$, $\tau_i$ from regular trains")
    ax.set_ylabel(r"fidelity $F$ of moved counts")
    ax.legend(fontsize=5.8, frameon=False, loc="upper left")
    _clean(ax)
    _label(ax, "(c)")
    _finish(fig, out / "fig_recordings", plotted)


def fig_coding(hc, mt, out):
    t1 = hc["tables"]["1_prediction_lossless"]
    t2 = hc["tables"]["2_prediction_lossy"]
    m5 = hc["tables"]["5_model"]
    fig, axes = plt.subplots(2, 4, figsize=(7.16, 3.9), constrained_layout=True)
    plotted = {"model": {}}
    ax = axes[0, 0]
    keys = (("b_lossless_P", "P pictures", BLUE, "o"), ("b_lossless_intra", "intra only", ORANGE, "s"),
            ("b_sparse", "voxel list", INK, "^"))
    for tau, ls in ((1000, "-"), (4000, "--")):
        cells = sorted((c for c in m5.values() if c["n"] == 3 and c["s"] == 1 and c["tau"] == tau),
                       key=lambda c: c["dt_over_tau"])
        r = np.array([c["dt_over_tau"] for c in cells])
        for key, lab, col, mk in keys:
            y = np.array([c[key] for c in cells])
            ax.plot(r, y, color=col, ls=ls, lw=0.9, marker=mk, ms=2.4, mew=0, zorder=3)
            plotted["model"][f"tau{tau}_{key}"] = {"dt_over_tau": r.tolist(), "bits_per_event": y.tolist()}
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel(r"$\Delta_t/\tau$")
    ax.set_ylabel("lossless bits per event")
    ax.set_title("model", fontsize=8)
    _clean(ax)
    _label(ax, "(a)", -0.3)
    lg = axes[1, 0]
    lg.axis("off")
    handles = [Line2D([], [], color=BLUE, marker="o", ms=2.4, lw=0.9, label="P pictures"),
               Line2D([], [], color=ORANGE, marker="s", ms=2.4, lw=0.9, label="intra only"),
               Line2D([], [], color=INK, marker="^", ms=2.4, lw=0.9, label="voxel list"),
               Line2D([], [], color=MUTED, lw=0.9, label=r"model: $\tau=1$ ms"),
               Line2D([], [], color=MUTED, lw=0.9, ls="--", label=r"model: $\tau=4$ ms"),
               Line2D([], [], color=MUTED, marker="o", ms=2.4, lw=1.0, label=r"recordings: $\Delta_t=T_0/3$"),
               Line2D([], [], color=INK, marker="s", ms=2.4, lw=1.0, label=r"recordings: $\Delta_t=T_0/64$"),
               Line2D([], [], color=INK, lw=1.0, ls="--", label="intra only (row a)"),
               Line2D([], [], color=INK, lw=0.8, ls=":", label="uncoded (row b)")]
    lg.legend(handles=handles, loc="center", frameon=False, fontsize=6.3)
    grids = (("s1_k3", "o"), ("s1_k64", "s"))
    for j, (lab, key, col, _) in enumerate(STRATA, start=1):
        plotted[key] = {}
        for g, mk in grids:
            shade = col if g == "s1_k64" else MUTED
            cell = t2[key][g]["qp"]
            bP = np.array([cell[f"qp{q}"]["b"]["median"] for q in QPS])
            FP = np.array([cell[f"qp{q}"]["F"]["median"] for q in QPS])
            bI = np.array([cell[f"qp{q}_intra"]["b"]["median"] for q in QPS])
            FI = np.array([cell[f"qp{q}_intra"]["F"]["median"] for q in QPS])
            ax = axes[0, j]
            ax.plot(bP, FP, color=shade, marker=mk, ms=2.4, lw=1.0)
            ax.plot(bI, FI, color=shade, marker=mk, ms=2.4, lw=1.0, ls="--", mfc="white")
            bq = t1[key][g]["b_sparse"]["median"]
            ax.plot(bq, 1.0, marker="*", ms=6, color=shade, ls="", zorder=4)
            m = mt["strata"][key][g]
            pts = [(m["qp"][f"qp{q}"]["b"], m["qp"][f"qp{q}"]["success1"], *m["qp"][f"qp{q}"]["ci95"]) for q in QPS]
            b, s, lo, hi = np.array(pts).T
            ax = axes[1, j]
            ax.errorbar(b, s, yerr=[s - lo, hi - s], color=shade, marker=mk, ms=2.4, lw=1.0, elinewidth=0.6,
                        capsize=1.2)
            ax.axhline(m["reference"]["success1"], color=shade, lw=0.8, ls=":")
            plotted[key][g] = {"qp": list(QPS), "b_P": bP.tolist(), "F_P": FP.tolist(), "b_intra": bI.tolist(),
                               "F_intra": FI.tolist(), "b_voxel_list": bq, "b_task": b.tolist(),
                               "success1": s.tolist(), "success1_ci95": np.c_[lo, hi].tolist(),
                               "reference_success1": m["reference"]["success1"]}
        axes[0, j].set_title(lab, fontsize=8)
        for i in (0, 1):
            ax = axes[i, j]
            ax.set_xscale("log")
            ax.set_ylim(0, 1.03)
            _clean(ax)
        axes[1, j].set_xlabel("bits per event")
    axes[0, 1].set_ylabel("fidelity $F$")
    axes[1, 1].set_ylabel("motion recovered\nwithin 1 px (share)")
    _label(axes[0, 1], "(b)")
    _label(axes[1, 1], "(c)")
    _finish(fig, out / "fig_coding", plotted)


def main(argv=None):
    ap = argparse.ArgumentParser()
    for k in ("pc", "pc2", "hc", "paper", "out"):
        ap.add_argument(f"--{k}", required=True)
    a = ap.parse_args(argv)
    load = lambda d, f: json.loads((Path(d) / f).read_text())
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    pc = load(a.pc, "report.json")
    fig_control(pc, out)
    fig_recordings(pc, load(a.paper, "fig_phase2.json"), load(a.pc2, "binned_fidelity.json"), out)
    fig_coding(load(a.hc, "report.json"), load(a.pc2, "motion_task.json"), out)


if __name__ == "__main__":
    main()
