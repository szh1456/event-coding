# Directive 029. Shared and private information along a path, the power of the phase test, and the coding figures split

| | |
|---|---|
| track | `structure`, short name `st` |
| population | synthetic only: the model of the manuscript; the figures also read the committed `results/pc`, `results/pc2`, `results/hc` and `results/paper` |
| results directory | `results/st/`, and figures in `results/paper/` |
| report | `docs/directives/reports/029.md` |
| runs after | directive 028 (`DONE`, report at `2c732af`) |

## 1. Why

A fourth review asks for two results and one change of layout.

- **How shared and private costs grow along a path.** Theorem 1, Theorem 3 and Proposition 1 together say:
  - describing every event time costs bits in proportion to the number M of pixels on the path;
  - so does describing the common shift of each pixel;
  - describing the motion of a path with a fixed number of parameters costs O(ln M) for a receiver that holds
    the template.

  No figure shows this yet. `fig_scaling` shows the three totals against M on the model. Each has its
  theoretical value and an implemented quantizer, and the motion is quantized explicitly, so its curve is a
  measured cost and not the bound.
- **What lock the phase test can detect.** The shared-phase model of directive 027 is an ideal positive
  control. Here the lock is graded: the phases of a path spread over a width w of the spacing (w = 0 shared,
  w = 1 independent), with and without a spread of 20% in the spacings. The test of 027 runs on these scenes,
  with the motion and delay estimated from the events as on the recordings. The result says which lock widths
  the recordings rule out. It becomes panel (c) of `fig_phase4`.
- **Fig. 6 in two figures.** `fig_coding_cost` shows the cost (model bits; F against bits). `fig_task` shows
  the consequence for the receiver (the motion task).

## 2. Disclosure

The director wrote the three files of the appendices and ran them on the model only:
- `path_costs` took 5 s;
- `power_table` took 6 min on the laptop.

The suite passes. These are pipeline tests, not results. They gave:

- **Per pixel, at tau = 1 ms:**
  - the fine quantizer costs 0.75 bit per pixel above Theorem 2, that is 0.25 bit per component;
  - the scalar quantizer costs 0.80 bit per pixel, against the bounds 0.31 to 0.49.
- **Motion:** its quantized parameters cost 21 bits at M = 10 and 48 at M = 10^5, with a measured distortion
  of 1.00 to 1.01 times D_A.
- **Power, spacing spread 0:** the mean Rayleigh statistic falls from 81 at w = 0 to 6.2 at w = 0.6, 1.26 at
  w = 0.8 and 1.05 at w = 1.
- **Power, spacing spread 0.2:** it is 5.1 at w = 0 and 1.2 at w = 0.6.

## 3. Author decisions

**D-029-1, default: authorized.** The executor adds `ec/structure.py`, `tests/test_structure_gate.py` and
`scripts/fig_029.py` with the content of Appendices A to C, unchanged.

**D-029-2, default: authorized.** The executor writes a runner, for example `scripts/st_run.py`, that writes
`results/st/report.json` as:

    {"directive": "029", "paths": ec.structure.path_costs(), "power": ec.structure.power_table()}

with NumPy values converted to JSON. It also writes `results/st/provenance.json`.

**D-029-3, default: as stated in Sections 4 to 7.**

## 4. Run

Run on `cnt` under `nice -n 19`, or on the laptop: this directive reads no recording, and its cost is
minutes. Then draw the figures:

```
python3 scripts/fig_029.py --st results/st --pc results/pc --pc2 results/pc2 --hc results/hc \
    --paper results/paper --out results/paper
```

The gate reads committed results. As in directives 027 and 028, copy them into the host checkout before
running the suite there, and say so.

## 5. The report

The report gives:

1. **Definitions**, from the code:
   - the three descriptions and their tolerances;
   - how each quantizer step is chosen;
   - how the bits of the motion are counted;
   - how its distortion is measured;
   - the lock width and the spacing spread;
   - the pooling and the interval of the power table.
2. **Table 1:** per M, the six totals of `paths.rows`, and the measured distortion of the motion code against
   D_A.
3. **Table 2:** per lock width and spacing spread, the mean Rayleigh statistic with its interval, the
   blocks, the pixels per block, and the null.
4. **Two derived numbers per spacing spread:**
   - the largest w whose interval lies entirely above 2, the reading threshold of directive 027;
   - for each stratum of `results/pc/report.json`, the smallest w at which the model's mean Z falls below the
     upper end of that stratum's interval, by linear interpolation between grid points. Locks narrower than
     this w would have given a larger mean Z than the recording did.
5. **Pixels per block:** the model's against the recordings' (from `results/pc/report.json`: pixels over
   blocks per stratum). The Rayleigh statistic of a lock grows with that number.
6. For each of `fig_scaling`, `fig_phase4`, `fig_coding_cost` and `fig_task`:
   - what is plotted, and from which file and key;
   - the conclusions the data support, with their conditions;
   - the conclusions they do not support.

## 6. Acceptance checks

1. The three files have the SHA-256 of Section 7, and the suite passes with no skipped test.
2. **Quantizers:** in `paths.pixel_codes`, both measured distortions are at most their targets. In every row
   of `paths.rows`, `motion.D_over_DA_mean <= 1.1`.
3. **Motion bits:** between M = 10^2 and 10^4, `motion_code_bits` grows by `2 log2(100)` to within 1 bit.
4. **Power:** at `cv = 0`, the mean Z exceeds 10 at w = 0 and lies between 0.8 and 1.25 at w = 1.
5. **Figures:**
   - The four figures exist in `results/paper/` as PDF, PNG and JSON.
   - `fig_scaling.json` equals `results/st/report.json` for the plotted keys.
   - `fig_phase4.json#/c/recordings_<stratum>` equals the intervals of `results/pc/report.json`.
6. No recording was opened. Under `results/`, nothing outside `results/st/` and the four new figures changed.

## 7. Files

The SHA-256 is that of the file content: the text between the fence lines of its appendix, ending in one
newline.

| file | SHA-256 |
|---|---|
| `ec/structure.py` | `41e06d876d0677bc340865dfe7c0c411d365376e43d24f17e2e2bd5d7dbed167` |
| `tests/test_structure_gate.py` | `179d37233f3664af32328c76d4d67c8c5aecc2bd3815f3176f92a69bf7364823` |
| `scripts/fig_029.py` | `0f73fc25f5845580dd8bafcd415deddaf30b6eace89b6e00aad303bb6da1538c` |

## Appendix A. `ec/structure.py`

Normative. The executor commits this file unchanged.

````python
"""Shared and private information along a path, and the power of the phase test (directive 029).

Path costs (``path_costs``). The model of the manuscript for one straight edge translating along a row of M
pixels: pixel i starts its passage at ``t_i = (i - x0) / v`` and emits n events at
``t_i + A_i + (k - 1) tau + eps``, with ``tau = W_PX / (n v)``, ``A_i`` uniform on (0, tau] and ``eps`` normal
with standard deviation SIGMA_US. Three descriptions, each at its own tolerance:

- ``fine``, at D_FINE = SIGMA^2 / 16: every event time. Theory: M times Eq. (rdlow). Implementation: the
  rotation of Eq. (XW), and one uniform quantizer on the common shift and on each of the n - 1 relative
  components, with the empirical entropy of the indices;
- ``scalar``, at D_MID = (SIGMA^2 + D_A) / 2: the common shift only. Theory: the bounds of Eq. (rdmid), times
  M. Implementation: a uniform quantizer on the common shift, the relative components reconstructed at 0,
  with the empirical entropy of the indices;

  in both, the step is the largest, found by bisection, whose measured distortion is at most the target,
  and the indices are reconstructed at the mean of their cell;
- ``motion``, at (1 + XI) D_A, for a receiver that holds the template: the two parameters (x0, v), each by a
  uniform quantizer whose step keeps the bias of every regenerated mean time below ``sqrt(XI D_A) / 2``,
  with ``x0`` uniform on (0, M) and ``v`` uniform on (V_LO, V_HI). Bits are the base-2 logarithms of the
  numbers of cells. The distortion of the regenerated events of Eq. (regen) at the quantized parameters is
  measured on simulated paths, averaged over paths: Proposition 1 bounds an expected distortion.

The per-pixel costs of ``fine`` and ``scalar`` do not depend on M, since the pixels are independent given the
edge and the motion (Theorem 1); their totals are M times the per-pixel cost.

Power of the phase test (``lock_scene``). Straight edges as ``ec.phase.edge_scene_v``, with a partial lock of
the phases along each path: ``A_i = tau_i (1 - frac(a + w (U_i - 1/2)))`` with ``a`` one per row and edge and
``U_i`` uniform per pixel, so that ``w = 0`` is a shared phase and ``w = 1`` independent phases; and spacings
that vary from pixel to pixel, ``tau_i = tau exp(cv Z_i)`` with ``Z_i`` standard normal. The test is that of
directive 027 (``ec.phase_control.block_phases``), with the motion and delay estimated from the events.
"""
from __future__ import annotations

import numpy as np

from . import blockcodec as bc

T0 = bc.T0_US
N_EV = 3
SIGMA_US = 50.0
W_PX = 3.0                        # ramp width in pixels: tau = W_PX / (n v)
V_LO, V_HI = 500e-6, 2000e-6      # pixels per microsecond (0.5 to 2 px/ms): tau from 0.5 to 2 ms
V_REF = 1000e-6                   # tau = 1 ms for the fine and scalar curves
XI = 0.1
MS = (10, 30, 100, 300, 1000, 3000, 10000, 30000, 100000)
N_PIX = 200_000
WIDTHS = (0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0)
CVS = (0.0, 0.2)
SPEEDS = (2.5, 6.5, 13.3)
SEEDS = (1, 2, 3)


def tau_of(v: float) -> float:
    return W_PX / (N_EV * v)


def eta(a: float, sigma: float, n_grid: int = 200_001) -> float:
    """Differential entropy (nats) of the sum of a uniform variable on (0, a) and N(0, sigma^2)."""
    from math import erf, sqrt
    x = np.linspace(-8 * sigma, a + 8 * sigma, n_grid)
    s2 = sqrt(2.0) * sigma
    f = (np.vectorize(erf)((x) / s2) - np.vectorize(erf)((x - a) / s2)) / (2.0 * a)
    f = np.clip(f, 1e-300, None)
    trap = getattr(np, "trapezoid", None) or np.trapz
    return float(-trap(f * np.log(f), x))


def theory(tau: float, sigma: float = SIGMA_US, n: int = N_EV) -> dict:
    """Per-pixel rates (nats) of Theorem 2 at D_FINE and D_MID, and the constants."""
    e = eta(np.sqrt(n) * tau, sigma)
    h = 0.5 * (n - 1) * np.log(2 * np.pi * np.e * sigma ** 2) + e
    s2 = n * tau ** 2 / 12.0 + sigma ** 2
    d_a = sigma ** 2 + tau ** 2 / 12.0
    gamma = 0.5 * np.log(2 * np.pi * np.e * s2) - e
    d_fine, d_mid = sigma ** 2 / 16.0, 0.5 * (sigma ** 2 + d_a)
    u = 0.5 * np.log(s2 / (n * d_mid - (n - 1) * sigma ** 2))
    return {"tau": tau, "sigma": sigma, "n": n, "D_A": d_a, "s2": s2, "Gamma": gamma, "h": h,
            "D_fine": d_fine, "D_mid": d_mid, "R_fine": h - 0.5 * n * np.log(2 * np.pi * np.e * d_fine),
            "R_mid_upper": u, "R_mid_lower": max(u - gamma, 0.0)}


def _entropy_bits(idx) -> float:
    _, c = np.unique(idx, return_counts=True)
    p = c / c.sum()
    return float(-(p * np.log2(p)).sum())


def _quantize(Y, cols, step):
    """Uniform quantizer of ``step`` on the columns ``cols`` of Y, the others reconstructed at 0; the cells
    reconstruct at their mean. Returns (bits per row, distortion per event)."""
    Yh = np.zeros_like(Y)
    bits = 0.0
    for j in cols:
        idx = np.floor(Y[:, j] / step).astype(np.int64)
        u, inv = np.unique(idx, return_inverse=True)
        mean = np.bincount(inv, weights=Y[:, j]) / np.bincount(inv)
        Yh[:, j] = mean[inv]
        bits += _entropy_bits(idx)
    return bits, float(((Y - Yh) ** 2).sum(axis=1).mean() / Y.shape[1])


def _largest_step(Y, cols, target, lo, hi, iters=40):
    for _ in range(iters):
        mid = np.sqrt(lo * hi)
        if _quantize(Y, cols, mid)[1] <= target:
            lo = mid
        else:
            hi = mid
    return lo


def pixel_codes(tau: float, seed: int = 1, n_pix: int = N_PIX) -> dict:
    """Empirical bits per pixel and distortion of the fine and scalar quantizers (see the module docstring)."""
    rng = np.random.default_rng(seed)
    th = theory(tau)
    n, sig = N_EV, SIGMA_US
    A = (1.0 - rng.random(n_pix)) * tau
    T = A[:, None] + rng.normal(0.0, sig, (n_pix, n))     # T_i - c_i
    q = np.linalg.qr(np.c_[np.ones(n) / np.sqrt(n), rng.normal(size=(n, n - 1))])[0]
    q = q * np.sign(q[0, 0])
    Y = T @ q                                             # column 0: the common shift X_i, then W_i
    out = {}
    for name, cols, target in (("fine", range(n), th["D_fine"]), ("scalar", [0], th["D_mid"])):
        step = _largest_step(Y, cols, target, 1e-3 * sig, 100.0 * tau)
        bits, d = _quantize(Y, cols, step)
        out[name] = {"bits_per_pixel": bits, "D": d, "D_target": target, "step_us": step}
    return out


def motion_code(M: int, seed: int = 1, n_paths: int = 200) -> dict:
    """Bits of the quantized (x0, v) for a path of M pixels, and the measured distortion of the regenerated
    events against (1 + XI) D_A."""
    rng = np.random.default_rng((seed, M))
    n = N_EV
    d_a_max = SIGMA_US ** 2 + tau_of(V_LO) ** 2 / 12.0
    d_a_min = SIGMA_US ** 2 + tau_of(V_HI) ** 2 / 12.0
    b = np.sqrt(XI * d_a_min) / 2.0                        # bias allowed to each parameter
    dx = V_LO * b                                          # |d t / d x0| = 1 / v <= 1 / V_LO
    dv = b * V_LO ** 2 / (M + W_PX)                       # |d tbar / d v| <= (M + W_PX) / V_LO^2
    nx, nv = int(np.ceil(M / dx)), int(np.ceil((V_HI - V_LO) / dv))
    bits = float(np.log2(nx) + np.log2(nv))
    ratios = []
    i = np.arange(M, dtype=np.float64)
    k = np.arange(1, n + 1, dtype=np.float64)
    for _ in range(n_paths):
        x0, v = rng.random() * M, V_LO + rng.random() * (V_HI - V_LO)
        tau = tau_of(v)
        xh = (np.floor(x0 / dx) + 0.5) * dx
        vh = V_LO + (np.floor((v - V_LO) / dv) + 0.5) * dv
        A = (1.0 - rng.random(M)) * tau
        T = (i - x0)[:, None] / v + A[:, None] + (k - 1.0)[None, :] * tau + rng.normal(0.0, SIGMA_US, (M, n))
        That = (i - xh)[:, None] / vh + (k - 0.5)[None, :] * tau_of(vh)
        d = float(((T - That) ** 2).mean())
        ratios.append(d / (SIGMA_US ** 2 + tau ** 2 / 12.0))
    return {"M": M, "bits": bits, "n_x0_cells": nx, "n_v_cells": nv, "D_over_DA_mean": float(np.mean(ratios)),
            "D_over_DA_max": float(np.max(ratios)), "target": 1.0 + XI, "D_A_range": [d_a_min, d_a_max]}


def path_costs() -> dict:
    """Total bits along a path for every M of MS: theory and implementations (see the module docstring)."""
    th = theory(tau_of(V_REF))
    px = pixel_codes(tau_of(V_REF))
    ln2 = np.log(2.0)
    rows = []
    for M in MS:
        mc = motion_code(M)
        rows.append({"M": M,
                     "fine_theory_bits": M * th["R_fine"] / ln2, "fine_code_bits": M * px["fine"]["bits_per_pixel"],
                     "scalar_upper_bits": M * th["R_mid_upper"] / ln2,
                     "scalar_lower_bits": M * th["R_mid_lower"] / ln2,
                     "scalar_code_bits": M * px["scalar"]["bits_per_pixel"],
                     "motion_code_bits": mc["bits"], "motion": mc})
    return {"theory": {k: float(v) for k, v in th.items()}, "pixel_codes": px, "rows": rows}


def lock_scene(width: int, height: int, v_px: float, tau_us: float, n: int, sigma_frac: float, spacing: int,
               n_windows: int, seed: int, w: float, cv: float):
    """Straight edges with a partial lock of width ``w`` and spacings that vary by ``cv`` (see the module
    docstring). The edges and arrival times do not depend on ``w``."""
    r_edge, r_lock, r_tau, r_jit = (np.random.default_rng((seed, j)) for j in range(4))
    v = v_px / T0
    span = n_windows * T0
    T, X, Y, P = [], [], [], []
    xs = np.arange(width)
    for e, x_e in enumerate(range(-int(np.ceil(v * span)) - spacing, width, spacing)):
        for y in range(height):
            phi = r_edge.random()
            a = r_lock.random()
            u = r_lock.random(width)
            tau_i = tau_us * np.exp(cv * r_tau.normal(0.0, 1.0, width))
            eps = r_jit.normal(0.0, 1.0, (n, width))
            t0 = (xs - x_e + phi) / v
            ok = (t0 >= -n * tau_us) & (t0 < span)
            if not ok.any():
                continue
            frac = np.mod(a + w * (u - 0.5), 1.0)
            A = (tau_i * (1.0 - frac))[ok]
            for j in range(n):
                T.append(t0[ok] + A + j * tau_i[ok] + sigma_frac * tau_i[ok] * eps[j, ok])
                X.append(xs[ok]); Y.append(np.full(int(ok.sum()), y)); P.append(np.full(int(ok.sum()), e % 2))
    t = np.rint(np.concatenate(T)).astype(np.int64)
    x, y, p = (np.concatenate(c).astype(np.int64) for c in (X, Y, P))
    keep = (t >= 0) & (t < span)
    o = np.argsort(t[keep], kind="stable")
    return tuple(c[keep][o] for c in (t, x, y, p))


def power_table(width: int = 320, height: int = 240, tau_us: float = 2000.0) -> dict:
    """Mean Rayleigh statistic of ``ec.phase_control.block_phases`` per lock width and spacing spread, pooled
    over SPEEDS and SEEDS with ``ec.phase_control.pool`` (each scene enters as one recording)."""
    from . import phase_control as pc
    out = []
    for cv in CVS:
        for w in WIDTHS:
            scenes = {}
            for v in SPEEDS:
                for seed in SEEDS:
                    ev = lock_scene(width, height, v, tau_us, N_EV, 0.05, 40, 8, seed, w, cv)
                    scenes[f"v{v}_s{seed}"] = [pc.block_phases(ev, 5, width, height)]
            p = pc.pool(scenes)
            r = p["rayleigh"]["pred"]
            out.append({"w": w, "cv": cv, "mean_Z": r["mean_Z"], "ci95": r["mean_Z_ci95"], "blocks": r["blocks"],
                        "pixels_per_block": r["pixels"] / r["blocks"] if r["blocks"] else float("nan"),
                        "null_mean_Z": p["rayleigh"]["null"]["mean_Z"], "n_scenes": len(scenes)})
    return {"rows": out, "tau_us": tau_us, "speeds": list(SPEEDS), "seeds": list(SEEDS)}
````

## Appendix B. `tests/test_structure_gate.py`

Normative. The executor commits this file unchanged.

````python
"""Gate for directive 029: path costs, the partial-lock scenes and the figure script."""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

from ec import phase_control as pc
from ec import structure as st

ROOT = Path(__file__).resolve().parent.parent


def test_theory_constants():
    th = st.theory(1000.0)
    assert np.isclose(th["D_A"], 50.0 ** 2 + 1000.0 ** 2 / 12)
    assert np.isclose(th["D_A"], (th["s2"] + 2 * 50.0 ** 2) / 3)
    assert 0 <= th["Gamma"] <= 0.5 * np.log(2 * np.pi * np.e / 12) + 1e-9
    assert th["R_mid_lower"] <= th["R_mid_upper"] < th["R_fine"]
    assert abs(st.eta(1000.0, 1e-3) - np.log(1000.0)) < 1e-3


def test_quantizers_meet_their_targets():
    px = st.pixel_codes(1000.0, n_pix=20_000)
    th = st.theory(1000.0)
    for name, rate in (("fine", th["R_fine"]), ("scalar", th["R_mid_lower"])):
        assert px[name]["D"] <= px[name]["D_target"] * (1 + 1e-9)
        assert px[name]["bits_per_pixel"] >= rate / np.log(2) - 0.05


def test_motion_bits_grow_as_log():
    a, b = st.motion_code(100, n_paths=40), st.motion_code(10_000, n_paths=4)
    assert a["D_over_DA_mean"] <= 1 + st.XI and b["D_over_DA_mean"] <= 1 + st.XI
    assert abs((b["bits"] - a["bits"]) - 2 * np.log2(100)) < 1.0


def test_lock_width():
    ev0 = st.lock_scene(160, 40, 6.5, 2000.0, 3, 0.0, 40, 8, 1, 0.0, 0.0)
    ev1 = st.lock_scene(160, 40, 6.5, 2000.0, 3, 0.0, 40, 8, 1, 1.0, 0.0)
    assert set(np.unique(ev0[1])) == set(np.unique(ev1[1]))
    z = {}
    for w in (0.0, 1.0):
        o = pc.block_phases(st.lock_scene(320, 240, 6.5, 2000.0, 3, 0.05, 40, 8, 1, w, 0.0), 5, 320, 240)
        z[w] = pc.rayleigh(o["blocks"]["pred"])["mean_Z"]
    assert z[0.0] > 10.0 and 0.7 < z[1.0] < 1.4


def test_figures(tmp_path):
    rows = []
    for M in (10, 100, 1000):
        mc = st.motion_code(M, n_paths=5)
        rows.append({"M": M, "fine_theory_bits": 6.0 * M, "fine_code_bits": 6.8 * M, "scalar_upper_bits": 0.5 * M,
                     "scalar_lower_bits": 0.3 * M, "scalar_code_bits": 0.8 * M, "motion_code_bits": mc["bits"],
                     "motion": mc})
    power = [{"w": w, "cv": cv, "mean_Z": 1 + 50 * (1 - w) ** 3, "ci95": [1, 2 + 50 * (1 - w) ** 3]}
             for cv in (0.0, 0.2) for w in (0.0, 0.5, 1.0)]
    (tmp_path / "st").mkdir()
    (tmp_path / "st" / "report.json").write_text(json.dumps({"paths": {"rows": rows}, "power": {"rows": power}}))
    r = ROOT / "results"
    subprocess.run([sys.executable, str(ROOT / "scripts" / "fig_029.py"), "--st", str(tmp_path / "st"), "--pc",
                    str(r / "pc"), "--pc2", str(r / "pc2"), "--hc", str(r / "hc"), "--paper", str(r / "paper"),
                    "--out", str(tmp_path / "out")], check=True)
    for name in ("fig_scaling", "fig_phase4", "fig_coding_cost", "fig_task"):
        for ext in ("pdf", "png", "json"):
            assert (tmp_path / "out" / f"{name}.{ext}").stat().st_size > 0
    fs = json.loads((tmp_path / "out" / "fig_scaling.json").read_text())
    assert fs["motion_code_bits"] == [x["motion_code_bits"] for x in rows]
    fp = json.loads((tmp_path / "out" / "fig_phase4.json").read_text())
    rep = json.loads((r / "pc" / "report.json").read_text())
    assert fp["c"]["recordings_day"] == rep["strata"]["day"]["rayleigh"]["pred"]["mean_Z_ci95"]
````

## Appendix C. `scripts/fig_029.py`

Normative. The executor commits this file unchanged.

````python
"""Directive 029: the figures of the manuscript after the fourth review, drawn from committed files only.

  python3 scripts/fig_029.py --st results/st --pc results/pc --pc2 results/pc2 --hc results/hc \
      --paper results/paper --out results/paper

fig_scaling     Total bits along a path of M pixels, from ``st/report.json#/paths`` (``ec.structure.path_costs``):
                every event time at D_FINE (Eq. (rdlow), line; quantizer, circles); the common shift at D_MID
                (the band of Eq. (rdmid); quantizer, squares); legends name Theorem 2, not equation labels; the parameters of the motion at (1 + XI) D_A for
                a receiver that holds the template (quantizer, triangles), with a dashed line of slope
                2 log2 M through its first point, the slope of Eq. (B) for a translation.

fig_phase4      Recordings and the power of the test, three panels in a row. (a) and (b) as ``fig_recordings``
                (directive 028). (c) The mean per-block Rayleigh statistic on the model against the lock width
                w, for cv = 0 (filled) and 0.2 (open), with 95% intervals (``st/report.json#/power``); the
                95% intervals of the recordings (``pc/report.json``) as horizontal bands; the reading
                threshold 2 as a dotted line.

fig_coding_cost x265 as a case, one row: (a) the model of directive 021, lossless bits per event against dt / tau;
                (b) to (d) F against bits per event per stratum, as ``fig_coding`` rows (a) and (b).

fig_task        The motion task per stratum, as row (c) of ``fig_coding``.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D

BLUE, ORANGE, AQUA = "#2a78d6", "#d6542a", "#1baf7a"
PURPLE = "#8a5cc2"
INK, MUTED, FAINT = "#0b0b0b", "#6f6e69", "#e4e3dd"
STRATA = (("eTraM, day", "day", BLUE, "o"), ("eTraM, night", "night", AQUA, "^"), ("DSEC", "all", ORANGE, "s"))
QPS = (12, 14, 16, 18, 20, 22, 24, 28)
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


def _label(ax, s, x=-0.16):
    ax.text(x, 1.02, s, transform=ax.transAxes, fontsize=8, fontweight="bold", va="bottom")


def _centred(h):
    h = np.asarray(h, dtype=np.float64)
    nb = len(h)
    d = h / h.sum() * nb if h.sum() else h
    c = (np.arange(nb) + 0.5) / nb
    c = np.where(c >= 0.5, c - 1.0, c)
    o = np.argsort(c)
    return c[o], d[o]


def fig_scaling(st, out):
    rows = st["paths"]["rows"]
    M = np.array([r["M"] for r in rows], dtype=np.float64)
    get = lambda k: np.array([r[k] for r in rows])
    fig, ax = plt.subplots(1, 1, figsize=(3.45, 2.6), constrained_layout=True)
    ax.plot(M, get("fine_theory_bits"), color=BLUE, lw=1.0, label="every event time, Theorem 2")
    ax.plot(M, get("fine_code_bits"), "o", color=BLUE, ms=3.0, mfc="white", mew=0.8, label="every event time, quantizer")
    ax.fill_between(M, get("scalar_lower_bits"), get("scalar_upper_bits"), color=ORANGE, alpha=0.25, lw=0,
                    label="common shift, Theorem 2 bounds")
    ax.plot(M, get("scalar_code_bits"), "s", color=ORANGE, ms=3.0, mfc="white", mew=0.8, label="common shift, quantizer")
    mb = get("motion_code_bits")
    ax.plot(M, mb, "^", color=INK, ms=3.4, label="motion parameters, quantizer")
    ax.plot(M, mb[0] + 2.0 * np.log2(M / M[0]), color=INK, lw=0.8, ls="--", label=r"slope $2\log_2M$")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel(r"pixels on the path $M$")
    ax.set_ylabel("total bits")
    ax.legend(fontsize=6.0, frameon=False, loc="upper left")
    _clean(ax)
    plotted = {"M": M.tolist(), **{k: get(k).tolist() for k in ("fine_theory_bits", "fine_code_bits",
               "scalar_lower_bits", "scalar_upper_bits", "scalar_code_bits", "motion_code_bits")},
               "motion_D_over_DA_mean": [r["motion"]["D_over_DA_mean"] for r in rows]}
    _finish(fig, out / "fig_scaling", plotted)


def fig_phase4(st, pc, p2, out):
    fig, axes = plt.subplots(1, 3, figsize=(7.16, 2.75), constrained_layout=True)
    plotted = {"a": p2["a"], "b": {}, "c": {}}
    ax = axes[0]
    ax.axvspan(8.0, 16.0, color=PURPLE, alpha=0.12, lw=0, zorder=0)
    ax.text(11.3, 0.55, "mains\nlighting", fontsize=6.5, color=PURPLE, ha="center")
    for i, (lab, key, col, mk) in enumerate(STRATA):
        a = p2["a"][key]
        x = np.array(a["tau_ms"]) * (1.0 + 0.06 * (i - 1))
        y, lo, hi = (np.array(a[k]) for k in ("cos", "lo", "hi"))
        ax.errorbar(x, y, yerr=[y - lo, hi - y], color=col, marker=mk, ms=3.0, lw=0.9, capsize=1.5,
                    elinewidth=0.6, label=lab, zorder=3)
        ax.plot(a["tau_ms"], a["null_cos"], color=MUTED, marker=mk, ms=2.2, lw=0, mfc="white", mew=0.5, zorder=2)
    ref = p2["a"]["shared_model_mean_cos"]
    ax.axhline(ref, color=INK, lw=0.8, ls="--", zorder=1)
    ax.text(0.14, ref - 0.03, "shared phases (model)", fontsize=6.5, va="top", color=INK)
    ax.axhline(0.0, color=MUTED, lw=0.6, zorder=1)
    ax.set_xscale("log")
    ax.set_xlim(0.12, 33)
    ax.set_ylim(-0.08, 1.02)
    ax.set_xlabel(r"spacing $\tau_i$ of the target pixel (ms)")
    ax.set_ylabel(r"mean $\cos 2\pi u$")
    ax.legend(fontsize=6.0, frameon=False, loc="center left", bbox_to_anchor=(0.0, 0.55))
    _clean(ax)
    _label(ax, "(a)")
    ax = axes[1]
    top = 3.4
    hm, hs = [], []
    for cond, ls, lab in (("shared", "--", "model, shared"), ("independent", ":", "model, independent")):
        c, d = _centred(pc["model_phase"][cond]["hist"])
        hm += ax.step(c, np.minimum(d, top), where="mid", color=INK, lw=0.9, ls=ls, label=lab, zorder=2)
        plotted["b"][f"model_{cond}"] = {"u": c.tolist(), "density": d.tolist(), "clipped_at": top}
    null = np.sum([pc["strata"][k]["hist"]["null"] for _, k, _, _ in STRATA], axis=0)
    c, d = _centred(null)
    hm += ax.step(c, d, where="mid", color=MUTED, lw=1.6, alpha=0.5, label="random times", zorder=1)
    for lab, key, col, mk in STRATA:
        c, d = _centred(pc["strata"][key]["hist"]["pred"])
        z = pc["strata"][key]["rayleigh"]["pred"]["mean_Z"]
        hs.append(ax.step(c, d, where="mid", color=col, lw=1.0,
                          label=fr"{lab.replace('eTraM, ', '')}, $\bar Z={z:.2f}$", zorder=3)[0])
        plotted["b"][key] = {"u": c.tolist(), "density": d.tolist(), "mean_Z": z}
    ax.set_xlim(-0.5, 0.5)
    ax.set_ylim(0, top)
    ax.set_xlabel(r"position $u$ in the target train")
    ax.set_ylabel("density")
    ax.legend(handles=hs + hm, fontsize=6.0, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.24),
              ncol=2, handlelength=1.4, columnspacing=0.8)
    _clean(ax)
    _label(ax, "(b)")
    ax = axes[2]
    for lab, key, col, mk in STRATA:
        lo, hi = pc["strata"][key]["rayleigh"]["pred"]["mean_Z_ci95"]
        ax.axhspan(lo, hi, color=col, alpha=0.22, lw=0, zorder=1)
        plotted["c"][f"recordings_{key}"] = [lo, hi]
    ax.axhline(2.0, color=MUTED, lw=0.8, ls=":", zorder=1)
    ax.text(1.0, 2.1, "reading threshold", fontsize=6.0, color=MUTED, va="bottom", ha="right")
    for cv, face in ((0.0, INK), (0.2, "white")):
        rows = sorted((r for r in st["power"]["rows"] if r["cv"] == cv), key=lambda r: r["w"])
        w = np.array([r["w"] for r in rows])
        z = np.array([r["mean_Z"] for r in rows])
        lo, hi = np.array([r["ci95"] for r in rows]).T
        ax.errorbar(w, z, yerr=[z - lo, hi - z], color=INK, marker="o", ms=3.0, mfc=face, mew=0.8, lw=0.9,
                    elinewidth=0.6, capsize=1.2, zorder=3, label=fr"model, spacing spread {cv:.1f}")
        plotted["c"][f"cv{cv}"] = {"w": w.tolist(), "mean_Z": z.tolist(), "ci95": np.c_[lo, hi].tolist()}
    ax.set_yscale("log")
    ax.set_xlim(-0.03, 1.03)
    ax.set_xlabel(r"lock width $w$ (0: shared, 1: independent)")
    ax.set_ylabel(r"mean Rayleigh statistic $\bar Z$")
    ax.legend(fontsize=6.0, frameon=False, loc="upper right")
    _clean(ax)
    _label(ax, "(c)")
    _finish(fig, out / "fig_phase4", plotted)


def _model_bits(ax, m5, plotted):
    keys = (("b_lossless_P", BLUE, "o"), ("b_lossless_intra", ORANGE, "s"), ("b_sparse", INK, "^"))
    for tau, ls in ((1000, "-"), (4000, "--")):
        cells = sorted((c for c in m5.values() if c["n"] == 3 and c["s"] == 1 and c["tau"] == tau),
                       key=lambda c: c["dt_over_tau"])
        r = np.array([c["dt_over_tau"] for c in cells])
        for key, col, mk in keys:
            y = np.array([c[key] for c in cells])
            ax.plot(r, y, color=col, ls=ls, lw=0.9, marker=mk, ms=2.4, mew=0, zorder=3)
            plotted[f"tau{tau}_{key}"] = {"dt_over_tau": r.tolist(), "bits_per_event": y.tolist()}
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel(r"$\Delta_t/\tau$")
    ax.set_ylabel("lossless bits per event")
    ax.set_title("model", fontsize=8)


def fig_coding_cost(hc, out):
    t1 = hc["tables"]["1_prediction_lossless"]
    t2 = hc["tables"]["2_prediction_lossy"]
    fig, axes = plt.subplots(1, 4, figsize=(7.16, 2.35), constrained_layout=True)
    plotted = {"model": {}}
    _model_bits(axes[0], hc["tables"]["5_model"], plotted["model"])
    _clean(axes[0])
    _label(axes[0], "(a)", -0.3)
    for j, (lab, key, col, _) in enumerate(STRATA, start=1):
        plotted[key] = {}
        ax = axes[j]
        for g, mk in (("s1_k3", "o"), ("s1_k64", "s")):
            shade = col if g == "s1_k64" else MUTED
            cell = t2[key][g]["qp"]
            bP = np.array([cell[f"qp{q}"]["b"]["median"] for q in QPS])
            FP = np.array([cell[f"qp{q}"]["F"]["median"] for q in QPS])
            bI = np.array([cell[f"qp{q}_intra"]["b"]["median"] for q in QPS])
            FI = np.array([cell[f"qp{q}_intra"]["F"]["median"] for q in QPS])
            ax.plot(bP, FP, color=shade, marker=mk, ms=2.4, lw=1.0)
            ax.plot(bI, FI, color=shade, marker=mk, ms=2.4, lw=1.0, ls="--", mfc="white")
            bq = t1[key][g]["b_sparse"]["median"]
            ax.plot(bq, 1.0, marker="*", ms=6, color=shade, ls="", zorder=4)
            plotted[key][g] = {"qp": list(QPS), "b_P": bP.tolist(), "F_P": FP.tolist(), "b_intra": bI.tolist(),
                               "F_intra": FI.tolist(), "b_voxel_list": bq}
        ax.set_title(lab, fontsize=8)
        ax.set_xscale("log")
        ax.set_ylim(0, 1.03)
        ax.set_xlabel("bits per event")
        _clean(ax)
    axes[1].set_ylabel("fidelity $F$")
    _label(axes[1], "(b)")
    handles = [Line2D([], [], color=BLUE, marker="o", ms=2.4, lw=0.9, label="P pictures"),
               Line2D([], [], color=ORANGE, marker="s", ms=2.4, lw=0.9, label="intra only"),
               Line2D([], [], color=INK, marker="^", ms=2.4, lw=0.9, label="voxel list"),
               Line2D([], [], color=MUTED, lw=0.9, label=r"(a) $\tau=1$ ms"),
               Line2D([], [], color=MUTED, lw=0.9, ls="--", label=r"(a) $\tau=4$ ms"),
               Line2D([], [], color=MUTED, marker="o", ms=2.4, lw=1.0, label=r"(b) $\Delta_t=T_0/3$"),
               Line2D([], [], color=INK, marker="s", ms=2.4, lw=1.0, label=r"(b) $\Delta_t=T_0/64$"),
               Line2D([], [], color=INK, lw=1.0, ls="--", label="(b) intra only"),
               Line2D([], [], color=INK, marker="*", ms=6, ls="", label="(b) voxel list")]
    fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, 0.0), ncol=5, fontsize=6.3,
               frameon=False)
    _finish(fig, out / "fig_coding_cost", plotted)


def fig_task(mt, out):
    fig, axes = plt.subplots(1, 3, figsize=(7.16, 2.0), constrained_layout=True)
    plotted = {}
    for j, (lab, key, col, _) in enumerate(STRATA):
        ax = axes[j]
        plotted[key] = {}
        for g, mk in (("s1_k3", "o"), ("s1_k64", "s")):
            shade = col if g == "s1_k64" else MUTED
            m = mt["strata"][key][g]
            pts = [(m["qp"][f"qp{q}"]["b"], m["qp"][f"qp{q}"]["success1"], *m["qp"][f"qp{q}"]["ci95"]) for q in QPS]
            b, s, lo, hi = np.array(pts).T
            ax.errorbar(b, s, yerr=[s - lo, hi - s], color=shade, marker=mk, ms=2.4, lw=1.0, elinewidth=0.6,
                        capsize=1.2, label=(r"$\Delta_t=T_0/3$" if g == "s1_k3" else r"$\Delta_t=T_0/64$"))
            ax.axhline(m["reference"]["success1"], color=shade, lw=0.8, ls=":")
            plotted[key][g] = {"b": b.tolist(), "success1": s.tolist(), "ci95": np.c_[lo, hi].tolist(),
                               "reference_success1": m["reference"]["success1"]}
        ax.set_title(lab, fontsize=8)
        ax.set_xscale("log")
        ax.set_ylim(0, 1.03)
        ax.set_xlabel("bits per event")
        ax.legend(fontsize=6.0, frameon=False, loc="lower right")
        _clean(ax)
    axes[0].set_ylabel("motion recovered\nwithin 1 px (share)")
    _finish(fig, out / "fig_task", plotted)


def main(argv=None):
    ap = argparse.ArgumentParser()
    for k in ("st", "pc", "pc2", "hc", "paper", "out"):
        ap.add_argument(f"--{k}", required=True)
    a = ap.parse_args(argv)
    load = lambda d, f: json.loads((Path(d) / f).read_text())
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    st, pc, hc = load(a.st, "report.json"), load(a.pc, "report.json"), load(a.hc, "report.json")
    fig_scaling(st, out)
    fig_phase4(st, pc, load(a.paper, "fig_phase2.json"), out)
    fig_coding_cost(hc, out)
    fig_task(load(a.pc2, "motion_task.json"), out)


if __name__ == "__main__":
    main()
````
