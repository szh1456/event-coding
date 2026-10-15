"""Directive 024: the object of each stratum (Section 4) and its tolerance demo (Section 5).

  python3 scripts/td_run.py select [--workers 6]   # candidates of every group, resumable
  python3 scripts/td_run.py one DS RID             # candidates of one recording
  python3 scripts/td_run.py demo OUT_DIR           # choice per stratum, ec.tolerance_demo.demo and save

Groups, events and tracks as directive 022 (D-024-2): the D2 groups of directive 019 (``hd_run.groups(ds,
"d2")``), the events of ``[(w - 3) T0, (w + 2) T0)``; eTraM read once per recording with ``bk_run.read`` (at most
six reads at once), DSEC from the caches of directive 017 (``fm_run.dsec_events``); tracks with
``rc_run.load_tracks`` (DSEC-Detection with the time base of directive 017). For every group, every box of
``ec.regions.boxes_at(tracks, w + 1, W, H)`` gets the count of the events of window ``w + 1`` with
``x0 <= x < x0 + bw`` and ``y0 <= y < y0 + bh``, after the hot-pixel rule of ``ec.threshold`` as
``ec.tolerance_demo.demo`` applies it. Candidates under ``~/prjs/event_coding/td/cand/``.
"""
from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS",
           "VECLIB_MAXIMUM_THREADS", "NUMBA_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ec import blockcodec as bc, mp, regions as rg, threshold as th, tolerance_demo as td  # noqa: E402
import bk_run as BK  # noqa: E402
import fb_run as FB  # noqa: E402
import fm_run as FM  # noqa: E402
import hd_run as HR  # noqa: E402
import mp_measure as M  # noqa: E402

T0 = bc.T0_US
TD = Path.home() / "prjs" / "event_coding" / "td"
READ_SLOTS_E = 6
STRATA = ("day", "night", "all")


def stratum(ds, rid):
    return "all" if ds == "dsec" else mp.lighting(rid)


def cand_path(ds, rid):
    return TD / "cand" / f"{ds}_{rid}.json"


def events(ds, rid, ws):
    """The events of ``[(w - 3) T0, (w + 2) T0)`` for each window of ``ws``, as int64, as directive 022."""
    evs = {}
    if ds == "etram":
        lk = M._read_lock(TD, slots=READ_SLOTS_E)
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
            evs[w] = tuple(np.asarray(v[a:b], dtype=np.int64) for v in e)
    return evs


def tracks(ds, rid):
    return HR.RC.load_tracks(ds, rid, t_offset=HR.RC.t_offset_of(rid) if ds == "dsec" else None)


def candidates(ev, w, W, H, trk):
    """(track id, box, events of window w + 1 inside the box after the hot-pixel rule) for every box."""
    span = th._window(ev, max(0, w - th.SPAN_BEFORE) * T0, (w + 1) * T0)
    keep = ~th.hot_pixels(span, W, H)[ev[2] * W + ev[1]]
    t, x, y, _ = th._window(tuple(a[keep] for a in ev), (w + 1) * T0, (w + 2) * T0)
    out = []
    for tid, (x0, y0, bw, bh) in rg.boxes_at(trk, w + 1, W, H):
        n = int(np.count_nonzero((x >= x0) & (x < x0 + bw) & (y >= y0) & (y < y0 + bh)))
        out.append({"track_id": int(tid), "box": [x0, y0, bw, bh], "n": n})
    return out


def one(ds, rid):
    out = cand_path(ds, rid)
    if out.exists():
        return
    t_start, c_start = time.time(), time.process_time()
    rows = HR.groups(ds, "d2")[rid]
    W, H = FB.DIMS[ds]
    ws = [r["w"] for r in rows]
    evs = events(ds, rid, ws)
    trk = tracks(ds, rid)
    res = {"dataset": ds, "recording": rid, "commit": (mp.REPO / "COMMIT").read_text().strip(), "groups": []}
    for r in rows:
        res["groups"].append({"j": r["j"], "w": r["w"], "boxes": candidates(evs[r["w"]], r["w"], W, H, trk)})
    res["task_wall_s"], res["task_cpu_s"] = time.time() - t_start, time.process_time() - c_start
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp")
    tmp.write_text(json.dumps(res) + "\n")
    tmp.rename(out)


def plan():
    rec = {ds: [(ds, rid) for rid in HR.groups(ds, "d2")] for ds in ("dsec", "etram")}
    return rec["etram"] + rec["dsec"]


def select(workers):
    (TD / "logs").mkdir(parents=True, exist_ok=True)
    tasks = plan()
    pending = [k for k in tasks if not cand_path(*k).exists()]
    running, fails, t0, done = {}, {}, time.time(), len(tasks) - len(pending)
    log = lambda m: print(f"{time.strftime('%H:%M:%S')} {m}", flush=True)
    log(f"{len(pending)} of {len(tasks)} recordings pending")
    while pending or running:
        for pr, k in list(running.items()):
            if pr.poll() is None:
                continue
            del running[pr]
            if pr.returncode == 0 and cand_path(*k).exists():
                done += 1
                log(f"[{done}/{len(tasks)}] {k[0]}|{k[1]} ok, running {len(running)}, t={time.time() - t0:.0f}s")
            else:
                fails[k] = fails.get(k, 0) + 1
                log(f"FAIL {k} rc={pr.returncode} (attempt {fails[k]})")
                if fails[k] < 2:
                    pending.append(k)
        while pending and len(running) < workers and M._mem_available_gb() > 40.0:
            k = pending.pop(0)
            lf = open(TD / "logs" / f"{k[0]}_{k[1]}.log", "w")
            running[subprocess.Popen([sys.executable, __file__, "one", *k], stdout=lf, stderr=subprocess.STDOUT)] = k
            time.sleep(1)
        time.sleep(5)
    log(f"DONE failed={sorted(f'{k[0]}|{k[1]}' for k, v in fails.items() if v >= 2)}")


def choose():
    """Section 4: per stratum the box with the most events; ties to the earliest recording in population order,
    then the smallest w, then the smallest track id."""
    best, n_boxes = {}, {s: 0 for s in STRATA}
    for ds in ("etram", "dsec"):
        for order, rid in enumerate(HR.groups(ds, "d2")):
            c = json.loads(cand_path(ds, rid).read_text())
            s = stratum(ds, rid)
            for g in c["groups"]:
                for b in g["boxes"]:
                    n_boxes[s] += 1
                    key = (-b["n"], order, g["w"], b["track_id"])
                    if s not in best or key < best[s][0]:
                        best[s] = (key, {"dataset": ds, "recording": rid, "population_index": order, "j": g["j"],
                                         "w": g["w"], "track_id": b["track_id"], "box": b["box"], "n_in_box": b["n"]})
    return {s: dict(best[s][1], n_boxes_compared=n_boxes[s]) for s in STRATA}


def demo(out_dir):
    ch = choose()
    demos = {}
    for s in STRATA:
        c = ch[s]
        W, H = FB.DIMS[c["dataset"]]
        ev = events(c["dataset"], c["recording"], [c["w"]])[c["w"]]
        c0 = time.process_time()
        demos[s] = td.demo(ev, c["w"], W, H, tuple(c["box"]))
        c["demo_cpu_s"] = time.process_time() - c0
        print(s, json.dumps(c), flush=True)
    td.save(demos, out_dir)
    (Path(out_dir) / "choice.json").write_text(json.dumps({"commit": (mp.REPO / "COMMIT").read_text().strip(),
                                                           "choice": ch}, indent=1) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode")
    ap.add_argument("args", nargs="*")
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    {"select": lambda: select(a.workers), "one": lambda: one(*a.args), "demo": lambda: demo(*a.args)}[a.mode]()


if __name__ == "__main__":
    main()
