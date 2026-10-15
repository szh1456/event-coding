"""Directive 021, Section 6: Tables 1 to 5, the curve data, the per-recording sums and the model outputs.

  python3 scripts/hc_reduce.py RESULTS_DIR

A recording enters with the sums of its D1 groups under the entering rule of directive 019 (at least 2 groups on
eTraM, 1 on DSEC). Bits are per true event; fidelities come from the summed terms (N, N2, M, Dsnr, Lsnr); error
counts are shares of the input events of the mode, from sums; tasks are pooled over groups as in directive 018.
Medians over recordings with the bootstrap of directive 007, seed 20261016. Strata: day, night (eTraM), all (DSEC).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ec import hevcctl as hc, hevcdiag as hd, mp  # noqa: E402
import fb_reduce as FR  # noqa: E402
import fm_reduce as FMR  # noqa: E402
import hc_run as HC  # noqa: E402
import hd_reduce as HDR  # noqa: E402
import hd_run as HR  # noqa: E402

STRATA = ("day", "night", "all")
MIN = {"etram": 2, "dsec": 1}
QMODES = tuple(f"qp{q}" for q in hd.QPS)
IMODES = tuple(f"qp{q}_intra" for q in hd.QPS)
ERR = ("removed1", "removed2", "lowered", "raised", "added")
F_TARGETS = (0.9, 0.95)
TASKS = FMR.TASK_KEYS


def gname(s, k):
    return f"s{s}_k{k}"


def add_dicts(xs):
    return {k: float(sum(x[k] for x in xs)) for k in xs[0]}


def mode_sums(ms, n):
    """Pooled values of one mode over groups."""
    out = {"bits": float(sum(m["bits"] for m in ms)), "b": sum(m["bits"] for m in ms) / n}
    if "summary" in ms[0]:
        out["I_bits"] = float(sum(m["summary"]["I_bits"] for m in ms))
        out["P_bits"] = float(sum(m["summary"]["P_bits"] for m in ms))
        out["padding_counts"] = int(sum(m["padding_counts"] for m in ms))
        out["enc_cpu_s"] = float(sum(m["enc_cpu_s"] for m in ms))
        sums = add_dicts([m["fid"]["sums"] for m in ms])
        out["fid_sums"] = sums
        out.update(HDR.fid_of(sums))
    if "errors" in ms[0]:
        out["errors"] = {k: int(sum(m["errors"][k] for m in ms)) for k in ms[0]["errors"]}
    if "tasks" in ms[0]:
        out["tasks"] = {pl: HDR.pool_tasks([m["tasks"][pl] for m in ms]) for pl in hd.PLACEMENTS}
    return out


def recording(groups):
    n = float(sum(sum(g["n_true"]) for g in groups))
    out = {"n_groups": len(groups), "n_true": n, "fine": {}, "coarse": {}}
    for s, k in HC.FINE_GRIDS:
        G = [g["fine"][gname(s, k)] for g in groups]
        r = {"modes": {m: mode_sums([x["modes"][m] for x in G], n) for m in hc.FINE_MODES},
             "clipped15": int(sum(x["clipped"]["15"] for x in G))}
        L = r["modes"]
        r["intra_over_lossless"] = L["lossless_intra"]["bits"] / L["lossless"]["bits"]
        r["lossless_over_sparse"] = L["lossless"]["bits"] / L["sparse"]["bits"]
        r["x16_over_lossless"] = L["lossless_x16"]["bits"] / L["lossless"]["bits"]
        tot = L["lossless"]["I_bits"] + L["lossless"]["P_bits"]
        r["lossless_I_share"] = L["lossless"]["I_bits"] / tot if tot else float("nan")
        for fam, modes in (("qp", QMODES), ("intra", IMODES)):
            pts = [(L[m]["F"], L[m]["b"]) for m in modes]
            r[f"b_at_F_{fam}"] = {str(t): HDR.first_crossing(t, pts) for t in F_TARGETS}
        r["b_at_F_ratio"] = {str(t): r["b_at_F_intra"][str(t)] / r["b_at_F_qp"][str(t)] for t in F_TARGETS}
        out["fine"][gname(s, k)] = r
    for s, k in hc.COARSE_GRIDS:
        G = [g["coarse"][gname(s, k)] for g in groups]
        r = {"modes": {m: mode_sums([x["modes"][m] for x in G], n) for m in hc.COARSE_MODES},
             "raw_events": int(sum(x["raw_events"] for x in G)), "raw_max": int(max(x["raw_max"] for x in G))}
        r["clipped_share"] = {c: sum(x["clipped"][c] for x in G) / n for c in G[0]["clipped"]}
        r["clip_fid"] = {c: HDR.fid_of(add_dicts([x["clip_fid"][c]["sums"] for x in G])) for c in G[0]["clip_fid"]}
        r["c255_over_sparse_raw"] = r["modes"]["lossless_c255"]["bits"] / r["modes"]["sparse_raw"]["bits"]
        out["coarse"][gname(s, k)] = r
    return out


def err_shares(e):
    return {k: e[k] / e["in_events"] if e["in_events"] else float("nan") for k in ERR} | \
           {"in_vox1_share": e["in_vox1"] / e["in_events"] if e["in_events"] else float("nan")}


def main(resdir):
    res = Path(resdir)
    tasks = json.loads((HC.HC_E / "plan.json").read_text())["tasks"]
    by_rec, acc = {}, {"d1_expected": 0, "d1_returned": 0, "d3_expected": 0, "d3_returned": 0, "check_019_pass": True,
                       "first_mismatch": None}
    for key in tasks:
        kind = key.split("|")[0]
        acc[f"{kind}_expected"] += 1
        if not HC.out_path(key).exists():
            continue
        acc[f"{kind}_returned"] += 1
        if kind == "d1":
            _, ds, rid, _ = key.split("|")
            g = HC.load(key)["groups"][0]
            if not g["check_019"]["pass"]:
                acc["check_019_pass"] = False
                acc["first_mismatch"] = acc["first_mismatch"] or {"key": key, **g["check_019"]["first_mismatch"]}
            by_rec.setdefault((ds, rid), []).append(g)
    per_rec = {rid: recording(sorted(gs, key=lambda g: g["j"])) for (ds, rid), gs in by_rec.items() if len(gs) >= MIN[ds]}
    stratum = lambda rid: "all" if not rid.startswith("train_") else mp.lighting(rid)
    T = {"1_prediction_lossless": {}, "2_prediction_lossy": {}, "3_decode_errors": {}, "4_clipping": {}, "5_model": {}}
    curves = {"strata": {}}
    for st in STRATA:
        R = [v for r, v in per_rec.items() if stratum(r) == st]
        t1, t2, t3, t4, cv = {}, {}, {}, {}, {}
        for s, k in HC.FINE_GRIDS:
            gn = gname(s, k)
            rows = [v["fine"][gn] for v in R]
            B = lambda m, f="b": FR.boot([r["modes"][m][f] for r in rows])
            t1[gn] = {"n_recordings": len(rows), **{f"b_{m}": B(m) for m in ("lossless", "lossless_intra", "sparse", "lossless_x16")},
                      **{q: FR.boot([r[q] for r in rows]) for q in ("intra_over_lossless", "lossless_over_sparse",
                                                                    "x16_over_lossless", "lossless_I_share")}}
            t2[gn] = {"qp": {m: {"F": B(m, "F"), "Fsnr": B(m, "Fsnr"), "b": B(m)} for m in QMODES + IMODES},
                      "b_at_F": {str(t): {fam: FR.boot([r[f"b_at_F_{fam}"][str(t)] for r in rows])
                                          | {"n_nan": int(sum(not np.isfinite(r[f"b_at_F_{fam}"][str(t)]) for r in rows))}
                                          for fam in ("qp", "intra")}
                                 | {"ratio_intra_over_qp": FR.boot([r["b_at_F_ratio"][str(t)] for r in rows])}
                                 for t in F_TARGETS}}
            t3[gn] = {m: {"shares": {k_: FR.boot([err_shares(r["modes"][m]["errors"])[k_] for r in rows])
                                     for k_ in ERR + ("in_vox1_share",)},
                          "pooled_shares": err_shares({k_: sum(r["modes"][m]["errors"][k_] for r in rows)
                                                       for k_ in rows[0]["modes"][m]["errors"]}),
                          "padding_counts_total": int(sum(r["modes"][m]["padding_counts"] for r in rows))}
                      for m in QMODES + IMODES}
            cv[gn] = {m: {"bits": sum(r["modes"][m]["bits"] for r in rows), "n_true": sum(v["n_true"] for v in R),
                          **({"fid_sums": {kk: sum(r["modes"][m]["fid_sums"][kk] for r in rows) for kk in rows[0]["modes"][m]["fid_sums"]}}
                             if "fid_sums" in rows[0]["modes"][m] else {}),
                          **({"errors": {kk: sum(r["modes"][m]["errors"][kk] for r in rows) for kk in rows[0]["modes"][m]["errors"]}}
                             if "errors" in rows[0]["modes"][m] else {})}
                      for m in hc.FINE_MODES}
        for s, k in hc.COARSE_GRIDS:
            gn = gname(s, k)
            rows = [v["coarse"][gn] for v in R]
            row = {"n_recordings": len(rows),
                   "clipped_share": {c: FR.boot([r["clipped_share"][c] for r in rows]) for c in rows[0]["clipped_share"]},
                   "clip_F": {c: FR.boot([r["clip_fid"][c]["F"] for r in rows]) for c in rows[0]["clip_fid"]},
                   "b_lossless_c255": FR.boot([r["modes"]["lossless_c255"]["b"] for r in rows]),
                   "b_sparse_raw": FR.boot([r["modes"]["sparse_raw"]["b"] for r in rows]),
                   "c255_over_sparse_raw": FR.boot([r["c255_over_sparse_raw"] for r in rows]), "qp": {}}
            for q in hc.COARSE_QPS:
                ms = {"qp": f"qp{q}", "s4c15": f"qp{q}_s4c15", "s4": f"qp{q}_s4"}
                cell = {}
                for lab, m in ms.items():
                    cell[lab] = {"b": FR.boot([r["modes"][m]["b"] for r in rows]),
                                 "F": FR.boot([r["modes"][m]["F"] for r in rows]),
                                 "Fsnr": FR.boot([r["modes"][m]["Fsnr"] for r in rows]),
                                 "tasks": {pl: {t: FR.boot([r["modes"][m]["tasks"][pl][t] for r in rows]) for t in TASKS}
                                           for pl in hd.PLACEMENTS}}
                for lab, (a, b) in (("clipping_s4_minus_s4c15", ("s4", "s4c15")), ("mapping_s4c15_minus_qp", ("s4c15", "qp"))):
                    ma, mb = ms[a], ms[b]
                    cell[lab] = {f: FR.boot([r["modes"][ma][f] - r["modes"][mb][f] for r in rows]) for f in ("b", "F", "Fsnr")}
                    cell[lab]["tasks"] = {pl: {t: FR.boot([r["modes"][ma]["tasks"][pl][t] - r["modes"][mb]["tasks"][pl][t]
                                                           for r in rows]) for t in TASKS} for pl in hd.PLACEMENTS}
                row["qp"][str(q)] = cell
            t4[gn] = row
            cv[gn + "_coarse"] = {m: {"bits": sum(r["modes"][m]["bits"] for r in rows),
                                      **({"fid_sums": {kk: sum(r["modes"][m]["fid_sums"][kk] for r in rows)
                                                       for kk in rows[0]["modes"][m]["fid_sums"]}}
                                         if "fid_sums" in rows[0]["modes"][m] else {}),
                                      **({"errors": {kk: sum(r["modes"][m]["errors"][kk] for r in rows)
                                                     for kk in rows[0]["modes"][m]["errors"]}}
                                         if "errors" in rows[0]["modes"][m] else {})} for m in hc.COARSE_MODES}
        T["1_prediction_lossless"][st], T["2_prediction_lossy"][st] = t1, t2
        T["3_decode_errors"][st], T["4_clipping"][st] = t3, t4
        curves["strata"][st] = cv
    # model
    scenes = [HC.load(k) for k in tasks if k.startswith("d3|") and HC.out_path(k).exists()]
    model = []
    for d in scenes:
        row = {"tau": d["tau"], "n": d["n"], "seed": d["seed"], "n_events": d["n_events"], "grids": {}}
        for gn, o in d["grids"].items():
            ne = float(sum(o["n_true"]))
            modes = {}
            for m, v in o["modes"].items():
                mm = {"bits": v["bits"], "b": v["bits"] / ne}
                if "summary" in v:
                    mm.update({"I_bits": v["summary"]["I_bits"], "P_bits": v["summary"]["P_bits"],
                               "F": v["fid"]["F"], "Fsnr": v["fid"]["Fsnr"], "padding_counts": v["padding_counts"]})
                if "errors" in v:
                    mm["errors"] = v["errors"]
                modes[m] = mm
            row["grids"][gn] = {"n_events_coded": ne, "clipped15": o["clipped"]["15"], "modes": modes}
        model.append(row)
    t5 = {}
    for tau in HR.D3["taus"]:
        for n in HR.D3["ns"]:
            sc = [r for r in model if r["tau"] == tau and r["n"] == n]
            if not sc:
                continue
            for s, k in HC.FINE_GRIDS:
                gn = gname(s, k)
                mean = lambda f: float(np.mean([f(r["grids"][gn]) for r in sc]))
                M_ = lambda r, m: r["modes"][m]
                cell = {"tau": tau, "n": n, "s": s, "k": k, "dt_over_tau": hd.T0 / k / tau, "n_seeds": len(sc),
                        **{f"b_{m}": mean(lambda g, m=m: M_(g, m)["b"]) for m in ("lossless", "lossless_intra", "sparse", "lossless_x16")},
                        "b_lossless_P": mean(lambda g: M_(g, "lossless")["P_bits"] / g["n_events_coded"]), "qp": {}}
                for m in QMODES + IMODES:
                    cell["qp"][m] = {"F": mean(lambda g, m=m: M_(g, m)["F"]), "b": mean(lambda g, m=m: M_(g, m)["b"]),
                                     **{e: mean(lambda g, m=m, e=e: err_shares(M_(g, m)["errors"])[e]) for e in ERR + ("in_vox1_share",)}}
                t5[f"tau{int(tau)}_n{n}_{gn}"] = cell
    T["5_model"] = t5
    curves["model"] = {k: {"b": {m: v[f"b_{m}"] for m in ("lossless", "lossless_intra", "sparse", "lossless_x16")},
                           "qp": v["qp"]} for k, v in t5.items()}
    out = {"directive": "021", "entering": {st: len([r for r in per_rec if stratum(r) == st]) for st in STRATA},
           "aggregation": {"unit": "recording", "min_groups": MIN, "n_boot": FR.N_BOOT, "seed": FR.SEED,
                           "b_at_F": "per recording, the first two consecutive QPs (QP order) that bracket the target, "
                                     "linear in F"},
           "acceptance": {"2_every_call_returned": {k: acc[k] for k in ("d1_expected", "d1_returned", "d3_expected", "d3_returned")}
                          | {"pass": acc["d1_expected"] == acc["d1_returned"] and acc["d3_expected"] == acc["d3_returned"]},
                          "3_reproduces_019": {"pass": acc["check_019_pass"], "first_mismatch": acc["first_mismatch"],
                                               "n_groups_checked": acc["d1_returned"]}},
           "tables": T}
    (res / "report.json").write_text(json.dumps(out, indent=1, default=float) + "\n")
    (res / "per_recording.json").write_text(json.dumps(per_rec, default=float, separators=(",", ":")) + "\n")
    (res / "curves.json").write_text(json.dumps(curves, default=float, separators=(",", ":")) + "\n")
    (res / "model.json").write_text(json.dumps(model, default=float, separators=(",", ":")) + "\n")
    print(json.dumps({"entering": out["entering"], "acceptance": out["acceptance"], "n_scenes": len(model)}, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
