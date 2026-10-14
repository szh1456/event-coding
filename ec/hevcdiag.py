"""Where a frame-based video coder pays on event streams: three diagnostics (directive 019).

The question is where HEVC, applied to events as the coders of the literature apply it (events counted
into frames, the frames coded as video), loses rate or task information, and whether the theory of the
manuscript predicts where. Nothing here is a new coder.

Grids. A grid ``(s, k)`` is ``s`` pixels and ``k`` time slices per window of ``T0``; slice ``f`` of window
``m`` is ``[(w + m) T0 + ceil(f T0 / k), ...)`` as ``ec.blockcodec.time_bin`` assigns it. ``KS`` holds the
slice counts (33.3 ms down to 0.52 ms) and ``SPACES`` the pixel sizes.

Frames. ``voxel_counts`` counts the events of K windows on a grid as a sparse list of (frame, row,
column, count): one frame per slice (K k frames), the two polarities side by side (polarity 1 to the
right), each side padded to an even size, as directive 018 did for k = 3, s = 2. Frames are written to
and read from the coder one at a time, so memory does not grow with K k. ``voxels_to_windows`` turns
counts back into events: ``start`` places them at the origin of the voxel and the first instant of the
slice, which is what coder Q decodes; ``center`` places them at the voxel's centre pixel ``s // 2`` and
the middle instant of the slice. ``count_frames`` builds the dense array, for small sensors only.

D1, slices and rate (``code_counts``). The counts, clipped to HEVC_MAX per voxel, are coded three ways:
``lossless`` (x265 lossless, luma = count; the decode must equal the clipped counts), ``qp<q>`` (x265 at a
constant QP, luma = 16 count, decode ``floor((Y + 8) / 16)``, as directive 018; a voxel with one event has
luma 16, which disappears between QP 14 and 26, so QPS is dense there; ``ipratio=1`` codes the intra frame at
the same QP as the P frames), and ``sparse`` (coder Q of
``ec.blockcodec`` on the same clipped counts at cell ``(s, k)``: no frames, one list of voxel indices per
window; its decode must equal the clipped counts). Every clip has one intra frame and P frames after it.
For each: bits (NAL units other than parameter sets and SEI; ``ec.families.nal_bits``), the bits of the
parameter sets, encoder and decoder CPU seconds of the child processes, and, from x265's own CSV log at
level 1, per frame its type, bits and the shares that x265 reports for intra, inter, skip and merge
coding units (x265 names the intra 4x4 share ``4x4``; the four shares of a frame must add up to 100), and
its QP. The tasks run on lossy decodes with both placements, so that D1 minus D2 is the loss of coding.
CPU seconds come from ``os.wait4`` on the child itself.

D2, the representation alone (``represent``). No coding: events to counts on ``(s, k)`` to events, with
both placements, without clipping.

D3, prediction on the model (``edge_scene``, ``oracle_shift``). Straight edges cross a small sensor at a
whole number ``u`` of pixels per window; every row is one path of the manuscript's model: pixel ``x`` of
the row starts its passage at ``(x - x_e + phi) / v``, with ``phi`` uniform per row and edge, and emits
``n`` events at ``A + (j - 1) tau + eps``, ``A`` uniform on ``(0, tau]``, ``eps`` normal with ``sigma``.
``oracle_shift`` predicts the counts of window m from those of window m - 1 moved by exactly ``u`` pixels,
the best a block motion compensation can do here, and reports ``F = 1 - L1 / (N + N')``. Eq. (binfidmoved)
predicts ``F = dt / tau - dt^2 / (3 n tau^2)`` for ``s = 1`` and ``dt <= tau / 2``.

Fidelities on a grid (``sums_on``): the voxel fidelity F of Eq. (fid) and the background-referenced
Fsnr of directive 018, both with the matched events counted on ``(s, k)``.
"""
from __future__ import annotations

import csv
import os
import subprocess
import tempfile

import numpy as np

from . import blockcodec as bc
from . import families as fa

T0 = bc.T0_US
KS = (1, 3, 6, 12, 32, 64)
SPACES = (1, 2)
QPS = (12, 14, 16, 18, 20, 22, 24, 28)
K_WIN = 4
HEVC_SCALE, HEVC_MAX = 16, 15
PRESET = "slow"
PARAMS = "ipratio=1:bframes=0:scenecut=0:open-gop=0:aq-mode=0:psy-rd=0:psy-rdoq=0:info=0:frame-threads=1:pools=none:log-level=error"
PLACEMENTS = ("start", "center")
B = fa.B
CSV_KINDS = ("Intra", "Inter", "Skip", "Merge")


# ----------------------------------------------------------------------------------------------
# grids and frames

def dims(s: int, width: int, height: int):
    """Voxels per row and column, and the padded frame size (height, width) with both polarities."""
    nx, ny = -(-width // s), -(-height // s)
    return nx, ny, ny + ny % 2, 2 * (nx + nx % 2)


def voxel_counts(windows, w: int, K: int, s: int, k: int, width: int, height: int):
    """Sparse counts of windows ``w .. w + K - 1`` on ``(s, k)``: sorted frame-major keys and their counts.

    ``key = (g * fh + row) * fw + column`` with ``g = m k + slice``.
    """
    nx, ny, fh, fw = dims(s, width, height)
    half = fw // 2
    keys = []
    for m in range(K):
        t, x, y, p = (np.asarray(a, dtype=np.int64) for a in windows[m])
        g = m * k + bc.time_bin(t - (w + m) * T0, k)
        keys.append((g * fh + y // s) * fw + p * half + x // s)
    key = np.concatenate(keys) if keys else np.zeros(0, dtype=np.int64)
    return np.unique(key, return_counts=True)


def voxels_to_windows(key, cnt, w: int, K: int, s: int, k: int, width: int, height: int, placement: str = "start"):
    """Events of each window from sparse counts; see the module docstring for the two placements."""
    nx, ny, fh, fw = dims(s, width, height)
    half = fw // 2
    key = np.asarray(key, dtype=np.int64)
    cnt = np.asarray(cnt, dtype=np.int64)
    col, r = key % fw, key // fw
    row, g = r % fh, r // fh
    p = (col >= half).astype(np.int64)
    vx = col - p * half
    if np.any(vx >= nx) or np.any(row >= ny) or np.any(g >= K * k):
        raise AssertionError("counts in the padding")
    out = []
    for m in range(K):
        sel = (g >= m * k) & (g < (m + 1) * k)
        f, c = g[sel] - m * k, cnt[sel]
        if placement == "start":
            t = (w + m) * T0 - ((-f * T0) // k)
            px, py = vx[sel] * s, row[sel] * s
        elif placement == "center":
            t = (w + m) * T0 + ((2 * f + 1) * T0) // (2 * k)
            px = np.minimum(vx[sel] * s + s // 2, width - 1)
            py = np.minimum(row[sel] * s + s // 2, height - 1)
        else:
            raise ValueError(placement)
        out.append((np.repeat(t, c), np.repeat(px, c), np.repeat(py, c), np.repeat(p[sel], c)))
    return out


def count_frames(windows, w: int, K: int, s: int, k: int, width: int, height: int):
    """Dense counts, shape (K k, frame height, frame width); for small sensors (the model of D3)."""
    nx, ny, fh, fw = dims(s, width, height)
    key, cnt = voxel_counts(windows, w, K, s, k, width, height)
    fr = np.zeros(K * k * fh * fw, dtype=np.int64)
    fr[key] = cnt
    return fr.reshape(K * k, fh, fw)


# ----------------------------------------------------------------------------------------------
# fidelities on a grid

def sums_on(true, rec, w0: int, cell, width: int, height: int, phi: float = 1.0, theta: float = 0.0) -> dict:
    """Sums of F and Fsnr for one window, with the matched events counted on ``cell`` = (s, k)."""
    true = tuple(np.asarray(a, dtype=np.int64) for a in true)
    rec = tuple(np.asarray(a, dtype=np.int64) for a in rec)
    s, k = cell
    if B % s:
        raise ValueError("the block side must be a multiple of s")
    kt, ct = fa.voxels(true, w0, cell, width, height)
    kr, cr = fa.voxels(rec, w0, cell, width, height)
    com, i, j = np.intersect1d(kt, kr, assume_unique=True, return_indices=True)
    mm = np.minimum(ct[i], cr[j]).astype(np.float64)
    nx, ny = -(-width // s), -(-height // s)
    vx, vy = (com % nx) * s, ((com // nx) % ny) * s
    nbx, nby = -(-width // B), -(-height // B)
    bM = np.bincount((vy // B) * nbx + vx // B, weights=mm, minlength=nbx * nby)
    bN = fa.block_counts(true[1], true[2], width, height)
    bN2 = fa.block_counts(rec[1], rec[2], width, height)
    enter = (bN > theta) | (bN2 > theta)
    lN, lN2, lM = (np.log1p(v[enter] / phi) for v in (bN, bN2, bM))
    return {"N": int(len(true[0])), "N2": int(len(rec[0])), "M": float(mm.sum()),
            "Dsnr": float((lN + lN2 - 2.0 * lM).sum()), "Lsnr": float((lN + lN2).sum())}


def fidelities(sums) -> dict:
    a = {key: float(sum(x[key] for x in sums)) for key in sums[0]}
    den = a["N"] + a["N2"]
    return {"F": 2.0 * a["M"] / den if den else 0.0,
            "Fsnr": min(1.0, max(0.0, 1.0 - a["Dsnr"] / a["Lsnr"])) if a["Lsnr"] > 0 else 0.0}


# ----------------------------------------------------------------------------------------------
# D1: coding the counts

def _run(cmd) -> float:
    """Run ``cmd``; return the CPU seconds of that child alone (``os.wait4``)."""
    with tempfile.TemporaryFile() as err:
        pr = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=err)
        _, status, ru = os.wait4(pr.pid, 0)
        pr.returncode = os.waitstatus_to_exitcode(status)
        if pr.returncode != 0:
            err.seek(0)
            raise RuntimeError(f"{cmd[0]} failed: {err.read().decode(errors='replace')[-2000:]}")
    return ru.ru_utime + ru.ru_stime


def parse_csv(path) -> list:
    """Per frame of x265's CSV log (level 1): type, bits, and the summed shares of each kind of coding unit."""
    rows = []
    with open(path, newline="") as f:
        rd = csv.reader(f)
        head = [h.strip() for h in next(rd)]
        for r in rd:
            if not r or not r[0].strip().isdigit():
                continue
            v = [c.strip() for c in r]
            row = {"type": v[head.index("Type")], "bits": int(float(v[head.index("Bits")])),
                   "qp": float(v[head.index("QP")])}
            for kind in CSV_KINDS:
                row[kind.lower()] = float(sum(float(v[i].rstrip("%")) for i, h in enumerate(head)
                                              if (h.startswith(kind + " ") or (kind == "Intra" and h == "4x4"))
                                              and i < len(v) and v[i].endswith("%")))
            tot = sum(row[kind.lower()] for kind in CSV_KINDS)
            if abs(tot - 100.0) > 0.5:
                raise AssertionError(f"x265 CSV: the coding-unit shares of a frame add up to {tot}")
            rows.append(row)
    return rows


def _in_padding(key, fh: int, fw: int, valid):
    nx, ny = valid
    col, row = key % fw, (key // fw) % fh
    return (col % (fw // 2) >= nx) | (row >= ny)


def hevc(key, cnt, n_frames: int, fh: int, fw: int, mode: str, workdir=None, valid=None) -> dict:
    """Code clipped sparse counts as ``n_frames`` frames of ``fh`` x ``fw`` with x265; ``mode`` is ``lossless`` or
    ``qp<q>``. Frames are written and read one at a time. Returns bits, CPU times, per-frame statistics and the
    decoded sparse counts."""
    if fh % 2 or fw % 2:
        raise ValueError("yuv420p needs even frame sides")
    key = np.asarray(key, dtype=np.int64)
    cnt = np.asarray(cnt, dtype=np.int64)
    if len(cnt) and (cnt.min() < 1 or cnt.max() > HEVC_MAX):
        raise ValueError("counts must be clipped to [1, HEVC_MAX]")
    lossless = mode == "lossless"
    scale = 1 if lossless else HEVC_SCALE
    valid = (fw // 2, fh) if valid is None else valid
    fsz = fh * fw
    U = np.full((fh // 2) * (fw // 2), 128, dtype=np.uint8).tobytes()
    starts = np.searchsorted(key, np.arange(n_frames + 1) * fsz)
    with tempfile.TemporaryDirectory(dir=workdir) as d:
        inp, out, dec, log = (os.path.join(d, f) for f in ("in.yuv", "out.hevc", "dec.yuv", "x265.csv"))
        Y = np.zeros(fsz, dtype=np.uint8)
        with open(inp, "wb") as f:
            for g in range(n_frames):
                a, b = starts[g], starts[g + 1]
                Y[key[a:b] - g * fsz] = (cnt[a:b] * scale).astype(np.uint8)
                f.write(Y.tobytes() + U + U)
                Y[key[a:b] - g * fsz] = 0
        rc = ("lossless=1" if lossless else f"qp={int(mode[2:])}")
        params = f"{rc}:keyint={n_frames}:min-keyint={n_frames}:{PARAMS}:csv={log}:csv-log-level=1"
        enc = _run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-f", "rawvideo", "-pix_fmt", "yuv420p",
              "-s", f"{fw}x{fh}", "-r", "90", "-i", inp, "-an", "-c:v", "libx265", "-pix_fmt", "yuv420p",
              "-profile:v", "main", "-preset", PRESET, "-x265-params", params, "-f", "hevc", out])
        os.remove(inp)
        dec_s = _run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-threads", "1", "-i", out,
                      "-f", "rawvideo", "-pix_fmt", "yuv420p", dec])
        with open(out, "rb") as f:
            stream = f.read()
        stats = parse_csv(log)
        size = os.path.getsize(dec)
        if size != n_frames * (fsz + 2 * len(U)):
            raise AssertionError(f"hevc: decoded {size / (fsz + 2 * len(U))} frames, encoded {n_frames}")
        dk, dc = [], []
        with open(dec, "rb") as f:
            for g in range(n_frames):
                buf = np.frombuffer(f.read(fsz + 2 * len(U)), dtype=np.uint8)[:fsz].astype(np.int64)
                v = buf if lossless else np.clip((buf + HEVC_SCALE // 2) // HEVC_SCALE, 0, HEVC_MAX)
                nz = np.flatnonzero(v)
                dk.append(nz + g * fsz)
                dc.append(v[nz])
    dkey, dcnt = np.concatenate(dk), np.concatenate(dc)
    if lossless and not (np.array_equal(dkey, key) and np.array_equal(dcnt, cnt)):
        raise AssertionError("x265 lossless did not return the counts")
    pad = _in_padding(dkey, fh, fw, valid)                 # lossy ringing into the padding is dropped and counted
    padding_counts = int(dcnt[pad].sum())
    dkey, dcnt = dkey[~pad], dcnt[~pad]
    bits, param_bits = fa.nal_bits(stream)
    if len(stats) != n_frames:
        raise AssertionError(f"x265 CSV has {len(stats)} frames, encoded {n_frames}")
    return {"bits": int(bits), "param_bits": int(param_bits), "enc_cpu_s": enc, "dec_cpu_s": dec_s,
            "padding_counts": padding_counts, "frames": stats, "key": dkey, "cnt": dcnt}


def sparse(key, cnt, w: int, K: int, s: int, k: int, width: int, height: int) -> dict:
    """Coder Q of ``ec.blockcodec`` on the clipped counts, one payload per window: bits and its exact decode check."""
    ev = voxels_to_windows(key, cnt, w, K, s, k, width, height, "start")
    bits = 0
    for m in range(K):
        t, x, y, p = ev[m]
        w0 = (w + m) * T0
        buf = bc.encode_events_Q(t - w0, x, y, p, (s, k), width, height)
        bits += 8 * len(buf)
        dt, dx, dy, dp = bc.decode_events_Q(buf, (s, k), width, height)
        a = np.sort(((np.asarray(dt) + w0) * 8192 + np.asarray(dx)) * 8192 * 2 + np.asarray(dy) * 2 + np.asarray(dp))
        b = np.sort((t * 8192 + x) * 8192 * 2 + y * 2 + p)
        if not np.array_equal(a, b):
            raise AssertionError("coder Q did not return the counts")
    return {"bits": int(bits)}


def code_counts(windows, w: int, s: int, k: int, width: int, height: int, modes, phi: float, theta: float,
                tasks=None, workdir=None, K: int = K_WIN) -> dict:
    """D1 for one group and grid: every mode of ``modes`` (``lossless``, ``qp<q>``, ``sparse``)."""
    nx, ny, fh, fw = dims(s, width, height)
    key, raw = voxel_counts(windows, w, K, s, k, width, height)
    cnt = np.minimum(raw, HEVC_MAX)
    out = {"s": s, "k": k, "n_true": [int(len(v[0])) for v in windows[:K]],
           "clipped_events": int((raw - cnt).sum()), "modes": {}}
    clip_ev = voxels_to_windows(key, cnt, w, K, s, k, width, height, "start")
    out["clip_fid"] = fidelities([sums_on(windows[m], clip_ev[m], (w + m) * T0, (s, k), width, height, phi, theta)
                                  for m in range(K)])
    for mode in modes:
        if mode == "sparse":
            out["modes"][mode] = sparse(key, cnt, w, K, s, k, width, height)
            continue
        r = hevc(key, cnt, K * k, fh, fw, mode, workdir, valid=(nx, ny))
        dkey, dcnt = r.pop("key"), r.pop("cnt")
        ev = voxels_to_windows(dkey, dcnt, w, K, s, k, width, height, "start")
        r["fid"] = fidelities([sums_on(windows[m], ev[m], (w + m) * T0, (s, k), width, height, phi, theta)
                               for m in range(K)])
        if tasks is not None and mode != "lossless":
            r["tasks"] = {pl: tasks.run(voxels_to_windows(dkey, dcnt, w, K, s, k, width, height, pl))
                          for pl in PLACEMENTS}
        out["modes"][mode] = r
    return out


# ----------------------------------------------------------------------------------------------
# D2: the representation alone

def represent(windows, w: int, s: int, k: int, width: int, height: int, placement: str, tasks=None,
              K: int = K_WIN) -> dict:
    """Events to counts on (s, k) to events, without clipping or coding; the tasks on the result."""
    key, cnt = voxel_counts(windows, w, K, s, k, width, height)
    ev = voxels_to_windows(key, cnt, w, K, s, k, width, height, placement)
    if [len(e[0]) for e in ev] != [len(v[0]) for v in windows[:K]]:
        raise AssertionError("the representation lost events")
    return {"s": s, "k": k, "placement": placement, "tasks": tasks.run(ev) if tasks is not None else None}


# ----------------------------------------------------------------------------------------------
# D3: the model

def edge_scene(width: int, height: int, u: int, tau_us: float, n: int, sigma_frac: float, spacing: int,
               n_windows: int, seed: int):
    """Events of straight edges crossing the sensor at ``u`` pixels per window (see the module docstring)."""
    rng = np.random.default_rng(seed)
    v = u / T0                                            # pixels per microsecond
    span = n_windows * T0
    T, X, Y, P = [], [], [], []
    xs = np.arange(width)
    for e, x_e in enumerate(range(-int(np.ceil(v * span)) - spacing, width, spacing)):
        for y in range(height):
            phi = rng.random()
            t0 = (xs - x_e + phi) / v
            ok = (t0 >= -n * tau_us) & (t0 < span)
            if not ok.any():
                continue
            xx = xs[ok]
            A = (1.0 - rng.random(len(xx))) * tau_us
            for j in range(n):
                tt = t0[ok] + A + j * tau_us + rng.normal(0.0, sigma_frac * tau_us, len(xx))
                T.append(tt); X.append(xx); Y.append(np.full(len(xx), y)); P.append(np.full(len(xx), e % 2))
    t = np.rint(np.concatenate(T)).astype(np.int64)
    x, y, p = (np.concatenate(a).astype(np.int64) for a in (X, Y, P))
    keep = (t >= 0) & (t < span)
    o = np.argsort(t[keep], kind="stable")
    return tuple(a[keep][o] for a in (t, x, y, p))


def windows_of(ev, w: int, K: int):
    t = ev[0]
    out = []
    for m in range(K):
        a, b = np.searchsorted(t, ((w + m) * T0, (w + m + 1) * T0))
        out.append(tuple(v[a:b] for v in ev))
    return out


def oracle_shift(ev, u: int, s: int, k: int, width: int, height: int, n_windows: int) -> dict:
    """Counts of window m predicted by those of window m - 1 moved by ``u`` pixels: ``F = 1 - L1 / (N + N')``."""
    win = windows_of(ev, 0, n_windows)
    fr = count_frames(win, 0, n_windows, s, k, width, height)
    nx, ny, fh, fw = dims(s, width, height)
    half = fw // 2
    if u % s:
        raise ValueError("u must be a multiple of s")
    d = u // s
    l1 = tot = 0.0
    for m in range(1, n_windows):
        prev, cur = fr[(m - 1) * k:m * k], fr[m * k:(m + 1) * k]
        pred = np.zeros_like(prev)
        for pol in (0, 1):
            src = prev[:, :, pol * half:pol * half + nx]
            dst = pred[:, :, pol * half:pol * half + nx]
            if d >= 0:
                dst[:, :, d:] = src[:, :, :nx - d]
            else:
                dst[:, :, :nx + d] = src[:, :, -d:]
        valid = np.zeros(fw, dtype=bool)                  # columns whose source lies on the sensor
        for pol in (0, 1):
            valid[pol * half + max(d, 0):pol * half + nx + min(d, 0)] = True
        l1 += np.abs(pred - cur)[:, :, valid].sum()
        tot += pred[:, :, valid].sum() + cur[:, :, valid].sum()
    return {"F": 1.0 - l1 / tot if tot else float("nan"), "n_events": float(tot / 2)}


def binfidmoved(dt: float, tau: float, n: int) -> float:
    """Eq. (binfidmoved) for ``dt <= tau / 2``; NaN beyond, where the manuscript gives no closed form."""
    return dt / tau - dt * dt / (3.0 * n * tau * tau) if dt <= tau / 2 else float("nan")
