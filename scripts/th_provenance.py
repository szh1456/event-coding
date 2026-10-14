"""Directive 020, Section 9: results/th/provenance.json.

  python3 scripts/th_provenance.py SUITE_LINE OUT.json
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
import th_run as TR  # noqa: E402


def main(suite, out):
    import h5py, numba, scipy, zstandard
    tasks, files = [], {"event_files": [], "dsec_cache_files": []}
    for ds in ("etram", "dsec"):
        for rid in HR.groups(ds, "d2"):
            d = TR.load(ds, rid)
            tasks.append({"dataset": ds, "recording": rid, "n_groups": len(d["groups"]), "read_s": d["read_s"],
                          "task_wall_s": d["task_wall_s"], "task_cpu_s": d["task_cpu_s"], "commit": d["commit"],
                          "group_cpu_s": sum(g["cpu_s"] for g in d["groups"])})
            if ds == "etram":
                p = mp.event_path(rid)
                files["event_files"].append({"path": str(p), "size": p.stat().st_size})
            else:
                for k in "txypwn":
                    c = FM.CACHE / rid / f"{k}.npy"
                    files["dsec_cache_files"].append({"path": str(c), "size": c.stat().st_size})
    log = (TR.TH_E / "run.log").read_text().splitlines()
    res = {"directive": "020", "host": socket.gethostname(),
           "commits": {"plan": json.loads((TR.TH_E / "plan.json").read_text())["commit"],
                       "executed": (mp.REPO / "COMMIT").read_text().strip(), "tasks": sorted({t["commit"] for t in tasks})},
           "versions": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__,
                        "h5py": h5py.__version__, "zstandard": zstandard.__version__, "numba": numba.__version__},
           "suite": suite, "events": "eTraM: bk_run.read once per recording (at most six at once); DSEC: the caches of 017",
           "no_annotations_read": "directive 020 uses no boxes; no annotation or label file was opened",
           "run_log_first_last": [log[0], log[-1]],
           "projection": json.loads((TR.TH_E / "projection.json").read_text()),
           "cpu_h": {"tasks": sum(t["task_cpu_s"] for t in tasks) / 3600,
                     "groups": sum(t["group_cpu_s"] for t in tasks) / 3600},
           "n_tasks": len(tasks), "tasks": tasks, "files_read": files, "n_files": {k: len(v) for k, v in files.items()}}
    Path(out).write_text(json.dumps(res, indent=1, default=float) + "\n")
    print(json.dumps({k: res[k] for k in ("commits", "cpu_h", "n_tasks", "n_files", "run_log_first_last")}, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:3])
