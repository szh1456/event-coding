"""Directive 013, Section 9: the DSEC row of Fig. 5, selected over the reporting subset; eTraM rows kept.

  python3 scripts/dt_recon.py BASE_DIR OUT_DIR

BASE_DIR holds the recon_images.npz and recon_selection.json of directive 012. Their eTraM entries
(``day_*``, ``night_*``) are copied unchanged; no file of eTraM is opened. The DSEC group is selected
by the rule of directive 012, Section 3, over the entering reporting sequences of directive 013, at
(B*, rho*) = (20, 1), and decoded from the stream ``affine_Q_K11`` of that configuration (the stream of
directive 009, D-013-2), as directive 011, Section 5, steps 3 to 8.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ec import blockcodec as bc, dsec  # noqa: E402
import ds_run as DR  # noqa: E402
import dt_run as DT  # noqa: E402
import pf_recon as PF  # noqa: E402


def main(base, outdir):
    base, out = Path(base), Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    old_img = np.load(base / "recon_images.npz")
    old_sel = json.loads((base / "recon_selection.json").read_text())
    images = {k: old_img[k] for k in old_img.files if k.startswith(("day_", "night_"))}
    record = {k: old_sel[k] for k in ("day", "night")}
    _, reporting = DT.subsets()
    DR.sequences = lambda: list(reporting)
    rids, cands = PF.candidates("all")
    (rid, w, F, match, n_rec, n_true), F_rec, F_rec_med, n_rec_rec = PF.select_012(cands)
    stream = PF.DS_DIR / "R_streams" / f"{rid}__affine_Q_K11.ec07"
    t, x, y, p, _ = dsec.read_events(DR.DATA / rid / "events.h5")
    h, groups = bc.decode_stream(stream.read_bytes())
    g = next(gg for gg in groups if gg["w"] == w)
    key, rec = bc.reconstruct(h, g, 0), bc.reconstruct(h, g, PF.M)
    w0 = (w + PF.M) * h["T0_us"]
    a, b = np.searchsorted(t, (w0, w0 + h["T0_us"]))
    tt, tx, ty, tp = t[a:b], x[a:b], y[a:b], p[a:b]
    m_dec = bc.Truth(tt, tx, ty, tp, w0, h["T0_us"]).match(*rec, bc.OBJECTIVE)
    F_dec = 2.0 * m_dec / (len(rec[0]) + len(tt))
    ok = m_dec == match and len(rec[0]) == n_rec and len(tt) == n_true and F_dec == F
    crop = [0, 0, dsec.WIDTH, dsec.HEIGHT]
    n_ev = {}
    for name, evs in (("key", key), ("true", (tt, tx, ty, tp)), ("rec", rec)):
        images[f"all_{name}"], n_ev[name] = PF.signed(*evs, crop)
    record["all"] = {"recording": rid, "w": w, "m": PF.M, "crop": crop, "n_events": n_ev, "F_window": F,
                     "F_window_median": float(np.median([c[2] for c in cands])), "n_groups": len(cands),
                     "n_recordings": len(rids), "stream_file": str(stream),
                     "check_step_5": {"match": [m_dec, match], "n_rec": [int(len(rec[0])), n_rec],
                                      "n_true": [int(len(tt)), n_true], "F_m": [F_dec, F]},
                     "check_pass": bool(ok), "F_rec": F_rec, "F_rec_median": F_rec_med,
                     "n_recordings_F_rec": n_rec_rec, "rule": "012",
                     "subset": "reporting subset of directive 013 (36 sequences)", "config": "B20_rho1.0"}
    np.savez_compressed(out / "recon_images.npz", **images)
    (out / "recon_selection.json").write_text(json.dumps(record, indent=1) + "\n")
    print(json.dumps({k: (v if not isinstance(v, (list, dict)) or k in ("n_events", "check_step_5") else v)
                      for k, v in record["all"].items()}, indent=1, default=float))


if __name__ == "__main__":
    main(*sys.argv[1:3])
