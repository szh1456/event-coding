"""Directive 017, Section 6: Tables 1 to 3 from the per-group outputs of ``scripts/rc_run.py``.

  python3 scripts/rc_reduce.py RESULTS_DIR

A recording enters with at least 10 groups (eTraM) or 5 (DSEC), as in report 016; per-recording values are
ratios of sums over its groups; medians over recordings come with the bootstrap of directive 007, seed
20261016. Tables 2 and 3 pool blocks (Table 2) and (block, target) pairs (Table 3) of the entering
recordings of a stratum. Strata: day and night (eTraM), all (DSEC).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ec import blockcodec as bc, mp, regions as rg  # noqa: E402
import fb_reduce as FR  # noqa: E402
import fb_run as FB  # noqa: E402
import rc_run as RC  # noqa: E402

STRATA = {"day": "etram", "night": "etram", "all": "dsec"}
EDGES = (0.0, 1 / 16, 1 / 8, 1 / 4, 1 / 2, 1.0, 2.0, np.inf)
TAB3_CELLS = ((1, 3), (1, 12), (1, 32))


def ratio(a, b):
    return float(a) / float(b) if b else float("nan")


def per_recording(d):
    """Sums of one recording behind Tables 1 and 3."""
    gs = d["groups"]
    lab = [g for g in gs if g["events"] is not None]
    s = {"n_groups": len(gs), "n_groups_with_boxes": len(lab), "has_labels": d["has_labels"],
         "checks_all_true": all(g["checks"] == {"n_key": True, "maps_k4_prefix": True, "match_equals_kept": True} for g in gs),
         "n_key": int(sum(g["n_key"] for g in lab)), "n_true0": int(sum(g["n_true"][0] for g in lab)),
         "n_blocks": int(sum(len(g["blocks"]["ids"]) for g in lab)),
         "touch10": int(sum(int(np.sum(g["blocks"]["touch"][10])) for g in lab)),
         "key_in_box": {str(m): int(sum(g["events"]["key_in_box"][m] for g in lab)) for m in rg.MARGINS},
         "true0_in_box": {str(m): int(sum(g["events"]["true0_in_box"][m] for g in lab)) for m in rg.MARGINS},
         "pairs": {k: int(sum(sum(g["pairs"][k]) for g in lab)) for k in ("match", "match_in_box", "true", "true_in_box")},
         "boxes0": {"n": int(sum(len(g["boxes0"]) for g in lab)),
                    "n_true": int(sum(b["n_true"] for g in lab for b in g["boxes0"])),
                    "n_in_active": int(sum(b["n_in_active"] for g in lab for b in g["boxes0"])),
                    "none": int(sum(b["n_in_active"] == 0 for g in lab for b in g["boxes0"])),
                    "half": int(sum(2 * b["n_in_active"] >= b["n_true"] for g in lab for b in g["boxes0"]))},
         "prec": {rg.cell_name(c): {"got": [int(sum(g["blocks"]["prec"][rg.cell_name(c)]["got"][:, m].sum() for g in gs))
                                            for m in range(10)],
                                    "n_in": [int(sum(g["blocks"]["prec"][rg.cell_name(c)]["n_in"][:, m].sum() for g in gs))
                                             for m in range(10)]} for c in rg.PREC_CELLS}}
    v = {"touch10_share": ratio(s["touch10"], s["n_blocks"]),
         **{f"key_in_box_{m}": ratio(s["key_in_box"][str(m)], s["n_key"]) for m in rg.MARGINS},
         **{f"true0_in_box_{m}": ratio(s["true0_in_box"][str(m)], s["n_true0"]) for m in rg.MARGINS},
         "pairs_in_box": ratio(s["pairs"]["match_in_box"], s["pairs"]["match"]),
         "true_in_box": ratio(s["pairs"]["true_in_box"], s["pairs"]["true"]),
         "boxes0_events_in_active": ratio(s["boxes0"]["n_in_active"], s["boxes0"]["n_true"]),
         "boxes0_none": ratio(s["boxes0"]["none"], s["boxes0"]["n"]), "boxes0_half": ratio(s["boxes0"]["half"], s["boxes0"]["n"])}
    return s, v


def pooled_blocks(ds_rows):
    """Block columns of a stratum: one row per active block of every group (``touch`` only with boxes)."""
    cols = {k: [] for k in ("tau_us", "covered", "static", "speed_px_per_window", "both_polarity", "n_key", "touch10",
                            "has_boxes")}
    prec = {rg.cell_name(c): {"got": [], "n_in": []} for c in rg.PREC_CELLS}
    for d in ds_rows:
        for g in d["groups"]:
            b = g["blocks"]
            n = len(b["ids"])
            for k in ("tau_us", "covered", "static", "speed_px_per_window", "both_polarity", "n_key"):
                cols[k].append(np.asarray(b[k], dtype=np.float64))
            has = "touch" in b
            cols["touch10"].append(np.asarray(b["touch"][10], dtype=np.float64) if has else np.full(n, np.nan))
            cols["has_boxes"].append(np.full(n, float(has)))
            for c in rg.PREC_CELLS:
                for k in ("got", "n_in"):
                    prec[rg.cell_name(c)][k].append(np.asarray(b["prec"][rg.cell_name(c)][k], dtype=np.int64).reshape(n, 10))
    out = {k: np.concatenate(v) if v else np.zeros(0) for k, v in cols.items()}
    out["prec"] = {c: {k: (np.concatenate(v) if v else np.zeros((0, 10), dtype=np.int64)) for k, v in p.items()}
                   for c, p in prec.items()}
    return out


def table2(bl):
    out = {}
    for name, sel in (("touch", bl["touch10"] == 1.0), ("no_touch", bl["touch10"] == 0.0)):
        n = int(sel.sum())
        med = lambda a: float(np.nanmedian(a[sel])) if n else None
        out[name] = {"n_blocks": n, "static_share": float(np.mean(bl["static"][sel])) if n else None,
                     "median_speed_px_per_window": med(bl["speed_px_per_window"]),
                     "median_both_polarity": med(bl["both_polarity"]), "median_n_key": med(bl["n_key"])}
    out["pooled"] = "active blocks of all groups with boxes of the stratum, split by touch[10]"
    return out


def table3(bl):
    tau = bl["tau_us"]
    fin = np.isfinite(tau)
    out = {"share_blocks_finite_tau": float(np.mean(fin)) if len(tau) else None,
           "median_covered": float(np.nanmedian(bl["covered"])) if len(tau) else None,
           "median_tau_us": float(np.median(tau[fin])) if fin.any() else None,
           "median_tau_us_touch": float(np.median(tau[fin & (bl["touch10"] == 1.0)])) if (fin & (bl["touch10"] == 1.0)).any() else None,
           "median_tau_us_no_touch": float(np.median(tau[fin & (bl["touch10"] == 0.0)])) if (fin & (bl["touch10"] == 0.0)).any() else None,
           "bins": [f"[{a}, {b})" for a, b in zip(EDGES[:-1], EDGES[1:])], "grids": {}}
    for c in TAB3_CELLS:
        k = c[1]
        got, n_in = bl["prec"][rg.cell_name(c)]["got"], bl["prec"][rg.cell_name(c)]["n_in"]
        r = (bc.T0_US / k) / tau
        res = {}
        for label, ms in (("m1", [0]), ("m1_10", list(range(10)))):
            rows = []
            for lo, hi in zip(EDGES[:-1], EDGES[1:]):
                G = N = n = 0
                pred = []
                for m in ms:
                    s = fin & (r >= lo) & (r < hi) & (n_in[:, m] > 0)
                    n += int(s.sum())
                    G += int(got[s, m].sum())
                    N += int(n_in[s, m].sum())
                    pred.append(np.minimum(1.0, r[s]))
                pr = np.concatenate(pred) if pred else np.zeros(0)
                rows.append({"n_pairs": n, "precision": ratio(G, N), "mean_min1_r": float(pr.mean()) if len(pr) else None})
            res[label] = rows
        out["grids"][rg.cell_name(c)] = res
    out["pooled"] = "(block, target) pairs with n_in > 0 and a finite tau, of all groups of the stratum"
    return out


def main(resdir):
    res = Path(resdir)
    per_rec, vals, blocks_json, rows_by = {}, {}, {}, {}
    checks = {"all_groups_checks_true": True, "groups_equal_016": True, "recordings_without_labels": []}
    entering = {}
    for ds in ("etram", "dsec"):
        entering[ds] = []
        for rid in FB.recordings(ds, "R"):
            d = RC.load(ds, rid)
            rg_rows = FB.remake_groups(ds, "R", rid)
            checks["groups_equal_016"] &= [g["w"] for g in d["groups"]] == [r["w"] for r in rg_rows]
            if not d["has_labels"]:
                checks["recordings_without_labels"].append(rid)
            s, v = per_recording(d)
            checks["all_groups_checks_true"] &= s["checks_all_true"]
            per_rec[rid] = s
            vals[rid] = v
            if len(d["groups"]) >= FR.MIN_GROUPS[ds]:
                entering[ds].append(rid)
                st = "all" if ds == "dsec" else mp.lighting(rid)
                rows_by.setdefault(st, []).append(d)
    T = {"1_objects": {}, "2_regions_by_kind": {}, "3_precision_vs_spacing": {}}
    for st, ds in STRATA.items():
        rids = [r for r in entering[ds] if ds == "dsec" or mp.lighting(r) == st]
        T["1_objects"][st] = {k: FR.boot([vals[r][k] for r in rids]) for k in vals[rids[0]]}
        bl = pooled_blocks(rows_by[st])
        T["2_regions_by_kind"][st] = table2(bl)
        T["3_precision_vs_spacing"][st] = table3(bl)
        blocks_json[st] = {k: (v.tolist() if not isinstance(v, dict) else
                               {c: {kk: vv.tolist() for kk, vv in p.items()} for c, p in v.items()}) for k, v in bl.items()}
    labels = json.loads((mp.REPO / "results" / "rc" / "labels_check.json").read_text())
    out = {"directive": "017", "entering": {ds: len(v) for ds, v in entering.items()},
           "strata": {st: len([r for r in entering[ds] if ds == "dsec" or mp.lighting(r) == st]) for st, ds in STRATA.items()},
           "recordings_below_min_groups": {ds: [r for r in FB.recordings(ds, "R") if r not in entering[ds]] for ds in entering},
           "labels_convention": labels["convention"],
           "aggregation": {"unit": "recording", "min_groups": FR.MIN_GROUPS, "n_boot": FR.N_BOOT, "seed": FR.SEED,
                           "per_recording": "ratios of sums over its groups (Table 1: groups with boxes)"},
           "acceptance": {"2_checks": {"all_groups_checks_true": checks["all_groups_checks_true"],
                                       "groups_equal_016": checks["groups_equal_016"],
                                       "pass": checks["all_groups_checks_true"] and checks["groups_equal_016"]},
                          "3_time_base": {"convention": labels["convention"], "median_ratio": labels["median_ratio"],
                                          "pass": labels["pass"]},
                          "recordings_without_labels": checks["recordings_without_labels"]},
           "tables": T}
    (res / "report.json").write_text(json.dumps(out, indent=1, default=float) + "\n")
    (res / "per_recording.json").write_text(json.dumps({"sums": per_rec, "values": vals}, default=float) + "\n")
    (res / "blocks.json").write_text(json.dumps(blocks_json, default=float, separators=(",", ":")) + "\n")
    print(json.dumps({"entering": out["entering"], "strata": out["strata"], "acceptance": out["acceptance"]}, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
