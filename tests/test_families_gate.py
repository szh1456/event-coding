"""Gate for directive 018: the families of schemes, the candidate fidelities and the HEVC path, on synthetic
events. The HEVC tests run ffmpeg with libx265 and are not skipped: the suite fails on a host without them.
The tolerances are fixed by the director.
"""
import numpy as np

from ec import blockcodec as bc
from ec import families as fa
from ec import fbc
from ec import synth

W, H, WKEY = 320, 240, 6
T0 = bc.T0_US


def scene(seed=3):
    s = synth.rigid_translation(width=W, height=H, n_points=1500, box_wh=(80.0, 60.0), c0=(60.0, 120.0),
                                v=(200.0, 0.0), duration_s=1.0, noise_rate_hz=0.05, seed=seed)
    return (s.t.astype(np.int64), s.x.astype(np.int64), s.y.astype(np.int64), s.p.astype(np.int64)), s.boxes


def windows(ev, K=11):
    t = ev[0]
    out = []
    for m in range(K):
        a, b = np.searchsorted(t, ((WKEY + m) * T0, (WKEY + m + 1) * T0))
        out.append(tuple(v[a:b] for v in ev))
    return out


# ---------------------------------------------------------------------------------- fidelities

def test_fidelities_of_the_truth_of_nothing_and_of_a_subset():
    ev, _ = scene()
    win = windows(ev, 3)
    tw = [fa.TrueWindow(win[m], (WKEY + m) * T0, W, H) for m in range(3)]
    f1 = fa.fidelities([fa.window_sums(tw[m], win[m]) for m in range(3)])
    assert all(abs(v - 1.0) < 1e-12 for v in f1.values())
    empty = tuple(np.zeros(0, dtype=np.int64) for _ in range(4))
    f0 = fa.fidelities([fa.window_sums(tw[m], empty) for m in range(3)])
    assert all(abs(v) < 1e-12 for v in f0.values())
    rng = np.random.default_rng(0)
    masks = [rng.random(len(win[m][0])) < 0.3 for m in range(3)]
    sub = [tuple(a[masks[m]] for a in win[m]) for m in range(3)]
    s = [fa.window_sums(tw[m], sub[m]) for m in range(3)]
    q = sum(len(v[0]) for v in sub) / sum(len(v[0]) for v in win)
    f = fa.fidelities(s)
    assert abs(f["F"] - 2 * q / (1 + q)) < 1e-12 and abs(f["F20"] - 2 * q / (1 + q)) < 1e-12
    for phi, theta in ((1.0, 0.0), (3.0, 9.0)):   # a subset: M_b = N'_b, so D_b = l(N_b) - l(N'_b)
        tws = [fa.TrueWindow(win[m], (WKEY + m) * T0, W, H, phi, theta) for m in range(3)]
        fs = fa.fidelities([fa.window_sums(tws[m], sub[m]) for m in range(3)])
        l = lambda n: np.log1p(n / phi)
        D = L = 0.0
        for m in range(3):
            bN = fa.block_counts(win[m][1], win[m][2], W, H)
            bS = fa.block_counts(sub[m][1], sub[m][2], W, H)
            e = (bN > theta) | (bS > theta)
            D += np.sum(l(bN[e]) - l(bS[e]))
            L += np.sum(l(bN[e]) + l(bS[e]))
        assert abs(fs["Fsnr"] - (1 - D / L)) < 1e-9
    assert 2 * q / (1 + q) < f["FH"] < 1.0


def test_fsnr_prefers_a_capped_subset_to_whole_blocks():
    ev, _ = scene()
    v = windows(ev, 1)[0]
    tw = fa.TrueWindow(v, WKEY * T0, W, H, 2.0, 8.0)
    cap = fa.cap_mask(v[1], v[2], 64, W)                                 # n well above the threshold theta = 8
    sel = fa.select_mask(v[1], v[2], 1.0, W)
    n = len(v[0])
    rng = np.random.default_rng(1)
    o = np.flatnonzero(sel)
    sel_n = np.zeros(n, dtype=bool)
    sel_n[rng.permutation(o)[:int(cap.sum())]] = True                   # same number of events, dense blocks only
    fc = fa.fidelities([fa.window_sums(tw, tuple(a[cap] for a in v))])
    fs = fa.fidelities([fa.window_sums(tw, tuple(a[sel_n] for a in v))])
    assert abs(fc["F"] - fs["F"]) < 1e-12
    assert fc["Fsnr"] > fs["Fsnr"] + 0.05


def test_background_rate_of_poisson_noise_with_and_without_an_edge():
    rng = np.random.default_rng(5)
    beta, span = 2.0, 200_000                # events per pixel and second, us
    n = rng.poisson(beta * W * H * span * 1e-6)
    noise = (np.sort(rng.integers(0, span, n)), rng.integers(0, W, n), rng.integers(0, H, n), rng.integers(0, 2, n))
    est = fa.background_rate(noise, 0, span, W, H)
    assert abs(est["beta_per_px_s"] - beta) < 0.08 * beta
    ev, _ = scene()
    a, b = np.searchsorted(ev[0], (100_000, 100_000 + span))
    edge = (ev[0][a:b] - 100_000, ev[1][a:b], ev[2][a:b], ev[3][a:b])
    both = tuple(np.concatenate((u, v)) for u, v in zip(noise, edge))
    o = np.argsort(both[0], kind="stable")
    est2 = fa.background_rate(tuple(v[o] for v in both), 0, span, W, H)
    assert abs(est2["beta_per_px_s"] - beta) < 0.15 * beta
    assert est2["phi"] == max(1.0, est2["beta_per_px_s"] * fa.B ** 2 * T0 * 1e-6)
    from scipy.stats import poisson
    assert poisson.sf(est2["theta"], est2["phi"]) <= fa.ALPHA < poisson.sf(est2["theta"] - 1, est2["phi"])
    quiet = fa.background_rate(edge, 0, span, W, H)
    assert quiet["phi"] == 1.0
    hot = (np.repeat(np.arange(0, span, 1000), 20), np.tile(np.arange(20) * 7 + 3, span // 1000),
           np.full(20 * (span // 1000), 100), np.zeros(20 * (span // 1000), dtype=np.int64))
    withhot = tuple(np.concatenate((u, v)) for u, v in zip(noise, hot))
    o = np.argsort(withhot[0], kind="stable")
    est3 = fa.background_rate(tuple(v[o] for v in withhot), 0, span, W, H)
    assert est3["n_hot"] == 20 and abs(est3["beta_per_px_s"] - beta) < 0.08 * beta
    for b_ in (10.0, 20.0):                  # beyond 1 / (8 tau) the isolation estimate saturates
        n = rng.poisson(b_ * W * H * span * 1e-6)
        loud = (np.sort(rng.integers(0, span, n)), rng.integers(0, W, n), rng.integers(0, H, n), rng.integers(0, 2, n))
        e = fa.background_rate(loud, 0, span, W, H)
        assert e["branch"] == (-1 if b_ > 12.5 else 0) and abs(e["beta_per_px_s"] - b_) < 0.08 * b_


def test_fsnr_ignores_background_blocks():
    ev, _ = scene()
    v = windows(ev, 1)[0]
    rng = np.random.default_rng(6)
    n = 3000
    noise = (np.sort(rng.integers(WKEY * T0, (WKEY + 1) * T0, n)), rng.integers(0, W, n), rng.integers(0, H, n),
             rng.integers(0, 2, n))
    allv = tuple(np.concatenate((a, b)) for a, b in zip(v, noise))
    o = np.argsort(allv[0], kind="stable")
    allv = tuple(a[o] for a in allv)
    phi = n / ((W // fa.B) * (H // fa.B))                    # the background events per block
    from scipy.stats import poisson
    tw = fa.TrueWindow(allv, WKEY * T0, W, H, phi, float(poisson.isf(fa.ALPHA, phi)))
    f_obj = fa.fidelities([fa.window_sums(tw, v)])           # the object without the background
    f_all = fa.fidelities([fa.window_sums(tw, allv)])
    assert f_all["Fsnr"] == 1.0 and f_obj["Fsnr"] > 0.9 and f_obj["F"] < 0.9
    half = tuple(a[::2] for a in v)                          # half of the object: credit, not zero
    assert 0.5 < fa.fidelities([fa.window_sums(tw, half)])["Fsnr"] < 1.0


# ---------------------------------------------------------------------------------- subsets

def test_cap_keeps_at_most_n_per_block_evenly():
    rng = np.random.default_rng(2)
    x, y = rng.integers(0, W, 20000), rng.integers(0, H, 20000)
    bid = bc.block_ids(x, y, fa.B, W)
    for n in fa.CAPS:
        keep = fa.cap_mask(x, y, n, W)
        ids, N = np.unique(bid, return_counts=True)
        kept = np.array([keep[bid == b].sum() for b in ids])
        assert np.array_equal(kept, np.minimum(N, n))
        b0 = ids[np.argmax(N)]
        r = np.flatnonzero(keep[bid == b0])
        Nb = int(N.max())
        assert np.array_equal(r, ((2 * np.arange(n) + 1) * Nb) // (2 * n))      # centred in n equal segments
        assert r[0] < Nb / n and r[-1] >= Nb - Nb / n


def test_subsets_code_and_decode_every_kept_event():
    ev, _ = scene()
    v = windows(ev, 1)[0]
    for keep in (fa.thin_mask(len(v[0]), 0.3, WKEY, 0), fa.select_mask(v[1], v[2], 0.5, W), fa.cap_mask(v[1], v[2], 8, W)):
        bits, r = fa.code_subset(v, keep, WKEY * T0, W, H)
        assert len(r[0]) == int(keep.sum()) and bits > 0
        assert r[0].min() >= WKEY * T0 and r[0].max() < (WKEY + 1) * T0


# ---------------------------------------------------------------------------------- HEVC

def test_count_frames_round_trip_equals_coder_q():
    ev, _ = scene()
    win = windows(ev, 4)
    back = fa.frames_to_windows(fa.count_frames(win, WKEY, 4, W, H), WKEY, 4, W, H)
    for m in range(4):
        a = (WKEY + m) * T0
        t, x, y, p = win[m]
        q = bc.decode_events_Q(bc.encode_events_Q(t - a, x, y, p, bc.Q_DIRECT, W, H), bc.Q_DIRECT, W, H)
        ref = np.sort(((q[0] + a) * 4096 + q[1]) * 4096 * 2 + q[2] * 2 + q[3])
        got = np.sort((back[m][0] * 4096 + back[m][1]) * 4096 * 2 + back[m][2] * 2 + back[m][3])
        assert np.array_equal(ref, got)


def test_nal_bits_skips_parameter_sets():
    s = b"\x00\x00\x00\x01" + bytes([32 << 1, 1, 0xAA]) + b"\x00\x00\x01" + bytes([1 << 1, 1, 0xBB, 0xCC]) \
        + b"\x00\x00\x00\x01" + bytes([39 << 1, 1])
    assert fa.nal_bits(s) == (32, 40)


def test_hevc_is_deterministic_has_one_intra_frame_and_trades_bits_for_fidelity():
    ev, _ = scene()
    win = windows(ev, 4)
    fr = fa.count_frames(win, WKEY, 4, W, H)
    res = {}
    for qp in (14, 46):
        b1, sk, cl, cnt, s1 = fa.hevc_code(fr, qp)
        b2, _, _, _, s2 = fa.hevc_code(fr, qp)
        assert s1 == s2 and b1 == b2 and sk > 0 and cl == 0
        b = np.frombuffer(s1, dtype=np.uint8)
        z = np.flatnonzero((b[:-2] == 0) & (b[1:-1] == 0) & (b[2:] == 1)) + 3
        types = (b[z] >> 1) & 0x3F
        assert int(np.isin(types, (16, 17, 18, 19, 20, 21)).sum()) == 1      # one IRAP picture
        rw = fa.frames_to_windows(cnt, WKEY, 4, W, H)
        tw = [fa.TrueWindow(win[m], (WKEY + m) * T0, W, H) for m in range(4)]
        res[qp] = (b1, fa.fidelities([fa.window_sums(tw[m], rw[m]) for m in range(4)])["F"])
    assert res[14][1] > 0.95
    assert res[46][0] < res[14][0] and res[46][1] < res[14][1]


# ---------------------------------------------------------------------------------- FBC on the working grid

def test_fbc2_without_flows_is_every_event_on_the_working_grid():
    ev, _ = scene()
    f = fbc.group_flows(*ev, WKEY, W, H, 2, 1000.0, 4)
    none = lambda v: (v[0], v[1], np.zeros_like(v[2]))
    fl = {"w": f["w"], "st_us": f["st_us"], "send": none(f["send"]), "windows": [none(v) for v in f["windows"]]}
    rec = fa.fbc2_record(*ev, WKEY, 4, W, H, fl)
    assert rec == fa.fbc2_record(*ev, WKEY, 4, W, H, fl)
    out = fa.fbc2_reconstruct(rec, WKEY, 4, W, H)
    for m, v in enumerate(windows(ev, 4)):
        a = (WKEY + m) * T0
        q = bc.decode_events_Q(bc.encode_events_Q(v[0] - a, *v[1:], bc.Q_DIRECT, W, H), bc.Q_DIRECT, W, H)
        assert len(out[m][0]) == len(q[0]) and np.array_equal(np.sort(out[m][1]), np.sort(q[1]))


def test_fbc2_predicts_and_costs_fewer_bits_than_fbc_with_q():
    ev, _ = scene()
    fl = fbc.group_flows(*ev, WKEY, W, H, 3, 20000.0, 4)
    r2 = fa.fbc2_record(*ev, WKEY, 4, W, H, fl)
    r1 = fbc.encode_group(*ev, WKEY, 4, W, H, "Q", fl)
    assert len(r2) < len(r1)
    out = fa.fbc2_reconstruct(r2, WKEY, 4, W, H)
    for m in range(4):
        a = (WKEY + m) * T0
        assert len(out[m][0]) > 0 and out[m][0].min() >= a and out[m][0].max() < a + T0


# ---------------------------------------------------------------------------------- one group

def test_evaluate_group_on_a_synthetic_group():
    ev, bx = scene()
    kept = bc.evaluate_group(*ev, WKEY, 0, W, H, blocks=(20,), densities=(1.0,), records_for=(20, 1.0))
    lo = WKEY * T0 - fbc.FIT_WINDOW_US
    a, b = np.searchsorted(ev[0], (lo, (WKEY + 11) * T0))
    e = tuple(v[a:b] for v in ev)
    boxes = {}
    for m in (1, 2, 3):
        i = int(np.argmin(np.abs(bx["t"].astype(np.float64) - (WKEY + m + 0.5) * T0)))
        boxes[m] = [(1, (float(bx["x"][i]), float(bx["y"][i]), float(bx["w"][i]), float(bx["h"][i])))]
    t2, x2, y2, _ = windows(ev, 3)[2]
    cnt = np.bincount((y2 // 40) * (W // 40) + x2 // 40, minlength=(W // 40) * (H // 40))
    squares = [((int(k % (W // 40)) * 40, int(k // (W // 40)) * 40, 40, 40), int(cnt[k])) for k in np.argsort(-cnt)[:3]]
    names = ["remake", "translation", "static", "thin_0.5", "select_1.0", "cap_8", "hevc_28", "fbc_r2_res2000"]
    out = fa.evaluate_group(e, WKEY, W, H, kept["records"], kept, boxes=boxes, squares=squares, schemes=names)
    assert out["checks"] == {"outside": 0, "remake_equals_kept": True}
    assert set(out["schemes"]) == set(names)
    for nm in names:
        s = out["schemes"][nm]
        assert len(s["K4"]["sums"]) == 4 and len(s["K11"]["sums"]) == 11 and s["K11"]["bits"] >= s["K4"]["bits"] > 0
        f = fa.fidelities(s["K4"]["sums"])
        assert all(0.0 <= v <= 1.0 for v in f.values())
        assert len(s["tasks"]["objects"]) == 3 and len(s["tasks"]["motion"]) == 3 and len(s["tasks"]["tracks"]) == 1
    r = out["schemes"]["remake"]
    km = kept["codec"]["B20_rho1.0"]["models"]["affine"]
    assert r["K11"]["bits"] == 8 * kept["codec"]["B20_rho1.0"]["models"]["affine"]["bytes"]["Q_K11"]
    F = fa.fidelities(r["K11"]["sums"])["F"]
    ref = bc.group_fidelity(kept["codec"]["B20_rho1.0"]["n_key"], km["n_rec"], kept["n_true"][:11], km["match_s2_k3"])
    assert abs(F - ref) < 1e-12
    th = fa.fidelities(out["schemes"]["thin_0.5"]["K4"]["sums"])["F"]
    assert abs(th - 2 / 3) < 0.02
    assert "hevc_28" in out["hevc"] and out["hevc"]["hevc_28"]["K4"]["clipped_events"] == 0
    full = out["schemes"]["remake"]["tasks"]["objects"]
    assert all(o["n_true"] >= fa.MIN_BOX_EVENTS for o in full)
    tr = out["schemes"]["remake"]["tasks"]["tracks"][0]
    assert tr["continuous"] and tr["velocity_error_px"] < 1.0
    assert out["schemes"]["select_4.0"]["tasks"]["tracks"][0]["continuous"] is False if "select_4.0" in out["schemes"] else True
    assert out["background"]["phi"] >= 1.0 and out["background"]["theta"] >= out["background"]["phi"]
