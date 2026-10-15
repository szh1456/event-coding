"""Directive 027, Section 10: results/pc/provenance.json.

  python3 scripts/pc_provenance.py SUITE_LINE OUT.json
"""
from __future__ import annotations

import json
import platform
import socket
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ec import mp  # noqa: E402
import fm_run as FM  # noqa: E402
import hd_run as HR  # noqa: E402
import pc_run as P  # noqa: E402


def main(suite, out):
    import h5py, numba, scipy, zstandard
    plan = json.loads((P.PC_E / "plan.json").read_text())
    tasks, by = [], {}
    for k in plan["tasks"]:
        d = P.load(k)
        tasks.append({"key": k, "task_wall_s": d["task_wall_s"], "task_cpu_s": d["task_cpu_s"], "commit": d["commit"]})
        kind = k.split("|")[0] + ("|" + k.split("|")[1] if k.startswith("rec") else "")
        by[kind] = by.get(kind, 0.0) + d["task_cpu_s"] / 3600
    files = {"event_files": [], "dsec_cache_files": []}
    for ds in ("etram", "dsec"):
        for rid in HR.groups(ds, "d2"):
            if ds == "etram":
                p = mp.event_path(rid)
                files["event_files"].append({"path": str(p), "size": p.stat().st_size})
            else:
                for kk in "txypwn":
                    c = FM.CACHE / rid / f"{kk}.npy"
                    files["dsec_cache_files"].append({"path": str(c), "size": c.stat().st_size})
    log = (P.PC_E / "run.log").read_text().splitlines()
    res = {"directive": "027", "host": socket.gethostname(),
           "commits": {"plan": plan["commit"], "executed": (mp.REPO / "COMMIT").read_text().strip(),
                       "tasks": sorted({t["commit"] for t in tasks})},
           "versions": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__,
                        "h5py": h5py.__version__, "zstandard": zstandard.__version__, "numba": numba.__version__},
           "suite": suite, "events": "eTraM: bk_run.read once per recording (at most six at once); DSEC: the caches of 017",
           "no_annotations_read": "directive 027 uses no boxes; no annotation or label file was opened",
           "run_log_first_last": [log[0], log[-1]],
           "projection": json.loads((P.PC_E / "projection.json").read_text()),
           "cpu_h": {"total": sum(t["task_cpu_s"] for t in tasks) / 3600, "by_kind": by},
           "n_tasks": len(tasks), "tasks": tasks, "files_read": files, "n_files": {k: len(v) for k, v in files.items()}}
    Path(out).write_text(json.dumps(res, indent=1, default=float) + "\n")
    print(json.dumps({k: res[k] for k in ("commits", "cpu_h", "n_tasks", "n_files", "run_log_first_last")}, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:3])
