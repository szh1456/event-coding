"""Directive 004, Section 5: preflight P0 to P2 on the execution host (P3 is the pytest run).

  python3 scripts/af_preflight.py REPORT_003.md GP_PREFLIGHT.json GP_PROVENANCE.json OUT.json

P0: report 003 exists with status DONE. P1: the environment equals P1 of directive 003.
P2: the Stage C per-row files of directive 003 exist and their SHA-256 equal its provenance.
"""
import json
import os
import re
import sys
from pathlib import Path

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_v, "1")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import gp_preflight  # noqa: E402
import mp_preflight  # noqa: E402


def main(rep003, gp_pre, gp_prov, out):
    text = Path(rep003).read_text() if Path(rep003).is_file() else ""
    m = re.search(r"^status:\s*(\S+)", text, re.M)
    p0 = {"report": "docs/directives/reports/003.md", "exists": bool(text), "status": m.group(1) if m else None}
    p0["pass"] = p0["status"] == "DONE"
    ref = json.loads(Path(gp_pre).read_text())["P1"]
    env = mp_preflight.env()
    diff = {k: {"003": ref.get(k), "004": env.get(k)} for k in gp_preflight.VERSION_KEYS if ref.get(k) != env.get(k)}
    p1 = env | {"compared_with": "results/gp/preflight.json#/P1", "differences": diff, "pass": not diff}
    p2 = gp_preflight.check(json.loads(Path(gp_prov).read_text())["per_row_files"])
    p2 |= {"reference": "results/gp/provenance.json#/per_row_files"}
    p2["pass"] = p2["pass"] and p2["n_expected"] == 700
    Path(out).write_text(json.dumps({"directive": "004", "P0": p0, "P1": p1, "P2": p2}, indent=1) + "\n")
    print(json.dumps({"P0": p0, "P1": {"pass": p1["pass"], "differences": diff},
                      "P2": {k: v for k, v in p2.items() if k not in ("missing", "mismatch")}}, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:5])
