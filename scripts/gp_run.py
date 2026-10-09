"""Directive 003, Sections 6 and 7: Stage C (groups) and Stage S (share of events in boxes), one pass.

  python3 scripts/gp_run.py probe OUTDIR [--workers W]   # 50 timed instants (ten targets each), no Stage S
  python3 scripts/gp_run.py cost RGDIR OUT.json           # project the cost from the probe
  python3 scripts/gp_run.py run OUTDIR [--workers W]     # every instant; resumable
  python3 scripts/gp_run.py one OUTDIR KEY               # one task (called by run)

Stage C uses ``ec.gop.evaluate_target`` unchanged, for every instant that
directive 001 scored at setting (100, 0) and the targets m = 1 to 10, one task per
shard of directive 001 (same tracks). The task for shard 0 of a recording also
computes Stage S on the recording's full event array, before the events are cut
to the shard's track lives (which leaves every Stage C result unchanged).
"""
from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS",
           "VECLIB_MAXIMUM_THREADS", "NUMBA_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import argparse
import glob
import json
import math
import multiprocessing as mpr
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ec import annotations, baseline, gop, motion, mp  # noqa: E402
import mp_measure as M  # noqa: E402

MP_RUN = Path.home() / "prjs" / "event_coding" / "mp" / "run"
WIDTH, HEIGHT = 1280, 720
T1_US, T2_US, MARGIN_PX = 100_000, 33_333, 2.0
TARGETS = tuple(range(1, gop.N_TARGETS + 1))
VEHICLES = (1, 3, 4, 5, 6)
STRATA_COLS = ("recording_id", "lighting", "track_id", "class_id", "group", "t_e_us", "setting",
               "speed_bin", "speed_label_strata", "overlap", "box_area_te")
READ_SLOTS = 6
S_US, S_WIN_US, S_MID_US, S_DIL_PX = 1_000_000, 33_333, 16_666, 2.0


def mp_plan():
    return json.loads((MP_RUN / "plan.json").read_text())["tasks"]


def mp_rows(rid, shard):
    return dict(np.load(MP_RUN / f"instants_{rid}_{shard:03d}.npz"))


def c_instants(z):
    """Stage C instants of one 001 file: scored at setting (100, 0)."""
    if "setting" not in z:
        return np.zeros(0, dtype=np.int64)
    return np.flatnonzero((z["skip"] == "") & (z["setting"] == 0))


# ----------------------------------------------------------------------------- Stage S
def share_sums(rid, ev, trs) -> dict:
    """Section 7 sums for one recording, from its full event array."""
    t_first, t_last = int(ev.t_us[0]), int(ev.t_us[-1])
    j = math.ceil(t_first / S_US)
    long_ = {tr.track_id for tr in trs if tr.t_last - tr.t_first >= 1_000_000}
    veh = {tr.track_id for tr in trs if tr.track_id in long_ and tr.class_id in VEHICLES}
    s = {k: 0 for k in ("windows", "events", "events_A", "events_L", "events_V", "pixels_A", "pixels_L", "pixels_V",
                        "windows_empty_A", "events_empty_A")}
    while j * S_US + S_WIN_US - 1 <= t_last:        # the window [u0, u0 + 33,333) lies inside [t_first, t_last]
        u0 = j * S_US
        a, b = np.searchsorted(ev.t_us, (u0, u0 + S_WIN_US))
        ex, ey = ev.x[a:b], ev.y[a:b]
        tj = u0 + S_MID_US
        masks = {k: np.zeros((HEIGHT, WIDTH), dtype=bool) for k in "ALV"}
        for tr in trs:
            if not (tr.t_first <= tj <= tr.t_last):
                continue
            bx, by, bw, bh = (float(v) for v in tr.box(float(tj)))
            c0, c1 = max(0, math.ceil(bx - S_DIL_PX)), min(WIDTH - 1, math.floor(bx + bw + S_DIL_PX))
            r0, r1 = max(0, math.ceil(by - S_DIL_PX)), min(HEIGHT - 1, math.floor(by + bh + S_DIL_PX))
            if c1 < c0 or r1 < r0:
                continue
            masks["A"][r0:r1 + 1, c0:c1 + 1] = True
            if tr.track_id in long_:
                masks["L"][r0:r1 + 1, c0:c1 + 1] = True
            if tr.track_id in veh:
                masks["V"][r0:r1 + 1, c0:c1 + 1] = True
        n = int(b - a)
        s["windows"] += 1
        s["events"] += n
        for k in "ALV":
            s[f"events_{k}"] += int(masks[k][ey, ex].sum())
            s[f"pixels_{k}"] += int(masks[k].sum())
        if not masks["A"].any():
            s["windows_empty_A"] += 1
            s["events_empty_A"] += n
        j += 1
    return {"recording_id": rid, "lighting": mp.lighting(rid), "t_first_us": t_first, "t_last_us": t_last,
            "sensor_pixels": WIDTH * HEIGHT, **s}


# ----------------------------------------------------------------------------- Stage C
def task(rid, shard, outdir, only=None, tag=None, stage_s=None):
    tag = tag or f"{rid}_{shard:03d}"
    out = Path(outdir) / f"rows_{tag}.npz"
    if out.exists():
        return 0
    stage_s = (shard == 0) if stage_s is None else stage_s
    t0 = time.time()
    z = mp_rows(rid, shard)
    idx = c_instants(z) if only is None else np.asarray(only, dtype=np.int64)
    trs = annotations.tracks(annotations.load_boxes(mp.annotation_path(rid)))
    trk = {tr.track_id: tr for tr in trs}
    rows, t_read, t_s = [], 0.0, 0.0
    if len(idx) or stage_s:
        lk = M._read_lock(outdir, slots=READ_SLOTS)
        ev = baseline.read_events(mp.event_path(rid))
        t_read = time.time() - t0
        if stage_s:
            t1 = time.time()
            (Path(outdir) / f"share_{rid}.json").write_text(json.dumps(share_sums(rid, ev, trs)) + "\n")
            t_s = time.time() - t1
        sl = None
        if len(idx):
            need = [trk[int(k)] for k in np.unique(z["track_id"][idx])]
            sl = M._Slice(ev, min(tr.t_first for tr in need), max(tr.t_last for tr in need))
        del ev
        lk.close()
        for i in idx:
            tr = trk[int(z["track_id"][i])]
            te = int(z["t_e_us"][i])
            v = (float(z["cmax_vx"][i]), float(z["cmax_vy"][i]))
            for m in TARGETS:
                t1 = time.perf_counter()
                r = gop.evaluate_target(sl.t_us, sl.x, sl.y, sl.p, tr, te, m, T2_US, WIDTH, HEIGHT, v,
                                        T1_us=T1_US, margin_px=MARGIN_PX, sizes=True)
                el = time.perf_counter() - t1
                row = {c: z[c][i].item() for c in STRATA_COLS}
                row.update({"mp_shard": shard, "mp_index": int(i), "target": m, "lead_us": gop.lead_us(m),
                            "elapsed_s": el, "skip": r.get("skipped", "")})
                row.update({k: val for k, val in r.items() if k not in ("skipped", "m")})
                rows.append(row)
    M.to_npz(rows, out) if rows else np.savez_compressed(out, empty=np.zeros(0))
    (Path(outdir) / f"task_{tag}.json").write_text(json.dumps(
        {"rid": rid, "shard": shard, "n_instants": int(len(idx)), "n_rows": len(rows), "read_s": t_read,
         "stage_s_s": t_s, "wall_s": time.time() - t0}) + "\n")
    return len(rows)


# ----------------------------------------------------------------------------- scheduling
def _out_name(key):
    rid, s = key.split("|")
    return f"rows_{rid}_{int(s):03d}.npz"


def schedule(out, max_workers, min_free_gb=40.0):
    tasks = json.loads((out / "plan.json").read_text())["tasks"]
    pending = [t for t in tasks if not (out / _out_name(t[0])).exists()]
    running, fails, t0, done = {}, {}, time.time(), len(tasks) - len(pending)
    log = lambda m: print(f"{time.strftime('%H:%M:%S')} {m}", flush=True)
    log(f"{len(pending)} of {len(tasks)} tasks pending")
    while pending or running:
        for pr, t in list(running.items()):
            rc = pr.poll()
            if rc is None:
                continue
            del running[pr]
            if rc == 0 and (out / _out_name(t[0])).exists():
                done += 1
                log(f"[{done}/{len(tasks)}] {t[0]} ok, running {len(running)}, t={time.time() - t0:.0f}s")
            else:
                fails[t[0]] = fails.get(t[0], 0) + 1
                log(f"FAIL {t[0]} rc={rc} (attempt {fails[t[0]]})")
                if fails[t[0]] < 2:
                    pending.append(t)
        target = M._target_workers(out, max_workers)
        while pending and len(running) < target and M._mem_available_gb() > min_free_gb:
            t = pending.pop(0)
            log_f = open(out / "logs" / f"{_out_name(t[0])[5:-4]}.log", "w")
            running[subprocess.Popen([sys.executable, __file__, "one", str(out), t[0]], stdout=log_f,
                                     stderr=subprocess.STDOUT)] = t
            time.sleep(2)
        time.sleep(10)
    log(f"DONE failed={sorted(k for k, v in fails.items() if v >= 2)}")


def _probe_one(args):
    outdir, rid, shard, idx = args
    task(rid, shard, outdir, only=idx, tag=f"probe_{rid}_{shard:03d}", stage_s=False)
    return rid


def probe(outdir, workers, n=50):
    out = Path(outdir)
    if out.exists() and any(out.iterdir()):
        sys.exit(f"{out} exists and is not empty")
    out.mkdir(parents=True)
    alli = [(t[0], t[1], int(i)) for t in mp_plan() for i in c_instants(mp_rows(t[0], t[1]))]
    pick = [alli[i] for i in np.unique(np.linspace(0, len(alli) - 1, n).astype(int))]
    by = {}
    for rid, s, i in pick:
        by.setdefault((rid, s), []).append(i)
    (out / "probe.json").write_text(json.dumps({"n_instants_stage": len(alli), "n_probe_instants": len(pick)}) + "\n")
    with mpr.get_context("spawn").Pool(workers, maxtasksperchild=1) as pool:
        for k, rid in enumerate(pool.imap_unordered(_probe_one, [(str(out), r, s, i) for (r, s), i in by.items()]), 1):
            print(f"[{k}/{len(by)}] {rid}", flush=True)
    print("DONE", flush=True)


def cost(gpdir, out_json):
    """Per-instant cost (ten targets, one core) by box-area bin, times the stage's instants per bin, plus reads."""
    gpdir = Path(gpdir)
    edges = (0, 1_000, 3_000, 10_000, 30_000, 100_000, np.inf)
    z = [dict(np.load(f)) for f in sorted((gpdir / "probe").glob("rows_*.npz"))]
    c = {k: np.concatenate([d[k] for d in z]) for k in ("recording_id", "track_id", "t_e_us", "box_area_te",
                                                        "elapsed_s", "aligned_n_eval", "skip")}
    key = np.char.add(np.char.add(c["recording_id"], "|"), np.char.add(c["track_id"].astype(int).astype(str),
                                                                       np.char.add("|", c["t_e_us"].astype(int).astype(str))))
    u, inv = np.unique(key, return_inverse=True)
    pc = np.bincount(inv, c["elapsed_s"])
    pa = np.bincount(inv, c["box_area_te"]) / np.bincount(inv)
    all_area = np.concatenate([mp_rows(t[0], t[1])["box_area_te"][c_instants(mp_rows(t[0], t[1]))] for t in mp_plan()])
    fallback = max(pc[(pa >= lo) & (pa < hi)].mean() for lo, hi in zip(edges[:-1], edges[1:])
                   if ((pa >= lo) & (pa < hi)).any())
    bins, total = [], 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        s = (pa >= lo) & (pa < hi)
        n = int(((all_area >= lo) & (all_area < hi)).sum())
        mean = float(pc[s].mean()) if s.any() else float(fallback)
        total += n * mean
        bins.append({"area_px2": [lo, None if np.isinf(hi) else hi], "n_probe_instants": int(s.sum()),
                     "mean_s_per_instant": mean, "max_s": float(pc[s].max()) if s.any() else None,
                     "n_instants_stage": n, "cpu_h": n * mean / 3600})
    pre = Path.home() / "prjs" / "event_coding" / "mp" / "preflight"
    read_s = {json.loads(Path(f).read_text())["recording_id"]: json.loads(Path(f).read_text())["read_s"]
              for f in glob.glob(str(pre / "train_*.json"))}
    reads = sum(read_s[t[0]] for t in mp_plan()) / 3600
    ne = c["aligned_n_eval"][c["skip"] == ""]
    res = {"n_probe_instants": int(len(u)), "n_probe_rows": int(len(c["skip"])), "n_instants_stage": int(len(all_area)),
           "bins": bins, "compute_cpu_h": total / 3600, "read_cpu_h": reads, "total_cpu_h": total / 3600 + reads,
           "probe_aligned_n_eval": {"median": float(np.median(ne)), "max": float(ne.max())},
           "limit_cpu_h": 120}
    res["within_limit"] = res["total_cpu_h"] <= 120
    Path(out_json).write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps({k: v for k, v in res.items() if k != "bins"}, indent=1))
    for b in bins:
        print(b)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("probe", "cost", "run", "one"))
    ap.add_argument("outdir")
    ap.add_argument("key", nargs="?")
    ap.add_argument("--workers", type=int, default=24)
    a = ap.parse_args()
    out = Path(a.outdir)
    if a.mode == "one":
        rid, s = a.key.split("|")
        task(rid, int(s), out)
        return
    if a.mode == "probe":
        probe(out, a.workers)
        return
    if a.mode == "cost":
        cost(out, a.key)
        return
    if (out / "plan.json").exists():
        if not (out / "RESUME").exists():
            sys.exit(f"{out} holds a run; touch {out}/RESUME to resume it")
    else:
        if out.exists() and any(out.iterdir()):
            sys.exit(f"{out} exists and is not empty")
        (out / "logs").mkdir(parents=True, exist_ok=True)
        tasks = sorted(([f"{t[0]}|{t[1]}", t[3]] for t in mp_plan()), key=lambda t: -t[1])
        (out / "plan.json").write_text(json.dumps({"commit": (mp.REPO / "COMMIT").read_text().strip(),
                                                   "tasks": tasks}) + "\n")
    schedule(out, a.workers)


if __name__ == "__main__":
    main()
