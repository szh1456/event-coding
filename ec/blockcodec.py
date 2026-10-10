"""Regeneration on a fixed block grid, with a complete bitstream (directive 007). Reference implementation.

Question. Directives 002 to 005 regenerated the events of annotated objects. A sender has no
annotation. It cuts the sensor into square blocks, sends the events of the active blocks of a key
window, and for each later window of the group one map per block. What does the receiver get for
the bytes that are actually written, over the complete windows, against sending fewer events?

Windows and groups. Window ``w`` of a recording is ``[w T0, (w + 1) T0)`` with ``T0`` = 33,333 us.
A group keyed at window ``w`` is the key window ``w`` (``m`` = 0) and the targets ``m`` = 1 ..
``K - 1``, the windows ``w + m``.

Regions. The sensor is cut into blocks of ``B x B`` pixels, aligned to the origin and numbered in
raster order. A block is active when it holds at least ``theta = max(1, ceil(rho B^2))`` events of
the key window. Each active block is one template region. The regions stay fixed within the group.

Sender. It transmits the key events, which are the events of the key window in the active blocks,
and for every target and every active block one map with integer parameters
``q = (dx, dy, ia, ib, ic, id)``. With ``(cx, cy)`` the center of the block and ``h = B / 2``, a
key event at ``(x, y)`` is moved to the pixel nearest to

    x' = x + dx + (ia / h) (x - cx) + (ib / h) (y - cy)
    y' = y + dy + (ic / h) (x - cx) + (id / h) (y - cy)

and by ``m T0`` in time, with its polarity. This is the map of ``ec.affine`` with the block in
place of the bounding rectangle. A moved event may leave its block. One that leaves the sensor is
dropped. Every key event is moved once per target. Models: ``static`` (all parameters zero, no
map is sent), ``translation`` (``dx, dy``), ``affine`` (all six).

Fit. For target ``m`` the sender holds the true events of window ``w + m`` as counts on the working
grid, 2 px blocks and three time bins per window (OBJECTIVE). It visits the active blocks in the
order of decreasing key count, ties in raster order. For each block it chooses the map that
maximizes the number of moved events of the block that can be paired, inside a voxel of the
working grid, with true events that no earlier block has claimed, and then claims them. The sum of
the claims over the blocks is therefore the number of paired events of the whole reconstruction on
the working grid, which is what the fidelity counts. A block that is active under a larger
threshold comes earlier in the order, so one fit under the smallest threshold serves all of them.
The translation search is the coarse-to-fine search of ``ec.gop.aligned_displacement``: for ``m``
= 1 it starts at zero with half-width RADIUS_FIRST, and for ``m`` > 1 at the map of the previous
target scaled by ``m / (m - 1)`` with half-width ``max(3, ceil(0.3 |d0|))``. It returns a
displacement that pairs at least as many events as its starting point and as the zero
displacement. The first search reaches RADIUS_FIRST plus the refinements, 36 px per window. The
shape search is that of ``ec.affine.fit_affine`` (STAGES), with offsets above ``B / 10`` left out,
and returns a map that pairs at least as many events as the translation it starts from. So, on
the events that are unclaimed when a block is visited, ``affine`` >= ``translation`` >= ``static``
for that block. The search scores coarse steps on coarser grids (STAGE_CELLS), whose counts are
kept consistent with the claims.

Event coders. ``T``: the transport of the companion project, U2 and zstd level 1, with times in
microseconds (``ec.baseline.payload_bits`` is the size of this payload). ``Q``: events quantized
to a receiver grid of ``s`` px and ``k`` time bins per window, sorted, with the gaps between their
voxel indices as ULEB128 and zstd level 19. A receiver that counts events on the working grid
needs the direct stream at (2 px, 3 bins). The codec needs its key events at (1 px, 3 bins),
because a map moves them by whole pixels and keeps their time bin.

Bitstream. A stream is a header of 28 bytes (HEADER) and one record per group:

    ULEB128  key window index, as the difference to that of the previous record
    ULEB128  length of the key payload, then the payload (coder T or Q)
    ULEB128  length of the map payload, then the payload     (absent for the model static)

The decoder reads the block side, the group length, the model and the coder from the header. The
active blocks are the blocks that hold key events, so no list of regions is sent. The map payload
holds, for each active block in raster order and each parameter of the model, the values for
``m`` = 1 .. ``K - 1`` as first differences along ``m``, zigzag and ULEB128, behind one byte that
says whether zstd level 19 was applied (it is applied when that is shorter). ``decode_stream``
and ``reconstruct`` take the bytes and nothing else.

Baselines, on the same windows and with the same two coders: ``direct`` (every event); ``thin``
(a random subset with keep probability ``chi`` in THIN_SHARES); and ``select`` (in every window,
the events of the blocks that are active in that window, by the rule of the key window, with no
regeneration). A subset pairs each of its events, so with the share ``q = n_kept / n`` its fidelity
is ``2 q / (1 + q)`` on every grid. Two subset schemes can be mixed over windows, which mixes
their shares and their bits linearly, so the baseline at a share ``q`` is the lower convex envelope
of the measured points ``(q, bits)`` of ``thin``, ``select`` and ``direct`` and of the origin. The
segment from the origin to ``direct`` is the scheme that sends some windows completely and drops
the others. A random subset costs more bits per kept event than all events do, because its events
lie further apart. Whole windows and whole blocks do not. The envelope is therefore the baseline
that separates regeneration from the choice of windows and blocks. Thinning alone is reported
next to it, by linear interpolation between its measured points.

Fidelity. For window ``m`` the reconstruction and the true events of the complete sensor are
compared as in ``ec.regen.voxel_f1`` (class ``Truth``). With ``match`` the paired events and ``n_rec``, ``n_true`` the
two counts, a group of ``K`` windows has

    F_K    = 2 sum_m match / sum_m (n_rec + n_true),      m = 0 .. K - 1,
    bits_K = 8 x the length of the group's record,

and the key window enters with ``match = n_rec = n_key``. A subset reaches ``F_K`` with the share
``q_eq = F_K / (2 - F_K)``. The gain of the codec is the bits of the baseline at ``q_eq`` divided
by ``bits_K``.
"""
from __future__ import annotations

import math
import struct

import numpy as np
import zstandard

from . import regen
from .baseline import RepresentationMode, decode_representation, encode_representation, pack_array, unpack_array

T0_US = 33_333
N_TARGETS = 10
GROUPS = (2, 4, 8, 11)
OBJECTIVE = (2, 3)                         # the working grid: block px, time bins per window
STAGE_CELLS = (OBJECTIVE, (4, 1), (8, 1), (16, 1))
BLOCKS = (20, 40, 80)
DENSITIES = (1 / 16, 1 / 8, 1 / 4, 1 / 2, 1.0)      # rho, events per pixel in the key window
MODELS = ("static", "translation", "affine")
N_PARAMS = {"static": 0, "translation": 2, "affine": 6}
RADIUS_FIRST = 24
# (block px, time bins), offsets, largest number of rounds: the stages of ec.affine
STAGES = (((8, 1), (-2, 2, -4, 4, -8, 8), 2),
          ((4, 1), (-1, 1, -2, 2, -4, 4), 2),
          (OBJECTIVE, (-1, 1, -2, 2), 4))
THIN_SHARES = (0.75, 0.5, 0.35, 0.25, 0.125)
THIN_SEED = 20261012
CELLS_ALL = tuple((s, k) for s in regen.BLOCKS_PX for k in regen.TIME_BINS)
CELLS_MAIN = (OBJECTIVE, (2, 1))
Q_KEY = (1, 3)                             # receiver grid of the key events under coder Q
Q_DIRECT = OBJECTIVE                       # receiver grid of the direct and thinned streams under coder Q
MAGIC, VERSION = b"EC07", 1
HEADER = struct.Struct("<4sBBBBHHHBBIq")   # magic, version, coder, model, K, width, height, B, qs, qk, T0, origin
CODERS = ("T", "Q")


def threshold(B: int, rho: float) -> int:
    return max(1, int(math.ceil(rho * B * B)))


# ----------------------------------------------------------------------------------------------
# integers and event payloads

def uleb_encode(values) -> bytes:
    """ULEB128 of an array of non-negative integers below 2^63."""
    v = np.asarray(values, dtype=np.uint64).ravel()
    if v.size == 0:
        return b""
    nb = np.ones(v.size, dtype=np.int64)
    for j in range(1, 9):
        nb += (v >= (np.uint64(1) << np.uint64(7 * j))).astype(np.int64)
    end = np.cumsum(nb)
    start = end - nb
    out = np.zeros(int(end[-1]), dtype=np.uint8)
    for j in range(int(nb.max())):
        sel = nb > j
        byte = ((v[sel] >> np.uint64(7 * j)) & np.uint64(0x7F)).astype(np.uint8)
        byte |= (nb[sel] > j + 1).astype(np.uint8) << 7
        out[start[sel] + j] = byte
    return out.tobytes()


def uleb_decode(buf: bytes, count: int | None = None, pos: int = 0):
    """Decode ``count`` values from ``pos`` (all remaining ones if None). Returns ``values, next_pos``."""
    b = np.frombuffer(buf, dtype=np.uint8)[pos:]
    if count is not None:
        b = b[:10 * count]
    ends = np.flatnonzero(b < 128)
    if count is None:
        count = int(ends.size)
    if count == 0:
        return np.zeros(0, dtype=np.int64), pos
    if ends.size < count:
        raise ValueError("truncated ULEB128 data")
    ends = ends[:count]
    starts = np.concatenate(([0], ends[:-1] + 1))
    n = int(ends[-1]) + 1
    which = np.repeat(np.arange(count), ends - starts + 1)
    shift = (np.arange(n) - starts[which]).astype(np.uint64) * np.uint64(7)
    vals = np.add.reduceat((b[:n].astype(np.uint64) & np.uint64(0x7F)) << shift, starts)
    return vals.astype(np.int64), pos + n


def _zstd(buf: bytes, level: int) -> bytes:
    return zstandard.ZstdCompressor(level=level).compress(buf)


def _unzstd(buf: bytes) -> bytes:
    return zstandard.ZstdDecompressor().decompress(buf)


def encode_events_T(t_rel, x, y, p) -> bytes:
    """Coder T. ``t_rel`` is relative to the window start. The size is ``ec.baseline.payload_bits`` / 8."""
    if len(t_rel) == 0:
        return b""
    return _zstd(encode_representation(pack_array(t_rel, x, y, p), RepresentationMode.AER40_SOA_DT), 1)


def decode_events_T(buf: bytes):
    if len(buf) == 0:
        z = np.zeros(0, dtype=np.int64)
        return z, z.copy(), z.copy(), z.copy()
    t, x, y, p = unpack_array(decode_representation(_unzstd(buf), RepresentationMode.AER40_SOA_DT))
    return t.astype(np.int64), x.astype(np.int64), y.astype(np.int64), p.astype(np.int64)


def time_bin(t_rel, k: int, T0_us: int = T0_US):
    return np.minimum(k - 1, (np.asarray(t_rel, dtype=np.int64) * k) // int(T0_us))


def encode_events_Q(t_rel, x, y, p, cell, width: int, height: int, T0_us: int = T0_US) -> bytes:
    """Coder Q on the receiver grid ``cell`` = (block px, time bins)."""
    s, k = cell
    if len(t_rel) == 0:
        return b""
    nx, ny = -(-width // s), -(-height // s)
    L = ((time_bin(t_rel, k, T0_us) * 2 + np.asarray(p, dtype=np.int64)) * ny
         + np.asarray(y, dtype=np.int64) // s) * nx + np.asarray(x, dtype=np.int64) // s
    L = np.sort(L)
    return _zstd(uleb_encode(np.concatenate(([len(L)], np.diff(L, prepend=0)))), 19)


def decode_events_Q(buf: bytes, cell, width: int, height: int, T0_us: int = T0_US):
    """Events at the origin of their voxel: the first pixel of the block and the first instant of the bin."""
    s, k = cell
    if len(buf) == 0:
        z = np.zeros(0, dtype=np.int64)
        return z, z.copy(), z.copy(), z.copy()
    v, _ = uleb_decode(_unzstd(buf))
    if v[0] != len(v) - 1:
        raise ValueError("coder Q: the count does not match the payload")
    L = np.cumsum(v[1:])
    nx, ny = -(-width // s), -(-height // s)
    x, r = (L % nx) * s, L // nx
    y, r = (r % ny) * s, r // ny
    p, tb = r % 2, r // 2
    return -((-tb * int(T0_us)) // k), x, y, p


# ----------------------------------------------------------------------------------------------
# maps

def block_ids(x, y, B: int, width: int):
    return (np.asarray(y, dtype=np.int64) // B) * (-(-width // B)) + np.asarray(x, dtype=np.int64) // B


def block_frame(b: int, B: int, width: int):
    nbx = -(-width // B)
    return (b % nbx) * B + (B - 1) / 2.0, (b // nbx) * B + (B - 1) / 2.0, B / 2.0


def move(sx, sy, frame, q):
    """Pixels of the key events of one block under the map ``q`` (six integers)."""
    cx, cy, h = frame
    u = np.asarray(sx, dtype=np.float64) - cx
    v = np.asarray(sy, dtype=np.float64) - cy
    xm = np.asarray(sx, dtype=np.float64) + q[0] + (q[2] / h) * u + (q[3] / h) * v
    ym = np.asarray(sy, dtype=np.float64) + q[1] + (q[4] / h) * u + (q[5] / h) * v
    return np.rint(xm).astype(np.int64), np.rint(ym).astype(np.int64)


def encode_maps(maps, n_params: int) -> bytes:
    """``maps``: integers of shape (active blocks in raster order, K - 1, >= n_params)."""
    v = np.asarray(maps, dtype=np.int64)[:, :, :n_params]
    d = np.diff(v, axis=1, prepend=0).transpose(0, 2, 1).ravel()
    raw = uleb_encode(((d << 1) ^ (d >> 63)).astype(np.uint64))
    z = _zstd(raw, 19)
    return b"\x01" + z if len(z) < len(raw) else b"\x00" + raw


def decode_maps(buf: bytes, n_blocks: int, n_targets: int, n_params: int):
    if len(buf) == 0 or buf[0] not in (0, 1):
        raise ValueError("map payload: bad flag")
    raw = _unzstd(buf[1:]) if buf[0] == 1 else buf[1:]
    zz, end = uleb_decode(raw, n_blocks * n_targets * n_params)
    if end != len(raw):
        raise ValueError("map payload: trailing bytes")
    d = (zz >> 1) ^ -(zz & 1)
    out = np.zeros((n_blocks, n_targets, 6), dtype=np.int64)
    out[:, :, :n_params] = np.cumsum(d.reshape(n_blocks, n_params, n_targets).transpose(0, 2, 1), axis=1)
    return out


# ----------------------------------------------------------------------------------------------
# bitstream

def encode_header(coder: str, model: str, K: int, width: int, height: int, B: int, T0_us: int = T0_US,
                  origin_us: int = 0) -> bytes:
    qs, qk = Q_KEY if coder == "Q" else (0, 0)
    return HEADER.pack(MAGIC, VERSION, CODERS.index(coder), MODELS.index(model), K, width, height, B, qs, qk,
                       T0_us, origin_us)


def encode_group(header: bytes, w_delta: int, key, maps=None) -> bytes:
    """One record. ``key`` = (t_rel, x, y, p) of the key events. ``maps``: (active blocks in raster order, K - 1, 6)."""
    h = decode_header(header)
    kt, kx, ky, kp = key
    if h["coder"] == "T":
        ev = encode_events_T(kt, kx, ky, kp)
    else:
        ev = encode_events_Q(kt, kx, ky, kp, h["qcell"], h["width"], h["height"], h["T0_us"])
    out = uleb_encode([w_delta, len(ev)]) + ev
    if h["model"] != "static":
        n_act = len(np.unique(block_ids(kx, ky, h["B"], h["width"])))
        maps = np.zeros((0, h["K"] - 1, 6), dtype=np.int64) if maps is None else np.asarray(maps)
        if maps.shape[:2] != (n_act, h["K"] - 1):
            raise ValueError("one map per active block and target is required")
        mp = encode_maps(maps, N_PARAMS[h["model"]])
        out += uleb_encode([len(mp)]) + mp
    return out


def decode_header(buf: bytes) -> dict:
    magic, version, coder, model, K, width, height, B, qs, qk, T0_us, origin = HEADER.unpack_from(buf, 0)
    if magic != MAGIC or version != VERSION:
        raise ValueError("not a stream of this codec")
    return {"coder": CODERS[coder], "model": MODELS[model], "K": K, "width": width, "height": height, "B": B,
            "qcell": (qs, qk), "T0_us": T0_us, "origin_us": origin}


def decode_stream(buf: bytes, cache: dict | None = None):
    """Header and groups of a stream. Each group: key window index ``w``, key events, active block ids, maps.

    ``cache`` memoizes decoded key payloads by their bytes. It changes no result.
    """
    h = decode_header(buf)
    pos, w, groups = HEADER.size, 0, []
    while pos < len(buf):
        (dw, n_ev), pos = uleb_decode(buf, 2, pos)
        ev = bytes(buf[pos:pos + int(n_ev)])
        if len(ev) != n_ev:
            raise ValueError("truncated key payload")
        pos += int(n_ev)
        ck = (h["coder"], h["qcell"], ev)
        if cache is not None and ck in cache:
            key = cache[ck]
        else:
            key = (decode_events_T(ev) if h["coder"] == "T" else
                   decode_events_Q(ev, h["qcell"], h["width"], h["height"], h["T0_us"]))
            if cache is not None:
                cache[ck] = key
        w += int(dw)
        bid = block_ids(key[1], key[2], h["B"], h["width"])
        ids = np.unique(bid)
        maps = np.zeros((len(ids), h["K"] - 1, 6), dtype=np.int64)
        if h["model"] != "static":
            (n_mp,), pos = uleb_decode(buf, 1, pos)
            mp = bytes(buf[pos:pos + int(n_mp)])
            if len(mp) != n_mp:
                raise ValueError("truncated map payload")
            pos += int(n_mp)
            maps = decode_maps(mp, len(ids), h["K"] - 1, N_PARAMS[h["model"]])
        groups.append({"w": w, "key": key, "bid": bid, "ids": ids, "maps": maps})
    return h, groups


def reconstruct(h: dict, group: dict, m: int):
    """Events ``(t_us, x, y, p)`` of window ``m`` of a decoded group, with absolute times."""
    kt, kx, ky, kp = group["key"]
    t = h["origin_us"] + (group["w"] + m) * h["T0_us"] + kt
    if m == 0:
        return t, kx, ky, kp
    ix, iy = np.empty_like(kx), np.empty_like(ky)
    for j, b in enumerate(group["ids"]):
        sel = group["bid"] == b
        ix[sel], iy[sel] = move(kx[sel], ky[sel], block_frame(int(b), h["B"], h["width"]), group["maps"][j, m - 1])
    keep = (ix >= 0) & (ix < h["width"]) & (iy >= 0) & (iy < h["height"])
    return t[keep], ix[keep], iy[keep], kp[keep]


# ----------------------------------------------------------------------------------------------
# the sender's fit

class Residual:
    """Counts of the true events of one window that no block has claimed, on the grids of STAGE_CELLS."""

    def __init__(self, t_rel, x, y, p, width: int, height: int, T0_us: int = T0_US):
        self.width, self.height, self.g = width, height, {}
        x, y, p = (np.asarray(a, dtype=np.int64) for a in (x, y, p))
        for s, k in STAGE_CELLS:
            nx, ny = -(-width // s), -(-height // s)
            idx = ((p * k + time_bin(t_rel, k, T0_us)) * ny + y // s) * nx + x // s
            self.g[(s, k)] = (nx, ny, np.bincount(idx, minlength=2 * k * ny * nx).astype(np.int64))

    def _index(self, ix, iy, tb, p, cell):
        s, k = cell
        nx, ny, _ = self.g[cell]
        keep = (ix >= 0) & (ix < self.width) & (iy >= 0) & (iy < self.height)
        tbk = tb[keep] if k == OBJECTIVE[1] else 0
        return ((p[keep] * k + tbk) * ny + iy[keep] // s) * nx + ix[keep] // s

    def matched(self, ix, iy, tb, p, cell) -> int:
        """Moved events (``tb``: their bin on the working grid) that can be paired with unclaimed true events."""
        u, c = np.unique(self._index(ix, iy, tb, p, cell), return_counts=True)
        return int(np.minimum(c, self.g[cell][2][u]).sum())

    def claim(self, ix, iy, tb, p):
        """Pair on the working grid and remove the paired true events from every grid. Returns ``paired, n_in_sensor``."""
        idx = self._index(ix, iy, tb, p, OBJECTIVE)
        u, c = np.unique(idx, return_counts=True)
        nx, ny, R = self.g[OBJECTIVE]
        got = np.minimum(c, R[u])
        R[u] -= got
        s0, k0 = OBJECTIVE
        bx, r = u % nx, u // nx
        by, r = r % ny, r // ny
        pol = r // k0
        for s, k in STAGE_CELLS[1:]:
            cnx, cny, C = self.g[(s, k)]
            np.subtract.at(C, (pol * k * cny + (by * s0) // s) * cnx + (bx * s0) // s, got)
        return int(got.sum()), int(len(idx))


def _stage_cell(step: int):
    s = 2 if step <= 2 else 4 if step <= 4 else 8 if step <= 8 else 16
    return s, (OBJECTIVE[1] if s == 2 else 1)


def search_translation(score, d0, R: int):
    """Integer displacement that pairs the most events. ``score(q, cell)``; see ``ec.gop.aligned_displacement``.

    Coarse to fine around ``rint(d0)``, then compared on the working grid with ``rint(d0)`` itself
    and with zero. On a tie the start wins over the search result, and both win over zero.
    """
    start = (int(np.rint(d0[0])), int(np.rint(d0[1])))
    step, reach, best = int(math.ceil(R / 4)), 4, start
    while True:
        cell = _stage_cell(step)
        offs = [(i, j) for i in range(-reach, reach + 1) for j in range(-reach, reach + 1)]
        offs.sort(key=lambda ij: (ij[0] * ij[0] + ij[1] * ij[1], ij))
        cand, top = best, -1
        for i, j in offs:
            d = (best[0] + i * step, best[1] + j * step)
            f = score(d + (0, 0, 0, 0), cell)
            if f > top:
                cand, top = d, f
        best = cand
        if step == 1:
            break
        step, reach = int(math.ceil(step / 2)), 2
    top = score(best + (0, 0, 0, 0), OBJECTIVE)
    for alt in (start, (0, 0)):                 # never fewer pairs than the start or than no motion
        if alt != best:
            f = score(alt + (0, 0, 0, 0), OBJECTIVE)
            if f > top or (f == top and alt == start):
                best, top = alt, f
    return best


def search_shape(score, d, shape_prev, ratio: float, B: int):
    """Six parameters that pair the most events, from the translation ``d``. See ``ec.affine.fit_affine``."""
    def stretched(q, k):
        return (q[0], q[1], q[2] + k, q[3], q[4], q[5] + k)

    def bumped(q, i, k):
        return tuple(v + (k if j == i else 0) for j, v in enumerate(q))

    moves = [stretched] + [lambda q, k, i=i: bumped(q, i, k) for i in (2, 5, 3, 4, 0, 1)]
    start = (int(d[0]), int(d[1]), 0, 0, 0, 0)
    start_top = score(start, OBJECTIVE)
    best = start
    if shape_prev is not None:
        warm = (start[0], start[1]) + tuple(int(np.rint(ratio * v)) for v in shape_prev)
        if warm != start and score(warm, OBJECTIVE) > start_top:
            best = warm
    for cell, offsets, max_rounds in STAGES:
        offsets = [k for k in offsets if abs(k) <= B // 10]
        if not offsets:
            continue
        top = score(best, cell)
        for _ in range(max_rounds):
            changed = False
            for mv in moves:
                cand, ctop = best, top
                for k in offsets:
                    q = mv(best, k)
                    f = score(q, cell)
                    if f > ctop:
                        cand, ctop = q, f
                if cand != best:
                    best, top, changed = cand, ctop, True
            if not changed:
                break
    if best != start and score(best, OBJECTIVE) <= start_top:
        best = start
    return best


def fit_group(key, truths, B: int, model: str, theta_min: int, width: int, height: int, T0_us: int = T0_US) -> dict:
    """Maps of every block with at least ``theta_min`` key events, for the targets ``m`` = 1 .. len(truths).

    ``key`` = (t_rel, x, y, p) of all events of the key window, ``truths[m - 1]`` the same for window
    ``m``. Returns the block ids in fitting order (``ids``), their key counts (``counts``), ``maps`` of
    shape (blocks, targets, 6), the claimed pairs and the moved events inside the sensor per block
    and target (``claimed``, ``n_in``), and the number of scored maps (``n_eval``).
    """
    kt, kx, ky, kp = (np.asarray(a, dtype=np.int64) for a in key)
    bid = block_ids(kx, ky, B, width)
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
        ev.append((kx[sel], ky[sel], time_bin(kt[sel], OBJECTIVE[1], T0_us), kp[sel], block_frame(int(b), B, width)))
    n_eval = 0
    for m in range(1, n_t + 1):
        res = Residual(*truths[m - 1], width, height, T0_us)
        for j, (sx, sy, tb, sp, frame) in enumerate(ev):
            def score(q, cell):
                nonlocal n_eval
                n_eval += 1
                ix, iy = move(sx, sy, frame, q)
                return res.matched(ix, iy, tb, sp, cell)

            q = (0, 0, 0, 0, 0, 0)
            if model != "static":
                if m == 1:
                    d0, R = (0.0, 0.0), RADIUS_FIRST
                else:
                    r = m / (m - 1.0)
                    d0 = (r * maps[j, m - 2, 0], r * maps[j, m - 2, 1])
                    R = max(3, int(math.ceil(0.3 * math.hypot(*d0))))
                d = search_translation(score, d0, R)
                q = d + (0, 0, 0, 0)
                if model == "affine":
                    prev = tuple(int(v) for v in maps[j, m - 2, 2:]) if m > 1 else None
                    q = search_shape(score, d, prev, m / (m - 1.0) if m > 1 else 1.0, B)
            maps[j, m - 1] = q
            claimed[j, m - 1], n_in[j, m - 1] = res.claim(*move(sx, sy, frame, q), tb, sp)
    return {"ids": ids, "counts": counts, "maps": maps, "claimed": claimed, "n_in": n_in, "n_eval": n_eval}


# ----------------------------------------------------------------------------------------------
# evaluation of one group

class Truth:
    """Voxel counts of the true events of one window, kept per grid. ``match`` equals ``ec.regen.voxel_f1``."""

    def __init__(self, t_us, x, y, p, w0_us: int, T0_us: int = T0_US):
        self.t, self.x, self.y, self.p, self.w0, self.T0, self._c = t_us, x, y, p, int(w0_us), int(T0_us), {}

    def _keys(self, t, x, y, p, s, k):
        bt = np.minimum(k - 1, ((np.asarray(t, dtype=np.int64) - self.w0) * k) // self.T0)
        return (((np.asarray(y, dtype=np.int64) // s) * (1 << 20) + np.asarray(x, dtype=np.int64) // s) * 64 + bt) * 2 \
            + np.asarray(p, dtype=np.int64)

    def match(self, t, x, y, p, cell) -> int:
        if len(t) == 0 or len(self.t) == 0:
            return 0
        if cell not in self._c:
            self._c[cell] = np.unique(self._keys(self.t, self.x, self.y, self.p, *cell), return_counts=True)
        kf, cf = self._c[cell]
        kp, cp = np.unique(self._keys(t, x, y, p, *cell), return_counts=True)
        _, ip, jf = np.intersect1d(kp, kf, assume_unique=True, return_indices=True)
        return int(np.minimum(cp[ip], cf[jf]).sum())


def group_fidelity(n_key: int, n_rec, n_true, match) -> float:
    """``F_K`` of the module docstring. ``n_rec`` and ``match`` hold the targets ``m`` = 1 .. ``K - 1``, ``n_true`` the windows ``m`` = 0 .. ``K - 1``."""
    den = n_key + np.sum(n_rec, dtype=np.float64) + np.sum(n_true, dtype=np.float64)
    return float(2.0 * (n_key + np.sum(match, dtype=np.float64)) / den) if den > 0 else 0.0


def baseline_bits(q: float, shares, bits, envelope: bool = True) -> float:
    """Bits of subset schemes at the share ``q``, from measured points ``(share, bits)`` and the origin.

    With ``envelope``: the cheapest mixture, the lower convex envelope of the points. Without: linear
    interpolation between neighboring points. Beyond the largest share the value of that point.
    """
    best = {0.0: 0.0}
    for s, b in zip(shares, bits):
        s, b = float(s), float(b)
        best[s] = min(b, best.get(s, b))
    pts = sorted(best.items())
    if envelope:
        hull = []
        for pt in pts:
            while len(hull) >= 2 and ((hull[-1][0] - hull[-2][0]) * (pt[1] - hull[-2][1])
                                      - (hull[-1][1] - hull[-2][1]) * (pt[0] - hull[-2][0])) <= 0:
                hull.pop()
            hull.append(pt)
        pts = hull
    return float(np.interp(q, [v[0] for v in pts], [v[1] for v in pts]))


def evaluate_group(t_us, x, y, p, w: int, w_prev: int, width: int, height: int, blocks=BLOCKS, densities=DENSITIES,
                   models=MODELS, grid_for=None, records_for=None, T0_us: int = T0_US) -> dict:
    """Everything of the group keyed at window ``w``. ``t_us`` must be nondecreasing.

    ``w_prev`` is the key window of the previous group of the stream (0 for the first group). Every
    fidelity is measured on events decoded from ``header + record``. ``grid_for`` = (B, rho) asks for
    all twelve grids of directive 002 for that configuration; the others get CELLS_MAIN. Configurations
    are keyed ``B{B}_rho{rho}`` with ``rho`` printed as a float. Fidelities
    of streams of coder Q are those of coder T on grids with one or three time bins, which is checked
    on the working grid (``q_equals_t``). ``records_for`` = (B, rho) returns the records of that
    configuration as bytes under ``records``, keyed ``model_coder_K``, for writing complete streams.
    """
    t_us = np.asarray(t_us, dtype=np.int64)
    grid_for = None if grid_for is None else (int(grid_for[0]), float(grid_for[1]))
    records_for = None if records_for is None else (int(records_for[0]), float(records_for[1]))
    edges = np.searchsorted(t_us, [(w + m) * T0_us for m in range(N_TARGETS + 2)])
    win = []
    for m in range(N_TARGETS + 1):
        a, b = edges[m], edges[m + 1]
        win.append((t_us[a:b] - (w + m) * T0_us, np.asarray(x[a:b], dtype=np.int64), np.asarray(y[a:b], dtype=np.int64),
                    np.asarray(p[a:b], dtype=np.int64)))
    truth = [Truth(t_us[edges[m]:edges[m + 1]], win[m][1], win[m][2], win[m][3], (w + m) * T0_us, T0_us)
             for m in range(N_TARGETS + 1)]
    n_true = [int(len(v[0])) for v in win]
    out = {"w": int(w), "n_true": n_true, "direct": {}, "thin": {}, "select": {}, "codec": {}, "fit": {}}

    # baselines
    u = np.random.default_rng((THIN_SEED, int(w))).random(int(edges[-1] - edges[0]))
    for coder in CODERS:
        enc = (lambda v: encode_events_T(*v)) if coder == "T" else \
              (lambda v: encode_events_Q(*v, Q_DIRECT, width, height, T0_us))
        out["direct"][coder] = [8 * len(enc(v)) for v in win]
        for chi in THIN_SHARES:
            bits, kept = [], []
            for m, v in enumerate(win):
                sel = u[edges[m] - edges[0]:edges[m + 1] - edges[0]] < chi
                bits.append(8 * len(enc(tuple(a[sel] for a in v))))
                kept.append(int(sel.sum()))
            out["thin"].setdefault(str(chi), {"n_kept": kept})[coder] = bits

    for B in blocks:                                        # select: the active blocks of every window, as they are
        bids = [block_ids(v[1], v[2], B, width) for v in win]
        for rho in densities:
            row = {"n_kept": [], "T": [], "Q": []}
            for v, bid in zip(win, bids):
                ids, cnt = np.unique(bid, return_counts=True)
                sel = np.isin(bid, ids[cnt >= threshold(B, rho)])
                kept = tuple(a[sel] for a in v)
                row["n_kept"].append(int(sel.sum()))
                row["T"].append(8 * len(encode_events_T(*kept)))
                row["Q"].append(8 * len(encode_events_Q(*kept, Q_DIRECT, width, height, T0_us)))
            out["select"][f"B{B}_rho{float(rho)}"] = row

    # the codec
    cache = {}
    for B in blocks:
        thetas = [threshold(B, rho) for rho in densities]
        fits = {model: fit_group(win[0], win[1:], B, model, min(thetas), width, height, T0_us) for model in models}
        out["fit"][str(B)] = {model: {"n_blocks": int(len(f["ids"])), "n_eval": int(f["n_eval"])} for model, f in fits.items()}
        bid0 = block_ids(win[0][1], win[0][2], B, width)
        for rho, theta in zip(densities, thetas):
            f0 = fits[models[0]]
            act = f0["counts"] >= theta                       # a prefix of the fitting order
            ids_r = np.sort(f0["ids"][act])
            ksel = np.isin(bid0, ids_r)
            key = tuple(a[ksel] for a in win[0])
            n_in_act = [int(np.isin(block_ids(v[1], v[2], B, width), ids_r).sum()) for v in win]
            cells = CELLS_ALL if grid_for == (int(B), float(rho)) else CELLS_MAIN
            row = {"theta": int(theta), "n_active": int(len(ids_r)), "n_key": int(ksel.sum()), "n_true_in_active": n_in_act,
                   "models": {}}
            for model in models:
                f = fits[model]
                pos = np.searchsorted(ids_r, f["ids"][act])   # fitting order -> raster order
                maps_r = np.zeros((len(ids_r), N_TARGETS, 6), dtype=np.int64)
                maps_r[pos] = f["maps"][act]
                r = {"bytes": {}, "claimed": f["claimed"][act].sum(0).tolist()}
                dec = {}
                for coder in CODERS:
                    for K in GROUPS:
                        hdr = encode_header(coder, model, K, width, height, B, T0_us)
                        rec = encode_group(hdr, w - w_prev, key, maps_r[:, :K - 1])
                        h, groups = decode_stream(hdr + rec, cache)
                        g = groups[0]
                        if len(groups) != 1 or g["w"] != w - w_prev or not np.array_equal(g["ids"], ids_r) \
                                or not np.array_equal(g["maps"], maps_r[:, :K - 1]):
                            raise AssertionError("the decoded group differs from the encoded one")
                        r["bytes"][f"{coder}_K{K}"] = len(rec)
                        if records_for == (int(B), float(rho)):
                            out.setdefault("records", {})[f"{model}_{coder}_K{K}"] = rec
                        if K == GROUPS[-1]:
                            g["w"] = w                          # the group is evaluated at its own window
                            dec[coder] = (h, g)
                h, g = dec["T"]
                rec_m = [reconstruct(h, g, m) for m in range(N_TARGETS + 1)]
                if len(rec_m[0][0]) != row["n_key"] or truth[0].match(*rec_m[0], OBJECTIVE) != row["n_key"]:
                    raise AssertionError("the decoded key events are not the key events")
                r["n_rec"] = [int(len(v[0])) for v in rec_m[1:]]
                for cell in cells:
                    r[f"match_s{cell[0]}_k{cell[1]}"] = [truth[m].match(*rec_m[m], cell) for m in range(1, N_TARGETS + 1)]
                hq, gq = dec["Q"]
                mq = [truth[m].match(*reconstruct(hq, gq, m), OBJECTIVE) for m in range(0, N_TARGETS + 1)]
                r["q_equals_t"] = bool(mq[0] == row["n_key"] and mq[1:] == r[f"match_s{OBJECTIVE[0]}_k{OBJECTIVE[1]}"])
                r["claim_equals_match"] = bool(r["claimed"] == r[f"match_s{OBJECTIVE[0]}_k{OBJECTIVE[1]}"])
                row["models"][model] = r
            out["codec"][f"B{B}_rho{float(rho)}"] = row
    return out


def sum_groups(groups) -> dict:
    """Sum of evaluated groups: counts and byte lengths add, the two checks are combined with ``and``."""
    def add(a, b):
        if isinstance(a, dict):
            return {k: (a[k] if k in ("w", "theta") else add(a[k], b[k])) for k in a}
        if isinstance(a, bool):
            return a and b
        if isinstance(a, list):
            return [add(u, v) for u, v in zip(a, b)]
        return a + b

    groups = [{k: v for k, v in g.items() if k != "records"} for g in groups]
    out = groups[0]
    for g in groups[1:]:
        out = add(out, g)
    out = dict(out)
    out["w"] = [int(g["w"]) for g in groups]
    return out


def evaluate_stream(buf: bytes, t_us, x, y, p, cell=OBJECTIVE) -> list:
    """The receiver's side: decode a complete stream and compare each of its windows with the true events.

    Uses the bytes of the stream and nothing of the sender. Returns one dictionary per group with
    the key window ``w`` and, for ``m`` = 0 .. ``K - 1``, ``n_rec``, ``n_true`` and ``match`` on ``cell``.
    """
    t_us = np.asarray(t_us, dtype=np.int64)
    h, groups = decode_stream(buf)
    T0, out = h["T0_us"], []
    for g in groups:
        row = {"w": int(g["w"]), "n_rec": [], "n_true": [], "match": []}
        for m in range(h["K"]):
            w0 = h["origin_us"] + (g["w"] + m) * T0
            a, b = np.searchsorted(t_us, (w0, w0 + T0))
            rec = reconstruct(h, g, m)
            row["n_rec"].append(int(len(rec[0])))
            row["n_true"].append(int(b - a))
            row["match"].append(Truth(t_us[a:b], x[a:b], y[a:b], p[a:b], w0, T0).match(*rec, cell))
        out.append(row)
    return out


def summarize(g: dict, config: str, model: str, coder: str, K: int, cell=OBJECTIVE) -> dict:
    """Fidelity, bits and the comparison with the baselines of one configuration, for a group or a sum of groups.

    ``g`` is the output of ``evaluate_group`` or of ``sum_groups``. Returns ``F``; ``q_eq = F / (2 - F)``;
    ``bits``, the bits of the records per true event; ``bits_direct``; ``bits_thin``, the bits of
    thinning at the share ``q_eq``; ``bits_base``, those of the envelope of ``thin``, of ``direct`` and
    of ``select`` with the block side of the configuration; ``gain = bits_base / bits`` and
    ``gain_thin = bits_thin / bits``; the event share ``share = n_key / n_true``; and
    ``gamma = q_eq / share``, the factor of directive 003 in events. With coder Q the comparison
    holds on grids of 2 or 4 px with one or three time bins, where the baselines pair every event.
    """
    row = g["codec"][config]
    r = row["models"][model]
    n = float(np.sum(g["n_true"][:K]))
    match = r[f"match_s{cell[0]}_k{cell[1]}"][:K - 1]
    F = group_fidelity(row["n_key"], r["n_rec"][:K - 1], g["n_true"][:K], match)
    q_eq = F / (2.0 - F)
    bits = 8.0 * r["bytes"][f"{coder}_K{K}"] / n
    direct = float(np.sum(g["direct"][coder][:K])) / n

    def points(rows):
        return ([float(np.sum(v["n_kept"][:K])) / n for v in rows] + [1.0],
                [float(np.sum(v[coder][:K])) / n for v in rows] + [direct])

    thin_pts = points([g["thin"][str(chi)] for chi in THIN_SHARES])
    side = config.split("_")[0] + "_"
    sel_pts = points([v for k, v in g["select"].items() if k.startswith(side)])
    thin = baseline_bits(q_eq, *thin_pts, envelope=False)
    base = baseline_bits(q_eq, thin_pts[0] + sel_pts[0], thin_pts[1] + sel_pts[1])
    share = row["n_key"] / n
    return {"F": F, "q_eq": q_eq, "bits": bits, "bits_direct": direct, "bits_thin": thin, "bits_base": base,
            "gain": base / bits, "gain_thin": thin / bits, "share": share,
            "gamma": q_eq / share if share > 0 else float("nan")}
