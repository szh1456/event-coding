"""Gate for directive 019: the three diagnostics of ``ec.hevcdiag`` on synthetic events.

The HEVC tests run ffmpeg with libx265 and are not skipped. The tolerances are fixed by the director.
"""
import numpy as np

from ec import blockcodec as bc
from ec import families as fa
from ec import hevcdiag as hd
from ec import synth

W, H, WKEY = 320, 240, 6
T0 = bc.T0_US


def scene(seed=3):
    s = synth.rigid_translation(width=W, height=H, n_points=1500, box_wh=(80.0, 60.0), c0=(60.0, 120.0),
                                v=(200.0, 0.0), duration_s=0.5, noise_rate_hz=0.05, seed=seed)
    return (s.t.astype(np.int64), s.x.astype(np.int64), s.y.astype(np.int64), s.p.astype(np.int64))


def test_slices_and_placements_keep_their_bin():
    for k in hd.KS:
        f = np.arange(k)
        assert np.array_equal(bc.time_bin(-((-f * T0) // k), k), f)
        assert np.array_equal(bc.time_bin(((2 * f + 1) * T0) // (2 * k), k), f)


def test_representation_round_trip_on_every_grid():
    win = hd.windows_of(scene(), WKEY, hd.K_WIN)
    for s in hd.SPACES:
        for k in hd.KS:
            key, cnt = hd.voxel_counts(win, WKEY, hd.K_WIN, s, k, W, H)
            dense = hd.count_frames(win, WKEY, hd.K_WIN, s, k, W, H)
            assert dense.sum() == cnt.sum() == sum(len(v[0]) for v in win)
            assert np.array_equal(np.flatnonzero(dense.ravel()), key)
            for placement in hd.PLACEMENTS:
                ev = hd.voxels_to_windows(key, cnt, WKEY, hd.K_WIN, s, k, W, H, placement)
                f = hd.fidelities([hd.sums_on(win[m], ev[m], (WKEY + m) * T0, (s, k), W, H) for m in range(hd.K_WIN)])
                assert f["F"] == 1.0 and f["Fsnr"] == 1.0
                for m, e in enumerate(ev):
                    a = (WKEY + m) * T0
                    assert e[0].min() >= a and e[0].max() < a + T0 and e[1].max() < W and e[2].max() < H


def test_sums_on_equal_those_of_directive_018_on_its_grid():
    win = hd.windows_of(scene(), WKEY, 2)
    rng = np.random.default_rng(0)
    keep = rng.random(len(win[1][0])) < 0.4
    sub = tuple(a[keep] for a in win[1])
    for phi, theta in ((1.0, 0.0), (3.0, 9.0)):
        tw = fa.TrueWindow(win[1], (WKEY + 1) * T0, W, H, phi, theta)
        ref = fa.window_sums(tw, sub)
        got = hd.sums_on(win[1], sub, (WKEY + 1) * T0, fa.GRID, W, H, phi, theta)
        assert got["M"] == ref["M"] and abs(got["Dsnr"] - ref["Dsnr"]) < 1e-9 and abs(got["Lsnr"] - ref["Lsnr"]) < 1e-9


def test_hevc_lossless_returns_the_counts_and_the_csv_has_every_frame():
    win = hd.windows_of(scene(), WKEY, hd.K_WIN)
    nx, ny, fh, fw = hd.dims(2, W, H)
    key, raw = hd.voxel_counts(win, WKEY, hd.K_WIN, 2, 3, W, H)
    cnt = np.minimum(raw, hd.HEVC_MAX)
    r = hd.hevc(key, cnt, hd.K_WIN * 3, fh, fw, "lossless")
    assert np.array_equal(r["key"], key) and np.array_equal(r["cnt"], cnt)
    assert len(r["frames"]) == hd.K_WIN * 3 and r["frames"][0]["type"].startswith("I")
    assert all(f["type"].startswith("P") for f in r["frames"][1:])
    assert sum(f["bits"] for f in r["frames"]) > 0 and r["param_bits"] > 0 and r["enc_cpu_s"] > 0
    for f in r["frames"]:
        assert abs(f["intra"] + f["inter"] + f["skip"] + f["merge"] - 100.0) <= 0.5
    assert r["frames"][0]["intra"] > 99.0 and r["padding_counts"] == 0
    q = hd.hevc(key, cnt, hd.K_WIN * 3, fh, fw, "qp24")
    assert len({f["qp"] for f in q["frames"]}) == 1                     # ipratio=1: one QP for I and P
    r2 = hd.hevc(key, cnt, hd.K_WIN * 3, fh, fw, "lossless")
    assert r2["bits"] == r["bits"]


def test_code_counts_on_a_small_group():
    win = hd.windows_of(scene(), WKEY, hd.K_WIN)
    out = hd.code_counts(win, WKEY, 2, 3, W, H, ("lossless", "qp12", "qp40", "sparse"), 1.0, 5.0)
    assert out["clipped_events"] == 0 and out["clip_fid"]["F"] == 1.0
    m = out["modes"]
    assert m["lossless"]["fid"]["F"] == 1.0
    assert m["qp12"]["fid"]["F"] > 0.95 and m["qp40"]["bits"] < m["qp12"]["bits"]
    assert m["qp40"]["fid"]["F"] < m["qp12"]["fid"]["F"]
    assert m["sparse"]["bits"] > 0


def test_clipping_is_counted():
    t = np.full(40, WKEY * T0 + 5, dtype=np.int64)
    x, y, p = np.full(40, 10), np.full(40, 10), np.zeros(40, dtype=np.int64)
    win = [(t, x, y, p)] + [tuple(np.zeros(0, dtype=np.int64) for _ in range(4))] * (hd.K_WIN - 1)
    out = hd.code_counts(win, WKEY, 1, 1, W, H, ("lossless",), 1.0, 0.0)
    assert out["clipped_events"] == 40 - hd.HEVC_MAX
    assert abs(out["clip_fid"]["F"] - 2 * hd.HEVC_MAX / (40 + hd.HEVC_MAX)) < 1e-12


def test_oracle_shift_follows_eq_binfidmoved_at_a_longer_spacing():
    ev = hd.edge_scene(W, H, 4, 8000.0, 4, 0.05, 40, 6, 2)
    for k in (12, 32, 64):
        o = hd.oracle_shift(ev, 4, 1, k, W, H, 6)
        assert abs(o["F"] - hd.binfidmoved(T0 / k, 8000.0, 4)) < 0.02


def test_oracle_shift_follows_eq_binfidmoved_on_the_model():
    tau = 4000.0
    ev = hd.edge_scene(W, H, 6, tau, 3, 0.05, 40, 6, 1)
    for k in hd.KS:
        o = hd.oracle_shift(ev, 6, 1, k, W, H, 6)
        dt = T0 / k
        pred = hd.binfidmoved(dt, tau, 3)
        if not np.isnan(pred):
            assert abs(o["F"] - pred) < 0.02
    fs = [hd.oracle_shift(ev, 6, 1, k, W, H, 6)["F"] for k in hd.KS]
    assert all(a >= b for a, b in zip(fs, fs[1:]))       # finer slices, worse prediction


def test_represent_keeps_every_event():
    win = hd.windows_of(scene(), WKEY, hd.K_WIN)
    r = hd.represent(win, WKEY, 2, 12, W, H, "center")
    assert r["placement"] == "center" and r["tasks"] is None
