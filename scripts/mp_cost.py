"""Directive 001, Section 11: full-run cost from the timed sample, by box area.

  python3 scripts/mp_cost.py COSTDIR PREFLIGHTDIR OUT.json

Cost of an instant = elapsed time of ``evaluate_instant`` summed over the six
settings, on one core of the execution host. The full pass is extrapolated as
sum over area bins of (generated instants in the bin) x (mean sampled cost in the
bin), plus one read of each recording per shard.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ec import annotations, motion, mp  # noqa: E402

AREA_EDGES = (0, 1_000, 3_000, 10_000, 30_000, np.inf)


def main(costdir, predir, out):
    costdir, predir = Path(costdir), Path(predir)
    per = {}
    for f in sorted(costdir.glob("instants_*.npz")):
        z = np.load(f)
        if "elapsed_s" not in z:
            continue
        for rid, tid, k, a, el, sk in zip(z["recording_id"], z["track_id"], z["instant_index"], z["box_area_te"],
                                          z["elapsed_s"], z["skip"]):
            d = per.setdefault((rid, tid, k), {"area": a, "s": 0.0, "n_scored": 0})
            d["s"] += el
            d["n_scored"] += sk == ""
    area = np.array([d["area"] for d in per.values()])
    cost = np.array([d["s"] for d in per.values()])
    # every generated instant of the population, box area at t_e (annotations only)
    ids, _ = mp.load_population()
    all_area = []
    for rid in ids:
        for tr in annotations.tracks(annotations.load_boxes(mp.annotation_path(rid))):
            for t in motion.evaluation_instants(tr):
                _, _, w, h = tr.box(float(t))
                all_area.append(float(w) * float(h))
    all_area = np.array(all_area)
    bins, total = [], 0.0
    for lo, hi in zip(AREA_EDGES[:-1], AREA_EDGES[1:]):
        s = (area >= lo) & (area < hi)
        n_all = int(((all_area >= lo) & (all_area < hi)).sum())
        mean = float(cost[s].mean()) if s.any() else float("nan")
        est = n_all * (mean if s.any() else float(cost.max()))
        total += est
        bins.append({"area_px2": [lo, None if np.isinf(hi) else hi], "n_sampled_instants": int(s.sum()),
                     "mean_s_per_instant_6_settings": mean,
                     "median_s": float(np.median(cost[s])) if s.any() else None,
                     "max_s": float(cost[s].max()) if s.any() else None,
                     "n_generated_instants": n_all, "cpu_h_estimate": est / 3600})
    reads = [json.loads(f.read_text())["read_s"] for f in predir.glob("train_*.json")]
    res = {"host_cores_physical": 28, "n_sampled_instants": int(len(cost)), "n_generated_instants": int(len(all_area)),
           "bins": bins, "compute_cpu_h": total / 3600, "read_cpu_h_per_pass": float(np.sum(reads)) / 3600,
           "note": "cost per instant is wall time on one core of cnt for all six settings and three models"}
    res["total_cpu_h_estimate_one_read_per_recording"] = res["compute_cpu_h"] + res["read_cpu_h_per_pass"]
    Path(out).write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:4])
