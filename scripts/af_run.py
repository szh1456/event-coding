"""Directive 004, Section 6: Stage A, the sender-fitted affine map.

  python3 scripts/af_run.py probe OUTDIR [--workers W]   # 50 timed instants (ten targets each)
  python3 scripts/af_run.py cost AFDIR OUT.json           # project the cost from the probe
  python3 scripts/af_run.py run OUTDIR [--workers W]     # every row of Stage C of directive 003; resumable
  python3 scripts/af_run.py one OUTDIR KEY               # one task (called by run)

Uses ``ec.affine.evaluate_affine`` unchanged on every row of Stage C of directive
003, one task per shard of that stage (the same tracks and instants). Within an
instant the targets are fitted in the order m = 1 to 10, ``d_start`` is
``(aligned_dx, aligned_dy)`` of the 003 row, and ``q_prev`` is the map fitted for
target m - 1, or None for m = 1 or when that target was skipped. A row that
directive 003 skipped gets ``d_start = None``: evaluate_affine skips it before the
fit, by the same tests. The events are cut to the shard's track lives, which
leaves every result unchanged (report 001, Section 4, item 4).
"""
from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS",
           "VECLIB_MAXIMUM_THREADS", "NUMBA_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import argparse
import glob
import json
import multiprocessing as mpr
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ec import affine, annotations, baseline, mp, regen  # noqa: E402
import mp_measure as M  # noqa: E402

GP_C = Path.home() / "prjs" / "event_coding" / "gp" / "C"
MP_RUN = Path.home() / "prjs" / "event_coding" / "mp" / "run"
WIDTH, HEIGHT = 1280, 720
T1_US, T2_US, MARGIN_PX = 100_000, 33_333, 2.0
GROWTH_LEAD_US = 300_000
READ_SLOTS = 6
STRATA_COLS = ("recording_id", "lighting", "track_id", "class_id", "group", "t_e_us", "speed_bin", "overlap",
               "box_area_te", "target")
GP_COPY = (["skip", "n_source", "n_future", "aligned_dx", "aligned_dy", "aligned_n_pred", "key_bits", "true_bits"]
           + [f"aligned_f1_s{s}_k{k}" for s in regen.BLOCKS_PX for k in regen.TIME_BINS])


def plan_keys():
    return [[f"{t[0]}|{t[1]}", t[3]] for t in json.loads((MP_RUN / "plan.json").read_text())["tasks"]]


def gp_rows(rid, shard):
    z = dict(np.load(GP_C / f"rows_{rid}_{shard:03d}.npz"))
    return z if "target" in z else None


def instants_of(g):
    """(track_id, t_e) of each instant of a 003 file, in file order, with its row index per target."""
    out = {}
    for j in range(len(g["target"])):
        out.setdefault((int(g["track_id"][j]), int(g["t_e_us"][j])), {})[int(g["target"][j])] = j
    return out


def _out_name(key):
    rid, s = key.split("|")
    return f"rows_{rid}_{int(s):03d}.npz"


def task(rid, shard, outdir, only=None, tag=None):
    tag = tag or f"{rid}_{shard:03d}"
    out = Path(outdir) / f"rows_{tag}.npz"
    if out.exists():
        return 0
    t0 = time.time()
    g = gp_rows(rid, shard)
    inst = instants_of(g) if g is not None else {}
    if only is not None:
        inst = {k: inst[k] for k in only}
    rows, t_read = [], 0.0
    if inst:
        trk = {tr.track_id: tr for tr in annotations.tracks(annotations.load_boxes(mp.annotation_path(rid)))}
        need = [trk[k] for k in sorted({k for k, _ in inst})]
        lk = M._read_lock(outdir, slots=READ_SLOTS)
        ev = baseline.read_events(mp.event_path(rid))
        sl = M._Slice(ev, min(tr.t_first for tr in need), max(tr.t_last for tr in need))
        del ev
        lk.close()
        t_read = time.time() - t0
        for (tid, te), by_m in inst.items():
            tr = trk[tid]
            a0 = float(np.prod(tr.box(float(te))[2:]))
            a1 = float(np.prod(tr.box(float(te + GROWTH_LEAD_US))[2:]))
            growth = a1 / a0 if a0 > 0 else float("nan")
            q_prev = None
            for m in range(1, 11):
                j = by_m[m]
                d_start = (int(g["aligned_dx"][j]), int(g["aligned_dy"][j])) if g["skip"][j] == "" else None
                given = q_prev is not None
                t1 = time.perf_counter()
                r = affine.evaluate_affine(sl.t_us, sl.x, sl.y, sl.p, tr, te, m, T2_US, WIDTH, HEIGHT, d_start,
                                           q_prev, T1_us=T1_US, margin_px=MARGIN_PX)
                el = time.perf_counter() - t1
                q_prev = None if "skipped" in r else tuple(r[f"affine_{n}"] for n in affine.PARAMS)
                row = {c: g[c][j].item() for c in STRATA_COLS}
                row.update({f"gp_{c}": g[c][j].item() for c in GP_COPY})
                row.update({"gp_shard": shard, "gp_index": j, "growth_ratio": growth, "elapsed_s": el,
                            "skip": r.get("skipped", ""), "q_prev_given": int(given)})
                row.update({k: v for k, v in r.items() if k not in ("skipped", "m")})
                rows.append(row)
    M.to_npz(rows, out) if rows else np.savez_compressed(out, empty=np.zeros(0))
    (Path(outdir) / f"task_{tag}.json").write_text(json.dumps(
        {"rid": rid, "shard": shard, "n_instants": len(inst), "n_rows": len(rows), "read_s": t_read,
         "wall_s": time.time() - t0}) + "\n")
    return len(rows)


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
    outdir, rid, shard, keys = args
    task(rid, shard, outdir, only=[tuple(k) for k in keys], tag=f"probe_{rid}_{shard:03d}")
    return rid


def probe(outdir, workers, n=50):
    out = Path(outdir)
    if out.exists() and any(out.iterdir()):
        sys.exit(f"{out} exists and is not empty")
    out.mkdir(parents=True)
    alli = []
    for key, _ in plan_keys():
        rid, s = key.split("|")
        g = gp_rows(rid, int(s))
        if g is not None:
            alli += [(rid, int(s), k) for k in instants_of(g)]
    pick = [alli[i] for i in np.unique(np.linspace(0, len(alli) - 1, n).astype(int))]
    by = {}
    for rid, s, k in pick:
        by.setdefault((rid, s), []).append(k)
    (out / "probe.json").write_text(json.dumps({"n_instants_stage": len(alli), "n_probe_instants": len(pick)}) + "\n")
    with mpr.get_context("spawn").Pool(workers, maxtasksperchild=1) as pool:
        for k, rid in enumerate(pool.imap_unordered(_probe_one, [(str(out), r, s, ks) for (r, s), ks in by.items()]), 1):
            print(f"[{k}/{len(by)}] {rid}", flush=True)
    print("DONE", flush=True)


def cost(afdir, out_json):
    """Per-instant cost (ten targets, one core) by box-area bin, times the stage's instants per bin, plus reads."""
    afdir = Path(afdir)
    edges = (0, 1_000, 3_000, 10_000, 30_000, 100_000, np.inf)
    z = [dict(np.load(f)) for f in sorted((afdir / "probe").glob("rows_*.npz"))]
    c = {k: np.concatenate([d[k] for d in z]) for k in ("recording_id", "track_id", "t_e_us", "box_area_te",
                                                        "elapsed_s", "skip")}
    ne = np.concatenate([d["affine_n_eval"] for d in z])
    key = np.char.add(np.char.add(c["recording_id"], "|"), np.char.add(c["track_id"].astype(int).astype(str),
                                                                       np.char.add("|", c["t_e_us"].astype(int).astype(str))))
    u, inv = np.unique(key, return_inverse=True)
    pc = np.bincount(inv, c["elapsed_s"])
    pa = np.bincount(inv, c["box_area_te"]) / np.bincount(inv)
    all_area = []
    for k, _ in plan_keys():
        rid, s = k.split("|")
        g = gp_rows(rid, int(s))
        if g is not None:
            m1 = g["target"] == 1
            all_area.append(g["box_area_te"][m1])
    all_area = np.concatenate(all_area)
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
    reads = sum(read_s[k.split("|")[0]] for k, _ in plan_keys()) / 3600
    nes = ne[np.isfinite(ne)]
    res = {"n_probe_instants": int(len(u)), "n_probe_rows": int(len(c["skip"])), "n_instants_stage": int(len(all_area)),
           "bins": bins, "compute_cpu_h": total / 3600, "read_cpu_h": reads, "total_cpu_h": total / 3600 + reads,
           "probe_affine_n_eval": {"median": float(np.median(nes)), "max": float(nes.max())}, "limit_cpu_h": 150}
    res["within_limit"] = res["total_cpu_h"] <= 150
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
        tasks = sorted(plan_keys(), key=lambda t: -t[1])
        (out / "plan.json").write_text(json.dumps({"commit": (mp.REPO / "COMMIT").read_text().strip(),
                                                   "tasks": tasks}) + "\n")
    schedule(out, a.workers)


if __name__ == "__main__":
    main()
