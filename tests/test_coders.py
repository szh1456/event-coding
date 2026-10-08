import math

import numpy as np
import pytest

pytest.importorskip("numba")
from ec import arith, coders as C, synth


def _scene(seed=0):
    return synth.rigid_translation(width=96, height=64, n_points=60, box_wh=(30.0, 20.0), c0=(20.0, 32.0),
                                   v=(150.0, 0.0), duration_s=0.4, jitter_us=200.0, noise_rate_hz=3.0, seed=seed)


def test_uniform_stream_costs_log2_of_the_pixel_count_at_the_start():
    sc = _scene()
    ab, pb, cls = C.context_code(sc.t, sc.x.astype(np.int64), sc.y.astype(np.int64), sc.p, 96, 64, 4000, True)
    assert abs(float(ab[0]) - math.log2(96 * 64)) < 1e-4       # no history: uniform over pixels
    assert np.all(ab > 0) and np.all(pb > 0) and np.all(np.isfinite(ab))


def test_context_coder_beats_the_rate_map_on_a_moving_object():
    sc = _scene(1)
    x, y = sc.x.astype(np.int64), sc.y.astype(np.int64)
    ab, _, _ = C.context_code(sc.t, x, y, sc.p, 96, 64, 4000, True)
    rm = C.ratemap_bits(x, y, 96, 64, 0.05)
    assert ab.mean() < rm.mean() - 1.0


def test_arithmetic_coder_round_trip_and_code_length_agreement():
    sc = _scene(2)
    r = arith.check(sc.t, sc.x, sc.y, sc.p, 96, 64)
    assert r["round_trip_exact"]
    assert abs(r["excess_fraction"]) < 0.002
    assert r["fast_vs_reference_rel_diff"] < 1e-6


def test_tie_order_saving_counts_permutations_of_distinct_events():
    t = np.array([5, 5, 5, 9, 9, 12], dtype=np.int64)
    x = np.array([1, 2, 3, 1, 1, 0]); y = np.zeros(6, dtype=np.int64); p = np.zeros(6, dtype=np.int64)
    bits, dup = C.order_free_saving_bits(t, x, y, p, 16)
    assert abs(bits - math.log2(6)) < 1e-9 and dup == 1    # 3! for the first group; the pair at t=9 is identical


def test_poisson_reference_matches_the_brief():
    assert abs(C.poisson_bits(0.1, 1e-6) - 24.70) < 0.01
    assert abs(C.poisson_bits(1.0, 1e-3) - 11.41) < 0.01
