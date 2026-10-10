"""Numerical checks of the statements that are specific to an affine flow (Sections II to IV).

P1  Lemma 2 and the remark on the uniform passage. For a ramp edge under an affine flow in the plane (scale, rotation and
    translation), the exact event times of a pixel are compared with t_i + A_i + (k - 1) tau_i, with
    tau_i = C / (gamma r_i) and r_i the crossing rate at t_i. The deviation is compared with the bound
    kappa_i P_i^2 / 2 of that remark. The closed form of the crossing rate, r_i = -<A_t^{-T} nu, v(i)>,
    is checked against a finite difference, and gamma r_i against |<grad L, v>| of Eq. (7).
    A time-stepping simulation of (A1) confirms the exact times on a subset of pixels.
P2  Remark on the event count. Under a pure change of scale about a fixed point, the number of pixels
    that an edge segment passes per unit time grows as the square of the scale factor.
P3  Appendix C. ln(sinh x / x) <= x^2 / 6, the inequality behind the lower bound (21), and the bound
    itself against the zero-rate point and the upper bound U of Theorem 2.
P4  Eq. (30). For one pixel and bins no longer than the event spacing, the voxel fidelity of the
    mean-time regeneration of an event train is Delta_t / tau in expectation over the phase.
P5  Proposition 2. The mean-squared timing error of events that are moved from one pixel to another,
    D_A,i + D_A,j + (4 n^2 - 1) (tau_i - tau_j)^2 / 12.

Synthetic data only. Usage: python3 check_affine_passage.py [out.json]
"""
from __future__ import annotations

import json
import math
import sys

import numpy as np
from scipy.linalg import expm
from scipy.optimize import brentq

C, GAMMA, N_LEVELS = 0.2, 0.3, 3            # threshold, slope per px (object units), events per pixel
WIDTH = N_LEVELS * C / GAMMA                # ramp width, so that V = n C


class Flow:
    """phi_t(u) = A_t u + b_t with velocity field v(x) = Lam x + v0."""

    def __init__(self, alpha, omega, v0):
        self.Lam = np.array([[alpha, -omega], [omega, alpha]], dtype=float)
        self.v0 = np.asarray(v0, dtype=float)
        self.Lam_inv = np.linalg.inv(self.Lam)

    def A(self, t):
        return expm(self.Lam * t)

    def b(self, t):
        return self.Lam_inv @ (self.A(t) - np.eye(2)) @ self.v0

    def u(self, i, t):                       # trajectory of pixel i in object coordinates
        return np.linalg.solve(self.A(t), np.asarray(i, dtype=float) - self.b(t))

    def v(self, x):
        return self.Lam @ np.asarray(x, dtype=float) + self.v0


def ramp(z):
    return np.clip(GAMMA * z, 0.0, N_LEVELS * C)


def check_passage(flow, nu, c0, pixels, t_lo, t_hi, rng, brute=6):
    nu = np.asarray(nu, dtype=float) / np.linalg.norm(nu)
    z = lambda i, t: float(nu @ flow.u(i, t) - c0)
    rows, n_brute = [], 0
    for i in pixels:
        if not (z(i, t_lo) < 0.0 < z(i, t_hi) - WIDTH):
            continue                          # the pixel must cross the whole ramp, from the low side
        t_i = brentq(lambda t: z(i, t), t_lo, t_hi, xtol=1e-13)
        m = np.linalg.solve(flow.A(t_i).T, nu)                 # A^{-T} nu
        r_closed = -float(m @ flow.v(i))
        h = 1e-6
        r_fd = (z(i, t_i + h) - z(i, t_i - h)) / (2 * h)
        if r_closed <= 0:
            continue
        tau = C / (GAMMA * r_closed)
        a = rng.uniform(0.0, C)
        levels = (a + C * np.arange(N_LEVELS)) / GAMMA          # edge coordinates of the events
        t_end = brentq(lambda t: z(i, t) - WIDTH, t_i, t_hi, xtol=1e-13)
        exact = np.array([brentq(lambda t, L=L: z(i, t) - L, t_i - 1e-9, t_end + 1e-9, xtol=1e-13) for L in levels])
        lemma = t_i + a / (GAMMA * r_closed) + tau * np.arange(N_LEVELS)
        cos_theta = abs(float(m @ flow.v(i))) / (np.linalg.norm(m) * np.linalg.norm(flow.v(i)))
        kappa = np.linalg.norm(flow.Lam, 2) / cos_theta
        P = N_LEVELS * tau
        # Eq. (6): gamma r_i = |<grad L, v>|, with grad L by central differences in the image at mid-passage
        t_mid = 0.5 * (t_i + t_end)
        L_at = lambda x: float(ramp(nu @ np.linalg.solve(flow.A(t_mid), np.asarray(x, dtype=float) - flow.b(t_mid)) - c0))
        e = 1e-4
        grad = np.array([(L_at((i[0] + e, i[1])) - L_at((i[0] - e, i[1]))) / (2 * e),
                         (L_at((i[0], i[1] + e)) - L_at((i[0], i[1] - e))) / (2 * e)])
        m_mid = np.linalg.solve(flow.A(t_mid).T, nu)
        rate_mid = -float(m_mid @ flow.v(i))
        row = {"dev": float(np.max(np.abs(exact - lemma))), "bound": 0.5 * kappa * P * P, "kappa_P": kappa * P,
               "r_rel_err": abs(r_fd - r_closed) / r_closed,
               "constancy_rel_err": abs(abs(float(grad @ flow.v(i))) - GAMMA * rate_mid) / (GAMMA * rate_mid),
               "tau": tau, "cos_theta": cos_theta}
        if n_brute < brute:                   # (A1) by time stepping
            dt = P / 200_000
            ts = np.arange(t_i - 0.05 * P, t_end + 0.05 * P, dt)
            # edge coordinate on the grid by interpolation of exact samples (smooth on this scale)
            tk = np.linspace(ts[0], ts[-1], 400)
            zk = np.array([z(i, t) for t in tk])
            s = ramp(np.interp(ts, tk, zk))
            ref, ev = a - C, []
            for k in range(len(ts)):
                while abs(s[k] - ref) >= C:
                    ref += C if s[k] > ref else -C
                    ev.append(ts[k])
            row["brute_count"] = len(ev)
            row["brute_dev"] = float(np.max(np.abs(np.array(ev) - exact))) if len(ev) == N_LEVELS else float("inf")
            row["brute_dt"] = dt
            n_brute += 1
        rows.append(row)
    return rows


def summarize(rows):
    dev = np.array([r["dev"] for r in rows]); bound = np.array([r["bound"] for r in rows])
    small = np.array([r["kappa_P"] for r in rows]) < 0.05           # first-order regime of the remark
    brute = [r for r in rows if "brute_dev" in r]
    return {"pixels": len(rows),
            "max_dev_over_bound_first_order_regime": float(np.max(dev[small] / bound[small])) if small.any() else None,
            "pixels_in_first_order_regime": int(small.sum()),
            "max_dev_s": float(dev.max()), "median_tau_s": float(np.median([r["tau"] for r in rows])),
            "max_rate_rel_err": float(max(r["r_rel_err"] for r in rows)),
            "max_constancy_rel_err": float(max(r["constancy_rel_err"] for r in rows)),
            "brute_pixels": len(brute), "brute_counts_all_n": all(r["brute_count"] == N_LEVELS for r in brute),
            "brute_max_dev_over_dt": float(max(r["brute_dev"] / r["brute_dt"] for r in brute)) if brute else None}


def check_count(alpha=0.6, d=400.0, length=60.0, t_a=0.0, t_b=1.0, window=0.2):
    """Pure scaling about the origin: v(x) = alpha x. Edge segment on the line <nu, u> = d, |<nu_perp, u>| <= length / 2."""
    nu, nup = np.array([1.0, 0.0]), np.array([0.0, 1.0])

    def passages(t0, t1):
        # pixel i reaches the edge at the time t with <nu, i> e^{-alpha t} = d
        count = 0
        for ix in range(1, 6000):
            t = math.log(ix / d) / alpha
            if not (t0 <= t < t1):
                continue
            s = math.exp(alpha * t)
            half = 0.5 * length * s                       # the segment is attached to the object
            count += int(math.floor(half)) + int(math.floor(half)) + 1
        return count

    n_a, n_b = passages(t_a, t_a + window), passages(t_b, t_b + window)
    # the swept area between t0 and t1 is d * length * (e^{2 alpha t1} - e^{2 alpha t0}) / 2
    area = lambda t0, t1: 0.5 * d * length * (math.exp(2 * alpha * t1) - math.exp(2 * alpha * t0))
    return {"passages_a": n_a, "passages_b": n_b, "ratio": n_b / n_a,
            "scale_factor_squared": math.exp(2 * alpha * (t_b - t_a)),
            "area_a": area(t_a, t_a + window), "area_b": area(t_b, t_b + window)}


def check_transport():
    x = np.concatenate((np.linspace(1e-6, 1.0, 2000), np.linspace(1.0, 60.0, 4000)))
    slack = x * x / 6.0 - (np.log(np.sinh(np.minimum(x, 700.0)) / x))
    out = {"min_slack_of_sinh_inequality": float(slack.min())}
    rows = []
    for n, tau, sigma in ((1, 1.0, 0.1), (3, 2.0, 0.5), (4, 1.0, 0.1)):
        s2 = n * tau * tau / 12 + sigma * sigma
        DA = sigma * sigma + tau * tau / 12
        for frac in (0.5, 0.9, 0.99, 0.999):
            D = sigma * sigma + frac * (DA - sigma * sigma)
            lower = n * (DA - D) / (2 * s2)
            U = 0.5 * math.log(s2 / (n * D - (n - 1) * sigma * sigma))
            rows.append({"n": n, "tau": tau, "sigma": sigma, "D_over_DA": D / DA, "lower": lower, "U": U,
                         "lower_le_U": bool(lower <= U + 1e-12)})
    out["rows"] = rows
    out["all_lower_le_U"] = all(r["lower_le_U"] for r in rows)
    return out


def check_bin_fidelity(seed=3, tau=1.0, n_events=200, trials=20000):
    rng = np.random.default_rng(seed)
    out = []
    for ratio in (0.1, 0.25, 0.5, 0.75, 1.0):
        delta, f = ratio * tau, []
        for _ in range(trials):
            true = rng.uniform(0, tau) + tau * np.arange(n_events) + rng.normal(0, 1e-4 * tau, n_events)
            regen = 0.5 * tau + tau * np.arange(n_events)
            edges = rng.uniform(0, delta)                       # arbitrary alignment of the bins
            ct = np.bincount(np.floor((true - edges) / delta).astype(int) + 2, minlength=int(n_events / ratio) + 8)
            cr = np.bincount(np.floor((regen - edges) / delta).astype(int) + 2, minlength=len(ct))
            m = min(len(ct), len(cr))
            f.append(2.0 * np.minimum(ct[:m], cr[:m]).sum() / (2 * n_events))
        out.append({"delta_over_tau": ratio, "fidelity": float(np.mean(f)), "sd": float(np.std(f))})
    return out


def check_moved(seed=5, trials=400_000):
    """Proposition 2: mean-squared timing error of moved events against the true events of another pixel."""
    rng = np.random.default_rng(seed)
    rows = []
    for n, tau_i, tau_j, sigma in ((1, 1.0, 1.0, 0.1), (3, 1.0, 1.0, 0.2), (3, 1.0, 1.3, 0.2), (5, 0.8, 1.0, 0.05)):
        k = np.arange(n)
        Ti = rng.uniform(0, tau_i, (trials, 1)) + k * tau_i + rng.normal(0, sigma, (trials, n))
        Tj = rng.uniform(0, tau_j, (trials, 1)) + k * tau_j + rng.normal(0, sigma, (trials, n))
        mse = float(np.mean((Ti - Tj) ** 2))
        formula = (2 * sigma ** 2 + (tau_i ** 2 + tau_j ** 2) / 12) + (4 * n * n - 1) / 12 * (tau_i - tau_j) ** 2
        rows.append({"n": n, "tau_i": tau_i, "tau_j": tau_j, "sigma": sigma, "simulated": mse, "formula": formula,
                     "relative_error": abs(mse - formula) / formula})
    return rows


if __name__ == "__main__":
    rng = np.random.default_rng(0)
    out = {"P1": {}}
    # the normal points against the motion, so that pixels cross the ramp from its low side
    cases = {"scale_and_rotation": (Flow(0.3, 0.2, (120.0, 30.0)), (-1.0, -0.3), 5.0),
             "fast_scale": (Flow(1.0, 0.0, (80.0, 0.0)), (-1.0, 0.0), 3.0),
             "oblique_edge": (Flow(0.3, -0.4, (60.0, 90.0)), (-1.0, -1.5), 0.0)}
    for name, (flow, nu, c0) in cases.items():
        pix = [(int(x), int(y)) for x, y in rng.integers(-150, 150, size=(1500, 2))]
        rows = check_passage(flow, nu, c0, pix, -1.0, 1.0, rng)
        out["P1"][name] = summarize(rows)
        print("P1", name, json.dumps(out["P1"][name]))
    out["P2"] = check_count()
    print("P2", json.dumps(out["P2"]))
    out["P3"] = check_transport()
    print("P3", json.dumps({k: v for k, v in out["P3"].items() if k != "rows"}))
    out["P4"] = check_bin_fidelity()
    print("P4", json.dumps(out["P4"]))
    out["P5"] = check_moved()
    print("P5", json.dumps(out["P5"]))
    if len(sys.argv) > 1:
        json.dump(out, open(sys.argv[1], "w"), indent=1)
