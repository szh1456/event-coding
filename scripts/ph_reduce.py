"""Directive 022, Section 6: Tables 1 to 5, the reading of Table 1, the curve data and the per-recording sums.

  python3 scripts/ph_reduce.py RESULTS_DIR

Recordings enter with the sums of their groups. Unless a table says otherwise, a cell gives the value pooled over the
recordings of a stratum, with a 95% interval from a bootstrap over recordings (2000 resamples of recordings, seed
20261016, as directive 007) of the same pooled statistic, and the numbers of recordings and of pixels or events.
Table 2 and Table 3 follow the 200-event rule of report 020 (``th_reduce.cell_table``).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ec import blockcodec as bc, mp, phase as ph, threshold as th  # noqa: E402
import fb_reduce as FR  # noqa: E402
import hd_run as HR  # noqa: E402
import ph_run as P  # noqa: E402
import th_reduce as TRD  # noqa: E402

STRATA = ("day", "night", "all")
T2_K = (3, 12, 32, 64, 256)
GRID_NAMES = [f"s{s}_k{k}" for s, k in ph.GRIDS]
SPEED_NAMES = [f"{a}_{b}" for a, b in th.SPEEDS]


def boot_ratio(num, den):
    """Pooled sum(num) / sum(den) over recordings, with the 95% interval of a bootstrap over recordings."""
    num, den = np.asarray(num, dtype=float), np.asarray(den, dtype=float)
    out = {"value": float(num.sum() / den.sum()) if den.sum() > 0 else float("nan"), "n_recordings": int(len(num)),
           "n": float(den.sum()), "ci95": [None, None]}
    if len(num) and den.sum() > 0:
        idx = np.random.default_rng(FR.SEED).integers(0, len(num), size=(FR.N_BOOT, len(num)))
        d = den[idx].sum(axis=1)
        r = np.where(d > 0, num[idx].sum(axis=1) / np.where(d > 0, d, 1), np.nan)
        out["ci95"] = [float(np.nanpercentile(r, 2.5)), float(np.nanpercentile(r, 97.5))]
    return out


def phase_cell(stats, sel):
    """Pixels, mean cos and sin of pred and null over the recordings ``stats`` (each a dict of phase_stat arrays)."""
    out = {}
    for kind in ("pred", "null"):
        a = [sel(s[kind]) for s in stats]
        n = [x[0] for x in a]
        out[kind] = {"pixels": int(sum(n)), "cos": boot_ratio([x[1] for x in a], n), "sin": boot_ratio([x[2] for x in a], n)}
    return out


def reading(ci):
    lo, hi = ci
    if hi is not None and hi < 0.1:
        return "independent"
    if lo is not None and lo > 0.3:
        return "correlated"
    return "partial"


def main(resdir):
    res = Path(resdir)
    tasks = json.loads((P.PH_E / "plan.json").read_text())["tasks"]
    per_rec, recs = {}, {st: [] for st in STRATA}
    acc = {"groups_expected": 0, "groups_returned": 0, "models_expected": 0, "models_returned": 0, "pairs_bounded": True,
           "N_equals_blocks_N": True, "phase_counts_equal": True}
    for ds in ("etram", "dsec"):
        for rid, rows in HR.groups(ds, "d2").items():
            acc["groups_expected"] += len(rows)
            key = f"rec|{ds}|{rid}"
            if not P.out_path(key).exists():
                continue
            gs = P.load(key)["groups"]
            acc["groups_returned"] += len(gs)
            for g in gs:
                for k in ("pairs_bounded", "N_equals_blocks_N", "phase_counts_equal"):
                    acc[k] &= g["checks"][k]
            S = {"sums": {k: sum(g["sums"][k] for g in gs) for k in ph.TAU_KINDS},
                 "phase": {k: sum(g["phase"][k] for g in gs) for k in ("pred", "null")},
                 "phase_stat": {k: sum(g["phase_stat"][k] for g in gs) for k in ("pred", "null")},
                 "regular_share": sum(g["regular_share"] for g in gs), "skipped": int(sum(g["skipped_no_source"] for g in gs)),
                 "candidates": int(sum(g["n_candidates"] for g in gs)),
                 "blocks": {k: [v for g in gs for v in g["blocks"][k]] for k in gs[0]["blocks"]}, "n_groups": len(gs)}
            st = "all" if ds == "dsec" else mp.lighting(rid)
            recs[st].append(S)
            per_rec[rid] = {"dataset": ds, "stratum": st, "n_groups": len(gs), "n_entering_blocks": len(S["blocks"]["ids"]),
                            "n_skipped_no_source": S["skipped"], "n_candidates": S["candidates"],
                            "regular_share": S["regular_share"].tolist(),
                            "sums": {k: v.tolist() for k, v in S["sums"].items()},
                            "phase": {k: v.tolist() for k, v in S["phase"].items()},
                            "phase_stat": {k: v.tolist() for k, v in S["phase_stat"].items()}}
    T = {"1_phase": {}, "1_reading": {}, "2_binned_fidelity": {}, "3_by_speed_reg": {}, "4_coverage": {}, "5_model": {}}
    curves = {"axes": {"speed": SPEED_NAMES, "zero": [0, 1], "flicker": [0, 1], "tau_edges_us": ph.TAU_EDGES.tolist(),
                       "u_bins": ph.U_BINS, "grid": GRID_NAMES, "r_edges": [float(v) for v in th.R_EDGES],
                       "last_axis_sums": ["N", "N2", "M", "M0"], "last_axis_phase_stat": ["count", "sum_cos", "sum_sin"]},
              "strata": {}}
    ref020 = json.loads((mp.REPO / "results" / "th" / "report.json").read_text())["tables"]["1_pixel"]
    for st in STRATA:
        R = recs[st]
        stats = [r["phase_stat"] for r in R]
        t1 = {}
        for i, spn in enumerate(SPEED_NAMES):
            for zero in (0, 1):
                t1[f"speed_{spn}_zero{zero}"] = phase_cell(stats, lambda a, i=i, z=zero: a[i, z, 0].sum(axis=0))
        t1["moving_all_speeds"] = phase_cell(stats, lambda a: a[:, 0, 0].sum(axis=(0, 1)))
        t1["zero_all_speeds"] = phase_cell(stats, lambda a: a[:, 1, 0].sum(axis=(0, 1)))
        t1["moving_by_tau_bin"] = [dict(phase_cell(stats, lambda a, b=b: a[:, 0, 0, b].sum(axis=0)),
                                        tau_lo_us=float(ph.TAU_EDGES[b]), tau_hi_us=float(ph.TAU_EDGES[b + 1]))
                                   for b in range(len(ph.TAU_EDGES) - 1)]
        t1["moving_flicker"] = phase_cell(stats, lambda a: a[:, 0, 1].sum(axis=(0, 1)))
        T["1_phase"][st] = t1
        cos = t1["moving_all_speeds"]["pred"]["cos"]
        T["1_reading"][st] = {"mean_cos": cos["value"], "ci95": cos["ci95"], "reading": reading(cos["ci95"]),
                              "mean_sin": t1["moving_all_speeds"]["pred"]["sin"]["value"],
                              "null_cos": t1["moving_all_speeds"]["null"]["cos"]["value"],
                              "pixels": t1["moving_all_speeds"]["pred"]["pixels"],
                              "rule": "moving slice, flicker 0, speeds pooled: CI below 0.1 independent, above 0.3 "
                                      "correlated, else partial"}
        # Table 2 and 3
        rid_sums = {i: r["sums"] for i, r in enumerate(R)}

        def table(kind, k, speed=None):
            g = ph.GRIDS.index((1, k))
            rows = []
            pooled = sum(r[kind] for r in rid_sums.values())
            for b in range(th.N_BINS):
                sel = (lambda a: a[0, :, g, b].sum(axis=0)) if speed is None else (lambda a: a[0, speed, g, b])
                c = TRD.cell_table([sel(r[kind]) for r in rid_sums.values()], sel(pooled))
                rc = TRD.bin_centre(b)
                c.update({"bin": b, "r_lo": float(th.R_EDGES[b]) if b < th.N_BINS - 1 else None,
                          "r_centre": rc, "pred_n1": float(th.predicted(rc, 1)) if np.isfinite(rc) else float("nan"),
                          "pred_ninf": float(th.predicted(rc, np.inf)) if np.isfinite(rc) else float("nan")})
                rows.append(c)
            return rows

        T["2_binned_fidelity"][st] = {kind: {f"s1_k{k}": table(kind, k) for k in T2_K} for kind in ph.TAU_KINDS}
        T["2_binned_fidelity"][st]["ref_020_s1_k32"] = ref020[st]["s1_k32"]
        T["3_by_speed_reg"][st] = {f"speed_{spn}": {f"s1_k{k}": table("reg", k, i) for k in (32, 64)}
                                   for i, spn in enumerate(SPEED_NAMES)}
        # Table 4
        reg = sum(r["sums"]["reg"] for r in R)
        g11 = ph.GRIDS.index((1, 1))
        nb = reg[:, :, g11].sum(axis=(0, 1))[:, 0]
        rs = sum(r["regular_share"] for r in R)
        B = {k: [v for r in R for v in r["blocks"][k]] for k in R[0]["blocks"]}
        sh = np.array(B["shift"]) if B["shift"] else np.zeros((0, 2))
        T["4_coverage"][st] = {
            "share_true_events_without_tau_reg": float(nb[-1] / nb.sum()) if nb.sum() else float("nan"),
            "regular_share_real": int(rs[0]), "regular_share_surrogate": int(rs[1]),
            "regular_share_ratio_real_over_surrogate": float(rs[0] / rs[1]) if rs[1] else float("inf"),
            "candidates": int(sum(r["candidates"] for r in R)), "skipped_no_source": int(sum(r["skipped"] for r in R)),
            "share_candidates_skipped": float(sum(r["skipped"] for r in R) / max(1, sum(r["candidates"] for r in R))),
            "share_entering_at_radius": float(np.mean(B["at_radius"])) if B["at_radius"] else float("nan"),
            "share_entering_shift_00": float(np.mean(np.all(sh == 0, axis=1))) if len(sh) else float("nan"),
            "median_runner_up": float(np.median(B["runner_up"])) if B["runner_up"] else float("nan"),
            "median_abs_delta_us": float(np.median(np.abs(B["delta_us"]))) if B["delta_us"] else float("nan"),
            "n_entering_blocks": len(B["ids"]), "n_recordings": len(R), "n_groups": int(sum(r["n_groups"] for r in R))}
        curves["strata"][st] = {"phase": {k: sum(r["phase"][k] for r in R).tolist() for k in ("pred", "null")},
                                "phase_stat": {k: sum(r["phase_stat"][k] for r in R).tolist() for k in ("pred", "null")},
                                "sums": {k: sum(r["sums"][k] for r in R).tolist() for k in ph.TAU_KINDS}}
    # Table 5, the model, and acceptance check 4
    model, t5, acc4 = [], {}, {"independent_within_4se": True, "shared_above_0.85": True}
    for v in P.SPEEDS:
        for shared in (False, True):
            outs = [P.load(f"model|{v}|{int(shared)}|{s}") for s in P.SEEDS]
            for d in outs:
                acc["models_returned"] += 1
                for k in ("pairs_bounded", "N_equals_blocks_N", "phase_counts_equal"):
                    acc[k] &= d["group"]["checks"][k]
            acc["models_expected"] += len(P.SEEDS)
            stt = [d["group"]["phase_stat"]["pred"][:, 0].sum(axis=(0, 1, 2)) for d in outs]
            pooled = np.sum(stt, axis=0)
            cell = {"v": v, "shared": shared, "pixels_mean": float(np.mean([s[0] for s in stt])),
                    "cos_mean": float(np.mean([s[1] / s[0] for s in stt])), "sin_mean": float(np.mean([s[2] / s[0] for s in stt])),
                    "cos_pooled": float(pooled[1] / pooled[0]), "sin_pooled": float(pooled[2] / pooled[0]),
                    "se_pooled": float(np.sqrt(0.5 / pooled[0])), "F": {}}
            for k in (32, 64, 128):
                g = ph.GRIDS.index((1, k))
                fs = []
                for d in outs:
                    vv = d["group"]["sums"]["reg"][0].sum(axis=0)[g].sum(axis=0)
                    fs.append(2 * vv[2] / (vv[0] + vv[1]) if vv[0] + vv[1] else float("nan"))
                r = (bc.T0_US / k) / 2000.0
                cell["F"][f"s1_k{k}"] = {"F": float(np.mean(fs)), "equation_n3": float(th.predicted(r, 3)), "r": r}
            if shared:
                if v in (2.5, 6.5, 13.3):
                    acc4["shared_above_0.85"] &= cell["cos_pooled"] > 0.85
            else:
                acc4["independent_within_4se"] &= abs(cell["cos_pooled"]) < 4 * cell["se_pooled"]
            t5[f"v{v}_{'shared' if shared else 'independent'}"] = cell
            model += [{"v": v, "shared": shared, "seed": d["seed"], "n_events": d["n_events"],
                       "phase_stat": {k: d["group"]["phase_stat"][k].tolist() for k in ("pred", "null")},
                       "sums_reg": d["group"]["sums"]["reg"].tolist(), "n_blocks": len(d["group"]["blocks"]["ids"]),
                       "skipped_no_source": d["group"]["skipped_no_source"]} for d in outs]
    T["5_model"] = t5
    acc_out = {"2_sums_and_phase_counts": {k: acc[k] for k in ("pairs_bounded", "N_equals_blocks_N", "phase_counts_equal")}
               | {"pass": acc["pairs_bounded"] and acc["N_equals_blocks_N"] and acc["phase_counts_equal"]},
               "3_every_group_and_scene": {k: acc[k] for k in ("groups_expected", "groups_returned", "models_expected",
                                                               "models_returned")}
               | {"pass": acc["groups_expected"] == acc["groups_returned"] and acc["models_expected"] == acc["models_returned"]},
               "4_model_agrees_with_section_2": acc4 | {"pass": acc4["independent_within_4se"] and acc4["shared_above_0.85"]}}
    out = {"directive": "022", "strata": {st: len(recs[st]) for st in STRATA}, "acceptance": acc_out,
           "aggregation": {"pooled": "sums over the recordings of a stratum", "bootstrap": "2000 resamples of recordings, seed "
                           "20261016, of the pooled statistic", "table2": "the 200-event rule of report 020"},
           "tables": T}
    (res / "report.json").write_text(json.dumps(out, indent=1, default=float) + "\n")
    (res / "per_recording.json").write_text(json.dumps(per_rec, separators=(",", ":"), default=float) + "\n")
    (res / "curves.json").write_text(json.dumps(curves, separators=(",", ":"), default=float) + "\n")
    (res / "model.json").write_text(json.dumps(model, separators=(",", ":"), default=float) + "\n")
    print(json.dumps({"strata": out["strata"], "acceptance": acc_out, "reading": T["1_reading"]}, indent=1, default=float))


if __name__ == "__main__":
    main(sys.argv[1])
