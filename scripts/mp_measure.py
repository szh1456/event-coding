"""Directive 001, Section 6: Stage M with the reference ``ec.motion.evaluate_instant``, unchanged.

  python3 scripts/mp_measure.py cost OUTDIR [--per-rec N] [--workers W]   # timed sample, by box area
  python3 scripts/mp_measure.py run OUTDIR [--workers W]                  # every instant of every track >= 1 s

One task = one recording and a subset of its tracks. A task reads the recording
once with ``ec.baseline.read_events`` and writes ``instants_<rid>_<shard>.npz``:
one row per (instant, setting), scored or skipped, with the strata, every output
of ``evaluate_instant`` and the elapsed time of the call.
"""
from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS",
           "VECLIB_MAXIMUM_THREADS", "NUMBA_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import argparse
import json
import math
import multiprocessing as mpr
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ec import annotations, baseline, motion, mp  # noqa: E402

WIDTH, HEIGHT = 1280, 720
T2_US = 33_333
SETTINGS = ((100_000, 0), (100_000, 33_333), (100_000, 100_000), (100_000, 300_000), (50_000, 0), (200_000, 0))
MARGIN_PX = 2.0
VEHICLES = (1, 3, 4, 5, 6)
MODELS = ("static", "label", "cmax")
SPEED_EDGES = (0.0, 20.0, 100.0, 300.0, math.inf)


def speed_bin(s: float) -> int:
    for k in range(4):
        if SPEED_EDGES[k] <= s < SPEED_EDGES[k + 1]:
            return k
    return -1


def support_rect(track, t_e, T1, D):
    """The support rectangle of ``evaluate_instant`` (same formula), or None when it leaves the sensor."""
    w0, w1 = t_e + D, t_e + D + T2_US
    v = track.velocity(t_e, T1)
    bx, by, bw, bh = (float(a) for a in track.box(0.5 * (w0 + w1)))
    grow = MARGIN_PX + 0.5 * math.hypot(*v) * T2_US * 1e-6
    sx0 = max(0, int(math.floor(bx - grow))); sx1 = min(WIDTH - 1, int(math.ceil(bx + bw + grow)))
    sy0 = max(0, int(math.floor(by - grow))); sy1 = min(HEIGHT - 1, int(math.ceil(by + bh + grow)))
    return None if (sx1 < sx0 or sy1 < sy0) else (sx0, sx1, sy0, sy1)


def overlapping(track, others, t_e, rect) -> int:
    """1 if the support rectangle meets another track's interpolated box at ``t_e`` (tracks alive at t_e)."""
    if rect is None:
        return -1
    sx0, sx1, sy0, sy1 = rect
    for o in others:
        if o.track_id == track.track_id or not (o.t_first <= t_e <= o.t_last):
            continue
        bx, by, bw, bh = (float(a) for a in o.box(float(t_e)))
        if bx <= sx1 and bx + bw >= sx0 and by <= sy1 and by + bh >= sy0:
            return 1
    return 0


def inbox_future(ev, track, t_e, D) -> int:
    """In-box events of the future window: inside the track's interpolated box dilated by margin_px."""
    w0, w1 = t_e + D, t_e + D + T2_US
    a, b = np.searchsorted(ev.t_us, (w0, w1))
    return int(annotations.in_box_mask(track, ev.t_us[a:b], ev.x[a:b], ev.y[a:b], MARGIN_PX).sum())


def instant_rows(rid, ev, trs, sel_ids, instants_of=None):
    """All rows for the tracks ``sel_ids`` of one recording. ``instants_of(track)`` overrides the instant list."""
    light = mp.lighting(rid)
    rows = []
    for tr in trs:
        if tr.track_id not in sel_ids:
            continue
        inst = motion.evaluation_instants(tr) if instants_of is None else instants_of(tr)
        grp = "vehicles" if tr.class_id in VEHICLES else "other"
        for k, t_e in enumerate(inst):
            t_e = int(t_e)
            _, _, bw0, bh0 = (float(a) for a in tr.box(float(t_e)))
            for si, (T1, D) in enumerate(SETTINGS):
                rect = support_rect(tr, t_e, T1, D)
                sp = math.hypot(*tr.velocity(t_e, T1))
                t0 = time.perf_counter()
                r = motion.evaluate_instant(ev.t_us, ev.x, ev.y, ev.p, tr, t_e, T1, D, T2_US, WIDTH, HEIGHT,
                                            margin_px=MARGIN_PX, models=MODELS)
                el = time.perf_counter() - t0
                row = {"recording_id": rid, "lighting": light, "track_id": tr.track_id, "class_id": tr.class_id,
                       "group": grp, "instant_index": k, "t_e_us": t_e, "setting": si, "T1_us": T1, "D_us": D,
                       "box_area_te": bw0 * bh0, "speed_label_strata": sp, "speed_bin": speed_bin(sp),
                       "overlap": overlapping(tr, trs, t_e, rect), "support_px_strata":
                       -1 if rect is None else (rect[1] - rect[0] + 1) * (rect[3] - rect[2] + 1),
                       "inbox_future_events": inbox_future(ev, tr, t_e, D), "elapsed_s": el,
                       "skip": r.get("skipped", "")}
                row.update({k2: v for k2, v in r.items() if k2 != "skipped"})
                rows.append(row)
    return rows


def to_npz(rows, path):
    keys = sorted({k for r in rows for k in r})
    cols = {}
    for k in keys:
        vals = [r.get(k) for r in rows]
        if any(isinstance(v, str) for v in vals if v is not None):
            cols[k] = np.array(["" if v is None else str(v) for v in vals])
        else:
            cols[k] = np.array([np.nan if v is None else v for v in vals], dtype=np.float64)
    tmp = Path(str(path) + ".tmp.npz")
    np.savez_compressed(tmp, **cols)
    tmp.rename(path)


AREA_EDGES = (0.0, 1_000.0, 3_000.0, 10_000.0, 30_000.0, math.inf)
# mean cost of one instant (six settings, seconds on one cnt core) per box-area bin, from the cost probe
AREA_COST_S = (0.52, 1.41, 3.92, 14.7, 66.2)


def instant_cost(area: float) -> float:
    for k in range(5):
        if AREA_EDGES[k] <= area < AREA_EDGES[k + 1]:
            return AREA_COST_S[k]
    return AREA_COST_S[-1]


class _Slice:
    """Events of one contiguous time range. Every window evaluate_instant reads for a track lies in its life."""

    def __init__(self, ev, t_lo, t_hi):
        a, b = np.searchsorted(ev.t_us, (t_lo, t_hi + 1))
        self.t_us, self.x, self.y, self.p = (np.ascontiguousarray(v[a:b]) for v in (ev.t_us, ev.x, ev.y, ev.p))
        self.n_full = int(len(ev.t_us))

    def __len__(self):
        return int(len(self.t_us))


def _read_lock(outdir, slots=3):
    """Hold one of ``slots`` file locks while reading a recording, so few full reads overlap in memory."""
    import fcntl
    while True:
        for k in range(slots):
            f = open(Path(outdir) / f".read_lock_{k}", "w")
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return f
            except OSError:
                f.close()
        time.sleep(2)


def task(args):
    rid, shard, track_ids, outdir, mode, per_rec = args
    out = Path(outdir) / f"instants_{rid}_{shard:03d}.npz"
    if out.exists():
        return rid, shard, "exists", 0.0
    t0 = time.time()
    boxes = annotations.load_boxes(mp.annotation_path(rid))
    trs = annotations.tracks(boxes)
    lock = _read_lock(outdir) if mode == "run" else None
    ev = baseline.read_events(mp.event_path(rid))
    n_events = int(len(ev))
    if mode == "run":
        sel = [tr for tr in trs if tr.track_id in set(track_ids)]
        ev = _Slice(ev, min(tr.t_first for tr in sel), max(tr.t_last for tr in sel))
        lock.close()
    t_read = time.time() - t0
    instants_of = None
    if mode == "cost":
        # an even sample of instants over the recording's tracks, setting cost measured on all six settings
        allinst = [(tr.track_id, int(t)) for tr in trs for t in motion.evaluation_instants(tr)]
        pick = set(allinst[i] for i in np.unique(np.linspace(0, len(allinst) - 1, min(per_rec, len(allinst))).astype(int))) \
            if allinst else set()
        instants_of = lambda tr: np.array([t for (k, t) in allinst if k == tr.track_id and (k, t) in pick], dtype=np.int64)
        track_ids = {k for k, _ in pick}
    rows = instant_rows(rid, ev, trs, set(track_ids), instants_of)
    if rows:
        to_npz(rows, out)
    else:
        np.savez_compressed(out, empty=np.zeros(0))
    meta = {"rid": rid, "shard": shard, "n_rows": len(rows), "read_s": t_read, "wall_s": time.time() - t0,
            "n_events": n_events, "n_events_held": int(len(ev)), "track_ids": sorted(int(k) for k in track_ids)}
    (Path(outdir) / f"task_{rid}_{shard:03d}.json").write_text(json.dumps(meta) + "\n")
    return rid, shard, f"{len(rows)} rows {meta['wall_s']:.0f}s", meta["wall_s"]


def plan_run(ids, shard_s):
    """Shards of time-contiguous tracks (ordered by first frame) of about ``shard_s`` estimated seconds each."""
    tasks = []
    for rid in ids:
        trs = sorted((tr for tr in annotations.tracks(annotations.load_boxes(mp.annotation_path(rid)))
                      if len(motion.evaluation_instants(tr))), key=lambda tr: (tr.t_first, tr.track_id))
        cur, c, s = [], 0.0, 0
        for tr in trs:
            ct = sum(instant_cost(float(np.prod(tr.box(float(t))[2:]))) for t in motion.evaluation_instants(tr))
            if cur and c + ct > shard_s:
                tasks.append([rid, s, cur, c]); s += 1; cur, c = [], 0.0
            cur.append(tr.track_id); c += ct
        if cur:
            tasks.append([rid, s, cur, c])
    tasks.sort(key=lambda t: -t[3])          # longest first
    return tasks


def _target_workers(outdir, max_workers, physical=28):
    f = Path(outdir) / "WORKERS"
    if f.exists():
        try:
            return int(f.read_text().strip())
        except ValueError:
            pass
    n_sbc = 0
    for d in Path("/proc").iterdir():
        if d.name.isdigit():
            try:
                if b"sbc_sealed.py" in (d / "cmdline").read_bytes():
                    n_sbc += 1
            except OSError:
                pass
    if n_sbc:                                # the companion job: use only the physical cores it leaves idle
        return max(0, min(max_workers, physical - max(0, n_sbc - 1)))
    return max_workers


def _mem_available_gb():
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) / 1e6
    return 0.0


def schedule(out, max_workers, min_free_gb=40.0):
    """Dynamic pool: one subprocess per shard; width follows _target_workers; resumable by output file."""
    import subprocess
    tasks = json.loads((out / "plan.json").read_text())["tasks"]
    pending = [t for t in tasks if not (out / f"instants_{t[0]}_{t[1]:03d}.npz").exists()]
    running, fails, t0, done = {}, {}, time.time(), len(tasks) - len(pending)
    log = lambda m: print(f"{time.strftime('%H:%M:%S')} {m}", flush=True)
    log(f"{len(pending)} of {len(tasks)} shards pending")
    while pending or running:
        for pr, t in list(running.items()):
            rc = pr.poll()
            if rc is None:
                continue
            del running[pr]
            if rc == 0 and (out / f"instants_{t[0]}_{t[1]:03d}.npz").exists():
                done += 1
                log(f"[{done}/{len(tasks)}] {t[0]}#{t[1]} ok, running {len(running)}, t={time.time() - t0:.0f}s")
            else:
                k = f"{t[0]}#{t[1]}"
                fails[k] = fails.get(k, 0) + 1
                log(f"FAIL {k} rc={rc} (attempt {fails[k]})")
                if fails[k] < 2:
                    pending.append(t)
        target = _target_workers(out, max_workers)
        while pending and len(running) < target and _mem_available_gb() > min_free_gb:
            t = pending.pop(0)
            pr = subprocess.Popen([sys.executable, __file__, "one", str(out), t[0], str(t[1])],
                                  stdout=open(out / "logs" / f"{t[0]}_{t[1]:03d}.log", "w"), stderr=subprocess.STDOUT)
            running[pr] = t
            time.sleep(3)
        time.sleep(15)
    log(f"DONE failed={sorted(k for k, v in fails.items() if v >= 2)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("cost", "run", "one"))
    ap.add_argument("outdir")
    ap.add_argument("rid", nargs="?")
    ap.add_argument("shard", nargs="?", type=int)
    ap.add_argument("--workers", type=int, default=24)
    ap.add_argument("--per-rec", type=int, default=12)
    ap.add_argument("--ids", default="", help="comma-separated subset")
    ap.add_argument("--shard-s", type=float, default=1800.0, help="run mode: estimated seconds per shard")
    a = ap.parse_args()
    out = Path(a.outdir)
    if a.mode == "one":
        t = next(t for t in json.loads((out / "plan.json").read_text())["tasks"] if t[0] == a.rid and t[1] == a.shard)
        print(task((t[0], t[1], t[2], str(out), "run", 0))[2], flush=True)
        return
    ids, _ = mp.load_population()
    if a.ids:
        ids = [i for i in ids if i in set(a.ids.split(","))]
    if a.mode == "run":
        if (out / "plan.json").exists():
            if not (out / "RESUME").exists():
                sys.exit(f"{out} holds a run; touch {out}/RESUME to resume it")
        else:
            if out.exists() and any(out.iterdir()):
                sys.exit(f"{out} exists and is not empty; refusing to append")
            (out / "logs").mkdir(parents=True, exist_ok=True)
            tasks = plan_run(ids, a.shard_s)
            (out / "plan.json").write_text(json.dumps({
                "commit": (mp.REPO / "COMMIT").read_text().strip(), "shard_s": a.shard_s, "n_tasks": len(tasks),
                "est_cpu_h": sum(t[3] for t in tasks) / 3600, "tasks": tasks}) + "\n")
        schedule(out, a.workers)
        return
    if out.exists() and any(out.iterdir()):
        sys.exit(f"{out} exists and is not empty; refusing to append")
    out.mkdir(parents=True, exist_ok=True)
    tasks = [(rid, 0, [], str(out), "cost", a.per_rec) for rid in ids]
    t0 = time.time()
    with mpr.get_context("spawn").Pool(a.workers, maxtasksperchild=1) as pool:
        for k, (rid, s, msg, _) in enumerate(pool.imap_unordered(task, tasks), 1):
            print(f"[{k}/{len(tasks)}] {rid}#{s} {msg} t={time.time() - t0:.0f}s", flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
