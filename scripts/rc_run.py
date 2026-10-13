"""Directive 017: what the regions of REMAKE hold, and the event spacing of the regions.

  python3 scripts/rc_run.py labels OUT.json               # Section 4: the time base of the DSEC labels
  python3 scripts/rc_run.py run [--workers W]             # Section 5, resumable: one task per recording
  python3 scripts/rc_run.py one DATASET RECORDING          # one task
  python3 scripts/rc_run.py project                        # Section 7: from the first 20 groups of each dataset

Groups: those of directive 016, Section 7 (``fb_run.remake_groups(ds, "R", rid)``). One task reads one
recording once (eTraM: ``bk_run.read``; DSEC: ``ds_run.read`` under the read lock and memory wait of
directive 009, so DSEC reads are one at a time) and runs ``ec.regions.evaluate_group`` on all its groups.
Outputs: ``~/prjs/event_coding/rc/<rid>.pkl`` (eTraM) and ``/data/<user>/event_coding/ds/rc/<rid>.pkl`` (DSEC).

The DSEC tasks also keep the events of every group, ``[(w - 3) T0, (w + 11) T0)``, in
``/data/<user>/event_coding/ds/cache/<rid>.npz``: directive 018 needs a sub-range of them,
``[w T0 - 50 ms, (w + 11) T0)``, and reads them there instead of reading each sequence again.

Record decoding goes through the decoders of ``ec.blockcodec_fast`` (``ec.codec.use_fast_decoders``),
which equal the reference on every Stage 0 stream.
"""
from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS",
           "VECLIB_MAXIMUM_THREADS", "NUMBA_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import argparse
import json
import pickle
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ec import annotations as an, blockcodec as bc, codec, mp, regions as rg  # noqa: E402
import bk_run as BK  # noqa: E402
import ds_run as DR  # noqa: E402
import fb_run as FB  # noqa: E402
import mp_measure as M  # noqa: E402

codec.use_fast_decoders()
T0 = bc.T0_US
RC_E = Path.home() / "prjs" / "event_coding" / "rc"
RC_D = DR.BASE / "ds" / "rc"
CACHE_D = DR.BASE / "ds" / "cache"
DET = DR.BASE / "dsec_det"
LABELS = mp.REPO / "results" / "rc" / "labels_check.json"
DIMS = FB.DIMS
N_LABEL_SEQ, N_LABEL_WIN = 5, 20
RING = (5, 15)


def outdir(ds):
    return RC_E if ds == "etram" else RC_D


# ------------------------------------------------------------------------------------------- labels
def load_tracks(ds, rid, convention=None, t_offset=None):
    """Tracks of a recording: eTraM train annotations; DSEC ``tracks.npy`` with the time base of Section 4."""
    if ds == "etram":
        return an.tracks(an.load_boxes(mp.annotation_path(rid)))
    path = DET / rid / "tracks.npy"
    if not path.is_file():
        return None
    a = an.load_boxes(path)
    if convention is None:
        convention = json.loads(LABELS.read_text())["convention"]
    if convention == "minus_t_offset":
        if t_offset is None:
            raise ValueError("t_offset needed")
        b = np.empty(len(a), dtype=[(n, (np.int64 if n == "t" else a.dtype[n])) for n in a.dtype.names])
        for n in a.dtype.names:
            b[n] = a[n]
        b["t"] = a["t"].astype(np.int64) - int(t_offset)
        a = b
    return an.tracks(a)


def t_offset_of(rid):
    import h5py
    import hdf5plugin  # noqa: F401
    with h5py.File(DR.DATA / rid / "events.h5", "r") as f:
        return int(np.asarray(f["t_offset"][()]).reshape(-1)[0])


def labels(out):
    """Section 4: the density inside each box over that of the ring 5 to 15 px around it, two time bases."""
    W, H = DIMS["dsec"]
    seqs = [r for r in FB.recordings("dsec", "R") if (DET / r / "tracks.npy").is_file()][:N_LABEL_SEQ]
    res = {"directive": "017", "sequences": {}, "rule": "per box: (events of the key window in the box / box area) "
           "/ (events in the ring 5 to 15 px around the box / ring area), the box and ring clipped to the sensor; "
           "the first 20 key windows of each sequence; the convention with the larger median over all boxes"}
    pooled = {"as_stored": [], "minus_t_offset": []}
    for rid in seqs:
        ws = [r["w"] for r in FB.remake_groups("dsec", "R", rid)][:N_LABEL_WIN]
        t, x, y, p, info = DR.read(rid, RC_D)
        toff = info["t_offset_us"]
        row = {"t_offset_us": toff, "key_windows": ws}
        for conv in pooled:
            trk = load_tracks("dsec", rid, conv, toff)
            ratios = []
            for w in ws:
                a, b = np.searchsorted(t, (w * T0, (w + 1) * T0))
                ex, ey = np.asarray(x[a:b], dtype=np.int64), np.asarray(y[a:b], dtype=np.int64)
                occ = np.zeros((H, W), dtype=np.int64)
                np.add.at(occ, (ey, ex), 1)
                for _, box in rg.boxes_at(trk, w, W, H):
                    inside = rg.box_mask([box], W, H, 0)
                    ring = rg.box_mask([box], W, H, RING[1]) & ~rg.box_mask([box], W, H, RING[0])
                    if not inside.any() or not ring.any():
                        continue
                    d_in, d_ring = occ[inside].sum() / inside.sum(), occ[ring].sum() / ring.sum()
                    ratios.append(float(d_in / d_ring) if d_ring > 0 else float("inf"))
            row[conv] = {"n_boxes": len(ratios), "median_ratio": float(np.median(ratios)) if ratios else None}
            pooled[conv] += ratios
        res["sequences"][rid] = row
        del t, x, y, p
        print(rid, {c: row[c] for c in pooled}, flush=True)
    med = {c: (float(np.median(v)) if v else None) for c, v in pooled.items()}
    conv = max(med, key=lambda c: -1.0 if med[c] is None else med[c])
    res.update({"median_ratio": med, "n_boxes": {c: len(v) for c, v in pooled.items()}, "convention": conv,
                "pass": med[conv] is not None and med[conv] >= 2.0})
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps({k: res[k] for k in ("median_ratio", "n_boxes", "convention", "pass")}))


# ------------------------------------------------------------------------------------------- one recording
def task(ds, rid):
    od = outdir(ds)
    out = od / f"{rid}.pkl"
    if out.exists():
        return
    t_start, c_start = time.time(), time.process_time()
    rows = FB.remake_groups(ds, "R", rid)
    W, H = DIMS[ds]
    if ds == "etram":
        ev = BK.read(rid)
        t, x, y, p, toff = ev.t_us, ev.x, ev.y, ev.p, None
    else:
        t, x, y, p, info = DR.read(rid, od)
        toff = info["t_offset_us"]
    read_s = time.time() - t_start
    full = (t, x, y, p)
    slices = {}
    for r in rows:
        w = r["w"]
        a, b = np.searchsorted(t, (max(0, w - rg.SPAN_BEFORE) * T0, (w + bc.N_TARGETS + 1) * T0))
        slices[w] = tuple(np.asarray(v[a:b], dtype=np.int64).copy() for v in full)
    del t, x, y, p, full
    if ds == "dsec":
        CACHE_D.mkdir(parents=True, exist_ok=True)
        ws = sorted(slices)
        n = [len(slices[w][0]) for w in ws]
        tmp = CACHE_D / f"{rid}.tmp.npz"
        np.savez(tmp, w=np.array(ws, dtype=np.int64), n=np.array(n, dtype=np.int64),
                 lo=np.array([max(0, w - rg.SPAN_BEFORE) * T0 for w in ws], dtype=np.int64),
                 t=np.concatenate([slices[w][0] for w in ws]),
                 x=np.concatenate([slices[w][1] for w in ws]).astype(np.uint16),
                 y=np.concatenate([slices[w][2] for w in ws]).astype(np.uint16),
                 p=np.concatenate([slices[w][3] for w in ws]).astype(np.uint8))
        tmp.rename(CACHE_D / f"{rid}.npz")
    tracks = load_tracks(ds, rid, t_offset=toff)
    res = []
    for r in rows:
        w, g = r["w"], r["group"]
        et, ex, ey, ep = slices[w]
        edges = np.searchsorted(et, [(w + m) * T0 for m in range(bc.N_TARGETS + 2)])
        windows = [tuple(v[edges[m]:edges[m + 1]] for v in (et, ex, ey, ep)) for m in range(bc.N_TARGETS + 1)]
        before = tuple(v[:edges[0]] for v in (et, ex, ey, ep))
        boxes = None if tracks is None else [[b for _, b in rg.boxes_at(tracks, w + m, W, H)] for m in range(4)]
        c0, p0 = time.process_time(), time.perf_counter()
        o = rg.evaluate_group(windows, g["records"], w, W, H, g, boxes=boxes, before=before)
        o.update({"j": r["j"], "cpu_s": time.process_time() - c0, "wall_s": time.perf_counter() - p0,
                  "finished_utc": time.time()})
        res.append(o)
    tmp = out.with_suffix(".tmp")
    with open(tmp, "wb") as f:
        pickle.dump({"dataset": ds, "recording": rid, "commit": (mp.REPO / "COMMIT").read_text().strip(),
                     "codec_decoders": codec.DECODERS, "has_labels": tracks is not None, "groups": res,
                     "read_s": read_s, "task_wall_s": time.time() - t_start,
                     "task_cpu_s": time.process_time() - c_start}, f, protocol=5)
    tmp.rename(out)


def load(ds, rid):
    with open(outdir(ds) / f"{rid}.pkl", "rb") as f:
        return pickle.load(f)


# ------------------------------------------------------------------------------------------- scheduler
def run(workers, dsec_max):
    state = RC_E
    for d in (RC_E, RC_D):
        (d / "logs").mkdir(parents=True, exist_ok=True)
    # the largest recordings first, DSEC interleaved: DSEC reads are serialized and set the wall time
    keys = [("dsec", r) for r in FB.recordings("dsec", "R")] + [("etram", r) for r in FB.recordings("etram", "R")]
    done_f = lambda k: (outdir(k[0]) / f"{k[1]}.pkl").exists()
    pending = [k for k in keys if not done_f(k)]
    running, fails, t0, done = {}, {}, time.time(), len(keys) - len(pending)
    log = lambda m: print(f"{time.strftime('%H:%M:%S')} {m}", flush=True)
    log(f"{len(pending)} of {len(keys)} recordings pending")
    while pending or running:
        for pr, k in list(running.items()):
            if pr.poll() is None:
                continue
            del running[pr]
            if pr.returncode == 0 and done_f(k):
                done += 1
                log(f"[{done}/{len(keys)}] {k[0]} {k[1]} ok, running {len(running)}, t={time.time() - t0:.0f}s")
            else:
                fails[k] = fails.get(k, 0) + 1
                log(f"FAIL {k} rc={pr.returncode} (attempt {fails[k]})")
                if fails[k] < 2:
                    pending.append(k)
        if (state / "STOP").exists():
            pending = []
        target = M._target_workers(state, workers)
        while pending and len(running) < target and M._mem_available_gb() > 40.0:
            n_d = sum(k[0] == "dsec" for k in running.values())
            nxt = next((k for k in pending if k[0] != "dsec" or n_d < dsec_max), None)
            if nxt is None:
                break
            pending.remove(nxt)
            lf = open(outdir(nxt[0]) / "logs" / f"{nxt[1]}.log", "w")
            running[subprocess.Popen([sys.executable, __file__, "one", nxt[0], nxt[1]], stdout=lf,
                                     stderr=subprocess.STDOUT)] = nxt
            time.sleep(1)
        time.sleep(5)
    log(f"DONE failed={sorted(k for k, v in fails.items() if v >= 2)}")


def project():
    """Section 7: CPU per group of each dataset from its first 20 finished groups, times its number of groups;
    the per-recording read time is added from the finished tasks."""
    res = {}
    for ds in ("etram", "dsec"):
        rows, reads = [], []
        for rid in FB.recordings(ds, "R"):
            f = outdir(ds) / f"{rid}.pkl"
            if f.exists():
                d = load(ds, rid)
                rows += [(g["finished_utc"], g["cpu_s"]) for g in d["groups"]]
                reads.append(d["task_cpu_s"] - sum(g["cpu_s"] for g in d["groups"]))
        rows.sort()
        first = [c for _, c in rows[:20]]
        ng = FB.n_groups(ds, "R")
        nr = len(FB.recordings(ds, "R"))
        res[ds] = {"n_groups": ng, "n_first": len(first), "mean_cpu_s": float(np.mean(first)) if first else None,
                   "mean_read_cpu_s_per_recording": float(np.mean(reads)) if reads else None,
                   "cpu_h": (float(np.mean(first)) * ng + (float(np.mean(reads)) if reads else 0.0) * nr) / 3600
                   if first else None}
    tot = sum(v["cpu_h"] for v in res.values()) if all(v["cpu_h"] is not None for v in res.values()) else None
    res = {"projection": res, "cpu_h": tot, "limit_cpu_h": 60, "pass": tot is not None and tot <= 60}
    print(json.dumps(res, indent=1))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode")
    ap.add_argument("args", nargs="*")
    ap.add_argument("--workers", type=int, default=24)
    ap.add_argument("--dsec-max", type=int, default=6)
    a = ap.parse_args()
    {"labels": lambda: labels(*a.args), "run": lambda: run(a.workers, a.dsec_max), "one": lambda: task(*a.args),
     "project": project}[a.mode]()


if __name__ == "__main__":
    main()
