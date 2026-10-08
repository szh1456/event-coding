"""The transport baseline of the companion project, and generic layouts next to it.

``payload_bits`` reproduces ``sim.scene_bandwidth.payload.payload_bits`` of
szh1456/scene-bandwidth: canonical AER40 records -> U2 (bit-packed 22-bit
addresses, ULEB128 time deltas) -> zstd level 1, one payload per tile. The three
modules it needs (``sim.workload``, ``sim.representations``, ``sim.etram``) are
verbatim copies under ``vendor/scene_bandwidth``; see ``SOURCE.json`` there.
"""
from __future__ import annotations

import lzma
import pathlib
import sys

import numpy as np

_VENDOR = pathlib.Path(__file__).resolve().parent.parent / "vendor" / "scene_bandwidth"
if str(_VENDOR) not in sys.path:
    sys.path.insert(0, str(_VENDOR))

from sim.etram import ETRAM_HEIGHT, ETRAM_WIDTH, probe, read_events  # noqa: E402,F401
from sim.representations import (RepresentationMode, decode_representation,  # noqa: E402,F401
                                 encode_representation)
from sim.workload import RECORD_BITS, T_MAX_US, pack_array, unpack_array  # noqa: E402,F401

ZSTD_LEVEL = 1
TILE_US = 50_000          # payload tile of the companion project (directive 004 there)


def _zstd1(buf: bytes) -> bytes:
    import zstandard
    return zstandard.ZstdCompressor(level=ZSTD_LEVEL).compress(buf)


def payload_bits(t_rel_us, x, y, p) -> int:
    """U2 + zstd-1 size in bits of one tile. ``t_rel_us`` is relative to the tile start."""
    if len(t_rel_us) == 0:
        return 0
    canonical = pack_array(t_rel_us, x, y, p)
    return 8 * len(_zstd1(encode_representation(canonical, RepresentationMode.AER40_SOA_DT)))


def byte_planes(t_rel_us, x, y, p) -> bytes:
    """Same events as U2, fields split into byte planes, polarity bit-packed. Order (t, x, y)."""
    t = np.asarray(t_rel_us, dtype=np.int64)
    x = np.asarray(x, dtype=np.int64)
    y = np.asarray(y, dtype=np.int64)
    p = np.asarray(p, dtype=np.int64)
    o = np.lexsort((y, x, t))
    t, x, y, p = t[o], x[o], y[o], p[o]
    dt = np.diff(t, prepend=0).astype("<u4")
    return (dt.view(np.uint8).reshape(-1, 4).T.tobytes()
            + x.astype("<u2").view(np.uint8).reshape(-1, 2).T.tobytes()
            + y.astype("<u2").view(np.uint8).reshape(-1, 2).T.tobytes()
            + np.packbits(p.astype(np.uint8)).tobytes())


def tile_edges(t_us: np.ndarray, t0_us: int, tile_us: int = TILE_US):
    """Start and end indices of the non-empty tiles of a nondecreasing timestamp array."""
    w = (np.asarray(t_us, dtype=np.int64) - int(t0_us)) // tile_us
    cut = np.flatnonzero(np.diff(w)) + 1
    starts = np.concatenate(([0], cut))
    ends = np.concatenate((cut, [len(w)]))
    return starts, ends, w[starts]


def tiled_sizes(t_us, x, y, p, t0_us: int, tile_us: int = TILE_US, with_xz: bool = True) -> dict:
    """Total bits over all tiles for the baseline and the generic variants."""
    t_us = np.asarray(t_us, dtype=np.int64)
    out = {"n_events": int(len(t_us)), "n_tiles": 0, "u2_raw": 0, "u2_zstd1": 0, "planes_zstd1": 0}
    if with_xz:
        out.update({"u2_xz": 0, "planes_xz": 0})
    if len(t_us) == 0:
        return out
    starts, ends, widx = tile_edges(t_us, t0_us, tile_us)
    out["n_tiles"] = int(len(starts))
    for s, e, k in zip(starts, ends, widx):
        tr = t_us[s:e] - (int(t0_us) + int(k) * tile_us)
        canonical = pack_array(tr, x[s:e], y[s:e], p[s:e])
        u2 = encode_representation(canonical, RepresentationMode.AER40_SOA_DT)
        planes = byte_planes(tr, x[s:e], y[s:e], p[s:e])
        out["u2_raw"] += 8 * len(u2)
        out["u2_zstd1"] += 8 * len(_zstd1(u2))
        out["planes_zstd1"] += 8 * len(_zstd1(planes))
        if with_xz:
            out["u2_xz"] += 8 * len(lzma.compress(u2, preset=9 | lzma.PRESET_EXTREME))
            out["planes_xz"] += 8 * len(lzma.compress(planes, preset=9 | lzma.PRESET_EXTREME))
    return out
