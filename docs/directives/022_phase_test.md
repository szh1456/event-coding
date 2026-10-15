# Directive 022. The phase test on recordings: do moved events keep the timing inside a train?

| | |
|---|---|
| track | `phase`, short name `ph` |
| population | the groups of directive 020 (the D2 groups of directive 019), and the model scenes of Section 4 |
| results directory | `results/ph/` |
| report | `docs/directives/reports/022.md` |
| runs after | directive 021 |

## 1. Why

Directive 020 found that the fidelity of a causal prediction on recordings does not follow
Eq. (binfidmoved) when it is binned by `r = dt / tau`, with `tau` the median interval of a pixel over
133 ms. That estimate is the director's error. On recordings a pixel often fires one or two events per
passing edge (a sixth to two fifths of the true events come from pixels with a single event in the span),
so the median interval often measures the gap between passages and not the spacing inside one.

On the model, the same estimator reproduces the pattern of the recordings. With two events per passage and
dense edges it puts pixels at small `r`, where they score far above the equation (`tests/test_phase_gate.py`,
`test_short_passages_bias_the_median_spacing_and_not_the_regular_one`). Where the spacing is measurable
(the slow blocks of report 020), the recordings come close to the equation.

The manuscript's mechanism makes a sharper prediction, which needs no estimate of `tau` over the span. A
moved train is `A_j + (k - 1) tau + e` and the true train `A_i + (k - 1) tau`, with independent phases, so the
position of the moved events inside the true train is uniform. This directive measures that position on
recordings, pixel by pixel:

- **Independent phases.** A uniform position supports the mechanism.
- **Correlated phases.** A position locked to a constant means the phases of neighbouring pixels are
  correlated on real sensors. Then motion carries timing inside the train, and the model's independence
  assumption fails in that share.

The directive also repeats the binned fidelity of 020 with a spacing taken from regular trains only, a
search radius of 32 px (a fifth of 020's blocks sat at 16 px), and a delay that is continuous instead of
on a grid of 0.52 ms.

## 2. Disclosure

The director wrote `ec/phase.py` and `tests/test_phase_gate.py` and ran them on synthetic events only.

**First review.** An independent review by a second agent found:

- that a nearest-neighbour delay wraps modulo `tau` at fractional speeds;
- that a motion fit by counts alone loses the true shift along edges;
- that a per-event position is biased by train truncation, while a per-pixel circular phase is not;
- that the regularity rule was loose;
- that the tests used whole speeds only.

**Second review** of the revision found:

- blocks without a source entering with shift (0, 0);
- that a shift of (0, 0) locks the phase through any timing that persists in one pixel (mains flicker);
- that a fixed near-tie tolerance loses the true shift at slow speeds.

All of these are fixed as Appendix A states:

- an onset delay;
- a near-tie rule scaled by the count noise;
- one circular phase per pixel;
- `RHO = 1.2` with a surrogate count;
- skipped source-less blocks;
- a separate slice for shift (0, 0);
- a flicker split.

The review measured a remaining inward shrink of the delay by 0.1 to 0.2 `tau` under window truncation, which
costs about 3% of fidelity and does not affect the phase.

**Model controls** of the director (200 x 160 pixels, `tau = 2 ms`, `n = 3`, `sigma = 0.05 tau`), with the mean
of `cos(2 pi u)` over pixels in the moving slice and F on (1 px, 1/128 window), where the equation gives
0.128:

| px per window | independent: mean cos (pixels) | independent: F | shared phases: mean cos | shared: F |
|---|---|---|---|---|
| 1.5 | -0.054 (683) | 0.081 | 0.889 | 0.415 |
| 2.5 | 0.025 (1,397) | 0.122 | 0.949 | 0.493 |
| 6.5 | 0.010 (3,940) | 0.121 | 0.959 | 0.546 |
| 13.3 | 0.000 (4,242) | 0.125 | 0.968 | 0.581 |

The test therefore separates the two hypotheses at every speed. The slowest case has the fewest pixels and
the lowest F.

The full suite passes. The director read no recording.

## 3. Author decisions

**D-022-1, default: authorized.** The executor adds `ec/phase.py` and `tests/test_phase_gate.py` with the
content of Appendices A and B, unchanged.

**D-022-2, default: authorized.** The runner may reuse the group list and the event reads of
`scripts/th_run.py` (eTraM read once per recording, at most six at once; DSEC from the caches of directive
017).

**D-022-3, default: as stated in Sections 4 to 7.** The protocol, including the reading rule of Section 6.

## 4. Definitions

**Groups and events.** Those of directive 020: the D2 groups of directive 019 on both datasets, and the events
of `[(w - 3) T0, (w + 2) T0)`.

**Strata.** Day and night for eTraM, `all` for DSEC.

**Model scenes.** On 320 x 240 pixels with `tau = 2 ms`, `n = 3`, `sigma_frac = 0.05`, `spacing = 40` and 8
windows, keyed at `w = 5`, for every speed in (1.5, 2.5, 6.5, 13.3) px per window, `shared` in (False, True)
and seed in (1, 2, 3):

    ec.phase.edge_scene_v(320, 240, v, 2000.0, 3, 0.05, 40, 8, seed, shared)

## 5. Run

For every group: `ec.phase.evaluate_group(events, w, W, H)`. For every model scene:
`ec.phase.evaluate_group(ev, 5, 320, 240)`.

Keep each output. Use `~/prjs/event_coding/ph/` for eTraM and the model, and
`/data/<user>/event_coding/ds/ph/` for DSEC. The sums and the phase arrays add over groups and recordings.

## 6. Tables

Recordings enter with the sums of their groups. Unless a table says otherwise, report:

- the value pooled over the recordings of a stratum;
- a 95% interval from a bootstrap over recordings (the bootstrap of directive 007, seed 20261016);
- the number of recordings and of pixels or events behind each cell.

**Table 1, the phase test (the main result).** Per stratum, speed class and zero slice (moving blocks, `zero =
0`; shift (0, 0), `zero = 1`), with `flicker = 0` and all `tau_i` bins pooled:

- the pixels counted, and the mean of `cos(2 pi u)` and of `sin(2 pi u)` for `pred` and for `null`.

Then the same per `tau_i` bin of `ec.phase.TAU_EDGES`, for the moving slice. The 20-bin histograms of `u` go
in `curves.json`.

**Reading rule, fixed before any number is seen.** In the moving slice with `flicker = 0`, pooled over the
speed classes of a stratum:

- a mean cos whose 95% interval lies below 0.1 reads as independent phases;
- an interval that lies above 0.3 reads as correlated phases;
- anything else reads as partial correlation.

The report states this reading per stratum. The director decides what the manuscript draws from it.

**Table 2, binned fidelity with the regular spacing.** For each of `tau_med` and `tau_reg`, the layout of Table
1 of report 020: per stratum and grid with s = 1 and k in (3, 12, 32, 64, 256), F and F0 per bin of `r`,
with `ec.threshold.predicted(r, 1)` and `predicted(r, inf)` at the bin centre, flicker = 0, all speeds
pooled. Cells follow the 200-event rule of report 020. The `tau_med` columns differ from 020 only by the
motion fit, so the report gives both next to 020's values for (1, 32).

**Table 3, Table 2 by speed** for `tau_reg` at (1, 32) and (1, 64).

**Table 4, coverage.** Per stratum:

- the share of true events in pixels without `tau_reg`;
- `regular_share` (real against surrogate), as a ratio;
- the share of candidate blocks skipped for lack of a source;
- the share of entering blocks at the search radius, and the share with shift (0, 0);
- the median of `runner_up`;
- the median of `abs(delta)`;
- the number of entering blocks.

**Table 5, the model scenes.** Per speed and `shared`, the mean over seeds of:

- the pixels counted and the mean cos and sin of `pred`;
- F at (1, 32), (1, 64) and (1, 128), with the equation.

This table checks the code on the host against Section 2.

**Curve data.** `results/ph/curves.json` holds, per stratum, speed, zero slice, flicker and `tau_i` bin, the
phase histograms and statistics, and the pooled N, N2, M and M0 of Table 2 per grid and bin. The
manuscript draws its figures from this file.

## 7. Cost

- Project from the first 10 groups of each dataset.
- If the projection exceeds 40 CPU-hours, stop and report `BLOCKED` with it.
- Directive 020 cost 3.9 CPU-hours. The director's dense synthetic group of 1280 x 720 pixels and 5.6 M events
  took about 70 s, against 205 s before the vectorization.
- Use the read lock and memory guard of directive 016. Do not compete with a companion-project job.

## 8. Acceptance checks

1. The two files have the SHA-256 of Section 10, and the suite passes with no skipped test.
2. For every group, for both `tau` kinds, these hold elementwise: `M <= min(N, N2)` and `M0 <= min(N, N2)`.
   The N at grid (1, 1), summed over bins, speeds and flicker, equals the sum of `blocks["N"]`. The pixel
   counts of the `pred` and `null` phase statistics are equal cell by cell.
3. Every group of Section 4 returned, and every model scene.
4. Table 5 agrees with Section 2:
   - independent phases give a mean cos within 4 standard errors of 0;
   - shared phases give a mean cos above 0.85 at 2.5, 6.5 and 13.3 px per window.
5. No eTraM val or test file was opened, and the annotation root was not listed. Nothing outside `results/ph/`
   changed under `results/`.

## 9. Outputs

| file | content |
|---|---|
| `results/ph/per_recording.json` | per recording, the summed sums and phase arrays, the number of groups, entering and skipped blocks |
| `results/ph/model.json` | the model outputs per scene |
| `results/ph/curves.json` | the curve data of Section 6 |
| `results/ph/report.json` | Tables 1 to 5, and the reading of Table 1 per stratum |
| `results/ph/provenance.json` | commit, host, versions, wall and CPU time, the files read |

## 10. Files

The SHA-256 is that of the file content: the text between the fence lines of its appendix, ending in one
newline.

| file | SHA-256 |
|---|---|
| `ec/phase.py` | `11f80fd610c503acea5a4b452698074f9b765fefa43e97a968a9d583b1aa5d50` |
| `tests/test_phase_gate.py` | `e5b4914fe4585401b7e59046704df34f1beb967a47b91c647743bedaf9d8e2e7` |

## Appendix A. `ec/phase.py`

````python
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
````

## Appendix B. `tests/test_phase_gate.py`

````python
"""Gate for directive 022: the phase test, the regular spacing and the motion fit, on constructed trains and on
the model at whole and fractional speeds. The tolerances are fixed by the director."""
import numpy as np

from ec import blockcodec as bc
from ec import hevcdiag as hd
from ec import phase as ph
from ec import threshold as th

T0 = bc.T0_US
W, H = 200, 160


def _ev(rows):
    t = np.array([r[0] for r in rows], dtype=np.int64)
    x, y, p = (np.array([r[i] for r in rows], dtype=np.int64) for i in (1, 2, 3))
    o = np.argsort(t, kind="stable")
    return tuple(a[o] for a in (t, x, y, p))


def test_regular_spacing_by_construction():
    rows = [(1000 * k, 0, 0, 1) for k in range(4)]                          # regular: 1000
    rows += [(t, 1, 0, 1) for t in (0, 1000, 21000, 22000)]                  # two passages of two: none
    rows += [(50000 * k, 2, 0, 1) for k in range(3)]                         # one event per passage: none
    rows += [(t, 3, 0, 1) for t in (0, 1000, 2100, 32100)]                   # 1000 and 1100 regular
    rows += [(t, 4, 0, 1) for t in (0, 1000)]                                # two events: none
    rows += [(t, 5, 0, 1) for t in (0, 15000, 30000, 45000)]                 # regular, two intervals within T0
    rows += [(t, 7, 0, 1) for t in (0, 1000, 2300)]                          # ratio 1.3 > RHO: none
    keys, tau = ph.regular_spacing(_ev(rows), W)
    got = dict(zip(((keys // 2) % W).tolist(), tau.tolist()))
    assert got == {0: 1000.0, 3: 1050.0, 5: 15000.0}
    keys, tau = ph.regular_spacing(_ev([(20000 * k, 6, 0, 0) for k in range(4)]), W)
    assert len(keys) == 0                                                     # 40 ms > T0


def test_median_spacing_equals_directive_020():
    rng = np.random.default_rng(3)
    n = 4000
    ev = _ev(list(zip(rng.integers(0, 4 * T0, n), rng.integers(0, 30, n), rng.integers(0, 20, n), rng.integers(0, 2, n))))
    k1, t1 = ph.median_spacing(ev, W)
    k2, t2 = th.pixel_spacing(ev, W)
    ok = np.isfinite(t2)
    assert np.array_equal(k1, k2[ok]) and np.allclose(t1, t2[ok])


def test_pixel_phases_by_construction():
    true = _ev([(1000 * k, 5, 5, 1) for k in range(4)]
               + [(t, 6, 5, 1) for t in (0, 1000, 5000)]                      # irregular
               + [(1000 * k + 300, 7, 5, 0) for k in range(3)])
    pred = _ev([(250, 5, 5, 1), (1250, 5, 5, 1), (3250, 5, 5, 1), (500, 6, 5, 1), (900, 7, 5, 0), (400, 8, 5, 1)])
    u, tau = ph.pixel_phases(true, pred, W)
    assert np.allclose(np.sort(u), [0.25, 0.6]) and np.allclose(tau, 1000.0)


def test_pixel_phases_are_uniform_under_independent_phases():
    rng = np.random.default_rng(5)
    for e in (0.0, 0.5, 1.5, 2.5):                                            # residual offset in units of tau
        rows_t, rows_p = [], []
        for i in range(3000):
            tau, nt, nq = 1000.0, rng.integers(3, 6), rng.integers(1, 6)
            a, b = rng.random() * tau, rng.random() * tau
            rows_t += [(int(a + k * tau + rng.normal(0, 50)) + 10000, i % 200, i // 200, 1) for k in range(nt)]
            rows_p += [(int(b + (k + e) * tau) + 10000, i % 200, i // 200, 1) for k in range(nq)]
        u, _ = ph.pixel_phases(_ev(rows_t), _ev(rows_p), W)
        assert len(u) > 2500
        assert abs(np.mean(np.cos(2 * np.pi * u))) < 0.05 and abs(np.mean(np.sin(2 * np.pi * u))) < 0.05


def test_onset_delay_recovers_a_shift_of_trains():
    rng = np.random.default_rng(0)
    rows = []
    for i in range(300):
        a = 5000 + rng.random() * 20000
        rows += [(int(a + 1000 * k), i % 50, i // 50, 1) for k in range(3)]
    true = _ev(rows)
    moved = (true[0] - 300, true[1], true[2], true[3])
    assert ph.onset_delay(moved, true, 0, W) == 300
    assert ph.onset_delay(tuple(a[:0] for a in true), true, 0, W) == 0


def test_choose_shift_prefers_the_smallest_near_tie():
    r = 3
    s = np.zeros((2 * r + 1, 2 * r + 1), dtype=np.int64)
    s[r, r + 3] = 100                                                          # dx = 3
    s[r, r + 2] = 81                                                           # dx = 2: within 2 sqrt(100) = 20
    s[r - 1, r - 1] = 79                                                       # dx = -1, dy = -1: outside, far
    d, pairs, runner = ph.choose_shift(s, r)
    assert d == (2, 0) and pairs == 100 and runner == 0.79
    s[r, r + 2] = 79
    assert ph.choose_shift(s, r)[0] == (3, 0)
    assert ph.choose_shift(np.zeros_like(s), r) == ((0, 0), 0, 0.0)


def test_shift_scores_match_directive_020():
    ev = hd.edge_scene(W, H, 6, 2000.0, 3, 0.05, 40, 8, 1)
    a = th._window(ev, 4 * T0, 5 * T0)
    b = th._in_block(th._window(ev, 5 * T0, 6 * T0), 60, 40)
    s = ph.shift_scores(a, b, 60, 40, th.R)
    d, m = th.best_shift(a, b, 60, 40)
    assert s.max() == m and s[d[1] + th.R, d[0] + th.R] == m


def test_independent_phases_read_uniform_and_shared_phases_lock():
    for v in (1.5, 2.5, 3.5, 6.0, 6.5, 13.3):
        for shared in (False, True):
            ev = ph.edge_scene_v(W, H, v, 2000.0, 3, 0.05, 40, 8, 1, shared)
            o = ph.evaluate_group(ev, 5, W, H)
            c, n = o["phase_stat"]["pred"][:, 0].sum(axis=(0, 1, 2)), o["phase_stat"]["null"][:, 0].sum(axis=(0, 1, 2))
            assert c[0] > 500 and n[0] > 50, (v, c[0], n[0])
            cos, sin = c[1] / c[0], c[2] / c[0]
            if shared:
                assert cos > 0.85, (v, cos)
            else:
                se = np.sqrt(0.5 / c[0])                                       # standard error of a mean cos or sin
                assert abs(cos) < 4 * se and abs(sin) < 4 * se, (v, cos, sin)
            assert abs(n[1] / n[0]) < 0.08 and abs(n[2] / n[0]) < 0.08


def test_regular_tau_follows_eq_binfidmoved_on_the_model():
    tau = 4000.0
    for v, tol in ((6.0, 0.02), (2.5, 0.2), (6.5, 0.15), (13.3, 0.2)):        # tol: absolute, then relative
        ev = ph.edge_scene_v(W, H, v, tau, 3, 0.05, 40, 8, 1, False)
        o = ph.evaluate_group(ev, 5, W, H)
        s = o["sums"]["reg"][0].sum(axis=0)
        for g, cell in enumerate(ph.GRIDS):
            r = (T0 / cell[1]) / tau
            pred = float(th.predicted(r, 3))
            if np.isfinite(pred) and r >= (1 / 64 if v == 6.0 else 1 / 16):
                v_ = s[g].sum(axis=0)
                f = 2 * v_[2] / (v_[0] + v_[1])
                err = abs(f - pred) if v == 6.0 else abs(f - pred) / pred
                assert err < tol, (v, cell, f, pred)
        for kind in ph.TAU_KINDS:
            a = o["sums"][kind]
            assert np.all(a[..., 2] <= np.minimum(a[..., 0], a[..., 1]))
            assert np.all(a[..., 3] <= np.minimum(a[..., 0], a[..., 1]))
            assert int(a[:, :, 0, :, 0].sum()) == int(np.sum(o["blocks"]["N"]))
        assert np.array_equal(o["phase_stat"]["pred"][..., 0], o["phase_stat"]["null"][..., 0])
        real, sur = o["regular_share"]
        assert sur < 0.1 * real


def test_short_passages_bias_the_median_spacing_and_not_the_regular_one():
    ev = hd.edge_scene(W, H, 6, 1000.0, 2, 0.05, 10, 8, 1)                     # two events per passage, dense edges
    o = ph.evaluate_group(ev, 5, W, H)
    g = ph.GRIDS.index((1, 64))
    med, reg = o["sums"]["med"][0].sum(axis=0)[g], o["sums"]["reg"][0].sum(axis=0)[g]
    small = th.R_EDGES[1:] <= 1 / 16
    v = med[:-1][small].sum(axis=0)
    assert v[0] > 200
    assert 2 * v[2] / (v[0] + v[1]) > 5 * float(th.predicted(1 / 16, np.inf))
    assert reg[:-1].sum(axis=0)[0] < 0.05 * reg.sum(axis=0)[0]


def test_the_wider_radius_finds_fast_motion():
    ev = hd.edge_scene(W, H, 24, 2000.0, 3, 0.05, 60, 8, 1)
    o = ph.evaluate_group(ev, 5, W, H)
    sh = np.array(o["blocks"]["shift"])
    assert len(sh) > 10 and np.mean(np.abs(sh[:, 0] - 24) <= 1) > 0.7 and np.mean(sh[:, 1] == 0) > 0.9


def test_blocks_without_a_source_are_skipped():
    ev = ph.edge_scene_v(W, H, 13.3, 2000.0, 3, 0.05, 40, 8, 1, False)
    o = ph.evaluate_group(ev, 5, W, H)
    assert o["skipped_no_source"] > 0
    assert all(p >= th.N_MIN / 2 for p in o["blocks"]["pairs"])
    assert not any(b % (-(-W // th.B)) == 0 and s == [0, 0] for b, s in zip(o["blocks"]["ids"], o["blocks"]["shift"]))


def test_static_flicker_goes_to_the_zero_slice():
    rng = np.random.default_rng(2)
    rows = []
    for x in range(40, 80):
        for y in range(40, 60):
            a = rng.random() * 10000.0                                         # independent phase per pixel
            rows += [(int(a + 10000.0 * k), x, y, 1) for k in range(int(8 * T0 / 10000.0))]
    ev = _ev(rows)
    o = ph.evaluate_group(ev, 5, W, H)
    pz = o["phase_stat"]["pred"][:, 1].sum(axis=(0, 1, 2))
    pm = o["phase_stat"]["pred"][:, 0].sum(axis=(0, 1, 2))
    assert len(o["blocks"]["ids"]) > 0 and all(s == [0, 0] for s in o["blocks"]["shift"])
    assert pz[0] > 100 and pm[0] == 0
    assert o["phase_stat"]["pred"][:, 1, 1].sum(axis=(0, 1))[0] == pz[0]       # flicker class
````
