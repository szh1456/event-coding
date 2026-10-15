"""Directive 027: the per-block phase test on recordings and model scenes, and the controlled model.

  python3 scripts/pc_run.py run [--workers W]      # Section 5, resumable
  python3 scripts/pc_run.py one KEY                # rec|DS|RID, model|V|SHARED|SEED or control|TAU|COND
  python3 scripts/pc_run.py project                # Section 7

Groups and events as directive 022 (D-027-2): the D2 groups of directive 019 (``hd_run.groups(ds, "d2")``), the
events of ``[(w - 3) T0, (w + 2) T0)``; eTraM read once per recording with ``bk_run.read`` (at most six reads at
once), DSEC from the caches of directive 017 (``fm_run.dsec_events``). For every group
``ec.phase_control.block_phases(events, w, W, H)``. Model scenes: ``ec.phase.edge_scene_v(320, 240, v, 2000.0, 3,
0.05, 40, 8, seed, shared)`` at ``w = 5``. Control cells: ``ec.phase_control.control_cell(tau, condition)``.
Outputs under ``~/prjs/event_coding/pc/`` (eTraM, model, control) and ``/data/<user>/event_coding/ds/pc/`` (DSEC).
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
from ec import blockcodec as bc, mp, phase as ph, phase_control as pcm, threshold as th  # noqa: E402
import bk_run as BK  # noqa: E402
import fb_run as FB  # noqa: E402
import fm_run as FM  # noqa: E402
import hd_run as HR  # noqa: E402
import mp_measure as M  # noqa: E402

T0 = bc.T0_US
PC_E = Path.home() / "prjs" / "event_coding" / "pc"
PC_D = HR.RC.DR.BASE / "ds" / "pc"
READ_SLOTS_E = 6
SPEEDS = (1.5, 2.5, 6.5, 13.3)
SEEDS = (1, 2, 3)
MW, MH = 320, 240
LIMIT_CPU_H = 40


def out_path(key):
    parts = key.split("|")
    if parts[0] in ("model", "control"):
        return PC_E / parts[0] / (key.replace("|", "_") + ".pkl")
    return (PC_D if parts[1] == "dsec" else PC_E) / "rec" / f"{parts[2]}.pkl"


def task(key):
    out = out_path(key)
    if out.exists():
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    t_start, c_start = time.time(), time.process_time()
    parts = key.split("|")
    res = {"key": key, "commit": (mp.REPO / "COMMIT").read_text().strip()}
    if parts[0] == "model":
        v, shared, seed = float(parts[1]), parts[2] == "1", int(parts[3])
        ev = ph.edge_scene_v(MW, MH, v, 2000.0, 3, 0.05, 40, 8, seed, shared)
        res.update({"v": v, "shared": shared, "seed": seed, "n_events": int(len(ev[0])),
                    "group": pcm.block_phases(ev, 5, MW, MH)})
    elif parts[0] == "control":
        res["cell"] = pcm.control_cell(float(parts[1]), parts[2])
    else:
        ds, rid = parts[1], parts[2]
        rows = HR.groups(ds, "d2")[rid]
        W, H = FB.DIMS[ds]
        ws = [r["w"] for r in rows]
        evs = {}
        if ds == "etram":
            lk = M._read_lock(PC_E, slots=READ_SLOTS_E)
            ev = BK.read(rid)
            lk.close()
            t, x, y, p = ev.t_us, ev.x, ev.y, ev.p
            for w in ws:
                a, b = np.searchsorted(t, (max(0, w - th.SPAN_BEFORE) * T0, (w + 2) * T0))
                evs[w] = tuple(np.asarray(v_[a:b], dtype=np.int64).copy() for v_ in (t, x, y, p))
            del ev, t, x, y, p
        else:
            for w, e in FM.dsec_events(rid, ws).items():
                a, b = np.searchsorted(e[0], (max(0, w - th.SPAN_BEFORE) * T0, (w + 2) * T0))
                evs[w] = tuple(v_[a:b] for v_ in e)
        res["read_s"] = time.time() - t_start
        res["groups"] = []
        for r in rows:
            w = r["w"]
            c0, p0 = time.process_time(), time.perf_counter()
            o = pcm.block_phases(evs[w], w, W, H)
            o.update({"j": r["j"], "cpu_s": time.process_time() - c0, "wall_s": time.perf_counter() - p0,
                      "finished_utc": time.time()})
            res["groups"].append(o)
        res.update({"dataset": ds, "recording": rid})
    res["task_wall_s"], res["task_cpu_s"] = time.time() - t_start, time.process_time() - c_start
    tmp = out.with_suffix(".tmp")
    with open(tmp, "wb") as f:
        pickle.dump(res, f, protocol=5)
    tmp.rename(out)


def load(key):
    with open(out_path(key), "rb") as f:
        return pickle.load(f)


def plan():
    control = [f"control|{tau}|{c}" for tau in pcm.TAUS_US for c in pcm.CONDITIONS]
    model = [f"model|{v}|{int(s)}|{seed}" for v in SPEEDS for s in (False, True) for seed in SEEDS]
    rec = {ds: [f"rec|{ds}|{rid}" for rid in HR.groups(ds, "d2")] for ds in ("dsec", "etram")}
    inter = []
    for i in range(max(len(rec["dsec"]), len(rec["etram"]))):
        inter += ([rec["dsec"][i]] if i < len(rec["dsec"]) else []) + ([rec["etram"][i]] if i < len(rec["etram"]) else [])
    return control + model + inter


def run(workers):
    (PC_E / "logs").mkdir(parents=True, exist_ok=True)
    if not (PC_E / "plan.json").exists():
        (PC_E / "plan.json").write_text(json.dumps({"commit": (mp.REPO / "COMMIT").read_text().strip(),
                                                    "tasks": plan()}) + "\n")
    tasks = json.loads((PC_E / "plan.json").read_text())["tasks"]
    pending = [k for k in tasks if not out_path(k).exists()]
    running, fails, t0, done = {}, {}, time.time(), len(tasks) - len(pending)
    log = lambda m: print(f"{time.strftime('%H:%M:%S')} {m}", flush=True)
    log(f"{len(pending)} of {len(tasks)} tasks pending")
    while pending or running:
        for pr, k in list(running.items()):
            if pr.poll() is None:
                continue
            del running[pr]
            if pr.returncode == 0 and out_path(k).exists():
                done += 1
                log(f"[{done}/{len(tasks)}] {k} ok, running {len(running)}, t={time.time() - t0:.0f}s")
            else:
                fails[k] = fails.get(k, 0) + 1
                log(f"FAIL {k} rc={pr.returncode} (attempt {fails[k]})")
                if fails[k] < 2:
                    pending.append(k)
        if (PC_E / "STOP").exists():
            pending = []
        target = M._target_workers(PC_E, workers)
        while pending and len(running) < target and M._mem_available_gb() > 40.0:
            k = pending.pop(0)
            lf = open(PC_E / "logs" / (k.replace("|", "_") + ".log"), "w")
            running[subprocess.Popen([sys.executable, __file__, "one", k], stdout=lf, stderr=subprocess.STDOUT)] = k
            time.sleep(1)
        time.sleep(5)
    log(f"DONE failed={sorted(k for k, v in fails.items() if v >= 2)}")


def project():
    """Section 7: CPU of the first 10 groups of each dataset (by finishing time) times the groups, plus the reads,
    plus the model and control tasks."""
    tasks = json.loads((PC_E / "plan.json").read_text())["tasks"]
    res = {}
    for ds in ("etram", "dsec"):
        rows, reads = [], []
        for k in tasks:
            if k.startswith(f"rec|{ds}|") and out_path(k).exists():
                d = load(k)
                rows += [(g["finished_utc"], g["cpu_s"]) for g in d["groups"]]
                reads.append(d["task_cpu_s"] - sum(g["cpu_s"] for g in d["groups"]))
        rows.sort()
        first = [c for _, c in rows[:10]]
        ng = sum(len(v) for v in HR.groups(ds, "d2").values())
        nr = len(HR.groups(ds, "d2"))
        ok = len(first) == 10
        res[ds] = {"n_first": len(first), "cpu_s_per_group": float(np.mean(first)) if first else None,
                   "read_cpu_s_per_recording": float(np.mean(reads)) if reads else None, "n_groups": ng,
                   "n_recordings": nr,
                   "cpu_h": (float(np.mean(first)) * ng + float(np.mean(reads)) * nr) / 3600 if ok else None}
    for kind in ("model", "control"):
        ms = [load(k)["task_cpu_s"] for k in tasks if k.startswith(kind + "|") and out_path(k).exists()]
        n_m = sum(1 for k in tasks if k.startswith(kind + "|"))
        res[kind] = {"n_done": len(ms), "n": n_m, "cpu_h": float(np.mean(ms)) * n_m / 3600 if ms else None}
    ok = all(v["cpu_h"] is not None for v in res.values())
    tot = sum(v["cpu_h"] for v in res.values()) if ok else None
    out = {"projection": res, "cpu_h": tot, "limit_cpu_h": LIMIT_CPU_H, "pass": ok and tot <= LIMIT_CPU_H}
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
