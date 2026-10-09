"""Gate for directive 004: regeneration with a sender-fitted affine map, on a synthetic expanding object.

The scenarios, seeds and tolerances are fixed here by the director. An executor implementation that
replaces or accelerates ``ec.affine`` must pass this file unchanged.
"""
import numpy as np

from ec import affine, annotations, gop, motion, regen, synth_affine

T1, T2 = 100_000, 33_333


def _groups(v, expand_rate, n_targets=10, **kw):
    """Groups keyed at the evaluation instants: the rows of ``ec.gop`` with those of ``ec.affine`` merged in."""
    sc = synth_affine.expanding_translation(v=v, expand_rate=expand_rate, duration_s=1.2, n_points=120, seed=0, **kw)
    tr = annotations.tracks(sc.boxes)[0]
    out = []
    for te in motion.evaluation_instants(tr):
        m0 = motion.evaluate_instant(sc.t, sc.x, sc.y, sc.p, tr, int(te), T1, 0, T2, sc.width, sc.height,
                                     models=("cmax",))
        if "skipped" in m0:
            continue
        rows = []
        for m in range(1, n_targets + 1):
            g = gop.evaluate_target(sc.t, sc.x, sc.y, sc.p, tr, int(te), m, T2, sc.width, sc.height,
                                    (m0["cmax_vx"], m0["cmax_vy"]), sizes=False)
            if "skipped" in g:
                rows = None
                break
            q_prev = tuple(rows[-1][f"affine_{n}"] for n in affine.PARAMS) if rows else None
            a = affine.evaluate_affine(sc.t, sc.x, sc.y, sc.p, tr, int(te), m, T2, sc.width, sc.height,
                                       (g["aligned_dx"], g["aligned_dy"]), q_prev)
            g.update(a)
            rows.append(g)
        if rows:
            out.append(rows)
    assert out
    return out


def _gamma(rows, model, K):
    r = rows[:K - 1]
    return gop.group_summary(rows[0]["n_source"], [a[f"{model}_n_pred"] for a in r], [a["n_future"] for a in r],
                             [a[f"{model}_f1_s2_k3"] for a in r])["gamma"]


def test_the_map_with_zero_shape_parameters_is_the_translation():
    sx, sy = np.array([10, 20, 30, 41]), np.array([5, 9, 6, 8])
    frame = affine.frame_of(sx, sy)
    assert frame == (25.5, 7.0, 15.5, 2.0)
    ix, iy = affine.move_affine(sx, sy, frame, (3, -2, 0, 0, 0, 0))
    assert list(ix) == [13, 23, 33, 44] and list(iy) == [3, 7, 4, 6]
    # ia = 2 moves the two edges of the rectangle by 2 px, outwards
    ix, _ = affine.move_affine(sx, sy, frame, (0, 0, 2, 0, 0, 0))
    assert ix[0] == 8 and ix[-1] == 43
    assert affine.MOTION_BITS == 72 and affine.PARAMS == ("dx", "dy", "ia", "ib", "ic", "id")


def test_a_translating_object_gets_no_shape_parameters():
    for rows in _groups((200.0, 0.0), 0.0):
        for r in rows:
            assert [r[f"affine_{n}"] for n in affine.PARAMS] == [r["aligned_dx"], r["aligned_dy"], 0, 0, 0, 0]
            assert r["affine_f1_s2_k3"] == r["aligned_f1_s2_k3"]


def test_the_translation_rows_are_those_of_directive_003():
    for rows in _groups((200.0, 0.0), 0.5):
        for r in rows:
            assert r["translation_n_pred"] == r["aligned_n_pred"]
            for s in regen.BLOCKS_PX:
                for k in regen.TIME_BINS:
                    assert r[f"translation_f1_s{s}_k{k}"] == r[f"aligned_f1_s{s}_k{k}"]


def test_an_approaching_object_is_followed_by_the_affine_map_and_not_by_the_translation():
    for rows in _groups((200.0, 0.0), 0.5):
        late = rows[6:]                                     # m = 7 .. 10, leads 200 to 300 ms
        assert min(r["affine_f1_s2_k3"] for r in late) > 0.55
        assert max(r["aligned_f1_s2_k3"] for r in late) < 0.3
        r = rows[9]                                         # the rectangle grows by 12 to 15% in 333 ms
        assert 4 <= r["affine_ia"] <= 6 and 2 <= r["affine_id"] <= 4
        assert abs(r["affine_ib"]) <= 1 and abs(r["affine_ic"]) <= 1
        assert _gamma(rows, "affine", 11) > 5.0 and _gamma(rows, "aligned", 11) < 3.5
        assert _gamma(rows, "affine", 4) > _gamma(rows, "aligned", 4) + 0.2


def test_a_receding_object_with_jitter():
    for rows in _groups((200.0, 0.0), -0.4, jitter_us=1000.0):
        assert rows[8]["affine_f1_s2_k3"] > 0.6 and rows[8]["aligned_f1_s2_k3"] < 0.4
        assert rows[8]["affine_ia"] < -2 and rows[8]["affine_id"] < -1


def test_the_affine_map_is_never_worse_than_the_translation():
    for kw in (dict(v=(200.0, 0.0), expand_rate=0.5), dict(v=(60.0, 20.0), expand_rate=0.8),
               dict(v=(200.0, 0.0), expand_rate=-0.4, jitter_us=3000.0)):
        for rows in _groups(**kw):
            for r in rows:
                assert r["affine_f1_s2_k3"] >= r["translation_f1_s2_k3"]
                assert 0.0 <= r["affine_f1_s1_k32"] <= r["affine_f1_s2_k32"] <= r["affine_f1_s4_k32"] <= 1.0
                assert r["affine_f1_s2_k32"] <= r["affine_f1_s2_k8"] <= r["affine_f1_s2_k1"]


def test_skips_and_reproducibility():
    sc = synth_affine.expanding_translation(v=(200.0, 0.0), expand_rate=0.5, duration_s=1.2, n_points=120, seed=0)
    tr = annotations.tracks(sc.boxes)[0]
    a = affine.evaluate_affine(sc.t, sc.x, sc.y, sc.p, tr, 600_000, 4, T2, sc.width, sc.height, (27, 0))
    b = affine.evaluate_affine(sc.t, sc.x, sc.y, sc.p, tr, 600_000, 4, T2, sc.width, sc.height, (27, 0))
    assert a == b and "skipped" not in a
    r = affine.evaluate_affine(sc.t, sc.x, sc.y, sc.p, tr, 50_000, 1, T2, sc.width, sc.height, (7, 0))
    assert r["skipped"] == "outside_track_life"
