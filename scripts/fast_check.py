"""The check of directive 007, Section 6 (Acceleration), for ``ec.blockcodec_fast``. Authorized by the author on
2026-10-12, outside a directive.

  python3 scripts/fast_check.py one DATASET RECORDING OUT_DIR   # one Stage 0 recording
  python3 scripts/fast_check.py collect OUT_DIR OUT.json

For every Stage 0 group of directives 007 (eTraM) and 009 (DSEC): ``ec.blockcodec_fast.evaluate_group`` with
the arguments of that Stage 0, compared with the kept output of the reference (``sender_<recording>.pkl``) in
every field, records included. For every Stage 0 stream: ``ec.blockcodec_fast.evaluate_streams`` compared with
the kept receiver output (``receiver.json``). Equal means equal: every field is an integer, a boolean or a byte
string. DSEC reads take the read lock of the running directive-016 Stage T, so no two DSEC reads overlap.
"""
from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS", "NUMBA_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import hashlib
import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ec import blockcodec as bc, blockcodec_fast as fast  # noqa: E402
import bk_run as BK  # noqa: E402
import ds_run as DR  # noqa: E402

DIRS = {"etram": Path.home() / "prjs" / "event_coding" / "bk" / "stage0", "dsec": DR.BASE / "ds" / "stage0"}
LOCK = {"etram": None, "dsec": DR.BASE / "ds" / "fb" / "T"}


def diff(a, b, path=""):
    if isinstance(a, dict):
        if not isinstance(b, dict) or set(a) != set(b):
            return [f"{path}: keys"]
        return [d for k in a for d in diff(a[k], b[k], f"{path}/{k}")]
    if isinstance(a, (list, tuple)):
        if not isinstance(b, (list, tuple)) or len(a) != len(b):
            return [f"{path}: length"]
        return [d for i, (u, v) in enumerate(zip(a, b)) for d in diff(u, v, f"{path}[{i}]")]
    if isinstance(a, np.ndarray) or isinstance(b, np.ndarray):
        a, b = np.asarray(a), np.asarray(b)
        return [] if a.shape == b.shape and np.array_equal(a, b) else [f"{path}: array"]
    if isinstance(a, (bool, np.bool_)) or isinstance(b, (bool, np.bool_)):
        return [] if bool(a) == bool(b) and isinstance(b, (bool, np.bool_)) else [f"{path}: {a!r} != {b!r}"]
    return [] if a == b and type(a) is type(b) else [f"{path}: {a!r} != {b!r}"]


def one(ds, rid, outdir):
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    d = DIRS[ds]
    snd = json.loads((d / "sender.json").read_text())["recordings"][rid]
    with open(d / f"sender_{rid}.pkl", "rb") as f:
        ref = pickle.load(f)
    t0 = time.time()
    if ds == "etram":
        ev = BK.read(rid)
        t, x, y, p = ev.t_us, ev.x, ev.y, ev.p
        W, H = BK.W, BK.H
        kw = dict(grid_for=(40, 1 / 16), records_for=(40, 1 / 16))
    else:
        t, x, y, p, _ = DR.read(rid, LOCK[ds])
        W, H = DR.W, DR.H
        kw = dict(blocks=(DR.FROZEN[0],), grid_for=DR.FROZEN, records_for=DR.FROZEN)
    read_s = time.time() - t0
    groups, w_prev = [], 0
    for j, w in enumerate(snd["w"]):
        c0 = time.process_time()
        g = fast.evaluate_group(t, x, y, p, w, w_prev, W, H, **kw)
        bad = diff(ref[j], g)
        groups.append({"j": j, "w": w, "equal": not bad, "differences": bad[:20], "n_differences": len(bad),
                       "fast_cpu_s": time.process_time() - c0})
        w_prev = w
        print(rid, j, w, "equal" if not bad else f"DIFF {len(bad)} {bad[:3]}", f"{groups[-1]['fast_cpu_s']:.1f}s", flush=True)
    rec = json.loads((d / "receiver.json").read_text())
    names = sorted(n for n in rec if n.startswith(rid + "__"))
    bufs = [(d / "streams" / n).read_bytes() for n in names]
    c0 = time.process_time()
    rows = fast.evaluate_streams(bufs, t, x, y, p)
    streams = {}
    for n, buf, r in zip(names, bufs, rows):
        ok_len = len(buf) == rec[n]["length"] and hashlib.sha256(buf).hexdigest() == rec[n]["sha256"]
        bad = diff(rec[n]["groups"], r)
        streams[n] = {"file_equal_to_receiver_record": ok_len, "equal": not bad, "differences": bad[:20]}
    res = {"dataset": ds, "recording": rid, "args": {k: list(v) if isinstance(v, tuple) else v for k, v in kw.items()},
           "read_s": read_s, "groups": groups, "streams": streams, "receiver_cpu_s": time.process_time() - c0,
           "reference_s": [r["evaluate_group_s"] for r in json.loads((d / "sender.json").read_text())["times"]
                           if r["rid"] == rid]}
    (out / f"{ds}_{rid}.json").write_text(json.dumps(res, indent=1) + "\n")
    print(rid, "groups equal", all(g["equal"] for g in groups), "streams equal",
          all(s["equal"] and s["file_equal_to_receiver_record"] for s in streams.values()), flush=True)


def collect(outdir, out):
    rows = [json.loads(f.read_text()) for f in sorted(Path(outdir).glob("*.json"))]
    n_g = sum(len(r["groups"]) for r in rows)
    n_s = sum(len(r["streams"]) for r in rows)
    ok_g = all(g["equal"] for r in rows for g in r["groups"])
    ok_s = all(s["equal"] and s["file_equal_to_receiver_record"] for r in rows for s in r["streams"].values())
    res = {"what": "directive 007, Section 6: ec.blockcodec_fast against the reference on every Stage 0 group "
                   "(directives 007 and 009), and the fast receiver against every Stage 0 stream",
           "authorized": "by the author, 2026-10-12, outside a directive",
           "commit": (Path(__file__).resolve().parent.parent / "COMMIT").read_text().strip()
           if (Path(__file__).resolve().parent.parent / "COMMIT").exists() else None,
           "n_groups": n_g, "n_streams": n_s, "groups_equal": ok_g, "streams_equal": ok_s, "pass": ok_g and ok_s,
           "speed": {r["recording"]: {"reference_s_per_group": float(np.mean(r["reference_s"])),
                                      "fast_cpu_s_per_group": float(np.mean([g["fast_cpu_s"] for g in r["groups"]]))}
                     for r in rows},
           "recordings": rows}
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps({k: res[k] for k in ("n_groups", "n_streams", "groups_equal", "streams_equal", "pass", "speed")},
                     indent=1))


if __name__ == "__main__":
    {"one": lambda: one(*sys.argv[2:5]), "collect": lambda: collect(*sys.argv[2:4])}[sys.argv[1]]()
