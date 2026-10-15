"""Gate for directive 022: the phase test, the regular spacing and the motion fit, on constructed trains and on
the model at whole and fractional speeds. The tolerances are fixed by the director."""
import numpy as np

from ec import blockcodec as bc
from ec import hevcdiag as hd
from ec import phase as ph
from ec import threshold as th

T0 = bc.T0_US
W, H = 200, 160


def _ev(rows):
    t = np.array([r[0] for r in rows], dtype=np.int64)
    x, y, p = (np.array([r[i] for r in rows], dtype=np.int64) for i in (1, 2, 3))
    o = np.argsort(t, kind="stable")
    return tuple(a[o] for a in (t, x, y, p))


def test_regular_spacing_by_construction():
    rows = [(1000 * k, 0, 0, 1) for k in range(4)]                          # regular: 1000
    rows += [(t, 1, 0, 1) for t in (0, 1000, 21000, 22000)]                  # two passages of two: none
    rows += [(50000 * k, 2, 0, 1) for k in range(3)]                         # one event per passage: none
    rows += [(t, 3, 0, 1) for t in (0, 1000, 2100, 32100)]                   # 1000 and 1100 regular
    rows += [(t, 4, 0, 1) for t in (0, 1000)]                                # two events: none
    rows += [(t, 5, 0, 1) for t in (0, 15000, 30000, 45000)]                 # regular, two intervals within T0
    rows += [(t, 7, 0, 1) for t in (0, 1000, 2300)]                          # ratio 1.3 > RHO: none
    keys, tau = ph.regular_spacing(_ev(rows), W)
    got = dict(zip(((keys // 2) % W).tolist(), tau.tolist()))
    assert got == {0: 1000.0, 3: 1050.0, 5: 15000.0}
    keys, tau = ph.regular_spacing(_ev([(20000 * k, 6, 0, 0) for k in range(4)]), W)
    assert len(keys) == 0                                                     # 40 ms > T0


def test_median_spacing_equals_directive_020():
    rng = np.random.default_rng(3)
    n = 4000
    ev = _ev(list(zip(rng.integers(0, 4 * T0, n), rng.integers(0, 30, n), rng.integers(0, 20, n), rng.integers(0, 2, n))))
    k1, t1 = ph.median_spacing(ev, W)
    k2, t2 = th.pixel_spacing(ev, W)
    ok = np.isfinite(t2)
    assert np.array_equal(k1, k2[ok]) and np.allclose(t1, t2[ok])


def test_pixel_phases_by_construction():
    true = _ev([(1000 * k, 5, 5, 1) for k in range(4)]
               + [(t, 6, 5, 1) for t in (0, 1000, 5000)]                      # irregular
               + [(1000 * k + 300, 7, 5, 0) for k in range(3)])
    pred = _ev([(250, 5, 5, 1), (1250, 5, 5, 1), (3250, 5, 5, 1), (500, 6, 5, 1), (900, 7, 5, 0), (400, 8, 5, 1)])
    u, tau = ph.pixel_phases(true, pred, W)
    assert np.allclose(np.sort(u), [0.25, 0.6]) and np.allclose(tau, 1000.0)


def test_pixel_phases_are_uniform_under_independent_phases():
    rng = np.random.default_rng(5)
    for e in (0.0, 0.5, 1.5, 2.5):                                            # residual offset in units of tau
        rows_t, rows_p = [], []
        for i in range(3000):
            tau, nt, nq = 1000.0, rng.integers(3, 6), rng.integers(1, 6)
            a, b = rng.random() * tau, rng.random() * tau
            rows_t += [(int(a + k * tau + rng.normal(0, 50)) + 10000, i % 200, i // 200, 1) for k in range(nt)]
            rows_p += [(int(b + (k + e) * tau) + 10000, i % 200, i // 200, 1) for k in range(nq)]
        u, _ = ph.pixel_phases(_ev(rows_t), _ev(rows_p), W)
        assert len(u) > 2500
        assert abs(np.mean(np.cos(2 * np.pi * u))) < 0.05 and abs(np.mean(np.sin(2 * np.pi * u))) < 0.05


def test_onset_delay_recovers_a_shift_of_trains():
    rng = np.random.default_rng(0)
    rows = []
    for i in range(300):
        a = 5000 + rng.random() * 20000
        rows += [(int(a + 1000 * k), i % 50, i // 50, 1) for k in range(3)]
    true = _ev(rows)
    moved = (true[0] - 300, true[1], true[2], true[3])
    assert ph.onset_delay(moved, true, 0, W) == 300
    assert ph.onset_delay(tuple(a[:0] for a in true), true, 0, W) == 0


def test_choose_shift_prefers_the_smallest_near_tie():
    r = 3
    s = np.zeros((2 * r + 1, 2 * r + 1), dtype=np.int64)
    s[r, r + 3] = 100                                                          # dx = 3
    s[r, r + 2] = 81                                                           # dx = 2: within 2 sqrt(100) = 20
    s[r - 1, r - 1] = 79                                                       # dx = -1, dy = -1: outside, far
    d, pairs, runner = ph.choose_shift(s, r)
    assert d == (2, 0) and pairs == 100 and runner == 0.79
    s[r, r + 2] = 79
    assert ph.choose_shift(s, r)[0] == (3, 0)
    assert ph.choose_shift(np.zeros_like(s), r) == ((0, 0), 0, 0.0)


def test_shift_scores_match_directive_020():
    ev = hd.edge_scene(W, H, 6, 2000.0, 3, 0.05, 40, 8, 1)
    a = th._window(ev, 4 * T0, 5 * T0)
    b = th._in_block(th._window(ev, 5 * T0, 6 * T0), 60, 40)
    s = ph.shift_scores(a, b, 60, 40, th.R)
    d, m = th.best_shift(a, b, 60, 40)
    assert s.max() == m and s[d[1] + th.R, d[0] + th.R] == m


def test_independent_phases_read_uniform_and_shared_phases_lock():
    for v in (1.5, 2.5, 3.5, 6.0, 6.5, 13.3):
        for shared in (False, True):
            ev = ph.edge_scene_v(W, H, v, 2000.0, 3, 0.05, 40, 8, 1, shared)
            o = ph.evaluate_group(ev, 5, W, H)
            c, n = o["phase_stat"]["pred"][:, 0].sum(axis=(0, 1, 2)), o["phase_stat"]["null"][:, 0].sum(axis=(0, 1, 2))
            assert c[0] > 500 and n[0] > 50, (v, c[0], n[0])
            cos, sin = c[1] / c[0], c[2] / c[0]
            if shared:
                assert cos > 0.85, (v, cos)
            else:
                se = np.sqrt(0.5 / c[0])                                       # standard error of a mean cos or sin
                assert abs(cos) < 4 * se and abs(sin) < 4 * se, (v, cos, sin)
            assert abs(n[1] / n[0]) < 0.08 and abs(n[2] / n[0]) < 0.08


def test_regular_tau_follows_eq_binfidmoved_on_the_model():
    tau = 4000.0
    for v, tol in ((6.0, 0.02), (2.5, 0.2), (6.5, 0.15), (13.3, 0.2)):        # tol: absolute, then relative
        ev = ph.edge_scene_v(W, H, v, tau, 3, 0.05, 40, 8, 1, False)
        o = ph.evaluate_group(ev, 5, W, H)
        s = o["sums"]["reg"][0].sum(axis=0)
        for g, cell in enumerate(ph.GRIDS):
            r = (T0 / cell[1]) / tau
            pred = float(th.predicted(r, 3))
            if np.isfinite(pred) and r >= (1 / 64 if v == 6.0 else 1 / 16):
                v_ = s[g].sum(axis=0)
                f = 2 * v_[2] / (v_[0] + v_[1])
                err = abs(f - pred) if v == 6.0 else abs(f - pred) / pred
                assert err < tol, (v, cell, f, pred)
        for kind in ph.TAU_KINDS:
            a = o["sums"][kind]
            assert np.all(a[..., 2] <= np.minimum(a[..., 0], a[..., 1]))
            assert np.all(a[..., 3] <= np.minimum(a[..., 0], a[..., 1]))
            assert int(a[:, :, 0, :, 0].sum()) == int(np.sum(o["blocks"]["N"]))
        assert np.array_equal(o["phase_stat"]["pred"][..., 0], o["phase_stat"]["null"][..., 0])
        real, sur = o["regular_share"]
        assert sur < 0.1 * real


def test_short_passages_bias_the_median_spacing_and_not_the_regular_one():
    ev = hd.edge_scene(W, H, 6, 1000.0, 2, 0.05, 10, 8, 1)                     # two events per passage, dense edges
    o = ph.evaluate_group(ev, 5, W, H)
    g = ph.GRIDS.index((1, 64))
    med, reg = o["sums"]["med"][0].sum(axis=0)[g], o["sums"]["reg"][0].sum(axis=0)[g]
    small = th.R_EDGES[1:] <= 1 / 16
    v = med[:-1][small].sum(axis=0)
    assert v[0] > 200
    assert 2 * v[2] / (v[0] + v[1]) > 5 * float(th.predicted(1 / 16, np.inf))
    assert reg[:-1].sum(axis=0)[0] < 0.05 * reg.sum(axis=0)[0]


def test_the_wider_radius_finds_fast_motion():
    ev = hd.edge_scene(W, H, 24, 2000.0, 3, 0.05, 60, 8, 1)
    o = ph.evaluate_group(ev, 5, W, H)
    sh = np.array(o["blocks"]["shift"])
    assert len(sh) > 10 and np.mean(np.abs(sh[:, 0] - 24) <= 1) > 0.7 and np.mean(sh[:, 1] == 0) > 0.9


def test_blocks_without_a_source_are_skipped():
    ev = ph.edge_scene_v(W, H, 13.3, 2000.0, 3, 0.05, 40, 8, 1, False)
    o = ph.evaluate_group(ev, 5, W, H)
    assert o["skipped_no_source"] > 0
    assert all(p >= th.N_MIN / 2 for p in o["blocks"]["pairs"])
    assert not any(b % (-(-W // th.B)) == 0 and s == [0, 0] for b, s in zip(o["blocks"]["ids"], o["blocks"]["shift"]))


def test_static_flicker_goes_to_the_zero_slice():
    rng = np.random.default_rng(2)
    rows = []
    for x in range(40, 80):
        for y in range(40, 60):
            a = rng.random() * 10000.0                                         # independent phase per pixel
            rows += [(int(a + 10000.0 * k), x, y, 1) for k in range(int(8 * T0 / 10000.0))]
    ev = _ev(rows)
    o = ph.evaluate_group(ev, 5, W, H)
    pz = o["phase_stat"]["pred"][:, 1].sum(axis=(0, 1, 2))
    pm = o["phase_stat"]["pred"][:, 0].sum(axis=(0, 1, 2))
    assert len(o["blocks"]["ids"]) > 0 and all(s == [0, 0] for s in o["blocks"]["shift"])
    assert pz[0] > 100 and pm[0] == 0
    assert o["phase_stat"]["pred"][:, 1, 1].sum(axis=(0, 1))[0] == pz[0]       # flicker class
