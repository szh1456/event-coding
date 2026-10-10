"""Gate for directive 007: regeneration on a fixed block grid with a complete bitstream, on synthetic scenes.

The scenes, seeds and tolerances are fixed here by the director. An executor implementation that
replaces or accelerates ``ec.blockcodec`` must pass this file unchanged.
"""
import numpy as np
import pytest

from ec import baseline, blockcodec as bc, regen, synth, synth_affine

W, H = 320, 240
T0 = bc.T0_US


def _merge(scenes, noise_per_px_window=0.0, duration_s=1.2, seed=7):
    z = [np.zeros(0, dtype=np.int64)]
    t = np.concatenate(z + [s.t for s in scenes]); x = np.concatenate(z + [s.x for s in scenes])
    y = np.concatenate(z + [s.y for s in scenes]); p = np.concatenate(z + [s.p for s in scenes])
    if noise_per_px_window > 0:
        rng = np.random.default_rng(seed)
        n = rng.poisson(noise_per_px_window * W * H * duration_s * 1e6 / T0)
        t = np.concatenate((t, rng.integers(0, int(duration_s * 1e6), n)))
        x = np.concatenate((x, rng.integers(0, W, n))); y = np.concatenate((y, rng.integers(0, H, n)))
        p = np.concatenate((p, rng.integers(0, 2, n)))
    o = np.argsort(t, kind="stable")
    return t[o].astype(np.int64), x[o].astype(np.int64), y[o].astype(np.int64), p[o].astype(np.int64)


def _scene(noise=0.01):
    a = synth.rigid_translation(width=W, height=H, n_points=400, c0=(40.0, 60.0), v=(200.0, 0.0), duration_s=1.2, seed=1)
    b = synth_affine.expanding_translation(width=W, height=H, n_points=400, c0=(100.0, 170.0), v=(60.0, 20.0),
                                           expand_rate=0.6, duration_s=1.2, seed=2)
    return _merge([a, b], noise)


@pytest.fixture(scope="module")
def ev():
    return _scene()


@pytest.fixture(scope="module")
def group(ev):
    return bc.evaluate_group(*ev, 9, 0, W, H, blocks=(40, 80), grid_for=(40, 1 / 16))


def test_uleb128_round_trip():
    v = np.array([0, 1, 127, 128, 16383, 16384, 2 ** 31, 2 ** 62 + 5])
    buf = bc.uleb_encode(v)
    assert len(buf) == 1 + 1 + 1 + 2 + 2 + 3 + 5 + 9
    out, pos = bc.uleb_decode(buf)
    assert list(out) == list(v) and pos == len(buf)
    out, pos = bc.uleb_decode(b"\xff" + buf, 3, 1)
    assert list(out) == [0, 1, 127] and pos == 4
    assert bc.uleb_encode([]) == b"" and len(bc.uleb_decode(b"")[0]) == 0


def test_coder_T_is_the_companion_transport_and_round_trips(ev):
    t, x, y, p = ev
    a, b = np.searchsorted(t, (9 * T0, 10 * T0))
    w = (t[a:b] - 9 * T0, x[a:b], y[a:b], p[a:b])
    buf = bc.encode_events_T(*w)
    assert 8 * len(buf) == baseline.payload_bits(*w)
    d = bc.decode_events_T(buf)
    o = np.lexsort((w[2], w[1], w[0]))
    assert all(np.array_equal(d[i], w[i][o]) for i in range(4))
    assert bc.encode_events_T(*(v[:0] for v in w)) == b"" and len(bc.decode_events_T(b"")[0]) == 0


def test_coder_Q_keeps_every_voxel_count_of_its_grid(ev):
    t, x, y, p = ev
    a, b = np.searchsorted(t, (9 * T0, 10 * T0))
    w = (t[a:b] - 9 * T0, x[a:b], y[a:b], p[a:b])
    for cell in ((1, 3), (2, 3), (2, 1), (1, 32)):
        d = bc.decode_events_Q(bc.encode_events_Q(*w, cell, W, H), cell, W, H)
        assert len(d[0]) == len(w[0])
        r = regen.voxel_f1(d[1], d[2], d[0], d[3], w[1], w[2], w[0], w[3], 0, T0, *cell)
        assert r["f1"] == 1.0
    # on the working grid the quantized stream is shorter than the transport, and coarser is shorter still
    q13, q23 = (len(bc.encode_events_Q(*w, c, W, H)) for c in ((1, 3), (2, 3)))
    assert q23 < q13 < len(bc.encode_events_T(*w))


def test_maps_round_trip_and_zero_maps_are_short():
    rng = np.random.default_rng(0)
    m = rng.integers(-40, 41, (7, 10, 6))
    for n_par in (2, 6):
        out = bc.decode_maps(bc.encode_maps(m, n_par), 7, 10, n_par)
        assert np.array_equal(out[:, :, :n_par], m[:, :, :n_par]) and not out[:, :, n_par:].any()
    assert len(bc.encode_maps(np.zeros((50, 10, 6), dtype=int), 6)) < 40
    assert bc.decode_maps(bc.encode_maps(np.zeros((0, 3, 6), dtype=int), 2), 0, 3, 2).shape == (0, 3, 6)


def test_the_map_with_zero_shape_parameters_is_the_translation():
    frame = bc.block_frame(9, 40, W)                       # second row, second block
    assert frame == (59.5, 59.5, 20.0)
    sx, sy = np.array([40, 50, 79]), np.array([40, 60, 79])
    ix, iy = bc.move(sx, sy, frame, (3, -2, 0, 0, 0, 0))
    assert list(ix) == [43, 53, 82] and list(iy) == [38, 58, 77]
    ix, _ = bc.move(sx, sy, frame, (0, 0, 2, 0, 0, 0))     # ia = 2: the two edges move by 2 px, outwards
    assert ix[0] == 38 and ix[-1] == 81
    assert bc.threshold(40, 1 / 16) == 100 and bc.threshold(20, 1 / 32) == 13 and bc.threshold(80, 1 / 2) == 3200
    assert bc.DENSITIES == (1 / 16, 1 / 8, 1 / 4, 1 / 2, 1.0) and bc.RADIUS_FIRST == 24


def test_the_search_never_pairs_fewer_events_than_no_motion_and_reaches_fast_objects():
    # an object at 900 px/s moves 30 px per window, beyond the first stage of a 12 px search
    a = synth.rigid_translation(width=W, height=H, n_points=300, c0=(20.0, 100.0), v=(900.0, 0.0), duration_s=0.4, seed=4)
    g = bc.evaluate_group(*_merge([a]), 1, 0, W, H, blocks=(40,), densities=(1 / 16,), models=("static", "translation"))
    r = g["codec"]["B40_rho0.0625"]["models"]
    assert r["translation"]["match_s2_k3"][0] > 0.8 * r["translation"]["n_rec"][0] > 0
    assert r["static"]["match_s2_k3"][0] < 0.4 * r["translation"]["match_s2_k3"][0]
    # a search whose window does not hold zero falls back to zero when zero pairs more
    calls = []

    def score(q, cell):
        calls.append(q)
        return 5 if q[:2] == (0, 0) else 1

    assert bc.search_translation(score, (40.0, 0.0), 3) == (0, 0)
    assert bc.search_translation(lambda q, cell: 1, (40.0, 0.0), 3) == (40, 0)


def test_a_stream_of_several_groups_decodes_from_its_bytes_alone(ev):
    t, x, y, p = ev
    hdr = bc.encode_header("T", "translation", 4, W, H, 40)
    assert len(hdr) == bc.HEADER.size == 28
    recs, sent, w_prev = [], [], 0
    for w in (9, 15, 21):
        a, b = np.searchsorted(t, (w * T0, (w + 1) * T0))
        win = (t[a:b] - w * T0, x[a:b], y[a:b], p[a:b])
        bid = bc.block_ids(win[1], win[2], 40, W)
        ids, cnt = np.unique(bid, return_counts=True)
        sel = np.isin(bid, ids[cnt >= 100])
        key = tuple(v[sel] for v in win)
        maps = np.arange(len(ids[cnt >= 100]) * 3 * 6).reshape(-1, 3, 6) % 7 - 3
        recs.append(bc.encode_group(hdr, w - w_prev, key, maps))
        sent.append((w, key, ids[cnt >= 100], maps))
        w_prev = w
    h, groups = bc.decode_stream(hdr + b"".join(recs))
    assert (h["coder"], h["model"], h["K"], h["B"], h["width"], h["height"], h["T0_us"]) == ("T", "translation", 4, 40, W, H, T0)
    assert len(groups) == 3
    for g, (w, key, ids, maps) in zip(groups, sent):
        assert g["w"] == w and np.array_equal(g["ids"], ids)
        assert np.array_equal(g["maps"][:, :, :2], maps[:, :, :2]) and not g["maps"][:, :, 2:].any()
        assert len(g["key"][0]) == len(key[0])
        r0 = bc.reconstruct(h, g, 0)
        assert r0[0].min() >= w * T0 and r0[0].max() < (w + 1) * T0
    with pytest.raises(ValueError):
        bc.decode_stream(hdr + recs[0][:-3])
    with pytest.raises(ValueError):
        bc.encode_group(hdr, 1, sent[0][1], sent[0][3][:-1])


def test_every_fidelity_comes_from_decoded_bytes_and_agrees_with_the_senders_count(group):
    for cfg, row in group["codec"].items():
        for model, r in row["models"].items():
            assert r["claim_equals_match"] and r["q_equals_t"], (cfg, model)
            assert all(0 <= a <= b for a, b in zip(r["match_s2_k3"], r["n_rec"]))
            assert all(a <= b for a, b in zip(r["match_s2_k3"], r["match_s2_k1"]))
            assert r["bytes"]["T_K2"] <= r["bytes"]["T_K4"] <= r["bytes"]["T_K8"] <= r["bytes"]["T_K11"]
            assert r["bytes"]["Q_K11"] < r["bytes"]["T_K11"] or row["n_key"] == 0
        assert row["n_key"] <= group["n_true"][0] and row["n_true_in_active"][0] == row["n_key"]
    full = group["codec"]["B40_rho0.0625"]["models"]["affine"]
    assert all(f"match_s{s}_k{k}" in full for s in (1, 2, 4) for k in (1, 3, 8, 32))
    assert all(a <= b for a, b in zip(full["match_s1_k32"], full["match_s2_k32"]))
    assert all(a <= b for a, b in zip(full["match_s2_k32"], full["match_s4_k32"]))
    assert "match_s1_k32" not in group["codec"]["B80_rho0.0625"]["models"]["affine"]


def test_match_equals_voxel_f1(ev):
    t, x, y, p = ev
    a, b, c = np.searchsorted(t, (9 * T0, 10 * T0, 11 * T0))
    tr = bc.Truth(t[b:c], x[b:c], y[b:c], p[b:c], 10 * T0)
    pt, px, py, pp = t[a:b] + T0, x[a:b] + 6, y[a:b], p[a:b]
    for cell in bc.CELLS_ALL:
        r = regen.voxel_f1(px, py, pt, pp, x[b:c], y[b:c], t[b:c], p[b:c], 10 * T0, T0, *cell)
        assert tr.match(pt, px, py, pp, cell) == round(r["f1"] * (r["n_pred"] + r["n_true"]) / 2)


def test_moving_objects_are_followed_by_the_maps_and_not_by_the_repeated_key_events(group):
    for cfg in ("B40_rho0.0625", "B80_rho0.0625"):
        s = {m: bc.summarize(group, cfg, m, "Q", 11) for m in bc.MODELS}
        assert s["translation"]["F"] > s["static"]["F"] + 0.25
        assert s["affine"]["F"] >= s["translation"]["F"] - 0.01
        # against the cheapest subset scheme the repeated key events gain nothing, the maps do
        assert s["static"]["gain"] < 1.0 and s["translation"]["gain"] > 3.0
        assert all(v["gain"] <= v["gain_thin"] for v in s.values())
        assert s["translation"]["bits"] < 0.25 * s["translation"]["bits_direct"]
    # with blocks of 80 px the growing object needs the shape parameters
    s80 = {m: bc.summarize(group, "B80_rho0.0625", m, "Q", 11) for m in bc.MODELS}
    assert s80["affine"]["F"] > s80["translation"]["F"] + 0.02
    s = bc.summarize(group, "B40_rho0.0625", "affine", "T", 4)
    assert abs(s["gamma"] - (s["F"] / (2 - s["F"])) / s["share"]) < 1e-12 and 0.15 < s["share"] < 0.25
    # a shorter group is more faithful and costs more
    a4, a11 = (bc.summarize(group, "B40_rho0.0625", "affine", "Q", K) for K in (4, 11))
    assert a4["F"] > a11["F"] and a4["bits"] > a11["bits"]


def test_thinning_is_what_its_formula_says(group):
    n = group["n_true"]
    assert bc.group_fidelity(10, [8, 6], [10, 12, 12], [4, 3]) == 2 * 17 / (10 + 14 + 34)
    for chi in bc.THIN_SHARES:
        kept = group["thin"][str(chi)]["n_kept"]
        assert abs(sum(kept) / sum(n) - chi) < 0.02
        assert all(a < b for a, b in zip(group["thin"][str(chi)]["Q"], group["direct"]["Q"]))
    # thinning costs more per kept event than sending everything: its points lie above the chord
    q = sum(group["thin"]["0.25"]["n_kept"]) / sum(n)
    assert sum(group["thin"]["0.25"]["Q"]) > q * sum(group["direct"]["Q"])


def test_the_baseline_is_the_lower_convex_envelope_of_the_subset_schemes():
    sh, b = [1.0, 0.5, 0.25], [10.0, 7.0, 4.0]                   # a concave curve, as thinning gives
    assert bc.baseline_bits(0.25, sh, b, envelope=False) == 4.0
    assert bc.baseline_bits(0.375, sh, b, envelope=False) == 5.5
    assert bc.baseline_bits(0.25, sh, b) == 2.5 and bc.baseline_bits(0.5, sh, b) == 5.0   # the chord to (1, 10)
    assert bc.baseline_bits(0.0, sh, b) == 0.0 and bc.baseline_bits(1.0, sh, b) == 10.0
    # a point under the chord enters the envelope, and the cheaper of two points at one share counts
    assert bc.baseline_bits(0.5, sh + [0.5, 0.5], b + [3.0, 9.0]) == 3.0
    assert bc.baseline_bits(0.25, sh + [0.5], b + [3.0]) == 1.5
    assert bc.baseline_bits(0.75, sh + [0.5], b + [3.0]) == 6.5


def test_select_sends_the_active_blocks_of_every_window(ev, group):
    t, x, y, p = ev
    row = group["select"]["B40_rho0.0625"]
    for m in (0, 3, 10):
        a, b = np.searchsorted(t, ((9 + m) * T0, (10 + m) * T0))
        bid = bc.block_ids(x[a:b], y[a:b], 40, W)
        ids, cnt = np.unique(bid, return_counts=True)
        sel = np.isin(bid, ids[cnt >= 100])
        assert row["n_kept"][m] == int(sel.sum())
        assert row["Q"][m] == 8 * len(bc.encode_events_Q(t[a:b][sel] - (9 + m) * T0, x[a:b][sel], y[a:b][sel], p[a:b][sel],
                                                         (2, 3), W, H))
    # in the key window select sends what the codec sends as key events
    assert row["n_kept"][0] == group["codec"]["B40_rho0.0625"]["n_key"]
    assert set(group["select"]) == set(group["codec"])


def test_one_fit_under_the_smallest_threshold_serves_the_larger_ones(ev):
    t, x, y, p = ev
    e = np.searchsorted(t, [(9 + m) * T0 for m in range(5)])
    win = [(t[a:b] - (9 + m) * T0, x[a:b], y[a:b], p[a:b]) for m, (a, b) in enumerate(zip(e[:-1], e[1:]))]
    lo = bc.fit_group(win[0], win[1:], 40, "affine", 50, W, H)
    hi = bc.fit_group(win[0], win[1:], 40, "affine", 400, W, H)
    n = len(hi["ids"])
    assert 0 < n < len(lo["ids"])
    assert np.array_equal(lo["ids"][:n], hi["ids"]) and np.array_equal(lo["maps"][:n], hi["maps"])
    assert np.array_equal(lo["claimed"][:n], hi["claimed"])
    assert list(lo["counts"]) == sorted(lo["counts"], reverse=True)
    again = bc.fit_group(win[0], win[1:], 40, "affine", 50, W, H)
    assert all(np.array_equal(lo[k], again[k]) for k in ("ids", "maps", "claimed", "n_in"))


def test_events_that_leave_the_sensor_are_dropped():
    a = synth.rigid_translation(width=W, height=H, n_points=300, c0=(250.0, 100.0), v=(300.0, 0.0), duration_s=1.2, seed=3)
    g = bc.evaluate_group(*_merge([a]), 3, 0, W, H, blocks=(40,), densities=(1 / 16,), models=("translation",))
    r = g["codec"]["B40_rho0.0625"]["models"]["translation"]
    assert r["n_rec"][0] > 0 and r["n_rec"][-1] < r["n_rec"][0] and r["claim_equals_match"]


def test_on_noise_alone_the_maps_add_almost_nothing_to_the_repeated_key_events():
    # Uniform noise pairs by chance on the working grid, and a search over displacements finds a few
    # more chance pairs. Neither amounts to a gain over the cheapest subset scheme.
    t, x, y, p = _merge([], noise_per_px_window=0.1, seed=11)
    g = bc.evaluate_group(t, x, y, p, 9, 0, W, H, blocks=(40,), densities=(1 / 16,), models=("static", "translation"))
    st, tr = (bc.summarize(g, "B40_rho0.0625", m, "Q", 11) for m in ("static", "translation"))
    assert st["F"] < 0.2 and 0.0 <= tr["F"] - st["F"] < 0.06
    assert st["gain"] < 1.0 and tr["gain"] < 1.0
    assert all(bc.summarize(g, "B40_rho0.0625", m, "Q", 4)["gain"] < 1.0 for m in ("static", "translation"))
    assert g["codec"]["B40_rho0.0625"]["models"]["translation"]["claim_equals_match"]


def test_groups_add_up(ev, group):
    other = bc.evaluate_group(*ev, 20, 9, W, H, blocks=(40, 80), grid_for=(40, 1 / 16))
    both = bc.sum_groups([group, other])
    assert both["w"] == [9, 20] and both["n_true"][0] == group["n_true"][0] + other["n_true"][0]
    a, b, c = (bc.summarize(g, "B40_rho0.0625", "affine", "Q", 4) for g in (group, other, both))
    assert min(a["F"], b["F"]) <= c["F"] <= max(a["F"], b["F"])
    assert min(a["bits"], b["bits"]) <= c["bits"] <= max(a["bits"], b["bits"])
    row = both["codec"]["B40_rho0.0625"]
    assert row["theta"] == 100 and row["models"]["affine"]["claim_equals_match"] is True
    assert row["n_key"] == group["codec"]["B40_rho0.0625"]["n_key"] + other["codec"]["B40_rho0.0625"]["n_key"]


def test_a_complete_stream_gives_the_receiver_the_numbers_of_the_sender(ev):
    cfg, B, rho = "B40_rho0.0625", 40, 1 / 16
    gs, w_prev = [], 0
    for w in (9, 20):
        gs.append(bc.evaluate_group(*ev, w, w_prev, W, H, blocks=(B,), densities=(rho,), records_for=(B, rho)))
        w_prev = w
    for model in bc.MODELS:
        for coder in bc.CODERS:
            for K in (4, 11):
                name = f"{model}_{coder}_K{K}"
                stream = bc.encode_header(coder, model, K, W, H, B) + b"".join(g["records"][name] for g in gs)
                assert len(stream) == 28 + sum(g["codec"][cfg]["models"][model]["bytes"][f"{coder}_K{K}"] for g in gs)
                rows = bc.evaluate_stream(stream, *ev)
                assert [r["w"] for r in rows] == [9, 20]
                for r, g in zip(rows, gs):
                    row = g["codec"][cfg]
                    assert r["n_true"] == g["n_true"][:K]
                    assert r["n_rec"] == [row["n_key"]] + row["models"][model]["n_rec"][:K - 1]
                    assert r["match"] == [row["n_key"]] + row["models"][model]["match_s2_k3"][:K - 1]
    assert "records" not in bc.sum_groups(gs)


def test_an_empty_key_window_is_a_valid_group():
    t, x, y, p = _merge([], noise_per_px_window=0.001, seed=5)
    g = bc.evaluate_group(t, x, y, p, 9, 0, W, H, blocks=(40,), densities=(1 / 2,))
    row = g["codec"]["B40_rho0.5"]
    assert row["n_active"] == 0 and row["n_key"] == 0
    assert bc.summarize(g, "B40_rho0.5", "affine", "T", 4)["F"] == 0.0
