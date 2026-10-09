"""Directive 002, Section 12: project the cost of Stages R and B from the 50-row probes.

  python3 scripts/rg_cost.py RGDIR OUT.json

Per-row cost (one core of the execution host) is averaged per box-area bin and
multiplied by the number of rows of the stage in that bin. A bin without probe
rows takes the largest probed bin mean. Reads: one per task, priced at the read
time each recording took in the preflight of directive 001.
"""
import glob
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rg_run as R  # noqa: E402

EDGES = (0, 1_000, 3_000, 10_000, 30_000, 100_000, np.inf)


def project(probe_area, probe_cost, all_area):
    bins, total = [], 0.0
    fallback = max((probe_cost[(probe_area >= lo) & (probe_area < hi)].mean()
                    for lo, hi in zip(EDGES[:-1], EDGES[1:]) if ((probe_area >= lo) & (probe_area < hi)).any()))
    for lo, hi in zip(EDGES[:-1], EDGES[1:]):
        s = (probe_area >= lo) & (probe_area < hi)
        n = int(((all_area >= lo) & (all_area < hi)).sum())
        mean = float(probe_cost[s].mean()) if s.any() else float(fallback)
        total += n * mean
        bins.append({"area_px2": [lo, None if np.isinf(hi) else hi], "n_probe_rows": int(s.sum()),
                     "mean_s_per_row": mean, "max_s": float(probe_cost[s].max()) if s.any() else None,
                     "n_rows_stage": n, "cpu_h": n * mean / 3600})
    return bins, total / 3600


def main(rgdir, out):
    rgdir = Path(rgdir)
    pre = Path.home() / "prjs" / "event_coding" / "mp" / "preflight"
    read_s = {json.loads(Path(f).read_text())["recording_id"]: json.loads(Path(f).read_text())["read_s"]
              for f in glob.glob(str(pre / "train_*.json"))}
    res = {}
    # Stage R
    z = [dict(np.load(f)) for f in sorted((rgdir / "probe_R").glob("rows_*.npz"))]
    pa = np.concatenate([d["box_area_te"] for d in z]); pc = np.concatenate([d["elapsed_s"] for d in z])
    all_area = np.concatenate([R.mp_rows(t[0], t[1])["box_area_te"][R.r_rows(R.mp_rows(t[0], t[1]))]
                               for t in R.mp_plan()])
    bins, cpu = project(pa, pc, all_area)
    reads = sum(read_s[t[0]] for t in R.mp_plan()) / 3600
    res["R"] = {"n_probe_rows": int(len(pc)), "n_rows": int(len(all_area)), "bins": bins, "compute_cpu_h": cpu,
                "read_cpu_h": reads, "total_cpu_h": cpu + reads}
    # Stage B
    z = [dict(np.load(f)) for f in sorted((rgdir / "probe_B").glob("rows_*.npz"))]
    pa = np.concatenate([d["box_area_te"] for d in z])
    pc = np.concatenate([d["b4_elapsed_s"] + d["b6_elapsed_s"] for d in z])
    p4 = np.concatenate([d["b4_elapsed_s"] for d in z]); p6 = np.concatenate([d["b6_elapsed_s"] for d in z])
    sub = json.loads((rgdir / "b_plan.json").read_text())["subsample"]
    bins, cpu = project(pa, pc, np.array([r["area"] for r in sub]))
    tasks = R.plan_tasks("B", rgdir / "B")
    reads = sum(read_s[t[0].split("|")[0]] for t in tasks) / 3600
    res["B"] = {"n_probe_rows": int(len(pc)), "n_rows": len(sub), "bins": bins, "compute_cpu_h": cpu,
                "read_cpu_h": reads, "total_cpu_h": cpu + reads,
                "probe_b6_over_b4_time": float(p6.sum() / p4.sum())}
    res["total_cpu_h"] = res["R"]["total_cpu_h"] + res["B"]["total_cpu_h"]
    res["limit_cpu_h"] = 80
    res["within_limit"] = res["total_cpu_h"] <= 80
    Path(out).write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps({k: (v if not isinstance(v, dict) else {kk: vv for kk, vv in v.items() if kk != "bins"})
                      for k, v in res.items()}, indent=1))
    for s in ("R", "B"):
        for b in res[s]["bins"]:
            print(s, b)


if __name__ == "__main__":
    main(*sys.argv[1:3])
