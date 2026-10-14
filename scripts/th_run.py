"""Directive 020: where motion stops predicting the counts of recorded events.

  python3 scripts/th_run.py run [--workers W]      # Section 5, resumable: one task per recording
  python3 scripts/th_run.py one DS RID             # one task
  python3 scripts/th_run.py project                # Section 7: from the first 10 groups of each dataset

Groups: the D2 groups of directive 019 (``hd_run.groups(ds, "d2")``: Stage R groups with ``j % 5 == 0``).
Events of a group: ``[(w - 3) T0, (w + 2) T0)``. eTraM is read once per recording with ``bk_run.read`` (at most
six reads at once); DSEC comes from the caches of directive 017 (``fm_run.dsec_events``), which hold
``[(w - 3) T0, (w + 11) T0)`` per group; no DSEC event file is read. For every group the task calls
``ec.threshold.evaluate_group(events, w, W, H)`` and checks acceptance check 2 on its output. Outputs:
``~/prjs/event_coding/th/<rid>.pkl`` (eTraM, a link to ``/data/<user>/event_coding/home/th``) and
``/data/<user>/event_coding/ds/th/<rid>.pkl`` (DSEC).
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
from ec import blockcodec as bc, mp, threshold as th  # noqa: E402
import bk_run as BK  # noqa: E402
import fb_run as FB  # noqa: E402
import fm_run as FM  # noqa: E402
import hd_run as HR  # noqa: E402
import mp_measure as M  # noqa: E402

T0 = bc.T0_US
TH_E = Path.home() / "prjs" / "event_coding" / "th"
TH_D = HR.RC.DR.BASE / "ds" / "th"
READ_SLOTS_E = 6


def outdir(ds):
    return TH_E if ds == "etram" else TH_D


def out_path(ds, rid):
    return outdir(ds) / f"{rid}.pkl"


def checks(o):
    """Acceptance check 2 on one group's output."""
    ok = True
    for scope in ("pixel", "block"):
        s = o["sums"][scope]
        lim = np.minimum(s[..., 0], s[..., 1])
        ok &= bool(np.all(s[..., 2] <= lim) and np.all(s[..., 3] <= lim))
    g = th.GRIDS.index((1, 1))
    n_pix = int(o["sums"]["pixel"][:, :, g, :, 0].sum())
    return {"pairs_bounded": ok, "pixel_N_equals_blocks_N": n_pix == int(np.sum(o["blocks"]["N"])),
            "pixel_N": n_pix, "blocks_N": int(np.sum(o["blocks"]["N"]))}


def task(ds, rid):
    out = out_path(ds, rid)
    if out.exists():
        return
    t_start, c_start = time.time(), time.process_time()
    rows = HR.groups(ds, "d2")[rid]
    W, H = FB.DIMS[ds]
    ws = [r["w"] for r in rows]
    evs = {}
    if ds == "etram":
        lk = M._read_lock(TH_E, slots=READ_SLOTS_E)
        ev = BK.read(rid)
        lk.close()
        t, x, y, p = ev.t_us, ev.x, ev.y, ev.p
        for w in ws:
            a, b = np.searchsorted(t, (max(0, w - th.SPAN_BEFORE) * T0, (w + 2) * T0))
            evs[w] = tuple(np.asarray(v[a:b], dtype=np.int64).copy() for v in (t, x, y, p))
        del ev, t, x, y, p
    else:
        for w, e in FM.dsec_events(rid, ws).items():
            a, b = np.searchsorted(e[0], (max(0, w - th.SPAN_BEFORE) * T0, (w + 2) * T0))
            evs[w] = tuple(v[a:b] for v in e)
    read_s = time.time() - t_start
    res = []
    for r in rows:
        w = r["w"]
        c0, p0 = time.process_time(), time.perf_counter()
        o = th.evaluate_group(evs[w], w, W, H)
        o.update({"j": r["j"], "checks": checks(o), "cpu_s": time.process_time() - c0,
                  "wall_s": time.perf_counter() - p0, "finished_utc": time.time()})
        res.append(o)
    tmp = out.with_suffix(".tmp")
    with open(tmp, "wb") as f:
        pickle.dump({"dataset": ds, "recording": rid, "commit": (mp.REPO / "COMMIT").read_text().strip(),
                     "events_from": "bk_run.read" if ds == "etram" else "the cache of directive 017",
                     "groups": res, "read_s": read_s, "task_wall_s": time.time() - t_start,
                     "task_cpu_s": time.process_time() - c_start}, f, protocol=5)
    tmp.rename(out)


def load(ds, rid):
    with open(out_path(ds, rid), "rb") as f:
        return pickle.load(f)


def plan():
    k = {ds: [(ds, rid) for rid in HR.groups(ds, "d2")] for ds in ("dsec", "etram")}
    out = []
    for i in range(max(len(k["dsec"]), len(k["etram"]))):
        out += ([k["dsec"][i]] if i < len(k["dsec"]) else []) + ([k["etram"][i]] if i < len(k["etram"]) else [])
    return out


def run(workers):
    for d in (TH_E, TH_D):
        (d / "logs").mkdir(parents=True, exist_ok=True)
    if not (TH_E / "plan.json").exists():
        (TH_E / "plan.json").write_text(json.dumps({"commit": (mp.REPO / "COMMIT").read_text().strip(),
                                                    "tasks": plan()}) + "\n")
    tasks = [tuple(t) for t in json.loads((TH_E / "plan.json").read_text())["tasks"]]
    pending = [t for t in tasks if not out_path(*t).exists()]
    running, fails, t0, done = {}, {}, time.time(), len(tasks) - len(pending)
    log = lambda m: print(f"{time.strftime('%H:%M:%S')} {m}", flush=True)
    log(f"{len(pending)} of {len(tasks)} tasks pending")
    while pending or running:
        for pr, k in list(running.items()):
            if pr.poll() is None:
                continue
            del running[pr]
            if pr.returncode == 0 and out_path(*k).exists():
                done += 1
                log(f"[{done}/{len(tasks)}] {k[0]} {k[1]} ok, running {len(running)}, t={time.time() - t0:.0f}s")
            else:
                fails[k] = fails.get(k, 0) + 1
                log(f"FAIL {k} rc={pr.returncode} (attempt {fails[k]})")
                if fails[k] < 2:
                    pending.append(k)
        if (TH_E / "STOP").exists():
            pending = []
        target = M._target_workers(TH_E, workers)
        while pending and len(running) < target and M._mem_available_gb() > 40.0:
            k = pending.pop(0)
            lf = open(outdir(k[0]) / "logs" / f"{k[1]}.log", "w")
            running[subprocess.Popen([sys.executable, __file__, "one", *k], stdout=lf, stderr=subprocess.STDOUT)] = k
            time.sleep(1)
        time.sleep(10)
    log(f"DONE failed={sorted(k for k, v in fails.items() if v >= 2)}")


def project():
    """Section 7: CPU per group from the first 10 finished groups of each dataset, times its groups; plus the
    measured read time per recording for eTraM."""
    res, tot = {}, 0.0
    for ds in ("etram", "dsec"):
        rows, reads = [], []
        for rid in HR.groups(ds, "d2"):
            if out_path(ds, rid).exists():
                d = load(ds, rid)
                rows += [(g["finished_utc"], g["cpu_s"]) for g in d["groups"]]
                reads.append(d["task_cpu_s"] - sum(g["cpu_s"] for g in d["groups"]))
        rows.sort()
        first = [c for _, c in rows[:10]]
        ng = sum(len(v) for v in HR.groups(ds, "d2").values())
        nr = len(HR.groups(ds, "d2"))
        if len(first) < 10:
            res[ds] = {"n_first": len(first), "cpu_h": None}
            continue
        cpu_h = (float(np.mean(first)) * ng + float(np.mean(reads)) * nr) / 3600
        res[ds] = {"n_first": 10, "cpu_s_per_group": float(np.mean(first)), "read_cpu_s_per_recording": float(np.mean(reads)),
                   "n_groups": ng, "n_recordings": nr, "cpu_h": cpu_h}
        tot += cpu_h
    ok = all(res[ds]["cpu_h"] is not None for ds in res)
    out = {"projection": res, "cpu_h": tot if ok else None, "limit_cpu_h": 40, "pass": ok and tot <= 40}
    print(json.dumps(out, indent=1))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode")
    ap.add_argument("args", nargs="*")
    ap.add_argument("--workers", type=int, default=22)
    a = ap.parse_args()
    {"run": lambda: run(a.workers), "one": lambda: task(*a.args), "project": project}[a.mode]()


if __name__ == "__main__":
    main()
