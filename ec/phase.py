"""Do moved events keep the timing of the target pixel's train, or only its pixels? (directive 022).

Directive 020 binned the fidelity of a causal prediction by ``r = dt / tau`` with ``tau`` the median interval of
a pixel over 133 ms. On recordings, many pixels fire one or two events per passing edge, so that median often
measures the gap between passages and not the spacing inside one. This module adds a test of the phase that
needs no such estimate, and repeats the binned fidelity with a spacing taken from regular trains only.

Regular trains. Two consecutive intervals ``a``, ``b`` of one pixel and polarity form a regular pair when
``max(a, b) <= RHO min(a, b)``, ``min(a, b) > 0`` and ``a + b <= T0``. An interval is regular when it belongs to
a regular pair. ``tau_reg`` of a pixel and polarity in the span is the median of its regular intervals;
``tau_med`` is directive 020's estimate, kept for comparison. Pixels whose times are redrawn uniformly over the
same span, with the same counts, give the share of pixels that the rule calls regular by chance
(``surrogate``).

Phase test. The model says that the train of a target pixel is ``A_i + (k - 1) tau`` and a moved train
``A_j + (k - 1) tau + e``, with independent phases and a residual offset ``e`` of the motion. For a target pixel
and polarity whose true events in the scored window hold a regular pair, with ``tau_i`` the median of its
regular intervals there, the phase of the prediction is ``u = arg(z) / (2 pi)`` in [0, 1) with
``z = sum_k exp(2 pi i p_k / tau_i) * sum_m exp(-2 pi i t_m / tau_i)`` over its predicted times ``p_k`` and its
true times ``t_m``. Under independent phases ``u`` is uniform whatever ``e``, the train lengths and their
truncation by the window, since ``A_j - A_i`` is uniform modulo ``tau_i``. A prediction that carries the
timing inside the train locks ``u`` to a constant. Each pixel counts once. The statistics are the mean of
``cos(2 pi u)`` and ``sin(2 pi u)``: both 0 for a uniform ``u``; ``(cos, sin)`` points to the lock otherwise.
The null (the predicted pixels with uniform random times) is uniform by construction.

Motion. Per block, all integer shifts with ``|dx|, |dy| <= RADIUS`` are scored by the pairs of directive 020
(the window ``w - 1`` moved onto ``w``, pixel by pixel and polarity by polarity over the whole window). Among
the shifts whose pairs are at least the most pairs ``m`` minus TIE_SIGMAS ``sqrt(m)``, the smallest
``|dx| + |dy|`` is chosen, then the smallest ``(dy, dx)``: along a moving edge, near-ties between shifts are
common, the pair counts fluctuate by about ``sqrt(m)``, and a shift error along the motion is a time offset that
the delay takes up. A block whose most pairs fall below N_MIN / 2 has no source for its events (an entry
border, newly revealed content) and is skipped and counted. ``runner_up`` is the share of the most pairs that
the best shift farther than one pixel (Chebyshev) from the chosen one reaches. The delay is the onset offset: the median, over the pixels and
polarities of the block, of the first true event in window ``w`` minus the first moved event there, both at
least GUARD after the window start; it is clipped to ``+-T0 / 2``. Window truncation shrinks it toward 0 by
about 0.1 to 0.2 ``tau``.

A shift of (0, 0) maps a pixel onto itself, so any timing that persists in one pixel (mains flicker, a slow
train that crosses the window boundary) locks ``u`` without saying anything about different pixels. Such
blocks enter the phase arrays in their own slice ``zero = 1``.

Sums. ``sums[tau_kind]``, ``tau_kind`` in (``med``, ``reg``), of shape (flicker, speed, grid, bin, 4) with N, N2,
M and M0 as directive 020, over the grids with s = 1 of ``ec.threshold.GRIDS``, binned by the target pixel's own
``dt / tau``. ``phase[kind]``, ``kind`` in (``pred``, ``null``), of shape (speed, zero, flicker, tau bin, U_BINS)
holds the histogram of ``u`` with ``tau_i`` binned by TAU_EDGES and ``flicker`` the class of ``tau_i`` as in
``ec.threshold``; ``phase_stat[kind]`` of the same shape with a last axis of 3 holds the count and the sums of
``cos(2 pi u)`` and ``sin(2 pi u)``.
"""
from __future__ import annotations

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

from . import blockcodec as bc
from . import hevcdiag as hd
from . import threshold as th

T0 = bc.T0_US
B = th.B
RADIUS = 32
RHO = 1.2
TIE_SIGMAS = 2.0
GUARD = T0 // 16
U_BINS = 20
TAU_EDGES = np.geomspace(125.0, 32000.0, 9)        # 8 bins of tau_i in us, 125 us to 32 ms
GRIDS = tuple(c for c in th.GRIDS if c[0] == 1)
TAU_KINDS = ("med", "reg")
SEED = 20261022


def _pk(ev, width: int):
    return (ev[2] * width + ev[1]) * 2 + ev[3]


def _sorted(ev, width: int):
    pk = _pk(ev, width)
    o = np.lexsort((ev[0], pk))
    return pk[o], ev[0][o].astype(np.float64)


def _regular_intervals(pk_o, t_o):
    """Intervals of consecutive events of one key, and whether each lies in a regular pair.

    Returns the key of each interval, its length and the regular flag (all of length ``len(t_o) - 1``)."""
    d = np.diff(t_o)
    same = pk_o[1:] == pk_o[:-1]
    reg = np.zeros(len(d), dtype=bool)
    if len(d) >= 2:
        a, b = d[:-1], d[1:]
        both = same[:-1] & same[1:]
        lo, hi = np.minimum(a, b), np.maximum(a, b)
        pair = both & (lo > 0) & (hi <= RHO * lo) & (a + b <= T0)
        reg[:-1] |= pair
        reg[1:] |= pair
    return pk_o[:-1], d, reg & same


def _grouped_median(keys, vals):
    """Median of ``vals`` per distinct key: (sorted distinct keys, medians)."""
    if len(keys) == 0:
        return np.zeros(0, dtype=np.int64), np.zeros(0)
    o = np.lexsort((vals, keys))
    k, v = keys[o], vals[o]
    start = np.flatnonzero(np.concatenate(([True], k[1:] != k[:-1])))
    size = np.diff(np.concatenate((start, [len(k)])))
    lo = start + (size - 1) // 2
    hi = start + size // 2
    return k[start], 0.5 * (v[lo] + v[hi])


def regular_spacing(span, width: int):
    """``tau_reg`` per pixel and polarity with a regular interval in the span: (sorted keys, tau)."""
    pk_o, t_o = _sorted(span, width)
    k, d, reg = _regular_intervals(pk_o, t_o)
    return _grouped_median(k[reg], d[reg])


def median_spacing(span, width: int):
    """``tau_med``: ``ec.threshold.pixel_spacing`` computed without a loop over pixels (sorted keys, tau)."""
    pk_o, t_o = _sorted(span, width)
    d = np.diff(t_o)
    same = pk_o[1:] == pk_o[:-1]
    return _grouped_median(pk_o[:-1][same], d[same])


def surrogate_share(span, width: int, rng) -> tuple:
    """Pixels and polarities with a regular interval: (real, with times redrawn uniformly over the span)."""
    if len(span[0]) == 0:
        return 0, 0
    real = len(regular_spacing(span, width)[0])
    t = rng.integers(int(span[0].min()), int(span[0].max()) + 1, len(span[0]))
    sur = len(regular_spacing((t, span[1], span[2], span[3]), width)[0])
    return int(real), int(sur)


def shift_scores(ref, tru, bx0: int, by0: int, radius: int = RADIUS):
    """Pairs for every shift: array (2 radius + 1, 2 radius + 1) indexed [dy + radius, dx + radius]."""
    target = th._image(tru[1], tru[2], tru[3], bx0, by0, B, B)
    src = th._image(ref[1], ref[2], ref[3], bx0 - radius, by0 - radius, B + 2 * radius, B + 2 * radius)
    win = sliding_window_view(src, (B, B), axis=(1, 2))           # (2, 2R + 1, 2R + 1, B, B), [sy, sx]
    m = np.minimum(win, target[:, None, None]).sum(axis=(0, 3, 4))
    return m[::-1, ::-1]                                            # sy = R - dy, sx = R - dx


def choose_shift(scores, radius: int = RADIUS):
    """The chosen shift, the most pairs, and ``runner_up`` (see the module docstring)."""
    mx = int(scores.max())
    if mx == 0:
        return (0, 0), 0, 0.0
    dy, dx = np.nonzero(scores >= mx - TIE_SIGMAS * np.sqrt(mx))
    dy, dx = dy - radius, dx - radius
    o = np.lexsort((dx, dy, np.abs(dx) + np.abs(dy)))
    d = (int(dx[o[0]]), int(dy[o[0]]))
    gy, gx = np.mgrid[-radius:radius + 1, -radius:radius + 1]
    far = np.maximum(np.abs(gx - d[0]), np.abs(gy - d[1])) > 1
    return d, mx, float(scores[far].max() / mx) if far.any() else 0.0


def onset_delay(moved, true, w0: int, width: int) -> int:
    """Median over pixels and polarities of (first true - first moved), both at least GUARD after ``w0``."""
    out = []
    for ev in (true, moved):
        sel = ev[0] >= w0 + GUARD
        k = _pk(ev, width)[sel]
        t = ev[0][sel]
        uk, inv = np.unique(k, return_inverse=True)
        first = np.full(len(uk), np.iinfo(np.int64).max)
        np.minimum.at(first, inv, t)
        out.append((uk, first))
    (kt, ft), (km, fm) = out
    _, i, j = np.intersect1d(kt, km, assume_unique=True, return_indices=True)
    if len(i) == 0:
        return 0
    return int(np.clip(np.round(np.median(ft[i] - fm[j])), -(T0 // 2), T0 // 2))


def pixel_phases(true, pred, width: int):
    """Per target pixel and polarity with a regular pair in ``true`` and a predicted event: (u, tau_i)."""
    if len(true[0]) < 3 or len(pred[0]) == 0:
        return np.zeros(0), np.zeros(0)
    pk_o, t_o = _sorted(true, width)
    k, d, reg = _regular_intervals(pk_o, t_o)
    keys, tau = _grouped_median(k[reg], d[reg])
    if len(keys) == 0:
        return np.zeros(0), np.zeros(0)
    kq = _pk(pred, width)
    zt = np.zeros(len(keys), dtype=np.complex128)
    zq = np.zeros(len(keys), dtype=np.complex128)
    for kk, tt, z, sign in ((pk_o, t_o, zt, -1.0), (kq, pred[0].astype(np.float64), zq, 1.0)):
        pos = np.searchsorted(keys, kk)
        ok = (pos < len(keys)) & (keys[np.minimum(pos, len(keys) - 1)] == kk)
        p = pos[ok]
        np.add.at(z, p, np.exp(sign * 2j * np.pi * np.mod(tt[ok], tau[p]) / tau[p]))
    has = np.abs(zq) > 0
    u = np.mod(np.angle(zq[has] * zt[has]) / (2.0 * np.pi), 1.0)
    return u, tau[has]


def _tbin(tau):
    return np.clip(np.searchsorted(TAU_EDGES, tau, side="right") - 1, 0, len(TAU_EDGES) - 2)


def empty():
    nt = len(TAU_EDGES) - 1
    return {"sums": {k: np.zeros((2, len(th.SPEEDS), len(GRIDS), th.N_BINS, 4), dtype=np.int64) for k in TAU_KINDS},
            "phase": {k: np.zeros((len(th.SPEEDS), 2, 2, nt, U_BINS), dtype=np.int64) for k in ("pred", "null")},
            "phase_stat": {k: np.zeros((len(th.SPEEDS), 2, 2, nt, 3)) for k in ("pred", "null")},
            "regular_share": np.zeros(2, dtype=np.int64), "skipped_no_source": 0}


def evaluate_group(ev, w: int, width: int, height: int, radius: int = RADIUS) -> dict:
    """Sums, phase statistics and a summary per entering block for the group keyed at ``w``.

    ``ev`` = (t_us, x, y, p), nondecreasing in time, covering ``[(w - SPAN_BEFORE) T0, (w + 2) T0)``."""
    ev = tuple(np.asarray(a, dtype=np.int64) for a in ev)
    span = th._window(ev, max(0, w - th.SPAN_BEFORE) * T0, (w + 1) * T0)
    hot = th.hot_pixels(span, width, height)
    keep = ~hot[ev[2] * width + ev[1]]
    ev = tuple(a[keep] for a in ev)
    span = th._window(ev, max(0, w - th.SPAN_BEFORE) * T0, (w + 1) * T0)
    win = {m: th._window(ev, (w + m) * T0, (w + m + 1) * T0) for m in (-1, 0, 1)}
    by = {m: th._ByBlock(win[m], width, height) for m in (-1, 0, 1)}
    taus = {"med": median_spacing(span, width), "reg": regular_spacing(span, width)}
    out = empty()
    out["regular_share"][:] = surrogate_share(span, width, np.random.default_rng((SEED, int(w), 1 << 30)))
    reach = -(-radius // B)
    nbx = -(-width // B)
    n1 = np.diff(by[1].start)
    cand = np.flatnonzero(n1 >= th.N_MIN)
    rows = {"ids": [], "shift": [], "pairs": [], "runner_up": [], "delta_us": [], "at_radius": [], "N": [], "N2": [],
            "n_phase": []}
    w0, w1 = w * T0, (w + 1) * T0
    for b in cand:
        b = int(b)
        bx0, by0 = (b % nbx) * B, (b // nbx) * B
        a_prev, a_ref, a_tru = by[-1].around(b, reach), by[0].around(b, reach), by[1].around(b, 0)
        fit_true = th._in_block(a_ref, bx0, by0)
        d, pairs, runner = choose_shift(shift_scores(a_prev, fit_true, bx0, by0, radius), radius)
        if pairs < th.N_MIN / 2:
            out["skipped_no_source"] += 1
            continue
        delta = onset_delay(th._moved(a_prev, d, 0, bx0, by0, w0), fit_true, w0, width)
        true = th._in_block(a_tru, bx0, by0)
        pred = th._moved(a_ref, d, delta, bx0, by0, w1)
        if len(true[0]) < th.N_MIN or len(pred[0]) < th.N_MIN:
            continue
        rng = np.random.default_rng((SEED, int(w), b))
        null = (rng.integers(w1, w1 + T0, len(pred[0])), pred[1], pred[2], pred[3])
        sp = th._speed_class(d)
        zero = int(d == (0, 0))
        n_ph = 0
        for kind, other in (("pred", pred), ("null", null)):
            u, tau_i = pixel_phases(true, other, width)
            tb = _tbin(tau_i)
            fl = th._flicker(tau_i).astype(np.int64)
            ub = np.minimum((u * U_BINS).astype(np.int64), U_BINS - 1)
            np.add.at(out["phase"][kind][sp, zero], (fl, tb, ub), 1)
            st = out["phase_stat"][kind][sp, zero]
            np.add.at(st, (fl, tb, 0), 1.0)
            np.add.at(st, (fl, tb, 1), np.cos(2.0 * np.pi * u))
            np.add.at(st, (fl, tb, 2), np.sin(2.0 * np.pi * u))
            if kind == "pred":
                n_ph = int(len(u))
        rows["ids"].append(b); rows["shift"].append([d[0], d[1]]); rows["pairs"].append(pairs)
        rows["runner_up"].append(runner); rows["delta_us"].append(int(delta))
        rows["at_radius"].append(bool(max(abs(d[0]), abs(d[1])) == radius))
        rows["N"].append(int(len(true[0]))); rows["N2"].append(int(len(pred[0]))); rows["n_phase"].append(n_ph)
        tk, qk = _pk(true, width), _pk(pred, width)
        uk = np.unique(np.concatenate((tk, qk)))
        idx = {}
        for kind in TAU_KINDS:
            pk, ptau = taus[kind]
            if len(pk) == 0:
                idx[kind] = np.full(len(uk), np.nan)
                continue
            pos = np.searchsorted(pk, uk)
            ok = (pos < len(pk)) & (pk[np.minimum(pos, len(pk) - 1)] == uk)
            idx[kind] = np.where(ok, ptau[np.minimum(pos, len(pk) - 1)], np.nan)
        for g, cell in enumerate(GRIDS):
            dt = T0 / cell[1]
            acc = np.zeros((len(uk), 4), dtype=np.int64)
            np.add.at(acc[:, 0], np.searchsorted(uk, tk), 1)
            np.add.at(acc[:, 1], np.searchsorted(uk, qk), 1)
            for col, other in ((2, pred), (3, null)):
                kk, m = th._pixel_pairs(true, other, w1, cell, width)
                np.add.at(acc[:, col], np.searchsorted(uk, kk), m)
            for kind in TAU_KINDS:
                tau_u = idx[kind]
                with np.errstate(divide="ignore", invalid="ignore"):
                    bins = th._bin(np.where(tau_u > 0, dt / tau_u, np.nan))
                fl = th._flicker(tau_u).astype(np.int64)
                np.add.at(out["sums"][kind], (fl, sp, g, bins), acc)
    out.update({"w": int(w), "n_hot": int(hot.sum()), "blocks": rows})
    return out


def edge_scene_v(width: int, height: int, v_px: float, tau_us: float, n: int, sigma_frac: float, spacing: int,
                 n_windows: int, seed: int, shared: bool):
    """Straight edges at ``v_px`` pixels per window (not necessarily whole), as ``ec.hevcdiag.edge_scene``, with
    independent phases, or one phase per row and edge when ``shared`` (the pixels of a path then fire in step)."""
    rng = np.random.default_rng(seed)
    v = v_px / T0
    span = n_windows * T0
    T, X, Y, P = [], [], [], []
    xs = np.arange(width)
    for e, x_e in enumerate(range(-int(np.ceil(v * span)) - spacing, width, spacing)):
        for y in range(height):
            phi = rng.random()
            t0 = (xs - x_e + phi) / v
            ok = (t0 >= -n * tau_us) & (t0 < span)
            if not ok.any():
                continue
            xx = xs[ok]
            if shared:
                A = np.full(len(xx), (1.0 - rng.random()) * tau_us)
            else:
                A = (1.0 - rng.random(len(xx))) * tau_us
            for j in range(n):
                tt = t0[ok] + A + j * tau_us + rng.normal(0.0, sigma_frac * tau_us, len(xx))
                T.append(tt); X.append(xx); Y.append(np.full(len(xx), y)); P.append(np.full(len(xx), e % 2))
    t = np.rint(np.concatenate(T)).astype(np.int64)
    x, y, p = (np.concatenate(a).astype(np.int64) for a in (X, Y, P))
    keep = (t >= 0) & (t < span)
    o = np.argsort(t[keep], kind="stable")
    return tuple(a[keep][o] for a in (t, x, y, p))
