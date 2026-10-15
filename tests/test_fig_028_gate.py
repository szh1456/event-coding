"""Gate for directive 028: the figure script on constructed inputs in the layouts of Section 5, and the
committed results of directives 021 and 026."""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
STRATA = ("day", "night", "all")
QPS = (12, 14, 16, 18, 20, 22, 24, 28)


def _pc():
    control = []
    for tau in (1000.0, 4000.0):
        for c in ("shared", "independent", "jitter"):
            r = {f"k{k}": 33333.0 / k / tau for k in (1, 3, 64)}
            f = {kk: 1.0 if c == "shared" else min(v, 1.0) for kk, v in r.items()}
            control.append({"tau_us": tau, "condition": c, "F": f, "dt_over_tau": r})
    hist = {"pred": [100] * 20, "null": [100] * 20}
    st = {"hist": hist, "rayleigh": {"pred": {"mean_Z": 1.01}, "null": {"mean_Z": 0.98}}}
    return {"control": control, "strata": {k: st for k in STRATA},
            "model_phase": {"shared": {"hist": [500, 200] + [0] * 16 + [50, 300]}, "independent": {"hist": [60] * 20}}}


def _bf():
    rows = []
    for j, r in enumerate((1 / 16, 1 / 8, 1 / 4, 1 / 2, 1.0, 2.0)):
        rows.append({"r_lo": r / 1.4, "r_hi": r * 1.4, "r_centre": r, "N": 50_000 if j else 5_000, "N2": 50_000,
                     "M": 1, "F": min(r, 1.0), "F_ci95": [min(r, 1.0) - 0.01, min(r, 1.0) + 0.01], "F0": r / 2,
                     "n_recordings": 20})
    s = {"coverage": {"share_events_with_tau_reg": 0.33, "share_events_in_plotted_bins": 0.3},
         "grids": {"s1_k32": rows, "s1_k64": rows}}
    return {"definitions": {}, "strata": {k: s for k in STRATA}}


def _mt():
    g = {"reference": {"success1": 0.9, "ci95": [0.85, 0.95], "n_squares": 100, "n_undefined": 3},
         "qp": {f"qp{q}": {"b": 40.0 / (1 + i), "success1": 0.9 - 0.08 * i, "ci95": [0.85 - 0.08 * i, 0.95 - 0.08 * i],
                           "fail_share": 0.02 * i, "median_err": 0.5 + 0.1 * i, "n_squares": 100}
                for i, q in enumerate(QPS)}}
    return {"definitions": {}, "strata": {k: {"s1_k3": g, "s1_k64": g} for k in STRATA}}


def test_figures(tmp_path):
    for d, f, obj in (("pc", "report.json", _pc()), ("pc2", "binned_fidelity.json", _bf()),
                      ("pc2", "motion_task.json", _mt())):
        (tmp_path / d).mkdir(exist_ok=True)
        (tmp_path / d / f).write_text(json.dumps(obj))
    r = ROOT / "results"
    subprocess.run([sys.executable, str(ROOT / "scripts" / "fig_028.py"), "--pc", str(tmp_path / "pc"), "--pc2",
                    str(tmp_path / "pc2"), "--hc", str(r / "hc"), "--paper", str(r / "paper"), "--out",
                    str(tmp_path / "out")], check=True)
    for name in ("fig_control", "fig_recordings", "fig_coding"):
        for ext in ("pdf", "png", "json"):
            assert (tmp_path / "out" / f"{name}.{ext}").stat().st_size > 0
    fc = json.loads((tmp_path / "out" / "fig_control.json").read_text())
    assert all(v == 1.0 for v in fc["shared"]["F"])
    fr = json.loads((tmp_path / "out" / "fig_recordings.json").read_text())
    assert len(fr["c"]["day"]["s1_k32"]["F"]) == 5            # the bin with 5,000 events is left out
    assert abs(np.mean(fr["b"]["day"]["density"]) - 1.0) < 1e-9
    fg = json.loads((tmp_path / "out" / "fig_coding.json").read_text())
    assert fg["day"]["s1_k64"]["success1"][0] == 0.9 and fg["day"]["s1_k3"]["reference_success1"] == 0.9
