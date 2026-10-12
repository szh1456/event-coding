"""Directive 013, Section 8: the tables over the reporting subset.

  python3 scripts/dt_reduce.py DSDIR DTDIR RESULTS_DIR

The frozen configuration is (20, 1), so by D-013-2 the Stage R of this directive is the Stage R of
directive 009 for the 36 reporting sequences (per-group files and streams checked in P4). The tables
are those of ``scripts/ds_reduce.py`` restricted to the reporting subset, with Section 8's changes:
Table 9 counted from the evaluated groups at B*, Table T in place of Table 11, and the new Table 13.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ec import blockcodec as bc, mp  # noqa: E402
import ds_reduce as RED  # noqa: E402
import ds_run as DR  # noqa: E402
import dt_run as DT  # noqa: E402


def main(dsdir, dtdir, resdir):
    dsdir, dtdir, res = Path(dsdir), Path(dtdir), Path(resdir)
    res.mkdir(parents=True, exist_ok=True)
    tuning, reporting = DT.subsets()
    tun = json.loads((dtdir / "tuning.json").read_text())
    B, rho = tun["frozen"]["B"], tun["frozen"]["rho"]
    assert (B, rho) == (20, 1.0), "Stage R of directive 009 is reused only for the frozen (20, 1) (D-013-2)"
    DR.sequences = lambda: list(reporting)                      # the reducer of 009 over the reporting subset
    tmp = res / "_ds_reduce"
    RED.main(dsdir, tmp)
    r = json.loads((tmp / "report.json").read_text())
    T = r["tables"]
    strata = {k: [s for s in reporting if k == "all" or s.startswith(k)] for k in r["strata"]}
    strata = {k: [s for s in v if s not in r["recordings_below_min_groups"]] for k, v in strata.items()}

    # Table 9 at B*, from the evaluated groups (the number of active blocks of each key window)
    sums_groups = {s: [x["group"] for x in DR.load_groups(dsdir, s)] for s in reporting}
    nblk = (DR.W // B) * (DR.H // B)
    t9 = {}
    for st, ss in strata.items():
        for rho_ in bc.DENSITIES:
            cfg = f"B{B}_rho{float(rho_)}"
            v = np.array([np.mean([g["codec"][cfg]["n_active"] for g in sums_groups[s]]) for s in ss if sums_groups[s]])
            t9.setdefault(st, {})[cfg] = {
                "mean_active_blocks_per_key_window": {str(x): float(np.quantile(v, x)) for x in (0.1, 0.5, 0.9)},
                "as_share_of_all_blocks": {str(x): float(np.quantile(v, x)) / nblk for x in (0.1, 0.5, 0.9)},
                "n_sequences": int(len(v)), "n_blocks_sensor": nblk, "source": "n_active of the evaluated groups"}
    T["9_census"] = t9
    # Table T in place of Table 11
    T.pop("11_next_to_etram", None)
    T["T_tuning"] = {"tuning_subset": tuning, "n_groups": tun["n_groups"], "table": tun["table"],
                     "frozen": tun["frozen"], "source": "results/dt/tuning.json"}
    # Table 13: the frozen configuration over the reporting subset next to report 009 over all 41 (copied)
    ds = json.loads((mp.REPO / "results" / "ds" / "report.json").read_text())["tables"]
    t13 = {}
    for K in (4, 11):
        here = T["2_headline"]["Q"]["all"][f"K{K}"]["affine"]
        ev = T["3_events"]["all"][f"K{K}"]["affine"]
        there = ds["2_headline"]["Q"]["all"][f"K{K}"]["affine"]
        ev009 = ds["3_events"]["all"][f"K{K}"]["affine"]
        t13[f"K{K}"] = {"reporting_subset_36": {"F": here["F"], "bits": here["bits"], "gain": here["gain"],
                                                "share": ev["share"]},
                        "report_009_all_41_copied": {"F": there["F"]["median"], "bits": there["bits"]["median"],
                                                     "gain": there["gain"]["median"], "share": ev009["share"]["median"]}}
    T["13_reporting_vs_009"] = {"coder": "Q", "model": "affine", "config": f"B{B}_rho{float(rho)}", **t13,
                                "note": "report-009 values copied from results/ds/report.json (all 41 sequences); "
                                        "not computed here"}
    # Acceptance: Stage T checks, tuning sequences absent from every table but Table T
    acc = r["acceptance"]
    acc["3_stage_T"] = tun["checks_stage_T"] | {"pass": tun["checks_stage_T"]["claim_equals_match_false"] == 0
                                                and tun["checks_stage_T"]["q_equals_t_false"] == 0}
    acc["4_streams"] = {"stage_R_ran": False, "note": "Stage R did not run (D-013-2); the streams of directive 009 "
                        "for the reporting sequences were checked again here", **acc.pop("7_streams_R")}
    text = json.dumps({k: v for k, v in T.items() if k != "T_tuning"})
    acc["5_tuning_absent"] = {"tuning_names_in_tables_other_than_T": [s for s in tuning if s in text],
                              "pass": not any(s in text for s in tuning)}
    out = {"directive": "013", "spacing": r["spacing"], "frozen": f"B{B}_rho{float(rho)}",
           "subset": "reporting (36 sequences)", "strata": r["strata"], "recordings_entering": r["recordings_entering"],
           "recordings_below_min_groups": r["recordings_below_min_groups"], "acceptance": acc,
           "aggregation": r["aggregation"], "stage_R": "the Stage R of directive 009 for the reporting sequences "
           "(D-013-2), files checked in P4", "tables": T,
           "for_comparison_rules_of_009_over_the_reporting_subset": r["decision_rule"]}
    (res / "report.json").write_text(json.dumps(out, indent=1, allow_nan=False, default=float) + "\n")
    per = json.loads((tmp / "per_recording.json").read_text())
    tsums = json.loads((dtdir / "T_sums.json").read_text())
    (res / "per_recording.json").write_text(json.dumps({"tuning_all_15_configurations": tsums,
                                                        "reporting_frozen": per}, default=float) + "\n")
    (res / "streams_provenance.json").write_text((tmp / "streams_provenance.json").read_text())
    for f in tmp.iterdir():
        f.unlink()
    tmp.rmdir()
    print(json.dumps({"strata": out["strata"], "entering": out["recordings_entering"],
                      "acc": {k: v.get("pass") for k, v in acc.items()},
                      "K4": t13["K4"], "K11": t13["K11"]}, indent=1, default=float))


if __name__ == "__main__":
    main(*sys.argv[1:4])
