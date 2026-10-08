"""Directive 001, Sections 6, 7 and 9: aggregate the per-instant files of Stage M.

  python3 scripts/mp_reduce.py RUNDIR RESULTS_DIR [--preflight-dir DIR]

Writes ``per_recording.npz``, ``report.json`` and ``provenance.json`` under
RESULTS_DIR. The unit is the recording: a recording's value of a quantity in a
stratum and setting is the median over its scored instants there, and it enters
only with at least 20 of them. A table entry is the median over recordings with a
95% percentile interval from 2000 bootstrap resamples of recordings (seed
20261008), the number of recordings and the number of instants behind it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import socket
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ec import annotations, motion, mp  # noqa: E402

SETTINGS = ((100_000, 0), (100_000, 33_333), (100_000, 100_000), (100_000, 300_000), (50_000, 0), (200_000, 0))
SETTING_NAMES = ("100,0", "100,33", "100,100", "100,300", "50,0", "200,0")
MODELS = ("static", "label", "cmax")
B_MIN = min(motion.BANDWIDTHS_PX)
MIN_INSTANTS = 20
N_BOOT, SEED = 2000, 20261008
T2_US = 33_333

# per-instant quantities; *_bmin are indicators whose per-recording "median" is replaced by the mean (a share)
QUANTITIES = (["Delta"] + [f"{m}_{q}" for m in MODELS for q in ("gain_bits", "eps", "set_bits", "b_px", "tau_eq_us",
                                                                   "redundancy", "bmin")]
              + ["ref_set_bits", "path_px_label", "speed_label", "cmax_speed", "speed_ratio", "angle_deg",
                 "ratio_in_0.8_1.25"])
SHARE_QUANTITIES = {f"{m}_bmin" for m in MODELS} | {"ratio_in_0.8_1.25"}

GROUPS = ("vehicles", "other", "all")
SPEEDS = ("0-20", "20-100", "100-300", "300-inf", "20-300", "all")
OVERLAPS = ("isolated", "overlapping", "all")


def load_rows(rundir: Path) -> tuple[dict, list[dict]]:
    cols, files = {}, []
    for f in sorted(rundir.glob("instants_*.npz")):
        z = np.load(f)
        h = hashlib.sha256(f.read_bytes()).hexdigest()
        files.append({"path": str(f), "sha256": h, "n_rows": int(len(z["setting"])) if "setting" in z else 0})
        if "setting" not in z:
            continue
        n = len(z["setting"])
        for k in set(cols) | set(z.files):
            if k in z.files:
                v = z[k]
            else:
                v = np.full(n, "" if k in ("recording_id", "lighting", "group", "skip") else np.nan)
            if k not in cols:
                prev = sum(len(c) for c in cols.get("setting", [])) if cols else 0
                cols[k] = [np.full(prev, "" if v.dtype.kind == "U" else np.nan)] if prev else []
            cols[k].append(v)
    return {k: np.concatenate(v) for k, v in cols.items()}, files


def derived(c: dict) -> dict:
    sc = c["skip"] == ""
    q = {}
    q["Delta"] = c["cmax_gain_bits"] - c["static_gain_bits"]
    for m in MODELS:
        for k in ("gain_bits", "eps", "set_bits", "b_px", "tau_eq_us", "redundancy"):
            q[f"{m}_{k}"] = c[f"{m}_{k}"]
        q[f"{m}_bmin"] = np.where(sc, (np.abs(c[f"{m}_b_px"] - B_MIN) < 1e-12).astype(float), np.nan)
    q["ref_set_bits"] = c["cmax_ref_set_bits"]
    q["path_px_label"] = c["path_px_label"]
    q["speed_label"] = c["speed_label"]
    q["cmax_speed"] = c["cmax_speed"]
    with np.errstate(divide="ignore", invalid="ignore"):
        q["speed_ratio"] = c["cmax_speed"] / c["speed_label"]
        cosang = (c["cmax_vx"] * c["v_label_x"] + c["cmax_vy"] * c["v_label_y"]) / (c["cmax_speed"] * c["speed_label"])
    q["angle_deg"] = np.degrees(np.arccos(np.clip(cosang, -1.0, 1.0)))
    q["ratio_in_0.8_1.25"] = np.where(np.isfinite(q["speed_ratio"]),
                                      ((q["speed_ratio"] >= 0.8) & (q["speed_ratio"] <= 1.25)).astype(float), np.nan)
    return q


def stratum_mask(c, group, speed, overlap):
    m = np.ones(len(c["setting"]), dtype=bool)
    if group != "all":
        m &= c["group"] == group
    sb = c["speed_bin"]
    if speed == "20-300":
        m &= (sb == 1) | (sb == 2)
    elif speed != "all":
        m &= sb == SPEEDS.index(speed)
    if overlap == "isolated":
        m &= c["overlap"] == 0
    elif overlap == "overlapping":
        m &= c["overlap"] == 1
    return m


def per_recording(c, q, ids):
    """[recording, setting, stratum, quantity] medians and [recording, setting, stratum] scored-instant counts."""
    strata = [(g, s, o) for g in GROUPS for s in SPEEDS for o in OVERLAPS]
    R, S, K, Q = len(ids), len(SETTINGS), len(strata), len(QUANTITIES)
    val = np.full((R, S, K, Q), np.nan)
    cnt = np.zeros((R, S, K), dtype=np.int64)
    rix = {r: i for i, r in enumerate(ids)}
    sc = c["skip"] == ""
    rec = np.array([rix.get(r, -1) for r in c["recording_id"]])
    smasks = [stratum_mask(c, *st) & sc for st in strata]
    qarr = np.stack([q[k] for k in QUANTITIES], axis=1)
    order = np.lexsort((c["setting"], rec))
    rec_o, set_o = rec[order], c["setting"][order].astype(int)
    keys = rec_o * S + set_o
    cut = np.flatnonzero(np.diff(keys)) + 1
    for a, b in zip(np.concatenate(([0], cut)), np.concatenate((cut, [len(keys)]))):
        ri, si = rec_o[a], set_o[a]
        if ri < 0:
            continue
        idx = order[a:b]
        for k, sm in enumerate(smasks):
            sel = idx[sm[idx]]
            cnt[ri, si, k] = len(sel)
            if len(sel) == 0:
                continue
            block = qarr[sel]
            for j, name in enumerate(QUANTITIES):
                v = block[:, j]
                v = v[np.isfinite(v)]
                if len(v):
                    val[ri, si, k, j] = v.mean() if name in SHARE_QUANTITIES else np.median(v)
    return strata, val, cnt


def boot_entry(vals, counts):
    ok = (counts >= MIN_INSTANTS) & np.isfinite(vals)
    v = vals[ok]
    out = {"median": None, "ci95": [None, None], "n_recordings": int(ok.sum()), "n_instants": int(counts[ok].sum())}
    if len(v) == 0:
        return out
    rng = np.random.default_rng(SEED)
    bs = np.median(v[rng.integers(0, len(v), size=(N_BOOT, len(v)))], axis=1)
    out["median"] = float(np.median(v))
    out["ci95"] = [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rundir")
    ap.add_argument("resdir")
    ap.add_argument("--wall-s", type=float, default=float("nan"))
    ap.add_argument("--workers", default="")
    a = ap.parse_args()
    rundir, resdir = Path(a.rundir), Path(a.resdir)
    resdir.mkdir(parents=True, exist_ok=True)
    ids, _ = mp.load_population()
    c, files = load_rows(rundir)
    q = derived(c)
    sc = c["skip"] == ""
    light = {r: mp.lighting(r) for r in ids}
    is_day = np.array([light[r] == "day" for r in ids])

    # ---------------------------------------------------------------- acceptance 3: scored + skipped = generated
    gen = {}
    for r in ids:
        gen[r] = sum(len(motion.evaluation_instants(tr)) for tr in annotations.tracks(
            annotations.load_boxes(mp.annotation_path(r))))
    acc3_bad = []
    for r in ids:
        m = c["recording_id"] == r
        for si in range(len(SETTINGS)):
            ms = m & (c["setting"] == si)
            n_sc, n_sk = int((ms & sc).sum()), int((ms & ~sc).sum())
            if n_sc + n_sk != gen[r]:
                acc3_bad.append({"recording_id": r, "setting": SETTING_NAMES[si], "scored": n_sc, "skipped": n_sk,
                                 "generated": gen[r]})
    dup = len(c["setting"]) - len(np.unique(np.char.add(np.char.add(c["recording_id"], "|"), np.char.add(
        c["track_id"].astype(int).astype(str), np.char.add("|", np.char.add(c["t_e_us"].astype(int).astype(str),
                                                                            np.char.add("|", c["setting"].astype(int).astype(str))))))))
    acc3 = {"pass": not acc3_bad and dup == 0, "n_generated_instants": int(sum(gen.values())),
            "n_rows": int(len(c["setting"])), "n_scored_rows": int(sc.sum()), "duplicates": int(dup),
            "mismatches": acc3_bad}

    # ---------------------------------------------------------------- acceptance 4: ref_bits and eps
    acc4 = {"pass": True, "by_model": {}}
    want = np.log2(2.0 * c["support_px"] * T2_US)
    for m in MODELS:
        err = np.abs(c[f"{m}_ref_bits"][sc] - want[sc])
        e = c[f"{m}_eps"][sc]
        bad_ref, bad_eps = int((~(err <= 1e-6)).sum()), int((~((e >= 0.001 - 1e-12) & (e <= 1.0))).sum())
        acc4["by_model"][m] = {"max_abs_ref_bits_error": float(err.max()) if len(err) else None,
                               "n_ref_bits_violations": bad_ref, "eps_min": float(e.min()) if len(e) else None,
                               "eps_max": float(e.max()) if len(e) else None, "n_eps_violations": bad_eps}
        acc4["pass"] &= bad_ref == 0 and bad_eps == 0

    # ---------------------------------------------------------------- per recording
    strata, val, cnt = per_recording(c, q, ids)
    sk = {st: k for k, st in enumerate(strata)}
    qi = {n: j for j, n in enumerate(QUANTITIES)}
    np.savez_compressed(resdir / "per_recording.npz", values=val, n_scored_instants=cnt,
                        recording_ids=np.array(ids), lighting=np.array([light[r] for r in ids]),
                        settings=np.array(SETTING_NAMES), strata=np.array(["|".join(s) for s in strata]),
                        quantities=np.array(QUANTITIES),
                        note=np.array("values[r, s, k, j]: median over the scored instants of recording r in "
                                      "setting s and stratum k (group|speed|overlap) of quantity j; *_bmin and "
                                      "ratio_in_0.8_1.25 are shares (means). n_scored_instants[r, s, k]."))

    def entry(setting, stratum, quantity, lighting=None):
        rs = np.ones(len(ids), dtype=bool) if lighting is None else (is_day if lighting == "day" else ~is_day)
        si = SETTING_NAMES.index(setting)
        return boot_entry(val[rs, si, sk[stratum], qi[quantity]], cnt[rs, si, sk[stratum]])

    H = ("vehicles", "20-300", "isolated")
    H_OVL = ("vehicles", "20-300", "overlapping")
    by_light = ("day", "night")
    t1_q = (["Delta"] + [f"{m}_gain_bits" for m in MODELS] + [f"{m}_eps" for m in MODELS]
            + [f"{m}_set_bits" for m in MODELS] + ["ref_set_bits", "cmax_b_px", "cmax_bmin", "cmax_tau_eq_us",
                                                   "cmax_redundancy", "static_redundancy", "path_px_label"])
    lead_q = ["Delta"] + [f"{m}_{k}" for m in ("cmax", "static") for k in
                          ("gain_bits", "eps", "set_bits", "b_px", "bmin", "tau_eq_us", "redundancy")] + \
        ["ref_set_bits", "path_px_label"]
    tables = {}
    tables["1_headline_H_100_0"] = {L: {k: entry("100,0", H, k, L) for k in t1_q} for L in by_light}
    tables["2_lead_H_T1_100"] = {s: {L: {k: entry(s, H, k, L) for k in lead_q} for L in by_light}
                                 for s in ("100,0", "100,33", "100,100", "100,300")}
    tables["3_template_length_H_D0"] = {s: {L: {k: entry(s, H, k, L) for k in lead_q} for L in by_light + (None,)}
                                        for s in ("50,0", "100,0", "200,0")}
    for s in tables["3_template_length_H_D0"]:
        tables["3_template_length_H_D0"][s]["pooled"] = tables["3_template_length_H_D0"][s].pop(None)
    tables["4_speed_class_isolated_100_0"] = {
        f"{g}|{sp}": {L: {k: entry("100,0", (g, sp, "isolated"), k, L) for k in ("Delta", "cmax_gain_bits", "cmax_eps")}
                      for L in by_light}
        for g in ("vehicles", "other") for sp in ("0-20", "20-100", "100-300", "300-inf")}
    tables["5_overlap_100_0"] = {name: {L: {k: entry("100,0", st, k, L) for k in t1_q} for L in by_light}
                                 for name, st in (("H_isolated", H), ("H_overlapping", H_OVL))}
    # Table 6: velocity agreement, pooled instants and per-recording
    m6 = sc & (c["setting"] == 0) & stratum_mask(c, *H)
    t6 = {}
    for L in by_light:
        mm = m6 & (c["lighting"] == L)
        r, ang = q["speed_ratio"][mm], q["angle_deg"][mm]
        r, ang = r[np.isfinite(r)], ang[np.isfinite(ang)]
        qs = (0.05, 0.25, 0.5, 0.75, 0.95)
        t6[L] = {"n_instants": int(mm.sum()),
                 "speed_ratio_quantiles": {str(x): float(np.quantile(r, x)) for x in qs} if len(r) else None,
                 "angle_deg_quantiles": {str(x): float(np.quantile(ang, x)) for x in qs} if len(ang) else None,
                 "pooled_share_ratio_in_0.8_1.25": float(((r >= 0.8) & (r <= 1.25)).mean()) if len(r) else None,
                 "pooled_share_angle_under_15deg": float((ang < 15).mean()) if len(ang) else None,
                 "per_recording_share_ratio_in_0.8_1.25": entry("100,0", H, "ratio_in_0.8_1.25", L),
                 "per_recording_median_speed_ratio": entry("100,0", H, "speed_ratio", L),
                 "per_recording_median_angle_deg": entry("100,0", H, "angle_deg", L)}
    tables["6_velocity_H_100_0"] = t6
    # Table 7: skips by reason, lighting, class group, per setting; share of in-box events in scored instants
    t7 = {}
    for si, sname in enumerate(SETTING_NAMES):
        ms = c["setting"] == si
        d = {}
        for L in by_light:
            for g in ("vehicles", "other"):
                mm = ms & (c["lighting"] == L) & (c["group"] == g)
                reasons, counts = np.unique(c["skip"][mm], return_counts=True)
                ib = c["inbox_future_events"][mm]
                d[f"{L}|{g}"] = {"generated": int(mm.sum()),
                                 "counts": {("scored" if k == "" else str(k)): int(n) for k, n in zip(reasons, counts)},
                                 "inbox_future_events_total": int(np.nansum(ib)),
                                 "share_inbox_events_in_scored_instants":
                                     float(np.nansum(ib[c["skip"][mm] == ""]) / max(1.0, np.nansum(ib)))}
        t7[sname] = d
    tables["7_skips"] = {"definition": "share = in-box events (inside the track's interpolated box dilated by "
                                       "margin_px) of the future windows of scored instants, over the same for all "
                                       "generated instants", "by_setting": t7}

    # ---------------------------------------------------------------- acceptance 5 and the decision rule
    acc5 = {}
    for L in by_light + (None,):
        a0, a3 = entry("100,0", H, "static_gain_bits", L)["median"], entry("100,300", H, "static_gain_bits", L)["median"]
        acc5[L or "pooled"] = {"static_gain_100_0": a0, "static_gain_100_300": a3,
                               "below": None if a0 is None or a3 is None else a3 < a0}
    acc5["pass"] = all(v["below"] for k, v in acc5.items() if k in ("day", "night", "pooled"))
    dd = tables["1_headline_H_100_0"]["day"]["Delta"]["median"]
    dn = tables["1_headline_H_100_0"]["night"]["Delta"]["median"]
    if dd is None or dn is None:
        decision = "UNDEFINED"
    elif dd >= 3 and dn >= 3:
        decision = "GO"
    elif dd < 1 and dn < 1:
        decision = "NO-GO"
    else:
        decision = "INTERMEDIATE"
    report = {"directive": "001", "decision_rule": {"Delta_day": dd, "Delta_night": dn, "outcome": decision},
              "acceptance": {"3_scored_plus_skipped_equals_generated": acc3, "4_ref_bits_and_eps": acc4,
                             "5_static_gain_falls_with_lead": acc5},
              "aggregation": {"unit": "recording", "min_instants": MIN_INSTANTS, "n_boot": N_BOOT, "seed": SEED,
                              "Delta": "per instant gain(cmax) - gain(static), then the median over the recording's "
                                       "instants", "shares": sorted(SHARE_QUANTITIES),
                              "H": "vehicles, isolated, speed_label in [20, 300) px/s, setting (100, 0)"},
              "tables": tables}
    (resdir / "report.json").write_text(json.dumps(report, indent=1, allow_nan=False, default=float) + "\n")
    prov = {"directive": "001", "host": socket.gethostname(),
            "commit": json.loads((rundir / "plan.json").read_text())["commit"],
            "implementation": "reference ec.motion.evaluate_instant, unchanged",
            "versions": json.loads((Path(rundir).parent / "preflight" / "env.json").read_text()),
            "wall_s": a.wall_s, "workers": a.workers,
            "cpu_s_evaluate_instant": float(np.nansum(c["elapsed_s"])),
            "per_instant_files": files}
    tasks = [json.loads(f.read_text()) for f in sorted(rundir.glob("task_*.json"))]
    prov["cpu_s_tasks_wall_sum"] = float(sum(t["wall_s"] for t in tasks))
    prov["n_tasks"] = len(tasks)
    (resdir / "provenance.json").write_text(json.dumps(prov, indent=1) + "\n")
    print(json.dumps({"decision": report["decision_rule"], "acc3": acc3["pass"], "acc4": acc4["pass"],
                      "acc5": acc5}, indent=1, default=float))


if __name__ == "__main__":
    main()
