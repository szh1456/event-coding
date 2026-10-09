"""Key windows and regenerated windows (directive 003). Reference implementation.

Question. A sender transmits the events of one window of an object (the key
window) and, for each of the next windows, only a displacement. The receiver
regenerates those windows by moving the key events. What fidelity does the
receiver get per event sent, against sending a random subset of all events?

For one evaluation instant ``t_e`` (the windows, the support and the truth are
those of ``ec.regen.evaluate_regen``):

* key window: ``[t_e - T2, t_e)``. Its events inside the label box (the source of
  ``ec.regen``) are sent as they are;
* target window ``m`` = 1, 2, ...: ``[t_e + D_m, t_e + D_m + T2)`` with lead
  ``D_m = (m - 1) * 100000 // 3`` microseconds, so that ``m`` = 1, 2, 4, 10 are the
  leads 0, 33, 100 and 300 ms of directive 002;
* model ``aligned``: the key events moved by an integer displacement
  ``(dx, dy)`` px and by ``D_m + T2`` in time. The sender chooses the displacement
  to maximize the fidelity against the true events of the target window, and
  transmits it. The search starts at the displacement that the ``cmax`` velocity
  of directive 001 predicts and is coarse to fine;
* the models of ``ec.regen`` (``static``, ``cmax``, ``label``, ``uniform``) are
  computed by ``ec.regen.evaluate_regen`` itself and returned next to it. ``cmax``
  extrapolates a velocity estimated before ``t_e`` and sends nothing per window;
  ``static`` repeats the key events in place.

A group of ``K`` windows is the key window and the targets ``m`` = 1 .. K - 1.
With ``n_key`` key events, and for each target ``n_pred`` regenerated events,
``n_true`` true events and ``match = F1 (n_pred + n_true) / 2`` paired events:

    fidelity    F   = 2 (n_key + sum match) / (2 n_key + sum (n_pred + n_true))
    event share phi = n_key / (n_key + sum n_true)

The key window counts as reproduced exactly. A random subset that keeps a share
``q`` of all events has precision 1 and recall ``q`` in every voxel grid, so its
fidelity is ``2 q / (1 + q)``. The share that random thinning needs to reach the
fidelity ``F`` is ``q_eq = F / (2 - F)``, and

    gamma = q_eq / phi

is the factor by which regeneration lowers the number of events sent at equal
fidelity. ``gamma`` = 1 means no better than thinning.

Transport sizes use the baseline of the companion project
(``ec.baseline.payload_bits``, U2 + zstd-1) on the events of one window of one
object, with times relative to the window start.
"""
from __future__ import annotations

import math

import numpy as np

from . import regen
from .annotations import Track, in_box_mask
from .baseline import payload_bits

N_TARGETS = 10
MOTION_BITS = 24                      # two signed 12-bit pixel displacements per regenerated window
THIN_SHARES = (0.75, 0.5, 0.35, 0.25, 0.125)
THIN_SEED = 20261010
OBJECTIVE = (2, 3)                    # the headline cell of directive 002


def lead_us(m: int) -> int:
    return (m - 1) * 100_000 // 3


def _stage_cell(step: int):
    s = 2 if step <= 2 else 4 if step <= 4 else 8 if step <= 8 else 16
    return s, (OBJECTIVE[1] if s == 2 else 1)


def aligned_displacement(sx, sy, st, sp, fx, fy, ft, fp, w0_us: int, T2_us: int, shift_us: int, support, d0):
    """Integer displacement that maximizes the voxel F1 of the moved source against the truth.

    ``d0`` is the predicted displacement in px. Half-width of the search:
    ``R = max(3, ceil(0.3 |d0|))``. The first stage tries the 9 x 9 displacements at
    spacing ``ceil(R / 4)`` around ``rint(d0)``; each later stage halves the spacing
    and tries 5 x 5, down to 1 px. A stage scores on blocks no smaller than its
    spacing (2, 4, 8 or 16 px), with three time bins at 2 px and one above. Ties go
    to the candidate nearest the current best. The result is never worse than
    ``rint(d0)`` at the objective cell. Returns ``(dx, dy), (d0x, d0y), n_evaluations``.
    """
    x0, x1, y0, y1 = support
    sx = np.asarray(sx, dtype=np.int64); sy = np.asarray(sy, dtype=np.int64)
    tm = np.asarray(st, dtype=np.int64) + int(shift_us)
    n_eval = 0

    def score(d, cell):
        nonlocal n_eval
        n_eval += 1
        ix, iy = sx + d[0], sy + d[1]
        keep = (ix >= x0) & (ix <= x1) & (iy >= y0) & (iy <= y1)
        return regen.voxel_f1(ix[keep], iy[keep], tm[keep], sp[keep], fx, fy, ft, fp, w0_us, T2_us, *cell)["f1"]

    start = (int(np.rint(d0[0])), int(np.rint(d0[1])))
    R = max(3, int(math.ceil(0.3 * math.hypot(d0[0], d0[1]))))
    step, reach, best = int(math.ceil(R / 4)), 4, start
    while True:
        cell = _stage_cell(step)
        offs = [(i, j) for i in range(-reach, reach + 1) for j in range(-reach, reach + 1)]
        offs.sort(key=lambda ij: (ij[0] * ij[0] + ij[1] * ij[1], ij))
        cand, top = best, -1.0
        for i, j in offs:
            d = (best[0] + i * step, best[1] + j * step)
            f = score(d, cell)
            if f > top:
                cand, top = d, f
        best = cand
        if step == 1:
            break
        step, reach = int(math.ceil(step / 2)), 2
    if best != start and score(best, OBJECTIVE) <= score(start, OBJECTIVE):
        best = start
    return best, start, n_eval


def evaluate_target(t_us, x, y, p, track: Track, t_e_us: int, m: int, T2_us: int, width: int, height: int,
                    v_cmax, T1_us: int = 100_000, margin_px: float = 2.0, sizes: bool = True) -> dict:
    """All quantities of target window ``m`` of the group keyed at ``t_e``. ``t_us`` must be nondecreasing."""
    D = lead_us(m)
    out = regen.evaluate_regen(t_us, x, y, p, track, t_e_us, D, T2_us, width, height, v_cmax, T1_us, margin_px)
    if "skipped" in out:
        return out
    t_us = np.asarray(t_us, dtype=np.int64)
    w0, w1, shift = int(t_e_us + D), int(t_e_us + D + T2_us), int(D + T2_us)
    # support, truth and source: identical to ec.regen.evaluate_regen
    v_lab = track.velocity(t_e_us, T1_us)
    bx, by, bw, bh = (float(a) for a in track.box(0.5 * (w0 + w1)))
    grow = margin_px + 0.5 * math.hypot(*v_lab) * T2_us * 1e-6
    sx0 = max(0, int(math.floor(bx - grow))); sx1 = min(width - 1, int(math.ceil(bx + bw + grow)))
    sy0 = max(0, int(math.floor(by - grow))); sy1 = min(height - 1, int(math.ceil(by + bh + grow)))
    b0, b1 = np.searchsorted(t_us, (w0, w1))
    fxa, fya = np.asarray(x[b0:b1]), np.asarray(y[b0:b1])
    fm = (fxa >= sx0) & (fxa <= sx1) & (fya >= sy0) & (fya <= sy1)
    ft, fx, fy, fp = t_us[b0:b1][fm], fxa[fm], fya[fm], np.asarray(p[b0:b1])[fm]
    a0, a1 = np.searchsorted(t_us, (t_e_us - T2_us, t_e_us))
    sm = in_box_mask(track, t_us[a0:a1], x[a0:a1], y[a0:a1], margin_px)
    st = t_us[a0:a1][sm]
    sx, sy, sp = np.asarray(x[a0:a1])[sm], np.asarray(y[a0:a1])[sm], np.asarray(p[a0:a1])[sm]
    assert len(st) == out["n_source"] and len(ft) == out["n_future"]
    d0 = (float(v_cmax[0]) * shift * 1e-6, float(v_cmax[1]) * shift * 1e-6)
    (dx, dy), (d0x, d0y), n_eval = aligned_displacement(sx, sy, st, sp, fx, fy, ft, fp, w0, T2_us, shift,
                                                        (sx0, sx1, sy0, sy1), d0)

    def cells(d, prefix):
        ix, iy = sx.astype(np.int64) + d[0], sy.astype(np.int64) + d[1]
        keep = (ix >= sx0) & (ix <= sx1) & (iy >= sy0) & (iy <= sy1)
        out[f"{prefix}_n_pred"] = int(keep.sum())
        for s in regen.BLOCKS_PX:
            for k in regen.TIME_BINS:
                out[f"{prefix}_f1_s{s}_k{k}"] = regen.voxel_f1(ix[keep], iy[keep], (st + shift)[keep], sp[keep],
                                                               fx, fy, ft, fp, w0, T2_us, s, k)["f1"]

    cells((dx, dy), "aligned")
    cells((d0x, d0y), "start")
    out.update({"m": int(m), "aligned_dx": dx, "aligned_dy": dy, "start_dx": d0x, "start_dy": d0y,
                "aligned_n_eval": n_eval})
    if sizes:
        out["true_bits"] = payload_bits(ft - w0, fx, fy, fp)
        if m == 1:
            out["key_bits"] = payload_bits(st - int(t_e_us - T2_us), sx, sy, sp)
            u = np.random.default_rng((THIN_SEED, int(track.track_id), int(t_e_us))).random(len(ft))
            for q in THIN_SHARES:
                kp = u < q
                out[f"thin_n_q{q}"] = int(kp.sum())
                out[f"thin_bits_q{q}"] = payload_bits((ft - w0)[kp], fx[kp], fy[kp], fp[kp])
    return out


def group_summary(n_key: int, n_pred, n_true, f1) -> dict:
    """Fidelity, event share and gamma of a group. The sequences hold the targets m = 1 .. K - 1."""
    n_pred = np.asarray(n_pred, dtype=np.float64)
    n_true = np.asarray(n_true, dtype=np.float64)
    match = np.asarray(f1, dtype=np.float64) * (n_pred + n_true) / 2.0
    F = 2.0 * (n_key + match.sum()) / (2.0 * n_key + (n_pred + n_true).sum())
    phi = n_key / (n_key + n_true.sum())
    q_eq = F / (2.0 - F)
    return {"fidelity": float(F), "share": float(phi), "q_eq": float(q_eq), "gamma": float(q_eq / phi)}
