# Directive 027. Does the phase cause the miss? A controlled model, a per-block phase test, and revised figures

| | |
|---|---|
| track | `phase control`, short name `pc` |
| population | the groups of directive 022, the model scenes of directive 022, and the controlled model of Section 4 |
| results directory | `results/pc/`, and figures in `results/paper/` |
| report | `docs/directives/reports/027.md` |
| runs after | directive 026 (`DONE`, report at `64cdf03`) |

## 1. Why

A third external review asked for three things that the manuscript cannot give from committed results.

- **A causal control on the model.** The same edges, the same exact motion and the same number of events
  per pixel, under three conditions: shared phases without jitter, independent phases without jitter, and
  independent phases with jitter. If moved counts reproduce the true ones under shared phases and miss
  under independent ones, the phase is the cause, since the motion is exact in all three.
- **A phase test that a lock varying from block to block cannot pass.** Directive 022 pooled
  `cos(2 pi u)` over pixels. A mean of 0 also arises when each block locks at its own value and the locks
  cancel in the pool. The Rayleigh statistic per block, `Z = |sum exp(2 pi i u)|^2 / m`, does not depend on
  the value of the lock: its mean is exactly 1 for independent uniform `u` and close to `m` for one lock per
  block. The review also asked for the histogram of `u` next to its controls and for the share of the
  events that the test covers.
- **Revised figures.**
  - `fig_moved2`: the control replaces panel (a), whose legend printed a LaTeX label.
  - `fig_phase3`: the phase lock against the spacing, and the histogram of `u` with its controls.
  - `fig_tolerance_compact2`: columns named by what each code sends, and F placed in the panel it refers to.
  - `fig_hevc2`: the motion error of the decode replaces the box fidelity in row (c).

## 2. Disclosure

The director wrote the three files of the appendices and ran them on synthetic events only.

- The full suite passes.
- On the controlled model at 320 x 240 pixels, shared phases give F = 1 on every grid. Independent phases
  give 0.253 at `tau = 2 ms` and `T0 / 64`, against 0.2529 from the equation. Jitter of `0.05 tau` changes F
  by at most 0.016.
- On the model scenes of directive 022, the mean Rayleigh statistic is 1.04 for independent phases and 64
  for shared phases.
- The figure script ran on a synthetic `pc` report and on the committed `hd`, `hc`, `td2` and `paper` files,
  to check the layout. Its numbers are not results.

The director read no recording.

## 3. Author decisions

**D-027-1, default: authorized.** The executor adds `ec/phase_control.py`, `tests/test_phase_control_gate.py`
and `scripts/fig_027.py` with the content of Appendices A to C, unchanged.

**D-027-2, default: authorized.** The runner may reuse the group list and the event reads of
`scripts/ph_run.py` (eTraM read once per recording, at most six at once; DSEC from the caches of directive
017).

**D-027-3, default: as stated in Sections 4 to 7**, including the reading rule of Section 6.

## 4. Definitions

**Controlled model.** For every `tau` in `ec.phase_control.TAUS_US` and every condition in
`ec.phase_control.CONDITIONS`:

    ec.phase_control.control_cell(tau, condition)

with its defaults (320 x 240 pixels, 6 px per window, `n = 3`, `sigma_frac = 0.05`, spacing 40, 12 windows,
seed 1).

**Model scenes for the phase.** Those of directive 022, Section 4: `ec.phase.edge_scene_v(320, 240, v, 2000.0,
3, 0.05, 40, 8, seed, shared)` for `v` in (1.5, 2.5, 6.5, 13.3), `shared` in (False, True) and seed in (1, 2, 3).

**Groups and strata.** Those of directive 022: 563 groups of 55 recordings by day, 448 of 45 by night, 253
of 36 DSEC sequences, with the events of `[(w - 3) T0, (w + 2) T0)`.

## 5. Run

- For every group: `ec.phase_control.block_phases(events, w, W, H)`.
- For every model scene: `ec.phase_control.block_phases(ev, 5, 320, 240)`.
- For every cell of the controlled model: `control_cell` as in Section 4.

Keep each output. Use `~/prjs/event_coding/pc/` for eTraM and the models, and `/data/<user>/event_coding/ds/pc/`
for DSEC.

## 6. Tables and the reading rule

`results/pc/report.json` holds:

- `directive`: `"027"`;
- `control`: the list of the `control_cell` outputs, in the order `tau`, then condition;
- `model_phase.shared` and `model_phase.independent`: `{"hist": ..., "rayleigh": ...}`, the `pred` histogram
  and Rayleigh summary of `ec.phase_control.pool` over the twelve scenes of that kind, each scene entering as
  one recording;
- `strata.<stratum>`: `ec.phase_control.pool` over the recordings of the stratum, for `day`, `night` and
  `all`.

The report gives:

**Table 1, the per-block phase test (the main result).** Per stratum, for `pred` and `null`:

- the blocks and pixels;
- the mean Z with its 95% interval;
- the share of blocks with `Z > ln 100`.

Then the same for the two model kinds.

**Reading rule, fixed before any number is seen.** For `pred`, per stratum:

- a 95% interval of the mean Z entirely below 2 reads as no lock within blocks;
- one entirely above 5 reads as a lock within blocks;
- anything else reads as partial.

**Table 2, coverage.** Per stratum, the four counts of `coverage` and the shares `share_tested` and
`share_band`.

**Table 3, the controlled model.** F per `tau`, condition and k, with the equation where it applies.

The director decides what the manuscript draws from them.

## 7. Cost

- Directive 022 cost less than this one: `block_phases` repeats its motion search and skips the binned sums.
- Project from the first 10 groups of each dataset. If the projection exceeds 40 CPU-hours, stop and report
  `BLOCKED` with it.
- Use the read lock and memory guard of directive 016. Do not compete with a companion-project job.

## 8. Figures

After `results/pc/report.json` is committed:

```
python3 scripts/fig_027.py --pc results/pc --hd results/hd --hc results/hc --demo results/td2 \
    --paper results/paper --out results/paper
```

## 9. Acceptance checks

1. The three files have the SHA-256 of Section 11, and the suite passes with no skipped test.
2. Every group of Section 4 returned, every model scene and every control cell. The group and recording
   counts of each stratum equal Section 4.
3. Control: under `shared` F is 1.0 in every cell. Under `independent`, F lies within 0.01 of the equation
   wherever the equation applies.
4. Model scenes: the mean Z of `pred` is above 10 for shared phases and between 0.8 and 1.25 for
   independent ones.
5. Per stratum, `n_true_band <= n_true_tested <= n_true_moving <= n_true_window`, and the `pred` histogram
   holds at least the pixels of the Rayleigh summary.
6. The four figures exist in `results/paper/` as PDF, PNG and JSON. In `fig_phase3.json`, `b.<stratum>.mean_Z`
   equals the report. In `fig_tolerance_compact2.json`, `recs.<rec>.F` equals `results/td2/demo.json` for
   the day stratum.
7. No eTraM val or test file was opened, and the annotation root was not listed. Under `results/`, nothing
   outside `results/pc/` and the four new figures in `results/paper/` changed.

## 10. Outputs

| file | content |
|---|---|
| `results/pc/report.json` | Section 6 |
| `results/pc/provenance.json` | commit, host, versions, wall and CPU time, the files read |
| `results/paper/fig_moved2.*`, `fig_phase3.*`, `fig_tolerance_compact2.*`, `fig_hevc2.*` | Section 8 |

## 11. Files

The SHA-256 is that of the file content: the text between the fence lines of its appendix, ending in one
newline.

| file | SHA-256 |
|---|---|
| `ec/phase_control.py` | `16b35946134d7f5935780d856f62054a745c792c73d0e2c855f5e5194e1015f4` |
| `tests/test_phase_control_gate.py` | `dcd67c3b6869ecac66688e3704c67c37c6bddcfdb98ebdfc1a4dcc9f0e8148d4` |
| `scripts/fig_027.py` | `017eaa8b0a7877f7ed2f8e5aafe94abaac4315be89399d2008c50e00dac7dadf` |

## 12. The report

The header, Tables 1 to 3, the reading of Table 1 per stratum, and the checks.

## Appendix A. `ec/phase_control.py`

Normative. The executor commits this file unchanged.

````python
"""Does the phase cause moved events to miss? A controlled model and a per-block phase test (directive 027).

Controlled model (``control_scene``, ``control_cell``). Straight edges cross the sensor at a whole number ``u``
of pixels per window, as ``ec.hevcdiag.edge_scene``. Three conditions share the edges, their arrival times and
the number of events per pixel, because each random quantity has its own stream:

- ``shared``: one phase per row and edge, no jitter; the pixels of a path fire in step;
- ``independent``: one phase per pixel, no jitter;
- ``jitter``: one phase per pixel, and jitter of ``sigma_frac tau``.

``control_cell`` predicts the counts of window m from those of window m - 1 moved by exactly ``u`` pixels
(``ec.hevcdiag.oracle_shift``), so the motion is exact and only the phase and the jitter can make the counts
differ. Under ``shared`` the moved counts equal the true ones.

Per-block phase test (``block_phases``). Directive 022 measured, per target pixel, the position ``u`` of the
moved events in its regular train, and pooled ``cos(2 pi u)`` over pixels. A mean of 0 does not exclude a lock
that differs from block to block. Here the same prediction (the motion and delay of ``ec.phase``, the same null
with random times) is scored per block. For the pixels of a moving block (shift other than (0, 0)) with
``TAU_LO <= tau_i < TAU_HI`` and outside the flicker classes of ``ec.threshold``, the block statistic is
``Z = |sum exp(2 pi i u)|^2 / m`` over its ``m`` pixels, the Rayleigh statistic. Its mean is exactly 1 when the
``u`` are independent and uniform, whatever ``m``, and close to ``m`` when the pixels of the block share one
lock, whatever its value. The module also returns the histogram of ``u`` over the same pixels and the share of
the true events of the scored window that the test covers.
"""
from __future__ import annotations

import numpy as np

from . import blockcodec as bc
from . import hevcdiag as hd
from . import phase as ph
from . import threshold as th

T0 = bc.T0_US
CONDITIONS = ("shared", "independent", "jitter")
TAUS_US = (250.0, 500.0, 1000.0, 2000.0, 4000.0, 8000.0)
KS = (1, 3, 6, 12, 32, 64)
U_PX, N_EV, SIGMA_FRAC, SPACING, N_WINDOWS = 6, 3, 0.05, 40, 12
TAU_LO, TAU_HI = 250.0, 4000.0
M_MIN = 5
U_BINS = ph.U_BINS


def control_scene(width: int, height: int, u: int, tau_us: float, n: int, sigma_frac: float, spacing: int,
                  n_windows: int, seed: int, condition: str):
    """Events of straight edges at ``u`` pixels per window under one of CONDITIONS (see the module docstring)."""
    if condition not in CONDITIONS:
        raise ValueError(condition)
    r_edge, r_phase, r_jit = (np.random.default_rng((seed, j)) for j in range(3))
    v = u / T0
    span = n_windows * T0
    sig = sigma_frac * tau_us if condition == "jitter" else 0.0
    T, X, Y, P = [], [], [], []
    xs = np.arange(width)
    for e, x_e in enumerate(range(-int(np.ceil(v * span)) - spacing, width, spacing)):
        for y in range(height):
            phi = r_edge.random()
            a_row = 1.0 - r_phase.random()
            a_pix = 1.0 - r_phase.random(width)
            eps = r_jit.normal(0.0, 1.0, (n, width))
            t0 = (xs - x_e + phi) / v
            ok = (t0 >= -n * tau_us) & (t0 < span)
            if not ok.any():
                continue
            A = (np.full(width, a_row) if condition == "shared" else a_pix)[ok] * tau_us
            for j in range(n):
                T.append(t0[ok] + A + j * tau_us + sig * eps[j, ok])
                X.append(xs[ok]); Y.append(np.full(int(ok.sum()), y)); P.append(np.full(int(ok.sum()), e % 2))
    t = np.rint(np.concatenate(T)).astype(np.int64)
    x, y, p = (np.concatenate(a).astype(np.int64) for a in (X, Y, P))
    keep = (t >= 0) & (t < span)
    o = np.argsort(t[keep], kind="stable")
    return tuple(a[keep][o] for a in (t, x, y, p))


def control_cell(tau_us: float, condition: str, width: int = 320, height: int = 240, seed: int = 1) -> dict:
    """F of the counts moved along the true motion, one-pixel voxels, for every k of KS."""
    ev = control_scene(width, height, U_PX, tau_us, N_EV, SIGMA_FRAC, SPACING, N_WINDOWS, seed, condition)
    out = {"tau_us": tau_us, "condition": condition, "n_events": int(len(ev[0])), "F": {}, "dt_over_tau": {},
           "equation": {}}
    for k in KS:
        dt = T0 / k
        out["F"][f"k{k}"] = hd.oracle_shift(ev, U_PX, 1, k, width, height, N_WINDOWS)["F"]
        out["dt_over_tau"][f"k{k}"] = dt / tau_us
        out["equation"][f"k{k}"] = hd.binfidmoved(dt, tau_us, N_EV)
    return out


def _phases(true, pred, width: int):
    """``ec.phase.pixel_phases`` that also returns the key of each tested pixel and polarity."""
    if len(true[0]) < 3 or len(pred[0]) == 0:
        return np.zeros(0), np.zeros(0), np.zeros(0, dtype=np.int64)
    pk_o, t_o = ph._sorted(true, width)
    k, d, reg = ph._regular_intervals(pk_o, t_o)
    keys, tau = ph._grouped_median(k[reg], d[reg])
    if len(keys) == 0:
        return np.zeros(0), np.zeros(0), np.zeros(0, dtype=np.int64)
    kq = ph._pk(pred, width)
    zt = np.zeros(len(keys), dtype=np.complex128)
    zq = np.zeros(len(keys), dtype=np.complex128)
    for kk, tt, z, sign in ((pk_o, t_o, zt, -1.0), (kq, pred[0].astype(np.float64), zq, 1.0)):
        pos = np.searchsorted(keys, kk)
        ok = (pos < len(keys)) & (keys[np.minimum(pos, len(keys) - 1)] == kk)
        p = pos[ok]
        np.add.at(z, p, np.exp(sign * 2j * np.pi * np.mod(tt[ok], tau[p]) / tau[p]))
    has = np.abs(zq) > 0
    u = np.mod(np.angle(zq[has] * zt[has]) / (2.0 * np.pi), 1.0)
    return u, tau[has], keys[has]


def block_phases(ev, w: int, width: int, height: int, radius: int = ph.RADIUS) -> dict:
    """Per-block Rayleigh sums, the histogram of ``u`` and the event coverage for the group keyed at ``w``.

    ``ev`` as ``ec.phase.evaluate_group``. The motion, delay, prediction and null are those of that function."""
    ev = tuple(np.asarray(a, dtype=np.int64) for a in ev)
    span = th._window(ev, max(0, w - th.SPAN_BEFORE) * T0, (w + 1) * T0)
    hot = th.hot_pixels(span, width, height)
    keep = ~hot[ev[2] * width + ev[1]]
    ev = tuple(a[keep] for a in ev)
    win = {m: th._window(ev, (w + m) * T0, (w + m + 1) * T0) for m in (-1, 0, 1)}
    by = {m: th._ByBlock(win[m], width, height) for m in (-1, 0, 1)}
    reach = -(-radius // ph.B)
    nbx = -(-width // ph.B)
    w0, w1 = w * T0, (w + 1) * T0
    out = {"w": int(w), "n_true_window": int(len(win[1][0])), "n_true_moving": 0, "n_true_tested": 0,
           "n_true_band": 0, "blocks": {"pred": [], "null": []},
           "hist": {k: np.zeros(U_BINS, dtype=np.int64) for k in ("pred", "null")}}
    for b in np.flatnonzero(np.diff(by[1].start) >= th.N_MIN):
        b = int(b)
        bx0, by0 = (b % nbx) * ph.B, (b // nbx) * ph.B
        a_prev, a_ref, a_tru = by[-1].around(b, reach), by[0].around(b, reach), by[1].around(b, 0)
        fit_true = th._in_block(a_ref, bx0, by0)
        d, pairs, _ = ph.choose_shift(ph.shift_scores(a_prev, fit_true, bx0, by0, radius), radius)
        if pairs < th.N_MIN / 2 or d == (0, 0):
            continue
        delta = ph.onset_delay(th._moved(a_prev, d, 0, bx0, by0, w0), fit_true, w0, width)
        true = th._in_block(a_tru, bx0, by0)
        pred = th._moved(a_ref, d, delta, bx0, by0, w1)
        if len(true[0]) < th.N_MIN or len(pred[0]) < th.N_MIN:
            continue
        rng = np.random.default_rng((ph.SEED, int(w), b))
        null = (rng.integers(w1, w1 + T0, len(pred[0])), pred[1], pred[2], pred[3])
        out["n_true_moving"] += int(len(true[0]))
        tk = ph._pk(true, width)
        for kind, other in (("pred", pred), ("null", null)):
            u, tau_i, keys = _phases(true, other, width)
            band = (tau_i >= TAU_LO) & (tau_i < TAU_HI) & ~th._flicker(tau_i)
            if kind == "pred":
                out["n_true_tested"] += int(np.isin(tk, keys).sum())
                out["n_true_band"] += int(np.isin(tk, keys[band]).sum())
            ub = u[band]
            np.add.at(out["hist"][kind], np.minimum((ub * U_BINS).astype(np.int64), U_BINS - 1), 1)
            c, s = float(np.cos(2 * np.pi * ub).sum()), float(np.sin(2 * np.pi * ub).sum())
            out["blocks"][kind].append([int(len(ub)), c, s])
    return out


def rayleigh(rows, m_min: int = M_MIN) -> dict:
    """Mean Rayleigh statistic over blocks with at least ``m_min`` pixels, and the share of blocks with
    ``Z > ln(100)`` (p below about 0.01 for a uniform ``u``)."""
    a = np.asarray(rows, dtype=np.float64).reshape(-1, 3)
    a = a[a[:, 0] >= m_min]
    if len(a) == 0:
        return {"blocks": 0, "pixels": 0, "mean_Z": float("nan"), "share_Z_above_ln100": float("nan")}
    z = (a[:, 1] ** 2 + a[:, 2] ** 2) / a[:, 0]
    return {"blocks": int(len(a)), "pixels": int(a[:, 0].sum()), "mean_Z": float(z.mean()),
            "share_Z_above_ln100": float((z > np.log(100.0)).mean())}


BOOT_SEED, BOOT_N = 20261016, 2000


def pool(by_recording: dict) -> dict:
    """One stratum: ``{recording: [block_phases(...) of its groups]}`` pooled over groups and recordings, with a
    95% interval of the mean Rayleigh statistic from a bootstrap over recordings."""
    names = sorted(by_recording)
    rows = {k: {r: [b for g in by_recording[r] for b in g["blocks"][k]] for r in names} for k in ("pred", "null")}
    out = {"n_recordings": len(names), "n_groups": int(sum(len(v) for v in by_recording.values())),
           "hist": {k: np.sum([g["hist"][k] for r in names for g in by_recording[r]], axis=0).astype(int).tolist()
                    for k in ("pred", "null")},
           "rayleigh": {}, "coverage": {}}
    for f in ("n_true_window", "n_true_moving", "n_true_tested", "n_true_band"):
        out["coverage"][f] = int(sum(g[f] for r in names for g in by_recording[r]))
    tot = out["coverage"]["n_true_window"]
    out["coverage"]["share_tested"] = out["coverage"]["n_true_tested"] / tot if tot else float("nan")
    out["coverage"]["share_band"] = out["coverage"]["n_true_band"] / tot if tot else float("nan")
    rng = np.random.default_rng(BOOT_SEED)
    for k in ("pred", "null"):
        out["rayleigh"][k] = rayleigh([b for r in names for b in rows[k][r]])
        per = []
        for r in names:
            a = np.asarray(rows[k][r], dtype=np.float64).reshape(-1, 3)
            a = a[a[:, 0] >= M_MIN]
            per.append(((a[:, 1] ** 2 + a[:, 2] ** 2) / a[:, 0]) if len(a) else np.zeros(0))
        means = []
        for _ in range(BOOT_N):
            pick = rng.integers(0, len(names), len(names))
            z = np.concatenate([per[i] for i in pick])
            if len(z):
                means.append(z.mean())
        out["rayleigh"][k]["mean_Z_ci95"] = ([float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))]
                                             if means else [float("nan")] * 2)
    return out
````

## Appendix B. `tests/test_phase_control_gate.py`

Normative.

````python
"""Gate for directive 027: the controlled model, the per-block phase test and the figure script."""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

from ec import hevcdiag as hd
from ec import phase as ph
from ec import phase_control as pc

ROOT = Path(__file__).resolve().parent.parent
W, H = 320, 240


def test_conditions_share_edges_and_counts():
    ev = {c: pc.control_scene(160, 40, 6, 2000.0, 3, 0.05, 40, 12, 7, c) for c in pc.CONDITIONS}
    n = {c: len(e[0]) for c, e in ev.items()}
    assert max(n.values()) - min(n.values()) <= 0.002 * n["shared"]
    for c in pc.CONDITIONS:                   # every pixel of every row fires on each passage
        assert set(np.unique(ev[c][1])) == set(range(160))


def test_exact_motion_on_the_model():
    f = {}
    for c in pc.CONDITIONS:
        e = pc.control_scene(160, 40, 6, 2000.0, 3, 0.05, 40, 12, 7, c)
        f[c] = {k: hd.oracle_shift(e, 6, 1, k, 160, 40, 12)["F"] for k in (3, 64)}
    assert f["shared"][3] == 1.0 and f["shared"][64] == 1.0
    assert abs(f["independent"][64] - hd.binfidmoved(pc.T0 / 64, 2000.0, 3)) < 0.01
    assert abs(f["jitter"][64] - f["independent"][64]) < 0.02          # a jitter of 0.05 tau changes little
    assert f["independent"][3] > 0.9


def test_rayleigh():
    r = pc.rayleigh([[5, 5.0, 0.0], [10, 0.0, 0.0], [2, 2.0, 0.0]])     # the block of 2 pixels is left out
    assert r["blocks"] == 2 and r["pixels"] == 15
    assert r["mean_Z"] == 2.5 and r["share_Z_above_ln100"] == 0.5


def test_block_phases_separate_shared_from_independent():
    z = {}
    for shared in (False, True):
        o = pc.block_phases(ph.edge_scene_v(W, H, 6.5, 2000.0, 3, 0.05, 40, 8, 1, shared), 5, W, H)
        assert o["n_true_band"] <= o["n_true_tested"] <= o["n_true_moving"] <= o["n_true_window"]
        r = pc.rayleigh(o["blocks"]["pred"])
        assert int(o["hist"]["pred"].sum()) == int(np.sum([b[0] for b in o["blocks"]["pred"]]))
        z[shared] = r["mean_Z"]
        assert 0.7 < pc.rayleigh(o["blocks"]["null"])["mean_Z"] < 1.3
    assert 0.7 < z[False] < 1.3 and z[True] > 10.0


def test_pool_and_figures(tmp_path):
    outs = {f"r{s}": [pc.block_phases(ph.edge_scene_v(W, H, 6.5, 2000.0, 3, 0.05, 40, 8, s, False), 5, W, H)]
            for s in (1, 2)}
    p = pc.pool(outs)
    lo, hi = p["rayleigh"]["pred"]["mean_Z_ci95"]
    assert p["n_groups"] == 2 and lo <= p["rayleigh"]["pred"]["mean_Z"] <= hi
    assert 0 < p["coverage"]["share_band"] <= p["coverage"]["share_tested"] <= 1
    rep = {"control": [pc.control_cell(t, c, 160, 40) for t in (1000.0, 4000.0) for c in pc.CONDITIONS],
           "model_phase": {"shared": {"hist": [50] + [0] * 19}, "independent": {"hist": [5] * 20}},
           "strata": {k: p for k in ("day", "night", "all")}}
    (tmp_path / "pc").mkdir()
    (tmp_path / "pc" / "report.json").write_text(json.dumps(rep))
    r = ROOT / "results"
    subprocess.run([sys.executable, str(ROOT / "scripts" / "fig_027.py"), "--pc", str(tmp_path / "pc"),
                    "--hd", str(r / "hd"), "--hc", str(r / "hc"), "--demo", str(r / "td2"), "--paper",
                    str(r / "paper"), "--out", str(tmp_path)], check=True)
    for name in ("fig_moved2", "fig_phase3", "fig_tolerance_compact2", "fig_hevc2"):
        for ext in ("pdf", "png", "json"):
            assert (tmp_path / f"{name}.{ext}").stat().st_size > 0
    fm = json.loads((tmp_path / "fig_moved2.json").read_text())
    assert all(v == 1.0 for v in fm["a"]["shared"]["F"])
    fp = json.loads((tmp_path / "fig_phase3.json").read_text())
    assert fp["b"]["day"]["mean_Z"] == p["rayleigh"]["pred"]["mean_Z"]
    assert abs(np.mean(fp["b"]["day"]["density"]) - 1.0) < 1e-9
````

## Appendix C. `scripts/fig_027.py`

Normative.

````python
"""Directive 027: figures of the manuscript after the third review, drawn from committed files only.

  python3 scripts/fig_027.py --pc results/pc --hd results/hd --hc results/hc --demo results/td2 \
      --paper results/paper --out results/paper

fig_moved2  (a) The controlled model of ``ec.phase_control``, n = 3: F of the counts moved along the true
            motion against dt / tau, for shared phases without jitter, independent phases without jitter and
            independent phases with jitter, from ``pc/report.json#/control``; lines: min(dt / tau, 1) and
            dt / tau - dt^2 / (3 n tau^2) where dt <= tau / 2. (b) As (b) of ``fig_moved`` (directive 023).

fig_phase3  (a) As ``fig_phase2`` (directive 026), from ``paper/fig_phase2.json``. (b) The histogram of u,
            centred on 0, as a density, for the pixels of moving blocks with 0.25 <= tau_i < 4 ms outside the
            flicker classes, per stratum, of the null pooled over strata, and of the model scenes with shared
            and with independent phases, from ``pc/report.json``; the legend gives the mean Rayleigh
            statistic per block of each stratum.

fig_tolerance_compact2
            As ``fig_tolerance_compact`` (directive 026), with column titles that name what each code sends,
            F on (1 px, T0 / 3) in the panel of the whole window, F on (1 px, T0 / 32) in the panel of the
            slice, and the pixel counts of the comparison in its panel.

fig_hevc2   As ``fig_hevc`` (directive 023), with row (c) the motion error of the P-picture decode,
            placement ``start``, median over recordings, from ``hd/frontier.json``.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

BLUE, ORANGE, AQUA = "#2a78d6", "#d6542a", "#1baf7a"
PURPLE = "#8a5cc2"
INK, MUTED, FAINT = "#0b0b0b", "#6f6e69", "#e4e3dd"
STRATA = (("eTraM, day", "day", BLUE, "o"), ("eTraM, night", "night", AQUA, "^"), ("DSEC", "all", ORANGE, "s"))
QPS = (12, 14, 16, 18, 20, 22, 24, 28)
CONDS = (("shared", "shared phases", INK, "s", INK), ("independent", "independent phases", BLUE, "o", BLUE),
         ("jitter", "independent phases, jitter", ORANGE, "^", "white"))
RECS = (("recorded", "recorded"), ("every", "all events"), ("pixel", "motion and one time\ncorrection per pixel"),
        ("motion", "motion only"))
BG, MATCH, MISSED, EXTRA = "#f6f6f4", "#9a9a96", "#6a3d9a", "#e8862a"
plt.rcParams.update({"font.family": "serif", "font.size": 8, "axes.linewidth": 0.6, "pdf.fonttype": 42,
                     "mathtext.fontset": "cm"})


def _finish(fig, out, plotted):
    fig.savefig(str(out) + ".pdf", bbox_inches="tight", pad_inches=0.02)
    fig.savefig(str(out) + ".png", dpi=220, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)
    Path(str(out) + ".json").write_text(json.dumps(plotted, indent=1) + "\n")


def _clean(ax):
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.tick_params(length=2, width=0.5)
    ax.tick_params(which="minor", length=1.2, width=0.4)
    ax.grid(color=FAINT, lw=0.5, zorder=0)


def _label(ax, s):
    ax.text(-0.16, 1.02, s, transform=ax.transAxes, fontsize=8, fontweight="bold", va="bottom")


def fig_moved2(pc, hc, out):
    fig, axes = plt.subplots(2, 1, figsize=(3.45, 4.3), constrained_layout=True)
    plotted = {"a": {}, "b": {}}
    ax = axes[0]
    for cond, lab, col, mk, face in CONDS:
        pts = sorted(((c["dt_over_tau"][k], c["F"][k]) for c in pc["control"] if c["condition"] == cond
                      for k in c["F"]), key=lambda p: p[0])
        r, f = np.array(pts).T
        ax.plot(r, f, mk, ms=3.0, mfc=face, mec=col, mew=0.7, ls="", zorder=3, label=lab)
        plotted["a"][cond] = {"dt_over_tau": r.tolist(), "F": f.tolist()}
    rr = np.geomspace(0.04, 200, 400)
    ax.plot(rr, np.minimum(rr, 1.0), color=MUTED, lw=0.9, ls=":", zorder=2, label=r"$\min(\Delta_t/\tau,1)$")
    rs = np.geomspace(0.04, 0.5, 100)
    ax.plot(rs, rs - rs ** 2 / 9.0, color=BLUE, lw=0.9, zorder=2,
            label=r"$\Delta_t/\tau-\Delta_t^2/(3n\tau^2)$")
    ax.set_xscale("log")
    ax.set_xlim(0.04, 200)
    ax.set_ylim(0, 1.05)
    ax.set_xlabel(r"$\Delta_t/\tau$")
    ax.set_ylabel(r"fidelity $F$, true motion")
    ax.legend(fontsize=6.5, frameon=False, loc="lower right")
    _clean(ax)
    _label(ax, "(a)")
    ax = axes[1]
    m5 = hc["tables"]["5_model"]
    keys = (("b_lossless_P", "x265, P pictures", BLUE, "o"), ("b_lossless_intra", "x265, intra only", ORANGE, "s"),
            ("b_sparse", "voxel list", INK, "^"))
    for tau, ls in ((1000, "-"), (4000, "--")):
        cells = sorted((c for c in m5.values() if c["n"] == 3 and c["s"] == 1 and c["tau"] == tau),
                       key=lambda c: c["dt_over_tau"])
        r = np.array([c["dt_over_tau"] for c in cells])
        for key, lab, col, mk in keys:
            y = np.array([c[key] for c in cells])
            ax.plot(r, y, color=col, ls=ls, lw=0.9, marker=mk, ms=2.6, mew=0, zorder=3,
                    label=lab if tau == 1000 else None)
            plotted["b"][f"tau{tau}_{key}"] = {"dt_over_tau": r.tolist(), "bits_per_event": y.tolist()}
    ax.plot([], [], color=MUTED, ls="-", lw=0.9, label=r"$\tau=1$ ms")
    ax.plot([], [], color=MUTED, ls="--", lw=0.9, label=r"$\tau=4$ ms")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(0.04, 200)
    ax.set_xlabel(r"$\Delta_t/\tau$")
    ax.set_ylabel("bits per event, lossless")
    ax.legend(fontsize=6.5, frameon=False, loc="upper right")
    _clean(ax)
    _label(ax, "(b)")
    _finish(fig, out / "fig_moved2", plotted)


def _centred(h):
    """A histogram over [0, 1) as a density over [-1/2, 1/2): bin centres and values."""
    h = np.asarray(h, dtype=np.float64)
    nb = len(h)
    d = h / h.sum() * nb if h.sum() else h
    c = (np.arange(nb) + 0.5) / nb
    c = np.where(c >= 0.5, c - 1.0, c)
    o = np.argsort(c)
    return c[o], d[o]


def fig_phase3(pc, p2, out):
    fig, axes = plt.subplots(2, 1, figsize=(3.45, 4.3), constrained_layout=True)
    plotted = {"a": p2["a"], "b": {}}
    ax = axes[0]
    ax.axvspan(8.0, 16.0, color=PURPLE, alpha=0.12, lw=0, zorder=0)
    ax.text(11.3, 0.55, "mains\nlighting", fontsize=6.5, color=PURPLE, ha="center")
    for i, (lab, key, col, mk) in enumerate(STRATA):
        a = p2["a"][key]
        x = np.array(a["tau_ms"]) * (1.0 + 0.06 * (i - 1))
        y, lo, hi = (np.array(a[k]) for k in ("cos", "lo", "hi"))
        ax.errorbar(x, y, yerr=[y - lo, hi - y], color=col, marker=mk, ms=3.2, lw=0.9, capsize=1.5,
                    elinewidth=0.6, label=lab, zorder=3)
        ax.plot(a["tau_ms"], a["null_cos"], color=MUTED, marker=mk, ms=2.2, lw=0, mfc="white", mew=0.5, zorder=2)
    ref = p2["a"]["shared_model_mean_cos"]
    ax.axhline(ref, color=INK, lw=0.8, ls="--", zorder=1)
    ax.text(0.14, ref - 0.03, "locked: shared phases (model)", fontsize=6.5, va="top", color=INK)
    ax.axhline(0.0, color=MUTED, lw=0.6, zorder=1)
    ax.text(0.14, 0.03, "uniform: independent phases", fontsize=6.5, va="bottom", color=MUTED)
    ax.set_xscale("log")
    ax.set_xlim(0.12, 33)
    ax.set_ylim(-0.08, 1.02)
    ax.set_xlabel(r"spacing $\tau_i$ of the target pixel (ms)")
    ax.set_ylabel(r"phase lock, mean $\cos 2\pi u$")
    ax.legend(fontsize=6.5, frameon=False, loc="center left", bbox_to_anchor=(0.0, 0.52))
    _clean(ax)
    _label(ax, "(a)")
    ax = axes[1]
    top = 3.4
    for cond, ls, lab in (("shared", "--", "model, shared"), ("independent", ":", "model, independent")):
        c, d = _centred(pc["model_phase"][cond]["hist"])
        ax.step(c, np.minimum(d, top), where="mid", color=INK, lw=0.9, ls=ls, label=lab, zorder=2)
        plotted["b"][f"model_{cond}"] = {"u": c.tolist(), "density": d.tolist()}
        if d.max() > top:
            ax.text(-0.13, top - 0.1, f"peak {d.max():.1f}", fontsize=6.5, va="top", ha="right")
    null = np.sum([pc["strata"][k]["hist"]["null"] for _, k, _, _ in STRATA], axis=0)
    c, d = _centred(null)
    ax.step(c, d, where="mid", color=MUTED, lw=1.6, alpha=0.5, label="random times", zorder=1)
    plotted["b"]["null"] = {"u": c.tolist(), "density": d.tolist()}
    for lab, key, col, mk in STRATA:
        c, d = _centred(pc["strata"][key]["hist"]["pred"])
        z = pc["strata"][key]["rayleigh"]["pred"]["mean_Z"]
        ax.step(c, d, where="mid", color=col, lw=1.0, label=fr"{lab.replace('eTraM, ', '')}, $\bar Z={z:.2f}$",
                zorder=3)
        plotted["b"][key] = {"u": c.tolist(), "density": d.tolist(), "mean_Z": z}
    ax.set_xlim(-0.5, 0.5)
    ax.set_ylim(0, top)
    ax.set_xlabel(r"position $u$ of moved events in the target train")
    ax.set_ylabel("density")
    ax.legend(fontsize=6.0, frameon=False, loc="upper right", ncol=1, handlelength=1.6)
    _clean(ax)
    _label(ax, "(b)")
    _finish(fig, out / "fig_phase3", plotted)


def compare(rec, true):
    """0 none, 1 both with the same sign, 2 recorded only (or opposite sign), 3 reconstruction only."""
    out = np.zeros(true.shape, dtype=np.int64)
    both = (rec != 0) & (true != 0)
    same = both & (np.sign(rec) == np.sign(true))
    out[same] = 1
    out[(true != 0) & ~same] = 2
    out[(rec != 0) & (true == 0)] = 3
    return out


def _tag(ax, s):
    ax.text(0.02, 0.03, s, transform=ax.transAxes, fontsize=6.5, ha="left", va="bottom",
            bbox=dict(boxstyle="square,pad=0.15", fc="white", ec="none", alpha=0.85))


def fig_tolerance_compact2(demo_dir, out, stratum="day", slc=2):
    meta = json.loads((Path(demo_dir) / "demo.json").read_text())[stratum]
    img = np.load(Path(demo_dir) / "demo.npz")
    starts = meta["frame_starts_us"]
    span = starts[1] - starts[0]
    t0 = starts[slc - 1]
    true_slice = img[f"{stratum}_recorded"][slc]
    h, w = true_slice.shape
    fig, axes = plt.subplots(3, len(RECS), figsize=(7.16, 3 * 7.16 / len(RECS) * h / w + 0.75),
                             constrained_layout=True)
    cmap = matplotlib.colormaps["RdBu_r"]
    cmap_d = ListedColormap([BG, MATCH, MISSED, EXTRA])
    plotted = {"stratum": stratum, "slice_us": [t0, t0 + span], "crop": meta["crop"], "recs": {}}
    for c, (name, title) in enumerate(RECS):
        rec = meta["recs"][name]
        fr = img[f"{stratum}_{name}"]
        for r, frame in ((0, fr[0]), (1, fr[slc])):
            axes[r, c].imshow(np.clip(frame, -1, 1), cmap=cmap, vmin=-1.6, vmax=1.6, interpolation="nearest")
        b = rec["bits_per_event"]
        axes[0, c].set_title(title + ("" if b is None else f"\n{b:.2f} bit/event"), fontsize=7)
        if name != "recorded":
            _tag(axes[0, c], fr"$F={rec['F']['k3']:.2f}$ on $T_0/3$")
            _tag(axes[1, c], fr"$F={rec['F']['k32']:.2f}$ on $T_0/32$")
        ax = axes[2, c]
        if name == "recorded":
            ax.axis("off")
            ax.legend(handles=[Patch(color=MATCH, label="event in both"), Patch(color=MISSED, label="missed"),
                               Patch(color=EXTRA, label="extra")], loc="center", frameon=False, fontsize=7)
            plotted["recs"][name] = {"bits_per_event": b, "F": rec["F"]}
        else:
            d = compare(fr[slc], true_slice)
            ax.imshow(d, cmap=cmap_d, vmin=-0.5, vmax=3.5, interpolation="nearest")
            n = {k: int((d == v).sum()) for k, v in (("both", 1), ("missed", 2), ("extra", 3))}
            _tag(ax, f"in both {n['both']}\nmissed {n['missed']}, extra {n['extra']}")
            plotted["recs"][name] = {"bits_per_event": b, "F": rec["F"], "pixels": n}
        for r in range(3):
            axes[r, c].set_xticks([]); axes[r, c].set_yticks([])
            for sp in axes[r, c].spines.values():
                sp.set_linewidth(0.4)
    axes[0, 0].set_ylabel("whole window", fontsize=7)
    axes[1, 0].set_ylabel(f"{t0 / 1000:.1f} to {(t0 + span) / 1000:.1f} ms", fontsize=7)
    axes[2, 1].set_ylabel("against the\nrecorded slice", fontsize=7)
    _finish(fig, Path(out) / "fig_tolerance_compact2", plotted)


def fig_hevc2(hc, fr, out):
    t1 = hc["tables"]["1_prediction_lossless"]
    t2 = hc["tables"]["2_prediction_lossy"]
    t3 = hc["tables"]["3_decode_errors"]
    grids = (("s1_k3", r"$\Delta_t=T_0/3$", "o"), ("s1_k64", r"$\Delta_t=T_0/64$", "s"))
    fig, axes = plt.subplots(3, 3, figsize=(7.16, 5.6), sharex=True, constrained_layout=True)
    plotted = {}
    for j, (lab, key, col, _) in enumerate(STRATA):
        plotted[key] = {}
        for g, glab, mk in grids:
            cell = t2[key][g]["qp"]
            bP = np.array([cell[f"qp{q}"]["b"]["median"] for q in QPS])
            FP = np.array([cell[f"qp{q}"]["F"]["median"] for q in QPS])
            bI = np.array([cell[f"qp{q}_intra"]["b"]["median"] for q in QPS])
            FI = np.array([cell[f"qp{q}_intra"]["F"]["median"] for q in QPS])
            shade = col if g == "s1_k64" else MUTED
            ax = axes[0, j]
            ax.plot(bP, FP, color=shade, marker=mk, ms=2.6, lw=1.0)
            ax.plot(bI, FI, color=shade, marker=mk, ms=2.6, lw=1.0, ls="--", mfc="white")
            bq = t1[key][g]["b_sparse"]["median"]
            ax.plot(bq, 1.0, marker="*", ms=6, color=shade, ls="", zorder=4)
            rem = np.array([t3[key][g][f"qp{q}"]["shares"]["removed1"]["median"] for q in QPS])
            axes[1, j].plot(bP, rem, color=shade, marker=mk, ms=2.6, lw=1.0)
            fq = fr[key][g]
            bF = np.array([fq[f"qp{q}"]["b"] for q in QPS])
            me = np.array([fq[f"qp{q}"]["tasks"]["start"]["motion_error_px"] for q in QPS])
            axes[2, j].plot(bF, me, color=shade, marker=mk, ms=2.6, lw=1.0)
            plotted[key][g] = {"qp": list(QPS), "b_P": bP.tolist(), "F_P": FP.tolist(), "b_intra": bI.tolist(),
                               "F_intra": FI.tolist(), "b_voxel_list": bq, "removed1": rem.tolist(),
                               "b_frontier": bF.tolist(), "motion_error_px": me.tolist()}
        axes[0, j].set_title(lab, fontsize=8)
    for i, ylab in enumerate(("fidelity $F$", "single events removed\n(share of input)",
                              "motion error\n(px per window)")):
        axes[i, 0].set_ylabel(ylab)
        for j in range(3):
            ax = axes[i, j]
            ax.set_xscale("log")
            _clean(ax)
            if i == 2:
                ax.set_xlabel("bits per event")
    for j in range(3):
        axes[0, j].set_ylim(0, 1.03)
        axes[1, j].set_ylim(-0.02, 1.0)
        axes[2, j].set_ylim(0, None)
    for i, s in enumerate("abc"):
        _label(axes[i, 0], f"({s})")
    handles = [Line2D([], [], color=MUTED, marker="o", ms=2.6, lw=1.0, label=r"$\Delta_t=T_0/3$"),
               Line2D([], [], color=INK, marker="s", ms=2.6, lw=1.0, label=r"$\Delta_t=T_0/64$ (stratum color)"),
               Line2D([], [], color=INK, lw=1.0, label="P pictures"),
               Line2D([], [], color=INK, lw=1.0, ls="--", label="intra only"),
               Line2D([], [], color=INK, marker="*", ms=6, ls="", label="voxel list, lossless")]
    fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=5, fontsize=7, frameon=False)
    _finish(fig, out / "fig_hevc2", plotted)


def main(argv=None):
    ap = argparse.ArgumentParser()
    for k in ("pc", "hd", "hc", "demo", "paper", "out"):
        ap.add_argument(f"--{k}", required=True)
    a = ap.parse_args(argv)
    load = lambda d, f: json.loads((Path(d) / f).read_text())
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    pc, hc = load(a.pc, "report.json"), load(a.hc, "report.json")
    fig_moved2(pc, hc, out)
    fig_phase3(pc, load(a.paper, "fig_phase2.json"), out)
    fig_tolerance_compact2(a.demo, out)
    fig_hevc2(hc, load(a.hd, "frontier.json"), out)


if __name__ == "__main__":
    main()
````
