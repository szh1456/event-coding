"""Directive 029 (D-029-2): results/st/report.json and results/st/provenance.json, synthetic only.

  python3 scripts/st_run.py OUT_DIR [SUITE_LINE]

report.json = {"directive": "029", "paths": ec.structure.path_costs(), "power": ec.structure.power_table()},
NumPy values converted to JSON (non-finite floats to null). No recording is read.
"""
from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS",
           "VECLIB_MAXIMUM_THREADS", "NUMBA_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import json
import math
import platform
import socket
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ec import mp, structure as st  # noqa: E402


def _json(o):
    if isinstance(o, dict):
        return {str(k): _json(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_json(v) for v in o]
    if isinstance(o, np.ndarray):
        return _json(o.tolist())
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        o = float(o)
    if isinstance(o, float) and not math.isfinite(o):
        return None
    return o


def main(out_dir, suite="not recorded"):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    timing = {}
    t0, c0 = time.time(), time.process_time()
    paths = st.path_costs()
    timing["path_costs"] = {"wall_s": time.time() - t0, "cpu_s": time.process_time() - c0}
    t1, c1 = time.time(), time.process_time()
    power = st.power_table()
    timing["power_table"] = {"wall_s": time.time() - t1, "cpu_s": time.process_time() - c1}
    (out / "report.json").write_text(json.dumps(_json({"directive": "029", "paths": paths, "power": power}),
                                                indent=1) + "\n")
    import scipy
    commit = (mp.REPO / "COMMIT").read_text().strip() if (mp.REPO / "COMMIT").exists() else "laptop"
    prov = {"directive": "029", "host": socket.gethostname(), "commit": commit,
            "versions": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__},
            "suite": suite, "timing": timing, "files_read": [], "recordings_read": "none: synthetic only"}
    (out / "provenance.json").write_text(json.dumps(prov, indent=1) + "\n")
    print(json.dumps(prov, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:3])
