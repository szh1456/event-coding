"""A faster implementation of ``ec.blockcodec``, meant to give the same results. Not normative.

``ec.blockcodec`` is the reference and is not changed. This module runs the reference code of
``evaluate_group``, ``fit_group``, ``decode_stream`` and ``evaluate_stream`` (their own bytecode,
rebound by ``_rebind``) with five helpers replaced:

- ``score`` of the fit: one numba pass that moves the key events of a block, indexes them on the
  grid and counts the pairs with the unclaimed true events. The reference does this with
  ``move``, ``Residual._index`` and ``np.unique`` on every one of several million calls. The
  floating-point operations are those of ``move``, in the same order, without fast-math, and the
  pair count is ``sum_v min(c_v, R_v)`` either way.
- ``reconstruct``: the map of each event taken from its block by index, not by one mask per block.
- ``encode_events_T`` / ``decode_events_T``: the U2 representation of the vendored transport with the
  ULEB128 of the time deltas done on arrays (``blockcodec.uleb_encode`` / ``uleb_decode``, which
  are canonical), in place of one Python call per event. The other fields are the vendored code's.
- ``evaluate_streams``: several streams of one recording scored together, so that the counts of a
  true window are built once for all streams that hold it.

Use. Unit tests (``tests/test_blockcodec_fast.py``) compare every output with the reference on
synthetic events. Directive 007, Section 6, admits a faster implementation only if it reproduces
the reference on every Stage 0 group in every field. That check has not been run, and running it
needs a directive. Until then no result of this project is computed with this module.
"""
from __future__ import annotations

import math
import types
from math import ceil

import numpy as np
from numba import njit

from . import blockcodec as bc
from .baseline import RepresentationMode, pack_array, unpack_array
from sim import representations as _rp  # noqa: E402  (on sys.path through ec.baseline)
from sim.workload import T_MAX_US

__all__ = ["evaluate_group", "fit_group", "decode_stream", "reconstruct", "evaluate_stream", "evaluate_streams",
           "encode_group", "encode_events_T", "decode_events_T"]


# ----------------------------------------------------------------------------------------------
# the score of a map

@njit(cache=True, nogil=True)
def _matched(sx, sy, tb, sp, cx, cy, q0, q1, a2, a3, a4, a5, s, k, use_tb, nx, ny, width, height, R, scratch):
    """``Residual.matched(*move(sx, sy, (cx, cy, h), q), tb, sp, (s, k))`` with ``a_i = q_i / h``.

    ``scratch`` is zero on entry and on return.
    """
    n = sx.shape[0]
    idx = np.empty(n, dtype=np.int64)
    m = 0
    for i in range(n):
        xf = np.float64(sx[i])
        yf = np.float64(sy[i])
        u = xf - cx
        v = yf - cy
        ix = np.int64(np.rint(xf + q0 + a2 * u + a3 * v))
        iy = np.int64(np.rint(yf + q1 + a4 * u + a5 * v))
        if ix < 0 or ix >= width or iy < 0 or iy >= height:
            continue
        tbk = tb[i] if use_tb else 0
        idx[m] = ((sp[i] * k + tbk) * ny + iy // s) * nx + ix // s
        m += 1
    got = 0
    for i in range(m):
        j = idx[i]
        scratch[j] += 1
        if scratch[j] <= R[j]:
            got += 1
    for i in range(m):
        scratch[idx[i]] = 0
    return got


class _Scorer:
    """``score(q, cell)`` of ``fit_group`` for one block and one residual."""

    def __init__(self, res, scratch):
        self.res, self.scratch = res, scratch

    def bind(self, sx, sy, tb, sp, frame):
        res, scratch = self.res, self.scratch
        cx, cy, h = frame
        W, H = res.width, res.height
        grids = {cell: (cell[0], cell[1], cell[1] == bc.OBJECTIVE[1], nx, ny, R, scratch[cell])
                 for cell, (nx, ny, R) in res.g.items()}

        def score(q, cell):
            s, k, use_tb, nx, ny, R, scr = grids[cell]
            return int(_matched(sx, sy, tb, sp, cx, cy, float(q[0]), float(q[1]), q[2] / h, q[3] / h, q[4] / h,
                                q[5] / h, s, k, use_tb, nx, ny, W, H, R, scr))
        return score


def fit_group(key, truths, B: int, model: str, theta_min: int, width: int, height: int, T0_us: int = bc.T0_US) -> dict:
    """``ec.blockcodec.fit_group``, with the score of a map computed by ``_matched``."""
    kt, kx, ky, kp = (np.asarray(a, dtype=np.int64) for a in key)
    bid = bc.block_ids(kx, ky, B, width)
    ids, counts = np.unique(bid, return_counts=True)
    ids, counts = ids[counts >= theta_min], counts[counts >= theta_min]
    order = np.lexsort((ids, -counts))
    ids, counts = ids[order], counts[order]
    n_t = len(truths)
    maps = np.zeros((len(ids), n_t, 6), dtype=np.int64)
    claimed = np.zeros((len(ids), n_t), dtype=np.int64)
    n_in = np.zeros((len(ids), n_t), dtype=np.int64)
    ev = []
    for b in ids:
        sel = bid == b
        ev.append((kx[sel], ky[sel], bc.time_bin(kt[sel], bc.OBJECTIVE[1], T0_us), kp[sel],
                   bc.block_frame(int(b), B, width)))
    n_eval = 0
    scratch = None
    for m in range(1, n_t + 1):
        res = bc.Residual(*truths[m - 1], width, height, T0_us)
        if scratch is None:
            scratch = {cell: np.zeros_like(R) for cell, (_, _, R) in res.g.items()}
        scorer = _Scorer(res, scratch)
        for j, (sx, sy, tb, sp, frame) in enumerate(ev):
            raw = scorer.bind(sx, sy, tb, sp, frame)

            def score(q, cell):
                nonlocal n_eval
                n_eval += 1
                return raw(q, cell)

            q = (0, 0, 0, 0, 0, 0)
            if model != "static":
                if m == 1:
                    d0, R = (0.0, 0.0), bc.RADIUS_FIRST
                else:
                    r = m / (m - 1.0)
                    d0 = (r * maps[j, m - 2, 0], r * maps[j, m - 2, 1])
                    R = max(3, int(math.ceil(0.3 * math.hypot(*d0))))
                d = bc.search_translation(score, d0, R)
                q = d + (0, 0, 0, 0)
                if model == "affine":
                    prev = tuple(int(v) for v in maps[j, m - 2, 2:]) if m > 1 else None
                    q = bc.search_shape(score, d, prev, m / (m - 1.0) if m > 1 else 1.0, B)
            maps[j, m - 1] = q
            claimed[j, m - 1], n_in[j, m - 1] = res.claim(*bc.move(sx, sy, frame, q), tb, sp)
    return {"ids": ids, "counts": counts, "maps": maps, "claimed": claimed, "n_in": n_in, "n_eval": n_eval}


# ----------------------------------------------------------------------------------------------
# the receiver

def reconstruct(h: dict, group: dict, m: int):
    """``ec.blockcodec.reconstruct``: the map of each event looked up by its block."""
    kt, kx, ky, kp = group["key"]
    t = h["origin_us"] + (group["w"] + m) * h["T0_us"] + kt
    if m == 0:
        return t, kx, ky, kp
    B, width = h["B"], h["width"]
    bid = group["bid"]
    q = group["maps"][np.searchsorted(group["ids"], bid), m - 1]
    nbx = -(-width // B)
    cx = (bid % nbx) * B + (B - 1) / 2.0
    cy = (bid // nbx) * B + (B - 1) / 2.0
    hh = B / 2.0
    xf, yf = np.asarray(kx, dtype=np.float64), np.asarray(ky, dtype=np.float64)
    u, v = xf - cx, yf - cy
    ix = np.rint(xf + q[:, 0] + (q[:, 2] / hh) * u + (q[:, 3] / hh) * v).astype(np.asarray(kx).dtype)
    iy = np.rint(yf + q[:, 1] + (q[:, 4] / hh) * u + (q[:, 5] / hh) * v).astype(np.asarray(ky).dtype)
    keep = (ix >= 0) & (ix < width) & (iy >= 0) & (iy < h["height"])
    return t[keep], ix[keep], iy[keep], kp[keep]


# ----------------------------------------------------------------------------------------------
# coder T

def _encode_u2(blob: bytes) -> bytes:
    """``sim.representations._encode_u2`` with the deltas through ``bc.uleb_encode``."""
    t, x, y, p = _rp._unpack_checked(blob)
    n = int(t.size)
    if n == 0:
        return b""
    if n > _rp.U2_MAX_EVENTS:
        raise _rp.RepresentationError(f"U2 count field is {_rp.U2_COUNT_BITS} bits, so N must be at most "
                                      f"{_rp.U2_MAX_EVENTS}, got {n}")
    out = bytearray(n.to_bytes(_rp.U2_COUNT_BITS // 8, "big"))
    addr = np.concatenate((_rp._bits_msb_first(x, _rp.X_BITS), _rp._bits_msb_first(y, _rp.Y_BITS),
                           _rp._bits_msb_first(p, _rp.POL_BITS)))
    out += np.packbits(addr).tobytes()
    out += int(t[0]).to_bytes(_rp.U2_T0_BITS // 8, "big")
    if n > 1:
        d = np.diff(np.asarray(t, dtype=np.int64))
        if d.min() < 0:
            raise _rp.RepresentationError("ULEB128 is unsigned")
        out += bc.uleb_encode(d)
    return bytes(out)


def _decode_u2(payload: bytes) -> bytes:
    """``sim.representations._decode_u2`` with the deltas through ``bc.uleb_decode``."""
    if len(payload) == 0:
        return b""
    n_count, n_t0 = _rp.U2_COUNT_BITS // 8, _rp.U2_T0_BITS // 8
    if len(payload) < n_count:
        raise _rp.RepresentationError("U2 payload shorter than the count field")
    n = int.from_bytes(payload[:n_count], "big")
    if n == 0:
        raise _rp.RepresentationError("U2 count of zero")
    addr_bytes = ceil(_rp.U2_ADDR_BITS * n / 8)
    if len(payload) < n_count + addr_bytes + n_t0:
        raise _rp.RepresentationError("U2 payload truncated")
    bits = np.unpackbits(np.frombuffer(payload[n_count:n_count + addr_bytes], dtype=np.uint8))
    used = _rp.U2_ADDR_BITS * n
    if np.any(bits[used:]):
        raise _rp.RepresentationError("U2 address block has a nonzero padding bit")
    o1, o2 = _rp.X_BITS * n, (_rp.X_BITS + _rp.Y_BITS) * n
    x = _rp._from_bits_msb_first(bits[:o1], n, _rp.X_BITS)
    y = _rp._from_bits_msb_first(bits[o1:o2], n, _rp.Y_BITS)
    p = _rp._from_bits_msb_first(bits[o2:used], n, _rp.POL_BITS)
    pos = n_count + addr_bytes
    t0 = int.from_bytes(payload[pos:pos + n_t0], "big")
    pos += n_t0
    if t0 > T_MAX_US:
        raise _rp.RepresentationError("U2 first timestamp out of range")
    d, end = bc.uleb_decode(payload, n - 1, pos) if n > 1 else (np.zeros(0, dtype=np.int64), pos)
    if end != len(payload):
        raise _rp.RepresentationError("U2 payload has trailing bytes")
    raw = np.frombuffer(payload, dtype=np.uint8)[pos:end]
    lens = np.diff(np.concatenate(([-1], np.flatnonzero(raw < 128))))
    if lens.size and (lens.max() > _rp.U2_MAX_DELTA_LEB_BYTES or np.any((raw[np.cumsum(lens) - 1] == 0) & (lens > 1))):
        raise _rp.RepresentationError("U2 delta: overlong or non-canonical ULEB128")
    t = np.empty(n, dtype=np.int64)
    t[0] = t0
    t[1:] = t0 + np.cumsum(d)
    if t[-1] > T_MAX_US:
        raise _rp.RepresentationError("U2 timestamp reconstruction overflows")
    return pack_array(t, x, y, p, presorted=True)


def encode_events_T(t_rel, x, y, p) -> bytes:
    """``ec.blockcodec.encode_events_T``."""
    if len(t_rel) == 0:
        return b""
    return bc._zstd(_encode_u2(pack_array(t_rel, x, y, p)), 1)


def decode_events_T(buf: bytes):
    """``ec.blockcodec.decode_events_T``."""
    if len(buf) == 0:
        z = np.zeros(0, dtype=np.int64)
        return z, z.copy(), z.copy(), z.copy()
    t, x, y, p = unpack_array(_decode_u2(bc._unzstd(buf)))
    return t.astype(np.int64), x.astype(np.int64), y.astype(np.int64), p.astype(np.int64)


# ----------------------------------------------------------------------------------------------
# the reference functions, rebound to the helpers above

def _rebind(fn, **names):
    g = dict(bc.__dict__)
    g.update(names)
    out = types.FunctionType(fn.__code__, g, fn.__name__, fn.__defaults__, fn.__closure__)
    out.__kwdefaults__ = fn.__kwdefaults__
    out.__doc__ = fn.__doc__
    return out


decode_stream = _rebind(bc.decode_stream, decode_events_T=decode_events_T)
evaluate_stream = _rebind(bc.evaluate_stream, decode_stream=decode_stream, reconstruct=reconstruct)
encode_group = _rebind(bc.encode_group, encode_events_T=encode_events_T)
evaluate_group = _rebind(bc.evaluate_group, fit_group=fit_group, reconstruct=reconstruct, decode_stream=decode_stream,
                         encode_group=encode_group, encode_events_T=encode_events_T)


def evaluate_streams(bufs, t_us, x, y, p, cell=bc.OBJECTIVE) -> list:
    """``[ec.blockcodec.evaluate_stream(b, t_us, x, y, p, cell) for b in bufs]``, for streams of one recording.

    The counts of each true window are built once and shared by the streams that hold it.
    """
    t_us = np.asarray(t_us, dtype=np.int64)
    dec = [decode_stream(b) for b in bufs]
    outs = [[None] * len(groups) for _, groups in dec]
    by_w = {}
    for i, (h, groups) in enumerate(dec):
        for j, g in enumerate(groups):
            by_w.setdefault((h["origin_us"], h["T0_us"], int(g["w"])), []).append((i, j))
    truths = {}
    for (origin, T0, w) in sorted(by_w, key=lambda k: (k[0] + k[2] * k[1], k)):
        for key in [k for k in truths if k[0] < origin + w * T0]:      # windows that start before this group
            del truths[key]
        for i, j in by_w[(origin, T0, w)]:
            h, g = dec[i][0], dec[i][1][j]
            row = {"w": int(g["w"]), "n_rec": [], "n_true": [], "match": []}
            for m in range(h["K"]):
                w0 = origin + (w + m) * T0
                if (w0, T0) not in truths:
                    a, b = np.searchsorted(t_us, (w0, w0 + T0))
                    truths[(w0, T0)] = (int(b - a), bc.Truth(t_us[a:b], x[a:b], y[a:b], p[a:b], w0, T0))
                n_true, tr = truths[(w0, T0)]
                rec = reconstruct(h, g, m)
                row["n_rec"].append(int(len(rec[0])))
                row["n_true"].append(n_true)
                row["match"].append(tr.match(*rec, cell))
            outs[i][j] = row
    return outs
