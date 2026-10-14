"""Directive 019: where a frame-based video coder pays on event streams (D1, D2, D3).

  python3 scripts/hd_run.py run [--workers W]          # Section 5, resumable
  python3 scripts/hd_run.py one KEY                    # one task
  python3 scripts/hd_run.py project                    # Section 7, from the first 10 D1 groups of each dataset
  python3 scripts/hd_run.py determinism OUT.json       # acceptance check 3

Groups (Section 4): ``fb_run.remake_groups(ds, "R", rid)``; D1 takes ``j % 40 == 0`` (eTraM) and ``j % 20 == 0``
(DSEC), D2 takes ``j % 5 == 0``. Every D1 group is a D2 group, so a D1 task runs D2 on its group too. Tasks:

  d1|DS|RID|J      one D1 group: ``code_counts`` on every (s, k), then ``represent`` on every (s, k, placement)
  d2|DS|RID        the D2 groups of a recording that are not D1 groups, one read
  d3|TAU|N|SEED    one model scene: ``oracle_shift`` and ``code_counts`` on every (s, k)

Events of a group: ``[w T0 - FIT_WINDOW_US, (w + 4) T0)``. eTraM is read with ``bk_run.read`` (at most six reads
at once); DSEC comes from the caches of directive 017 (``fm_run.dsec_events``). Background, tasks, boxes and
squares as Section 4 states. Outputs: eTraM and D3 under ``~/prjs/event_coding/hd/``, DSEC under
``/data/<user>/event_coding/ds/hd/``; x265 scratch under ``/data/<user>/event_coding/ds/hd/work/``.
CPU time of a group counts the ffmpeg processes it starts (``RUSAGE_CHILDREN``).
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
from ec import blockcodec as bc, families as fa, fbc, hevcdiag as hd, mp, regions as rg  # noqa: E402
import bk_run as BK  # noqa: E402
import fb_run as FB  # noqa: E402
import fm_run as FM  # noqa: E402
import mp_measure as M  # noqa: E402
import rc_run as RC  # noqa: E402

T0 = bc.T0_US
HD_E = Path.home() / "prjs" / "event_coding" / "hd"
HD_D = RC.DR.BASE / "ds" / "hd"
WORK = HD_D / "work"
D1_MOD = {"etram": 40, "dsec": 20}
D2_MOD = 5
MODES = ("lossless", "sparse") + tuple(f"qp{q}" for q in hd.QPS)
D3 = {"width": 320, "height": 240, "u": 6, "taus": (250, 500, 1000, 2000, 4000, 8000), "ns": (1, 3), "seeds": (1, 2, 3),
      "sigma_frac": 0.05, "spacing": 40, "n_windows": 12}
READ_SLOTS_E = 6


def outdir(kind, ds=None):
    return HD_D if ds == "dsec" else HD_E


def cpu_now():
    return FM.cpu_now()


# ------------------------------------------------------------------------------------------- groups and events
def groups(ds, which):
    rows = {}
    for rid in FB.recordings(ds, "R"):
        rr = [r for r in FB.remake_groups(ds, "R", rid) if r["j"] % (D1_MOD[ds] if which == "d1" else D2_MOD) == 0]
        if rr:
            rows[rid] = rr
    return rows


def events(ds, rid, ws):
    """The events of ``[w T0 - FIT_WINDOW_US, (w + 4) T0)`` for each key window of ``ws``, as int64."""
    out = {}
    if ds == "etram":
        lk = M._read_lock(HD_E, slots=READ_SLOTS_E)
        ev = BK.read(rid)
        lk.close()
        t, x, y, p = ev.t_us, ev.x, ev.y, ev.p
        for w in ws:
            a, b = np.searchsorted(t, (w * T0 - fbc.FIT_WINDOW_US, (w + hd.K_WIN) * T0))
            out[w] = tuple(np.asarray(v[a:b], dtype=np.int64).copy() for v in (t, x, y, p))
        del ev, t, x, y, p
    else:
        for w, e in FM.dsec_events(rid, ws).items():
            a, b = np.searchsorted(e[0], (w * T0 - fbc.FIT_WINDOW_US, (w + hd.K_WIN) * T0))
            out[w] = tuple(v[a:b] for v in e)
    return out


def context(ds, rid, w, e, tracks):
    """Windows, background, and the tasks of Section 4 for one group."""
    W, H = FB.DIMS[ds]
    edges = np.searchsorted(e[0], [(w + m) * T0 for m in range(hd.K_WIN + 1)])
    windows = [tuple(v[edges[m]:edges[m + 1]] for v in e) for m in range(hd.K_WIN)]
    bg = fa.background_rate(e, max(0, w * T0 - fbc.FIT_WINDOW_US), (w + 1) * T0, W, H)
    boxes = None if tracks is None else {m: rg.boxes_at(tracks, w + m, W, H) for m in (1, 2, 3)}
    squares = FB.squares_for(windows[2], W, H)
    return windows, bg, fa._Tasks(windows, w, boxes, squares)


def d2_group(ds, w, windows, tasks):
    W, H = FB.DIMS[ds]
    return {f"s{s}_k{k}_{pl}": hd.represent(windows, w, s, k, W, H, pl, tasks=tasks)
            for s in hd.SPACES for k in hd.KS for pl in hd.PLACEMENTS}


# ------------------------------------------------------------------------------------------- tasks
def out_path(key):
    kind = key.split("|")[0]
    if kind == "d3":
        return HD_E / "d3" / (key.replace("|", "_") + ".pkl")
    ds = key.split("|")[1]
    return outdir(kind, ds) / kind / (key.replace("|", "_") + ".pkl")


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
        tau, n, seed = float(tau), int(n), int(seed)
        c = D3
        ev = hd.edge_scene(c["width"], c["height"], c["u"], tau, n, c["sigma_frac"], c["spacing"], c["n_windows"], seed)
        res.update({"tau": tau, "n": n, "seed": seed, "n_events": int(len(ev[0])), "grids": {}})
        for s in hd.SPACES:
            for k in hd.KS:
                c0 = cpu_now()
                o = hd.oracle_shift(ev, c["u"], s, k, c["width"], c["height"], c["n_windows"])
                cc = hd.code_counts(hd.windows_of(ev, 1, hd.K_WIN), 1, s, k, c["width"], c["height"], MODES, 1.0, 0.0,
                                    workdir=str(WORK))
                res["grids"][f"s{s}_k{k}"] = {"oracle": o, "code": cc, "cpu_s": cpu_now() - c0}
    else:
        ds, rid = key.split("|")[1:3]
        W, H = FB.DIMS[ds]
        if kind == "d1":
            j = int(key.split("|")[3])
            rows = [r for r in FB.remake_groups(ds, "R", rid) if r["j"] == j]
        else:
            rows = [r for r in groups(ds, "d2").get(rid, []) if r["j"] % D1_MOD[ds] != 0]
        toff = RC.t_offset_of(rid) if ds == "dsec" else None
        evs = events(ds, rid, [r["w"] for r in rows])
        tracks = RC.load_tracks(ds, rid, t_offset=toff)
        res["read_s"] = time.time() - t_start
        res["groups"] = []
        for r in rows:
            w = r["w"]
            windows, bg, tasks = context(ds, rid, w, evs[w], tracks)
            g = {"j": r["j"], "w": w, "background": bg, "n_true": [int(len(v[0])) for v in windows]}
            if kind == "d1":
                g["d1"] = {}
                c0 = cpu_now()
                for s in hd.SPACES:
                    for k in hd.KS:
                        c1 = cpu_now()
                        o = hd.code_counts(windows, w, s, k, W, H, MODES, bg["phi"], bg["theta"], tasks=tasks,
                                           workdir=str(WORK))
                        o["cpu_s"] = cpu_now() - c1
                        g["d1"][f"s{s}_k{k}"] = o
                g["d1_cpu_s"] = cpu_now() - c0
            c0 = cpu_now()
            g["d2"] = d2_group(ds, w, windows, tasks)
            g["d2_cpu_s"] = cpu_now() - c0
            g["finished_utc"] = time.time()
            res["groups"].append(g)
    res["task_wall_s"], res["task_cpu_s"] = time.time() - t_start, cpu_now() - c_start
    tmp = out.with_suffix(".tmp")
    with open(tmp, "wb") as f:
        pickle.dump(res, f, protocol=5)
    tmp.rename(out)


def plan():
    d1 = {ds: [f"d1|{ds}|{rid}|{r['j']}" for rid, rr in groups(ds, "d1").items() for r in rr] for ds in ("dsec", "etram")}
    d1_all = []
    for i in range(max(len(d1["dsec"]), len(d1["etram"]))):        # interleaved: the first D1 groups hold both
        d1_all += ([d1["dsec"][i]] if i < len(d1["dsec"]) else []) + ([d1["etram"][i]] if i < len(d1["etram"]) else [])
    d2 = [f"d2|{ds}|{rid}" for ds in ("dsec", "etram") for rid, rr in groups(ds, "d2").items()
          if any(r["j"] % D1_MOD[ds] for r in rr)]
    d3 = [f"d3|{tau}|{n}|{seed}" for tau in D3["taus"] for n in D3["ns"] for seed in D3["seeds"]]
    return d1_all[:20] + d3[:1] + d1_all[20:] + d2 + d3[1:]


def run(workers):
    HD_E.mkdir(parents=True, exist_ok=True)
    (HD_E / "logs").mkdir(exist_ok=True)
    if not (HD_E / "plan.json").exists():
        (HD_E / "plan.json").write_text(json.dumps({"commit": (mp.REPO / "COMMIT").read_text().strip(),
                                                    "tasks": plan()}) + "\n")
    tasks = json.loads((HD_E / "plan.json").read_text())["tasks"]
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
        if (HD_E / "STOP").exists():
            pending = []
        target = M._target_workers(HD_E, workers)
        while pending and len(running) < target and M._mem_available_gb() > 40.0:
            k = pending.pop(0)
            lf = open(HD_E / "logs" / (k.replace("|", "_") + ".log"), "w")
            running[subprocess.Popen([sys.executable, __file__, "one", k], stdout=lf, stderr=subprocess.STDOUT)] = k
            time.sleep(1)
        time.sleep(10)
    log(f"DONE failed={sorted(k for k, v in fails.items() if v >= 2)}")


def load(key):
    with open(out_path(key), "rb") as f:
        return pickle.load(f)


def project():
    """Section 7: D1 and D2 CPU per group from the first 10 D1 groups of each dataset (each D1 task also runs D2 on its
    group), D3 from its first finished scene, times the numbers of groups and scenes."""
    tasks = json.loads((HD_E / "plan.json").read_text())["tasks"]
    res, tot = {}, 0.0
    for ds in ("etram", "dsec"):
        rows = []
        for k in tasks:
            if k.startswith(f"d1|{ds}|") and out_path(k).exists():
                d = load(k)
                g = d["groups"][0]
                rows.append((g["finished_utc"], g["d1_cpu_s"], g["d2_cpu_s"], d["task_cpu_s"] - g["d1_cpu_s"] - g["d2_cpu_s"]))
        rows.sort()
        first = rows[:10]
        n1 = sum(len(v) for v in groups(ds, "d1").values())
        n2 = sum(len(v) for v in groups(ds, "d2").values())
        n_rec2 = len(groups(ds, "d2"))
        if len(first) < 10:
            res[ds] = {"n_first": len(first), "cpu_h": None}
            continue
        d1, d2, rd = (float(np.mean([r[i] for r in first])) for i in (1, 2, 3))
        cpu_h = (n1 * (d1 + d2 + rd) + (n2 - n1) * d2 + n_rec2 * rd) / 3600
        res[ds] = {"n_first": 10, "d1_cpu_s_per_group": d1, "d2_cpu_s_per_group": d2, "read_cpu_s_per_task": rd,
                   "n_d1_groups": n1, "n_d2_groups": n2, "n_d2_tasks": n_rec2, "cpu_h": cpu_h}
        tot += cpu_h
    d3 = [load(k) for k in tasks if k.startswith("d3|") and out_path(k).exists()]
    n3 = sum(1 for k in tasks if k.startswith("d3|"))
    if d3:
        res["d3"] = {"n_first": len(d3), "cpu_s_per_scene": float(np.mean([d["task_cpu_s"] for d in d3])), "n_scenes": n3,
                     "cpu_h": float(np.mean([d["task_cpu_s"] for d in d3])) * n3 / 3600}
        tot += res["d3"]["cpu_h"]
    ok = all(res.get(k, {}).get("cpu_h") is not None for k in ("etram", "dsec", "d3"))
    out = {"projection": res, "cpu_h": tot if ok else None, "limit_cpu_h": 300, "pass": ok and tot <= 300}
    print(json.dumps(out, indent=1))
    return out


def determinism(out):
    """Acceptance check 3: the first D1 group of two recordings of each dataset, ``code_counts`` at s = 2, k = 12
    twice; every bit count must be equal."""
    WORK.mkdir(parents=True, exist_ok=True)
    res = {"rule": "first D1 group of the first two recordings with D1 groups, per dataset; code_counts at s = 2, "
                   "k = 12, every mode, twice", "groups": [], "pass": True}
    for ds in ("etram", "dsec"):
        W, H = FB.DIMS[ds]
        for rid, rr in list(groups(ds, "d1").items())[:2]:
            w = rr[0]["w"]
            toff = RC.t_offset_of(rid) if ds == "dsec" else None
            e = events(ds, rid, [w])[w]
            windows, bg, _ = context(ds, rid, w, e, RC.load_tracks(ds, rid, t_offset=toff))
            runs = [hd.code_counts(windows, w, 2, 12, W, H, MODES, bg["phi"], bg["theta"], workdir=str(WORK)) for _ in range(2)]
            bits = [{m: (v["bits"], v.get("param_bits"), tuple(f["bits"] for f in v.get("frames", [])))
                     for m, v in r["modes"].items()} for r in runs]
            eq = bits[0] == bits[1]
            res["pass"] &= eq
            res["groups"].append({"dataset": ds, "recording": rid, "j": rr[0]["j"], "w": w, "equal": eq,
                                  "bits": {m: v[0] for m, v in bits[0].items()}})
            print(ds, rid, rr[0]["j"], eq, flush=True)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(res, indent=1) + "\n")
    print("pass", res["pass"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode")
    ap.add_argument("args", nargs="*")
    ap.add_argument("--workers", type=int, default=24)
    a = ap.parse_args()
    {"run": lambda: run(a.workers), "one": lambda: task(*a.args), "project": project,
     "determinism": lambda: determinism(*a.args)}[a.mode]()


if __name__ == "__main__":
    main()
