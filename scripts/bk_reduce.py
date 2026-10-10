"""Directive 007, Sections 10, 12 and 13: tables, rule D-007-6 and acceptance checks 4 to 8.

  python3 scripts/bk_reduce.py BKDIR RESULTS_DIR

Unit: the recording. Its groups are added with ``ec.blockcodec.sum_groups`` and every quantity is
computed from the sums (``summarize`` where it has it). A recording enters with at least 10 groups
(S = 90). An entry is the median over recordings, by lighting, with a 95% interval from 2000
bootstrap resamples of recordings (seed 20261012) and the numbers of recordings and of groups. A
recording whose value is not a number is left out of that entry and counted.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ec import blockcodec as bc, mp  # noqa: E402
import bk_run as R  # noqa: E402

N_BOOT, SEED = 2000, 20261012
MIN_GROUPS = {90: 10, 180: 5, 360: 3}
LB = ("day", "night")
KS = bc.GROUPS


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


def main(bkdir, resdir):
    bkdir, res = Path(bkdir), Path(resdir)
    res.mkdir(parents=True, exist_ok=True)
    plan_r = json.loads((bkdir / "R" / "plan.json").read_text())
    S = plan_r["spacing"]
    Bs, rhos = plan_r["frozen"]
    Bs = int(Bs)
    FROZEN = f"B{Bs}_rho{float(rhos)}"
    tuning_json = json.loads((bkdir / "tuning.json").read_text())
    cen = json.loads((bkdir / "census.json").read_text())["recordings"]
    _, reporting = R.subsets()
    light = {r: mp.lighting(r) for r in reporting}

    groups, sums, times = {}, {}, {}
    for rid in reporting:
        rows = R.load_groups("R", bkdir, rid)
        groups[rid] = [r["group"] for r in rows]
        times[rid] = rows
        if rows:
            sums[rid] = bc.sum_groups(groups[rid])
    enter = [r for r in reporting if len(groups[r]) >= MIN_GROUPS[S]]
    ng = {r: len(groups[r]) for r in reporting}

    def agg(fn, L):
        rs = [r for r in enter if light[r] == L]
        vals = []
        for r in rs:
            try:
                vals.append(float(fn(r)))
            except ZeroDivisionError:
                vals.append(float("nan"))
        return boot(vals, [ng[r] for r in rs])

    summ = lambda r, model, coder, K, cfg=FROZEN, cell=bc.OBJECTIVE: bc.summarize(sums[r], cfg, model, coder, K, cell)

    # ============================================================== acceptance checks 4, 5, 7, 8
    acc = {"4_claim_equals_match": {}, "5_q_equals_t": {}, "7_match_bounds": {}, "8_every_group": {}}
    for stage in ("T", "R"):
        tun, rep = R.subsets()
        ids = tun if stage == "T" else rep
        n, c_false, q_false, m_bad, m_n, empty = 0, 0, 0, 0, 0, 0
        missing = []
        for rid in ids:
            gs = [r["group"] for r in R.load_groups(stage, bkdir, rid)]
            exp_ws = R.key_windows(cen[rid]["t_last_us"], S)
            if [g["w"] for g in gs] != exp_ws:
                missing.append(rid)
            for g in gs:
                for cfg, row in g["codec"].items():
                    if row["n_active"] == 0:
                        empty += 1
                    for model, r in row["models"].items():
                        n += 1
                        c_false += not r["claim_equals_match"]
                        q_false += not r["q_equals_t"]
                        for a, b, c in zip(r["match_s2_k3"], r["n_rec"], r["match_s2_k1"]):
                            m_n += 1
                            m_bad += not (0 <= a <= b and a <= c)
        acc["4_claim_equals_match"][stage] = {"n": n, "n_false": c_false}
        acc["5_q_equals_t"][stage] = {"n": n, "n_false": q_false}
        acc["7_match_bounds"][stage] = {"n_group_config_model_target": m_n, "n_violations": m_bad}
        acc["8_every_group"][stage] = {"recordings": len(ids), "recordings_with_missing_or_extra_groups": missing,
                                       "n_groups": sum(len(R.key_windows(cen[r]["t_last_us"], S)) for r in ids),
                                       "n_group_configs_with_no_active_block": empty}
    for k in ("4_claim_equals_match", "5_q_equals_t"):
        acc[k]["pass"] = all(v["n_false"] == 0 for s, v in acc[k].items() if s in ("T", "R"))
    acc["7_match_bounds"]["pass"] = all(v["n_violations"] == 0 for s, v in acc["7_match_bounds"].items() if s in ("T", "R"))
    acc["8_every_group"]["pass"] = all(not v["recordings_with_missing_or_extra_groups"]
                                       for s, v in acc["8_every_group"].items() if s in ("T", "R"))
    # acceptance 6: streams of Stage R
    rec = json.loads((bkdir / "R_receiver.json").read_text())
    s_bad, s_n, prov_streams = [], 0, []
    for rid in reporting:
        for coder in bc.CODERS:
            for K in KS:
                name = f"{rid}__affine_{coder}_K{K}.ec07"
                p = bkdir / "R_streams" / name
                buf = p.read_bytes()
                prov_streams.append({"path": str(p), "size": len(buf), "sha256": hashlib.sha256(buf).hexdigest()})
                exp_len, bad = R.compare_streams(groups[rid], rec[name], FROZEN, "affine", coder, K)
                s_n += 1
                if bad or len(buf) != rec[name]["length"] or prov_streams[-1]["sha256"] != rec[name]["sha256"]:
                    s_bad.append({"stream": name, "failures": bad})
    acc["6_streams_R"] = {"n_streams": s_n, "n_failing": len(s_bad), "failing": s_bad, "pass": not s_bad}

    T = {}
    # ============================================================== Table 1
    T["1_tuning"] = {"table": tuning_json["table"], "frozen": tuning_json["frozen"],
                     "recordings_entering": tuning_json["recordings_entering"]}
    # ============================================================== Table 2 and 3
    q_list = ("F", "bits", "bits_direct", "bits_base", "bits_thin", "gain", "gain_thin")
    t2, t3 = {}, {}
    for coder in ("Q", "T"):
        for L in LB:
            for K in KS:
                for model in bc.MODELS:
                    d = {q: agg(lambda r, q=q: summ(r, model, coder, K)[q], L) for q in q_list}
                    d["gain_over_gain_static"] = agg(lambda r: summ(r, model, coder, K)["gain"]
                                                     / summ(r, "static", coder, K)["gain"], L)
                    t2.setdefault(coder, {}).setdefault(L, {}).setdefault(f"K{K}", {})[model] = d
                    if coder == "Q":
                        t3.setdefault(L, {}).setdefault(f"K{K}", {})[model] = {
                            q: agg(lambda r, q=q: summ(r, model, coder, K)[q], L) for q in ("share", "gamma")}
    gp = json.loads((mp.REPO / "results" / "gp" / "report.json").read_text())["tables"]["1_headline_H"]["headline"] \
        if (mp.REPO / "results" / "gp" / "report.json").exists() else None
    af = json.loads((mp.REPO / "results" / "af" / "report.json").read_text())["tables"]["1_headline_H"]["headline"] \
        if (mp.REPO / "results" / "af" / "report.json").exists() else None
    T["2_headline"] = t2
    T["3_events"] = {"block_codec": t3, "copied_from_reports_on_annotated_boxes": {
        "note": "stratum H, headline cell; copied from report 003 Table 1 (aligned) and report 004 Table 1 (affine)",
        "gamma_aligned_003": {L: {f"K{K}": gp[L][f"K{K}"]["aligned_gamma"]["median"] for K in KS} for L in LB} if gp else None,
        "gamma_affine_004": {L: {f"K{K}": af[L][f"K{K}"]["gamma_affine"]["median"] for K in KS} for L in LB} if af else None}}
    # ============================================================== Table 4
    t4 = {}
    for rho in bc.DENSITIES:
        cfg = f"B{Bs}_rho{float(rho)}"
        for L in LB:
            for K in (4, 11):
                t4.setdefault(cfg, {}).setdefault(L, {})[f"K{K}"] = {
                    **{q: agg(lambda r, q=q: summ(r, "affine", "Q", K, cfg)[q], L) for q in ("F", "bits", "gain")},
                    "active_blocks_per_group": agg(lambda r: sums[r]["codec"][cfg]["n_active"] / ng[r], L),
                    "share_key_window_events_that_are_key_events":
                        agg(lambda r: sums[r]["codec"][cfg]["n_key"] / sums[r]["n_true"][0], L)}
    T["4_thresholds"] = t4
    # ============================================================== Table 5
    t5 = {}
    for L in LB:
        d = {"key_window_2nkey_over_nkey_plus_ntrue":
             agg(lambda r: 2 * sums[r]["codec"][FROZEN]["n_key"] / (sums[r]["codec"][FROZEN]["n_key"] + sums[r]["n_true"][0]), L)}
        for model in bc.MODELS:
            for cell in ("s2_k3", "s2_k1"):
                for m in range(1, 11):
                    d[f"{model}_{cell}_m{m}"] = agg(lambda r, m=m: 2 * sums[r]["codec"][FROZEN]["models"][model][f"match_{cell}"][m - 1]
                                                    / (sums[r]["codec"][FROZEN]["models"][model]["n_rec"][m - 1]
                                                       + sums[r]["n_true"][m]), L)
            for m in (1, 4, 10):
                d[f"{model}_nrec_over_ntrue_m{m}"] = agg(lambda r, m=m: sums[r]["codec"][FROZEN]["models"][model]["n_rec"][m - 1]
                                                         / sums[r]["n_true"][m], L)
        for m in (1, 4, 10):
            d[f"share_true_in_active_m{m}"] = agg(lambda r, m=m: sums[r]["codec"][FROZEN]["n_true_in_active"][m]
                                                  / sums[r]["n_true"][m], L)
        t5[L] = d
    T["5_windows"] = t5
    # ============================================================== Table 6
    T["6_grids"] = {L: {f"s{s}_k{k}": {q: agg(lambda r, q=q, s=s, k=k: summ(r, "affine", "T", 4, FROZEN, (s, k))[q], L)
                                       for q in ("F", "gain", "gain_thin")} for s, k in bc.CELLS_ALL} for L in LB}
    # ============================================================== Table 7
    t7 = {}
    for L in LB:
        for coder in bc.CODERS:
            for K in KS:
                kk = f"{coder}_K{K}"
                t7.setdefault(L, {})[kk] = {
                    "bytes_per_group": agg(lambda r: sums[r]["codec"][FROZEN]["models"]["affine"]["bytes"][kk] / ng[r], L),
                    "share_map_payload": agg(lambda r: 1 - sums[r]["codec"][FROZEN]["models"]["static"]["bytes"][kk]
                                             / sums[r]["codec"][FROZEN]["models"]["affine"]["bytes"][kk], L),
                    "share_header_in_stream": agg(lambda r: 28 / (28 + sums[r]["codec"][FROZEN]["models"]["affine"]["bytes"][kk]), L)}
    T["7_bytes"] = t7
    # ============================================================== Table 8
    t8 = {}
    for L in LB:
        for coder in bc.CODERS:
            n11 = lambda r: float(np.sum(sums[r]["n_true"]))
            d = {"direct": agg(lambda r: np.sum(sums[r]["direct"][coder]) / n11(r), L)}
            for chi in bc.THIN_SHARES:
                d[f"thin_{chi}"] = {"bits": agg(lambda r, c=chi: np.sum(sums[r]["thin"][str(c)][coder]) / n11(r), L),
                                    "share": agg(lambda r, c=chi: np.sum(sums[r]["thin"][str(c)]["n_kept"]) / n11(r), L)}
            for rho in bc.DENSITIES:
                cfg = f"B{Bs}_rho{float(rho)}"
                d[f"select_{cfg}"] = {"bits": agg(lambda r, c=cfg: np.sum(sums[r]["select"][c][coder]) / n11(r), L),
                                      "share": agg(lambda r, c=cfg: np.sum(sums[r]["select"][c]["n_kept"]) / n11(r), L)}
            t8.setdefault(L, {})[coder] = d
    T["8_baselines"] = t8
    # ============================================================== Table 9 (census, all 112 recordings, key windows at S)
    t9, nblk = {}, {B: (-(-1280 // B)) * (-(-720 // B)) for B in bc.BLOCKS}
    for L in LB:
        for B in bc.BLOCKS:
            for i, rho in enumerate(bc.DENSITIES):
                v = []
                for rid, c in cen.items():
                    if mp.lighting(rid) != L:
                        continue
                    gs = R.groups_at(c, S)
                    if gs:
                        v.append(float(np.mean([g[str(B)][i] for g in gs])))
                v = np.array(v)
                t9.setdefault(L, {})[f"B{B}_rho{float(rho)}"] = {
                    "mean_active_blocks_per_key_window": {str(x): float(np.quantile(v, x)) for x in (0.1, 0.5, 0.9)},
                    "as_share_of_all_blocks": {str(x): float(np.quantile(v, x)) / nblk[B] for x in (0.1, 0.5, 0.9)},
                    "n_recordings": int(len(v)), "n_blocks_sensor": nblk[B]}
    T["9_census"] = t9
    # ============================================================== Table 10
    t10 = {}
    for stage, ids in (("T", R.subsets()[0]), ("R", reporting)):
        per_group = {m: [] for m in bc.MODELS}
        per_block = {m: [] for m in bc.MODELS}
        wall = []
        for rid in ids:
            for row in R.load_groups(stage, bkdir, rid):
                wall.append(row["evaluate_group_s"])
                for B, fm in row["group"]["fit"].items():
                    for m, f in fm.items():
                        per_group[m].append(f["n_eval"])
                        if f["n_blocks"] > 0:
                            per_block[m].append(f["n_eval"] / f["n_blocks"] / bc.N_TARGETS)
        qs = lambda v: {str(x): float(np.quantile(v, x)) for x in (0.1, 0.5, 0.9)} if len(v) else None
        t10[stage] = {"scored_maps_per_group_and_block_side": {m: qs(v) for m, v in per_group.items()},
                      "scored_maps_per_block_and_target": {m: qs(v) for m, v in per_block.items()},
                      "wall_s_per_group": qs(wall) | {"mean": float(np.mean(wall)), "sum_cpu_h": float(np.sum(wall)) / 3600},
                      "n_groups": len(wall)}
    T["10_fit"] = t10
    T["11_checks"] = acc

    # ============================================================== rule D-007-6
    g4 = {L: t2["Q"][L]["K4"]["affine"]["gain"]["median"] for L in LB}
    ratio4 = {L: t2["Q"][L]["K4"]["affine"]["gain_over_gain_static"]["median"] for L in LB}
    gall = {L: {f"K{K}": t2["Q"][L][f"K{K}"]["affine"]["gain"]["median"] for K in KS} for L in LB}
    if all(g4[L] >= 1.25 and ratio4[L] >= 1.10 for L in LB):
        outcome = "GO"
    elif any(all(v < 1.10 for v in gall[L].values()) for L in LB):
        outcome = "NO-GO for this region scheme"
    else:
        outcome = "intermediate (reported as measured)"
    decision = {"gain_affine_K4": g4, "gain_affine_over_gain_static_K4": ratio4, "gain_affine_all_K": gall,
                "outcome": outcome, "frozen": FROZEN}
    report = {"directive": "007", "spacing": S, "frozen": FROZEN, "decision_rule": decision,
              "acceptance": acc, "recordings_entering": len(enter),
              "recordings_below_min_groups": [r for r in reporting if r not in enter],
              "aggregation": {"unit": "recording", "min_groups": MIN_GROUPS[S], "n_boot": N_BOOT, "seed": SEED,
                              "ratios": "formed per recording from its sums, then the median over recordings"},
              "tables": T}
    (res / "report.json").write_text(json.dumps(report, indent=1, allow_nan=False, default=float) + "\n")
    (res / "per_recording.json").write_text(json.dumps({r: sums[r] for r in sorted(sums)}, default=float) + "\n")
    print(json.dumps({"decision": decision, "acc": {k: v["pass"] for k, v in acc.items()}}, indent=1, default=float))
    return prov_streams


if __name__ == "__main__":
    ps = main(*sys.argv[1:3])
    Path(sys.argv[2], "streams_provenance.json").write_text(json.dumps(ps) + "\n")
