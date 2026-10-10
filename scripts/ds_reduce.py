"""Directive 009, Sections 10, 11 and 14: tables, rules D-009-2 and D-009-3, acceptance checks.

  python3 scripts/ds_reduce.py DSDIR RESULTS_DIR

Layout of results/bk/report.json, with the strata of Section 7 in place of day and night: ``all``
(every sequence) and one stratum per location (the name up to its first digit) with at least five
entering sequences. Unit: the sequence; it enters with at least 10 groups at S = 30, 5 at 60, 3 at
90. Median over sequences with a 95% interval from 2000 bootstrap resamples (seed 20261013).
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ec import blockcodec as bc, mp  # noqa: E402
import ds_run as DR  # noqa: E402
import bk_run as BK  # noqa: E402

N_BOOT, SEED = 2000, 20261013
MIN_GROUPS = {30: 10, 60: 5, 90: 3}
KS = bc.GROUPS
CFG = DR.CFG
MODELS = bc.MODELS


def location(seq):
    return re.match(r"[^0-9]*", seq).group(0)


def boot(vals, n_groups):
    v = np.asarray(vals, dtype=float)
    ng = np.asarray(n_groups)
    ok = np.isfinite(v)
    out = {"median": None, "ci95": [None, None], "n_recordings": int(ok.sum()), "n_groups": int(ng[ok].sum()),
           "n_not_a_number": int((~ok).sum())}
    if ok.any():
        x = v[ok]
        bs = np.median(x[np.random.default_rng(SEED).integers(0, len(x), size=(N_BOOT, len(x)))], axis=1)
        out.update(median=float(np.median(x)), ci95=[float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))])
    return out


def main(dsdir, resdir):
    dsdir, res = Path(dsdir), Path(resdir)
    res.mkdir(parents=True, exist_ok=True)
    S = json.loads((dsdir / "R" / "plan.json").read_text())["spacing"]
    cen = json.loads((dsdir / "census.json").read_text())["recordings"]
    fmt = json.loads((dsdir / "stageD" / "format.json").read_text())
    seqs = DR.sequences()
    groups, sums, rows_t = {}, {}, {}
    for s in seqs:
        rows = DR.load_groups(dsdir, s)
        rows_t[s] = rows
        groups[s] = [r["group"] for r in rows]
        if rows:
            sums[s] = bc.sum_groups(groups[s])
    ng = {s: len(groups[s]) for s in seqs}
    enter = [s for s in seqs if ng[s] >= MIN_GROUPS[S]]
    locs = sorted({location(s) for s in enter})
    strata = {"all": enter, **{l: [s for s in enter if location(s) == l] for l in locs
                               if sum(location(s) == l for s in enter) >= 5}}

    def agg(fn, stratum):
        ss = strata[stratum]
        vals = []
        for s in ss:
            try:
                vals.append(float(fn(s)))
            except ZeroDivisionError:
                vals.append(float("nan"))
        return boot(vals, [ng[s] for s in ss])

    summ = lambda s, model, coder, K, cfg=CFG, cell=bc.OBJECTIVE: bc.summarize(sums[s], cfg, model, coder, K, cell)

    # ============================================================== acceptance checks
    acc = {}
    n, c_false, q_false, m_bad, m_n, empty, missing = 0, 0, 0, 0, 0, 0, []
    for s in seqs:
        if [g["w"] for g in groups[s]] != DR.key_windows(cen[s]["t_first_us"], cen[s]["t_last_us"], S):
            missing.append(s)
        for g in groups[s]:
            for cfg, row in g["codec"].items():
                empty += row["n_active"] == 0
                for model, r in row["models"].items():
                    n += 1
                    c_false += not r["claim_equals_match"]
                    q_false += not r["q_equals_t"]
                    for a, b, c in zip(r["match_s2_k3"], r["n_rec"], r["match_s2_k1"]):
                        m_n += 1
                        m_bad += not (0 <= a <= b and a <= c)
    acc["6_claim_and_q"] = {"n": n, "claim_equals_match_false": c_false, "q_equals_t_false": q_false,
                            "match_bounds_entries": m_n, "match_bounds_violations": m_bad,
                            "pass": c_false == 0 and q_false == 0 and m_bad == 0}
    acc["8_every_group"] = {"n_sequences": len(seqs), "n_groups": sum(ng.values()),
                            "sequences_with_missing_or_extra_groups": missing,
                            "group_configs_with_no_active_block": empty, "pass": not missing}
    rec = json.loads((dsdir / "R_receiver.json").read_text())
    s_bad, prov_streams = [], []
    for s in seqs:
        for model in ("affine", "translation"):
            for coder in bc.CODERS:
                for K in KS:
                    name = f"{s}__{model}_{coder}_K{K}.ec07"
                    p = dsdir / "R_streams" / name
                    buf = p.read_bytes()
                    prov_streams.append({"path": str(p), "size": len(buf), "sha256": hashlib.sha256(buf).hexdigest()})
                    _, bad = BK.compare_streams(groups[s], rec[name], CFG, model, coder, K)
                    if bad or len(buf) != rec[name]["length"] or prov_streams[-1]["sha256"] != rec[name]["sha256"]:
                        s_bad.append({"stream": name, "failures": bad})
    acc["7_streams_R"] = {"n_streams": len(prov_streams), "n_failing": len(s_bad), "failing": s_bad, "pass": not s_bad}

    T = {}
    # ============================================================== Table 1
    inv = fmt["inventory"]
    T["1_inventory"] = {"per_sequence": inv, "totals": {
        "n_sequences": len(inv), "n_events": int(sum(v["n_events"] for v in inv.values())),
        "duration_s": float(sum(v["duration_s"] for v in inv.values())),
        "median_events_per_pixel_and_window": float(np.median([v["events_per_pixel_and_window"] for v in inv.values()])),
        "time_inversions_clamped": int(sum(v["n_time_inversions_clamped"] for v in inv.values()))}}
    # ============================================================== Tables 2, 3
    ql = ("F", "bits", "bits_direct", "bits_base", "bits_thin", "gain", "gain_thin")
    t2, t3 = {}, {}
    for coder in ("Q", "T"):
        for st in strata:
            for K in KS:
                for model in MODELS:
                    d = {q: agg(lambda s, q=q: summ(s, model, coder, K)[q], st) for q in ql}
                    d["gain_over_gain_static"] = agg(lambda s: summ(s, model, coder, K)["gain"]
                                                     / summ(s, "static", coder, K)["gain"], st)
                    d["gain_over_gain_translation"] = agg(lambda s: summ(s, model, coder, K)["gain"]
                                                          / summ(s, "translation", coder, K)["gain"], st)
                    t2.setdefault(coder, {}).setdefault(st, {}).setdefault(f"K{K}", {})[model] = d
                    if coder == "Q":
                        t3.setdefault(st, {}).setdefault(f"K{K}", {})[model] = {
                            q: agg(lambda s, q=q: summ(s, model, coder, K)[q], st) for q in ("share", "gamma")}
    T["2_headline"] = t2
    T["3_events"] = t3
    # ============================================================== Table 4
    t4 = {}
    for rho in bc.DENSITIES:
        cfg = f"B20_rho{float(rho)}"
        for st in strata:
            for K in (4, 11):
                t4.setdefault(cfg, {}).setdefault(st, {})[f"K{K}"] = {
                    **{q: agg(lambda s, q=q: summ(s, "affine", "Q", K, cfg)[q], st) for q in ("F", "bits", "gain")},
                    "active_blocks_per_group": agg(lambda s: sums[s]["codec"][cfg]["n_active"] / ng[s], st),
                    "share_key_window_events_that_are_key_events":
                        agg(lambda s: sums[s]["codec"][cfg]["n_key"] / sums[s]["n_true"][0], st)}
    T["4_thresholds"] = t4
    # ============================================================== Table 5
    t5 = {}
    for st in strata:
        d = {"key_window_2nkey_over_nkey_plus_ntrue":
             agg(lambda s: 2 * sums[s]["codec"][CFG]["n_key"] / (sums[s]["codec"][CFG]["n_key"] + sums[s]["n_true"][0]), st)}
        for model in MODELS:
            for cell in ("s2_k3", "s2_k1"):
                for m in range(1, 11):
                    d[f"{model}_{cell}_m{m}"] = agg(lambda s, m=m: 2 * sums[s]["codec"][CFG]["models"][model][f"match_{cell}"][m - 1]
                                                    / (sums[s]["codec"][CFG]["models"][model]["n_rec"][m - 1]
                                                       + sums[s]["n_true"][m]), st)
            for m in (1, 4, 10):
                d[f"{model}_nrec_over_ntrue_m{m}"] = agg(lambda s, m=m: sums[s]["codec"][CFG]["models"][model]["n_rec"][m - 1]
                                                         / sums[s]["n_true"][m], st)
        for m in (1, 4, 10):
            d[f"share_true_in_active_m{m}"] = agg(lambda s, m=m: sums[s]["codec"][CFG]["n_true_in_active"][m]
                                                  / sums[s]["n_true"][m], st)
        t5[st] = d
    T["5_windows"] = t5
    # ============================================================== Table 6
    T["6_grids"] = {st: {f"s{s_}_k{k}": {q: agg(lambda s, q=q, s_=s_, k=k: summ(s, "affine", "T", 4, CFG, (s_, k))[q], st)
                                         for q in ("F", "gain", "gain_thin")} for s_, k in bc.CELLS_ALL} for st in strata}
    # ============================================================== Table 7
    t7 = {}
    for st in strata:
        for model in ("affine", "translation"):
            for coder in bc.CODERS:
                for K in KS:
                    kk = f"{coder}_K{K}"
                    t7.setdefault(st, {}).setdefault(model, {})[kk] = {
                        "bytes_per_group": agg(lambda s: sums[s]["codec"][CFG]["models"][model]["bytes"][kk] / ng[s], st),
                        "share_map_payload": agg(lambda s: 1 - sums[s]["codec"][CFG]["models"]["static"]["bytes"][kk]
                                                 / sums[s]["codec"][CFG]["models"][model]["bytes"][kk], st),
                        "share_header_in_stream": agg(lambda s: 28 / (28 + sums[s]["codec"][CFG]["models"][model]["bytes"][kk]), st)}
    T["7_bytes"] = t7
    # ============================================================== Table 8
    t8 = {}
    for st in strata:
        for coder in bc.CODERS:
            n11 = lambda s: float(np.sum(sums[s]["n_true"]))
            d = {"direct": agg(lambda s: np.sum(sums[s]["direct"][coder]) / n11(s), st)}
            for chi in bc.THIN_SHARES:
                d[f"thin_{chi}"] = {"bits": agg(lambda s, c=chi: np.sum(sums[s]["thin"][str(c)][coder]) / n11(s), st),
                                    "share": agg(lambda s, c=chi: np.sum(sums[s]["thin"][str(c)]["n_kept"]) / n11(s), st)}
            for rho in bc.DENSITIES:
                cfg = f"B20_rho{float(rho)}"
                d[f"select_{cfg}"] = {"bits": agg(lambda s, c=cfg: np.sum(sums[s]["select"][c][coder]) / n11(s), st),
                                      "share": agg(lambda s, c=cfg: np.sum(sums[s]["select"][c]["n_kept"]) / n11(s), st)}
            t8.setdefault(st, {})[coder] = d
    T["8_baselines"] = t8
    # ============================================================== Table 9 (census, B = 20, key windows at S)
    nblk = (DR.W // 20) * (DR.H // 20)
    t9 = {}
    for st, ss in {"all": seqs, **{l: [s for s in seqs if location(s) == l] for l in strata if l != "all"}}.items():
        for i, rho in enumerate(bc.DENSITIES):
            v = np.array([np.mean([g["20"][i] for g in DR.groups_at(cen[s], S)]) for s in ss if DR.groups_at(cen[s], S)])
            t9.setdefault(st, {})[f"B20_rho{float(rho)}"] = {
                "mean_active_blocks_per_key_window": {str(x): float(np.quantile(v, x)) for x in (0.1, 0.5, 0.9)},
                "as_share_of_all_blocks": {str(x): float(np.quantile(v, x)) / nblk for x in (0.1, 0.5, 0.9)},
                "n_sequences": int(len(v)), "n_blocks_sensor": nblk}
    T["9_census"] = t9
    # ============================================================== Table 10: maps of the decoded affine streams
    disp = {m: [] for m in (1, 4, 10)}
    shape_nz = {m: [] for m in (1, 4, 10)}
    for s in seqs:
        buf = (dsdir / "R_streams" / f"{s}__affine_Q_K11.ec07").read_bytes()
        _, gs = bc.decode_stream(buf)
        for g in gs:
            mps = g["maps"]                       # (blocks, 10, 6)
            for m in (1, 4, 10):
                if len(mps):
                    disp[m].append(np.hypot(mps[:, m - 1, 0], mps[:, m - 1, 1]))
                    shape_nz[m].append((mps[:, m - 1, 2:] != 0).any(axis=1))
    t10 = {}
    for m in (1, 4, 10):
        dv = np.concatenate(disp[m]) if disp[m] else np.zeros(0)
        sv = np.concatenate(shape_nz[m]) if shape_nz[m] else np.zeros(0, bool)
        t10[f"m{m}"] = {"n_blocks": int(len(dv)),
                        "displacement_px_quantiles": {str(x): float(np.quantile(dv, x)) for x in (0.1, 0.5, 0.9)} if len(dv) else None,
                        "share_blocks_nonzero_shape": float(sv.mean()) if len(sv) else None}
    T["10_maps"] = {"source": "decoded streams affine_Q_K11 of every sequence (frozen configuration)", **t10}
    # ============================================================== Table 11: next to eTraM (copied)
    ref = mp.REPO / "results" / "bk" / "report.json"
    bk = json.loads(ref.read_text())["tables"]["2_headline"]["Q"] if ref.exists() else None
    T["11_next_to_etram"] = {
        "dsec_all": {f"K{K}": {m: {q: t2["Q"]["all"][f"K{K}"][m][q]["median"] for q in ql}
                               for m in ("affine", "translation")} for K in (4, 11)},
        "etram_copied_from_report_007": ({L: {f"K{K}": {m: {q: bk[L][f"K{K}"][m][q]["median"] for q in ql}
                                                        for m in ("affine", "translation")} for K in (4, 11)}
                                          for L in ("day", "night")} if bk else None),
        "note": "eTraM rows copied from results/bk/report.json (report 007, Table 2), coder Q; not computed here"}
    # ============================================================== Table 12: fit and checks
    wall = [r["evaluate_group_s"] for s in seqs for r in rows_t[s]]
    pg = {m: [] for m in MODELS}
    pb = {m: [] for m in MODELS}
    for s in seqs:
        for r in rows_t[s]:
            for B, fm in r["group"]["fit"].items():
                for m, f in fm.items():
                    pg[m].append(f["n_eval"])
                    if f["n_blocks"] > 0:
                        pb[m].append(f["n_eval"] / f["n_blocks"] / bc.N_TARGETS)
    qs = lambda v: {str(x): float(np.quantile(v, x)) for x in (0.1, 0.5, 0.9)} if len(v) else None
    T["12_fit_and_checks"] = {"scored_maps_per_group": {m: qs(v) for m, v in pg.items()},
                              "scored_maps_per_block_and_target": {m: qs(v) for m, v in pb.items()},
                              "wall_s_per_group": (qs(wall) or {}) | {"mean": float(np.mean(wall)),
                                                                     "sum_cpu_h": float(np.sum(wall)) / 3600},
                              "n_groups": len(wall), "checks": acc}

    # ============================================================== rules
    g4 = {m: t2["Q"]["all"]["K4"][m]["gain"]["median"] for m in ("affine", "translation")}
    best = max(g4, key=g4.get)
    ratio = t2["Q"]["all"]["K4"][best]["gain_over_gain_static"]["median"]
    replicated = g4[best] >= 1.25 and ratio >= 1.10
    d2 = {"gain_K4": g4, "better_model": best, "gain_over_gain_static_K4_of_better": ratio,
          "outcome": "REPLICATED" if replicated else "NOT REPLICATED"}
    d3 = {"gain_translation_K4": g4["translation"], "gain_affine_K4": g4["affine"],
          "outcome": "translation per block" if g4["translation"] > g4["affine"] else "affine map"}
    report = {"directive": "009", "spacing": S, "frozen": CFG, "strata": {k: len(v) for k, v in strata.items()},
              "recordings_entering": len(enter), "recordings_below_min_groups": [s for s in seqs if s not in enter],
              "decision_rule": {"D-009-2": d2, "D-009-3": d3}, "acceptance": acc,
              "aggregation": {"unit": "sequence", "min_groups": MIN_GROUPS[S], "n_boot": N_BOOT, "seed": SEED,
                              "ratios": "formed per sequence from its sums, then the median over sequences"},
              "tables": T}
    (res / "report.json").write_text(json.dumps(report, indent=1, allow_nan=False, default=float) + "\n")
    (res / "per_recording.json").write_text(json.dumps({s: sums[s] for s in sorted(sums)}, default=float) + "\n")
    (res / "streams_provenance.json").write_text(json.dumps(prov_streams) + "\n")
    print(json.dumps({"decision": report["decision_rule"], "acc": {k: v["pass"] for k, v in acc.items()},
                      "strata": report["strata"]}, indent=1, default=float))


if __name__ == "__main__":
    main(*sys.argv[1:3])
