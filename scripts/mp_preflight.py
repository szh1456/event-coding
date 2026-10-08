"""Directive 001, Section 5: preflight P1 to P4 on the execution host.

  python3 scripts/mp_preflight.py run OUTDIR [--workers N]   # one JSON per recording, plus env.json
  python3 scripts/mp_preflight.py reduce OUTDIR OUT.json      # preflight.json (P5 is added from the pytest log)

Each recording is read once with ``ec.baseline.read_events``. P3 (box convention
and clock) runs on the first five day and first five night recordings in sorted
order, over the first 60 s of events.
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
import platform
import socket
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ec import annotations, baseline, motion, mp  # noqa: E402

WIDTH, HEIGHT = 1280, 720
SHIFTS_US = (-200_000, -100_000, -33_333, 0, 33_333, 100_000, 200_000)
CONVENTIONS = ("top-left", "center")
FRAME_US = 1_000_000 / 30.0
P3_SPAN_US = 60_000_000
VEHICLES = (1, 3, 4, 5, 6)


def p3_ids(ids):
    day = [i for i in ids if mp.lighting(i) == "day"][:5]
    night = [i for i in ids if mp.lighting(i) == "night"][:5]
    return day + night


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rho_counts(ev, boxes) -> dict:
    """Event and area sums inside the union of a frame's boxes and outside all of them, per (shift, convention)."""
    t0 = int(ev.t_us[0])
    t_end = t0 + P3_SPAN_US
    bt = boxes["t"].astype(np.int64)
    frames = np.unique(bt)
    xs, ys = ev.x, ev.y
    out = {}
    for s in SHIFTS_US:
        for c in CONVENTIONS:
            acc = np.zeros(4)        # events in, area in, events out, area out
            n_frames = 0
            for ft in frames:
                tau = int(ft) + s
                if tau < t0 or tau + FRAME_US > t_end:
                    continue
                b = boxes[bt == ft]
                x0 = b["x"].astype(np.float64); y0 = b["y"].astype(np.float64)
                w = b["w"].astype(np.float64); h = b["h"].astype(np.float64)
                if c == "center":
                    x0, y0 = x0 - 0.5 * w, y0 - 0.5 * h
                grid = np.zeros((HEIGHT, WIDTH), dtype=bool)
                for a0, a1, c0, c1 in zip(np.ceil(y0), np.floor(y0 + h), np.ceil(x0), np.floor(x0 + w)):
                    r0, r1 = max(0, int(a0)), min(HEIGHT - 1, int(a1))
                    q0, q1 = max(0, int(c0)), min(WIDTH - 1, int(c1))
                    if r1 >= r0 and q1 >= q0:
                        grid[r0:r1 + 1, q0:q1 + 1] = True
                area = int(grid.sum())
                i0, i1 = np.searchsorted(ev.t_us, (tau, int(np.ceil(tau + FRAME_US))))
                ins = int(grid[ys[i0:i1], xs[i0:i1]].sum())
                acc += (ins, area, (i1 - i0) - ins, WIDTH * HEIGHT - area)
                n_frames += 1
            out[f"{s}|{c}"] = {"events_in": int(acc[0]), "area_in": int(acc[1]), "events_out": int(acc[2]),
                               "area_out": int(acc[3]), "n_frames": n_frames}
    return out


def track_stats(rid, boxes) -> list[dict]:
    rows = []
    for tr in annotations.tracks(boxes):
        dur = (tr.t_last - tr.t_first) * 1e-6
        if dur < 1.0:
            continue
        inst = motion.evaluation_instants(tr)
        sp = [float(np.hypot(*tr.velocity(int(t), 100_000))) for t in inst]
        rows.append({"track_id": tr.track_id, "class_id": tr.class_id, "lighting": mp.lighting(rid),
                     "group": "vehicles" if tr.class_id in VEHICLES else "other", "duration_s": dur,
                     "median_area_px": float(np.median(tr.w * tr.h)),
                     "median_speed_label": float(np.median(sp)) if sp else float("nan"), "n_instants": len(inst)})
    return rows


def one(args):
    rid, outdir, do_p3 = args
    out = Path(outdir) / f"{rid}.json"
    if out.exists():
        return rid, "exists"
    t_start = time.time()
    ann = mp.annotation_path(rid)
    boxes = annotations.load_boxes(ann)
    trs = annotations.tracks(boxes)
    t_read = time.time()
    ev = baseline.read_events(mp.event_path(rid))
    t_read = time.time() - t_read
    res = {"recording_id": rid, "lighting": mp.lighting(rid),
           "event_file": mp.event_path(rid).name, "annotation_file": ann.name,
           "annotation_sha256": sha256_file(ann),
           "n_events": int(len(ev)), "t_first_us": int(ev.t_us[0]), "t_last_us": int(ev.t_us[-1]),
           "duration_s": (int(ev.t_us[-1]) - int(ev.t_us[0])) * 1e-6,
           "n_time_inversions_clamped": int(ev.n_time_inversions_clamped),
           "n_coord_msb_repaired": int(ev.n_coord_msb_repaired),
           "x_max": int(ev.x.max()), "y_max": int(ev.y.max()),
           "n_boxes": int(len(boxes)), "n_tracks": len(trs),
           "ann_t_first_us": int(boxes["t"].min()) if len(boxes) else None,
           "ann_t_last_us": int(boxes["t"].max()) if len(boxes) else None,
           "tracks_ge_1s": track_stats(rid, boxes), "read_s": t_read}
    if do_p3:
        res["p3"] = rho_counts(ev, boxes)
    res["wall_s"] = time.time() - t_start
    tmp = out.with_suffix(".tmp")
    tmp.write_text(json.dumps(res) + "\n")
    tmp.rename(out)
    return rid, f"{res['wall_s']:.0f}s"


def env() -> dict:
    import h5py, numba, scipy, zstandard
    return {"host": socket.gethostname(), "python": platform.python_version(), "numpy": np.__version__,
            "scipy": scipy.__version__, "h5py": h5py.__version__, "zstandard": zstandard.__version__,
            "numba": numba.__version__, "blas_threads": {k: os.environ.get(k) for k in (
                "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")},
            "commit": (mp.REPO / "COMMIT").read_text().strip() if (mp.REPO / "COMMIT").exists() else "UNKNOWN"}


def run(outdir, workers):
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    ids, _ = mp.load_population()
    (outdir / "env.json").write_text(json.dumps(env(), indent=1) + "\n")
    p3 = set(p3_ids(ids))
    # longest first: file size is the cost
    order = sorted(ids, key=lambda r: -os.path.getsize(mp.event_path(r)))
    t0 = time.time()
    with mpr.get_context("spawn").Pool(workers, maxtasksperchild=1) as pool:
        for k, (rid, msg) in enumerate(pool.imap_unordered(one, [(r, str(outdir), r in p3) for r in order]), 1):
            print(f"[{k:3d}/112] {rid} {msg} t={time.time() - t0:.0f}s", flush=True)
    print("DONE", flush=True)


# ----------------------------------------------------------------------------- reduce
def _q(a):
    a = np.asarray([v for v in a if np.isfinite(v)], dtype=float)
    if len(a) == 0:
        return None
    return {"n": int(len(a)), **{f"q{int(q * 100):02d}": float(np.quantile(a, q)) for q in (0.05, 0.25, 0.5, 0.75, 0.95)}}


def reduce(outdir, out_json):
    outdir = Path(outdir)
    ids, d = mp.load_population()
    recs = {r: json.loads((outdir / f"{r}.json").read_text()) for r in ids if (outdir / f"{r}.json").exists()}
    e = json.loads((outdir / "env.json").read_text())
    # P2
    inv = [{k: v for k, v in recs[r].items() if k not in ("tracks_ge_1s", "p3")} for r in ids if r in recs]
    p2 = {"n_event_files_read": len(recs), "n_annotation_files_read": len(recs), "n_expected": len(ids),
          "ids_sorted_sha256": mp.ids_sha256(ids), "ids_sorted_sha256_matches": mp.ids_sha256(ids) == d["ids_sorted_sha256"],
          "n_events_total": int(sum(r["n_events"] for r in inv)),
          "n_boxes_total": int(sum(r["n_boxes"] for r in inv)), "n_tracks_total": int(sum(r["n_tracks"] for r in inv)),
          "n_time_inversions_clamped_total": int(sum(r["n_time_inversions_clamped"] for r in inv)),
          "n_coord_msb_repaired_total": int(sum(r["n_coord_msb_repaired"] for r in inv)),
          "nonzero_repairs": {r["recording_id"]: {"clamped": r["n_time_inversions_clamped"],
                                                   "msb": r["n_coord_msb_repaired"]}
                              for r in inv if r["n_time_inversions_clamped"] or r["n_coord_msb_repaired"]},
          "per_recording": inv}
    p2["pass"] = len(recs) == len(ids) == 112 and p2["ids_sorted_sha256_matches"]
    # P3
    p3r = [r for r in p3_ids(ids) if r in recs]
    keys = [f"{s}|{c}" for s in SHIFTS_US for c in CONVENTIONS]

    def rho(c):
        if c["area_in"] == 0 or c["events_out"] == 0:
            return float("nan")
        return (c["events_in"] / c["area_in"]) / (c["events_out"] / c["area_out"])

    table, argmax = {}, {}
    pooled = {k: {"events_in": 0, "area_in": 0, "events_out": 0, "area_out": 0, "n_frames": 0} for k in keys}
    for r in p3r:
        table[r] = {k: rho(recs[r]["p3"][k]) for k in keys}
        argmax[r] = max(keys, key=lambda k: table[r][k] if np.isfinite(table[r][k]) else -1)
        for k in keys:
            for f in pooled[k]:
                pooled[k][f] += recs[r]["p3"][k][f]
    table["pooled"] = {k: rho(pooled[k]) for k in keys}
    argmax["pooled"] = max(keys, key=lambda k: table["pooled"][k])
    ref = f"0|top-left"
    n_win = sum(argmax[r] == ref for r in p3r)
    p3 = {"recordings": p3r, "shifts_us": list(SHIFTS_US), "conventions": list(CONVENTIONS),
          "window": "first 60 s of events; frames whose shifted window [tau, tau + 33.333 ms) lies inside it",
          "rho": table, "argmax": argmax, "counts": {r: recs[r]["p3"] for r in p3r}, "pooled_counts": pooled,
          "n_recordings_with_argmax_at_0_top_left": int(n_win)}
    p3["pass"] = len(p3r) == 10 and n_win >= 8 and argmax["pooled"] == ref
    # P4
    rows = [t | {"recording_id": r} for r in ids if r in recs for t in recs[r]["tracks_ge_1s"]]
    strata = {}
    for light in ("day", "night", "all"):
        for grp in ("vehicles", "other", "all"):
            sel = [t for t in rows if (light == "all" or t["lighting"] == light) and (grp == "all" or t["group"] == grp)]
            strata[f"{light}|{grp}"] = {
                "n_tracks_ge_1s": len(sel), "n_instants": int(sum(t["n_instants"] for t in sel)),
                "duration_s": _q([t["duration_s"] for t in sel]), "median_area_px": _q([t["median_area_px"] for t in sel]),
                "median_speed_label_px_s": _q([t["median_speed_label"] for t in sel])}
    p4 = {"definition": "tracks living at least 1 s; vehicles = class_id in {1,3,4,5,6}; speed = median over the "
                        "track's evaluation instants of |velocity over the last 100 ms|; area = median w*h over frames",
          "class_id_counts": {str(k): int(v) for k, v in zip(*np.unique([t["class_id"] for t in rows], return_counts=True))},
          "strata": strata, "pass": len(rows) > 0}
    res = {"directive": "001", "P1": e | {"pass": True}, "P2": p2, "P3": p3, "P4": p4}
    Path(out_json).write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps({"P2": {k: v for k, v in p2.items() if k != "per_recording"}, "P3": {
        "argmax": argmax, "n_win": n_win, "pass": p3["pass"]}, "P4": {"tracks": strata["all|all"]["n_tracks_ge_1s"],
        "instants": strata["all|all"]["n_instants"]}}, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("run"); a.add_argument("outdir"); a.add_argument("--workers", type=int, default=12)
    b = sub.add_parser("reduce"); b.add_argument("outdir"); b.add_argument("out")
    args = ap.parse_args()
    run(args.outdir, args.workers) if args.cmd == "run" else reduce(args.outdir, args.out)
