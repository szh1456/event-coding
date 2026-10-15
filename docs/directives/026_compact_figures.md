# Directive 026. Two figures in compact form: the phase lock and the reconstructions

| | |
|---|---|
| track | `paper figures`, short name `pf` |
| population | none: committed files only |
| results directory | `results/paper/` |
| report | `docs/directives/reports/026.md` |
| runs after | directive 025 (`DONE`, report at `ad42960`) |

## 1. Why

The author found two figures hard to read or too large.

- **`fig_phase2`.** `fig_phase` had a histogram panel that showed only flat lines. The new figure keeps the
  phase lock against the spacing, labels its two ends (uniform: independent phases; locked: shared phases),
  and shades the band of mains lighting.
- **`fig_tolerance_compact`.** `fig_tolerance` of directive 025 took a full page. The new figure shows the
  day car only, in three rows: the whole window, one slice of 2.1 ms, and that slice compared with the
  recorded one pixel by pixel. The comparison marks the pixels that match, those the reconstruction misses
  and those it adds.

The existing figures stay as they are.

## 2. Disclosure

The director drew both figures from the committed `results/ph/` and `results/td2/` files at `ad42960` to
check the layout. No number is computed beyond counts of pixels in the comparison.

## 3. Author decisions

**D-026-1, default: authorized.** The executor adds `scripts/fig_revise.py` with the content of Appendix A,
unchanged.

## 4. What to run

```
python3 scripts/fig_revise.py --ph results/ph --demo results/td2 --out results/paper
```

## 5. Acceptance checks

1. `scripts/fig_revise.py` has the SHA-256 of Section 6, and the suite passes with no skipped test.
2. `results/paper/fig_phase2` and `results/paper/fig_tolerance_compact` exist as PDF, PNG and JSON.
   - In `fig_phase2.json`, `a.<stratum>.cos` equals `fig_phase.json`.
   - In `fig_tolerance_compact.json`, `recs.<rec>.F` equals `results/td2/demo.json` for the day stratum.
3. No other file under `results/` changed, and nothing outside `results/paper/` and
   `scripts/fig_revise.py` changed.

## 6. Files

SHA-256 of the file content, which is the text between the fence lines of its appendix, ending in one
newline.

| file | SHA-256 |
|---|---|
| `scripts/fig_revise.py` | `aa34626405eb8c5ba8acd87a3a2a4eac805a18039b626462a0cff5d77da717f0` |

## 7. The report

The header and the checks.

## Appendix A. `scripts/fig_revise.py`

Normative. The executor commits this file unchanged.

````python
"""Directive 026: revised figures of the manuscript, drawn from committed files only.

  python3 scripts/fig_revise.py --ph results/ph --demo results/td2 --out results/paper

fig_phase2   Directive 022, moving blocks, flicker 0. The phase lock, the mean of cos(2 pi u) of the
             prediction, per bin of the pixel's spacing tau_i and per stratum, with the 95% bootstrap interval
             (``ph/report.json#/tables/1_phase/<stratum>/moving_by_tau_bin``); random times in grey; the
             mean over the shared-phase model scenes (``tables/5_model``) as a dashed line; the band of 8 to
             16 ms shaded, which holds the periods of mains lighting. Bins with fewer than 1,000 pixels are
             left out.

fig_tolerance_compact
             Directive 025, eTraM by day. Columns: recorded, every event, motion and one number per pixel,
             motion only. Rows: the whole window; the slice of 14.6 to 16.7 ms (frame 2 of the npz); the
             slice compared pixel by pixel with the recorded slice: grey where both have an event of the
             same sign, purple where only the recording has one (missed), orange where only the
             reconstruction has one (extra). Column titles: bits per event and F at T0 / 32.
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
from matplotlib.patches import Patch

BLUE, ORANGE, AQUA = "#2a78d6", "#d6542a", "#1baf7a"
PURPLE = "#8a5cc2"
INK, MUTED, FAINT = "#0b0b0b", "#6f6e69", "#e4e3dd"
STRATA = (("eTraM, day", "day", BLUE, "o"), ("eTraM, night", "night", AQUA, "^"), ("DSEC", "all", ORANGE, "s"))
TAU_EDGES_MS = np.geomspace(0.125, 32.0, 9)
MIN_PIXELS = 1000
RECS = (("recorded", "recorded"), ("every", "small tolerance:\nevery event"),
        ("pixel", "medium tolerance:\none number per pixel"), ("motion", "large tolerance:\nmotion only"))
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


def fig_phase2(ph, out):
    t1 = ph["tables"]["1_phase"]
    centers = np.sqrt(TAU_EDGES_MS[:-1] * TAU_EDGES_MS[1:])
    fig, ax = plt.subplots(1, 1, figsize=(3.45, 2.3), constrained_layout=True)
    plotted = {"a": {}}
    ax.axvspan(8.0, 16.0, color=PURPLE, alpha=0.12, lw=0, zorder=0)
    ax.text(11.3, 0.55, "mains\nlighting", fontsize=6.5, color=PURPLE, ha="center")
    for i, (lab, key, col, mk) in enumerate(STRATA):
        x, y, lo, hi, x0, y0 = [], [], [], [], [], []
        for b, row in enumerate(t1[key]["moving_by_tau_bin"]):
            if row["pred"]["pixels"] < MIN_PIXELS:
                continue
            cb = np.sqrt(row["tau_lo_us"] * row["tau_hi_us"]) / 1000.0
            if not np.isclose(cb, centers[b]):
                raise AssertionError("tau bins differ from ec.phase.TAU_EDGES")
            c = row["pred"]["cos"]
            x.append(centers[b] * (1.0 + 0.06 * (i - 1)))
            y.append(c["value"]); lo.append(c["ci95"][0]); hi.append(c["ci95"][1])
            x0.append(centers[b]); y0.append(row["null"]["cos"]["value"])
        y, lo, hi = map(np.array, (y, lo, hi))
        ax.errorbar(x, y, yerr=[y - lo, hi - y], color=col, marker=mk, ms=3.2, lw=0.9, capsize=1.5, elinewidth=0.6,
                    label=lab, zorder=3)
        ax.plot(x0, y0, color=MUTED, marker=mk, ms=2.2, lw=0, mfc="white", mew=0.5, zorder=2)
        plotted["a"][key] = {"tau_ms": [float(v) for v in x0], "cos": y.tolist(), "lo": lo.tolist(),
                             "hi": hi.tolist(), "null_cos": [float(v) for v in y0]}
    ref = float(np.mean([c["cos_pooled"] for c in ph["tables"]["5_model"].values() if c["shared"]]))
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
    plotted["a"]["shared_model_mean_cos"] = ref
    _clean(ax)
    _finish(fig, out / "fig_phase2", plotted)


def compare(rec, true):
    """0 none, 1 both with the same sign, 2 recorded only (or opposite sign), 3 reconstruction only."""
    out = np.zeros(true.shape, dtype=np.int64)
    both = (rec != 0) & (true != 0)
    same = both & (np.sign(rec) == np.sign(true))
    out[same] = 1
    out[(true != 0) & ~same] = 2
    out[(rec != 0) & (true == 0)] = 3
    return out


def fig_tolerance_compact(demo_dir, out, stratum="day", slc=2):
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
        axes[0, c].set_title(f"{title}\n" + ("" if b is None else f"{b:.2f} bit/event, ") +
                             f"$F={rec['F']['k32']:.2f}$", fontsize=7)
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
            plotted["recs"][name] = {"bits_per_event": b, "F": rec["F"], "pixels": n}
        for r in range(3):
            axes[r, c].set_xticks([]); axes[r, c].set_yticks([])
            for sp in axes[r, c].spines.values():
                sp.set_linewidth(0.4)
    axes[0, 0].set_ylabel("whole window", fontsize=7)
    axes[1, 0].set_ylabel(f"{t0 / 1000:.1f} to {(t0 + span) / 1000:.1f} ms", fontsize=7)
    axes[2, 1].set_ylabel("against the\nrecorded slice", fontsize=7)
    _finish(fig, Path(out) / "fig_tolerance_compact", plotted)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--ph", required=True)
    ap.add_argument("--demo", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    load = lambda f: json.loads((Path(a.ph) / f).read_text())
    fig_phase2(load("report.json"), out)
    fig_tolerance_compact(a.demo, out)


if __name__ == "__main__":
    main()
````
