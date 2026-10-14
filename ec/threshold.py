"""Where motion stops predicting the voxel counts of real event streams (directive 020).

The theory of the manuscript says that the counts of a window are predictable from the previous window moved
by the motion only when the time slice dt of the grid is long against the event spacing tau of the pixels.
Eq. (binfidmoved) gives the fidelity of moved events, ``dt / tau - dt^2 / (3 n tau^2)`` for ``dt <= tau / 2``,
and directive 019 confirmed it on the model. This module measures the same quantity on recordings.

Windows. For a group keyed at ``w``: the motion is chosen on the pair (``w - 1`` -> ``w``) and scored on the
pair (``w`` -> ``w + 1``), as a causal encoder would choose it. The spacing uses
``[(w - SPAN_BEFORE) T0, (w + 1) T0)``, which the encoder holds.

Hot pixels. A pixel is hot if its events in the spacing span reach ``max(HOT_MIN, HOT_FACTOR x median)``, the
median over the pixels with events (the rule of ``ec.families.background_rate``). Its events are removed from
every window before anything else.

Spacing. For each pixel and polarity with at least two events in the span, ``tau`` is the median interval
between its consecutive events. A block's ``tau`` is the median over its pixels and polarities with an
interval (as ``ec.regions.block_spacing``), and ``covered`` the share of its pixels and polarities with events
that have one.

Motion. Per block of B pixels, ``best_shift`` chooses the integer displacement ``d`` with ``|dx|, |dy| <= R``
that pairs the most events, pixel by pixel and polarity by polarity over the whole window, between window
``w`` in the block and window ``w - 1`` moved by ``d``. Ties go to the smallest ``|dx| + |dy|``, then the
smallest ``(dy, dx)``. Then ``best_delay`` chooses a time offset ``delta`` in ``DELAYS`` that pairs the most
events on the grid (1 px, 32 slices) for the same pair, ties to the smallest ``|delta|``: a motion that is not
a whole number of pixels per window shifts the moved events in time, and the offset takes this up.

Prediction and score. The events of window ``w`` whose pixel moved by ``d`` falls in the block, with times
moved by ``T0 + delta`` and kept if they fall in window ``w + 1``, predict the block in window ``w + 1``. A
block enters if both the true and the predicted events of the block number at least N_MIN. The null keeps
the predicted pixels and polarities and draws their times uniformly in the window (``default_rng((SEED, w,
block))``); its pairs ``M0`` say what a prediction with the right pixels and no timing achieves.

Sums. For every grid ``(s, k)`` of GRIDS: ``N`` (true events), ``N2`` (predicted), ``M`` (pairs inside a voxel)
and ``M0`` (pairs of the null). ``pixel`` sums, for the grids with ``s = 1``, are taken per target pixel and
polarity, where pairs never cross pixels, and binned by that pixel's own ``r = dt / tau``. ``block`` sums are
binned by the block's ``r``, for blocks with ``covered >= COVER_MIN``. Both are split by ``speed``
(``|d|_inf`` <= 1, 2 to 5, >= 6 px per window) and by ``flicker`` (a ``tau`` within FLICKER_TOL of a period in
FLICKER_US, the 100 Hz and 120 Hz of mains lighting). Pixels without ``tau``, or with ``tau = 0`` (events of
one pixel and polarity in the same microsecond), fall in the last bin.
"""
from __future__ import annotations

import numpy as np

from . import blockcodec as bc
from . import families as fa
from . import regions as rg

T0 = bc.T0_US
B = 20
R = 16
N_MIN = 50
COVER_MIN = 0.8
SEED = 20261020
SPAN_BEFORE = rg.SPAN_BEFORE
GRIDS = tuple((1, k) for k in (1, 3, 6, 12, 32, 64, 128, 256)) + tuple((2, k) for k in (1, 3, 6, 12, 32, 64))
DELAYS = tuple(int(round(j * T0 / 64)) for j in range(-32, 33))
FIT_CELL = (1, 32)
FLICKER_US = (10_000.0, 1e6 / 120.0)
FLICKER_TOL = 0.02
R_EDGES = np.concatenate(([0.0], np.geomspace(1 / 128, 128, 29), [np.inf]))
N_BINS = len(R_EDGES)                       # bins 0 .. len - 2 by r, the last for "no tau"
SPEEDS = ((0, 1), (2, 5), (6, 10 ** 6))


def predicted(r, n):
    """Eq. (binfidmoved) at ``r = dt / tau``: ``r - r^2 / (3 n)`` for ``r <= 1/2``, NaN beyond; ``n = inf`` gives ``r``."""
    r = np.asarray(r, dtype=np.float64)
    f = r - (0.0 if np.isinf(n) else r * r / (3.0 * n))
    return np.where(r <= 0.5, f, np.nan)


def _window(ev, a: int, b: int):
    i, j = np.searchsorted(ev[0], (a, b))
    return tuple(np.asarray(v[i:j], dtype=np.int64) for v in ev)


class _ByBlock:
    """The events of one window sorted by block, to slice a block and its eight neighbours."""

    def __init__(self, ev, width: int, height: int):
        self.nbx, self.nby = -(-width // B), -(-height // B)
        bid = bc.block_ids(ev[1], ev[2], B, width)
        o = np.argsort(bid, kind="stable")
        self.ev = tuple(a[o] for a in ev)
        self.start = np.searchsorted(bid[o], np.arange(self.nbx * self.nby + 1))

    def around(self, b: int, reach: int):
        bx, by = b % self.nbx, b // self.nbx
        parts = []
        for yy in range(max(0, by - reach), min(self.nby, by + reach + 1)):
            for xx in range(max(0, bx - reach), min(self.nbx, bx + reach + 1)):
                c = yy * self.nbx + xx
                parts.append(slice(self.start[c], self.start[c + 1]))
        return tuple(np.concatenate([a[s] for s in parts]) for a in self.ev)


def _image(x, y, p, x0: int, y0: int, w: int, h: int):
    img = np.zeros((2, h, w), dtype=np.int64)
    sel = (x >= x0) & (x < x0 + w) & (y >= y0) & (y < y0 + h)
    np.add.at(img, (p[sel], y[sel] - y0, x[sel] - x0), 1)
    return img


def best_shift(ref, tru, bx0: int, by0: int, radius: int = R):
    """Integer displacement that pairs the most events of the block at (bx0, by0) over the whole window."""
    target = _image(tru[1], tru[2], tru[3], bx0, by0, B, B)
    src = _image(ref[1], ref[2], ref[3], bx0 - radius, by0 - radius, B + 2 * radius, B + 2 * radius)
    best, best_key = (0, 0), None
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            sx, sy = radius - dx, radius - dy           # a reference pixel at (x, y) moves to (x + dx, y + dy)
            m = int(np.minimum(target, src[:, sy:sy + B, sx:sx + B]).sum())
            key = (-m, abs(dx) + abs(dy), dy, dx)
            if best_key is None or key < best_key:
                best, best_key = (dx, dy), key
    return best, -best_key[0]


def _keys(t, x, y, p, w0: int, cell):
    s, k = cell
    return (((p * k + bc.time_bin(t - w0, k)) * 4096 + y // s) * 4096) + x // s


def _moved(ref, d, delta: int, bx0: int, by0: int, w0: int):
    """Events of ``ref`` moved by ``d`` and ``T0 + delta`` that land in the block and in ``[w0, w0 + T0)``."""
    t, x, y, p = ref
    mx, my, mt = x + d[0], y + d[1], t + T0 + delta
    sel = (mx >= bx0) & (mx < bx0 + B) & (my >= by0) & (my < by0 + B) & (mt >= w0) & (mt < w0 + T0)
    return mt[sel], mx[sel], my[sel], p[sel]


def _in_block(ev, bx0: int, by0: int):
    t, x, y, p = ev
    sel = (x >= bx0) & (x < bx0 + B) & (y >= by0) & (y < by0 + B)
    return t[sel], x[sel], y[sel], p[sel]


def _pairs(true, pred, w0: int, cell) -> int:
    ku, cu = np.unique(_keys(*true, w0, cell), return_counts=True)
    kv, cv = np.unique(_keys(*pred, w0, cell), return_counts=True)
    _, i, j = np.intersect1d(ku, kv, assume_unique=True, return_indices=True)
    return int(np.minimum(cu[i], cv[j]).sum())


def best_delay(ref, tru, d, bx0: int, by0: int, w0: int) -> int:
    """Time offset of DELAYS that pairs the most events on FIT_CELL; ties to the smallest |delta|."""
    true = _in_block(tru, bx0, by0)
    best, best_key = 0, None
    for delta in DELAYS:
        m = _pairs(true, _moved(ref, d, delta, bx0, by0, w0), w0, FIT_CELL)
        key = (-m, abs(delta), delta)
        if best_key is None or key < best_key:
            best, best_key = delta, key
    return best


def _pixel_pairs(true, pred, w0: int, cell, width: int):
    """Per target pixel and polarity: pairs inside a voxel of ``cell`` (s = 1), as (pixel-polarity keys, pairs)."""
    ku, cu = np.unique(_keys(*true, w0, cell), return_counts=True)
    kv, cv = np.unique(_keys(*pred, w0, cell), return_counts=True)
    com, i, j = np.intersect1d(ku, kv, assume_unique=True, return_indices=True)
    k = cell[1]
    x, r = com % 4096, com // 4096
    y, r = r % 4096, r // 4096
    p = r // k
    return (y * width + x) * 2 + p, np.minimum(cu[i], cv[j])


def _speed_class(d) -> int:
    v = max(abs(int(d[0])), abs(int(d[1])))
    return next(i for i, (a, b) in enumerate(SPEEDS) if a <= v <= b)


def _bin(r):
    r = np.asarray(r, dtype=np.float64)
    b = np.searchsorted(R_EDGES, r, side="right") - 1
    return np.where(np.isfinite(r), np.clip(b, 0, N_BINS - 2), N_BINS - 1)


def _flicker(tau):
    tau = np.asarray(tau, dtype=np.float64)
    out = np.zeros(tau.shape, dtype=bool)
    for per in FLICKER_US:
        out |= np.abs(tau - per) <= FLICKER_TOL * per
    return out


def hot_pixels(span, width: int, height: int):
    _, x, y, _ = span
    cnt = np.bincount(y * width + x, minlength=width * height)
    med = float(np.median(cnt[cnt > 0])) if (cnt > 0).any() else 0.0
    return cnt >= max(fa.HOT_MIN, fa.HOT_FACTOR * med)


def pixel_spacing(span, width: int):
    """Median interval (us) per pixel and polarity with at least two events; keys ``(y W + x) 2 + p``."""
    t, x, y, p = span
    pk = (y * width + x) * 2 + p
    o = np.lexsort((t, pk))
    pk_o, t_o = pk[o], t[o]
    start = np.flatnonzero(np.concatenate(([True], pk_o[1:] != pk_o[:-1])))
    size = np.diff(np.concatenate((start, [len(pk_o)])))
    keys = pk_o[start]
    tau = np.full(len(start), np.nan)
    d = np.diff(t_o)
    for i in np.flatnonzero(size >= 2):
        tau[i] = np.median(d[start[i]:start[i] + size[i] - 1])
    return keys, tau


def empty_sums():
    """Zero sums: ``[scope][flicker][speed]`` -> array (grids, bins, 4) with N, N2, M, M0."""
    return {scope: np.zeros((2, len(SPEEDS), len(GRIDS), N_BINS, 4), dtype=np.int64) for scope in ("pixel", "block")}


def evaluate_group(ev, w: int, width: int, height: int) -> dict:
    """Sums of the group keyed at ``w`` and a summary per entering block.

    ``ev`` = (t_us, x, y, p), nondecreasing in time, covering ``[(w - SPAN_BEFORE) T0, (w + 2) T0)``.
    """
    ev = tuple(np.asarray(a, dtype=np.int64) for a in ev)
    span = _window(ev, max(0, w - SPAN_BEFORE) * T0, (w + 1) * T0)
    hot = hot_pixels(span, width, height)
    keep = ~hot[ev[2] * width + ev[1]]
    ev = tuple(a[keep] for a in ev)
    span = _window(ev, max(0, w - SPAN_BEFORE) * T0, (w + 1) * T0)
    win = {m: _window(ev, (w + m) * T0, (w + m + 1) * T0) for m in (-1, 0, 1)}
    by = {m: _ByBlock(win[m], width, height) for m in (-1, 0, 1)}
    pk, ptau = pixel_spacing(span, width)
    nbx = -(-width // B)
    bid_s = bc.block_ids(span[1], span[2], B, width)
    n1 = np.diff(by[1].start)
    cand = np.flatnonzero(n1 >= N_MIN)
    btau, _, bcov = rg.block_spacing(*(a[np.isin(bid_s, cand)] for a in span), bid_s[np.isin(bid_s, cand)], cand, width)
    sums = empty_sums()
    rows = {"ids": [], "tau_us": [], "covered": [], "shift": [], "delta_us": [], "at_radius": [], "N": [], "N2": []}
    w1 = (w + 1) * T0
    for j, b in enumerate(cand):
        b = int(b)
        bx0, by0 = (b % nbx) * B, (b // nbx) * B
        a_prev, a_ref, a_tru = by[-1].around(b, 1), by[0].around(b, 1), by[1].around(b, 0)
        d, _ = best_shift(a_prev, _in_block(a_ref, bx0, by0), bx0, by0)
        delta = best_delay(a_prev, a_ref, d, bx0, by0, w * T0)
        true = _in_block(a_tru, bx0, by0)
        pred = _moved(a_ref, d, delta, bx0, by0, w1)
        if len(true[0]) < N_MIN or len(pred[0]) < N_MIN:
            continue
        rng = np.random.default_rng((SEED, int(w), b))
        null = (rng.integers(w1, w1 + T0, len(pred[0])), pred[1], pred[2], pred[3])
        sp = _speed_class(d)
        fl_b = int(_flicker(btau[j]))
        rows["ids"].append(b); rows["tau_us"].append(float(btau[j])); rows["covered"].append(float(bcov[j]))
        rows["shift"].append([int(d[0]), int(d[1])]); rows["delta_us"].append(int(delta))
        rows["at_radius"].append(bool(max(abs(d[0]), abs(d[1])) == R))
        rows["N"].append(int(len(true[0]))); rows["N2"].append(int(len(pred[0])))
        # pixel scope: target pixel-polarity keys and their own tau
        tk = (true[2] * width + true[1]) * 2 + true[3]
        qk = (pred[2] * width + pred[1]) * 2 + pred[3]
        for g, cell in enumerate(GRIDS):
            dt = T0 / cell[1]
            if bcov[j] >= COVER_MIN and np.isfinite(btau[j]):
                bb = int(_bin(dt / btau[j]))
                v = sums["block"][fl_b, sp, g, bb]
                v += (len(true[0]), len(pred[0]), _pairs(true, pred, w1, cell), _pairs(true, null, w1, cell))
            if cell[0] != 1:
                continue
            keys = np.concatenate((tk, qk))
            uk = np.unique(keys)
            pos = np.searchsorted(pk, uk)
            ok = (pos < len(pk)) & (pk[np.minimum(pos, len(pk) - 1)] == uk)
            tau_u = np.where(ok, ptau[np.minimum(pos, len(pk) - 1)], np.nan)
            with np.errstate(divide="ignore", invalid="ignore"):
                bins = _bin(np.where(tau_u > 0, dt / tau_u, np.nan))
            fl = _flicker(tau_u).astype(np.int64)
            acc = np.zeros((len(uk), 4), dtype=np.int64)
            np.add.at(acc[:, 0], np.searchsorted(uk, tk), 1)
            np.add.at(acc[:, 1], np.searchsorted(uk, qk), 1)
            for col, other in ((2, pred), (3, null)):
                kk, m = _pixel_pairs(true, other, w1, cell, width)
                np.add.at(acc[:, col], np.searchsorted(uk, kk), m)
            np.add.at(sums["pixel"], (fl, sp, g, bins), acc)
    return {"w": int(w), "n_hot": int(hot.sum()), "sums": sums, "blocks": rows}
