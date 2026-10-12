"""Directive 016, Sections 6 and 7: the tables of the baseline and of the downstream tasks.

  python3 scripts/fb_reduce.py RESULTS_DIR

Reads the Stage R outputs of ``scripts/fb_run.py`` and the kept per-group files of REMAKE; writes
``per_recording.json`` and ``report.json``. Strata: ``day`` and ``night`` (eTraM reporting recordings
with at least 10 groups), ``all`` (the 36 DSEC reporting sequences with at least 5 groups). Medians over
recordings with the bootstrap of directive 007 (2000 resamples of recordings), seed 20261016.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ec import blockcodec as bc, fbc, mp  # noqa: E402
import fb_run as FB  # noqa: E402

SEED, N_BOOT = 20261016, 2000
MIN_GROUPS = {"etram": 10, "dsec": 5}
STRATA = {"day": "etram", "night": "etram", "all": "dsec"}


def boot(vals):
    v = np.asarray(vals, dtype=float)
    ok = np.isfinite(v)
    out = {"median": None, "ci95": [None, None], "n_recordings": int(ok.sum()), "n_not_a_number": int((~ok).sum())}
    if ok.any():
        x = v[ok]
        bs = np.median(x[np.random.default_rng(SEED).integers(0, len(x), size=(N_BOOT, len(x)))], axis=1)
        out.update(median=float(np.median(x)), ci95=[float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))])
    return out


def nanmed(v):
    v = np.asarray(v, dtype=float)
    v = v[np.isfinite(v)]
    return float(np.median(v)) if len(v) else float("nan")


def interp_bits(F, pts):
    """Baseline bits at fidelity F, linear in F between the two neighbouring points; NaN outside the curve."""
    pts = sorted(pts)
    Fs = [a for a, _ in pts]
    if not (Fs[0] <= F <= Fs[-1]):
        return float("nan")
    for (f0, b0), (f1, b1) in zip(pts[:-1], pts[1:]):
        if f0 <= F <= f1:
            return b0 if f1 == f0 else b0 + (b1 - b0) * (F - f0) / (f1 - f0)
    return float("nan")


def main(resdir):
    res = Path(resdir)
    res.mkdir(parents=True, exist_ok=True)
    per_rec, rec_vals, checks = {}, {}, {"n_true_equal": True, "groups_equal_remake": True, "summarize_raised": [],
                                         "outside": {s: 0 for s in FB.SCHEMES}, "n_groups": {}}
    entering = {}
    for ds in ("etram", "dsec"):
        per_rec[ds], entering[ds] = {}, []
        for rid in FB.recordings(ds, "R"):
            rows = FB.load(ds, "R", rid)
            rg = FB.remake_groups(ds, "R", rid)
            checks["n_groups"][rid] = len(rows)
            checks["groups_equal_remake"] &= [r["w"] for r in rows] == [r["w"] for r in rg]
            checks["n_true_equal"] &= all(r["n_true_equal"] for r in rows)
            if len(rows) >= MIN_GROUPS[ds]:
                entering[ds].append(rid)
            g = bc.sum_groups([r["group"] for r in rg])
            sums = {c: {f"K{K}": fbc.sum_groups([r["fbc"][c] for r in rows], f"{c}_K{K}") for K in bc.GROUPS}
                    for c in bc.CODERS}
            per_rec[ds][rid] = {"n_groups": len(rows), "st_us": {c: [r["fbc"][c]["st_us"] for r in rows] for c in bc.CODERS},
                                "sums": sums}
            v = {"st_us": {c: float(np.median([r["fbc"][c]["st_us"] for r in rows])) for c in bc.CODERS}}
            for c in bc.CODERS:
                for K in bc.GROUPS:
                    try:
                        s = fbc.summarize(sums[c][f"K{K}"], g, c, K)
                    except ValueError as e:
                        checks["summarize_raised"].append([rid, c, K, str(e)])
                        continue
                    rm = bc.summarize(g, "B20_rho1.0", "affine", c, K)
                    v[(c, K)] = {"fb": s, "remake": rm}
                pts = [(v[(c, K)]["fb"]["F"], v[(c, K)]["fb"]["bits"]) for K in bc.GROUPS if (c, K) in v]
                for K in bc.GROUPS:
                    if (c, K) in v:
                        rm = v[(c, K)]["remake"]
                        v[(c, K)]["G_pred"] = interp_bits(rm["F"], pts) / rm["bits"]
            # downstream
            d = [r["downstream"] for r in rows]
            n_g = [float(np.sum(r["group"]["n_true"][:4])) for r in rg]
            for r in d:
                for s, k in r["outside"].items():
                    checks["outside"][s] += k
            v["bits"] = {k: float(np.sum([x["bits"][k] * n for x, n in zip(d, n_g)]) / np.sum(n_g)) for k in d[0]["bits"]}
            obj = [o for r in d for o in r["objects"]]
            mot = [o for r in d for o in r["motion"]]
            v["objects"] = {s: {"F": nanmed([o["scores"][s]["F"] for o in obj]),
                                "share_empty": (float(np.mean([o["scores"][s]["n_rec"] == 0 for o in obj])) if obj else float("nan")),
                                "centroid_px": nanmed([o["scores"][s]["centroid_px"] for o in obj if o["scores"][s]["n_rec"] > 0]),
                                "n_boxes": len(obj)} for s in FB.SCHEMES} if ds == "etram" else None
            v["motion"] = {s: {"error_px": nanmed([o["error_px"][s] for o in mot]),
                               "share_no_event": float(np.mean([not np.isfinite(o["error_px"][s]) for o in mot])) if mot else float("nan"),
                               "n_squares": len(mot)} for s in FB.SCHEMES}
            rec_vals[rid] = v
    T = {"1_baseline": {}, "2_equal_K": {}, "3_equal_F": {}, "objects": {}, "motion": {}, "bits": {}}
    for st, ds in STRATA.items():
        rids = [r for r in entering[ds] if ds == "dsec" or mp.lighting(r) == st]
        V = [rec_vals[r] for r in rids]
        for c in bc.CODERS:
            for K in bc.GROUPS:
                key = f"K{K}"
                rows = [v[(c, K)] for v in V if (c, K) in v]
                T["1_baseline"].setdefault(st, {}).setdefault(c, {})[key] = {
                    **{f: boot([r["fb"][f] for r in rows]) for f in ("F", "bits", "bits_base", "gain_sub")},
                    "st_us": boot([v["st_us"][c] for v in V])}
                T["2_equal_K"].setdefault(st, {}).setdefault(c, {})[key] = {
                    "bits_ratio_fb_over_remake": boot([r["fb"]["bits"] / r["remake"]["bits"] for r in rows]),
                    "F_remake_minus_F_fb": boot([r["remake"]["F"] - r["fb"]["F"] for r in rows]),
                    "remake_F": boot([r["remake"]["F"] for r in rows]), "remake_bits": boot([r["remake"]["bits"] for r in rows]),
                    "fb_F": boot([r["fb"]["F"] for r in rows]), "fb_bits": boot([r["fb"]["bits"] for r in rows])}
                gp = [r["G_pred"] for r in rows]
                T["3_equal_F"].setdefault(st, {}).setdefault(c, {})[key] = {
                    "G_pred": boot(gp), "n_nan": int(np.sum(~np.isfinite(gp))), "n_recordings": len(gp)}
        if ds == "etram":
            T["objects"][st] = {s: {f: boot([v["objects"][s][f] for v in V]) for f in ("F", "share_empty", "centroid_px")}
                                | {"n_boxes": int(sum(v["objects"][s]["n_boxes"] for v in V))} for s in FB.SCHEMES}
        T["motion"][st] = {s: {f: boot([v["motion"][s][f] for v in V]) for f in ("error_px", "share_no_event")}
                           | {"n_squares": int(sum(v["motion"][s]["n_squares"] for v in V))} for s in FB.SCHEMES}
        T["bits"][st] = {k: boot([v["bits"][k] for v in V]) for k in V[0]["bits"]}
    # acceptance check 5: REMAKE at K = 4 against Table 2 of reports 007 and 013
    rep = {"etram": json.loads((mp.REPO / "results" / "bk" / "report.json").read_text()),
           "dsec": json.loads((mp.REPO / "results" / "dt" / "report.json").read_text())}
    c5 = {}
    for st, ds in STRATA.items():
        for c in bc.CODERS:
            h = rep[ds]["tables"]["2_headline"][c][st]["K4"]["affine"]
            here = T["2_equal_K"][st][c]["K4"]
            c5[f"{st}_{c}"] = {"F": [here["remake_F"]["median"], h["F"]["median"]],
                               "bits": [here["remake_bits"]["median"], h["bits"]["median"]],
                               "pass": here["remake_F"]["median"] == h["F"]["median"]
                               and here["remake_bits"]["median"] == h["bits"]["median"]}
    tun = json.loads((mp.REPO / "results" / "fb" / "tuning.json").read_text())
    acc = {"3_true_events_equal": {"n_true_equal": checks["n_true_equal"], "summarize_raised": checks["summarize_raised"],
                                   "groups_equal_remake": checks["groups_equal_remake"],
                                   "pass": checks["n_true_equal"] and not checks["summarize_raised"]
                                   and checks["groups_equal_remake"]},
           "4_decoded_in_window_and_sensor": {"events_outside": checks["outside"],
                                              "pass": all(v == 0 for v in checks["outside"].values())},
           "5_remake_K4_equals_reports": c5 | {"pass": all(v["pass"] for v in c5.values())}}
    out = {"directive": "016", "frozen": {ds: v["frozen"] for ds, v in tun["datasets"].items()},
           "entering": {ds: len(v) for ds, v in entering.items()},
           "recordings_below_min_groups": {ds: [r for r in FB.recordings(ds, "R") if r not in entering[ds]]
                                           for ds in ("etram", "dsec")},
           "strata": {st: len([r for r in entering[ds] if ds == "dsec" or mp.lighting(r) == st]) for st, ds in STRATA.items()},
           "aggregation": {"unit": "recording", "min_groups": MIN_GROUPS, "n_boot": N_BOOT, "seed": SEED,
                           "objects": "per recording: median F over boxes, share of boxes with n_rec = 0, median "
                                      "centroid_px over the boxes with n_rec > 0; then medians over recordings",
                           "motion": "per recording: median error over squares where both sets have events, share "
                                     "of squares where the scheme has no event (error NaN); then medians over recordings",
                           "bits": "per recording: bits of the scheme over the four windows of each group per true "
                                   "event, summed over groups; then medians over recordings",
                           "st_us": "per recording: median over its groups"},
           "acceptance": acc, "tables": T}
    (res / "report.json").write_text(json.dumps(out, indent=1, default=float) + "\n")
    (res / "per_recording.json").write_text(json.dumps(per_rec, default=float) + "\n")
    print(json.dumps({"entering": out["entering"], "strata": out["strata"],
                      "acceptance": {k: v["pass"] for k, v in acc.items()}}, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
