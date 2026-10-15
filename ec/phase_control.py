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
