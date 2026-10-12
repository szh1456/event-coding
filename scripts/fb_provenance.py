"""Directive 016, Section 10: results/fb/provenance.json.

  python3 scripts/fb_provenance.py SUITE_LINE OUT.json

Commits, host, versions, wall and CPU time of Stages T and R (sums over tasks and groups, from the task
outputs), and the files read: event files, annotation files and the kept per-group files of REMAKE, with
their sizes. Every path is constructed from a recording identifier of the populations; nothing is listed.
"""
from __future__ import annotations

import json
import pickle
import platform
import socket
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ec import mp  # noqa: E402
import ds_run as DR  # noqa: E402
import fb_run as FB  # noqa: E402


def stage_times(stage):
    out = {"n_tasks": 0, "n_groups": 0, "task_cpu_s": 0.0, "group_cpu_s": 0.0, "commits": set()}
    first, last = None, None
    for ds in ("etram", "dsec"):
        for rid in FB.recordings(ds, stage):
            for f in sorted(FB.outdir(ds, stage).glob(f"{rid}_[0-9][0-9][0-9].pkl")):
                with open(f, "rb") as fh:
                    d = pickle.load(fh)
                out["n_tasks"] += 1
                out["n_groups"] += len(d["groups"])
                out["task_cpu_s"] += d["task_cpu_s"]
                out["group_cpu_s"] += sum(g["cpu_s"] for g in d["groups"])
                out["commits"].add(d["commit"])
                ts = [g["finished_utc"] for g in d["groups"]]
                first = min(first, min(ts)) if first else min(ts)
                last = max(last, max(ts)) if last else max(ts)
    log = (FB.FB_E / f"run_{stage}.log").read_text().splitlines()
    out["commits"] = sorted(out["commits"])
    out["task_cpu_h"], out["group_cpu_h"] = out.pop("task_cpu_s") / 3600, out.pop("group_cpu_s") / 3600
    out["first_group_finished_utc"], out["last_group_finished_utc"] = first, last
    out["scheduler_log_first_last"] = [log[0], log[-1]]
    return out


def main(suite, out):
    import h5py, numba, scipy, zstandard
    files = {"event_files": [], "annotation_files": [], "remake_per_group_files": []}
    for ds in ("etram", "dsec"):
        for stage in ("T", "R"):
            for rid in FB.recordings(ds, stage):
                p = mp.event_path(rid) if ds == "etram" else DR.DATA / rid / "events.h5"
                files["event_files"].append({"dataset": ds, "stage": stage, "path": str(p), "size": p.stat().st_size})
                if ds == "etram" and stage == "R":
                    a = mp.annotation_path(rid)
                    files["annotation_files"].append({"path": str(a), "size": a.stat().st_size})
                base = {("etram", "T"): FB.BK_DIR / "T", ("etram", "R"): FB.BK_DIR / "R",
                        ("dsec", "T"): DR.BASE / "ds" / "dt" / "T", ("dsec", "R"): DR.BASE / "ds" / "R"}[(ds, stage)]
                for f in sorted(base.glob(f"groups_{rid}_[0-9][0-9][0-9].pkl")):
                    files["remake_per_group_files"].append({"path": str(f), "size": f.stat().st_size})
    res = {"directive": "016", "host": socket.gethostname(),
           "commits": {"tuning": "ebf7e7f", "stage_T_plan": json.loads((FB.FB_E / "T" / "plan.json").read_text())["commit"],
                       "stage_R_plan": json.loads((FB.FB_E / "R" / "plan.json").read_text())["commit"],
                       "executed": (mp.REPO / "COMMIT").read_text().strip()},
           "versions": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__,
                        "h5py": h5py.__version__, "zstandard": zstandard.__version__, "numba": numba.__version__},
           "suite": suite,
           "implementation": "ec.fbc and ec.downstream (Appendices A and B, unchanged); REMAKE not evaluated again: its "
                             "groups, sums and records are those of the kept per-group files",
           "workers": "up to 20 under nice -n 19, one BLAS thread; eTraM: at most 6 reads at once; DSEC: one read at a "
                      "time (read lock and memory wait of directive 009), at most 6 DSEC tasks at once; no worker "
                      "launched below 40 GB available",
           "stage_T": stage_times("T"), "stage_R": stage_times("R"), "files_read": files,
           "n_files_read": {k: len(v) for k, v in files.items()}}
    Path(out).write_text(json.dumps(res, indent=1, default=float) + "\n")
    print(json.dumps({k: res[k] for k in ("commits", "stage_T", "stage_R", "n_files_read")}, indent=1, default=float))


if __name__ == "__main__":
    main(*sys.argv[1:3])
