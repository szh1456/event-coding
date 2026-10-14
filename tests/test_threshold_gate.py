"""Gate for directive 020: per-pixel and per-block prediction of the counts against Eq. (binfidmoved).

The model scenes of ``ec.hevcdiag`` give a known spacing and motion; the textured translation of ``ec.synth``
gives a motion without the aperture problem. The tolerances are fixed by the director.
"""
import numpy as np

from ec import blockcodec as bc
from ec import hevcdiag as hd
from ec import synth
from ec import threshold as th

W, H = 320, 240
T0 = bc.T0_US


def pooled(sums, scope, cell, flicker=None):
    g = th.GRIDS.index(cell)
    a = sums[scope][:, :, g] if flicker is None else sums[scope][flicker:flicker + 1, :, g]
    return a.sum(axis=(0, 1))                      # (bins, 4)


def F(v):
    return 2 * v[..., 2] / np.maximum(v[..., 0] + v[..., 1], 1)


def test_model_follows_eq_binfidmoved_per_pixel_and_beats_the_null():
    for tau in (1000.0, 4000.0):
        ev = hd.edge_scene(W, H, 6, tau, 3, 0.05, 40, 8, 1)
        o = th.evaluate_group(ev, 5, W, H)
        assert len(o["blocks"]["ids"]) > 40
        assert np.mean(np.array(o["blocks"]["shift"])[:, 0] == 6) > 0.95
        assert np.median(o["blocks"]["tau_us"]) == np.median(o["blocks"]["tau_us"])
        for cell in [c for c in th.GRIDS if c[0] == 1]:
            v = pooled(o["sums"], "pixel", cell).sum(axis=0)
            r = (T0 / cell[1]) / tau
            pred = th.predicted(r, 3)
            if np.isfinite(pred):
                assert abs(F(v) - pred) < 0.02, (tau, cell, F(v), pred)
            m0 = 2 * v[3] / (v[0] + v[1])
            if r < 4:
                assert F(v) > m0                                   # timing carries information beyond the pixels


def test_subpixel_motion_is_taken_up_by_the_delay():
    tau = 4000.0
    ev = hd.edge_scene(W, H, 6, tau, 3, 0.05, 40, 8, 1)
    ref = th.evaluate_group(ev, 5, W, H)
    # the same scene at 6.5 px per window
    rng = np.random.default_rng(1)
    v = 6.5 / T0
    T, X, Y, P = [], [], [], []
    xs = np.arange(W)
    for e, x_e in enumerate(range(-int(np.ceil(v * 8 * T0)) - 40, W, 40)):
        for y in range(H):
            phi = rng.random()
            t0 = (xs - x_e + phi) / v
            ok = (t0 >= -3 * tau) & (t0 < 8 * T0)
            xx = xs[ok]
            A = (1.0 - rng.random(len(xx))) * tau
            for j in range(3):
                T.append(t0[ok] + A + j * tau + rng.normal(0, 0.05 * tau, len(xx))); X.append(xx)
                Y.append(np.full(len(xx), y)); P.append(np.full(len(xx), e % 2))
    t = np.rint(np.concatenate(T)).astype(np.int64)
    x, y, p = (np.concatenate(a).astype(np.int64) for a in (X, Y, P))
    k = (t >= 0) & (t < 8 * T0)
    o_ = np.argsort(t[k], kind="stable")
    ev2 = tuple(a[k][o_] for a in (t, x, y, p))
    o = th.evaluate_group(ev2, 5, W, H)
    assert np.mean(np.array(o["blocks"]["delta_us"]) != 0) > 0.8
    for cell in ((1, 32), (1, 64)):
        a = F(pooled(o["sums"], "pixel", cell).sum(axis=0))
        b = F(pooled(ref["sums"], "pixel", cell).sum(axis=0))
        assert a > 0.85 * b


def test_textured_translation_gives_the_true_shift():
    sc = synth.rigid_translation(width=W, height=H, n_points=3000, box_wh=(140.0, 100.0), c0=(120.0, 120.0),
                                 v=(180.0, 0.0), duration_s=0.4, seed=4)
    ev = tuple(np.asarray(a, dtype=np.int64) for a in (sc.t, sc.x, sc.y, sc.p))
    o = th.evaluate_group(ev, 5, W, H)
    s = np.array(o["blocks"]["shift"])
    assert len(s) >= 8 and np.mean((s[:, 0] == 6) & (s[:, 1] == 0)) > 0.9


def test_hot_pixels_are_removed_and_flicker_is_flagged():
    ev = hd.edge_scene(W, H, 6, 2000.0, 3, 0.05, 40, 8, 2)
    hot_t = np.arange(0, 8 * T0, 500)
    hot = (hot_t, np.full(len(hot_t), 33), np.full(len(hot_t), 77), np.zeros(len(hot_t), dtype=np.int64))
    fl_t = np.concatenate([np.arange(int(ph), 8 * T0, 10_000) for ph in np.linspace(0, 9000, 400)])
    fx = np.repeat(np.arange(200, 220), 20)[:400]
    fy = np.tile(np.arange(200, 220), 20)[:400]
    reps = np.repeat(np.arange(400), [len(np.arange(int(ph), 8 * T0, 10_000)) for ph in np.linspace(0, 9000, 400)])
    fl = (fl_t, fx[reps], fy[reps], np.ones(len(fl_t), dtype=np.int64))
    allv = tuple(np.concatenate(z) for z in zip(ev, hot, fl))
    o_ = np.argsort(allv[0], kind="stable")
    o = th.evaluate_group(tuple(a[o_] for a in allv), 5, W, H)
    assert o["n_hot"] >= 1
    taus = np.array(o["blocks"]["tau_us"])
    assert np.any(np.abs(taus - 10_000) < 200)
    assert o["sums"]["block"][1].sum() > 0                          # the flicker block is in the flicker stratum


def test_sums_are_consistent():
    ev = hd.edge_scene(W, H, 6, 2000.0, 3, 0.05, 40, 8, 2)
    o = th.evaluate_group(ev, 5, W, H)
    for scope in ("pixel", "block"):
        s = o["sums"][scope]
        assert np.all(s[..., 2] <= np.minimum(s[..., 0], s[..., 1])) and np.all(s[..., 3] <= np.minimum(s[..., 0], s[..., 1]))
    n = np.array(o["blocks"]["N"]).sum()
    assert o["sums"]["pixel"][:, :, 0, :, 0].sum() == n
    assert th.best_shift(*(tuple(np.zeros(0, dtype=np.int64) for _ in range(4)),) * 2, 100, 100) == ((0, 0), 0)
