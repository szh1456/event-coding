# Directive 003. Key windows and regenerated windows: fidelity per event sent

| | |
|---|---|
| track | `groups`, short name `gp` |
| population | the 112 development recordings of `config/population.yaml`, and no other recording |
| results directory | `results/gp/` |
| report | `docs/directives/reports/003.md` |
| runs after | directive 002 (`DONE`, results at `25f8d20`, report at `64f76f6`) |

## 1. Why

**What directive 002 found.** Rule D-002-3 gives GO. With no bits spent on the
new events, moving an object's last 33 ms of events along its `cmax` velocity
reproduces 0.65 (day) and 0.66 (night) of the receiver's voxel grid at 2 px and
11.1 ms, against 0.24 and 0.34 for repeating them and 0.11 for chance. The
fidelity falls with the lead: 0.47 and 0.51 at 100 ms, 0.27 and 0.28 at 300 ms.
In directive 002 the velocity was estimated before the key window and
extrapolated, so that fall mixes two causes: the error of the extrapolated
velocity, which a sender can remove by transmitting the displacement, and the
aging of the events themselves, which it cannot.

**What this directive measures.** The simplest regenerating codec. The sender
transmits one window of an object's events (the key window) and, for each of the
next `K - 1` windows, one displacement that it fits to the true events. The
receiver moves the key events. Stage C measures, for groups of `K` windows, the
fidelity of the receiver's voxel grid and the share of the events that was sent.
The comparison is random thinning, which sends a share `q` of all events and has
fidelity `2 q / (1 + q)` on every voxel grid. The headline is

```
gamma(K) = q_eq / phi                                                    (1)
```

the factor by which regeneration lowers the number of events sent at equal
fidelity, with `phi` the share sent and `q_eq` the share thinning needs. All
definitions are in the docstring of `ec/gop.py` (Appendix A), which is part of
this directive.

`gamma` counts events, so it does not depend on how a sent event is coded. Stage
C also sizes the sent events with the transport of the companion project, to
state the result in bits. Stage S measures which share of a recording's events
lies in annotated boxes at all, because regeneration acts only there.

## 2. Disclosure

Before this directive was written the director had:

- read reports 001 and 002 and the committed files under `results/mp/` and
  `results/rg/` (aggregates only);
- developed `ec/gop.py` and its gate on synthetic data from `ec/synth.py` only.
  The search of the displacement, the group sizes and the gate tolerances were
  fixed there;
- kept the headline cell (2 px, 11.1 ms) and the stratum H of directive 002.

## 3. Author decisions

**D-003-1, default: authorized.** The 112 development recordings, their
annotations, and the per-instant files of directive 001 and the per-row files of
directive 002 on `cnt` are read. The run stays on `cnt`.

**D-003-2, default: authorized.** The executor adds `ec/gop.py` and
`tests/test_gop_gate.py` with the content of Appendices A and B.

**D-003-3, default: as stated in Section 9.** The decision rule and its
thresholds.

**D-003-4, default: accepted.** Question 1 of report 002 is closed without a
further run. The paper quotes `Delta` under `B6` (1.55 and 1.29 bits) as an upper
bound on what explicit motion saves losslessly, and the fixed-bandwidth gain of
`cmax`, which peaks inside the set at 0.5 to 1 px (2.76 and 2.98 bits), as its
uncensored value.

## 4. Isolation

As in directive 002, Section 4, with `results/gp/population_check.json`. Write
only under `~/prjs/event_coding/` on the host and `results/gp/` in the
repository.

## 5. Stage P: preflight

A failed check is a `BLOCKED` report with the evidence.

**P1. Environment.** The versions equal those of `results/rg/preflight.json`. A
difference is a `BLOCKED` condition, because acceptance check 4 compares exactly.

**P2. Inputs.** The per-instant files of directive 001 and the Stage R per-row
files of directive 002 exist and their SHA-256 equal the two provenance files.

**P3. Gates.** `python3 -m pytest -q -p no:anyio` passes on the host with no
skipped test. `tests/test_motion_gate.py`, `tests/test_regen_gate.py` and
`tests/test_gop_gate.py` are the gates and are not edited.

## 6. Stage C: groups

Use `ec.gop.evaluate_target` as it is. An accelerated implementation is allowed
under the rule of directive 001, Section 6.

**Rows.** Every instant that directive 001 scored at setting (100, 0), with the
targets `m` = 1 to 10. `v_cmax` is `(cmax_vx, cmax_vy)` of that instant. `T1` =
100 ms, `T2` = 33,333 us, `margin_px` = 2, sensor 1280 x 720, `sizes=True`.

**Skips.** Those of `ec.regen.evaluate_regen`, counted by reason, target and
stratum.

**Groups.** For `K` in {2, 4, 8, 11} and each model in {`aligned`, `cmax`,
`static`}, `ec.gop.group_summary` on the targets `m` = 1 to `K - 1` of an
instant, at the headline cell (2 px, `k` = 3) and at the frame cell (2 px, `k` =
1). An instant with a skipped target among them has no group of that size. Count
those.

**Transport sizes.** With `N_K = n_source + sum of n_future` over the targets of
a group:

```
b_direct(K)  = (key_bits + sum of true_bits) / N_K
b_aligned(K) = (key_bits + 24 (K - 1)) / N_K
b_thin(q)    = thin_bits_q / n_future          (target m = 1 only)
```

all in bits per original event.

**Strata and aggregation.** The strata of an instant are those directive 001
assigned to it at setting (100, 0). Aggregation is that of directive 001,
Section 6, with bootstrap seed 20261010. Group quantities are formed per instant
and then aggregated.

## 7. Stage S: the share of events in boxes

For each recording and each integer `j` such that the window
`U_j = [j * 1,000,000, j * 1,000,000 + 33,333)` us lies inside the span of the
recording's events:

- take the events of `U_j`;
- take the tracks alive at `t_j = j * 1,000,000 + 16,666` us, that is with
  `t_first <= t_j <= t_last`, and the box of each at `t_j`, dilated by 2 px. A
  box covers the pixels `ceil(x - 2) .. floor(x + w + 2)` by
  `ceil(y - 2) .. floor(y + h + 2)`, clipped to the sensor;
- form three pixel masks: `A`, all alive tracks; `L`, the tracks that live at
  least 1 s; `V`, the vehicle tracks (as in directive 001) that live at least
  1 s.

Per recording, sum over the windows: the events, the events in each mask, the
pixels of each mask, the windows, and the events and the count of the windows
with an empty `A`. Report the three event shares and the three pixel shares.

## 8. Tables for the report

1. **Headline, stratum H, headline cell, by lighting:** for `K` in {2, 4, 8, 11},
   the share `phi`, the fidelity and `gamma` of `aligned`, `cmax` and `static`,
   and the fidelity of thinning at the same share, `2 phi / (1 + phi)`. The same
   at the frame cell.
2. **Targets:** `F1` of `aligned`, `cmax`, `static` and `uniform` at the headline
   cell and at the frame cell for `m` = 1 to 10, stratum H, by lighting. For each
   `m`, the median distance in px between the sent and the predicted
   displacement, and the share of rows in which they differ.
3. **Grid:** `gamma` of `aligned` at `K` = 4 in the 12 cells, stratum H, by
   lighting. For a cell other than the headline cell, form the group from the
   `F1` of that cell.
4. **Speed and class:** `gamma` and fidelity of `aligned` and `static` at `K` = 4
   and `K` = 11, headline cell, for each speed bin and class group, isolated
   instants, by lighting.
5. **Bits:** stratum H, by lighting: `b_direct(K)` and `b_aligned(K)` for `K` in
   {2, 4, 8, 11} with the fidelity of `aligned` next to them, and `b_thin(q)` for
   the five shares with the fidelity `2 q / (1 + q)`. Also `key_bits / n_source`.
6. **Stage S, by lighting:** the three event shares and the three pixel shares,
   as medians over recordings and pooled, and the share of events in windows
   with an empty `A`.
7. **Skips and search:** skips by reason and target; groups without a full set of
   targets by `K`; the distribution of `aligned_n_eval`.

## 9. Predictions and decision rule

Written by the director before any Stage C or Stage S number existed. Stratum H,
headline cell, medians over recordings, the same range by day and by night
unless two are given.

| quantity | predicted |
|---|---|
| `F1(aligned)`, `m` = 1 | 0.66 to 0.75 |
| `F1(aligned)`, `m` = 4 | 0.55 to 0.70 |
| `F1(aligned)`, `m` = 10 | 0.40 to 0.62 |
| `gamma(aligned)` at `K` = 2 / 4 / 8 / 11 | 1.40 to 1.60 / 2.0 to 2.7 / 3.0 to 4.6 / 3.6 to 6.0 |
| `gamma(cmax)` at `K` = 4 / 11 | 1.9 to 2.3 / 3.2 to 3.9 |
| `gamma(static)` at `K` = 4 | 0.8 to 1.1 |
| median distance between sent and predicted displacement at `m` = 10 | 1 to 6 px |
| `key_bits / n_source` | 20 to 30 bits |
| Stage S, share of events in `A` | day 0.4 to 0.9, night 0.15 to 0.7 |

The values for `cmax` and `static` follow from Table 3 of report 002. On the
synthetic fixture at 200 px/s with a velocity that is 20% wrong,
`gamma(aligned)` is 3.4 at `K` = 4 and 9.0 at `K` = 11, `gamma(cmax)` is 1.2 and
1.4, and `gamma(static)` is 0.8 and 1.0. With 5 Hz of noise per pixel
`gamma(aligned)` falls to 2.2 at `K` = 4, because noise events cannot be
regenerated.

**Rule (D-003-3).** With `gamma(aligned)` at the headline cell, stratum H:

- **GO** for the validation phase if `gamma(aligned)` at `K` = 4 is at least 2.0
  by day and by night: one quarter of the events then gives the fidelity that
  thinning reaches with half. The codec of Appendix A is then frozen, and the
  next directive names a second dataset with a downstream task;
- **NO-GO** if `gamma(aligned)` is under 1.3 for every `K` in {2, 4, 8, 11}, by
  day and by night. Regeneration then is not worth a codec, and the paper is
  theory note 1 with the measurements of directives 001 and 002;
- otherwise the director proposes one refinement of the codec, chosen from
  Tables 2 to 4, before any second dataset.

Stage S changes no decision. It sets how the paper states the saving for a whole
stream.

## 10. Acceptance checks

1. P1 to P3 pass.
2. `results/gp/population_check.json` was committed before the first event file
   was opened, and the report gives both commit hashes.
3. Every instant of Section 6 has ten rows, each scored or counted as a skip.
4. For `m` in {1, 2, 4, 10}, every output of the models `static`, `cmax`, `label`
   and `uniform`, and `n_source`, `n_future` and `support_px`, equal the row of
   directive 002 at the lead 0, 33, 100 and 300 ms exactly.
5. For every scored row, `aligned_f1_s2_k3 >= start_f1_s2_k3`. Report the number
   of rows in which any `start` output differs from the `cmax` output (they
   differ only when a predicted displacement ends in exactly one half).
6. For every scored row, every `aligned` `F1` lies in [0, 1] and does not
   decrease along the nested coarsenings of directive 002, acceptance check 5.
7. For every group, `share` lies in (0, 1], and the group with `n_pred` set to
   zero has `gamma` = 1 to 1e-12.
8. The suite passes at the executed commit.

## 11. Outputs

| file | content |
|---|---|
| `results/gp/population_check.json` | Section 4 |
| `results/gp/preflight.json` | P1 to P3 and the cost projection |
| `results/gp/per_recording.npz` | recording x stratum x quantity medians and instant counts, Stage C |
| `results/gp/share.json` | Stage S: the per-recording sums and Table 6 |
| `results/gp/report.json` | every table of Section 8 |
| `results/gp/provenance.json` | commit, host, versions, wall time, and the path and SHA-256 of the per-row files kept on the host |

Per-row files stay on the host under `~/prjs/event_coding/gp/` and are not
committed.

## 12. Cost

Stage C has about 656,000 rows. A row costs the 0.06 s of a Stage R row plus the
search, 80 to 190 evaluations of one voxel grid. It is expected to take 30 to 60
CPU-hours. Stage S reads one window per second and is negligible next to the
file reads, which Stage C needs anyway. Probe 50 instants first. If the projected
total exceeds 120 CPU-hours, stop after the preflight and report the measured
cost. Do not compete with a companion-project job on `cnt`.

## 13. Answers to the questions of report 002

1. **`static` still at the largest bandwidth.** Closed by D-003-4. No further
   run.
2. **Lead.** Table 2 of this directive separates the two causes: `cmax` against
   `aligned` is the error of the extrapolated velocity, and the fall of `aligned`
   with `m` is the aging of the key events. The group size of a codec is read
   from Tables 1 and 2.
3. **Slow objects.** No separate mode in this directive. Table 4 reports `gamma`
   by speed bin. A decision on slow objects follows that table.

## 14. What comes next

On GO, the director proposes a second dataset with a downstream task, and
theory note 2 relates `gamma(K)` to the path length of note 1, Corollary 1. A
time offset per window and a coded innovation are the two refinements held back
from this directive.

## Appendix A. `ec/gop.py`

Normative. The executor commits this file unchanged.

```python
"""Key windows and regenerated windows (directive 003). Reference implementation.

Question. A sender transmits the events of one window of an object (the key
window) and, for each of the next windows, only a displacement. The receiver
regenerates those windows by moving the key events. What fidelity does the
receiver get per event sent, against sending a random subset of all events?

For one evaluation instant ``t_e`` (the windows, the support and the truth are
those of ``ec.regen.evaluate_regen``):

* key window: ``[t_e - T2, t_e)``. Its events inside the label box (the source of
  ``ec.regen``) are sent as they are;
* target window ``m`` = 1, 2, ...: ``[t_e + D_m, t_e + D_m + T2)`` with lead
  ``D_m = (m - 1) * 100000 // 3`` microseconds, so that ``m`` = 1, 2, 4, 10 are the
  leads 0, 33, 100 and 300 ms of directive 002;
* model ``aligned``: the key events moved by an integer displacement
  ``(dx, dy)`` px and by ``D_m + T2`` in time. The sender chooses the displacement
  to maximize the fidelity against the true events of the target window, and
  transmits it. The search starts at the displacement that the ``cmax`` velocity
  of directive 001 predicts and is coarse to fine;
* the models of ``ec.regen`` (``static``, ``cmax``, ``label``, ``uniform``) are
  computed by ``ec.regen.evaluate_regen`` itself and returned next to it. ``cmax``
  extrapolates a velocity estimated before ``t_e`` and sends nothing per window;
  ``static`` repeats the key events in place.

A group of ``K`` windows is the key window and the targets ``m`` = 1 .. K - 1.
With ``n_key`` key events, and for each target ``n_pred`` regenerated events,
``n_true`` true events and ``match = F1 (n_pred + n_true) / 2`` paired events:

    fidelity    F   = 2 (n_key + sum match) / (2 n_key + sum (n_pred + n_true))
    event share phi = n_key / (n_key + sum n_true)

The key window counts as reproduced exactly. A random subset that keeps a share
``q`` of all events has precision 1 and recall ``q`` in every voxel grid, so its
fidelity is ``2 q / (1 + q)``. The share that random thinning needs to reach the
fidelity ``F`` is ``q_eq = F / (2 - F)``, and

    gamma = q_eq / phi

is the factor by which regeneration lowers the number of events sent at equal
fidelity. ``gamma`` = 1 means no better than thinning.

Transport sizes use the baseline of the companion project
(``ec.baseline.payload_bits``, U2 + zstd-1) on the events of one window of one
object, with times relative to the window start.
"""
from __future__ import annotations

import math

import numpy as np

from . import regen
from .annotations import Track, in_box_mask
from .baseline import payload_bits

N_TARGETS = 10
MOTION_BITS = 24                      # two signed 12-bit pixel displacements per regenerated window
THIN_SHARES = (0.75, 0.5, 0.35, 0.25, 0.125)
THIN_SEED = 20261010
OBJECTIVE = (2, 3)                    # the headline cell of directive 002


def lead_us(m: int) -> int:
    return (m - 1) * 100_000 // 3


def _stage_cell(step: int):
    s = 2 if step <= 2 else 4 if step <= 4 else 8 if step <= 8 else 16
    return s, (OBJECTIVE[1] if s == 2 else 1)


def aligned_displacement(sx, sy, st, sp, fx, fy, ft, fp, w0_us: int, T2_us: int, shift_us: int, support, d0):
    """Integer displacement that maximizes the voxel F1 of the moved source against the truth.

    ``d0`` is the predicted displacement in px. Half-width of the search:
    ``R = max(3, ceil(0.3 |d0|))``. The first stage tries the 9 x 9 displacements at
    spacing ``ceil(R / 4)`` around ``rint(d0)``; each later stage halves the spacing
    and tries 5 x 5, down to 1 px. A stage scores on blocks no smaller than its
    spacing (2, 4, 8 or 16 px), with three time bins at 2 px and one above. Ties go
    to the candidate nearest the current best. The result is never worse than
    ``rint(d0)`` at the objective cell. Returns ``(dx, dy), (d0x, d0y), n_evaluations``.
    """
    x0, x1, y0, y1 = support
    sx = np.asarray(sx, dtype=np.int64); sy = np.asarray(sy, dtype=np.int64)
    tm = np.asarray(st, dtype=np.int64) + int(shift_us)
    n_eval = 0

    def score(d, cell):
        nonlocal n_eval
        n_eval += 1
        ix, iy = sx + d[0], sy + d[1]
        keep = (ix >= x0) & (ix <= x1) & (iy >= y0) & (iy <= y1)
        return regen.voxel_f1(ix[keep], iy[keep], tm[keep], sp[keep], fx, fy, ft, fp, w0_us, T2_us, *cell)["f1"]

    start = (int(np.rint(d0[0])), int(np.rint(d0[1])))
    R = max(3, int(math.ceil(0.3 * math.hypot(d0[0], d0[1]))))
    step, reach, best = int(math.ceil(R / 4)), 4, start
    while True:
        cell = _stage_cell(step)
        offs = [(i, j) for i in range(-reach, reach + 1) for j in range(-reach, reach + 1)]
        offs.sort(key=lambda ij: (ij[0] * ij[0] + ij[1] * ij[1], ij))
        cand, top = best, -1.0
        for i, j in offs:
            d = (best[0] + i * step, best[1] + j * step)
            f = score(d, cell)
            if f > top:
                cand, top = d, f
        best = cand
        if step == 1:
            break
        step, reach = int(math.ceil(step / 2)), 2
    if best != start and score(best, OBJECTIVE) <= score(start, OBJECTIVE):
        best = start
    return best, start, n_eval


def evaluate_target(t_us, x, y, p, track: Track, t_e_us: int, m: int, T2_us: int, width: int, height: int,
                    v_cmax, T1_us: int = 100_000, margin_px: float = 2.0, sizes: bool = True) -> dict:
    """All quantities of target window ``m`` of the group keyed at ``t_e``. ``t_us`` must be nondecreasing."""
    D = lead_us(m)
    out = regen.evaluate_regen(t_us, x, y, p, track, t_e_us, D, T2_us, width, height, v_cmax, T1_us, margin_px)
    if "skipped" in out:
        return out
    t_us = np.asarray(t_us, dtype=np.int64)
    w0, w1, shift = int(t_e_us + D), int(t_e_us + D + T2_us), int(D + T2_us)
    # support, truth and source: identical to ec.regen.evaluate_regen
    v_lab = track.velocity(t_e_us, T1_us)
    bx, by, bw, bh = (float(a) for a in track.box(0.5 * (w0 + w1)))
    grow = margin_px + 0.5 * math.hypot(*v_lab) * T2_us * 1e-6
    sx0 = max(0, int(math.floor(bx - grow))); sx1 = min(width - 1, int(math.ceil(bx + bw + grow)))
    sy0 = max(0, int(math.floor(by - grow))); sy1 = min(height - 1, int(math.ceil(by + bh + grow)))
    b0, b1 = np.searchsorted(t_us, (w0, w1))
    fxa, fya = np.asarray(x[b0:b1]), np.asarray(y[b0:b1])
    fm = (fxa >= sx0) & (fxa <= sx1) & (fya >= sy0) & (fya <= sy1)
    ft, fx, fy, fp = t_us[b0:b1][fm], fxa[fm], fya[fm], np.asarray(p[b0:b1])[fm]
    a0, a1 = np.searchsorted(t_us, (t_e_us - T2_us, t_e_us))
    sm = in_box_mask(track, t_us[a0:a1], x[a0:a1], y[a0:a1], margin_px)
    st = t_us[a0:a1][sm]
    sx, sy, sp = np.asarray(x[a0:a1])[sm], np.asarray(y[a0:a1])[sm], np.asarray(p[a0:a1])[sm]
    assert len(st) == out["n_source"] and len(ft) == out["n_future"]
    d0 = (float(v_cmax[0]) * shift * 1e-6, float(v_cmax[1]) * shift * 1e-6)
    (dx, dy), (d0x, d0y), n_eval = aligned_displacement(sx, sy, st, sp, fx, fy, ft, fp, w0, T2_us, shift,
                                                        (sx0, sx1, sy0, sy1), d0)

    def cells(d, prefix):
        ix, iy = sx.astype(np.int64) + d[0], sy.astype(np.int64) + d[1]
        keep = (ix >= sx0) & (ix <= sx1) & (iy >= sy0) & (iy <= sy1)
        out[f"{prefix}_n_pred"] = int(keep.sum())
        for s in regen.BLOCKS_PX:
            for k in regen.TIME_BINS:
                out[f"{prefix}_f1_s{s}_k{k}"] = regen.voxel_f1(ix[keep], iy[keep], (st + shift)[keep], sp[keep],
                                                               fx, fy, ft, fp, w0, T2_us, s, k)["f1"]

    cells((dx, dy), "aligned")
    cells((d0x, d0y), "start")
    out.update({"m": int(m), "aligned_dx": dx, "aligned_dy": dy, "start_dx": d0x, "start_dy": d0y,
                "aligned_n_eval": n_eval})
    if sizes:
        out["true_bits"] = payload_bits(ft - w0, fx, fy, fp)
        if m == 1:
            out["key_bits"] = payload_bits(st - int(t_e_us - T2_us), sx, sy, sp)
            u = np.random.default_rng((THIN_SEED, int(track.track_id), int(t_e_us))).random(len(ft))
            for q in THIN_SHARES:
                kp = u < q
                out[f"thin_n_q{q}"] = int(kp.sum())
                out[f"thin_bits_q{q}"] = payload_bits((ft - w0)[kp], fx[kp], fy[kp], fp[kp])
    return out


def group_summary(n_key: int, n_pred, n_true, f1) -> dict:
    """Fidelity, event share and gamma of a group. The sequences hold the targets m = 1 .. K - 1."""
    n_pred = np.asarray(n_pred, dtype=np.float64)
    n_true = np.asarray(n_true, dtype=np.float64)
    match = np.asarray(f1, dtype=np.float64) * (n_pred + n_true) / 2.0
    F = 2.0 * (n_key + match.sum()) / (2.0 * n_key + (n_pred + n_true).sum())
    phi = n_key / (n_key + n_true.sum())
    q_eq = F / (2.0 - F)
    return {"fidelity": float(F), "share": float(phi), "q_eq": float(q_eq), "gamma": float(q_eq / phi)}
```

## Appendix B. `tests/test_gop_gate.py`

Normative. The executor commits this file unchanged. It is the gate of Stage C.

```python
"""Gate for directive 003: key windows and regenerated windows on synthetic rigid translation.

The scenarios, seeds and tolerances are fixed here by the director. An executor implementation that
replaces or accelerates ``ec.gop`` must pass this file unchanged.
"""
import numpy as np

from ec import annotations, gop, motion, regen, synth

T1, T2 = 100_000, 33_333


def _groups(v, v_factor=1.0, n_targets=4, sizes=False, **kw):
    """Groups keyed at the evaluation instants. The cmax velocity is scaled by ``v_factor`` before use."""
    sc = synth.rigid_translation(v=v, duration_s=1.2, n_points=120, seed=0, **kw)
    tr = annotations.tracks(sc.boxes)[0]
    out = []
    for te in motion.evaluation_instants(tr):
        m0 = motion.evaluate_instant(sc.t, sc.x, sc.y, sc.p, tr, int(te), T1, 0, T2, sc.width, sc.height,
                                     models=("cmax",))
        if "skipped" in m0:
            continue
        vc = (m0["cmax_vx"] * v_factor, m0["cmax_vy"] * v_factor)
        rows = [gop.evaluate_target(sc.t, sc.x, sc.y, sc.p, tr, int(te), m, T2, sc.width, sc.height, vc,
                                    sizes=sizes) for m in range(1, n_targets + 1)]
        if not any("skipped" in r for r in rows):
            out.append(rows)
    assert out
    return out


def _gamma(rows, model, K):
    r = rows[:K - 1]
    return gop.group_summary(rows[0]["n_source"], [a[f"{model}_n_pred"] for a in r], [a["n_future"] for a in r],
                             [a[f"{model}_f1_s2_k3"] for a in r])


def test_leads_are_those_of_directive_002():
    assert [gop.lead_us(m) for m in (1, 2, 4, 10)] == [0, 33_333, 100_000, 300_000]
    assert gop.N_TARGETS == 10 and gop.OBJECTIVE == (2, 3)


def test_group_summary_by_hand():
    s = gop.group_summary(100, [100], [100], [0.5])
    assert abs(s["fidelity"] - 0.75) < 1e-12 and abs(s["share"] - 0.5) < 1e-12
    assert abs(s["q_eq"] - 0.6) < 1e-12 and abs(s["gamma"] - 1.2) < 1e-12
    # nothing regenerated: the group is a thinned stream, and gamma is 1
    s = gop.group_summary(100, [0, 0, 0], [100, 80, 120], [0.0, 0.0, 0.0])
    assert abs(s["share"] - 0.25) < 1e-12 and abs(s["fidelity"] - 0.4) < 1e-12 and abs(s["gamma"] - 1.0) < 1e-12
    # false events lower the fidelity below that of thinning
    assert gop.group_summary(100, [100], [100], [0.0])["gamma"] < 1.0


def test_exact_velocity_needs_no_correction():
    for rows in _groups((200.0, 0.0)):
        for r in rows:
            assert (r["aligned_dx"], r["aligned_dy"]) == (r["start_dx"], r["start_dy"])
            for s in regen.BLOCKS_PX:
                for k in regen.TIME_BINS:
                    assert r[f"aligned_f1_s{s}_k{k}"] == r[f"start_f1_s{s}_k{k}"] == r[f"cmax_f1_s{s}_k{k}"]


def test_a_wrong_velocity_is_corrected_by_the_sent_displacement():
    for rows in _groups((200.0, 0.0), v_factor=1.2):
        r = rows[3]                                         # m = 4, lead 100 ms, true displacement 26.7 px
        assert r["start_dx"] == 32 and abs(r["aligned_dx"] - 27) <= 1 and r["aligned_dy"] == 0
        assert r["aligned_f1_s2_k3"] > 0.75 and r["cmax_f1_s2_k3"] < 0.2
    for rows in _groups((150.0, -80.0), v_factor=0.85, jitter_us=1000.0):
        r = rows[3]
        assert abs(r["aligned_dx"] - 20) <= 1 and abs(r["aligned_dy"] + 11) <= 1
        assert r["aligned_f1_s2_k3"] > 0.6 and r["cmax_f1_s2_k3"] < 0.25


def test_the_sent_displacement_is_never_worse_than_the_predicted_one():
    for kw in (dict(v=(200.0, 0.0), v_factor=1.1, noise_rate_hz=5.0), dict(v=(40.0, 0.0), v_factor=1.3),
               dict(v=(150.0, -80.0), v_factor=0.85, jitter_us=3000.0)):
        for rows in _groups(**kw):
            for r in rows:
                assert r["aligned_f1_s2_k3"] >= r["start_f1_s2_k3"]
                assert 0.0 <= r["aligned_f1_s1_k32"] <= r["aligned_f1_s2_k32"] <= r["aligned_f1_s4_k32"] <= 1.0
                assert r["aligned_f1_s2_k32"] <= r["aligned_f1_s2_k8"] <= r["aligned_f1_s2_k1"]


def test_regeneration_beats_thinning_and_repetition_does_not():
    for rows in _groups((200.0, 0.0), v_factor=1.2, n_targets=7):
        a4, a8, c4, s4 = _gamma(rows, "aligned", 4), _gamma(rows, "aligned", 8), _gamma(rows, "cmax", 4), \
            _gamma(rows, "static", 4)
        assert a4["gamma"] > 2.8 and a8["gamma"] > 5.0 and abs(a4["share"] - 0.25) < 0.02
        assert c4["gamma"] < 1.5 and s4["gamma"] < 1.0
    for rows in _groups((200.0, 0.0), noise_rate_hz=5.0):   # noise events cannot be regenerated
        assert 1.6 < _gamma(rows, "aligned", 4)["gamma"] < 2.8


def test_transport_sizes_and_thinning_are_reproducible():
    a = _groups((200.0, 0.0), jitter_us=1000.0, n_targets=2, sizes=True)[0]
    b = _groups((200.0, 0.0), jitter_us=1000.0, n_targets=2, sizes=True)[0]
    assert a == b
    r = a[0]
    assert r["key_bits"] > 0 and r["true_bits"] > 0 and "key_bits" not in a[1] and a[1]["true_bits"] > 0
    n = [r[f"thin_n_q{q}"] for q in gop.THIN_SHARES]
    assert n == sorted(n, reverse=True) and n[0] < r["n_future"]
    for q in gop.THIN_SHARES:
        assert abs(r[f"thin_n_q{q}"] / r["n_future"] - q) < 0.06
    # a sparser subset costs more bits per kept event
    per = [r[f"thin_bits_q{q}"] / r[f"thin_n_q{q}"] for q in gop.THIN_SHARES]
    assert per[0] < per[-1]
```
