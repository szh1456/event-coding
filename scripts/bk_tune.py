"""Directive 007, Section 8: the criterion J on the tuning subset, and the frozen configuration.

  python3 scripts/bk_tune.py BKDIR OUT.json

For each tuning recording, its Stage T groups are added with ``sum_groups``; for
each configuration ``s = summarize(sum, config, "affine", "Q", 4)`` and
``J = (bits_base - bits) / bits_direct``. ``J(B, rho)`` is the median over the
tuning recordings with at least 10 groups (S = 90), day and night together. The
largest J is frozen; on a tie the larger B, then the larger rho.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ec import blockcodec as bc, mp  # noqa: E402
import bk_run as R  # noqa: E402

MIN_GROUPS = {90: 10, 180: 5, 360: 3}


def main(bkdir, out):
    bkdir = Path(bkdir)
    S = json.loads((bkdir / "T" / "plan.json").read_text())["spacing"]
    tuning, _ = R.subsets()
    sums, n_groups, checks = {}, {}, {"n": 0, "claim_equals_match_false": 0, "q_equals_t_false": 0}
    for rid in tuning:
        gs = [r["group"] for r in R.load_groups("T", bkdir, rid)]
        n_groups[rid] = len(gs)
        for g in gs:
            for row in g["codec"].values():
                for r in row["models"].values():
                    checks["n"] += 1
                    checks["claim_equals_match_false"] += not r["claim_equals_match"]
                    checks["q_equals_t_false"] += not r["q_equals_t"]
        if gs:
            sums[rid] = bc.sum_groups(gs)
    cfgs = [f"B{B}_rho{float(rho)}" for B in bc.BLOCKS for rho in bc.DENSITIES]
    per, table = {}, {}
    enter = [r for r in tuning if n_groups.get(r, 0) >= MIN_GROUPS[S]]
    for cfg in cfgs:
        rows = {}
        for rid in enter:
            s = bc.summarize(sums[rid], cfg, "affine", "Q", 4)
            rows[rid] = s | {"J": (s["bits_base"] - s["bits"]) / s["bits_direct"]}
        per[cfg] = rows
        med = lambda k, L=None: float(np.median([v[k] for r, v in rows.items() if L is None or mp.lighting(r) == L]))
        table[cfg] = {"J": med("J"), "J_day": med("J", "day"), "J_night": med("J", "night"),
                      **{f"median_{k}": med(k) for k in ("F", "bits", "bits_base", "gain")}, "n_recordings": len(rows)}
    key = lambda c: (table[c]["J"], int(c.split("_")[0][1:]), float(c.split("rho")[1]))
    frozen = max(cfgs, key=key)
    B, rho = int(frozen.split("_")[0][1:]), float(frozen.split("rho")[1])
    res = {"directive": "007", "stage": "T", "spacing": S, "criterion": "J = (bits_base - bits) / bits_direct, "
           "summarize(sum, config, 'affine', 'Q', 4); median over tuning recordings, day and night together",
           "n_groups_per_recording": n_groups, "recordings_entering": enter, "min_groups": MIN_GROUPS[S],
           "table": table, "frozen": {"config": frozen, "B": B, "rho": rho},
           "tie_rule": "largest J; on a tie the larger B, then the larger rho", "checks_stage_T": checks,
           "per_recording": per}
    Path(out).write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps({"frozen": res["frozen"], "checks": checks,
                      "J": {c: round(table[c]["J"], 4) for c in cfgs}}, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:3])
