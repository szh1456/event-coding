# Directive 028. Figures and statistics of the restructured manuscript: the controlled model, the recordings, and the coding case

| | |
|---|---|
| track | `phase control, figures`, short name `pc2` |
| population | the outputs of directives 019, 021, 022 and 027; nothing is read from a recording unless Section 4 says so |
| results directory | `results/pc2/`, and figures in `results/paper/` |
| report | `docs/directives/reports/028.md` |
| runs after | directive 027 (it reads `results/pc/report.json`) |

## 1. Why

The manuscript is being restructured around its rate-distortion result. Each experimental figure now answers
one question, and each statistic it shows must be defined before it is drawn.

- **`fig_control` (Fig. 3)** answers "does the phase cause moved events to miss?" with synthetic data only:
  the controlled model of directive 027.
- **`fig_recordings` (Fig. 4)** answers "what do recordings show about the same mechanism, and on which
  events?". It has three panels:
  - the phase lock against the spacing;
  - the histogram of `u` with the per-block Rayleigh statistic;
  - the fidelity of moved counts against `dt / tau_i` on regular trains, with its coverage.
- **`fig_coding` (Fig. 6)** answers "what does this mean for a standard coder?". It has three parts:
  - the lossless bits of x265 on the model;
  - F against bits on recordings;
  - a motion task on recordings in which **failed estimates count as failures**.

Two statistics need to be checked or recomputed rather than redrawn:

- **The motion error.** `motion_error_px` in `results/hd/frontier.json` is a median over the squares whose
  velocity could be estimated (`nanmedian` in `scripts/fm_reduce.py`). Squares whose decode leaves no usable
  events drop out of it, so it describes successful estimates only.
- **The binned fidelity on recordings.** Before it is plotted against Eq. (binfidmoved), its selection,
  its unit and its weights must be stated.

The figures of directive 027 stay as produced. The manuscript uses these three and
`fig_tolerance_compact2`.

## 2. Disclosure

The director wrote the two files of the appendices and ran them only on constructed inputs and on the committed
`results/hc` and `results/paper` files. The suite passes.

The director has seen two committed results before setting any threshold of this directive:

- Table 2 of report 022 (binned fidelity with `tau_reg`);
- the medians `motion_error_px` and `motion_no_event` in `results/hd/frontier.json`.

The plotting rule (at least 10,000 true events and 5 recordings per bin) and the success threshold of the
motion task (1 px per window) were set after seeing those values. They were not set after seeing the
statistics of Section 4, which do not exist yet.

The director notes one observation from Table 2 of report 022, to be confirmed or corrected by Section 4A.
At `r` near 1/8 the pooled fidelity lies close to the equation. For `r >= 1/2` it stays near 0.2 to 0.4, far
below `min(r, 1)`. The report must explain this from the definitions rather than leave it to the reader.

## 3. Author decisions

**D-028-1, default: authorized.** The executor adds `scripts/fig_028.py` and `tests/test_fig_028_gate.py`
with the content of Appendices A and B, unchanged.

**D-028-2, default: authorized.** The executor writes the code that produces the two files of Section 4,
following its definitions. The module layout is free.

**D-028-3, default: as stated in Sections 4 to 8.**

## 4. Definitions

### 4A. `results/pc2/binned_fidelity.json`

**Source.** The per-group sums of directive 022: `sums["reg"]`, with `flicker = 0` and the speed classes
pooled, on the grids (1, 32) and (1, 64), per bin of `r = dt / tau_reg` (`ec.threshold.R_EDGES`).

If the per-group outputs of 022 are no longer on the hosts, recompute them with
`ec.phase.evaluate_group` on the 022 groups, within the cost limit of Section 7.

**Layout.**

```
{"definitions": {...},
 "strata": {"day" | "night" | "all": {
     "coverage": {"share_events_with_tau_reg": ..., "share_events_in_plotted_bins": ...,
                  "denominator": "<what the shares are of>"},
     "grids": {"s1_k32" | "s1_k64": [
         {"bin": .., "r_lo": .., "r_hi": .., "r_centre": .., "N": .., "N2": .., "M": .., "M0": ..,
          "F": .., "F_ci95": [lo, hi], "F0": .., "n_recordings": ..}, ...]}}}}
```

**Statistics.**

- `N`, `N2`, `M` and `M0` are summed over all groups and recordings of the stratum.
- `F = 2M / (N + N2)` and `F0 = 2 M0 / (N + N2)`, so the pooled value is weighted by events.
- `F_ci95` is from a bootstrap over recordings of the pooled `F`: 2,000 resamples, seed 20261016.
- `n_recordings` counts the recordings with `N > 0` in the bin.
- `r_centre` is the bin centre of report 022.
- `share_events_in_plotted_bins` uses the rule of `fig_028.py` (`N >= 10,000` and `n_recordings >= 5`), on
  the grid (1, 32).

**What the report states, under "Definitions", from the code and not from memory:**

1. The span from which `tau_reg` is estimated, and whether it excludes the scored window.
2. Which events enter `N`, `N2` and `M`:
   - the true events of window `w + 1` in the pixel-polarities that have a `tau_reg`;
   - the moved events in those pixel-polarities;
   - whether a pixel-polarity with true events and no moved event, or the reverse, enters, and how.
3. How the motion of the prediction was obtained: estimated, causal, the rule of `ec.phase`. It is therefore
   not the exact motion that Eq. (binfidmoved) assumes.
4. Which events the denominator of the coverage shares counts.
5. For each `r` range (below 1/4, 1/4 to 1/2, above 1/2), whether Eq. (binfidmoved) applies, and what in
   the definitions explains the distance between `F` and the equation or `min(r, 1)`. Such causes include:
   - trains shorter than the bin;
   - pixels with true and no moved events;
   - count mismatch;
   - the estimated motion.

   Where the report cannot attribute the distance, it says so.

### 4B. `results/pc2/motion_task.json`

**Source.** The per-square records of directive 019 (`ec.families._Tasks.run`, key `motion`), placement
`start`. Use two sets of records:

- D1: the P-picture decodes at every QP of `scripts/fm_reduce.py`;
- D2: the uncoded representation, as reference.

Both on the grids (1, 3) and (1, 64), per stratum. If the per-group outputs of 019 are no longer on the hosts,
recompute the tasks for these operating points with the code path of directive 019 Section 5, within the cost
limit of Section 7.

**Classification of each square:**

- **undefined** when the velocity on the true events is not finite. Such a square is excluded and counted
  in `n_undefined`.
- **failure** when the velocity on the decoded events is not finite, or the decode leaves no event in the
  square. A failure counts as not recovered.
- otherwise its **error** is `error_px`.

**Layout.**

```
{"definitions": {...},
 "strata": {"day" | "night" | "all": {"s1_k3" | "s1_k64": {
     "reference": {"success1": .., "ci95": [lo, hi], "fail_share": .., "median_err": .., "n_squares": ..,
                   "n_undefined": ..},
     "qp": {"qp<q>": {"b": .., "success1": .., "ci95": [lo, hi], "fail_share": .., "median_err": ..,
                      "n_squares": .., "n_undefined": ..}}}}}}
```

**Statistics.**

- `success1` is the share of defined squares whose error is at most 1 px per window, pooled over all
  defined squares of the stratum.
- `ci95` is from a bootstrap over recordings, as in 4A.
- `fail_share` is the share of defined squares that fail.
- `median_err` is the median error with each failure counted as an infinite error, or `null` when
  `fail_share >= 0.5`.
- `b` is the median over recordings of bits per event at that operating point, as in
  `results/hd/frontier.json`. The F panels use directive 021 (one group in 40). The report states how the
  task population differs from that.

**What the report states:**

1. The definitions above as implemented.
2. The number of squares per stratum and grid.
3. Next to each `success1`, the success-only median that `motion_error_px` gave. The comparison shows
   what the earlier statistic left out.

## 5. Figures

After `results/pc/report.json` (directive 027) and the two files of Section 4 are committed:

```
python3 scripts/fig_028.py --pc results/pc --pc2 results/pc2 --hc results/hc --paper results/paper \
    --out results/paper
```

## 6. The report

For each of `fig_control`, `fig_recordings` and `fig_coding`, the report gives:

1. what each panel plots, with the file and key it comes from;
2. the definition of every statistic: unit, weighting, selection, how failures and empty cells enter;
3. the numbers behind the main features of the panel;
4. **conclusions the data support**, each with its condition (stratum, grid, range of `r` or of `tau_i`,
   share of events covered);
5. **conclusions the data do not support**, where a reader might draw them. For example:
   - a flat histogram and a mean Rayleigh statistic near 1 do not prove that the phases are uniform or
     independent; they show no detectable lock on the selected trains at the tested scale;
   - the fidelity of moved counts on recordings is measured under an estimated motion.

The director decides what the manuscript draws from it.

## 7. Cost

- Section 4 reads committed or kept outputs and should take minutes.
- If a recomputation is needed, project it from the first 10 groups of each dataset. If the projection
  exceeds 40 CPU-hours, stop and report `BLOCKED` with it.
- Use the read lock and memory guard of directive 016. Do not compete with a companion-project job.

## 8. Acceptance checks

1. The two files have the SHA-256 of Section 10, and the suite passes with no skipped test.
2. **Binned fidelity:**
   - At (1, 32), `F` of every bin equals `F_pooled` of `results/ph/report.json#/tables/2_binned_fidelity/<stratum>/reg`
     to 1e-9, where both are finite.
   - `1 - share_events_with_tau_reg` equals `share_true_events_without_tau_reg` of Table 4 of report 022 to
     1e-6, when the denominators are the same; otherwise the report says how they differ.
3. **Motion task:**
   - For every operating point, the median of the finite errors of the defined squares equals
     `motion_error_px` of `results/hd/frontier.json` to 1e-9. This checks that the records are the same.
   - `success1 + fail_share <= 1`.
4. The three figures exist in `results/paper/` as PDF, PNG and JSON. In `fig_recordings.json`,
   `c.<stratum>.coverage` equals `binned_fidelity.json`.
5. No eTraM val or test file was opened, and the annotation root was not listed. Under `results/`, nothing
   outside `results/pc2/` and the three new figures in `results/paper/` changed.

## 9. Outputs

| file | content |
|---|---|
| `results/pc2/binned_fidelity.json` | Section 4A |
| `results/pc2/motion_task.json` | Section 4B |
| `results/pc2/provenance.json` | commit, host, versions, wall and CPU time, the files read |
| `results/paper/fig_control.*`, `fig_recordings.*`, `fig_coding.*` | Section 5 |

## 10. Files

The SHA-256 is that of the file content: the text between the fence lines of its appendix, ending in one
newline.

| file | SHA-256 |
|---|---|
| `scripts/fig_028.py` | `11c302557409580ed6b555c716679d2b22192c32936ff631a4f872c895f28324` |
| `tests/test_fig_028_gate.py` | `73ffa2159b09b2001fd3c5c69864c3bceedc27d20a516597d11aeb3391e3edf8` |

## Appendix A. `scripts/fig_028.py`

Normative. The executor commits this file unchanged.

````python
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
````

## Appendix B. `tests/test_fig_028_gate.py`

Normative. The executor commits this file unchanged.

````python
"""Gate for directive 028: the figure script on constructed inputs in the layouts of Section 5, and the
committed results of directives 021 and 026."""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
STRATA = ("day", "night", "all")
QPS = (12, 14, 16, 18, 20, 22, 24, 28)


def _pc():
    control = []
    for tau in (1000.0, 4000.0):
        for c in ("shared", "independent", "jitter"):
            r = {f"k{k}": 33333.0 / k / tau for k in (1, 3, 64)}
            f = {kk: 1.0 if c == "shared" else min(v, 1.0) for kk, v in r.items()}
            control.append({"tau_us": tau, "condition": c, "F": f, "dt_over_tau": r})
    hist = {"pred": [100] * 20, "null": [100] * 20}
    st = {"hist": hist, "rayleigh": {"pred": {"mean_Z": 1.01}, "null": {"mean_Z": 0.98}}}
    return {"control": control, "strata": {k: st for k in STRATA},
            "model_phase": {"shared": {"hist": [500, 200] + [0] * 16 + [50, 300]}, "independent": {"hist": [60] * 20}}}


def _bf():
    rows = []
    for j, r in enumerate((1 / 16, 1 / 8, 1 / 4, 1 / 2, 1.0, 2.0)):
        rows.append({"r_lo": r / 1.4, "r_hi": r * 1.4, "r_centre": r, "N": 50_000 if j else 5_000, "N2": 50_000,
                     "M": 1, "F": min(r, 1.0), "F_ci95": [min(r, 1.0) - 0.01, min(r, 1.0) + 0.01], "F0": r / 2,
                     "n_recordings": 20})
    s = {"coverage": {"share_events_with_tau_reg": 0.33, "share_events_in_plotted_bins": 0.3},
         "grids": {"s1_k32": rows, "s1_k64": rows}}
    return {"definitions": {}, "strata": {k: s for k in STRATA}}


def _mt():
    g = {"reference": {"success1": 0.9, "ci95": [0.85, 0.95], "n_squares": 100, "n_undefined": 3},
         "qp": {f"qp{q}": {"b": 40.0 / (1 + i), "success1": 0.9 - 0.08 * i, "ci95": [0.85 - 0.08 * i, 0.95 - 0.08 * i],
                           "fail_share": 0.02 * i, "median_err": 0.5 + 0.1 * i, "n_squares": 100}
                for i, q in enumerate(QPS)}}
    return {"definitions": {}, "strata": {k: {"s1_k3": g, "s1_k64": g} for k in STRATA}}


def test_figures(tmp_path):
    for d, f, obj in (("pc", "report.json", _pc()), ("pc2", "binned_fidelity.json", _bf()),
                      ("pc2", "motion_task.json", _mt())):
        (tmp_path / d).mkdir(exist_ok=True)
        (tmp_path / d / f).write_text(json.dumps(obj))
    r = ROOT / "results"
    subprocess.run([sys.executable, str(ROOT / "scripts" / "fig_028.py"), "--pc", str(tmp_path / "pc"), "--pc2",
                    str(tmp_path / "pc2"), "--hc", str(r / "hc"), "--paper", str(r / "paper"), "--out",
                    str(tmp_path / "out")], check=True)
    for name in ("fig_control", "fig_recordings", "fig_coding"):
        for ext in ("pdf", "png", "json"):
            assert (tmp_path / "out" / f"{name}.{ext}").stat().st_size > 0
    fc = json.loads((tmp_path / "out" / "fig_control.json").read_text())
    assert all(v == 1.0 for v in fc["shared"]["F"])
    fr = json.loads((tmp_path / "out" / "fig_recordings.json").read_text())
    assert len(fr["c"]["day"]["s1_k32"]["F"]) == 5            # the bin with 5,000 events is left out
    assert abs(np.mean(fr["b"]["day"]["density"]) - 1.0) < 1e-9
    fg = json.loads((tmp_path / "out" / "fig_coding.json").read_text())
    assert fg["day"]["s1_k64"]["success1"][0] == 0.9 and fg["day"]["s1_k3"]["reference_success1"] == 0.9
````
