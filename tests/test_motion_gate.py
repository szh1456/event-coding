"""Gate for directive 001: the reference estimator on synthetic rigid translation with known truth.

The scenarios, seeds and tolerances are fixed here by the director. An executor implementation that
replaces or accelerates ``ec.motion`` must pass this file unchanged.
"""
import math

import numpy as np
import pytest

from ec import annotations, motion, synth

T1, T2 = 100_000, 33_333


def _run(v, jitter_us=300.0, noise=0.0, label_noise=0.0, D=0, n_points=120, seed=0):
    sc = synth.rigid_translation(v=v, jitter_us=jitter_us, noise_rate_hz=noise, label_noise_px=label_noise,
                                 seed=seed, duration_s=1.2, n_points=n_points)
    tr = annotations.tracks(sc.boxes)[0]
    res = [motion.evaluate_instant(sc.t, sc.x, sc.y, sc.p, tr, int(te), T1, D, T2, sc.width, sc.height)
           for te in motion.evaluation_instants(tr)]
    res = [r for r in res if "skipped" not in r]       # a fast object leaves the sensor before its last instant
    assert res
    return {k: float(np.median([r[k] for r in res])) for k in res[0]}


def test_velocity_is_recovered():
    for v in ((200.0, 0.0), (150.0, -80.0), (600.0, 0.0), (40.0, 0.0)):
        m = _run(v)
        err = math.hypot(m["cmax_vx"] - v[0], m["cmax_vy"] - v[1]) / math.hypot(*v)
        assert err < 0.04, (v, m["cmax_vx"], m["cmax_vy"])
    m = _run((200.0, 0.0))
    assert math.hypot(m["cmax_vx"] - 200.0, m["cmax_vy"]) / 200.0 < 0.02


def test_motion_template_explains_the_events_and_a_static_one_does_not():
    m = _run((200.0, 0.0))
    assert m["cmax_gain_bits"] > 6.0 and m["static_gain_bits"] < 0.5
    assert m["cmax_eps"] < 0.05 and m["static_eps"] > 0.5
    assert m["cmax_redundancy"] > 10.0 and m["static_redundancy"] < 2.0
    assert abs(m["cmax_ref_bits"] - math.log2(2 * m["support_px"] * T2)) < 1e-6


def test_gain_falls_with_timing_jitter():
    g = [_run((200.0, 0.0), jitter_us=j)["cmax_gain_bits"] for j in (0.0, 1000.0, 3000.0)]
    assert g[0] > g[1] + 0.5 > g[2] + 1.0


def test_eps_tracks_the_share_of_noise_events():
    lo, hi = _run((200.0, 0.0), noise=5.0), _run((200.0, 0.0), noise=20.0)
    assert 0.25 < lo["cmax_eps"] < 0.6 and 0.5 < hi["cmax_eps"] < 0.8
    assert hi["cmax_eps"] > lo["cmax_eps"] + 0.1
    assert _run((200.0, 0.0))["cmax_eps"] < 0.05


def test_label_warp_fails_under_label_noise_and_cmax_does_not():
    m = _run((200.0, 0.0), label_noise=2.0)
    assert m["cmax_gain_bits"] > m["label_gain_bits"] + 2.0


def test_exact_labels_and_cmax_agree():
    m = _run((200.0, 0.0))
    assert abs(m["cmax_gain_bits"] - m["label_gain_bits"]) < 1.0


def test_short_or_empty_windows_are_reported_as_skips():
    sc = synth.rigid_translation(v=(200.0, 0.0), n_points=3, duration_s=1.2, seed=1)
    tr = annotations.tracks(sc.boxes)[0]
    r = motion.evaluate_instant(sc.t, sc.x, sc.y, sc.p, tr, 600_000, T1, 0, T2, sc.width, sc.height)
    assert r["skipped"] == "template_too_small"
    r = motion.evaluate_instant(sc.t, sc.x, sc.y, sc.p, tr, 50_000, T1, 0, T2, sc.width, sc.height)
    assert r["skipped"] == "outside_track_life"
