# Directive 020. Where motion stops predicting the counts of recorded events

| | |
|---|---|
| track | `threshold`, short name `th` |
| population | eTraM: the reporting recordings of directive 007. DSEC: the 36 reporting sequences of directive 013 |
| results directory | `results/th/` |
| report | `docs/directives/reports/020.md` |
| runs after | directive 019 |

## 1. Why

The manuscript's theory says that the counts of a window can be predicted from the previous window moved
by the motion only when the time slice dt of the receiver's grid is long compared with the event spacing
tau of the pixels. Eq. (binfidmoved) gives the fidelity of the moved events for dt <= tau / 2. Directive
019 confirmed the equation on the model, and found that x265 pays for its P frames as dt falls below tau.
What is missing is the same test on recordings, with tau measured pixel by pixel. That test is the bridge
from the model to real streams, and the paper's argument rests on it.

This directive measures, block by block and pixel by pixel:

- the fidelity of the best causal motion prediction against dt / tau;
- next to it, a null prediction with the right pixels and random times;
- next to it, the theory's prediction.

It runs no coder.

## 2. Disclosure

The director wrote `ec/threshold.py` and `tests/test_threshold_gate.py` and ran them on synthetic events
only. On the model, tau is recovered within 1% and the per-pixel fidelity follows Eq. (binfidmoved) within
0.02. On a textured translation, the shift is exact.

An independent review of the first version found no indexing errors but seven design problems. Each of
them would have biased the test toward "the theory fails at fine dt". All are addressed:

- **Motion chosen causally.** The motion is now chosen on the pair (w - 1, w) and scored on (w, w + 1).
  Before, it was fitted on the data it was scored on.
- **Time offset per block.** A time offset per block now takes up motion that is not a whole number of
  pixels per window.
- **Null prediction.** A null with random times now shows what the right pixels alone achieve.
- **Flicker reported separately.** On a 100 Hz flicker patch, the fidelity matches dt / tau with no
  motion at all. The median DSEC tau of report 017 is 9,999 us.
- **Hot pixels masked.** Hot pixels are masked with the rule of directive 018.
- **Per-pixel binning.** At 1 px, the sums are binned by each pixel's own tau, so that fast and slow
  pixels of a block are not pooled under one tau.
- **Entry after the shift.** A block now enters on its true and predicted counts after the shift. Before,
  it entered on its own reference count, which dropped moving content.

Two further changes:

- slices of 1/128 and 1/256 of a window were added, so that the range dt <= tau / 2 is covered for the
  measured spacings;
- the remaining limits (the unknown n, single-event pixels without tau, blocks at the search radius) are
  reported, not hidden.

The director read no recording.

## 3. Author decisions

**D-020-1, default: authorized.** The executor adds `ec/threshold.py` and `tests/test_threshold_gate.py`
with the content of Appendices A and B, unchanged.

**D-020-2, default: authorized.** The reads of directive 019, Section 4. DSEC events come from the caches
of directive 017.

**D-020-3, default: authorized.** The executor updates the host paths of `docs/DATA.md` to the locations
under `/data/<user>/event_coding/` to which the project's files were moved after directive 019. It notes
that symbolic links keep the old paths valid, and cites this directive.

**D-020-4, default: as stated in Sections 4 to 6.** The protocol.

## 4. Definitions

**Groups.** The D2 groups of directive 019: the Stage R groups of directive 016 with `j % 5 == 0`, on both
datasets.

**Events of a group.** The events of `[(w - 3) T0, (w + 2) T0)`.

**Strata.** Day and night for eTraM. `all` for DSEC.

## 5. Run

For every group, call `ec.threshold.evaluate_group(events, w, W, H)` and keep its output. The output
holds:

- the sums `sums[scope]` of shape (flicker, speed, grid, bin, 4), where the last axis is N, N2, M and M0;
- the per-block summary `blocks`;
- `n_hot`.

The outputs are kept under `~/prjs/event_coding/th/` (eTraM) and `/data/<user>/event_coding/ds/th/`
(DSEC). The sums add over groups and recordings.

## 6. Tables

For a set of sums: `F = 2 M / (N + N2)` and `F0 = 2 M0 / (N + N2)`. Recordings enter with the sums of their
groups. Report medians over recordings with 95% intervals (the bootstrap of directive 007, seed 20261016)
where a recording has at least 200 true events in the cell. Otherwise, report the pooled value and say so.

**Table 1, pixel scope, the main test.** For each stratum and each grid with s = 1, report per bin of r =
dt / tau (`ec.threshold.R_EDGES`), with flicker = 0 and all speeds pooled:

- F and F0, and their difference;
- the number of true events in the cell;
- `ec.threshold.predicted(r, 1)` and `predicted(r, inf)` at the bin's geometric centre. These bracket the
  equation over the unknown n, for bins with r <= 1/2.

**Table 2, pixel scope, by speed.** Table 1 split by the three speed classes.

**Table 3, block scope.** Table 1 at block scope, for the grids with s = 1 and s = 2.

**Table 4, flicker.** Tables 1 and 3 with flicker = 1: the share of true events in the flicker stratum,
and F and F0 per bin.

**Table 5, coverage.** Per stratum:

- the share of true events in pixels without tau (the last bin);
- the median `covered` of the entering blocks;
- the share of blocks at the search radius;
- the median |delta| and its share at the ends of `DELAYS`;
- the median `n_hot`;
- the number of entering blocks.

**Curve data.** Per stratum, scope, flicker, speed, grid and bin, the pooled N, N2, M and M0, in
`results/th/curves.json`. The manuscript draws its figure from this file.

## 7. Cost

- Project from the first 10 groups of each dataset.
- If the projection exceeds 40 CPU-hours, stop and report `BLOCKED` with it.
- Use the read lock and memory guard of directive 016.
- Do not compete with a companion-project job.

## 8. Acceptance checks

1. The two files have the SHA-256 of Section 10, and the suite passes with no skipped test.
2. For every group, `sums[..., 2] <= min(N, N2)` and `sums[..., 3] <= min(N, N2)` hold elementwise. For
   every group, the pixel-scope N summed over bins and strata at grid (1, 1) equals the sum of
   `blocks["N"]`.
3. Every group of Section 4 returned.
4. No eTraM val or test file was opened, and the annotation root was not listed. Nothing outside
   `results/th/` changed under `results/`.

## 9. Outputs

| file | content |
|---|---|
| `results/th/per_recording.json` | per recording, the summed sums, the number of groups and of entering blocks |
| `results/th/curves.json` | the curve data of Section 6 |
| `results/th/report.json` | Tables 1 to 5 |
| `results/th/provenance.json` | commit, host, versions, wall and CPU time, the files read |

## 10. Files

The SHA-256 is that of the file content: the text between the fence lines of its appendix, ending in one
newline.

| file | SHA-256 |
|---|---|
| `ec/threshold.py` | `15a4df953975039dc697fd022779384b99845d8e4b77e972a342b424ce7fdf23` |
| `tests/test_threshold_gate.py` | `dc4d7817640bf3a9fd91001f90fd031ad156f3588677206d46236eeaab80365b` |

## Appendix A. `ec/threshold.py`

````python
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
````

## Appendix B. `tests/test_threshold_gate.py`

````python
"""Gate for directive 020: per-pixel and per-block prediction of the counts against Eq. (binfidmoved).

The model scenes of ``ec.hevcdiag`` give a known spacing and motion; the textured translation of ``ec.synth``
gives a motion without the aperture problem. The tolerances are fixed by the director.
"""
import numpy as np

from ec import blockcodec as bc
from ec import hevcdiag as hd
from ec import synth
from ec import threshold as th

W, H = 320, 240
T0 = bc.T0_US


def pooled(sums, scope, cell, flicker=None):
    g = th.GRIDS.index(cell)
    a = sums[scope][:, :, g] if flicker is None else sums[scope][flicker:flicker + 1, :, g]
    return a.sum(axis=(0, 1))                      # (bins, 4)


def F(v):
    return 2 * v[..., 2] / np.maximum(v[..., 0] + v[..., 1], 1)


def test_model_follows_eq_binfidmoved_per_pixel_and_beats_the_null():
    for tau in (1000.0, 4000.0):
        ev = hd.edge_scene(W, H, 6, tau, 3, 0.05, 40, 8, 1)
        o = th.evaluate_group(ev, 5, W, H)
        assert len(o["blocks"]["ids"]) > 40
        assert np.mean(np.array(o["blocks"]["shift"])[:, 0] == 6) > 0.95
        assert np.median(o["blocks"]["tau_us"]) == np.median(o["blocks"]["tau_us"])
        for cell in [c for c in th.GRIDS if c[0] == 1]:
            v = pooled(o["sums"], "pixel", cell).sum(axis=0)
            r = (T0 / cell[1]) / tau
            pred = th.predicted(r, 3)
            if np.isfinite(pred):
                assert abs(F(v) - pred) < 0.02, (tau, cell, F(v), pred)
            m0 = 2 * v[3] / (v[0] + v[1])
            if r < 4:
                assert F(v) > m0                                   # timing carries information beyond the pixels


def test_subpixel_motion_is_taken_up_by_the_delay():
    tau = 4000.0
    ev = hd.edge_scene(W, H, 6, tau, 3, 0.05, 40, 8, 1)
    ref = th.evaluate_group(ev, 5, W, H)
    # the same scene at 6.5 px per window
    rng = np.random.default_rng(1)
    v = 6.5 / T0
    T, X, Y, P = [], [], [], []
    xs = np.arange(W)
    for e, x_e in enumerate(range(-int(np.ceil(v * 8 * T0)) - 40, W, 40)):
        for y in range(H):
            phi = rng.random()
            t0 = (xs - x_e + phi) / v
            ok = (t0 >= -3 * tau) & (t0 < 8 * T0)
            xx = xs[ok]
            A = (1.0 - rng.random(len(xx))) * tau
            for j in range(3):
                T.append(t0[ok] + A + j * tau + rng.normal(0, 0.05 * tau, len(xx))); X.append(xx)
                Y.append(np.full(len(xx), y)); P.append(np.full(len(xx), e % 2))
    t = np.rint(np.concatenate(T)).astype(np.int64)
    x, y, p = (np.concatenate(a).astype(np.int64) for a in (X, Y, P))
    k = (t >= 0) & (t < 8 * T0)
    o_ = np.argsort(t[k], kind="stable")
    ev2 = tuple(a[k][o_] for a in (t, x, y, p))
    o = th.evaluate_group(ev2, 5, W, H)
    assert np.mean(np.array(o["blocks"]["delta_us"]) != 0) > 0.8
    for cell in ((1, 32), (1, 64)):
        a = F(pooled(o["sums"], "pixel", cell).sum(axis=0))
        b = F(pooled(ref["sums"], "pixel", cell).sum(axis=0))
        assert a > 0.85 * b


def test_textured_translation_gives_the_true_shift():
    sc = synth.rigid_translation(width=W, height=H, n_points=3000, box_wh=(140.0, 100.0), c0=(120.0, 120.0),
                                 v=(180.0, 0.0), duration_s=0.4, seed=4)
    ev = tuple(np.asarray(a, dtype=np.int64) for a in (sc.t, sc.x, sc.y, sc.p))
    o = th.evaluate_group(ev, 5, W, H)
    s = np.array(o["blocks"]["shift"])
    assert len(s) >= 8 and np.mean((s[:, 0] == 6) & (s[:, 1] == 0)) > 0.9


def test_hot_pixels_are_removed_and_flicker_is_flagged():
    ev = hd.edge_scene(W, H, 6, 2000.0, 3, 0.05, 40, 8, 2)
    hot_t = np.arange(0, 8 * T0, 500)
    hot = (hot_t, np.full(len(hot_t), 33), np.full(len(hot_t), 77), np.zeros(len(hot_t), dtype=np.int64))
    fl_t = np.concatenate([np.arange(int(ph), 8 * T0, 10_000) for ph in np.linspace(0, 9000, 400)])
    fx = np.repeat(np.arange(200, 220), 20)[:400]
    fy = np.tile(np.arange(200, 220), 20)[:400]
    reps = np.repeat(np.arange(400), [len(np.arange(int(ph), 8 * T0, 10_000)) for ph in np.linspace(0, 9000, 400)])
    fl = (fl_t, fx[reps], fy[reps], np.ones(len(fl_t), dtype=np.int64))
    allv = tuple(np.concatenate(z) for z in zip(ev, hot, fl))
    o_ = np.argsort(allv[0], kind="stable")
    o = th.evaluate_group(tuple(a[o_] for a in allv), 5, W, H)
    assert o["n_hot"] >= 1
    taus = np.array(o["blocks"]["tau_us"])
    assert np.any(np.abs(taus - 10_000) < 200)
    assert o["sums"]["block"][1].sum() > 0                          # the flicker block is in the flicker stratum


def test_sums_are_consistent():
    ev = hd.edge_scene(W, H, 6, 2000.0, 3, 0.05, 40, 8, 2)
    o = th.evaluate_group(ev, 5, W, H)
    for scope in ("pixel", "block"):
        s = o["sums"][scope]
        assert np.all(s[..., 2] <= np.minimum(s[..., 0], s[..., 1])) and np.all(s[..., 3] <= np.minimum(s[..., 0], s[..., 1]))
    n = np.array(o["blocks"]["N"]).sum()
    assert o["sums"]["pixel"][:, :, 0, :, 0].sum() == n
    assert th.best_shift(*(tuple(np.zeros(0, dtype=np.int64) for _ in range(4)),) * 2, 100, 100) == ((0, 0), 0)
````
