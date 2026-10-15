"""Gate for directive 027: the controlled model, the per-block phase test and the figure script."""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

from ec import hevcdiag as hd
from ec import phase as ph
from ec import phase_control as pc

ROOT = Path(__file__).resolve().parent.parent
W, H = 320, 240


def test_conditions_share_edges_and_counts():
    ev = {c: pc.control_scene(160, 40, 6, 2000.0, 3, 0.05, 40, 12, 7, c) for c in pc.CONDITIONS}
    n = {c: len(e[0]) for c, e in ev.items()}
    assert max(n.values()) - min(n.values()) <= 0.002 * n["shared"]
    for c in pc.CONDITIONS:                   # every pixel of every row fires on each passage
        assert set(np.unique(ev[c][1])) == set(range(160))


def test_exact_motion_on_the_model():
    f = {}
    for c in pc.CONDITIONS:
        e = pc.control_scene(160, 40, 6, 2000.0, 3, 0.05, 40, 12, 7, c)
        f[c] = {k: hd.oracle_shift(e, 6, 1, k, 160, 40, 12)["F"] for k in (3, 64)}
    assert f["shared"][3] == 1.0 and f["shared"][64] == 1.0
    assert abs(f["independent"][64] - hd.binfidmoved(pc.T0 / 64, 2000.0, 3)) < 0.01
    assert abs(f["jitter"][64] - f["independent"][64]) < 0.02          # a jitter of 0.05 tau changes little
    assert f["independent"][3] > 0.9


def test_rayleigh():
    r = pc.rayleigh([[5, 5.0, 0.0], [10, 0.0, 0.0], [2, 2.0, 0.0]])     # the block of 2 pixels is left out
    assert r["blocks"] == 2 and r["pixels"] == 15
    assert r["mean_Z"] == 2.5 and r["share_Z_above_ln100"] == 0.5


def test_block_phases_separate_shared_from_independent():
    z = {}
    for shared in (False, True):
        o = pc.block_phases(ph.edge_scene_v(W, H, 6.5, 2000.0, 3, 0.05, 40, 8, 1, shared), 5, W, H)
        assert o["n_true_band"] <= o["n_true_tested"] <= o["n_true_moving"] <= o["n_true_window"]
        r = pc.rayleigh(o["blocks"]["pred"])
        assert int(o["hist"]["pred"].sum()) == int(np.sum([b[0] for b in o["blocks"]["pred"]]))
        z[shared] = r["mean_Z"]
        assert 0.7 < pc.rayleigh(o["blocks"]["null"])["mean_Z"] < 1.3
    assert 0.7 < z[False] < 1.3 and z[True] > 10.0


def test_pool_and_figures(tmp_path):
    outs = {f"r{s}": [pc.block_phases(ph.edge_scene_v(W, H, 6.5, 2000.0, 3, 0.05, 40, 8, s, False), 5, W, H)]
            for s in (1, 2)}
    p = pc.pool(outs)
    lo, hi = p["rayleigh"]["pred"]["mean_Z_ci95"]
    assert p["n_groups"] == 2 and lo <= p["rayleigh"]["pred"]["mean_Z"] <= hi
    assert 0 < p["coverage"]["share_band"] <= p["coverage"]["share_tested"] <= 1
    rep = {"control": [pc.control_cell(t, c, 160, 40) for t in (1000.0, 4000.0) for c in pc.CONDITIONS],
           "model_phase": {"shared": {"hist": [50] + [0] * 19}, "independent": {"hist": [5] * 20}},
           "strata": {k: p for k in ("day", "night", "all")}}
    (tmp_path / "pc").mkdir()
    (tmp_path / "pc" / "report.json").write_text(json.dumps(rep))
    r = ROOT / "results"
    subprocess.run([sys.executable, str(ROOT / "scripts" / "fig_027.py"), "--pc", str(tmp_path / "pc"),
                    "--hd", str(r / "hd"), "--hc", str(r / "hc"), "--demo", str(r / "td2"), "--paper",
                    str(r / "paper"), "--out", str(tmp_path)], check=True)
    for name in ("fig_moved2", "fig_phase3", "fig_tolerance_compact2", "fig_hevc2"):
        for ext in ("pdf", "png", "json"):
            assert (tmp_path / f"{name}.{ext}").stat().st_size > 0
    fm = json.loads((tmp_path / "fig_moved2.json").read_text())
    assert all(v == 1.0 for v in fm["a"]["shared"]["F"])
    fp = json.loads((tmp_path / "fig_phase3.json").read_text())
    assert fp["b"]["day"]["mean_Z"] == p["rayleigh"]["pred"]["mean_Z"]
    assert abs(np.mean(fp["b"]["day"]["density"]) - 1.0) < 1e-9
