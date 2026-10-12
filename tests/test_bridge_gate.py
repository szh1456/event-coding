"""Gate for directive 014: moved key events against regenerated events on the ramp model.

The configuration ``ec.bridge.SMOKE`` and its tolerances are fixed by the director. The figure
comes from ``ec.bridge.REFERENCE``, which this file does not run.
"""
import numpy as np

from ec import bridge


def test_voxel_fidelity_counts_pairs_inside_a_voxel():
    p = np.zeros(3, dtype=np.int64)
    m, nr, nt = bridge._voxel_fidelity(p, np.array([0, 0, 5]), np.array([0.1, 0.2, 3.0]),
                                       p, np.array([0, 1, 5]), np.array([0.15, 0.1, 4.1]), 1, 1.0, 1)
    assert m.tolist() == [1.0] and nr == 3 and nt == 3          # (0, bin 0) pairs once; (5, bins 3 and 4) does not


def test_smoke_runs_and_every_check_holds():
    out = bridge.run(bridge.SMOKE)
    assert set(out["cases"]) == {"translation", "subpixel", "scale"}
    assert "exact" not in out["cases"]["subpixel"]["timing"]
    assert all(out["checks"].values()), out["checks"]
    sp = out["cases"]["subpixel"]
    assert sp["timing"]["round"]["D_over_DA"] > sp["timing"]["regen"]["D_over_DA"] + 1.0
