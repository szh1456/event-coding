# Directive 014. From the theorem to REMAKE, and figures that show the trade-off

| | |
|---|---|
| track | `bridge`, short name `br` |
| population | none for Section 4; the committed `results/bk/per_recording.json` and `results/dt/per_recording.json` for Section 5; the three recordings and kept streams that directive 013 selected for Fig. 5, for Section 6 |
| results directories | `results/br/` and `results/paper/` |
| report | `docs/directives/reports/014.md` |
| runs after | directive 013 (`DONE`, report at `76b182b`) |

## 1. Why

A review of the manuscript at PR #19 found four gaps, which this directive closes.

1. Fig. 2 checks Theorem 2 on the model. No figure shows how the regenerating
   decoder of the theorem becomes REMAKE. Between them lie four steps: moving
   key events instead of regenerating them (Proposition 2), moving them by
   whole pixels, scoring whole windows, and fitting the map. Section 4
   measures each step on the ramp model.
2. Fig. 3 gives one operating point per group length. The trade-off between
   bits and fidelity over the threshold is not drawn. Section 5 computes it.
3. Fig. 4 shows whole windows. It cannot show timing. Section 6 adds a zoomed
   square in the three time bins of the window.
4. The top of Fig. 5 shows the fidelity against the time bin. The claim is that
   the gain shrinks with it. Section 7 adds the gain on the same grids.

## 2. Disclosure

The director derived the voxel fidelity of moved events on one-pixel voxels
(Section 4) and checked it with a seconds-long simulation of single trains.
It ran `ec.bridge` in its smoke configuration and drew every new figure from
the smoke output and from stand-in data, to check the layout. No smoke
number enters the paper. The director read no recording and computed nothing
from a committed per-recording file.

## 3. Author decisions

**D-014-1, default: authorized.** The executor adds `ec/bridge.py`,
`tests/test_bridge_gate.py` and the new `scripts/paper_figures.py` with the
content of Appendices A, B and C, unchanged.

**D-014-2, default: authorized.** The reads of Section 6: the three
recordings and the three kept streams of `results/paper/recon_selection.json`
at `76b182b`, as D-011-2 allowed them. No group is evaluated again, and the
selection is not changed.

## 4. The bridge on the model

```
python3 -m ec.bridge reference results/br/bridge.json
```

Every entry of `checks` must be true. The module docstring defines the cases,
the reconstructions and the two fidelities.

**Predictions.** These follow from the model, not from a measurement.

| quantity | predicted |
|---|---|
| timing error of `regen`, every case | `D_A` |
| `exact`, `translation` | `2 D_A` (Proposition 2) |
| `exact`, `scale` | Proposition 2 with the spacings of the two pixels |
| `round`, `subpixel` | Proposition 2 plus the squared timing bias of the whole-pixel map |
| fidelity `pixel`, `dt <= tau / 2` | `regen`: `dt / tau`; `exact`: `dt / tau - dt^2 / (3 n tau^2)` |
| fidelity `window` against `pixel`, `exact` | lower, by the trains that a window boundary cuts |

## 5. The trade-off table

Write `scripts/pf_tradeoff.py` (the executor's file). For each stratum:

- `day` and `night`: the reporting recordings of eTraM that enter the tables
  of report 007, from `results/bk/per_recording.json`;
- `all`: the 36 reporting sequences of DSEC that enter the tables of report
  013, from `results/dt/per_recording.json`.

For each K in 2, 4, 8 and 11, and each configuration `B20_rho0.0625`,
`B20_rho0.125`, `B20_rho0.25`, `B20_rho0.5` and `B20_rho1.0`, compute per
recording `s = ec.blockcodec.summarize(sum, config, "affine", "Q", K)`. Then
take the medians over recordings of:

- `F = s["F"]`;
- `bits_pct = 100 s["bits"] / s["bits_direct"]`;
- `sub_pct = 100 s["bits_base"] / s["bits_direct"]`;
- `gain = s["gain"]`.

Write them to `results/paper/tradeoff.json` with the layout
`{"strata": {stratum: {"K4": {config: {"F", "bits_pct", "sub_pct", "gain", "n_recordings"}}}}}`.

**Check.** For every stratum, `F` and `gain` of `B20_rho1.0` equal the medians
of `tables/2_headline/Q/<stratum>/<K>/affine` of the report of their dataset,
for the four K. For K = 4 and K = 11 and every configuration, they also equal
those of `tables/4_thresholds`.

## 6. Time slices of Fig. 4

Use the group of each stratum in `results/paper/recon_selection.json` at
`76b182b`, window m = 4, decoded from its stream as in directive 011,
Section 5.

1. **Zoom.** Consider the squares of side 80 px whose corners lie on
   multiples of 20 px and which lie inside the crop of that stratum. Take the
   one that holds the most true events of window m. On a tie, take the
   smaller row, then the smaller column.
2. **Thirds.** An event of window m belongs to third
   `b = ec.blockcodec.time_bin(t_rel, 3)`, with `t_rel` its time relative to
   the start of window m. A rebuilt event uses its decoded time.
3. **Images.** For b = 0, 1 and 2, the signed count per pixel (positive
   polarity minus negative) of the true events and of the rebuilt events of
   third b inside the square. Add them to `results/paper/recon_images.npz` as
   `<stratum>_zoom_true_b<b>` and `<stratum>_zoom_rec_b<b>`, arrays of 80 x 80
   (rows are y). Keep the nine existing arrays unchanged.
4. **Numbers.** Add to the entry of each stratum in `recon_selection.json`:
   - `zoom`, as `[x0, y0, 80, 80]`;
   - `zoom_n_events`, as `{"true": [3 counts], "rec": [3 counts]}`;
   - `zoom_F_bins`, the fidelity of Eq. (fid) of each third. It is computed
     inside the square on voxels of 2 x 2 px and one polarity.
5. **Check.** For each stratum, the zoom counts summed over the three thirds
   equal the number of true and rebuilt events of window m in the square.
   Count these directly from the decoded window.

Before writing, copy `results/paper/` as it is at `76b182b`, except `v011/`
and `v012/`, to `results/paper/v013/`.

## 7. Figures

```
python3 scripts/paper_figures.py --etram results/bk/report.json --dsec results/dt/report.json \
    --out results/paper --recon results/paper --tradeoff results/paper/tradeoff.json \
    --bridge results/br/bridge.json
```

## 8. Acceptance checks

1. The three files have the SHA-256 of Section 10, and
   `python3 -m pytest -q -p no:anyio` passes with no skipped test.
2. `python3 -m ec.bridge reference` exits 0, and every entry of `checks` is
   true.
3. The check of Section 5 holds for every stratum and K.
4. The check of Section 6, step 5, holds for every stratum, and the nine
   existing arrays of the npz equal those at `76b182b`.
5. `results/paper/v013/` equals `results/paper/` at `76b182b`, without the two
   older version folders.
6. `fig_bits_all.json` and `fig_recon.json` equal those at `76b182b`. The
   fidelity entries of `fig_limits.json` equal those at `76b182b`.
7. Nothing under `results/bk/`, `results/ds/` or `results/dt/` changed, and
   no recording other than the three of Section 6 was opened.

## 9. Cost

The smoke configuration took about 20 s on the director's machine, and the
reference takes about seven times as many paths. Section 5 reads two
committed files. Section 6 reads three recordings and decodes three streams.

## 10. Files

SHA-256 of the file content, which is the text between the fence lines of its
appendix, ending in one newline.

| file | SHA-256 |
|---|---|
| `ec/bridge.py` | `2012997de933350f3137052581ee07ead793f5dcb8ce286ac78bf48019363950` |
| `tests/test_bridge_gate.py` | `4c464385e674bf0c6ee71f1a9c4d7cf7cbda84a099d159fd42345214b2e9197f` |
| `scripts/paper_figures.py` | `7600a302e478bbf3bff287793343478a2064e4d6a6930d1917f71cd1e3e0b891` |

## 11. The report

The header and the checks. Then:

- the table of `results/br/bridge.json`: timing error over `D_A`, measured and
  predicted, per case and reconstruction;
- the two fidelities at `dt / tau` = 0.25, 0.5 and 1;
- the share of fitted shifts at the nearest whole pixel;
- `tradeoff.json` at K = 4 and 11 for the five thresholds;
- the zoom squares, with their counts and their fidelities.

## Appendix A. `ec/bridge.py`

Normative. The executor commits this file unchanged.

```python
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
```

## Appendix B. `tests/test_bridge_gate.py`

Normative. The executor commits this file unchanged.

```python
"""Gate for directive 014: moved key events against regenerated events on the ramp model.

The configuration ``ec.bridge.SMOKE`` and its tolerances are fixed by the director. The figure
comes from ``ec.bridge.REFERENCE``, which this file does not run.
"""
import numpy as np

from ec import bridge


def test_voxel_fidelity_counts_pairs_inside_a_voxel():
    p = np.zeros(3, dtype=np.int64)
    m, nr, nt = bridge._voxel_fidelity(p, np.array([0, 0, 5]), np.array([0.1, 0.2, 3.0]),
                                       p, np.array([0, 1, 5]), np.array([0.15, 0.1, 4.1]), 1, 1.0, 1)
    assert m.tolist() == [1.0] and nr == 3 and nt == 3          # (0, bin 0) pairs once; (5, bins 3 and 4) does not


def test_smoke_runs_and_every_check_holds():
    out = bridge.run(bridge.SMOKE)
    assert set(out["cases"]) == {"translation", "subpixel", "scale"}
    assert "exact" not in out["cases"]["subpixel"]["timing"]
    assert all(out["checks"].values()), out["checks"]
    sp = out["cases"]["subpixel"]
    assert sp["timing"]["round"]["D_over_DA"] > sp["timing"]["regen"]["D_over_DA"] + 1.0
```

## Appendix C. `scripts/paper_figures.py`

Normative. The executor commits this file unchanged.

```python
"""Directives 010 to 014: the figures of the paper, drawn from committed files.

  python3 scripts/paper_figures.py --etram ETRAM_REPORT.json --dsec DSEC_REPORT.json --out OUTDIR
                                   [--recon RECON_DIR] [--tradeoff TRADEOFF.json] [--bridge BRIDGE.json]

ETRAM_REPORT is ``results/bk/report.json`` (directive 007), DSEC_REPORT is ``results/dt/report.json``
(directive 013). Three strata are drawn: ``day`` and ``night`` of the first and ``all`` of the second.
Values are medians over recordings, frozen configuration. Nothing is computed here but percentages.
Each figure is written as PDF and PNG, with its plotted values as JSON.

fig_bits_all   Bits against fidelity at one operating point per K, matched coder, working grid, from
               ``tables/2_headline/Q``. One panel per stratum and one row per group length K. In each
               row, at the fidelity F of REMAKE, a circle marks its bits and a ring the bits of the
               cheapest subset scheme at that fidelity (``bits_base``), both as a percentage of the bits
               of sending every event (``bits_direct``). The label is the gain G of the report.

fig_tradeoff   Drawn when TRADEOFF.json is given (directive 014, Section 6). One panel per stratum:
               bits as a percentage of the bits of every event against F, for K = 4 and K = 11, over
               the five thresholds. Solid with filled markers: REMAKE. Dashed with open markers: the
               cheapest subset scheme at the fidelity of each point. The threshold rises to the left.

fig_limits     Top: fidelity of a group of four windows against the time bin of the receiver grid,
               2 px blocks, affine map, from ``tables/6_grids`` (cells ``s2_k1``, ``s2_k3``,
               ``s2_k8``, ``s2_k32``, a window being 33,333 us). Middle: the gain of the transport coder
               on the same grids, from the same cells. Bottom: fidelity of window m against m on the
               working grid, from ``tables/5_windows``, affine map (solid) and translation (dashed).

fig_recon      Drawn when RECON_DIR holds ``recon_images.npz`` and ``recon_selection.json``
               (directives 011 to 013). One row per stratum, three columns: the key events that are
               sent, the true events of window m, and the events that the receiver rebuilds for window
               m from the stream. Each image is the signed event count per pixel, positive polarity
               minus negative, clipped to [-2, 2].

fig_slices     Drawn when the npz also holds the zoom images of directive 014, Section 7. One row per
               stratum, six columns: the true and the rebuilt events of the zoom square in each third of
               window m, signed counts per pixel clipped to [-1, 1], with the fidelity of that third on
               the working grid inside the square.

fig_bridge     Drawn when BRIDGE.json is given (``ec.bridge``, directive 014). Top: timing error per
               event over D_A against the window m, for the regenerated events, moved events under the
               exact map (equal and growing spacings) and under the nearest whole-pixel map, with the
               prediction of Proposition 2 as open markers. Bottom: fidelity on one-pixel voxels
               against the bin over the event spacing, for the regenerated events, the moved events
               (exact map, and nearest whole-pixel map), and the moved events of the fitted map scored
               on whole windows as REMAKE is, with the predictions for bins up to half the spacing.
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
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.lines import Line2D

BLUE, ORANGE, AQUA = "#2a78d6", "#d6542a", "#1baf7a"      # checked together for color-vision separation
PURPLE = "#8a5cc2"
INK, MUTED = "#0b0b0b", "#6f6e69"
GROUPS = ("K2", "K4", "K8", "K11")
T0_MS = 33.333
BINS = (("s2_k32", T0_MS / 32), ("s2_k8", T0_MS / 8), ("s2_k3", T0_MS / 3), ("s2_k1", T0_MS))
STRATA = (("eTraM, day", 0, "day", BLUE, "o"), ("eTraM, night", 0, "night", AQUA, "^"), ("DSEC", 1, "all", ORANGE, "s"))
COLUMNS = (("key", "sent: key events"), ("true", "true, window $m$"), ("rec", "rebuilt, window $m$"))
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


def fig_bits_all(reports, out):
    plotted = {}
    fig, axes = plt.subplots(len(STRATA), 1, figsize=(3.45, 0.45 + 1.2 * len(STRATA)), sharex=True,
                             gridspec_kw={"hspace": 0.32})
    for ax, (label, which, name, _, _) in zip(axes, STRATA):
        rows = reports[which]["tables"]["2_headline"]["Q"][name]
        med = lambda K, key: rows[K]["affine"][key]["median"]
        plotted[label] = {}
        for r, K in enumerate(GROUPS):
            y = len(GROUPS) - 1 - r
            direct = med(K, "bits_direct")
            codec, base = 100.0 * med(K, "bits") / direct, 100.0 * med(K, "bits_base") / direct
            F, G = med(K, "F"), med(K, "gain")
            ax.plot([codec, base], [y, y], color=MUTED, lw=1.0, zorder=1)
            ax.plot(base, y, "o", ms=4.6, mfc="white", mec=INK, mew=0.9, zorder=2)
            ax.plot(codec, y, "o", ms=4.6, color=BLUE, mec="white", mew=0.5, zorder=3)
            ax.text(max(codec, base) + 2.5, y, f"$\\times{G:.2f}$", va="center", ha="left", fontsize=7, color=INK)
            plotted[label][K] = {"F": F, "codec_percent": codec, "subset_percent": base, "gain": G}
        ax.set_yticks(range(len(GROUPS)))
        ax.set_yticklabels([f"$K={K[1:]}$, $F={plotted[label][K]['F']:.2f}$" for K in GROUPS][::-1], fontsize=7)
        ax.set_ylim(-0.6, len(GROUPS) - 0.4)
        ax.set_xlim(0, 100)
        ax.set_title(label, fontsize=7.5, loc="left", pad=2, color=INK)
        _clean(ax)
        ax.tick_params(axis="y", length=0)
        ax.grid(axis="x", color="#e4e3dd", lw=0.5, zorder=0)
    axes[-1].set_xlabel("bits sent, % of sending every event", labelpad=1)
    axes[0].legend(handles=[Line2D([], [], ls="", marker="o", ms=4.6, color=BLUE, mec="white", label="REMAKE"),
                            Line2D([], [], ls="", marker="o", ms=4.6, mfc="white", mec=INK, mew=0.9,
                                   label="cheapest subset scheme, same $F$")],
                   loc="upper center", bbox_to_anchor=(0.5, 1.42), ncol=2, frameon=False, fontsize=6.5,
                   handletextpad=0.3, columnspacing=1.2)
    _finish(fig, out, plotted)


def fig_limits(reports, out):
    plotted = {"bins_ms": [b for _, b in BINS], "group_fidelity_K4": {}, "gain_T_K4": {}, "window_fidelity": {}}
    fig, (ax, gx, bx) = plt.subplots(3, 1, figsize=(3.45, 5.7), gridspec_kw={"hspace": 0.5})
    for label, which, name, color, marker in STRATA:
        tables = reports[which]["tables"]
        F = [tables["6_grids"][name][cell]["F"]["median"] for cell, _ in BINS]
        ax.plot([b for _, b in BINS], F, "-", marker=marker, color=color, lw=0.9, ms=3.8, mec="white", mew=0.5, label=label)
        plotted["group_fidelity_K4"][label] = F
        Gt = [tables["6_grids"][name][cell]["gain"]["median"] for cell, _ in BINS]
        gx.plot([b for _, b in BINS], Gt, "-", marker=marker, color=color, lw=0.9, ms=3.8, mec="white", mew=0.5)
        plotted["gain_T_K4"][label] = Gt
        w = tables["5_windows"][name]
        m = list(range(1, 11))
        aff = [w[f"affine_s2_k3_m{j}"]["median"] for j in m]
        tra = [w[f"translation_s2_k3_m{j}"]["median"] for j in m]
        bx.plot(m, tra, color=color, lw=0.8, ls=(0, (3, 2)))
        bx.plot(m, aff, "-", marker=marker, color=color, lw=0.9, ms=3.4, mec="white", mew=0.5)
        plotted["window_fidelity"][label] = {"affine": aff, "translation": tra}
    for a in (ax, gx):
        a.set_xscale("log")
        a.set_xticks([b for _, b in BINS])
        a.set_xticklabels(["1.04", "4.17", "11.1", "33.3"])
        a.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
        a.minorticks_off()
        a.set_xlabel("time bin of the receiver grid (ms)", labelpad=1)
    ax.set_ylabel("fidelity, $K=4$", labelpad=2)
    ax.set_ylim(0.4, 0.8)
    gx.set_ylabel("gain $G_{\\mathrm{T}}$, $K=4$", labelpad=2)
    gx.axhline(1.0, color=MUTED, lw=0.5, ls=(0, (2, 2)), zorder=0)
    gx.set_ylim(0, 3.4)
    ax.legend(loc="lower right", frameon=False, fontsize=6.5, handlelength=1.8, borderaxespad=0.2, labelspacing=0.25)
    bx.set_xticks(range(1, 11))
    bx.set_xlabel("windows since the key window, $m$", labelpad=1)
    bx.set_ylabel("fidelity of window $m$", labelpad=2)
    bx.set_ylim(0.4, 0.7)
    bx.legend(handles=[Line2D([], [], color=INK, lw=0.9, label="affine map"),
                       Line2D([], [], color=INK, lw=0.8, ls=(0, (3, 2)), label="translation")],
              loc="upper right", frameon=False, fontsize=6.5, handlelength=1.8, borderaxespad=0.2, labelspacing=0.25)
    for a in (ax, gx, bx):
        _clean(a)
    _finish(fig, out, plotted)


def fig_recon(recon_dir, out):
    images = np.load(Path(recon_dir) / "recon_images.npz")
    sel = json.loads((Path(recon_dir) / "recon_selection.json").read_text())
    cmap = LinearSegmentedColormap.from_list("signed", [BLUE, "#ffffff", ORANGE])
    fig, axes = plt.subplots(len(STRATA), len(COLUMNS), figsize=(7.0, 0.3 + 1.45 * len(STRATA)),
                             gridspec_kw={"hspace": 0.08, "wspace": 0.04})
    plotted = {}
    for r, (label, _, name, _, _) in enumerate(STRATA):
        s = sel[name]
        plotted[label] = {k: s[k] for k in ("recording", "w", "m", "crop", "n_events", "F_window", "F_window_median")}
        for c, (panel, title) in enumerate(COLUMNS):
            ax = axes[r, c]
            img = np.clip(images[f"{name}_{panel}"], -2, 2)
            ax.imshow(img, cmap=cmap, vmin=-2, vmax=2, interpolation="nearest", aspect="equal")
            ax.set_xticks([]); ax.set_yticks([])
            for sp in ax.spines.values():
                sp.set_linewidth(0.4); sp.set_color(MUTED)
            ax.text(0.02, 0.03, f"{s['n_events'][panel]:,} events", transform=ax.transAxes, fontsize=6, color=INK,
                    ha="left", va="bottom", bbox=dict(facecolor="white", edgecolor="none", pad=0.8, alpha=0.8))
            if panel == "rec":
                ax.text(0.98, 0.03, f"$F={s['F_window']:.2f}$", transform=ax.transAxes, fontsize=6.5, color=INK,
                        ha="right", va="bottom", bbox=dict(facecolor="white", edgecolor="none", pad=0.8, alpha=0.8))
            if r == 0:
                ax.set_title(title.replace("$m$", f"$m={s['m']}$"), fontsize=7.5, pad=3)
            if c == 0:
                ax.set_ylabel(label, fontsize=7.5, labelpad=3)
    _finish(fig, out, plotted)


RHOS = (("B20_rho0.0625", "1/16"), ("B20_rho0.125", "1/8"), ("B20_rho0.25", "1/4"), ("B20_rho0.5", "1/2"),
        ("B20_rho1.0", "1"))
TRADE_K = (("K4", BLUE, "o"), ("K11", ORANGE, "s"))


def fig_tradeoff(trade, out):
    plotted = {}
    fig, axes = plt.subplots(len(STRATA), 1, figsize=(3.45, 0.5 + 1.55 * len(STRATA)), sharex=True,
                             gridspec_kw={"hspace": 0.3})
    for ax, (label, _, name, _, _) in zip(axes, STRATA):
        plotted[label] = {}
        for K, color, marker in TRADE_K:
            pts = [trade["strata"][name][K][rho] for rho, _ in RHOS]
            F = [p["F"] for p in pts]
            ax.plot(F, [p["bits_pct"] for p in pts], "-", marker=marker, color=color, lw=0.9, ms=3.6,
                    mec="white", mew=0.5, zorder=3)
            ax.plot(F, [p["sub_pct"] for p in pts], ls=(0, (3, 2)), marker=marker, color=color, lw=0.8, ms=3.6,
                    mfc="white", mec=color, mew=0.8, zorder=2)
            plotted[label][K] = {rho: pts[i] for i, (rho, _) in enumerate(RHOS)}
        ax.set_title(label, fontsize=7.5, loc="left", pad=2, color=INK)
        ax.set_ylabel("bits, % of all", labelpad=2)
        ax.set_ylim(0, None)
        _clean(ax)
        ax.grid(color="#e4e3dd", lw=0.5, zorder=0)
    axes[-1].set_xlabel("fidelity $F$", labelpad=1)
    handles = [Line2D([], [], color=c, marker=mk, ms=3.6, lw=0.9, mec="white", mew=0.5, label=f"REMAKE, $K={K[1:]}$")
               for K, c, mk in TRADE_K]
    handles += [Line2D([], [], color=c, marker=mk, ms=3.6, lw=0.8, ls=(0, (3, 2)), mfc="white", mec=c, mew=0.8,
                       label=f"subset, $K={K[1:]}$") for K, c, mk in TRADE_K]
    axes[0].legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, 1.48), ncol=2, frameon=False,
                   fontsize=6.5, handlelength=2.2, columnspacing=1.0, labelspacing=0.3)
    _finish(fig, out, plotted)


def fig_slices(recon_dir, out):
    images = np.load(Path(recon_dir) / "recon_images.npz")
    sel = json.loads((Path(recon_dir) / "recon_selection.json").read_text())
    cmap = LinearSegmentedColormap.from_list("signed", [BLUE, "#ffffff", ORANGE])
    fig, axes = plt.subplots(len(STRATA), 6, figsize=(7.0, 0.35 + 1.18 * len(STRATA)),
                             gridspec_kw={"hspace": 0.1, "wspace": 0.05})
    plotted = {}
    for r, (label, _, name, _, _) in enumerate(STRATA):
        s = sel[name]
        plotted[label] = {"zoom": s["zoom"], "zoom_F_bins": s["zoom_F_bins"], "zoom_n_events": s["zoom_n_events"]}
        for b in range(3):
            for c, kind in enumerate(("true", "rec")):
                ax = axes[r, 2 * b + c]
                img = np.clip(images[f"{name}_zoom_{kind}_b{b}"], -1, 1)
                ax.imshow(img, cmap=cmap, vmin=-1, vmax=1, interpolation="nearest", aspect="equal")
                ax.set_xticks([]); ax.set_yticks([])
                for sp in ax.spines.values():
                    sp.set_linewidth(0.4); sp.set_color(MUTED)
                if kind == "rec":
                    ax.text(0.97, 0.04, f"$F={s['zoom_F_bins'][b]:.2f}$", transform=ax.transAxes, fontsize=6,
                            color=INK, ha="right", va="bottom",
                            bbox=dict(facecolor="white", edgecolor="none", pad=0.6, alpha=0.8))
                if r == 0:
                    t0, t1 = b * T0_MS / 3, (b + 1) * T0_MS / 3
                    ax.set_title(("true" if kind == "true" else "rebuilt") + f", {t0:.0f}$-${t1:.0f} ms",
                                 fontsize=6.8, pad=3)
                if c == 0 and b == 0:
                    ax.set_ylabel(label, fontsize=7.5, labelpad=3)
    _finish(fig, out, plotted)


def fig_bridge(br, out):
    cases = br["cases"]
    fig, (ax, bx) = plt.subplots(2, 1, figsize=(3.45, 4.6), gridspec_kw={"hspace": 0.62})
    plotted = {"timing": {}, "fidelity": {}}
    series = (("regenerated", cases["translation"], "regen", BLUE, "o"),
              ("moved, exact map", cases["translation"], "exact", ORANGE, "s"),
              ("moved, exact map, growing spacing", cases["scale"], "exact", PURPLE, "D"),
              ("moved, nearest whole pixel", cases["subpixel"], "round", AQUA, "^"))
    for label, c, key, color, marker in series:
        m = [row["m"] for row in c["per_m"]]
        y = [row[f"{key}_D_over_DA"] for row in c["per_m"]]
        ax.plot(m, y, "-", marker=marker, color=color, lw=0.9, ms=3.4, mec="white", mew=0.5, label=label, zorder=3)
        if key != "regen":
            pr = [row[f"{key}_pred_over_DA"] for row in c["per_m"]]
            ax.plot(m, pr, ls="", marker=marker, ms=5.2, mfc="none", mec=INK, mew=0.5, zorder=4)
        else:
            pr = None
        plotted["timing"][label] = {"m": m, "measured": y, "predicted": pr}
    ax.set_xticks(range(1, 11))
    ax.set_xlabel("windows since the key window, $m$", labelpad=1)
    ax.set_ylabel("timing error / $D_{A}$", labelpad=2)
    ax.set_ylim(0, None)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=2, frameon=False, fontsize=6.2, handlelength=1.8,
              borderaxespad=0.2, labelspacing=0.25, columnspacing=1.0)
    dts = cases["translation"]["dt_over_tau"]
    fseries = (("regenerated", cases["translation"]["fidelity"]["pixel"]["regen"], BLUE, "o", "-"),
               ("moved, exact map", cases["translation"]["fidelity"]["pixel"]["exact"], ORANGE, "s", "-"),
               ("moved, nearest whole pixel", cases["subpixel"]["fidelity"]["pixel"]["round"], AQUA, "^", "-"),
               ("moved, fitted map, whole windows", cases["subpixel"]["fidelity"]["window"]["fit"], INK, "v", "-"))
    for label, y, color, marker, ls in fseries:
        bx.plot(dts, y, ls=ls, marker=marker, color=color, lw=0.9, ms=3.4, mec="white", mew=0.5, label=label, zorder=3)
        plotted["fidelity"][label] = y
    th = cases["translation"]["fidelity_theory"]
    xs = [d for d in dts if d <= 0.5]
    bx.plot(xs, [th["regen"][dts.index(d)] for d in xs], color=BLUE, lw=0.5, ls=(0, (1, 1.5)), zorder=2)
    bx.plot(xs, [th["moved"][dts.index(d)] for d in xs], color=ORANGE, lw=0.5, ls=(0, (1, 1.5)), zorder=2)
    plotted["fidelity"]["dt_over_tau"] = dts
    plotted["fidelity"]["theory"] = th
    bx.set_xscale("log")
    bx.set_xlabel("time bin / event spacing, $\\Delta_t/\\tau$", labelpad=1)
    bx.set_ylabel("fidelity, 1-pixel voxels", labelpad=2)
    bx.set_ylim(0, 1.0)
    bx.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}"))
    bx.legend(loc="upper left", frameon=False, fontsize=6.2, handlelength=1.8, borderaxespad=0.2, labelspacing=0.25)
    for a in (ax, bx):
        _clean(a)
    _finish(fig, out, plotted)


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--etram", required=True)
    ap.add_argument("--dsec", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--recon")
    ap.add_argument("--tradeoff")
    ap.add_argument("--bridge")
    a = ap.parse_args(argv)
    reports = [json.loads(Path(p).read_text()) for p in (a.etram, a.dsec)]
    outdir = Path(a.out)
    outdir.mkdir(parents=True, exist_ok=True)
    fig_bits_all(reports, outdir / "fig_bits_all")
    fig_limits(reports, outdir / "fig_limits")
    if a.recon:
        fig_recon(a.recon, outdir / "fig_recon")
        if "day_zoom_true_b0" in np.load(Path(a.recon) / "recon_images.npz").files:
            fig_slices(a.recon, outdir / "fig_slices")
    if a.tradeoff:
        fig_tradeoff(json.loads(Path(a.tradeoff).read_text()), outdir / "fig_tradeoff")
    if a.bridge:
        fig_bridge(json.loads(Path(a.bridge).read_text()), outdir / "fig_bridge")
    print("wrote the figures under", outdir)


if __name__ == "__main__":
    main()
```
