"""Regeneration with a sender-fitted affine map (directive 004). Reference implementation.

Question. Directive 003 moves the key events of an object by one integer
displacement per target window. An object that approaches, recedes or turns also
changes its size and shape in the image. How much fidelity does the receiver gain
when the sender transmits an affine map per window, six numbers in place of two?

The windows, the support, the source (key) events and the truth are those of
``ec.gop.evaluate_target``. With ``(cx, cy)`` the center and ``hx``, ``hy`` the
half-widths of the bounding rectangle of the key events, a key event ``(x, y)`` is
moved to

    x' = x + dx + (ia / hx) (x - cx) + (ib / hy) (y - cy)
    y' = y + dy + (ic / hx) (x - cx) + (id / hy) (y - cy)

and by ``D_m + T2`` in time. The six parameters are integers. Each one is a
displacement in px at the edge of the rectangle: ``ia`` and ``id`` stretch the
object along x and y, ``ib`` and ``ic`` shear or rotate it. The receiver knows
``cx, cy, hx, hy`` from the key events. With ``ia = ib = ic = id = 0`` the map is
the translation of directive 003.

Fit. The sender maximizes the voxel F1 at the objective cell (2 px, three time
bins) by coordinate search. It has two starting points: the translation that
directive 003 sent, with zero for the other four parameters, and, from the second
target on, the map it fitted for the previous target, with its four shape
parameters scaled by the ratio of the two time shifts and the translation of
directive 003. It starts at the better one, the translation on a tie. One round
tries, in this order: a common stretch of both axes, then ``ia``, ``id``, ``ib``,
``ic``, ``dx``, ``dy``. For each it scores a set of offsets and moves only on a
strict improvement. Rounds repeat until one changes nothing. The search runs in
three stages, coarse to fine, as the displacement search of directive 003 does:
8 px blocks and one time bin with offsets up to 8, then 4 px blocks and one time
bin with offsets up to 4, then the objective cell with offsets up to 2 (STAGES).
If the result does not beat the translation at the objective cell, the
translation is kept, so the result is never worse than directive 003. The
targets of a group are fitted in the order ``m`` = 1, 2, ...
"""
from __future__ import annotations

import math

import numpy as np

from . import regen
from .annotations import Track, in_box_mask
from .gop import OBJECTIVE, lead_us

MOTION_BITS = 72                      # six signed 12-bit integers per regenerated window
# (block px, time bins), offsets, largest number of rounds
STAGES = (((8, 1), (-2, 2, -4, 4, -8, 8), 2),
          ((4, 1), (-1, 1, -2, 2, -4, 4), 2),
          (OBJECTIVE, (-1, 1, -2, 2), 4))
PARAMS = ("dx", "dy", "ia", "ib", "ic", "id")


def frame_of(sx, sy):
    """Center and half-widths of the bounding rectangle of the key events."""
    x0, x1, y0, y1 = float(np.min(sx)), float(np.max(sx)), float(np.min(sy)), float(np.max(sy))
    return 0.5 * (x0 + x1), 0.5 * (y0 + y1), max(1.0, 0.5 * (x1 - x0)), max(1.0, 0.5 * (y1 - y0))


def move_affine(sx, sy, frame, q):
    """Pixel positions of the key events under the map with integer parameters ``q`` (order of PARAMS)."""
    cx, cy, hx, hy = frame
    dx, dy, ia, ib, ic, id_ = q
    u = np.asarray(sx, dtype=np.float64) - cx
    v = np.asarray(sy, dtype=np.float64) - cy
    xm = np.asarray(sx, dtype=np.float64) + dx + (ia / hx) * u + (ib / hy) * v
    ym = np.asarray(sy, dtype=np.float64) + dy + (ic / hx) * u + (id_ / hy) * v
    return np.rint(xm).astype(np.int64), np.rint(ym).astype(np.int64)


def fit_affine(sx, sy, st, sp, fx, fy, ft, fp, w0_us: int, T2_us: int, shift_us: int, support, d_start,
               q_prev=None, shift_prev_us=None):
    """Integer parameters of the affine map that maximize the voxel F1 at the objective cell.

    ``q_prev`` and ``shift_prev_us`` are the fitted map and the time shift of the
    previous target of the same group, or None for the first target. Returns
    ``q, frame, n_evaluations``. See the module docstring for the search.
    """
    x0, x1, y0, y1 = support
    frame = frame_of(sx, sy)
    hx, hy = frame[2], frame[3]
    tm = np.asarray(st, dtype=np.int64) + int(shift_us)
    n_eval = 0

    def score(q, cell=OBJECTIVE):
        nonlocal n_eval
        n_eval += 1
        ix, iy = move_affine(sx, sy, frame, q)
        keep = (ix >= x0) & (ix <= x1) & (iy >= y0) & (iy <= y1)
        return regen.voxel_f1(ix[keep], iy[keep], tm[keep], sp[keep], fx, fy, ft, fp, w0_us, T2_us, *cell)["f1"]

    def stretched(q, k):                 # a common stretch: k px at the edge of the longer axis
        r = k / max(hx, hy)
        return (q[0], q[1], q[2] + int(np.rint(r * hx)), q[3], q[4], q[5] + int(np.rint(r * hy)))

    def bumped(q, i, k):
        return tuple(v + (k if j == i else 0) for j, v in enumerate(q))

    moves = [stretched] + [lambda q, k, i=i: bumped(q, i, k) for i in (2, 5, 3, 4, 0, 1)]
    start = (int(d_start[0]), int(d_start[1]), 0, 0, 0, 0)
    start_top = score(start)
    best = start
    if q_prev is not None:
        r = float(shift_us) / float(shift_prev_us)
        warm = (start[0], start[1]) + tuple(int(np.rint(r * v)) for v in q_prev[2:])
        if warm != start and score(warm) > start_top:
            best = warm
    for cell, offsets, max_rounds in STAGES:
        top = score(best, cell)
        for _ in range(max_rounds):
            changed = False
            for move in moves:
                cand, ctop = best, top
                for k in offsets:
                    q = move(best, k)
                    if q == best:
                        continue
                    f = score(q, cell)
                    if f > ctop:
                        cand, ctop = q, f
                if cand != best:
                    best, top, changed = cand, ctop, True
            if not changed:
                break
    if best != start and score(best) <= start_top:
        best = start
    return best, frame, n_eval


def evaluate_affine(t_us, x, y, p, track: Track, t_e_us: int, m: int, T2_us: int, width: int, height: int,
                    d_start, q_prev=None, T1_us: int = 100_000, margin_px: float = 2.0) -> dict:
    """The ``affine`` model for target window ``m`` of the group keyed at ``t_e``.

    ``d_start`` is ``(aligned_dx, aligned_dy)`` of the same row from directive 003.
    ``q_prev`` is the fitted map of target ``m - 1`` of the same group (the six
    ``affine_*`` parameters in the order of PARAMS), or None when ``m`` = 1 or that
    target was skipped. ``t_us`` must be nondecreasing.
    """
    t_us = np.asarray(t_us, dtype=np.int64)
    D = lead_us(m)
    w0, w1, shift = int(t_e_us + D), int(t_e_us + D + T2_us), int(D + T2_us)
    if t_e_us - T1_us < track.t_first or w1 > track.t_last:
        return {"skipped": "outside_track_life"}
    # support, truth and source: identical to ec.regen.evaluate_regen
    v_lab = track.velocity(t_e_us, T1_us)
    bx, by, bw, bh = (float(a) for a in track.box(0.5 * (w0 + w1)))
    grow = margin_px + 0.5 * math.hypot(*v_lab) * T2_us * 1e-6
    sx0 = max(0, int(math.floor(bx - grow))); sx1 = min(width - 1, int(math.ceil(bx + bw + grow)))
    sy0 = max(0, int(math.floor(by - grow))); sy1 = min(height - 1, int(math.ceil(by + bh + grow)))
    if sx1 < sx0 or sy1 < sy0:
        return {"skipped": "support_outside_sensor"}
    b0, b1 = np.searchsorted(t_us, (w0, w1))
    fxa, fya = np.asarray(x[b0:b1]), np.asarray(y[b0:b1])
    fm = (fxa >= sx0) & (fxa <= sx1) & (fya >= sy0) & (fya <= sy1)
    ft, fx, fy, fp = t_us[b0:b1][fm], fxa[fm], fya[fm], np.asarray(p[b0:b1])[fm]
    a0, a1 = np.searchsorted(t_us, (t_e_us - T2_us, t_e_us))
    sm = in_box_mask(track, t_us[a0:a1], x[a0:a1], y[a0:a1], margin_px)
    st = t_us[a0:a1][sm]
    sx, sy, sp = np.asarray(x[a0:a1])[sm], np.asarray(y[a0:a1])[sm], np.asarray(p[a0:a1])[sm]
    if len(st) < regen.MIN_SOURCE_EVENTS:
        return {"skipped": "source_too_small", "n_source": int(len(st)), "n_future": int(len(ft))}
    if len(ft) < regen.MIN_FUTURE_EVENTS:
        return {"skipped": "future_too_small", "n_source": int(len(st)), "n_future": int(len(ft))}
    support = (sx0, sx1, sy0, sy1)
    shift_prev = int(lead_us(m - 1) + T2_us) if (q_prev is not None and m > 1) else None
    q, frame, n_eval = fit_affine(sx, sy, st, sp, fx, fy, ft, fp, w0, T2_us, shift, support, d_start,
                                  q_prev if shift_prev is not None else None, shift_prev)
    out = {"m": int(m), "n_source": int(len(st)), "n_future": int(len(ft)), "affine_n_eval": n_eval,
           "frame_hx": frame[2], "frame_hy": frame[3]}
    out.update({f"affine_{name}": int(val) for name, val in zip(PARAMS, q)})
    for prefix, qq in (("affine", q), ("translation", (int(d_start[0]), int(d_start[1]), 0, 0, 0, 0))):
        ix, iy = move_affine(sx, sy, frame, qq)
        keep = (ix >= sx0) & (ix <= sx1) & (iy >= sy0) & (iy <= sy1)
        out[f"{prefix}_n_pred"] = int(keep.sum())
        for s in regen.BLOCKS_PX:
            for k in regen.TIME_BINS:
                out[f"{prefix}_f1_s{s}_k{k}"] = regen.voxel_f1(ix[keep], iy[keep], (st + shift)[keep], sp[keep],
                                                               fx, fy, ft, fp, w0, T2_us, s, k)["f1"]
    return out
