import lzma

import numpy as np
import pytest

from ec import baseline as B

zstandard = pytest.importorskip("zstandard")


def _events(n=5000, seed=0, span_us=200_000):
    rng = np.random.default_rng(seed)
    t = np.sort(rng.integers(0, span_us, n)).astype(np.int64)
    return t, rng.integers(0, 1280, n), rng.integers(0, 720, n), rng.integers(0, 2, n)


def test_u2_is_a_bijection_on_canonical_blobs():
    t, x, y, p = _events(3000, span_us=40_000)
    blob = B.pack_array(t, x, y, p)
    u2 = B.encode_representation(blob, B.RepresentationMode.AER40_SOA_DT)
    assert B.decode_representation(u2, B.RepresentationMode.AER40_SOA_DT) == blob
    assert B.RECORD_BITS == 40


def test_payload_bits_is_u2_then_zstd_level_1():
    t, x, y, p = _events(2000, span_us=45_000)
    u2 = B.encode_representation(B.pack_array(t, x, y, p), B.RepresentationMode.AER40_SOA_DT)
    assert B.payload_bits(t, x, y, p) == 8 * len(zstandard.ZstdCompressor(level=1).compress(u2))
    assert B.payload_bits(t[:0], x[:0], y[:0], p[:0]) == 0


def test_tiled_sizes_sum_the_tiles_and_skip_empty_ones():
    t, x, y, p = _events(6000, span_us=200_000)
    t = t + 1_000_000
    keep = (t < 1_050_000) | (t >= 1_100_000)          # leave tile 1 empty
    t, x, y, p = t[keep], x[keep], y[keep], p[keep]
    out = B.tiled_sizes(t, x, y, p, t0_us=1_000_000)
    assert out["n_tiles"] == 3 and out["n_events"] == len(t)
    total = 0
    for k in (0, 2, 3):
        m = (t >= 1_000_000 + k * 50_000) & (t < 1_000_000 + (k + 1) * 50_000)
        total += B.payload_bits(t[m] - (1_000_000 + k * 50_000), x[m], y[m], p[m])
    assert out["u2_zstd1"] == total
    assert out["u2_raw"] > 0 and out["planes_zstd1"] > 0 and out["planes_xz"] > 0 and out["u2_xz"] > 0


def test_byte_planes_hold_every_field():
    t, x, y, p = _events(1000, span_us=40_000)
    planes = B.byte_planes(t, x, y, p)
    n = len(t)
    assert len(planes) == 4 * n + 2 * n + 2 * n + (n + 7) // 8
    o = np.lexsort((y, x, t))
    dt = np.frombuffer(planes[:4 * n], dtype=np.uint8).reshape(4, n).T.copy().view("<u4").ravel()
    assert np.array_equal(np.cumsum(dt), t[o])
    assert len(lzma.compress(planes)) < len(planes)
