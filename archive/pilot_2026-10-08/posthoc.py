#!/usr/bin/env python3
"""Post hoc analyses, run after the planned pilot (not part of the pre-stated plan).
1. C1 with finer age resolution (slot of 1 ms and 250 us instead of 4 ms).
2. Cost of events by pixel activity (low-rate pixels as a proxy for background and noise).
Usage: python3 -I posthoc.py <name> <kind> <path> <W> <H> <out.json>"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np

import coders as C
from io_events import load_evt2, load_txt

name, kind, path, W, H, out = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5]), sys.argv[6]
t, x, y, p, _ = (load_evt2 if kind == "evt2" else load_txt)(path)
n = len(t)
dur = (t[-1] - t[0]) / 1e6
N = W * H
tb = C.time_bits(t).astype(np.float64)
save, _ = C.order_free_saving_bits(t, x, y, p, W)
R = {"name": name, "n": n, "dur": dur, "slots": {}}
per_event = None
for slot in (4000, 1000, 250):
    ab, pb, cls = C.context_code(t, x, y, p, W, H, slot, True)
    tot = tb + ab + pb
    fresh = (cls % C.NB == 0)
    R["slots"][slot] = {"bpe": float(tot.mean()), "bpe_tie_order_free": float(tot.mean() - save / n),
                        "address": float(ab.mean()), "polarity": float(pb.mean()), "time": float(tb.mean()),
                        "share_events_nbr_fresh": float(fresh.mean()),
                        "bpe_nbr_fresh": float(tot[fresh].mean()), "bpe_rest": float(tot[~fresh].mean())}
    if slot == 4000:
        per_event = tot
    print(slot, R["slots"][slot], flush=True)

# pixel-activity split (slot 4 ms code lengths)
u = y.astype(np.int64) * W + x
cnt = np.bincount(u, minlength=N)
R["pixels_never_fired"] = float((cnt == 0).mean())
R["pixel_count_quantiles"] = {str(q): float(np.quantile(cnt, q)) for q in (0.1, 0.25, 0.5, 0.75, 0.9, 0.99, 0.999)}
groups = []
for lo, hi in ((1, 1), (2, 5), (6, 20), (21, 100), (101, 10 ** 9)):
    pix = (cnt >= lo) & (cnt <= hi)
    ev = pix[u]
    if ev.sum() == 0:
        continue
    rate = cnt[pix].mean() / dur
    groups.append({"events_per_pixel": [lo, hi if hi < 10 ** 9 else None], "share_pixels": float(pix.mean()),
                   "share_events": float(ev.mean()), "share_bits": float(per_event[ev].sum() / per_event.sum()),
                   "c1_bpe": float(per_event[ev].mean()), "mean_rate_hz": float(rate),
                   "eq2_plus_1bit": C.poisson_bits(rate, 1e-6) + 1.0})
R["by_pixel_activity"] = groups
for g in groups:
    print(g)
json.dump(R, open(out, "w"), indent=1)
