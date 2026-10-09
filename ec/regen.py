"""Regeneration fidelity of in-box events (directive 002). Reference implementation.

Question. A receiver that holds the events of an object over the last ``T2`` and
its motion regenerates the object's next events by moving the old ones. How much
of what a receiver computes from the true events does it reproduce, with no bits
spent on the new events?

For one evaluation instant ``t_e`` and lead ``D`` (the windows and the support are
those of ``ec.motion.evaluate_instant``):

* truth ``F``: every event with pixel in the support ``S`` and time in
  ``W = [t_e + D, t_e + D + T2)``;
* source: the events of ``[t_e - T2, t_e)`` inside the interpolated label box
  dilated by ``margin_px``;
* a model moves each source event ``(x, y, t, p)`` to ``(x', y', t + D + T2, p)``.
  The time shift is the same for every event, so the regenerated times fill ``W``;
* regenerated set ``P``: the moved events whose pixel ``(rint(x'), rint(y'))`` lies
  in ``S``;
* receiver representation: counts per voxel, a voxel being a block of ``s`` x ``s``
  pixels (blocks aligned to the sensor origin), one of ``k`` equal time bins of
  ``W``, and a polarity;
* fidelity: ``F1 = 2 sum(min(c_P, c_F)) / (N_P + N_F)``, with precision
  ``sum(min) / N_P`` and recall ``sum(min) / N_F``. This is the largest share of
  events that can be paired one to one within a voxel.

Models:

* ``static``: ``(x', y') = (x, y)``. The receiver repeats the last window in place;
* ``cmax``: ``(x', y') = (x, y) + v (D + T2)`` with the velocity that directive 001
  estimated from ``[t_e - T1, t_e)``. Causal;
* ``label``: the box map from the label box at ``t`` to the label box at
  ``t + D + T2`` (translation and scale). Reads future boxes, a reference only;
* ``uniform``: as many events as the source holds, uniform over ``S``, ``W`` and
  polarity. The chance level of the voxel grid.
"""
from __future__ import annotations

import math

import numpy as np

from .annotations import Track, in_box_mask

BLOCKS_PX = (1, 2, 4)
TIME_BINS = (1, 3, 8, 32)
MIN_SOURCE_EVENTS = 50
MIN_FUTURE_EVENTS = 50
UNIFORM_SEED = 20261009


def voxel_f1(px, py, pt, pp, fx, fy, ft, fp, w0_us: int, T2_us: int, s: int, k: int) -> dict:
    """Histogram intersection of two event sets on the (s px, T2 / k, polarity) voxel grid."""
    def keys(x, y, t, p):
        bx = np.asarray(x, dtype=np.int64) // s
        by = np.asarray(y, dtype=np.int64) // s
        bt = np.minimum(k - 1, ((np.asarray(t, dtype=np.int64) - int(w0_us)) * k) // int(T2_us))
        return ((by * (1 << 20) + bx) * 64 + bt) * 2 + np.asarray(p, dtype=np.int64)

    n_p, n_f = len(px), len(fx)
    if n_p == 0 or n_f == 0:
        return {"f1": 0.0, "precision": 0.0, "recall": 0.0, "n_pred": n_p, "n_true": n_f}
    kp, cp = np.unique(keys(px, py, pt, pp), return_counts=True)
    kf, cf = np.unique(keys(fx, fy, ft, fp), return_counts=True)
    _, ip, jf = np.intersect1d(kp, kf, assume_unique=True, return_indices=True)
    m = float(np.minimum(cp[ip], cf[jf]).sum())
    return {"f1": 2.0 * m / (n_p + n_f), "precision": m / n_p, "recall": m / n_f, "n_pred": n_p, "n_true": n_f}


def move_label(x, y, t_us, shift_us: int, track: Track):
    """Box map from the label box at each event's time to the label box ``shift_us`` later."""
    t = np.asarray(t_us, dtype=np.float64)
    bx, by, bw, bh = track.box(t)
    rx, ry, rw, rh = track.box(t + float(shift_us))
    xm = (rx + 0.5 * rw) + (np.asarray(x, dtype=np.float64) - (bx + 0.5 * bw)) * (rw / np.maximum(bw, 1e-9))
    ym = (ry + 0.5 * rh) + (np.asarray(y, dtype=np.float64) - (by + 0.5 * bh)) * (rh / np.maximum(bh, 1e-9))
    return xm, ym


def evaluate_regen(t_us, x, y, p, track: Track, t_e_us: int, D_us: int, T2_us: int, width: int, height: int,
                   v_cmax, T1_us: int = 100_000, margin_px: float = 2.0,
                   models=("static", "cmax", "label", "uniform")) -> dict:
    """All quantities of one evaluation instant and lead. ``t_us`` must be nondecreasing.

    ``v_cmax`` is ``(cmax_vx, cmax_vy)`` of the same instant from directive 001.
    """
    t_us = np.asarray(t_us, dtype=np.int64)
    w0, w1 = int(t_e_us + D_us), int(t_e_us + D_us + T2_us)
    shift = int(D_us + T2_us)
    if t_e_us - T1_us < track.t_first or w1 > track.t_last:
        return {"skipped": "outside_track_life"}
    # support and truth: identical to ec.motion.evaluate_instant
    v_lab = track.velocity(t_e_us, T1_us)
    speed_lab = math.hypot(*v_lab)
    bx, by, bw, bh = (float(a) for a in track.box(0.5 * (w0 + w1)))
    grow = margin_px + 0.5 * speed_lab * T2_us * 1e-6
    sx0 = max(0, int(math.floor(bx - grow))); sx1 = min(width - 1, int(math.ceil(bx + bw + grow)))
    sy0 = max(0, int(math.floor(by - grow))); sy1 = min(height - 1, int(math.ceil(by + bh + grow)))
    if sx1 < sx0 or sy1 < sy0:
        return {"skipped": "support_outside_sensor"}
    b0, b1 = np.searchsorted(t_us, (w0, w1))
    fxa, fya = np.asarray(x[b0:b1]), np.asarray(y[b0:b1])
    fm = (fxa >= sx0) & (fxa <= sx1) & (fya >= sy0) & (fya <= sy1)
    ft, fx, fy, fp = t_us[b0:b1][fm], fxa[fm], fya[fm], np.asarray(p[b0:b1])[fm]
    # source: the last T2 before t_e, inside the label box
    a0, a1 = np.searchsorted(t_us, (t_e_us - T2_us, t_e_us))
    sm = in_box_mask(track, t_us[a0:a1], x[a0:a1], y[a0:a1], margin_px)
    st = t_us[a0:a1][sm]
    sx, sy, sp = np.asarray(x[a0:a1])[sm], np.asarray(y[a0:a1])[sm], np.asarray(p[a0:a1])[sm]
    if len(st) < MIN_SOURCE_EVENTS:
        return {"skipped": "source_too_small", "n_source": int(len(st)), "n_future": int(len(ft))}
    if len(ft) < MIN_FUTURE_EVENTS:
        return {"skipped": "future_too_small", "n_source": int(len(st)), "n_future": int(len(ft))}
    out = {"n_source": int(len(st)), "n_future": int(len(ft)), "support_px": (sx1 - sx0 + 1) * (sy1 - sy0 + 1),
           "speed_label": speed_lab}
    for model in models:
        if model == "static":
            xm, ym, tm, pm = sx.astype(np.float64), sy.astype(np.float64), st + shift, sp
        elif model == "cmax":
            xm = sx + float(v_cmax[0]) * shift * 1e-6
            ym = sy + float(v_cmax[1]) * shift * 1e-6
            tm, pm = st + shift, sp
        elif model == "label":
            xm, ym = move_label(sx, sy, st, shift, track)
            tm, pm = st + shift, sp
        elif model == "uniform":
            rng = np.random.default_rng((UNIFORM_SEED, int(track.track_id), int(t_e_us), int(D_us)))
            n = len(st)
            xm = rng.integers(sx0, sx1 + 1, n).astype(np.float64)
            ym = rng.integers(sy0, sy1 + 1, n).astype(np.float64)
            tm = rng.integers(w0, w1, n)
            pm = rng.integers(0, 2, n)
        else:
            raise ValueError(model)
        ix, iy = np.rint(xm).astype(np.int64), np.rint(ym).astype(np.int64)
        keep = (ix >= sx0) & (ix <= sx1) & (iy >= sy0) & (iy <= sy1)
        ix, iy, tm, pm = ix[keep], iy[keep], np.asarray(tm)[keep], np.asarray(pm)[keep]
        out[f"{model}_n_pred"] = int(keep.sum())
        for s in BLOCKS_PX:
            for k in TIME_BINS:
                r = voxel_f1(ix, iy, tm, pm, fx, fy, ft, fp, w0, T2_us, s, k)
                out[f"{model}_f1_s{s}_k{k}"] = r["f1"]
                if (s, k) == (2, 3):
                    out[f"{model}_precision"] = r["precision"]
                    out[f"{model}_recall"] = r["recall"]
    return out
