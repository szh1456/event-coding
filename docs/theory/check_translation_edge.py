#!/usr/bin/env python3
"""Numerical checks for docs/theory/translation_edge.tex. Synthetic only; runs in under a minute.

N1  Lemma 1: a brute-force send-on-delta pixel (time stepping, reference update) against Eq. (3)
    for a ramp, against the level-crossing times for a smooth edge with non-integer V/C, and the
    firing rule of Remark 2(i) against the definition on random zigzag signals.
N2  Theorem 1: Kozachenko-Leonenko estimate of the differential entropy of the event-time vector
    against the closed form ((n-1)/2) ln(2 pi e sigma^2) + eta(sqrt(n) tau_phi, sigma).
N3  Theorem 2: three operational coders (phase-free, phase-only, transform) against the lower and
    upper bounds on the rate-distortion function.

Usage: python3 check_translation_edge.py [out.json]
"""
import json
import math
import sys

import numpy as np
from scipy.integrate import quad
from scipy.spatial import cKDTree
from scipy.special import digamma, gammaln
from scipy.stats import norm

LN2 = math.log(2.0)


# ----------------------------------------------------------------------------- shared closed forms
def eta(w: float, sigma: float) -> float:
    """Differential entropy (nats) of U + Z, U uniform on (0, w), Z normal with standard deviation sigma."""
    def pdf(x):
        return (norm.cdf(x / sigma) - norm.cdf((x - w) / sigma)) / w

    def integrand(x):
        f = pdf(x)
        return -f * math.log(f) if f > 1e-300 else 0.0

    lo, hi = -10 * sigma, w + 10 * sigma
    pts = [0.0, w] if w > 0 else None
    val, _ = quad(integrand, lo, hi, points=pts, limit=400)
    return val


def bounds(D, n, sigma, tau):
    """Lower bound L(D), upper bound U(D) (nats per pixel pass) and the gap Gamma of Theorem 2."""
    sx2 = n * tau ** 2 / 12 + sigma ** 2
    e = eta(math.sqrt(n) * tau, sigma)
    gamma = 0.5 * math.log(2 * math.pi * math.e * sx2) - e
    DA = sigma ** 2 + tau ** 2 / 12
    if D >= DA:
        return 0.0, 0.0, gamma, DA
    if D <= sigma ** 2:
        # Eq. (9): R_1 is known exactly, h(T_i) - (n/2) ln(2 pi e D).
        hT = (n - 1) / 2 * math.log(2 * math.pi * math.e * sigma ** 2) + e
        R = hT - n / 2 * math.log(2 * math.pi * math.e * D)
        return R, R, gamma, DA
    dx = n * D - (n - 1) * sigma ** 2
    U = 0.5 * math.log(sx2 / dx)
    L = max(0.0, U - gamma)
    return L, U, gamma, DA


# ----------------------------------------------------------------------------- N1
def brute_force_pixel(profile, v, i, r0, C, t_end, dt):
    """Send-on-delta by time stepping: event when |s - r| >= C, then r <- r + p C."""
    t = np.arange(0.0, t_end, dt)
    s = profile(v * t - i)
    events, r = [], r0
    for k in range(len(t)):
        while abs(s[k] - r) >= C:
            p = 1 if s[k] > r else -1
            r += p * C
            events.append((t[k], p))
    return events


def zigzag_events_by_definition(turns, r0, C):
    """Exact events of (A1) on a piecewise-linear signal through the points `turns` (levels only)."""
    ev, r = [], r0
    for a, b in zip(turns[:-1], turns[1:]):
        step = 1 if b > a else -1
        while (b - r) * step >= C:           # the leg reaches r + step*C
            r += step * C
            ev.append((r, step))
    return ev


def zigzag_events_by_rule(turns, r0, C):
    """Rule of Remark 2(i): a lattice level fires when crossed unless it was the last level crossed."""
    ev, last = [], r0
    for a, b in zip(turns[:-1], turns[1:]):
        lo, hi = (a, b) if a < b else (b, a)
        k0 = math.ceil((lo - r0) / C)
        levels = [r0 + k * C for k in range(k0, math.floor((hi - r0) / C) + 1)]
        if b < a:
            levels = levels[::-1]
        for lev in levels:
            if abs(lev - last) > 1e-9:
                ev.append((lev, 1 if b > a else -1))
            last = lev
    return ev


def check_lemma1(seed=0):
    rng = np.random.default_rng(seed)
    C, v, dt = 0.25, 200.0, 2e-6
    out = {}
    # (a) ramp of height nC under (A2), (A3): exactly n events at the times of Eq. (3)
    n, gamma = 4, 0.5
    w = n * C / gamma
    ramp = lambda u: np.clip(gamma * u, 0.0, n * C)
    tphi = C / (gamma * v)
    worst = 0.0
    for i in range(8):
        a = rng.uniform(0, C)
        ev = brute_force_pixel(ramp, v, i + 2, a - C, C, 0.2, dt)
        assert len(ev) == n and all(p == 1 for _, p in ev)
        pred = (i + 2) / v + a / (gamma * v) + tphi * np.arange(n)
        worst = max(worst, float(np.max(np.abs(np.array([t for t, _ in ev]) - pred))))
    out["ramp"] = {"n": n, "max_abs_time_error_s": worst, "time_step_s": dt}
    # (b) smooth monotone edge with non-integer V/C: level-crossing times and the two possible counts
    V, wd = 3.2 * C, 1.5
    g = lambda u: 0.5 * V * (1 + np.tanh(u / wd))
    ginv = lambda lev: wd * np.arctanh(2 * lev / V - 1)
    worst, counts = 0.0, []
    for i in range(8):
        r0 = -rng.uniform(0, C)
        ev = brute_force_pixel(g, v, i + 8, r0, C, 0.2, dt)
        levels = r0 + C + C * np.arange(0, 8)
        levels = levels[levels < V]
        t_pred = (i + 8 + ginv(levels)) / v
        assert len(ev) == len(levels) and all(p == 1 for _, p in ev)
        worst = max(worst, float(np.max(np.abs(np.array([t for t, _ in ev]) - t_pred))))
        counts.append(len(ev))
    out["tanh_edge"] = {"max_abs_time_error_s": worst, "time_step_s": dt, "counts": counts, "V_over_C": V / C}
    # (c) random zigzags: the definition (A1) against the rule of Remark 2(i)
    mism, n_ev, n_rev, n_skip = 0, 0, 0, 0
    for _ in range(20000):
        r0 = -rng.uniform(0, 1.0)
        turns, x, sgn = [0.0], 0.0, (1 if rng.random() < 0.5 else -1)
        for _ in range(int(rng.integers(2, 9))):
            x += sgn * rng.uniform(0.0, 3.5)
            turns.append(x)
            sgn = -sgn
        d = zigzag_events_by_definition(turns, r0, 1.0)
        r = zigzag_events_by_rule(turns, r0, 1.0)
        ok = len(d) == len(r) and all(abs(a[0] - b[0]) < 1e-9 and a[1] == b[1] for a, b in zip(d, r))
        mism += (not ok)
        n_ev += len(d)
        n_rev += len(turns) - 2
    out["zigzag"] = {"profiles": 20000, "rule_mismatches": int(mism), "events": int(n_ev), "reversals": int(n_rev)}
    return out


# ----------------------------------------------------------------------------- N2
def kl_entropy(x: np.ndarray, k: int = 4) -> float:
    """Kozachenko-Leonenko k-nearest-neighbor estimate of differential entropy, in nats."""
    m, d = x.shape
    r = cKDTree(x).query(x, k=k + 1)[0][:, k]
    log_vd = (d / 2) * math.log(math.pi) - gammaln(d / 2 + 1)
    return float(digamma(m) - digamma(k) + log_vd + d * np.mean(np.log(r)))


def sample_times(m, n, sigma, tau, rng):
    A = rng.uniform(0, tau, m)[:, None]
    return A + tau * np.arange(n)[None, :] + rng.normal(0, sigma, (m, n))


def check_theorem1(seed=1):
    rng = np.random.default_rng(seed)
    rows = []
    for n, sigma, tau in ((3, 0.1, 2.0), (3, 0.6, 2.0), (3, 3.0, 2.0), (5, 0.3, 2.0), (2, 0.2, 1.0)):
        T = sample_times(200_000, n, sigma, tau, rng)
        est = kl_entropy(T)
        closed = (n - 1) / 2 * math.log(2 * math.pi * math.e * sigma ** 2) + eta(math.sqrt(n) * tau, sigma)
        small = (n - 1) * math.log(sigma * math.sqrt(2 * math.pi * math.e)) + math.log(math.sqrt(n) * tau)
        rows.append({"n": n, "sigma_over_tau": sigma / tau, "kl_estimate_nats": est, "closed_form_nats": closed,
                     "difference_nats": est - closed, "small_jitter_form_nats": small})
    return rows


# ----------------------------------------------------------------------------- N3
def index_entropy(idx: np.ndarray) -> float:
    _, c = np.unique(idx, return_counts=True)
    q = c / c.sum()
    return float(-(q * np.log(q)).sum())


def check_theorem2(seed=2, n=3, sigma=0.1, tau=5.0, m=400_000):
    """Times in milliseconds. Returns bounds and operating points in bits per event."""
    rng = np.random.default_rng(seed)
    T = sample_times(m, n, sigma, tau, rng)
    c = tau * np.arange(n)[None, :]                       # known to the decoder (g and v known)
    R = T - c                                             # residuals: A + eps
    e1 = np.ones(n) / math.sqrt(n)
    basis = np.linalg.qr(np.column_stack([e1, rng.normal(size=(n, n - 1))]))[0]
    basis[:, 0] = e1 * np.sign(basis[0, 0] * e1[0])
    Z = R @ basis                                         # Z[:, 0] = sqrt(n) A + noise, others pure noise
    X, W = Z[:, 0], Z[:, 1:]
    pts = []
    # coder A: phase-free regeneration at the mean phase
    rec = c + tau / 2
    pts.append({"coder": "phase-free", "rate_nats": 0.0, "D": float(np.mean((T - rec) ** 2))})
    # coder B: quantize the mean component only (entropy-coded uniform quantizer)
    for q in (4.0, 2.0, 1.0, 0.5, 0.25, 0.12):
        iq = np.round(X / q)
        Zr = np.column_stack([iq * q, np.zeros((m, n - 1))])
        rec = Zr @ basis.T + c
        pts.append({"coder": "phase-only", "step": q, "rate_nats": index_entropy(iq),
                    "D": float(np.mean((T - rec) ** 2))})
    # coder C: quantize every component with one step
    for q in (0.2, 0.1, 0.05, 0.02, 0.01):
        iq = np.round(Z / q)
        rate = index_entropy(iq[:, 0]) + sum(index_entropy(iq[:, j]) for j in range(1, n))
        rec = (iq * q) @ basis.T + c
        pts.append({"coder": "transform", "step": q, "rate_nats": rate, "D": float(np.mean((T - rec) ** 2))})
    out = []
    for p in pts:
        L, U, gamma, DA = bounds(p["D"], n, sigma, tau)
        out.append({**p, "rms_error_ms": math.sqrt(p["D"]), "rate_bits_per_event": p["rate_nats"] / LN2 / n,
                    "L_bits_per_event": L / LN2 / n, "U_bits_per_event": U / LN2 / n,
                    "excess_over_L_bits_per_pass": (p["rate_nats"] - L) / LN2})
    L, U, gamma, DA = bounds(sigma ** 2 / 4, n, sigma, tau)
    curve = []
    for rms in np.geomspace(0.005, 3.0, 25):
        Lc, Uc, _, _ = bounds(rms ** 2, n, sigma, tau)
        curve.append({"rms_error_ms": float(rms), "L_bits_per_event": Lc / LN2 / n, "U_bits_per_event": Uc / LN2 / n})
    return {"n": n, "sigma_ms": sigma, "tau_phi_ms": tau, "gamma_bits_per_pass": gamma / LN2,
            "D_A_rms_ms": math.sqrt(DA), "operating_points": out, "bound_curve": curve}


if __name__ == "__main__":
    res = {"N1_lemma1": check_lemma1(), "N2_theorem1": check_theorem1(), "N3_theorem2": check_theorem2()}
    print(json.dumps(res["N1_lemma1"], indent=1))
    for r in res["N2_theorem1"]:
        print("N2", {k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()})
    t2 = res["N3_theorem2"]
    print("N3 gamma bits/pass", round(t2["gamma_bits_per_pass"], 4), "rms at D_A (ms)", round(t2["D_A_rms_ms"], 4))
    for p in t2["operating_points"]:
        print("N3 %-10s rms=%.4f ms  rate=%.3f  L=%.3f  U=%.3f  bits/event   excess over L = %.3f bits/pass"
              % (p["coder"], p["rms_error_ms"], p["rate_bits_per_event"], p["L_bits_per_event"],
                 p["U_bits_per_event"], p["excess_over_L_bits_per_pass"]))
    if len(sys.argv) > 1:
        json.dump(res, open(sys.argv[1], "w"), indent=1)
