"""Directive 005: where the fidelity is lost. Join of the rows of directives 003 and 004, and the tables.

  python3 scripts/dg_reduce.py RESULTS_DIR [--wall-s S]

Reads only the per-row files of Stage C of directive 003 and Stage A of directive
004 on the host. The row is the instance: for a stratum, target and lighting, a
recording's value is the median over its rows (directive 001, Section 6), it enters
with at least 20 rows, and a table entry is the median over recordings with a 95%
interval from 2000 bootstrap resamples of recordings (seed 20261012).
"""
from __future__ import annotations

import argparse
import json
import platform
import socket
import sys
import time
from pathlib import Path

import numpy as np

N_BOOT, SEED, MIN_N = 2000, 20261012, 20
GP_C = Path.home() / "prjs" / "event_coding" / "gp" / "C"
AF_A = Path.home() / "prjs" / "event_coding" / "af" / "A"
CELLS = {"headline": "s2_k3", "frame": "s2_k1"}
MODELS = ("aligned", "affine")
LB = ("day", "night")
GP_COLS = ("recording_id", "track_id", "t_e_us", "target", "skip", "lighting", "group", "speed_bin", "overlap",
           "n_source", "n_future", "aligned_n_pred", "aligned_f1_s2_k3", "aligned_f1_s2_k1", "aligned_dx", "aligned_dy")
AF_COLS = ("recording_id", "track_id", "t_e_us", "target", "skip", "n_source", "n_future", "growth_ratio",
           "affine_n_pred", "affine_f1_s2_k3", "affine_f1_s2_k1")


def load(dirpath, cols):
    parts = []
    for f in sorted(dirpath.glob("rows_*.npz")):
        z = np.load(f)
        if "target" in z:
            parts.append({c: z[c] for c in cols if c in z.files} | {c: np.full(len(z["target"]), np.nan)
                                                                    for c in cols if c not in z.files})
    return {c: np.concatenate([p[c] for p in parts]) for c in cols}


def key(d):
    return np.char.add(np.char.add(np.char.add(d["recording_id"].astype(str), "|"),
                                   np.char.add(d["track_id"].astype(np.int64).astype(str), "|")),
                       np.char.add(np.char.add(d["t_e_us"].astype(np.int64).astype(str), "|"),
                                   d["target"].astype(np.int64).astype(str)))


def boot(vals, counts):
    ok = (counts >= MIN_N) & np.isfinite(vals)
    v = vals[ok]
    out = {"median": None, "ci95": [None, None], "n_recordings": int(ok.sum()), "n_rows": int(counts[ok].sum())}
    if len(v):
        bs = np.median(v[np.random.default_rng(SEED).integers(0, len(v), size=(N_BOOT, len(v)))], axis=1)
        out.update(median=float(np.median(v)), ci95=[float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("resdir")
    a = ap.parse_args()
    t_start = time.time()
    res = Path(a.resdir)
    res.mkdir(parents=True, exist_ok=True)
    g = load(GP_C, GP_COLS)
    f = load(AF_A, AF_COLS)
    gsc, fsc = g["skip"] == "", f["skip"] == ""
    kg, kf = key(g), key(f)

    # ================================================== acceptance 1: join
    kgs, kfs = kg[gsc], kf[fsc]
    o = np.argsort(kfs)
    pos = np.minimum(np.searchsorted(kfs[o], kgs), len(kfs) - 1)
    found = kfs[o][pos] == kgs
    jf = np.flatnonzero(fsc)[o][pos]
    jg = np.flatnonzero(gsc)
    acc1 = {"n_scored_rows_003": int(gsc.sum()), "n_scored_rows_004": int(fsc.sum()),
            "n_unique_keys_003": int(len(np.unique(kgs))), "n_joined": int(found.sum()),
            "n_n_source_or_n_future_differ": int(((g["n_source"][jg][found] != f["n_source"][jf][found])
                                                  | (g["n_future"][jg][found] != f["n_future"][jf][found])).sum())}
    acc1["n_rows"] = acc1["n_joined"]
    acc1["pass"] = (acc1["n_joined"] == acc1["n_scored_rows_003"] == acc1["n_scored_rows_004"]
                    == acc1["n_unique_keys_003"] and acc1["n_n_source_or_n_future_differ"] == 0)
    jg, jf = jg[found], jf[found]
    R = {c: g[c][jg] for c in GP_COLS}
    for c in ("growth_ratio", "affine_n_pred", "affine_f1_s2_k3", "affine_f1_s2_k1"):
        R[c] = f[c][jf]
    del g, f

    # ================================================== per-row quantities
    n_true = R["n_future"].astype(np.float64)
    q = {"rho": n_true / R["n_source"].astype(np.float64),
         "growth": R["growth_ratio"].astype(np.float64),
         "disp": np.hypot(R["aligned_dx"].astype(np.float64), R["aligned_dy"].astype(np.float64))}
    acc2 = {"by_model_cell": {}}
    ok2 = True
    zero_pred = {}
    for m in MODELS:
        npred = R[f"{m}_n_pred"].astype(np.float64)
        zero = npred == 0
        zero_pred[m] = int(zero.sum())
        q[f"{m}_pred_over_true"] = npred / n_true
        for cname, cell in CELLS.items():
            F1 = R[f"{m}_f1_{cell}"].astype(np.float64)
            match = F1 * (npred + n_true) / 2.0
            with np.errstate(divide="ignore", invalid="ignore"):
                prec = np.where(zero, np.nan, match / npred)
                rec = match / n_true
                ceil = 2.0 * np.minimum(npred, n_true) / (npred + n_true)
                plac = np.where(zero, np.nan, match / np.minimum(npred, n_true))
            pre = f"{m}_{cname}"
            q[f"F1_{pre}"], q[f"ceiling_{pre}"], q[f"placement_{pre}"] = F1, ceil, plac
            q[f"precision_{pre}"], q[f"recall_{pre}"] = prec, rec
            nz = ~zero
            err = np.abs(ceil[nz] * plac[nz] - F1[nz])
            inr = lambda v: int((~((v >= 0) & (v <= 1))).sum())
            d = {"max_abs_ceiling_x_placement_minus_F1": float(err.max()), "n_over_1e-12": int((err > 1e-12).sum()),
                 "n_zero_pred_rows": int(zero.sum()), "n_zero_pred_rows_with_F1_nonzero": int((F1[zero] != 0).sum()),
                 "n_outside_0_1": {"precision": inr(prec[nz]), "recall": inr(rec), "ceiling": inr(ceil),
                                   "placement": inr(plac[nz])}}
            acc2["by_model_cell"][pre] = d
            ok2 &= d["n_over_1e-12"] == 0 and d["n_zero_pred_rows_with_F1_nonzero"] == 0 \
                and not any(d["n_outside_0_1"].values())
    acc2["pass"] = bool(ok2)

    # ================================================== aggregation over recordings
    ids = np.unique(R["recording_id"])
    rec = np.searchsorted(ids, R["recording_id"])
    light = R["lighting"]
    tgt = R["target"].astype(int)
    H = (R["group"] == "vehicles") & (R["overlap"] == 0) & ((R["speed_bin"] == 1) | (R["speed_bin"] == 2))
    ISOV = (R["group"] == "vehicles") & (R["overlap"] == 0)

    def agg(mask, name, L):
        mm = mask & (light == L)
        v = q[name][mm]; r = rec[mm]
        fin = np.isfinite(v)
        v, r = v[fin], r[fin]
        if len(v) == 0:
            return boot(np.zeros(0), np.zeros(0))
        o = np.argsort(r, kind="stable")
        v, r = v[o], r[o]
        cut = np.flatnonzero(np.diff(r)) + 1
        meds = np.array([np.median(x) for x in np.split(v, cut)])
        cnts = np.array([len(x) for x in np.split(v, cut)])
        return boot(meds, cnts)

    def pooled(mask, name, L, qs=(0.5,)):
        v = q[name][mask & (light == L)]
        v = v[np.isfinite(v)]
        return {str(x): (float(np.quantile(v, x)) if len(v) else None) for x in qs}

    T = {}
    t1 = {}
    for m_ in range(1, 11):
        for L in LB:
            d = {}
            for mo in MODELS:
                for qn in ("F1", "ceiling", "placement", "precision", "recall"):
                    d[f"{qn}_{mo}_headline"] = agg(H & (tgt == m_), f"{qn}_{mo}_headline", L)
                    if m_ in (1, 4, 10):
                        d[f"{qn}_{mo}_frame"] = agg(H & (tgt == m_), f"{qn}_{mo}_frame", L)
            t1.setdefault(f"m{m_}", {})[L] = d
    T["1_counts_against_placement_H"] = t1
    T["2_counts_H_pooled_quantiles"] = {f"m{m_}": {L: {n: pooled(H & (tgt == m_), n, L, (0.1, 0.5, 0.9)) | {
        "n_rows": int((H & (tgt == m_) & (light == L)).sum())} for n in ("rho", "aligned_pred_over_true",
                                                                         "affine_pred_over_true")} for L in LB}
                                         for m_ in (1, 4, 10)}
    gb = ((0, 0.8), (0.8, 0.9), (0.9, 1.1), (1.1, 1.25), (1.25, np.inf))
    t3 = {}
    for lo, hi in gb:
        b = H & (tgt == 10) & (q["growth"] >= lo) & (q["growth"] < hi)
        name = f"[{lo}, {'inf' if np.isinf(hi) else hi})"
        t3[name] = {L: {"n_rows": int((b & (light == L)).sum()),
                        **{n: {"over_recordings": agg(b, n, L), "pooled_median": pooled(b, n, L)["0.5"]}
                           for n in ("growth", "rho", "ceiling_aligned_headline", "placement_aligned_headline",
                                     "ceiling_affine_headline", "placement_affine_headline")}} for L in LB}
    T["3_growth_H_m10"] = t3
    db = ((0, 2), (2, 5), (5, 10), (10, 20), (20, 40), (40, np.inf))
    t4a = {}
    for m_ in (4, 10):
        for lo, hi in db:
            b = ISOV & (tgt == m_) & (q["disp"] >= lo) & (q["disp"] < hi)
            t4a.setdefault(f"m{m_}", {})[f"[{lo}, {'inf' if np.isinf(hi) else hi})"] = {
                L: {"n_rows": int((b & (light == L)).sum()),
                    **{f"{qn}_{mo}": agg(b, f"{qn}_{mo}_headline", L) for mo in MODELS for qn in ("F1", "placement")}}
                for L in LB}
    t4b = {}
    for m_ in range(1, 11):
        b = ISOV & (tgt == m_) & (q["disp"] >= 5) & (q["disp"] < 10)
        t4b[f"m{m_}"] = {L: {"n_rows": int((b & (light == L)).sum()),
                             **{f"{qn}_{mo}": agg(b, f"{qn}_{mo}_headline", L) for mo in MODELS
                                for qn in ("F1", "placement")}} for L in LB}
    T["4_time_against_distance_isolated_vehicles"] = {"a_by_disp": t4a, "b_disp_5_10_by_target": t4b}
    kb = ((50, 200), (200, 1000), (1000, 5000), (5000, np.inf))
    t5 = {}
    for m_ in (1, 10):
        for lo, hi in kb:
            b = H & (tgt == m_) & (R["n_source"] >= lo) & (R["n_source"] < hi)
            t5.setdefault(f"m{m_}", {})[f"[{lo}, {'inf' if np.isinf(hi) else hi})"] = {
                L: {"n_rows": int((b & (light == L)).sum()),
                    **{n: {"over_recordings": agg(b, n, L), "pooled_median": pooled(b, n, L)["0.5"]}
                       for n in ("ceiling_aligned_headline", "placement_aligned_headline")}} for L in LB}
    T["5_key_size_H"] = t5

    # ================================================== acceptance 3: F1 medians of reports 003 and 004
    ref = {"aligned": {L: [] for L in LB}, "affine": {L: [] for L in LB}}
    g3 = json.loads((res / "ref_gp_report.json").read_text())["tables"]["2_targets_H"]
    a4 = json.loads((res / "ref_af_report.json").read_text())["tables"]["2_targets_H"]
    cmp = []
    for m_ in range(1, 11):
        for L in LB:
            for mo, src, k in (("aligned", g3, f"F1_aligned_{CELLS['headline']}"),
                               ("aligned", g3, f"F1_aligned_{CELLS['frame']}"),
                               ("affine", a4, f"F1_affine_{CELLS['headline']}"),
                               ("affine", a4, f"F1_affine_{CELLS['frame']}"),
                               ("aligned", a4, f"F1_aligned_{CELLS['headline']}")):
                cname = "headline" if k.endswith(CELLS["headline"]) else "frame"
                if cname == "frame" and m_ not in (1, 4, 10):
                    continue
                mine = t1[f"m{m_}"][L][f"F1_{mo}_{cname}"]["median"]
                theirs = src[f"m{m_}"][L][k]["median"]
                cmp.append({"m": m_, "lighting": L, "quantity": k, "report": "003" if src is g3 else "004",
                            "dg": mine, "reference": theirs, "equal_to_printed_digits": f"{mine:.3f}" == f"{theirs:.3f}"})
    acc3 = {"n_compared": len(cmp), "n_unequal": sum(not c["equal_to_printed_digits"] for c in cmp),
            "unequal": [c for c in cmp if not c["equal_to_printed_digits"]]}
    acc3["pass"] = acc3["n_unequal"] == 0
    pc = json.loads((res / "population_check.json").read_text())
    acc4 = {"exists": True, "names_event_or_annotation_files": pc["names_event_or_annotation_files"],
            "pass": not pc["names_event_or_annotation_files"]}

    # ================================================== shares for the predictions
    share = {}
    for L in LB:
        f1a, f1b = t1["m1"][L]["F1_affine_headline"]["median"], t1["m10"][L]["F1_affine_headline"]["median"]
        ca, cb = t1["m1"][L]["ceiling_affine_headline"]["median"], t1["m10"][L]["ceiling_affine_headline"]["median"]
        share[L] = {"log_share": float(np.log(ca / cb) / np.log(f1a / f1b)),
                    "linear_ratio": float((ca - cb) / (f1a - f1b))}
    report = {"directive": "005", "zero_pred_rows": zero_pred,
              "share_of_fall_of_F1_affine_accounted_for_by_ceiling": share,
              "acceptance": {"1_join": acc1, "2_identity_and_ranges": acc2, "3_F1_medians_equal_reports_003_004": acc3,
                             "4_population_check": acc4},
              "aggregation": {"instance": "row (instant and target)", "unit": "recording", "min_rows": MIN_N,
                              "n_boot": N_BOOT, "seed": SEED,
                              "H": "vehicles, isolated, speed_label in [20, 300) px/s, setting (100, 0)",
                              "table_4": "all isolated vehicle rows", "headline_cell": CELLS["headline"],
                              "frame_cell": CELLS["frame"],
                              "share_of_fall": "log_share = ln(ceiling(1)/ceiling(10)) / ln(F1(1)/F1(10)), exact since "
                                               "F1 = ceiling x placement; linear_ratio = (ceiling(1) - ceiling(10)) / "
                                               "(F1(1) - F1(10)); both on the medians over recordings of Table 1"},
              "tables": T}
    (res / "report.json").write_text(json.dumps(report, indent=1, allow_nan=False) + "\n")
    commit = (Path(__file__).resolve().parent.parent / "COMMIT").read_text().strip()
    prov = {"directive": "005", "host": socket.gethostname(), "commit": commit, "python": platform.python_version(),
            "numpy": np.__version__, "wall_s": time.time() - t_start,
            "inputs": "the per-row files listed in population_check.json, read in place"}
    (res / "provenance.json").write_text(json.dumps(prov, indent=1) + "\n")
    print(json.dumps({"acc": {k: v["pass"] for k, v in report["acceptance"].items()}, "acc1": acc1,
                      "acc3_unequal": acc3["n_unequal"], "zero_pred": zero_pred, "share": share,
                      "wall_s": prov["wall_s"]}, indent=1))


if __name__ == "__main__":
    main()
