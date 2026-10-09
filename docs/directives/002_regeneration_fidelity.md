# Directive 002. Regeneration fidelity of in-box events, and the bandwidth cap of directive 001

| | |
|---|---|
| track | `regeneration`, short name `rg` |
| population | the 112 development recordings of `config/population.yaml`, and no other recording |
| results directory | `results/rg/` |
| report | `docs/directives/reports/002.md` |
| runs after | directive 001 (`DONE`, results at `17a12d0`, report at `c3b0cbb`) |

## 1. Why

**What directive 001 found.** In stratum H at setting (100, 0), an in-box event
costs 18.3 bits when only the box is known, and 15.6 (day) and 15.3 (night) bits
when the template and the `cmax` motion are known. The motion-compensated
template removes about 3 of 18 bits, and explicit motion accounts for 2.04 and
1.63 of them. The outcome of D-001-3 is "intermediate".

The same tables say where the remaining bits sit. `eps(cmax)` is 0.02, so almost
every future event lies where the moved template puts mass. The template width
that scores best is 0.5 to 1 px, that is 4.5 to 7 ms at the object's speed. The
events of a moving object are therefore predictable to about a pixel and a few
milliseconds, and not more finely. A lossless code pays for the rest at every
event. Theory note 1 (`docs/theory/translation_edge.tex`, pull request 2) derives
this for a translating edge: given the edge and its velocity, each event still
costs a threshold phase or a timing jitter (its Theorem 1), and the description
is needed only while the timing tolerance is below the event spacing of a pixel
(its Theorem 2).

**What this directive measures.** A receiver that holds an object's events of the
last `T2` and its velocity can regenerate the next events by moving the old ones,
with no bits spent on the new events. Stage R measures how much of a receiver's
voxel-grid representation of the true events that regeneration reproduces, as a
function of the voxel size in space and time. Repeating the old events in place
is the comparison, and uniformly placed events give the chance level. All
definitions are in the docstring of `ec/regen.py` (Appendix A), which is part of
this directive.

The headline is, at 2 px blocks and 11.1 ms bins,

```
G = F1(cmax) - F1(static)                                                (1)
```

the fidelity that motion adds to repetition, together with `F1(cmax)` itself.

Stage R measures a predictor with a perfect past: the source events are the true
ones. A codec whose receiver holds only its own reconstruction can do no better.
No rate is reported here. Rate accounting belongs to the directive that
specifies a codec.

**Stage B** closes question 1 of report 001: the bandwidth set of `ec.motion`
ends at 1 px and the `static` model sits at that end in every instant.

## 2. Disclosure

Before this directive was written the director had:

- read report 001 and the committed files under `results/mp/` (aggregates only;
  the per-instant files are on the host and were not seen);
- written theory note 1, whose predictions P1 to P3 were stated before report 001
  existed;
- developed `ec/regen.py` and its gate on synthetic data from `ec/synth.py` only.
  The voxel grid, the skip thresholds and the gate tolerances were fixed there;
- chosen the headline cell (2 px, 11.1 ms) as a common receiver representation
  (half resolution, three bins per 33 ms window), before any Stage R number.

## 3. Author decisions

**D-002-1, default: accepted.** Directive 001 closes as "intermediate", and
neither further measurement named in D-001-3 is run. A finer grid is not needed:
`b_px` of `cmax` is at the smallest bandwidth in 0% of the instants. A
scale-aware warp is not supported by the tables: the `label` model, which
includes scale, gains less than `cmax` (2.52 against 2.86 bits by day). No
lossless motion-compensated coder is built. The project turns to regeneration
under a tolerance.

**D-002-2, default: authorized.** The 112 development recordings, their
annotations, and the per-instant files of directive 001 under
`~/prjs/event_coding/mp/run/` are read on `cnt`. The run stays on `cnt`, so that
Stage B can reproduce stored values exactly.

**D-002-3, default: as stated in Section 9.** The decision rule and its
thresholds.

**D-002-4, default: authorized.** The executor adds `ec/regen.py` and
`tests/test_regen_gate.py` with the content of Appendices A and B, and extends
`ec/motion.py` as Section 7 states, with unchanged defaults.

## 4. Isolation

As in directive 001, Section 4, with `results/rg/population_check.json`, and with
two changes:

- Build every annotation path from the recording identifier and the
  subdirectory now given in `docs/DATA.md`. Do not list any directory under the
  annotation root.
- `ec.annotations.find_annotation` searches the whole annotation root. Replace
  its search by the explicit path, or remove it, in the first commit of this
  directive.

Write only under `~/prjs/event_coding/` on the host and `results/rg/` in the
repository.

## 5. Stage P: preflight

A failed check is a `BLOCKED` report with the evidence.

**P1. Environment.** As P1 of directive 001. The versions must equal those of
`results/mp/preflight.json`. A difference is reported and, for Stage B, is a
`BLOCKED` condition.

**P2. Inputs.** The 700 per-instant files of directive 001 exist and their
SHA-256 equal `results/mp/provenance.json`.

**P3. Gates.** `python3 -m pytest -q -p no:anyio` passes on the host with no
skipped test. `tests/test_motion_gate.py` and `tests/test_regen_gate.py` are the
gates and are not edited.

## 6. Stage R: regeneration fidelity

Use `ec.regen.evaluate_regen` as it is. An accelerated implementation is allowed
under the rule of directive 001, Section 6.

**Rows.** Every row that directive 001 scored at the settings (100, 0),
(100, 33), (100, 100) and (100, 300). `v_cmax` is `(cmax_vx, cmax_vy)` of that
row. `T1` = 100 ms, `T2` = 33,333 us, `margin_px` = 2, sensor 1280 x 720.

**Skips.** `source_too_small` (fewer than 50 source events) and the reasons of
directive 001. Count them by reason and stratum. Do not change the thresholds.

**Strata and aggregation.** The strata of each row are those directive 001
assigned to it. Aggregation is that of directive 001, Section 6, with bootstrap
seed 20261009. Differences such as `G` are formed per row and then aggregated.

**Grid.** Blocks of 1, 2 and 4 px. Time bins per window `k` in {1, 3, 8, 32},
that is 33.3, 11.1, 4.17 and 1.04 ms. The headline cell is (2 px, `k` = 3). The
frame cell is (2 px, `k` = 1).

## 7. Stage B: the bandwidth cap of directive 001

**Rows.** The rows that directive 001 scored in stratum H at setting (100, 0),
sorted by recording identifier, `track_id` and `t_e`. Within each recording take
the rows at positions 0, 10, 20, and so on.

**Code.** `ec.motion.evaluate_instant` gains a keyword `bandwidths`, default
`BANDWIDTHS_PX`, passed to `predictive_cost`. `predictive_cost` returns, in
addition, for each bandwidth its code length before the selection penalty
(`bits_b`) and its fitted `eps` (`eps_b`). Nothing else changes, and
`tests/test_motion_gate.py` passes unchanged.

**Runs.** Score each row twice, with `B4` = (0.125, 0.25, 0.5, 1) px and with
`B6` = `B4` + (2, 4) px, for the three models.

**Quantities.** Per row: `Delta`, `gain`, `eps` and `b_px` under each set, the
paired differences `Delta(B6) - Delta(B4)` and `gain(B6) - gain(B4)` per model,
and for each bandwidth of `B6` the fixed-bandwidth gain
`ref_bits - bits_b - 0.5 log2(N) / N` and `eps_b`.

**Aggregation.** As in Stage R, with a recording entering at 3 or more of its
subsampled rows.

## 8. Tables for the report

1. **Headline, stratum H, D = 0, by lighting:** at the headline cell, `F1` of
   `cmax`, `label`, `static` and `uniform`, `G` of Eq. (1), `F1(cmax) -
   F1(uniform)`, precision and recall of `cmax`, and `cmax_n_pred / n_future`.
   The same `F1` values at the frame cell.
2. **Grid:** `F1` of `cmax`, `static` and `uniform` in the 12 cells, stratum H,
   D = 0, by lighting.
3. **Lead:** `F1` of the four models and `G` at the headline cell and at the
   frame cell, for D in {0, 33, 100, 300} ms, stratum H, by lighting.
4. **Speed and class:** `G`, `F1(cmax)` and `F1(static)` at the headline cell for
   each speed bin and class group, isolated rows, D = 0, by lighting.
5. **Overlap:** stratum H against the same stratum with overlapping rows.
6. **Skips:** counts by reason, lighting and class group, at each lead.
7. **Stage B, by lighting:** `Delta`, `gain` and `eps` of each model under `B4`
   and `B6`; the paired differences; the share of rows with `b_px` at 4 px, per
   model; the fixed-bandwidth gain and `eps_b` of each model at each bandwidth
   of `B6`.

## 9. Predictions and decision rule

Written by the director before any Stage R or Stage B number existed. Stratum H,
D = 0, medians over recordings.

| quantity | day | night |
|---|---|---|
| `F1(cmax)`, headline cell | 0.35 to 0.65 | 0.30 to 0.60 |
| `F1(static)`, headline cell | 0.20 to 0.45 | 0.20 to 0.45 |
| `F1(uniform)`, headline cell | 0.08 to 0.30 | 0.08 to 0.30 |
| `G` | 0.05 to 0.25 | 0.05 to 0.25 |
| `F1(cmax)`, frame cell | 0.50 to 0.80 | 0.45 to 0.75 |
| `F1(cmax)` at (2 px, 1.04 ms) | under 0.30 | under 0.30 |
| `F1(cmax)` at D = 300 ms over D = 0, headline cell | 0.5 to 0.9 | 0.5 to 0.9 |
| `G` in the speed bin 0 to 20 px/s, vehicles | within 0.03 of zero | within 0.03 of zero |
| Stage B, `Delta(B6) - Delta(B4)` | -0.6 to 0 bits | -0.6 to 0 bits |
| Stage B, `gain(cmax)` under `B6` minus under `B4` | 0 to 0.2 bits | 0 to 0.2 bits |

On the synthetic fixture at 200 px/s with 0.3 ms jitter, `F1(cmax)` is 0.85 at
the headline cell and 0.04 at (2 px, 1.04 ms), and `F1(static)` is 0.09. The
fidelity there is set by one quantity, the time an edge needs to cross a pixel
(5 ms at 200 px/s): a regenerated event is off by up to half of it. Real edges
fire several times per pixel, and their counts vary from pixel to pixel, so the
real values should fall below the fixture.

**Rule (D-002-3).** With `F1(cmax)` and `G` at the headline cell, stratum H,
D = 0:

- **GO** for a regenerating codec if `F1(cmax)` is at least 0.50 and `G` is at
  least 0.10, both by day and by night. The next directive then specifies the
  codec (a template that is refreshed, motion, and a coded innovation) and its
  rate accounting;
- **NO-GO** if `G` is under 0.03 by day and by night, or if `F1(cmax) -
  F1(uniform)` is under 0.10 by day and by night. Regeneration by motion then
  adds nothing at this resolution, and the project continues as theory note 1
  with the bit-budget analysis of the brief;
- otherwise the director proposes one further measurement, chosen from Tables 2
  to 4, before any codec is specified.

Stage B changes no decision. It replaces the lower bounds of directive 001 by
values that the paper can quote.

## 10. Acceptance checks

1. P1 to P3 pass.
2. `results/rg/population_check.json` was committed before the first event file
   was opened, and the report gives both commit hashes.
3. Every row of Section 6 is either scored or counted as a skip.
4. For every scored row of Stage R, `n_future` and `support_px` equal the values
   of directive 001 exactly.
5. For every scored row and model, every `F1` lies in [0, 1], and `F1` does not
   decrease along a nested coarsening: 1 to 2 to 4 px at fixed `k`, and `k` from
   32 to 8 to 1 and from 3 to 1 at fixed block size.
6. Stage B under `B4` reproduces `gain_bits`, `eps` and `b_px` of directive 001
   for every subsampled row and model, to 1e-9.
7. The suite passes at the executed commit.

## 11. Outputs

| file | content |
|---|---|
| `results/rg/population_check.json` | Section 4 |
| `results/rg/preflight.json` | P1 to P3 |
| `results/rg/per_recording.npz` | recording x lead x stratum x quantity medians and row counts, Stage R |
| `results/rg/bandwidth.json` | Stage B: Table 7 and the per-recording values behind it |
| `results/rg/report.json` | every table of Section 8 |
| `results/rg/provenance.json` | commit, host, versions, wall time, and the path and SHA-256 of the per-row files kept on the host |

Per-row files stay on the host under `~/prjs/event_coding/rg/` and are not
committed.

## 12. Cost

Stage R sorts and counts the events of two windows per row. About 260,000 rows
are expected to take under 20 CPU-hours, most of it reading the recordings.
Stage B scores about 2,200 rows. The two added bandwidths cost about four times
the original four, so it is expected to take 10 to 30 CPU-hours. Probe 50 rows of
each stage first. If the projected total exceeds 80 CPU-hours, stop after the
preflight and report the measured cost. Do not compete with a companion-project
job on `cnt`.

## 13. Answers to the questions of report 001

1. **Bandwidth cap.** Stage B answers it on a subsample. The decision does not
   rest on it: no value of `Delta` under 3 bits leads to a lossless coder, and a
   wider set is expected to lower `Delta`.
2. **`eps`.** Keep `eps` as defined. Stage B adds the fixed-bandwidth `eps_b`.
   From this directive on, the share that motion does not reproduce is carried by
   the fidelity of Stage R.
3. **Lead.** The rule of directive 001 is read at D = 0, as it was stated. The
   outcome is "intermediate" at every lead up to 100 ms, so the choice does not
   matter here.
4. **Accelerated `predictive_cost`.** Not needed for this directive. Stage B is a
   subsample and Stage R does not use it.

Deviation 1 of report 001 (directory names under the annotation root were
listed) is noted. `docs/DATA.md` now gives the subdirectory.

## 14. What comes next

On GO, directive 003 specifies a regenerating codec and measures rate against
fidelity on the development recordings, against the actual baseline
(`ec.baseline.tiled_sizes`). A second dataset with a downstream task comes after
that.

## Appendix A. `ec/regen.py`

Normative. The executor commits this file unchanged.

```python
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
```

## Appendix B. `tests/test_regen_gate.py`

Normative. The executor commits this file unchanged. It is the gate of Stage R.

```python
"""Gate for directive 002: regeneration fidelity on synthetic rigid translation with known truth.

The scenarios, seeds and tolerances are fixed here by the director. An executor implementation that
replaces or accelerates ``ec.regen`` must pass this file unchanged.
"""
import numpy as np

from ec import annotations, motion, regen, synth

T1, T2 = 100_000, 33_333


def _run(v, jitter_us=300.0, noise=0.0, label_noise=0.0, D=0, n_points=120, seed=0):
    sc = synth.rigid_translation(v=v, jitter_us=jitter_us, noise_rate_hz=noise, label_noise_px=label_noise,
                                 seed=seed, duration_s=1.2, n_points=n_points)
    tr = annotations.tracks(sc.boxes)[0]
    rows = []
    for te in motion.evaluation_instants(tr):
        m = motion.evaluate_instant(sc.t, sc.x, sc.y, sc.p, tr, int(te), T1, D, T2, sc.width, sc.height,
                                    models=("cmax",))
        if "skipped" in m:
            continue
        r = regen.evaluate_regen(sc.t, sc.x, sc.y, sc.p, tr, int(te), D, T2, sc.width, sc.height,
                                 (m["cmax_vx"], m["cmax_vy"]))
        if "skipped" not in r:
            rows.append(r)
    assert rows
    return {k: float(np.median([r[k] for r in rows])) for k in rows[0]}


def test_voxel_f1_on_small_sets():
    x = np.array([10, 10, 11, 40]); y = np.array([5, 5, 5, 9]); p = np.array([1, 1, 0, 1])
    t = np.array([100, 200, 300, 30_000])
    same = regen.voxel_f1(x, y, t, p, x, y, t, p, 0, T2, 1, 32)
    assert same["f1"] == 1.0 and same["precision"] == 1.0 and same["recall"] == 1.0
    assert regen.voxel_f1(x[:2], y[:2], t[:2], p[:2], x[:2], y[:2], t[:2], 1 - p[:2], 0, T2, 4, 1)["f1"] == 0.0
    # two of three predicted events share a voxel with the four true ones: min counts sum to 2
    r = regen.voxel_f1(x[:3] + 1, y[:3], t[:3], p[:3], x, y, t, p, 0, T2, 2, 1)
    assert r["precision"] == 2 / 3 and r["recall"] == 2 / 4 and abs(r["f1"] - 4 / 7) < 1e-12
    # 1 ms bins separate events that the whole-window bin joins
    a = regen.voxel_f1(x[:1], y[:1], t[:1], p[:1], x[:1], y[:1], t[:1] + 5_000, p[:1], 0, T2, 1, 1)
    b = regen.voxel_f1(x[:1], y[:1], t[:1], p[:1], x[:1], y[:1], t[:1] + 5_000, p[:1], 0, T2, 1, 32)
    assert a["f1"] == 1.0 and b["f1"] == 0.0


def test_moved_events_reproduce_the_window_and_repeated_ones_do_not():
    m = _run((200.0, 0.0))
    assert m["cmax_f1_s2_k3"] > 0.75 and m["cmax_f1_s1_k1"] > 0.9
    assert m["static_f1_s2_k3"] < 0.2 and m["uniform_f1_s2_k3"] < 0.2
    assert abs(m["cmax_f1_s2_k3"] - m["label_f1_s2_k3"]) < 0.05
    assert 0.9 < m["cmax_n_pred"] / m["n_future"] < 1.1


def test_fidelity_rises_with_the_time_bin():
    m = _run((200.0, 0.0))
    f = [m[f"cmax_f1_s2_k{k}"] for k in (32, 8, 3, 1)]
    assert f[0] < 0.2 and f[0] + 0.3 < f[1] < f[2] - 0.05 and f[2] < f[3] - 0.03
    slow = _run((40.0, 0.0))                           # one pixel takes 25 ms: only the whole window agrees
    assert slow["cmax_f1_s2_k1"] > 0.6 and slow["cmax_f1_s2_k3"] < 0.45


def test_fidelity_falls_with_timing_jitter():
    f = [_run((200.0, 0.0), jitter_us=j)["cmax_f1_s2_k3"] for j in (0.0, 3000.0, 10000.0)]
    assert f[0] > f[1] + 0.08 and f[1] > f[2] + 0.15


def test_noise_lowers_fidelity_and_raises_the_chance_level():
    clean, lo, hi = _run((200.0, 0.0)), _run((200.0, 0.0), noise=5.0), _run((200.0, 0.0), noise=20.0)
    assert clean["cmax_f1_s2_k3"] > lo["cmax_f1_s2_k3"] + 0.2 > hi["cmax_f1_s2_k3"] + 0.25
    assert clean["uniform_f1_s2_k3"] + 0.04 < lo["uniform_f1_s2_k3"] < hi["uniform_f1_s2_k3"] - 0.08


def test_label_move_fails_under_label_noise_and_cmax_does_not():
    m = _run((200.0, 0.0), label_noise=2.0)
    assert m["cmax_f1_s2_k3"] > m["label_f1_s2_k3"] + 0.3


def test_regeneration_holds_across_a_lead_and_repetition_does_not():
    m = _run((200.0, 0.0), D=300_000)
    assert m["cmax_f1_s2_k1"] > 0.8 and m["static_f1_s2_k1"] < 0.05


def test_uniform_reference_is_reproducible_and_skips_are_reported():
    sc = synth.rigid_translation(v=(200.0, 0.0), duration_s=1.2, n_points=120, seed=0)
    tr = annotations.tracks(sc.boxes)[0]
    a = regen.evaluate_regen(sc.t, sc.x, sc.y, sc.p, tr, 600_000, 0, T2, sc.width, sc.height, (200.0, 0.0))
    b = regen.evaluate_regen(sc.t, sc.x, sc.y, sc.p, tr, 600_000, 0, T2, sc.width, sc.height, (200.0, 0.0))
    assert a == b and "skipped" not in a
    r = regen.evaluate_regen(sc.t, sc.x, sc.y, sc.p, tr, 50_000, 0, T2, sc.width, sc.height, (200.0, 0.0))
    assert r["skipped"] == "outside_track_life"
    few = synth.rigid_translation(v=(200.0, 0.0), n_points=3, duration_s=1.2, seed=1)
    tf = annotations.tracks(few.boxes)[0]
    r = regen.evaluate_regen(few.t, few.x, few.y, few.p, tf, 600_000, 0, T2, few.width, few.height, (200.0, 0.0))
    assert r["skipped"] == "source_too_small"
```
