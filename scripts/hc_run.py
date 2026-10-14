"""Directive 021: controls for the HEVC diagnostics (prediction, amplitude mapping, clipping).

  python3 scripts/hc_run.py run [--workers W]      # Section 5, resumable
  python3 scripts/hc_run.py one KEY                # d1|DS|RID|J or d3|TAU|N|SEED
  python3 scripts/hc_run.py project                # Section 7

Groups, events, background and tasks: ``hd_run.groups``, ``hd_run.events`` and ``hd_run.context`` of directive 019,
unchanged (D-021-2): D1 groups ``j % 40 == 0`` (eTraM) and ``j % 20 == 0`` (DSEC); eTraM read with ``bk_run.read``
(at most six reads at once), DSEC from the caches of directive 017. For every D1 group: every grid of 019 with
``FINE_MODES``, and the coarse grids with ``COARSE_MODES`` and the tasks on their lossy modes at both placements.
The 36 model scenes of 019 with the fine modes. x265 scratch under ``/data/<user>/event_coding/ds/hc/work``.

Importing ``hd_run`` wraps ``ec.hevcdiag.fidelities`` to also return its summed terms (``sums``), as in 019; F and
Fsnr are unchanged. Acceptance check 3 runs inside every D1 task against the 019 output of the same group: on a
mismatch the task writes ``MISMATCH_<key>.json`` and the scheduler launches no further task.
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
from ec import hevcctl as hc, hevcdiag as hd, mp  # noqa: E402
import fb_run as FB  # noqa: E402
import fm_run as FM  # noqa: E402
import hd_run as HR  # noqa: E402
import mp_measure as M  # noqa: E402

HC_E = Path.home() / "prjs" / "event_coding" / "hc"
HC_D = HR.RC.DR.BASE / "ds" / "hc"
WORK = HC_D / "work"
FINE_GRIDS = [(s, k) for s in hd.SPACES for k in hd.KS]
COARSE_LOSSY = tuple(m for m in hc.COARSE_MODES if m.startswith("qp"))
CHECK_MODES = ("lossless", "sparse") + tuple(f"qp{q}" for q in hd.QPS)


def cpu_now():
    return FM.cpu_now()


def out_path(key):
    kind = key.split("|")[0]
    if kind == "d3":
        return HC_E / "d3" / (key.replace("|", "_") + ".pkl")
    ds = key.split("|")[1]
    return (HC_D if ds == "dsec" else HC_E) / "d1" / (key.replace("|", "_") + ".pkl")


def check_019(key, g):
    """Acceptance check 3: the bits of lossless, sparse and every qp<q>, and the F of every qp<q>, equal 019's."""
    ref = HR.load(key)["groups"][0]
    if ref["w"] != g["w"]:
        return {"field": "w", "ours": g["w"], "019": ref["w"]}
    for s, k in FINE_GRIDS:
        gn = f"s{s}_k{k}"
        a, b = g["fine"][gn]["modes"], ref["d1"][gn]["modes"]
        for m in CHECK_MODES:
            if a[m]["bits"] != b[m]["bits"]:
                return {"grid": gn, "mode": m, "field": "bits", "ours": a[m]["bits"], "019": b[m]["bits"]}
            if m.startswith("qp") and a[m]["fid"]["F"] != b[m]["fid"]["F"]:
                return {"grid": gn, "mode": m, "field": "F", "ours": a[m]["fid"]["F"], "019": b[m]["fid"]["F"]}
    return None


def task(key):
    out = out_path(key)
    if out.exists():
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    t_start, c_start = time.time(), cpu_now()
    kind = key.split("|")[0]
    res = {"key": key, "commit": (mp.REPO / "COMMIT").read_text().strip()}
    if kind == "d3":
        _, tau, n, seed = key.split("|")
        c = HR.D3
        ev = hd.edge_scene(c["width"], c["height"], c["u"], float(tau), int(n), c["sigma_frac"], c["spacing"],
                           c["n_windows"], int(seed))
        res.update({"tau": float(tau), "n": int(n), "seed": int(seed), "n_events": int(len(ev[0])), "grids": {}})
        for s, k in FINE_GRIDS:
            c0 = cpu_now()
            o = hc.code_controls(hd.windows_of(ev, 1, hd.K_WIN), 1, s, k, c["width"], c["height"], hc.FINE_MODES,
                                 1.0, 0.0, workdir=str(WORK))
            o["cpu_s"] = cpu_now() - c0
            res["grids"][f"s{s}_k{k}"] = o
    else:
        _, ds, rid, j = key.split("|")
        j = int(j)
        W, H = FB.DIMS[ds]
        r = next(r for r in FB.remake_groups(ds, "R", rid) if r["j"] == j)
        w = r["w"]
        toff = HR.RC.t_offset_of(rid) if ds == "dsec" else None
        e = HR.events(ds, rid, [w])[w]
        tracks = HR.RC.load_tracks(ds, rid, t_offset=toff)
        res["read_s"] = time.time() - t_start
        windows, bg, tasks = HR.context(ds, rid, w, e, tracks)
        g = {"j": j, "w": w, "background": bg, "n_true": [int(len(v[0])) for v in windows], "fine": {}, "coarse": {}}
        c0 = cpu_now()
        for s, k in FINE_GRIDS:
            c1 = cpu_now()
            o = hc.code_controls(windows, w, s, k, W, H, hc.FINE_MODES, bg["phi"], bg["theta"], workdir=str(WORK))
            o["cpu_s"] = cpu_now() - c1
            g["fine"][f"s{s}_k{k}"] = o
        g["fine_cpu_s"] = cpu_now() - c0
        c0 = cpu_now()
        for s, k in hc.COARSE_GRIDS:
            c1 = cpu_now()
            o = hc.code_controls(windows, w, s, k, W, H, hc.COARSE_MODES, bg["phi"], bg["theta"], tasks=tasks,
                                 task_modes=COARSE_LOSSY, workdir=str(WORK))
            o["cpu_s"] = cpu_now() - c1
            g["coarse"][f"s{s}_k{k}"] = o
        g["coarse_cpu_s"] = cpu_now() - c0
        g["finished_utc"] = time.time()
        mis = check_019(f"d1|{ds}|{rid}|{j}", g)
        g["check_019"] = {"pass": mis is None, "first_mismatch": mis}
        if mis is not None:
            (HC_E / f"MISMATCH_{key.replace('|', '_')}.json").write_text(json.dumps({"key": key, **mis}, default=float) + "\n")
        res["groups"] = [g]
    res["task_wall_s"], res["task_cpu_s"] = time.time() - t_start, cpu_now() - c_start
    tmp = out.with_suffix(".tmp")
    with open(tmp, "wb") as f:
        pickle.dump(res, f, protocol=5)
    tmp.rename(out)


def load(key):
    with open(out_path(key), "rb") as f:
        return pickle.load(f)


def plan():
    d1 = {ds: [f"d1|{ds}|{rid}|{r['j']}" for rid, rr in HR.groups(ds, "d1").items() for r in rr] for ds in ("dsec", "etram")}
    inter = []
    for i in range(max(len(d1["dsec"]), len(d1["etram"]))):
        inter += ([d1["dsec"][i]] if i < len(d1["dsec"]) else []) + ([d1["etram"][i]] if i < len(d1["etram"]) else [])
    d3 = [f"d3|{tau}|{n}|{seed}" for tau in HR.D3["taus"] for n in HR.D3["ns"] for seed in HR.D3["seeds"]]
    return d3[:1] + inter[:20] + inter[20:] + d3[1:]


def run(workers):
    (HC_E / "logs").mkdir(parents=True, exist_ok=True)
    if not (HC_E / "plan.json").exists():
        (HC_E / "plan.json").write_text(json.dumps({"commit": (mp.REPO / "COMMIT").read_text().strip(),
                                                    "tasks": plan()}) + "\n")
    tasks = json.loads((HC_E / "plan.json").read_text())["tasks"]
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
        if (HC_E / "STOP").exists() or list(HC_E.glob("MISMATCH_*.json")):
            if pending:
                log("STOP or MISMATCH: no further task is launched")
            pending = []
        target = M._target_workers(HC_E, workers)
        while pending and len(running) < target and M._mem_available_gb() > 40.0:
            k = pending.pop(0)
            lf = open(HC_E / "logs" / (k.replace("|", "_") + ".log"), "w")
            running[subprocess.Popen([sys.executable, __file__, "one", k], stdout=lf, stderr=subprocess.STDOUT)] = k
            time.sleep(1)
        time.sleep(10)
    log(f"DONE failed={sorted(k for k, v in fails.items() if v >= 2)}")


def project():
    tasks = json.loads((HC_E / "plan.json").read_text())["tasks"]
    res, tot = {}, 0.0
    for ds in ("etram", "dsec"):
        rows = []
        for k in tasks:
            if k.startswith(f"d1|{ds}|") and out_path(k).exists():
                d = load(k)
                rows.append((d["groups"][0]["finished_utc"], d["task_cpu_s"]))
        rows.sort()
        first = [c for _, c in rows[:10]]
        n1 = sum(len(v) for v in HR.groups(ds, "d1").values())
        res[ds] = {"n_first": len(first), "cpu_s_per_group": float(np.mean(first)) if first else None, "n_groups": n1,
                   "cpu_h": float(np.mean(first)) * n1 / 3600 if len(first) == 10 else None}
    d3 = [load(k) for k in tasks if k.startswith("d3|") and out_path(k).exists()]
    n3 = sum(1 for k in tasks if k.startswith("d3|"))
    res["d3"] = {"n_first": len(d3[:1]), "cpu_s_per_scene": d3[0]["task_cpu_s"] if d3 else None, "n_scenes": n3,
                 "cpu_h": d3[0]["task_cpu_s"] * n3 / 3600 if d3 else None}
    ok = all(v["cpu_h"] is not None for v in res.values())
    tot = sum(v["cpu_h"] for v in res.values()) if ok else None
    out = {"projection": res, "cpu_h": tot, "limit_cpu_h": 350, "pass": ok and tot <= 350}
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
