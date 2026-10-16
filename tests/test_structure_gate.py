"""Gate for directive 029: path costs, the partial-lock scenes and the figure script."""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

from ec import phase_control as pc
from ec import structure as st

ROOT = Path(__file__).resolve().parent.parent


def test_theory_constants():
    th = st.theory(1000.0)
    assert np.isclose(th["D_A"], 50.0 ** 2 + 1000.0 ** 2 / 12)
    assert np.isclose(th["D_A"], (th["s2"] + 2 * 50.0 ** 2) / 3)
    assert 0 <= th["Gamma"] <= 0.5 * np.log(2 * np.pi * np.e / 12) + 1e-9
    assert th["R_mid_lower"] <= th["R_mid_upper"] < th["R_fine"]
    assert abs(st.eta(1000.0, 1e-3) - np.log(1000.0)) < 1e-3


def test_quantizers_meet_their_targets():
    px = st.pixel_codes(1000.0, n_pix=20_000)
    th = st.theory(1000.0)
    for name, rate in (("fine", th["R_fine"]), ("scalar", th["R_mid_lower"])):
        assert px[name]["D"] <= px[name]["D_target"] * (1 + 1e-9)
        assert px[name]["bits_per_pixel"] >= rate / np.log(2) - 0.05


def test_motion_bits_grow_as_log():
    a, b = st.motion_code(100, n_paths=40), st.motion_code(10_000, n_paths=4)
    assert a["D_over_DA_mean"] <= 1 + st.XI and b["D_over_DA_mean"] <= 1 + st.XI
    assert abs((b["bits"] - a["bits"]) - 2 * np.log2(100)) < 1.0


def test_lock_width():
    ev0 = st.lock_scene(160, 40, 6.5, 2000.0, 3, 0.0, 40, 8, 1, 0.0, 0.0)
    ev1 = st.lock_scene(160, 40, 6.5, 2000.0, 3, 0.0, 40, 8, 1, 1.0, 0.0)
    assert set(np.unique(ev0[1])) == set(np.unique(ev1[1]))
    z = {}
    for w in (0.0, 1.0):
        o = pc.block_phases(st.lock_scene(320, 240, 6.5, 2000.0, 3, 0.05, 40, 8, 1, w, 0.0), 5, 320, 240)
        z[w] = pc.rayleigh(o["blocks"]["pred"])["mean_Z"]
    assert z[0.0] > 10.0 and 0.7 < z[1.0] < 1.4


def test_figures(tmp_path):
    rows = []
    for M in (10, 100, 1000):
        mc = st.motion_code(M, n_paths=5)
        rows.append({"M": M, "fine_theory_bits": 6.0 * M, "fine_code_bits": 6.8 * M, "scalar_upper_bits": 0.5 * M,
                     "scalar_lower_bits": 0.3 * M, "scalar_code_bits": 0.8 * M, "motion_code_bits": mc["bits"],
                     "motion": mc})
    power = [{"w": w, "cv": cv, "mean_Z": 1 + 50 * (1 - w) ** 3, "ci95": [1, 2 + 50 * (1 - w) ** 3]}
             for cv in (0.0, 0.2) for w in (0.0, 0.5, 1.0)]
    (tmp_path / "st").mkdir()
    (tmp_path / "st" / "report.json").write_text(json.dumps({"paths": {"rows": rows}, "power": {"rows": power}}))
    r = ROOT / "results"
    subprocess.run([sys.executable, str(ROOT / "scripts" / "fig_029.py"), "--st", str(tmp_path / "st"), "--pc",
                    str(r / "pc"), "--pc2", str(r / "pc2"), "--hc", str(r / "hc"), "--paper", str(r / "paper"),
                    "--out", str(tmp_path / "out")], check=True)
    for name in ("fig_scaling", "fig_phase4", "fig_coding_cost", "fig_task"):
        for ext in ("pdf", "png", "json"):
            assert (tmp_path / "out" / f"{name}.{ext}").stat().st_size > 0
    fs = json.loads((tmp_path / "out" / "fig_scaling.json").read_text())
    assert fs["motion_code_bits"] == [x["motion_code_bits"] for x in rows]
    fp = json.loads((tmp_path / "out" / "fig_phase4.json").read_text())
    rep = json.loads((r / "pc" / "report.json").read_text())
    assert fp["c"]["recordings_day"] == rep["strata"]["day"]["rayleigh"]["pred"]["mean_Z_ci95"]
