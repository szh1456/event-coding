"""``ec.blockcodec_fast`` against the reference ``ec.blockcodec``, on synthetic events only.

Every output is compared for exact equality: maps, counts, byte lengths, records and matches. The
gate of directive 007 runs unchanged against the fast implementation in ``test_blockcodec_fast_gate.py``.
"""
import numpy as np
import pytest

from ec import blockcodec as bc, blockcodec_fast as fast

W, H = 320, 240
T0 = bc.T0_US


def _equal(a, b, path="") -> list:
    if isinstance(a, dict):
        if not isinstance(b, dict) or set(a) != set(b):
            return [f"{path}: keys {sorted(a) if isinstance(a, dict) else a} != {sorted(b) if isinstance(b, dict) else b}"]
        return [d for k in a for d in _equal(a[k], b[k], f"{path}/{k}")]
    if isinstance(a, (list, tuple)):
        if not isinstance(b, (list, tuple)) or len(a) != len(b):
            return [f"{path}: length"]
        return [d for i, (u, v) in enumerate(zip(a, b)) for d in _equal(u, v, f"{path}[{i}]")]
    if isinstance(a, np.ndarray) or isinstance(b, np.ndarray):
        a, b = np.asarray(a), np.asarray(b)
        return [] if a.shape == b.shape and a.dtype == b.dtype and np.array_equal(a, b) else [f"{path}: array"]
    return [] if type(a) is type(b) and a == b else [f"{path}: {a!r} != {b!r}"]


def _scene(seed=0, n_layers=3, noise=0.02, duration_s=0.8, rate=25_000):
    """Textured layers under translation and scaling, plus uniform noise, in sorted time order."""
    rng = np.random.default_rng(seed)
    n = int(rate * duration_s * 1e6 / T0)
    t = np.sort(rng.integers(0, int(duration_s * 1e6), n))
    layer = rng.integers(0, n_layers, n)
    k = rng.integers(0, 3000, n)
    px, py = rng.uniform(-60, W + 60, (n_layers, 3000)), rng.uniform(-60, H + 60, (n_layers, 3000))
    v = rng.uniform(-400, 400, (n_layers, 2)) * 1e-6
    sc = 1 + rng.uniform(-0.4, 0.4, n_layers)[layer] * 1e-6 * t
    cx, cy = W / 2, H / 2
    x = cx + (px[layer, k] - cx) * sc + v[layer, 0] * t + rng.normal(0, 0.6, n)
    y = cy + (py[layer, k] - cy) * sc + v[layer, 1] * t + rng.normal(0, 0.6, n)
    z = rng.random(n) < noise
    x[z], y[z] = rng.uniform(0, W, z.sum()), rng.uniform(0, H, z.sum())
    x, y = np.floor(x).astype(np.int64), np.floor(y).astype(np.int64)
    keep = (x >= 0) & (x < W) & (y >= 0) & (y < H)
    return t[keep].astype(np.int64), x[keep], y[keep], rng.integers(0, 2, n)[keep].astype(np.int64)


@pytest.fixture(scope="module")
def ev():
    return _scene()


def test_the_score_kernel_equals_move_and_matched():
    rng = np.random.default_rng(1)
    t, x, y, p = _scene(seed=2, duration_s=0.1)
    res = bc.Residual(t[t < T0], x[t < T0], y[t < T0], p[t < T0], W, H)
    scratch = {c: np.zeros_like(R) for c, (_, _, R) in res.g.items()}
    for B in (20, 40, 80):
        for _ in range(60):
            b = int(rng.integers(0, (W // B) * (H // B)))
            frame = bc.block_frame(b, B, W)
            n = int(rng.integers(0, 300))
            sx = (b % (W // B)) * B + rng.integers(0, B, n)
            sy = (b // (W // B)) * B + rng.integers(0, B, n)
            tb, sp = rng.integers(0, 3, n), rng.integers(0, 2, n)
            score = fast._Scorer(res, scratch).bind(sx, sy, tb, sp, frame)
            for _ in range(20):
                q = tuple(int(v) for v in rng.integers(-40, 41, 2)) + tuple(int(v) for v in rng.integers(-B, B + 1, 4))
                for cell in bc.STAGE_CELLS:
                    ref = res.matched(*bc.move(sx, sy, frame, q), tb, sp, cell)
                    assert score(q, cell) == ref
            assert all(not s.any() for s in scratch.values())


def test_coder_T_bytes_and_events_equal_the_vendored_transport(ev):
    t, x, y, p = ev
    for a, b in ((0, 0), (0, 1), (0, 2), (100, 5000), (0, int(np.searchsorted(t, 250_000)))):
        w = (t[a:b] - t[a] if b > a else t[a:b], x[a:b], y[a:b], p[a:b])
        buf = bc.encode_events_T(*w)
        assert fast.encode_events_T(*w) == buf
        assert not _equal(list(fast.decode_events_T(buf)), list(bc.decode_events_T(buf)))
    w = (np.array([0, 1, 200, 70_000, 262_143]), np.array([1, 2, 3, 4, 5]), np.array([5, 4, 3, 2, 1]), np.array([0, 1, 0, 1, 1]))
    buf = bc.encode_events_T(*w)
    assert fast.encode_events_T(*w) == buf and not _equal(list(fast.decode_events_T(buf)), list(bc.decode_events_T(buf)))


@pytest.mark.parametrize("blocks,grid_for,records_for,w,w_prev", [((20, 40, 80), (40, 1 / 16), (20, 1.0), 3, 0),
                                                                    ((20,), None, None, 10, 3)])
def test_evaluate_group_equals_the_reference(ev, blocks, grid_for, records_for, w, w_prev):
    ref = bc.evaluate_group(*ev, w, w_prev, W, H, blocks=blocks, grid_for=grid_for, records_for=records_for)
    out = fast.evaluate_group(*ev, w, w_prev, W, H, blocks=blocks, grid_for=grid_for, records_for=records_for)
    assert not _equal(ref, out)


def test_fit_group_equals_the_reference_on_dense_noise_and_large_motion():
    t, x, y, p = _scene(seed=5, n_layers=2, noise=0.3, rate=40_000, duration_s=0.25)
    edges = np.searchsorted(t, [m * T0 for m in range(6)])
    win = [(t[a:b] - m * T0, x[a:b], y[a:b], p[a:b]) for m, (a, b) in enumerate(zip(edges[:-1], edges[1:]))]
    for B in (20, 80):
        for model in bc.MODELS:
            ref = bc.fit_group(win[0], win[1:], B, model, 1, W, H)
            assert not _equal(ref, fast.fit_group(win[0], win[1:], B, model, 1, W, H))


def _streams(ev, ws):
    """The eight streams of ``static`` and ``affine`` at (20, 1/4), from one evaluation per group."""
    recs, prev = [], 0
    for w in ws:
        recs.append(bc.evaluate_group(*ev, w, prev, W, H, blocks=(20,), densities=(1 / 4,), models=("static", "affine"),
                                      records_for=(20, 1 / 4))["records"])
        prev = w
    return [bc.encode_header(coder, model, K, W, H, 20) + b"".join(r[f"{model}_{coder}_K{K}"] for r in recs)
            for model in ("affine", "static") for coder in bc.CODERS for K in (4, 11)]


def test_streams_decode_and_score_as_the_reference(ev):
    bufs = _streams(ev, (0, 4, 6, 13))          # overlapping groups
    ref = [bc.evaluate_stream(b, *ev) for b in bufs]
    for b, r in zip(bufs, ref):
        assert not _equal(r, fast.evaluate_stream(b, *ev))
        h, groups = bc.decode_stream(b)
        hf, gf = fast.decode_stream(b)
        assert h == hf and not _equal(groups, gf)
        for g in groups:
            for m in range(h["K"]):
                assert not _equal(list(bc.reconstruct(h, g, m)), list(fast.reconstruct(h, g, m)))
    assert not _equal(ref, fast.evaluate_streams(bufs, *ev))
    assert not _equal([bc.evaluate_stream(b, *ev, cell=(4, 1)) for b in bufs], fast.evaluate_streams(bufs, *ev, cell=(4, 1)))
