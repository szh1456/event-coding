"""Directive 018, Section 9: results/fm/provenance.json.

  python3 scripts/fm_provenance.py SUITE_LINE OUT.json
"""
from __future__ import annotations

import json
import pickle
import platform
import socket
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ec import mp  # noqa: E402
import ds_run as DR  # noqa: E402
import fb_run as FB  # noqa: E402
import fm_run as FM  # noqa: E402
import rc_run as RC  # noqa: E402


def sh(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True).stdout.strip()


def main(suite, out):
    import h5py, numba, scipy, zstandard
    tasks, files = [], {"event_files": [], "annotation_files": [], "dsec_label_files": [], "dsec_cache_files": [],
                        "remake_per_group_files": []}
    for ds in ("etram", "dsec"):
        for rid in FB.recordings(ds, "R"):
            for f in sorted(FM.outdir(ds).glob(f"{rid}_[0-9][0-9][0-9].pkl")):
                with open(f, "rb") as fh:
                    d = pickle.load(fh)
                tasks.append({"key": d["key"], "n_groups": len(d["groups"]), "read_s": d["read_s"],
                              "task_wall_s": d["task_wall_s"], "task_cpu_s": d["task_cpu_s"], "commit": d["commit"],
                              "group_cpu_s": sum(g["cpu_s"] for g in d["groups"]),
                              "first": min(g["finished_utc"] for g in d["groups"]),
                              "last": max(g["finished_utc"] for g in d["groups"])})
            if ds == "etram":
                p = mp.event_path(rid)
                files["event_files"].append({"path": str(p), "size": p.stat().st_size})
                a = mp.annotation_path(rid)
                files["annotation_files"].append({"path": str(a), "size": a.stat().st_size})
                base = FB.BK_DIR / "R"
            else:
                a = RC.DET / rid / "tracks.npy"
                files["dsec_label_files"].append({"path": str(a), "size": a.stat().st_size})
                for k in "txypwn":
                    c = FM.CACHE / rid / f"{k}.npy"
                    files["dsec_cache_files"].append({"path": str(c), "size": c.stat().st_size})
                base = DR.BASE / "ds" / "R"
            for f in sorted(base.glob(f"groups_{rid}_[0-9][0-9][0-9].pkl")):
                files["remake_per_group_files"].append({"path": str(f), "size": f.stat().st_size})
    log = (FM.FM_E / "run.log").read_text().splitlines()
    res = {"directive": "018", "host": socket.gethostname(),
           "commits": {"plan": json.loads((FM.FM_E / "plan.json").read_text())["commit"],
                       "executed": (mp.REPO / "COMMIT").read_text().strip(), "tasks": sorted({t["commit"] for t in tasks})},
           "versions": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__,
                        "h5py": h5py.__version__, "zstandard": zstandard.__version__, "numba": numba.__version__,
                        "ffmpeg": sh("ffmpeg -hide_banner -version | head -n 1"), "ffmpeg_path": sh("command -v ffmpeg"),
                        "libx265": sh("dpkg-query -W -f='${Package} ${Version}' 'libx265-*' 2>/dev/null"),
                        "libx265_so": sh("ldd $(command -v ffmpeg) | grep -o 'libx265[^ ]*' | head -n 1")},
           "ffmpeg_install": "the system build of the host (Ubuntu 22.04 package), used as it is; nothing installed",
           "suite": suite, "decoders": "ec.blockcodec_fast.decode_events_T and reconstruct (ec.codec.use_fast_decoders)",
           "window_sums": "wrapped from the runner to add n_enter and n_blocks (Table 4); other outputs unchanged",
           "events": "eTraM: bk_run.read per task of 6 groups; DSEC: the caches written by directive 017",
           "run_log_first_last": [log[0], log[-1]],
           "projection": json.loads((FM.FM_E / "projection.json").read_text()),
           "cpu_h": {"tasks": sum(t["task_cpu_s"] for t in tasks) / 3600,
                     "groups": sum(t["group_cpu_s"] for t in tasks) / 3600,
                     "note": "CPU of the task processes and of the ffmpeg processes they started (RUSAGE_CHILDREN)"},
           "n_tasks": len(tasks), "n_groups": sum(t["n_groups"] for t in tasks), "tasks": tasks, "files_read": files,
           "n_files": {k: len(v) for k, v in files.items()}}
    Path(out).write_text(json.dumps(res, indent=1, default=float) + "\n")
    print(json.dumps({k: res[k] for k in ("commits", "versions", "cpu_h", "n_tasks", "n_groups", "n_files",
                                          "run_log_first_last")}, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:3])
