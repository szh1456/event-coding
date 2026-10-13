# Directive 017. REMAKE with a sampled remainder, and the baseline on its whole frontier

| | |
|---|---|
| track | `hybrid`, short name `hy` |
| population | as directive 016: eTraM train recordings and train annotations, DSEC training sequences, and the kept per-group files and streams of directives 007, 009 and 013 |
| results directory | `results/hy/` |
| report | `docs/directives/reports/017.md` |
| runs after | directive 016 (`DONE`, report at `6539b35`) |

## 1. Why

Report 016 found two things.

1. **Downstream tasks.** At (nearly) equal bits, a random subset beats REMAKE on objects by day and on
   motion by day and on DSEC. By day, REMAKE rebuilds no event in half of the annotated boxes. REMAKE
   sends only blocks that hold at least `psi B^2` key events, so a sparse object outside the regions is
   lost. The global fidelity hides this loss, because it is dominated by dense blocks.
2. **The baseline.** The criterion of 016 froze the configuration of the baseline that predicts least,
   which sends nearly every event. The comparison at equal F was therefore undefined. In 016 the random
   subset also cost up to twice the bits of REMAKE with coder Q, so the downstream comparison was not at
   equal bits.

This directive:

- **Part H.** Adds to REMAKE a random subset of the events in the blocks that REMAKE leaves empty
  (`ec/hybrid.py`). It measures fidelity, bits and both tasks, against random subsets whose bits are
  matched by bisection.
- **Part B.** Widens the grid of the baseline. It reports the baseline's whole frontier of fidelity
  against bits instead of one frozen configuration. In the downstream tasks it uses the configuration
  of the baseline whose bits come closest to those of REMAKE.

## 2. Disclosure

The director wrote `ec/hybrid.py` and tested it on synthetic events only. The director read report 016
and its tables, and no recording.

## 3. Author decisions

**D-017-1, default: authorized.** The executor adds `ec/hybrid.py` and `tests/test_hybrid_gate.py`
with the content of Appendices A and B, unchanged.

**D-017-2, default: as stated in Section 5.** The share of the hybrid is tuned on the tuning subsets
with the criterion of REMAKE, and frozen per dataset and coder.

**D-017-3, default: as stated in Section 6.** The grid of the baseline and its frontier.

**D-017-4, default: authorized.** The reads of directive 016, Section 4, for the groups of this
directive.

## 4. Definitions

Groups, entering rules, strata, tuning and reporting subsets, host paths (under `.../hy/`) and the
bootstrap are those of directive 016, with seed 20261017.

**Sums.** A per-group output of `ec.hybrid.evaluate_group` has the layout of `ec.fbc.evaluate_group`.
`ec.fbc.sum_groups` and `ec.fbc.summarize` therefore apply to it unchanged, with the keys `<coder>_s<share>`.

## 5. Part H: the hybrid

**Stage T.**

- Run every group of the tuning recordings with
  `ec.hybrid.evaluate_group(t, x, y, p, w, records, 4, width, height)`.
- `records` holds, for each coder, the kept REMAKE record `affine_<coder>_K4` of configuration (20, 1)
  of that group.
- The shares are `ec.hybrid.SHARES`, plus 0 (REMAKE alone).
- Compute `J` as in directive 016, Section 5, from `ec.fbc.summarize`.
- For each dataset and coder, freeze the share with the largest median `J`. Share 0 is a candidate. On a
  tie, take the smaller share.
- Commit `results/hy/tuning.json` before Stage R evaluates a reporting group.

**Stage R.**

- Run every reporting group for K = 4 and K = 11, with all shares.
- Per recording, compute `summarize` for every coder, K and share.

Tables:

1. **Hybrid:** `F`, `bits`, `bits_base` and `gain_sub` against the share, per stratum, coder and K. Share
   0 must reproduce REMAKE (Section 8, check 3).
2. **Remainder:** the share of the true events of the group that lie outside the covered blocks, per
   stratum.

## 6. Part B: the baseline on its frontier

**Stage T.**

- Run every group of the tuning recordings with `ec.fbc.evaluate_group(..., Ks=(4,), coders=("T", "Q"))`.
- Use the twelve new configurations: `radius` in 1, 2 and 3, and `res_us` in 2000, 5000, 10000 and
  20000.
- Keep the nine configurations of `results/fb/tuning.json`.

**Frontier.** Per dataset and coder:

- Over the 21 configurations, take the medians of `F` and `bits` over the tuning recordings.
- A configuration is on the frontier when no other configuration has both a higher F and fewer bits.
- From the frontier, select three configurations: the one with the fewest bits, the one with the
  highest F, and the one whose bits are closest to the geometric mean of those two.
- Commit them in `results/hy/frontier.json` before Stage R.

**Stage R.**

- Run every reporting group with the selected configurations, at K = 2, 4, 8 and 11 and both coders.
- Do not run a configuration again if `results/fb/` already holds it.

Per recording and coder, the baseline's points are all `(F, bits)` over the selected configurations and
the four K.

- `b_pred(F)` is the fewest bits among the points whose F is at least F.
- At each K of REMAKE, report `G_pred = b_pred(F_REMAKE) / b_REMAKE`, together with the F of the point
  that attains it.
- `b_pred` is defined whenever some point reaches F. Report the share of recordings where none does.

## 7. Downstream tasks

The tasks, the boxes, the squares and the aggregation are those of directive 016, Section 7, and its
report, Section 7, items 4 and 5, at K = 4. The schemes are:

| scheme | events |
|---|---|
| `true` | the recorded events |
| `remake_<coder>` | the decoded REMAKE record |
| `hybrid_<coder>` | REMAKE plus the remainder at the frozen share of Section 5 |
| `thin_remake_<coder>` | `ec.hybrid.thin_matched` to the bytes of `remake_<coder>` of the group |
| `thin_hybrid_<coder>` | `ec.hybrid.thin_matched` to the bytes of `hybrid_<coder>` of the group |
| `fbc_<coder>` | the frontier configuration and K of Section 6 whose median bits on the tuning subsets come closest to those of REMAKE at K = 4, from its decoded record |

For every scheme, report the median over recordings of its bits per true event. Report also the median
ratio of its bits to those of the scheme it is matched to.

## 8. Acceptance checks

1. The two files have the SHA-256 of Section 11, and the suite passes with no skipped test.
2. `results/hy/tuning.json` and `results/hy/frontier.json` were committed before Stage R.
3. **Share 0 reproduces REMAKE.** At share 0, `F` and `bits` of every recording equal the values of
   `ec.blockcodec.summarize` for `affine`, (20, 1), coder and K of the kept sums, to 1e-12.
4. **Matched bytes.** For every group and matched scheme, the bytes of `thin_matched` lie within 3% of the
   target. Otherwise, report the share of groups outside and their median deviation.
5. **Valid windows.** The decoded events of every scheme lie in their window and on the sensor.
6. **Files untouched.** No eTraM val or test file was opened, and the annotation root was not listed.
   Nothing outside `results/hy/` changed under `results/`.

## 9. Cost

Project from 20 groups of each stage and dataset. If the total exceeds 250 CPU-hours, stop after the two
Stage T runs, commit both files, and report `BLOCKED` with the projection. A run that then costs more is
let finish, and both numbers are reported.

Read the DSEC sequences one at a time with the memory guard of report 009. Use the single read per
sequence of report 016, Section 7, item 2.2. The eTraM reads may overlap.

## 10. Outputs

| file | content |
|---|---|
| `results/hy/tuning.json`, `results/hy/frontier.json` | Sections 5 and 6, Stage T |
| `results/hy/per_recording.json` | sums of every reporting recording, per scheme, coder, K and share |
| `results/hy/report.json` | the tables of Sections 5 to 7 |
| `results/hy/provenance.json` | commit, host, versions, wall and CPU time, and the files read |

## 11. Files

SHA-256 of the file content, which is the text between the fence lines of its appendix, ending in one
newline.

| file | SHA-256 |
|---|---|
| `ec/hybrid.py` | `ef8e2a1c6e4b154a3e1997045134e0b525eb1f8686ac44184f9513dc2208348f` |
| `tests/test_hybrid_gate.py` | `a8fbc305fd394bfd6c8e8fb37543970efa8665c0dd014de37c5789f6f6911b1e` |

## Appendix A. `ec/hybrid.py`

Normative. The executor commits this file unchanged.

```python
"""REMAKE with a sampled remainder, and random subsets at matched bits (directive 017).

REMAKE sends key events only in blocks whose key window holds at least ``psi B^2`` events, so a sparse
object outside the regions is not rebuilt at all. The hybrid adds, for every window m = 0 .. K - 1 of a
group, a random subset of the true events that lie in blocks where the REMAKE reconstruction of window m
has no event (for m = 0: the blocks that are not regions). Each such event is kept with probability
``share``. The subset is coded per window with the coder of the record (coder Q on the working grid,
``ec.blockcodec.Q_DIRECT``, as the subset schemes; coder T at one microsecond), and the receiver adds the
decoded subset to the rebuilt events. The generator of window m of the group keyed at w is
``np.random.default_rng(SEED + 16 * w + m)``.

``thin_matched`` draws a random subset of all events of the group whose coded bytes come closest to a
target, by bisection on the share, so that a comparison at equal bits holds to within a few percent.
"""
from __future__ import annotations

import numpy as np

from . import blockcodec as bc

SEED = 20261017
SHARES = (0.05, 0.1, 0.2, 0.35)
BISECTION_STEPS = 12


def decode_record(record: bytes, coder: str, model: str, K: int, width: int, height: int, B: int, w: int,
                  T0_us: int = bc.T0_US):
    """The REMAKE windows m = 0 .. K - 1 of one kept record (bytes of ``encode_group``), as (t_us, x, y, p).
    A record holds its key window as a difference to the previous group, so the decoded index is replaced by
    ``w``."""
    head = bc.encode_header(coder, model, K, width, height, B, T0_us)
    h, groups = bc.decode_stream(head + record)
    g = dict(groups[0], w=int(w))
    return [bc.reconstruct(h, g, m) for m in range(K)], g


def _code(coder, t_rel, x, y, p, width, height):
    if coder == "T":
        return bc.encode_events_T(t_rel, x, y, p)
    return bc.encode_events_Q(t_rel, x, y, p, bc.Q_DIRECT, width, height)


def _decode(coder, buf, width, height):
    if coder == "T":
        return bc.decode_events_T(buf)
    return bc.decode_events_Q(buf, bc.Q_DIRECT, width, height)


def _window(t, x, y, p, a, b):
    s = (t >= a) & (t < b)
    return t[s], x[s], y[s], p[s]


def remainder(true, rebuilt, B: int, width: int, share: float, rng):
    """The events of ``true`` in blocks of side B where ``rebuilt`` has none, each kept with probability ``share``."""
    t, x, y, p = true
    covered = np.unique(bc.block_ids(rebuilt[1], rebuilt[2], B, width)) if len(rebuilt[0]) else np.zeros(0, np.int64)
    out = ~np.isin(bc.block_ids(x, y, B, width), covered)
    keep = out & (rng.random(len(t)) < share)
    return t[keep], x[keep], y[keep], p[keep]


def evaluate_group(t, x, y, p, w: int, records: dict, K: int, width: int, height: int, B: int = 20,
                   shares=SHARES, T0_us: int = bc.T0_US) -> dict:
    """``records``: coder -> bytes of the kept REMAKE record (model ``affine``) of this group and K.
    Returns, keyed ``<coder>_s<share>`` and ``<coder>_s0`` for REMAKE alone: ``bytes`` (record plus subsets),
    and per window ``n_rec``, ``n_true`` and ``match`` on the working grid, with the group fidelity ``F``."""
    t, x, y, p = (np.asarray(a, dtype=np.int64) for a in (t, x, y, p))
    w0 = w * T0_us
    trues = [_window(t, x, y, p, w0 + m * T0_us, w0 + (m + 1) * T0_us) for m in range(K)]
    truths = [bc.Truth(*tr, w0 + m * T0_us, T0_us) for m, tr in enumerate(trues)]
    n_true = [int(len(tr[0])) for tr in trues]
    out = {"w": int(w), "K": int(K)}
    for coder, rec in records.items():
        rebuilt, _ = decode_record(rec, coder, "affine", K, width, height, B, w, T0_us)
        for share in (0.0,) + tuple(shares):
            n_rec, match, extra = [], [], 0
            for m in range(K):
                rt, rx, ry, rp = rebuilt[m]
                if share > 0:
                    rng = np.random.default_rng(SEED + 16 * w + m)
                    st, sx, sy, sp = remainder(trues[m], rebuilt[m], B, width, share, rng)
                    a = w0 + m * T0_us
                    buf = _code(coder, st - a, sx, sy, sp, width, height)
                    extra += len(buf)
                    dt, dx, dy, dp = _decode(coder, buf, width, height)
                    rt, rx, ry, rp = (np.concatenate((u, v)) for u, v in ((rt, dt + a), (rx, dx), (ry, dy), (rp, dp)))
                n_rec.append(int(len(rt)))
                match.append(truths[m].match(rt, rx, ry, rp, bc.OBJECTIVE))
            den = sum(n_rec) + sum(n_true)
            out[f"{coder}_s{share:g}"] = {"bytes": len(rec) + extra, "n_rec": n_rec, "n_true": n_true,
                                          "match": match, "F": 2.0 * sum(match) / den if den else 0.0}
    return out


def thin_events(t, x, y, p, w: int, K: int, coder: str, share: float, width: int, height: int,
                T0_us: int = bc.T0_US):
    """A random subset of every window of the group at ``share``, coded and decoded: (bytes, windows)."""
    w0 = w * T0_us
    total, wins = 0, []
    for m in range(K):
        a = w0 + m * T0_us
        tt, tx, ty, tp = _window(t, x, y, p, a, a + T0_us)
        keep = np.random.default_rng(SEED + 16 * w + m).random(len(tt)) < share
        buf = _code(coder, tt[keep] - a, tx[keep], ty[keep], tp[keep], width, height)
        total += len(buf)
        dt, dx, dy, dp = _decode(coder, buf, width, height)
        wins.append((dt + a, dx, dy, dp))
    return total, wins


def thin_matched(t, x, y, p, w: int, K: int, coder: str, target_bytes: int, width: int, height: int,
                 T0_us: int = bc.T0_US):
    """The share in [0, 1] whose subset bytes come closest to ``target_bytes``, by bisection. Returns
    ``share``, ``bytes`` and the decoded windows."""
    t, x, y, p = (np.asarray(a, dtype=np.int64) for a in (t, x, y, p))
    lo, hi = 0.0, 1.0
    best = None
    for _ in range(BISECTION_STEPS):
        mid = 0.5 * (lo + hi)
        b, wins = thin_events(t, x, y, p, w, K, coder, mid, width, height, T0_us)
        if best is None or abs(b - target_bytes) < abs(best[1] - target_bytes):
            best = (mid, b, wins)
        if b < target_bytes:
            lo = mid
        else:
            hi = mid
    return best
```

## Appendix B. `tests/test_hybrid_gate.py`

Normative. The executor commits this file unchanged.

```python
"""Gate for directive 017: REMAKE with a sampled remainder, and random subsets at matched bits.

A large textured object and a small one move across a small sensor. With the frozen configuration
(20, 1), REMAKE sends the large object; the small one lies outside the regions. Tolerances are fixed by
the director.
"""
import numpy as np
import pytest

from ec import blockcodec as bc
from ec import hybrid
from ec import synth

W, H, WIN = 320, 240, 6


@pytest.fixture(scope="module")
def scene():
    a = synth.rigid_translation(width=W, height=H, n_points=3000, box_wh=(120, 80), c0=(80, 120),
                                v=(150.0, -50.0), duration_s=1.0, jitter_us=200, seed=2)
    b = synth.rigid_translation(width=W, height=H, n_points=60, box_wh=(20, 20), c0=(250, 40),
                                v=(-40.0, 30.0), duration_s=1.0, jitter_us=200, seed=3)
    t = np.concatenate([a.t, b.t])
    o = np.argsort(t, kind="stable")
    ev = [np.concatenate([u, v])[o].astype(np.int64) for u, v in ((a.t, b.t), (a.x, b.x), (a.y, b.y), (a.p, b.p))]
    g = bc.evaluate_group(*ev, WIN, 0, W, H, blocks=(20,), densities=(1.0,), models=("affine",),
                          records_for=(20, 1.0))
    recs = {c: g["records"][f"affine_{c}_K4"] for c in bc.CODERS}
    return ev, g, recs, hybrid.evaluate_group(*ev, WIN, recs, 4, W, H)


def test_share_zero_is_remake(scene):
    ev, g, recs, r = scene
    gs = bc.sum_groups([g])
    for c in bc.CODERS:
        assert r[f"{c}_s0"]["bytes"] == len(recs[c])
        assert abs(r[f"{c}_s0"]["F"] - bc.summarize(gs, "B20_rho1.0", "affine", c, 4)["F"]) < 1e-12


def test_fidelity_and_bytes_grow_with_the_share(scene):
    _, _, _, r = scene
    for c in bc.CODERS:
        F = [r[f"{c}_s{s:g}"]["F"] for s in (0.0,) + hybrid.SHARES]
        b = [r[f"{c}_s{s:g}"]["bytes"] for s in (0.0,) + hybrid.SHARES]
        assert all(F[i] < F[i + 1] for i in range(len(F) - 1))
        assert all(b[i] < b[i + 1] for i in range(len(b) - 1))


def test_remainder_avoids_covered_blocks(scene):
    ev, _, recs, _ = scene
    rebuilt, _ = hybrid.decode_record(recs["T"], "T", "affine", 4, W, H, 20, WIN)
    a = (WIN + 2) * bc.T0_US
    s = (ev[0] >= a) & (ev[0] < a + bc.T0_US)
    true = tuple(e[s] for e in ev)
    sub = hybrid.remainder(true, rebuilt[2], 20, W, 1.0, np.random.default_rng(0))
    covered = set(bc.block_ids(rebuilt[2][1], rebuilt[2][2], 20, W).tolist())
    assert len(sub[0]) > 0
    assert not (set(bc.block_ids(sub[1], sub[2], 20, W).tolist()) & covered)


def test_thin_matched_hits_the_target(scene):
    ev, _, _, r = scene
    for c in bc.CODERS:
        target = r[f"{c}_s0.2"]["bytes"]
        share, b, wins = hybrid.thin_matched(*ev, WIN, 4, c, target, W, H)
        assert 0 < share < 1 and abs(b - target) <= 0.02 * target and len(wins) == 4
```
