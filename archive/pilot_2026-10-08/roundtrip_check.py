#!/usr/bin/env python3
"""Validity check for the C1 code lengths.

1. A second, independent implementation of the C1 model (plain numpy, written as a step-by-step codec)
   drives a real integer arithmetic coder. The decoder sees only the bitstream, the first timestamp, and
   the sensor size. The decoded events must equal the input.
2. The size of the bitstream must match the ideal code length of the reference model (small excess from
   16-bit probability quantization).
3. The ideal code length of the reference model must match the numba estimator in coders.py.

Usage: python3 -I roundtrip_check.py <kind> <path> <W> <H> <n_events>
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np

import coders as C
from io_events import load_evt2, load_txt

NB, NC, KT, K = 7, 49, 0.5, 40
PREC = 16
TOP = 1 << 32
HALF = 1 << 31
QUARTER = 1 << 30


class Encoder:
    def __init__(self):
        self.low, self.high, self.pending, self.bits = 0, TOP - 1, 0, []

    def _emit(self, b):
        self.bits.append(b)
        self.bits.extend([1 - b] * self.pending)
        self.pending = 0

    def encode(self, lo, hi, total):
        r = self.high - self.low + 1
        self.high = self.low + r * hi // total - 1
        self.low = self.low + r * lo // total
        while True:
            if self.high < HALF:
                self._emit(0)
            elif self.low >= HALF:
                self._emit(1)
                self.low -= HALF
                self.high -= HALF
            elif self.low >= QUARTER and self.high < 3 * QUARTER:
                self.pending += 1
                self.low -= QUARTER
                self.high -= QUARTER
            else:
                break
            self.low <<= 1
            self.high = (self.high << 1) | 1

    def finish(self):
        self.pending += 1
        self._emit(0 if self.low < QUARTER else 1)
        return self.bits


class Decoder:
    def __init__(self, bits):
        self.bits, self.pos = bits, 0
        self.low, self.high, self.value = 0, TOP - 1, 0
        for _ in range(32):
            self.value = (self.value << 1) | self._next()

    def _next(self):
        b = self.bits[self.pos] if self.pos < len(self.bits) else 0
        self.pos += 1
        return b

    def target(self, total):
        r = self.high - self.low + 1
        return ((self.value - self.low + 1) * total - 1) // r

    def consume(self, lo, hi, total):
        r = self.high - self.low + 1
        self.high = self.low + r * hi // total - 1
        self.low = self.low + r * lo // total
        while True:
            if self.high < HALF:
                pass
            elif self.low >= HALF:
                self.low -= HALF
                self.high -= HALF
                self.value -= HALF
            elif self.low >= QUARTER and self.high < 3 * QUARTER:
                self.low -= QUARTER
                self.high -= QUARTER
                self.value -= QUARTER
            else:
                break
            self.low <<= 1
            self.high = (self.high << 1) | 1
            self.value = (self.value << 1) | self._next()


def quantize(prob):
    """Integer frequencies with total near 2^PREC and at least 1 for every symbol of nonzero probability."""
    f = np.where(prob > 0, np.maximum(1, np.round(prob * (1 << PREC))), 0).astype(np.int64)
    return f


BUCKET_EDGES = np.array([1, 2, 4, 16, 64, 256])


class RefModel:
    """C1 model state. Every method uses only events already coded."""

    def __init__(self, W, H, slot_us, t0):
        self.W, self.H, self.N, self.slot_us = W, H, W * H, slot_us
        self.S = np.full((H, W), -(10 ** 9), dtype=np.int64)
        self.TL = np.full((H, W), -1, dtype=np.int64)
        self.LP = np.full((H, W), -1, dtype=np.int64)
        self.nev = np.zeros(NC)
        self.expo = np.zeros(NC)
        self.pc = np.full((3 * NB * 3, 2), KT)
        self.tc = np.full((K, K), KT)
        self.prev_k = 0
        self.cur = t0 // slot_us
        self.refresh()

    def refresh(self):
        self.bs = np.searchsorted(BUCKET_EDGES, self.cur - self.S, side="right").astype(np.int64)
        pad = np.pad(self.bs, 1, constant_values=6)
        H, W = self.H, self.W
        m = np.full((H, W), 6, dtype=np.int64)
        for dy in (0, 1, 2):
            for dx in (0, 1, 2):
                if dy == 1 and dx == 1:
                    continue
                m = np.minimum(m, pad[dy:dy + H, dx:dx + W])
        self.bn = m
        self.cls = self.bs * NB + self.bn
        self.Nc = np.bincount(self.cls.ravel(), minlength=NC).astype(np.float64)

    def time_probs(self):
        row = self.tc[self.prev_k]
        return row / row.sum()

    def set_time(self, t, k):
        self.tc[self.prev_k, k] += 1.0
        self.prev_k = k
        s = t // self.slot_us
        if s != self.cur:
            self.cur = s
            self.refresh()

    def class_probs(self):
        rho = (self.nev + KT) / (self.expo + KT * self.N)
        w = self.Nc * rho
        return w / w.sum()

    def pol_ctx(self, x, y):
        best, npol = -1, 0
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                x2, y2 = x + dx, y + dy
                if 0 <= x2 < self.W and 0 <= y2 < self.H and self.TL[y2, x2] > best:
                    best = self.TL[y2, x2]
                    npol = self.LP[y2, x2] + 1
        return (self.LP[y, x] + 1) * (NB * 3) + self.bs[y, x] * 3 + npol

    def pol_probs(self, ctx):
        return self.pc[ctx] / self.pc[ctx].sum()

    def update(self, t, x, y, p, c, ctx):
        self.pc[ctx, p] += 1.0
        self.expo += self.Nc
        self.nev[c] += 1.0
        self.S[y, x] = self.cur
        self.TL[y, x] = t
        self.LP[y, x] = p
        y0, y1, x0, x1 = max(0, y - 1), min(self.H, y + 2), max(0, x - 1), min(self.W, x + 2)
        old = self.cls[y0:y1, x0:x1].copy()
        self.bn[y0:y1, x0:x1] = 0
        self.bn[y, x] = old[y - y0, x - x0] % NB          # own neighbor bucket is unchanged
        self.bs[y, x] = 0
        new = self.bs[y0:y1, x0:x1] * NB + self.bn[y0:y1, x0:x1]
        self.cls[y0:y1, x0:x1] = new
        np.subtract.at(self.Nc, old.ravel(), 1.0)
        np.add.at(self.Nc, new.ravel(), 1.0)


def cum(f, s):
    lo = int(f[:s].sum())
    return lo, lo + int(f[s]), int(f.sum())


def encode(t, x, y, p, W, H, slot_us):
    m = RefModel(W, H, slot_us, int(t[0]))
    enc = Encoder()
    ideal = 0.0
    for i in range(len(t)):
        ti, xi, yi, pi = int(t[i]), int(x[i]), int(y[i]), int(p[i])
        if i > 0:
            d = ti - int(t[i - 1]) + 1
            k = d.bit_length() - 1
            pr = m.time_probs()
            f = quantize(pr)
            enc.encode(*cum(f, k))
            if k > 0:
                enc.encode(d - (1 << k), d - (1 << k) + 1, 1 << k)
            ideal += -math.log2(pr[k]) + k
            m.set_time(ti, k)
        pr = m.class_probs()
        c = int(m.cls[yi, xi])
        f = quantize(pr)
        enc.encode(*cum(f, c))
        nc = int(m.Nc[c])
        rank = int(np.count_nonzero(m.cls.ravel()[:yi * W + xi] == c))
        enc.encode(rank, rank + 1, nc)
        ideal += -math.log2(pr[c]) + math.log2(nc)
        ctx = int(m.pol_ctx(xi, yi))
        pp = m.pol_probs(ctx)
        f = quantize(pp)
        enc.encode(*cum(f, pi))
        ideal += -math.log2(pp[pi])
        m.update(ti, xi, yi, pi, c, ctx)
    return enc.finish(), ideal


def decode(bits, n, t0, W, H, slot_us):
    m = RefModel(W, H, slot_us, int(t0))
    dec = Decoder(bits)
    T, X, Y, P = [], [], [], []
    tprev = int(t0)
    for i in range(n):
        if i > 0:
            f = quantize(m.time_probs())
            cs = np.cumsum(f)
            tg = dec.target(int(cs[-1]))
            k = int(np.searchsorted(cs, tg, side="right"))
            dec.consume(*cum(f, k))
            off = 0
            if k > 0:
                off = dec.target(1 << k)
                dec.consume(off, off + 1, 1 << k)
            ti = tprev + (1 << k) + off - 1
            m.set_time(ti, k)
        else:
            ti = tprev
        f = quantize(m.class_probs())
        cs = np.cumsum(f)
        tg = dec.target(int(cs[-1]))
        c = int(np.searchsorted(cs, tg, side="right"))
        dec.consume(*cum(f, c))
        nc = int(m.Nc[c])
        rank = dec.target(nc)
        dec.consume(rank, rank + 1, nc)
        u = int(np.flatnonzero(m.cls.ravel() == c)[rank])
        yi, xi = divmod(u, W)
        ctx = int(m.pol_ctx(xi, yi))
        f = quantize(m.pol_probs(ctx))
        tg = dec.target(int(f.sum()))
        pi = 0 if tg < f[0] else 1
        dec.consume(*cum(f, pi))
        m.update(ti, xi, yi, pi, c, ctx)
        T.append(ti); X.append(xi); Y.append(yi); P.append(pi)
        tprev = ti
    return np.array(T), np.array(X), np.array(Y), np.array(P)


def main():
    kind, path, W, H, n = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
    t, x, y, p, _ = (load_evt2 if kind == "evt2" else load_txt)(path)
    t, x, y, p = t[:n].copy(), x[:n].copy(), y[:n].copy(), p[:n].copy()
    slot = 4000
    bits, ideal = encode(t, x, y, p, W, H, slot)
    T, X, Y, P = decode(bits, n, t[0], W, H, slot)
    ok = bool((T == t).all() and (X == x).all() and (Y == y).all() and (P == p).all())
    tb = C.time_bits(t)
    ab, pb, _ = C.context_code(t, x, y, p, W, H, slot, True)
    numba_total = float(tb.astype(np.float64).sum() + ab.astype(np.float64).sum() + pb.astype(np.float64).sum())
    print(f"events {n}  slots spanned {(t[-1] - t[0]) // slot + 1}")
    print(f"round trip exact: {ok}")
    print(f"bitstream bits   : {len(bits)}  ({len(bits) / n:.4f} bpe)")
    print(f"ideal (reference): {ideal:.1f}  ({ideal / n:.4f} bpe)  excess of bitstream {100 * (len(bits) / ideal - 1):.3f}%")
    print(f"ideal (numba)    : {numba_total:.1f}  ({numba_total / n:.4f} bpe)  rel. diff to reference {abs(numba_total - ideal) / ideal:.2e}")


if __name__ == "__main__":
    main()
