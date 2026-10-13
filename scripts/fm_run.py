"""Directive 018: five families of schemes, four candidate fidelities and the tasks, on the groups of directive 016.

  python3 scripts/fm_run.py cache                       # the DSEC caches of directive 017 as memory-mapped arrays
  python3 scripts/fm_run.py run [--workers W]            # Section 5, resumable
  python3 scripts/fm_run.py one KEY                      # one task: DATASET|RECORDING|CHUNK
  python3 scripts/fm_run.py project                      # Section 7: from the first 20 groups of each dataset
  python3 scripts/fm_run.py determinism OUT.json         # acceptance check 3

Groups: ``fb_run.remake_groups(ds, "R", rid)``. Events of a group: ``[w T0 - FIT_WINDOW_US, (w + 11) T0)``.
eTraM events are read with ``bk_run.read`` once per task (at most READ_SLOTS reads at once), and the task keeps
only the range of its groups. DSEC events come from the caches that directive 017 wrote while reading each
sequence once under the read lock of directive 009 (``[(w - 3) T0, (w + 11) T0)`` per group, which contains
the range above); no DSEC event file is read again. Boxes: ``ec.regions.boxes_at`` with the tracks and the
time base of directive 017 (``rc_run.load_tracks``); squares: ``fb_run.squares_for`` of window w + 2.

CPU time of a group counts the ffmpeg processes it starts (``RUSAGE_CHILDREN``). Record decoding goes through
the decoders of ``ec.blockcodec_fast`` (``ec.codec.use_fast_decoders``). ``ec.families.window_sums`` is wrapped
from the runner to also return ``n_enter`` and ``n_blocks``, the blocks that enter Fsnr (Table 4); its other
outputs are unchanged.
"""
from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS",
           "VECLIB_MAXIMUM_THREADS", "NUMBA_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import argparse
import json
import pickle
import resource
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ec import blockcodec as bc, codec, families as fa, fbc, mp, regions as rg  # noqa: E402
import bk_run as BK  # noqa: E402
import fb_run as FB  # noqa: E402
import mp_measure as M  # noqa: E402
import rc_run as RC  # noqa: E402

codec.use_fast_decoders()
T0 = bc.T0_US
_WINDOW_SUMS = fa.window_sums


def _window_sums(tw, rec):
    """``ec.families.window_sums`` plus the number of blocks that enter Fsnr (Table 4), by its own rule."""
    out = _WINDOW_SUMS(tw, rec)
    r = tuple(np.asarray(a, dtype=np.int64) for a in rec)
    enter = (tw.blocks > tw.theta) | (fa.block_counts(r[1], r[2], tw.width, tw.height) > tw.theta)
    out["n_enter"], out["n_blocks"] = int(enter.sum()), int(len(enter))
    return out


fa.window_sums = _window_sums               # evaluate_group calls the module attribute: wrapped from the runner
FM_E = Path.home() / "prjs" / "event_coding" / "fm"
FM_D = RC.DR.BASE / "ds" / "fm"
WORK = Path.home() / "prjs" / "event_coding" / "fm_work"
CACHE = RC.CACHE_D
CHUNK = {"etram": 6, "dsec": 3}
READ_SLOTS_E = 6


def outdir(ds):
    return FM_E if ds == "etram" else FM_D


def cpu_now():
    c = resource.getrusage(resource.RUSAGE_CHILDREN)
    return time.process_time() + c.ru_utime + c.ru_stime


# ------------------------------------------------------------------------------------------- DSEC caches
def cache():
    """Each ``<rid>.npz`` of directive 017 as a directory of .npy files, for memory-mapped reads."""
    for rid in FB.recordings("dsec", "R"):
        d = CACHE / rid
        if (d / "DONE").exists():
            continue
        d.mkdir(parents=True, exist_ok=True)
        z = np.load(CACHE / f"{rid}.npz")
        for k in z.files:
            np.save(d / f"{k}.npy", z[k])
        (d / "DONE").write_text("ok\n")
        print(rid, {k: int(z[k].size) for k in ("w", "t")}, flush=True)


def dsec_events(rid, ws):
    """The events of the groups ``ws`` from the cache: (t, x, y, p) as int64 over the union of their ranges."""
    d = CACHE / rid
    W = np.load(d / "w.npy")
    n = np.load(d / "n.npy")
    off = np.concatenate(([0], np.cumsum(n)))
    arr = {k: np.load(d / f"{k}.npy", mmap_mode="r") for k in "txyp"}
    out = {}
    for w in ws:
        i = int(np.searchsorted(W, w))
        if i >= len(W) or W[i] != w:
            raise KeyError(f"{rid}: no cached events for w={w}")
        a, b = int(off[i]), int(off[i + 1])
        out[w] = tuple(np.asarray(arr[k][a:b], dtype=np.int64) for k in "txyp")
    return out


# ------------------------------------------------------------------------------------------- tasks
def plan():
    tasks = {"dsec": [], "etram": []}
    for ds in tasks:
        for rid in FB.recordings(ds, "R"):
            n = len(FB.remake_groups(ds, "R", rid))
            tasks[ds] += [f"{ds}|{rid}|{c}" for c in range(-(-n // CHUNK[ds]))]
    a, b = tasks["dsec"], tasks["etram"]                       # interleaved: the first finished groups hold both
    out = []
    for i in range(max(len(a), len(b))):
        out += ([a[i]] if i < len(a) else []) + ([b[i]] if i < len(b) else [])
    return out


def out_name(key):
    ds, rid, c = key.split("|")
    return f"{rid}_{int(c):03d}.pkl"


def task(key):
    ds, rid, ci = key.split("|")
    ci = int(ci)
    od = outdir(ds)
    out = od / out_name(key)
    if out.exists():
        return
    t_start, c_start = time.time(), cpu_now()
    rows = FB.remake_groups(ds, "R", rid)[ci * CHUNK[ds]:(ci + 1) * CHUNK[ds]]
    W, H = FB.DIMS[ds]
    if ds == "etram":
        lk = M._read_lock(od, slots=READ_SLOTS_E)
        ev = BK.read(rid)
        lk.close()
        t, x, y, p, toff = ev.t_us, ev.x, ev.y, ev.p, None
        evs = {}
        for r in rows:
            a, b = np.searchsorted(t, (r["w"] * T0 - fbc.FIT_WINDOW_US, (r["w"] + bc.N_TARGETS + 1) * T0))
            evs[r["w"]] = tuple(np.asarray(v[a:b], dtype=np.int64).copy() for v in (t, x, y, p))
        del ev, t, x, y, p
    else:
        toff = RC.t_offset_of(rid)
        evs = {}
        for w, e in dsec_events(rid, [r["w"] for r in rows]).items():
            a = np.searchsorted(e[0], w * T0 - fbc.FIT_WINDOW_US)
            evs[w] = tuple(v[a:] for v in e)
    read_s = time.time() - t_start
    tracks = RC.load_tracks(ds, rid, t_offset=toff)
    work = WORK / f"{rid}_{ci:03d}"
    work.mkdir(parents=True, exist_ok=True)
    res = []
    for r in rows:
        w, g = r["w"], r["group"]
        e = evs[w]
        boxes = None if tracks is None else {m: rg.boxes_at(tracks, w + m, W, H) for m in (1, 2, 3)}
        a, b = np.searchsorted(e[0], ((w + 2) * T0, (w + 3) * T0))
        squares = FB.squares_for(tuple(v[a:b] for v in e), W, H)
        c0, p0 = cpu_now(), time.perf_counter()
        o = fa.evaluate_group(e, w, W, H, g["records"], g, boxes=boxes, squares=squares, workdir=str(work))
        o.update({"j": r["j"], "cpu_s": cpu_now() - c0, "wall_s": time.perf_counter() - p0, "finished_utc": time.time()})
        res.append(o)
    work.rmdir()
    tmp = out.with_suffix(".tmp")
    with open(tmp, "wb") as f:
        pickle.dump({"key": key, "commit": (mp.REPO / "COMMIT").read_text().strip(), "decoders": codec.DECODERS,
                     "events_from": "bk_run.read" if ds == "etram" else "the cache of directive 017",
                     "groups": res, "read_s": read_s, "task_wall_s": time.time() - t_start,
                     "task_cpu_s": cpu_now() - c_start}, f, protocol=5)
    tmp.rename(out)


def load(ds, rid):
    out = []
    for f in sorted(outdir(ds).glob(f"{rid}_[0-9][0-9][0-9].pkl")):
        with open(f, "rb") as fh:
            out += pickle.load(fh)["groups"]
    out.sort(key=lambda r: r["j"])
    return out


def run(workers):
    state = FM_E
    for d in (FM_E, FM_D):
        (d / "logs").mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    if not (state / "plan.json").exists():
        (state / "plan.json").write_text(json.dumps({"commit": (mp.REPO / "COMMIT").read_text().strip(),
                                                     "chunk": CHUNK, "tasks": plan()}) + "\n")
    tasks = json.loads((state / "plan.json").read_text())["tasks"]
    done_f = lambda k: (outdir(k.split("|")[0]) / out_name(k)).exists()
    pending = [k for k in tasks if not done_f(k)]
    running, fails, t0, done = {}, {}, time.time(), len(tasks) - len(pending)
    log = lambda m: print(f"{time.strftime('%H:%M:%S')} {m}", flush=True)
    log(f"{len(pending)} of {len(tasks)} tasks pending")
    while pending or running:
        for pr, k in list(running.items()):
            if pr.poll() is None:
                continue
            del running[pr]
            if pr.returncode == 0 and done_f(k):
                done += 1
                log(f"[{done}/{len(tasks)}] {k} ok, running {len(running)}, t={time.time() - t0:.0f}s")
            else:
                fails[k] = fails.get(k, 0) + 1
                log(f"FAIL {k} rc={pr.returncode} (attempt {fails[k]})")
                if fails[k] < 2:
                    pending.append(k)
        if (state / "STOP").exists():
            pending = []
        target = M._target_workers(state, workers)
        while pending and len(running) < target and M._mem_available_gb() > 40.0:
            k = pending.pop(0)
            lf = open(outdir(k.split("|")[0]) / "logs" / f"{out_name(k)[:-4]}.log", "w")
            running[subprocess.Popen([sys.executable, __file__, "one", k], stdout=lf, stderr=subprocess.STDOUT)] = k
            time.sleep(1)
        time.sleep(10)
    log(f"DONE failed={sorted(k for k, v in fails.items() if v >= 2)}")


def project():
    res = {}
    for ds in ("etram", "dsec"):
        rows = []
        for f in outdir(ds).glob("*_[0-9][0-9][0-9].pkl"):
            with open(f, "rb") as fh:
                d = pickle.load(fh)
            rows += [(g["finished_utc"], g["cpu_s"]) for g in d["groups"]]
        rows.sort()
        first = [c for _, c in rows[:20]]
        ng = FB.n_groups(ds, "R")
        res[ds] = {"n_groups": ng, "n_done": len(rows), "n_first": len(first),
                   "mean_cpu_s": float(np.mean(first)) if first else None,
                   "cpu_h": float(np.mean(first)) * ng / 3600 if first else None}
    tot = sum(v["cpu_h"] for v in res.values()) if all(v["cpu_h"] for v in res.values()) else None
    out = {"projection": res, "cpu_h": tot, "limit_cpu_h": 600, "pass": tot is not None and tot <= 600}
    print(json.dumps(out, indent=1))
    return out


def determinism(out):
    """Acceptance check 3: the first group of five recordings of each dataset, hevc_code twice on its K = 4 frames
    at every QP; the two streams must be equal."""
    WORK.mkdir(parents=True, exist_ok=True)
    res = {"rule": "first group of the first five reporting recordings of each dataset; K = 4 frames; every QP; "
                   "hevc_code twice", "groups": [], "pass": True}
    for ds in ("etram", "dsec"):
        W, H = FB.DIMS[ds]
        for rid in FB.recordings(ds, "R")[:5]:
            r = FB.remake_groups(ds, "R", rid)[0]
            w = r["w"]
            if ds == "etram":
                ev = BK.read(rid)
                a, b = np.searchsorted(ev.t_us, (w * T0, (w + 4) * T0))
                e = tuple(np.asarray(v[a:b], dtype=np.int64) for v in (ev.t_us, ev.x, ev.y, ev.p))
                del ev
            else:
                e = dsec_events(rid, [w])[w]
            edges = np.searchsorted(e[0], [(w + m) * T0 for m in range(5)])
            win = [tuple(v[edges[m]:edges[m + 1]] for v in e) for m in range(4)]
            fr = fa.count_frames(win, w, 4, W, H)
            row = {"dataset": ds, "recording": rid, "w": w, "qp": {}}
            for qp in fa.HEVC_QPS:
                s1 = fa.hevc_code(fr, qp, str(WORK))[4]
                s2 = fa.hevc_code(fr, qp, str(WORK))[4]
                row["qp"][str(qp)] = {"equal": s1 == s2, "bytes": len(s1)}
                res["pass"] &= s1 == s2
            res["groups"].append(row)
            print(ds, rid, w, all(v["equal"] for v in row["qp"].values()), flush=True)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(res, indent=1) + "\n")
    print("pass", res["pass"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode")
    ap.add_argument("args", nargs="*")
    ap.add_argument("--workers", type=int, default=26)
    a = ap.parse_args()
    {"cache": cache, "run": lambda: run(a.workers), "one": lambda: task(*a.args), "project": project,
     "determinism": lambda: determinism(*a.args)}[a.mode]()


if __name__ == "__main__":
    main()
