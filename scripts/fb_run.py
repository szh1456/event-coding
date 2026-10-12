"""Directive 016: the flow-based baseline (``ec.fbc``), and the two downstream tasks (``ec.downstream``).

  python3 scripts/fb_run.py run STAGE [--workers W]      # STAGE T or R; resumable scheduler
  python3 scripts/fb_run.py one STAGE KEY                # one task
  python3 scripts/fb_run.py project STAGE                # Section 8: time per group from the first finished groups
  python3 scripts/fb_run.py tune OUT.json                # Section 5: J and the freeze, per dataset and coder

Groups are those of the kept per-group files of REMAKE: eTraM Stage T and Stage R of directive 007
(``~/prjs/event_coding/bk/{T,R}``, S = 90), DSEC Stage T of directive 013 (``.../ds/dt/T``) and the
Stage R of directive 009 for the 36 reporting sequences of directive 013 (``.../ds/R``, S = 60, D-013-2).
Every call of ``ec.fbc.evaluate_group`` receives the events of [w T0 - FIT_WINDOW_US, (w + 11) T0).
Outputs: eTraM under ``~/prjs/event_coding/fb/``, DSEC under ``/data/<user>/event_coding/ds/fb/``; the
scheduler's state under the eTraM directory. One eTraM recording is read per task (at most READ_SLOTS
at once), one DSEC sequence at a time (the read lock and memory wait of directive 009); no worker is
launched below 40 GB of available memory.

Stage R also runs the tasks of Section 7 on the same read: for every group, K = 4, windows m = 1, 2, 3,
the schemes ``true``, ``remake_T``, ``remake_Q``, ``translation_Q``, ``static_Q`` (records of the kept
per-group file, configuration (20, 1)), ``fbc_T``, ``fbc_Q`` (the K = 4 records of the frozen baseline,
taken from the call of ``evaluate_group``) and ``thin_T``, ``thin_Q`` (random subset at the bits of
``remake_<coder>``, drawn per window w + m with ``default_rng(20261016 + w + m)``, coded and decoded).
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
from ec import annotations as an, blockcodec as bc, downstream as dn, fbc, mp  # noqa: E402
import bk_run as BK  # noqa: E402
import ds_run as DR  # noqa: E402
import dt_run as DT  # noqa: E402
import mp_measure as M  # noqa: E402

T0 = bc.T0_US
FB_E = Path.home() / "prjs" / "event_coding" / "fb"
FB_D = DR.BASE / "ds" / "fb"
BK_DIR = Path.home() / "prjs" / "event_coding" / "bk"
RADII, RES = (2, 3, 4), (500, 1000, 2000)
CONFIGS = [(r, s) for r in RADII for s in RES]
SEED = 20261016
CHUNK = {"T": 2, "R": 3}
READ_SLOTS_E = 6
SCHEMES = ("true", "remake_T", "remake_Q", "translation_Q", "static_Q", "fbc_T", "fbc_Q", "thin_T", "thin_Q")
DIMS = {"etram": (BK.W, BK.H), "dsec": (DR.W, DR.H)}
MIN_EVENTS_BOX, SQUARE, N_SQUARES, MIN_EVENTS_SQUARE = 50, 40, 10, 200


def cfg_key(radius, res_us):
    return f"r{int(radius)}_res{int(res_us)}"


def outdir(ds, stage):
    return (FB_E if ds == "etram" else FB_D) / stage


# ------------------------------------------------------------------------------------------- populations
def subsets(ds):
    return BK.subsets() if ds == "etram" else DT.subsets()


def remake_groups(ds, stage, rid):
    """The rows of the kept per-group files of REMAKE for one recording (``j``, ``w``, ``group``)."""
    if ds == "etram":
        return BK.load_groups(stage, BK_DIR, rid)
    return DT.load_T(DT.DT, rid) if stage == "T" else DR.load_groups(DR.BASE / "ds", rid)


def recordings(ds, stage):
    tuning, reporting = subsets(ds)
    return tuning if stage == "T" else reporting


def plan(stage):
    """Tasks of both datasets, interleaved, so that the first finished groups hold both."""
    per = {}
    for ds in ("dsec", "etram"):
        tasks = []
        for rid in recordings(ds, stage):
            js = [r["j"] for r in remake_groups(ds, stage, rid)]
            for c in range(0, len(js), CHUNK[stage]):
                tasks.append(f"{ds}|{rid}|{c // CHUNK[stage]}")
        per[ds] = tasks
    out, a, b = [], per["dsec"], per["etram"]
    for i in range(max(len(a), len(b))):
        out += ([a[i]] if i < len(a) else []) + ([b[i]] if i < len(b) else [])
    return out


def out_name(key):
    ds, rid, c = key.split("|")
    return f"{rid}_{int(c):03d}.pkl"


# ------------------------------------------------------------------------------------------- reading
def read(ds, rid, ws, lock_dir):
    """Events of a recording, sorted by time, as int64 arrays, restricted to the windows the groups need."""
    lo, hi = min(ws) * T0 - fbc.FIT_WINDOW_US, (max(ws) + bc.N_TARGETS + 1) * T0
    if ds == "etram":
        lk = M._read_lock(lock_dir, slots=READ_SLOTS_E)
        ev = BK.read(rid)
        lk.close()
        t, x, y, p = ev.t_us, ev.x, ev.y, ev.p
    else:
        t, x, y, p, _ = DR.read(rid, lock_dir, window=(lo // T0 - 1, hi // T0))
    a, b = np.searchsorted(t, (lo, hi))
    return tuple(np.asarray(v[a:b], dtype=np.int64) for v in (t, x, y, p))


def group_events(ev, w):
    t = ev[0]
    a, b = np.searchsorted(t, (w * T0 - fbc.FIT_WINDOW_US, (w + bc.N_TARGETS + 1) * T0))
    return tuple(v[a:b] for v in ev)


# ------------------------------------------------------------------------------------------- the baseline
_RECORDS = {}
_ORIG_ENCODE = fbc.encode_group


def _capture(t, x, y, p, w, K, width, height, coder, flows, T0_us=bc.T0_US):
    rec = _ORIG_ENCODE(t, x, y, p, w, K, width, height, coder, flows, T0_us)
    _RECORDS[(coder, K)] = rec
    return rec


fbc.encode_group = _capture                  # evaluate_group calls the module attribute: wrapped from the runner


def frozen():
    tun = json.loads((mp.REPO / "results" / "fb" / "tuning.json").read_text())
    return {ds: {coder: tuple(v["frozen"][coder]["radius_res_us"]) for coder in bc.CODERS}
            for ds, v in tun["datasets"].items()}


# ------------------------------------------------------------------------------------------- downstream
def remake_window(ds, g, model, coder, w, m):
    W_, H_ = DIMS[ds]
    hdr = bc.encode_header(coder, model, 4, W_, H_, 20)
    h, groups = bc.decode_stream(hdr + g["records"][f"{model}_{coder}_K4"])
    gg = groups[0]
    gg["w"] = w
    return bc.reconstruct(h, gg, m)


def window_events(ev, wm):
    a, b = np.searchsorted(ev[0], (wm * T0, (wm + 1) * T0))
    return tuple(v[a:b] for v in ev)


def thin(ds, ev, g, w, coder):
    """Section 7: a random subset of every window m = 0..3 at the bits of remake_<coder>; coded and decoded."""
    W_, H_ = DIMS[ds]
    n = float(np.sum(g["n_true"][:4]))
    b = 8.0 * len(g["records"][f"affine_{coder}_K4"]) / n
    b_direct = float(np.sum(g["direct"][coder][:4])) / n
    q = min(1.0, b / b_direct)
    wins, nbytes = {}, 0
    for m in range(4):
        wm = w + m
        t, x, y, p = window_events(ev, wm)
        keep = np.random.default_rng(SEED + wm).random(len(t)) < q
        tr = t[keep] - wm * T0
        if coder == "T":
            buf = bc.encode_events_T(tr, x[keep], y[keep], p[keep])
            dt_, dx, dy, dp = bc.decode_events_T(buf)
        else:
            buf = bc.encode_events_Q(tr, x[keep], y[keep], p[keep], bc.Q_DIRECT, W_, H_)
            dt_, dx, dy, dp = bc.decode_events_Q(buf, bc.Q_DIRECT, W_, H_)
        nbytes += len(buf)
        wins[m] = (np.asarray(dt_, dtype=np.int64) + wm * T0, np.asarray(dx, dtype=np.int64),
                   np.asarray(dy, dtype=np.int64), np.asarray(dp, dtype=np.int64))
    return wins, {"q": q, "bits_per_true_event": 8.0 * nbytes / n}


def boxes_for(tracks, wm, W_, H_):
    """Section 7: per track, the box of the annotation frame nearest the window center, if it lies in the window."""
    c = (wm + 0.5) * T0
    out = []
    for tr in tracks:
        i = int(np.argmin(np.abs(tr.t - c)))
        if not (wm * T0 <= tr.t[i] < (wm + 1) * T0):
            continue
        x0, y0 = max(0.0, tr.x[i]), max(0.0, tr.y[i])
        x1, y1 = min(float(W_), tr.x[i] + tr.w[i]), min(float(H_), tr.y[i] + tr.h[i])
        if x1 > x0 and y1 > y0:
            out.append((int(tr.track_id), (x0, y0, x1 - x0, y1 - y0)))
    return out


def squares_for(true, W_, H_):
    _, x, y, _ = true
    nx = W_ // SQUARE
    cnt = np.bincount((y // SQUARE) * nx + x // SQUARE, minlength=nx * (H_ // SQUARE))
    order = np.lexsort((np.arange(len(cnt)), -cnt))[:N_SQUARES]
    return [((int(k % nx) * SQUARE, int(k // nx) * SQUARE, SQUARE, SQUARE), int(cnt[k])) for k in order
            if cnt[k] >= MIN_EVENTS_SQUARE]


def downstream(ds, ev, g, w, fbc_recs, tracks):
    W_, H_ = DIMS[ds]
    n = float(np.sum(g["n_true"][:4]))
    thin_w, thin_info = {}, {}
    for coder in bc.CODERS:
        thin_w[coder], thin_info[coder] = thin(ds, ev, g, w, coder)
    fbc_w = {coder: fbc.reconstruct(fbc_recs[coder], w, 4, W_, H_) for coder in bc.CODERS}
    bits = {"true_T": float(np.sum(g["direct"]["T"][:4])) / n, "true_Q": float(np.sum(g["direct"]["Q"][:4])) / n,
            "remake_T": 8.0 * len(g["records"]["affine_T_K4"]) / n, "remake_Q": 8.0 * len(g["records"]["affine_Q_K4"]) / n,
            "translation_Q": 8.0 * len(g["records"]["translation_Q_K4"]) / n,
            "static_Q": 8.0 * len(g["records"]["static_Q_K4"]) / n,
            "fbc_T": 8.0 * len(fbc_recs["T"]) / n, "fbc_Q": 8.0 * len(fbc_recs["Q"]) / n,
            "thin_T": thin_info["T"]["bits_per_true_event"], "thin_Q": thin_info["Q"]["bits_per_true_event"]}
    out = {"bits": bits, "thin_q": {c: thin_info[c]["q"] for c in bc.CODERS}, "objects": [], "motion": [],
           "outside": {s: 0 for s in SCHEMES}, "n_events": {}}
    for m in (1, 2, 3):
        wm = w + m
        true = window_events(ev, wm)
        rec = {"true": true,
               "remake_T": remake_window(ds, g, "affine", "T", w, m), "remake_Q": remake_window(ds, g, "affine", "Q", w, m),
               "translation_Q": remake_window(ds, g, "translation", "Q", w, m),
               "static_Q": remake_window(ds, g, "static", "Q", w, m),
               "fbc_T": fbc_w["T"][m], "fbc_Q": fbc_w["Q"][m], "thin_T": thin_w["T"][m], "thin_Q": thin_w["Q"][m]}
        rec = {s: tuple(np.asarray(v, dtype=np.int64) for v in r) for s, r in rec.items()}
        for s, (t, x, y, _) in rec.items():                         # acceptance check 4
            out["outside"][s] += int(np.count_nonzero((t < wm * T0) | (t >= (wm + 1) * T0) | (x < 0) | (x >= W_)
                                                      | (y < 0) | (y >= H_)))
        out["n_events"][str(m)] = {s: int(len(r[0])) for s, r in rec.items()}
        if tracks is not None:
            for tid, box in boxes_for(tracks, wm, W_, H_):
                t, x, y, _ = true
                n_in = int(np.count_nonzero((x >= box[0]) & (x < box[0] + box[2]) & (y >= box[1]) & (y < box[1] + box[3])))
                if n_in < MIN_EVENTS_BOX:
                    continue
                out["objects"].append({"m": m, "track": tid, "box": list(box),
                                       "scores": {s: dn.box_scores(true, r, box, wm * T0) for s, r in rec.items()}})
        if m == 2:
            for sq, n_sq in squares_for(true, W_, H_):
                out["motion"].append({"square": list(sq), "n_true": n_sq,
                                      "error_px": {s: dn.motion_error_px(true, r, sq, wm * T0) for s, r in rec.items()}})
    return out


# ------------------------------------------------------------------------------------------- tasks
def task(stage, key):
    ds, rid, ci = key.split("|")
    ci = int(ci)
    od = outdir(ds, stage)
    out = od / out_name(key)
    if out.exists():
        return
    t_start, c_start = time.time(), time.process_time()
    rows = remake_groups(ds, stage, rid)[ci * CHUNK[stage]:(ci + 1) * CHUNK[stage]]
    ev = read(ds, rid, [r["w"] for r in rows], od)
    W_, H_ = DIMS[ds]
    tracks = an.tracks(an.load_boxes(mp.annotation_path(rid))) if (ds == "etram" and stage == "R") else None
    res = []
    for r in rows:
        w, g = r["w"], r["group"]
        e = group_events(ev, w)
        item = {"j": r["j"], "w": w}
        c0, p0 = time.process_time(), time.perf_counter()
        if stage == "T":
            for radius, res_us in CONFIGS:
                o = fbc.evaluate_group(*e, w, W_, H_, Ks=(4,), coders=bc.CODERS, radius=radius, res_us=res_us)
                item[cfg_key(radius, res_us)] = o
            item["n_true_equal"] = all(item[cfg_key(*c)][f"{coder}_K4"]["n_true"] == g["n_true"][:4]
                                       for c in CONFIGS for coder in bc.CODERS)
        else:
            fz = frozen()[ds]
            item["fbc"], recs = {}, {}
            for cfg in sorted(set(fz.values())):
                coders = tuple(c for c in bc.CODERS if fz[c] == cfg)
                _RECORDS.clear()
                o = fbc.evaluate_group(*e, w, W_, H_, Ks=bc.GROUPS, coders=coders, radius=cfg[0], res_us=cfg[1])
                for c in coders:
                    item["fbc"][c] = {k: v for k, v in o.items() if not k[0] in "TQ" or k.startswith(c + "_")}
                    recs[c] = _RECORDS[(c, 4)]
            item["n_true_equal"] = all(item["fbc"][c][f"{c}_K{K}"]["n_true"] == g["n_true"][:K]
                                       for c in bc.CODERS for K in bc.GROUPS)
            item["fbc_cpu_s"] = time.process_time() - c0
            item["downstream"] = downstream(ds, ev, g, w, recs, tracks)
        item["cpu_s"], item["wall_s"] = time.process_time() - c0, time.perf_counter() - p0
        item["finished_utc"] = time.time()
        res.append(item)
    tmp = out.with_suffix(".tmp")
    with open(tmp, "wb") as f:
        pickle.dump({"key": key, "commit": (mp.REPO / "COMMIT").read_text().strip(), "groups": res,
                     "task_wall_s": time.time() - t_start, "task_cpu_s": time.process_time() - c_start}, f, protocol=5)
    tmp.rename(out)


def load(ds, stage, rid):
    out = []
    for f in sorted(outdir(ds, stage).glob(f"{rid}_[0-9][0-9][0-9].pkl")):
        with open(f, "rb") as fh:
            out += pickle.load(fh)["groups"]
    out.sort(key=lambda r: r["j"])
    return out


def run(stage, workers):
    state = FB_E / stage
    if (state / "plan.json").exists():
        if not (state / "RESUME").exists():
            sys.exit(f"{state} holds a run; touch {state}/RESUME to resume it")
    else:
        for ds in ("etram", "dsec"):
            d = outdir(ds, stage)
            if d.exists() and any(d.iterdir()):
                sys.exit(f"{d} exists and is not empty")
            d.mkdir(parents=True, exist_ok=True)
        (state / "logs").mkdir(parents=True, exist_ok=True)
        (state / "plan.json").write_text(json.dumps({"commit": (mp.REPO / "COMMIT").read_text().strip(),
                                                     "chunk": CHUNK[stage], "tasks": plan(stage)}) + "\n")
    tasks = json.loads((state / "plan.json").read_text())["tasks"]
    done_f = lambda k: (outdir(k.split("|")[0], stage) / out_name(k)).exists()
    pending = [t for t in tasks if not done_f(t)]
    running, fails, t0, done = {}, {}, time.time(), len(tasks) - len(pending)
    log = lambda m: print(f"{time.strftime('%H:%M:%S')} {m}", flush=True)
    log(f"{len(pending)} of {len(tasks)} tasks pending")
    while pending or running:
        for pr, k in list(running.items()):
            rc = pr.poll()
            if rc is None:
                continue
            del running[pr]
            if rc == 0 and done_f(k):
                done += 1
                log(f"[{done}/{len(tasks)}] {k} ok, running {len(running)}, t={time.time() - t0:.0f}s")
            else:
                fails[k] = fails.get(k, 0) + 1
                log(f"FAIL {k} rc={rc} (attempt {fails[k]})")
                if fails[k] < 2:
                    pending.append(k)
        if (state / "STOP").exists():
            pending = []
        target = M._target_workers(state, workers)
        while pending and len(running) < target and M._mem_available_gb() > 40.0:
            k = pending.pop(0)
            lf = open(state / "logs" / f"{k.replace('|', '_')}.log", "w")
            running[subprocess.Popen([sys.executable, __file__, "one", stage, k], stdout=lf,
                                     stderr=subprocess.STDOUT)] = k
            time.sleep(2)
        time.sleep(10)
    log(f"DONE failed={sorted(k for k, v in fails.items() if v >= 2)}")


# ------------------------------------------------------------------------------------------- projection
def n_groups(ds, stage):
    return sum(len(remake_groups(ds, stage, r)) for r in recordings(ds, stage))


def project(stage):
    """Section 8: CPU seconds per group of each dataset from the first 20 finished groups of the stage."""
    rows = []
    for ds in ("etram", "dsec"):
        for f in outdir(ds, stage).glob("*.pkl"):
            with open(f, "rb") as fh:
                d = pickle.load(fh)
            rows += [(g["finished_utc"], ds, g["cpu_s"]) for g in d["groups"]]
    rows.sort()
    first = rows[:20]
    per = {ds: [c for _, d, c in first if d == ds] for ds in ("etram", "dsec")}
    res = {"stage": stage, "n_groups_done": len(rows), "first_20": [{"dataset": d, "cpu_s": c} for _, d, c in first]}
    proj = {}
    for ds in ("etram", "dsec"):
        ng = n_groups(ds, stage)
        proj[ds] = {"n_groups": ng, "n_first": len(per[ds]), "mean_cpu_s": float(np.mean(per[ds])) if per[ds] else None,
                    "cpu_h": float(np.mean(per[ds])) * ng / 3600 if per[ds] else None}
    res["projection"] = proj
    res["cpu_h"] = sum(v["cpu_h"] for v in proj.values()) if all(v["cpu_h"] is not None for v in proj.values()) else None
    print(json.dumps(res, indent=1))
    return res


# ------------------------------------------------------------------------------------------- Stage T: the freeze
def tune(out):
    res = {"directive": "016", "stage": "T", "criterion": "J = (bits_base - bits) / bits_direct, s = fbc.summarize("
           "fbc.sum_groups(groups, '<coder>_K4'), g, coder, 4) with g the REMAKE sum of the same groups; median over "
           "the tuning recordings", "tie_rule": "largest J; on a tie the larger radius, then the larger res_us",
           "configurations": [list(c) for c in CONFIGS], "datasets": {}}
    for ds in ("etram", "dsec"):
        tuning = recordings(ds, "T")
        rows_fb = {r: load(ds, "T", r) for r in tuning}
        g_sum = {r: bc.sum_groups([x["group"] for x in remake_groups(ds, "T", r)]) for r in tuning}
        checks = {"n_groups": {r: len(v) for r, v in rows_fb.items()},
                  "groups_equal_remake": all([x["w"] for x in rows_fb[r]] == [x["w"] for x in remake_groups(ds, "T", r)]
                                             for r in tuning),
                  "n_true_equal": all(x["n_true_equal"] for v in rows_fb.values() for x in v)}
        d = res["datasets"][ds] = {"tuning": tuning, "checks": checks, "table": {}, "per_recording": {}, "frozen": {}}
        for coder in bc.CODERS:
            tab, per = {}, {}
            for c in CONFIGS:
                k = cfg_key(*c)
                pr = {}
                for r in tuning:
                    s = fbc.summarize(fbc.sum_groups([x[k] for x in rows_fb[r]], f"{coder}_K4"), g_sum[r], coder, 4)
                    pr[r] = s | {"J": (s["bits_base"] - s["bits"]) / s["bits_direct"],
                                 "st_us_median": float(np.median([x[k]["st_us"] for x in rows_fb[r]]))}
                med = lambda f: float(np.median([v[f] for v in pr.values()]))
                tab[k] = {"J": med("J"), "F": med("F"), "bits": med("bits"), "bits_base": med("bits_base"),
                          "gain_sub": med("gain_sub"), "st_us": med("st_us_median"), "n_recordings": len(pr)}
                per[k] = pr
            best = max(CONFIGS, key=lambda c: (tab[cfg_key(*c)]["J"], c[0], c[1]))
            d["table"][coder], d["per_recording"][coder] = tab, per
            d["frozen"][coder] = {"config": cfg_key(*best), "radius_res_us": list(best), **tab[cfg_key(*best)]}
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps({ds: {"frozen": v["frozen"], "checks": {k: x for k, x in v["checks"].items() if k != "n_groups"},
                           "J": {c: {k: round(x["J"], 4) for k, x in v["table"][c].items()} for c in bc.CODERS}}
                      for ds, v in res["datasets"].items()}, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode")
    ap.add_argument("args", nargs="*")
    ap.add_argument("--workers", type=int, default=20)
    a = ap.parse_args()
    {"run": lambda: run(a.args[0], a.workers), "one": lambda: task(*a.args), "project": lambda: project(*a.args),
     "tune": lambda: tune(*a.args)}[a.mode]()


if __name__ == "__main__":
    main()
