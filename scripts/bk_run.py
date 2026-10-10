"""Directive 007: Stage P, Stage 0, the census, the cost projection, Stages T and R.

  python3 scripts/bk_run.py preflight OUT.json
  python3 scripts/bk_run.py stage0 BKDIR                  # sender: two recordings, five groups, 48 stream files
  python3 scripts/bk_run.py receive STREAMDIR OUT.json     # receiver: a separate process, stream files only
  python3 scripts/bk_run.py stage0_check BKDIR OUT.json
  python3 scripts/bk_run.py census BKDIR [--workers W]
  python3 scripts/bk_run.py project BKDIR OUT.json
  python3 scripts/bk_run.py run T|R BKDIR --spacing S [--workers W] [--frozen B,rho]
  python3 scripts/bk_run.py one T|R BKDIR KEY --spacing S [--frozen B,rho]
  python3 scripts/bk_run.py streams BKDIR                  # Stage R: write the eight streams of each recording

Every process that reads a recording checks its number of events against
results/mp/preflight.json (P4). ``ec.blockcodec`` is used as it is. Times of
``fit_group`` are taken by wrapping it from here (Section 6, Timing).
"""
from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS",
           "VECLIB_MAXIMUM_THREADS", "NUMBA_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import argparse
import hashlib
import json
import math
import multiprocessing as mpr
import pickle
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ec import baseline, blockcodec as bc, mp  # noqa: E402
import mp_measure as M  # noqa: E402

W, H, T0 = 1280, 720, bc.T0_US
FIRST_KEY = 30
MP_PREFLIGHT = Path.home() / "prjs" / "event_coding" / "mp" / "preflight"
READ_SLOTS = 6
STAGE0_GROUPS = 5
CHUNK = 3                                  # groups per task in Stages T and R

# ------------------------------------------------------------------------------------------- common
_FIT_TIMES = []


def _timed_fit(*a, **k):
    t0 = time.perf_counter()
    r = _ORIG_FIT(*a, **k)
    _FIT_TIMES.append({"B": int(a[2]), "model": a[3], "n_blocks": int(len(r["ids"])), "s": time.perf_counter() - t0})
    return r


_ORIG_FIT = bc.fit_group
bc.fit_group = _timed_fit                  # evaluate_group calls the module attribute: wrapped from the runner


def expected_events(rid) -> int:
    return int(json.loads((MP_PREFLIGHT / f"{rid}.json").read_text())["n_events"])


def read(rid, lock_dir=None):
    lk = M._read_lock(lock_dir, slots=READ_SLOTS) if lock_dir else None
    ev = baseline.read_events(mp.event_path(rid))
    if lk:
        lk.close()
    n, exp = int(len(ev)), expected_events(rid)
    if n != exp:
        raise RuntimeError(f"P4: {rid} has {n} events, results/mp/preflight.json says {exp}")
    return ev


def key_windows(t_last: int, S: int):
    out, j = [], 0
    while (FIRST_KEY + S * j + 11) * T0 <= t_last:
        out.append(FIRST_KEY + S * j)
        j += 1
    return out


def subsets():
    pc = json.loads((mp.REPO / "results" / "bk" / "population_check.json").read_text()) \
        if (mp.REPO / "results" / "bk" / "population_check.json").exists() else None
    if pc is None:
        pc = json.loads((Path.home() / "prjs" / "event_coding" / "bk" / "population_check.json").read_text())
    return pc["tuning_subset"], pc["reporting_subset"]


def stage0_recordings():
    tuning, _ = subsets()
    return [next(r for r in tuning if mp.lighting(r) == "day"), next(r for r in tuning if mp.lighting(r) == "night")]


# ------------------------------------------------------------------------------------------- Stage P
def preflight(out):
    import zstandard, scipy, h5py, numba, platform, socket
    refp = Path.home() / "prjs" / "event_coding" / "bk" / "ref" / "af_preflight.json"   # results/af/preflight.json
    ref = json.loads(refp.read_text())["P1"] if refp.exists() else None
    env = {"host": socket.gethostname(), "python": platform.python_version(), "numpy": np.__version__,
           "scipy": scipy.__version__, "h5py": h5py.__version__, "zstandard": zstandard.__version__,
           "numba": numba.__version__, "blas_threads": {k: os.environ.get(k) for k in (
               "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")}}
    keys = ("host", "python", "numpy", "scipy", "h5py", "zstandard", "numba", "blas_threads")
    diff = {k: {"004": ref.get(k), "007": env.get(k)} for k in keys if ref is None or ref.get(k) != env.get(k)}
    sha = {p: hashlib.sha256((mp.REPO / p).read_bytes()).hexdigest()
           for p in ("ec/blockcodec.py", "tests/test_blockcodec_gate.py")}
    want = {"ec/blockcodec.py": "644539ec0fb900cc2c3ccd08de0d7105ed55a56cf1d67a545b9784d690390c9e",
            "tests/test_blockcodec_gate.py": "4ca8ec70fcd3ae5101a37592f1ab3d809d5d28692eacd9ac6d0687bb28adedf0"}
    ids, _ = mp.load_population()
    found = sum(os.path.isfile(mp.event_path(r)) for r in ids)
    res = {"directive": "007", "commit": (mp.REPO / "COMMIT").read_text().strip(),
           "P1": env | {"compared_with": "results/af/preflight.json#/P1", "differences": diff, "pass": not diff},
           "P2": {"sha256": sha, "expected": want, "pass": sha == want},
           "P4": {"n_event_files_found": found, "n_expected": 112, "isfile_pass": found == 112,
                  "event_counts": "checked against results/mp/preflight.json#/P2/per_recording by every process "
                                  "that reads a recording (census, Stage 0, Stages T and R, receivers)"}}
    Path(out).write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps({k: (v["pass"] if "pass" in v else v) for k, v in res.items() if k.startswith("P")}, indent=1),
          json.dumps(diff))


# ------------------------------------------------------------------------------------------- Stage 0
def stage0(bkdir):
    bkdir = Path(bkdir)
    out = bkdir / "stage0"
    if out.exists() and any(out.iterdir()):
        sys.exit(f"{out} exists and is not empty")
    (out / "streams").mkdir(parents=True, exist_ok=True)
    res = {"recordings": {}, "times": []}
    for rid in stage0_recordings():
        ev = read(rid)
        ws = key_windows(int(ev.t_us[-1]), 90)[:STAGE0_GROUPS]
        groups, w_prev = [], 0
        for j, w in enumerate(ws):
            _FIT_TIMES.clear()
            t0 = time.perf_counter()
            g = bc.evaluate_group(ev.t_us, ev.x, ev.y, ev.p, w, w_prev, W, H, grid_for=(40, 1 / 16),
                                  records_for=(40, 1 / 16))
            el = time.perf_counter() - t0
            res["times"].append({"rid": rid, "j": j, "w": w, "evaluate_group_s": el, "fits": list(_FIT_TIMES)})
            groups.append(g)
            w_prev = w
            print(f"{rid} group {j} w={w} {el:.1f}s", flush=True)
        with open(out / f"sender_{rid}.pkl", "wb") as f:
            pickle.dump(groups, f, protocol=5)
        for model in bc.MODELS:
            for coder in bc.CODERS:
                for K in bc.GROUPS:
                    name = f"{model}_{coder}_K{K}"
                    p = out / "streams" / f"{rid}__{name}.ec07"
                    with open(p, "wb") as f:
                        f.write(bc.encode_header(coder, model, K, W, H, 40))
                        for g in groups:
                            f.write(g["records"][name])
        res["recordings"][rid] = {"w": ws, "n_events": int(len(ev))}
    (out / "sender.json").write_text(json.dumps(res, indent=1) + "\n")


def receive(streamdir, out):
    """The receiver: only the stream files and, to score, the events of the recording named in the file name."""
    streamdir = Path(streamdir)
    files = sorted(streamdir.glob("*.ec07"))
    by_rid = {}
    for f in files:
        by_rid.setdefault(f.name.split("__")[0], []).append(f)
    res = {}
    for rid, fs in by_rid.items():
        ev = read(rid)
        for f in fs:
            buf = f.read_bytes()
            res[f.name] = {"length": len(buf), "sha256": hashlib.sha256(buf).hexdigest(),
                           "groups": bc.evaluate_stream(buf, ev.t_us, ev.x, ev.y, ev.p)}
    Path(out).write_text(json.dumps(res) + "\n")
    print(len(res), "streams scored", flush=True)


def compare_streams(groups, rec, cfg, model, coder, K):
    """Section 7 checks of one stream: length, and the receiver's n_rec, n_true, match per group and m < K."""
    exp_len = 28 + sum(g["codec"][cfg]["models"][model]["bytes"][f"{coder}_K{K}"] for g in groups)
    bad = []
    if rec["length"] != exp_len:
        bad.append(f"length {rec['length']} != {exp_len}")
    if len(rec["groups"]) != len(groups):
        bad.append("number of groups")
    for r, g in zip(rec["groups"], groups):
        row = g["codec"][cfg]
        mr = row["models"][model]
        if r["w"] != g["w"]:
            bad.append(f"w {r['w']} != {g['w']}")
        if r["n_true"] != g["n_true"][:K]:
            bad.append(f"n_true at w={g['w']}")
        if r["n_rec"] != [row["n_key"]] + mr["n_rec"][:K - 1]:
            bad.append(f"n_rec at w={g['w']}")
        if r["match"] != [row["n_key"]] + mr["match_s2_k3"][:K - 1]:
            bad.append(f"match at w={g['w']}")
    return exp_len, bad


def checks_of_groups(groups):
    n, bad = 0, []
    for g in groups:
        for cfg, row in g["codec"].items():
            for model, r in row["models"].items():
                n += 1
                if not (r["claim_equals_match"] and r["q_equals_t"]):
                    bad.append((g["w"], cfg, model, r["claim_equals_match"], r["q_equals_t"]))
    return n, bad


def stage0_check(bkdir, out):
    bkdir = Path(bkdir) / "stage0"
    rec = json.loads((bkdir / "receiver.json").read_text())
    snd = json.loads((bkdir / "sender.json").read_text())
    res = {"streams": {}, "groups": {}, "pass": True}
    for rid in snd["recordings"]:
        with open(bkdir / f"sender_{rid}.pkl", "rb") as f:
            groups = pickle.load(f)
        n, bad = checks_of_groups(groups)
        res["groups"][rid] = {"n_config_model_group": n, "failures": bad}
        res["pass"] &= not bad
        for model in bc.MODELS:
            for coder in bc.CODERS:
                for K in bc.GROUPS:
                    name = f"{rid}__{model}_{coder}_K{K}.ec07"
                    exp_len, b = compare_streams(groups, rec[name], "B40_rho0.0625", model, coder, K)
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
    rid, lock_dir = args
    ev = read(rid, lock_dir)
    t_last = int(ev.t_us[-1])
    rows = []
    for w in key_windows(t_last, 90):
        a, b = np.searchsorted(ev.t_us, (w * T0, (w + 1) * T0))
        x, y = ev.x[a:b], ev.y[a:b]
        row = {"w": int(w), "n_events": int(b - a)}
        for B in bc.BLOCKS:
            _, cnt = np.unique(bc.block_ids(x, y, B, W), return_counts=True)
            row[str(B)] = [int((cnt >= bc.threshold(B, rho)).sum()) for rho in bc.DENSITIES]
        rows.append(row)
    return rid, {"n_events": int(len(ev)), "t_last_us": t_last, "key_windows_S90": rows}


def census(bkdir, workers):
    bkdir = Path(bkdir)
    ids, _ = mp.load_population()
    order = sorted(ids, key=lambda r: -os.path.getsize(mp.event_path(r)))
    res = {}
    with mpr.get_context("spawn").Pool(workers, maxtasksperchild=1) as pool:
        for k, (rid, r) in enumerate(pool.imap_unordered(_census_one, [(r, str(bkdir)) for r in order]), 1):
            res[rid] = r
            print(f"[{k}/112] {rid} {len(r['key_windows_S90'])} key windows", flush=True)
    out = {"directive": "007", "spacing_of_listing": 90, "first_key": FIRST_KEY,
           "blocks": list(bc.BLOCKS), "densities": list(bc.DENSITIES),
           "note": "per key window: events of the key window, and for each block side the number of active blocks "
                   "at each density (block_ids, threshold); events checked against results/mp/preflight.json",
           "recordings": {r: res[r] for r in sorted(res)}}
    (bkdir / "census.json").write_text(json.dumps(out) + "\n")


# ------------------------------------------------------------------------------------------- projection
def groups_at(cen_rec, S):
    """Key windows at spacing S (a subset of those at S = 90, since 30 + S j = 30 + 90 (S / 90) j)."""
    ws = key_windows(cen_rec["t_last_us"], S)
    by_w = {r["w"]: r for r in cen_rec["key_windows_S90"]}
    return [by_w[w] for w in ws]


def project(bkdir, out):
    bkdir = Path(bkdir)
    s0 = json.loads((bkdir / "stage0" / "sender.json").read_text())
    cen = json.loads((bkdir / "census.json").read_text())["recordings"]
    tuning, reporting = subsets()
    cB, c0s = {}, []
    for B in bc.BLOCKS:
        per = []
        for t in s0["times"]:
            fits = [f for f in t["fits"] if f["B"] == B and f["model"] in ("translation", "affine")]
            nb = fits[0]["n_blocks"] if fits else 0
            if nb > 0:
                per.append(sum(f["s"] for f in fits) / nb)
        cB[B] = float(np.mean(per)) if per else float("nan")
    for t in s0["times"]:
        c0s.append(t["evaluate_group_s"] - sum(f["s"] for f in t["fits"]))
    c0 = float(np.mean(c0s))
    proj = {}
    for S in (90, 180, 360):
        T = sum(sum(g[str(B)][0] * cB[B] for B in bc.BLOCKS) + c0 for r in tuning for g in groups_at(cen[r], S))
        Rb = {B: sum(g[str(B)][0] * cB[B] + c0 for r in reporting for g in groups_at(cen[r], S)) for B in bc.BLOCKS}
        Bmax = max(Rb, key=Rb.get)
        nT = sum(len(groups_at(cen[r], S)) for r in tuning)
        nR = sum(len(groups_at(cen[r], S)) for r in reporting)
        proj[str(S)] = {"stage_T_cpu_h": T / 3600, "stage_R_cpu_h_by_B": {str(B): v / 3600 for B, v in Rb.items()},
                        "stage_R_B_used": Bmax, "stage_R_cpu_h": Rb[Bmax] / 3600,
                        "total_cpu_h": (T + Rb[Bmax]) / 3600, "n_groups_T": nT, "n_groups_R": nR}
    chosen = next((S for S in (90, 180, 360) if proj[str(S)]["total_cpu_h"] <= 150), None)
    res = {"c_B_s_per_block": {str(B): v for B, v in cB.items()}, "c_0_s_per_group": c0,
           "c_0_samples": c0s, "limit_cpu_h": 150, "projection": proj, "spacing_chosen": chosen,
           "rule": "Section 15: S = 90 unless T + R exceeds 150 CPU-hours, then 180, then 360, else stop after Stage 0"}
    Path(out).write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps(res, indent=1))


# ------------------------------------------------------------------------------------------- Stages T and R
def plan(stage, bkdir, S):
    cen = json.loads((Path(bkdir) / "census.json").read_text())["recordings"]
    tuning, reporting = subsets()
    ids = tuning if stage == "T" else reporting
    tasks = []
    for r in ids:
        ws = key_windows(cen[r]["t_last_us"], S)
        gs = groups_at(cen[r], S)
        for c in range(0, len(ws), CHUNK):
            cost = sum(sum(g[str(B)][0] for B in bc.BLOCKS) for g in gs[c:c + CHUNK])
            tasks.append([f"{r}|{c // CHUNK}", float(cost)])
    tasks.sort(key=lambda t: -t[1])
    return tasks


def task(stage, bkdir, key, S, frozen):
    bkdir = Path(bkdir)
    rid, ci = key.split("|")
    ci = int(ci)
    out = bkdir / stage / f"groups_{rid}_{ci:03d}.pkl"
    if out.exists():
        return
    t_start = time.time()
    ev = read(rid, bkdir / stage)
    ws = key_windows(int(ev.t_us[-1]), S)
    js = list(range(ci * CHUNK, min(len(ws), (ci + 1) * CHUNK)))
    res = []
    for j in js:
        w, w_prev = ws[j], (ws[j - 1] if j > 0 else 0)
        _FIT_TIMES.clear()
        t0 = time.perf_counter()
        if stage == "T":
            g = bc.evaluate_group(ev.t_us, ev.x, ev.y, ev.p, w, w_prev, W, H)
        else:
            B, rho = frozen
            g = bc.evaluate_group(ev.t_us, ev.x, ev.y, ev.p, w, w_prev, W, H, blocks=(B,), grid_for=(B, rho),
                                  records_for=(B, rho))
        res.append({"j": j, "w": w, "w_prev": w_prev, "evaluate_group_s": time.perf_counter() - t0,
                    "fits": list(_FIT_TIMES), "group": g})
    tmp = out.with_suffix(".tmp")
    with open(tmp, "wb") as f:
        pickle.dump(res, f, protocol=5)
    tmp.rename(out)
    (bkdir / stage / f"task_{rid}_{ci:03d}.json").write_text(json.dumps(
        {"rid": rid, "chunk": ci, "js": js, "n_events": int(len(ev)), "wall_s": time.time() - t_start}) + "\n")


def _out_name(stage, key):
    rid, c = key.split("|")
    return f"groups_{rid}_{int(c):03d}.pkl"


def schedule(stage, bkdir, max_workers, S, frozen, min_free_gb=40.0):
    out = Path(bkdir) / stage
    tasks = json.loads((out / "plan.json").read_text())["tasks"]
    pending = [t for t in tasks if not (out / _out_name(stage, t[0])).exists()]
    running, fails, t0, done = {}, {}, time.time(), len(tasks) - len(pending)
    log = lambda m: print(f"{time.strftime('%H:%M:%S')} {m}", flush=True)
    log(f"{len(pending)} of {len(tasks)} tasks pending")
    extra = ["--spacing", str(S)] + (["--frozen", f"{frozen[0]},{frozen[1]}"] if frozen else [])
    while pending or running:
        for pr, t in list(running.items()):
            rc = pr.poll()
            if rc is None:
                continue
            del running[pr]
            if rc == 0 and (out / _out_name(stage, t[0])).exists():
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
            log_f = open(out / "logs" / f"{_out_name(stage, t[0])[7:-4]}.log", "w")
            running[subprocess.Popen([sys.executable, __file__, "one", stage, str(bkdir), t[0]] + extra,
                                     stdout=log_f, stderr=subprocess.STDOUT)] = t
            time.sleep(2)
        time.sleep(10)
    log(f"DONE failed={sorted(k for k, v in fails.items() if v >= 2)}")


def run(stage, bkdir, workers, S, frozen):
    out = Path(bkdir) / stage
    if (out / "plan.json").exists():
        if not (out / "RESUME").exists():
            sys.exit(f"{out} holds a run; touch {out}/RESUME to resume it")
    else:
        if out.exists() and any(out.iterdir()):
            sys.exit(f"{out} exists and is not empty")
        (out / "logs").mkdir(parents=True, exist_ok=True)
        (out / "plan.json").write_text(json.dumps({"commit": (mp.REPO / "COMMIT").read_text().strip(), "stage": stage,
                                                   "spacing": S, "frozen": frozen, "chunk": CHUNK,
                                                   "tasks": plan(stage, bkdir, S)}) + "\n")
    schedule(stage, bkdir, workers, S, frozen)


def load_groups(stage, bkdir, rid):
    out = []
    for f in sorted((Path(bkdir) / stage).glob(f"groups_{rid}_*.pkl")):
        with open(f, "rb") as fh:
            out += pickle.load(fh)
    out.sort(key=lambda r: r["j"])
    return out


def streams(bkdir):
    """Stage R: the eight complete streams (model affine, two coders, four K) of every reporting recording."""
    bkdir = Path(bkdir)
    plan_ = json.loads((bkdir / "R" / "plan.json").read_text())
    B, rho = plan_["frozen"]
    sd = bkdir / "R_streams"
    sd.mkdir(exist_ok=True)
    _, reporting = subsets()
    for rid in reporting:
        groups = load_groups("R", bkdir, rid)
        for coder in bc.CODERS:
            for K in bc.GROUPS:
                name = f"affine_{coder}_K{K}"
                with open(sd / f"{rid}__{name}.ec07", "wb") as f:
                    f.write(bc.encode_header(coder, "affine", K, W, H, int(B)))
                    for r in groups:
                        f.write(r["group"]["records"][name])
    print("streams written", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode")
    ap.add_argument("args", nargs="*")
    ap.add_argument("--workers", type=int, default=24)
    ap.add_argument("--spacing", type=int, default=0)
    ap.add_argument("--frozen", default="")
    a = ap.parse_args()
    frozen = None
    if a.frozen:
        b, r = a.frozen.split(",")
        frozen = (int(b), float(r))
    if a.mode == "preflight":
        preflight(*a.args)
    elif a.mode == "stage0":
        stage0(*a.args)
    elif a.mode == "receive":
        receive(*a.args)
    elif a.mode == "stage0_check":
        stage0_check(*a.args)
    elif a.mode == "census":
        census(a.args[0], a.workers)
    elif a.mode == "project":
        project(*a.args)
    elif a.mode == "run":
        run(a.args[0], a.args[1], a.workers, a.spacing, frozen)
    elif a.mode == "one":
        task(a.args[0], a.args[1], a.args[2], a.spacing, frozen)
    elif a.mode == "streams":
        streams(*a.args)
    else:
        sys.exit(f"unknown mode {a.mode}")


if __name__ == "__main__":
    main()
