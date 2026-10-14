# Directive 021. Controls for the HEVC diagnostics: prediction, amplitude mapping, clipping

| | |
|---|---|
| track | `hevc controls`, short name `hc` |
| population | the D1 groups of directive 019, and its D3 model scenes |
| results directory | `results/hc/` |
| report | `docs/directives/reports/021.md` |
| runs after | directive 020 |

## 1. Why

Directive 019 compared x265 with coder Q, a list of the counts. A review of the manuscript raised three
points that this comparison cannot answer:

1. **Prediction.** x265 against coder Q compares two complete coders, which also differ in partitioning,
   syntax and entropy coding. It does not say what the temporal prediction of x265 saves. The control is
   the same x265 on the same counts with every picture intra.
2. **Amplitude mapping.** The lossy modes code luma = 16 count and the lossless mode luma = count. A lossy
   point that costs more than the lossless one mixes the quantizer with the mapping. The control is
   lossless x265 on luma = 16 count. The review also asks what the lossy decode does to the counts: how
   many events it removes, lowers, raises and adds.
3. **Clipping.** Counts are clipped at 15. On coarse grids this removes up to 28% of the events (019,
   night, s = 2, k = 1), which changes the input. The controls are an unclipped lossless code and a lossy
   mapping that keeps counts up to 63.

This directive runs these controls. It adds no task beyond those of directive 019 and no new coder.

## 2. Disclosure

The director wrote `ec/hevcctl.py` and `tests/test_hevcctl_gate.py` and ran them on synthetic events
only, with ffmpeg 6.1.1 and libx265 3.5. On a model scene of 160 x 120 pixels (tau = 1 ms, n = 3,
4 windows):

- lossless, one intra picture and P pictures against all intra: 0.69 against 1.85 bits per event at
  k = 3, and 9.58 against 16.18 at k = 64, with coder Q at 5.45;
- lossless on luma = 16 count: 16.66 bits per event at k = 64;
- at QP 20 and k = 64, the decode removes 18,813 of 34,552 events, all from voxels with one event, and
  adds 2,102.

An independent review of the code by a second agent found no bug that would crash a run or bias a
number, and one design flaw: x265's in-loop filters (SAO, deblocking) act in fixed luma units, so luma =
4 count at QP q - 12 is not the same decoder as luma = 16 count at QP q, even where nothing is clipped.
On the model the two differ in their raised and added events by up to a factor of nine at QP 46. The
mode `qp<q>_s4c15` was added: it differs from `qp<q>_s4` only in the clip, so their difference is the
clipping alone. The review's minor points are also in:

- a check of the QP of every picture;
- a check that the keys are sorted;
- tasks at both placements, as in directive 019;
- tests of the clip at 63 and of `s4` against `s4c15`.

The full suite passes (148 tests). The director read no recording.

## 3. Author decisions

**D-021-1, default: authorized.** The executor adds `ec/hevcctl.py` and `tests/test_hevcctl_gate.py`
with the content of Appendices A and B, unchanged. The ffmpeg and x265 of directive 019 on `cnt` are
used, and their versions are recorded.

**D-021-2, default: authorized.** The runner may reuse the functions of `scripts/hd_run.py` for the
groups, the events, the background and the tasks (`groups`, `events`, `context`), unchanged. The reads
are those of directive 019.

**D-021-3, default: as stated in Sections 4 to 7.** The protocol.

## 4. Definitions

**Groups, events, background, tasks, strata.** Those of directive 019, Section 4, for its D1 groups (`j %
40 == 0` on eTraM, `j % 20 == 0` on DSEC).

**Fine part.** Every grid of directive 019 (`s` in `ec.hevcdiag.SPACES`, `k` in `ec.hevcdiag.KS`) with
the modes `ec.hevcctl.FINE_MODES`:

- `lossless`, `lossless_intra`, `lossless_x16`, `sparse`;
- `qp<q>` and `qp<q>_intra` for every q of `ec.hevcdiag.QPS`.

**Coarse part.** The grids `ec.hevcctl.COARSE_GRIDS`, (2, 3), (2, 1) and (1, 1), with the modes
`ec.hevcctl.COARSE_MODES`:

- `lossless_c255` and `sparse_raw`;
- `qp<q>`, `qp<q>_s4` and `qp<q>_s4c15` for q in (14, 28, 36, 46).

The tasks run on every lossy mode of the coarse part, at both placements.

**Model.** The 36 D3 scenes of directive 019 (`tau` in (250, 500, 1000, 2000, 4000, 8000) us, `n` in
(1, 3), seed in (1, 2, 3), 320 x 240 pixels, `u = 6`, `sigma_frac = 0.05`, `spacing = 40`, 12
windows), on the windows `ec.hevcdiag.windows_of(ev, 1, 4)` with key window 1, every grid, the fine
modes, `phi = 1` and `theta = 0`, and no tasks.

## 5. Run

For every D1 group:

- for every grid of the fine part: `ec.hevcctl.code_controls(windows, w, s, k, W, H, FINE_MODES, phi,
  theta, workdir=<local scratch>)`;
- for every grid of the coarse part: `ec.hevcctl.code_controls(windows, w, s, k, W, H, COARSE_MODES, phi,
  theta, tasks=tasks, task_modes=<the lossy modes of COARSE_MODES>, workdir=<local scratch>)`.

For every model scene and grid: `ec.hevcctl.code_controls(windows_of(ev, 1, 4), 1, s, k, 320, 240,
FINE_MODES, 1.0, 0.0, workdir=<local scratch>)`.

Keep each output per group or scene. Use `~/prjs/event_coding/hc/` for eTraM and the model, and
`/data/<user>/event_coding/ds/hc/` for DSEC. One encode is single threaded, as in directive 019. A run at
s = 1, k = 64 writes about 1.4 GB of YUV files in its scratch directory, so put the scratch on local disk
with that much free space per worker.

## 6. Tables

A recording enters with sums over its groups, under the entering rule of directive 019. Report medians
over recordings with 95% intervals (the bootstrap of directive 007, seed 20261016). Bits are per true
event; error counts are shares of the input events of the mode, from sums.

**Table 1, prediction without loss (fine part).** Per stratum, `s` and `k`:

- bits of `lossless`, `lossless_intra`, `sparse` and `lossless_x16`;
- the per-recording medians of the ratios `lossless_intra / lossless` (the saving of the temporal
  prediction), `lossless / sparse`, and `lossless_x16 / lossless` (the cost of the mapping);
- for `lossless`, the bits of the I picture and of the P pictures as shares.

**Table 2, prediction with loss (fine part).** Per stratum, `s`, `k` and QP: F, Fsnr and bits of `qp<q>`
and of `qp<q>_intra`. Then, per stratum, `s` and `k`, for F targets 0.9 and 0.95, the bits of each of the
two at which the QP ladder reaches the target, interpolated linearly in F between the two consecutive QPs
that bracket it, per recording, and their ratio. The value is NaN outside the ladder, and the report gives
the number of NaN.

**Table 3, what the lossy decode does to the counts (fine part, `qp<q>`).** Per stratum, `s`, `k` and
QP, as shares of the input events:

- `removed1`, `removed2` and `lowered`;
- `raised` and `added`;
- the share of input events that lie in voxels with count 1;
- the total of `padding_counts`.

The same for `qp<q>_intra`, in `report.json`.

**Table 4, clipping on coarse grids (coarse part).** Per stratum and coarse grid:

- the clipped shares at 15, 63 and 255, and the F of the clipped counts at each (`clip_fid`);
- bits of `lossless_c255` and `sparse_raw`, and their ratio.

Then per QP in (14, 28, 36, 46), for `qp<q>`, `qp<q>_s4c15` and `qp<q>_s4`:

- bits, F and Fsnr;
- the task scores of directive 019, Table 2, at placement `start` (`center` in `report.json`).

The differences `s4 - s4c15` (clipping) and `s4c15 - qp` (mapping) are reported with their intervals.

**Table 5, the model.** Per `tau`, `n`, `s` and `k`, the mean over seeds of:

- bits of `lossless`, `lossless_intra`, `sparse` and `lossless_x16`, and of the P pictures of `lossless`;
- per QP, F and bits of `qp<q>` and `qp<q>_intra`, and the error shares of Table 3.

**Curve data.** `results/hc/curves.json` holds, per stratum (and per model `tau` and `n`), `s`, `k` and
mode, the pooled sums behind F and the bits, and the error totals. The manuscript draws its figures from
this file.

## 7. Cost

- Project from the first 10 D1 groups of each dataset and the first model scene.
- If the projection exceeds 350 CPU-hours, stop and report `BLOCKED` with it.
- Directive 019's D1 cost 75 CPU-hours for 9 encodes per grid. The fine part has 19 encodes per grid,
  of which the intra ones code every picture without temporal prediction.
- Use the read lock and memory guard of directive 016. Do not compete with a companion-project job.

## 8. Acceptance checks

1. The two files have the SHA-256 of Section 10, and the suite passes with no skipped test, ffmpeg tests
   included.
2. Every call of Section 5 returned. Each call checks:
   - the lossless decodes;
   - the slice types and the QP of every picture;
   - the identities of `count_errors`.
3. **Reproduction of directive 019.** For every D1 group and fine grid, the bits of `lossless`, `sparse` and
   every `qp<q>` equal those of the directive 019 output of the same group and grid, and so does the F of
   every `qp<q>`. A mismatch means that the encoder or the counts changed: stop and report `BLOCKED` with
   the first mismatch.
4. No eTraM val or test file was opened, and the annotation root was not listed. Nothing outside
   `results/hc/` changed under `results/`.

## 9. Outputs

| file | content |
|---|---|
| `results/hc/per_recording.json` | per recording, the sums of every mode and grid, and the number of groups |
| `results/hc/model.json` | the model outputs, per scene and grid, without per-picture rows |
| `results/hc/curves.json` | the curve data of Section 6 |
| `results/hc/report.json` | Tables 1 to 5 and acceptance check 3 |
| `results/hc/provenance.json` | commit, host, versions, wall and CPU time, the files read |

## 10. Files

The SHA-256 is that of the file content: the text between the fence lines of its appendix, ending in one
newline.

| file | SHA-256 |
|---|---|
| `ec/hevcctl.py` | `ca1e5f6463acb49c64e525442f7b47e9c0fbfe860e1b31b28dc030ceca84d4fa` |
| `tests/test_hevcctl_gate.py` | `e13c8d5b9afc3ea06a6878d6917bc59ed9425680878a40ba6cf9fd0a975d4603` |

## Appendix A. `ec/hevcctl.py`

````python
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
````

## Appendix B. `tests/test_hevcctl_gate.py`

````python
"""Gate for directive 021: the controls of ``ec.hevcctl`` on synthetic counts and on the model of directive 019."""
import numpy as np
import pytest

from ec import hevcctl as hc
from ec import hevcdiag as hd

W, H = 96, 64


def test_specs():
    assert hc.spec("lossless") == {"intra": False, "scale": 1, "cmax": 15, "qp": None}
    assert hc.spec("lossless_intra")["intra"] and hc.spec("lossless_intra")["qp"] is None
    assert hc.spec("lossless_x16")["scale"] == 16 and hc.spec("lossless_c255")["cmax"] == 255
    assert hc.spec("qp20") == {"intra": False, "scale": 16, "cmax": 15, "qp": 20}
    assert hc.spec("qp20_intra") == {"intra": True, "scale": 16, "cmax": 15, "qp": 20}
    assert hc.spec("qp46_s4") == {"intra": False, "scale": 4, "cmax": 63, "qp": 34}
    assert hc.spec("qp46_s4c15") == {"intra": False, "scale": 4, "cmax": 15, "qp": 34}
    for bad in ("qp8_s4", "qp20_x", "lossy"):
        with pytest.raises(ValueError):
            hc.spec(bad)
    for m in hc.FINE_MODES + hc.COARSE_MODES:          # every listed mode parses, and its luma fits 8 bits
        if not m.startswith("sparse"):
            sp = hc.spec(m)
            assert sp["scale"] * sp["cmax"] <= 255


def test_count_errors_by_construction():
    key = np.array([1, 2, 3, 5, 8, 9])
    cnt = np.array([1, 3, 1, 2, 1, 4])
    dkey = np.array([2, 3, 4, 8, 9])
    dcnt = np.array([1, 2, 2, 1, 6])
    e = hc.count_errors(key, cnt, dkey, dcnt)
    assert e["removed1"] == 1 and e["removed2"] == 2                    # voxel 1 (count 1), voxel 5 (count 2)
    assert e["kept"] == 3 + 1 + 1 + 4 and e["lowered"] == 2 and e["raised"] == 1 + 2
    assert e["added"] == 2 and e["added_vox"] == 1
    assert e["in_events"] == 12 and e["out_events"] == 12
    assert e["in_vox1"] == 3 and e["in_vox2"] == 3


def _random_counts(rng, n_frames, fh, fw, cmax, density=0.05):
    keys = np.flatnonzero(rng.random(n_frames * fh * fw) < density)
    return keys, rng.integers(1, cmax + 1, len(keys))


@pytest.mark.parametrize("mode", ["lossless", "lossless_intra", "lossless_x16", "lossless_c255"])
def test_lossless_modes_return_the_counts(mode, tmp_path):
    rng = np.random.default_rng(1)
    nx, ny, fh, fw = hd.dims(1, W, H)
    sp = hc.spec(mode)
    key, cnt = _random_counts(rng, 6, fh, fw, sp["cmax"])
    col, row = key % fw, (key // fw) % fh
    ok = (col % (fw // 2) < nx) & (row < ny)
    key, cnt = key[ok], cnt[ok]
    r = hc.x265_code(key, cnt, 6, fh, fw, sp, str(tmp_path), valid=(nx, ny))
    assert np.array_equal(r["key"], key) and np.array_equal(r["cnt"], cnt)
    types = [hc._kind(f) for f in r["frames"]]
    assert types == (["I"] * 6 if sp["intra"] else ["I"] + ["P"] * 5)
    assert r["bits"] > 0 and r["padding_counts"] == 0


def test_scale4_keeps_counts_above_15(tmp_path):
    rng = np.random.default_rng(2)
    nx, ny, fh, fw = hd.dims(1, W, H)
    key, cnt = _random_counts(rng, 4, fh, fw, 80, density=0.02)
    col, row = key % fw, (key // fw) % fh
    ok = (col % (fw // 2) < nx) & (row < ny)
    key, cnt = key[ok], cnt[ok]
    r = hc.x265_code(key, np.minimum(cnt, 63), 4, fh, fw, hc.spec("qp14_s4"), str(tmp_path), valid=(nx, ny))
    e = hc.count_errors(key, np.minimum(cnt, 63), r["key"], r["cnt"])
    assert e["in_events"] == int(np.minimum(cnt, 63).sum()) and cnt.max() > 63
    assert e["out_events"] > 0.9 * e["in_events"]
    assert r["cnt"].max() > 15                                         # the clip at 15 is gone
    assert all(f["qp"] == 2 for f in r["frames"])


_MODEL = {}


def model():
    if not _MODEL:
        ev = hd.edge_scene(W, H, 6, 1000.0, 3, 0.05, 40, 6, 1)
        _MODEL["win"] = hd.windows_of(ev, 1, hd.K_WIN)
    return _MODEL["win"]


def test_controls_match_directive_019_on_the_model(tmp_path):
    win = model()
    modes = ("lossless", "sparse", "qp20")
    a = hd.code_counts(win, 1, 1, 12, W, H, modes, 1.0, 0.0, workdir=str(tmp_path))
    b = hc.code_controls(win, 1, 1, 12, W, H, modes + ("lossless_intra", "qp20_intra"), 1.0, 0.0,
                         workdir=str(tmp_path))
    for m in modes:                                    # same encoder, settings and counts: the same bits
        assert b["modes"][m]["bits"] == a["modes"][m]["bits"]
    assert b["modes"]["qp20"]["fid"] == a["modes"]["qp20"]["fid"]
    assert b["clip_fid"]["15"] == a["clip_fid"] and b["clipped"]["15"] == a["clipped_events"]
    s = b["modes"]["lossless_intra"]["summary"]
    assert s["n_I"] == hd.K_WIN * 12 and s["n_P"] == 0
    s = b["modes"]["lossless"]["summary"]
    assert s["n_I"] == 1 and s["n_P"] == hd.K_WIN * 12 - 1
    e = b["modes"]["qp20"]["errors"]
    assert e["in_events"] == sum(b["n_true"]) - b["clipped"]["15"]


def test_controls_are_deterministic(tmp_path):
    win = model()
    modes = ("lossless_intra", "lossless_x16", "qp28_intra", "qp28_s4")
    a = hc.code_controls(win, 1, 2, 3, W, H, modes, 1.0, 0.0, workdir=str(tmp_path))
    b = hc.code_controls(win, 1, 2, 3, W, H, modes, 1.0, 0.0, workdir=str(tmp_path))
    for m in modes:
        assert a["modes"][m]["bits"] == b["modes"][m]["bits"]
        assert a["modes"][m]["fid"] == b["modes"][m]["fid"]


def test_coarse_controls_clip_and_unclipped_list(tmp_path):
    rng = np.random.default_rng(3)
    t = np.sort(rng.integers(hd.T0, 5 * hd.T0, 6000))                 # one hot pixel with many events per voxel
    x = np.where(rng.random(6000) < 0.5, 7, rng.integers(0, W, 6000))
    y = np.where(x == 7, 9, rng.integers(0, H, 6000))
    p = rng.integers(0, 2, 6000)
    o = np.argsort(t, kind="stable")
    ev = tuple(a[o].astype(np.int64) for a in (t, x, y, p))
    win = hd.windows_of(ev, 1, hd.K_WIN)
    r = hc.code_controls(win, 1, 2, 1, W, H, ("lossless_c255", "sparse_raw", "sparse", "qp28", "qp28_s4"), 1.0, 0.0,
                         workdir=str(tmp_path))
    assert r["raw_max"] > 63 and r["clipped"]["15"] > r["clipped"]["63"] > r["clipped"]["255"] >= 0
    assert r["clip_fid"]["255"]["F"] >= r["clip_fid"]["63"]["F"] >= r["clip_fid"]["15"]["F"]
    assert r["modes"]["sparse_raw"]["bits"] >= r["modes"]["sparse"]["bits"]
    assert r["modes"]["qp28_s4"]["errors"]["in_events"] == r["raw_events"] - r["clipped"]["63"]


def test_s4_modes_differ_only_in_the_clip(tmp_path):
    win = model()
    r = hc.code_controls(win, 1, 2, 3, W, H, ("qp28_s4", "qp28_s4c15"), 1.0, 0.0, workdir=str(tmp_path))
    assert r["raw_max"] <= 15                                          # nothing to clip on the model
    a, b = r["modes"]["qp28_s4"], r["modes"]["qp28_s4c15"]
    assert a["bits"] == b["bits"] and a["fid"] == b["fid"] and a["errors"] == b["errors"]


def test_tasks_run_at_both_placements(tmp_path):
    class Tasks:
        def run(self, ev):
            return {"n": int(sum(len(e[0]) for e in ev)), "t0": int(ev[0][0].min()) if len(ev[0][0]) else -1}
    win = model()
    r = hc.code_controls(win, 1, 1, 3, W, H, ("qp20", "lossless"), 1.0, 0.0, tasks=Tasks(), task_modes=("qp20",),
                         workdir=str(tmp_path))
    t = r["modes"]["qp20"]["tasks"]
    assert set(t) == set(hd.PLACEMENTS) and t["start"]["n"] == t["center"]["n"]
    assert t["start"]["t0"] < t["center"]["t0"] and "tasks" not in r["modes"]["lossless"]
````
