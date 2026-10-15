# Directive 023. The figures of the experiments: moved counts, the phase test, HEVC

| | |
|---|---|
| track | `paper figures`, short name `pf` |
| population | none: committed files only |
| results directory | `results/paper/` |
| report | `docs/directives/reports/023.md` |
| runs after | directive 022 (`DONE`, report at `464ac60`) |

## 1. Why

The manuscript's experiments now rest on directives 019, 021 and 022. Their numbers sit in tables and
paragraphs. Three figures carry them, one per claim:

- **`fig_moved`, the model.** Moved counts follow Eq. (binfidmoved). The P pictures of x265 beat a voxel
  list only where the bin is long against the event spacing.
- **`fig_phase`, recordings.** The position of moved events inside the true train is uniform for pixels with
  a spacing below 4 ms, as independent phases imply. It locks only in the band of mains lighting.
- **`fig_hevc`, recordings.** Fidelity, removed single events and box fidelity against bits, for P pictures
  and intra pictures, on a slice of a third and of a sixty-fourth of a window.

## 2. Disclosure

The director drew the three figures from the committed `results/hd/`, `results/hc/` and `results/ph/` files
at `464ac60`, to check the layout. No number is computed beyond means of committed values.

## 3. Author decisions

**D-023-1, default: authorized.** The executor adds `scripts/fig_route_a.py` with the content of Appendix A,
unchanged.

## 4. What to run

```
python3 scripts/fig_route_a.py --hd results/hd --hc results/hc --ph results/ph --out results/paper
```

## 5. Acceptance checks

1. `scripts/fig_route_a.py` has the SHA-256 of Section 6, and `python3 -m pytest -q -p no:anyio` passes with
   no skipped test.
2. `results/paper/fig_moved`, `fig_phase` and `fig_hevc` exist as PDF, PNG and JSON. These JSON values equal
   the source tables at the paths that the docstring of Appendix A names:
   - in `fig_phase.json`, `a.<stratum>.cos`;
   - in `fig_hevc.json`, `F_P` of `s1_k64`.
3. No file under `results/paper/` other than these nine changed, and nothing outside `results/paper/` and
   `scripts/fig_route_a.py` changed.

## 6. Files

SHA-256 of the file content, which is the text between the fence lines of its appendix, ending in one
newline.

| file | SHA-256 |
|---|---|
| `scripts/fig_route_a.py` | `05dd57cb9aee29a266f3c2476757e9d66bfc9c96225cfbd5ffda1595c1867507` |

## 7. The report

The header and the checks.

## Appendix A. `scripts/fig_route_a.py`

Normative. The executor commits this file unchanged.

````python
"""Directive 023: the figures of the manuscript's experiments, drawn from committed files only.

  python3 scripts/fig_route_a.py --hd results/hd --hc results/hc --ph results/ph --out results/paper

Nothing is computed here but ratios, means over committed sums and percentages. Each figure is written as
PDF and PNG, with its plotted values as JSON.

fig_moved   The model of directive 019 (D3) and 021 (Table 5), one-pixel voxels. (a) The fidelity of the
            counts of the previous window moved by the true motion against dt / tau, for n = 1 and n = 3
            and every tau, from ``hd/report.json#/tables/4_model`` (``oracle_F``); lines: Eq. (binfid),
            min(dt / tau, 1), and Eq. (binfidmoved) for n = 1 and 3 where dt <= tau / 2. (b) Lossless bits
            per event against dt / tau for n = 3, for tau = 1 ms (solid) and 4 ms (dashed), every slice count k:
            the P pictures of x265 with one intra picture and P pictures (``b_lossless_P``), x265 with intra
            pictures only (``b_lossless_intra``) and the voxel list (``b_sparse``), from
            ``hc/report.json#/tables/5_model``.

fig_phase   Directive 022, moving blocks, flicker 0. (a) The mean of cos(2 pi u) of the prediction per bin
            of the pixel's spacing tau_i, per stratum, with the 95% bootstrap interval, from
            ``ph/report.json#/tables/1_phase/<stratum>/moving_by_tau_bin``; the null in grey; a dashed
            line at the mean over the shared-phase model scenes (``tables/5_model``); vertical lines at 8.33
            and 10 ms. Bins with fewer than 1,000 pixels are left out. (b) The histogram of u, as a density,
            pooled over speeds and over the tau_i bins below 4 ms, per stratum, and of the null over all
            strata, from ``ph/curves.json``.

fig_hevc    Directives 019 and 021, recordings, medians over recordings. Columns: eTraM by day, at night,
            DSEC. Rows: (a) F against bits per event of x265 with P pictures (solid) and intra pictures
            only (dashed), on (1 px, 1/3 window) and (1 px, 1/64 window), over the QP ladder, from
            ``hc/report.json#/tables/2_prediction_lossy``, with the voxel list at F = 1 (star, from
            ``tables/1_prediction_lossless``); (b) the share of the input events in voxels of one event that
            the P-picture decode removes (``removed1``), against the same bits, from ``tables/3_decode_errors``;
            (c) the mean box fidelity of the P-picture decode against its bits, placement ``start``, from
            ``hd/frontier.json``.
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

BLUE, ORANGE, AQUA = "#2a78d6", "#d6542a", "#1baf7a"      # the colors of scripts/paper_figures.py
PURPLE = "#8a5cc2"
INK, MUTED, FAINT = "#0b0b0b", "#6f6e69", "#e4e3dd"
STRATA = (("eTraM, day", "day", BLUE, "o"), ("eTraM, night", "night", AQUA, "^"), ("DSEC", "all", ORANGE, "s"))
T0_US = 1e6 / 30
QPS = (12, 14, 16, 18, 20, 22, 24, 28)
TAU_EDGES_MS = np.geomspace(0.125, 32.0, 9)
MIN_PIXELS = 1000
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


def fig_moved(hd, hc, out):
    m4 = hd["tables"]["4_model"]
    m5 = hc["tables"]["5_model"]
    fig, axes = plt.subplots(2, 1, figsize=(3.45, 4.3), constrained_layout=True)
    ax = axes[0]
    plotted = {"a": {}, "b": {}}
    for n, mk, face in ((1, "o", "white"), (3, "o", INK)):
        rows = sorted((c["dt_over_tau"], c["oracle_F"]) for c in m4.values() if c["n"] == n and c["s"] == 1)
        r, f = np.array(rows).T
        ax.plot(r, f, mk, ms=3.0, mfc=face, mec=INK, mew=0.6, ls="", zorder=3, label=f"moved counts, $n={n}$")
        plotted["a"][f"n{n}"] = {"dt_over_tau": r.tolist(), "F": f.tolist()}
    rr = np.geomspace(0.04, 200, 400)
    ax.plot(rr, np.minimum(rr, 1.0), color=MUTED, lw=0.9, ls=":", zorder=2, label=r"$\min(\Delta_t/\tau,1)$")
    rs = np.geomspace(0.04, 0.5, 100)
    for n, ls in ((1, "--"), (3, "-")):
        ax.plot(rs, rs - rs ** 2 / (3 * n), color=BLUE, lw=0.9, ls=ls, zorder=2, label=f"Eq. (binfidmoved), $n={n}$")
    ax.set_xscale("log")
    ax.set_xlim(0.04, 200)
    ax.set_ylim(0, 1.05)
    ax.set_xlabel(r"$\Delta_t/\tau$")
    ax.set_ylabel(r"fidelity $F$")
    ax.legend(fontsize=6.5, frameon=False, loc="lower right")
    _clean(ax)
    _label(ax, "(a)")
    ax = axes[1]
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
    _finish(fig, out / "fig_moved", plotted)


def fig_phase(ph, phc, out):
    t1 = ph["tables"]["1_phase"]
    centers = np.sqrt(TAU_EDGES_MS[:-1] * TAU_EDGES_MS[1:])
    fig, axes = plt.subplots(2, 1, figsize=(3.45, 4.3), constrained_layout=True)
    ax = axes[0]
    plotted = {"a": {}, "b": {}}
    for i, (lab, key, col, mk) in enumerate(STRATA):
        rows = t1[key]["moving_by_tau_bin"]
        x, y, lo, hi, x0, y0 = [], [], [], [], [], []
        for b, row in enumerate(rows):
            if row["pred"]["pixels"] < MIN_PIXELS:
                continue
            c = row["pred"]["cos"]
            cb = np.sqrt(row["tau_lo_us"] * row["tau_hi_us"]) / 1000.0
            if not np.isclose(cb, centers[b]):
                raise AssertionError("tau bins differ from ec.phase.TAU_EDGES")
            x.append(centers[b] * (1.0 + 0.06 * (i - 1)))
            y.append(c["value"]); lo.append(c["ci95"][0]); hi.append(c["ci95"][1])
            x0.append(centers[b]); y0.append(row["null"]["cos"]["value"])
        y, lo, hi = map(np.array, (y, lo, hi))
        ax.errorbar(x, y, yerr=[y - lo, hi - y], color=col, marker=mk, ms=3.2, lw=0.9, capsize=1.5, elinewidth=0.6,
                    label=lab, zorder=3)
        ax.plot(x0, y0, color=MUTED, marker=mk, ms=2.2, lw=0, mfc="white", mew=0.5, zorder=2)
        plotted["a"][key] = {"tau_ms": [float(v) for v in x0], "cos": y.tolist(), "lo": lo.tolist(), "hi": hi.tolist(),
                             "null_cos": [float(v) for v in y0]}
    shared = [c["cos_pooled"] for c in ph["tables"]["5_model"].values() if c["shared"]]
    ref = float(np.mean(shared))
    ax.axhline(ref, color=INK, lw=0.8, ls="--", zorder=1)
    ax.text(0.14, ref - 0.03, "shared phases (model)", fontsize=6.5, va="top", color=INK)
    ax.axhline(0.0, color=MUTED, lw=0.6, zorder=1)
    for p in (1000 / 120, 10.0):
        ax.axvline(p, color=PURPLE, lw=0.7, ls=":", zorder=1)
    ax.text(9.1, 0.62, "mains\nlighting", fontsize=6.5, color=PURPLE, ha="center")
    ax.set_xscale("log")
    ax.set_xlim(0.12, 33)
    ax.set_ylim(-0.08, 1.02)
    ax.set_xlabel(r"spacing $\tau_i$ of the target pixel (ms)")
    ax.set_ylabel(r"mean $\cos 2\pi u$")
    ax.legend(fontsize=6.5, frameon=False, loc="center left")
    plotted["a"]["shared_model_mean_cos"] = ref
    _clean(ax)
    _label(ax, "(a)")
    ax = axes[1]
    below = int(np.searchsorted(TAU_EDGES_MS, 4.0))           # tau bins with an upper edge <= 4 ms
    edges = np.linspace(0, 1, 21)
    null_tot = None
    for lab, key, col, mk in STRATA:
        h = np.asarray(phc["strata"][key]["phase"]["pred"])     # (speed, zero, flicker, tau bin, U)
        hp = h[:, 0, 0, :below].sum(axis=(0, 1))
        dens = hp / hp.sum() * len(hp)
        ax.stairs(dens, edges, color=col, lw=1.0, label=lab)
        hn = np.asarray(phc["strata"][key]["phase"]["null"])[:, 0, 0, :below].sum(axis=(0, 1))
        null_tot = hn if null_tot is None else null_tot + hn
        plotted["b"][key] = {"density": dens.tolist(), "pixels": int(hp.sum())}
    dn = null_tot / null_tot.sum() * len(null_tot)
    ax.stairs(dn, edges, color=MUTED, lw=0.8, ls="--", label="random times")
    plotted["b"]["null"] = {"density": dn.tolist(), "pixels": int(null_tot.sum())}
    ax.axhline(1.0, color=MUTED, lw=0.5)
    ax.set_xlim(0, 1)
    ax.set_ylim(0.8, 1.2)
    ax.set_xlabel(r"position $u$ of the moved events in the train, $\tau_i<4$ ms")
    ax.set_ylabel("density")
    ax.legend(fontsize=6.5, frameon=False, ncol=2, loc="upper center")
    _clean(ax)
    _label(ax, "(b)")
    _finish(fig, out / "fig_phase", plotted)


def fig_hevc(hc, fr, out):
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
            ax.plot(bP, FP, color=shade, marker=mk, ms=2.6, lw=1.0, label=f"P pictures, {glab}")
            ax.plot(bI, FI, color=shade, marker=mk, ms=2.6, lw=1.0, ls="--", mfc="white", label=f"intra only, {glab}")
            bq = t1[key][g]["b_sparse"]["median"]
            ax.plot(bq, 1.0, marker="*", ms=6, color=shade, ls="", zorder=4)
            rem = np.array([t3[key][g][f"qp{q}"]["shares"]["removed1"]["median"] for q in QPS])
            axes[1, j].plot(bP, rem, color=shade, marker=mk, ms=2.6, lw=1.0)
            fq = fr[key][g]
            bF = np.array([fq[f"qp{q}"]["b"] for q in QPS])
            box = np.array([fq[f"qp{q}"]["tasks"]["start"]["box_F_mean"] for q in QPS])
            axes[2, j].plot(bF, box, color=shade, marker=mk, ms=2.6, lw=1.0)
            plotted[key][g] = {"qp": list(QPS), "b_P": bP.tolist(), "F_P": FP.tolist(), "b_intra": bI.tolist(),
                               "F_intra": FI.tolist(), "b_voxel_list": bq, "removed1": rem.tolist(),
                               "b_frontier": bF.tolist(), "box_F": box.tolist()}
        axes[0, j].set_title(lab, fontsize=8)
    for i, ylab in enumerate(("fidelity $F$", "single events removed\n(share of input)", "box fidelity")):
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
        axes[2, j].set_ylim(0, 1.0)
    for i, s in enumerate("abc"):
        _label(axes[i, 0], f"({s})")
    handles = [Line2D([], [], color=MUTED, marker="o", ms=2.6, lw=1.0, label=r"$\Delta_t=T_0/3$"),
               Line2D([], [], color=INK, marker="s", ms=2.6, lw=1.0, label=r"$\Delta_t=T_0/64$ (stratum color)"),
               Line2D([], [], color=INK, lw=1.0, label="P pictures"),
               Line2D([], [], color=INK, lw=1.0, ls="--", label="intra only"),
               Line2D([], [], color=INK, marker="*", ms=6, ls="", label="voxel list, lossless")]
    fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=5, fontsize=7, frameon=False)
    _finish(fig, out / "fig_hevc", plotted)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--hd", required=True)
    ap.add_argument("--hc", required=True)
    ap.add_argument("--ph", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    load = lambda d, f: json.loads((Path(d) / f).read_text())
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    hd, hc, ph = load(a.hd, "report.json"), load(a.hc, "report.json"), load(a.ph, "report.json")
    fig_moved(hd, hc, out)
    fig_phase(ph, load(a.ph, "curves.json"), out)
    fig_hevc(hc, load(a.hd, "frontier.json"), out)


if __name__ == "__main__":
    main()
````
