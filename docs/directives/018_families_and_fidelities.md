# Directive 018. A video-coding baseline, five families of schemes, and which fidelity predicts the tasks

| | |
|---|---|
| track | `families`, short name `fm` |
| population | eTraM: the reporting recordings of directive 007 and their train annotations. DSEC: the 36 reporting sequences of directive 013 and the DSEC-Detection labels kept by directive 017 |
| results directory | `results/fm/` |
| report | `docs/directives/reports/018.md` |
| runs after | directive 017 |

## 1. Why

REMAKE has so far been compared with three kinds of scheme. The first
two predict nothing: random subsets, whole windows, and the blocks of
the key-window rule. The third, the flow-based baseline of directive
016, almost never predicted at its frozen configuration. Its fidelity was
0.999 or more. The fidelity itself counts events, so a scheme that
spends its bits on the densest blocks scores well. On the tasks of
directive 016, such a scheme can still lose half of the objects. This
directive measures:

1. **A motion-compensated video coder as baseline.** The voxel counts of
   the working grid are coded as video by HEVC (x265) at a ladder of
   QPs. This is the hybrid coder with motion compensation, residual and
   rate-distortion mode decision that REMAKE has to beat. On a synthetic
   translating box, it reached REMAKE's fidelity with about half of
   REMAKE's bits.
2. **Five families of operating points on the same groups:**
   - `thin`, a random subset;
   - `select`, whole dense blocks;
   - `cap`, at most n events per block;
   - `hevc`, the video coder above;
   - `fbc`, the flow-based baseline with its events without flow coded
     on the working grid, at the configuration frozen in 016 and at eight
     that predict more.

   `select` is the subset that the event fidelity F favors, since dense
   blocks cost the fewest bits per event. `cap` is the subset that the
   background-referenced fidelity Fsnr favors.
3. **Four candidate fidelities for every scheme.** Each candidate is
   additive over windows, so a later codec can optimize it with one
   Lagrange multiplier:
   - F, Eq. (fid);
   - F20, the same on blocks of 20 px;
   - FH, a Hellinger affinity on cells of 8 px;
   - Fsnr, a per-block fidelity referenced to the background of the
     group.

   Fsnr values a block by ln(1 + n / φ), its count in units of the
   background φ of the group. A block enters only where the true or the
   rebuilt field exceeds the upper 10^-3 Poisson quantile of φ. A block
   that holds only background is therefore worth nothing, and no constant
   is tuned to the data.

   The sender estimates the background rate for each group from the
   events it holds before the targets, without hot pixels. It forms two
   estimates, each an upper bound when its own assumption fails, and
   takes the smaller:
   - from the isolated events (no same-polarity neighbor within 10 ms,
     the neighborhood of the background filter of eTraM), by inverting
     the isolation probability of a Poisson background;
   - from the median rate of the blocks.

   The definitions are in the docstring of Appendix A.
4. **The tasks of the two datasets at every operating point.** Both
   datasets label boxes with track ids, for detection and tracking:
   eTraM [verma2024etram], and DSEC-Detection [dsec_detection], kept by
   directive 017. Without a trained model we score:
   - *detection*: the box scores of directive 016;
   - *tracking*: for each track present in windows 1 to 3, whether every
     window rebuilds events in its box, and the error of the velocity
     of its centroid;
   - *motion*: the velocity found by contrast maximization, as in 016.

   Equal bits are then reached by interpolation along each family. The
   rank agreement between each candidate and each task score tells which
   fidelity predicts what a receiver can do.

This directive decides nothing about the next codec. The author chooses
the distortion measure from its report. The codec with a Lagrangian mode
decision (SKIP, INTRA, EMPTY per block and window, the key events of a
block as the parent of its later SKIPs) follows in a later directive.

## 2. Disclosure

The director wrote `ec/families.py` and `tests/test_families_gate.py`
and ran them on synthetic events only, in seconds, with ffmpeg 6.1.1 and
libx265 on the director's host. That run gave the statement on the
synthetic box in Section 1.

An independent review of the code by a second agent found no wrong
formula. It found six biases, all fixed before Fsnr and the tracking
score were added:

- the kept ranks of `cap` leaned late in time; they are now centered;
- the rounding of decoded luma was asymmetric; it is now floor of
  (Y + 8) / 16;
- the encoder could silently convert the pixel format; it is now pinned
  to 8-bit `yuv420p`, profile main;
- the window check missed windows 4 to 10; it now covers every window
  of every K;
- the frozen configuration of 016 was missing from the FBC ladder;
- the log fidelity could reach -0.0; it is now clipped.

A second review of Fsnr, the background estimate and the tracking score
found five issues, all fixed:

- the DSEC labels are on the absolute clock; directive 017, Section 4,
  now settles the time base;
- at 20 Hz labels, tracks were never complete; boxes are now
  interpolated;
- slow texture and hot pixels inflated the isolation estimate; the
  quiet-block bound and the hot-pixel rule now cover this;
- above 12.5 events per pixel and second the isolation estimate took the
  wrong root; the quiet-block bound now selects the branch;
- a large background zeroed Fsnr for subsets; the threshold now only
  decides which blocks enter.

On synthetic Poisson noise from 0.3 to 40 events per pixel and second,
the estimate is within 3%. It stays within 15% with a moving edge or 20
hot pixels added. On a moving edge alone it gives no background above one
event per block and window.

The review measured about 123 CPU-seconds and 1.4 GB per group on a
synthetic 640 × 480 group with 1.76 million events. The director read no
recording.

## 3. Author decisions

**D-018-1, default: authorized.** The executor adds `ec/families.py` and
`tests/test_families_gate.py` with the content of Appendices A and B,
unchanged.

**D-018-2, default: authorized.** The executor installs ffmpeg with
libx265 under its own user on `cnt`, without changing the system. A
static build or a conda environment are both acceptable. It records the
versions of ffmpeg and x265 in `results/fm/provenance.json`. The tests
of Appendix B run ffmpeg and are not skipped.

**D-018-3, default: authorized.** The reads of directive 017,
Section 3, again.

**D-018-4, default: as stated in Sections 4 to 7.** The protocol.

## 4. Definitions

**Groups.** Those of directive 017, Section 4: the Stage R groups that
directive 016 used, with the kept group `g` and its records of
configuration (20, 1).

**Events of a group.** The events of
`[w T0 - ec.fbc.FIT_WINDOW_US, (w + 11) T0)`, as in directive 016.

**Boxes and squares.** As in directive 016, Section 7:

- `boxes = {m: ec.regions.boxes_at(tracks, w + m, W, H) for m in (1, 2, 3)}`
  on both datasets, with the tracks and the DSEC time base of
  directive 017, Section 4, and None for a sequence without labels.
  `boxes_at` interpolates each box at the center of the window. Directive
  016 took the nearest labeled frame, which leaves windows without a box
  at the 20 Hz of DSEC-Detection.
- `squares = scripts/fb_run.py:squares_for(window w + 2, W, H)` on both
  datasets.

The module keeps a box only if it holds at least 50 true events of its
window.

**Schemes.** The 43 names of `ec.families.scheme_names()`:

| family | schemes |
|---|---|
| REMAKE | `remake`, `translation`, `static` |
| `thin` | 8 shares |
| `select` | 7 densities |
| `cap` | 8 caps |
| `hevc` | 8 QPs |
| `fbc` | 9 configurations |

## 5. Run

For every group, call

    ec.families.evaluate_group(ev, w, W, H, g["records"], g, boxes=boxes, squares=squares, workdir=<local scratch>)

Keep its output per group, under `~/prjs/event_coding/fm/` for eTraM and
`/data/<user>/event_coding/ds/fm/` for DSEC.

- `workdir` is a directory on a local disk of the host, under the
  project's own paths. The HEVC files are written and deleted there.
- Size the number of workers to about 3 GB per DSEC worker.

## 6. Tables

A recording enters with sums over its groups, with the entering rule of
report 016. For a scheme, a recording and K = 4 or 11:

- **Bits:** `b = Σ bits / Σ n_true[:K]`.
- **Fidelities:** `ec.families.fidelities` of the window sums of all its
  groups. Fsnr uses the background of each group, which the window sums
  already carry.
- **Tasks (K = 4, windows 1 to 3):**
  - over boxes: the mean of `F`, the share with `n_rec` = 0, and the
    median of `centroid_px` over the others;
  - by box size: the same over boxes with 50 to 199, 200 to 999, and at
    least 1000 true events;
  - over tracks: the share with `continuous` True, and the median of
    `velocity_error_px` over the continuous ones;
  - over squares: the median of `error_px` over finite values, and the
    share with `n_rec` = 0.

Medians over recordings come with the bootstrap of directive 007, seed
20261016. Strata: day and night for eTraM, `all` for DSEC.

**Table 1, bits at REMAKE's fidelity.** For each recording, K, and family
f in `thin`, `select`, `cap`, `hevc`, `fbc`, the union of the three
subset families, and the union of all five:

    b_f = ec.blockcodec.baseline_bits(F_remake, [F of the points of f] + [1], [b of the points] + [b_direct])

Here `b_direct` is `Σ direct_bits[:K] / Σ n_true[:K]`. This is the lower
convex envelope of the points, which time sharing over groups reaches.
Report `G_f = b_f / b_remake`, the same for `translation` and `static`
against the union of all five, and the number of recordings that enter.

**Table 2, everything at REMAKE's bits, K = 4.** For each family, sort
its points by `b`. Interpolate every fidelity and task score linearly in
`b` at `b_remake`. The value is NaN where `b_remake` lies outside the
points, and the report gives how many recordings are NaN. Next to the
interpolated values, report those of `remake`, `translation` and
`static`.

**Table 3, which fidelity predicts the tasks.**

- For each recording, take the 43 schemes at K = 4.
- Compute each candidate on the sums of windows 1 to 3 only, the windows
  of the tasks.
- Compute Kendall's τ_b (`scipy.stats.kendalltau`) between each
  candidate and each task score. Orient every score so that larger is
  better:
  - mean box F;
  - 1 minus the empty-box share;
  - minus the median centroid error;
  - the share of continuous tracks;
  - minus the median track velocity error;
  - minus the median motion error;
  - 1 minus the share of squares without events.
- Drop schemes whose score is NaN.
- Report the median over recordings, per stratum.

**Table 4, accounting.** Per stratum:

- for every `hevc` scheme, the median share of `param_sei_bits` in its
  bits, and the total of `clipped_events` over the population;
- for every `fbc` scheme, the median `st_us`;
- the median and the 10th and 90th percentiles over groups of
  `beta_per_px_s`, `beta_iso`, `beta_med`, `phi` and `theta`;
- the number of groups with `saturated`, with `near_saturation`, and
  with `branch` = -1, and the median of `n_hot`;
- per scheme, the median share of blocks that enter Fsnr.

If more than 5% of the groups of a stratum are `saturated`, the report
says so next to every Fsnr value of that stratum.

**Frontier data.** Per stratum and K, the medians over recordings of `b`
and of every fidelity for every scheme, in `results/fm/frontier.json`.
The manuscript draws its figures from this file.

## 7. Cost

- Project from the first 20 finished groups of each dataset.
- If the projection exceeds 600 CPU-hours, stop and report `BLOCKED`
  with it.
- A run that then costs more than projected is let finish, and both
  numbers are reported.
- Use the read lock and memory guard of directive 016.
- Do not compete with a companion-project job.

## 8. Acceptance checks

1. The two files have the SHA-256 of Section 10. The suite passes with
   no skipped test, including the ffmpeg tests.
2. For every group:
   - `checks["remake_equals_kept"]` is True;
   - `checks["outside"]` is 0.
3. **Determinism.** For the first group of five recordings of each
   dataset, `ec.families.hevc_code` is run twice on its K = 4 frames at
   every QP, and the two streams are equal.
4. The K = 4 medians of `F` and `b` for `remake` (coder Q) equal the
   REMAKE values that acceptance check 5 of report 016 lists, in
   `results/fb/report.json#/acceptance/5_remake_K4_equals_reports`.
5. No eTraM val or test file was opened, and the annotation root was not
   listed. Nothing outside `results/fm/` changed under `results/`.

## 9. Outputs

| file | content |
|---|---|
| `results/fm/per_recording.json` | per recording, scheme and K: `b`, the four fidelities, the sums of windows 1 to 3, and the task scores |
| `results/fm/report.json` | Tables 1 to 4 |
| `results/fm/frontier.json` | the frontier data of Section 6 |
| `results/fm/provenance.json` | commit, host, versions of ffmpeg and x265, wall and CPU time, and the files read |

## 10. Files

The SHA-256 is that of the file content: the text between the fence
lines of its appendix, ending in one newline.

| file | SHA-256 |
|---|---|
| `ec/families.py` | `07f3af517840ff6d692d7db6893508c9f964ead252fe5958fd1ab6819b2a2a4e` |
| `tests/test_families_gate.py` | `ef6e0bf634338460e29a2afc4cf320634b25ac7249b2070f484c21b483c7c4d7` |

## Appendix A. `ec/families.py`

````python
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
````

## Appendix B. `tests/test_families_gate.py`

````python
"""Gate for directive 018: the families of schemes, the candidate fidelities and the HEVC path, on synthetic
events. The HEVC tests run ffmpeg with libx265 and are not skipped: the suite fails on a host without them.
The tolerances are fixed by the director.
"""
import numpy as np

from ec import blockcodec as bc
from ec import families as fa
from ec import fbc
from ec import synth

W, H, WKEY = 320, 240, 6
T0 = bc.T0_US


def scene(seed=3):
    s = synth.rigid_translation(width=W, height=H, n_points=1500, box_wh=(80.0, 60.0), c0=(60.0, 120.0),
                                v=(200.0, 0.0), duration_s=1.0, noise_rate_hz=0.05, seed=seed)
    return (s.t.astype(np.int64), s.x.astype(np.int64), s.y.astype(np.int64), s.p.astype(np.int64)), s.boxes


def windows(ev, K=11):
    t = ev[0]
    out = []
    for m in range(K):
        a, b = np.searchsorted(t, ((WKEY + m) * T0, (WKEY + m + 1) * T0))
        out.append(tuple(v[a:b] for v in ev))
    return out


# ---------------------------------------------------------------------------------- fidelities

def test_fidelities_of_the_truth_of_nothing_and_of_a_subset():
    ev, _ = scene()
    win = windows(ev, 3)
    tw = [fa.TrueWindow(win[m], (WKEY + m) * T0, W, H) for m in range(3)]
    f1 = fa.fidelities([fa.window_sums(tw[m], win[m]) for m in range(3)])
    assert all(abs(v - 1.0) < 1e-12 for v in f1.values())
    empty = tuple(np.zeros(0, dtype=np.int64) for _ in range(4))
    f0 = fa.fidelities([fa.window_sums(tw[m], empty) for m in range(3)])
    assert all(abs(v) < 1e-12 for v in f0.values())
    rng = np.random.default_rng(0)
    masks = [rng.random(len(win[m][0])) < 0.3 for m in range(3)]
    sub = [tuple(a[masks[m]] for a in win[m]) for m in range(3)]
    s = [fa.window_sums(tw[m], sub[m]) for m in range(3)]
    q = sum(len(v[0]) for v in sub) / sum(len(v[0]) for v in win)
    f = fa.fidelities(s)
    assert abs(f["F"] - 2 * q / (1 + q)) < 1e-12 and abs(f["F20"] - 2 * q / (1 + q)) < 1e-12
    for phi, theta in ((1.0, 0.0), (3.0, 9.0)):   # a subset: M_b = N'_b, so D_b = l(N_b) - l(N'_b)
        tws = [fa.TrueWindow(win[m], (WKEY + m) * T0, W, H, phi, theta) for m in range(3)]
        fs = fa.fidelities([fa.window_sums(tws[m], sub[m]) for m in range(3)])
        l = lambda n: np.log1p(n / phi)
        D = L = 0.0
        for m in range(3):
            bN = fa.block_counts(win[m][1], win[m][2], W, H)
            bS = fa.block_counts(sub[m][1], sub[m][2], W, H)
            e = (bN > theta) | (bS > theta)
            D += np.sum(l(bN[e]) - l(bS[e]))
            L += np.sum(l(bN[e]) + l(bS[e]))
        assert abs(fs["Fsnr"] - (1 - D / L)) < 1e-9
    assert 2 * q / (1 + q) < f["FH"] < 1.0


def test_fsnr_prefers_a_capped_subset_to_whole_blocks():
    ev, _ = scene()
    v = windows(ev, 1)[0]
    tw = fa.TrueWindow(v, WKEY * T0, W, H, 2.0, 8.0)
    cap = fa.cap_mask(v[1], v[2], 64, W)                                 # n well above the threshold theta = 8
    sel = fa.select_mask(v[1], v[2], 1.0, W)
    n = len(v[0])
    rng = np.random.default_rng(1)
    o = np.flatnonzero(sel)
    sel_n = np.zeros(n, dtype=bool)
    sel_n[rng.permutation(o)[:int(cap.sum())]] = True                   # same number of events, dense blocks only
    fc = fa.fidelities([fa.window_sums(tw, tuple(a[cap] for a in v))])
    fs = fa.fidelities([fa.window_sums(tw, tuple(a[sel_n] for a in v))])
    assert abs(fc["F"] - fs["F"]) < 1e-12
    assert fc["Fsnr"] > fs["Fsnr"] + 0.05


def test_background_rate_of_poisson_noise_with_and_without_an_edge():
    rng = np.random.default_rng(5)
    beta, span = 2.0, 200_000                # events per pixel and second, us
    n = rng.poisson(beta * W * H * span * 1e-6)
    noise = (np.sort(rng.integers(0, span, n)), rng.integers(0, W, n), rng.integers(0, H, n), rng.integers(0, 2, n))
    est = fa.background_rate(noise, 0, span, W, H)
    assert abs(est["beta_per_px_s"] - beta) < 0.08 * beta
    ev, _ = scene()
    a, b = np.searchsorted(ev[0], (100_000, 100_000 + span))
    edge = (ev[0][a:b] - 100_000, ev[1][a:b], ev[2][a:b], ev[3][a:b])
    both = tuple(np.concatenate((u, v)) for u, v in zip(noise, edge))
    o = np.argsort(both[0], kind="stable")
    est2 = fa.background_rate(tuple(v[o] for v in both), 0, span, W, H)
    assert abs(est2["beta_per_px_s"] - beta) < 0.15 * beta
    assert est2["phi"] == max(1.0, est2["beta_per_px_s"] * fa.B ** 2 * T0 * 1e-6)
    from scipy.stats import poisson
    assert poisson.sf(est2["theta"], est2["phi"]) <= fa.ALPHA < poisson.sf(est2["theta"] - 1, est2["phi"])
    quiet = fa.background_rate(edge, 0, span, W, H)
    assert quiet["phi"] == 1.0
    hot = (np.repeat(np.arange(0, span, 1000), 20), np.tile(np.arange(20) * 7 + 3, span // 1000),
           np.full(20 * (span // 1000), 100), np.zeros(20 * (span // 1000), dtype=np.int64))
    withhot = tuple(np.concatenate((u, v)) for u, v in zip(noise, hot))
    o = np.argsort(withhot[0], kind="stable")
    est3 = fa.background_rate(tuple(v[o] for v in withhot), 0, span, W, H)
    assert est3["n_hot"] == 20 and abs(est3["beta_per_px_s"] - beta) < 0.08 * beta
    for b_ in (10.0, 20.0):                  # beyond 1 / (8 tau) the isolation estimate saturates
        n = rng.poisson(b_ * W * H * span * 1e-6)
        loud = (np.sort(rng.integers(0, span, n)), rng.integers(0, W, n), rng.integers(0, H, n), rng.integers(0, 2, n))
        e = fa.background_rate(loud, 0, span, W, H)
        assert e["branch"] == (-1 if b_ > 12.5 else 0) and abs(e["beta_per_px_s"] - b_) < 0.08 * b_


def test_fsnr_ignores_background_blocks():
    ev, _ = scene()
    v = windows(ev, 1)[0]
    rng = np.random.default_rng(6)
    n = 3000
    noise = (np.sort(rng.integers(WKEY * T0, (WKEY + 1) * T0, n)), rng.integers(0, W, n), rng.integers(0, H, n),
             rng.integers(0, 2, n))
    allv = tuple(np.concatenate((a, b)) for a, b in zip(v, noise))
    o = np.argsort(allv[0], kind="stable")
    allv = tuple(a[o] for a in allv)
    phi = n / ((W // fa.B) * (H // fa.B))                    # the background events per block
    from scipy.stats import poisson
    tw = fa.TrueWindow(allv, WKEY * T0, W, H, phi, float(poisson.isf(fa.ALPHA, phi)))
    f_obj = fa.fidelities([fa.window_sums(tw, v)])           # the object without the background
    f_all = fa.fidelities([fa.window_sums(tw, allv)])
    assert f_all["Fsnr"] == 1.0 and f_obj["Fsnr"] > 0.9 and f_obj["F"] < 0.9
    half = tuple(a[::2] for a in v)                          # half of the object: credit, not zero
    assert 0.5 < fa.fidelities([fa.window_sums(tw, half)])["Fsnr"] < 1.0


# ---------------------------------------------------------------------------------- subsets

def test_cap_keeps_at_most_n_per_block_evenly():
    rng = np.random.default_rng(2)
    x, y = rng.integers(0, W, 20000), rng.integers(0, H, 20000)
    bid = bc.block_ids(x, y, fa.B, W)
    for n in fa.CAPS:
        keep = fa.cap_mask(x, y, n, W)
        ids, N = np.unique(bid, return_counts=True)
        kept = np.array([keep[bid == b].sum() for b in ids])
        assert np.array_equal(kept, np.minimum(N, n))
        b0 = ids[np.argmax(N)]
        r = np.flatnonzero(keep[bid == b0])
        Nb = int(N.max())
        assert np.array_equal(r, ((2 * np.arange(n) + 1) * Nb) // (2 * n))      # centred in n equal segments
        assert r[0] < Nb / n and r[-1] >= Nb - Nb / n


def test_subsets_code_and_decode_every_kept_event():
    ev, _ = scene()
    v = windows(ev, 1)[0]
    for keep in (fa.thin_mask(len(v[0]), 0.3, WKEY, 0), fa.select_mask(v[1], v[2], 0.5, W), fa.cap_mask(v[1], v[2], 8, W)):
        bits, r = fa.code_subset(v, keep, WKEY * T0, W, H)
        assert len(r[0]) == int(keep.sum()) and bits > 0
        assert r[0].min() >= WKEY * T0 and r[0].max() < (WKEY + 1) * T0


# ---------------------------------------------------------------------------------- HEVC

def test_count_frames_round_trip_equals_coder_q():
    ev, _ = scene()
    win = windows(ev, 4)
    back = fa.frames_to_windows(fa.count_frames(win, WKEY, 4, W, H), WKEY, 4, W, H)
    for m in range(4):
        a = (WKEY + m) * T0
        t, x, y, p = win[m]
        q = bc.decode_events_Q(bc.encode_events_Q(t - a, x, y, p, bc.Q_DIRECT, W, H), bc.Q_DIRECT, W, H)
        ref = np.sort(((q[0] + a) * 4096 + q[1]) * 4096 * 2 + q[2] * 2 + q[3])
        got = np.sort((back[m][0] * 4096 + back[m][1]) * 4096 * 2 + back[m][2] * 2 + back[m][3])
        assert np.array_equal(ref, got)


def test_nal_bits_skips_parameter_sets():
    s = b"\x00\x00\x00\x01" + bytes([32 << 1, 1, 0xAA]) + b"\x00\x00\x01" + bytes([1 << 1, 1, 0xBB, 0xCC]) \
        + b"\x00\x00\x00\x01" + bytes([39 << 1, 1])
    assert fa.nal_bits(s) == (32, 40)


def test_hevc_is_deterministic_has_one_intra_frame_and_trades_bits_for_fidelity():
    ev, _ = scene()
    win = windows(ev, 4)
    fr = fa.count_frames(win, WKEY, 4, W, H)
    res = {}
    for qp in (14, 46):
        b1, sk, cl, cnt, s1 = fa.hevc_code(fr, qp)
        b2, _, _, _, s2 = fa.hevc_code(fr, qp)
        assert s1 == s2 and b1 == b2 and sk > 0 and cl == 0
        b = np.frombuffer(s1, dtype=np.uint8)
        z = np.flatnonzero((b[:-2] == 0) & (b[1:-1] == 0) & (b[2:] == 1)) + 3
        types = (b[z] >> 1) & 0x3F
        assert int(np.isin(types, (16, 17, 18, 19, 20, 21)).sum()) == 1      # one IRAP picture
        rw = fa.frames_to_windows(cnt, WKEY, 4, W, H)
        tw = [fa.TrueWindow(win[m], (WKEY + m) * T0, W, H) for m in range(4)]
        res[qp] = (b1, fa.fidelities([fa.window_sums(tw[m], rw[m]) for m in range(4)])["F"])
    assert res[14][1] > 0.95
    assert res[46][0] < res[14][0] and res[46][1] < res[14][1]


# ---------------------------------------------------------------------------------- FBC on the working grid

def test_fbc2_without_flows_is_every_event_on_the_working_grid():
    ev, _ = scene()
    f = fbc.group_flows(*ev, WKEY, W, H, 2, 1000.0, 4)
    none = lambda v: (v[0], v[1], np.zeros_like(v[2]))
    fl = {"w": f["w"], "st_us": f["st_us"], "send": none(f["send"]), "windows": [none(v) for v in f["windows"]]}
    rec = fa.fbc2_record(*ev, WKEY, 4, W, H, fl)
    assert rec == fa.fbc2_record(*ev, WKEY, 4, W, H, fl)
    out = fa.fbc2_reconstruct(rec, WKEY, 4, W, H)
    for m, v in enumerate(windows(ev, 4)):
        a = (WKEY + m) * T0
        q = bc.decode_events_Q(bc.encode_events_Q(v[0] - a, *v[1:], bc.Q_DIRECT, W, H), bc.Q_DIRECT, W, H)
        assert len(out[m][0]) == len(q[0]) and np.array_equal(np.sort(out[m][1]), np.sort(q[1]))


def test_fbc2_predicts_and_costs_fewer_bits_than_fbc_with_q():
    ev, _ = scene()
    fl = fbc.group_flows(*ev, WKEY, W, H, 3, 20000.0, 4)
    r2 = fa.fbc2_record(*ev, WKEY, 4, W, H, fl)
    r1 = fbc.encode_group(*ev, WKEY, 4, W, H, "Q", fl)
    assert len(r2) < len(r1)
    out = fa.fbc2_reconstruct(r2, WKEY, 4, W, H)
    for m in range(4):
        a = (WKEY + m) * T0
        assert len(out[m][0]) > 0 and out[m][0].min() >= a and out[m][0].max() < a + T0


# ---------------------------------------------------------------------------------- one group

def test_evaluate_group_on_a_synthetic_group():
    ev, bx = scene()
    kept = bc.evaluate_group(*ev, WKEY, 0, W, H, blocks=(20,), densities=(1.0,), records_for=(20, 1.0))
    lo = WKEY * T0 - fbc.FIT_WINDOW_US
    a, b = np.searchsorted(ev[0], (lo, (WKEY + 11) * T0))
    e = tuple(v[a:b] for v in ev)
    boxes = {}
    for m in (1, 2, 3):
        i = int(np.argmin(np.abs(bx["t"].astype(np.float64) - (WKEY + m + 0.5) * T0)))
        boxes[m] = [(1, (float(bx["x"][i]), float(bx["y"][i]), float(bx["w"][i]), float(bx["h"][i])))]
    t2, x2, y2, _ = windows(ev, 3)[2]
    cnt = np.bincount((y2 // 40) * (W // 40) + x2 // 40, minlength=(W // 40) * (H // 40))
    squares = [((int(k % (W // 40)) * 40, int(k // (W // 40)) * 40, 40, 40), int(cnt[k])) for k in np.argsort(-cnt)[:3]]
    names = ["remake", "translation", "static", "thin_0.5", "select_1.0", "cap_8", "hevc_28", "fbc_r2_res2000"]
    out = fa.evaluate_group(e, WKEY, W, H, kept["records"], kept, boxes=boxes, squares=squares, schemes=names)
    assert out["checks"] == {"outside": 0, "remake_equals_kept": True}
    assert set(out["schemes"]) == set(names)
    for nm in names:
        s = out["schemes"][nm]
        assert len(s["K4"]["sums"]) == 4 and len(s["K11"]["sums"]) == 11 and s["K11"]["bits"] >= s["K4"]["bits"] > 0
        f = fa.fidelities(s["K4"]["sums"])
        assert all(0.0 <= v <= 1.0 for v in f.values())
        assert len(s["tasks"]["objects"]) == 3 and len(s["tasks"]["motion"]) == 3 and len(s["tasks"]["tracks"]) == 1
    r = out["schemes"]["remake"]
    km = kept["codec"]["B20_rho1.0"]["models"]["affine"]
    assert r["K11"]["bits"] == 8 * kept["codec"]["B20_rho1.0"]["models"]["affine"]["bytes"]["Q_K11"]
    F = fa.fidelities(r["K11"]["sums"])["F"]
    ref = bc.group_fidelity(kept["codec"]["B20_rho1.0"]["n_key"], km["n_rec"], kept["n_true"][:11], km["match_s2_k3"])
    assert abs(F - ref) < 1e-12
    th = fa.fidelities(out["schemes"]["thin_0.5"]["K4"]["sums"])["F"]
    assert abs(th - 2 / 3) < 0.02
    assert "hevc_28" in out["hevc"] and out["hevc"]["hevc_28"]["K4"]["clipped_events"] == 0
    full = out["schemes"]["remake"]["tasks"]["objects"]
    assert all(o["n_true"] >= fa.MIN_BOX_EVENTS for o in full)
    tr = out["schemes"]["remake"]["tasks"]["tracks"][0]
    assert tr["continuous"] and tr["velocity_error_px"] < 1.0
    assert out["schemes"]["select_4.0"]["tasks"]["tracks"][0]["continuous"] is False if "select_4.0" in out["schemes"] else True
    assert out["background"]["phi"] >= 1.0 and out["background"]["theta"] >= out["background"]["phi"]
````
