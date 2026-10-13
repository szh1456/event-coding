"""Gate for directive 017: regions, event spacing and per-block precision, on synthetic events.

A textured box translates across a small sensor. The reference codec of directive 007 fits and writes the
records of one group, as the kept per-group files hold them; ``ec.regions`` then reads only those records
and the true events. The tolerances are fixed by the director.
"""
import numpy as np

from ec import blockcodec as bc
from ec import downstream as dn
from ec import regions as rg
from ec import synth

W, H, WKEY = 320, 240, 6
T0 = bc.T0_US


def scene():
    s = synth.rigid_translation(width=W, height=H, n_points=1500, box_wh=(80.0, 60.0), c0=(60.0, 120.0),
                                v=(200.0, 0.0), duration_s=1.0, seed=3)
    return (s.t.astype(np.int64), s.x.astype(np.int64), s.y.astype(np.int64), s.p.astype(np.int64)), s.boxes


def kept_group(ev):
    return bc.evaluate_group(*ev, WKEY, 0, W, H, blocks=(20,), densities=(1.0,), models=("affine",),
                             records_for=(20, 1.0))


def windows(ev):
    t = ev[0]
    out = []
    for m in range(11):
        a, b = np.searchsorted(t, ((WKEY + m) * T0, (WKEY + m + 1) * T0))
        out.append(tuple(v[a:b] for v in ev))
    return out


def boxes_of(bx, m):
    c = (WKEY + m + 0.5) * T0
    i = int(np.argmin(np.abs(bx["t"].astype(np.float64) - c)))
    return [(float(bx["x"][i]), float(bx["y"][i]), float(bx["w"][i]), float(bx["h"][i]))]


_CACHE = {}


def group():
    if not _CACHE:
        ev, bx = scene()
        g = kept_group(ev)
        win = windows(ev)
        a, b = np.searchsorted(ev[0], ((WKEY - rg.SPAN_BEFORE) * T0, WKEY * T0))
        before = tuple(v[a:b] for v in ev)
        out = rg.evaluate_group(win, g["records"], WKEY, W, H, g, boxes=[boxes_of(bx, m) for m in range(4)],
                                before=before)
        _CACHE.update(ev=ev, g=g, win=win, out=out, bx=bx)
    return _CACHE


def test_checks_hold_on_a_moving_box():
    out = group()["out"]
    assert out["checks"] == {"n_key": True, "maps_k4_prefix": True, "match_equals_kept": True}
    assert len(out["blocks"]["ids"]) >= 4
    assert not out["blocks"]["static"].any()
    assert np.all(np.abs(out["blocks"]["speed_px_per_window"] - 200.0 * T0 * 1e-6) < 2.0)


def test_regions_and_pairs_lie_in_the_box():
    out = group()["out"]
    assert out["events"]["key_in_box"][10] == out["n_key"]
    assert out["blocks"]["touch"][10].all()
    pr = out["pairs"]
    assert all(m > 0 for m in pr["match"])
    assert all(a >= 0.95 * b for a, b in zip(pr["match_in_box"], pr["match"]))
    assert len(out["boxes0"]) == 1 and out["boxes0"][0]["n_in_active"] <= out["boxes0"][0]["n_true"]


def test_precision_falls_with_the_bin_and_pairs_add_up():
    out = group()["out"]
    prec = out["blocks"]["prec"]
    got = {c: prec[rg.cell_name(c)]["got"].sum() for c in rg.PREC_CELLS}
    n_in = {c: prec[rg.cell_name(c)]["n_in"].sum() for c in rg.PREC_CELLS}
    assert len(set(n_in.values())) == 1
    assert got[(2, 3)] >= got[(1, 3)] >= got[(1, 12)] >= got[(1, 32)] > 0


def test_box_mask_is_the_rule_of_box_scores():
    rng = np.random.default_rng(0)
    yy, xx = np.mgrid[0:H, 0:W]
    for _ in range(20):
        box = (rng.uniform(-10, W), rng.uniform(-10, H), rng.uniform(0.5, 90), rng.uniform(0.5, 90))
        for d in rg.MARGINS:
            m = rg.box_mask([box], W, H, d)
            ref = (xx >= box[0] - d) & (xx < box[0] + box[2] + d) & (yy >= box[1] - d) & (yy < box[1] + box[3] + d)
            assert np.array_equal(m, ref)
        t = np.zeros(1000, dtype=np.int64)
        x, y = rng.integers(0, W, 1000), rng.integers(0, H, 1000)
        sc = dn.box_scores((t, x, y, t), (t, x, y, t), box, 0)
        assert sc["n_true"] == int(rg.box_mask([box], W, H, 0)[y, x].sum())


def test_claims_add_up_to_the_matched_events_in_any_order():
    rng = np.random.default_rng(1)
    true = rng.integers(0, 50, 400)
    moved = [rng.integers(0, 60, int(n)) for n in rng.integers(0, 80, 7)]
    u, c = np.unique(true, return_counts=True)
    v, cv = np.unique(np.concatenate(moved), return_counts=True)
    com, i, j = np.intersect1d(u, v, return_indices=True)
    total = int(np.minimum(c[i], cv[j]).sum())
    for _ in range(5):
        got = rg.claim_by_block(moved, true, rng.permutation(7))
        assert int(got.sum()) == total
        assert np.all(got <= [len(m) for m in moved])


def test_spacing_and_polarity_of_constructed_trains():
    ts, xs, ys, ps = [], [], [], []
    for px in range(10):                     # block 0: one pixel fires 40 events at 500 us, nine fire 4 at 2000 us
        n, d = (40, 500) if px == 0 else (4, 2000)
        ts += [100 * px + d * j for j in range(n)]; xs += [px] * n; ys += [0] * n; ps += [1] * n
    for px in range(10):                     # block 1: one event per pixel and polarity, both polarities
        ts += [50 * px, 50 * px + 500]; xs += [20 + px] * 2; ys += [0] * 2; ps += [0, 1]
    t, x, y, p = (np.asarray(a, dtype=np.int64) for a in (ts, xs, ys, ps))
    o = np.argsort(t, kind="stable")
    t, x, y, p = t[o], x[o], y[o], p[o]
    bid = bc.block_ids(x, y, rg.B, W)
    ids = np.array([0, 1])
    tau, n, cov = rg.block_spacing(t, x, y, p, bid, ids, W)
    assert tau[0] == 2000.0 and n[0] == 10 and cov[0] == 1.0      # the fast pixel counts once
    assert np.isnan(tau[1]) and n[1] == 0 and cov[1] == 0.0
    both = rg.both_polarity_share(x, y, p, bid, ids, W)
    assert both[0] == 0.0 and both[1] == 1.0


def test_spacing_of_the_moving_box_is_its_crossing_interval():
    b = group()["out"]["blocks"]
    assert np.all(np.isfinite(b["tau_us"])) and np.all(b["covered"] > 0.5)


def test_boxes_at_interpolates_between_labels():
    from ec import annotations as an
    bx = synth.rigid_translation(width=W, height=H, n_points=10, duration_s=1.0, seed=0).boxes
    tr = an.tracks(bx[::3])                  # labels at 10 Hz
    for wm in range(1, 25):
        b = rg.boxes_at(tr, wm, W, H)
        c = (wm + 0.5) * T0
        if c > tr[0].t_last:
            assert b == []
            continue
        assert len(b) == 1 and b[0][0] == tr[0].track_id
        x = float(np.interp(c, tr[0].t.astype(float), tr[0].x))
        assert abs(b[0][1][0] - max(0.0, x)) < 1e-9
