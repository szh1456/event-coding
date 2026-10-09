# Directive 006. The three rate regimes: controlled validation of Theorem 2

| | |
|---|---|
| track | `regimes`, short name `rd` |
| population | none. No recording and no annotation is opened, listed or hashed |
| results directory | `results/rd/` |
| report | `docs/directives/reports/006.md` |
| runs after | nothing. It is independent of directive 007 and comes first because it is lower in number |

## 1. Why

Theorem 2 of the manuscript (`papers/tsp/main.tex`) gives the rate-distortion
function of the events of one pixel under a mean-squared timing tolerance `D`.
It has three regimes. Below the jitter variance the code describes every event
time and the rate is known exactly. Between the jitter variance and the
threshold `D_A = sigma^2 + tau^2 / 12` it describes one number per pixel, and the
theorem brackets the rate to within 0.255 bit per pixel. From `D_A` on the rate
is zero and the decoder regenerates the events.

The theorem was reviewed and its parts were checked numerically during the
review. The manuscript has no figure that shows it, and its Section VI-B is
reserved for one. This directive produces the numbers and the figure: the
theorem against a rate-distortion function that is computed without the
theorem, and against a coder that is simple enough to build. All definitions are
in the docstring of `ec/regimes.py` (Appendix A), which is part of this
directive.

This is a controlled experiment on the model. It says nothing about recorded
streams, which directive 007 measures.

## 2. Disclosure

Before this directive was written the director had:

- run `ec.regimes.run(SMOKE)`, the coarse configuration of the gate, and a
  second coarse run (the slopes of `REFERENCE` on a grid of 8 points per `sigma`,
  100,000 simulated pixels) whose only use was to lay out the figure;
- run `coder_simulated` alone at the reference size, to set the tolerances of
  R3, and seen its differences to `coder_numeric` (at most 1.8e-3 nat in the
  rate and 1.2e-3 relative in the distortion);
- not run `ec.regimes.run(REFERENCE)`;
- seen, during the review of the theory in an earlier session, a
  Blahut-Arimoto computation by a reviewing agent for other parameters
  (`n` in {1, 3, 4}, `sigma / tau` in {0.1, 0.25, 0.3}), in which no bound of the
  theorem was violated;
- had this directive reviewed by an independent agent, which reran the coarse
  layout run on grids of 8 and 4 points per `sigma` and reported 5, 9 and 5 rows
  in the three classes and a pass. Its findings changed the classification of
  the rows, added the check on the width of the bracket and relaxed the check
  at `D_A` to the rate alone.

## 3. Author decisions

**D-006-1, default: authorized.** The executor adds `ec/regimes.py`,
`tests/test_regimes_gate.py` and `scripts/rd_figure.py` with the content of
Appendices A, B and C, unchanged. Their SHA-256 are in Section 9.

**D-006-2, default: accepted.** Numbers and figures that enter the manuscript
are produced by the executor on the author's hosts and committed under
`results/`. The director writes the code into the directive and runs, on its own
side, only synthetic self-tests of seconds that touch no data and produce no
number of the paper.

**D-006-3, default: accepted.** The parameters of the figure are `n` = 3 events
per pixel and `sigma / tau` = 0.05. They are illustrative. The manuscript states
them, and makes no claim that they are those of a sensor.

**D-006-4, default: authorized.** `scripts/rd_figure.py` needs matplotlib, which
is not a dependency of the project. If it is absent on `cnt`, install it for the
user that runs the directive, and record its version in the provenance file.
Nothing else is installed.

## 4. What to run

On `cnt`, from the repository root, under `nice -n 19`, with one BLAS thread:

```
python3 -m pytest -q -p no:anyio
python3 -m ec.regimes reference results/rd/regimes.json
python3 scripts/rd_figure.py results/rd/regimes.json results/rd/fig_regimes.pdf
```

`scripts/rd_figure.py` also writes `results/rd/fig_regimes.png`. Commit all
three files. Expected cost: minutes of one core and under 2 GB of memory. The
host and the numerical library versions go into
`results/rd/provenance.json`. No acceleration is needed, and none is allowed:
run the reference as it is.

## 5. Acceptance checks

1. The suite passes with no skipped test, and `tests/test_regimes_gate.py` is
   unedited.
2. The three files of Appendices A to C have the SHA-256 of Section 9.
3. `python3 -m ec.regimes reference` exits with status 0, that is, every entry
   of `checks` in `results/rd/regimes.json` is true:
   - `R1_low_matches_formula`: on the rows with `r <= sigma` the numerical rate
     equals Eq. (rdlow) to 5e-4 nat per pixel, at a distortion equal to `r^2` to
     1e-3 relative;
   - `R1_mid_consistent_with_bounds`: on the rows between, the numerical bracket
     and the band between the bounds (rdmid) and (rdpos) overlap to 5e-4 nat;
   - `R1_mid_bracket_is_narrow`: on those rows the bracket is narrower than
     1e-2 nat, against a band of 0.13 nat;
   - `R1_zero_at_D_A`: on the rows whose distortion is within 0.2% of `D_A` or
     above, the rate is below 2e-3 nat;
   - `R1_grid_refinement`: the rate changes by less than 2e-3 nat when the grid
     is made twice as coarse;
   - `R2_coder_not_below_lower_bound`: no operating point of the quantizer lies
     below the lower bound of the theorem;
   - `R3_simulation_matches_rate`, `R3_simulation_matches_distortion`: the coder
     on simulated event times agrees with the coder computed from the density
     to 5e-3 nat and to 5e-3 relative;
   - `R3_regeneration_at_D_A`: the measured distortion of the regenerated events
     is `D_A` to 5e-3 relative.
4. `results/rd/fig_regimes.pdf` and `.png` exist and were drawn from the
   committed JSON.

A failed entry of check 3 is a `BLOCKED` report with the JSON committed as it
is. Do not change a tolerance, a grid or a seed. A failure would mean an error
in the theorem, in the computation or in a tolerance, and the director resolves
which.

## 6. Tables for the report

1. The constants: `D_A`, `s2`, `h_T`, `Gamma` in bit and its bound.
2. For every row of `rd`: `sqrt(D) / tau`, the numerical bracket
   (`R_lower`, `R_upper`) and the theorem (`theory_lower`, `theory_upper`), in
   bits per event (divide nats per pixel by `n ln 2`).
3. `R1` and `R3` as they are.
4. For every operating point of the coder: the step, `sqrt(D) / tau`, the rate
   in bits per event from the density and from the simulation, and the excess
   over the lower and the upper value of the theorem at that distortion.
5. The wall time and the peak memory.

## 7. What the report does not decide

There is no decision rule. The director places the figure in Section VI-B of
the manuscript and writes its text from Tables 2 and 4.

## 8. Predictions

Written before the reference run.

| quantity | predicted |
|---|---|
| `Gamma` | 0.187 bit per pixel (from the coarse runs; the bound is 0.255) |
| rows in the classes `low`, `mid`, `top` | 5, 9, 5 |
| numerical rate for `D <= sigma^2` against Eq. (rdlow) | equal to 1e-4 nat |
| numerical rate just above `sigma^2` | within 0.01 nat of the lower bound `U - Gamma` |
| numerical rate near `D_A` | within 0.01 nat of the lower bound (rdpos), below the upper bound `U` |
| quantizer on every component, `D <= sigma^2` | 0.20 to 0.30 bit per event above the theorem (the high-resolution loss of a uniform quantizer is 0.255 bit per component) |
| quantizer on the mean time, `sigma^2 < D < D_A` | 0.2 to 0.6 bit per pixel above the lower bound, most at its coarsest steps |
| regenerated events | distortion `D_A`, rate zero |

## 9. Files

SHA-256 of the file content, which is the text between the fence lines of its
appendix, ending in one newline.

| file | SHA-256 |
|---|---|
| `ec/regimes.py` | `31b614b15d44759c3c721cd322de5954c725c9d456e46869029a022cf677cefb` |
| `tests/test_regimes_gate.py` | `d88d2bd15a9c68c0eac44f16bc11044d0e183c6c6d458f4487d9727fd865a737` |
| `scripts/rd_figure.py` | `b1a8c35457592bd9535d9b032132f4c9e2707444674d541b15f289dd0a1d84d3` |

## 10. Outputs

| file | content |
|---|---|
| `results/rd/regimes.json` | the output of `ec.regimes.run(REFERENCE)` |
| `results/rd/fig_regimes.pdf`, `results/rd/fig_regimes.png` | the figure |
| `results/rd/provenance.json` | commit, host, Python, numpy, scipy and matplotlib versions, wall time, peak memory |

## 11. Sources

`docs/REFERENCE_LEDGER.md` gains three entries in the commit that adds this
directive: `blahut1972computation`, `rate_distortion_dual_lower_bound` and
`plug_in_entropy_bias`. The last two are `UNRESOLVED`: the code uses the
statements, which are derived in the ledger entries, and no source for them was
opened.

## Appendix A. `ec/regimes.py`

Normative. The executor commits this file unchanged.

```python
"""The three rate regimes of one pixel under a timing tolerance (directive 006). Reference implementation.

Model (manuscript, Section II). An edge of height ``V = n C`` passes a pixel in uniform
passage. The pixel emits ``n`` events at

    T_k = t_i + A + (k - 1) tau + eps_k,      k = 1 .. n,

with the phase time ``A`` uniform on ``(0, tau]``, the jitter ``eps_k`` independent
``N(0, sigma^2)``, and ``t_i`` and ``tau`` known to the encoder and the decoder. The
distortion is ``(1 / n) E ||T - That||^2``. After the known times are removed, an
orthonormal map (first row constant) sends the event times to

    X   = sqrt(n) (A + mean jitter):  uniform on (0, sqrt(n) tau) plus N(0, sigma^2),
    W_j ~ N(0, sigma^2),  j = 1 .. n - 1,  independent of X and of each other.

The manuscript states (Theorem 2), with ``s2 = n tau^2 / 12 + sigma^2``,
``D_A = sigma^2 + tau^2 / 12``, ``U(D) = (1/2) ln(s2 / (n D - (n - 1) sigma^2))`` and
``Gamma = (1/2) ln(2 pi e s2) - h(X)``:

    R(D) = h(T) - (n / 2) ln(2 pi e D)                    for D <= sigma^2,
    max(U - Gamma, n (D_A - D) / (2 s2), 0) <= R(D) <= U  for sigma^2 < D < D_A,
    R(D) = 0                                              for D >= D_A.

This module checks these statements without using them:

R1  Numerical rate-distortion function. Blahut-Arimoto on a discretized ``X`` gives a
    point of its rate-distortion function at a slope ``beta = 1 / (2 r^2)``. The Gaussian
    components are at the same slope, ``d_W = min(sigma^2, 1 / (2 beta))``. For each slope
    an upper value (``R_upper``, the mutual information at the fixed point) and the dual
    bound (``R_lower``) bracket the rate of the discretized source at the achieved
    distortion. A row is ``low`` when ``r <= sigma``, where the theorem is exact and the
    distortion is ``r^2``; ``top`` when its distortion is within 0.2% of ``D_A`` or above;
    and ``mid`` otherwise. Beyond the slope at which the rate reaches zero the iteration
    converges slowly to a single reproduction point, so a ``top`` row can show a distortion
    above ``D_A`` at a rate near zero. The computation is repeated on a grid twice as coarse.
R2  A simple coder: a uniform scalar quantizer with ideal entropy coding and centroid
    reconstruction. ``all``: on ``X`` and on every ``W_j``, one step. ``mean``: on ``X``
    alone, the ``W_j`` not described (reconstructed as zero). ``none``: nothing is
    described and the decoder outputs the mean times ``t_i + (k - 1/2) tau``.
R3  The coder of R2 run on simulated event times, with empirical joint entropies
    (plug-in with the Miller-Madow correction), empirical centroids and the measured
    distortion. This path does not use the density of ``X``.

All rates are in nats per pixel. ``run`` returns one dictionary, which ``main`` writes
as JSON. ``REFERENCE`` is the configuration of the figure. ``SMOKE`` is a coarse
configuration for the gate, with looser tolerances.
"""
from __future__ import annotations

import json
import sys

import numpy as np
from scipy import integrate
from scipy.special import ndtr
from scipy.stats import norm

LN2 = float(np.log(2.0))
SEED = 20261010

REFERENCE = {
    "name": "reference", "n": 3, "tau": 1.0, "sigma": 0.05,
    "rms_x_over_sigma": (0.2, 0.3, 0.45, 0.7, 1.0, 1.25, 1.6, 2.0, 2.6, 3.4, 4.5, 6.0, 8.0, 10.0, 12.0, 14.0,
                         17.0, 22.0, 40.0),
    "grid_per_sigma": 25, "ba_iters": 6000,
    "steps_all_over_sigma": (0.5, 0.8, 1.2, 1.8), "steps_mean_divisors": (12.0, 8.0, 5.0, 3.0, 2.0, 1.5, 1.2),
    "coder_grid_per_sigma": 100, "n_pixels": 2_000_000,
    "tol": {"low_abs_nat": 5e-4, "bounds_nat": 5e-4, "dual_gap_nat": 1e-2, "top_nat": 2e-3, "refine_dR_nat": 2e-3,
            "sim_dR_nat": 5e-3, "sim_rel_dD": 5e-3, "regen_rel": 5e-3},
}
SMOKE = {
    "name": "smoke", "n": 3, "tau": 1.0, "sigma": 0.05,
    "rms_x_over_sigma": (0.6, 1.0, 2.0, 6.0, 40.0),
    "grid_per_sigma": 8, "ba_iters": 1500,
    "steps_all_over_sigma": (0.8,), "steps_mean_divisors": (8.0, 3.0),
    "coder_grid_per_sigma": 40, "n_pixels": 200_000,
    "tol": {"low_abs_nat": 5e-3, "bounds_nat": 5e-3, "dual_gap_nat": 2e-2, "top_nat": 5e-3, "refine_dR_nat": 2e-2,
            "sim_dR_nat": 3e-2, "sim_rel_dD": 2e-2, "regen_rel": 2e-2},
}


def density(x, a, s):
    """Density of uniform(0, a) + N(0, s^2)."""
    return (ndtr(x / s) - ndtr((x - a) / s)) / a


def cdf(x, a, s):
    g = lambda u: u * ndtr(u) + norm.pdf(u)
    return s * (g(x / s) - g((x - a) / s)) / a


def eta(a, s):
    """Differential entropy in nats of uniform(0, a) + N(0, s^2), by quadrature."""
    def f(x):
        p = density(x, a, s)
        return -p * np.log(p) if p > 0 else 0.0
    v, _ = integrate.quad(f, -12 * s, a + 12 * s, points=[0, a], limit=2000, epsabs=1e-13, epsrel=1e-13)
    return float(v)


def constants(n, tau, s):
    a = float(np.sqrt(n) * tau)
    s2 = n * tau * tau / 12 + s * s
    e = eta(a, s)
    return {"n": int(n), "tau": float(tau), "sigma": float(s), "a": a, "s2": float(s2),
            "D_A": float(s * s + tau * tau / 12), "eta": e,
            "h_T": (n - 1) / 2 * float(np.log(2 * np.pi * np.e * s * s)) + e,
            "Gamma": 0.5 * float(np.log(2 * np.pi * np.e * s2)) - e,
            "Gamma_max": 0.5 * float(np.log(2 * np.pi * np.e / 12))}


TOP_MARGIN = 2e-3                     # a row within this relative distance below D_A is in the class top


def theory(D, c, low=None):
    """Theorem 2 at distortion ``D``: ``(lower, upper)`` in nats per pixel. Equal where the theorem is exact.

    ``low`` forces (True) or forbids (False) the exact formula of the regime ``D <= sigma^2``, for a
    row whose regime is known from its slope and whose distortion is at the boundary.
    """
    n, s, s2, DA = c["n"], c["sigma"], c["s2"], c["D_A"]
    if (D <= s * s) if low is None else low:
        r = c["h_T"] - n / 2 * np.log(2 * np.pi * np.e * D)
        return float(r), float(r)
    if D >= DA:
        return 0.0, 0.0
    U = 0.5 * np.log(s2 / (n * D - (n - 1) * s * s))
    return float(max(U - c["Gamma"], n * (DA - D) / (2 * s2), 0.0)), float(U)


def source_grid(a, s, h):
    """Midpoints and probabilities of a grid of step about ``h`` on the support of ``X``."""
    lo, hi = -7 * s, a + 7 * s
    N = int(np.ceil((hi - lo) / h))
    edges = lo + np.arange(N + 1) * (hi - lo) / N
    p = np.diff(cdf(edges, a, s))
    return 0.5 * (edges[1:] + edges[:-1]), p / p.sum()


def blahut_arimoto(x, p, beta, q=None, iters=6000, tol=1e-13):
    """One point of the rate-distortion function of the discrete source ``(x, p)`` under squared error.

    Returns ``D, R_lower, R_upper, q``: the achieved distortion, the dual lower bound and the
    achieved mutual information at that distortion, and the output distribution.
    """
    d = (x[:, None] - x[None, :]) ** 2
    K = np.exp(-beta * d)
    q = np.full(len(x), 1.0 / len(x)) if q is None else q
    for it in range(iters):
        qn = q * ((p / (K @ q)) @ K)
        done = it > 50 and np.max(np.abs(qn - q)) < tol
        q = qn
        if done:
            break
    Z = K @ q
    Q = K * q[None, :] / Z[:, None]
    D = float((p[:, None] * Q * d).sum())
    upper = float(-(p * np.log(Z)).sum() - beta * D)
    lower = upper - float(np.log(((p / Z) @ K).max()))
    return D, lower, upper, q


def rd_curve(c, h, rms_x, iters):
    """R1. One row per slope. The slope is ``1 / (2 r^2)`` for a target rms error ``r`` of ``X``."""
    n, s = c["n"], c["sigma"]
    x, p = source_grid(c["a"], s, h)
    rows, q = [], None
    for r in rms_x:
        beta = 1.0 / (2.0 * r * r)
        dX, lo, up, q = blahut_arimoto(x, p, beta, q, iters)
        dW = min(s * s, 1.0 / (2.0 * beta))
        gauss = (n - 1) * 0.5 * float(np.log(s * s / dW))
        D = (dX + (n - 1) * dW) / n
        cls = "low" if r <= s * (1 + 1e-9) else "top" if D >= c["D_A"] * (1 - TOP_MARGIN) else "mid"
        tl, tu = theory(D, c, low=(cls == "low"))
        rows.append({"class": cls, "r": float(r), "beta": float(beta), "D": float(D), "R_lower": lo + gauss,
                     "R_upper": up + gauss, "theory_lower": tl, "theory_upper": tu})
    return rows, len(x)


def ecsq_numeric(x, p, center, step):
    """Entropy in nats and distortion of a uniform quantizer of step ``step`` with a cell centered at ``center``."""
    cell = np.floor((x - center) / step + 0.5).astype(np.int64)
    cell -= cell.min()
    P = np.bincount(cell, weights=p)
    m1 = np.bincount(cell, weights=p * x)
    ok = P > 0
    cen = np.zeros_like(P)
    cen[ok] = m1[ok] / P[ok]
    return float(-(P[ok] * np.log(P[ok])).sum()), float((p * (x - cen[cell]) ** 2).sum())


def coder_numeric(c, steps_all, steps_mean, h):
    """R2, from the densities of ``X`` and ``W_j``."""
    n, s = c["n"], c["sigma"]
    x, p = source_grid(c["a"], s, h)
    w = np.arange(-9 * s, 9 * s, h) + h / 2
    pw = norm.pdf(w / s)
    pw /= pw.sum()
    out = {"all": [], "mean": []}
    for st in steps_all:
        HX, dX = ecsq_numeric(x, p, c["a"] / 2, st)
        HW, dW = ecsq_numeric(w, pw, 0.0, st)
        out["all"].append({"step": float(st), "R": HX + (n - 1) * HW, "D": (dX + (n - 1) * dW) / n})
    for st in steps_mean:
        HX, dX = ecsq_numeric(x, p, c["a"] / 2, st)
        out["mean"].append({"step": float(st), "R": HX, "D": (dX + (n - 1) * s * s) / n})
    out["none"] = {"R": 0.0, "D": c["D_A"]}
    return out


def helmert(n):
    """Orthonormal ``n x n`` matrix whose first row is constant."""
    H = np.zeros((n, n))
    H[0] = 1.0 / np.sqrt(n)
    for j in range(1, n):
        H[j, :j] = 1.0 / np.sqrt(j * (j + 1))
        H[j, j] = -j / np.sqrt(j * (j + 1))
    return H


def coder_simulated(c, steps_all, steps_mean, n_pix, seed=SEED):
    """R3. The coder of R2 on simulated event times of ``n_pix`` pixels."""
    n, tau, s = c["n"], c["tau"], c["sigma"]
    rng = np.random.default_rng(seed)
    t_i = rng.uniform(0.0, 50.0, n_pix)                        # arrival of the edge, known to the decoder
    A = tau * (1.0 - rng.random(n_pix))                         # uniform on (0, tau]
    k = np.arange(n)
    T = t_i[:, None] + A[:, None] + k[None, :] * tau + s * rng.standard_normal((n_pix, n))
    known = t_i[:, None] + k[None, :] * tau
    H = helmert(n)
    Z = (T - known) @ H.T                                       # column 0 is X, the others are the W_j

    def quantize(z, center, step):
        cell = np.floor((z - center) / step + 0.5).astype(np.int64)
        cell -= cell.min()
        cnt = np.bincount(cell)
        cen = np.bincount(cell, weights=z) / np.maximum(cnt, 1)
        return cell, cen[cell], int(cnt.size)

    def joint_entropy(cells, sizes):
        key = np.zeros(n_pix, dtype=np.int64)
        for cl, sz in zip(cells, sizes):
            key = key * sz + cl
        cnt = np.unique(key, return_counts=True)[1].astype(np.float64)
        P = cnt / n_pix
        # plug-in entropy with the Miller-Madow correction for its bias
        return float(-(P * np.log(P)).sum() + (cnt.size - 1) / (2.0 * n_pix)), int(cnt.size)

    def distortion(That):
        return float(((T - That) ** 2).sum(1).mean() / n)

    out = {"all": [], "mean": [], "n_pixels": int(n_pix)}
    for st in steps_all:
        cells, rec, sizes = [], np.empty_like(Z), []
        for j in range(n):
            cl, rec[:, j], sz = quantize(Z[:, j], c["a"] / 2 if j == 0 else 0.0, st)
            cells.append(cl); sizes.append(sz)
        Hj, n_cells = joint_entropy(cells, sizes)
        out["all"].append({"step": float(st), "R": Hj, "D": distortion(rec @ H + known), "cells": n_cells})
    for st in steps_mean:
        cl, rx, sz = quantize(Z[:, 0], c["a"] / 2, st)
        rec = np.zeros_like(Z)
        rec[:, 0] = rx
        Hj, n_cells = joint_entropy([cl], [sz])
        out["mean"].append({"step": float(st), "R": Hj, "D": distortion(rec @ H + known), "cells": n_cells})
    out["none"] = {"R": 0.0, "D": distortion(t_i[:, None] + (k[None, :] + 0.5) * tau)}   # the regenerated events
    return out


def run(cfg) -> dict:
    """All of R1 to R3 for one configuration, with the checks and their verdict."""
    c = constants(cfg["n"], cfg["tau"], cfg["sigma"])
    s, tol = c["sigma"], cfg["tol"]
    rms_x = s * np.asarray(cfg["rms_x_over_sigma"], dtype=np.float64)
    h = s / cfg["grid_per_sigma"]
    fine, n_fine = rd_curve(c, h, rms_x, cfg["ba_iters"])
    coarse, n_coarse = rd_curve(c, 2 * h, rms_x, cfg["ba_iters"])
    low, mid, top = ([r for r in fine if r["class"] == k] for k in ("low", "mid", "top"))
    b, inf = tol["bounds_nat"], float("inf")
    r1 = {"grid_points": n_fine, "grid_points_coarse": n_coarse, "h": float(h),
          "n_low": len(low), "n_mid": len(mid), "n_top": len(top),
          "low_max_abs_error": max((abs(r["R_upper"] - r["theory_upper"]) for r in low), default=inf),
          "low_max_rel_dD": max((abs(r["D"] / r["r"] ** 2 - 1.0) for r in low), default=inf),
          "mid_inside_bounds": bool(mid) and bool(all(r["theory_lower"] - b <= r["R_upper"]
                                                      and r["R_lower"] <= r["theory_upper"] + b for r in mid)),
          "mid_max_dual_gap": max((r["R_upper"] - r["R_lower"] for r in mid), default=inf),
          "mid_min_margin_to_upper": min((r["theory_upper"] - r["R_upper"] for r in mid), default=-inf),
          "mid_min_margin_to_lower": min((r["R_upper"] - r["theory_lower"] for r in mid), default=-inf),
          "top_max_rate": max((r["R_upper"] for r in top), default=inf),
          "top_max_rel_dD": max((abs(r["D"] / c["D_A"] - 1.0) for r in top), default=inf),
          "refinement_max_abs_dR": max(abs(a["R_upper"] - b_["R_upper"]) for a, b_ in zip(fine, coarse)),
          "refinement_max_rel_dD": max(abs(a["D"] - b_["D"]) / a["D"] for a, b_ in zip(fine, coarse))}

    steps_all = [float(v) * s for v in cfg["steps_all_over_sigma"]]
    steps_mean = [c["a"] / float(v) for v in cfg["steps_mean_divisors"]]
    num = coder_numeric(c, steps_all, steps_mean, s / cfg["coder_grid_per_sigma"])
    sim = coder_simulated(c, steps_all, steps_mean, cfg["n_pixels"])
    pairs = [(a, b_) for key in ("all", "mean") for a, b_ in zip(num[key], sim[key])] + [(num["none"], sim["none"])]
    excess = [pt["R"] - theory(pt["D"], c)[0] for key in ("all", "mean") for pt in num[key]]
    r3 = {"max_abs_dR": max(abs(a["R"] - b_["R"]) for a, b_ in pairs),
          "max_rel_dD": max(abs(a["D"] - b_["D"]) / a["D"] for a, b_ in pairs),
          "regen_D_over_D_A": sim["none"]["D"] / c["D_A"],
          "coder_min_excess_over_lower_bound": min(excess), "coder_max_excess_over_lower_bound": max(excess)}
    checks = {
        "R1_low_matches_formula": r1["low_max_abs_error"] < tol["low_abs_nat"] and r1["low_max_rel_dD"] < 1e-3,
        "R1_mid_consistent_with_bounds": r1["mid_inside_bounds"],
        "R1_mid_bracket_is_narrow": r1["mid_max_dual_gap"] < tol["dual_gap_nat"],
        "R1_zero_at_D_A": r1["top_max_rate"] < tol["top_nat"],
        "R1_grid_refinement": r1["refinement_max_abs_dR"] < tol["refine_dR_nat"],
        "R2_coder_not_below_lower_bound": r3["coder_min_excess_over_lower_bound"] > -tol["bounds_nat"],
        "R3_simulation_matches_rate": r3["max_abs_dR"] < tol["sim_dR_nat"],
        "R3_simulation_matches_distortion": r3["max_rel_dD"] < tol["sim_rel_dD"],
        "R3_regeneration_at_D_A": abs(r3["regen_D_over_D_A"] - 1.0) < tol["regen_rel"],
    }
    checks = {k: bool(v) for k, v in checks.items()}
    return {"config": {k: (list(v) if isinstance(v, tuple) else v) for k, v in cfg.items()}, "constants": c,
            "rd": fine, "rd_coarse": coarse, "R1": r1, "coder": num, "coder_simulated": sim, "R3": r3,
            "checks": checks, "pass": bool(all(checks.values()))}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2 or argv[0] not in ("reference", "smoke"):
        sys.exit("usage: python3 -m ec.regimes reference|smoke OUT.json")
    import pathlib
    pathlib.Path(argv[1]).parent.mkdir(parents=True, exist_ok=True)
    open(argv[1], "a").close()                                  # fail before the computation, not after it
    out = run(REFERENCE if argv[0] == "reference" else SMOKE)
    with open(argv[1], "w") as f:
        json.dump(out, f, indent=1)
        f.write("\n")
    c = out["constants"]
    print(f"n={c['n']} tau={c['tau']} sigma={c['sigma']}  D_A={c['D_A']:.6f}  Gamma={c['Gamma'] / LN2:.4f} bit "
          f"(at most {c['Gamma_max'] / LN2:.4f})")
    for k, v in out["checks"].items():
        print(f"  {'PASS' if v else 'FAIL'}  {k}")
    print("PASS" if out["pass"] else "FAIL")
    return 0 if out["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

## Appendix B. `tests/test_regimes_gate.py`

Normative. The executor commits this file unchanged.

```python
"""Gate for directive 006: the three rate regimes of one pixel, on the coarse configuration.

The configuration ``ec.regimes.SMOKE`` and its tolerances are fixed by the director. The gate
checks that the computation runs and agrees with Theorem 2 of the manuscript to the coarse
tolerances. The figure comes from ``ec.regimes.REFERENCE``, which this file does not run.
"""
import numpy as np
import pytest

from ec import regimes


def test_constants_and_the_bound_on_the_gap():
    c = regimes.constants(3, 1.0, 0.05)
    assert abs(c["D_A"] - (0.05 ** 2 + 1.0 / 12)) < 1e-15
    assert abs(c["s2"] - (3.0 / 12 + 0.05 ** 2)) < 1e-15
    assert 0.0 <= c["Gamma"] <= c["Gamma_max"]
    assert abs(c["Gamma_max"] / regimes.LN2 - 0.2546) < 1e-4
    # the entropy of uniform + Gaussian lies between the entropy-power bound and the Gaussian bound
    for a, s in ((1.0, 1e-3), (1.0, 0.1), (1.0, 1.0), (3.7, 0.2)):
        e = regimes.eta(a, s)
        assert 0.5 * np.log(a * a + 2 * np.pi * np.e * s * s) <= e + 1e-9
        assert e <= 0.5 * np.log(2 * np.pi * np.e * (a * a / 12 + s * s)) + 1e-9


def test_theory_is_continuous_at_the_jitter_variance_up_to_the_gap_and_zero_from_the_threshold():
    c = regimes.constants(3, 1.0, 0.05)
    s2 = c["sigma"] ** 2
    lo, up = regimes.theory(s2, c)
    assert lo == up
    lo2, up2 = regimes.theory(s2 * (1 + 1e-9), c)
    assert abs(lo2 - lo) < 1e-6 and abs(up2 - lo - c["Gamma"]) < 1e-6
    assert regimes.theory(c["D_A"], c) == (0.0, 0.0)
    lo3, up3 = regimes.theory(0.999 * c["D_A"], c)
    assert 0.0 < lo3 <= up3 < 2e-3
    # a row whose slope puts it in the exact regime is scored with the exact formula at the boundary
    assert regimes.theory(s2 * (1 + 1e-9), c, low=True) == pytest.approx((lo, lo), abs=1e-6)
    assert regimes.theory(s2, c, low=False)[1] == pytest.approx(lo + c["Gamma"], abs=1e-9)


def test_blahut_arimoto_reproduces_a_gaussian_source():
    x = np.linspace(-6.0, 6.0, 241)
    p = np.exp(-0.5 * x * x)
    p /= p.sum()
    D, lo, up, _ = regimes.blahut_arimoto(x, p, beta=1.0 / (2 * 0.25), iters=3000)
    assert abs(D - 0.25) < 2e-3 and abs(up - 0.5 * np.log(1.0 / D)) < 2e-3 and lo <= up + 1e-12


def test_the_helmert_matrix_is_orthonormal_with_a_constant_first_row():
    for n in (1, 2, 3, 5):
        H = regimes.helmert(n)
        assert np.allclose(H @ H.T, np.eye(n)) and np.allclose(H[0], 1 / np.sqrt(n))


def test_the_coarse_configuration_passes_every_check():
    out = regimes.run(regimes.SMOKE)
    assert out["pass"], out["checks"]
    assert (out["R1"]["n_low"], out["R1"]["n_mid"], out["R1"]["n_top"]) == (2, 2, 1)
    assert [r["class"] for r in out["rd"]] == ["low", "low", "mid", "mid", "top"]
    assert len(out["checks"]) == 9
    # the regenerating decoder sits at the threshold, and the quantizer is above the lower bound
    assert abs(out["R3"]["regen_D_over_D_A"] - 1.0) < 0.02
    assert out["R3"]["coder_min_excess_over_lower_bound"] > 0.0


def test_reference_configuration_is_the_one_of_the_figure():
    r = regimes.REFERENCE
    assert (r["n"], r["tau"], r["sigma"], r["grid_per_sigma"], r["n_pixels"]) == (3, 1.0, 0.05, 25, 2_000_000)
    assert len(r["rms_x_over_sigma"]) == 19
```

## Appendix C. `scripts/rd_figure.py`

Normative. The executor commits this file unchanged.

```python
"""Directive 006: the figure of the three regimes, drawn from the JSON of ``ec.regimes``.

  python3 scripts/rd_figure.py IN.json OUT.pdf

Top: the rate in bits per event against the rms timing tolerance, on a logarithmic axis. Bottom:
the regime between the jitter and the regeneration threshold on a linear axis. Theorem 2 gives the
solid lines and the band between its bounds. The circles are the numerical rate-distortion
function (R1) and the squares the operating points of the simple coder (R2). Nothing is computed
here except Theorem 2 on a dense axis, through ``ec.regimes.theory``.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker  # noqa: F401
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ec import regimes  # noqa: E402

BLUE, ORANGE = "#2a78d6", "#d6542a"       # the two categorical colors of Fig. 1 of the manuscript
INK, MUTED, BAND = "#0b0b0b", "#52514e", "#dcdbd5"
plt.rcParams.update({"font.family": "serif", "font.size": 8, "axes.linewidth": 0.6, "pdf.fonttype": 42,
                     "mathtext.fontset": "cm"})


def draw(d, out_pdf):
    c = d["constants"]
    n, tau, s, DA = c["n"], c["tau"], c["sigma"], c["D_A"]
    per = 1.0 / (n * regimes.LN2)                          # nats per pixel -> bits per event
    x_s, x_a = s / tau, np.sqrt(DA) / tau

    def th(D):
        lo, up = zip(*(regimes.theory(float(v), c) for v in D))
        return np.array(lo) * per, np.array(up) * per

    ba = np.array([(np.sqrt(r["D"]) / tau, r["R_upper"] * per) for r in d["rd"]])
    cod = [(np.sqrt(p["D"]) / tau, p["R"] * per) for k in ("all", "mean") for p in d["coder"][k]]
    cod = np.array(cod + [(np.sqrt(d["coder"]["none"]["D"]) / tau, 0.0)])

    fig, (ax, bx) = plt.subplots(2, 1, figsize=(3.45, 3.9), gridspec_kw={"height_ratios": [1.25, 1.0], "hspace": 0.42})

    # top: all three regimes
    x_lo, x_hi = 0.6 * ba[:, 0].min(), 0.62
    r_lo = np.geomspace(x_lo, x_s, 60)
    ax.plot(r_lo, th((r_lo * tau) ** 2)[1], color=INK, lw=1.1, zorder=3, label="Theorem 2")
    r_mid = np.linspace(x_s, x_a, 200)[1:-1]
    lo, up = th((r_mid * tau) ** 2)
    ax.fill_between(r_mid, lo, up, color=BAND, lw=0, zorder=1)
    ax.plot(r_mid, lo, color=INK, lw=0.6, zorder=2)
    ax.plot(r_mid, up, color=INK, lw=0.6, zorder=2)
    ax.plot([x_a, x_hi], [0, 0], color=INK, lw=1.1, zorder=3)
    ax.plot(ba[:, 0], ba[:, 1], "o", color=BLUE, ms=3.4, mec="white", mew=0.5, zorder=5, label="numerical $R(D)$")
    ax.plot(cod[:, 0], cod[:, 1], "s", color=ORANGE, ms=3.2, mec="white", mew=0.5, zorder=4, label="scalar quantizer")
    y_hi = 1.12 * max(ba[:, 1].max(), cod[:, 1].max())
    for xv in (x_s, x_a):
        ax.plot([xv, xv], [0, y_hi], color=MUTED, lw=0.5, ls=(0, (2, 2)), zorder=0)
    ax.set_xscale("log")
    ax.set_xlim(x_lo, x_hi)
    ticks = [v for v in (0.003, 0.01, 0.03, 0.1, 0.3) if x_lo <= v <= x_hi]
    ax.set_xticks(ticks)
    ax.set_xticklabels([f"{v:g}" for v in ticks])
    ax.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    ax.set_ylim(-0.04 * y_hi, y_hi)
    ax.set_ylabel("bits per event", labelpad=2)
    ax.set_xlabel(r"rms timing tolerance $\sqrt{D}/\tau_i$", labelpad=1)
    top = ax.secondary_xaxis("top")
    top.set_xticks([x_s, x_a])
    top.set_xticklabels([r"$\sigma$", r"$\sqrt{D_{A,i}}$"])
    top.tick_params(length=2, width=0.5, pad=1)
    top.minorticks_off()
    ty = 0.93 * y_hi
    for xv, text in ((np.sqrt(x_lo * x_s) * 1.25, "every\nevent time"), (np.sqrt(x_s * x_a), "one number\nper pixel"),
                     (np.sqrt(x_a * x_hi), "nothing")):
        ax.text(xv, ty, text, ha="center", va="top", fontsize=7, color=INK, linespacing=1.05)
    ax.legend(loc="lower left", frameon=False, fontsize=7, handlelength=1.4, borderaxespad=0.3, labelspacing=0.3)

    # bottom: between the jitter and the threshold
    r_mid = np.linspace(x_s, x_a, 300)[1:]
    lo, up = th((r_mid * tau) ** 2)
    bx.fill_between(r_mid, lo, up, color=BAND, lw=0, zorder=1)
    bx.plot(r_mid, lo, color=INK, lw=0.6, zorder=2)
    bx.plot(r_mid, up, color=INK, lw=0.6, zorder=2)
    bx.plot([x_a, 1.12 * x_a], [0, 0], color=INK, lw=1.1, zorder=3)
    sel = ba[:, 0] >= 0.98 * x_s
    bx.plot(ba[sel, 0], ba[sel, 1], "o", color=BLUE, ms=3.4, mec="white", mew=0.5, zorder=5)
    sel = cod[:, 0] >= 0.98 * x_s
    bx.plot(cod[sel, 0], cod[sel, 1], "s", color=ORANGE, ms=3.2, mec="white", mew=0.5, zorder=4)
    y2 = 1.08 * max(up.max(), cod[sel, 1].max())
    bx.plot([x_a, x_a], [0, y2], color=MUTED, lw=0.5, ls=(0, (2, 2)), zorder=0)
    bx.set_xlim(0.9 * x_s, 1.12 * x_a)
    bx.set_ylim(-0.04 * y2, y2)
    bx.set_ylabel("bits per event", labelpad=2)
    bx.set_xlabel(r"rms timing tolerance $\sqrt{D}/\tau_i$", labelpad=1)
    k = int(np.argmin(np.abs(r_mid - 0.45 * (x_s + x_a))))
    bx.annotate("bounds of\nTheorem 2", xy=(r_mid[k], 0.5 * (lo[k] + up[k])), xytext=(r_mid[k] + 0.25 * (x_a - x_s), 0.62 * y2),
                fontsize=7, ha="left", va="center", color=INK,
                arrowprops=dict(arrowstyle="-", lw=0.5, color=MUTED, shrinkA=1, shrinkB=1))
    for a in (ax, bx):
        for sp in ("top", "right"):
            a.spines[sp].set_visible(False)
        a.tick_params(length=2, width=0.5)
        a.tick_params(which="minor", length=1.2, width=0.4)
    fig.savefig(out_pdf, bbox_inches="tight", pad_inches=0.02)
    fig.savefig(str(out_pdf)[:-4] + ".png", dpi=220, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


if __name__ == "__main__":
    if len(sys.argv) != 3 or not sys.argv[2].endswith(".pdf"):
        sys.exit("usage: python3 scripts/rd_figure.py IN.json OUT.pdf")
    draw(json.loads(Path(sys.argv[1]).read_text()), sys.argv[2])
    print("wrote", sys.argv[2])
```
