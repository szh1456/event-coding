"""Directive 013, Section 13: results/dt/preflight.json and results/dt/provenance.json.

  python3 scripts/dt_provenance.py SUITE_LINE OUT_DIR

Reads the host preflight of Stage P, the Stage T task records and the provenance of directive 009;
hashes the Stage T per-group files. The per-group and stream files of the reporting sequences are those
of directive 009 (D-013-2), listed with the size and SHA-256 that P4 checked them against.
"""
from __future__ import annotations

import hashlib
import json
import re
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ec import mp  # noqa: E402
import dt_run as DT  # noqa: E402


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 24), b""):
            h.update(b)
    return h.hexdigest()


def main(suite, outdir):
    out = Path(outdir)
    tuning, reporting = DT.subsets()
    pre = json.loads((DT.DT / "preflight.json").read_text())
    pre["P2"]["suite"] = {"command": "python3 -m pytest -q -p no:anyio", "result": suite,
                          "pass": bool(re.search(r"\b\d+ passed", suite)) and "exit 0" in suite
                          and not re.search(r"\b[1-9]\d* (failed|skipped|errors?)\b", suite)}
    (out / "preflight.json").write_text(json.dumps(pre, indent=1) + "\n")
    ds = json.loads((mp.REPO / "results" / "ds" / "provenance.json").read_text())
    tasks = [json.loads(p.read_text()) for p in sorted((DT.DT / "T").glob("task_*.json"))]
    t0, t1 = (int((DT.DT / "logs" / n).read_text()) for n in ("T_start", "T_end"))
    plan = json.loads((DT.DT / "T" / "plan.json").read_text())
    pkl = [{"path": str(p), "size": p.stat().st_size, "sha256": sha(p)} for p in sorted((DT.DT / "T").glob("groups_*.pkl"))]

    def rep(path):
        return any(Path(path).name.startswith((f"groups_{s}_", f"{s}__")) for s in reporting)
    prov = {"directive": "013", "host": socket.gethostname(),
            "commits": {"population_check": "d85aecc", "tuning": "c26043a", "stage_T_runner": plan["commit"],
                        "executed": (mp.REPO / "COMMIT").read_text().strip()},
            "versions": {k: pre["P1"][k] for k in ("python", "numpy", "scipy", "h5py", "zstandard", "numba", "hdf5plugin")},
            "paths": {"data": ds["paths"]["data"], "computed": str(DT.DT)},
            "frozen": "B20_rho1.0", "spacing": 60,
            "stage_T": {"n_groups": sum(len(t["group_s"]) for t in tasks), "n_tasks": len(tasks),
                        "workers": "up to 12 (adaptive) under nice -n 19, one sequence read at a time, memory guard",
                        "wall_s": t1 - t0, "cpu_h_sum_of_evaluate_group": sum(sum(t["group_s"]) for t in tasks) / 3600,
                        "cpu_h_sum_of_task_wall": sum(t["wall_s"] for t in tasks) / 3600,
                        "projected_cpu_h": 28.1, "limit_cpu_h": 80, "per_group_files": pkl},
            "stage_R": {"ran": False, "source": "Stage R of directive 009 (D-013-2), checked in P4",
                        "per_group_files": [f for f in ds["per_group_files"] if rep(f["path"])],
                        "stream_files": [f for f in ds["stream_files_stage_R"] if rep(f["path"])]},
            "eTraM_opened": False}
    (out / "provenance.json").write_text(json.dumps(prov, indent=1) + "\n")
    print(json.dumps({k: v for k, v in prov["stage_T"].items() if k != "per_group_files"} |
                     {"n_R_groups": len(prov["stage_R"]["per_group_files"]),
                      "n_R_streams": len(prov["stage_R"]["stream_files"]), "suite": pre["P2"]["suite"]}, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:3])
