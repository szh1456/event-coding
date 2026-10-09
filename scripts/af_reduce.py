"""Directive 004, Sections 6, 7, 9 and 10: aggregate Stage A.

  python3 scripts/af_reduce.py AFDIR RESULTS_DIR [--wall-s S] [--workers TEXT]

Writes per_recording.npz, report.json and provenance.json. Groups are formed per
instant with ``ec.gop.group_summary`` for ``affine`` (this stage) and ``aligned``
(the rows of directive 003, copied into each row as ``gp_*``); ratios and
differences between the two are formed per instant and then aggregated. A
recording's value is the median over its instants in the stratum (shares are
means); it enters with at least 20 instants that have the quantity; a table entry
is the median over recordings with a 95% interval from 2000 bootstrap resamples of
recordings (seed 20261011).
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
from ec import affine, gop, mp, regen  # noqa: E402
from gp_reduce import _grid, keystr, same, smask  # noqa: E402

N_BOOT, SEED, MIN_N = 2000, 20261011, 20
GP_C = Path.home() / "prjs" / "event_coding" / "gp" / "C"
KS = (2, 4, 8, 11)
CELLS = [(s, k) for s in regen.BLOCKS_PX for k in regen.TIME_BINS]
HC, FC = "s2_k3", "s2_k1"
GROUPS = ("vehicles", "other", "all")
SPEEDS = ("0-20", "20-100", "100-300", "300-inf", "20-300", "all")
OVERLAPS = ("isolated", "overlapping", "all")
GROWTHS = ("all", "growing", "steady", "shrinking")
LB = ("day", "night")


def load(dirpath: Path):
    parts, files = [], []
    for f in sorted(dirpath.glob("rows_*.npz")):
        z = dict(np.load(f))
        files.append({"path": str(f), "sha256": hashlib.sha256(f.read_bytes()).hexdigest(),
                      "n_rows": int(len(z["target"])) if "target" in z else 0})
        if "target" in z:
            parts.append(z)
    keys = sorted({k for z in parts for k in z})
    kinds = {k: next(z[k].dtype.kind for z in parts if k in z) for k in keys}
    return {k: np.concatenate([z[k] if k in z else np.full(len(z["target"]), "" if kinds[k] == "U" else np.nan)
                               for z in parts]) for k in keys}, files


def boot(vals, counts):
    ok = (counts >= MIN_N) & np.isfinite(vals)
    v = vals[ok]
    out = {"median": None, "ci95": [None, None], "n_recordings": int(ok.sum()), "n_instants": int(counts[ok].sum())}
    if len(v):
        bs = np.median(v[np.random.default_rng(SEED).integers(0, len(v), size=(N_BOOT, len(v)))], axis=1)
        out.update(median=float(np.median(v)), ci95=[float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("afdir"); ap.add_argument("resdir")
    ap.add_argument("--wall-s", type=float, default=float("nan"))
    ap.add_argument("--workers", default="")
    a = ap.parse_args()
    af, res = Path(a.afdir), Path(a.resdir)
    res.mkdir(parents=True, exist_ok=True)
    ids, _ = mp.load_population()
    light = {r: mp.lighting(r) for r in ids}
    is_day = np.array([light[r] == "day" for r in ids])
    rsel = lambda L: np.ones(len(ids), bool) if L is None else (is_day if L == "day" else ~is_day)

    c, files = load(af / "A")
    sc = c["skip"] == ""
    tgt = c["target"].astype(int)

    # ============================================================== acceptance 3
    exp = []
    for f in sorted(GP_C.glob("rows_*.npz")):
        z = np.load(f)
        if "target" in z:
            exp.append(keystr(z["recording_id"], z["track_id"], z["t_e_us"], z["target"]))
    exp = np.concatenate(exp)
    got = keystr(c["recording_id"], c["track_id"], c["t_e_us"], c["target"])
    acc3 = {"n_rows_003": int(len(exp)), "n_rows": int(len(got)), "n_unique": int(len(np.unique(got))),
            "missing": int(len(np.setdiff1d(exp, got))), "extra": int(len(np.setdiff1d(got, exp))),
            "n_skip_reason_differs_from_003": int((c["skip"] != c["gp_skip"]).sum()), "n_scored": int(sc.sum()),
            "skips": {k: int(v) for k, v in zip(*np.unique(c["skip"][~sc], return_counts=True))}}
    acc3["pass"] = (acc3["n_rows"] == acc3["n_unique"] == acc3["n_rows_003"] and not acc3["missing"]
                    and not acc3["extra"] and acc3["n_skip_reason_differs_from_003"] == 0)

    # ============================================================== acceptance 4, 5, 6
    pairs = [("n_source", "gp_n_source"), ("n_future", "gp_n_future"), ("translation_n_pred", "gp_aligned_n_pred")]
    pairs += [(f"translation_f1_s{s}_k{k}", f"gp_aligned_f1_s{s}_k{k}") for s, k in CELLS]
    bad4 = {x: int((~same(c[x][sc], c[y][sc])).sum()) for x, y in pairs}
    acc4 = {"n_scored": int(sc.sum()), "columns_compared": len(pairs),
            "mismatches": {k: v for k, v in bad4.items() if v}, "pass": not any(bad4.values())}
    acc5 = {"n_scored": int(sc.sum()),
            "n_affine_below_translation_s2_k3": int((c["affine_f1_s2_k3"][sc] < c["translation_f1_s2_k3"][sc]).sum())}
    acc5["pass"] = acc5["n_affine_below_translation_s2_k3"] == 0
    f_af = {ce: c[f"affine_f1_s{ce[0]}_k{ce[1]}"][sc] for ce in CELLS}
    out_rng = int(sum(((v < 0) | (v > 1) | ~np.isfinite(v)).sum() for v in f_af.values()))
    viol = 0
    for k in regen.TIME_BINS:
        viol += int((f_af[(2, k)] < f_af[(1, k)]).sum() + (f_af[(4, k)] < f_af[(2, k)]).sum())
    for s in regen.BLOCKS_PX:
        viol += int((f_af[(s, 8)] < f_af[(s, 32)]).sum() + (f_af[(s, 1)] < f_af[(s, 8)]).sum()
                    + (f_af[(s, 1)] < f_af[(s, 3)]).sum())
    acc6 = {"f1_outside_0_1": out_rng, "monotonicity_violations": viol, "pass": out_rng == 0 and viol == 0}

    # ============================================================== per instant
    ik = keystr(c["recording_id"], c["track_id"], c["t_e_us"])
    inst_keys, inv = np.unique(ik, return_inverse=True)
    n_i = len(inst_keys)
    A = lambda col: _grid(c[col], inv, tgt, n_i, np.nan)
    skipped = _grid((~sc).astype(float), inv, tgt, n_i, 1.0) > 0
    first = np.zeros(n_i, dtype=np.int64)
    first[inv[tgt == 1]] = np.flatnonzero(tgt == 1)
    st = {k: c[k][first] for k in ("recording_id", "lighting", "group", "speed_bin", "overlap", "growth_ratio")}
    gr = st["growth_ratio"]
    st["growth"] = np.where(gr > 1.10, "growing", np.where(gr < 0.90, "shrinking", "steady"))
    n_true = A("n_future")
    n_key = A("n_source")[:, 0]
    q, shares = {}, set()
    for K in KS:
        has = ~skipped[:, :K - 1].any(axis=1)
        for model, pref in (("affine", "affine"), ("aligned", "gp_aligned")):
            n_pred = A(f"{pref}_n_pred")
            for cell in (HC, FC):
                f1 = A(f"{pref}_f1_{cell}")
                g = np.full(n_i, np.nan); F = np.full(n_i, np.nan)
                for i in np.flatnonzero(has):
                    r = gop.group_summary(int(n_key[i]), n_pred[i, :K - 1], n_true[i, :K - 1], f1[i, :K - 1])
                    g[i], F[i] = r["gamma"], r["fidelity"]
                q[f"gamma_{model}_K{K}_{cell}"] = g
                q[f"fidelity_{model}_K{K}_{cell}"] = F
        for cell in (HC, FC):
            q[f"ratio_K{K}_{cell}"] = q[f"gamma_affine_K{K}_{cell}"] / q[f"gamma_aligned_K{K}_{cell}"]
        kb = A("gp_key_bits")[:, 0]
        NK = n_key + n_true[:, :K - 1].sum(axis=1)
        q[f"b_affine_K{K}"] = np.where(has, (kb + affine.MOTION_BITS * (K - 1)) / NK, np.nan)
        q[f"b_aligned_K{K}"] = np.where(has, (kb + gop.MOTION_BITS * (K - 1)) / NK, np.nan)
    shape = {n: A(f"affine_{n}") for n in ("ia", "ib", "ic", "id")}
    hx, hy = A("frame_hx"), A("frame_hy")
    for m in range(1, 11):
        ok = ~skipped[:, m - 1]
        for cell in (HC, FC):
            fa = np.where(ok, A(f"affine_f1_{cell}")[:, m - 1], np.nan)
            fl = np.where(ok, A(f"gp_aligned_f1_{cell}")[:, m - 1], np.nan)
            q[f"F1_affine_m{m}_{cell}"], q[f"F1_aligned_m{m}_{cell}"], q[f"F1_diff_m{m}_{cell}"] = fa, fl, fa - fl
        nz = np.zeros(n_i, dtype=bool)
        for n in shape:
            nz |= shape[n][:, m - 1] != 0
        q[f"shape_nonzero_m{m}"] = np.where(ok, nz.astype(float), np.nan)
        shares.add(f"shape_nonzero_m{m}")
        q[f"stretch_pct_m{m}"] = np.where(ok, 100.0 * 0.5 * (shape["ia"][:, m - 1] / hx[:, m - 1]
                                                             + shape["id"][:, m - 1] / hy[:, m - 1]), np.nan)
    names = list(q)
    qa = np.stack([q[n] for n in names], axis=1)

    strata = [(g, s, o, w) for g in GROUPS for s in SPEEDS for o in OVERLAPS for w in GROWTHS]
    sk = {s_: i for i, s_ in enumerate(strata)}
    rix = {r: i for i, r in enumerate(ids)}
    rec = np.array([rix[r] for r in st["recording_id"]])
    val = np.full((len(ids), len(strata), len(names)), np.nan)
    cnt = np.zeros((len(ids), len(strata), len(names)), dtype=np.int64)
    is_share = np.array([n in shares for n in names])
    base = {s_[:3]: smask(st, *s_[:3]) for s_ in strata}
    for ri in range(len(ids)):
        rm = rec == ri
        if not rm.any():
            continue
        for k, s_ in enumerate(strata):
            m_ = rm & base[s_[:3]] & ((st["growth"] == s_[3]) if s_[3] != "all" else True)
            block = qa[m_]
            if len(block) == 0:
                continue
            fin = np.isfinite(block)
            cnt[ri, k] = fin.sum(axis=0)
            with np.errstate(all="ignore"), _quiet():
                med = np.nanmedian(np.where(fin, block, np.nan), axis=0)
                mean = np.nanmean(np.where(fin, block, np.nan), axis=0)
            val[ri, k] = np.where(is_share, mean, med)
    np.savez_compressed(res / "per_recording.npz", values=val, n_instants=cnt, recording_ids=np.array(ids),
                        lighting=np.array([light[r] for r in ids]), strata=np.array(["|".join(s_) for s_ in strata]),
                        quantities=np.array(names),
                        note=np.array("Stage A. values[r, stratum, quantity]: median over the instants of recording r "
                                      "in the stratum (group|speed|overlap|growth) that have the quantity; "
                                      "shape_nonzero_m* are shares (means). n_instants[r, stratum, quantity]."))
    qi = {n: j for j, n in enumerate(names)}
    H = ("vehicles", "20-300", "isolated", "all")
    E = lambda s_, n, L: boot(val[rsel(L), sk[s_], qi[n]], cnt[rsel(L), sk[s_], qi[n]])

    T = {}
    T["1_headline_H"] = {cname: {L: {f"K{K}": {**{f"{w}_{m}": E(H, f"{w}_{m}_K{K}_{cell}", L)
                                                   for m in ("affine", "aligned") for w in ("fidelity", "gamma")},
                                               "ratio_affine_over_aligned": E(H, f"ratio_K{K}_{cell}", L)} for K in KS}
                                 for L in LB} for cell, cname in ((HC, "headline"), (FC, "frame"))}
    t2 = {}
    for m in range(1, 11):
        t2[f"m{m}"] = {}
        for L in LB:
            d = {f"{n}_{cell}": E(H, f"{n}_m{m}_{cell}", L) for n in ("F1_affine", "F1_aligned", "F1_diff")
                 for cell in (HC, FC)}
            d["share_shape_nonzero"] = E(H, f"shape_nonzero_m{m}", L)
            d["stretch_pct_median_over_recordings"] = E(H, f"stretch_pct_m{m}", L)
            mm = _inst_mask(st, H, L)
            v = q[f"stretch_pct_m{m}"][mm]; v = v[np.isfinite(v)]
            d["stretch_pct_pooled_quantiles"] = {str(x): float(np.quantile(v, x)) for x in (0.1, 0.5, 0.9)} if len(v) else None
            nzp = q[f"shape_nonzero_m{m}"][mm]; nzp = nzp[np.isfinite(nzp)]
            d["share_shape_nonzero_pooled"] = float(nzp.mean()) if len(nzp) else None
            t2[f"m{m}"][L] = d
    T["2_targets_H"] = t2
    T["3_growth_H"] = {w: {L: {**{f"{n}_K{K}": E(H[:3] + (w,), f"{n}_K{K}_{HC}" if n != "ratio" else f"ratio_K{K}_{HC}", L)
                                  for K in (4, 11) for n in ("gamma_affine", "gamma_aligned", "ratio")},
                               "n_instants_pooled": int(_inst_mask(st, H[:3] + (w,), L).sum())} for L in LB}
                       for w in ("growing", "steady", "shrinking")}
    T["4_speed_class_isolated"] = {
        f"{g}|{sp}": {L: {f"{n}_K{K}": E((g, sp, "isolated", "all"), f"{n}_K{K}_{HC}" if n != "ratio" else f"ratio_K{K}_{HC}", L)
                          for K in (4, 11) for n in ("ratio", "gamma_affine")} for L in LB}
        for g in ("vehicles", "other") for sp in ("0-20", "20-100", "100-300", "300-inf")}
    t5 = {}
    for m in (4, 10):
        for L in LB + (None,):
            mm = _inst_mask(st, H, L) & ~skipped[:, m - 1]
            t5.setdefault(f"m{m}", {})[L or "pooled"] = {
                "n_rows": int(mm.sum()),
                **{n: ({str(x): float(np.quantile(shape[n][mm, m - 1], x)) for x in (0.1, 0.5, 0.9)}
                       if mm.any() else None) for n in ("ia", "id", "ib", "ic")}}
    T["5_shape_parameters_H"] = t5
    T["6_bits_H"] = {L: {f"K{K}": {"b_affine": E(H, f"b_affine_K{K}", L), "b_aligned": E(H, f"b_aligned_K{K}", L),
                                   "fidelity_affine": E(H, f"fidelity_affine_K{K}_{HC}", L),
                                   "fidelity_aligned": E(H, f"fidelity_aligned_K{K}_{HC}", L)} for K in KS} for L in LB}
    t7 = {"skips_by_reason_and_target": {}}
    for m in range(1, 11):
        r_, n_ = np.unique(c["skip"][tgt == m], return_counts=True)
        t7["skips_by_reason_and_target"][str(m)] = {("scored" if k == "" else str(k)): int(v) for k, v in zip(r_, n_)}
    ne = c["affine_n_eval"][sc]
    t7["affine_n_eval"] = {"pooled_quantiles": {str(x): float(np.quantile(ne, x)) for x in (0, 0.05, 0.25, 0.5, 0.75, 0.95, 1)},
                           "mean": float(ne.mean())}
    t7["q_prev_given_rows"] = int(c["q_prev_given"][sc].sum())
    T["7_skips_and_search"] = t7

    # ============================================================== rule D-004-4
    t1 = T["1_headline_H"]["headline"]
    ratio11 = {L: t1[L]["K11"]["ratio_affine_over_aligned"]["median"] for L in LB}
    model = "affine" if all(v is not None and v >= 1.10 for v in ratio11.values()) else "aligned"
    gsel = {L: {f"K{K}": t1[L][f"K{K}"][f"gamma_{model}"]["median"] for K in KS} for L in LB}
    if any(v is None for L in LB for v in gsel[L].values()) or any(v is None for v in ratio11.values()):
        codec = "UNDEFINED"
    elif all(gsel[L]["K4"] >= 2.0 for L in LB):
        codec = "GO"
    elif all(v < 1.3 for L in LB for v in gsel[L].values()):
        codec = "NO-GO"
    else:
        codec = "INTERMEDIATE"
    decision = {"step_1_motion_model": {"ratio_K11": ratio11, "threshold": 1.10,
                                        "selected": "affine map" if model == "affine" else "translation (aligned)"},
                "step_2_codec": {"gamma_of_selected_model": gsel, "outcome": codec}}
    report = {"directive": "004", "decision_rule": decision,
              "acceptance": {"3_rows_scored_or_skipped_as_003": acc3, "4_translation_equals_003_aligned": acc4,
                             "5_affine_not_below_translation": acc5, "6_affine_f1_range_and_monotone": acc6},
              "aggregation": {"unit": "recording", "min_instants": MIN_N, "n_boot": N_BOOT, "seed": SEED,
                              "ratios_and_differences": "formed per instant (per row for F1), then aggregated",
                              "H": "vehicles, isolated, speed_label in [20, 300) px/s, setting (100, 0)",
                              "growth": "label box area at t_e + 300 ms over that at t_e: growing > 1.10, "
                                        "shrinking < 0.90, steady otherwise",
                              "headline_cell": HC, "frame_cell": FC},
              "tables": T}
    (res / "report.json").write_text(json.dumps(report, indent=1, allow_nan=False) + "\n")
    tasks = [json.loads(f.read_text()) for f in sorted((af / "A").glob("task_*.json"))]
    prov = {"directive": "004", "host": socket.gethostname(),
            "commit": json.loads((af / "A" / "plan.json").read_text())["commit"],
            "implementation": "reference ec.affine.evaluate_affine and ec.gop.group_summary, unchanged",
            "versions": json.loads((af / "preflight_p012.json").read_text())["P1"], "workers": a.workers,
            "wall_s": a.wall_s, "cpu_h": {"tasks_wall_sum": sum(t["wall_s"] for t in tasks) / 3600,
                                          "evaluate_affine": float(np.nansum(c["elapsed_s"])) / 3600,
                                          "reads_incl_slot_wait": sum(t["read_s"] for t in tasks) / 3600},
            "per_row_files": files}
    (res / "provenance.json").write_text(json.dumps(prov, indent=1) + "\n")
    print(json.dumps({"decision": decision, "acc": {k: v["pass"] for k, v in report["acceptance"].items()},
                      "cpu_h": prov["cpu_h"]}, indent=1))


def _inst_mask(st, s_, L):
    m = smask(st, *s_[:3])
    if s_[3] != "all":
        m &= st["growth"] == s_[3]
    if L is not None:
        m &= st["lighting"] == L
    return m


class _quiet:
    def __enter__(self):
        import warnings
        self._w = warnings.catch_warnings()
        self._w.__enter__()
        warnings.simplefilter("ignore", RuntimeWarning)

    def __exit__(self, *exc):
        return self._w.__exit__(*exc)


if __name__ == "__main__":
    main()
