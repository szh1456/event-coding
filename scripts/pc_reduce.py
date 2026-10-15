"""Directive 027, Section 6: results/pc/report.json, and the reading of Table 1 and checks 2 to 5 in checks.json.

  python3 scripts/pc_reduce.py RESULTS_DIR

``report.json`` holds exactly the keys of Section 6. ``model_phase.<kind>`` gives the ``pred`` histogram and
Rayleigh summary of ``ec.phase_control.pool`` over the twelve scenes of that kind, each scene entering as one
recording; ``model_phase.<kind>.rayleigh_null`` adds the summary of the null for Table 1.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ec import mp, phase_control as pcm  # noqa: E402
import hd_run as HR  # noqa: E402
import pc_run as P  # noqa: E402

STRATA = ("day", "night", "all")
EXPECTED = {"day": (563, 55), "night": (448, 45), "all": (253, 36)}


def _json(o):
    if isinstance(o, dict):
        return {k: _json(v) for k, v in o.items()}
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


def reading(ci):
    """Section 6, fixed before any number was seen."""
    lo, hi = ci
    if hi < 2:
        return "no lock within blocks"
    if lo > 5:
        return "lock within blocks"
    return "partial"


def main(out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    tasks = json.loads((P.PC_E / "plan.json").read_text())["tasks"]
    missing = [k for k in tasks if not P.out_path(k).exists()]
    control = [P.load(f"control|{tau}|{c}")["cell"] for tau in pcm.TAUS_US for c in pcm.CONDITIONS]
    model = {}
    for kind, shared in (("shared", True), ("independent", False)):
        scenes = {k: [P.load(k)["group"]] for k in tasks if k.startswith("model|") and k.split("|")[2] == str(int(shared))}
        p = pcm.pool(scenes)
        model[kind] = {"hist": p["hist"]["pred"], "rayleigh": p["rayleigh"]["pred"], "rayleigh_null": p["rayleigh"]["null"],
                       "n_scenes": len(scenes)}
    by = {s: {} for s in STRATA}
    for ds in ("etram", "dsec"):
        for rid in HR.groups(ds, "d2"):
            d = P.load(f"rec|{ds}|{rid}")
            by["all" if ds == "dsec" else mp.lighting(rid)][rid] = d["groups"]
    strata = {s: pcm.pool(by[s]) for s in STRATA}
    report = _json({"directive": "027", "control": control, "model_phase": model, "strata": strata})
    (out / "report.json").write_text(json.dumps(report, indent=1) + "\n")

    chk = {"missing_tasks": missing, "counts": {}, "control": {}, "model": {}, "coverage_order": {}, "hist_holds": {},
           "reading": {}}
    for s in STRATA:
        chk["counts"][s] = {"groups": strata[s]["n_groups"], "recordings": strata[s]["n_recordings"],
                            "expected": list(EXPECTED[s]),
                            "ok": (strata[s]["n_groups"], strata[s]["n_recordings"]) == EXPECTED[s]}
        c = strata[s]["coverage"]
        chk["coverage_order"][s] = c["n_true_band"] <= c["n_true_tested"] <= c["n_true_moving"] <= c["n_true_window"]
        chk["hist_holds"][s] = {"hist_pred": int(sum(strata[s]["hist"]["pred"])),
                                "rayleigh_pixels": strata[s]["rayleigh"]["pred"]["pixels"],
                                "ok": sum(strata[s]["hist"]["pred"]) >= strata[s]["rayleigh"]["pred"]["pixels"]}
        ci = strata[s]["rayleigh"]["pred"]["mean_Z_ci95"]
        chk["reading"][s] = {"mean_Z": strata[s]["rayleigh"]["pred"]["mean_Z"], "ci95": ci, "reading": reading(ci)}
    worst = {}
    shared_ok = True
    for c in control:
        for k, f in c["F"].items():
            if c["condition"] == "shared":
                shared_ok &= f == 1.0
            elif c["condition"] == "independent" and math.isfinite(c["equation"][k]):
                worst[f"{c['tau_us']}|{k}"] = abs(f - c["equation"][k])
    chk["control"] = {"shared_all_F_1": bool(shared_ok), "independent_max_abs_dev": max(worst.values()),
                      "independent_n_cells_with_equation": len(worst), "independent_within_0.01": max(worst.values()) <= 0.01}
    chk["model"] = {"shared_mean_Z": model["shared"]["rayleigh"]["mean_Z"],
                    "independent_mean_Z": model["independent"]["rayleigh"]["mean_Z"],
                    "ok": model["shared"]["rayleigh"]["mean_Z"] > 10 and 0.8 <= model["independent"]["rayleigh"]["mean_Z"] <= 1.25}
    (out / "checks.json").write_text(json.dumps(_json(chk), indent=1) + "\n")
    print(json.dumps(_json(chk), indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
