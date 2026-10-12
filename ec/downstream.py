"""Two tasks on rebuilt events that need no trained model (directive 016).

objects   For an annotated box and a window, the events of the window inside the box, true and
          rebuilt. ``box_scores`` returns their counts, the fidelity of Eq. (fid) inside the box on
          the working grid, and the distance in pixels between the centroids of the two sets, or
          NaN when the rebuilt set is empty.

motion    The velocity of the events of a square region in one window, by contrast maximization
          [gallego2018cmax]: the events are warped to the start of the window along a candidate
          velocity, counted per pixel, and the velocity whose image has the largest variance is
          taken. The search is a grid of step CMAX_COARSE over [-CMAX_VMAX, CMAX_VMAX]^2 px/ms,
          then of step CMAX_FINE within one coarse step of the best point. ``cmax_velocity``
          uses at most CMAX_EVENTS events, every k-th in time order. The error of a rebuilt set is
          the length of the difference between its velocity and that of the true events, times
          T0, in pixels per window.
"""
from __future__ import annotations

import numpy as np

from . import blockcodec as bc

CMAX_VMAX = 0.6          # px/ms
CMAX_COARSE = 0.1
CMAX_FINE = 0.02
CMAX_EVENTS = 4000
CMAX_MARGIN = 20         # px around the region in the warped image


def box_scores(true, rec, box, w0_us: int, T0_us: int = bc.T0_US) -> dict:
    """``true``, ``rec``: (t_us, x, y, p) of one window starting at ``w0_us``. ``box`` = (x0, y0, w, h)."""
    x0, y0, w, h = box
    def inside(ev):
        t, x, y, p = ev
        s = (x >= x0) & (x < x0 + w) & (y >= y0) & (y < y0 + h)
        return t[s], x[s], y[s], p[s]
    tt, tx, ty, tp = inside(true)
    rt, rx, ry, rp = inside(rec)
    m = bc.Truth(tt, tx, ty, tp, w0_us, T0_us).match(rt, rx, ry, rp, bc.OBJECTIVE)
    den = len(tt) + len(rt)
    err = float(np.hypot(rx.mean() - tx.mean(), ry.mean() - ty.mean())) if len(rt) and len(tt) else float("nan")
    return {"n_true": int(len(tt)), "n_rec": int(len(rt)), "F": 2.0 * m / den if den else float("nan"),
            "centroid_px": err}


def _subsample(t, x, y):
    if len(t) <= CMAX_EVENTS:
        return t, x, y
    k = int(np.ceil(len(t) / CMAX_EVENTS))
    o = np.argsort(t, kind="stable")[::k]
    return t[o], x[o], y[o]


def _variance(t_ms, x, y, vx, vy, box):
    x0, y0, w, h = box
    nx, ny = w + 2 * CMAX_MARGIN, h + 2 * CMAX_MARGIN
    wx = np.rint(x - vx * t_ms).astype(np.int64) - (x0 - CMAX_MARGIN)
    wy = np.rint(y - vy * t_ms).astype(np.int64) - (y0 - CMAX_MARGIN)
    keep = (wx >= 0) & (wx < nx) & (wy >= 0) & (wy < ny)
    img = np.bincount(wy[keep] * nx + wx[keep], minlength=nx * ny).astype(np.float64)
    return img.var()


def cmax_velocity(ev, box, w0_us: int):
    """Velocity (px/ms) of the events ``ev`` = (t_us, x, y, p) inside ``box``, warped to ``w0_us``. NaNs without events."""
    t, x, y, _ = ev
    x0, y0, w, h = box
    s = (x >= x0) & (x < x0 + w) & (y >= y0) & (y < y0 + h)
    if not s.any():
        return np.array([np.nan, np.nan])
    t, x, y = _subsample(np.asarray(t[s]), np.asarray(x[s]), np.asarray(y[s]))
    tm = (t - w0_us) / 1000.0
    best, bv = -1.0, (0.0, 0.0)
    g = np.arange(-CMAX_VMAX, CMAX_VMAX + 1e-9, CMAX_COARSE)
    for vx in g:
        for vy in g:
            f = _variance(tm, x, y, vx, vy, box)
            if f > best:
                best, bv = f, (vx, vy)
    f0 = np.arange(-CMAX_COARSE, CMAX_COARSE + 1e-9, CMAX_FINE)
    cx, cy = bv
    for dx in f0:
        for dy in f0:
            f = _variance(tm, x, y, cx + dx, cy + dy, box)
            if f > best:
                best, bv = f, (cx + dx, cy + dy)
    return np.array(bv)


def motion_error_px(true, rec, box, w0_us: int, T0_us: int = bc.T0_US) -> float:
    """Length of the velocity difference times T0, in pixels per window; NaN if a set is empty in the box."""
    vt = cmax_velocity(true, box, w0_us)
    vr = cmax_velocity(rec, box, w0_us)
    if np.isnan(vt).any() or np.isnan(vr).any():
        return float("nan")
    return float(np.hypot(*(vr - vt)) * T0_us / 1000.0)
