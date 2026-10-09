"""Directive 002, Sections 6 and 7: Stage R (regeneration fidelity) and Stage B (bandwidth cap).

  python3 scripts/rg_run.py plan OUTDIR                     # Stage B subsample, from the 001 per-instant files
  python3 scripts/rg_run.py probe R|B OUTDIR [--workers W]   # 50 timed rows of a stage
  python3 scripts/rg_run.py run R|B OUTDIR [--workers W]     # every row of a stage; resumable
  python3 scripts/rg_run.py one R|B OUTDIR KEY               # one task (called by run)

Stage R uses ``ec.regen.evaluate_regen`` unchanged on every row that directive 001
scored at settings (100, 0), (100, 33), (100, 100) and (100, 300), one task per
shard of directive 001 (same tracks). Stage B scores the rows of the subsample
with ``ec.motion.evaluate_instant`` under B4 and B6. Each task reads its recording
once with ``ec.baseline.read_events`` and keeps the events of its tracks' lives,
which leaves every result unchanged (directive 001, report Section 4, item 4).
"""
from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS",
           "VECLIB_MAXIMUM_THREADS", "NUMBA_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import argparse
import json
import multiprocessing as mpr
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ec import annotations, baseline, motion, mp, regen  # noqa: E402
import mp_measure as M  # noqa: E402

MP_RUN = Path.home() / "prjs" / "event_coding" / "mp" / "run"
WIDTH, HEIGHT = 1280, 720
T1_US, T2_US, MARGIN_PX = 100_000, 33_333, 2.0
R_SETTINGS = (0, 1, 2, 3)                       # (100, 0), (100, 33), (100, 100), (100, 300)
B4 = (0.125, 0.25, 0.5, 1.0)
B6 = B4 + (2.0, 4.0)
MODELS = ("static", "label", "cmax")
STRATA_COLS = ("recording_id", "lighting", "track_id", "class_id", "group", "t_e_us", "setting", "T1_us", "D_us",
               "speed_bin", "speed_label_strata", "overlap", "box_area_te")
B_STEP = 10
B_ROWS_PER_TASK = 5


def mp_plan():
    return json.loads((MP_RUN / "plan.json").read_text())["tasks"]


def mp_rows(rid, shard):
    return dict(np.load(MP_RUN / f"instants_{rid}_{shard:03d}.npz"))


def r_rows(z):
    """Indices of the Stage R rows of one 001 file: scored at settings 0 to 3."""
    if "setting" not in z:
        return np.zeros(0, dtype=np.int64)
    return np.flatnonzero((z["skip"] == "") & np.isin(z["setting"].astype(int), R_SETTINGS))


def b_subsample():
    """Stage B rows: scored, stratum H, setting (100, 0); sorted by recording, track_id, t_e; every 10th."""
    rows = []
    for t in mp_plan():
        z = mp_rows(t[0], t[1])
        if "setting" not in z:
            continue
        h = np.flatnonzero((z["skip"] == "") & (z["setting"] == 0) & (z["group"] == "vehicles") & (z["overlap"] == 0)
                           & ((z["speed_bin"] == 1) | (z["speed_bin"] == 2)))
        for i in h:
            rows.append({"recording_id": str(z["recording_id"][i]), "track_id": int(z["track_id"][i]),
                         "t_e_us": int(z["t_e_us"][i]), "mp_shard": int(t[1]), "mp_index": int(i)})
    rows.sort(key=lambda r: (r["recording_id"], r["track_id"], r["t_e_us"]))
    out, pos = [], {}
    for r in rows:
        k = pos.get(r["recording_id"], 0)
        pos[r["recording_id"]] = k + 1
        if k % B_STEP == 0:
            out.append(r | {"position": k})
    return rows, out


# ----------------------------------------------------------------------------- tasks
def _events_for(rid, trs_needed, outdir, lock=True):
    lk = M._read_lock(outdir) if lock else None
    ev = baseline.read_events(mp.event_path(rid))
    sl = M._Slice(ev, min(tr.t_first for tr in trs_needed), max(tr.t_last for tr in trs_needed))
    if lk:
        lk.close()
    return sl


def task_R(rid, shard, outdir, only=None, tag=None):
    """Stage R rows of one 001 shard (``only``: a subset of row indices of that file, for the probe)."""
    out = Path(outdir) / f"rows_{tag or f'{rid}_{shard:03d}'}.npz"
    if out.exists():
        return 0
    t0 = time.time()
    z = mp_rows(rid, shard)
    idx = r_rows(z) if only is None else np.asarray(only, dtype=np.int64)
    trk = {tr.track_id: tr for tr in annotations.tracks(annotations.load_boxes(mp.annotation_path(rid)))}
    rows = []
    if len(idx):
        ev = _events_for(rid, [trk[int(k)] for k in np.unique(z["track_id"][idx])], outdir)
        t_read = time.time() - t0
        for i in idx:
            tr = trk[int(z["track_id"][i])]
            t1 = time.perf_counter()
            r = regen.evaluate_regen(ev.t_us, ev.x, ev.y, ev.p, tr, int(z["t_e_us"][i]), int(z["D_us"][i]), T2_US,
                                     WIDTH, HEIGHT, (float(z["cmax_vx"][i]), float(z["cmax_vy"][i])),
                                     T1_us=T1_US, margin_px=MARGIN_PX)
            el = time.perf_counter() - t1
            row = {c: z[c][i].item() for c in STRATA_COLS}
            row.update({"mp_shard": shard, "mp_index": int(i), "mp_n_future": int(z["n_future"][i]),
                        "mp_support_px": int(z["support_px"][i]), "elapsed_s": el, "skip": r.get("skipped", "")})
            row.update({k: v for k, v in r.items() if k != "skipped"})
            rows.append(row)
    else:
        t_read = 0.0
    M.to_npz(rows, out) if rows else np.savez_compressed(out, empty=np.zeros(0))
    (Path(outdir) / f"task_{out.stem[5:]}.json").write_text(json.dumps(
        {"rid": rid, "shard": shard, "n_rows": len(rows), "read_s": t_read, "wall_s": time.time() - t0}) + "\n")
    return len(rows)


def task_B(rows_spec, outdir, tag):
    """Stage B rows (one recording): evaluate_instant under B4 and B6, three models."""
    out = Path(outdir) / f"rows_{tag}.npz"
    if out.exists():
        return 0
    t0 = time.time()
    rid = rows_spec[0]["recording_id"]
    trk = {tr.track_id: tr for tr in annotations.tracks(annotations.load_boxes(mp.annotation_path(rid)))}
    ev = _events_for(rid, [trk[r["track_id"]] for r in rows_spec], outdir)
    t_read = time.time() - t0
    cache = {}
    rows = []
    for spec in rows_spec:
        if spec["mp_shard"] not in cache:
            cache[spec["mp_shard"]] = mp_rows(rid, spec["mp_shard"])
        z, i = cache[spec["mp_shard"]], spec["mp_index"]
        assert int(z["track_id"][i]) == spec["track_id"] and int(z["t_e_us"][i]) == spec["t_e_us"]
        tr = trk[spec["track_id"]]
        row = {c: z[c][i].item() for c in STRATA_COLS}
        row.update({"position": spec["position"], "mp_shard": spec["mp_shard"], "mp_index": i})
        for m in MODELS:
            for q in ("gain_bits", "eps", "b_px", "ref_bits"):
                row[f"mp_{m}_{q}"] = float(z[f"{m}_{q}"][i])
        for name, bw in (("b4", B4), ("b6", B6)):
            t1 = time.perf_counter()
            r = motion.evaluate_instant(ev.t_us, ev.x, ev.y, ev.p, tr, spec["t_e_us"], T1_US, 0, T2_US, WIDTH, HEIGHT,
                                        margin_px=MARGIN_PX, models=MODELS, bandwidths=bw)
            row[f"{name}_elapsed_s"] = time.perf_counter() - t1
            row[f"{name}_skip"] = r.get("skipped", "")
            row.update({f"{name}_{k}": v for k, v in r.items() if k != "skipped"})
        rows.append(row)
    M.to_npz(rows, out)
    (Path(outdir) / f"task_{tag}.json").write_text(json.dumps(
        {"rid": rid, "tag": tag, "n_rows": len(rows), "read_s": t_read, "wall_s": time.time() - t0}) + "\n")
    return len(rows)


# ----------------------------------------------------------------------------- plans
def plan_tasks(stage, outdir):
    """[key, est_cost] per task, longest first."""
    if stage == "R":
        tasks = [[f"{t[0]}|{t[1]}", t[3]] for t in mp_plan()]
    else:
        sub = json.loads((Path(outdir).parent / "b_plan.json").read_text())["subsample"]
        by = {}
        for r in sub:
            by.setdefault(r["recording_id"], []).append(r)
        tasks = []
        for rid, rs in by.items():
            for c in range(0, len(rs), B_ROWS_PER_TASK):
                chunk = rs[c:c + B_ROWS_PER_TASK]
                tasks.append([f"{rid}|{c // B_ROWS_PER_TASK}", sum(r["area"] for r in chunk)])
    tasks.sort(key=lambda t: -t[1])
    return tasks


def run_key(stage, outdir, key):
    rid, s = key.split("|")
    if stage == "R":
        task_R(rid, int(s), outdir)
    else:
        sub = [r for r in json.loads((Path(outdir).parent / "b_plan.json").read_text())["subsample"]
               if r["recording_id"] == rid]
        c = int(s)
        task_B(sub[c * B_ROWS_PER_TASK:(c + 1) * B_ROWS_PER_TASK], outdir, f"{rid}_{c:03d}")


def out_of(stage, key):
    rid, s = key.split("|")
    return f"rows_{rid}_{int(s):03d}.npz"


def schedule(stage, out, max_workers, min_free_gb=40.0):
    tasks = json.loads((out / "plan.json").read_text())["tasks"]
    pending = [t for t in tasks if not (out / out_of(stage, t[0])).exists()]
    running, fails, t0, done = {}, {}, time.time(), len(tasks) - len(pending)
    log = lambda m: print(f"{time.strftime('%H:%M:%S')} {m}", flush=True)
    log(f"{len(pending)} of {len(tasks)} tasks pending")
    while pending or running:
        for pr, t in list(running.items()):
            rc = pr.poll()
            if rc is None:
                continue
            del running[pr]
            if rc == 0 and (out / out_of(stage, t[0])).exists():
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
            log_f = open(out / "logs" / f"{out_of(stage, t[0])[5:-4]}.log", "w")
            running[subprocess.Popen([sys.executable, __file__, "one", stage, str(out), t[0]], stdout=log_f,
                                     stderr=subprocess.STDOUT)] = t
            time.sleep(2)
        time.sleep(10)
    log(f"DONE failed={sorted(k for k, v in fails.items() if v >= 2)}")


# ----------------------------------------------------------------------------- probe
def _probe_one(args):
    stage, outdir, item = args
    if stage == "R":
        rid, shard, idx = item
        task_R(rid, shard, outdir, only=idx, tag=f"probe_{rid}_{shard:03d}")
    else:
        task_B(item, outdir, f"probe_{item[0]['recording_id']}")
    return item[0] if stage == "R" else item[0]["recording_id"]


def probe(stage, outdir, workers, n=50):
    out = Path(outdir)
    if out.exists() and any(out.iterdir()):
        sys.exit(f"{out} exists and is not empty")
    out.mkdir(parents=True)
    if stage == "R":
        allr = [(t[0], t[1], int(i)) for t in mp_plan() for i in r_rows(mp_rows(t[0], t[1]))]
        pick = [allr[i] for i in np.unique(np.linspace(0, len(allr) - 1, n).astype(int))]
        by = {}
        for rid, s, i in pick:
            by.setdefault((rid, s), []).append(i)
        items = [(rid, s, idx) for (rid, s), idx in by.items()]
        meta = {"n_rows_stage": len(allr)}
    else:
        sub = json.loads((out.parent / "b_plan.json").read_text())["subsample"]
        pick = [sub[i] for i in np.unique(np.linspace(0, len(sub) - 1, n).astype(int))]
        by = {}
        for r in pick:
            by.setdefault(r["recording_id"], []).append(r)
        items = list(by.values())
        meta = {"n_rows_stage": len(sub)}
    (out / "probe.json").write_text(json.dumps(meta | {"n_probe_rows": len(pick)}) + "\n")
    with mpr.get_context("spawn").Pool(workers, maxtasksperchild=1) as pool:
        for k, name in enumerate(pool.imap_unordered(_probe_one, [(stage, str(out), it) for it in items]), 1):
            print(f"[{k}/{len(items)}] {name}", flush=True)
    print("DONE", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("plan", "probe", "run", "one"))
    ap.add_argument("stage_or_out")
    ap.add_argument("outdir", nargs="?")
    ap.add_argument("key", nargs="?")
    ap.add_argument("--workers", type=int, default=24)
    a = ap.parse_args()
    if a.mode == "plan":
        out = Path(a.stage_or_out)
        out.mkdir(parents=True, exist_ok=True)
        allh, sub = b_subsample()
        for r in sub:
            z = mp_rows(r["recording_id"], r["mp_shard"])
            r["area"] = float(z["box_area_te"][r["mp_index"]])
        (out / "b_plan.json").write_text(json.dumps({"rule": "scored rows of 001 in stratum H at (100, 0), sorted by "
                                                     "recording, track_id, t_e; positions 0, 10, 20, ... per recording",
                                                     "n_H_rows": len(allh), "n_subsample": len(sub),
                                                     "subsample": sub}) + "\n")
        print(len(allh), "H rows,", len(sub), "subsampled")
        return
    stage, out = a.stage_or_out, Path(a.outdir)
    if a.mode == "one":
        run_key(stage, out, a.key)
        return
    if a.mode == "probe":
        probe(stage, out, a.workers)
        return
    if (out / "plan.json").exists():
        if not (out / "RESUME").exists():
            sys.exit(f"{out} holds a run; touch {out}/RESUME to resume it")
    else:
        if out.exists() and any(out.iterdir()):
            sys.exit(f"{out} exists and is not empty")
        (out / "logs").mkdir(parents=True, exist_ok=True)
        (out / "plan.json").write_text(json.dumps({"commit": (mp.REPO / "COMMIT").read_text().strip(),
                                                   "stage": stage, "tasks": plan_tasks(stage, out)}) + "\n")
    schedule(stage, out, a.workers)


if __name__ == "__main__":
    main()
