# Directive 017. REMAKE with a Lagrangian choice of modes, and the baseline on its whole frontier

| | |
|---|---|
| track | `hybrid`, short name `hy` |
| population | as directive 016: eTraM train recordings and train annotations, DSEC training sequences, and the kept per-group files and streams of directives 007, 009 and 013 |
| results directory | `results/hy/` |
| report | `docs/directives/reports/017.md` |
| runs after | directive 016 (`DONE`, report at `6539b35`) |

## 1. Why

Report 016 found two things.

1. **Downstream tasks.** At (nearly) equal bits, a random subset beats REMAKE on objects by day and on
   motion by day and on DSEC. By day, REMAKE rebuilds no event in half of the annotated boxes. REMAKE
   sends only blocks that hold at least `psi B^2` key events, so a sparse object outside the regions is
   lost. The global fidelity hides this loss, because it is dominated by dense blocks.
2. **The baseline.** The criterion of 016 froze the configuration of the baseline that predicts least,
   which sends nearly every event. The comparison at equal F was therefore undefined. In 016 the random
   subset also cost up to twice the bits of REMAKE with coder Q, so the downstream comparison was not at
   equal bits.

This directive:

- **Part H.** Adds to REMAKE a Lagrangian choice of modes (`ec/hybrid.py`). The candidate regions stay
  those of configuration (20, 1), whose records are kept.
  - Each region is kept or dropped by its gain per bit.
  - In every window, each block keeps its rebuilt events, is replaced by its true events, or is emptied,
    by the largest gain minus `lam` times bits.
  - The remaining empty blocks are sampled at the critical slope, by events or by whole blocks.
  - The objective is the linearization of the fidelity at the operating point, which makes it additive
    over blocks.

  The module docstring gives the derivation and its sources. Part H measures fidelity, bits and both
  tasks, against random subsets whose bits are matched by bisection.
- **Part B.** Widens the grid of the baseline. It reports the baseline's whole frontier of fidelity
  against bits instead of one frozen configuration. In the downstream tasks it uses the configuration
  of the baseline whose bits come closest to those of REMAKE.

## 2. Disclosure

The director wrote `ec/hybrid.py` and tested it on synthetic events only. The director read report 016
and its tables, and no recording. On the synthetic scene of the gate, the block-wise remainder reached a
given fidelity with fewer bytes than the event-wise one. That is why both are measured here. The method
rests on [dinkelbach1967], [shoham1988], [sullivan1998] and [wiegand2003], whose ledger entries this pull
request adds with their verification status.

## 3. Author decisions

**D-017-1, default: authorized.** The executor adds `ec/hybrid.py` and `tests/test_hybrid_gate.py`
with the content of Appendices A and B, unchanged.

**D-017-2, default: as stated in Section 5.** The operating point of the hybrid, `(kappa, share,
mode)` of `ec.hybrid.POINTS`, is tuned on the tuning subsets with the criterion of REMAKE, and frozen per
dataset and coder.

**D-017-3, default: as stated in Section 6.** The grid of the baseline and its frontier.

**D-017-4, default: authorized.** The reads of directive 016, Section 4, for the groups of this
directive.

## 4. Definitions

Groups, entering rules, strata, tuning and reporting subsets, host paths (under `.../hy/`) and the
bootstrap are those of directive 016, with seed 20261017.

**Sums.** A per-group output of `ec.hybrid.evaluate_group` has the layout of `ec.fbc.evaluate_group`.
`ec.fbc.sum_groups` and `ec.fbc.summarize` therefore apply to it unchanged, with the keys `<coder>_remake` and
`<coder>_k<kappa>_s<share>_<mode>`.

## 5. Part H: the hybrid

**Stage T.**

- Run every group of the tuning recordings with
  `ec.hybrid.evaluate_group(t, x, y, p, w, records, 4, width, height)`.
- `records` holds, for each coder, the kept REMAKE record `affine_<coder>_K4` of configuration (20, 1)
  of that group.
- Compute `J` as in directive 016, Section 5, from `ec.fbc.summarize`, for every point of
  `ec.hybrid.POINTS` and for `<coder>_remake`.
- For each dataset and coder, freeze the point with the largest median `J`. `remake` is a candidate. On
  a tie, take the point with fewer median bits.
- Commit `results/hy/tuning.json` before Stage R evaluates a reporting group.

**Stage R.**

- Run every reporting group for K = 4 and K = 11, with all points.
- Per recording, compute `summarize` for every coder, K and point.

Tables:

1. **Hybrid:** `F`, `bits`, `bits_base` and `gain_sub` per stratum, coder and K, for every point and
   for `remake`. `remake` must reproduce REMAKE (Section 8, check 3).
2. **Modes:** the share of regions kept, of rebuilt blocks replaced and emptied, and of the true events
   in empty blocks, per stratum, at the frozen point. These counts come from a pass that records the
   decisions of `encode_group`. That pass may be the executor's own code. It must reproduce the bytes
   of the module for every group.

## 6. Part B: the baseline on its frontier

**Stage T.**

- Run every group of the tuning recordings with `ec.fbc.evaluate_group(..., Ks=(4,), coders=("T", "Q"))`.
- Use the twelve new configurations: `radius` in 1, 2 and 3, and `res_us` in 2000, 5000, 10000 and
  20000.
- Keep the nine configurations of `results/fb/tuning.json`.

**Frontier.** Per dataset and coder:

- Over the 21 configurations, take the medians of `F` and `bits` over the tuning recordings.
- A configuration is on the frontier when no other configuration has both a higher F and fewer bits.
- From the frontier, select three configurations: the one with the fewest bits, the one with the
  highest F, and the one whose bits are closest to the geometric mean of those two.
- Commit them in `results/hy/frontier.json` before Stage R.

**Stage R.**

- Run every reporting group with the selected configurations, at K = 2, 4, 8 and 11 and both coders.
- Do not run a configuration again if `results/fb/` already holds it.

Per recording and coder, the baseline's points are all `(F, bits)` over the selected configurations and
the four K.

- `b_pred(F)` is the fewest bits among the points whose F is at least F.
- At each K of REMAKE, report `G_pred = b_pred(F_REMAKE) / b_REMAKE`, together with the F of the point
  that attains it.
- `b_pred` is defined whenever some point reaches F. Report the share of recordings where none does.

## 7. Downstream tasks

The tasks, the boxes, the squares and the aggregation are those of directive 016, Section 7, and its
report, Section 7, items 4 and 5, at K = 4. The schemes are:

| scheme | events |
|---|---|
| `true` | the recorded events |
| `remake_<coder>` | the decoded REMAKE record |
| `hybrid_<coder>` | `ec.hybrid.reconstruct` of the stream at the frozen point of Section 5 |
| `thin_remake_<coder>` | `ec.hybrid.thin_matched` to the bytes of `remake_<coder>` of the group |
| `thin_hybrid_<coder>` | `ec.hybrid.thin_matched` to the bytes of `hybrid_<coder>` of the group |
| `fbc_<coder>` | the frontier configuration and K of Section 6 whose median bits on the tuning subsets come closest to those of REMAKE at K = 4, from its decoded record |

For every scheme, report the median over recordings of its bits per true event. Report also the median
ratio of its bits to those of the scheme it is matched to.

## 8. Acceptance checks

1. The two files have the SHA-256 of Section 11, and the suite passes with no skipped test.
2. `results/hy/tuning.json` and `results/hy/frontier.json` were committed before Stage R.
3. **`remake` reproduces REMAKE.** For every recording, `F` and `bits` of `<coder>_remake` equal the
   values of `ec.blockcodec.summarize` for `affine`, (20, 1), coder and K of the kept sums, to 1e-12.
4. **Matched bytes.** For every group and matched scheme, the bytes of `thin_matched` lie within 3% of the
   target. Otherwise, report the share of groups outside and their median deviation.
5. **Valid windows.** The decoded events of every scheme lie in their window and on the sensor.
6. **Files untouched.** No eTraM val or test file was opened, and the annotation root was not listed.
   Nothing outside `results/hy/` changed under `results/`.

## 9. Cost

Project from 20 groups of each stage and dataset. If the total exceeds 250 CPU-hours, stop after the two
Stage T runs, commit both files, and report `BLOCKED` with the projection. A run that then costs more is
let finish, and both numbers are reported.

Read the DSEC sequences one at a time with the memory guard of report 009. Use the single read per
sequence of report 016, Section 7, item 2.2. The eTraM reads may overlap.

## 10. Outputs

| file | content |
|---|---|
| `results/hy/tuning.json`, `results/hy/frontier.json` | Sections 5 and 6, Stage T |
| `results/hy/per_recording.json` | sums of every reporting recording, per scheme, coder, K and share |
| `results/hy/report.json` | the tables of Sections 5 to 7 |
| `results/hy/provenance.json` | commit, host, versions, wall and CPU time, and the files read |

## 11. Files

SHA-256 of the file content, which is the text between the fence lines of its appendix, ending in one
newline.

| file | SHA-256 |
|---|---|
| `ec/hybrid.py` | `1c15f01cb6495729c1e8d4b955e41f26376e903eff22bc5ab59f8983f42c81f1` |
| `tests/test_hybrid_gate.py` | `cc4c4d13d9a773e6baccddd800fc145c37effdf7f6335db7e727d48e18f8f7e7` |

## Appendix A. `ec/hybrid.py`

Normative. The executor commits this file unchanged.

```python
"""REMAKE with a Lagrangian choice between regenerating and sending events (directive 017).

Objective. On the working grid the fidelity of Eq. (fid) is the ratio ``F = 2 M / (N_rec + N_true)`` of
the pairs ``M`` that rebuilt and true events form inside their voxels. ``N_true`` is fixed, so at the
fidelity ``phi`` of an operating point, raising ``F`` at a given rate is maximizing

    U = 2 M - phi N_rec,

the parametric form of a ratio objective [dinkelbach1967]. ``U`` is additive over voxels, hence over
blocks and windows, which a Lagrangian allocation needs [shoham1988]. ``phi`` is the fidelity of the
REMAKE record of the group, which the sender computes from the events it holds (one step of
[dinkelbach1967]).

Actions and their slopes. An action is taken when its gain in ``U`` per bit is at least ``lam``, the
rule of [shoham1988] and of rate-constrained mode decision in video coders [sullivan1998, wiegand2003].
With ``r`` the bits per event of sending every event of the group with the coder,
``lam = kappa (2 - phi) / r``.

region   A region of the kept REMAKE record (configuration (20, 1)) gains ``(2 - phi) n_key`` in the key
         window, where its key events pair with themselves, and ``2 P_m - phi n_m`` in window m, where
         its ``n_m`` moved events find ``P_m`` partners among the true events that regions earlier in
         the order of decreasing key count have not claimed. Its bits are its share of the key payload,
         in proportion to its key events, plus its share of the map payload, in proportion to one
         region. It is kept when its gain per bit is at least ``lam``.
block    In window m, a block of side B holding rebuilt events can keep them (``2 M_b - phi n_rec,b``),
         be replaced by its true events (``(2 - phi) n_true,b``, about ``r`` bits per event), or be
         emptied (0, ``FLAG_BITS`` bits). The largest of gain minus ``lam`` times bits is taken.
remainder  A block without rebuilt events can only be sent. Every event of it gains ``2 - phi`` at about
         ``r`` bits, the same slope for every such event. At ``kappa = 1`` this slope equals ``lam``,
         and every subset of these events lies on the same line of gain against bits: the operating
         point between sending none and sending all is a time sharing, which a uniform random subset at
         the share ``share`` realizes in expectation. Above ``kappa = 1`` none is sent. Two realizations are
         measured, because the coded bits per event are not equal for every subset (sparse sets code
         worse): ``events``, each event with probability ``share``; and ``blocks``, each empty block of
         the window, with all its events, with probability ``share``.

Stream. The record of the kept regions (``ec.blockcodec.encode_group``), then for each window m the
sent events (coder T at one microsecond, or coder Q on the working grid) and the list of emptied blocks
(ULEB gaps, Zstandard level 19). The receiver removes the rebuilt events in every block that holds sent
events or is listed, and adds the sent events. ``evaluate_group`` scores what ``reconstruct`` rebuilds
from these bytes alone. The generator of the remainder of window m of the group keyed at w is
``np.random.default_rng(SEED + 16 * w + m)``. ``thin_matched`` draws a random subset of all events whose
coded bytes come closest to a target, by bisection on the share.
"""
from __future__ import annotations

import numpy as np

from . import blockcodec as bc

SEED = 20261017
FLAG_BITS = 16
POINTS = ((1.5, 0.0, "events"), (1.25, 0.0, "events"), (1.0, 0.0, "events")) + tuple(
    (1.0, s, mode) for mode in ("events", "blocks") for s in (0.05, 0.1, 0.2, 0.35, 0.5))
BISECTION_STEPS = 12


def _code(coder, t_rel, x, y, p, width, height):
    if coder == "T":
        return bc.encode_events_T(t_rel, x, y, p)
    return bc.encode_events_Q(t_rel, x, y, p, bc.Q_DIRECT, width, height)


def _decode(coder, buf, width, height):
    if coder == "T":
        return bc.decode_events_T(buf)
    return bc.decode_events_Q(buf, bc.Q_DIRECT, width, height)


def _window(ev, a, b):
    t, x, y, p = ev
    s = (t >= a) & (t < b)
    return t[s], x[s], y[s], p[s]


def _split_record(record: bytes):
    """Key payload bytes and map payload bytes of one record (model with maps)."""
    (dw, n_ev), pos = bc.uleb_decode(record, 2, 0)
    pos += int(n_ev)
    (n_mp,), _ = bc.uleb_decode(record, 1, pos)
    return int(n_ev), int(n_mp)


def _decode_group(record, coder, K, width, height, B, w, T0_us):
    head = bc.encode_header(coder, "affine", K, width, height, B, T0_us)
    h, groups = bc.decode_stream(head + record)
    return h, dict(groups[0], w=int(w))


def _moved(h, g, keep_ids, m):
    """Rebuilt events of window m from the regions ``keep_ids``, with each event's region."""
    kt, kx, ky, kp = g["key"]
    t = h["origin_us"] + (g["w"] + m) * h["T0_us"] + kt
    sel = np.isin(g["bid"], keep_ids)
    if m == 0:
        return t[sel], kx[sel], ky[sel], kp[sel], g["bid"][sel]
    ix, iy = np.empty_like(kx), np.empty_like(ky)
    for j, b in enumerate(g["ids"]):
        s = g["bid"] == b
        ix[s], iy[s] = bc.move(kx[s], ky[s], bc.block_frame(int(b), h["B"], h["width"]), g["maps"][j, m - 1])
    keep = sel & (ix >= 0) & (ix < h["width"]) & (iy >= 0) & (iy < h["height"])
    return t[keep], ix[keep], iy[keep], kp[keep], g["bid"][keep]


def region_gains(true_windows, h, g, w, K, width, height, phi, T0_us=bc.T0_US):
    """Per region: its gain in ``U`` with the greedy claims, and its key event count."""
    ids, bid = g["ids"], g["bid"]
    n_key = np.array([int(np.sum(bid == b)) for b in ids])
    order = np.argsort(-n_key, kind="stable")
    gain = (2.0 - phi) * n_key.astype(np.float64)
    for m in range(1, K):
        a = (w + m) * T0_us
        tt, tx, ty, tp = true_windows[m]
        res = bc.Residual(tt - a, tx, ty, tp, width, height, T0_us)
        mt, mx, my, mp, mb = _moved(h, g, ids, m)
        tb = bc.time_bin(mt - a, bc.OBJECTIVE[1], T0_us)
        for j in order:
            s = mb == ids[j]
            paired, n_in = res.claim(mx[s], my[s], tb[s], mp[s])
            gain[j] += 2 * paired - phi * n_in
    return gain, n_key


def _block_D(true, rebuilt, B, width, a, T0_us):
    """Per block id: true count, rebuilt count and D inside the block, on the working grid."""
    s, k = bc.OBJECTIVE
    def keys(ev):
        t, x, y, p = ev
        tb = bc.time_bin(t - a, k, T0_us)
        blk = bc.block_ids(x, y, B, width)
        vox = (((y // s) * (1 << 20) + x // s) * 64 + tb) * 2 + p
        return blk, vox
    tb_, tv = keys(true)
    rb_, rv = keys(rebuilt)
    allv = np.concatenate((tv, rv))
    allb = np.concatenate((tb_, rb_))
    sign = np.concatenate((np.ones(len(tv), np.int64), -np.ones(len(rv), np.int64)))
    uv, inv = np.unique(allv, return_inverse=True)
    net = np.bincount(inv, weights=sign, minlength=len(uv))
    vblk = np.zeros(len(uv), dtype=np.int64)
    vblk[inv] = allb
    ub, binv = np.unique(vblk, return_inverse=True)
    D = np.bincount(binv, weights=np.abs(net), minlength=len(ub))
    nt = np.bincount(np.searchsorted(ub, tb_), minlength=len(ub)) if len(tb_) else np.zeros(len(ub))
    nr = np.bincount(np.searchsorted(ub, rb_), minlength=len(ub)) if len(rb_) else np.zeros(len(ub))
    return ub, nt, nr, D


def _fidelity(trues, windows, w, K, T0_us):
    m_ = sum(bc.Truth(*trues[m], (w + m) * T0_us, T0_us).match(*windows[m], bc.OBJECTIVE) for m in range(K))
    den = sum(len(z[0]) for z in windows) + sum(len(z[0]) for z in trues)
    return 2.0 * m_ / den if den else 0.0


def encode_group(t, x, y, p, w: int, record: bytes, coder: str, K: int, width: int, height: int,
                 kappa: float, share: float, mode: str = "events", B: int = 20, T0_us: int = bc.T0_US) -> bytes:
    """The stream of one group at ``kappa`` and remainder share ``share`` (used only at kappa = 1), the
    remainder drawn by ``mode`` (``events`` or ``blocks``)."""
    ev = tuple(np.asarray(a, dtype=np.int64) for a in (t, x, y, p))
    w0 = w * T0_us
    trues = [_window(ev, w0 + m * T0_us, w0 + (m + 1) * T0_us) for m in range(K)]
    n_true = sum(len(tr[0]) for tr in trues)
    r = 8.0 * sum(len(_code(coder, tr[0] - (w0 + m * T0_us), *tr[1:], width, height))
                  for m, tr in enumerate(trues)) / max(n_true, 1)
    h, g = _decode_group(record, coder, K, width, height, B, w, T0_us)
    phi = _fidelity(trues, [bc.reconstruct(h, g, m) for m in range(K)], w, K, T0_us)
    lam = kappa * (2.0 - phi) / r
    key_b, map_b = _split_record(record)
    gain, n_key = region_gains(trues, h, g, w, K, width, height, phi, T0_us)
    n_reg = max(len(g["ids"]), 1)
    bits = 8.0 * (key_b * n_key / max(n_key.sum(), 1) + map_b / n_reg)
    keep_ids = g["ids"][gain >= lam * bits]
    kt, kx, ky, kp = g["key"]
    ksel = np.isin(g["bid"], keep_ids)
    jsel = np.isin(g["ids"], keep_ids)
    head = bc.encode_header(coder, "affine", K, width, height, B, T0_us)
    parts = [bc.encode_group(head, 0, (kt[ksel], kx[ksel], ky[ksel], kp[ksel]), g["maps"][jsel])]
    for m in range(K):
        a = w0 + m * T0_us
        mt, mx, my, mp, _ = _moved(h, g, keep_ids, m)
        reb = (mt, mx, my, mp)
        ub, nt, nr, D = _block_D(trues[m], reb, B, width, a, T0_us)
        v_keep = (nt + nr - D) - phi * nr                      # 2 M_b - phi n_rec,b
        v_send = (2.0 - phi) * nt - lam * r * nt
        v_drop = -lam * FLAG_BITS * np.ones(len(ub))
        has = nr > 0
        send = has & (v_send > v_keep) & (v_send >= v_drop)
        drop = has & ~send & (v_drop > v_keep)
        tblk = bc.block_ids(trues[m][1], trues[m][2], B, width)
        out = np.isin(tblk, ub[send])
        if kappa == 1.0 and share > 0:
            empty = ~np.isin(tblk, ub[has])
            rng = np.random.default_rng(SEED + 16 * w + m)
            if mode == "events":
                out |= empty & (rng.random(len(tblk)) < share)
            else:
                cand = np.unique(tblk[empty])
                out |= np.isin(tblk, cand[rng.random(len(cand)) < share])
        elif kappa < 1.0:
            out |= ~np.isin(tblk, ub[has])
        tt, tx, ty, tp = (z[out] for z in trues[m])
        parts.append(_code(coder, tt - a, tx, ty, tp, width, height))
        dl = np.sort(ub[drop])
        parts.append(bc._zstd(bc.uleb_encode(np.concatenate(([len(dl)], np.diff(dl, prepend=0)))), 19))
    return b"".join(bc.uleb_encode([len(q)]) + q for q in parts)


def reconstruct(stream: bytes, coder: str, w: int, K: int, width: int, height: int, B: int = 20,
                T0_us: int = bc.T0_US):
    """Events (t_us, x, y, p) of each window m = 0 .. K - 1, from the stream alone."""
    parts, pos = [], 0
    for _ in range(1 + 2 * K):
        (L,), pos = bc.uleb_decode(stream, 1, pos)
        parts.append(stream[pos:pos + int(L)])
        pos += int(L)
    h, g = _decode_group(parts[0], coder, K, width, height, B, w, T0_us)
    out = []
    for m in range(K):
        a = (w + m) * T0_us
        mt, mx, my, mp, _ = _moved(h, g, g["ids"], m)
        st, sx, sy, sp = _decode(coder, parts[1 + 2 * m], width, height)
        st = st + a
        v, _ = bc.uleb_decode(bc._unzstd(parts[2 + 2 * m]))
        dl = np.cumsum(np.asarray(v[1:], dtype=np.int64))
        gone = np.concatenate((np.unique(bc.block_ids(sx, sy, B, width)), dl))
        keep = ~np.isin(bc.block_ids(mx, my, B, width), gone)
        out.append(tuple(np.concatenate((u[keep], s)).astype(np.int64)
                         for u, s in ((mt, st), (mx, sx), (my, sy), (mp, sp))))
    return out


def evaluate_group(t, x, y, p, w: int, records: dict, K: int, width: int, height: int, B: int = 20,
                   points=POINTS, T0_us: int = bc.T0_US) -> dict:
    """``records``: coder -> the kept REMAKE record ``affine_<coder>_K<K>`` of configuration (B, 1) of this
    group. Keyed ``<coder>_k<kappa>_s<share>_<mode>``: ``bytes``, and per window ``n_rec``, ``n_true`` and
    ``match`` on the working grid, with ``F``. ``<coder>_remake`` scores the record alone."""
    ev = tuple(np.asarray(a, dtype=np.int64) for a in (t, x, y, p))
    w0 = w * T0_us
    trues = [_window(ev, w0 + m * T0_us, w0 + (m + 1) * T0_us) for m in range(K)]
    truths = [bc.Truth(*tr, w0 + m * T0_us, T0_us) for m, tr in enumerate(trues)]
    n_true = [int(len(tr[0])) for tr in trues]
    out = {"w": int(w), "K": int(K)}

    def score(windows, nbytes):
        n_rec = [int(len(z[0])) for z in windows]
        match = [truths[m].match(*windows[m], bc.OBJECTIVE) for m in range(K)]
        den = sum(n_rec) + sum(n_true)
        return {"bytes": int(nbytes), "n_rec": n_rec, "n_true": n_true, "match": match,
                "F": 2.0 * sum(match) / den if den else 0.0}

    for coder, rec in records.items():
        h, g = _decode_group(rec, coder, K, width, height, B, w, T0_us)
        out[f"{coder}_remake"] = score([bc.reconstruct(h, g, m) for m in range(K)], len(rec))
        for kappa, share, mode in points:
            s = encode_group(*ev, w, rec, coder, K, width, height, kappa, share, mode, B, T0_us)
            out[f"{coder}_k{kappa:g}_s{share:g}_{mode}"] = score(reconstruct(s, coder, w, K, width, height, B, T0_us),
                                                                  len(s))
    return out


def thin_events(t, x, y, p, w: int, K: int, coder: str, share: float, width: int, height: int,
                T0_us: int = bc.T0_US):
    """A random subset of every window of the group at ``share``, coded and decoded: (bytes, windows)."""
    ev = tuple(np.asarray(a, dtype=np.int64) for a in (t, x, y, p))
    w0 = w * T0_us
    total, wins = 0, []
    for m in range(K):
        a = w0 + m * T0_us
        tt, tx, ty, tp = _window(ev, a, a + T0_us)
        keep = np.random.default_rng(SEED + 16 * w + m).random(len(tt)) < share
        buf = _code(coder, tt[keep] - a, tx[keep], ty[keep], tp[keep], width, height)
        total += len(buf)
        dt, dx, dy, dp = _decode(coder, buf, width, height)
        wins.append((dt + a, dx, dy, dp))
    return total, wins


def thin_matched(t, x, y, p, w: int, K: int, coder: str, target_bytes: int, width: int, height: int,
                 T0_us: int = bc.T0_US):
    """The share in [0, 1] whose subset bytes come closest to ``target_bytes``, by bisection. Returns
    ``share``, ``bytes`` and the decoded windows."""
    lo, hi, best = 0.0, 1.0, None
    for _ in range(BISECTION_STEPS):
        mid = 0.5 * (lo + hi)
        b, wins = thin_events(t, x, y, p, w, K, coder, mid, width, height, T0_us)
        if best is None or abs(b - target_bytes) < abs(best[1] - target_bytes):
            best = (mid, b, wins)
        lo, hi = (mid, hi) if b < target_bytes else (lo, mid)
    return best
```

## Appendix B. `tests/test_hybrid_gate.py`

Normative. The executor commits this file unchanged.

```python
"""Gate for directive 017: REMAKE with a Lagrangian choice between regenerating and sending events.

A large textured object and a small one move across a small sensor. With the frozen configuration
(20, 1), REMAKE sends the large object; the small one lies outside the regions. Tolerances are fixed by
the director.
"""
import numpy as np
import pytest

from ec import blockcodec as bc
from ec import hybrid
from ec import synth

W, H, WIN = 320, 240, 6


@pytest.fixture(scope="module")
def scene():
    a = synth.rigid_translation(width=W, height=H, n_points=3000, box_wh=(120, 80), c0=(80, 120),
                                v=(150.0, -50.0), duration_s=1.0, jitter_us=200, seed=2)
    b = synth.rigid_translation(width=W, height=H, n_points=60, box_wh=(20, 20), c0=(250, 40),
                                v=(-40.0, 30.0), duration_s=1.0, jitter_us=200, seed=3)
    t = np.concatenate([a.t, b.t])
    o = np.argsort(t, kind="stable")
    ev = [np.concatenate([u, v])[o].astype(np.int64) for u, v in ((a.t, b.t), (a.x, b.x), (a.y, b.y), (a.p, b.p))]
    g = bc.evaluate_group(*ev, WIN, 0, W, H, blocks=(20,), densities=(1.0,), models=("affine",),
                          records_for=(20, 1.0))
    recs = {c: g["records"][f"affine_{c}_K4"] for c in bc.CODERS}
    return ev, g, recs, hybrid.evaluate_group(*ev, WIN, recs, 4, W, H)


def test_remake_entry_reproduces_the_codec(scene):
    _, g, recs, r = scene
    gs = bc.sum_groups([g])
    for c in bc.CODERS:
        assert r[f"{c}_remake"]["bytes"] == len(recs[c])
        assert abs(r[f"{c}_remake"]["F"] - bc.summarize(gs, "B20_rho1.0", "affine", c, 4)["F"]) < 1e-12


def test_stream_decodes_inside_windows(scene):
    ev, _, recs, _ = scene
    for c in bc.CODERS:
        s = hybrid.encode_group(*ev, WIN, recs[c], c, 4, W, H, 1.0, 0.2, "events")
        for m, (t, x, y, p) in enumerate(hybrid.reconstruct(s, c, WIN, 4, W, H)):
            a = (WIN + m) * bc.T0_US
            assert len(t) and t.min() >= a and t.max() < a + bc.T0_US
            assert x.min() >= 0 and x.max() < W and y.min() >= 0 and y.max() < H


def test_remainder_raises_fidelity_and_bytes(scene):
    _, _, _, r = scene
    for c in bc.CODERS:
        for mode in ("events", "blocks"):
            keys = [f"{c}_k1_s0_events"] + [f"{c}_k1_s{s:g}_{mode}" for s in (0.05, 0.1, 0.2, 0.35, 0.5)]
            F = [r[k]["F"] for k in keys]
            b = [r[k]["bytes"] for k in keys]
            assert F[-1] > F[0] and b[-1] > b[0]
            assert all(b[i] <= b[i + 1] for i in range(len(b) - 1))


def test_larger_slope_sends_fewer_bytes(scene):
    _, _, _, r = scene
    for c in bc.CODERS:
        b = [r[f"{c}_k{k:g}_s0_events"]["bytes"] for k in (1.5, 1.25, 1.0)]
        assert b[0] <= b[1] <= b[2]


def test_thin_matched_hits_the_target(scene):
    ev, _, _, r = scene
    for c in bc.CODERS:
        target = r[f"{c}_k1_s0.2_events"]["bytes"]
        share, b, wins = hybrid.thin_matched(*ev, WIN, 4, c, target, W, H)
        assert 0 < share < 1 and abs(b - target) <= 0.02 * target and len(wins) == 4
```
