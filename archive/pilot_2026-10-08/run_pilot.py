#!/usr/bin/env python3
"""Pilot runner. Usage: python3 -I run_pilot.py <name> <kind> <path> <W> <H> <out.json> [--sweep]"""
import json
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np

import coders as C
from io_events import load_evt2, load_txt

SLOT_US = 4000


def main():
    name, kind, path, W, H, out = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5]), sys.argv[6]
    sweep = "--sweep" in sys.argv
    if kind == "evt2":
        t, x, y, p, info = load_evt2(path)
        native_bytes = info["payload_bytes"]
    else:
        t, x, y, p, info = load_txt(path)
        native_bytes = None
    n = len(t)
    assert x.max() < W and y.max() < H and (np.diff(t) >= 0).all()
    dur = (t[-1] - t[0]) / 1e6
    N = W * H
    R = {"name": name, "n_events": n, "duration_s": dur, "rate_ev_s": n / dur, "W": W, "H": H,
         "on_fraction": float(p.mean()), "tie_fraction": float((np.diff(t) == 0).mean()),
         "mean_pixel_rate_hz": n / dur / N}
    cnt = np.bincount(y.astype(np.int64) * W + x, minlength=N)
    R["active_pixels"] = int((cnt > 0).sum())
    top = np.sort(cnt)[::-1]
    k = max(1, N // 1000)
    R["share_events_top_0.1pct_pixels"] = float(top[:k].sum() / n)
    R["max_pixel_rate_hz"] = float(top[0] / dur)

    bpe = {}
    bpe["AER40"] = 40.0
    if native_bytes:
        bpe["native EVT2 file"] = native_bytes * 8 / n
    # --- generic baselines, stream order
    t0 = time.time()
    u2 = C.u2_arrays(t, x, y, p)
    for k_, v in C.generic_sizes(u2, "U2").items():
        bpe[k_] = v * 8 / n
    bpe["U2+zstd-1 (64k-event chunks)"] = C.u2_chunked_zstd1(t, x, y, p) * 8 / n
    tc, xc, yc, pc = C.canonical_order(t, x, y, p)
    u2c = C.u2_arrays(tc, xc, yc, pc)
    for k_, v in C.generic_sizes(u2c, "U2 canonical").items():
        bpe[k_] = v * 8 / n
    for k_, v in C.generic_sizes(C.u2_shuffled(t, x, y, p), "U2 byte-planes").items():
        bpe[k_] = v * 8 / n
    for k_, v in C.generic_sizes(C.u2_shuffled(tc, xc, yc, pc), "U2 byte-planes canonical").items():
        bpe[k_] = v * 8 / n
    a64 = C.aos64(t, x, y, p)
    for k_, v in C.generic_sizes(a64, "AoS64").items():
        bpe[k_] = v * 8 / n
    R["t_generic_s"] = time.time() - t0

    # --- models
    t0 = time.time()
    tb = C.time_bits(t)
    pb0 = C.polarity_order0_bits(p)
    R["time_bits"] = float(tb.mean())
    R["polarity_order0_bits"] = float(pb0.mean())
    bpe["M0 uniform address"] = float(tb.mean() + math.log2(N) + pb0.mean())
    best = None
    for alpha in (0.5, 0.05, 0.005):
        rb = C.ratemap_bits(x, y, W, H, alpha)
        if best is None or rb.mean() < best[1]:
            best = (alpha, float(rb.mean()))
    R["M1_alpha"], R["M1_address_bits"] = best
    bpe["M1 adaptive rate map"] = float(tb.mean() + best[1] + pb0.mean())
    R["M1star_address_bits"] = C.empirical_address_entropy(x, y, W, H)
    bpe["M1* empirical rate map (not causal)"] = float(tb.mean() + R["M1star_address_bits"] + pb0.mean())
    ab2, pb2, _ = C.context_code(t, x, y, p, W, H, SLOT_US, False)
    bpe["M2 self-age context"] = float(tb.mean() + ab2.mean() + pb2.mean())
    R["M2_fields"] = [float(tb.mean()), float(ab2.mean()), float(pb2.mean())]
    ab, pb, cls = C.context_code(t, x, y, p, W, H, SLOT_US, True)
    c1 = tb.astype(np.float64) + ab + pb
    bpe["C1 context coder"] = float(c1.mean())
    R["C1_fields"] = {"time": float(tb.mean()), "address": float(ab.mean()), "polarity": float(pb.mean())}
    save, ndup = C.order_free_saving_bits(t, x, y, p, W)
    R["order_free_saving_bpe"] = save / n
    R["duplicate_event_groups"] = ndup
    bpe["C1, original order minus tie-order bits (optimistic)"] = float(c1.mean() - save / n)
    ts_, xs_, ys_, ps_ = C.shuffle_within_ties(t, x, y, p)
    abs_, pbs_, _ = C.context_code(ts_, xs_, ys_, ps_, W, H, SLOT_US, True)
    bpe["C1 multiset (random tie order, bits-back)"] = float(tb.mean() + abs_.mean() + pbs_.mean() - save / n)
    R["t_models_s"] = time.time() - t0
    R["poisson_eq2_uniform_bits"] = C.poisson_bits(n / dur / N, 1e-6)

    # --- class breakdown of C1
    rows = []
    for c in range(C.NC):
        m = cls == c
        if m.sum() == 0:
            continue
        rows.append({"self": int(c // C.NB), "nbr": int(c % C.NB), "share_events": float(m.mean()),
                     "share_bits": float(c1[m].sum() / c1.sum()), "addr_bits": float(ab[m].mean()),
                     "total_bits": float(c1[m].mean())})
    R["C1_classes"] = rows
    iso = (cls // C.NB >= 4) & (cls % C.NB >= 4)   # nothing at the pixel or its neighbors for 64 ms
    R["isolated64ms"] = {"share_events": float(iso.mean()), "share_bits": float(c1[iso].sum() / c1.sum()),
                         "bits_per_event": float(c1[iso].mean()) if iso.any() else None,
                         "bits_per_event_others": float(c1[~iso].mean())}
    iso1 = (cls // C.NB == 6) & (cls % C.NB == 6)
    R["isolated1s"] = {"share_events": float(iso1.mean()), "share_bits": float(c1[iso1].sum() / c1.sum()),
                       "bits_per_event": float(c1[iso1].mean()) if iso1.any() else None}
    R["bpe"] = bpe

    # --- timestamp resolution sweep
    if sweep:
        S = []
        for D in (1, 10, 100, 1000, 10000):
            tq = t // D
            tcq, xcq, ycq, pcq = C.canonical_order(tq, x, y, p)
            buf = C.u2_shuffled(tcq, xcq, ycq, pcq)
            import zstandard as zstd, lzma
            z1 = len(zstd.ZstdCompressor(level=1).compress(buf)) * 8 / n
            z19 = len(zstd.ZstdCompressor(level=19).compress(buf)) * 8 / n
            xz = len(lzma.compress(buf, preset=9 | lzma.PRESET_EXTREME)) * 8 / n
            tbq = C.time_bits(tq)
            abq, pbq, _ = C.context_code(tq, x, y, p, W, H, max(1, SLOT_US // D), True)
            sv, _ = C.order_free_saving_bits(tq, x, y, p, W)
            seq = float(tbq.mean() + abq.mean() + pbq.mean())
            tsq, xsq, ysq, psq = C.shuffle_within_ties(tq, x, y, p)
            absq, pbsq, _ = C.context_code(tsq, xsq, ysq, psq, W, H, max(1, SLOT_US // D), True)
            ms = float(tbq.mean() + absq.mean() + pbsq.mean() - sv / n)
            S.append({"delta_us": D, "U2planes-canon+zstd-1": z1, "U2planes-canon+zstd-19": z19, "U2planes-canon+xz-9e": xz,
                      "C1 sequence": seq, "C1 multiset (bits-back)": ms, "tie_order_bits": sv / n,
                      "C1 fields": [float(tbq.mean()), float(abq.mean()), float(pbq.mean())],
                      "tie_fraction": float((np.diff(tq) == 0).mean()),
                      "poisson_eq2_uniform": C.poisson_bits(n / dur / N, D * 1e-6)})
        R["sweep"] = S
    with open(out, "w") as f:
        json.dump(R, f, indent=1)
    print(json.dumps({k: v for k, v in R.items() if k not in ("C1_classes", "sweep")}, indent=1))
    if sweep:
        for s in R["sweep"]:
            print(s)


if __name__ == "__main__":
    main()
