"""Directive 024: event frames of one recorded object, as recorded and as received at three timing tolerances.

  python3 scripts/fig_tolerance.py --demo results/td --out results/paper

DEMO holds ``demo.json`` (the metrics of ``ec.tolerance_demo.demo`` per stratum, without the images) and
``demo.npz`` (the frames, key ``<stratum>_<rec>``, shape (frames, height, width)). For each stratum present,
one row per reconstruction (recorded; every event; motion and one number per pixel; motion only); the first
column is the whole window, the others are short slices: the signed event count, red for positive and blue
for negative polarity.
Each row is labelled with its bits per event and F at T0 / 32. Written as fig_tolerance.{pdf,png,json}.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

RECS = (("recorded", "recorded"), ("every", "small tolerance:\nevery event"),
        ("pixel", "medium tolerance:\none number per pixel"), ("motion", "large tolerance:\nmotion only"))
STRATA = (("day", "eTraM, day"), ("night", "eTraM, night"), ("all", "DSEC"))
plt.rcParams.update({"font.family": "serif", "font.size": 8, "axes.linewidth": 0.6, "pdf.fonttype": 42,
                     "mathtext.fontset": "cm"})


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    meta = json.loads((Path(a.demo) / "demo.json").read_text())
    img = np.load(Path(a.demo) / "demo.npz")
    strata = [(k, lab) for k, lab in STRATA if k in meta]
    n_f = img[f"{strata[0][0]}_recorded"].shape[0]
    fig, axes = plt.subplots(len(RECS) * len(strata), n_f, figsize=(7.16, 1.2 * len(RECS) * len(strata)),
                             constrained_layout=True, squeeze=False)
    cmap = matplotlib.colormaps["RdBu_r"]
    plotted = {}
    for si, (key, lab) in enumerate(strata):
        m = meta[key]
        starts = m["frame_starts_us"]
        plotted[key] = {"crop": m["crop"], "n_true": m["n_true"], "frame_starts_us": starts, "recs": {}}
        for ri, (name, title) in enumerate(RECS):
            rec = m["recs"][name]
            fr = img[f"{key}_{name}"]
            row = si * len(RECS) + ri
            for c in range(n_f):
                ax = axes[row, c]
                ax.imshow(np.clip(fr[c], -1, 1), cmap=cmap, vmin=-1.6, vmax=1.6, interpolation="nearest")
                ax.set_xticks([]); ax.set_yticks([])
                for sp in ax.spines.values():
                    sp.set_linewidth(0.4)
                if row == 0:
                    span = starts[1] - starts[0]
                    ax.set_title("whole window, 33.3 ms" if c == 0 else
                                 f"{starts[c - 1] / 1000:.1f} to {(starts[c - 1] + span) / 1000:.1f} ms", fontsize=7)
            b = rec["bits_per_event"]
            info = ("" if b is None else f"{b:.2f} bit/event, ") + f"$F={rec['F']['k32']:.2f}$"
            label = (f"{lab}\n" if ri == 0 else "") + f"{title}\n{info}"
            axes[row, 0].set_ylabel(label, fontsize=6.5, rotation=0, ha="right", va="center", labelpad=4)
            plotted[key]["recs"][name] = {"bits_per_event": b, "F": rec["F"], "n": rec["n"]}
    out = Path(a.out) / "fig_tolerance"
    fig.savefig(str(out) + ".pdf", bbox_inches="tight", pad_inches=0.02)
    fig.savefig(str(out) + ".png", dpi=220, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)
    Path(str(out) + ".json").write_text(json.dumps(plotted, indent=1) + "\n")


if __name__ == "__main__":
    main()
