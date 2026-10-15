"""Directive 028, Section 9: results/pc2/provenance.json.

  python3 scripts/pc2_provenance.py SUITE_LINE CHECKS.json OUT.json
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
import hd_run as HR  # noqa: E402
import ph_run as P  # noqa: E402


def main(suite, checks, out):
    import scipy
    files = {"ph_outputs": [], "hd_outputs": [], "committed_results": []}
    for ds in ("etram", "dsec"):
        for rid in HR.groups(ds, "d2"):
            p = P.out_path(f"rec|{ds}|{rid}")
            files["ph_outputs"].append({"path": str(p), "size": p.stat().st_size})
    for key in json.loads((HR.HD_E / "plan.json").read_text())["tasks"]:
        if not key.startswith("d3"):
            p = HR.out_path(key)
            files["hd_outputs"].append({"path": str(p), "size": p.stat().st_size})
    for rel in ("results/ph/report.json", "results/hd/frontier.json"):
        p = mp.REPO / rel
        files["committed_results"].append({"path": rel, "size": p.stat().st_size})
    c = json.loads(Path(checks).read_text())
    res = {"directive": "028", "host": socket.gethostname(),
           "commit": (mp.REPO / "COMMIT").read_text().strip(),
           "versions": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__},
           "suite": suite, "wall_s": c["wall_s"], "cpu_s": c["cpu_s"],
           "recordings_read": "none: only the kept per-group outputs of directives 022 and 019 and committed results",
           "files_read": files, "n_files": {k: len(v) for k, v in files.items()}}
    Path(out).write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps({k: res[k] for k in ("commit", "wall_s", "cpu_s", "n_files")}, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:4])
