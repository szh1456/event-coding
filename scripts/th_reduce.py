"""Directive 020, Section 6: Tables 1 to 5, the curve data and the per-recording sums.

  python3 scripts/th_reduce.py RESULTS_DIR

For a set of sums, ``F = 2 M / (N + N2)`` and ``F0 = 2 M0 / (N + N2)``. A recording enters a cell with the sums of
its groups when it has at least 200 true events there; the cell then reports the median over those recordings
with the 95% interval of the bootstrap of directive 007 (seed 20261016). A cell that no recording reaches reports
the pooled value over all recordings of the stratum, marked ``pooled``. The pooled value is given for every cell.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ec import blockcodec as bc, mp, threshold as th  # noqa: E402
import fb_reduce as FR  # noqa: E402
import hd_run as HR  # noqa: E402
import th_run as TR  # noqa: E402

STRATA = ("day", "night", "all")
MIN_EVENTS = 200
GRID_NAMES = [f"s{s}_k{k}" for s, k in th.GRIDS]
S1 = [i for i, (s, _) in enumerate(th.GRIDS) if s == 1]
DMAX = max(abs(d) for d in th.DELAYS)


def stratum(ds, rid):
    return "all" if ds == "dsec" else mp.lighting(rid)


def bin_centre(i):
    """Geometric centre of bin i of R_EDGES; the first bin [0, e1) uses the geometric step below e1; NaN for
    [128, inf) and for the no-tau bin."""
    e = th.R_EDGES
    if i >= th.N_BINS - 2:
        return float("nan")
    if i == 0:
        step = e[2] / e[1]
        return float(e[1] / np.sqrt(step))
    return float(np.sqrt(e[i] * e[i + 1]))


def fF(v):
    den = v[0] + v[1]
    return (2.0 * v[2] / den, 2.0 * v[3] / den) if den else (float("nan"), float("nan"))


def cell_table(rec_vecs, pooled_vec):
    """``rec_vecs``: per recording the 4-vector (N, N2, M, M0) of the cell; median rule of Section 6."""
    ent = [v for v in rec_vecs if v[0] >= MIN_EVENTS]
    Fp, F0p = fF(pooled_vec)
    out = {"N_pooled": int(pooled_vec[0]), "F_pooled": Fp, "F0_pooled": F0p,
           "diff_pooled": Fp - F0p if np.isfinite(Fp) else float("nan"), "n_recordings": len(ent)}
    if ent:
        F = [fF(v)[0] for v in ent]
        F0 = [fF(v)[1] for v in ent]
        out.update({"F": FR.boot(F), "F0": FR.boot(F0), "diff": FR.boot([a - b for a, b in zip(F, F0)]), "pooled": False})
    else:
        out.update({"F": {"median": Fp}, "F0": {"median": F0p}, "diff": {"median": Fp - F0p if np.isfinite(Fp) else float("nan")},
                    "pooled": True})
    return out


def main(resdir):
    res = Path(resdir)
    per_rec, sums, blocks, n_hot = {}, {}, {}, {}
    acc = {"groups_expected": 0, "groups_returned": 0, "pairs_bounded": True, "pixel_N_equals_blocks_N": True,
           "recordings_missing": []}
    for ds in ("etram", "dsec"):
        for rid, rows in HR.groups(ds, "d2").items():
            acc["groups_expected"] += len(rows)
            if not TR.out_path(ds, rid).exists():
                acc["recordings_missing"].append(rid)
                continue
            d = TR.load(ds, rid)
            gs = d["groups"]
            acc["groups_returned"] += len(gs)
            acc["groups_equal_019"] = acc.get("groups_equal_019", True) and [g["w"] for g in gs] == [r["w"] for r in rows]
            for g in gs:
                acc["pairs_bounded"] &= g["checks"]["pairs_bounded"]
                acc["pixel_N_equals_blocks_N"] &= g["checks"]["pixel_N_equals_blocks_N"]
            S = {sc: sum(g["sums"][sc] for g in gs) for sc in ("pixel", "block")}
            st = stratum(ds, rid)
            sums.setdefault(st, {})[rid] = S
            bl = {k: [v for g in gs for v in g["blocks"][k]] for k in gs[0]["blocks"]}
            blocks.setdefault(st, []).append(bl)
            n_hot.setdefault(st, []).extend(g["n_hot"] for g in gs)
            per_rec[rid] = {"dataset": ds, "stratum": st, "n_groups": len(gs), "n_entering_blocks": len(bl["ids"]),
                            "sums": {sc: S[sc].tolist() for sc in S}}
    T = {"1_pixel": {}, "2_pixel_by_speed": {}, "3_block": {}, "4_flicker": {}, "5_coverage": {}}
    curves = {"axes": {"flicker": [0, 1], "speed": [list(s) for s in th.SPEEDS], "grid": GRID_NAMES,
                       "bin_edges_r": [float(v) for v in th.R_EDGES], "last_bin": "pixels without tau",
                       "last_axis": ["N", "N2", "M", "M0"]}, "strata": {}}
    for st in STRATA:
        R = sums[st]
        pooled = {sc: sum(R[r][sc] for r in R) for sc in ("pixel", "block")}
        curves["strata"][st] = {sc: pooled[sc].tolist() for sc in pooled}

        def table(scope, grids, fl, speed=None):
            out = {}
            for g in grids:
                rows = []
                for b in range(th.N_BINS):
                    sel = (lambda a: a[fl, :, g, b].sum(axis=0)) if speed is None else (lambda a: a[fl, speed, g, b])
                    c = cell_table([sel(R[r][scope]) for r in R], sel(pooled[scope]))
                    r_c = bin_centre(b)
                    c.update({"bin": b, "r_lo": float(th.R_EDGES[b]) if b < th.N_BINS - 1 else None,
                              "r_hi": float(th.R_EDGES[b + 1]) if b < th.N_BINS - 1 else None,
                              "r_centre": r_c,
                              "pred_n1": float(th.predicted(r_c, 1)) if np.isfinite(r_c) else float("nan"),
                              "pred_ninf": float(th.predicted(r_c, np.inf)) if np.isfinite(r_c) else float("nan")})
                    rows.append(c)
                out[GRID_NAMES[g]] = rows
            return out

        T["1_pixel"][st] = table("pixel", S1, 0)
        T["2_pixel_by_speed"][st] = {f"speed_{a}_{b}": table("pixel", S1, 0, i) for i, (a, b) in enumerate(th.SPEEDS)}
        T["3_block"][st] = table("block", range(len(th.GRIDS)), 0)
        g11 = th.GRIDS.index((1, 1))
        share = {sc: float(pooled[sc][1, :, g11].sum(axis=0)[:, 0].sum() / max(1, pooled[sc][:, :, g11].sum(axis=(0, 1))[:, 0].sum()))
                 for sc in ("pixel", "block")}
        T["4_flicker"][st] = {"share_true_events_in_flicker": share, "pixel": table("pixel", S1, 1),
                              "block": table("block", range(len(th.GRIDS)), 1)}
        B = {k: [v for bl in blocks[st] for v in bl[k]] for k in blocks[st][0]}
        pix = pooled["pixel"][:, :, g11].sum(axis=(0, 1))[:, 0]
        dl = np.abs(np.array(B["delta_us"], dtype=float))
        T["5_coverage"][st] = {
            "share_true_events_without_tau": float(pix[-1] / pix.sum()) if pix.sum() else float("nan"),
            "median_covered": float(np.nanmedian(B["covered"])), "share_blocks_at_radius": float(np.mean(B["at_radius"])),
            "median_abs_delta_us": float(np.median(dl)), "share_delta_at_ends": float(np.mean(dl == DMAX)),
            "median_n_hot": float(np.median(n_hot[st])), "n_entering_blocks": len(B["ids"]),
            "n_recordings": len(R), "n_groups": int(sum(per_rec[r]["n_groups"] for r in R))}
    acc_out = {"2_sums_consistent": {"pairs_bounded": acc["pairs_bounded"],
                                     "pixel_N_equals_blocks_N": acc["pixel_N_equals_blocks_N"],
                                     "pass": acc["pairs_bounded"] and acc["pixel_N_equals_blocks_N"]},
               "3_every_group_returned": {"expected": acc["groups_expected"], "returned": acc["groups_returned"],
                                          "groups_equal_019": acc.get("groups_equal_019", False),
                                          "recordings_missing": acc["recordings_missing"],
                                          "pass": acc["groups_expected"] == acc["groups_returned"] and acc.get("groups_equal_019", False)}}
    out = {"directive": "020", "strata": {st: len(sums[st]) for st in STRATA},
           "rule": f"median over recordings with at least {MIN_EVENTS} true events in the cell (bootstrap of directive 007, "
                   "seed 20261016); otherwise the pooled value, marked pooled",
           "flicker": 0, "acceptance": acc_out, "tables": T}
    (res / "report.json").write_text(json.dumps(out, indent=1, default=float) + "\n")
    (res / "curves.json").write_text(json.dumps(curves, separators=(",", ":")) + "\n")
    (res / "per_recording.json").write_text(json.dumps(per_rec, separators=(",", ":")) + "\n")
    print(json.dumps({"strata": out["strata"], "acceptance": acc_out}, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
