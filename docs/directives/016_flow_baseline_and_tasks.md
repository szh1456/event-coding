# Directive 016. A motion-predictive baseline, two downstream tasks, and the ablations on them

| | |
|---|---|
| track | `flow baseline`, short name `fb` |
| population | eTraM: the 112 train recordings of `config/population.yaml` and their train annotations, as directive 007 read them. DSEC: the 41 sequences of `config/population_dsec.yaml`, as directive 013 read them |
| results directory | `results/fb/` |
| report | `docs/directives/reports/016.md` |
| runs after | directive 015 |

## 1. Why

REMAKE is compared so far only with schemes that send a subset of the events.
This directive adds three things.

1. **A motion-predictive baseline.** It follows the flow-based coder of
   [stumpp2024] (FBC), which is the published event coder closest to
   REMAKE. FBC sends events with their optical flow and lets the receiver
   extrapolate them, and like REMAKE it sends no residual.
2. **Two downstream tasks that need no trained model.** Both are scored on
   the rebuilt events of every scheme at equal bits.
   - *objects*: fidelity and centroid error inside the annotated boxes of
     eTraM;
   - *motion*: the velocity that contrast maximization [gallego2018cmax]
     finds on the rebuilt events, against the velocity it finds on the true
     events.
3. **The ablations of REMAKE on these tasks.** The tasks are also run with
   one translation per block, and with the key events repeated without a
   map.

## 2. Disclosure

The director wrote `ec/fbc.py` and `ec/downstream.py` and tested them on
synthetic events only, in seconds. The tests use parallel edges and the
textured translation of `ec.synth`. The tests of Appendix C are the
director's acceptance tolerances. The director read no recording.

What the director knows of [stumpp2024] comes from:

- the arXiv abstract page of 2403.08086;
- the brief, `docs/brief/event_coding_brief.md`, entry `[stumpp2024]`.

From these it took four things: the two states, the confidence rule, the
prediction rule with the slack 0.4, and ST from the first 500 flows. The
four differences from FBC are listed in the docstring of `ec/fbc.py`. The
largest is the flow: a local plane fit [benosman2014] replaces ARMS.

## 3. Author decisions

**D-016-1, default: authorized.** The executor adds `ec/fbc.py`,
`ec/downstream.py` and `tests/test_fbc_gate.py` with the content of
Appendices A, B and C, unchanged.

**D-016-2, default: as stated in Section 5.** The baseline is calibrated
like REMAKE. On each dataset its two fit parameters are tuned on the tuning
subset of that dataset, with the criterion of REMAKE, separately for each
coder. The frozen configuration is then reported over the reporting subset.

**D-016-3, default: authorized.** The reads of Section 4. These are:

- the event files of both datasets;
- the train annotations of the eTraM reporting recordings;
- the per-group files and kept streams of Stage R of directives 007 and
  009.

**D-016-4, default: as stated in Section 7.** The downstream protocol.

## 4. Definitions

**Groups.** The key windows, the spacing and the entering rule of Stage R
are those of directive 007 for eTraM (S = 90, at least 10 groups) and of
directive 013 for DSEC (S = 60, at least 5 groups). The tuning subsets are
those of directive 007, Section 6, and of directive 013, Section 4.

**Events.** Every call of `ec.fbc.evaluate_group` receives the events from
`FIT_WINDOW_US` before the key window to the end of window 10.

**Host paths.** For eTraM, `~/prjs/event_coding/fb/`. For DSEC,
`/data/<user>/event_coding/ds/fb/`.

## 5. Stage T: the baseline on the tuning subsets

**Run.** Every group of the tuning recordings, with
`ec.fbc.evaluate_group(t, x, y, p, w, width, height, Ks=(4,), coders=("T", "Q"), radius, res_us)`,
for `radius` in 2, 3, 4 and `res_us` in 500, 1000, 2000. That is nine
configurations.

**Criterion.** For a recording, a configuration and a coder, let
`s = ec.fbc.summarize(ec.fbc.sum_groups(groups, f"{coder}_K4"), g, coder, 4)`.
Here `g` is the REMAKE sum of the same groups, taken from the per-group
files of directive 007 (Stage T) or 013. Then

    J = (s["bits_base"] - s["bits"]) / s["bits_direct"]

as for REMAKE. `J` is the median over the tuning recordings of the
dataset.

**Freeze.** For each dataset and coder, take the configuration with the
largest `J`. On a tie, take the larger `radius`, then the larger `res_us`.
Commit `results/fb/tuning.json` before Stage R evaluates a reporting group,
and give the commit in the report.

## 6. Stage R: the baseline on the reporting subsets

Every group of the reporting recordings, with
`evaluate_group(..., Ks=(2, 4, 8, 11), coders=("T", "Q"))` at the frozen
configuration of each coder. Per recording, apply `sum_groups` and
`summarize` for each coder and K.

**Report tables, medians over recordings with 95% intervals.** These use
the bootstrap of directive 007, with seed 20261016. Strata: day and night
for eTraM, `all` for DSEC.

1. **The baseline:** `F`, `bits`, `bits_base`, `gain_sub` and `st_us`, per
   coder and K.
2. **REMAKE against the baseline at equal K.** Per recording, the ratio of
   the baseline's bits to REMAKE's bits, and the difference of their `F`.
   REMAKE is `summarize(g, "B20_rho1.0", "affine", coder, K)`, with the same
   coder.
3. **REMAKE against the baseline at equal F.** Per recording and coder, the
   baseline's four points `(F_K, bits_K)` form a curve. Its bits at REMAKE's
   F at K are interpolated linearly in F between the two neighboring points.
   This is NaN if REMAKE's F lies outside the range of the curve. Report
   `G_pred = interpolated bits / REMAKE bits`, with the number of recordings
   that are NaN.

## 7. Downstream tasks

**Schemes.** For every reporting group, K = 4, windows m = 1, 2 and 3:

| scheme | events of window m |
|---|---|
| `true` | the recorded events |
| `remake_T`, `remake_Q` | `ec.blockcodec.reconstruct` of the decoded record `affine_<coder>_K4` of configuration (20, 1) |
| `translation_Q`, `static_Q` | the same for the records `translation_Q_K4` and `static_Q_K4` |
| `fbc_T`, `fbc_Q` | `ec.fbc.reconstruct` of the frozen baseline, K = 4 |
| `thin_T`, `thin_Q` | a random subset with the bits of `remake_<coder>` |

For the random subset, the share is `q = min(1, b / b_direct)`. Here `b` is
the bits of that REMAKE record per true event of the group, and `b_direct`
the bits of all events with the same coder. Draw the subset per window with
`np.random.default_rng(20261016 + w)`. Code it with the coder (Q on the
working grid, `ec.blockcodec.Q_DIRECT`) and decode it. Record its actual
bits.

If the per-group files do not hold the records of `translation` and `static`,
drop those two schemes and say so. Do not evaluate any group again for
them.

**Objects (eTraM).**

- For every track of the annotation file and every window m, take the box
  of the annotation frame nearest the center of the window, if it lies
  within the window.
- Clip the box to the sensor. Keep it if it holds at least 50 true events
  of the window.
- For every scheme, compute `ec.downstream.box_scores(true, rec, box, w0)`.

Per recording, report for each scheme:

- the median of `F` over boxes;
- the share of boxes with `n_rec` = 0;
- the median `centroid_px` over the other boxes.

Then take the medians over recordings, by day and by night.

**Motion (both datasets), window m = 2 only.**

- Cut the sensor into squares of 40 px aligned to multiples of 40.
- Take the 10 squares with the most true events, if each holds at least 200.
- For every scheme, compute `ec.downstream.motion_error_px(true, rec, square, w0)`.

Per recording, report for each scheme the median over squares and the
share of squares where the scheme has no event. Then take the medians over
recordings, per stratum.

**Bits.** Report the median over recordings of each scheme's bits per true
event, next to the scores, so that equal bits can be checked.

## 8. Cost

Each call of `ec.fbc.evaluate_group` fits flows once per window and
encodes all eight K and coder combinations from them. Project Stages T and
R and the tasks from the first 20 groups of Stage T and from 20 reporting
groups.

- If the projection of everything exceeds 250 CPU-hours, stop after Stage T
  and report `BLOCKED` with the projection.
- A run that then costs more than projected is let finish, and both numbers
  are reported.
- Read one recording at a time, with the memory guard of report 009.
- Do not compete with a companion-project job.

## 9. Acceptance checks

1. The three files have the SHA-256 of Section 11, and the suite passes
   with no skipped test.
2. `results/fb/tuning.json` was committed before Stage R evaluated a
   reporting group.
3. For every group, the true events counted by the baseline equal those of
   the REMAKE group (`summarize` raises otherwise).
4. For every scheme of Section 7, the decoded events of a window lie in that
   window and on the sensor.
5. For K = 4, the REMAKE values of table 2 equal Table 2 of reports 007 and
   013.
6. No eTraM val or test file was opened, and the annotation root was not
   listed. Nothing outside `results/fb/` changed under `results/`.

## 10. Outputs

| file | content |
|---|---|
| `results/fb/tuning.json` | `J`, `F` and `bits` for the nine configurations, per dataset and coder, and the frozen ones |
| `results/fb/per_recording.json` | for every reporting recording, coder and K, the output of `sum_groups` |
| `results/fb/report.json` | the tables of Sections 6 and 7 |
| `results/fb/provenance.json` | commit, host, versions, wall and CPU time, and the files read |

## 11. Files

SHA-256 of the file content, which is the text between the fence lines of
its appendix, ending in one newline.

| file | SHA-256 |
|---|---|
| `ec/fbc.py` | `8dc33f47894ee85c883ba09e7f194caad6caedfdaac4f85d04fa9a2d075c0885` |
| `ec/downstream.py` | `829a0cb74763ded238e23be570487cbadea94cb8283f40b789ac323456350cdd` |
| `tests/test_fbc_gate.py` | `fef11c34b305feb17fbf821c3f4004a6871480ecaf6d4d0572e9229338303afa` |

## Appendix A. `ec/fbc.py`

Normative. The executor commits this file unchanged.

```python
"""A flow-based predictive coder after [stumpp2024], as a baseline for REMAKE (directive 016).

The coder of [stumpp2024] (FBC) alternates a sending state and a predicting state. In the sending
state of length ST it transmits every event, and with every event whose optical flow is confident
it transmits the flow. In the predicting state of length PT it transmits only the events without a
confident flow. The receiver extrapolates every flow event along a straight line at its velocity
and places a predicted event at each pixel whose center lies within ``XI`` pixels of that line,
at the time of closest approach. ST is set to the time in which the mean of the first ``C_FIRST``
flow speeds moves one pixel.

This module keeps that structure and these constants. It differs in four points, which the
manuscript states:

flow       [stumpp2024] uses aperture-robust multi-scale flow (ARMS) per event. Here the flow is the
           local plane fit of [benosman2014] on the surface of active events: for each pixel and
           polarity, the latest event times of its (2 FIT_RADIUS + 1)^2 neighborhood within
           FIT_WINDOW_US before an evaluation instant are fitted by a plane t = a x + b y + c, and
           the flow is (a, b) / (a^2 + b^2). A fit is confident with at least FIT_MIN points, an
           rms residual of at most FIT_RES_US, and a speed between SPEED_MIN and FLOW_MAX px/s.
           Flows are evaluated at the end of the sending state, and for the predicting state at
           the end of each window.
groups     The two states fill one group of K windows of REMAKE: the sending state starts at the
           key window, ST is clipped to [ST_MIN_US, T0], and PT = K T0 - ST.
flows      One flow per pixel and polarity with a flow event in the sending state, two signed
           integers in px/s within 12 bits each, in raster order, coded as zigzag ULEB and
           Zstandard level 19. [stumpp2024] attaches 24 bits to every flow event.
coders     The events are coded per window with coder T or coder Q of ``ec.blockcodec`` (Q on the
           grid of the key events of REMAKE, one pixel and three bins per window), so that the
           baseline and REMAKE share their event coders.

``group_flows`` computes the sender's flows of a group once; ``encode_group`` writes the record of
one K and coder; ``reconstruct`` rebuilds every window of the group from the record alone;
``evaluate_group`` scores the reconstruction on the working grid as ``ec.blockcodec.evaluate_group``
scores REMAKE; ``sum_groups`` and ``summarize`` aggregate a recording and compare it with the subset
schemes of the same groups.
"""
from __future__ import annotations

import struct

import numpy as np

from . import blockcodec as bc

C_FIRST = 500
XI = 0.4
FLOW_MAX = 2047
FIT_RADIUS = 2
FIT_WINDOW_US = 50_000
FIT_MIN = 6
FIT_RES_US = 1000.0
SPEED_MIN = 1.0
ST_MIN_US = 1000
CHUNK = 20_000
REC = struct.Struct("<IB")          # ST in microseconds, coder


def plane_flow(t, x, y, p, t_end: int, width: int, height: int, radius: int = FIT_RADIUS, res_us: float = FIT_RES_US):
    """Flows at ``t_end`` from the events before it. Returns ``vx, vy`` (int px/s) and ``ok``, each (2, height, width)."""
    t, x, y, p = (np.asarray(a, dtype=np.int64) for a in (t, x, y, p))
    sel = (t < t_end) & (t >= t_end - FIT_WINDOW_US)
    S = np.full((2, height, width), np.nan)
    o = np.argsort(t[sel], kind="stable")
    S[p[sel][o], y[sel][o], x[sel][o]] = (t[sel][o] - t_end).astype(np.float64)   # latest event wins
    vx = np.zeros((2, height, width), dtype=np.int64)
    vy = np.zeros_like(vx)
    ok = np.zeros((2, height, width), dtype=bool)
    R = radius
    Yg, Xg = np.mgrid[0:height, 0:width].astype(np.float64)

    def box(A):
        P = np.zeros((height + 2 * R + 1, width + 2 * R + 1))
        P[R + 1:R + 1 + height, R + 1:R + 1 + width] = A
        C = P.cumsum(0).cumsum(1)
        k = 2 * R + 1
        return C[k:k + height, k:k + width] - C[:height, k:k + width] - C[k:k + height, :width] + C[:height, :width]

    for pol in (0, 1):
        V = ~np.isnan(S[pol])
        v = V.astype(np.float64)
        T = np.where(V, S[pol], 0.0)
        n = box(v); bX = box(v * Xg); bY = box(v * Yg)
        bT = box(T); bTX = box(T * Xg); bTY = box(T * Yg)
        acc = {"n": n, "x": bX - Xg * n, "y": bY - Yg * n, "t": bT,
               "xx": box(v * Xg * Xg) - 2 * Xg * bX + Xg * Xg * n,
               "yy": box(v * Yg * Yg) - 2 * Yg * bY + Yg * Yg * n,
               "xy": box(v * Xg * Yg) - Xg * bY - Yg * bX + Xg * Yg * n,
               "xt": bTX - Xg * bT, "yt": bTY - Yg * bT, "tt": box(T * T)}
        cand = V & (acc["n"] >= FIT_MIN)
        if not cand.any():
            continue
        g = {k: a[cand] for k, a in acc.items()}
        M = np.stack([np.stack([g["xx"], g["xy"], g["x"]], -1), np.stack([g["xy"], g["yy"], g["y"]], -1),
                      np.stack([g["x"], g["y"], g["n"]], -1)], -2)
        rhs = np.stack([g["xt"], g["yt"], g["t"]], -1)
        good = np.abs(np.linalg.det(M)) > 1e-9
        sol = np.zeros_like(rhs)
        sol[good] = np.linalg.solve(M[good], rhs[good][..., None])[..., 0]
        a, b, c = sol[:, 0], sol[:, 1], sol[:, 2]
        sse = g["tt"] - (a * g["xt"] + b * g["yt"] + c * g["t"])
        rms = np.sqrt(np.maximum(sse, 0.0) / g["n"])
        g2 = a * a + b * b
        with np.errstate(divide="ignore", invalid="ignore"):
            fx, fy = 1e6 * a / g2, 1e6 * b / g2                                 # px/s
        speed = np.hypot(fx, fy)
        conf = good & (g2 > 0) & (rms <= res_us) & (speed >= SPEED_MIN) & \
            (np.abs(fx) <= FLOW_MAX) & (np.abs(fy) <= FLOW_MAX)
        iy, ix = np.nonzero(cand)
        ok[pol, iy[conf], ix[conf]] = True
        vx[pol, iy[conf], ix[conf]] = np.rint(fx[conf]).astype(np.int64)
        vy[pol, iy[conf], ix[conf]] = np.rint(fy[conf]).astype(np.int64)
    return vx, vy, ok


def _zz(v):
    v = np.asarray(v, dtype=np.int64)
    return (v << 1) ^ (v >> 63)


def _unzz(u):
    u = np.asarray(u, dtype=np.int64)
    return (u >> 1) ^ -(u & 1)


def _code(coder, t_rel, x, y, p, width, height):
    if coder == "T":
        return bc.encode_events_T(t_rel, x, y, p)
    return bc.encode_events_Q(t_rel, x, y, p, bc.Q_KEY, width, height)


def _decode(coder, buf, width, height):
    if coder == "T":
        return bc.decode_events_T(buf)
    return bc.decode_events_Q(buf, bc.Q_KEY, width, height)


def _pack(parts):
    return b"".join(bc.uleb_encode([len(b)]) + b for b in parts)


def _unpack(buf, n):
    out, pos = [], 0
    for _ in range(n):
        (L,), pos = bc.uleb_decode(buf, 1, pos)
        out.append(buf[pos:pos + int(L)])
        pos += int(L)
    return out


def group_flows(t, x, y, p, w: int, width: int, height: int, radius: int = FIT_RADIUS, res_us: float = FIT_RES_US,
                n_windows: int = 1 + bc.N_TARGETS, T0_us: int = bc.T0_US) -> dict:
    """The sender's flows for the group keyed at window ``w``, shared by every K and coder: ST, the flows at the
    end of the sending state, and the flows at the end of each window m = 0 .. n_windows - 1."""
    t, x, y, p = (np.asarray(a, dtype=np.int64) for a in (t, x, y, p))
    w0 = w * T0_us
    win = [plane_flow(t, x, y, p, w0 + (m + 1) * T0_us, width, height, radius, res_us) for m in range(n_windows)]
    vx, vy, ok = win[0]
    first = (t >= w0) & (t < w0 + T0_us)
    fl = ok[p[first], y[first], x[first]]
    sp = np.hypot(vx[p[first], y[first], x[first]], vy[p[first], y[first], x[first]])[fl][:C_FIRST]
    st = int(np.clip(np.rint(1e6 / sp.mean()), ST_MIN_US, T0_us)) if sp.size else T0_us
    send = win[0] if st == T0_us else plane_flow(t, x, y, p, w0 + st, width, height, radius, res_us)
    return {"w": int(w), "st_us": st, "send": send, "windows": win}


def encode_group(t, x, y, p, w: int, K: int, width: int, height: int, coder: str, flows: dict,
                 T0_us: int = bc.T0_US) -> bytes:
    """The record of the group keyed at window ``w`` with ``flows`` of ``group_flows``. ``t`` must be nondecreasing."""
    t, x, y, p = (np.asarray(a, dtype=np.int64) for a in (t, x, y, p))
    w0 = w * T0_us
    st = flows["st_us"]
    s_end = w0 + st
    vx, vy, ok = flows["send"]
    snd = (t >= w0) & (t < s_end)
    has = np.zeros(len(t), dtype=bool)
    has[snd] = ok[p[snd], y[snd], x[snd]]
    flow_ev = snd & has
    keys = np.unique((p[flow_ev] * height + y[flow_ev]) * width + x[flow_ev])
    kp, rem = keys // (height * width), keys % (height * width)
    ky, kx = rem // width, rem % width
    fv = np.stack([vx[kp, ky, kx], vy[kp, ky, kx]], -1).reshape(-1)
    parts = [REC.pack(st, 0 if coder == "T" else 1),
             _code(coder, t[flow_ev] - w0, x[flow_ev], y[flow_ev], p[flow_ev], width, height),
             bc._zstd(bc.uleb_encode(np.concatenate(([len(keys)], _zz(fv)))), 19)]
    for m in range(K):
        a, b = w0 + m * T0_us, w0 + (m + 1) * T0_us
        sel = (t >= a) & (t < b)
        plain = sel & snd & ~has if m == 0 else np.zeros(len(t), dtype=bool)
        pred_part = sel & (t >= s_end)
        if pred_part.any():
            fok = flows["windows"][m][2]
            plain |= pred_part & ~fok[p, y, x]
        parts.append(_code(coder, t[plain] - a, x[plain], y[plain], p[plain], width, height))
    return _pack(parts)


def _predict(t, x, y, p, vx, vy, t_from, t_to, width, height):
    """Events predicted from flow events (px/s) at pixel centers within XI of each straight path, in [t_from, t_to)."""
    outs = []
    for c0 in range(0, len(t), CHUNK):
        sl = slice(c0, c0 + CHUNK)
        ts, xs, ys, ps = t[sl].astype(np.float64), x[sl].astype(np.float64), y[sl].astype(np.float64), p[sl]
        ux, uy = vx[sl] * 1e-6, vy[sl] * 1e-6                               # px/us
        sp = np.hypot(ux, uy)
        d0 = sp * np.maximum(t_from - ts, 0.0)
        d1 = sp * (t_to - ts)
        n = np.ceil(2 * (d1 - d0)).astype(np.int64) + 2
        idx = np.repeat(np.arange(len(ts)), n)
        step = np.arange(n.sum()) - np.repeat(np.cumsum(n) - n, n)
        dist = d0[idx] + 0.5 * step
        tau = dist / np.where(sp[idx] > 0, sp[idx], 1.0)
        px, py = xs[idx] + ux[idx] * tau, ys[idx] + uy[idx] * tau
        for ox in (0, 1):
            for oy in (0, 1):
                cx, cy = np.floor(px) + ox, np.floor(py) + oy
                rx, ry = cx - xs[idx], cy - ys[idx]
                s2 = sp[idx] ** 2
                tm = (rx * ux[idx] + ry * uy[idx]) / np.where(s2 > 0, s2, 1.0)
                ex, ey = rx - ux[idx] * tm, ry - uy[idx] * tm
                tt = ts[idx] + tm
                keep = (np.hypot(ex, ey) < XI) & (tt >= t_from) & (tt < t_to) & \
                    (cx >= 0) & (cx < width) & (cy >= 0) & (cy < height)
                outs.append(np.stack([idx[keep] + c0, cx[keep], cy[keep], tt[keep], ps[idx[keep]]], -1))
    if not outs:
        z = np.zeros(0, dtype=np.int64)
        return z, z, z, z
    a = np.concatenate(outs)
    a = a[np.lexsort((a[:, 3], a[:, 2], a[:, 1], a[:, 0]))]
    first = np.ones(len(a), dtype=bool)
    first[1:] = np.any(a[1:, :3] != a[:-1, :3], axis=1)                       # one event per source and pixel
    a = a[first]
    return np.floor(a[:, 3]).astype(np.int64), a[:, 1].astype(np.int64), a[:, 2].astype(np.int64), a[:, 4].astype(np.int64)


def reconstruct(record: bytes, w: int, K: int, width: int, height: int, T0_us: int = bc.T0_US):
    """Events ``(t_us, x, y, p)`` of each window m = 0 .. K - 1 of the group, from the record alone."""
    parts = _unpack(record, 3 + K)
    st, cflag = REC.unpack(parts[0])
    coder = "T" if cflag == 0 else "Q"
    w0 = w * T0_us
    s_end, end = w0 + st, w0 + K * T0_us
    ft, fx, fy, fp = _decode(coder, parts[1], width, height)
    ft = ft + w0
    v, _ = bc.uleb_decode(bc._unzstd(parts[2])) if parts[2] else (np.array([0]), 0)
    nk = int(v[0])
    fl = _unzz(np.asarray(v[1:1 + 2 * nk])).reshape(-1, 2) if nk else np.zeros((0, 2), dtype=np.int64)
    keys = np.unique((fp * height + fy) * width + fx)
    if len(keys) != nk:
        raise ValueError("fbc: flow count does not match the flow events")
    j = np.searchsorted(keys, (fp * height + fy) * width + fx)
    pt, px, py, pp = _predict(ft, fx, fy, fp, fl[j, 0], fl[j, 1], s_end, end, width, height)
    out = []
    for m in range(K):
        a, b = w0 + m * T0_us, w0 + (m + 1) * T0_us
        qt, qx, qy, qp = _decode(coder, parts[3 + m], width, height)
        T = [qt + a]; X = [qx]; Y = [qy]; P = [qp]
        if m == 0:
            T.append(ft); X.append(fx); Y.append(fy); P.append(fp)
        sel = (pt >= a) & (pt < b)
        T.append(pt[sel]); X.append(px[sel]); Y.append(py[sel]); P.append(pp[sel])
        out.append(tuple(np.concatenate(z).astype(np.int64) for z in (T, X, Y, P)))
    return out


def evaluate_group(t, x, y, p, w: int, width: int, height: int, Ks=bc.GROUPS, coders=bc.CODERS,
                   radius: int = FIT_RADIUS, res_us: float = FIT_RES_US, T0_us: int = bc.T0_US) -> dict:
    """For every K and coder, keyed ``<coder>_K<K>``: bytes of the record and, per window of the decoded
    reconstruction, ``n_rec``, ``n_true`` and ``match`` on the working grid, with the group fidelity ``F``."""
    t, x, y, p = (np.asarray(a, dtype=np.int64) for a in (t, x, y, p))
    flows = group_flows(t, x, y, p, w, width, height, radius, res_us, max(Ks), T0_us)
    w0 = w * T0_us
    truths, n_true = [], []
    for m in range(max(Ks)):
        a, b = w0 + m * T0_us, w0 + (m + 1) * T0_us
        sel = (t >= a) & (t < b)
        truths.append(bc.Truth(t[sel], x[sel], y[sel], p[sel], a, T0_us))
        n_true.append(int(sel.sum()))
    out = {"w": int(w), "st_us": flows["st_us"], "radius": int(radius), "res_us": float(res_us)}
    for coder in coders:
        for K in Ks:
            rec = encode_group(t, x, y, p, w, K, width, height, coder, flows, T0_us)
            windows = reconstruct(rec, w, K, width, height, T0_us)
            n_rec = [int(len(r[0])) for r in windows]
            match = [truths[m].match(*windows[m], bc.OBJECTIVE) for m in range(K)]
            den = sum(n_rec) + sum(n_true[:K])
            out[f"{coder}_K{K}"] = {"bytes": len(rec), "n_rec": n_rec, "n_true": n_true[:K], "match": match,
                                    "F": 2.0 * sum(match) / den if den else 0.0}
    return out


def sum_groups(groups, key: str) -> dict:
    """Sum of the entries ``key`` (``<coder>_K<K>``) of several outputs of ``evaluate_group``."""
    rows = [g[key] for g in groups]
    return {"bytes": int(sum(r["bytes"] for r in rows)),
            "n_rec": np.sum([r["n_rec"] for r in rows], axis=0).astype(np.int64).tolist(),
            "n_true": np.sum([r["n_true"] for r in rows], axis=0).astype(np.int64).tolist(),
            "match": np.sum([r["match"] for r in rows], axis=0).astype(np.int64).tolist(),
            "n_groups": len(rows)}


def summarize(fb: dict, g: dict, coder: str, K: int, config: str = "B20_rho1.0") -> dict:
    """Fidelity, bits and gains of the baseline over the same groups as ``g``, the output of
    ``ec.blockcodec.sum_groups`` for REMAKE. The subset schemes are those of ``ec.blockcodec.summarize``
    for ``config``: ``bits_base`` is their envelope at the share ``F / (2 - F)``, ``gain_sub`` = bits_base
    / bits. Raises if the true events of the two sums differ."""
    n = float(np.sum(g["n_true"][:K]))
    if int(np.sum(fb["n_true"])) != int(n):
        raise ValueError("fbc.summarize: the groups of the two sums differ")
    F = 2.0 * float(np.sum(fb["match"])) / (float(np.sum(fb["n_rec"])) + n)
    q_eq = F / (2.0 - F)
    bits = 8.0 * fb["bytes"] / n
    direct = float(np.sum(g["direct"][coder][:K])) / n

    def points(rows):
        return ([float(np.sum(v["n_kept"][:K])) / n for v in rows] + [1.0],
                [float(np.sum(v[coder][:K])) / n for v in rows] + [direct])

    thin_pts = points([g["thin"][str(chi)] for chi in bc.THIN_SHARES])
    side = config.split("_")[0] + "_"
    sel_pts = points([v for k, v in g["select"].items() if k.startswith(side)])
    base = bc.baseline_bits(q_eq, thin_pts[0] + sel_pts[0], thin_pts[1] + sel_pts[1])
    return {"F": F, "q_eq": q_eq, "bits": bits, "bits_direct": direct, "bits_base": base,
            "gain_sub": base / bits if bits > 0 else float("nan")}
```

## Appendix B. `ec/downstream.py`

Normative. The executor commits this file unchanged.

```python
"""Two tasks on rebuilt events that need no trained model (directive 016).

objects   For an annotated box and a window, the events of the window inside the box, true and
          rebuilt. ``box_scores`` returns their counts, the fidelity of Eq. (fid) inside the box on
          the working grid, and the distance in pixels between the centroids of the two sets, or
          NaN when the rebuilt set is empty.

motion    The velocity of the events of a square region in one window, by contrast maximization
          [gallego2018cmax]: the events are warped to the start of the window along a candidate
          velocity, counted per pixel, and the velocity whose image has the largest variance is
          taken. The search is a grid of step CMAX_COARSE over [-CMAX_VMAX, CMAX_VMAX]^2 px/ms,
          then of step CMAX_FINE within one coarse step of the best point. ``cmax_velocity``
          uses at most CMAX_EVENTS events, every k-th in time order. The error of a rebuilt set is
          the length of the difference between its velocity and that of the true events, times
          T0, in pixels per window.
"""
from __future__ import annotations

import numpy as np

from . import blockcodec as bc

CMAX_VMAX = 0.6          # px/ms
CMAX_COARSE = 0.1
CMAX_FINE = 0.02
CMAX_EVENTS = 4000
CMAX_MARGIN = 20         # px around the region in the warped image


def box_scores(true, rec, box, w0_us: int, T0_us: int = bc.T0_US) -> dict:
    """``true``, ``rec``: (t_us, x, y, p) of one window starting at ``w0_us``. ``box`` = (x0, y0, w, h)."""
    x0, y0, w, h = box
    def inside(ev):
        t, x, y, p = ev
        s = (x >= x0) & (x < x0 + w) & (y >= y0) & (y < y0 + h)
        return t[s], x[s], y[s], p[s]
    tt, tx, ty, tp = inside(true)
    rt, rx, ry, rp = inside(rec)
    m = bc.Truth(tt, tx, ty, tp, w0_us, T0_us).match(rt, rx, ry, rp, bc.OBJECTIVE)
    den = len(tt) + len(rt)
    err = float(np.hypot(rx.mean() - tx.mean(), ry.mean() - ty.mean())) if len(rt) and len(tt) else float("nan")
    return {"n_true": int(len(tt)), "n_rec": int(len(rt)), "F": 2.0 * m / den if den else float("nan"),
            "centroid_px": err}


def _subsample(t, x, y):
    if len(t) <= CMAX_EVENTS:
        return t, x, y
    k = int(np.ceil(len(t) / CMAX_EVENTS))
    o = np.argsort(t, kind="stable")[::k]
    return t[o], x[o], y[o]


def _variance(t_ms, x, y, vx, vy, box):
    x0, y0, w, h = box
    nx, ny = w + 2 * CMAX_MARGIN, h + 2 * CMAX_MARGIN
    wx = np.rint(x - vx * t_ms).astype(np.int64) - (x0 - CMAX_MARGIN)
    wy = np.rint(y - vy * t_ms).astype(np.int64) - (y0 - CMAX_MARGIN)
    keep = (wx >= 0) & (wx < nx) & (wy >= 0) & (wy < ny)
    img = np.bincount(wy[keep] * nx + wx[keep], minlength=nx * ny).astype(np.float64)
    return img.var()


def cmax_velocity(ev, box, w0_us: int):
    """Velocity (px/ms) of the events ``ev`` = (t_us, x, y, p) inside ``box``, warped to ``w0_us``. NaNs without events."""
    t, x, y, _ = ev
    x0, y0, w, h = box
    s = (x >= x0) & (x < x0 + w) & (y >= y0) & (y < y0 + h)
    if not s.any():
        return np.array([np.nan, np.nan])
    t, x, y = _subsample(np.asarray(t[s]), np.asarray(x[s]), np.asarray(y[s]))
    tm = (t - w0_us) / 1000.0
    best, bv = -1.0, (0.0, 0.0)
    g = np.arange(-CMAX_VMAX, CMAX_VMAX + 1e-9, CMAX_COARSE)
    for vx in g:
        for vy in g:
            f = _variance(tm, x, y, vx, vy, box)
            if f > best:
                best, bv = f, (vx, vy)
    f0 = np.arange(-CMAX_COARSE, CMAX_COARSE + 1e-9, CMAX_FINE)
    cx, cy = bv
    for dx in f0:
        for dy in f0:
            f = _variance(tm, x, y, cx + dx, cy + dy, box)
            if f > best:
                best, bv = f, (cx + dx, cy + dy)
    return np.array(bv)


def motion_error_px(true, rec, box, w0_us: int, T0_us: int = bc.T0_US) -> float:
    """Length of the velocity difference times T0, in pixels per window; NaN if a set is empty in the box."""
    vt = cmax_velocity(true, box, w0_us)
    vr = cmax_velocity(rec, box, w0_us)
    if np.isnan(vt).any() or np.isnan(vr).any():
        return float("nan")
    return float(np.hypot(*(vr - vt)) * T0_us / 1000.0)
```

## Appendix C. `tests/test_fbc_gate.py`

Normative. The executor commits this file unchanged.

```python
"""Gate for directive 016: the flow-based baseline and the two downstream tasks, on synthetic events.

Parallel straight edges move across a small sensor at a known speed. Each pixel emits n events per
passage with a uniform phase and Gaussian jitter. The motion task uses the textured translation of
``ec.synth``, because straight edges leave the velocity along them undetermined. The tolerances are
fixed by the director.
"""
import numpy as np

from ec import blockcodec as bc
from ec import downstream as ds
from ec import fbc
from ec import synth

W, H, U, N, TAU = 320, 240, 200.0, 3, 2000


def edges(seed=0, jitter=100.0):
    rng = np.random.default_rng(seed)
    XX, YY = np.meshgrid(np.arange(W), np.arange(H))
    T, X, Y = [], [], []
    for x0 in np.arange(-200, W, 40):
        tp = (XX - x0) / U * 1e6
        ph = rng.random(XX.shape) * TAU
        for j in range(N):
            tt = tp + ph + j * TAU + rng.normal(0, jitter, XX.shape)
            s = (tt > 0) & (tt < 1e6)
            T.append(tt[s]); X.append(XX[s]); Y.append(YY[s])
    t = np.rint(np.concatenate(T)).astype(np.int64)
    o = np.argsort(t, kind="stable")
    return t[o], np.concatenate(X)[o], np.concatenate(Y)[o], np.zeros(len(t), dtype=np.int64)


def test_plane_flow_recovers_the_speed():
    t, x, y, p = edges()
    vx, vy, ok = fbc.plane_flow(t, x, y, p, 300_000, W, H, radius=4)
    assert ok.sum() > 10_000
    assert abs(np.median(vx[ok]) - U) < 0.05 * U and abs(np.median(vy[ok])) < 5


def test_record_is_decodable_and_deterministic():
    t, x, y, p = edges()
    fl = fbc.group_flows(t, x, y, p, 6, W, H, radius=4)
    for coder in bc.CODERS:
        r1 = fbc.encode_group(t, x, y, p, 6, 4, W, H, coder, fl)
        r2 = fbc.encode_group(t, x, y, p, 6, 4, W, H, coder, fl)
        assert r1 == r2
        win = fbc.reconstruct(r1, 6, 4, W, H)
        assert len(win) == 4 and all(len(w[0]) > 0 for w in win)
        for m, (rt, rx, ry, rp) in enumerate(win):
            a = (6 + m) * bc.T0_US
            assert rt.min() >= a and rt.max() < a + bc.T0_US
            assert rx.min() >= 0 and rx.max() < W and ry.min() >= 0 and ry.max() < H


def test_baseline_saves_bits_and_keeps_fidelity_on_edges():
    t, x, y, p = edges()
    r = fbc.evaluate_group(t, x, y, p, 6, W, H, Ks=(4,), coders=("T",), radius=4)["T_K4"]
    w0 = 6 * bc.T0_US
    direct = 0
    for m in range(4):
        a = w0 + m * bc.T0_US
        s = (t >= a) & (t < a + bc.T0_US)
        direct += len(bc.encode_events_T(t[s] - a, x[s], y[s], p[s]))
    assert r["bytes"] < 0.5 * direct
    assert r["F"] > 0.55


def test_downstream_tasks():
    sc_ = synth.rigid_translation(width=W, height=H, n_points=1500, box_wh=(60, 40), c0=(60, 120),
                                  v=(200.0, -80.0), duration_s=1.0, jitter_us=200, seed=1)
    w0 = 6 * bc.T0_US
    s = (sc_.t >= w0) & (sc_.t < w0 + bc.T0_US)
    ev = (sc_.t[s], sc_.x[s].astype(np.int64), sc_.y[s].astype(np.int64), sc_.p[s].astype(np.int64))
    box = (60, 60, 120, 120)
    v = ds.cmax_velocity(ev, box, w0)
    assert abs(v[0] - 0.2) <= 0.02 and abs(v[1] + 0.08) <= 0.02
    sc = ds.box_scores(ev, ev, box, w0)
    assert sc["F"] == 1.0 and sc["centroid_px"] == 0.0
    shifted = (ev[0], ev[1] + 4, ev[2], ev[3])
    assert ds.box_scores(ev, shifted, box, w0)["centroid_px"] > 3.0
    assert ds.motion_error_px(ev, shifted, box, w0) < 1.0
```
