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
