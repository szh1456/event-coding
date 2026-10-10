"""Gate for directive 006: the three rate regimes of one pixel, on the coarse configuration.

The configuration ``ec.regimes.SMOKE`` and its tolerances are fixed by the director. The gate
checks that the computation runs and agrees with Theorem 2 of the manuscript to the coarse
tolerances. The figure comes from ``ec.regimes.REFERENCE``, which this file does not run.
"""
import numpy as np
import pytest

from ec import regimes


def test_constants_and_the_bound_on_the_gap():
    c = regimes.constants(3, 1.0, 0.05)
    assert abs(c["D_A"] - (0.05 ** 2 + 1.0 / 12)) < 1e-15
    assert abs(c["s2"] - (3.0 / 12 + 0.05 ** 2)) < 1e-15
    assert 0.0 <= c["Gamma"] <= c["Gamma_max"]
    assert abs(c["Gamma_max"] / regimes.LN2 - 0.2546) < 1e-4
    # the entropy of uniform + Gaussian lies between the entropy-power bound and the Gaussian bound
    for a, s in ((1.0, 1e-3), (1.0, 0.1), (1.0, 1.0), (3.7, 0.2)):
        e = regimes.eta(a, s)
        assert 0.5 * np.log(a * a + 2 * np.pi * np.e * s * s) <= e + 1e-9
        assert e <= 0.5 * np.log(2 * np.pi * np.e * (a * a / 12 + s * s)) + 1e-9


def test_theory_is_continuous_at_the_jitter_variance_up_to_the_gap_and_zero_from_the_threshold():
    c = regimes.constants(3, 1.0, 0.05)
    s2 = c["sigma"] ** 2
    lo, up = regimes.theory(s2, c)
    assert lo == up
    lo2, up2 = regimes.theory(s2 * (1 + 1e-9), c)
    assert abs(lo2 - lo) < 1e-6 and abs(up2 - lo - c["Gamma"]) < 1e-6
    assert regimes.theory(c["D_A"], c) == (0.0, 0.0)
    lo3, up3 = regimes.theory(0.999 * c["D_A"], c)
    assert 0.0 < lo3 <= up3 < 2e-3
    # a row whose slope puts it in the exact regime is scored with the exact formula at the boundary
    assert regimes.theory(s2 * (1 + 1e-9), c, low=True) == pytest.approx((lo, lo), abs=1e-6)
    assert regimes.theory(s2, c, low=False)[1] == pytest.approx(lo + c["Gamma"], abs=1e-9)


def test_blahut_arimoto_reproduces_a_gaussian_source():
    x = np.linspace(-6.0, 6.0, 241)
    p = np.exp(-0.5 * x * x)
    p /= p.sum()
    D, lo, up, _ = regimes.blahut_arimoto(x, p, beta=1.0 / (2 * 0.25), iters=3000)
    assert abs(D - 0.25) < 2e-3 and abs(up - 0.5 * np.log(1.0 / D)) < 2e-3 and lo <= up + 1e-12


def test_the_helmert_matrix_is_orthonormal_with_a_constant_first_row():
    for n in (1, 2, 3, 5):
        H = regimes.helmert(n)
        assert np.allclose(H @ H.T, np.eye(n)) and np.allclose(H[0], 1 / np.sqrt(n))


def test_the_coarse_configuration_passes_every_check():
    out = regimes.run(regimes.SMOKE)
    assert out["pass"], out["checks"]
    assert (out["R1"]["n_low"], out["R1"]["n_mid"], out["R1"]["n_top"]) == (2, 2, 1)
    assert [r["class"] for r in out["rd"]] == ["low", "low", "mid", "mid", "top"]
    assert len(out["checks"]) == 9
    # the regenerating decoder sits at the threshold, and the quantizer is above the lower bound
    assert abs(out["R3"]["regen_D_over_D_A"] - 1.0) < 0.02
    assert out["R3"]["coder_min_excess_over_lower_bound"] > 0.0


def test_reference_configuration_is_the_one_of_the_figure():
    r = regimes.REFERENCE
    assert (r["n"], r["tau"], r["sigma"], r["grid_per_sigma"], r["n_pixels"]) == (3, 1.0, 0.05, 25, 2_000_000)
    assert len(r["rms_x_over_sigma"]) == 19
