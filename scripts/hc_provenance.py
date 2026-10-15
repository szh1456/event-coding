"""Directive 021, Section 9: results/hc/provenance.json.

  python3 scripts/hc_provenance.py SUITE_LINE OUT.json
"""
from __future__ import annotations

import json
import platform
import socket
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ec import mp  # noqa: E402
import fb_run as FB  # noqa: E402
import fm_run as FM  # noqa: E402
import hc_run as HC  # noqa: E402
import hd_run as HR  # noqa: E402
import rc_run as RC  # noqa: E402


def sh(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True).stdout.strip()


def main(suite, out):
    import h5py, numba, scipy, zstandard
    plan = json.loads((HC.HC_E / "plan.json").read_text())
    tasks, by = [], {}
    for k in plan["tasks"]:
        d = HC.load(k)
        tasks.append({"key": k, "task_wall_s": d["task_wall_s"], "task_cpu_s": d["task_cpu_s"], "commit": d["commit"],
                      "read_s": d.get("read_s")})
        kind = k.split("|")[0] + ("|" + k.split("|")[1] if k.startswith("d1") else "")
        by[kind] = by.get(kind, 0.0) + d["task_cpu_s"] / 3600
    files = {"event_files": [], "annotation_files": [], "dsec_label_files": [], "dsec_cache_files": [],
             "remake_per_group_files": [], "hd_019_outputs": []}
    for ds in ("etram", "dsec"):
        for rid, rr in HR.groups(ds, "d1").items():
            if ds == "etram":
                p = mp.event_path(rid)
                files["event_files"].append({"path": str(p), "size": p.stat().st_size})
                a = mp.annotation_path(rid)
                files["annotation_files"].append({"path": str(a), "size": a.stat().st_size})
                base = FB.BK_DIR / "R"
            else:
                a = RC.DET / rid / "tracks.npy"
                files["dsec_label_files"].append({"path": str(a), "size": a.stat().st_size})
                for kk in "txypwn":
                    c = FM.CACHE / rid / f"{kk}.npy"
                    files["dsec_cache_files"].append({"path": str(c), "size": c.stat().st_size})
                base = HR.RC.DR.BASE / "ds" / "R"
            for f in sorted(base.glob(f"groups_{rid}_[0-9][0-9][0-9].pkl")):
                files["remake_per_group_files"].append({"path": str(f), "size": f.stat().st_size})
            for r in rr:
                f = HR.out_path(f"d1|{ds}|{rid}|{r['j']}")
                files["hd_019_outputs"].append({"path": str(f), "size": f.stat().st_size})
    log = (HC.HC_E / "run.log").read_text().splitlines()
    res = {"directive": "021", "host": socket.gethostname(),
           "commits": {"plan": plan["commit"], "executed": (mp.REPO / "COMMIT").read_text().strip(),
                       "tasks": sorted({t["commit"] for t in tasks})},
           "versions": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__,
                        "h5py": h5py.__version__, "zstandard": zstandard.__version__, "numba": numba.__version__,
                        "ffmpeg": sh("ffmpeg -hide_banner -version | head -n 1"), "ffmpeg_path": sh("command -v ffmpeg"),
                        "libx265": sh("dpkg-query -W -f='${Package} ${Version}' 'libx265-*' 2>/dev/null"),
                        "libx265_so": sh("ldd $(command -v ffmpeg) | grep -o 'libx265[^ ]*' | head -n 1")},
           "suite": suite, "scratch": str(HC.WORK) + " (local disk, /data)",
           "fidelities": "ec.hevcdiag.fidelities wrapped by hd_run (import) to also return its summed terms; F unchanged",
           "events": "eTraM: hd_run.events (bk_run.read, at most six at once); DSEC: the caches of directive 017",
           "run_log_first_last": [log[0], log[-1]],
           "projection": json.loads((HC.HC_E / "projection.json").read_text()),
           "cpu_h": {"total": sum(t["task_cpu_s"] for t in tasks) / 3600, "by_kind": by,
                     "note": "CPU of the task processes and of the ffmpeg processes they started"},
           "n_tasks": len(tasks), "tasks": tasks, "files_read": files, "n_files": {k: len(v) for k, v in files.items()}}
    Path(out).write_text(json.dumps(res, indent=1, default=float) + "\n")
    print(json.dumps({k: res[k] for k in ("commits", "versions", "cpu_h", "n_tasks", "n_files", "run_log_first_last")},
                     indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:3])
