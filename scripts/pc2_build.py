"""Directive 028, Section 4: results/pc2/binned_fidelity.json and results/pc2/motion_task.json from kept outputs.

  python3 scripts/pc2_build.py OUT_DIR

4A reads the per-group outputs of directive 022 (``ph_run.load``); 4B the per-group outputs of directive 019
(``hd_run.load``). Nothing is read from a recording. ``checks.json`` holds checks 2 and 3 of Section 8.

4A. ``sums["reg"]`` of ``ec.phase.evaluate_group`` has the shape (flicker, speed, grid, bin, [N, N2, M, M0]). A row
of a grid is ``sums[0, :, g, b].sum(axis=0)`` summed over the groups and recordings of the stratum, exactly as
Table 2 of ``scripts/ph_reduce.py``. ``F_ci95`` resamples the recordings of the stratum (all of them, also those
with N = 0 in the bin) 2,000 times with seed 20261016 and recomputes the pooled F. Each row also gives
``F_k1_same_pixels``: F on the grid (1, 1) (one voxel per window, so M is the sum over pixel-polarities of
min(true count, moved count)) of the bin that holds the same pixel-polarities, ``b + 10`` (the edges step by
sqrt(2), and T0 / 1 over T0 / 32 is 2^5); it bounds F from above by count matching alone. Coverage shares are of
the true events of window w + 1 in the pixel-polarities of the blocks that entered the sums (``N`` over all
flicker classes, speed classes and bins, the no-tau bin included, on (1, 32)), the denominator of Table 4 of
report 022.

4B. Records of ``ec.families._Tasks.run``, key ``motion``, placement ``start``. D1: the P-picture modes ``qp<q>`` of
the D1 groups of directive 019, recordings with at least 2 (eTraM) or 1 (DSEC) groups, as ``hd_reduce``; D2
(reference): ``d2["s1_k<k>_start"]`` of every group of 019 (D1 and D2 tasks), same rule. A square is undefined
when the true velocity is not finite; ``ec.downstream.cmax_velocity`` returns NaN only for an empty set, and the
squares of ``fb_run.squares_for`` hold at least 200 true events of that window, so no square is undefined; a
record with a NaN error and ``n_rec > 0`` would mean an undefined square and is counted so. A failure is a
defined square whose decode leaves no event in it (``n_rec == 0``; the decoded velocity is then NaN).
"""
from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ec import hevcdiag as hd, mp, phase as ph, threshold as th  # noqa: E402
import hd_run as HR  # noqa: E402
import ph_run as P  # noqa: E402
import th_reduce as TRD  # noqa: E402

STRATA = ("day", "night", "all")
SEED, N_BOOT = 20261016, 2000
MIN_EVENTS, MIN_RECORDINGS = 10_000, 5          # the plotting rule of scripts/fig_028.py
SHIFT = {"s1_k32": 10, "s1_k64": 12}             # bins between these grids and (1, 1): log_sqrt2(k)
MIN_GROUPS = {"etram": 2, "dsec": 1}
QPS = hd.QPS
GRID_4B = ("s1_k3", "s1_k64")
REPO_RESULTS = mp.REPO / "results"


def _json(o):
    if isinstance(o, dict):
        return {k: _json(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_json(v) for v in o]
    if isinstance(o, np.ndarray):
        return _json(o.tolist())
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        o = float(o)
    if isinstance(o, float) and not math.isfinite(o):
        return None
    return o


def stratum(ds, rid):
    return "all" if ds == "dsec" else mp.lighting(rid)


def F_of(v):
    den = v[..., 0] + v[..., 1]
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(den > 0, 2.0 * v[..., 2] / den, np.nan), np.where(den > 0, 2.0 * v[..., 3] / den, np.nan)


# ------------------------------------------------------------------------------------------------ 4A
def binned_fidelity():
    per = {s: [] for s in STRATA}
    for ds in ("etram", "dsec"):
        for rid in HR.groups(ds, "d2"):
            gs = P.load(f"rec|{ds}|{rid}")["groups"]
            per[stratum(ds, rid)].append((rid, sum(g["sums"]["reg"] for g in gs)))
    g32, g64, g1 = (ph.GRIDS.index((1, k)) for k in (32, 64, 1))
    out = {"strata": {}}
    for s in STRATA:
        A = np.stack([a for _, a in per[s]]).astype(np.float64)        # (rec, flicker, speed, grid, bin, 4)
        R = A[:, 0].sum(axis=1)                                         # flicker 0, speeds pooled: (rec, grid, bin, 4)
        rng = np.random.default_rng(SEED)
        idx = rng.integers(0, len(A), size=(N_BOOT, len(A)))
        grids = {}
        for gname, g in (("s1_k32", g32), ("s1_k64", g64)):
            rows = []
            boot = R[idx][:, :, g].sum(axis=1)                           # (boot, bin, 4)
            Fb, _ = F_of(boot)
            for b in range(th.N_BINS):
                v = R[:, g, b].sum(axis=0)
                F, F0 = F_of(v)
                fb = Fb[:, b]
                fb = fb[np.isfinite(fb)]
                kb = b + SHIFT[gname]
                exact = 1 <= b and kb <= th.N_BINS - 3                     # both bins bounded and geometric
                k1 = F_of(R[:, g1, kb].sum(axis=0))[0] if exact else float("nan")
                rows.append({"bin": b, "r_lo": float(th.R_EDGES[b]) if b < th.N_BINS - 1 else None,
                             "r_hi": float(th.R_EDGES[b + 1]) if b < th.N_BINS - 2 else None,
                             "r_centre": TRD.bin_centre(b), "N": int(v[0]), "N2": int(v[1]), "M": int(v[2]),
                             "M0": int(v[3]), "F": float(F), "F0": float(F0),
                             "F_ci95": ([float(np.percentile(fb, 2.5)), float(np.percentile(fb, 97.5))] if len(fb)
                                        else [float("nan")] * 2),
                             "n_recordings": int((R[:, g, b, 0] > 0).sum()),
                             "F_k1_same_pixels": float(k1), "k1_bin": kb if exact else None})
            grids[gname] = rows
        tot = A[:, :, :, g32, :, 0].sum()                               # all flicker, speeds, bins on (1, 32)
        no_tau = A[:, :, :, g32, th.N_BINS - 1, 0].sum()
        plotted = sum(r["N"] for r in grids["s1_k32"]
                      if r["N"] >= MIN_EVENTS and r["n_recordings"] >= MIN_RECORDINGS and math.isfinite(r["F"]))
        out["strata"][s] = {
            "n_recordings": len(A),
            "coverage": {"share_events_with_tau_reg": float(1.0 - no_tau / tot),
                         "share_events_in_plotted_bins": float(plotted / tot),
                         "denominator": "true events of window w + 1 in the pixel-polarities of the blocks that entered "
                                        "the sums of directive 022 (candidate blocks with at least N_MIN true events, a "
                                        "source, and at least N_MIN true and moved events), all flicker and speed "
                                        "classes, the no-tau bin included, grid (1, 32): the denominator of Table 4 of "
                                        "report 022",
                         "n_true_events": int(tot)},
            "grids": grids}
    out["definitions"] = {
        "source": "directive 022, ec.phase.evaluate_group sums['reg'], flicker 0, speed classes pooled",
        "tau_reg": "median of the regular intervals (two consecutive intervals a, b of one pixel and polarity with "
                   "max <= 1.2 min, min > 0, a + b <= T0) over [(w - 3) T0, (w + 1) T0), windows w - 3 to w; the scored "
                   "window w + 1 is excluded; hot pixels removed first",
        "N": "true events of window w + 1 of the pixel-polarity, per pixel-polarity in the union of the true and moved "
             "keys of an entering block, binned by r = dt / tau_reg of that pixel-polarity",
        "N2": "moved events (window w moved by the block's shift and onset delay) landing in window w + 1, same keys",
        "M": "sum over voxels (1 px, T0 / k, polarity) of min(true, moved)",
        "M0": "as M with the moved times redrawn uniformly in window w + 1 (null)",
        "unmatched": "a pixel-polarity with true events and no moved event enters with N2 = 0, M = 0; one with moved "
                     "events and no true event enters with N = 0, M = 0; both lower F",
        "motion": "estimated per 20 x 20 block on the pair (w - 1, w) by ec.phase.choose_shift (pairs of directive "
                  "020, ties within 2 sqrt(m) to the smallest |dx| + |dy|), onset delay as ec.phase.onset_delay; "
                  "causal; not the exact motion of Eq. (binfidmoved)",
        "F": "2 M / (N + N2) pooled over groups and recordings (event-weighted); F0 = 2 M0 / (N + N2)",
        "F_ci95": "bootstrap over the recordings of the stratum, 2000 resamples, seed 20261016",
        "n_recordings": "recordings with N > 0 in the bin",
        "r_centre": "th_reduce.bin_centre (geometric centre; NaN for [128, inf) and the no-tau bin)",
        "F_k1_same_pixels": "F on grid (1, 1) of bin k1_bin, which holds the same pixel-polarities (k1_bin = bin + 10 "
                            "for (1, 32), bin + 12 for (1, 64)); count matching alone, an upper bound of F",
        "plotted_rule": f"N >= {MIN_EVENTS} and n_recordings >= {MIN_RECORDINGS} (scripts/fig_028.py), on (1, 32)"}
    return out


# ------------------------------------------------------------------------------------------------ 4B
def _records(groups_by_rec, select):
    """{rid: [motion records]} for the recordings with enough groups."""
    return {rid: [m for g in gs for m in select(g)] for rid, gs in groups_by_rec.items()}


def classify(recs):
    """Per record: 'undefined', 'failure' or the error."""
    out = []
    for m in recs:
        e = m["error_px"]
        if e is not None and math.isfinite(e):
            out.append(e)
        elif m["n_rec"] > 0:
            out.append("undefined")
        else:
            out.append("failure")
    return out


def task_cell(by_rec):
    """success1, ci95, fail_share, median_err, n_squares, n_undefined over the recordings ``by_rec``."""
    names = sorted(by_rec)
    ok, fail, n = [], [], []
    errs = []
    n_und = 0
    for r in names:
        c = classify(by_rec[r])
        d = [x for x in c if x != "undefined"]
        n_und += len(c) - len(d)
        e = [x for x in d if x != "failure"]
        ok.append(sum(1 for x in e if x <= 1.0))
        fail.append(len(d) - len(e))
        n.append(len(d))
        errs += e + [math.inf] * (len(d) - len(e))
    ok, fail, n = (np.array(v, dtype=np.float64) for v in (ok, fail, n))
    rng = np.random.default_rng(SEED)
    idx = rng.integers(0, len(names), size=(N_BOOT, len(names)))
    den = n[idx].sum(axis=1)
    sb = np.where(den > 0, ok[idx].sum(axis=1) / np.where(den > 0, den, 1), np.nan)
    sb = sb[np.isfinite(sb)]
    fs = fail.sum() / n.sum() if n.sum() else float("nan")
    return {"success1": float(ok.sum() / n.sum()) if n.sum() else float("nan"),
            "ci95": [float(np.percentile(sb, 2.5)), float(np.percentile(sb, 97.5))] if len(sb) else [float("nan")] * 2,
            "fail_share": float(fs), "median_err": float(np.median(errs)) if errs and fs < 0.5 else None,
            "n_squares": int(n.sum()), "n_undefined": int(n_und), "n_recordings": len(names)}


def motion_task():
    tasks = json.loads((HR.HD_E / "plan.json").read_text())["tasks"]
    d1g, allg = {}, {}
    for key in tasks:
        kind = key.split("|")[0]
        if kind == "d3":
            continue
        ds, rid = key.split("|")[1:3]
        d = HR.load(key)
        if kind == "d1":
            d1g.setdefault((ds, rid), []).extend(d["groups"])
        allg.setdefault((ds, rid), []).extend(d["groups"])
    d1g = {k: v for k, v in d1g.items() if len(v) >= MIN_GROUPS[k[0]]}
    allg = {k: v for k, v in allg.items() if len(v) >= MIN_GROUPS[k[0]]}
    frontier = json.loads((REPO_RESULTS / "hd" / "frontier.json").read_text())
    out, chk = {"strata": {}}, {}
    for s in STRATA:
        D1 = {rid: gs for (ds, rid), gs in d1g.items() if stratum(ds, rid) == s}
        D2 = {rid: gs for (ds, rid), gs in allg.items() if stratum(ds, rid) == s}
        out["strata"][s] = {}
        for gn in GRID_4B:
            ref = task_cell(_records(D2, lambda g, gn=gn: g["d2"][f"{gn}_start"]["tasks"]["motion"]))
            cell = {"reference": ref, "qp": {}}
            for q in QPS:
                qm = f"qp{q}"
                recs = _records(D1, lambda g, gn=gn, qm=qm: g["d1"][gn]["modes"][qm]["tasks"]["start"]["motion"])
                c = task_cell(recs)
                bs = [sum(g["d1"][gn]["modes"][qm]["bits"] for g in gs) / float(sum(sum(g["n_true"]) for g in gs))
                      for gs in D1.values()]
                c["b"] = float(np.median(bs))
                # the success-only statistic of results/hd/frontier.json: median over recordings of the per-recording
                # median of the finite errors
                pr = []
                for rid in recs:
                    e = [m["error_px"] for m in recs[rid] if m["error_px"] is not None and math.isfinite(m["error_px"])]
                    pr.append(float(np.median(e)) if e else float("nan"))
                pr = [v for v in pr if math.isfinite(v)]
                c["success_only_median_err"] = float(np.median(pr)) if pr else float("nan")
                fr = frontier[s][gn][qm]
                c["frontier_motion_error_px"] = fr["tasks"]["start"]["motion_error_px"]
                c["frontier_motion_no_event"] = fr["tasks"]["start"]["motion_no_event"]
                chk[f"{s}|{gn}|{qm}"] = {
                    "median_finite_equals_frontier": abs(c["success_only_median_err"] - fr["tasks"]["start"]["motion_error_px"]) <= 1e-9,
                    "b_equals_frontier": abs(c["b"] - fr["b"]) <= 1e-9,
                    "success_plus_fail_le_1": c["success1"] + c["fail_share"] <= 1 + 1e-12}
                cell["qp"][qm] = c
            out["strata"][s][gn] = cell
    out["definitions"] = {
        "source": "directive 019 per-group outputs (hd_run.load), ec.families._Tasks.run key 'motion', placement 'start'",
        "squares": "fb_run.squares_for on the true events of window w + 2: the 10 densest 40 x 40 squares with at least "
                   "200 events; the velocity is ec.downstream.cmax_velocity (contrast maximisation) over the square, "
                   "warped to (w + 2) T0; error_px = |v_dec - v_true| T0 in px per window",
        "D1": "P-picture modes qp<q> of the D1 groups of directive 019 (j % 40 == 0 eTraM, j % 20 == 0 DSEC), "
              "recordings with at least 2 (eTraM) or 1 (DSEC) groups",
        "reference": "D2: hevcdiag.represent, counts on (1, k) back to events at the voxel start, no coding, on every "
                     "group of directive 019 (D1 and D2 tasks), same recording rule",
        "undefined": "true velocity not finite; cmax_velocity is NaN only for an empty set and every square holds >= 200 "
                     "true events, so none occurs; a record with NaN error and n_rec > 0 would count here",
        "failure": "decoded velocity not finite: the decode leaves no event in the square (n_rec == 0); counted as not "
                   "recovered",
        "success1": "share of defined squares with error <= 1 px per window, pooled over squares of the stratum",
        "ci95": "bootstrap over recordings of the pooled share, 2000 resamples, seed 20261016",
        "fail_share": "share of defined squares that fail",
        "median_err": "median error with failures as infinite; null when fail_share >= 0.5",
        "b": "median over recordings of bits per true event of the four windows at that QP (results/hd/frontier.json)",
        "success_only_median_err": "median over recordings of the per-recording median of the finite errors: the "
                                   "construction of motion_error_px in results/hd/frontier.json"}
    return out, chk


def main(out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    t0, c0 = time.time(), time.process_time()
    bf = binned_fidelity()
    (out / "binned_fidelity.json").write_text(json.dumps(_json(bf), indent=1) + "\n")
    mt, chk3 = motion_task()
    (out / "motion_task.json").write_text(json.dumps(_json(mt), indent=1) + "\n")
    # check 2
    ph_rep = json.loads((REPO_RESULTS / "ph" / "report.json").read_text())
    chk2 = {}
    for s in STRATA:
        t2 = ph_rep["tables"]["2_binned_fidelity"][s]["reg"]["s1_k32"]
        dev = [abs(a["F"] - b["F_pooled"]) for a, b in zip(bf["strata"][s]["grids"]["s1_k32"], t2)
               if math.isfinite(a["F"]) and b["F_pooled"] is not None and math.isfinite(b["F_pooled"])]
        t4 = ph_rep["tables"]["4_coverage"][s]["share_true_events_without_tau_reg"]
        chk2[s] = {"F_max_abs_dev": max(dev), "n_bins_compared": len(dev), "F_ok": max(dev) <= 1e-9,
                   "without_tau_reg_dev": abs(1.0 - bf["strata"][s]["coverage"]["share_events_with_tau_reg"] - t4),
                   "without_tau_reg_ok": abs(1.0 - bf["strata"][s]["coverage"]["share_events_with_tau_reg"] - t4) <= 1e-6}
    checks = {"2_binned_fidelity": chk2,
              "3_motion_task": {"all_ok": all(all(v.values()) for v in chk3.values()), "cells": chk3},
              "wall_s": time.time() - t0, "cpu_s": time.process_time() - c0}
    (out / "checks.json").write_text(json.dumps(_json(checks), indent=1) + "\n")
    print(json.dumps(_json({"2": chk2, "3_all_ok": checks["3_motion_task"]["all_ok"],
                            "3_failing": [k for k, v in chk3.items() if not all(v.values())][:10]}), indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
