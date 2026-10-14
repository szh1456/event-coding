"""Directive 019, Section 6: Tables 1 to 4, the frontier data, per-recording sums and the model outputs.

  python3 scripts/hd_reduce.py RESULTS_DIR

A recording enters a D1 table with at least 2 D1 groups on eTraM and 1 on DSEC, a D2 table with the same numbers of
D2 groups; its values come from sums over those groups (bits and events; the fidelity terms N, N2, M, Dsnr, Lsnr
that ``hd_run`` keeps; x265's frame statistics; the task lists, pooled as in directive 018). Medians over
recordings with the bootstrap of directive 007, seed 20261016. Strata: day and night (eTraM), all (DSEC).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ec import blockcodec as bc, hevcdiag as hd, mp  # noqa: E402
import fb_reduce as FR  # noqa: E402
import fm_reduce as FMR  # noqa: E402
import hd_run as HR  # noqa: E402

STRATA = {"day": "etram", "night": "etram", "all": "dsec"}
MIN = {"etram": 2, "dsec": 1}
QMODES = tuple(f"qp{q}" for q in hd.QPS)
TARGETS = (0.5, 0.7, 0.9)
BUDGETS = (0.05, 0.1, 0.2, 0.5, 1.0)
TASKS = FMR.TASK_KEYS
GRIDS = [(s, k) for s in hd.SPACES for k in hd.KS]


def gname(s, k):
    return f"s{s}_k{k}"


def fid_of(sums):
    """F and Fsnr from summed terms, by the formula of ``ec.hevcdiag.fidelities``."""
    den = sums["N"] + sums["N2"]
    return {"F": 2.0 * sums["M"] / den if den else 0.0,
            "Fsnr": min(1.0, max(0.0, 1.0 - sums["Dsnr"] / sums["Lsnr"])) if sums["Lsnr"] > 0 else 0.0}


def add_sums(xs):
    return {k: float(sum(x[k] for x in xs)) for k in xs[0]}


def frame_stats(modes_list):
    """Pooled x265 frame statistics of one mode over groups: I and P bit shares, mean P coding-unit shares."""
    fr = [f for m in modes_list for f in m["frames"]]
    tot = sum(f["bits"] for f in fr)
    I = sum(f["bits"] for f in fr if f["type"].startswith("I"))
    P = [f for f in fr if f["type"].startswith("P")]
    return {"I_share": I / tot if tot else float("nan"), "P_share": (tot - I) / tot if tot else float("nan"),
            "I_bits": float(I), "P_bits": float(tot - I),
            **{f"P_{c}": float(np.mean([f[c] for f in P])) if P else float("nan") for c in ("intra", "inter", "skip", "merge")}}


def pool_tasks(task_runs):
    return FMR.task_scores([o for t in task_runs for o in t["objects"]], [o for t in task_runs for o in t["tracks"]],
                           [o for t in task_runs for o in t["motion"]])


def first_crossing(target, pts):
    """Bits at Fsnr = target along the QP ladder (points in QP order): linear in Fsnr between the first two
    consecutive QPs that bracket it; NaN if none does."""
    for (f0, b0), (f1, b1) in zip(pts[:-1], pts[1:]):
        if min(f0, f1) <= target <= max(f0, f1):
            return b0 if f1 == f0 else b0 + (b1 - b0) * (target - f0) / (f1 - f0)
    return float("nan")


def d1_recording(groups):
    n = float(sum(sum(g["n_true"]) for g in groups))
    out = {"n_groups": len(groups), "n_true": n, "grids": {}}
    for s, k in GRIDS:
        G = [g["d1"][gname(s, k)] for g in groups]
        r = {"clipped_share": sum(x["clipped_events"] for x in G) / n,
             "clip_fid": fid_of(add_sums([x["clip_fid"]["sums"] for x in G])), "modes": {}}
        for mode in ("lossless", "sparse") + QMODES:
            ms = [x["modes"][mode] for x in G]
            m = {"bits": float(sum(x["bits"] for x in ms)), "b": sum(x["bits"] for x in ms) / n}
            if mode != "sparse":
                m.update({"param_bits": float(sum(x["param_bits"] for x in ms)),
                          "enc_cpu_s_per_kev": sum(x["enc_cpu_s"] for x in ms) / (n / 1000.0),
                          "dec_cpu_s_per_kev": sum(x["dec_cpu_s"] for x in ms) / (n / 1000.0),
                          "padding_counts": int(sum(x["padding_counts"] for x in ms)), **frame_stats(ms)})
                sums = add_sums([x["fid"]["sums"] for x in ms])
                m.update({"fid_sums": sums, **fid_of(sums)})
                if mode != "lossless":
                    m["tasks"] = {pl: pool_tasks([x["tasks"][pl] for x in ms]) for pl in hd.PLACEMENTS}
            r["modes"][mode] = m
        r["lossless_over_sparse"] = r["modes"]["lossless"]["bits"] / r["modes"]["sparse"]["bits"]
        pts = [(r["modes"][q]["Fsnr"], r["modes"][q]["b"]) for q in QMODES]
        r["b_at_Fsnr"] = {str(t): first_crossing(t, pts) for t in TARGETS}
        out["grids"][gname(s, k)] = r
    return out


def d2_recording(groups):
    out = {"n_groups": len(groups), "grids": {}}
    for s, k in GRIDS:
        for pl in hd.PLACEMENTS:
            out["grids"][f"{gname(s, k)}_{pl}"] = pool_tasks([g["d2"][f"{gname(s, k)}_{pl}"]["tasks"] for g in groups])
    return out


def main(resdir):
    res = Path(resdir)
    tasks = json.loads((HR.HD_E / "plan.json").read_text())["tasks"]
    d1g, d2g = {}, {}
    acc2 = {"d1_tasks": 0, "d1_tasks_done": 0}
    for key in tasks:
        kind = key.split("|")[0]
        if kind == "d3":
            continue
        ds, rid = key.split("|")[1:3]
        if kind == "d1":
            acc2["d1_tasks"] += 1
        if not HR.out_path(key).exists():
            continue
        d = HR.load(key)
        if kind == "d1":
            acc2["d1_tasks_done"] += 1
            d1g.setdefault((ds, rid), []).extend(d["groups"])
        d2g.setdefault((ds, rid), []).extend(d["groups"])
    per_rec = {"d1": {}, "d2": {}}
    for (ds, rid), gs in d1g.items():
        if len(gs) >= MIN[ds]:
            per_rec["d1"][rid] = d1_recording(sorted(gs, key=lambda g: g["j"]))
    for (ds, rid), gs in d2g.items():
        if len(gs) >= MIN[ds]:
            per_rec["d2"][rid] = d2_recording(sorted(gs, key=lambda g: g["j"]))
    stratum = lambda rid: "all" if not rid.startswith("train_") else mp.lighting(rid)
    T = {"1_rate_vs_slice": {}, "2_representation": {}, "3_tasks_per_bit": {}, "4_model": {}}
    frontier = {}
    for st in STRATA:
        R1 = [v for r, v in per_rec["d1"].items() if stratum(r) == st]
        R2 = [v for r, v in per_rec["d2"].items() if stratum(r) == st]
        t1, fr = {}, {}
        for s, k in GRIDS:
            gn = gname(s, k)
            rows = [v["grids"][gn] for v in R1]
            L = lambda m, f: FR.boot([r["modes"][m][f] for r in rows])
            t1[gn] = {"n_recordings": len(rows),
                      "b_lossless": L("lossless", "b"), "b_sparse": L("sparse", "b"),
                      "lossless_over_sparse": FR.boot([r["lossless_over_sparse"] for r in rows]),
                      "lossless_frames": {f: L("lossless", f) for f in ("I_share", "P_share", "P_intra", "P_inter", "P_skip", "P_merge")},
                      "cpu_s_per_kev": {m: {"enc": L(m, "enc_cpu_s_per_kev"), "dec": L(m, "dec_cpu_s_per_kev")}
                                        for m in ("lossless",) + QMODES},
                      "clipped_share": FR.boot([r["clipped_share"] for r in rows]),
                      "padding_counts_total": {m: int(sum(r["modes"][m]["padding_counts"] for r in rows)) for m in QMODES},
                      "b_at_Fsnr": {t: FR.boot([r["b_at_Fsnr"][t] for r in rows])
                                    | {"n_nan": int(sum(not np.isfinite(r["b_at_Fsnr"][t]) for r in rows))} for t in map(str, TARGETS)}}
            fr[gn] = {q: {"b": FMR.nanmed([r["modes"][q]["b"] for r in rows]),
                          "F": FMR.nanmed([r["modes"][q]["F"] for r in rows]),
                          "Fsnr": FMR.nanmed([r["modes"][q]["Fsnr"] for r in rows]),
                          "tasks": {pl: {t: FMR.nanmed([r["modes"][q]["tasks"][pl][t] for r in rows]) for t in TASKS}
                                    for pl in hd.PLACEMENTS}} for q in QMODES}
            fr[gn]["lossless"] = {"b": FMR.nanmed([r["modes"]["lossless"]["b"] for r in rows])}
            fr[gn]["sparse"] = {"b": FMR.nanmed([r["modes"]["sparse"]["b"] for r in rows])}
        T["1_rate_vs_slice"][st] = t1
        frontier[st] = fr
        T["2_representation"][st] = {f"{gname(s, k)}_{pl}": {t: FR.boot([v["grids"][f"{gname(s, k)}_{pl}"][t] for v in R2])
                                                             for t in TASKS} | {"n_recordings": len(R2)}
                                     for s, k in GRIDS for pl in hd.PLACEMENTS}
        # Table 3: on the frontier (medians over recordings), the best score under each budget
        t3 = {}
        for bgt in BUDGETS:
            for k in hd.KS:
                for pl in hd.PLACEMENTS:
                    cell = {}
                    for t in TASKS:
                        best = None
                        for s in hd.SPACES:
                            for q in QMODES:
                                p = fr[gname(s, k)][q]
                                v = p["tasks"][pl][t]
                                if not (np.isfinite(p["b"]) and p["b"] <= bgt and np.isfinite(v)):
                                    continue
                                score = FMR.ORIENT[t] * v
                                if best is None or score > best[0]:
                                    best = (score, v, s, q, p["b"])
                        cell[t] = None if best is None else {"value": best[1], "s": best[2], "qp": best[3], "b": best[4]}
                    t3[f"b{bgt}_k{k}_{pl}"] = cell
        T["3_tasks_per_bit"][st] = t3
    # Table 4 and model.json
    scenes = [HR.load(k) for k in tasks if k.startswith("d3|") and HR.out_path(k).exists()]
    model = []
    for d in scenes:
        row = {"tau": d["tau"], "n": d["n"], "seed": d["seed"], "n_events": d["n_events"], "grids": {}}
        for gn, gr in d["grids"].items():
            cc = gr["code"]
            ne = float(sum(cc["n_true"]))
            modes = {}
            for m, v in cc["modes"].items():
                mm = {"bits": v["bits"], "b": v["bits"] / ne}
                if m != "sparse":
                    mm.update({kk: v[kk] for kk in ("param_bits", "enc_cpu_s", "dec_cpu_s", "padding_counts")})
                    mm.update(frame_stats([v]))
                    mm.update({kk: v["fid"][kk] for kk in ("F", "Fsnr")})
                modes[m] = mm
            row["grids"][gn] = {"oracle": gr["oracle"], "n_events_coded": ne, "clipped_events": cc["clipped_events"],
                                "modes": modes}
        model.append(row)
    t4 = {}
    for tau in HR.D3["taus"]:
        for n in HR.D3["ns"]:
            sc = [r for r in model if r["tau"] == tau and r["n"] == n]
            if not sc:
                continue
            for s, k in GRIDS:
                gn = gname(s, k)
                dt = bc.T0_US / k
                mean = lambda f: float(np.mean([f(r["grids"][gn]) for r in sc]))
                L = lambda r: r["modes"]["lossless"]
                t4[f"tau{int(tau)}_n{n}_{gn}"] = {
                    "tau": tau, "n": n, "s": s, "k": k, "dt_over_tau": dt / tau, "n_seeds": len(sc),
                    "oracle_F": mean(lambda g: g["oracle"]["F"]),
                    "binfidmoved": hd.binfidmoved(dt, tau, n) if s == 1 else None,
                    "lossless_b_I": mean(lambda g: L(g)["I_bits"] / g["n_events_coded"]),
                    "lossless_b_P": mean(lambda g: L(g)["P_bits"] / g["n_events_coded"]),
                    **{f"lossless_P_{c}": mean(lambda g, c=c: L(g)[f"P_{c}"]) for c in ("skip", "merge", "inter", "intra")},
                    "qp": {q: {"Fsnr": mean(lambda g, q=q: g["modes"][q]["Fsnr"]), "b": mean(lambda g, q=q: g["modes"][q]["b"])}
                           for q in QMODES}}
    T["4_model"] = t4
    out = {"directive": "019", "entering": {"d1": {st: len([r for r in per_rec["d1"] if stratum(r) == st]) for st in STRATA},
                                            "d2": {st: len([r for r in per_rec["d2"] if stratum(r) == st]) for st in STRATA}},
           "aggregation": {"unit": "recording", "min_groups": MIN, "n_boot": FR.N_BOOT, "seed": FR.SEED,
                           "fidelities": "from the summed terms kept by hd_run (N, N2, M, Dsnr, Lsnr)",
                           "tasks": "pooled over the groups of a recording as in directive 018 (fm_reduce.task_scores)",
                           "table3": "on the frontier: medians over recordings per (s, k, QP); the best score whose median "
                                     "bits do not exceed the budget",
                           "b_at_Fsnr": "per recording, the first pair of consecutive QPs (QP order) that brackets the "
                                        "target, linear in Fsnr"},
           "acceptance": {"2_every_d1_call_returned": acc2 | {"pass": acc2["d1_tasks"] == acc2["d1_tasks_done"]}},
           "tables": T}
    (res / "report.json").write_text(json.dumps(out, indent=1, default=float) + "\n")
    (res / "per_recording.json").write_text(json.dumps(per_rec, default=float, separators=(",", ":")) + "\n")
    (res / "frontier.json").write_text(json.dumps(frontier, indent=1, default=float) + "\n")
    (res / "model.json").write_text(json.dumps(model, default=float, separators=(",", ":")) + "\n")
    print(json.dumps({"entering": out["entering"], "acceptance": out["acceptance"], "n_scenes": len(model)}, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
