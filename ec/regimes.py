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
