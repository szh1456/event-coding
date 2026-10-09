"""Directive 003, Section 5: preflight P1 and P2 on the execution host (P3 is the pytest run).

  python3 scripts/gp_preflight.py RG_PREFLIGHT.json MP_PROVENANCE.json RG_PROVENANCE.json OUT.json

P1: the environment, compared field by field with P1 of directive 002.
P2: the per-instant files of directive 001 and the Stage R per-row files of directive 002 exist and their
SHA-256 equal the two provenance files.
"""
import hashlib
import json
import os
import sys
from pathlib import Path

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_v, "1")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import mp_preflight  # noqa: E402

VERSION_KEYS = ("host", "python", "numpy", "scipy", "h5py", "zstandard", "numba", "blas_threads")


def check(files):
    bad, missing = [], []
    for f in files:
        p = Path(f["path"])
        if not p.is_file():
            missing.append(str(p))
        elif hashlib.sha256(p.read_bytes()).hexdigest() != f["sha256"]:
            bad.append(str(p))
    return {"n_expected": len(files), "n_found": len(files) - len(missing), "n_sha256_mismatch": len(bad),
            "missing": missing, "mismatch": bad, "pass": len(files) > 0 and not missing and not bad}


def main(rg_pre, mp_prov, rg_prov, out):
    ref = json.loads(Path(rg_pre).read_text())["P1"]
    env = mp_preflight.env()
    diff = {k: {"002": ref.get(k), "003": env.get(k)} for k in VERSION_KEYS if ref.get(k) != env.get(k)}
    p1 = env | {"compared_with": "results/rg/preflight.json#/P1", "differences": diff, "pass": not diff}
    mp_files = check(json.loads(Path(mp_prov).read_text())["per_instant_files"])
    rg_files = check(json.loads(Path(rg_prov).read_text())["per_row_files"]["R"])
    p2 = {"directive_001_per_instant_files": mp_files | {"reference": "results/mp/provenance.json#/per_instant_files"},
          "directive_002_stage_R_per_row_files": rg_files | {"reference": "results/rg/provenance.json#/per_row_files/R"},
          "pass": mp_files["pass"] and rg_files["pass"] and mp_files["n_expected"] == 700
          and rg_files["n_expected"] == 700}
    Path(out).write_text(json.dumps({"directive": "003", "P1": p1, "P2": p2}, indent=1) + "\n")
    print(json.dumps({"P1": {"pass": p1["pass"], "differences": diff},
                      "P2": {k: (v if not isinstance(v, dict) else {kk: vv for kk, vv in v.items()
                                                                     if kk not in ("missing", "mismatch")})
                             for k, v in p2.items()}}, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:5])
