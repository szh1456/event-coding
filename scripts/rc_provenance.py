"""Directive 017, Section 9: results/rc/provenance.json.

  python3 scripts/rc_provenance.py SUITE_LINE OUT.json
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
import ds_run as DR  # noqa: E402
import fb_run as FB  # noqa: E402
import rc_run as RC  # noqa: E402


def main(suite, out):
    import h5py, numba, scipy, zstandard
    tasks, files = [], {"event_files": [], "annotation_files": [], "dsec_label_files": [], "remake_per_group_files": [],
                        "dsec_cache_files_written": []}
    for ds in ("etram", "dsec"):
        for rid in FB.recordings(ds, "R"):
            d = RC.load(ds, rid)
            tasks.append({"dataset": ds, "recording": rid, "n_groups": len(d["groups"]), "read_s": d["read_s"],
                          "task_wall_s": d["task_wall_s"], "task_cpu_s": d["task_cpu_s"], "commit": d["commit"],
                          "first": min(g["finished_utc"] for g in d["groups"]),
                          "last": max(g["finished_utc"] for g in d["groups"])})
            p = mp.event_path(rid) if ds == "etram" else DR.DATA / rid / "events.h5"
            files["event_files"].append({"path": str(p), "size": p.stat().st_size})
            if ds == "etram":
                a = mp.annotation_path(rid)
                files["annotation_files"].append({"path": str(a), "size": a.stat().st_size})
                base = FB.BK_DIR / "R"
            else:
                a = RC.DET / rid / "tracks.npy"
                files["dsec_label_files"].append({"path": str(a), "size": a.stat().st_size})
                c = RC.CACHE_D / f"{rid}.npz"
                files["dsec_cache_files_written"].append({"path": str(c), "size": c.stat().st_size})
                base = DR.BASE / "ds" / "R"
            for f in sorted(base.glob(f"groups_{rid}_[0-9][0-9][0-9].pkl")):
                files["remake_per_group_files"].append({"path": str(f), "size": f.stat().st_size})
    log = (RC.RC_E / "run.log").read_text().splitlines()
    res = {"directive": "017", "host": socket.gethostname(), "commits": {"executed": (mp.REPO / "COMMIT").read_text().strip(),
                                                                         "tasks": sorted({t["commit"] for t in tasks})},
           "versions": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__,
                        "h5py": h5py.__version__, "zstandard": zstandard.__version__, "numba": numba.__version__},
           "suite": suite, "decoders": "ec.blockcodec_fast.decode_events_T and reconstruct (ec.codec.use_fast_decoders)",
           "run_log_first_last": [log[0], log[-1]],
           "cpu_h": sum(t["task_cpu_s"] for t in tasks) / 3600, "n_tasks": len(tasks),
           "n_groups": sum(t["n_groups"] for t in tasks), "tasks": tasks,
           "dsec_detection": json.loads((RC.DET / "download.json").read_text()), "files_read": files,
           "n_files": {k: len(v) for k, v in files.items()}}
    Path(out).write_text(json.dumps(res, indent=1, default=float) + "\n")
    print(json.dumps({k: res[k] for k in ("commits", "cpu_h", "n_tasks", "n_groups", "n_files", "run_log_first_last")},
                     indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:3])
