# Directive 004. Regeneration with a sender-fitted affine map

| | |
|---|---|
| track | `affine`, short name `af` |
| population | the 112 development recordings of `config/population.yaml`, and no other recording |
| results directory | `results/af/` |
| report | `docs/directives/reports/004.md` |
| runs after | directive 003, once its report is `DONE` |

## 1. Why

The motion model of this project is affine in the image plane: an object
translates, and it also grows or shrinks as it approaches or recedes, and it
turns. Directives 001 to 003 measured translation. The only model with a scale
was `label` of directive 001, which takes it from the annotation boxes, and
D-002-1 set a scale-aware warp aside because `label` gained less than `cmax`.
That comparison shows that the boxes are noisy. It does not show that scale is
small.

The cameras of the population look along roads, so most objects approach or
recede. A box of 100 px that grows by 5% moves its edges by 2.5 px, more than
the 2 px block of the headline cell. On a synthetic object that grows by 50% per
second, the fidelity of the translation of directive 003 falls from 0.79 at the
first target to 0.19 at the tenth, a fall of the same shape as Table 3 of report
002, and an affine map holds it at 0.65 to 0.71 from the second target on.

**What this directive measures.** The codec of directive 003 with one change:
for each regenerated window the sender fits and transmits an affine map, six
integers in place of two. Stage A measures the fidelity, the event share and
`gamma` of the groups of directive 003 under that map, on the same rows, against
the translation that directive 003 sent. All definitions are in the docstring of
`ec/affine.py` (Appendix B), which is part of this directive.

## 2. Disclosure

This directive was written while directive 003 was running. Before it was
written the director had:

- seen no result of directive 003, only the cost projection in a commit
  message;
- read reports 001 and 002 and the committed aggregates of both;
- developed `ec/affine.py`, `ec/synth_affine.py` and the gate on synthetic data
  only. The search (its stages, offsets and starting points) was fixed there,
  after a first version without the coarse stages had missed the true map at
  long leads on the synthetic object.

## 3. Author decisions

**D-004-1, default: accepted.** The reason that D-002-1 gave for not measuring a
scale-aware model is withdrawn. Its conclusion on the lossless track stands.

**D-004-2, default: authorized.** The 112 development recordings, their
annotations, and this project's per-instant and per-row files on `cnt` are read.
The run stays on `cnt`.

**D-004-3, default: authorized.** The executor adds `ec/synth_affine.py`,
`ec/affine.py` and `tests/test_affine_gate.py` with the content of Appendices A,
B and C.

**D-004-4, default: as stated in Section 9.** The decision rule. It replaces the
consequences that D-003-3 attaches to its outcome: the codec is not frozen, and
no second dataset is named, before this directive has reported. The outcome of
D-003-3 itself is recorded as measured.

## 4. Isolation

As in directive 002, Section 4, with `results/af/population_check.json`. Write
only under `~/prjs/event_coding/` on the host and `results/af/` in the
repository.

## 5. Stage P: preflight

A failed check is a `BLOCKED` report with the evidence.

**P0. Directive 003.** `docs/directives/reports/003.md` exists with status
`DONE`. If it is `BLOCKED`, this directive is `BLOCKED` with that reason.

**P1. Environment.** The versions equal those of `results/gp/preflight.json`.

**P2. Inputs.** The Stage C per-row files of directive 003 exist and their
SHA-256 equal `results/gp/provenance.json`.

**P3. Gates.** `python3 -m pytest -q -p no:anyio` passes on the host with no
skipped test. The four gate files, `tests/test_motion_gate.py`,
`tests/test_regen_gate.py`, `tests/test_gop_gate.py` and
`tests/test_affine_gate.py`, are not edited.

## 6. Stage A: the affine map

Use `ec.affine.evaluate_affine` as it is. An accelerated implementation is
allowed under the rule of directive 001, Section 6.

**Rows.** Every row of Stage C of directive 003 (instant and target `m` = 1 to
10). `d_start` is `(aligned_dx, aligned_dy)` of that row. Within an instant, fit
the targets in the order `m` = 1 to 10. `q_prev` is the fitted map of target
`m - 1` of the same instant, and `None` for `m` = 1 or when that target was
skipped. `T2` = 33,333 us, `T1` = 100 ms, `margin_px` = 2, sensor 1280 x 720.

**Groups.** As in directive 003, Section 6, for `K` in {2, 4, 8, 11}, for the
model `affine`, next to `aligned` from the rows of directive 003.

**Bits.** `b_affine(K) = (key_bits + 72 (K - 1)) / N_K`, with `key_bits` and `N_K`
of directive 003.

**Growth stratum.** For each instant, the ratio of the label box area `w h` at
`t_e + 300 ms` to that at `t_e`: `growing` above 1.10, `shrinking` under 0.90,
`steady` otherwise. The labels serve only to sort the instants.

**Strata and aggregation.** Otherwise as in directive 003, with bootstrap seed
20261011. Differences and ratios between the two models are formed per instant
and then aggregated.

## 7. Tables for the report

1. **Headline, stratum H, by lighting:** for `K` in {2, 4, 8, 11}, the fidelity
   and `gamma` of `affine` and of `aligned`, and the ratio
   `gamma(affine) / gamma(aligned)`, at the headline cell and at the frame cell.
2. **Targets:** `F1` of `affine` and `aligned` and their difference at the
   headline cell and at the frame cell for `m` = 1 to 10, stratum H, by lighting.
   For each `m`: the share of rows with a nonzero shape parameter, and the median
   and the 10% and 90% quantiles of the common stretch
   `(ia / hx + id / hy) / 2` in percent.
3. **Growth:** `gamma` of both models and their ratio at `K` = 4 and `K` = 11,
   headline cell, for the three growth strata within stratum H, by lighting,
   with the number of instants in each.
4. **Speed and class:** the ratio `gamma(affine) / gamma(aligned)` and
   `gamma(affine)` at `K` = 4 and `K` = 11, headline cell, for each speed bin and
   class group, isolated instants, by lighting.
5. **Shape parameters:** at `m` = 4 and `m` = 10, stratum H, pooled rows: the 10%,
   50% and 90% quantiles of `ia`, `id`, `ib` and `ic`.
6. **Bits:** `b_affine(K)` next to `b_aligned(K)` of directive 003, stratum H, by
   lighting.
7. **Skips and search:** skips by reason and target, and the distribution of
   `affine_n_eval`.

## 8. What the report does not decide

The report states the outcome of the rule of Section 9 and no more. Whether the
paper's codec keeps six parameters, a subset, or adds a time offset is the
director's proposal after this report.

## 9. Predictions and decision rule

Written by the director before any result of directive 003 or of this directive
existed. Stratum H, headline cell, medians over recordings, the same range by
day and by night.

| quantity | predicted |
|---|---|
| `F1(affine) - F1(aligned)`, `m` = 1 | 0 to 0.03 |
| `F1(affine) - F1(aligned)`, `m` = 4 | 0.02 to 0.10 |
| `F1(affine) - F1(aligned)`, `m` = 10 | 0.05 to 0.25 |
| `gamma(affine) / gamma(aligned)` at `K` = 4 | 1.02 to 1.12 |
| `gamma(affine) / gamma(aligned)` at `K` = 11 | 1.08 to 1.45 |
| share of rows with a nonzero shape parameter, `m` = 10 | 0.5 to 0.95 |
| the ratio at `K` = 11 in the growth strata | larger in `growing` and `shrinking` than in `steady` |

On the synthetic object that grows by 50% per second, the ratio is 1.16 at `K` =
4 and 2.0 at `K` = 11. Real objects grow more slowly, and part of what the
translation misses is not affine, so the real ratios should be smaller.

**Rule (D-004-4).** At the headline cell, stratum H:

1. **Motion model.** If `gamma(affine)` is at least 1.10 times `gamma(aligned)`
   at `K` = 11, by day and by night, the codec's motion model is the affine map.
   Otherwise it stays the translation, and this directive is reported in the
   paper as an ablation.
2. **Codec.** With `gamma` of the model that step 1 selects:
   - **GO** for the validation phase if `gamma` at `K` = 4 is at least 2.0 by day
     and by night;
   - **NO-GO** if `gamma` is under 1.3 for every `K` in {2, 4, 8, 11}, by day and
     by night;
   - otherwise the director proposes one refinement before any second dataset.

## 10. Acceptance checks

1. P0 to P3 pass.
2. `results/af/population_check.json` was committed before the first event file
   was opened, and the report gives both commit hashes.
3. Every row of Section 6 is either scored or counted as a skip, with the skip
   reason that directive 003 recorded for it.
4. For every scored row, `n_source` and `n_future` equal those of directive 003,
   and every `translation` output equals the `aligned` output of directive 003
   exactly.
5. For every scored row, `affine_f1_s2_k3 >= translation_f1_s2_k3`.
6. For every scored row, every `affine` `F1` lies in [0, 1] and does not decrease
   along the nested coarsenings of directive 002, acceptance check 5.
7. The suite passes at the executed commit.

## 11. Outputs

| file | content |
|---|---|
| `results/af/population_check.json` | Section 4 |
| `results/af/preflight.json` | P0 to P3 and the cost projection |
| `results/af/per_recording.npz` | recording x stratum x quantity medians and instant counts |
| `results/af/report.json` | every table of Section 7 |
| `results/af/provenance.json` | commit, host, versions, wall time, and the path and SHA-256 of the per-row files kept on the host |

Per-row files stay on the host under `~/prjs/event_coding/af/` and are not
committed.

## 12. Cost

About 656,000 rows. The fit scores 116 to about 260 voxel grids per row, against
80 to 190 for the search of directive 003, so Stage A is expected to cost about
1.5 times the search part of Stage C. Probe 50 instants first. If the projected
total exceeds 150 CPU-hours, stop after the preflight and report the measured
cost. Do not compete with a companion-project job on `cnt`.

## 13. What comes next

The director reads reports 003 and 004 together and proposes the codec of the
paper. Theory note 1 treats a translating edge. Its extension to an affine map
keeps the structure of its Theorems 1 and 2, because a pixel still sees one
profile at a known, now pixel-dependent, speed, and it adds parameters to its
Corollary 1.

## Appendix A. `ec/synth_affine.py`

Normative. The executor commits this file unchanged.

```python
"""Synthetic expanding rigid object, for the gate of directive 004.

As ``ec.synth.rigid_translation``, with one addition: the object grows at a constant
rate. A scene point at offset ``o`` from the center sits at
``c0 + v t + (1 + expand_rate * t) o``, so it moves at its own constant velocity
``v + expand_rate * o``, and the box grows by the factor ``1 + expand_rate * t``.
This is an object that approaches the camera. Between two times the motion of the
points is a translation and a scale about the box center, an affine map.
"""
from __future__ import annotations

import numpy as np

from .synth import BOX_DTYPE, FRAME_US, SynthScene, _crossings


def expanding_translation(width=320, height=240, n_points=400, box_wh=(60.0, 40.0), c0=(40.0, 120.0),
                          v=(200.0, 0.0), expand_rate=0.0, duration_s=1.0, jitter_us=0.0, seed=0,
                          track_id=1, class_id=1) -> SynthScene:
    rng = np.random.default_rng(seed)
    w, h = box_wh
    ox = rng.uniform(-w / 2 + 1, w / 2 - 1, n_points)
    oy = rng.uniform(-h / 2 + 1, h / 2 - 1, n_points)
    pol = rng.integers(0, 2, n_points)
    T, X, Y, P, S = [], [], [], [], []
    eps = 1e-9
    for k in range(n_points):
        px0, py0 = c0[0] + ox[k], c0[1] + oy[k]
        vx, vy = v[0] + expand_rate * ox[k], v[1] + expand_rate * oy[k]
        tc = np.concatenate((_crossings(px0, vx, duration_s), _crossings(py0, vy, duration_s)))
        if tc.size == 0:
            continue
        xs = np.rint(px0 + vx * (tc + eps * np.sign(vx or 1.0))).astype(np.int64)
        ys = np.rint(py0 + vy * (tc + eps * np.sign(vy or 1.0))).astype(np.int64)
        tt = tc * 1e6 + (rng.normal(0.0, jitter_us, tc.size) if jitter_us > 0 else 0.0)
        T.append(tt); X.append(xs); Y.append(ys)
        P.append(np.full(tc.size, pol[k])); S.append(np.full(tc.size, k))
    t = np.rint(np.concatenate(T)).astype(np.int64)
    x = np.concatenate(X); y = np.concatenate(Y); p = np.concatenate(P); s = np.concatenate(S)
    ok = (x >= 0) & (x < width) & (y >= 0) & (y < height) & (t >= 0) & (t < int(duration_s * 1e6))
    t, x, y, p, s = t[ok], x[ok], y[ok], p[ok], s[ok]
    o = np.argsort(t, kind="stable")
    n_frames = int(np.floor(duration_s * 1e6 / FRAME_US)) + 1
    boxes = np.zeros(n_frames, dtype=BOX_DTYPE)
    tf = np.arange(n_frames) * FRAME_US
    g = 1.0 + expand_rate * tf * 1e-6
    boxes["t"] = np.rint(tf).astype(np.uint64)
    boxes["x"] = c0[0] + v[0] * tf * 1e-6 - g * w / 2
    boxes["y"] = c0[1] + v[1] * tf * 1e-6 - g * h / 2
    boxes["w"], boxes["h"] = g * w, g * h
    boxes["class_id"], boxes["track_id"], boxes["class_confidence"] = class_id, track_id, 1.0
    return SynthScene(t[o], x[o].astype(np.int32), y[o].astype(np.int32), p[o].astype(np.uint8),
                      s[o].astype(np.int32), boxes, width, height, tuple(v), float(jitter_us))
```

## Appendix B. `ec/affine.py`

Normative. The executor commits this file unchanged.

```python
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
```

## Appendix C. `tests/test_affine_gate.py`

Normative. The executor commits this file unchanged. It is the gate of Stage A.

```python
"""Gate for directive 004: regeneration with a sender-fitted affine map, on a synthetic expanding object.

The scenarios, seeds and tolerances are fixed here by the director. An executor implementation that
replaces or accelerates ``ec.affine`` must pass this file unchanged.
"""
import numpy as np

from ec import affine, annotations, gop, motion, regen, synth_affine

T1, T2 = 100_000, 33_333


def _groups(v, expand_rate, n_targets=10, **kw):
    """Groups keyed at the evaluation instants: the rows of ``ec.gop`` with those of ``ec.affine`` merged in."""
    sc = synth_affine.expanding_translation(v=v, expand_rate=expand_rate, duration_s=1.2, n_points=120, seed=0, **kw)
    tr = annotations.tracks(sc.boxes)[0]
    out = []
    for te in motion.evaluation_instants(tr):
        m0 = motion.evaluate_instant(sc.t, sc.x, sc.y, sc.p, tr, int(te), T1, 0, T2, sc.width, sc.height,
                                     models=("cmax",))
        if "skipped" in m0:
            continue
        rows = []
        for m in range(1, n_targets + 1):
            g = gop.evaluate_target(sc.t, sc.x, sc.y, sc.p, tr, int(te), m, T2, sc.width, sc.height,
                                    (m0["cmax_vx"], m0["cmax_vy"]), sizes=False)
            if "skipped" in g:
                rows = None
                break
            q_prev = tuple(rows[-1][f"affine_{n}"] for n in affine.PARAMS) if rows else None
            a = affine.evaluate_affine(sc.t, sc.x, sc.y, sc.p, tr, int(te), m, T2, sc.width, sc.height,
                                       (g["aligned_dx"], g["aligned_dy"]), q_prev)
            g.update(a)
            rows.append(g)
        if rows:
            out.append(rows)
    assert out
    return out


def _gamma(rows, model, K):
    r = rows[:K - 1]
    return gop.group_summary(rows[0]["n_source"], [a[f"{model}_n_pred"] for a in r], [a["n_future"] for a in r],
                             [a[f"{model}_f1_s2_k3"] for a in r])["gamma"]


def test_the_map_with_zero_shape_parameters_is_the_translation():
    sx, sy = np.array([10, 20, 30, 41]), np.array([5, 9, 6, 8])
    frame = affine.frame_of(sx, sy)
    assert frame == (25.5, 7.0, 15.5, 2.0)
    ix, iy = affine.move_affine(sx, sy, frame, (3, -2, 0, 0, 0, 0))
    assert list(ix) == [13, 23, 33, 44] and list(iy) == [3, 7, 4, 6]
    # ia = 2 moves the two edges of the rectangle by 2 px, outwards
    ix, _ = affine.move_affine(sx, sy, frame, (0, 0, 2, 0, 0, 0))
    assert ix[0] == 8 and ix[-1] == 43
    assert affine.MOTION_BITS == 72 and affine.PARAMS == ("dx", "dy", "ia", "ib", "ic", "id")


def test_a_translating_object_gets_no_shape_parameters():
    for rows in _groups((200.0, 0.0), 0.0):
        for r in rows:
            assert [r[f"affine_{n}"] for n in affine.PARAMS] == [r["aligned_dx"], r["aligned_dy"], 0, 0, 0, 0]
            assert r["affine_f1_s2_k3"] == r["aligned_f1_s2_k3"]


def test_the_translation_rows_are_those_of_directive_003():
    for rows in _groups((200.0, 0.0), 0.5):
        for r in rows:
            assert r["translation_n_pred"] == r["aligned_n_pred"]
            for s in regen.BLOCKS_PX:
                for k in regen.TIME_BINS:
                    assert r[f"translation_f1_s{s}_k{k}"] == r[f"aligned_f1_s{s}_k{k}"]


def test_an_approaching_object_is_followed_by_the_affine_map_and_not_by_the_translation():
    for rows in _groups((200.0, 0.0), 0.5):
        late = rows[6:]                                     # m = 7 .. 10, leads 200 to 300 ms
        assert min(r["affine_f1_s2_k3"] for r in late) > 0.55
        assert max(r["aligned_f1_s2_k3"] for r in late) < 0.3
        r = rows[9]                                         # the rectangle grows by 12 to 15% in 333 ms
        assert 4 <= r["affine_ia"] <= 6 and 2 <= r["affine_id"] <= 4
        assert abs(r["affine_ib"]) <= 1 and abs(r["affine_ic"]) <= 1
        assert _gamma(rows, "affine", 11) > 5.0 and _gamma(rows, "aligned", 11) < 3.5
        assert _gamma(rows, "affine", 4) > _gamma(rows, "aligned", 4) + 0.2


def test_a_receding_object_with_jitter():
    for rows in _groups((200.0, 0.0), -0.4, jitter_us=1000.0):
        assert rows[8]["affine_f1_s2_k3"] > 0.6 and rows[8]["aligned_f1_s2_k3"] < 0.4
        assert rows[8]["affine_ia"] < -2 and rows[8]["affine_id"] < -1


def test_the_affine_map_is_never_worse_than_the_translation():
    for kw in (dict(v=(200.0, 0.0), expand_rate=0.5), dict(v=(60.0, 20.0), expand_rate=0.8),
               dict(v=(200.0, 0.0), expand_rate=-0.4, jitter_us=3000.0)):
        for rows in _groups(**kw):
            for r in rows:
                assert r["affine_f1_s2_k3"] >= r["translation_f1_s2_k3"]
                assert 0.0 <= r["affine_f1_s1_k32"] <= r["affine_f1_s2_k32"] <= r["affine_f1_s4_k32"] <= 1.0
                assert r["affine_f1_s2_k32"] <= r["affine_f1_s2_k8"] <= r["affine_f1_s2_k1"]


def test_skips_and_reproducibility():
    sc = synth_affine.expanding_translation(v=(200.0, 0.0), expand_rate=0.5, duration_s=1.2, n_points=120, seed=0)
    tr = annotations.tracks(sc.boxes)[0]
    a = affine.evaluate_affine(sc.t, sc.x, sc.y, sc.p, tr, 600_000, 4, T2, sc.width, sc.height, (27, 0))
    b = affine.evaluate_affine(sc.t, sc.x, sc.y, sc.p, tr, 600_000, 4, T2, sc.width, sc.height, (27, 0))
    assert a == b and "skipped" not in a
    r = affine.evaluate_affine(sc.t, sc.x, sc.y, sc.p, tr, 50_000, 1, T2, sc.width, sc.height, (7, 0))
    assert r["skipped"] == "outside_track_life"
```
