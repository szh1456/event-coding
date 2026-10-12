"""Directive 013: DSEC calibrated on its own tuning subset.

  python3 scripts/dt_run.py popcheck OUT.json                 # Section 4 (no file is opened)
  python3 scripts/dt_run.py preflight REF_PROVENANCE.json OUT.json
  python3 scripts/dt_run.py runT DTDIR [--workers W]          # Stage T, resumable
  python3 scripts/dt_run.py oneT DTDIR KEY
  python3 scripts/dt_run.py projectT DTDIR                     # Section 11: from the first ten groups
  python3 scripts/dt_run.py tune DTDIR OUT.json                # Section 6: J and the freeze

As directive 009 (spacing S = 60, ``ec.dsec.read_events``, one recording read at a time, events kept
only for the windows of a task), with the default blocks (20, 40, 80), the five densities and the
three models, ``grid_for = records_for = None`` in Stage T. Host paths under
``/data/<user>/event_coding/ds/dt/``.
"""
from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS",
           "VECLIB_MAXIMUM_THREADS", "NUMBA_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import argparse
import hashlib
import json
import pickle
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ec import blockcodec as bc, codec, dsec, mp  # noqa: E402
import bk_run as BK  # noqa: E402
import ds_run as DR  # noqa: E402
import mp_measure as M  # noqa: E402

S = 60
CHUNK_T = 3
DT = DR.BASE / "ds" / "dt"
CENSUS = DR.BASE / "ds" / "census.json"


def subsets():
    names = sorted(DR.sequences())
    tuning = [names[i] for i in (0, 10, 20, 30, 40)]
    return tuning, [n for n in names if n not in tuning]


def cmd_popcheck(out):
    tuning, reporting = subsets()
    loc = lambda s: s.split("0")[0] if s[0] != "z" else "zurich_city_"
    res = {"directive": "013", "population": "config/population_dsec.yaml", "rule": "sorted names; tuning = positions "
           "0, 10, 20, 30, 40; reporting = the other 36", "tuning_subset": tuning, "reporting_subset": reporting,
           "n_reporting_by_location": {l: sum(s.startswith(l) for s in reporting) for l in ("interlaken_", "thun_", "zurich_city_")},
           "spacing": S, "statement": "no event file opened to write this file"}
    Path(out).write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps({k: v for k, v in res.items() if k != "reporting_subset"}, indent=1))


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def cmd_preflight(ref, out):
    import platform, socket, scipy, h5py, zstandard, numba, hdf5plugin
    prov = json.loads(Path(ref).read_text())
    env = {"host": socket.gethostname(), "python": platform.python_version(), "numpy": np.__version__,
           "scipy": scipy.__version__, "h5py": h5py.__version__, "zstandard": zstandard.__version__,
           "numba": numba.__version__, "hdf5plugin": hdf5plugin.version,
           "blas_threads": {k: os.environ.get(k) for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                                                          "NUMEXPR_NUM_THREADS")}}
    v = prov["versions"]
    diff = {k: {"009": v.get(k), "013": env[k]} for k in env if v.get(k) != env[k]}
    code = {p: sha256(mp.REPO / p) for p in ("ec/blockcodec.py", "tests/test_blockcodec_gate.py", "ec/dsec.py",
                                             "tests/test_dsec_gate.py")}
    want = {"ec/blockcodec.py": "644539ec0fb900cc2c3ccd08de0d7105ed55a56cf1d67a545b9784d690390c9e",
            "tests/test_blockcodec_gate.py": "4ca8ec70fcd3ae5101a37592f1ab3d809d5d28692eacd9ac6d0687bb28adedf0",
            "ec/dsec.py": "8d6d5baad01e7da4607e3108684578c280d7fdc9b95c6eb0319d549340437fb6",
            "tests/test_dsec_gate.py": "d23276bc29229fbe79bb3fd986a4b3a1b47952fcf96b756bb74a04d93ef151c0"}
    p3 = []
    for f in prov["downloaded_files"]:
        p = Path(f["kept_path"])
        ok = p.is_file() and p.stat().st_size == f["kept_bytes"] and sha256(p) == f["kept_sha256"]
        p3.append({"sequence": f["sequence"], "ok": ok})
    _, reporting = subsets()
    p4 = {"per_group": [], "streams": []}
    for f in prov["per_group_files"]:
        name = Path(f["path"]).name
        if name.startswith("groups_") and any(name.startswith(f"groups_{s}_") for s in reporting):
            p = Path(f["path"])
            p4["per_group"].append({"path": f["path"], "ok": p.is_file() and p.stat().st_size == f["size"]
                                    and sha256(p) == f["sha256"]})
    for f in prov["stream_files_stage_R"]:
        if Path(f["path"]).name.split("__")[0] in reporting:
            p = Path(f["path"])
            p4["streams"].append({"path": f["path"], "ok": p.is_file() and p.stat().st_size == f["size"]
                                  and sha256(p) == f["sha256"]})
    res = {"directive": "013", "P1": env | {"compared_with": "results/ds/provenance.json#/versions", "differences": diff,
                                           "pass": not diff},
           "P2": {"sha256": code, "expected": want, "pass": code == want,
                  "suite": "run separately: python3 -m pytest -q -p no:anyio"},
           "P3": {"n_files": len(p3), "n_ok": sum(r["ok"] for r in p3), "failing": [r for r in p3 if not r["ok"]],
                  "pass": len(p3) == 41 and all(r["ok"] for r in p3)},
           "P4": {"n_per_group": len(p4["per_group"]), "n_per_group_ok": sum(r["ok"] for r in p4["per_group"]),
                  "n_streams": len(p4["streams"]), "n_streams_ok": sum(r["ok"] for r in p4["streams"]),
                  "failing": [r for k in p4 for r in p4[k] if not r["ok"]],
                  "pass": all(r["ok"] for k in p4 for r in p4[k]) and len(p4["streams"]) == 36 * 16}}
    Path(out).write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps({k: (v["pass"] if isinstance(v, dict) and "pass" in v else v) for k, v in res.items()}, indent=1),
          json.dumps(diff), res["P4"]["n_per_group"], res["P4"]["n_streams"])


# ------------------------------------------------------------------------------------------- Stage T
def plan_T():
    cen = json.loads(CENSUS.read_text())["recordings"]
    tuning, _ = subsets()
    tasks = []
    for s in tuning:
        gs = DR.groups_at(cen[s], S)
        for c in range(0, len(gs), CHUNK_T):
            tasks.append([f"{s}|{c // CHUNK_T}", float(sum(g["20"][0] for g in gs[c:c + CHUNK_T]))])
    return tasks                                   # in sequence order: the first groups of each sequence come early


def task_T(dtdir, key):
    dtdir = Path(dtdir)
    seq, ci = key.split("|")
    ci = int(ci)
    out = dtdir / "T" / f"groups_{seq}_{ci:03d}.pkl"
    if out.exists():
        return
    t_start = time.time()
    c = json.loads(CENSUS.read_text())["recordings"][seq]
    ws = DR.key_windows(c["t_first_us"], c["t_last_us"], S)
    js = list(range(ci * CHUNK_T, min(len(ws), (ci + 1) * CHUNK_T)))
    t, x, y, p, info = DR.read(seq, dtdir / "T", window=(ws[js[0]], ws[js[-1]] + bc.N_TARGETS + 1))
    res = []
    for j in js:
        w, w_prev = ws[j], (ws[j - 1] if j > 0 else 0)
        BK._FIT_TIMES.clear()
        t0 = time.perf_counter()
        g = codec.evaluate_group(t, x, y, p, w, w_prev, DR.W, DR.H)
        res.append({"j": j, "w": w, "w_prev": w_prev, "evaluate_group_s": time.perf_counter() - t0,
                    "finished_utc": time.time(), "fits": list(BK._FIT_TIMES), "codec": codec.NAME, "group": g})
    tmp = out.with_suffix(".tmp")
    with open(tmp, "wb") as f:
        pickle.dump(res, f, protocol=5)
    tmp.rename(out)
    (dtdir / "T" / f"task_{seq}_{ci:03d}.json").write_text(json.dumps(
        {"seq": seq, "chunk": ci, "js": js, "n_events_file": info["n_events"], "wall_s": time.time() - t_start,
         "group_s": [r["evaluate_group_s"] for r in res], "finished_utc": time.time()}) + "\n")


def _out_name(key):
    s, c = key.split("|")
    return f"groups_{s}_{int(c):03d}.pkl"


def run_T(dtdir, workers):
    out = Path(dtdir) / "T"
    if (out / "plan.json").exists():
        if not (out / "RESUME").exists():
            sys.exit(f"{out} holds a run; touch {out}/RESUME to resume it")
    else:
        if out.exists() and any(out.iterdir()):
            sys.exit(f"{out} exists and is not empty")
        (out / "logs").mkdir(parents=True, exist_ok=True)
        (out / "plan.json").write_text(json.dumps({"commit": (mp.REPO / "COMMIT").read_text().strip(), "spacing": S,
                                                   "chunk": CHUNK_T, "tasks": plan_T()}) + "\n")
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
        target = M._target_workers(out, workers)
        while pending and len(running) < target and M._mem_available_gb() > 40.0:
            t = pending.pop(0)
            log_f = open(out / "logs" / f"{_out_name(t[0])[7:-4]}.log", "w")
            running[subprocess.Popen([sys.executable, __file__, "oneT", str(dtdir), t[0]], stdout=log_f,
                                     stderr=subprocess.STDOUT)] = t
            time.sleep(2)
        time.sleep(10)
    log(f"DONE failed={sorted(k for k, v in fails.items() if v >= 2)}")


def load_T(dtdir, seq):
    out = []
    for f in sorted((Path(dtdir) / "T").glob(f"groups_{seq}_*.pkl")):
        with open(f, "rb") as fh:
            out += pickle.load(fh)
    out.sort(key=lambda r: r["j"])
    return out


def project_T(dtdir):
    """Section 11: the first ten groups that finished, in order of their finishing time."""
    rows = []
    for f in (Path(dtdir) / "T").glob("task_*.json"):
        d = json.loads(f.read_text())
        rows += [(d["finished_utc"], s) for s in d["group_s"]]
    rows.sort()
    first = [s for _, s in rows[:10]]
    n_total = sum(len(DR.key_windows(c["t_first_us"], c["t_last_us"], S))
                  for s, c in json.loads(CENSUS.read_text())["recordings"].items() if s in subsets()[0])
    proj = float(np.mean(first)) * n_total / 3600 if len(first) == 10 else None
    res = {"n_groups_done": len(rows), "first_ten_s": first, "n_groups_stage_T": n_total,
           "projection_cpu_h": proj, "limit_cpu_h": 80, "pass": proj is not None and proj <= 80}
    print(json.dumps(res, indent=1))
    return res


def tune(dtdir, out):
    tuning, _ = subsets()
    cfgs = [f"B{B}_rho{float(rho)}" for B in bc.BLOCKS for rho in bc.DENSITIES]
    sums, ng, checks = {}, {}, {"n": 0, "claim_equals_match_false": 0, "q_equals_t_false": 0}
    for s in tuning:
        gs = [r["group"] for r in load_T(dtdir, s)]
        ng[s] = len(gs)
        for g in gs:
            for row in g["codec"].values():
                for r in row["models"].values():
                    checks["n"] += 1
                    checks["claim_equals_match_false"] += not r["claim_equals_match"]
                    checks["q_equals_t_false"] += not r["q_equals_t"]
        sums[s] = bc.sum_groups(gs)
    table, per = {}, {}
    for cfg in cfgs:
        rows = {}
        for s in tuning:
            v = bc.summarize(sums[s], cfg, "affine", "Q", 4)
            rows[s] = v | {"J": (v["bits_base"] - v["bits"]) / v["bits_direct"]}
        per[cfg] = rows
        med = lambda k: float(np.median([r[k] for r in rows.values()]))
        table[cfg] = {"J": med("J"), **{f"median_{k}": med(k) for k in ("F", "bits", "bits_base", "gain")},
                      "n_sequences": len(rows)}
    key = lambda c: (table[c]["J"], int(c.split("_")[0][1:]), float(c.split("rho")[1]))
    frozen = max(cfgs, key=key)
    res = {"directive": "013", "stage": "T", "spacing": S, "tuning_subset": tuning, "n_groups": ng,
           "criterion": "J = (bits_base - bits) / bits_direct, summarize(sum, config, 'affine', 'Q', 4); median over "
                        "the five tuning sequences",
           "table": table, "frozen": {"config": frozen, "B": int(frozen.split("_")[0][1:]),
                                      "rho": float(frozen.split("rho")[1])},
           "tie_rule": "largest J; on a tie the larger B, then the larger rho", "checks_stage_T": checks,
           "per_sequence": per}
    Path(out).write_text(json.dumps(res, indent=1) + "\n")
    (Path(dtdir) / "T_sums.json").write_text(json.dumps(sums, default=float) + "\n")
    print(json.dumps({"frozen": res["frozen"], "checks": checks, "J": {c: round(table[c]["J"], 4) for c in cfgs}},
                     indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode")
    ap.add_argument("args", nargs="*")
    ap.add_argument("--workers", type=int, default=12)
    a = ap.parse_args()
    {"popcheck": lambda: cmd_popcheck(*a.args), "preflight": lambda: cmd_preflight(*a.args),
     "runT": lambda: run_T(a.args[0], a.workers), "oneT": lambda: task_T(*a.args),
     "projectT": lambda: project_T(*a.args), "tune": lambda: tune(*a.args)}[a.mode]()


if __name__ == "__main__":
    main()
