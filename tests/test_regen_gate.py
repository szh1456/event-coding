"""Gate for directive 002: regeneration fidelity on synthetic rigid translation with known truth.

The scenarios, seeds and tolerances are fixed here by the director. An executor implementation that
replaces or accelerates ``ec.regen`` must pass this file unchanged.
"""
import numpy as np

from ec import annotations, motion, regen, synth

T1, T2 = 100_000, 33_333


def _run(v, jitter_us=300.0, noise=0.0, label_noise=0.0, D=0, n_points=120, seed=0):
    sc = synth.rigid_translation(v=v, jitter_us=jitter_us, noise_rate_hz=noise, label_noise_px=label_noise,
                                 seed=seed, duration_s=1.2, n_points=n_points)
    tr = annotations.tracks(sc.boxes)[0]
    rows = []
    for te in motion.evaluation_instants(tr):
        m = motion.evaluate_instant(sc.t, sc.x, sc.y, sc.p, tr, int(te), T1, D, T2, sc.width, sc.height,
                                    models=("cmax",))
        if "skipped" in m:
            continue
        r = regen.evaluate_regen(sc.t, sc.x, sc.y, sc.p, tr, int(te), D, T2, sc.width, sc.height,
                                 (m["cmax_vx"], m["cmax_vy"]))
        if "skipped" not in r:
            rows.append(r)
    assert rows
    return {k: float(np.median([r[k] for r in rows])) for k in rows[0]}


def test_voxel_f1_on_small_sets():
    x = np.array([10, 10, 11, 40]); y = np.array([5, 5, 5, 9]); p = np.array([1, 1, 0, 1])
    t = np.array([100, 200, 300, 30_000])
    same = regen.voxel_f1(x, y, t, p, x, y, t, p, 0, T2, 1, 32)
    assert same["f1"] == 1.0 and same["precision"] == 1.0 and same["recall"] == 1.0
    assert regen.voxel_f1(x[:2], y[:2], t[:2], p[:2], x[:2], y[:2], t[:2], 1 - p[:2], 0, T2, 4, 1)["f1"] == 0.0
    # two of three predicted events share a voxel with the four true ones: min counts sum to 2
    r = regen.voxel_f1(x[:3] + 1, y[:3], t[:3], p[:3], x, y, t, p, 0, T2, 2, 1)
    assert r["precision"] == 2 / 3 and r["recall"] == 2 / 4 and abs(r["f1"] - 4 / 7) < 1e-12
    # 1 ms bins separate events that the whole-window bin joins
    a = regen.voxel_f1(x[:1], y[:1], t[:1], p[:1], x[:1], y[:1], t[:1] + 5_000, p[:1], 0, T2, 1, 1)
    b = regen.voxel_f1(x[:1], y[:1], t[:1], p[:1], x[:1], y[:1], t[:1] + 5_000, p[:1], 0, T2, 1, 32)
    assert a["f1"] == 1.0 and b["f1"] == 0.0


def test_moved_events_reproduce_the_window_and_repeated_ones_do_not():
    m = _run((200.0, 0.0))
    assert m["cmax_f1_s2_k3"] > 0.75 and m["cmax_f1_s1_k1"] > 0.9
    assert m["static_f1_s2_k3"] < 0.2 and m["uniform_f1_s2_k3"] < 0.2
    assert abs(m["cmax_f1_s2_k3"] - m["label_f1_s2_k3"]) < 0.05
    assert 0.9 < m["cmax_n_pred"] / m["n_future"] < 1.1


def test_fidelity_rises_with_the_time_bin():
    m = _run((200.0, 0.0))
    f = [m[f"cmax_f1_s2_k{k}"] for k in (32, 8, 3, 1)]
    assert f[0] < 0.2 and f[0] + 0.3 < f[1] < f[2] - 0.05 and f[2] < f[3] - 0.03
    slow = _run((40.0, 0.0))                           # one pixel takes 25 ms: only the whole window agrees
    assert slow["cmax_f1_s2_k1"] > 0.6 and slow["cmax_f1_s2_k3"] < 0.45


def test_fidelity_falls_with_timing_jitter():
    f = [_run((200.0, 0.0), jitter_us=j)["cmax_f1_s2_k3"] for j in (0.0, 3000.0, 10000.0)]
    assert f[0] > f[1] + 0.08 and f[1] > f[2] + 0.15


def test_noise_lowers_fidelity_and_raises_the_chance_level():
    clean, lo, hi = _run((200.0, 0.0)), _run((200.0, 0.0), noise=5.0), _run((200.0, 0.0), noise=20.0)
    assert clean["cmax_f1_s2_k3"] > lo["cmax_f1_s2_k3"] + 0.2 > hi["cmax_f1_s2_k3"] + 0.25
    assert clean["uniform_f1_s2_k3"] + 0.04 < lo["uniform_f1_s2_k3"] < hi["uniform_f1_s2_k3"] - 0.08


def test_label_move_fails_under_label_noise_and_cmax_does_not():
    m = _run((200.0, 0.0), label_noise=2.0)
    assert m["cmax_f1_s2_k3"] > m["label_f1_s2_k3"] + 0.3


def test_regeneration_holds_across_a_lead_and_repetition_does_not():
    m = _run((200.0, 0.0), D=300_000)
    assert m["cmax_f1_s2_k1"] > 0.8 and m["static_f1_s2_k1"] < 0.05


def test_uniform_reference_is_reproducible_and_skips_are_reported():
    sc = synth.rigid_translation(v=(200.0, 0.0), duration_s=1.2, n_points=120, seed=0)
    tr = annotations.tracks(sc.boxes)[0]
    a = regen.evaluate_regen(sc.t, sc.x, sc.y, sc.p, tr, 600_000, 0, T2, sc.width, sc.height, (200.0, 0.0))
    b = regen.evaluate_regen(sc.t, sc.x, sc.y, sc.p, tr, 600_000, 0, T2, sc.width, sc.height, (200.0, 0.0))
    assert a == b and "skipped" not in a
    r = regen.evaluate_regen(sc.t, sc.x, sc.y, sc.p, tr, 50_000, 0, T2, sc.width, sc.height, (200.0, 0.0))
    assert r["skipped"] == "outside_track_life"
    few = synth.rigid_translation(v=(200.0, 0.0), n_points=3, duration_s=1.2, seed=1)
    tf = annotations.tracks(few.boxes)[0]
    r = regen.evaluate_regen(few.t, few.x, few.y, few.p, tf, 600_000, 0, T2, few.width, few.height, (200.0, 0.0))
    assert r["skipped"] == "source_too_small"
