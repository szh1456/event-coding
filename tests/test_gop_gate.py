"""Gate for directive 003: key windows and regenerated windows on synthetic rigid translation.

The scenarios, seeds and tolerances are fixed here by the director. An executor implementation that
replaces or accelerates ``ec.gop`` must pass this file unchanged.
"""
import numpy as np

from ec import annotations, gop, motion, regen, synth

T1, T2 = 100_000, 33_333


def _groups(v, v_factor=1.0, n_targets=4, sizes=False, **kw):
    """Groups keyed at the evaluation instants. The cmax velocity is scaled by ``v_factor`` before use."""
    sc = synth.rigid_translation(v=v, duration_s=1.2, n_points=120, seed=0, **kw)
    tr = annotations.tracks(sc.boxes)[0]
    out = []
    for te in motion.evaluation_instants(tr):
        m0 = motion.evaluate_instant(sc.t, sc.x, sc.y, sc.p, tr, int(te), T1, 0, T2, sc.width, sc.height,
                                     models=("cmax",))
        if "skipped" in m0:
            continue
        vc = (m0["cmax_vx"] * v_factor, m0["cmax_vy"] * v_factor)
        rows = [gop.evaluate_target(sc.t, sc.x, sc.y, sc.p, tr, int(te), m, T2, sc.width, sc.height, vc,
                                    sizes=sizes) for m in range(1, n_targets + 1)]
        if not any("skipped" in r for r in rows):
            out.append(rows)
    assert out
    return out


def _gamma(rows, model, K):
    r = rows[:K - 1]
    return gop.group_summary(rows[0]["n_source"], [a[f"{model}_n_pred"] for a in r], [a["n_future"] for a in r],
                             [a[f"{model}_f1_s2_k3"] for a in r])


def test_leads_are_those_of_directive_002():
    assert [gop.lead_us(m) for m in (1, 2, 4, 10)] == [0, 33_333, 100_000, 300_000]
    assert gop.N_TARGETS == 10 and gop.OBJECTIVE == (2, 3)


def test_group_summary_by_hand():
    s = gop.group_summary(100, [100], [100], [0.5])
    assert abs(s["fidelity"] - 0.75) < 1e-12 and abs(s["share"] - 0.5) < 1e-12
    assert abs(s["q_eq"] - 0.6) < 1e-12 and abs(s["gamma"] - 1.2) < 1e-12
    # nothing regenerated: the group is a thinned stream, and gamma is 1
    s = gop.group_summary(100, [0, 0, 0], [100, 80, 120], [0.0, 0.0, 0.0])
    assert abs(s["share"] - 0.25) < 1e-12 and abs(s["fidelity"] - 0.4) < 1e-12 and abs(s["gamma"] - 1.0) < 1e-12
    # false events lower the fidelity below that of thinning
    assert gop.group_summary(100, [100], [100], [0.0])["gamma"] < 1.0


def test_exact_velocity_needs_no_correction():
    for rows in _groups((200.0, 0.0)):
        for r in rows:
            assert (r["aligned_dx"], r["aligned_dy"]) == (r["start_dx"], r["start_dy"])
            for s in regen.BLOCKS_PX:
                for k in regen.TIME_BINS:
                    assert r[f"aligned_f1_s{s}_k{k}"] == r[f"start_f1_s{s}_k{k}"] == r[f"cmax_f1_s{s}_k{k}"]


def test_a_wrong_velocity_is_corrected_by_the_sent_displacement():
    for rows in _groups((200.0, 0.0), v_factor=1.2):
        r = rows[3]                                         # m = 4, lead 100 ms, true displacement 26.7 px
        assert r["start_dx"] == 32 and abs(r["aligned_dx"] - 27) <= 1 and r["aligned_dy"] == 0
        assert r["aligned_f1_s2_k3"] > 0.75 and r["cmax_f1_s2_k3"] < 0.2
    for rows in _groups((150.0, -80.0), v_factor=0.85, jitter_us=1000.0):
        r = rows[3]
        assert abs(r["aligned_dx"] - 20) <= 1 and abs(r["aligned_dy"] + 11) <= 1
        assert r["aligned_f1_s2_k3"] > 0.6 and r["cmax_f1_s2_k3"] < 0.25


def test_the_sent_displacement_is_never_worse_than_the_predicted_one():
    for kw in (dict(v=(200.0, 0.0), v_factor=1.1, noise_rate_hz=5.0), dict(v=(40.0, 0.0), v_factor=1.3),
               dict(v=(150.0, -80.0), v_factor=0.85, jitter_us=3000.0)):
        for rows in _groups(**kw):
            for r in rows:
                assert r["aligned_f1_s2_k3"] >= r["start_f1_s2_k3"]
                assert 0.0 <= r["aligned_f1_s1_k32"] <= r["aligned_f1_s2_k32"] <= r["aligned_f1_s4_k32"] <= 1.0
                assert r["aligned_f1_s2_k32"] <= r["aligned_f1_s2_k8"] <= r["aligned_f1_s2_k1"]


def test_regeneration_beats_thinning_and_repetition_does_not():
    for rows in _groups((200.0, 0.0), v_factor=1.2, n_targets=7):
        a4, a8, c4, s4 = _gamma(rows, "aligned", 4), _gamma(rows, "aligned", 8), _gamma(rows, "cmax", 4), \
            _gamma(rows, "static", 4)
        assert a4["gamma"] > 2.8 and a8["gamma"] > 5.0 and abs(a4["share"] - 0.25) < 0.02
        assert c4["gamma"] < 1.5 and s4["gamma"] < 1.0
    for rows in _groups((200.0, 0.0), noise_rate_hz=5.0):   # noise events cannot be regenerated
        assert 1.6 < _gamma(rows, "aligned", 4)["gamma"] < 2.8


def test_transport_sizes_and_thinning_are_reproducible():
    a = _groups((200.0, 0.0), jitter_us=1000.0, n_targets=2, sizes=True)[0]
    b = _groups((200.0, 0.0), jitter_us=1000.0, n_targets=2, sizes=True)[0]
    assert a == b
    r = a[0]
    assert r["key_bits"] > 0 and r["true_bits"] > 0 and "key_bits" not in a[1] and a[1]["true_bits"] > 0
    n = [r[f"thin_n_q{q}"] for q in gop.THIN_SHARES]
    assert n == sorted(n, reverse=True) and n[0] < r["n_future"]
    for q in gop.THIN_SHARES:
        assert abs(r[f"thin_n_q{q}"] / r["n_future"] - q) < 0.06
    # a sparser subset costs more bits per kept event
    per = [r[f"thin_bits_q{q}"] / r[f"thin_n_q{q}"] for q in gop.THIN_SHARES]
    assert per[0] < per[-1]
