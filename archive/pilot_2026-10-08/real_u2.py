#!/usr/bin/env python3
"""Measure the companion project's actual U2 + zstd-1 payload (50 ms tiles) on the pilot recordings.
Imports sim.representations / sim.workload / sim.scene_bandwidth.payload from a read-only clone.
Usage: python3 -I real_u2.py <repo> <kind> <path> <name>"""
import json, lzma, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, sys.argv[1])
import numpy as np, zstandard as zstd
from io_events import load_evt2, load_txt
from sim.scene_bandwidth.payload import payload_bits
from sim.representations import RepresentationMode, encode_representation
from sim.workload import pack_array

kind, path, name = sys.argv[2], sys.argv[3], sys.argv[4]
t, x, y, p, _ = (load_evt2 if kind == "evt2" else load_txt)(path)
TILE = 50_000
w = (t - t[0]) // TILE
edges = np.flatnonzero(np.diff(w)) + 1
starts = np.concatenate(([0], edges)); ends = np.concatenate((edges, [len(t)]))
z1 = zstd.ZstdCompressor(level=1)
tot = dict(u2_raw=0, u2_zstd1=0, u2_xz=0, planes_zstd1=0, planes_xz=0, addr_only_zstd1=0)
n = 0
for s, e in zip(starts, ends):
    tr = (t[s:e] - (t[0] + w[s] * TILE)).astype(np.int64)
    xs, ys, ps = x[s:e].astype(np.int64), y[s:e].astype(np.int64), p[s:e].astype(np.int64)
    # canonical order of the companion project: (t, x, y)
    o = np.lexsort((ys, xs, tr)); tr, xs, ys, ps = tr[o], xs[o], ys[o], ps[o]
    canon = pack_array(tr, xs, ys, ps)
    u2 = encode_representation(canon, RepresentationMode.AER40_SOA_DT)
    assert payload_bits(tr, xs, ys, ps) == 8 * len(z1.compress(u2))
    tot["u2_raw"] += 8 * len(u2)
    tot["u2_zstd1"] += 8 * len(z1.compress(u2))
    tot["u2_xz"] += 8 * len(lzma.compress(u2, preset=9 | lzma.PRESET_EXTREME))
    dt = np.diff(tr, prepend=0).astype("<u4")
    planes = (dt.view(np.uint8).reshape(-1, 4).T.tobytes() + xs.astype("<u2").view(np.uint8).reshape(-1, 2).T.tobytes()
              + ys.astype("<u2").view(np.uint8).reshape(-1, 2).T.tobytes() + np.packbits(ps.astype(np.uint8)).tobytes())
    tot["planes_zstd1"] += 8 * len(z1.compress(planes))
    tot["planes_xz"] += 8 * len(lzma.compress(planes, preset=9 | lzma.PRESET_EXTREME))
    n += e - s
out = {"name": name, "events": int(n), "tiles": int(len(starts)), "events_per_tile_mean": n / len(starts),
       "bpe": {k: v / n for k, v in tot.items() if v}}
print(json.dumps(out, indent=1))
json.dump(out, open(f"out/real_u2_{name}.json", "w"), indent=1)
