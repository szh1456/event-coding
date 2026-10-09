"""Directive 002, Section 5: preflight P1 and P2 on the execution host (P3 is the pytest run).

  python3 scripts/rg_preflight.py MP_PREFLIGHT.json MP_PROVENANCE.json OUT.json

P1: the environment, compared field by field with P1 of directive 001.
P2: the 700 per-instant files of directive 001 exist and their SHA-256 equal its provenance.
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


def main(mp_pre, mp_prov, out):
    ref = json.loads(Path(mp_pre).read_text())["P1"]
    env = mp_preflight.env()
    diff = {k: {"001": ref.get(k), "002": env.get(k)} for k in VERSION_KEYS if ref.get(k) != env.get(k)}
    p1 = env | {"compared_with": "results/mp/preflight.json#/P1", "differences": diff, "pass": not diff}
    files = json.loads(Path(mp_prov).read_text())["per_instant_files"]
    bad, missing = [], []
    for f in files:
        p = Path(f["path"])
        if not p.is_file():
            missing.append(str(p)); continue
        if hashlib.sha256(p.read_bytes()).hexdigest() != f["sha256"]:
            bad.append(str(p))
    p2 = {"n_expected": len(files), "n_found": len(files) - len(missing), "n_sha256_mismatch": len(bad),
          "missing": missing, "mismatch": bad, "reference": "results/mp/provenance.json#/per_instant_files",
          "pass": len(files) == 700 and not missing and not bad}
    res = {"directive": "002", "P1": p1, "P2": p2}
    Path(out).write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps({"P1": {"pass": p1["pass"], "differences": diff}, "P2": {k: v for k, v in p2.items()
                                                                              if k not in ("missing", "mismatch")}},
                     indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:4])
