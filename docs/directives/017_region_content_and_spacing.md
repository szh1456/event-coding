# Directive 017. What the regions of REMAKE hold, and whether their precision follows the event spacing

| | |
|---|---|
| track | `region content`, short name `rc` |
| population | eTraM: the reporting recordings of directive 007 and their train annotations. DSEC: the 36 reporting sequences of directive 013 |
| results directory | `results/rc/` |
| report | `docs/directives/reports/017.md` |
| runs after | directive 016 |

## 1. Why

Report 016 found that REMAKE at its frozen configuration (B = 20, ψ = 1)
rebuilds no event in about half of the annotated boxes by day. Its
fidelity is still 0.71, because the fidelity counts events, and the
regions hold most of the events of the key window: at ψ = 1 they are 1% of
the blocks of eTraM and hold 83% of the key window's events by day. What
those blocks contain was never measured. This directive measures three
things and runs no codec.

1. **What the regions hold** (eTraM). For each region we ask whether it
   touches an annotated object, and whether its map stays in place over
   three windows. The second test separates flicker and swaying
   vegetation from motion. We also measure how much of REMAKE's fidelity
   numerator comes from annotated objects, and how much of each object
   the regions cover.
2. **The event spacing of the regions** (both datasets). This is the
   spacing τ of the per-pixel rate theorem (`thm:pixel`) and of
   Eq. (binfid), measured from the events that the sender holds.
3. **Whether the precision of the moved events follows Δt/τ**
   (both datasets). This holds for each region, on grids of one pixel
   with bins of 11.1, 2.78 and 1.04 ms. Section VI-E of the manuscript
   now compares only trends, because the spacings were not measured.
   This turns that comparison into a measurement.

The results decide two things. First, whether the gain of REMAKE in the
manuscript is a gain on objects or on clutter. Second, how the distortion
measure of the next codec weighs blocks (directive 018 measures the
candidates).

## 2. Disclosure

The director wrote `ec/regions.py` and `tests/test_regions_gate.py` and
ran them on synthetic events only, in seconds: a textured box that
translates across a 320 × 240 sensor, coded by the reference codec of
directive 007. An independent review of the code by a second agent
found:

- a bias in the first spacing estimator: pooled intervals let one fast
  pixel dominate;
- an unverified claim order.

The estimator was replaced by the median over pixels of per-pixel
medians, over the key window and the three windows before it. The claim
order was confirmed equal to that of `fit_group`, ties included. The
director read no recording.

## 3. Author decisions

**D-017-1, default: authorized.** The executor adds `ec/regions.py` and
`tests/test_regions_gate.py` with the content of Appendices A and B,
unchanged.

**D-017-2, default: authorized.** The reads of this directive:

- the event files of the reporting recordings of both datasets;
- the train annotations of the eTraM reporting recordings;
- the kept per-group files of Stage R of directives 007 and 009, which
  are the files that directive 016 read.

**D-017-3, default: as stated in Sections 4 to 6.** The protocol.

## 4. Definitions

**Groups.** The groups of Stage R that directive 016, Section 7, used:
`scripts/fb_run.py:remake_groups(ds, "R", rid)` for every reporting
recording of each dataset. Each row holds `w` and the kept group `g`.
`g["records"]` holds the records of configuration (20, 1).

**Events of a group.** The events of `[(w - 3) T0, (w + 11) T0)`, read as
directive 016 read them, one recording at a time.

- `windows[m]` holds the events of `[(w + m) T0, (w + m + 1) T0)`, for
  m = 0 to 10.
- `before` holds those of `[max(0, w - 3) T0, w T0)`.

**Boxes (eTraM).** For m = 0, 1, 2 and 3, the boxes of window `w + m` are
those that `scripts/fb_run.py:boxes_for(tracks, w + m, W, H)` returns,
without the track ids.

**Strata.** Day and night for eTraM. `all` for DSEC.

## 5. Run

For every group, call

    ec.regions.evaluate_group(windows, g["records"], w, W, H, g, boxes=boxes, before=before)

with `boxes=None` for DSEC. Keep its output per group, under
`~/prjs/event_coding/rc/` for eTraM and `/data/<user>/event_coding/ds/rc/`
for DSEC. Nothing else is computed per group.

## 6. Tables

A recording enters with sums over its groups. Report medians over
recordings with 95% intervals: the bootstrap of directive 007, seed
20261016, with the entering rule of report 016 (10 groups on eTraM, 5 on
DSEC). Where a table pools blocks instead, it says so.

**Table 1, objects (eTraM).** Per recording:

1. the share of active blocks that touch a box dilated by 10 px
   (`blocks.touch[10]`);
2. the share of key events in boxes, at margins 0 and 10 px
   (`events.key_in_box`), next to the share of all events of the key
   window in boxes (`events.true0_in_box`);
3. the share of REMAKE's pairs of windows 1 to 3 that lie in boxes
   (`pairs.match_in_box / pairs.match`), next to the share of true events
   of those windows in boxes (`pairs.true_in_box / pairs.true`);
4. over the boxes of the key window with at least 50 events (`boxes0`):
   - the share of their events that lie in active blocks;
   - the share of boxes with none there;
   - the share of boxes with at least half there.

**Table 2, the regions by kind (eTraM).** Pool the active blocks of all
groups of a stratum, split by `touch[10]`. For each part report:

- the number of blocks;
- the share with a static map (`static`);
- the median speed (`speed_px_per_window`);
- the median share of pixels with both polarities (`both_polarity`);
- the median key count (`n_key`).

Add the same columns for all active blocks of DSEC, without the split.

**Table 3, precision against Δt/τ (both datasets).**

- For each block with a finite `tau_us`, each target m and each grid
  (1, 3), (1, 12) and (1, 32), let r = (T0 / k) / τ.
- Bin r at the edges 0, 1/16, 1/8, 1/4, 1/2, 1, 2 and ∞.
- Pool the (block, m) pairs of a stratum with `n_in` > 0.
- Per bin, report:
  - the number of pairs;
  - the pooled precision Σ got / Σ n_in;
  - the mean of min(1, r) over the pairs, which is the prediction of
    Eq. (binfid) for an exact map.
- Report this once for m = 1 and once for m = 1 to 10.
- Per stratum, also report the share of active blocks with a finite τ,
  the median of `covered`, and the median τ. For eTraM, give the median τ
  separately for blocks that touch a box and blocks that do not.

## 7. Cost

The groups are those of directive 016. The work per group is one read
and the claims of Section 5, with no fit and no codec.

- Project from the first 20 groups of each dataset.
- If the projection exceeds 60 CPU-hours, stop and report `BLOCKED` with
  it.
- Use the read lock and memory guard of directive 016.
- Do not compete with a companion-project job.

## 8. Acceptance checks

1. The two files have the SHA-256 of Section 10, and the suite passes
   with no skipped test.
2. For every group, `checks` is `{"n_key": True, "maps_k4_prefix": True,
   "match_equals_kept": True}`.
3. No eTraM val or test file was opened, and the annotation root was not
   listed.
4. Nothing outside `results/rc/` changed under `results/`.

## 9. Outputs

| file | content |
|---|---|
| `results/rc/per_recording.json` | per recording, the sums behind Tables 1 and 3 and the number of groups |
| `results/rc/blocks.json` | per stratum, the pooled block columns behind Tables 2 and 3 (`tau_us`, `covered`, `static`, `speed`, `both_polarity`, `n_key`, `touch`, and `got` and `n_in` per grid and m) |
| `results/rc/report.json` | Tables 1 to 3 |
| `results/rc/provenance.json` | commit, host, versions, wall and CPU time, and the files read |

## 10. Files

The SHA-256 is that of the file content: the text between the fence
lines of its appendix, ending in one newline.

| file | SHA-256 |
|---|---|
| `ec/regions.py` | `afd8b63ac1551a4516412b2d82e463752f7263978fb9efee2597a4218d8af9de` |
| `tests/test_regions_gate.py` | `f7e38fe63b7582529e450a4d2fd10321e6013798babcd7e833c09a7860c11b6d` |

## Appendix A. `ec/regions.py`

````python
"""What the regions of REMAKE hold, and how the precision of their moved events follows the event spacing
(directive 017).

Records. The functions read the kept records of REMAKE for the configuration (20, 1), model affine, coder
T: ``affine_T_K11`` and ``affine_T_K4``. Coder T keeps the times of the key events in microseconds, which
the fine time bins below need. One fit serves every K, so the maps of K = 4 are the first three maps of
K = 11 (check ``maps_k4_prefix``).

Regions. The active blocks of the group are the blocks of side B that hold key events, in raster order, as
``ec.blockcodec.decode_stream`` returns them. The key events are all events of the key window in these
blocks (check ``n_key``).

Boxes. A box is ``(x0, y0, w, h)`` in pixels, top-left corner, as ``scripts/fb_run.py:boxes_for`` returns
it. Pixel ``(x, y)`` lies in the box dilated by ``d`` pixels if ``x0 - d <= x < x0 + w + d`` and
``y0 - d <= y < y0 + h + d``. For ``d`` = 0 this is the rule of ``ec.downstream.box_scores``.

Precision of a block. For window ``m`` of the group and a grid of ``s`` pixels and ``k`` time bins per
window, the moved events of the active blocks are paired with the true events of the window in the order
in which the sender fitted the blocks: decreasing number of key events, ties in raster order. Block ``b``
takes, in every voxel, the smaller of its moved events there and the true events of the voxel that no
earlier block took. ``got`` counts its pairs and ``n_in`` its moved events on the sensor; its precision is
``got / n_in``. Whatever the order, the pairs of all blocks add up to the matched events of the whole
reconstruction, so on the working grid they equal the kept ``match_s2_k3`` (check ``match_equals_kept``).

Event spacing of a block. Over the true events of the block in the key window and the SPAN_BEFORE windows
before it, which the sender holds, take for every pixel and polarity the intervals between its
consecutive events and their median. ``tau_us`` is the median of these medians over the pixels and
polarities of the block, or NaN if fewer than MIN_PIXELS of them have an interval. A pixel that fires
once in the span gives no interval; ``covered`` is the share of the pixels and polarities with events
that give one. By Eq. (binfid) of the manuscript, moved events of an exact map on a grid of one
pixel and bins of length ``Delta_t <= tau`` have precision about ``Delta_t / tau``.
"""
from __future__ import annotations

import numpy as np

from . import blockcodec as bc

B = 20
CONFIG = "B20_rho1.0"
K_LONG, K_SHORT = 11, 4
MARGINS = (0, 10)
PREC_CELLS = ((2, 3), (1, 3), (1, 12), (1, 32))
SPAN_BEFORE = 3
MIN_PIXELS = 5
MIN_BOX_EVENTS = 50
STATIC_PX = 1


def cell_name(cell) -> str:
    return f"s{cell[0]}_k{cell[1]}"


def decode(record: bytes, K: int, w: int, width: int, height: int, model: str = "affine", coder: str = "T"):
    """Header and group of one kept record, evaluated at its own key window ``w``."""
    hdr = bc.encode_header(coder, model, K, width, height, B)
    h, groups = bc.decode_stream(hdr + record)
    if len(groups) != 1:
        raise ValueError("a kept record holds exactly one group")
    g = groups[0]
    g["w"] = int(w)
    return h, g


def voxel_keys(t_rel, x, y, p, cell, width: int, height: int, T0_us: int = bc.T0_US):
    """Voxel index of each event on the grid ``cell`` = (s px, k bins per window); ``t_rel`` from the window start."""
    s, k = cell
    nx, ny = -(-width // s), -(-height // s)
    tb = bc.time_bin(np.asarray(t_rel, dtype=np.int64), k, T0_us)
    return ((np.asarray(p, dtype=np.int64) * k + tb) * ny + np.asarray(y, dtype=np.int64) // s) * nx \
        + np.asarray(x, dtype=np.int64) // s


def box_mask(boxes, width: int, height: int, margin: float):
    """Pixels inside at least one of ``boxes`` dilated by ``margin``, as a (height, width) boolean array."""
    m = np.zeros((height, width), dtype=bool)
    for x0, y0, bw, bh in boxes:
        xa, xb = max(0, int(np.ceil(x0 - margin))), min(width, int(np.ceil(x0 + bw + margin)))
        ya, yb = max(0, int(np.ceil(y0 - margin))), min(height, int(np.ceil(y0 + bh + margin)))
        if xb > xa and yb > ya:
            m[ya:yb, xa:xb] = True
    return m


def blocks_touching(mask, width: int, height: int):
    """For every block in raster order, whether one of its pixels lies in ``mask``."""
    nbx, nby = -(-width // B), -(-height // B)
    P = np.zeros((nby * B, nbx * B), dtype=bool)
    P[:height, :width] = mask
    return P.reshape(nby, B, nbx, B).any(axis=(1, 3)).ravel()


def claim_by_block(moved_keys, true_keys, order):
    """Pairs of each block, ``moved_keys[j]`` the voxel keys of its moved events on the sensor, taken in ``order``."""
    u, R = np.unique(np.asarray(true_keys, dtype=np.int64), return_counts=True)
    got = np.zeros(len(moved_keys), dtype=np.int64)
    if len(u) == 0:
        return got
    for j in order:
        kk = moved_keys[j]
        if len(kk) == 0:
            continue
        v, c = np.unique(kk, return_counts=True)
        pos = np.minimum(np.searchsorted(u, v), len(u) - 1)
        hit = u[pos] == v
        g = np.minimum(c[hit], R[pos[hit]])
        R[pos[hit]] -= g
        got[j] = int(g.sum())
    return got


def block_spacing(t_us, x, y, p, bid, ids, width: int):
    """Per block of ``ids``: median over pixels and polarities of their median interval (us), their number, and
    the share of the pixels and polarities with events that have an interval."""
    n = len(ids)
    tau, n_pix, covered = np.full(n, np.nan), np.zeros(n, dtype=np.int64), np.full(n, np.nan)
    t_us = np.asarray(t_us, dtype=np.int64)
    if len(t_us) == 0 or n == 0:
        return tau, n_pix, covered
    pk = (np.asarray(y, dtype=np.int64) * width + np.asarray(x, dtype=np.int64)) * 2 + np.asarray(p, dtype=np.int64)
    o = np.lexsort((t_us, pk))
    pk_o, t_o, b_o = pk[o], t_us[o], np.asarray(bid)[o]
    start = np.flatnonzero(np.concatenate(([True], pk_o[1:] != pk_o[:-1])))
    size = np.diff(np.concatenate((start, [len(pk_o)])))
    jb = np.searchsorted(ids, b_o[start])                        # block of each pixel and polarity
    n_all = np.bincount(jb, minlength=n)
    med = np.full(len(start), np.nan)
    d = np.diff(t_o)
    for i in np.flatnonzero(size >= 2):
        med[i] = np.median(d[start[i]:start[i] + size[i] - 1])
    has = ~np.isnan(med)
    n_pix[:] = np.bincount(jb[has], minlength=n)
    for j in range(n):
        if n_all[j]:
            covered[j] = n_pix[j] / n_all[j]
        if n_pix[j] >= MIN_PIXELS:
            tau[j] = float(np.median(med[has & (jb == j)]))
    return tau, n_pix, covered


def both_polarity_share(x, y, p, bid, ids, width: int):
    """Per block of ``ids``: the share of its pixels with events that have events of both polarities."""
    pix = np.asarray(y, dtype=np.int64) * width + np.asarray(x, dtype=np.int64)
    up = np.unique(pix * 2 + np.asarray(p, dtype=np.int64))
    pix_u, n_pol = np.unique(up // 2, return_counts=True)
    blk = (pix_u // width // B) * (-(-width // B)) + (pix_u % width) // B
    j = np.searchsorted(ids, blk)
    tot = np.bincount(j, minlength=len(ids)).astype(np.float64)
    both = np.bincount(j, weights=(n_pol == 2).astype(np.float64), minlength=len(ids))
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(tot > 0, both / tot, np.nan)


def evaluate_group(windows, records: dict, w: int, width: int, height: int, kept: dict, boxes=None, before=None,
                   T0_us: int = bc.T0_US) -> dict:
    """Regions, spacing and precision of one group.

    ``windows[m]`` = (t_us, x, y, p), int64, of window ``w + m``, m = 0 .. 10, times nondecreasing.
    ``records`` holds ``affine_T_K11`` and ``affine_T_K4``. ``kept`` is the kept group of directive 007
    or 009 (``evaluate_group`` output); its configuration CONFIG, model affine, gives ``n_key``,
    ``match_s2_k3`` and ``n_rec`` for the checks. ``boxes``: None (no annotation) or a list over m = 0 .. 3
    of lists of boxes ``(x0, y0, w, h)``. ``before``: (t_us, x, y, p) of ``[(w - SPAN_BEFORE) T0, w T0)``,
    for the event spacing.
    """
    h11, g = decode(records[f"affine_T_K{K_LONG}"], K_LONG, w, width, height)
    _, g4 = decode(records[f"affine_T_K{K_SHORT}"], K_SHORT, w, width, height)
    kt, kx, ky, kp = (np.asarray(a, dtype=np.int64) for a in g["key"])
    ids, bid, maps = g["ids"], g["bid"], g["maps"]
    nb = len(ids)
    j_of = np.searchsorted(ids, bid)
    counts = np.bincount(j_of, minlength=nb)
    order = np.lexsort((ids, -counts))
    members = [np.flatnonzero(j_of == j) for j in range(nb)]
    frames = [bc.block_frame(int(b), B, width) for b in ids]

    t0, x0, y0, p0 = (np.asarray(a, dtype=np.int64) for a in windows[0])
    bid0 = bc.block_ids(x0, y0, B, width)
    in_act = np.isin(bid0, ids)
    kept_row = kept["codec"][CONFIG]
    kept_m = kept_row["models"]["affine"]
    checks = {"n_key": bool(int(in_act.sum()) == len(kt) == int(kept_row["n_key"])),
              "maps_k4_prefix": bool(np.array_equal(g4["ids"], ids)
                                     and np.array_equal(g4["maps"], maps[:, :K_SHORT - 1]))}

    # the moved events of every block, per target, with their time offset in the window
    moved = []
    for m in range(1, K_LONG):
        per = []
        for j in range(nb):
            sel = members[j]
            ix, iy = bc.move(kx[sel], ky[sel], frames[j], maps[j, m - 1])
            on = (ix >= 0) & (ix < width) & (iy >= 0) & (iy < height)
            per.append((kt[sel][on], ix[on], iy[on], kp[sel][on]))
        moved.append(per)

    prec = {}
    for cell in PREC_CELLS:
        got = np.zeros((nb, K_LONG - 1), dtype=np.int64)
        n_in = np.zeros((nb, K_LONG - 1), dtype=np.int64)
        for m in range(1, K_LONG):
            tt, tx, ty, tp = windows[m]
            tk = voxel_keys(np.asarray(tt, dtype=np.int64) - (w + m) * T0_us, tx, ty, tp, cell, width, height, T0_us)
            mk = [voxel_keys(*ev, cell, width, height, T0_us) for ev in moved[m - 1]]
            got[:, m - 1] = claim_by_block(mk, tk, order)
            n_in[:, m - 1] = [len(k) for k in mk]
        prec[cell_name(cell)] = {"got": got, "n_in": n_in}
    wg = prec[cell_name(bc.OBJECTIVE)]
    checks["match_equals_kept"] = bool(wg["got"].sum(0).tolist() == list(kept_m[f"match_s{bc.OBJECTIVE[0]}_k{bc.OBJECTIVE[1]}"])
                                       and wg["n_in"].sum(0).tolist() == list(kept_m["n_rec"]))

    if before is None:
        raise ValueError("the event spacing needs the windows before the key window")
    tb_, xb_, yb_, pb_ = (np.asarray(a, dtype=np.int64) for a in before)
    if len(tb_) and (tb_.min() < (w - SPAN_BEFORE) * T0_us or tb_.max() >= w * T0_us):
        raise ValueError("before: events outside [(w - SPAN_BEFORE) T0, w T0)")
    sp = (np.concatenate((tb_, t0)), np.concatenate((xb_, x0)), np.concatenate((yb_, y0)), np.concatenate((pb_, p0)))
    bsp = bc.block_ids(sp[1], sp[2], B, width)
    a_ = np.isin(bsp, ids)
    tau, n_pix, covered = block_spacing(sp[0][a_], sp[1][a_], sp[2][a_], sp[3][a_], bsp[a_], ids, width)
    d3 = maps[:, :3, :2] if nb else np.zeros((0, 3, 2), dtype=np.int64)
    static = (np.abs(d3).max(axis=(1, 2)) <= STATIC_PX) & ~np.any(maps[:, :3, 2:] != 0, axis=(1, 2)) if nb \
        else np.zeros(0, dtype=bool)
    speed = np.hypot(maps[:, 2, 0], maps[:, 2, 1]) / 3.0 if nb else np.zeros(0)
    blocks = {"ids": ids, "n_key": counts, "order": order, "static": static, "speed_px_per_window": speed,
              "both_polarity": both_polarity_share(x0[in_act], y0[in_act], p0[in_act], bid0[in_act], ids, width),
              "tau_us": tau, "n_pixels_spacing": n_pix, "covered": covered, "prec": prec}
    out = {"w": int(w), "n_key": int(len(kt)), "n_true": [int(len(v[0])) for v in windows],
           "n_blocks_sensor": int((-(-width // B)) * (-(-height // B))), "blocks": blocks, "checks": checks,
           "events": None, "pairs": None, "boxes0": None}
    if boxes is None:
        return out

    # boxes: which regions touch them, which key events and pairs fall in them, which objects the regions cover
    masks = [{d: box_mask(boxes[m], width, height, d) for d in MARGINS} for m in range(K_SHORT)]
    blocks["touch"] = {d: blocks_touching(masks[0][d], width, height)[ids] for d in MARGINS}
    out["events"] = {"key_in_box": {d: int(masks[0][d][ky, kx].sum()) for d in MARGINS},
                     "true0_in_box": {d: int(masks[0][d][y0, x0].sum()) for d in MARGINS}}
    s, k = bc.OBJECTIVE
    nx, ny = -(-width // s), -(-height // s)
    pairs = {"m": [], "match": [], "match_in_box": [], "true": [], "true_in_box": []}
    for m in range(1, K_SHORT):
        tt, tx, ty, tp = (np.asarray(a, dtype=np.int64) for a in windows[m])
        tk = voxel_keys(tt - (w + m) * T0_us, tx, ty, tp, bc.OBJECTIVE, width, height, T0_us)
        rk = np.concatenate([voxel_keys(*ev, bc.OBJECTIVE, width, height, T0_us) for ev in moved[m - 1]]) \
            if nb else np.zeros(0, dtype=np.int64)
        u, cu = np.unique(tk, return_counts=True)
        v, cv = np.unique(rk, return_counts=True)
        com, i1, i2 = np.intersect1d(u, v, assume_unique=True, return_indices=True)
        mm = np.minimum(cu[i1], cv[i2])
        vx, vy = (com % nx) * s, ((com // nx) % ny) * s
        mk = masks[m][MARGINS[-1]]
        pairs["m"].append(m)
        pairs["match"].append(int(mm.sum()))
        pairs["match_in_box"].append(int(mm[mk[vy, vx]].sum()))
        pairs["true"].append(int(len(tt)))
        pairs["true_in_box"].append(int(mk[ty, tx].sum()))
    out["pairs"] = pairs
    rows = []
    for x0b, y0b, bw, bh in boxes[0]:
        inside = (x0 >= x0b) & (x0 < x0b + bw) & (y0 >= y0b) & (y0 < y0b + bh)
        n = int(inside.sum())
        if n >= MIN_BOX_EVENTS:
            rows.append({"box": [float(x0b), float(y0b), float(bw), float(bh)], "n_true": n,
                         "n_in_active": int((inside & in_act).sum())})
    out["boxes0"] = rows
    return out
````

## Appendix B. `tests/test_regions_gate.py`

````python
"""Gate for directive 017: regions, event spacing and per-block precision, on synthetic events.

A textured box translates across a small sensor. The reference codec of directive 007 fits and writes the
records of one group, as the kept per-group files hold them; ``ec.regions`` then reads only those records
and the true events. The tolerances are fixed by the director.
"""
import numpy as np

from ec import blockcodec as bc
from ec import downstream as dn
from ec import regions as rg
from ec import synth

W, H, WKEY = 320, 240, 6
T0 = bc.T0_US


def scene():
    s = synth.rigid_translation(width=W, height=H, n_points=1500, box_wh=(80.0, 60.0), c0=(60.0, 120.0),
                                v=(200.0, 0.0), duration_s=1.0, seed=3)
    return (s.t.astype(np.int64), s.x.astype(np.int64), s.y.astype(np.int64), s.p.astype(np.int64)), s.boxes


def kept_group(ev):
    return bc.evaluate_group(*ev, WKEY, 0, W, H, blocks=(20,), densities=(1.0,), models=("affine",),
                             records_for=(20, 1.0))


def windows(ev):
    t = ev[0]
    out = []
    for m in range(11):
        a, b = np.searchsorted(t, ((WKEY + m) * T0, (WKEY + m + 1) * T0))
        out.append(tuple(v[a:b] for v in ev))
    return out


def boxes_of(bx, m):
    c = (WKEY + m + 0.5) * T0
    i = int(np.argmin(np.abs(bx["t"].astype(np.float64) - c)))
    return [(float(bx["x"][i]), float(bx["y"][i]), float(bx["w"][i]), float(bx["h"][i]))]


_CACHE = {}


def group():
    if not _CACHE:
        ev, bx = scene()
        g = kept_group(ev)
        win = windows(ev)
        a, b = np.searchsorted(ev[0], ((WKEY - rg.SPAN_BEFORE) * T0, WKEY * T0))
        before = tuple(v[a:b] for v in ev)
        out = rg.evaluate_group(win, g["records"], WKEY, W, H, g, boxes=[boxes_of(bx, m) for m in range(4)],
                                before=before)
        _CACHE.update(ev=ev, g=g, win=win, out=out, bx=bx)
    return _CACHE


def test_checks_hold_on_a_moving_box():
    out = group()["out"]
    assert out["checks"] == {"n_key": True, "maps_k4_prefix": True, "match_equals_kept": True}
    assert len(out["blocks"]["ids"]) >= 4
    assert not out["blocks"]["static"].any()
    assert np.all(np.abs(out["blocks"]["speed_px_per_window"] - 200.0 * T0 * 1e-6) < 2.0)


def test_regions_and_pairs_lie_in_the_box():
    out = group()["out"]
    assert out["events"]["key_in_box"][10] == out["n_key"]
    assert out["blocks"]["touch"][10].all()
    pr = out["pairs"]
    assert all(m > 0 for m in pr["match"])
    assert all(a >= 0.95 * b for a, b in zip(pr["match_in_box"], pr["match"]))
    assert len(out["boxes0"]) == 1 and out["boxes0"][0]["n_in_active"] <= out["boxes0"][0]["n_true"]


def test_precision_falls_with_the_bin_and_pairs_add_up():
    out = group()["out"]
    prec = out["blocks"]["prec"]
    got = {c: prec[rg.cell_name(c)]["got"].sum() for c in rg.PREC_CELLS}
    n_in = {c: prec[rg.cell_name(c)]["n_in"].sum() for c in rg.PREC_CELLS}
    assert len(set(n_in.values())) == 1
    assert got[(2, 3)] >= got[(1, 3)] >= got[(1, 12)] >= got[(1, 32)] > 0


def test_box_mask_is_the_rule_of_box_scores():
    rng = np.random.default_rng(0)
    yy, xx = np.mgrid[0:H, 0:W]
    for _ in range(20):
        box = (rng.uniform(-10, W), rng.uniform(-10, H), rng.uniform(0.5, 90), rng.uniform(0.5, 90))
        for d in rg.MARGINS:
            m = rg.box_mask([box], W, H, d)
            ref = (xx >= box[0] - d) & (xx < box[0] + box[2] + d) & (yy >= box[1] - d) & (yy < box[1] + box[3] + d)
            assert np.array_equal(m, ref)
        t = np.zeros(1000, dtype=np.int64)
        x, y = rng.integers(0, W, 1000), rng.integers(0, H, 1000)
        sc = dn.box_scores((t, x, y, t), (t, x, y, t), box, 0)
        assert sc["n_true"] == int(rg.box_mask([box], W, H, 0)[y, x].sum())


def test_claims_add_up_to_the_matched_events_in_any_order():
    rng = np.random.default_rng(1)
    true = rng.integers(0, 50, 400)
    moved = [rng.integers(0, 60, int(n)) for n in rng.integers(0, 80, 7)]
    u, c = np.unique(true, return_counts=True)
    v, cv = np.unique(np.concatenate(moved), return_counts=True)
    com, i, j = np.intersect1d(u, v, return_indices=True)
    total = int(np.minimum(c[i], cv[j]).sum())
    for _ in range(5):
        got = rg.claim_by_block(moved, true, rng.permutation(7))
        assert int(got.sum()) == total
        assert np.all(got <= [len(m) for m in moved])


def test_spacing_and_polarity_of_constructed_trains():
    ts, xs, ys, ps = [], [], [], []
    for px in range(10):                     # block 0: one pixel fires 40 events at 500 us, nine fire 4 at 2000 us
        n, d = (40, 500) if px == 0 else (4, 2000)
        ts += [100 * px + d * j for j in range(n)]; xs += [px] * n; ys += [0] * n; ps += [1] * n
    for px in range(10):                     # block 1: one event per pixel and polarity, both polarities
        ts += [50 * px, 50 * px + 500]; xs += [20 + px] * 2; ys += [0] * 2; ps += [0, 1]
    t, x, y, p = (np.asarray(a, dtype=np.int64) for a in (ts, xs, ys, ps))
    o = np.argsort(t, kind="stable")
    t, x, y, p = t[o], x[o], y[o], p[o]
    bid = bc.block_ids(x, y, rg.B, W)
    ids = np.array([0, 1])
    tau, n, cov = rg.block_spacing(t, x, y, p, bid, ids, W)
    assert tau[0] == 2000.0 and n[0] == 10 and cov[0] == 1.0      # the fast pixel counts once
    assert np.isnan(tau[1]) and n[1] == 0 and cov[1] == 0.0
    both = rg.both_polarity_share(x, y, p, bid, ids, W)
    assert both[0] == 0.0 and both[1] == 1.0


def test_spacing_of_the_moving_box_is_its_crossing_interval():
    b = group()["out"]["blocks"]
    assert np.all(np.isfinite(b["tau_us"])) and np.all(b["covered"] > 0.5)
````
