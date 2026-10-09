"""Directive 003, Sections 6 to 10: aggregate Stages C and S.

  python3 scripts/gp_reduce.py GPDIR RESULTS_DIR [--wall-s S] [--workers TEXT]

Writes per_recording.npz, share.json, report.json and provenance.json. Groups are
formed per instant with ``ec.gop.group_summary`` and then aggregated: a
recording's value is the median over its instants in the stratum (shares are
means), it enters with at least 20 instants that have the quantity, and a table
entry is the median over recordings with a 95% percentile interval from 2000
bootstrap resamples of recordings (seed 20261010).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import socket
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ec import gop, mp, regen  # noqa: E402
import gp_run as GR  # noqa: E402

N_BOOT, SEED, MIN_N = 2000, 20261010, 20
RG_R = Path.home() / "prjs" / "event_coding" / "rg" / "R"
KS = (2, 4, 8, 11)
G_MODELS = ("aligned", "cmax", "static")
T_MODELS = ("aligned", "cmax", "static", "uniform")
CELLS = [(s, k) for s in regen.BLOCKS_PX for k in regen.TIME_BINS]
HC, FC = "s2_k3", "s2_k1"
GROUPS = ("vehicles", "other", "all")
SPEEDS = ("0-20", "20-100", "100-300", "300-inf", "20-300", "all")
OVERLAPS = ("isolated", "overlapping", "all")
H = ("vehicles", "20-300", "isolated")
M_TO_SETTING = {1: 0, 2: 1, 4: 2, 10: 3}
CMP_PREFIX = ("static_", "cmax_", "label_", "uniform_")
CMP_EXTRA = ("n_source", "n_future", "support_px")


def load(dirpath: Path, pattern="rows_*.npz"):
    parts, files = [], []
    for f in sorted(dirpath.glob(pattern)):
        z = dict(np.load(f))
        files.append({"path": str(f), "sha256": hashlib.sha256(f.read_bytes()).hexdigest(),
                      "n_rows": int(len(z["target"])) if "target" in z else int(len(z.get("setting", [])))})
        if "setting" in z:
            parts.append(z)
    keys = sorted({k for z in parts for k in z})
    kinds = {k: next(z[k].dtype.kind for z in parts if k in z) for k in keys}
    return {k: np.concatenate([z[k] if k in z else np.full(len(z["setting"]), "" if kinds[k] == "U" else np.nan)
                               for z in parts]) for k in keys}, files


def keystr(rid, tid, te, extra=None):
    k = np.char.add(np.char.add(rid.astype(str), "|"), np.char.add(np.asarray(tid).astype(np.int64).astype(str),
                                                                    np.char.add("|", np.asarray(te).astype(np.int64).astype(str))))
    if extra is not None:
        k = np.char.add(np.char.add(k, "|"), np.asarray(extra).astype(np.int64).astype(str))
    return k


def same(a, b):
    if a.dtype.kind in "US" or b.dtype.kind in "US":
        return a.astype(str) == b.astype(str)
    a = a.astype(np.float64); b = b.astype(np.float64)
    return (a == b) | (np.isnan(a) & np.isnan(b))


def boot(vals, counts):
    ok = (counts >= MIN_N) & np.isfinite(vals)
    v = vals[ok]
    out = {"median": None, "ci95": [None, None], "n_recordings": int(ok.sum()), "n_instants": int(counts[ok].sum())}
    if len(v):
        bs = np.median(v[np.random.default_rng(SEED).integers(0, len(v), size=(N_BOOT, len(v)))], axis=1)
        out.update(median=float(np.median(v)), ci95=[float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))])
    return out


def smask(st, group, speed, overlap):
    m = np.ones(len(st["group"]), dtype=bool)
    if group != "all":
        m &= st["group"] == group
    if speed == "20-300":
        m &= (st["speed_bin"] == 1) | (st["speed_bin"] == 2)
    elif speed != "all":
        m &= st["speed_bin"] == SPEEDS.index(speed)
    if overlap == "isolated":
        m &= st["overlap"] == 0
    elif overlap == "overlapping":
        m &= st["overlap"] == 1
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("gpdir"); ap.add_argument("resdir")
    ap.add_argument("--wall-s", type=float, default=float("nan"))
    ap.add_argument("--workers", default="")
    a = ap.parse_args()
    gp, res = Path(a.gpdir), Path(a.resdir)
    res.mkdir(parents=True, exist_ok=True)
    ids, _ = mp.load_population()
    light = {r: mp.lighting(r) for r in ids}
    is_day = np.array([light[r] == "day" for r in ids])
    rsel = lambda L: np.ones(len(ids), bool) if L is None else (is_day if L == "day" else ~is_day)
    LB = ("day", "night")

    c, files = load(gp / "C")
    sc = c["skip"] == ""
    tgt = c["target"].astype(int)

    # ============================================================== acceptance 3: ten rows per instant
    expected = {}
    for t in GR.mp_plan():
        z = GR.mp_rows(t[0], t[1])
        for i in GR.c_instants(z):
            expected[(t[0], int(z["track_id"][i]), int(z["t_e_us"][i]))] = 0
    ik = keystr(c["recording_id"], c["track_id"], c["t_e_us"])
    inst_keys, inv, counts = np.unique(ik, return_inverse=True, return_counts=True)
    per_target = {}
    for kk, m in zip(inv, tgt):
        per_target.setdefault(kk, set()).add(m)
    full = [i for i in range(len(inst_keys)) if counts[i] == 10 and per_target[i] == set(range(1, 11))]
    allowed = {"", "source_too_small", "future_too_small", "outside_track_life", "support_outside_sensor"}
    exp_keys = {f"{r}|{tid}|{te}" for (r, tid, te) in expected}
    acc3 = {"n_instants_expected": len(expected), "n_instants": int(len(inst_keys)), "n_rows": int(len(tgt)),
            "n_instants_with_ten_targets": len(full), "missing_instants": len(exp_keys - set(inst_keys.tolist())),
            "extra_instants": len(set(inst_keys.tolist()) - exp_keys),
            "unknown_skip_reasons": sorted(set(c["skip"]) - allowed), "n_scored_rows": int(sc.sum())}
    acc3["pass"] = (acc3["n_instants"] == acc3["n_instants_expected"] == acc3["n_instants_with_ten_targets"]
                    and acc3["n_rows"] == 10 * acc3["n_instants"] and not acc3["missing_instants"]
                    and not acc3["extra_instants"] and not acc3["unknown_skip_reasons"])

    # ============================================================== acceptance 4: equal to directive 002
    r2, _ = load(RG_R)
    cols = sorted(k for k in r2 if k.startswith(CMP_PREFIX)) + list(CMP_EXTRA) + ["skip"]
    k2 = keystr(r2["recording_id"], r2["track_id"], r2["t_e_us"], r2["setting"])
    o2 = np.argsort(k2); k2s = k2[o2]
    acc4 = {"columns_compared": len(cols), "by_target": {}}
    ok4 = True
    for m, s in M_TO_SETTING.items():
        sel = np.flatnonzero(tgt == m)
        kc = keystr(c["recording_id"][sel], c["track_id"][sel], c["t_e_us"][sel], np.full(len(sel), s))
        pos = np.searchsorted(k2s, kc)
        pos = np.minimum(pos, len(k2s) - 1)
        found = k2s[pos] == kc
        j2 = o2[pos[found]]; j3 = sel[found]
        bad_rows = np.zeros(len(j3), dtype=bool)
        bad_cols = {}
        for col in cols:
            if col not in c:
                bad_cols[col] = "missing in 003 rows"
                bad_rows[:] = True
                continue
            eq = same(c[col][j3], r2[col][j2])
            if col != "skip":                    # model outputs exist on scored rows only
                eq |= c["skip"][j3] != ""
            n = int((~eq).sum())
            if n:
                bad_cols[col] = n
                bad_rows |= ~eq
        acc4["by_target"][str(m)] = {"lead_ms": [0, 33, 100, 300][list(M_TO_SETTING).index(m)],
                                     "n_rows": int(len(sel)), "n_with_002_row": int(found.sum()),
                                     "n_without_002_row": int((~found).sum()),
                                     "n_rows_mismatch": int(bad_rows.sum()), "mismatched_columns": bad_cols}
        ok4 &= not bad_rows.any()
    acc4["note"] = ("rows are matched on (recording, track_id, t_e, setting); an instant that directive 001 did not "
                    "score at the lead's setting has no row in directive 002 and is counted as without a 002 row. "
                    "Model outputs are compared on scored rows; the skip reason on every matched row")
    acc4["pass"] = bool(ok4)

    # ============================================================== acceptance 5 and 6
    f_al = {ce: c[f"aligned_f1_s{ce[0]}_k{ce[1]}"] for ce in CELLS}
    acc5 = {"n_scored_rows": int(sc.sum()),
            "n_aligned_below_start_s2_k3": int((f_al[(2, 3)][sc] < c["start_f1_s2_k3"][sc]).sum())}
    diff = np.zeros(int(sc.sum()), dtype=bool)
    for col in ["n_pred"] + [f"f1_s{s}_k{k}" for s, k in CELLS]:
        diff |= ~same(c[f"start_{col}"][sc], c[f"cmax_{col}"][sc])
    acc5["n_rows_start_differs_from_cmax"] = int(diff.sum())
    acc5["pass"] = acc5["n_aligned_below_start_s2_k3"] == 0
    out_rng = int(sum(((v[sc] < 0) | (v[sc] > 1) | ~np.isfinite(v[sc])).sum() for v in f_al.values()))
    viol = 0
    for k in regen.TIME_BINS:
        viol += int((f_al[(2, k)][sc] < f_al[(1, k)][sc]).sum() + (f_al[(4, k)][sc] < f_al[(2, k)][sc]).sum())
    for s in regen.BLOCKS_PX:
        viol += int((f_al[(s, 8)][sc] < f_al[(s, 32)][sc]).sum() + (f_al[(s, 1)][sc] < f_al[(s, 8)][sc]).sum()
                    + (f_al[(s, 1)][sc] < f_al[(s, 3)][sc]).sum())
    acc6 = {"f1_outside_0_1": out_rng, "monotonicity_violations": viol, "pass": out_rng == 0 and viol == 0}

    # ============================================================== per-instant arrays (instant x target)
    n_i = len(inst_keys)
    A = lambda col, fill=np.nan: _grid(c[col], inv, tgt, n_i, fill)
    skipped = _grid((~sc).astype(float), inv, tgt, n_i, 1.0) > 0
    n_true = A("n_future")
    n_key = A("n_source")[:, 0]
    first = np.zeros(n_i, dtype=np.int64)
    first[inv[tgt == 1]] = np.flatnonzero(tgt == 1)
    st = {k: c[k][first] for k in ("recording_id", "lighting", "group", "speed_bin", "overlap", "track_id", "t_e_us")}

    q, shares = {}, set()
    groups_missing = {}
    acc7_bad_share, acc7_bad_gamma, acc7_n = 0, 0, 0
    for K in KS:
        has = ~skipped[:, :K - 1].any(axis=1)
        groups_missing[str(K)] = int((~has).sum())
        phi = np.full(n_i, np.nan)
        thin = np.full(n_i, np.nan)
        for model in G_MODELS:
            cells = [HC, FC] if model != "aligned" or K != 4 else [f"s{s}_k{k}" for s, k in CELLS]
            n_pred = A(f"{model}_n_pred")
            for cell in cells:
                f1 = A(f"{model}_f1_{cell}")
                g = np.full(n_i, np.nan); F = np.full(n_i, np.nan)
                for i in np.flatnonzero(has):
                    r = gop.group_summary(int(n_key[i]), n_pred[i, :K - 1], n_true[i, :K - 1], f1[i, :K - 1])
                    g[i], F[i], phi[i] = r["gamma"], r["fidelity"], r["share"]
                q[f"gamma_{model}_K{K}_{cell}"] = g
                q[f"fidelity_{model}_K{K}_{cell}"] = F
        for i in np.flatnonzero(has):           # acceptance 7, once per group
            acc7_n += 1
            if not (0.0 < phi[i] <= 1.0):
                acc7_bad_share += 1
            z0 = gop.group_summary(int(n_key[i]), np.zeros(K - 1), n_true[i, :K - 1], np.zeros(K - 1))
            if abs(z0["gamma"] - 1.0) > 1e-12:
                acc7_bad_gamma += 1
        thin = 2.0 * phi / (1.0 + phi)
        q[f"share_K{K}"] = phi
        q[f"thin_fidelity_K{K}"] = thin
        kb = A("key_bits")[:, 0]
        tb = A("true_bits")
        NK = n_key + n_true[:, :K - 1].sum(axis=1)
        q[f"b_direct_K{K}"] = np.where(has, (kb + tb[:, :K - 1].sum(axis=1)) / NK, np.nan)
        q[f"b_aligned_K{K}"] = np.where(has, (kb + gop.MOTION_BITS * (K - 1)) / NK, np.nan)
    acc7 = {"n_groups": acc7_n, "n_share_outside_0_1": acc7_bad_share, "n_zero_pred_gamma_not_1": acc7_bad_gamma,
            "zero_pred_group": "group_summary(n_key, n_pred = 0, n_true, f1 = 0)",
            "pass": acc7_bad_share == 0 and acc7_bad_gamma == 0}
    sc1 = ~skipped[:, 0]
    q["key_bits_per_event"] = np.where(sc1, A("key_bits")[:, 0] / n_key, np.nan)
    for qq in gop.THIN_SHARES:
        q[f"b_thin_q{qq}"] = np.where(sc1, A(f"thin_bits_q{qq}")[:, 0] / n_true[:, 0], np.nan)
    for m in range(1, 11):
        ok = ~skipped[:, m - 1]
        for model in T_MODELS:
            for cell in (HC, FC):
                q[f"F1_{model}_m{m}_{cell}"] = np.where(ok, A(f"{model}_f1_{cell}")[:, m - 1], np.nan)
        dx = A("aligned_dx")[:, m - 1] - A("start_dx")[:, m - 1]
        dy = A("aligned_dy")[:, m - 1] - A("start_dy")[:, m - 1]
        q[f"disp_dist_px_m{m}"] = np.where(ok, np.hypot(dx, dy), np.nan)
        q[f"disp_differs_m{m}"] = np.where(ok, ((dx != 0) | (dy != 0)).astype(float), np.nan)
        shares.add(f"disp_differs_m{m}")
    names = list(q)
    qa = np.stack([q[n] for n in names], axis=1)

    # per recording, per stratum
    strata = [(g, s, o) for g in GROUPS for s in SPEEDS for o in OVERLAPS]
    sk = {s_: i for i, s_ in enumerate(strata)}
    rix = {r: i for i, r in enumerate(ids)}
    rec = np.array([rix[r] for r in st["recording_id"]])
    val = np.full((len(ids), len(strata), len(names)), np.nan)
    cnt = np.zeros((len(ids), len(strata), len(names)), dtype=np.int64)
    is_share = np.array([n in shares for n in names])
    smasks = [smask(st, *s_) for s_ in strata]
    for ri in range(len(ids)):
        rm = rec == ri
        if not rm.any():
            continue
        for k, smk in enumerate(smasks):
            block = qa[rm & smk]
            if len(block) == 0:
                continue
            fin = np.isfinite(block)
            cnt[ri, k] = fin.sum(axis=0)
            with np.errstate(all="ignore"):
                med = np.nanmedian(np.where(fin, block, np.nan), axis=0) if fin.any() else np.full(len(names), np.nan)
                mean = np.nanmean(np.where(fin, block, np.nan), axis=0) if fin.any() else np.full(len(names), np.nan)
            val[ri, k] = np.where(is_share, mean, med)
    np.savez_compressed(res / "per_recording.npz", values=val, n_instants=cnt, recording_ids=np.array(ids),
                        lighting=np.array([light[r] for r in ids]), strata=np.array(["|".join(s_) for s_ in strata]),
                        quantities=np.array(names),
                        note=np.array("Stage C. values[r, stratum, quantity]: median over the instants of recording "
                                      "r in the stratum (group|speed|overlap) that have the quantity; "
                                      "disp_differs_m* are shares (means). n_instants[r, stratum, quantity]."))
    qi = {n: j for j, n in enumerate(names)}
    E = lambda s_, n, L: boot(val[rsel(L), sk[s_], qi[n]], cnt[rsel(L), sk[s_], qi[n]])

    T = {}
    t1 = {}
    for cell, cname in ((HC, "headline"), (FC, "frame")):
        t1[cname] = {L: {f"K{K}": {"share": E(H, f"share_K{K}", L),
                                   "thin_fidelity_at_share": E(H, f"thin_fidelity_K{K}", L),
                                   **{f"{m}_{w}": E(H, f"{w}_{m}_K{K}_{cell}", L) for m in G_MODELS
                                      for w in ("fidelity", "gamma")}} for K in KS} for L in LB}
    T["1_headline_H"] = t1
    T["2_targets_H"] = {f"m{m}": {L: {**{f"F1_{mo}_{cell}": E(H, f"F1_{mo}_m{m}_{cell}", L)
                                         for mo in T_MODELS for cell in (HC, FC)},
                                      "disp_distance_px": E(H, f"disp_dist_px_m{m}", L),
                                      "share_disp_differs": E(H, f"disp_differs_m{m}", L)} for L in LB}
                        for m in range(1, 11)}
    T["3_grid_aligned_K4_H"] = {L: {f"s{s}_k{k}": E(H, f"gamma_aligned_K4_s{s}_k{k}", L) for s, k in CELLS} for L in LB}
    T["4_speed_class_isolated"] = {
        f"{g}|{sp}": {L: {f"{w}_{mo}_K{K}": E((g, sp, "isolated"), f"{w}_{mo}_K{K}_{HC}", L)
                          for K in (4, 11) for mo in ("aligned", "static") for w in ("gamma", "fidelity")} for L in LB}
        for g in ("vehicles", "other") for sp in ("0-20", "20-100", "100-300", "300-inf")}
    T["5_bits_H"] = {L: {**{f"K{K}": {"b_direct": E(H, f"b_direct_K{K}", L), "b_aligned": E(H, f"b_aligned_K{K}", L),
                                     "fidelity_aligned": E(H, f"fidelity_aligned_K{K}_{HC}", L),
                                     "share": E(H, f"share_K{K}", L)} for K in KS},
                         **{f"thin_q{qq}": {"b_thin": E(H, f"b_thin_q{qq}", L), "fidelity": 2 * qq / (1 + qq)}
                            for qq in gop.THIN_SHARES},
                         "key_bits_per_event": E(H, "key_bits_per_event", L)} for L in LB}
    # Table 7
    t7 = {"skips_by_reason_and_target": {}, "groups_without_full_targets_by_K": groups_missing}
    for m in range(1, 11):
        mm = tgt == m
        r_, n_ = np.unique(c["skip"][mm], return_counts=True)
        t7["skips_by_reason_and_target"][str(m)] = {("scored" if k == "" else str(k)): int(v) for k, v in zip(r_, n_)}
    ne = c["aligned_n_eval"][sc]
    qs = (0.0, 0.05, 0.25, 0.5, 0.75, 0.95, 1.0)
    t7["aligned_n_eval"] = {"pooled_quantiles": {str(x): float(np.quantile(ne, x)) for x in qs},
                            "mean": float(ne.mean()), "values": {str(int(v)): int(n) for v, n in
                                                                 zip(*np.unique(ne, return_counts=True))}}
    T["7_skips_and_search"] = t7

    # ============================================================== Stage S
    sh = [json.loads(f.read_text()) for f in sorted((gp / "C").glob("share_*.json"))]
    per = {}
    for s_ in sh:
        pix = s_["windows"] * s_["sensor_pixels"]
        per[s_["recording_id"]] = s_ | {
            **{f"event_share_{k}": s_[f"events_{k}"] / s_["events"] if s_["events"] else None for k in "ALV"},
            **{f"pixel_share_{k}": s_[f"pixels_{k}"] / pix if pix else None for k in "ALV"},
            "event_share_empty_A_windows": s_["events_empty_A"] / s_["events"] if s_["events"] else None}
    t6 = {}
    for L in LB:
        rs = [p for r, p in per.items() if light[r] == L]
        d = {"n_recordings": len(rs), "n_windows": int(sum(p["windows"] for p in rs))}
        for name in [f"event_share_{k}" for k in "ALV"] + [f"pixel_share_{k}" for k in "ALV"] + ["event_share_empty_A_windows"]:
            v = np.array([p[name] for p in rs if p[name] is not None], dtype=float)
            bs = np.median(v[np.random.default_rng(SEED).integers(0, len(v), size=(N_BOOT, len(v)))], axis=1)
            d[name] = {"median_over_recordings": float(np.median(v)),
                       "ci95": [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]}
        ev = sum(p["events"] for p in rs); px = sum(p["windows"] * p["sensor_pixels"] for p in rs)
        for k in "ALV":
            d[f"event_share_{k}"]["pooled"] = sum(p[f"events_{k}"] for p in rs) / ev
            d[f"pixel_share_{k}"]["pooled"] = sum(p[f"pixels_{k}"] for p in rs) / px
        d["event_share_empty_A_windows"]["pooled"] = sum(p["events_empty_A"] for p in rs) / ev
        d["share_of_windows_with_empty_A"] = sum(p["windows_empty_A"] for p in rs) / d["n_windows"]
        t6[L] = d
    share = {"directive": "003", "stage": "S", "n_recordings": len(per),
             "definition": "windows [j s, j s + 33,333 us) inside [first event, last event]; boxes at j s + 16,666 us "
                           "of the tracks alive then, dilated by 2 px, pixels ceil(x - 2) .. floor(x + w + 2), "
                           "clipped; A all alive tracks, L tracks living >= 1 s, V vehicle tracks living >= 1 s",
             "table_6": t6, "per_recording": per}
    (res / "share.json").write_text(json.dumps(share, indent=1) + "\n")
    T["6_stage_S"] = {"see": "share.json#/table_6", **t6}

    # ============================================================== decision rule
    g = {L: {f"K{K}": T["1_headline_H"]["headline"][L][f"K{K}"]["aligned_gamma"]["median"] for K in KS} for L in LB}
    if any(v is None for L in LB for v in g[L].values()):
        outcome = "UNDEFINED"
    elif g["day"]["K4"] >= 2.0 and g["night"]["K4"] >= 2.0:
        outcome = "GO"
    elif all(v < 1.3 for L in LB for v in g[L].values()):
        outcome = "NO-GO"
    else:
        outcome = "INTERMEDIATE"
    report = {"directive": "003", "decision_rule": {"gamma_aligned_headline_H": g, "outcome": outcome},
              "acceptance": {"3_ten_rows_per_instant": acc3, "4_equal_to_002": acc4, "5_aligned_not_below_start": acc5,
                             "6_aligned_f1_range_and_monotone": acc6, "7_groups": acc7},
              "aggregation": {"unit": "recording", "min_instants": MIN_N, "n_boot": N_BOOT, "seed": SEED,
                              "group_quantities": "formed per instant with ec.gop.group_summary, then aggregated",
                              "H": "vehicles, isolated, speed_label in [20, 300) px/s, setting (100, 0)",
                              "headline_cell": HC, "frame_cell": FC},
              "tables": T}
    (res / "report.json").write_text(json.dumps(report, indent=1, allow_nan=False) + "\n")
    tasks = [json.loads(f.read_text()) for f in sorted((gp / "C").glob("task_*.json"))]
    prov = {"directive": "003", "host": socket.gethostname(),
            "commit": json.loads((gp / "C" / "plan.json").read_text())["commit"],
            "implementation": "reference ec.gop.evaluate_target and ec.gop.group_summary, unchanged",
            "versions": json.loads((gp / "preflight_p12.json").read_text())["P1"], "workers": a.workers,
            "wall_s": a.wall_s, "cpu_h": {"tasks_wall_sum": sum(t["wall_s"] for t in tasks) / 3600,
                                          "evaluate_target": float(np.nansum(c["elapsed_s"])) / 3600,
                                          "stage_S": sum(t["stage_s_s"] for t in tasks) / 3600,
                                          "reads_incl_slot_wait": sum(t["read_s"] for t in tasks) / 3600},
            "per_row_files": files,
            "share_files": [{"path": str(f), "sha256": hashlib.sha256(f.read_bytes()).hexdigest()}
                            for f in sorted((gp / "C").glob("share_*.json"))]}
    (res / "provenance.json").write_text(json.dumps(prov, indent=1) + "\n")
    print(json.dumps({"decision": report["decision_rule"], "acc": {k: v["pass"] for k, v in report["acceptance"].items()},
                      "cpu_h": prov["cpu_h"]}, indent=1))


def _grid(col, inv, tgt, n_i, fill):
    g = np.full((n_i, 10), fill, dtype=np.float64)
    g[inv, tgt - 1] = col.astype(np.float64)
    return g


if __name__ == "__main__":
    main()
