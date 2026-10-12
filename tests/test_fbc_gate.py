"""Gate for directive 016: the flow-based baseline and the two downstream tasks, on synthetic events.

Parallel straight edges move across a small sensor at a known speed. Each pixel emits n events per
passage with a uniform phase and Gaussian jitter. The motion task uses the textured translation of
``ec.synth``, because straight edges leave the velocity along them undetermined. The tolerances are
fixed by the director.
"""
import numpy as np

from ec import blockcodec as bc
from ec import downstream as ds
from ec import fbc
from ec import synth

W, H, U, N, TAU = 320, 240, 200.0, 3, 2000


def edges(seed=0, jitter=100.0):
    rng = np.random.default_rng(seed)
    XX, YY = np.meshgrid(np.arange(W), np.arange(H))
    T, X, Y = [], [], []
    for x0 in np.arange(-200, W, 40):
        tp = (XX - x0) / U * 1e6
        ph = rng.random(XX.shape) * TAU
        for j in range(N):
            tt = tp + ph + j * TAU + rng.normal(0, jitter, XX.shape)
            s = (tt > 0) & (tt < 1e6)
            T.append(tt[s]); X.append(XX[s]); Y.append(YY[s])
    t = np.rint(np.concatenate(T)).astype(np.int64)
    o = np.argsort(t, kind="stable")
    return t[o], np.concatenate(X)[o], np.concatenate(Y)[o], np.zeros(len(t), dtype=np.int64)


def test_plane_flow_recovers_the_speed():
    t, x, y, p = edges()
    vx, vy, ok = fbc.plane_flow(t, x, y, p, 300_000, W, H, radius=4)
    assert ok.sum() > 10_000
    assert abs(np.median(vx[ok]) - U) < 0.05 * U and abs(np.median(vy[ok])) < 5


def test_record_is_decodable_and_deterministic():
    t, x, y, p = edges()
    fl = fbc.group_flows(t, x, y, p, 6, W, H, radius=4)
    for coder in bc.CODERS:
        r1 = fbc.encode_group(t, x, y, p, 6, 4, W, H, coder, fl)
        r2 = fbc.encode_group(t, x, y, p, 6, 4, W, H, coder, fl)
        assert r1 == r2
        win = fbc.reconstruct(r1, 6, 4, W, H)
        assert len(win) == 4 and all(len(w[0]) > 0 for w in win)
        for m, (rt, rx, ry, rp) in enumerate(win):
            a = (6 + m) * bc.T0_US
            assert rt.min() >= a and rt.max() < a + bc.T0_US
            assert rx.min() >= 0 and rx.max() < W and ry.min() >= 0 and ry.max() < H


def test_baseline_saves_bits_and_keeps_fidelity_on_edges():
    t, x, y, p = edges()
    r = fbc.evaluate_group(t, x, y, p, 6, W, H, Ks=(4,), coders=("T",), radius=4)["T_K4"]
    w0 = 6 * bc.T0_US
    direct = 0
    for m in range(4):
        a = w0 + m * bc.T0_US
        s = (t >= a) & (t < a + bc.T0_US)
        direct += len(bc.encode_events_T(t[s] - a, x[s], y[s], p[s]))
    assert r["bytes"] < 0.5 * direct
    assert r["F"] > 0.55


def test_downstream_tasks():
    sc_ = synth.rigid_translation(width=W, height=H, n_points=1500, box_wh=(60, 40), c0=(60, 120),
                                  v=(200.0, -80.0), duration_s=1.0, jitter_us=200, seed=1)
    w0 = 6 * bc.T0_US
    s = (sc_.t >= w0) & (sc_.t < w0 + bc.T0_US)
    ev = (sc_.t[s], sc_.x[s].astype(np.int64), sc_.y[s].astype(np.int64), sc_.p[s].astype(np.int64))
    box = (60, 60, 120, 120)
    v = ds.cmax_velocity(ev, box, w0)
    assert abs(v[0] - 0.2) <= 0.02 and abs(v[1] + 0.08) <= 0.02
    sc = ds.box_scores(ev, ev, box, w0)
    assert sc["F"] == 1.0 and sc["centroid_px"] == 0.0
    shifted = (ev[0], ev[1] + 4, ev[2], ev[3])
    assert ds.box_scores(ev, shifted, box, w0)["centroid_px"] > 3.0
    assert ds.motion_error_px(ev, shifted, box, w0) < 1.0
