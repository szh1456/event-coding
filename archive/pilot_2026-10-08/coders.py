"""Pilot coders and code-length estimators (plan: event_coding_brief.md, Section 4.2).

All model code lengths are prequential: the probability of each symbol is computed from counts that
depend only on earlier events, and the counts are updated afterwards. The sum of -log2(p) is what an
arithmetic coder achieves up to a few bits per file (checked by roundtrip_check.py on a short segment).
"""
import bz2
import lzma
import math

import numpy as np
import zstandard as zstd
from numba import njit

NB = 7          # age buckets
NC = NB * NB    # address classes (self bucket, neighbor bucket)
KT = 0.5


# ----------------------------------------------------------------------------- generic baselines
def u2_arrays(t, x, y, p):
    """Pilot re-implementation of the U2 layout: structure of arrays with delta timestamps."""
    dt = np.diff(t, prepend=t[0])
    assert dt.min() >= 0 and dt.max() < 2 ** 32
    return dt.astype("<u4").tobytes() + x.astype("<u2").tobytes() + y.astype("<u2").tobytes() + p.astype("u1").tobytes()


def u2_shuffled(t, x, y, p):
    """U2 with byte planes split (as Blosc shuffle does) and polarity bit-packed. Post hoc variant, added
    after the first run showed that 1-byte Huffman symbols cost at least 1 bit for every zero high byte."""
    dt = np.diff(t, prepend=t[0]).astype("<u4")
    planes = [dt.view(np.uint8).reshape(-1, 4).T.tobytes(),
              x.astype("<u2").view(np.uint8).reshape(-1, 2).T.tobytes(),
              y.astype("<u2").view(np.uint8).reshape(-1, 2).T.tobytes(),
              np.packbits(p.astype(np.uint8)).tobytes()]
    return b"".join(planes)


def shuffle_within_ties(t, x, y, p, seed=0):
    """Random order inside each group of equal timestamps (for the bits-back multiset estimate)."""
    rng = np.random.default_rng(seed)
    idx = np.lexsort((rng.random(len(t)), t))
    return t[idx], x[idx], y[idx], p[idx]


def aos64(t, x, y, p):
    """8-byte record per event (32-bit time, 16-bit x, 15-bit y, 1-bit polarity), as in the 64-bit raw
    size used by most of the literature."""
    rec = np.zeros(len(t), dtype=[("t", "<u4"), ("x", "<u2"), ("yp", "<u2")])
    rec["t"] = (t - t[0]).astype(np.uint32)
    rec["x"] = x
    rec["yp"] = (y.astype(np.uint16) << 1) | p.astype(np.uint16)
    return rec.tobytes()


def canonical_order(t, x, y, p):
    idx = np.lexsort((p, x, y, t))
    return t[idx], x[idx], y[idx], p[idx]


def generic_sizes(buf, tag, chunk_events=None, rec_bytes=None):
    out = {}
    out[tag + "+zstd-1"] = len(zstd.ZstdCompressor(level=1).compress(buf))
    out[tag + "+zstd-19"] = len(zstd.ZstdCompressor(level=19).compress(buf))
    params = zstd.ZstdCompressionParameters.from_level(22, window_log=27, enable_ldm=True)
    out[tag + "+zstd-22-long"] = len(zstd.ZstdCompressor(compression_params=params).compress(buf))
    out[tag + "+xz-9e"] = len(lzma.compress(buf, preset=9 | lzma.PRESET_EXTREME))
    out[tag + "+bzip2-9"] = len(bz2.compress(buf, 9))
    return out


def u2_chunked_zstd1(t, x, y, p, chunk=65536):
    c = zstd.ZstdCompressor(level=1)
    total = 0
    for s in range(0, len(t), chunk):
        e = min(len(t), s + chunk)
        total += len(c.compress(u2_arrays(t[s:e], x[s:e], y[s:e], p[s:e])))
    return total


# ----------------------------------------------------------------------------- time model
@njit(cache=True)
def time_bits(t):
    """Adaptive model of k = floor(log2(dt+1)) given the previous k, plus k raw bits for the offset."""
    n = t.shape[0]
    K = 40
    cnt = np.full((K, K), KT)
    tot = np.full(K, KT * K)
    out = np.zeros(n, dtype=np.float32)
    prev = 0
    for i in range(1, n):
        d = t[i] - t[i - 1] + 1
        k = 0
        while (d >> (k + 1)) > 0:
            k += 1
        out[i] = -math.log2(cnt[prev, k] / tot[prev]) + k
        cnt[prev, k] += 1.0
        tot[prev] += 1.0
        prev = k
    return out


# ----------------------------------------------------------------------------- address and polarity models
@njit(cache=True)
def _bucket(a):
    if a < 1:
        return 0
    if a < 2:
        return 1
    if a < 4:
        return 2
    if a < 16:
        return 3
    if a < 64:
        return 4
    if a < 256:
        return 5
    return 6


@njit(cache=True)
def _refresh(S, bs, bn, Nc, s, W, H, use_nbr):
    N = W * H
    for u in range(N):
        bs[u] = _bucket(s - S[u])
    for c in range(NC):
        Nc[c] = 0.0
    for yy in range(H):
        for xx in range(W):
            u = yy * W + xx
            m = 6
            if use_nbr:
                for dy in range(-1, 2):
                    y2 = yy + dy
                    if y2 < 0 or y2 >= H:
                        continue
                    for dx in range(-1, 2):
                        x2 = xx + dx
                        if x2 < 0 or x2 >= W or (dx == 0 and dy == 0):
                            continue
                        b = bs[y2 * W + x2]
                        if b < m:
                            m = b
            else:
                m = 0
            bn[u] = m
            Nc[bs[u] * NB + m] += 1.0


@njit(cache=True)
def context_code(t, x, y, p, W, H, slot_us, use_nbr):
    """C1 (use_nbr=True) and M2 (use_nbr=False). Returns per-event address bits, polarity bits, class index."""
    n = t.shape[0]
    N = W * H
    S = np.full(N, -(10 ** 9), dtype=np.int64)      # slot of last event
    TL = np.full(N, -1, dtype=np.int64)             # exact time of last event
    LP = np.full(N, -1, dtype=np.int8)              # polarity of last event
    bs = np.full(N, 6, dtype=np.int8)
    bn = np.full(N, 6, dtype=np.int8)
    Nc = np.zeros(NC)
    nev = np.zeros(NC)
    expo = np.zeros(NC)
    pc = np.full((3 * NB * 3, 2), KT)
    a_bits = np.zeros(n, dtype=np.float32)
    p_bits = np.zeros(n, dtype=np.float32)
    cls = np.zeros(n, dtype=np.int16)
    cur = t[0] // slot_us
    _refresh(S, bs, bn, Nc, cur, W, H, use_nbr)
    aN = KT * N
    for i in range(n):
        s = t[i] // slot_us
        if s != cur:
            cur = s
            _refresh(S, bs, bn, Nc, cur, W, H, use_nbr)
        xx = x[i]
        yy = y[i]
        u = yy * W + xx
        c = bs[u] * NB + bn[u]
        Z = 0.0
        for cc in range(NC):
            if Nc[cc] > 0.0:
                Z += Nc[cc] * (nev[cc] + KT) / (expo[cc] + aN)
        a_bits[i] = -math.log2(((nev[c] + KT) / (expo[c] + aN)) / Z)
        cls[i] = c
        # polarity context: last polarity here, own age bucket, polarity of the most recent neighbor event
        best = -1
        npol = 0
        for dy in range(-1, 2):
            y2 = yy + dy
            if y2 < 0 or y2 >= H:
                continue
            for dx in range(-1, 2):
                x2 = xx + dx
                if x2 < 0 or x2 >= W or (dx == 0 and dy == 0):
                    continue
                v = y2 * W + x2
                if TL[v] > best:
                    best = TL[v]
                    npol = LP[v] + 1
        ctx = (LP[u] + 1) * (NB * 3) + bs[u] * 3 + npol
        pi = p[i]
        p_bits[i] = -math.log2(pc[ctx, pi] / (pc[ctx, 0] + pc[ctx, 1]))
        pc[ctx, pi] += 1.0
        # update statistics, then state
        for cc in range(NC):
            expo[cc] += Nc[cc]
        nev[c] += 1.0
        S[u] = cur
        TL[u] = t[i]
        LP[u] = pi
        if bs[u] != 0:
            Nc[c] -= 1.0
            bs[u] = 0
            Nc[bn[u]] += 1.0
        if use_nbr:
            for dy in range(-1, 2):
                y2 = yy + dy
                if y2 < 0 or y2 >= H:
                    continue
                for dx in range(-1, 2):
                    x2 = xx + dx
                    if x2 < 0 or x2 >= W or (dx == 0 and dy == 0):
                        continue
                    v = y2 * W + x2
                    if bn[v] != 0:
                        Nc[bs[v] * NB + bn[v]] -= 1.0
                        bn[v] = 0
                        Nc[bs[v] * NB] += 1.0
    return a_bits, p_bits, cls


@njit(cache=True)
def ratemap_bits(x, y, W, H, alpha):
    """M1: adaptive per-pixel rate map, P(u) = (n_u + alpha) / (i + alpha N)."""
    n = x.shape[0]
    N = W * H
    cnt = np.zeros(N)
    out = np.zeros(n, dtype=np.float32)
    for i in range(n):
        u = y[i] * W + x[i]
        out[i] = -math.log2((cnt[u] + alpha) / (i + alpha * N))
        cnt[u] += 1.0
    return out


@njit(cache=True)
def polarity_order0_bits(p):
    c = np.full(2, KT)
    out = np.zeros(p.shape[0], dtype=np.float32)
    for i in range(p.shape[0]):
        out[i] = -math.log2(c[p[i]] / (c[0] + c[1]))
        c[p[i]] += 1.0
    return out


def empirical_address_entropy(x, y, W, H):
    """M1*: order-0 entropy of the address with the rate map of the whole recording (optimistic)."""
    cnt = np.bincount(y.astype(np.int64) * W + x, minlength=W * H).astype(np.float64)
    q = cnt[cnt > 0] / cnt.sum()
    return float(-(q * np.log2(q)).sum())


def order_free_saving_bits(t, x, y, p, W):
    """Bits saved when the order of events that share a timestamp is not coded: sum over tie groups of
    log2(n!) minus log2 of the multiplicities of identical events."""
    key = (y.astype(np.int64) * W + x) * 2 + p
    idx = np.lexsort((key, t))
    ts, ks = t[idx], key[idx]
    newg = np.empty(len(ts), dtype=bool)
    newg[0] = True
    newg[1:] = ts[1:] != ts[:-1]
    gsize = np.diff(np.append(np.flatnonzero(newg), len(ts)))
    lg = np.vectorize(math.lgamma)
    total = lg(gsize[gsize > 1] + 1.0).sum() if (gsize > 1).any() else 0.0
    newe = newg.copy()
    newe[1:] |= ks[1:] != ks[:-1]
    msize = np.diff(np.append(np.flatnonzero(newe), len(ts)))
    dup = lg(msize[msize > 1] + 1.0).sum() if (msize > 1).any() else 0.0
    return float((total - dup) / math.log(2)), float((msize > 1).sum())


def poisson_bits(rate_hz, delta_s):
    """Eq. (2) of the brief."""
    return (1.0 - math.log(rate_hz * delta_s)) / math.log(2)
