"""Directive 009 (with Amendment 1): Stage 0, the census, the projection and Stage R on DSEC.

  python3 scripts/ds_run.py stage0 DSDIR
  python3 scripts/ds_run.py receive STREAMDIR OUT.json
  python3 scripts/ds_run.py stage0_check DSDIR OUT.json
  python3 scripts/ds_run.py census DSDIR [--workers W]
  python3 scripts/ds_run.py project DSDIR OUT.json
  python3 scripts/ds_run.py run DSDIR --spacing S [--workers W]
  python3 scripts/ds_run.py one DSDIR KEY --spacing S
  python3 scripts/ds_run.py streams DSDIR

Events are read with ``ec.dsec.read_events`` (unchanged), the stored times without ``t_offset``.
The configuration is frozen: ``blocks=(20,)``, the five densities, the three models,
``grid_for=(20, 1.0)``, ``records_for=(20, 1.0)``. A task keeps, right after reading, only the
events of the windows its groups use, as x, y in uint16 and p in uint8; ``evaluate_group``
reads nothing else, so its results are unchanged. ``fit_group`` is timed from here, as in
directive 007 (the wrapper of ``scripts/bk_run.py``).
"""
from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS",
           "VECLIB_MAXIMUM_THREADS", "NUMBA_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import argparse
import hashlib
import json
import multiprocessing as mpr
import pickle
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ec import blockcodec as bc, dsec, mp  # noqa: E402
import bk_run as BK  # noqa: E402   (fit_group timing wrapper, stream comparison; it opens no file on import)
import mp_measure as M  # noqa: E402

W, H, T0 = dsec.WIDTH, dsec.HEIGHT, bc.T0_US
BASE = Path("/data") / os.environ.get("USER", "") / "event_coding"
DATA = BASE / "dsec"
FROZEN = (20, 1.0)
CFG = "B20_rho1.0"
STAGE0_GROUPS = 5
CHUNK = 12                                  # groups per task in Stage R
READ_SLOTS = 1                              # one read at a time: a read of the largest file peaks near 145 GB
BYTES_PER_EVENT_PEAK = 44                   # reader: four int64 arrays plus the stored arrays during the cast


def sequences():
    d = yaml.safe_load((mp.REPO / "config" / "population_dsec.yaml").read_text())
    return [s["name"] for s in d["sequences"]]


def inventory():
    p = BASE / "ds" / "stageD" / "format.json"
    return json.loads(p.read_text())["inventory"] if p.exists() else {}


def _wait_memory(need_bytes, poll=10):
    while M._mem_available_gb() * 1e9 < need_bytes + 20e9:
        time.sleep(poll)


def read(seq, lock_dir=None, window=None):
    """Events of one sequence through ec.dsec.read_events; with ``window`` = (w_lo, w_hi) only [w_lo T0, w_hi T0)."""
    lk = M._read_lock(lock_dir, slots=READ_SLOTS) if lock_dir else None
    inv = inventory().get(seq)
    if lk and inv:
        _wait_memory(inv["n_events"] * BYTES_PER_EVENT_PEAK)
    t, x, y, p, info = dsec.read_events(DATA / seq / "events.h5")
    if inv and info["n_events"] != inv["n_events"]:
        raise RuntimeError(f"{seq}: {info['n_events']} events, the inventory says {inv['n_events']}")
    if window is not None:
        a, b = np.searchsorted(t, (window[0] * T0, window[1] * T0))
        t, x, y, p = t[a:b].copy(), x[a:b], y[a:b], p[a:b]
    out = (t, x.astype(np.uint16), y.astype(np.uint16), p.astype(np.uint8), info)
    del x, y, p
    if lk:
        lk.close()
    return out


def key_windows(t_first, t_last, S):
    w_first = int(t_first) // T0
    out, j = [], 0
    while (w_first + 30 + S * j + 11) * T0 <= t_last:
        out.append(w_first + 30 + S * j)
        j += 1
    return out


def stage0_sequences():
    s = sequences()
    return [s[0], s[len(s) // 2]]


# ------------------------------------------------------------------------------------------- Stage 0
def stage0(dsdir):
    dsdir = Path(dsdir)
    out = dsdir / "stage0"
    if out.exists() and any(out.iterdir()):
        sys.exit(f"{out} exists and is not empty")
    (out / "streams").mkdir(parents=True, exist_ok=True)
    res = {"recordings": {}, "times": []}
    for seq in stage0_sequences():
        t, x, y, p, info = read(seq)
        ws = key_windows(info["t_first_us"], info["t_last_us"], 30)[:STAGE0_GROUPS]
        groups, w_prev = [], 0
        for j, w in enumerate(ws):
            BK._FIT_TIMES.clear()
            t0 = time.perf_counter()
            g = bc.evaluate_group(t, x, y, p, w, w_prev, W, H, blocks=(FROZEN[0],), grid_for=FROZEN, records_for=FROZEN)
            el = time.perf_counter() - t0
            res["times"].append({"rid": seq, "j": j, "w": w, "evaluate_group_s": el, "fits": list(BK._FIT_TIMES)})
            groups.append(g)
            w_prev = w
            print(f"{seq} group {j} w={w} {el:.1f}s", flush=True)
        with open(out / f"sender_{seq}.pkl", "wb") as f:
            pickle.dump(groups, f, protocol=5)
        for model in bc.MODELS:
            for coder in bc.CODERS:
                for K in bc.GROUPS:
                    name = f"{model}_{coder}_K{K}"
                    with open(out / "streams" / f"{seq}__{name}.ec07", "wb") as f:
                        f.write(bc.encode_header(coder, model, K, W, H, FROZEN[0]))
                        for g in groups:
                            f.write(g["records"][name])
        res["recordings"][seq] = {"w": ws, "n_events": info["n_events"]}
    (out / "sender.json").write_text(json.dumps(res, indent=1) + "\n")


def receive(streamdir, out):
    """The receiver: the stream files, and the events of the sequence named in the file name to score."""
    files = sorted(Path(streamdir).glob("*.ec07"))
    by = {}
    for f in files:
        by.setdefault(f.name.split("__")[0], []).append(f)
    res = {}
    for seq, fs in by.items():
        t, x, y, p, _ = read(seq)
        for f in fs:
            buf = f.read_bytes()
            res[f.name] = {"length": len(buf), "sha256": hashlib.sha256(buf).hexdigest(),
                           "groups": bc.evaluate_stream(buf, t, x, y, p)}
        del t, x, y, p
        print(seq, len(fs), "streams", flush=True)
    Path(out).write_text(json.dumps(res) + "\n")
    print(len(res), "streams scored", flush=True)


def stage0_check(dsdir, out):
    d = Path(dsdir) / "stage0"
    rec = json.loads((d / "receiver.json").read_text())
    snd = json.loads((d / "sender.json").read_text())
    res = {"streams": {}, "groups": {}, "pass": True}
    for seq in snd["recordings"]:
        with open(d / f"sender_{seq}.pkl", "rb") as f:
            groups = pickle.load(f)
        n, bad = BK.checks_of_groups(groups)
        res["groups"][seq] = {"n_config_model_group": n, "failures": bad}
        res["pass"] &= not bad
        for model in bc.MODELS:
            for coder in bc.CODERS:
                for K in bc.GROUPS:
                    name = f"{seq}__{model}_{coder}_K{K}.ec07"
                    exp_len, b = BK.compare_streams(groups, rec[name], CFG, model, coder, K)
                    res["streams"][name] = {"length": rec[name]["length"], "expected_length": exp_len,
                                            "sha256": rec[name]["sha256"], "failures": b}
                    res["pass"] &= not b
    res["n_streams"] = len(res["streams"])
    res["times"] = snd["times"]
    Path(out).write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps({"pass": res["pass"], "n_streams": res["n_streams"],
                      "group_failures": {k: len(v["failures"]) for k, v in res["groups"].items()},
                      "stream_failures": sum(len(v["failures"]) for v in res["streams"].values())}, indent=1))


# ------------------------------------------------------------------------------------------- census
def _census_one(args):
    seq, lock_dir = args
    t, x, y, p, info = read(seq, lock_dir)
    rows = []
    for w in key_windows(info["t_first_us"], info["t_last_us"], 30):
        a, b = np.searchsorted(t, (w * T0, (w + 1) * T0))
        _, cnt = np.unique(bc.block_ids(x[a:b], y[a:b], FROZEN[0], W), return_counts=True)
        rows.append({"w": int(w), "n_events": int(b - a),
                     "20": [int((cnt >= bc.threshold(FROZEN[0], rho)).sum()) for rho in bc.DENSITIES]})
    return seq, {"n_events": info["n_events"], "t_first_us": info["t_first_us"], "t_last_us": info["t_last_us"],
                 "key_windows_S30": rows}


def census(dsdir, workers):
    dsdir = Path(dsdir)
    seqs = sorted(sequences(), key=lambda s: -inventory()[s]["n_events"])
    res = {}
    with mpr.get_context("spawn").Pool(workers, maxtasksperchild=1) as pool:
        for k, (s, r) in enumerate(pool.imap_unordered(_census_one, [(s, str(dsdir)) for s in seqs]), 1):
            res[s] = r
            print(f"[{k}/{len(seqs)}] {s} {len(r['key_windows_S30'])} key windows", flush=True)
    (dsdir / "census.json").write_text(json.dumps({
        "directive": "009", "spacing_of_listing": 30, "block": FROZEN[0], "densities": list(bc.DENSITIES),
        "note": "per key window at S = 30: events of the key window and the active blocks at B = 20 for each density",
        "recordings": {s: res[s] for s in sorted(res)}}) + "\n")


def groups_at(c, S):
    ws = key_windows(c["t_first_us"], c["t_last_us"], S)
    by = {r["w"]: r for r in c["key_windows_S30"]}
    return [by[w] for w in ws]


def project(dsdir, out):
    dsdir = Path(dsdir)
    s0 = json.loads((dsdir / "stage0" / "sender.json").read_text())
    cen = json.loads((dsdir / "census.json").read_text())["recordings"]
    per, c0s = [], []
    for t in s0["times"]:
        fits = [f for f in t["fits"] if f["model"] in ("translation", "affine")]
        nb = fits[0]["n_blocks"] if fits else 0
        if nb > 0:
            per.append(sum(f["s"] for f in fits) / nb)
        c0s.append(t["evaluate_group_s"] - sum(f["s"] for f in t["fits"]))
    c20, c0 = float(np.mean(per)), float(np.mean(c0s))
    proj = {}
    for S in (30, 60, 90):
        gs = [g for s in cen for g in groups_at(cen[s], S)]
        proj[str(S)] = {"n_groups": len(gs), "stage_R_cpu_h": sum(g["20"][0] * c20 + c0 for g in gs) / 3600}
    chosen = next((S for S in (30, 60, 90) if proj[str(S)]["stage_R_cpu_h"] <= 150), None)
    res = {"c_20_s_per_block": c20, "c_20_samples": per, "c_0_s_per_group": c0, "c_0_samples": c0s,
           "limit_cpu_h": 150, "projection": proj, "spacing_chosen": chosen,
           "rule": "Section 12: S = 30 unless Stage R exceeds 150 CPU-hours, then 60, then 90, else stop after Stage 0"}
    Path(out).write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps(res, indent=1))


# ------------------------------------------------------------------------------------------- Stage R
def plan(dsdir, S):
    cen = json.loads((Path(dsdir) / "census.json").read_text())["recordings"]
    tasks = []
    for s in sequences():
        gs = groups_at(cen[s], S)
        for c in range(0, len(gs), CHUNK):
            tasks.append([f"{s}|{c // CHUNK}", float(sum(g["20"][0] for g in gs[c:c + CHUNK]) + 50 * len(gs[c:c + CHUNK]))])
    tasks.sort(key=lambda t: -t[1])
    return tasks


def task(dsdir, key, S):
    dsdir = Path(dsdir)
    seq, ci = key.split("|")
    ci = int(ci)
    out = dsdir / "R" / f"groups_{seq}_{ci:03d}.pkl"
    if out.exists():
        return
    t_start = time.time()
    c = json.loads((dsdir / "census.json").read_text())["recordings"][seq]
    ws = key_windows(c["t_first_us"], c["t_last_us"], S)
    js = list(range(ci * CHUNK, min(len(ws), (ci + 1) * CHUNK)))
    t, x, y, p, info = read(seq, dsdir / "R", window=(ws[js[0]], ws[js[-1]] + bc.N_TARGETS + 1))
    res = []
    for j in js:
        w, w_prev = ws[j], (ws[j - 1] if j > 0 else 0)
        BK._FIT_TIMES.clear()
        t0 = time.perf_counter()
        g = bc.evaluate_group(t, x, y, p, w, w_prev, W, H, blocks=(FROZEN[0],), grid_for=FROZEN, records_for=FROZEN)
        res.append({"j": j, "w": w, "w_prev": w_prev, "evaluate_group_s": time.perf_counter() - t0,
                    "fits": list(BK._FIT_TIMES), "group": g})
    tmp = out.with_suffix(".tmp")
    with open(tmp, "wb") as f:
        pickle.dump(res, f, protocol=5)
    tmp.rename(out)
    (dsdir / "R" / f"task_{seq}_{ci:03d}.json").write_text(json.dumps(
        {"seq": seq, "chunk": ci, "js": js, "n_events_file": info["n_events"], "wall_s": time.time() - t_start}) + "\n")


def _out_name(key):
    s, c = key.split("|")
    return f"groups_{s}_{int(c):03d}.pkl"


def schedule(dsdir, max_workers, S, min_free_gb=40.0):
    out = Path(dsdir) / "R"
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
            log_f = open(out / "logs" / f"{_out_name(t[0])[7:-4]}.log", "w")
            running[subprocess.Popen([sys.executable, __file__, "one", str(dsdir), t[0], "--spacing", str(S)],
                                     stdout=log_f, stderr=subprocess.STDOUT)] = t
            time.sleep(2)
        time.sleep(10)
    log(f"DONE failed={sorted(k for k, v in fails.items() if v >= 2)}")


def run(dsdir, workers, S):
    out = Path(dsdir) / "R"
    if (out / "plan.json").exists():
        if not (out / "RESUME").exists():
            sys.exit(f"{out} holds a run; touch {out}/RESUME to resume it")
    else:
        if out.exists() and any(out.iterdir()):
            sys.exit(f"{out} exists and is not empty")
        (out / "logs").mkdir(parents=True, exist_ok=True)
        (out / "plan.json").write_text(json.dumps({"commit": (mp.REPO / "COMMIT").read_text().strip(), "spacing": S,
                                                   "frozen": list(FROZEN), "chunk": CHUNK,
                                                   "tasks": plan(dsdir, S)}) + "\n")
    schedule(dsdir, workers, S)


def load_groups(dsdir, seq):
    out = []
    for f in sorted((Path(dsdir) / "R").glob(f"groups_{seq}_*.pkl")):
        with open(f, "rb") as fh:
            out += pickle.load(fh)
    out.sort(key=lambda r: r["j"])
    return out


def streams(dsdir):
    """Stage R: the eight streams of affine and the eight of translation (two coders, four K) of every sequence."""
    dsdir = Path(dsdir)
    sd = dsdir / "R_streams"
    sd.mkdir(exist_ok=True)
    for seq in sequences():
        groups = load_groups(dsdir, seq)
        for model in ("affine", "translation"):
            for coder in bc.CODERS:
                for K in bc.GROUPS:
                    name = f"{model}_{coder}_K{K}"
                    with open(sd / f"{seq}__{name}.ec07", "wb") as f:
                        f.write(bc.encode_header(coder, model, K, W, H, FROZEN[0]))
                        for r in groups:
                            f.write(r["group"]["records"][name])
    print("streams written", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode")
    ap.add_argument("args", nargs="*")
    ap.add_argument("--workers", type=int, default=24)
    ap.add_argument("--spacing", type=int, default=0)
    a = ap.parse_args()
    f = {"stage0": lambda: stage0(*a.args), "receive": lambda: receive(*a.args),
         "stage0_check": lambda: stage0_check(*a.args), "census": lambda: census(a.args[0], a.workers),
         "project": lambda: project(*a.args), "run": lambda: run(a.args[0], a.workers, a.spacing),
         "one": lambda: task(a.args[0], a.args[1], a.spacing), "streams": lambda: streams(*a.args)}
    f[a.mode]()


if __name__ == "__main__":
    main()
