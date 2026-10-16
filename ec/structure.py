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
