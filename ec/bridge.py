"""From the regenerating decoder to moved key events, on the ramp model (directive 014).

Model (manuscript, Section II, one path). An edge passes the pixels x = 0, 1, 2, ... of a line at
``u`` pixels per unit time. Pixel x starts its passage at ``t_x = (x + phi) / u``, with an offset
``phi`` uniform on (0, 1) per path, and emits ``n`` events at

    T_{x,k} = t_x + A_x + (k - 1) tau_x + eps_{x,k},       k = 1 .. n,

with ``A_x`` uniform on (0, tau_x], ``eps`` independent N(0, sigma^2). Time is in units of the event
spacing ``tau`` of the reference pixel. Windows have length ``T0``; window m is [m T0, (m + 1) T0).
``D_A(x) = sigma^2 + tau_x^2 / 12``.

Reconstructions of the events of window m = 1 .. M_WIN:

regen    the decoder of Eq. (regen): ``t_x + (k - 1/2) tau_x`` for every pixel. It knows the edge and
         the motion (Theorem 2).
exact    the key events, the events with times in window 0, moved by the exact map: pixel x to
         x + d_m with ``d_m = u m T0``, time T to T + m T0. Only in the cases where ``u T0`` is a
         whole number of pixels.
round    as ``exact`` with ``d_m = round(u m T0)``, the nearest whole pixel (REMAKE moves by whole
         pixels, manuscript Eq. (map)).
fit      as ``round`` with ``d_m`` chosen by the objective of REMAKE: the number of moved key events
         that can be paired with true events of window m inside a voxel of the working grid
         (``FIT_DX`` pixels, ``T0 / 3``), over the candidates round(u m T0) + (-4 .. 4). Ties go to
         the middle candidate of the tied ones (the lower middle for an even number).

Two distortions.

timing   ``(1 / n) sum_k (T_{x,k} - That_{x,k})^2`` over the pixels x whose passage starts in window
         m and, for the moved reconstructions, whose source pixel x - d_m starts its passage in
         window 0, so that events are paired by index as in Proposition 2. Reported as a ratio to
         the mean ``D_A`` of the target pixels, with the prediction of Proposition 2 plus the
         squared timing bias ``((d_m - u m T0) / u)^2`` of a whole-pixel map.
voxel    the fidelity of Eq. (fid) on voxels of one pixel and ``dt``, summed over paths and windows
         before the ratio, as the paper sums over groups. Two event sets. ``pixel``: all n events of
         the pixels whose passage starts in window m, against all n events that the scheme gives
         them (for a moved scheme, those of the source pixels whose passage starts in window 0).
         ``window``: the events with times in window m, against every event that the scheme places
         in window m, as REMAKE is scored; a window boundary then cuts the trains of a source pixel
         and of its target pixel at different events.

Prediction for the voxel fidelity, one-pixel voxels, ``dt <= tau / 2``, no jitter, trains of n
events, bins at a uniform offset (derived in the manuscript, Section V-E):

    regen:  F = dt / tau,          moved, equal spacings:  F = dt / tau - dt^2 / (3 n tau^2).

Cases (``CASES``): ``translation`` (u T0 = 10 pixels, equal spacings), ``subpixel`` (u T0 = 10.4,
equal spacings) and ``scale`` (u T0 = 10, spacing growing by ``GROWTH`` per window,
``tau_x = 1 + GROWTH t_x / T0``). ``run`` returns one dictionary, which ``main`` writes as JSON.
"""
from __future__ import annotations

import json
import sys

import numpy as np

SEED = 20261014
FIT_DX = 2
FIT_CANDIDATES = np.arange(-4, 5)

REFERENCE = {
    "name": "reference", "n": 3, "sigma": 0.05, "T0": 33.333 / 3.2, "M_WIN": 10, "n_paths": 20000,
    "dt_over_tau": (0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.7, 1.0, 1.5, 2.0, 3.0),
    "cases": {"translation": {"px_per_window": 10.0, "growth": 0.0},
              "subpixel": {"px_per_window": 10.4, "growth": 0.0},
              "scale": {"px_per_window": 10.0, "growth": 0.05}},
}
SMOKE = dict(REFERENCE, name="smoke", n_paths=3000, dt_over_tau=(0.1, 0.25, 0.5, 1.0))


def simulate(case: dict, cfg: dict, rng) -> dict:
    """Event times of ``n_paths`` paths: arrays (paths, pixels, n), with the pixel start times."""
    n, T0, P = cfg["n"], cfg["T0"], cfg["n_paths"]
    u = case["px_per_window"] / T0
    n_px = int(np.ceil(u * (cfg["M_WIN"] + 1) * T0)) + 2
    x = np.arange(n_px)
    phi = rng.random((P, 1))
    t = (x[None, :] + phi) / u                                         # passage start
    tau = 1.0 + case["growth"] * t / T0
    A = rng.random((P, n_px)) * tau
    A = np.where(A == 0.0, tau, A)                                      # (0, tau]
    k = np.arange(n)
    T = t[..., None] + A[..., None] + k * tau[..., None] + cfg["sigma"] * rng.standard_normal((P, n_px, n))
    return {"u": u, "t": t, "tau": tau, "T": T, "x": x}


def _window(times, T0):
    return np.floor(times / T0).astype(np.int64)


def _voxel_fidelity(path_r, x_r, t_r, path_s, x_s, t_s, dx: int, dt: float, n_paths: int):
    """Sum over paths of min(c', c) on voxels (dx pixels, dt), and the two event counts."""
    def keys(p, x, t):
        return (p.astype(np.int64) * (1 << 40) + (x // dx).astype(np.int64) * (1 << 22)
                + np.floor(t / dt).astype(np.int64))
    kr, ks = keys(path_r, x_r, t_r), keys(path_s, x_s, t_s)
    ur, cr = np.unique(kr, return_counts=True)
    us, cs = np.unique(ks, return_counts=True)
    common, ir, i_s = np.intersect1d(ur, us, assume_unique=True, return_indices=True)
    match = np.minimum(cr[ir], cs[i_s])
    per_path = np.bincount((common >> 40).astype(np.int64), weights=match, minlength=n_paths)
    return per_path, len(kr), len(ks)


def _flat(sel, T, x_of):
    p, xi, k = np.nonzero(sel)
    return p, x_of[xi], T[p, xi, k]


def _key_events(sim, T0):
    sel = _window(sim["T"], T0) == 0
    return _flat(sel, sim["T"], sim["x"])


def _true_events(sim, m, T0):
    sel = _window(sim["T"], T0) == m
    return _flat(sel, sim["T"], sim["x"])


def _regen_events(sim, m, T0, n):
    k = np.arange(n)
    R = sim["t"][..., None] + (k + 0.5) * sim["tau"][..., None]
    sel = _window(R, T0) == m
    return _flat(sel, R, sim["x"])


def _fit_shift(key, true, m, d0, cfg, n_paths):
    """Per path, the candidate shift with most voxel pairs on the working grid; ties to the middle."""
    T0 = cfg["T0"]
    scores = np.empty((n_paths, len(FIT_CANDIDATES)))
    for c, off in enumerate(FIT_CANDIDATES):
        s, _, _ = _voxel_fidelity(key[0], key[1] + d0 + off, key[2] + m * T0, *true, FIT_DX, T0 / 3, n_paths)
        scores[:, c] = s
    best = scores.max(axis=1, keepdims=True)
    tied = scores == best
    idx = np.empty(n_paths, dtype=np.int64)
    for p in range(n_paths):
        w = np.flatnonzero(tied[p])
        idx[p] = w[(len(w) - 1) // 2]
    return d0 + FIT_CANDIDATES[idx]


def _timing(sim, m, shift, T0, n):
    """Index-paired timing error of moved events (shift per path) and of regenerated events."""
    t, tau, T = sim["t"], sim["tau"], sim["T"]
    P, n_px = t.shape
    win = _window(t, T0)
    tgt = win == m
    k = np.arange(n)
    regen = t[..., None] + (k + 0.5) * tau[..., None]
    e_regen = ((T - regen) ** 2).mean(axis=2)
    out = {"regen_sum": float(e_regen[tgt].sum()), "regen_DA": float((1.0 / 12 * tau[tgt] ** 2).sum()),
           "regen_pixels": int(tgt.sum())}
    res = {}
    for name, d in shift.items():
        d = np.broadcast_to(np.asarray(d, dtype=np.int64).reshape(-1, 1), (P, 1))
        src = np.arange(n_px)[None, :] - d
        ok = tgt & (src >= 0) & (src < n_px)
        srcc = np.clip(src, 0, n_px - 1)
        rows = np.arange(P)[:, None]
        ok &= win[rows, srcc] == 0
        moved = T[rows, srcc] + m * T0
        err = ((T - moved) ** 2).mean(axis=2)
        tau_s = tau[rows, srcc]
        da_i = tau ** 2 / 12
        da_j = tau_s ** 2 / 12
        bias = (t - t[rows, srcc] - m * T0)
        pred = da_i + da_j + 2 * 0.0 + (4 * n * n - 1) / 12 * (tau - tau_s) ** 2 + bias ** 2
        res[name] = {"sum": float(err[ok].sum()), "pred_sum_wo_jitter": float(pred[ok].sum()),
                     "DA_sum_wo_jitter": float(da_i[ok].sum()), "pixels": int(ok.sum()),
                     "bias2_sum": float((bias ** 2)[ok].sum())}
    out["moved"] = res
    return out


def run_case(case: dict, cfg: dict, rng) -> dict:
    n, T0, P, s2 = cfg["n"], cfg["T0"], cfg["n_paths"], cfg["sigma"] ** 2
    sim = simulate(case, cfg, rng)
    u = sim["u"]
    key = _key_events(sim, T0)
    dts = [float(v) for v in cfg["dt_over_tau"]]
    acc = {s: {"match": np.zeros(len(dts)), "n_rec": np.zeros(len(dts)), "n_true": np.zeros(len(dts))}
           for s in ("regen", "exact", "round", "fit")}
    acc_px = {s: {"match": np.zeros(len(dts)), "n_rec": np.zeros(len(dts)), "n_true": np.zeros(len(dts))}
              for s in ("regen", "exact", "round")}
    win_t = _window(sim["t"], T0)
    k_ = np.arange(n)
    timing = {s: {"sum": 0.0, "pred": 0.0, "DA": 0.0, "pixels": 0, "bias2": 0.0} for s in ("exact", "round", "fit")}
    reg = {"sum": 0.0, "DA": 0.0, "pixels": 0}
    per_m = []
    fit_dev = []
    for m in range(1, cfg["M_WIN"] + 1):
        true = _true_events(sim, m, T0)
        d_float = u * m * T0
        d_round = int(np.rint(d_float))
        shifts = {"round": d_round, "fit": _fit_shift(key, true, m, d_round, cfg, P)}
        if float(case["px_per_window"]).is_integer():
            shifts["exact"] = d_round
        fit_dev.append(np.abs(shifts["fit"] - d_float))
        tm = _timing(sim, m, shifts, T0, n)
        reg["sum"] += tm["regen_sum"]
        reg["DA"] += tm["regen_DA"] + s2 * tm["regen_pixels"]
        reg["pixels"] += tm["regen_pixels"]
        row = {"m": m, "d_float": d_float, "d_round": d_round,
               "regen_D_over_DA": tm["regen_sum"] / (tm["regen_DA"] + s2 * tm["regen_pixels"])}
        for name, v in tm["moved"].items():
            DA = v["DA_sum_wo_jitter"] + s2 * v["pixels"]
            pred = v["pred_sum_wo_jitter"] + 2 * s2 * v["pixels"]
            row[f"{name}_D_over_DA"] = v["sum"] / DA
            row[f"{name}_pred_over_DA"] = pred / DA
            t_ = timing[name]
            t_["sum"] += v["sum"]; t_["pred"] += pred; t_["DA"] += DA; t_["pixels"] += v["pixels"]
            t_["bias2"] += v["bias2_sum"]
        per_m.append(row)
        recs = {"regen": _regen_events(sim, m, T0, n)}
        for name, d in shifts.items():
            dd = np.asarray(d).reshape(-1)
            dk = dd[key[0]] if dd.size > 1 else dd[0]
            recs[name] = (key[0], key[1] + dk, key[2] + m * T0)
        for name, r in recs.items():
            for j, dt in enumerate(dts):
                mt, nr, nt = _voxel_fidelity(*r, *true, 1, dt, P)
                acc[name]["match"][j] += mt.sum(); acc[name]["n_rec"][j] += nr; acc[name]["n_true"][j] += nt
        tgt = np.broadcast_to((win_t == m)[..., None], sim["T"].shape)
        true_px = _flat(tgt, sim["T"], sim["x"])
        R = sim["t"][..., None] + (k_ + 0.5) * sim["tau"][..., None]
        recs_px = {"regen": _flat(tgt, R, sim["x"])}
        src = np.broadcast_to((win_t == 0)[..., None], sim["T"].shape)
        for name in ("exact", "round"):
            if name in shifts:
                p_, x_, t_ = _flat(src, sim["T"], sim["x"])
                recs_px[name] = (p_, x_ + shifts[name], t_ + m * T0)
        for name, r in recs_px.items():
            for j, dt in enumerate(dts):
                mt, nr, nt = _voxel_fidelity(*r, *true_px, 1, dt, P)
                acc_px[name]["match"][j] += mt.sum(); acc_px[name]["n_rec"][j] += nr; acc_px[name]["n_true"][j] += nt
    def ratio(a):
        return {name: [float(2 * v["match"][j] / (v["n_rec"][j] + v["n_true"][j])) for j in range(len(dts))]
                for name, v in a.items() if v["n_true"].sum() > 0 and v["n_rec"].sum() > 0}
    fid = {"window": ratio(acc), "pixel": ratio(acc_px)}
    theory = {"regen": [dt if dt <= 0.5 else None for dt in dts],
              "moved": [dt - dt * dt / (3 * n) if dt <= 0.5 else None for dt in dts]}
    timing_out = {name: {"D_over_DA": v["sum"] / v["DA"], "pred_over_DA": v["pred"] / v["DA"],
                         "bias2_over_DA": v["bias2"] / v["DA"], "pixels": v["pixels"]}
                  for name, v in timing.items() if v["pixels"] > 0}
    fd = np.concatenate(fit_dev)
    return {"case": case, "u_px_per_tau": u,
            "timing": dict(timing_out, regen={"D_over_DA": reg["sum"] / reg["DA"], "pixels": reg["pixels"]}),
            "per_m": per_m, "dt_over_tau": dts, "fidelity": fid, "fidelity_theory": theory,
            "fit_abs_dev_px": {"mean": float(fd.mean()), "share_at_nearest": float(np.mean(fd <= 0.5 + 1e-9))}}


def checks(out: dict, tol: dict) -> dict:
    tr, sp, sc = out["cases"]["translation"], out["cases"]["subpixel"], out["cases"]["scale"]
    c = {}
    c["regen_at_D_A"] = all(abs(v["timing"]["regen"]["D_over_DA"] - 1) < tol["rel"] for v in out["cases"].values())
    c["exact_equals_prop2"] = all(abs(v["timing"]["exact"]["D_over_DA"] / v["timing"]["exact"]["pred_over_DA"] - 1)
                                  < tol["rel"] for v in (tr, sc))
    c["exact_translation_is_2DA"] = abs(tr["timing"]["exact"]["D_over_DA"] - 2) < 2 * tol["rel"]
    c["round_equals_prop2_plus_bias"] = abs(sp["timing"]["round"]["D_over_DA"] / sp["timing"]["round"]["pred_over_DA"]
                                            - 1) < tol["rel"]
    ok = True
    for v in (tr, sp):
        for j, dt in enumerate(tr["dt_over_tau"]):
            if dt <= 0.5:
                ok &= abs(v["fidelity"]["pixel"]["regen"][j] - dt) < tol["fid"]
    for j, dt in enumerate(tr["dt_over_tau"]):
        if dt <= 0.5:
            ok &= abs(tr["fidelity"]["pixel"]["exact"][j] - tr["fidelity_theory"]["moved"][j]) < tol["fid"]
    c["voxel_fidelity_matches_prediction"] = bool(ok)
    return c


def run(cfg: dict) -> dict:
    rng = np.random.default_rng(SEED)
    out = {"config": {k: (list(v) if isinstance(v, tuple) else v) for k, v in cfg.items()},
           "cases": {name: run_case(case, cfg, rng) for name, case in cfg["cases"].items()}}
    tol = {"rel": 0.03, "fid": 0.02} if cfg["name"] == "reference" else {"rel": 0.06, "fid": 0.03}
    out["tolerances"] = tol
    out["checks"] = checks(out, tol)
    return out


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2 or argv[0] not in ("reference", "smoke"):
        sys.exit("usage: python3 -m ec.bridge reference|smoke OUT.json")
    import pathlib
    pathlib.Path(argv[1]).parent.mkdir(parents=True, exist_ok=True)
    out = run(REFERENCE if argv[0] == "reference" else SMOKE)
    pathlib.Path(argv[1]).write_text(json.dumps(out, indent=1, default=float) + "\n")
    print(json.dumps(out["checks"]))
    return 0 if all(out["checks"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
