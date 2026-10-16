"""Directive 029: the figures of the manuscript after the fourth review, drawn from committed files only.

  python3 scripts/fig_029.py --st results/st --pc results/pc --pc2 results/pc2 --hc results/hc \
      --paper results/paper --out results/paper

fig_scaling     Total bits along a path of M pixels, from ``st/report.json#/paths`` (``ec.structure.path_costs``):
                every event time at D_FINE (Eq. (rdlow), line; quantizer, circles); the common shift at D_MID
                (the band of Eq. (rdmid); quantizer, squares); legends name Theorem 2, not equation labels; the parameters of the motion at (1 + XI) D_A for
                a receiver that holds the template (quantizer, triangles), with a dashed line of slope
                2 log2 M through its first point, the slope of Eq. (B) for a translation.

fig_phase4      Recordings and the power of the test, three panels in a row. (a) and (b) as ``fig_recordings``
                (directive 028). (c) The mean per-block Rayleigh statistic on the model against the lock width
                w, for cv = 0 (filled) and 0.2 (open), with 95% intervals (``st/report.json#/power``); the
                95% intervals of the recordings (``pc/report.json``) as horizontal bands; the reading
                threshold 2 as a dotted line.

fig_coding_cost x265 as a case, one row: (a) the model of directive 021, lossless bits per event against dt / tau;
                (b) to (d) F against bits per event per stratum, as ``fig_coding`` rows (a) and (b).

fig_task        The motion task per stratum, as row (c) of ``fig_coding``.
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


def _centred(h):
    h = np.asarray(h, dtype=np.float64)
    nb = len(h)
    d = h / h.sum() * nb if h.sum() else h
    c = (np.arange(nb) + 0.5) / nb
    c = np.where(c >= 0.5, c - 1.0, c)
    o = np.argsort(c)
    return c[o], d[o]


def fig_scaling(st, out):
    rows = st["paths"]["rows"]
    M = np.array([r["M"] for r in rows], dtype=np.float64)
    get = lambda k: np.array([r[k] for r in rows])
    fig, ax = plt.subplots(1, 1, figsize=(3.45, 2.6), constrained_layout=True)
    ax.plot(M, get("fine_theory_bits"), color=BLUE, lw=1.0, label="every event time, Theorem 2")
    ax.plot(M, get("fine_code_bits"), "o", color=BLUE, ms=3.0, mfc="white", mew=0.8, label="every event time, quantizer")
    ax.fill_between(M, get("scalar_lower_bits"), get("scalar_upper_bits"), color=ORANGE, alpha=0.25, lw=0,
                    label="common shift, Theorem 2 bounds")
    ax.plot(M, get("scalar_code_bits"), "s", color=ORANGE, ms=3.0, mfc="white", mew=0.8, label="common shift, quantizer")
    mb = get("motion_code_bits")
    ax.plot(M, mb, "^", color=INK, ms=3.4, label="motion parameters, quantizer")
    ax.plot(M, mb[0] + 2.0 * np.log2(M / M[0]), color=INK, lw=0.8, ls="--", label=r"slope $2\log_2M$")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel(r"pixels on the path $M$")
    ax.set_ylabel("total bits")
    ax.legend(fontsize=6.0, frameon=False, loc="upper left")
    _clean(ax)
    plotted = {"M": M.tolist(), **{k: get(k).tolist() for k in ("fine_theory_bits", "fine_code_bits",
               "scalar_lower_bits", "scalar_upper_bits", "scalar_code_bits", "motion_code_bits")},
               "motion_D_over_DA_mean": [r["motion"]["D_over_DA_mean"] for r in rows]}
    _finish(fig, out / "fig_scaling", plotted)


def fig_phase4(st, pc, p2, out):
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
    hm, hs = [], []
    for cond, ls, lab in (("shared", "--", "model, shared"), ("independent", ":", "model, independent")):
        c, d = _centred(pc["model_phase"][cond]["hist"])
        hm += ax.step(c, np.minimum(d, top), where="mid", color=INK, lw=0.9, ls=ls, label=lab, zorder=2)
        plotted["b"][f"model_{cond}"] = {"u": c.tolist(), "density": d.tolist(), "clipped_at": top}
    null = np.sum([pc["strata"][k]["hist"]["null"] for _, k, _, _ in STRATA], axis=0)
    c, d = _centred(null)
    hm += ax.step(c, d, where="mid", color=MUTED, lw=1.6, alpha=0.5, label="random times", zorder=1)
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
    for lab, key, col, mk in STRATA:
        lo, hi = pc["strata"][key]["rayleigh"]["pred"]["mean_Z_ci95"]
        ax.axhspan(lo, hi, color=col, alpha=0.22, lw=0, zorder=1)
        plotted["c"][f"recordings_{key}"] = [lo, hi]
    ax.axhline(2.0, color=MUTED, lw=0.8, ls=":", zorder=1)
    ax.text(1.0, 2.1, "reading threshold", fontsize=6.0, color=MUTED, va="bottom", ha="right")
    for cv, face in ((0.0, INK), (0.2, "white")):
        rows = sorted((r for r in st["power"]["rows"] if r["cv"] == cv), key=lambda r: r["w"])
        w = np.array([r["w"] for r in rows])
        z = np.array([r["mean_Z"] for r in rows])
        lo, hi = np.array([r["ci95"] for r in rows]).T
        ax.errorbar(w, z, yerr=[z - lo, hi - z], color=INK, marker="o", ms=3.0, mfc=face, mew=0.8, lw=0.9,
                    elinewidth=0.6, capsize=1.2, zorder=3, label=fr"model, spacing spread {cv:.1f}")
        plotted["c"][f"cv{cv}"] = {"w": w.tolist(), "mean_Z": z.tolist(), "ci95": np.c_[lo, hi].tolist()}
    ax.set_yscale("log")
    ax.set_xlim(-0.03, 1.03)
    ax.set_xlabel(r"lock width $w$")
    ax.set_ylabel(r"mean Rayleigh statistic $\bar Z$")
    ax.legend(fontsize=6.0, frameon=False, loc="upper right")
    _clean(ax)
    _label(ax, "(c)")
    _finish(fig, out / "fig_phase4", plotted)


def _model_bits(ax, m5, plotted):
    keys = (("b_lossless_P", BLUE, "o"), ("b_lossless_intra", ORANGE, "s"), ("b_sparse", INK, "^"))
    for tau, ls in ((1000, "-"), (4000, "--")):
        cells = sorted((c for c in m5.values() if c["n"] == 3 and c["s"] == 1 and c["tau"] == tau),
                       key=lambda c: c["dt_over_tau"])
        r = np.array([c["dt_over_tau"] for c in cells])
        for key, col, mk in keys:
            y = np.array([c[key] for c in cells])
            ax.plot(r, y, color=col, ls=ls, lw=0.9, marker=mk, ms=2.4, mew=0, zorder=3)
            plotted[f"tau{tau}_{key}"] = {"dt_over_tau": r.tolist(), "bits_per_event": y.tolist()}
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel(r"$\Delta_t/\tau$")
    ax.set_ylabel("lossless bits per event")
    ax.set_title("model", fontsize=8)


def fig_coding_cost(hc, out):
    t1 = hc["tables"]["1_prediction_lossless"]
    t2 = hc["tables"]["2_prediction_lossy"]
    fig, axes = plt.subplots(1, 4, figsize=(7.16, 2.35), constrained_layout=True)
    plotted = {"model": {}}
    _model_bits(axes[0], hc["tables"]["5_model"], plotted["model"])
    _clean(axes[0])
    _label(axes[0], "(a)", -0.3)
    for j, (lab, key, col, _) in enumerate(STRATA, start=1):
        plotted[key] = {}
        ax = axes[j]
        for g, mk in (("s1_k3", "o"), ("s1_k64", "s")):
            shade = col if g == "s1_k64" else MUTED
            cell = t2[key][g]["qp"]
            bP = np.array([cell[f"qp{q}"]["b"]["median"] for q in QPS])
            FP = np.array([cell[f"qp{q}"]["F"]["median"] for q in QPS])
            bI = np.array([cell[f"qp{q}_intra"]["b"]["median"] for q in QPS])
            FI = np.array([cell[f"qp{q}_intra"]["F"]["median"] for q in QPS])
            ax.plot(bP, FP, color=shade, marker=mk, ms=2.4, lw=1.0)
            ax.plot(bI, FI, color=shade, marker=mk, ms=2.4, lw=1.0, ls="--", mfc="white")
            bq = t1[key][g]["b_sparse"]["median"]
            ax.plot(bq, 1.0, marker="*", ms=6, color=shade, ls="", zorder=4)
            plotted[key][g] = {"qp": list(QPS), "b_P": bP.tolist(), "F_P": FP.tolist(), "b_intra": bI.tolist(),
                               "F_intra": FI.tolist(), "b_voxel_list": bq}
        ax.set_title(lab, fontsize=8)
        ax.set_xscale("log")
        ax.set_ylim(0, 1.03)
        ax.set_xlabel("bits per event")
        _clean(ax)
    axes[1].set_ylabel("fidelity $F$")
    _label(axes[1], "(b)")
    handles = [Line2D([], [], color=BLUE, marker="o", ms=2.4, lw=0.9, label="P pictures"),
               Line2D([], [], color=ORANGE, marker="s", ms=2.4, lw=0.9, label="intra only"),
               Line2D([], [], color=INK, marker="^", ms=2.4, lw=0.9, label="voxel list"),
               Line2D([], [], color=MUTED, lw=0.9, label=r"(a) $\tau=1$ ms"),
               Line2D([], [], color=MUTED, lw=0.9, ls="--", label=r"(a) $\tau=4$ ms"),
               Line2D([], [], color=MUTED, marker="o", ms=2.4, lw=1.0, label=r"(b) $\Delta_t=T_0/3$"),
               Line2D([], [], color=INK, marker="s", ms=2.4, lw=1.0, label=r"(b) $\Delta_t=T_0/64$"),
               Line2D([], [], color=INK, lw=1.0, ls="--", label="(b) intra only"),
               Line2D([], [], color=INK, marker="*", ms=6, ls="", label="(b) voxel list")]
    fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, 0.0), ncol=5, fontsize=6.3,
               frameon=False)
    _finish(fig, out / "fig_coding_cost", plotted)


def fig_task(mt, out):
    fig, axes = plt.subplots(1, 3, figsize=(7.16, 2.0), constrained_layout=True)
    plotted = {}
    for j, (lab, key, col, _) in enumerate(STRATA):
        ax = axes[j]
        plotted[key] = {}
        for g, mk in (("s1_k3", "o"), ("s1_k64", "s")):
            shade = col if g == "s1_k64" else MUTED
            m = mt["strata"][key][g]
            pts = [(m["qp"][f"qp{q}"]["b"], m["qp"][f"qp{q}"]["success1"], *m["qp"][f"qp{q}"]["ci95"]) for q in QPS]
            b, s, lo, hi = np.array(pts).T
            ax.errorbar(b, s, yerr=[s - lo, hi - s], color=shade, marker=mk, ms=2.4, lw=1.0, elinewidth=0.6,
                        capsize=1.2, label=(r"$\Delta_t=T_0/3$" if g == "s1_k3" else r"$\Delta_t=T_0/64$"))
            ax.axhline(m["reference"]["success1"], color=shade, lw=0.8, ls=":")
            plotted[key][g] = {"b": b.tolist(), "success1": s.tolist(), "ci95": np.c_[lo, hi].tolist(),
                               "reference_success1": m["reference"]["success1"]}
        ax.set_title(lab, fontsize=8)
        ax.set_xscale("log")
        ax.set_ylim(0, 1.03)
        ax.set_xlabel("bits per event")
        ax.legend(fontsize=6.0, frameon=False, loc="lower right")
        _clean(ax)
    axes[0].set_ylabel("motion recovered\nwithin 1 px (share)")
    _finish(fig, out / "fig_task", plotted)


def main(argv=None):
    ap = argparse.ArgumentParser()
    for k in ("st", "pc", "pc2", "hc", "paper", "out"):
        ap.add_argument(f"--{k}", required=True)
    a = ap.parse_args(argv)
    load = lambda d, f: json.loads((Path(d) / f).read_text())
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    st, pc, hc = load(a.st, "report.json"), load(a.pc, "report.json"), load(a.hc, "report.json")
    fig_scaling(st, out)
    fig_phase4(st, pc, load(a.paper, "fig_phase2.json"), out)
    fig_coding_cost(hc, out)
    fig_task(load(a.pc2, "motion_task.json"), out)


if __name__ == "__main__":
    main()
