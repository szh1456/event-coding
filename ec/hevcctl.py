"""Controls for the HEVC diagnostics of directive 019 (directive 021).

Directive 019 compared x265 with coder Q, a list of the counts. That ratio compares two complete coders and
does not isolate what the temporal prediction of x265 saves. Its lossy points also mix two effects: the
quantizer and the amplitude mapping (luma = 16 count), and on coarse grids the clipping at 15. This module
adds controls on the same counts, with the same encoder and settings as ``ec.hevcdiag``:

- ``lossless_intra`` and ``qp<q>_intra``: every picture intra (``keyint=1``), against the clip of one intra
  picture and P pictures. The ratio of the two isolates the temporal prediction of x265.
- ``lossless_x16``: lossless on luma = 16 count, the mapping of the lossy modes. Against ``lossless``
  (luma = count) it gives the cost of the mapping alone.
- ``qp<q>_s4`` and ``qp<q>_s4c15``: luma = 4 count at the x265 QP ``q - 12``, with counts clipped at 63 and at
  15. The quantizer step per event is that of ``qp<q>`` (the step doubles every 6 QP), but the in-loop filters
  of x265 (SAO offsets, deblocking) act in fixed luma units, so the mapping itself changes the decode. The
  clipping is therefore isolated by ``qp<q>_s4`` against ``qp<q>_s4c15``, which differ only in the clip, and
  the mapping by ``qp<q>_s4c15`` against ``qp<q>``. With ``lossless_c255`` (luma = count, clipped at 255) and
  ``sparse_raw`` (coder Q on the unclipped counts) they are the controls for clipping on coarse grids.

Every mode reports bits as ``ec.hevcdiag.hevc`` does (NAL units other than parameter sets and SEI), the
per-picture CSV statistics, the fidelity of the decode against the true events (``F`` and ``Fsnr`` of
``ec.hevcdiag.fidelities``; clipped events count as lost), and, for lossy modes, ``count_errors`` of the
decode against the coder's input counts: the events of the input voxels that the decode removes (split by
input count 1 and >= 2), the events it lowers or raises in voxels it keeps, and the events it adds in empty
voxels. Counts that the decode places in the padding of a picture are dropped and reported as
``padding_counts``, not as ``added``.

Nothing here is a new coder.
"""
from __future__ import annotations

import os
import tempfile

import numpy as np

from . import families as fa
from . import hevcdiag as hd

QPS = hd.QPS
COARSE_QPS = (14, 28, 36, 46)
COARSE_GRIDS = ((2, 3), (2, 1), (1, 1))
S4_SHIFT = 12
FINE_MODES = (("lossless", "lossless_intra", "lossless_x16", "sparse")
              + tuple(f"qp{q}" for q in QPS) + tuple(f"qp{q}_intra" for q in QPS))
COARSE_MODES = (("lossless_c255", "sparse_raw") + tuple(f"qp{q}" for q in COARSE_QPS)
                + tuple(f"qp{q}_s4" for q in COARSE_QPS) + tuple(f"qp{q}_s4c15" for q in COARSE_QPS))


def spec(mode: str) -> dict:
    """Intra only, luma scale, clip, x265 QP (None for lossless) of a mode."""
    if mode == "lossless":
        return {"intra": False, "scale": 1, "cmax": hd.HEVC_MAX, "qp": None}
    if mode == "lossless_intra":
        return {"intra": True, "scale": 1, "cmax": hd.HEVC_MAX, "qp": None}
    if mode == "lossless_x16":
        return {"intra": False, "scale": hd.HEVC_SCALE, "cmax": hd.HEVC_MAX, "qp": None}
    if mode == "lossless_c255":
        return {"intra": False, "scale": 1, "cmax": 255, "qp": None}
    if mode.startswith("qp"):
        q, _, tail = mode[2:].partition("_")
        q = int(q)
        if tail == "":
            return {"intra": False, "scale": hd.HEVC_SCALE, "cmax": hd.HEVC_MAX, "qp": q}
        if tail == "intra":
            return {"intra": True, "scale": hd.HEVC_SCALE, "cmax": hd.HEVC_MAX, "qp": q}
        if tail in ("s4", "s4c15"):
            if q - S4_SHIFT < 0:
                raise ValueError("qp_s4 needs q >= 12")
            return {"intra": False, "scale": 4, "cmax": 63 if tail == "s4" else hd.HEVC_MAX, "qp": q - S4_SHIFT}
    raise ValueError(mode)


def x265_code(key, cnt, n_frames: int, fh: int, fw: int, sp: dict, workdir=None, valid=None) -> dict:
    """Code sparse counts (already clipped to ``sp['cmax']``) as ``n_frames`` pictures with x265 under ``sp``.

    As ``ec.hevcdiag.hevc``, with the intra period, the luma scale and the clip of ``sp``. Returns bits, CPU
    times, per-picture statistics and the decoded sparse counts."""
    if fh % 2 or fw % 2:
        raise ValueError("yuv420p needs even frame sides")
    key = np.asarray(key, dtype=np.int64)
    cnt = np.asarray(cnt, dtype=np.int64)
    scale, cmax, qp = sp["scale"], sp["cmax"], sp["qp"]
    if scale * cmax > 255:
        raise ValueError("the luma does not fit 8 bits")
    if len(cnt) and (cnt.min() < 1 or cnt.max() > cmax):
        raise ValueError("counts must be clipped to [1, cmax]")
    lossless = qp is None
    valid = (fw // 2, fh) if valid is None else valid
    fsz = fh * fw
    U = np.full((fh // 2) * (fw // 2), 128, dtype=np.uint8).tobytes()
    starts = np.searchsorted(key, np.arange(n_frames + 1) * fsz)
    gop = 1 if sp["intra"] else n_frames
    with tempfile.TemporaryDirectory(dir=workdir) as d:
        inp, out, dec, log = (os.path.join(d, f) for f in ("in.yuv", "out.hevc", "dec.yuv", "x265.csv"))
        Y = np.zeros(fsz, dtype=np.uint8)
        with open(inp, "wb") as f:
            for g in range(n_frames):
                a, b = starts[g], starts[g + 1]
                Y[key[a:b] - g * fsz] = (cnt[a:b] * scale).astype(np.uint8)
                f.write(Y.tobytes() + U + U)
                Y[key[a:b] - g * fsz] = 0
        rc = "lossless=1" if lossless else f"qp={int(qp)}"
        params = f"{rc}:keyint={gop}:min-keyint={gop}:{hd.PARAMS}:csv={log}:csv-log-level=1"
        enc = hd._run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-f", "rawvideo",
                       "-pix_fmt", "yuv420p", "-s", f"{fw}x{fh}", "-r", "90", "-i", inp, "-an", "-c:v", "libx265",
                       "-pix_fmt", "yuv420p", "-profile:v", "main", "-preset", hd.PRESET, "-x265-params", params,
                       "-f", "hevc", out])
        os.remove(inp)
        dec_s = hd._run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-threads", "1", "-i", out,
                         "-f", "rawvideo", "-pix_fmt", "yuv420p", dec])
        with open(out, "rb") as f:
            stream = f.read()
        stats = hd.parse_csv(log)
        if os.path.getsize(dec) != n_frames * (fsz + 2 * len(U)):
            raise AssertionError("x265_code: decoded and encoded picture counts differ")
        dk, dc = [], []
        with open(dec, "rb") as f:
            for g in range(n_frames):
                buf = np.frombuffer(f.read(fsz + 2 * len(U)), dtype=np.uint8)[:fsz].astype(np.int64)
                if lossless:
                    if np.any(buf % scale):
                        raise AssertionError("x265 lossless returned a luma off the scale")
                    v = buf // scale
                else:
                    v = np.clip((buf + scale // 2) // scale, 0, cmax)
                nz = np.flatnonzero(v)
                dk.append(nz + g * fsz)
                dc.append(v[nz])
    dkey, dcnt = np.concatenate(dk), np.concatenate(dc)
    if lossless and not (np.array_equal(dkey, key) and np.array_equal(dcnt, cnt)):
        raise AssertionError("x265 lossless did not return the counts")
    pad = hd._in_padding(dkey, fh, fw, valid)
    padding_counts = int(dcnt[pad].sum())
    dkey, dcnt = dkey[~pad], dcnt[~pad]
    bits, param_bits = fa.nal_bits(stream)
    if len(stats) != n_frames:
        raise AssertionError("x265 CSV and encoded picture counts differ")
    if qp is not None and any(r["qp"] != qp for r in stats):
        raise AssertionError("x265 coded a picture at a QP other than the one set")
    types = [_kind(r) for r in stats]
    if sp["intra"] and set(types) != {"I"}:
        raise AssertionError("an intra-only clip holds a picture that is not intra")
    if not sp["intra"] and (types[0] != "I" or set(types[1:]) - {"P"}):
        raise AssertionError("a clip is not one intra picture followed by P pictures")
    return {"bits": int(bits), "param_bits": int(param_bits), "enc_cpu_s": enc, "dec_cpu_s": dec_s,
            "padding_counts": padding_counts, "frames": stats, "key": dkey, "cnt": dcnt}


def count_errors(key, cnt, dkey, dcnt) -> dict:
    """Events of the decode against the input counts, both sparse with sorted unique keys.

    ``removed1`` and ``removed2``: input events of the voxels with input count 1 and >= 2 that the decode
    empties. ``lowered`` and ``raised``: events below and above the input in voxels that both hold. ``added``:
    events in voxels that the input leaves empty. ``in_events = removed1 + removed2 + kept`` and
    ``out_events = kept - lowered + raised + added`` with ``kept`` the input events of the voxels both hold."""
    key, cnt = np.asarray(key, dtype=np.int64), np.asarray(cnt, dtype=np.int64)
    dkey, dcnt = np.asarray(dkey, dtype=np.int64), np.asarray(dcnt, dtype=np.int64)
    if np.any(np.diff(key) <= 0) or np.any(np.diff(dkey) <= 0):
        raise ValueError("count_errors needs sorted unique keys")
    both, i, j = np.intersect1d(key, dkey, assume_unique=True, return_indices=True)
    gone = np.ones(len(key), dtype=bool)
    gone[i] = False
    new = np.ones(len(dkey), dtype=bool)
    new[j] = False
    c, d = cnt[i], dcnt[j]
    out = {"in_events": int(cnt.sum()), "out_events": int(dcnt.sum()),
           "in_vox1": int((cnt == 1).sum()), "in_vox2": int((cnt >= 2).sum()),
           "removed1": int(cnt[gone & (cnt == 1)].sum()), "removed2": int(cnt[gone & (cnt >= 2)].sum()),
           "kept": int(c.sum()), "lowered": int(np.maximum(c - d, 0).sum()), "raised": int(np.maximum(d - c, 0).sum()),
           "added": int(dcnt[new].sum()), "added_vox": int(new.sum())}
    if out["removed1"] + out["removed2"] + out["kept"] != out["in_events"]:
        raise AssertionError("count_errors: input events do not add up")
    if out["kept"] - out["lowered"] + out["raised"] + out["added"] != out["out_events"]:
        raise AssertionError("count_errors: output events do not add up")
    return out


def _kind(row) -> str:
    """The slice type of a CSV row, ``I``, ``P`` or ``B`` (x265 writes ``I-SLICE``, ``P-SLICE``, ...)."""
    return row["type"].strip().upper()[:1]


def _summary(frames) -> dict:
    """Bits of the intra and the P pictures, and the mean shares of the coding units of the P pictures."""
    I = [r for r in frames if _kind(r) == "I"]
    P = [r for r in frames if _kind(r) == "P"]
    out = {"I_bits": float(sum(r["bits"] for r in I)), "P_bits": float(sum(r["bits"] for r in P)),
           "n_I": len(I), "n_P": len(P)}
    for kind in hd.CSV_KINDS:
        out["P_" + kind.lower()] = float(np.mean([r[kind.lower()] for r in P])) if P else float("nan")
    return out


def code_controls(windows, w: int, s: int, k: int, width: int, height: int, modes, phi: float, theta: float,
                  tasks=None, task_modes=(), workdir=None, K: int = hd.K_WIN) -> dict:
    """The modes of ``modes`` for one group and grid (``sparse`` and ``sparse_raw`` are coder Q on the counts
    clipped at 15 and unclipped). Tasks run on the decodes of ``task_modes`` at both placements of
    ``ec.hevcdiag.PLACEMENTS``, as ``ec.hevcdiag.code_counts`` runs them."""
    nx, ny, fh, fw = hd.dims(s, width, height)
    key, raw = hd.voxel_counts(windows, w, K, s, k, width, height)
    out = {"s": s, "k": k, "n_true": [int(len(v[0])) for v in windows[:K]], "raw_events": int(raw.sum()),
           "raw_max": int(raw.max()) if len(raw) else 0, "clipped": {}, "clip_fid": {}, "modes": {}}
    for cmax in sorted({spec(m)["cmax"] for m in modes if not m.startswith("sparse")} | {hd.HEVC_MAX}):
        c = np.minimum(raw, cmax)
        out["clipped"][str(cmax)] = int((raw - c).sum())
        ev = hd.voxels_to_windows(key, c, w, K, s, k, width, height, "start")
        out["clip_fid"][str(cmax)] = hd.fidelities([hd.sums_on(windows[m], ev[m], (w + m) * hd.T0, (s, k), width,
                                                               height, phi, theta) for m in range(K)])
    for mode in modes:
        if mode in ("sparse", "sparse_raw"):
            c = np.minimum(raw, hd.HEVC_MAX) if mode == "sparse" else raw
            out["modes"][mode] = hd.sparse(key, c, w, K, s, k, width, height)
            continue
        sp = spec(mode)
        c = np.minimum(raw, sp["cmax"])
        r = x265_code(key, c, K * k, fh, fw, sp, workdir, valid=(nx, ny))
        dkey, dcnt = r.pop("key"), r.pop("cnt")
        r["summary"] = _summary(r.pop("frames"))
        ev = hd.voxels_to_windows(dkey, dcnt, w, K, s, k, width, height, "start")
        r["fid"] = hd.fidelities([hd.sums_on(windows[m], ev[m], (w + m) * hd.T0, (s, k), width, height, phi, theta)
                                  for m in range(K)])
        if sp["qp"] is not None:
            r["errors"] = count_errors(key, c, dkey, dcnt)
            if tasks is not None and mode in task_modes:
                r["tasks"] = {pl: tasks.run(ev if pl == "start" else
                                            hd.voxels_to_windows(dkey, dcnt, w, K, s, k, width, height, pl))
                              for pl in hd.PLACEMENTS}
        out["modes"][mode] = r
    return out
