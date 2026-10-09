"""Directive 002, Sections 6 to 10: aggregate Stages R and B.

  python3 scripts/rg_reduce.py RGDIR RESULTS_DIR [--wall-r S] [--wall-b S] [--workers TEXT]

Writes per_recording.npz, bandwidth.json, report.json and provenance.json. The unit
is the recording: its value of a quantity in a stratum and lead is the median over
its scored rows there (shares are means), and it enters with at least 20 rows in
Stage R and at least 3 subsampled rows in Stage B. A table entry is the median over
recordings with a 95% percentile interval from 2000 bootstrap resamples of
recordings (seed 20261009), and the numbers of recordings and rows behind it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import socket
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ec import mp, regen  # noqa: E402
import rg_run as RR  # noqa: E402

N_BOOT, SEED = 2000, 20261009
MIN_R, MIN_B = 20, 3
LEADS = ("0", "33", "100", "300")                 # settings 0..3 of directive 001, T1 = 100 ms
R_MODELS = ("cmax", "label", "static", "uniform")
CELLS = [(s, k) for s in regen.BLOCKS_PX for k in regen.TIME_BINS]
HEAD, FRAME = (2, 3), (2, 1)
GROUPS = ("vehicles", "other", "all")
SPEEDS = ("0-20", "20-100", "100-300", "300-inf", "20-300", "all")
OVERLAPS = ("isolated", "overlapping", "all")
H = ("vehicles", "20-300", "isolated")
B_MODELS = ("static", "label", "cmax")
B6 = RR.B6


def cell(s, k):
    return f"s{s}_k{k}"


def load(dirpath: Path):
    parts, files = [], []
    for f in sorted(dirpath.glob("rows_*.npz")):
        z = dict(np.load(f))
        files.append({"path": str(f), "sha256": hashlib.sha256(f.read_bytes()).hexdigest(),
                      "n_rows": int(len(z["setting"])) if "setting" in z else 0})
        if "setting" in z:
            parts.append(z)
    keys = sorted({k for z in parts for k in z})
    kinds = {k: next(z[k].dtype.kind for z in parts if k in z) for k in keys}
    return {k: np.concatenate([z[k] if k in z else np.full(len(z["setting"]), "" if kinds[k] == "U" else np.nan)
                               for z in parts]) for k in keys}, files


def smask(c, group, speed, overlap):
    m = np.ones(len(c["setting"]), dtype=bool)
    if group != "all":
        m &= c["group"] == group
    if speed == "20-300":
        m &= (c["speed_bin"] == 1) | (c["speed_bin"] == 2)
    elif speed != "all":
        m &= c["speed_bin"] == SPEEDS.index(speed)
    if overlap == "isolated":
        m &= c["overlap"] == 0
    elif overlap == "overlapping":
        m &= c["overlap"] == 1
    return m


def boot(vals, counts, min_n):
    ok = (counts >= min_n) & np.isfinite(vals)
    v = vals[ok]
    out = {"median": None, "ci95": [None, None], "n_recordings": int(ok.sum()), "n_rows": int(counts[ok].sum())}
    if len(v):
        bs = np.median(v[np.random.default_rng(SEED).integers(0, len(v), size=(N_BOOT, len(v)))], axis=1)
        out.update(median=float(np.median(v)), ci95=[float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))])
    return out


def per_rec(c, q, names, ids, groups_of, strata, shares):
    """values[rec, group, stratum, quantity], counts[rec, group, stratum]."""
    rix = {r: i for i, r in enumerate(ids)}
    rec = np.array([rix[r] for r in c["recording_id"]])
    G = len(groups_of)
    val = np.full((len(ids), G, len(strata), len(names)), np.nan)
    cnt = np.zeros((len(ids), G, len(strata)), dtype=np.int64)
    qa = np.stack([q[n] for n in names], axis=1)
    sm = [smask(c, *st) for st in strata]
    for gi, gmask in enumerate(groups_of):
        for ri in range(len(ids)):
            base = gmask & (rec == ri)
            if not base.any():
                continue
            for k, m in enumerate(sm):
                sel = base & m
                n = int(sel.sum())
                cnt[ri, gi, k] = n
                if n == 0:
                    continue
                block = qa[sel]
                for j, name in enumerate(names):
                    v = block[:, j]; v = v[np.isfinite(v)]
                    if len(v):
                        val[ri, gi, k, j] = v.mean() if name in shares else np.median(v)
    return val, cnt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rgdir"); ap.add_argument("resdir")
    ap.add_argument("--wall-r", type=float, default=float("nan"))
    ap.add_argument("--wall-b", type=float, default=float("nan"))
    ap.add_argument("--workers", default="")
    a = ap.parse_args()
    rg, res = Path(a.rgdir), Path(a.resdir)
    res.mkdir(parents=True, exist_ok=True)
    ids, _ = mp.load_population()
    light = {r: mp.lighting(r) for r in ids}
    is_day = np.array([light[r] == "day" for r in ids])
    rsel = lambda L: np.ones(len(ids), bool) if L is None else (is_day if L == "day" else ~is_day)

    # ============================================================== Stage R
    c, files_r = load(rg / "R")
    sc = c["skip"] == ""
    lead = c["setting"].astype(int)
    # acceptance 3: every Stage R row scored or counted as a skip, exactly once
    expected = {}
    for t in RR.mp_plan():
        z = RR.mp_rows(t[0], t[1])
        for i in RR.r_rows(z):
            expected[(t[0], int(t[1]), int(i))] = int(z["setting"][i])
    got = list(zip(c["recording_id"], c["mp_shard"].astype(int), c["mp_index"].astype(int)))
    allowed = {"", "source_too_small", "future_too_small", "outside_track_life", "support_outside_sensor"}
    acc3 = {"n_expected_rows": len(expected), "n_rows": len(got), "n_unique": len(set(got)),
            "missing": len(set(expected) - set(got)), "extra": len(set(got) - set(expected)),
            "unknown_skip_reasons": sorted(set(c["skip"]) - allowed),
            "n_scored": int(sc.sum()), "skips": {k: int(v) for k, v in zip(*np.unique(c["skip"][~sc], return_counts=True))}}
    acc3["pass"] = (acc3["n_rows"] == acc3["n_unique"] == acc3["n_expected_rows"] and not acc3["missing"]
                    and not acc3["extra"] and not acc3["unknown_skip_reasons"])
    # acceptance 4: n_future and support_px equal those of directive 001
    bad_nf = int((c["n_future"][sc] != c["mp_n_future"][sc]).sum())
    bad_sp = int((c["support_px"][sc] != c["mp_support_px"][sc]).sum())
    acc4 = {"n_scored": int(sc.sum()), "n_future_mismatch": bad_nf, "support_px_mismatch": bad_sp,
            "pass": bad_nf == 0 and bad_sp == 0}
    # acceptance 5: F1 in [0, 1]; non-decreasing along nested coarsening
    acc5 = {"chains": "1->2->4 px at each k; k 32->8->1 and 3->1 at each block size", "by_model": {}}
    ok5 = True
    for m in R_MODELS:
        f = {ce: c[f"{m}_f1_{cell(*ce)}"][sc] for ce in CELLS}
        out_rng = int(sum(((v < 0) | (v > 1) | ~np.isfinite(v)).sum() for v in f.values()))
        viol = 0
        for k in regen.TIME_BINS:
            viol += int((f[(2, k)] < f[(1, k)]).sum() + (f[(4, k)] < f[(2, k)]).sum())
        for s in regen.BLOCKS_PX:
            viol += int((f[(s, 8)] < f[(s, 32)]).sum() + (f[(s, 1)] < f[(s, 8)]).sum() + (f[(s, 1)] < f[(s, 3)]).sum())
        acc5["by_model"][m] = {"f1_outside_0_1": out_rng, "monotonicity_violations": viol}
        ok5 &= out_rng == 0 and viol == 0
    acc5["pass"] = ok5

    # per-row quantities
    q = {}
    for m in R_MODELS:
        for ce in CELLS:
            q[f"F1_{m}_{cell(*ce)}"] = np.where(sc, c[f"{m}_f1_{cell(*ce)}"], np.nan)
    for ce in CELLS:
        q[f"G_{cell(*ce)}"] = q[f"F1_cmax_{cell(*ce)}"] - q[f"F1_static_{cell(*ce)}"]
        q[f"cmax_minus_uniform_{cell(*ce)}"] = q[f"F1_cmax_{cell(*ce)}"] - q[f"F1_uniform_{cell(*ce)}"]
    q["cmax_precision"] = np.where(sc, c["cmax_precision"], np.nan)
    q["cmax_recall"] = np.where(sc, c["cmax_recall"], np.nan)
    q["cmax_npred_over_nfuture"] = np.where(sc, c["cmax_n_pred"] / c["n_future"], np.nan)
    names = list(q)
    strata = [(g, s, o) for g in GROUPS for s in SPEEDS for o in OVERLAPS]
    sk = {st: i for i, st in enumerate(strata)}
    val, cnt = per_rec(c, q, names, ids, [sc & (lead == li) for li in range(4)], strata, set())
    np.savez_compressed(res / "per_recording.npz", values=val, n_scored_rows=cnt, recording_ids=np.array(ids),
                        lighting=np.array([light[r] for r in ids]), leads_ms=np.array(LEADS),
                        strata=np.array(["|".join(s) for s in strata]), quantities=np.array(names),
                        note=np.array("Stage R. values[r, lead, stratum, quantity]: median over the scored rows of "
                                      "recording r at that lead (T1 = 100 ms) and stratum (group|speed|overlap). "
                                      "F1_<model>_s<block px>_k<time bins>; G = F1 cmax - F1 static per row. "
                                      "n_scored_rows[r, lead, stratum]."))
    qi = {n: j for j, n in enumerate(names)}

    def E(ld, st, name, L):
        li = LEADS.index(ld); rs = rsel(L)
        return boot(val[rs, li, sk[st], qi[name]], cnt[rs, li, sk[st]], MIN_R)

    LB = ("day", "night")
    hc, fc = cell(*HEAD), cell(*FRAME)
    T = {}
    t1q = [f"F1_{m}_{hc}" for m in R_MODELS] + [f"G_{hc}", f"cmax_minus_uniform_{hc}", "cmax_precision",
                                                 "cmax_recall", "cmax_npred_over_nfuture"] + \
        [f"F1_{m}_{fc}" for m in R_MODELS]
    T["1_headline_H_D0"] = {L: {n: E("0", H, n, L) for n in t1q} for L in LB}
    T["2_grid_H_D0"] = {L: {f"{m}|{cell(*ce)}": E("0", H, f"F1_{m}_{cell(*ce)}", L)
                            for m in ("cmax", "static", "uniform") for ce in CELLS} for L in LB}
    T["3_lead_H"] = {ld: {L: {n: E(ld, H, n, L) for n in [f"F1_{m}_{x}" for x in (hc, fc) for m in R_MODELS]
                              + [f"G_{hc}", f"G_{fc}"]} for L in LB} for ld in LEADS}
    T["4_speed_class_isolated_D0"] = {
        f"{g}|{s}": {L: {n: E("0", (g, s, "isolated"), n, L) for n in (f"G_{hc}", f"F1_cmax_{hc}", f"F1_static_{hc}")}
                     for L in LB} for g in ("vehicles", "other") for s in ("0-20", "20-100", "100-300", "300-inf")}
    T["5_overlap_D0"] = {nm: {L: {n: E("0", st, n, L) for n in t1q} for L in LB}
                         for nm, st in (("H_isolated", H), ("H_overlapping", ("vehicles", "20-300", "overlapping")))}
    t6 = {}
    for li, ld in enumerate(LEADS):
        for L in LB:
            for g in ("vehicles", "other"):
                mm = (lead == li) & (c["lighting"] == L) & (c["group"] == g)
                r_, n_ = np.unique(c["skip"][mm], return_counts=True)
                t6.setdefault(ld, {})[f"{L}|{g}"] = {"rows": int(mm.sum()), **{("scored" if k == "" else str(k)): int(v)
                                                                               for k, v in zip(r_, n_)}}
    T["6_skips"] = t6
    dd, dn = T["1_headline_H_D0"]["day"], T["1_headline_H_D0"]["night"]
    f1d, f1n = dd[f"F1_cmax_{hc}"]["median"], dn[f"F1_cmax_{hc}"]["median"]
    gd, gn = dd[f"G_{hc}"]["median"], dn[f"G_{hc}"]["median"]
    ud, un = dd[f"cmax_minus_uniform_{hc}"]["median"], dn[f"cmax_minus_uniform_{hc}"]["median"]
    if None in (f1d, f1n, gd, gn, ud, un):
        outcome = "UNDEFINED"
    elif f1d >= 0.50 and f1n >= 0.50 and gd >= 0.10 and gn >= 0.10:
        outcome = "GO"
    elif (gd < 0.03 and gn < 0.03) or (ud < 0.10 and un < 0.10):
        outcome = "NO-GO"
    else:
        outcome = "INTERMEDIATE"
    decision = {"F1_cmax": {"day": f1d, "night": f1n}, "G": {"day": gd, "night": gn},
                "F1_cmax_minus_F1_uniform": {"day": ud, "night": un}, "outcome": outcome,
                "cell": "2 px, k = 3 (11.1 ms)", "stratum": "H, D = 0"}

    # ============================================================== Stage B
    b, files_b = load(rg / "B")
    sub = json.loads((rg / "b_plan.json").read_text())
    bsc = (b["b4_skip"] == "") & (b["b6_skip"] == "")
    acc6 = {"n_subsample": sub["n_subsample"], "n_rows": int(len(b["setting"])), "n_scored_both": int(bsc.sum()),
            "by_model": {}}
    ok6 = acc6["n_rows"] == sub["n_subsample"] == acc6["n_scored_both"]
    for m in B_MODELS:
        d = {}
        for qn in ("gain_bits", "eps", "b_px"):
            err = np.abs(b[f"b4_{m}_{qn}"] - b[f"mp_{m}_{qn}"])
            d[qn] = {"max_abs_diff": float(np.nanmax(err)), "n_over_1e-9": int((~(err <= 1e-9)).sum())}
            ok6 &= d[qn]["n_over_1e-9"] == 0
        acc6["by_model"][m] = d
    acc6["pass"] = bool(ok6)
    qb = {}
    for S in ("b4", "b6"):
        qb[f"Delta_{S}"] = b[f"{S}_cmax_gain_bits"] - b[f"{S}_static_gain_bits"]
        for m in B_MODELS:
            for qn in ("gain_bits", "eps", "b_px"):
                qb[f"{m}_{qn}_{S}"] = b[f"{S}_{m}_{qn}"]
    qb["Delta_b6_minus_b4"] = qb["Delta_b6"] - qb["Delta_b4"]
    for m in B_MODELS:
        qb[f"{m}_gain_b6_minus_b4"] = qb[f"{m}_gain_bits_b6"] - qb[f"{m}_gain_bits_b4"]
        qb[f"{m}_share_b_px_4"] = (np.abs(b[f"b6_{m}_b_px"] - 4.0) < 1e-12).astype(float)
        n = b["b6_n_future"]
        for bw in B6:
            qb[f"{m}_fixed_gain_{bw:g}"] = b[f"b6_{m}_ref_bits"] - b[f"b6_{m}_bits_b_{bw:g}"] - 0.5 * np.log2(n) / n
            qb[f"{m}_eps_b_{bw:g}"] = b[f"b6_{m}_eps_b_{bw:g}"]
    bnames = list(qb)
    bstr = [H]
    bshares = {f"{m}_share_b_px_4" for m in B_MODELS}
    bval, bcnt = per_rec(b, qb, bnames, ids, [bsc], bstr, bshares)
    bqi = {n: j for j, n in enumerate(bnames)}
    EB = lambda name, L: boot(bval[rsel(L), 0, 0, bqi[name]], bcnt[rsel(L), 0, 0], MIN_B)
    t7 = {L: {n: EB(n, L) for n in bnames} for L in LB}
    t7_pooled_share = {L: {f"{m}_share_b_px_4": float(qb[f"{m}_share_b_px_4"][bsc & (b["lighting"] == L)].mean())
                           for m in B_MODELS} for L in LB}
    bandwidth = {"directive": "002", "stage": "B", "subsample_rule": sub["rule"], "n_H_rows": sub["n_H_rows"],
                 "n_subsample": sub["n_subsample"], "B4": list(RR.B4), "B6": list(B6), "min_rows_per_recording": MIN_B,
                 "fixed_bandwidth_gain": "ref_bits - bits_b - 0.5 log2(N) / N, N = n_future",
                 "table_7": t7, "pooled_share_b_px_4": t7_pooled_share,
                 "per_recording": {r: {"n_rows": int(bcnt[i, 0, 0]),
                                       **{n: (None if not np.isfinite(bval[i, 0, 0, j]) else float(bval[i, 0, 0, j]))
                                          for j, n in enumerate(bnames)}}
                                   for i, r in enumerate(ids) if bcnt[i, 0, 0] > 0}}
    (res / "bandwidth.json").write_text(json.dumps(bandwidth, indent=1) + "\n")
    T["7_stage_B_H_D0"] = {"see": "bandwidth.json#/table_7", **t7}

    report = {"directive": "002", "decision_rule": decision,
              "acceptance": {"3_rows_scored_or_skipped": acc3, "4_n_future_and_support_equal_001": acc4,
                             "5_f1_range_and_monotone": acc5, "6_stage_B_B4_reproduces_001": acc6},
              "aggregation": {"unit": "recording", "min_rows_stage_R": MIN_R, "min_rows_stage_B": MIN_B,
                              "n_boot": N_BOOT, "seed": SEED, "differences": "formed per row, then aggregated",
                              "H": "vehicles, isolated, speed_label in [20, 300) px/s", "headline_cell": hc,
                              "frame_cell": fc},
              "tables": T}
    (res / "report.json").write_text(json.dumps(report, indent=1, allow_nan=False) + "\n")
    tasks_r = [json.loads(f.read_text()) for f in sorted((rg / "R").glob("task_*.json"))]
    tasks_b = [json.loads(f.read_text()) for f in sorted((rg / "B").glob("task_*.json"))]
    prov = {"directive": "002", "host": socket.gethostname(),
            "commit": {"R": json.loads((rg / "R" / "plan.json").read_text())["commit"],
                       "B": json.loads((rg / "B" / "plan.json").read_text())["commit"]},
            "implementation": "reference ec.regen.evaluate_regen and ec.motion.evaluate_instant, unchanged",
            "versions": json.loads((rg / "preflight_p12.json").read_text())["P1"],
            "workers": a.workers, "wall_s": {"R": a.wall_r, "B": a.wall_b},
            "cpu_h": {"R_tasks": sum(t["wall_s"] for t in tasks_r) / 3600,
                      "R_evaluate_regen": float(np.nansum(c["elapsed_s"])) / 3600,
                      "B_tasks": sum(t["wall_s"] for t in tasks_b) / 3600,
                      "B_evaluate_instant": float(np.nansum(b["b4_elapsed_s"]) + np.nansum(b["b6_elapsed_s"])) / 3600},
            "per_row_files": {"R": files_r, "B": files_b}}
    (res / "provenance.json").write_text(json.dumps(prov, indent=1) + "\n")
    print(json.dumps({"decision": decision, "acc3": acc3["pass"], "acc4": acc4["pass"], "acc5": acc5["pass"],
                      "acc6": acc6["pass"], "cpu_h": prov["cpu_h"]}, indent=1))


if __name__ == "__main__":
    main()
