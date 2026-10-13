"""Directive 018, Section 6: Tables 1 to 4 and the frontier data, from the per-group outputs of ``scripts/fm_run.py``.

  python3 scripts/fm_reduce.py RESULTS_DIR

A recording enters with the rule of report 016 (10 groups on eTraM, 5 on DSEC). For a scheme, a recording and
K: ``b = sum bits / sum n_true[:K]``; the fidelities are ``ec.families.fidelities`` of the window sums of all its
groups; the tasks (K = 4, windows 1 to 3) as Section 6 lists them. Medians over recordings with the bootstrap of
directive 007, seed 20261016. Strata: day and night (eTraM), all (DSEC).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from scipy.stats import kendalltau

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ec import blockcodec as bc, families as fa, mp  # noqa: E402
import fb_reduce as FR  # noqa: E402
import fb_run as FB  # noqa: E402
import fm_run as FM  # noqa: E402

STRATA = {"day": "etram", "night": "etram", "all": "dsec"}
FAMILIES = ("thin", "select", "cap", "hevc", "fbc")
CANDS = ("F", "F20", "FH", "Fsnr")
SIZES = (("50_199", 50, 200), ("200_999", 200, 1000), ("1000_up", 1000, None))
TASK_KEYS = ("box_F_mean", "box_empty", "box_centroid_px", "track_continuous", "track_velocity_error_px",
             "motion_error_px", "motion_no_event")
ORIENT = {"box_F_mean": 1, "box_empty": -1, "box_centroid_px": -1, "track_continuous": 1,
          "track_velocity_error_px": -1, "motion_error_px": -1, "motion_no_event": -1}


def family(name):
    return name.split("_")[0] if name.split("_")[0] in FAMILIES else name


def nanmed(v):
    v = np.asarray(v, dtype=float)
    v = v[np.isfinite(v)]
    return float(np.median(v)) if len(v) else float("nan")


def task_scores(objs, tracks, mot):
    def boxes(sel):
        o = [x for x in objs if sel(x)]
        return {"F_mean": float(np.mean([x["F"] for x in o])) if o else float("nan"),
                "empty": float(np.mean([x["n_rec"] == 0 for x in o])) if o else float("nan"),
                "centroid_px": nanmed([x["centroid_px"] for x in o if x["n_rec"] > 0]), "n": len(o)}
    out = {}
    b = boxes(lambda x: True)
    out.update({"box_F_mean": b["F_mean"], "box_empty": b["empty"], "box_centroid_px": b["centroid_px"], "n_boxes": b["n"]})
    for lab, lo, hi in SIZES:
        bb = boxes(lambda x, lo=lo, hi=hi: x["n_true"] >= lo and (hi is None or x["n_true"] < hi))
        out.update({f"box_{lab}_{k}": v for k, v in bb.items()})
    cont = [t for t in tracks if t["continuous"]]
    out.update({"track_continuous": float(np.mean([t["continuous"] for t in tracks])) if tracks else float("nan"),
                "track_velocity_error_px": nanmed([t["velocity_error_px"] for t in cont]), "n_tracks": len(tracks),
                "motion_error_px": nanmed([m["error_px"] for m in mot]),
                "motion_no_event": float(np.mean([m["n_rec"] == 0 for m in mot])) if mot else float("nan"),
                "n_squares": len(mot)})
    return out


def per_recording(groups):
    """Per scheme and K: b, the four fidelities (all windows and windows 1 to 3), the window sums; tasks at K = 4."""
    names = list(groups[0]["schemes"])
    out = {}
    for nm in names:
        r = {}
        for K in fa.KS:
            key = f"K{K}"
            n = float(sum(sum(g["n_true"][:K]) for g in groups))
            sums = [s for g in groups for s in g["schemes"][nm][key]["sums"]]
            s13 = [s for g in groups for s in g["schemes"][nm][key]["sums"][1:4]]
            r[key] = {"b": sum(g["schemes"][nm][key]["bits"] for g in groups) / n,
                      "b_direct": sum(sum(g["direct_bits"][:K]) for g in groups) / n,
                      **fa.fidelities(sums), "w13": fa.fidelities(s13),
                      "fsnr_enter_share": sum(s["n_enter"] for s in sums) / max(1, sum(s["n_blocks"] for s in sums))}
        tk = [g["schemes"][nm]["tasks"] for g in groups]
        r["tasks"] = task_scores([o for t in tk for o in t["objects"]], [o for t in tk for o in t["tracks"]],
                                 [o for t in tk for o in t["motion"]])
        out[nm] = r
    return out


def interp_at(bq, pts):
    """Linear interpolation in b of the values of the points (b, value); NaN outside."""
    pts = sorted(pts)
    bs = [p[0] for p in pts]
    if not pts or not (bs[0] <= bq <= bs[-1]):
        return float("nan")
    for (b0, v0), (b1, v1) in zip(pts[:-1], pts[1:]):
        if b0 <= bq <= b1:
            return v0 if b1 == b0 else v0 + (v1 - v0) * (bq - b0) / (b1 - b0)
    return float(pts[0][1])


def main(resdir):
    res = Path(resdir)
    per_rec, entering, acc = {}, {}, {"remake_equals_kept": True, "outside": 0, "n_groups": 0}
    bg_rows, hevc_rows, fbc_st = {}, {}, {}
    for ds in ("etram", "dsec"):
        entering[ds] = []
        for rid in FB.recordings(ds, "R"):
            gs = FM.load(ds, rid)
            ws = [r["w"] for r in FB.remake_groups(ds, "R", rid)]
            acc["groups_equal_016"] = acc.get("groups_equal_016", True) and [g["w"] for g in gs] == ws
            for g in gs:
                acc["remake_equals_kept"] &= g["checks"]["remake_equals_kept"]
                acc["outside"] += g["checks"]["outside"]
                acc["n_groups"] += 1
            st = "all" if ds == "dsec" else mp.lighting(rid)
            bg_rows.setdefault(st, []).extend(g["background"] for g in gs)
            if len(gs) < FR.MIN_GROUPS[ds]:
                continue
            entering[ds].append(rid)
            per_rec[rid] = per_recording(gs)
            for nm in gs[0]["hevc"]:
                for K in fa.KS:
                    k = f"K{K}"
                    hevc_rows.setdefault(st, {}).setdefault(nm, {}).setdefault(k, []).append(
                        (sum(g["hevc"][nm][k]["param_sei_bits"] for g in gs),
                         sum(g["schemes"][nm][k]["bits"] for g in gs), sum(g["hevc"][nm][k]["clipped_events"] for g in gs)))
            for nm in gs[0]["schemes"]:
                if nm.startswith("fbc"):
                    fbc_st.setdefault(st, {}).setdefault(nm, []).extend(g["schemes"][nm]["K4"]["st_us"] for g in gs)
    names = fa.scheme_names()
    T = {"1_bits_at_remake_F": {}, "2_at_remake_bits_K4": {}, "3_kendall_tau_b": {}, "4_accounting": {}}
    frontier = {}
    rep016 = json.loads((mp.REPO / "results" / "fb" / "report.json").read_text())["acceptance"]["5_remake_K4_equals_reports"]
    c4 = {}
    for st, ds in STRATA.items():
        rids = [r for r in entering[ds] if ds == "dsec" or mp.lighting(r) == st]
        P = [per_rec[r] for r in rids]
        # Table 1
        t1 = {}
        for K in fa.KS:
            key = f"K{K}"
            groups_f = {f: [n for n in names if family(n) == f] for f in FAMILIES}
            groups_f["subsets"] = groups_f["thin"] + groups_f["select"] + groups_f["cap"]
            groups_f["all_five"] = [n for f in FAMILIES for n in groups_f[f]]
            row = {}
            for fname, members in groups_f.items():
                G = []
                for p in P:
                    pts_F = [p[n][key]["F"] for n in members] + [1.0]
                    pts_b = [p[n][key]["b"] for n in members] + [p["remake"][key]["b_direct"]]
                    G.append(bc.baseline_bits(p["remake"][key]["F"], pts_F, pts_b) / p["remake"][key]["b"])
                row[fname] = FR.boot(G)
            for m in ("translation", "static"):
                G = []
                for p in P:
                    pts_F = [p[n][key]["F"] for n in groups_f["all_five"]] + [1.0]
                    pts_b = [p[n][key]["b"] for n in groups_f["all_five"]] + [p[m][key]["b_direct"]]
                    G.append(bc.baseline_bits(p[m][key]["F"], pts_F, pts_b) / p[m][key]["b"])
                row[f"{m}_vs_all_five"] = FR.boot(G)
            row["n_recordings"] = len(P)
            t1[key] = row
        T["1_bits_at_remake_F"][st] = t1
        # Table 2
        t2 = {}
        quantities = list(CANDS) + list(TASK_KEYS)
        val = lambda p, n, q: p[n]["K4"][q] if q in CANDS else p[n]["tasks"][q]
        for f in FAMILIES:
            members = [n for n in names if family(n) == f]
            row = {}
            for q in quantities:
                v = [interp_at(p["remake"]["K4"]["b"], [(p[n]["K4"]["b"], val(p, n, q)) for n in members]) for p in P]
                row[q] = FR.boot(v) | {"n_nan": int(np.sum(~np.isfinite(v)))}
            t2[f] = row
        for m in ("remake", "translation", "static"):
            t2[m] = {q: FR.boot([val(p, m, q) for p in P]) for q in quantities} | {"b": FR.boot([p[m]["K4"]["b"] for p in P])}
        T["2_at_remake_bits_K4"][st] = t2
        # Table 3
        t3 = {}
        for c in CANDS:
            t3[c] = {}
            for q in TASK_KEYS:
                taus = []
                for p in P:
                    xs = [p[n]["K4"]["w13"][c] for n in names]
                    ys = [ORIENT[q] * p[n]["tasks"][q] for n in names]
                    ok = [np.isfinite(a) and np.isfinite(b) for a, b in zip(xs, ys)]
                    xa, ya = np.array(xs)[ok], np.array(ys)[ok]
                    taus.append(float(kendalltau(xa, ya).statistic) if len(xa) >= 2 else float("nan"))
                t3[c][q] = {"median": nanmed(taus), "n_recordings": int(np.sum(np.isfinite(taus)))}
        T["3_kendall_tau_b"][st] = t3
        # Table 4
        bgs = bg_rows[st]
        q = lambda k: {"median": float(np.median([b[k] for b in bgs])), "p10": float(np.percentile([b[k] for b in bgs], 10)),
                       "p90": float(np.percentile([b[k] for b in bgs], 90))}
        n_sat = int(sum(b["saturated"] for b in bgs))
        T["4_accounting"][st] = {
            "hevc": {nm: {k: {"median_param_sei_share": nanmed([a / b if b else np.nan for a, b, _ in v]),
                              "clipped_events_total": int(sum(c for _, _, c in v))} for k, v in d.items()}
                     for nm, d in hevc_rows[st].items()},
            "fbc_median_st_us": {nm: float(np.median(v)) for nm, v in fbc_st[st].items()},
            "background": {k: q(k) for k in ("beta_per_px_s", "beta_iso", "beta_med", "phi", "theta")},
            "n_groups": len(bgs), "n_saturated": n_sat, "n_near_saturation": int(sum(b["near_saturation"] for b in bgs)),
            "n_branch_minus1": int(sum(b["branch"] == -1 for b in bgs)), "median_n_hot": float(np.median([b["n_hot"] for b in bgs])),
            "saturated_over_5pct": bool(n_sat > 0.05 * len(bgs)),
            "fsnr_enter_share_K4": {n: nanmed([p[n]["K4"]["fsnr_enter_share"] for p in P]) for n in names}}
        frontier[st] = {f"K{K}": {n: {k: nanmed([p[n][f"K{K}"][k] for p in P]) for k in ("b",) + CANDS} for n in names}
                        for K in fa.KS}
        # acceptance check 4
        ref = rep016[f"{st}_Q"]
        F4 = FR.boot([p["remake"]["K4"]["F"] for p in P])["median"]
        b4 = FR.boot([p["remake"]["K4"]["b"] for p in P])["median"]
        c4[st] = {"F": [F4, ref["F"][0]], "b": [b4, ref["bits"][0]], "pass": F4 == ref["F"][0] and b4 == ref["bits"][0]}
    acc_out = {"2_every_group": {"remake_equals_kept": acc["remake_equals_kept"], "outside": acc["outside"],
                                 "n_groups": acc["n_groups"], "groups_equal_016": acc["groups_equal_016"],
                                 "pass": acc["remake_equals_kept"] and acc["outside"] == 0 and acc["groups_equal_016"]},
               "4_remake_K4_equals_016": c4 | {"pass": all(v["pass"] for v in c4.values())}}
    out = {"directive": "018", "entering": {ds: len(v) for ds, v in entering.items()},
           "strata": {st: len([r for r in entering[ds] if ds == "dsec" or mp.lighting(r) == st]) for st, ds in STRATA.items()},
           "schemes": names, "aggregation": {"unit": "recording", "min_groups": FR.MIN_GROUPS, "n_boot": FR.N_BOOT,
                                             "seed": FR.SEED}, "acceptance": acc_out, "tables": T}
    (res / "report.json").write_text(json.dumps(out, indent=1, default=float) + "\n")
    (res / "per_recording.json").write_text(json.dumps(per_rec, default=float, separators=(",", ":")) + "\n")
    (res / "frontier.json").write_text(json.dumps(frontier, indent=1, default=float) + "\n")
    print(json.dumps({"entering": out["entering"], "strata": out["strata"],
                      "acceptance": {k: v["pass"] for k, v in acc_out.items()}}, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
