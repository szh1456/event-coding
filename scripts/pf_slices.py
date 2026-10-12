"""Directive 014, Section 6: time slices of Fig. 4 in a zoomed square.

  python3 scripts/pf_slices.py RECON_DIR

RECON_DIR holds ``recon_images.npz`` and ``recon_selection.json`` (as at 76b182b). For the group of each
stratum there, window m, decoded from its kept stream ``affine_Q_K11`` as in directive 011, Section 5,
this script reads the recording (D-014-2), takes the 80 px square on the 20 px lattice inside the crop
that holds the most true events of window m (ties: smaller row, then smaller column), and splits the
true and the rebuilt events of window m into its thirds ``time_bin(t_rel, 3)``. It adds the signed
images ``<stratum>_zoom_{true,rec}_b<b>`` to the npz, keeping the nine existing arrays, and ``zoom``,
``zoom_n_events``, ``zoom_F_bins`` and the check of step 5 to each entry of the selection. The
fidelity of a third is that of Eq. (fid) inside the square on voxels of 2 x 2 px and one polarity.
No group is evaluated again and the selection is not changed.
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
import ds_run as DR  # noqa: E402
import pf_recon as PF  # noqa: E402

SIDE, STEP, VOX = 80, 20, 2


def zoom_square(x, y, crop):
    x0, y0, w, h = crop
    best, arg = -1, None
    for sy in range(y0 - y0 % STEP + (STEP if y0 % STEP else 0), y0 + h - SIDE + 1, STEP):   # rows first: ties keep the smaller row
        for sx in range(x0 - x0 % STEP + (STEP if x0 % STEP else 0), x0 + w - SIDE + 1, STEP):
            c = int(np.count_nonzero((x >= sx) & (x < sx + SIDE) & (y >= sy) & (y < sy + SIDE)))
            if c > best:
                best, arg = c, [sx, sy, SIDE, SIDE]
    return arg


def inside(x, y, sq):
    sx, sy, w, h = sq
    return (x >= sx) & (x < sx + w) & (y >= sy) & (y < sy + h)


def fidelity(a, b):
    """Eq. (fid) of two event sets (x, y, p) on voxels of VOX x VOX px and one polarity."""
    def keys(x, y, p):
        return ((np.asarray(y, dtype=np.int64) // VOX) * (1 << 20) + np.asarray(x, dtype=np.int64) // VOX) * 2 \
            + np.asarray(p, dtype=np.int64)
    n = len(a[0]) + len(b[0])
    if n == 0:
        return 0.0
    ka, ca = np.unique(keys(*a), return_counts=True)
    kb, cb = np.unique(keys(*b), return_counts=True)
    _, ia, ib = np.intersect1d(ka, kb, assume_unique=True, return_indices=True)
    return float(2.0 * np.minimum(ca[ia], cb[ib]).sum() / n)


def main(recon_dir):
    d = Path(recon_dir)
    old = np.load(d / "recon_images.npz")
    images = {k: old[k] for k in old.files}
    sel = json.loads((d / "recon_selection.json").read_text())
    for stratum in ("day", "night", "all"):
        s = sel[stratum]
        rid, w, M = s["recording"], s["w"], s["m"]
        stream = Path(s["stream_file"])
        if stratum == "all":
            t, x, y, p, _ = dsec.read_events(DR.DATA / rid / "events.h5")
        else:
            ev = baseline.read_events(mp.event_path(rid))
            t, x, y, p = ev.t_us, ev.x, ev.y, ev.p
        h, groups = bc.decode_stream(stream.read_bytes())
        g = next(gg for gg in groups if gg["w"] == w)
        rec = bc.reconstruct(h, g, M)
        T0 = h["T0_us"]
        w0 = h["origin_us"] + (w + M) * T0
        a, b = np.searchsorted(t, (w0, w0 + T0))
        tt, tx, ty, tp = (np.asarray(v[a:b], dtype=np.int64) for v in (t, x, y, p))
        del t, x, y, p
        m_dec = bc.Truth(tt, tx, ty, tp, w0, T0).match(*rec, bc.OBJECTIVE)
        step5 = [m_dec == s["check_step_5"]["match"][1], int(len(rec[0])) == s["check_step_5"]["n_rec"][1],
                 int(len(tt)) == s["check_step_5"]["n_true"][1]]
        sq = zoom_square(tx, ty, s["crop"])
        rt, rx, ry, rp = (np.asarray(v, dtype=np.int64) for v in rec)
        tb_true, tb_rec = bc.time_bin(tt - w0, 3, T0), bc.time_bin(rt - w0, 3, T0)
        in_t, in_r = inside(tx, ty, sq), inside(rx, ry, sq)
        n_true, n_rec, F = [], [], []
        for k in range(3):
            st, sr = in_t & (tb_true == k), in_r & (tb_rec == k)
            images[f"{stratum}_zoom_true_b{k}"], nt = PF.signed(tt[st], tx[st], ty[st], tp[st], sq)
            images[f"{stratum}_zoom_rec_b{k}"], nr = PF.signed(rt[sr], rx[sr], ry[sr], rp[sr], sq)
            n_true.append(nt)
            n_rec.append(nr)
            F.append(fidelity((tx[st], ty[st], tp[st]), (rx[sr], ry[sr], rp[sr])))
        direct = {"true": int(in_t.sum()), "rec": int(in_r.sum())}
        s["zoom"] = sq
        s["zoom_n_events"] = {"true": n_true, "rec": n_rec}
        s["zoom_F_bins"] = F
        s["zoom_check_step_5"] = {"sum_over_thirds": {"true": sum(n_true), "rec": sum(n_rec)}, "counted_directly": direct,
                                  "pass": sum(n_true) == direct["true"] and sum(n_rec) == direct["rec"],
                                  "decoded_window_equals_check_step_5_of_011": bool(all(step5))}
        print(stratum, rid, w, sq, s["zoom_n_events"], [round(v, 4) for v in F], s["zoom_check_step_5"], flush=True)
    np.savez_compressed(d / "recon_images.npz", **images)
    (d / "recon_selection.json").write_text(json.dumps(sel, indent=1) + "\n")


if __name__ == "__main__":
    main(sys.argv[1])
