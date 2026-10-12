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
