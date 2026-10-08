"""Motion predictability of in-box events (directive 001). Reference implementation.

Question. Warp the events of an object over the last ``T1`` along its motion to a
common reference time. They form a point cloud that traces the object's edges (the
template). How many bits does that template save in describing the object's next
events, compared with knowing only where the object is?

Everything is a code length. For one evaluation instant ``t_e``:

* template: events of ``[t_e - T1, t_e)`` inside the interpolated label box
  (dilated by ``margin_px``), back-warped to ``t_e``;
* support ``S``: the label box at the middle of the future window, dilated by
  ``margin_px + 0.5 |v_label| T2``, clipped to the sensor (a fixed pixel rectangle);
* future: every event with pixel in ``S`` and time in ``[t_e + D, t_e + D + T2)``;
* a motion model maps (pixel, time) to a back-warped position ``u(x, y, t)``;
* the template is histogrammed on a ``cell``-px grid per polarity and smoothed with
  a Gaussian of bandwidth ``b`` px, giving ``g_p(u)``;
* predictive density of an event, per pixel and per second, given the count:

      a(x, y, p, t) = g_p(u(x, y, t)) / Z,
      Z = sum over p and over pixels of S of the time integral of g_p(u(x, y, t)),

  with ``Z`` computed numerically, so the density is normalized over
  (pixel, polarity, time) whatever the warp;
* mixture with a uniform floor: ``f = (1 - eps) a + eps / (2 |S| T2)``; ``eps`` is
  fitted by EM on the future events and is the share of future events that the
  template does not explain (new content, other objects, noise);
* cost in bits per event at resolution ``delta`` = 1 us:
  ``-mean(log2(f delta)) + (log2(#bandwidths) + 0.5 log2 N) / N``, where the second
  term charges for choosing ``b`` and ``eps`` on the events being scored;
* reference cost: uniform over ``S``, polarity and time, ``log2(2 |S| T2 / delta)``;
* gain = reference cost - cost;
* both costs describe each event independently. The events of a window are a set,
  so ``log2(N!) / N`` bits per event can be taken off both (``set_bits``,
  ``ref_set_bits``). The gain is unaffected. For a uniform Poisson stream
  ``ref_set_bits`` is Eq. (2) of the brief plus one polarity bit.

Motion models:

* ``static``: ``u = (x, y)``. The template is the recent event map of the box.
  This is what recency contexts (the C1 coder of the brief) can exploit;
* ``label``: ``u`` from the interpolated annotation box (translation and scale),
  no estimation. Not causal for the future window, since it reads future boxes;
* ``cmax``: translation at the constant velocity that maximizes the sharpness of
  the warped template, searched around the label velocity. Causal for ``D >= 0``.

The number of interest is ``gain(cmax) - gain(static)``: the bits per event that
explicit motion buys on top of recency. ``b*`` over the model speed is the timing
precision at which the template stops helping. The grid cell is 1/8 px, so a
``b*`` at the smallest bandwidth means "1/8 px or finer", and the gain is then a
lower estimate.
"""
from __future__ import annotations

import math

import numpy as np
from scipy.ndimage import gaussian_filter

from .annotations import Track, in_box_mask

CELL_PX = 0.125
BANDWIDTHS_PX = (0.125, 0.25, 0.5, 1.0)
DELTA_S = 1e-6
MIN_TEMPLATE_EVENTS = 200
MIN_FUTURE_EVENTS = 50
CMAX_MAX_EVENTS = 20_000
_OFF = 1 << 20


# ----------------------------------------------------------------------------- warps
def warp_translation(x, y, t_us, t_ref_us, v):
    dt = (np.asarray(t_us, dtype=np.float64) - float(t_ref_us)) * 1e-6
    return np.asarray(x, dtype=np.float64) - v[0] * dt, np.asarray(y, dtype=np.float64) - v[1] * dt


def warp_label(x, y, t_us, t_ref_us, track: Track):
    bx, by, bw, bh = track.box(np.asarray(t_us, dtype=np.float64))
    rx, ry, rw, rh = (float(a) for a in track.box(float(t_ref_us)))
    xw = (rx + 0.5 * rw) + (np.asarray(x, dtype=np.float64) - (bx + 0.5 * bw)) * (rw / np.maximum(bw, 1e-9))
    yw = (ry + 0.5 * rh) + (np.asarray(y, dtype=np.float64) - (by + 0.5 * bh)) * (rh / np.maximum(bh, 1e-9))
    return xw, yw


# ----------------------------------------------------------------------------- velocity
def _site_keys(xw, yw, p, cell: float = 1.0):
    ix = np.rint(np.asarray(xw) / cell).astype(np.int64) + _OFF
    iy = np.rint(np.asarray(yw) / cell).astype(np.int64) + _OFF
    return (iy * (1 << 22) + ix) * 2 + np.asarray(p, dtype=np.int64)


def sharpness(xw, yw, p, cell: float = 1.0) -> float:
    """Sum of squared site counts over the number of events (1 for no overlap, larger when sharp)."""
    if len(xw) == 0:
        return 0.0
    _, c = np.unique(_site_keys(xw, yw, p, cell), return_counts=True)
    return float((c.astype(np.float64) ** 2).sum() / len(xw))


def cmax_velocity(x, y, p, t_us, t_ref_us, v_init, seed: int = 0):
    """Velocity (px/s) that maximizes template sharpness, by coarse-to-fine grid search.

    Search half-width: max(30 px/s, 0.5 |v_init|). Each stage uses a site size
    matched to the displacement step of its grid (never below 1 px), so the
    objective is smooth at the scale being searched. Five stages; the last step is
    half-width / 64. Ties go to the candidate nearest the current best, which keeps
    the estimate from drifting along a flat direction.
    """
    x = np.asarray(x); y = np.asarray(y); p = np.asarray(p); t_us = np.asarray(t_us)
    if len(x) > CMAX_MAX_EVENTS:
        idx = np.random.default_rng(seed).choice(len(x), CMAX_MAX_EVENTS, replace=False)
        x, y, p, t_us = x[idx], y[idx], p[idx], t_us[idx]
    span_t = max(1e-6, (float(t_us.max()) - float(t_us.min())) * 1e-6)
    half = max(30.0, 0.5 * math.hypot(v_init[0], v_init[1]))
    best = (float(v_init[0]), float(v_init[1]))
    step = half / 4.0
    reach = 4
    for stage in range(5):
        cell = max(1.0, step * span_t)
        offs = [(i, j) for i in range(-reach, reach + 1) for j in range(-reach, reach + 1)]
        offs.sort(key=lambda ij: (ij[0] * ij[0] + ij[1] * ij[1], ij))
        cand, score = best, -1.0
        for i, j in offs:
            v = (best[0] + i * step, best[1] + j * step)
            xw, yw = warp_translation(x, y, t_us, t_ref_us, v)
            s = sharpness(xw, yw, p, cell)
            if s > score * (1.0 + 1e-9):
                cand, score = v, s
        best = cand
        reach = 2
        step /= 2.0
    xw, yw = warp_translation(x, y, t_us, t_ref_us, best)
    return best, sharpness(xw, yw, p, 1.0)


# ----------------------------------------------------------------------------- predictive cost
def _fit_eps(a: np.ndarray, u: float, iters: int = 50) -> float:
    eps = 0.3
    for _ in range(iters):
        r = eps * u / ((1.0 - eps) * a + eps * u)
        eps = float(np.clip(r.mean(), 1e-3, 1.0))
    return eps


def predictive_cost(tx, ty, tp, fx, fy, fp, ft_us, support, window_us, warp, speed: float,
                    cell: float = CELL_PX, bandwidths=BANDWIDTHS_PX) -> dict:
    """Cost in bits per future event under one motion model. See the module docstring.

    ``tx, ty, tp``: template, already back-warped. ``fx, fy, fp, ft_us``: future
    events in sensor coordinates. ``support``: (x0, x1, y0, y1) inclusive pixel
    rectangle. ``warp(x, y, t_us)`` returns back-warped coordinates.
    """
    x0, x1, y0, y1 = support
    t0, t1 = window_us
    T2 = (t1 - t0) * 1e-6
    n = len(fx)
    area = (x1 - x0 + 1) * (y1 - y0 + 1)
    uni = 1.0 / (2.0 * area * T2)
    ref_bits = -math.log2(uni * DELTA_S)
    px, py = np.meshgrid(np.arange(x0, x1 + 1), np.arange(y0, y1 + 1))
    px, py = px.ravel().astype(np.float64), py.ravel().astype(np.float64)
    # time samples for the normalizer: the lattice moves by at most cell/2 between samples
    k = max(1, int(math.ceil(speed * T2 / (cell / 2.0))))
    ts = t0 + (np.arange(k) + 0.5) * (t1 - t0) / k
    dt = T2 / k
    fu, fv = warp(fx, fy, ft_us)
    cx = np.array([x0, x1, x0, x1], dtype=np.float64)
    cy = np.array([y0, y0, y1, y1], dtype=np.float64)
    lo_x, hi_x, lo_y, hi_y = np.min(tx), np.max(tx), np.min(ty), np.max(ty)
    for tk in np.unique(np.concatenate((ts[:1], ts[-1:], ts[:: max(1, k // 16)]))):
        ux, uy = warp(cx, cy, np.full(4, tk))
        lo_x, hi_x = min(lo_x, ux.min()), max(hi_x, ux.max())
        lo_y, hi_y = min(lo_y, uy.min()), max(hi_y, uy.max())
    lo_x, hi_x = min(lo_x, fu.min()), max(hi_x, fu.max())
    lo_y, hi_y = min(lo_y, fv.min()), max(hi_y, fv.max())
    pad = 4.0 * max(bandwidths) + 1.0
    gx0, gy0 = lo_x - pad, lo_y - pad
    nx = int(math.ceil((hi_x + pad - gx0) / cell)) + 1
    ny = int(math.ceil((hi_y + pad - gy0) / cell)) + 1

    def cells(u, v):
        return (np.clip(np.rint((v - gy0) / cell).astype(np.int64), 0, ny - 1),
                np.clip(np.rint((u - gx0) / cell).astype(np.int64), 0, nx - 1))

    hist = np.zeros((2, ny, nx))
    iy, ix = cells(np.asarray(tx, dtype=np.float64), np.asarray(ty, dtype=np.float64))
    np.add.at(hist, (np.asarray(tp, dtype=np.int64), iy, ix), 1.0)
    hist /= max(1, len(tx))
    lat = [cells(*warp(px, py, np.full(px.shape, tk))) for tk in ts]
    fiy, fix = cells(fu, fv)
    fpi = np.asarray(fp, dtype=np.int64)
    best = None
    for b in bandwidths:
        g = np.stack([gaussian_filter(hist[q], sigma=b / cell, mode="constant") for q in (0, 1)])
        z = 0.0
        for liy, lix in lat:
            z += float(g[0][liy, lix].sum() + g[1][liy, lix].sum()) * dt
        if z <= 0:
            continue
        a = g[fpi, fiy, fix] / z
        eps = _fit_eps(a, uni)
        bits = float(-np.mean(np.log2(((1.0 - eps) * a + eps * uni) * DELTA_S)))
        if best is None or bits < best["bits"]:
            best = {"bits": bits, "eps": eps, "b_px": float(b)}
    if best is None:
        return {"bits": ref_bits, "gain_bits": 0.0, "eps": 1.0, "b_px": float("nan"),
                "tau_eq_us": float("nan"), "ref_bits": ref_bits}
    penalty = (math.log2(len(bandwidths)) + 0.5 * math.log2(n)) / n
    bits = best["bits"] + penalty
    order_bits = math.lgamma(n + 1) / math.log(2) / n      # events of a window form a set, not a list
    return {"bits": bits, "gain_bits": ref_bits - bits, "eps": best["eps"], "b_px": best["b_px"],
            "tau_eq_us": best["b_px"] / speed * 1e6 if speed > 0 else float("nan"), "ref_bits": ref_bits,
            "set_bits": bits - order_bits, "ref_set_bits": ref_bits - order_bits}


# ----------------------------------------------------------------------------- one instant
def evaluate_instant(t_us, x, y, p, track: Track, t_e_us: int, T1_us: int, D_us: int, T2_us: int,
                     width: int, height: int, margin_px: float = 2.0,
                     models=("static", "label", "cmax")) -> dict:
    """All quantities of one evaluation instant. ``t_us`` must be nondecreasing.

    Returns ``{"skipped": reason, ...}`` when the instant cannot be scored, so that
    skips are counted and never silently dropped.
    """
    t_us = np.asarray(t_us, dtype=np.int64)
    w0, w1 = int(t_e_us + D_us), int(t_e_us + D_us + T2_us)
    if t_e_us - T1_us < track.t_first or w1 > track.t_last:
        return {"skipped": "outside_track_life"}
    a0, a1 = np.searchsorted(t_us, (t_e_us - T1_us, t_e_us))
    tm = in_box_mask(track, t_us[a0:a1], x[a0:a1], y[a0:a1], margin_px)
    tt = t_us[a0:a1][tm]
    tx, ty, tp = np.asarray(x[a0:a1])[tm], np.asarray(y[a0:a1])[tm], np.asarray(p[a0:a1])[tm]
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
    ft, fx, fy, fp = t_us[b0:b1][fm], fxa[fm].astype(np.float64), fya[fm].astype(np.float64), np.asarray(p[b0:b1])[fm]
    if len(tt) < MIN_TEMPLATE_EVENTS:
        return {"skipped": "template_too_small", "n_template": int(len(tt)), "n_future": int(len(ft))}
    if len(ft) < MIN_FUTURE_EVENTS:
        return {"skipped": "future_too_small", "n_template": int(len(tt)), "n_future": int(len(ft))}
    out = {"n_template": int(len(tt)), "n_future": int(len(ft)), "support_px": (sx1 - sx0 + 1) * (sy1 - sy0 + 1),
           "v_label_x": v_lab[0], "v_label_y": v_lab[1], "speed_label": speed_lab,
           "path_px_label": speed_lab * T1_us * 1e-6}
    support, window = (sx0, sx1, sy0, sy1), (w0, w1)
    for model in models:
        if model == "static":
            warp = lambda xx, yy, tq: (np.asarray(xx, dtype=np.float64), np.asarray(yy, dtype=np.float64))
            speed = 0.0
        elif model == "label":
            warp = lambda xx, yy, tq: warp_label(xx, yy, tq, t_e_us, track)
            speed = speed_lab
        elif model == "cmax":
            v, sharp = cmax_velocity(tx, ty, tp, tt, t_e_us, v_lab)
            warp = lambda xx, yy, tq, v=v: warp_translation(xx, yy, tq, t_e_us, v)
            speed = math.hypot(*v)
            out.update({"cmax_vx": v[0], "cmax_vy": v[1], "cmax_speed": speed, "cmax_sharpness": sharp,
                        "static_sharpness": sharpness(tx.astype(np.float64), ty.astype(np.float64), tp, 1.0)})
        else:
            raise ValueError(model)
        txw, tyw = warp(tx, ty, tt)
        res = predictive_cost(txw, tyw, tp, fx, fy, fp, ft, support, window, warp, speed)
        n_sites = len(np.unique(_site_keys(txw, tyw, tp, 1.0)))
        res["redundancy"] = float(len(tt) / max(1, n_sites))
        for k, val in res.items():
            out[f"{model}_{k}"] = val
    return out


def evaluation_instants(track: Track, first_offset_us: int = 300_000, step_us: int = 500_000,
                        tail_us: int = 350_000) -> np.ndarray:
    """Instants t_e = first + 0.3 s + k 0.5 s with t_e + 0.35 s <= last, for tracks of at least 1 s."""
    if track.t_last - track.t_first < 1_000_000:
        return np.zeros(0, dtype=np.int64)
    return np.arange(track.t_first + first_offset_us, track.t_last - tail_us + 1, step_us, dtype=np.int64)
