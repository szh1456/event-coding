"""Directive 011, Section 5: one typical group per stratum, decoded from its kept stream, for Fig. 5.

  python3 scripts/pf_recon.py OUTDIR [--rule 011|012]       (default 012)

Strata: eTraM by day and by night (the reporting recordings that enter the tables of report 007) and
DSEC (all 41 sequences). Selection from the per-group outputs of Stage R at the frozen configuration
(B = 20, rho = 1.0), model ``affine``, window m = 4: F_m = 2 match / (n_rec + n_true), median over the
groups of the stratum, the group closest to it (ties: smaller recording identifier, then smaller key
window). The group is decoded from the stream ``affine_Q_K11`` that Stage R kept; the true events of
window w + m are read with the dataset's reader; the match, the counts and F_m are checked against the
per-group values. No group is evaluated again (D-011-2). Writes recon_images.npz and recon_selection.json.

Rule 012 (directive 012, Section 3), the aggregation of the paper: for every recording
F_rec = 2 S_match / (S_rec + S_true) from the sums over its groups; the recording closest to the median
of F_rec over the recordings of the stratum (ties: smaller identifier); within it, the group whose F_m is
closest to F_rec (ties: smaller key window). Rule 011 is the selection of directive 011.
"""
from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ec import baseline, blockcodec as bc, dsec, mp  # noqa: E402
import bk_run as BK  # noqa: E402
import ds_run as DR  # noqa: E402

M = 4
CFG = "B20_rho1.0"
BK_DIR = Path.home() / "prjs" / "event_coding" / "bk"
DS_DIR = DR.BASE / "ds"
CROP_ETRAM = (320, 180)
STEP = 20


def f_m(g):
    r = g["codec"][CFG]["models"]["affine"]
    match, n_rec, n_true = r["match_s2_k3"][M - 1], r["n_rec"][M - 1], g["n_true"][M]
    den = n_rec + n_true
    return (2.0 * match / den if den > 0 else 0.0), match, n_rec, n_true


def candidates(stratum):
    """(recording, w, F_m, match, n_rec, n_true) of every group of the stratum."""
    out = []
    if stratum in ("day", "night"):
        rep = json.loads((mp.REPO / "results" / "bk" / "report.json").read_text())
        _, reporting = BK.subsets()
        below = set(rep["recordings_below_min_groups"])
        rids = [r for r in reporting if r not in below and mp.lighting(r) == stratum]
        load = lambda r: [x["group"] for x in BK.load_groups("R", BK_DIR, r)]
    else:
        rids = DR.sequences()
        load = lambda r: [x["group"] for x in DR.load_groups(DS_DIR, r)]
    for r in rids:
        for g in load(r):
            out.append((r, int(g["w"])) + f_m(g))
    return rids, out


def select(cands):
    """Rule 011: the group whose F_m is closest to the median of F_m over the groups of the stratum."""
    med = float(np.median([c[2] for c in cands]))
    best = min(cands, key=lambda c: (abs(c[2] - med), c[0], c[1]))
    return best, med


def select_012(cands):
    """Rule 012: the recording closest to the median of F_rec, then its group closest to F_rec."""
    sums = {}
    for r, w, F, match, n_rec, n_true in cands:
        s = sums.setdefault(r, [0, 0, 0])
        s[0] += match; s[1] += n_rec; s[2] += n_true
    f_rec = {r: (2.0 * s[0] / (s[1] + s[2]) if s[1] + s[2] > 0 else 0.0) for r, s in sums.items()}
    med = float(np.median(list(f_rec.values())))
    rid = min(f_rec, key=lambda r: (abs(f_rec[r] - med), r))
    best = min((c for c in cands if c[0] == rid), key=lambda c: (abs(c[2] - f_rec[rid]), c[1]))
    return best, f_rec[rid], med, len(f_rec)


def signed(t, x, y, p, crop):
    x0, y0, w, h = crop
    img = np.zeros((h, w), dtype=np.int16)
    x, y, p = (np.asarray(a, dtype=np.int64) for a in (x, y, p))
    sel = (x >= x0) & (x < x0 + w) & (y >= y0) & (y < y0 + h)
    np.add.at(img, (y[sel] - y0, x[sel] - x0), np.where(p[sel] == 1, 1, -1).astype(np.int16))
    return img, int(sel.sum())


def best_crop(x, y, W, H):
    cw, ch = CROP_ETRAM
    counts = np.zeros((H // STEP, W // STEP), dtype=np.int64)
    np.add.at(counts, (np.asarray(y) // STEP, np.asarray(x) // STEP), 1)
    nb_y, nb_x = ch // STEP, cw // STEP
    best, arg = -1, None
    for y0 in range(0, H - ch + 1, STEP):               # smallest y first, then smallest x: ties keep the first
        for x0 in range(0, W - cw + 1, STEP):
            c = int(counts[y0 // STEP:y0 // STEP + nb_y, x0 // STEP:x0 // STEP + nb_x].sum())
            if c > best:
                best, arg = c, (x0, y0, cw, ch)
    return arg


def main(outdir, rule="012"):
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    images, record = {}, {}
    for stratum in ("day", "night", "all"):
        rids, cands = candidates(stratum)
        extra = {}
        if rule == "012":
            (rid, w, F, match, n_rec, n_true), F_rec, F_rec_med, n_rec_rec = select_012(cands)
            med = float(np.median([c[2] for c in cands]))
            extra = {"F_rec": F_rec, "F_rec_median": F_rec_med, "n_recordings_F_rec": n_rec_rec, "rule": "012"}
        else:
            (rid, w, F, match, n_rec, n_true), med = select(cands)
            extra = {"rule": "011"}
        if stratum == "all":
            stream = DS_DIR / "R_streams" / f"{rid}__affine_Q_K11.ec07"
            t, x, y, p, _ = dsec.read_events(DR.DATA / rid / "events.h5")
            W, H = dsec.WIDTH, dsec.HEIGHT
        else:
            stream = BK_DIR / "R_streams" / f"{rid}__affine_Q_K11.ec07"
            ev = baseline.read_events(mp.event_path(rid))
            t, x, y, p = ev.t_us, ev.x, ev.y, ev.p
            W, H = 1280, 720
        h, groups = bc.decode_stream(stream.read_bytes())
        g = next(gg for gg in groups if gg["w"] == w)
        key = bc.reconstruct(h, g, 0)
        rec = bc.reconstruct(h, g, M)
        w0 = (w + M) * h["T0_us"]
        a, b = np.searchsorted(t, (w0, w0 + h["T0_us"]))
        tt, tx, ty, tp = t[a:b], x[a:b], y[a:b], p[a:b]
        m_dec = bc.Truth(tt, tx, ty, tp, w0, h["T0_us"]).match(*rec, bc.OBJECTIVE)
        F_dec = 2.0 * m_dec / (len(rec[0]) + len(tt)) if (len(rec[0]) + len(tt)) else 0.0
        check = {"match": [m_dec, match], "n_rec": [int(len(rec[0])), n_rec], "n_true": [int(len(tt)), n_true],
                 "F_m": [F_dec, F]}
        ok = m_dec == match and len(rec[0]) == n_rec and len(tt) == n_true and F_dec == F
        crop = [0, 0, W, H] if stratum == "all" else list(best_crop(tx, ty, W, H))
        n_ev = {}
        for name, evs in (("key", key), ("true", (tt, tx, ty, tp)), ("rec", rec)):
            images[f"{stratum}_{name}"], n_ev[name] = signed(*evs, crop)
        record[stratum] = {"recording": rid, "w": w, "m": M, "crop": crop, "n_events": n_ev, "F_window": F,
                           "F_window_median": med, "n_groups": len(cands), "n_recordings": len(rids),
                           "stream_file": str(stream), "check_step_5": check, "check_pass": bool(ok), **extra}
        print(stratum, rid, w, round(F, 4), round(med, 4), len(cands), "check", ok, check, flush=True)
        del t, x, y, p
    np.savez_compressed(out / "recon_images.npz", **images)
    (out / "recon_selection.json").write_text(json.dumps(record, indent=1) + "\n")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[3] if len(sys.argv) > 3 and sys.argv[2] == "--rule" else "012")
