"""Directive 014, Section 5: the trade-off between bits and fidelity over the threshold, from committed files.

  python3 scripts/pf_tradeoff.py OUT.json

Strata: ``day`` and ``night``, the reporting recordings of eTraM that enter the tables of report 007
(``results/bk/per_recording.json`` minus ``recordings_below_min_groups`` of ``results/bk/report.json``);
``all``, the reporting sequences of DSEC that enter the tables of report 013
(``results/dt/per_recording.json#/reporting_frozen`` minus those of ``results/dt/report.json``).
Per recording ``s = summarize(sum, config, "affine", "Q", K)``; medians over recordings of ``F``,
``100 bits / bits_direct``, ``100 bits_base / bits_direct`` and ``gain``, over the finite values, as
the reducers of 007 and 013 take them. No recording is read.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ec import blockcodec as bc  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
GROUPS = ("K2", "K4", "K8", "K11")
CONFIGS = ("B20_rho0.0625", "B20_rho0.125", "B20_rho0.25", "B20_rho0.5", "B20_rho1.0")
FIELDS = ("F", "bits_pct", "sub_pct", "gain")


def _median(vals):
    v = np.asarray(vals, dtype=float)
    ok = np.isfinite(v)
    return (float(np.median(v[ok])) if ok.any() else None), int(ok.sum())


def strata():
    bk = json.loads((REPO / "results" / "bk" / "report.json").read_text())
    dt = json.loads((REPO / "results" / "dt" / "report.json").read_text())
    s_bk = json.loads((REPO / "results" / "bk" / "per_recording.json").read_text())
    s_dt = json.loads((REPO / "results" / "dt" / "per_recording.json").read_text())["reporting_frozen"]
    enter_bk = [r for r in sorted(s_bk) if r not in bk["recordings_below_min_groups"]]
    enter_dt = [r for r in sorted(s_dt) if r not in dt["recordings_below_min_groups"]]
    return ({"day": ([r for r in enter_bk if r.startswith("train_day_")], s_bk, bk),
             "night": ([r for r in enter_bk if r.startswith("train_night_")], s_bk, bk),
             "all": (enter_dt, s_dt, dt)})


def main(out):
    res = {"directive": "014", "coder": "Q", "model": "affine", "cell": list(bc.OBJECTIVE), "strata": {},
           "n_recordings": {}, "check": {}}
    ok_all = True
    for name, (rids, sums, report) in strata().items():
        res["n_recordings"][name] = len(rids)
        T = report["tables"]
        st = res["strata"][name] = {}
        chk = res["check"][name] = {}
        for K in GROUPS:
            st[K] = {}
            for cfg in CONFIGS:
                rows = []
                for r in rids:
                    try:
                        s = bc.summarize(sums[r], cfg, "affine", "Q", int(K[1:]))
                        rows.append((s["F"], 100.0 * s["bits"] / s["bits_direct"], 100.0 * s["bits_base"] / s["bits_direct"],
                                     s["gain"]))
                    except ZeroDivisionError:
                        rows.append((float("nan"),) * 4)
                cols = list(zip(*rows))
                st[K][cfg] = {f: _median(c)[0] for f, c in zip(FIELDS, cols)}
                st[K][cfg]["n_recordings"] = _median(cols[0])[1]
            # the check of Section 5
            h = T["2_headline"]["Q"][name][K]["affine"]
            got = st[K]["B20_rho1.0"]
            c = {"headline": {"F": [got["F"], h["F"]["median"]], "gain": [got["gain"], h["gain"]["median"]]}}
            c["headline"]["pass"] = got["F"] == h["F"]["median"] and got["gain"] == h["gain"]["median"]
            ok_all &= c["headline"]["pass"]
            if K in ("K4", "K11"):
                c["thresholds"] = {}
                for cfg in CONFIGS:
                    t4 = T["4_thresholds"][cfg][name][K]
                    p = st[K][cfg]["F"] == t4["F"]["median"] and st[K][cfg]["gain"] == t4["gain"]["median"]
                    c["thresholds"][cfg] = {"F": [st[K][cfg]["F"], t4["F"]["median"]],
                                            "gain": [st[K][cfg]["gain"], t4["gain"]["median"]], "pass": p}
                    ok_all &= p
            chk[K] = c
    res["check_pass"] = bool(ok_all)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps({"n_recordings": res["n_recordings"], "check_pass": res["check_pass"]}))
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
