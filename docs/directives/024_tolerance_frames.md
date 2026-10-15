# Directive 024. What a receiver sees: event frames of one object at three timing tolerances

| | |
|---|---|
| track | `tolerance demo`, short name `td` |
| population | one group per stratum, chosen by the rule of Section 4 among the groups of directive 022 |
| results directory | `results/td/` and `results/paper/fig_tolerance.*` |
| report | `docs/directives/reports/024.md` |
| runs after | directive 023 |

## 1. Why

The theory has three regimes. With a small timing tolerance, a code describes every event time. With a
medium one, it describes one number per pixel. With a large one, it describes only the edge and its
motion. The manuscript states the bits of each regime, but a reader cannot see what each regime delivers.

This directive builds a practical reconstruction for each regime from recorded events, for one object per
stratum, and draws the event frames that a receiver would display:

- **Every event:** times in bins of `T0 / 256`, coded by coder Q.
- **Motion and one number per pixel:** the events of the previous window moved along the motion of their
  block, with one coded time offset per pixel.
- **Motion only:** the moved events alone.

The frames are drawn over the whole window and over four slices of about 2 ms. Over the whole window
the three reconstructions look alike. In the short slices, the events of the pixels appear where their
timing puts them.

## 2. Disclosure

The director wrote `ec/tolerance_demo.py`, `scripts/fig_tolerance.py` and `tests/test_tolerance_demo_gate.py`,
and ran them on the model only (320 x 240 pixels, `tau = 2 ms`, `n = 3`, 6.5 px per window). With
independent phases:

| reconstruction | bits per event | F on (1 px, T0 / 32) |
|---|---|---|
| every event | 9.98 | 1.00 |
| one number per pixel | 1.71 | 0.79 |
| motion only | 0.07 | 0.46 |

With shared phases, motion only reaches F = 0.84.

The motion fit is that of `ec.phase` (directive 022), unchanged. The suite passes (167 tests). The director
read no recording.

## 3. Author decisions

**D-024-1, default: authorized.** The executor adds the three files with the content of Appendices A to C,
unchanged.

**D-024-2, default: authorized.** The runner may reuse the group list, event reads and track loading of
`scripts/ph_run.py` and `scripts/hd_run.py`. Labels are read as in directives 017 to 022: eTraM annotations of
the population, and DSEC-Detection with the time base of directive 017.

## 4. Choice of the object

For each stratum (eTraM by day, eTraM at night, DSEC), among the groups of directive 022 and their window
`w + 1`:

1. take the boxes of `ec.regions.boxes_at(tracks, w + 1, W, H)`;
2. count the events of window `w + 1` inside each box, after the hot-pixel rule of `ec.threshold`;
3. choose the box with the most events, ties to the earliest recording in population order, then the
   smallest `w`, then the smallest track id.

The report names the recording, `w`, the track id and the box.

## 5. What to run

For each stratum:

    d = ec.tolerance_demo.demo(events, w, W, H, box)

`events` covers `[(w - 3) T0, (w + 2) T0)`, as in directive 022. Then:

    ec.tolerance_demo.save({"day": d_day, "night": d_night, "all": d_dsec}, "results/td")
    python3 scripts/fig_tolerance.py --demo results/td --out results/paper

## 6. Acceptance checks

1. The three files have the SHA-256 of Section 7, and the suite passes with no skipped test.
2. `results/td/demo.json`, `results/td/demo.npz` and `results/paper/fig_tolerance.{pdf,png,json}` exist. For
   every stratum, the `recorded` row has F = 1 on every grid.
3. No eTraM val or test file was opened, and the annotation root was not listed. Nothing outside
   `results/td/` and `results/paper/fig_tolerance.*` changed under `results/`.

The report gives the choice of Section 4 and, per stratum and reconstruction, the bits per event and F on
the three grids.

## 7. Files

The SHA-256 is that of the file content: the text between the fence lines of its appendix, ending in one
newline.

| file | SHA-256 |
|---|---|
| `ec/tolerance_demo.py` | `49fb29448179410fd324a3a76a918fb0920306f7b9875698e1110585ddf13e0c` |
| `scripts/fig_tolerance.py` | `0e07a35a2aa86aa9ca1b6a36a3687c061623cfbccd2b14035a1a44a7c8c6e853` |
| `tests/test_tolerance_demo_gate.py` | `3a03e38c04d236e57bbb46b4631d995c25ec6686b0d0f2176b7d475dcd5e48d2` |

## Appendix A. `ec/tolerance_demo.py`

````python
"""What a receiver gets from a recorded object at three timing tolerances (directive 024).

The theory has three regimes: below the jitter the code describes every event time; above it one number
per pixel; beyond the event spacing nothing but the edge and its motion. This module builds a practical
reconstruction for each regime from the recorded events of one window, inside a crop around one object:

- ``every``: every event, its time quantized to bins of ``T0 / K_EVERY``, coded by coder Q of
  ``ec.blockcodec`` on the cell (1, K_EVERY) and placed at the middle of its bin;
- ``pixel``: the events of the previous window moved along the motion of their block, with one number per
  target pixel and polarity: the offset of its first true event from its first moved event, rounded to
  OFFSET_STEP, which shifts all its moved events, or a symbol that deletes them when the pixel has no true
  event; the numbers are coded with Zstandard;
- ``motion``: the moved events alone; only the motion is sent.

The crop is the box, cut to its central MAX_BOX pixels if larger, with a margin of MARGIN pixels. Hot pixels
(the rule of ``ec.threshold``) are removed from the recorded events before anything else.

The motion is that of ``ec.phase``: per block of B pixels, the shift chosen on the pair (w - 1, w) and the
onset delay, applied to window w to predict window w + 1. Its parameters (dx, dy, delay in us) for the blocks
that meet the crop are coded with Zstandard, and their bits count for ``pixel`` and ``motion``. Bits are per
true event of the crop. The fidelity F of Eq. (fid) is measured inside the crop on (1 px, T0 / k) for every
k of F_KS. The images are event frames, as an event camera is usually shown: the signed count per pixel
(positive minus negative polarity), first over the whole window, then in N_FRAMES consecutive slices of
FRAME_US each, centred in the window. The whole window hides the timing; a short slice shows it: when the
events of a pixel come at the wrong time, they appear in the wrong slice.
"""
from __future__ import annotations

import numpy as np
import zstandard

from . import blockcodec as bc
from . import hevcdiag as hd
from . import phase as ph
from . import threshold as th

T0 = bc.T0_US
B = th.B
K_EVERY = 256
OFFSET_STEP = T0 // 64
DELETE = np.iinfo(np.int16).min
F_KS = (3, 32, 256)
MARGIN = 16
LEVEL = 19
MAX_BOX = (240, 180)
N_FRAMES = 4
FRAME_US = T0 // 16


def clip_box(box, max_wh=MAX_BOX):
    """The central part of a box (x, y, w, h) of at most ``max_wh`` pixels."""
    x, y, w, h = box
    cw, ch = min(w, max_wh[0]), min(h, max_wh[1])
    return x + (w - cw) / 2.0, y + (h - ch) / 2.0, cw, ch


def crop_of(box, width: int, height: int, margin: int = MARGIN):
    """Integer crop (x0, y0, x1, y1) around a box (x, y, w, h), with a margin, clipped to the sensor."""
    x, y, w, h = box
    x0, y0 = max(0, int(np.floor(x)) - margin), max(0, int(np.floor(y)) - margin)
    x1, y1 = min(width, int(np.ceil(x + w)) + margin), min(height, int(np.ceil(y + h)) + margin)
    return x0, y0, x1, y1


def _in(ev, crop):
    x0, y0, x1, y1 = crop
    t, x, y, p = ev
    s = (x >= x0) & (x < x1) & (y >= y0) & (y < y1)
    return t[s], x[s], y[s], p[s]


def _local(ev, crop, w0: int):
    """Events relative to the crop origin and to the window start."""
    t, x, y, p = ev
    return t - w0, x - crop[0], y - crop[1], p


def _zbits(arr) -> int:
    return 8 * len(zstandard.ZstdCompressor(level=LEVEL).compress(np.ascontiguousarray(arr).tobytes()))


def motion_prediction(ev, w: int, width: int, height: int, crop, radius: int = ph.RADIUS):
    """Window w moved to window w + 1 along the motion of every block that meets the crop.

    Returns the moved events inside the crop, and the parameters (dx, dy, delay) of those blocks."""
    ev = tuple(np.asarray(a, dtype=np.int64) for a in ev)
    span = th._window(ev, max(0, w - th.SPAN_BEFORE) * T0, (w + 1) * T0)
    hot = th.hot_pixels(span, width, height)
    keep = ~hot[ev[2] * width + ev[1]]
    ev = tuple(a[keep] for a in ev)
    win = {m: th._window(ev, (w + m) * T0, (w + m + 1) * T0) for m in (-1, 0)}
    by = {m: th._ByBlock(win[m], width, height) for m in (-1, 0)}
    reach = -(-radius // B)
    nbx = -(-width // B)
    x0, y0, x1, y1 = crop
    parts, params = [], []
    for by0 in range((y0 // B) * B, y1, B):
        for bx0 in range((x0 // B) * B, x1, B):
            b = (by0 // B) * nbx + bx0 // B
            a_prev, a_ref = by[-1].around(b, reach), by[0].around(b, reach)
            fit_true = th._in_block(a_ref, bx0, by0)
            d, pairs, _ = ph.choose_shift(ph.shift_scores(a_prev, fit_true, bx0, by0, radius), radius)
            if pairs < th.N_MIN / 2:
                d, delta = (0, 0), 0
            else:
                delta = ph.onset_delay(th._moved(a_prev, d, 0, bx0, by0, w * T0), fit_true, w * T0, width)
            params.append((d[0], d[1], delta))
            parts.append(th._moved(a_ref, d, delta, bx0, by0, (w + 1) * T0))
    pred = tuple(np.concatenate([q[i] for q in parts]) for i in range(4))
    o = np.argsort(pred[0], kind="stable")
    pred = _in(tuple(a[o] for a in pred), crop)
    return pred, np.asarray(params, dtype=np.int32)


def pixel_offsets(pred, true, width: int):
    """``pred`` with one offset per pixel and polarity (see the module docstring), and the coded symbols."""
    kq, kt = ph._pk(pred, width), ph._pk(true, width)
    uq, iq = np.unique(kq, return_inverse=True)
    first_q = np.full(len(uq), np.iinfo(np.int64).max)
    np.minimum.at(first_q, iq, pred[0])
    ut, it = np.unique(kt, return_inverse=True)
    first_t = np.full(len(ut), np.iinfo(np.int64).max)
    np.minimum.at(first_t, it, true[0])
    pos = np.searchsorted(ut, uq)
    has = (pos < len(ut)) & (ut[np.minimum(pos, len(ut) - 1)] == uq)
    off = np.where(has, first_t[np.minimum(pos, len(ut) - 1)] - first_q, 0)
    sym = np.where(has, np.clip(np.round(off / OFFSET_STEP), -32767, 32767), DELETE).astype(np.int16)
    keep = sym[iq] != DELETE
    shift = sym.astype(np.int64)[iq] * OFFSET_STEP
    out = (pred[0][keep] + shift[keep], pred[1][keep], pred[2][keep], pred[3][keep])
    o = np.argsort(out[0], kind="stable")
    return tuple(a[o] for a in out), sym


def every_event(true, crop, w1: int, k: int = K_EVERY):
    """Every true event of the crop on (1, k), placed at the middle of its bin, and the bits of coder Q."""
    cw, ch = crop[2] - crop[0], crop[3] - crop[1]
    tl, xl, yl, pl = _local(true, crop, w1)
    buf = bc.encode_events_Q(tl, xl, yl, pl, (1, k), cw, ch)
    key, cnt = hd.voxel_counts([(tl + w1, xl, yl, pl)], w1 // T0, 1, 1, k, cw, ch)
    ev = hd.voxels_to_windows(key, cnt, w1 // T0, 1, 1, k, cw, ch, "center")[0]
    return (ev[0], ev[1] + crop[0], ev[2] + crop[1], ev[3]), 8 * len(buf)


def frames(ev, crop, w1: int):
    """Signed event frames of the crop, shape (1 + N_FRAMES, height, width): the whole window, then the
    slices; and the slice starts in us."""
    cw, ch = crop[2] - crop[0], crop[3] - crop[1]
    t, x, y, p = _local(ev, crop, w1)
    start = T0 // 2 - N_FRAMES * FRAME_US // 2
    f = (t - start) // FRAME_US
    s = (f >= 0) & (f < N_FRAMES)
    img = np.zeros((1 + N_FRAMES, ch, cw))
    np.add.at(img, (np.zeros(len(t), dtype=np.int64), y, x), np.where(p > 0, 1.0, -1.0))
    np.add.at(img, (1 + f[s], y[s], x[s]), np.where(p[s] > 0, 1.0, -1.0))
    return img, [int(start + i * FRAME_US) for i in range(N_FRAMES)]


def fidelity(true, rec, crop, w1: int) -> dict:
    cw, ch = crop[2] - crop[0], crop[3] - crop[1]
    a, b = _local(true, crop, w1), _local(rec, crop, w1)
    out = {}
    for k in F_KS:
        s = hd.sums_on((a[0] + w1, a[1], a[2], a[3]), (b[0] + w1, b[1], b[2], b[3]), w1, (1, k), cw, ch)
        out[f"k{k}"] = 2.0 * s["M"] / (s["N"] + s["N2"]) if s["N"] + s["N2"] else float("nan")
    return out


def demo(ev, w: int, width: int, height: int, box) -> dict:
    """The three reconstructions of window w + 1 inside the crop around ``box``, with images and metrics."""
    ev = tuple(np.asarray(a, dtype=np.int64) for a in ev)
    span = th._window(ev, max(0, w - th.SPAN_BEFORE) * T0, (w + 1) * T0)
    keep = ~th.hot_pixels(span, width, height)[ev[2] * width + ev[1]]   # hot pixels out of every row
    ev = tuple(a[keep] for a in ev)
    crop = crop_of(clip_box(box), width, height)
    w1 = (w + 1) * T0
    true = _in(th._window(ev, w1, w1 + T0), crop)
    n = len(true[0])
    if n == 0:
        raise ValueError("no event in the crop")
    every, b_every = every_event(true, crop, w1)
    motion, params = motion_prediction(ev, w, width, height, crop)
    b_motion = _zbits(params)
    pixel, sym = pixel_offsets(motion, true, width)
    b_pixel = b_motion + _zbits(sym)
    out = {"crop": [int(c) for c in crop], "n_true": int(n), "w": int(w), "recs": {}}
    for name, rec, bits in (("recorded", true, None), ("every", every, b_every), ("pixel", pixel, b_pixel),
                            ("motion", motion, b_motion)):
        img, starts = frames(rec, crop, w1)
        out["recs"][name] = {"n": int(len(rec[0])), "bits_per_event": None if bits is None else bits / n,
                             "F": fidelity(true, rec, crop, w1), "frames": img}
    out["frame_starts_us"] = starts
    out["n_blocks"] = int(len(params))
    out["n_pixel_symbols"] = int(len(sym))
    return out


def save(demos: dict, out_dir) -> None:
    """Write ``demo.json`` (metrics) and ``demo.npz`` (images) for ``{stratum: demo(...)}``."""
    import json
    from pathlib import Path
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    meta, arrays = {}, {}
    for key, d in demos.items():
        meta[key] = {k: v for k, v in d.items() if k != "recs"}
        meta[key]["recs"] = {}
        for name, r in d["recs"].items():
            meta[key]["recs"][name] = {k: v for k, v in r.items() if k != "frames"}
            arrays[f"{key}_{name}"] = r["frames"]
    (out / "demo.json").write_text(json.dumps(meta, indent=1) + "\n")
    np.savez_compressed(out / "demo.npz", **arrays)
````

## Appendix B. `scripts/fig_tolerance.py`

````python
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
````

## Appendix C. `tests/test_tolerance_demo_gate.py`

````python
"""Gate for directive 024: the three reconstructions of ``ec.tolerance_demo`` on constructed events and on the
model, and the figure script on their output."""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

from ec import blockcodec as bc
from ec import phase as ph
from ec import tolerance_demo as td

T0 = bc.T0_US
W, H = 320, 240
ROOT = Path(__file__).resolve().parent.parent


def _ev(rows):
    t = np.array([r[0] for r in rows], dtype=np.int64)
    x, y, p = (np.array([r[i] for r in rows], dtype=np.int64) for i in (1, 2, 3))
    o = np.argsort(t, kind="stable")
    return tuple(a[o] for a in (t, x, y, p))


def test_crop_and_box():
    assert td.crop_of((10.5, 20.0, 30.0, 40.0), W, H) == (0, 4, 57, 76)
    assert td.crop_of((300.0, 230.0, 30.0, 40.0), W, H) == (284, 214, 320, 240)
    assert td.clip_box((0.0, 0.0, 480.0, 200.0)) == (120.0, 10.0, 240, 180)
    assert td.clip_box((5.0, 6.0, 50.0, 60.0)) == (5.0, 6.0, 50.0, 60.0)


def test_every_event_keeps_every_event_in_its_bin():
    rng = np.random.default_rng(0)
    w1 = 6 * T0
    n = 3000
    crop = (40, 30, 140, 110)
    true = _ev(list(zip(w1 + rng.integers(0, T0, n), rng.integers(40, 140, n), rng.integers(30, 110, n),
                        rng.integers(0, 2, n))))
    ev, bits = td.every_event(true, crop, w1)
    assert len(ev[0]) == n and bits > 0
    f = td.fidelity(true, ev, crop, w1)
    assert f["k256"] == 1.0 and f["k32"] == 1.0
    assert np.all((ev[0] >= w1) & (ev[0] < w1 + T0))


def test_pixel_offsets_by_construction():
    true = _ev([(1000 + 2000 * k, 5, 5, 1) for k in range(3)] + [(4000, 6, 5, 1)])
    pred = _ev([(1500 + 2000 * k, 5, 5, 1) for k in range(3)] + [(9000, 7, 5, 1), (4300, 6, 5, 1)])
    out, sym = td.pixel_offsets(pred, true, W)
    step = td.OFFSET_STEP
    assert len(sym) == 3 and (sym == td.DELETE).sum() == 1
    t5 = np.sort(out[0][out[1] == 5])
    assert np.array_equal(t5, 1500 + 2000 * np.arange(3) + round(-500 / step) * step)
    assert not np.any(out[1] == 7)
    assert np.array_equal(out[0][out[1] == 6], [4300 + round(-300 / step) * step])


def test_frames():
    crop = (10, 10, 20, 15)
    s0 = T0 // 2 - td.N_FRAMES * td.FRAME_US // 2
    ev = _ev([(T0 + s0 + 10, 11, 12, 1), (T0 + s0 + 20, 11, 12, 0), (T0 + s0 + td.FRAME_US + 5, 12, 12, 1),
              (T0 + 5, 13, 12, 1)])
    img, starts = td.frames(ev, crop, T0)
    assert img.shape == (1 + td.N_FRAMES, 5, 10) and starts[0] == s0
    assert img[1, 2, 1] == 0 and img[2, 2, 2] == 1 and img[1:].sum() == 1  # the event before the slices is out
    assert img[0].sum() == 2 and img[0, 2, 3] == 1                         # the whole window holds all four


def test_the_ladder_on_the_model():
    for shared in (False, True):
        ev = ph.edge_scene_v(W, H, 6.5, 2000.0, 3, 0.05, 40, 8, 1, shared)
        d = td.demo(ev, 5, W, H, (100.0, 60.0, 120.0, 100.0))
        r = d["recs"]
        assert r["recorded"]["F"]["k256"] == 1.0
        assert r["every"]["F"]["k32"] == 1.0
        assert r["every"]["bits_per_event"] > r["pixel"]["bits_per_event"] > r["motion"]["bits_per_event"] > 0
        if shared:
            assert r["motion"]["F"]["k32"] > 0.75
        else:
            assert r["motion"]["F"]["k32"] < 0.6 < r["pixel"]["F"]["k32"] < 0.95


def test_save_and_figure(tmp_path):
    ev = ph.edge_scene_v(W, H, 6.5, 2000.0, 3, 0.05, 40, 8, 1, False)
    d = td.demo(ev, 5, W, H, (100.0, 60.0, 120.0, 100.0))
    td.save({"day": d}, tmp_path)
    meta = json.loads((tmp_path / "demo.json").read_text())
    assert meta["day"]["recs"]["pixel"]["bits_per_event"] == d["recs"]["pixel"]["bits_per_event"]
    subprocess.run([sys.executable, str(ROOT / "scripts" / "fig_tolerance.py"), "--demo", str(tmp_path), "--out",
                    str(tmp_path)], check=True)
    fig = json.loads((tmp_path / "fig_tolerance.json").read_text())
    assert fig["day"]["recs"]["motion"]["F"] == d["recs"]["motion"]["F"]
    for ext in ("pdf", "png"):
        assert (tmp_path / f"fig_tolerance.{ext}").stat().st_size > 0
````
