"""Operating points of six families of schemes on the same groups, four candidate fidelities, and the
downstream tasks at every point (directive 018).

Families. Every scheme codes the events of a group of K windows and returns, per window, the events the
receiver rebuilds. All event coders are coder Q of ``ec.blockcodec``.

remake     The kept records ``<model>_Q_K<K>`` of configuration (20, 1), decoded and rebuilt by
           ``ec.blockcodec.reconstruct``; models affine (``remake``), ``translation`` and ``static``.
thin       In every window, each event independently with probability ``chi`` (THIN_SHARES), drawn with
           ``np.random.default_rng(SEED + w + m)`` as in directive 016; coded on the working grid.
select     In every window, the events of the blocks of side B that hold at least
           ``ec.blockcodec.threshold(B, rho)`` events of that window (SELECT_RHOS); coded on the working grid.
cap        In every window and every block of side B, at most ``n`` events (CAPS), evenly spaced in the
           time order of the block: the events of rank ``floor((j + 1/2) N_b / n)``, j = 0 .. n - 1, among
           the ``N_b`` events of the block, and all of them if ``N_b <= n``; coded on the working grid. ``cap`` is the subset that a per-block logarithmic fidelity (``F_log``) prefers.
hevc       The voxel counts of the working grid as video: one frame per time bin (three per window,
           3 K frames per group), the two polarities side by side, luma ``16 min(c, 15)``, chroma 128.
           Coded by x265 through ffmpeg at a constant QP (HEVC_QPS) with one intra frame at the start
           of the group and P frames after it (HEVC_PARAMS), decoded by ffmpeg, and read back as
           ``clip(floor((Y + 8) / 16), 0, 15)`` events per voxel at the origin of the voxel, as coder Q
           decodes. The QP is that of the P frames; x265 gives the intra frame its default offset. The bits
           are those of the NAL units other than parameter sets and SEI (``nal_bits``); the parameter sets
           are reported separately, as the 28-byte stream header of REMAKE is.
fbc        The flow-based baseline of directive 016 (``ec.fbc``) with its events without flow coded on
           the working grid instead of the grid of one pixel. Its flow events stay on the grid of one
           pixel, because the receiver extrapolates them from their pixel. Configurations FBC_CONFIGS:
           the one frozen in directive 016, (4, 500), and eight that predict more.

Candidate fidelities, each additive over windows (sums are kept per window). For one window, with
``c`` and ``c'`` the true and rebuilt counts of a voxel, ``N`` and ``N'`` the two numbers of events:

F          ``2 sum min(c, c') / (N + N')`` on the working grid, Eq. (fid) of the manuscript.
F20        the same on blocks of B pixels and one bin per window.
FH         ``2 sum sqrt(c c') / (N + N')`` on cells of 8 pixels and one bin per window: the Hellinger
           affinity of the two count fields, which weighs counts as a Poisson observation does.
Fsnr       per block b of side B and window: ``N_b``, ``N'_b`` the events in the block and ``M_b`` the
           matched events of its voxels on the working grid. With the background ``phi`` of the group in
           events per block and window and its upper Poisson quantile
           ``theta = F^-1_Poisson(phi)(1 - ALPHA)`` (``background_rate``), a block enters if
           ``N_b > theta`` or ``N'_b > theta``: either field holds more than the background alone exceeds
           with probability ALPHA. Over the blocks that enter, with ``l(n) = ln(1 + n / phi)``,
           ``D_b = l(N_b) + l(N'_b) - 2 l(M_b)`` and ``Fsnr = 1 - sum D_b / sum (l(N_b) + l(N'_b))``.
           The value of a block is the logarithm of one plus its count in units of the background, so
           blocks that hold only background do not count, and a block loses its value in proportion to
           the logarithm of the share it keeps, not to the number of events. A subset loses most in the
           blocks it empties, and the subset with the best ``Fsnr`` at a given number of events keeps a
           similar number in every block that enters, which is ``cap``.

Background. ``background_rate`` estimates the rate ``beta`` of background events per pixel and second
from the events that the sender holds before the targets, ``[w T0 - ec.fbc.FIT_WINDOW_US, (w + 1) T0)``,
without hot pixels: a pixel is hot if its events in the span reach HOT_MIN and HOT_FACTOR times the
median over the pixels with events. Two estimates are formed, each unbiased under its own assumption
and too large when that assumption fails:

isolation  An event is isolated if none of the eight pixels around it has an event of the same polarity
           within ISO_TAU_US of it, the neighborhood of the background filter of [verma2024etram]. An
           event of a Poisson background of rate ``beta`` per pixel, half of each polarity, is isolated
           with probability ``exp(-8 beta tau)``; events of a moving edge have neighbors and are not,
           unless the edge moves slower than one pixel per ``tau``. Counting only the events at least
           ``tau`` from both ends of the span, with ``r`` the isolated ones per pixel and second,
           ``beta`` solves ``r = beta exp(-8 beta tau)``, which has two roots below
           ``r_max = 1 / (8 e tau)``: ``-W_k(-8 tau r) / (8 tau)`` with the branches k = 0 and -1 of
           Lambert W. ``beta_iso`` is the smaller root, or the larger one if ``beta_med`` (below), an
           upper bound, exceeds ``1 / (8 tau)``. At ``r >= r_max``, ``saturated`` flags the group and
           ``beta_iso = 1 / (8 tau)``.
quiet      ``beta_med``: the median over the blocks of the sensor of their events per pixel and second.
           It is the background where most blocks hold only background, as for a static camera.

``beta = min(beta_iso, beta_med)``. The background of a block and window is
``phi = max(1, beta B^2 T0)``: a background below one event cannot be resolved.

``evaluate_group`` runs every scheme of a group, keeps the sums and the bits for K = 4 and 11, and runs the
two tasks of ``ec.downstream`` on windows 1 to 3 of K = 4, one scheme at a time.
"""
from __future__ import annotations

import os
import subprocess
import tempfile

import numpy as np

from scipy.special import lambertw
from scipy.stats import poisson

from . import blockcodec as bc
from . import downstream as dn
from . import fbc

T0 = bc.T0_US
GRID = bc.OBJECTIVE                       # (2 px, 3 bins per window)
B = 20
CONFIG = "B20_rho1.0"
KS = (4, 11)
N_WIN = 11
SEED = 20261016
THIN_SHARES = (0.03, 0.06, 0.1, 0.15, 0.2, 0.3, 0.5, 0.75)
SELECT_RHOS = (1 / 16, 1 / 8, 1 / 4, 1 / 2, 1.0, 2.0, 4.0)
CAPS = (1, 2, 4, 8, 16, 32, 64, 128)
HEVC_QPS = (14, 20, 24, 28, 32, 36, 40, 46)
HEVC_SCALE, HEVC_MAX = 16, 15
HEVC_PRESET = "slow"
HEVC_PARAMS = ("bframes=0:scenecut=0:open-gop=0:aq-mode=0:psy-rd=0:psy-rdoq=0:info=0:"
               "frame-threads=1:pools=none:log-level=error")
FBC_CONFIGS = ((4, 500),) + tuple((r, s) for r in (2, 3) for s in (2000, 5000, 10000, 20000))
REMAKE_MODELS = (("remake", "affine"), ("translation", "translation"), ("static", "static"))
ISO_TAU_US = 10_000
ALPHA = 1e-3
HOT_MIN, HOT_FACTOR = 10, 20
HELL_CELL = (8, 1)
BLOCK_CELL = (B, 1)
MIN_BOX_EVENTS = 50
NAL_SKIP = (32, 33, 34, 39, 40)           # VPS, SPS, PPS, prefix and suffix SEI


def scheme_names():
    return ([s for s, _ in REMAKE_MODELS] + [f"thin_{c}" for c in THIN_SHARES]
            + [f"select_{float(r)}" for r in SELECT_RHOS] + [f"cap_{n}" for n in CAPS]
            + [f"hevc_{q}" for q in HEVC_QPS] + [f"fbc_r{r}_res{s}" for r, s in FBC_CONFIGS])


# ----------------------------------------------------------------------------------------------
# voxels and candidate fidelities

def voxels(ev, w0: int, cell, width: int, height: int):
    """Sorted voxel keys and counts of events ``ev`` = (t_us, x, y, p) of the window starting at ``w0``."""
    t, x, y, p = (np.asarray(a, dtype=np.int64) for a in ev)
    s, k = cell
    nx, ny = -(-width // s), -(-height // s)
    key = ((p * k + bc.time_bin(t - w0, k)) * ny + y // s) * nx + x // s
    return np.unique(key, return_counts=True)


def block_counts(x, y, width: int, height: int):
    nbx, nby = -(-width // B), -(-height // B)
    return np.bincount((np.asarray(y, dtype=np.int64) // B) * nbx + np.asarray(x, dtype=np.int64) // B,
                       minlength=nbx * nby).astype(np.float64)


def background_rate(ev, lo_us: int, hi_us: int, width: int, height: int) -> dict:
    """The background of the events ``ev`` in ``[lo_us, hi_us)``: ``beta`` per pixel and second, ``phi`` and ``theta``."""
    t, x, y, p = (np.asarray(a, dtype=np.int64) for a in ev)
    sel = (t >= lo_us) & (t < hi_us)
    t, x, y, p = t[sel] - lo_us, x[sel], y[sel], p[sel]
    span = int(hi_us - lo_us)
    pix = y * width + x
    cnt = np.bincount(pix, minlength=width * height)
    med = float(np.median(cnt[cnt > 0])) if (cnt > 0).any() else 0.0
    hot = cnt >= max(HOT_MIN, HOT_FACTOR * med)
    keep = ~hot[pix]
    t, x, y, p = t[keep], x[keep], y[keep], p[keep]
    n_px = width * height - int(hot.sum())
    # isolation
    T = span + 2 * ISO_TAU_US + 2                     # larger than any time offset plus the reach
    key = ((p * height + y) * width + x) * T + t
    K = np.sort(key)
    has = np.zeros(len(t), dtype=bool)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            nx_, ny_ = x + dx, y + dy
            ok = (nx_ >= 0) & (nx_ < width) & (ny_ >= 0) & (ny_ < height)
            base = ((p * height + ny_) * width + nx_) * T
            a = np.searchsorted(K, base + np.maximum(t - ISO_TAU_US, 0), side="left")
            b = np.searchsorted(K, base + np.minimum(t + ISO_TAU_US, T - 1), side="right")
            has |= ok & (b > a)
    inner = (t >= ISO_TAU_US) & (t < span - ISO_TAU_US)
    n_iso = int((inner & ~has).sum())
    inner_s = max(span - 2 * ISO_TAU_US, 0) * 1e-6
    r = n_iso / (n_px * inner_s) if inner_s > 0 and n_px > 0 else 0.0
    tau = ISO_TAU_US * 1e-6
    # quiet blocks
    nbx, nby = -(-width // B), -(-height // B)
    bcnt = np.bincount((y // B) * nbx + x // B, minlength=nbx * nby)
    beta_med = float(np.median(bcnt)) / (B * B * span * 1e-6) if span > 0 else 0.0
    saturated = bool(r >= 1.0 / (8.0 * np.e * tau))
    branch = -1 if beta_med > 1.0 / (8.0 * tau) else 0
    beta_iso = 1.0 / (8.0 * tau) if saturated else \
        (float(-lambertw(-8.0 * tau * r, branch).real / (8.0 * tau)) if r > 0 else 0.0)
    beta = min(beta_iso, beta_med)
    phi = max(1.0, beta * B * B * T0 * 1e-6)
    theta = float(poisson.isf(ALPHA, phi))            # smallest k with P(Poisson(phi) > k) <= ALPHA
    return {"beta_per_px_s": float(beta), "beta_iso": float(beta_iso), "beta_med": beta_med, "branch": branch,
            "saturated": saturated,
            "near_saturation": bool(r >= 0.9 / (8.0 * np.e * tau)), "n_hot": int(hot.sum()), "n_iso": n_iso,
            "n": int(len(t)), "span_us": span, "phi": float(phi), "theta": theta}


class TrueWindow:
    """The true events of one window, with their voxel counts cached per grid."""

    def __init__(self, ev, w0: int, width: int, height: int, phi: float = 1.0, theta: float = 0.0):
        self.ev = tuple(np.asarray(a, dtype=np.int64) for a in ev)
        self.w0, self.width, self.height, self.n = int(w0), width, height, int(len(self.ev[0]))
        self.phi, self.theta = float(phi), float(theta)
        self._v = {}
        self.blocks = block_counts(self.ev[1], self.ev[2], width, height)

    def vox(self, cell):
        if cell not in self._v:
            self._v[cell] = voxels(self.ev, self.w0, cell, self.width, self.height)
        return self._v[cell]


def _common(a, b):
    ka, ca = a
    kb, cb = b
    com, i, j = np.intersect1d(ka, kb, assume_unique=True, return_indices=True)
    return com, ca[i].astype(np.float64), cb[j].astype(np.float64)


def window_sums(tw: TrueWindow, rec) -> dict:
    """The sums of the candidate fidelities for the rebuilt events ``rec`` of the window ``tw``."""
    W, H = tw.width, tw.height
    rec = tuple(np.asarray(a, dtype=np.int64) for a in rec)
    out = {"N": tw.n, "N2": int(len(rec[0]))}
    com, c, c2 = _common(tw.vox(GRID), voxels(rec, tw.w0, GRID, W, H))
    mm = np.minimum(c, c2)
    out["M"] = int(mm.sum())
    _, c, c2 = _common(tw.vox(BLOCK_CELL), voxels(rec, tw.w0, BLOCK_CELL, W, H))
    out["M20"] = int(np.minimum(c, c2).sum())
    _, c, c2 = _common(tw.vox(HELL_CELL), voxels(rec, tw.w0, HELL_CELL, W, H))
    out["H"] = float(2.0 * np.sqrt(c * c2).sum())
    s, k = GRID
    nx, ny = -(-W // s), -(-H // s)
    vx, vy = (com % nx) * s, ((com // nx) % ny) * s
    nbx, nby = -(-W // B), -(-H // B)
    bM = np.bincount((vy // B) * nbx + vx // B, weights=mm, minlength=nbx * nby)
    bN, bN2 = tw.blocks, block_counts(rec[1], rec[2], W, H)
    enter = (bN > tw.theta) | (bN2 > tw.theta)
    lN, lN2, lM = (np.log1p(v[enter] / tw.phi) for v in (bN, bN2, bM))
    out["Dsnr"] = float((lN + lN2 - 2.0 * lM).sum())
    out["Lsnr"] = float((lN + lN2).sum())
    return out


def fidelities(sums) -> dict:
    """The four candidates over a list of window sums."""
    a = {k: float(sum(s[k] for s in sums)) for k in sums[0]}
    den = a["N"] + a["N2"]
    out = {"F": 2.0 * a["M"] / den if den else 0.0, "F20": 2.0 * a["M20"] / den if den else 0.0,
           "FH": a["H"] / den if den else 0.0}
    L = a["Lsnr"]
    out["Fsnr"] = min(1.0, max(0.0, 1.0 - a["Dsnr"] / L)) if L > 0 else 0.0
    return out


# ----------------------------------------------------------------------------------------------
# subsets of one window

def thin_mask(n: int, chi: float, w: int, m: int):
    return np.random.default_rng(SEED + w + m).random(n) < chi


def select_mask(x, y, rho: float, width: int):
    bid = bc.block_ids(x, y, B, width)
    ids, cnt = np.unique(bid, return_counts=True)
    return np.isin(bid, ids[cnt >= bc.threshold(B, rho)])


def cap_mask(x, y, n: int, width: int):
    """At most ``n`` events per block: ranks ``floor((j + 1/2) N_b / n)`` in the order of the events (their time order)."""
    bid = bc.block_ids(x, y, B, width)
    if len(bid) == 0:
        return np.ones(0, dtype=bool)
    o = np.argsort(bid, kind="stable")
    bo = bid[o]
    start = np.flatnonzero(np.concatenate(([True], bo[1:] != bo[:-1])))
    size = np.diff(np.concatenate((start, [len(bo)])))
    keep_o = np.repeat(size <= n, size)                          # small blocks: every event
    big = np.flatnonzero(size > n)
    if len(big):
        j = np.tile(np.arange(n, dtype=np.int64), len(big))
        Nb = np.repeat(size[big], n).astype(np.int64)
        keep_o[np.repeat(start[big], n) + ((2 * j + 1) * Nb) // (2 * n)] = True
    keep = np.zeros(len(bid), dtype=bool)
    keep[o] = keep_o
    return keep


def code_subset(ev, keep, w0: int, width: int, height: int):
    """Code the kept events of one window with coder Q on the working grid and decode them. Returns bits, events."""
    t, x, y, p = ev
    buf = bc.encode_events_Q(t[keep] - w0, x[keep], y[keep], p[keep], bc.Q_DIRECT, width, height)
    dt, dx, dy, dp = bc.decode_events_Q(buf, bc.Q_DIRECT, width, height)
    if len(dt) != int(keep.sum()):
        raise AssertionError("coder Q lost events")
    return 8 * len(buf), (np.asarray(dt, dtype=np.int64) + w0, np.asarray(dx, dtype=np.int64),
                          np.asarray(dy, dtype=np.int64), np.asarray(dp, dtype=np.int64))


# ----------------------------------------------------------------------------------------------
# HEVC

def count_frames(windows, w: int, K: int, width: int, height: int):
    """Voxel counts of the working grid, shape (3 K, ny, 2 nx): frame 3 m + bin, polarity 1 to the right."""
    s, k = GRID
    nx, ny = -(-width // s), -(-height // s)
    fr = np.zeros((K * k, ny, 2 * nx), dtype=np.int64)
    for m in range(K):
        t, x, y, p = (np.asarray(a, dtype=np.int64) for a in windows[m])
        np.add.at(fr, (m * k + bc.time_bin(t - (w + m) * T0, k), y // s, p * nx + x // s), 1)
    return fr


def frames_to_windows(cnt, w: int, K: int, width: int, height: int):
    """Events of each window from voxel counts, at the origin of the voxel and the first instant of the bin."""
    s, k = GRID
    nx = -(-width // s)
    out = []
    for m in range(K):
        f, yy, xx = np.nonzero(cnt[m * k:(m + 1) * k])
        c = cnt[m * k:(m + 1) * k][f, yy, xx].astype(np.int64)
        p = (xx >= nx).astype(np.int64)
        t = (w + m) * T0 - ((-f.astype(np.int64) * T0) // k)
        out.append((np.repeat(t, c), np.repeat((xx - p * nx) * s, c).astype(np.int64),
                    np.repeat(yy * s, c).astype(np.int64), np.repeat(p, c)))
    return out


def nal_bits(stream: bytes):
    """Bits of the NAL units of an Annex B stream, without start codes: (counted, skipped) by NAL_SKIP."""
    b = np.frombuffer(stream, dtype=np.uint8)
    z = np.flatnonzero((b[:-2] == 0) & (b[1:-1] == 0) & (b[2:] == 1)) if len(b) >= 3 else np.zeros(0, dtype=np.int64)
    starts = z + 3
    ends = np.concatenate((z[1:], [len(b)]))
    counted = skipped = 0
    for a, e in zip(starts, ends):
        while e > a and b[e - 1] == 0:          # trailing zeros belong to the next start code
            e -= 1
        typ = (int(b[a]) >> 1) & 0x3F
        if typ in NAL_SKIP:
            skipped += 8 * int(e - a)
        else:
            counted += 8 * int(e - a)
    return counted, skipped


def _run(cmd):
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(f"{cmd[0]} failed: {r.stderr.decode(errors='replace')[-2000:]}")


def hevc_code(cnt, qp: int, workdir=None):
    """Code a group of count frames at ``qp`` and decode it. Returns counted bits, skipped bits, clipped events, counts."""
    n, h, w2 = cnt.shape
    if h % 2 or w2 % 2:
        raise ValueError("hevc: yuv420p needs even frame sides")
    Y = (np.minimum(cnt, HEVC_MAX) * HEVC_SCALE).astype(np.uint8)
    clipped = int(np.maximum(cnt - HEVC_MAX, 0).sum())
    U = np.full((h // 2, w2 // 2), 128, dtype=np.uint8).tobytes()
    with tempfile.TemporaryDirectory(dir=workdir) as d:
        inp, out, dec = (os.path.join(d, f) for f in ("in.yuv", "out.hevc", "dec.yuv"))
        with open(inp, "wb") as f:
            for i in range(n):
                f.write(Y[i].tobytes() + U + U)
        params = f"qp={int(qp)}:keyint={n}:min-keyint={n}:" + HEVC_PARAMS
        _run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-f", "rawvideo", "-pix_fmt", "yuv420p",
              "-s", f"{w2}x{h}", "-r", "90", "-i", inp, "-an", "-c:v", "libx265", "-pix_fmt", "yuv420p",
              "-profile:v", "main", "-preset", HEVC_PRESET,
              "-x265-params", params, "-f", "hevc", out])
        with open(out, "rb") as f:
            stream = f.read()
        _run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-threads", "1", "-i", out,
              "-f", "rawvideo", "-pix_fmt", "yuv420p", dec])
        raw = np.fromfile(dec, dtype=np.uint8)
    fsz = h * w2 * 3 // 2
    if raw.size != n * fsz:
        raise AssertionError(f"hevc: decoded {raw.size / fsz} frames, encoded {n}")
    Yd = raw.reshape(n, fsz)[:, :h * w2].reshape(n, h, w2).astype(np.float64)
    counted, skipped = nal_bits(stream)
    return counted, skipped, clipped, np.clip(np.floor((Yd + HEVC_SCALE // 2) / HEVC_SCALE), 0, HEVC_MAX).astype(np.int64), stream


# ----------------------------------------------------------------------------------------------
# the flow-based baseline with its events without flow on the working grid

FBC2_FLAG = 2


def fbc2_record(t, x, y, p, w: int, K: int, width: int, height: int, flows: dict) -> bytes:
    """``ec.fbc.encode_group`` with coder Q, except that the events without flow use the working grid."""
    t, x, y, p = (np.asarray(a, dtype=np.int64) for a in (t, x, y, p))
    w0 = w * T0
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
    parts = [fbc.REC.pack(st, FBC2_FLAG),
             bc.encode_events_Q(t[flow_ev] - w0, x[flow_ev], y[flow_ev], p[flow_ev], bc.Q_KEY, width, height),
             bc._zstd(bc.uleb_encode(np.concatenate(([len(keys)], fbc._zz(fv)))), 19)]
    for m in range(K):
        a, b = w0 + m * T0, w0 + (m + 1) * T0
        sel = (t >= a) & (t < b)
        plain = sel & snd & ~has if m == 0 else np.zeros(len(t), dtype=bool)
        pred_part = sel & (t >= s_end)
        if pred_part.any():
            fok = flows["windows"][m][2]
            plain |= pred_part & ~fok[p, y, x]
        parts.append(bc.encode_events_Q(t[plain] - a, x[plain], y[plain], p[plain], bc.Q_DIRECT, width, height))
    return fbc._pack(parts)


def fbc2_reconstruct(record: bytes, w: int, K: int, width: int, height: int):
    """Events of each window m = 0 .. K - 1 from a record of ``fbc2_record`` alone."""
    parts = fbc._unpack(record, 3 + K)
    st, flag = fbc.REC.unpack(parts[0])
    if flag != FBC2_FLAG:
        raise ValueError("not a record of fbc2_record")
    w0 = w * T0
    s_end, end = w0 + st, w0 + K * T0
    ft, fx, fy, fp = bc.decode_events_Q(parts[1], bc.Q_KEY, width, height)
    ft = np.asarray(ft, dtype=np.int64) + w0
    v, _ = bc.uleb_decode(bc._unzstd(parts[2])) if parts[2] else (np.array([0]), 0)
    nk = int(v[0])
    fl = fbc._unzz(np.asarray(v[1:1 + 2 * nk])).reshape(-1, 2) if nk else np.zeros((0, 2), dtype=np.int64)
    keys = np.unique((fp * height + fy) * width + fx)
    if len(keys) != nk:
        raise ValueError("fbc2: flow count does not match the flow events")
    j = np.searchsorted(keys, (fp * height + fy) * width + fx)
    pt, px, py, pp = fbc._predict(ft, fx, fy, fp, fl[j, 0], fl[j, 1], s_end, end, width, height)
    out = []
    for m in range(K):
        a, b = w0 + m * T0, w0 + (m + 1) * T0
        qt, qx, qy, qp = bc.decode_events_Q(parts[3 + m], bc.Q_DIRECT, width, height)
        T, X, Y, P = [np.asarray(qt, dtype=np.int64) + a], [qx], [qy], [qp]
        if m == 0:
            T.append(ft); X.append(fx); Y.append(fy); P.append(fp)
        sel = (pt >= a) & (pt < b)
        T.append(pt[sel]); X.append(px[sel]); Y.append(py[sel]); P.append(pp[sel])
        out.append(tuple(np.concatenate(z).astype(np.int64) for z in (T, X, Y, P)))
    return out


# ----------------------------------------------------------------------------------------------
# one group

def _in_window(rec, w0: int, width: int, height: int) -> int:
    t, x, y, _ = rec
    return int(np.count_nonzero((t < w0) | (t >= w0 + T0) | (x < 0) | (x >= width) | (y < 0) | (y >= height)))


class _Tasks:
    """The two tasks of ``ec.downstream`` on windows 1 to 3, with the velocities of the true events computed once."""

    def __init__(self, truth, w: int, boxes, squares):
        self.truth, self.w = truth, w
        self.boxes = {}
        for m, bl in (boxes or {}).items():
            keep = []
            for tid, box in bl:
                t, x, y, _ = truth[m]
                n = int(np.count_nonzero((x >= box[0]) & (x < box[0] + box[2]) & (y >= box[1]) & (y < box[1] + box[3])))
                if n >= MIN_BOX_EVENTS:
                    keep.append((tid, box, n))
            self.boxes[m] = keep
        self.squares = [(sq, dn.cmax_velocity(truth[2], sq, (w + 2) * T0)) for sq, _ in (squares or [])]

    def run(self, rec):
        obj, cen = [], {}
        for m in (1, 2, 3):
            for tid, box, n in self.boxes.get(m, []):
                obj.append({"m": m, "track": int(tid), "n_true": n,
                            **dn.box_scores(self.truth[m], rec[m], box, (self.w + m) * T0)})
                cen[(int(tid), m)] = (_centroid(self.truth[m], box), _centroid(rec[m], box))
        tracks = []
        for tid in sorted({k[0] for k in cen}):
            if not all((tid, m) in cen for m in (1, 2, 3)):
                continue
            ct = [cen[(tid, m)][0] for m in (1, 2, 3)]
            cr = [cen[(tid, m)][1] for m in (1, 2, 3)]
            cont = all(c is not None for c in cr)
            err = float(np.hypot(*((cr[2] - cr[0]) - (ct[2] - ct[0]))) / 2.0) if cont else float("nan")
            tracks.append({"track": tid, "continuous": bool(cont), "velocity_error_px": err})
        mot = []
        for sq, vt in self.squares:
            vr = dn.cmax_velocity(rec[2], sq, (self.w + 2) * T0)
            err = float("nan") if (np.isnan(vt).any() or np.isnan(vr).any()) else float(np.hypot(*(vr - vt)) * T0 / 1000.0)
            mot.append({"square": list(sq), "error_px": err, "n_rec": int(np.count_nonzero(
                (rec[2][1] >= sq[0]) & (rec[2][1] < sq[0] + sq[2]) & (rec[2][2] >= sq[1]) & (rec[2][2] < sq[1] + sq[3])))})
        return {"objects": obj, "tracks": tracks, "motion": mot}


def _centroid(ev, box):
    """Mean pixel of the events inside ``box`` by the rule of ``ec.downstream.box_scores``, or None."""
    _, x, y, _ = ev
    s = (x >= box[0]) & (x < box[0] + box[2]) & (y >= box[1]) & (y < box[1] + box[3])
    if not s.any():
        return None
    return np.array([x[s].mean(), y[s].mean()])


def evaluate_group(ev, w: int, width: int, height: int, records: dict, kept: dict, boxes=None, squares=None,
                   schemes=None, workdir=None) -> dict:
    """Every scheme on the group keyed at window ``w``.

    ``ev`` = (t_us, x, y, p), int64, nondecreasing in time, covering
    ``[w T0 - ec.fbc.FIT_WINDOW_US, (w + 11) T0)``. ``records``: the kept records ``<model>_Q_K<K>`` of
    configuration CONFIG; ``kept``: the kept group, whose ``match_s2_k3`` and ``n_rec`` check the rebuilt
    REMAKE. ``boxes``: {m: [(track, (x0, y0, w, h))]} for m = 1, 2, 3, or None. ``squares``: the squares of
    window 2 as ``scripts/fb_run.py:squares_for`` returns them. ``schemes``: a subset of ``scheme_names()``.
    """
    t, x, y, p = (np.asarray(a, dtype=np.int64) for a in ev)
    names = scheme_names() if schemes is None else list(schemes)
    edges = np.searchsorted(t, [(w + m) * T0 for m in range(N_WIN + 1)])
    win = [(t[edges[m]:edges[m + 1]], x[edges[m]:edges[m + 1]], y[edges[m]:edges[m + 1]], p[edges[m]:edges[m + 1]])
           for m in range(N_WIN)]
    bg = background_rate((t, x, y, p), max(0, w * T0 - fbc.FIT_WINDOW_US), (w + 1) * T0, width, height)
    tw = [TrueWindow(win[m], (w + m) * T0, width, height, bg["phi"], bg["theta"]) for m in range(N_WIN)]
    tasks = _Tasks(win, w, boxes, squares)
    direct = [8 * len(bc.encode_events_Q(v[0] - (w + m) * T0, v[1], v[2], v[3], bc.Q_DIRECT, width, height))
              for m, v in enumerate(win)]
    out = {"w": int(w), "n_true": [tw[m].n for m in range(N_WIN)], "direct_bits": direct, "background": bg, "schemes": {},
           "hevc": {}, "checks": {"outside": 0, "remake_equals_kept": True}}

    def check(rw):
        out["checks"]["outside"] += sum(_in_window(rw[m], (w + m) * T0, width, height) for m in range(len(rw)))

    def finish(name, per_K, rec4):
        out["schemes"][name] = {**per_K, "tasks": tasks.run(rec4)}

    for name in names:
        kind = name.split("_")[0]
        if kind in ("remake", "translation", "static"):
            model = dict(REMAKE_MODELS)[name]
            per_K = {}
            for K in KS:
                rec = records[f"{model}_Q_K{K}"]
                hdr = bc.encode_header("Q", model, K, width, height, B)
                h, groups = bc.decode_stream(hdr + rec)
                g = groups[0]
                g["w"] = int(w)
                rw = [bc.reconstruct(h, g, m) for m in range(K)]
                check(rw)
                sums = [window_sums(tw[m], rw[m]) for m in range(K)]
                km = kept["codec"][CONFIG]["models"][model]
                ok = ([s["M"] for s in sums[1:]] == list(km["match_s2_k3"][:K - 1])
                      and [s["N2"] for s in sums[1:]] == list(km["n_rec"][:K - 1])
                      and sums[0]["M"] == sums[0]["N2"] == int(kept["codec"][CONFIG]["n_key"]))
                out["checks"]["remake_equals_kept"] &= bool(ok)
                per_K[f"K{K}"] = {"bits": 8 * len(rec), "sums": sums}
                if K == 4:
                    rec4 = rw
            finish(name, per_K, rec4)
        elif kind in ("thin", "select", "cap"):
            arg = float(name.split("_", 1)[1])
            bits, sums, rw = [], [], []
            for m in range(N_WIN):
                v = win[m]
                keep = (thin_mask(len(v[0]), arg, w, m) if kind == "thin" else
                        select_mask(v[1], v[2], arg, width) if kind == "select" else cap_mask(v[1], v[2], int(arg), width))
                b, r = code_subset(v, keep, (w + m) * T0, width, height)
                out["checks"]["outside"] += _in_window(r, (w + m) * T0, width, height)
                bits.append(b)
                sums.append(window_sums(tw[m], r))
                if m < 4:
                    rw.append(r)
            finish(name, {f"K{K}": {"bits": int(sum(bits[:K])), "sums": sums[:K]} for K in KS}, rw)
        elif kind == "hevc":
            qp = int(name.split("_")[1])
            per_K, extra = {}, {}
            for K in KS:
                b, skipped, clipped, cnt, _ = hevc_code(count_frames(win, w, K, width, height), qp, workdir)
                rw = frames_to_windows(cnt, w, K, width, height)
                check(rw)
                per_K[f"K{K}"] = {"bits": int(b), "sums": [window_sums(tw[m], rw[m]) for m in range(K)]}
                extra[f"K{K}"] = {"param_sei_bits": int(skipped), "clipped_events": int(clipped)}
                if K == 4:
                    rec4 = rw
            out["hevc"][name] = extra
            finish(name, per_K, rec4)
        elif kind == "fbc":
            r_, s_ = name[len("fbc_r"):].split("_res")
            flows = fbc.group_flows(t, x, y, p, w, width, height, int(r_), float(s_), max(KS))
            per_K = {}
            for K in KS:
                rec = fbc2_record(t, x, y, p, w, K, width, height, flows)
                rw = fbc2_reconstruct(rec, w, K, width, height)
                check(rw)
                per_K[f"K{K}"] = {"bits": 8 * len(rec), "sums": [window_sums(tw[m], rw[m]) for m in range(K)],
                                  "st_us": int(flows["st_us"])}
                if K == 4:
                    rec4 = rw
            finish(name, per_K, rec4)
        else:
            raise ValueError(f"unknown scheme {name}")
    return out
