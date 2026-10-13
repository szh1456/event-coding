"""What the regions of REMAKE hold, and how the precision of their moved events follows the event spacing
(directive 017).

Records. The functions read the kept records of REMAKE for the configuration (20, 1), model affine, coder
T: ``affine_T_K11`` and ``affine_T_K4``. Coder T keeps the times of the key events in microseconds, which
the fine time bins below need. One fit serves every K, so the maps of K = 4 are the first three maps of
K = 11 (check ``maps_k4_prefix``).

Regions. The active blocks of the group are the blocks of side B that hold key events, in raster order, as
``ec.blockcodec.decode_stream`` returns them. The key events are all events of the key window in these
blocks (check ``n_key``).

Boxes. ``boxes_at`` gives, for every track alive at the center of a window, its box interpolated
linearly between its labeled frames at that instant and clipped to the sensor, as ``(track_id, (x0, y0,
w, h))`` in pixels with the top-left corner. Directive 016 took the nearest labeled frame instead, which
leaves windows without a box when labels come at 20 Hz, as those of DSEC-Detection do. Pixel ``(x, y)`` lies in the box dilated by ``d`` pixels if ``x0 - d <= x < x0 + w + d`` and
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


def boxes_at(tracks, wm: int, width: int, height: int, T0_us: int = bc.T0_US):
    """Boxes of the tracks alive at the center of window ``wm``, interpolated and clipped to the sensor."""
    c = (wm + 0.5) * T0_us
    out = []
    for tr in tracks:
        if not (tr.t_first <= c <= tr.t_last):
            continue
        x, y, w, h = (float(v) for v in tr.box(c))
        x0, y0 = max(0.0, x), max(0.0, y)
        x1, y1 = min(float(width), x + w), min(float(height), y + h)
        if x1 > x0 and y1 > y0:
            out.append((int(tr.track_id), (x0, y0, x1 - x0, y1 - y0)))
    return out


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
