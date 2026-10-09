# Directive 007. Regeneration on a fixed block grid, with a complete bitstream

| | |
|---|---|
| track | `block`, short name `bk` |
| population | the 112 development recordings of `config/population.yaml`, events only. No annotation is opened |
| results directory | `results/bk/` |
| report | `docs/directives/reports/007.md` |
| runs after | directive 006. It does not use its results |

## 1. Why

Directives 002 to 005 regenerated the events of annotated objects: the regions
were the label boxes, the truth was the events in a box, and the cost was
counted in events or in the payload of the key events plus a fixed number of
bits per map. A sender has no annotation, and a receiver needs a stream that it
can decode. Three things were therefore still missing, and the reviews of the
manuscript asked for each of them:

1. regions that the sender finds by itself, with their description in the count;
2. a complete bitstream, from which a decoder that holds nothing else rebuilds
   every window, with the size taken from the bytes that are written;
3. results over the complete windows, which include the events outside the
   regions and the events that appear after the key window.

**What this directive measures.** The codec of `ec/blockcodec.py` (Appendix A),
whose docstring holds every definition and is part of this directive. In short:
the sensor is cut into square blocks. The blocks that hold enough events of the
key window are the regions. The sender transmits their events and, for each
later window of the group and each region, one map. The receiver moves the key
events. The fidelity is measured on the complete sensor against all true
events, on events decoded from the bytes, and the bits are eight times the
bytes. The codec is compared, in bits at equal fidelity, with schemes that
send a subset of the events and regenerate nothing: a random subset, complete
windows, and the active blocks of every window. It is also compared with
repeating the key events without motion. Two event coders are used throughout:
the transport of the companion project, and a coder matched to the grid on
which the receiver counts.

The results on annotated boxes of directives 003 and 004 stay as the reference
under ideal regions. This directive does not assume that the block grid is
worse or better than they are.

## 2. Disclosure

Before this directive was written the director had:

- read reports 001 to 005 and the committed aggregates of all five;
- developed `ec/blockcodec.py` and its gate on synthetic scenes only (two
  moving point objects and uniform noise on a 320 x 240 sensor). No recording
  was read;
- fixed on those scenes: the order of the fit and the claiming of paired
  events, the limit `B / 10` on the shape offsets, the bitstream layout, and
  coder Q;
- seen on those scenes that uniform noise pairs by chance on the working grid
  (fidelity 0.06 to 0.16 per window for repeated key events), and that the
  displacement search finds a few more chance pairs (+0.03 to +0.04);
- had this directive reviewed by an independent agent before it was proposed.
  The review found that a random subset costs more bits per kept event than
  all events do under either coder, so that a gain over thinning alone mixes
  regeneration with the choice of blocks: on a synthetic scene, repeating the
  key events without motion had `gamma` = 1.0 and a gain of 1.34 over thinning
  with coder Q. The baseline of the rule is therefore the lower convex envelope
  of thinning, of complete windows and of the active blocks of every window.
  Against it, on the director's scenes, the repeated key events gain 0.6 to 1.1,
  and on pure noise the repeated key events and the translation gain under 1.1;
- taken from the same review: the first search was widened from 12 to 24 px,
  the translation falls back to zero displacement when that pairs more events,
  and the cost is projected from a census of the active blocks;
- read in `results/mp/preflight.json` that the median recording holds 0.041
  events per pixel and window over the whole sensor. The densities therefore
  start at 1/16 and not at 1/32, which would make most blocks of the background
  active;
- seen on the synthetic scenes that the gain is largest at the largest
  thresholds, where the fidelity is low. The criterion of Section 8 is
  therefore a saving in bits and not a ratio;
- measured 45 to 75 microseconds per scored map in the reference
  implementation, and 115 to 140 scored maps per block and target for the
  translation and 250 to 370 for the affine map, its translation included.

## 3. Author decisions

**D-007-1, default: accepted.** The motion model of the codec is the affine map.
This is the author's decision of 2026-10-09, taken after report 004: the
translation is the special case of the affine map with zero shape parameters,
so the affine map is never worse on the sender's objective, and the paper's
theory is written for affine flow. The outcome of rule D-004-4, step 1, stays
recorded as measured. The translation and the repeated key events are reported
next to the affine map as baselines.

**D-007-2, default: accepted.** The first automatic region scheme is the fixed
block grid, with these rules, which are the author's:

- *Key window.* Events are counted per block of the fixed grid. The blocks at
  or above a preset threshold are the active blocks, and each one is a template
  region.
- *Later windows.* The template events are mapped in sensor coordinates and may
  cross block boundaries. Every source event is rebuilt once per window. An
  event that leaves the sensor is dropped.
- *Within a group the templates are fixed.* No region is added before the next
  key window. Objects that enter, occlusion and changes of activity are losses
  of fidelity. No update mechanism is added in this version.
- *Scope.* The main results are over the complete windows, including the blocks
  that were not selected and the events that appear within the group.
- *Bits.* The count is the bytes of the complete stream: the fixed
  configuration as a sequence header, the correspondence of blocks, events and
  maps, the group length and the record boundaries included. The tables count
  the records. The header is 28 bytes per stream of a recording and is reported
  separately (Table 7).

**D-007-3, default: authorized.** The event files of the 112 development
recordings are read on `cnt`. No annotation file is read. The run stays on
`cnt`.

**D-007-4, default: authorized.** The executor adds `ec/blockcodec.py` and
`tests/test_blockcodec_gate.py` with the content of Appendices A and B,
unchanged. Their SHA-256 are in Section 14.

**D-007-5, default: as stated in Section 8.** The tuning subset, the
configurations, and the criterion that freezes one of them.

**D-007-6, default: as stated in Section 12.** The decision rule.

**D-007-7, default: accepted.** The sentence of the abstract of the manuscript
that reports measured results stays marked as provisional in the source until
this directive and the second dataset have reported. If they change the
conclusion, the abstract changes with them.

## 4. Isolation

As in directive 002, Section 4, with `results/bk/population_check.json`,
committed before the first event file is opened. This directive builds no
annotation path. Write only under `~/prjs/event_coding/bk/` on the host and
`results/bk/` in the repository. The complete streams stay on the host.

## 5. Stage P: preflight

A failed check is a `BLOCKED` report with the evidence.

**P1. Environment.** The versions equal those of `results/af/preflight.json`.

**P2. Files.** `ec/blockcodec.py` and `tests/test_blockcodec_gate.py` have the
SHA-256 of Section 14.

**P3. Gates.** `python3 -m pytest -q -p no:anyio` passes on the host with no
skipped test. No gate file is edited.

**P4. Inputs.** The 112 event files exist (`os.path.isfile` on the paths of
`ec.mp.event_path`). When a recording is read, its number of events equals
`results/mp/preflight.json#/P2/per_recording`.

## 6. Definitions common to all stages

**Windows.** `T0` = 33,333 us, origin 0: window `w` is `[w T0, (w + 1) T0)` in
the microsecond timestamps that `ec.baseline.read_events` returns. Sensor
1280 x 720.

**Groups.** In every recording the key windows are `w_j = 30 + S j`, `j` = 0, 1,
..., for as long as `(w_j + 11) T0` does not exceed the time of the last event,
with the spacing `S` = 90 windows (3 s) unless Section 15 changes it. `w_prev`
is `w_(j-1)`, and 0 for `j` = 0. Each group is evaluated by
`ec.blockcodec.evaluate_group`, which returns integers and two checks.

**Subsets.** Sort the identifiers of the day recordings and of the night
recordings. The *tuning subset* is the positions 0, 10, 20, 30, 40 and 50 of
each list, twelve recordings. The *reporting subset* is the other 100. Write
both lists into `results/bk/population_check.json`.

**Unit and aggregation.** The unit is the recording. Its groups are added with
`ec.blockcodec.sum_groups`, and every quantity of a recording is computed from
the sums, with `ec.blockcodec.summarize` where that function has it. A
recording enters a table, and the criterion of Section 8, with at least 10
groups at `S` = 90, 5 at `S` = 180 and 3 at `S` = 360. A table entry is the
median over recordings, by lighting unless stated, with a 95% interval from
2000 bootstrap resamples of recordings (seed 20261012) and the numbers of
recordings and of groups behind it. A recording whose value is not a number
(`gamma` without key events) is left out of that entry and counted.

**Acceleration.** `ec/blockcodec.py` stays as it is, and its gate tests it. A
faster `evaluate_group` may live in a new module. It may be used for Stages T
and R if it returns, on every group of Stage 0, the output of the reference in
every field. All fields are integers, booleans or byte strings, so equal means
equal. State which one ran.

**Timing.** Where a stage asks for the time of a part of `evaluate_group`, wrap
the function of that part (`fit_group`) from the runner. Do not edit the module.

## 7. Stage 0: one complete pass on two recordings

The purpose is to push a few groups through encoding, decoding and counting
before anything is run in bulk, and to show that the decoder needs the stream
and the agreed configuration only.

**Recordings and groups.** The first recording of the tuning subset by day and
by night, groups `j` = 0 to 4.

**Run.** `evaluate_group(t, x, y, p, w_j, w_prev, 1280, 720, grid_for=(40, 1/16),
records_for=(40, 1/16))`, with the defaults for the blocks, the densities and
the models.

**Streams.** For each of the two recordings and each of the 24 combinations of
model, coder and `K`, write the complete stream of configuration (40, 1/16):
`encode_header(coder, model, K, 1280, 720, 40)` followed by the five records in
order. Keep the files under `~/prjs/event_coding/bk/stage0/`.

**Receiver.** In a separate process, started after the files are closed, read
each stream file, and call `ec.blockcodec.evaluate_stream` with the bytes of
the file and the events of the recording. The process receives nothing that
the sender computed: no map, no block list, no count. The events are used only
to score the reconstruction.

**Checks of Stage 0.** For every stream: its length is 28 plus the sum of the
`bytes` entries of its groups; and for every group and every `m` below `K`, the
receiver's `n_rec`, `n_true` and `match` equal `n_key` and the entries of
`n_rec`, `n_true` and `match_s2_k3` of `evaluate_group`. For every
configuration, model and group: `claim_equals_match` and `q_equals_t` are true.

**Census.** For every key window of Section 6 of all 112 recordings, count the
active blocks for each block side and each density (`block_ids`, `threshold`).
This reads the events and fits nothing. Write the counts to
`results/bk/census.json`. The census opens the reporting recordings before the
configuration is frozen. It computes no fidelity and no size.

**Cost.** Time each call of `evaluate_group`, and each call of `fit_group`
inside it. Project Stages T and R as in Section 15.

Stage 0 is reported in the same report as the later stages. If one of its
checks fails, stop there with a `BLOCKED` report.

## 8. Stage T: tuning (D-007-5)

**Run.** Every group of the twelve tuning recordings, with the default blocks
(20, 40 and 80 px), densities (`rho` = 1/16, 1/8, 1/4, 1/2, 1 events per pixel
of the key window) and models. Fifteen configurations `(B, rho)`.

**Criterion.** For a recording and a configuration, with
`s = summarize(sum, config, "affine", "Q", 4)`,

    J = (s["bits_base"] - s["bits"]) / s["bits_direct"],

the share of the direct bits that the codec saves against the cheapest subset
scheme at the fidelity that the codec reaches, in groups of four windows, on
the working grid, with coder Q. `J(B, rho)` is the median over the tuning
recordings, day and night together.

**Freeze.** The configuration `(B*, rho*)` with the largest `J`. On a tie, the
larger `B`, then the larger `rho`. Commit `results/bk/tuning.json`, with `J` for
all fifteen configurations and the frozen one, before Stage R evaluates a
group of the reporting subset, and give the commit hash in the report. The
frozen configuration is not changed afterwards, whatever Stage R shows.

## 9. Stage R: the reporting subset

**Run.** Every group of the 100 reporting recordings, with
`blocks=(B*,)`, the five densities, the three models, `grid_for=(B*, rho*)` and
`records_for=(B*, rho*)`. The baseline `select` is then that of the block side
`B*`.

**Streams.** For every reporting recording, write the eight complete streams
of the frozen configuration with the model `affine` (two coders, four `K`),
and score each one with `evaluate_stream` in a separate process, as in Stage 0.
Record the size and the SHA-256 of every stream file in
`results/bk/provenance.json`.

## 10. Tables for the report

Coder Q and the working grid (2 px, 11.1 ms) unless stated. "Frozen" is
`(B*, rho*)`.

1. **Tuning.** `J`, and the medians of `F`, `bits`, `bits_base` and `gain`, for
   the fifteen configurations (model `affine`, `K` = 4), tuning subset, day and
   night together, and `J` by lighting. The frozen configuration.
2. **Headline.** Frozen configuration, reporting subset, by lighting, for `K` in
   {2, 4, 8, 11} and the three models: `F`, `bits`, `bits_direct`, `bits_base`,
   `bits_thin`, `gain`, `gain_thin`, and the ratio of `gain` to that of the
   model `static`. Once with coder Q and once with coder T.
3. **Events.** The same rows with `share` and `gamma`, next to `gamma` of
   `aligned` (report 003, Table 1) and of `affine` (report 004, Table 1) on
   annotated boxes, copied from those reports and marked as such.
4. **Thresholds.** For the five densities at `B*`, model `affine`, `K` = 4 and
   `K` = 11: `F`, `bits`, `gain`, the number of active blocks per group, and the
   share of the key-window events that are key events.
5. **Windows.** Frozen configuration, by lighting: for the key window,
   `2 n_key / (n_key + n_true)`, and for `m` = 1 to 10 the fidelity of the window
   `2 match / (n_rec + n_true)`, for the three models, on the working grid and
   on the frame grid (2 px, 33.3 ms). For `m` = 1, 4 and 10: `n_rec / n_true`,
   and the share of the true events that lie in the active blocks.
6. **Grids.** Frozen configuration, model `affine`, coder T, `K` = 4: `F`,
   `gain` and `gain_thin` on the twelve grids of directive 002.
7. **Bytes.** Frozen configuration, model `affine`, by lighting, for the four
   `K` and both coders: bytes per group; the share of the map payload, taken as
   the difference between the records of `affine` and of `static`; the share of
   the 28-byte header in the complete stream of a recording.
8. **Baselines.** By lighting, both coders, in bits per true event over the
   eleven windows of the groups: `direct`; `thin` at its five shares; `select`
   at `B*` and its five densities, each with its share of the events.
9. **Census.** By lighting, for each block side and density: the median and the
   10% and 90% quantiles over recordings of the mean number of active blocks
   per key window, and that number as a share of all blocks.
10. **Fit.** The number of scored maps per group, and per block of the fit
    (the blocks at the smallest density), by model, and the wall time per
    group.
11. **Checks.** The counts behind acceptance checks 4 to 7.

## 11. What the report does not decide

The report states the frozen configuration, the tables and the outcome of the
rule of Section 12, and no more. Whether the codec gains an update of the
regions within a group, a change of the number of regenerated events, or
another region scheme is the director's proposal after this report. So is the
choice of the second dataset.

## 12. Predictions and decision rule

Written by the director before any recording was coded with this codec. Frozen
configuration, reporting subset, working grid, medians over recordings.

| quantity | predicted |
|---|---|
| `B*` | 40 px |
| `bits_direct`, coder T | 24 to 28 bits per event |
| `bits_direct`, coder Q | 3 to 7 bits per event |
| share of the key-window events that are key events | 0.6 to 0.9 by day, 0.4 to 0.8 by night |
| `F` at `K` = 4, model `affine` | 0.45 to 0.75 |
| `F(affine) - F(static)` at `K` = 4 | 0.08 to 0.30 |
| `F(affine) - F(translation)` at `K` = 11 | -0.01 to 0.05 |
| `gain`, coder Q, `K` = 4 | 1.1 to 2.0 |
| `gain`, coder Q, `K` = 11 | 1.2 to 3.5 |
| `gain_thin`, coder Q, `K` = 4 | 1.3 to 2.6 |
| `gain`, coder T, `K` = 4 | 1.1 to 2.2 |
| `gain` of the model `static`, coder Q, `K` = 4 | 0.6 to 1.1 |
| share of the map payload in the record, coder Q, `K` = 11 | 0.05 to 0.35 |

**Rule (D-007-6).** Frozen configuration, reporting subset, working grid, coder
Q. `gain` is against the envelope of the subset schemes.

- **GO** if, by day and by night, at `K` = 4, `gain` of the model `affine` is at
  least 1.25 and at least 1.10 times `gain` of the model `static`. The block
  codec is then the codec of the paper, and the next directive names the
  second dataset.
- **NO-GO for this region scheme** if `gain` of the model `affine` is under
  1.10 at every `K` in {2, 4, 8, 11}, by day or by night. The director then
  proposes one change of the region scheme before any second dataset.
- Otherwise the result is reported as measured, and the director proposes one
  refinement of the codec before any second dataset.

## 13. Acceptance checks

1. P1 to P4 pass.
2. `results/bk/population_check.json` was committed before the first event file
   was opened, and `results/bk/tuning.json` before Stage R evaluated a group.
   The report gives the commit hashes.
3. Every check of Stage 0 passes.
4. `claim_equals_match` is true for every group, configuration and model of
   Stages T and R: the sender's count of paired events equals the count on the
   decoded events.
5. `q_equals_t` is true for every group, configuration and model: a stream of
   coder Q gives the receiver the same counts on the working grid as a stream
   of coder T.
6. For every stream of Stage R, the receiver's numbers equal those of
   `evaluate_group`, as in Stage 0, and the file length is 28 plus the sum of
   its records.
7. For every group, configuration, model and `m`: `0 <= match <= n_rec`, and
   `match` does not decrease from the working grid to the frame grid.
8. Every group of Section 6 is evaluated. A group whose key window holds no
   active block is a valid group with fidelity zero for its targets.
9. The suite passes at the executed commit.

## 14. Files

SHA-256 of the file content, which is the text between the fence lines of its
appendix, ending in one newline.

| file | SHA-256 |
|---|---|
| `ec/blockcodec.py` | `644539ec0fb900cc2c3ccd08de0d7105ed55a56cf1d67a545b9784d690390c9e` |
| `tests/test_blockcodec_gate.py` | `4ca8ec70fcd3ae5101a37592f1ab3d809d5d28692eacd9ac6d0687bb28adedf0` |

## 15. Cost

The fit dominates, and its cost follows the number of active blocks at the
smallest density, which the director does not know. The reference scores 115
to 140 maps per block and target for the translation and 250 to 370 for the
affine map, at 45 to 75 microseconds each. With 100 to 300 blocks of 40 px
that is 30 to 100 s per group for that block side. Stage T fits three block
sides, and the side of 20 px has up to four times the blocks.

**Projection.** From Stage 0: `c_B`, the time of the two fitting passes
(`translation` and `affine`) of a group at block side `B`, divided by its
number of blocks at the smallest density, as a mean over the ten groups; and
`c_0`, the mean time of a group outside the fits. From the census: `N_B(g)`,
the number of blocks at the smallest density of group `g`. A stage costs

    sum over its groups g, sum over its block sides B, of N_B(g) c_B, plus c_0 per group.

Stage T has the three block sides. Stage R has one, not yet known: use the one
with the largest projected cost.

**Spacing.** If the projection for Stages T and R exceeds 150 CPU-hours at
`S` = 90, use `S` = 180 for both stages. If it still does, use `S` = 360. If it
still does, stop after Stage 0 and report the census and the projection. The
spacing is chosen once, before Stage T, and is not changed afterwards. If the
run then costs more than projected, let it finish and report both numbers. Do
not compete with a companion-project job on `cnt`.

## 16. Outputs

| file | content |
|---|---|
| `results/bk/population_check.json` | Section 4, with the two subsets |
| `results/bk/preflight.json` | P1 to P4 |
| `results/bk/stage0.json` | the checks and the times of Stage 0, and the cost projection |
| `results/bk/census.json` | the active blocks of every key window, by block side and density |
| `results/bk/tuning.json` | Section 8 |
| `results/bk/per_recording.json` | for every recording, the output of `sum_groups` |
| `results/bk/report.json` | every table of Section 10 |
| `results/bk/provenance.json` | commit, host, versions, spacing, wall time, and the path, size and SHA-256 of every stream file and per-group file kept on the host |

Per-group outputs and stream files stay on the host under
`~/prjs/event_coding/bk/` and are not committed.

## 17. What comes next

With a GO, the director names the second dataset, recorded from a moving
camera, and writes its directive with the frozen configuration unchanged. The
manuscript takes Fig. 3 from Table 2 and its Section V-C from the docstring of
`ec/blockcodec.py`.

## Appendix A. `ec/blockcodec.py`

Normative. The executor commits this file unchanged.

```python
"""Regeneration on a fixed block grid, with a complete bitstream (directive 007). Reference implementation.

Question. Directives 002 to 005 regenerated the events of annotated objects. A sender has no
annotation. It cuts the sensor into square blocks, sends the events of the active blocks of a key
window, and for each later window of the group one map per block. What does the receiver get for
the bytes that are actually written, over the complete windows, against sending fewer events?

Windows and groups. Window ``w`` of a recording is ``[w T0, (w + 1) T0)`` with ``T0`` = 33,333 us.
A group keyed at window ``w`` is the key window ``w`` (``m`` = 0) and the targets ``m`` = 1 ..
``K - 1``, the windows ``w + m``.

Regions. The sensor is cut into blocks of ``B x B`` pixels, aligned to the origin and numbered in
raster order. A block is active when it holds at least ``theta = max(1, ceil(rho B^2))`` events of
the key window. Each active block is one template region. The regions stay fixed within the group.

Sender. It transmits the key events, which are the events of the key window in the active blocks,
and for every target and every active block one map with integer parameters
``q = (dx, dy, ia, ib, ic, id)``. With ``(cx, cy)`` the center of the block and ``h = B / 2``, a
key event at ``(x, y)`` is moved to the pixel nearest to

    x' = x + dx + (ia / h) (x - cx) + (ib / h) (y - cy)
    y' = y + dy + (ic / h) (x - cx) + (id / h) (y - cy)

and by ``m T0`` in time, with its polarity. This is the map of ``ec.affine`` with the block in
place of the bounding rectangle. A moved event may leave its block. One that leaves the sensor is
dropped. Every key event is moved once per target. Models: ``static`` (all parameters zero, no
map is sent), ``translation`` (``dx, dy``), ``affine`` (all six).

Fit. For target ``m`` the sender holds the true events of window ``w + m`` as counts on the working
grid, 2 px blocks and three time bins per window (OBJECTIVE). It visits the active blocks in the
order of decreasing key count, ties in raster order. For each block it chooses the map that
maximizes the number of moved events of the block that can be paired, inside a voxel of the
working grid, with true events that no earlier block has claimed, and then claims them. The sum of
the claims over the blocks is therefore the number of paired events of the whole reconstruction on
the working grid, which is what the fidelity counts. A block that is active under a larger
threshold comes earlier in the order, so one fit under the smallest threshold serves all of them.
The translation search is the coarse-to-fine search of ``ec.gop.aligned_displacement``: for ``m``
= 1 it starts at zero with half-width RADIUS_FIRST, and for ``m`` > 1 at the map of the previous
target scaled by ``m / (m - 1)`` with half-width ``max(3, ceil(0.3 |d0|))``. It returns a
displacement that pairs at least as many events as its starting point and as the zero
displacement. The first search reaches RADIUS_FIRST plus the refinements, 36 px per window. The
shape search is that of ``ec.affine.fit_affine`` (STAGES), with offsets above ``B / 10`` left out,
and returns a map that pairs at least as many events as the translation it starts from. So, on
the events that are unclaimed when a block is visited, ``affine`` >= ``translation`` >= ``static``
for that block. The search scores coarse steps on coarser grids (STAGE_CELLS), whose counts are
kept consistent with the claims.

Event coders. ``T``: the transport of the companion project, U2 and zstd level 1, with times in
microseconds (``ec.baseline.payload_bits`` is the size of this payload). ``Q``: events quantized
to a receiver grid of ``s`` px and ``k`` time bins per window, sorted, with the gaps between their
voxel indices as ULEB128 and zstd level 19. A receiver that counts events on the working grid
needs the direct stream at (2 px, 3 bins). The codec needs its key events at (1 px, 3 bins),
because a map moves them by whole pixels and keeps their time bin.

Bitstream. A stream is a header of 28 bytes (HEADER) and one record per group:

    ULEB128  key window index, as the difference to that of the previous record
    ULEB128  length of the key payload, then the payload (coder T or Q)
    ULEB128  length of the map payload, then the payload     (absent for the model static)

The decoder reads the block side, the group length, the model and the coder from the header. The
active blocks are the blocks that hold key events, so no list of regions is sent. The map payload
holds, for each active block in raster order and each parameter of the model, the values for
``m`` = 1 .. ``K - 1`` as first differences along ``m``, zigzag and ULEB128, behind one byte that
says whether zstd level 19 was applied (it is applied when that is shorter). ``decode_stream``
and ``reconstruct`` take the bytes and nothing else.

Baselines, on the same windows and with the same two coders: ``direct`` (every event); ``thin``
(a random subset with keep probability ``chi`` in THIN_SHARES); and ``select`` (in every window,
the events of the blocks that are active in that window, by the rule of the key window, with no
regeneration). A subset pairs each of its events, so with the share ``q = n_kept / n`` its fidelity
is ``2 q / (1 + q)`` on every grid. Two subset schemes can be mixed over windows, which mixes
their shares and their bits linearly, so the baseline at a share ``q`` is the lower convex envelope
of the measured points ``(q, bits)`` of ``thin``, ``select`` and ``direct`` and of the origin. The
segment from the origin to ``direct`` is the scheme that sends some windows completely and drops
the others. A random subset costs more bits per kept event than all events do, because its events
lie further apart. Whole windows and whole blocks do not. The envelope is therefore the baseline
that separates regeneration from the choice of windows and blocks. Thinning alone is reported
next to it, by linear interpolation between its measured points.

Fidelity. For window ``m`` the reconstruction and the true events of the complete sensor are
compared as in ``ec.regen.voxel_f1`` (class ``Truth``). With ``match`` the paired events and ``n_rec``, ``n_true`` the
two counts, a group of ``K`` windows has

    F_K    = 2 sum_m match / sum_m (n_rec + n_true),      m = 0 .. K - 1,
    bits_K = 8 x the length of the group's record,

and the key window enters with ``match = n_rec = n_key``. A subset reaches ``F_K`` with the share
``q_eq = F_K / (2 - F_K)``. The gain of the codec is the bits of the baseline at ``q_eq`` divided
by ``bits_K``.
"""
from __future__ import annotations

import math
import struct

import numpy as np
import zstandard

from . import regen
from .baseline import RepresentationMode, decode_representation, encode_representation, pack_array, unpack_array

T0_US = 33_333
N_TARGETS = 10
GROUPS = (2, 4, 8, 11)
OBJECTIVE = (2, 3)                         # the working grid: block px, time bins per window
STAGE_CELLS = (OBJECTIVE, (4, 1), (8, 1), (16, 1))
BLOCKS = (20, 40, 80)
DENSITIES = (1 / 16, 1 / 8, 1 / 4, 1 / 2, 1.0)      # rho, events per pixel in the key window
MODELS = ("static", "translation", "affine")
N_PARAMS = {"static": 0, "translation": 2, "affine": 6}
RADIUS_FIRST = 24
# (block px, time bins), offsets, largest number of rounds: the stages of ec.affine
STAGES = (((8, 1), (-2, 2, -4, 4, -8, 8), 2),
          ((4, 1), (-1, 1, -2, 2, -4, 4), 2),
          (OBJECTIVE, (-1, 1, -2, 2), 4))
THIN_SHARES = (0.75, 0.5, 0.35, 0.25, 0.125)
THIN_SEED = 20261012
CELLS_ALL = tuple((s, k) for s in regen.BLOCKS_PX for k in regen.TIME_BINS)
CELLS_MAIN = (OBJECTIVE, (2, 1))
Q_KEY = (1, 3)                             # receiver grid of the key events under coder Q
Q_DIRECT = OBJECTIVE                       # receiver grid of the direct and thinned streams under coder Q
MAGIC, VERSION = b"EC07", 1
HEADER = struct.Struct("<4sBBBBHHHBBIq")   # magic, version, coder, model, K, width, height, B, qs, qk, T0, origin
CODERS = ("T", "Q")


def threshold(B: int, rho: float) -> int:
    return max(1, int(math.ceil(rho * B * B)))


# ----------------------------------------------------------------------------------------------
# integers and event payloads

def uleb_encode(values) -> bytes:
    """ULEB128 of an array of non-negative integers below 2^63."""
    v = np.asarray(values, dtype=np.uint64).ravel()
    if v.size == 0:
        return b""
    nb = np.ones(v.size, dtype=np.int64)
    for j in range(1, 9):
        nb += (v >= (np.uint64(1) << np.uint64(7 * j))).astype(np.int64)
    end = np.cumsum(nb)
    start = end - nb
    out = np.zeros(int(end[-1]), dtype=np.uint8)
    for j in range(int(nb.max())):
        sel = nb > j
        byte = ((v[sel] >> np.uint64(7 * j)) & np.uint64(0x7F)).astype(np.uint8)
        byte |= (nb[sel] > j + 1).astype(np.uint8) << 7
        out[start[sel] + j] = byte
    return out.tobytes()


def uleb_decode(buf: bytes, count: int | None = None, pos: int = 0):
    """Decode ``count`` values from ``pos`` (all remaining ones if None). Returns ``values, next_pos``."""
    b = np.frombuffer(buf, dtype=np.uint8)[pos:]
    if count is not None:
        b = b[:10 * count]
    ends = np.flatnonzero(b < 128)
    if count is None:
        count = int(ends.size)
    if count == 0:
        return np.zeros(0, dtype=np.int64), pos
    if ends.size < count:
        raise ValueError("truncated ULEB128 data")
    ends = ends[:count]
    starts = np.concatenate(([0], ends[:-1] + 1))
    n = int(ends[-1]) + 1
    which = np.repeat(np.arange(count), ends - starts + 1)
    shift = (np.arange(n) - starts[which]).astype(np.uint64) * np.uint64(7)
    vals = np.add.reduceat((b[:n].astype(np.uint64) & np.uint64(0x7F)) << shift, starts)
    return vals.astype(np.int64), pos + n


def _zstd(buf: bytes, level: int) -> bytes:
    return zstandard.ZstdCompressor(level=level).compress(buf)


def _unzstd(buf: bytes) -> bytes:
    return zstandard.ZstdDecompressor().decompress(buf)


def encode_events_T(t_rel, x, y, p) -> bytes:
    """Coder T. ``t_rel`` is relative to the window start. The size is ``ec.baseline.payload_bits`` / 8."""
    if len(t_rel) == 0:
        return b""
    return _zstd(encode_representation(pack_array(t_rel, x, y, p), RepresentationMode.AER40_SOA_DT), 1)


def decode_events_T(buf: bytes):
    if len(buf) == 0:
        z = np.zeros(0, dtype=np.int64)
        return z, z.copy(), z.copy(), z.copy()
    t, x, y, p = unpack_array(decode_representation(_unzstd(buf), RepresentationMode.AER40_SOA_DT))
    return t.astype(np.int64), x.astype(np.int64), y.astype(np.int64), p.astype(np.int64)


def time_bin(t_rel, k: int, T0_us: int = T0_US):
    return np.minimum(k - 1, (np.asarray(t_rel, dtype=np.int64) * k) // int(T0_us))


def encode_events_Q(t_rel, x, y, p, cell, width: int, height: int, T0_us: int = T0_US) -> bytes:
    """Coder Q on the receiver grid ``cell`` = (block px, time bins)."""
    s, k = cell
    if len(t_rel) == 0:
        return b""
    nx, ny = -(-width // s), -(-height // s)
    L = ((time_bin(t_rel, k, T0_us) * 2 + np.asarray(p, dtype=np.int64)) * ny
         + np.asarray(y, dtype=np.int64) // s) * nx + np.asarray(x, dtype=np.int64) // s
    L = np.sort(L)
    return _zstd(uleb_encode(np.concatenate(([len(L)], np.diff(L, prepend=0)))), 19)


def decode_events_Q(buf: bytes, cell, width: int, height: int, T0_us: int = T0_US):
    """Events at the origin of their voxel: the first pixel of the block and the first instant of the bin."""
    s, k = cell
    if len(buf) == 0:
        z = np.zeros(0, dtype=np.int64)
        return z, z.copy(), z.copy(), z.copy()
    v, _ = uleb_decode(_unzstd(buf))
    if v[0] != len(v) - 1:
        raise ValueError("coder Q: the count does not match the payload")
    L = np.cumsum(v[1:])
    nx, ny = -(-width // s), -(-height // s)
    x, r = (L % nx) * s, L // nx
    y, r = (r % ny) * s, r // ny
    p, tb = r % 2, r // 2
    return -((-tb * int(T0_us)) // k), x, y, p


# ----------------------------------------------------------------------------------------------
# maps

def block_ids(x, y, B: int, width: int):
    return (np.asarray(y, dtype=np.int64) // B) * (-(-width // B)) + np.asarray(x, dtype=np.int64) // B


def block_frame(b: int, B: int, width: int):
    nbx = -(-width // B)
    return (b % nbx) * B + (B - 1) / 2.0, (b // nbx) * B + (B - 1) / 2.0, B / 2.0


def move(sx, sy, frame, q):
    """Pixels of the key events of one block under the map ``q`` (six integers)."""
    cx, cy, h = frame
    u = np.asarray(sx, dtype=np.float64) - cx
    v = np.asarray(sy, dtype=np.float64) - cy
    xm = np.asarray(sx, dtype=np.float64) + q[0] + (q[2] / h) * u + (q[3] / h) * v
    ym = np.asarray(sy, dtype=np.float64) + q[1] + (q[4] / h) * u + (q[5] / h) * v
    return np.rint(xm).astype(np.int64), np.rint(ym).astype(np.int64)


def encode_maps(maps, n_params: int) -> bytes:
    """``maps``: integers of shape (active blocks in raster order, K - 1, >= n_params)."""
    v = np.asarray(maps, dtype=np.int64)[:, :, :n_params]
    d = np.diff(v, axis=1, prepend=0).transpose(0, 2, 1).ravel()
    raw = uleb_encode(((d << 1) ^ (d >> 63)).astype(np.uint64))
    z = _zstd(raw, 19)
    return b"\x01" + z if len(z) < len(raw) else b"\x00" + raw


def decode_maps(buf: bytes, n_blocks: int, n_targets: int, n_params: int):
    if len(buf) == 0 or buf[0] not in (0, 1):
        raise ValueError("map payload: bad flag")
    raw = _unzstd(buf[1:]) if buf[0] == 1 else buf[1:]
    zz, end = uleb_decode(raw, n_blocks * n_targets * n_params)
    if end != len(raw):
        raise ValueError("map payload: trailing bytes")
    d = (zz >> 1) ^ -(zz & 1)
    out = np.zeros((n_blocks, n_targets, 6), dtype=np.int64)
    out[:, :, :n_params] = np.cumsum(d.reshape(n_blocks, n_params, n_targets).transpose(0, 2, 1), axis=1)
    return out


# ----------------------------------------------------------------------------------------------
# bitstream

def encode_header(coder: str, model: str, K: int, width: int, height: int, B: int, T0_us: int = T0_US,
                  origin_us: int = 0) -> bytes:
    qs, qk = Q_KEY if coder == "Q" else (0, 0)
    return HEADER.pack(MAGIC, VERSION, CODERS.index(coder), MODELS.index(model), K, width, height, B, qs, qk,
                       T0_us, origin_us)


def encode_group(header: bytes, w_delta: int, key, maps=None) -> bytes:
    """One record. ``key`` = (t_rel, x, y, p) of the key events. ``maps``: (active blocks in raster order, K - 1, 6)."""
    h = decode_header(header)
    kt, kx, ky, kp = key
    if h["coder"] == "T":
        ev = encode_events_T(kt, kx, ky, kp)
    else:
        ev = encode_events_Q(kt, kx, ky, kp, h["qcell"], h["width"], h["height"], h["T0_us"])
    out = uleb_encode([w_delta, len(ev)]) + ev
    if h["model"] != "static":
        n_act = len(np.unique(block_ids(kx, ky, h["B"], h["width"])))
        maps = np.zeros((0, h["K"] - 1, 6), dtype=np.int64) if maps is None else np.asarray(maps)
        if maps.shape[:2] != (n_act, h["K"] - 1):
            raise ValueError("one map per active block and target is required")
        mp = encode_maps(maps, N_PARAMS[h["model"]])
        out += uleb_encode([len(mp)]) + mp
    return out


def decode_header(buf: bytes) -> dict:
    magic, version, coder, model, K, width, height, B, qs, qk, T0_us, origin = HEADER.unpack_from(buf, 0)
    if magic != MAGIC or version != VERSION:
        raise ValueError("not a stream of this codec")
    return {"coder": CODERS[coder], "model": MODELS[model], "K": K, "width": width, "height": height, "B": B,
            "qcell": (qs, qk), "T0_us": T0_us, "origin_us": origin}


def decode_stream(buf: bytes, cache: dict | None = None):
    """Header and groups of a stream. Each group: key window index ``w``, key events, active block ids, maps.

    ``cache`` memoizes decoded key payloads by their bytes. It changes no result.
    """
    h = decode_header(buf)
    pos, w, groups = HEADER.size, 0, []
    while pos < len(buf):
        (dw, n_ev), pos = uleb_decode(buf, 2, pos)
        ev = bytes(buf[pos:pos + int(n_ev)])
        if len(ev) != n_ev:
            raise ValueError("truncated key payload")
        pos += int(n_ev)
        ck = (h["coder"], h["qcell"], ev)
        if cache is not None and ck in cache:
            key = cache[ck]
        else:
            key = (decode_events_T(ev) if h["coder"] == "T" else
                   decode_events_Q(ev, h["qcell"], h["width"], h["height"], h["T0_us"]))
            if cache is not None:
                cache[ck] = key
        w += int(dw)
        bid = block_ids(key[1], key[2], h["B"], h["width"])
        ids = np.unique(bid)
        maps = np.zeros((len(ids), h["K"] - 1, 6), dtype=np.int64)
        if h["model"] != "static":
            (n_mp,), pos = uleb_decode(buf, 1, pos)
            mp = bytes(buf[pos:pos + int(n_mp)])
            if len(mp) != n_mp:
                raise ValueError("truncated map payload")
            pos += int(n_mp)
            maps = decode_maps(mp, len(ids), h["K"] - 1, N_PARAMS[h["model"]])
        groups.append({"w": w, "key": key, "bid": bid, "ids": ids, "maps": maps})
    return h, groups


def reconstruct(h: dict, group: dict, m: int):
    """Events ``(t_us, x, y, p)`` of window ``m`` of a decoded group, with absolute times."""
    kt, kx, ky, kp = group["key"]
    t = h["origin_us"] + (group["w"] + m) * h["T0_us"] + kt
    if m == 0:
        return t, kx, ky, kp
    ix, iy = np.empty_like(kx), np.empty_like(ky)
    for j, b in enumerate(group["ids"]):
        sel = group["bid"] == b
        ix[sel], iy[sel] = move(kx[sel], ky[sel], block_frame(int(b), h["B"], h["width"]), group["maps"][j, m - 1])
    keep = (ix >= 0) & (ix < h["width"]) & (iy >= 0) & (iy < h["height"])
    return t[keep], ix[keep], iy[keep], kp[keep]


# ----------------------------------------------------------------------------------------------
# the sender's fit

class Residual:
    """Counts of the true events of one window that no block has claimed, on the grids of STAGE_CELLS."""

    def __init__(self, t_rel, x, y, p, width: int, height: int, T0_us: int = T0_US):
        self.width, self.height, self.g = width, height, {}
        x, y, p = (np.asarray(a, dtype=np.int64) for a in (x, y, p))
        for s, k in STAGE_CELLS:
            nx, ny = -(-width // s), -(-height // s)
            idx = ((p * k + time_bin(t_rel, k, T0_us)) * ny + y // s) * nx + x // s
            self.g[(s, k)] = (nx, ny, np.bincount(idx, minlength=2 * k * ny * nx).astype(np.int64))

    def _index(self, ix, iy, tb, p, cell):
        s, k = cell
        nx, ny, _ = self.g[cell]
        keep = (ix >= 0) & (ix < self.width) & (iy >= 0) & (iy < self.height)
        tbk = tb[keep] if k == OBJECTIVE[1] else 0
        return ((p[keep] * k + tbk) * ny + iy[keep] // s) * nx + ix[keep] // s

    def matched(self, ix, iy, tb, p, cell) -> int:
        """Moved events (``tb``: their bin on the working grid) that can be paired with unclaimed true events."""
        u, c = np.unique(self._index(ix, iy, tb, p, cell), return_counts=True)
        return int(np.minimum(c, self.g[cell][2][u]).sum())

    def claim(self, ix, iy, tb, p):
        """Pair on the working grid and remove the paired true events from every grid. Returns ``paired, n_in_sensor``."""
        idx = self._index(ix, iy, tb, p, OBJECTIVE)
        u, c = np.unique(idx, return_counts=True)
        nx, ny, R = self.g[OBJECTIVE]
        got = np.minimum(c, R[u])
        R[u] -= got
        s0, k0 = OBJECTIVE
        bx, r = u % nx, u // nx
        by, r = r % ny, r // ny
        pol = r // k0
        for s, k in STAGE_CELLS[1:]:
            cnx, cny, C = self.g[(s, k)]
            np.subtract.at(C, (pol * k * cny + (by * s0) // s) * cnx + (bx * s0) // s, got)
        return int(got.sum()), int(len(idx))


def _stage_cell(step: int):
    s = 2 if step <= 2 else 4 if step <= 4 else 8 if step <= 8 else 16
    return s, (OBJECTIVE[1] if s == 2 else 1)


def search_translation(score, d0, R: int):
    """Integer displacement that pairs the most events. ``score(q, cell)``; see ``ec.gop.aligned_displacement``.

    Coarse to fine around ``rint(d0)``, then compared on the working grid with ``rint(d0)`` itself
    and with zero. On a tie the start wins over the search result, and both win over zero.
    """
    start = (int(np.rint(d0[0])), int(np.rint(d0[1])))
    step, reach, best = int(math.ceil(R / 4)), 4, start
    while True:
        cell = _stage_cell(step)
        offs = [(i, j) for i in range(-reach, reach + 1) for j in range(-reach, reach + 1)]
        offs.sort(key=lambda ij: (ij[0] * ij[0] + ij[1] * ij[1], ij))
        cand, top = best, -1
        for i, j in offs:
            d = (best[0] + i * step, best[1] + j * step)
            f = score(d + (0, 0, 0, 0), cell)
            if f > top:
                cand, top = d, f
        best = cand
        if step == 1:
            break
        step, reach = int(math.ceil(step / 2)), 2
    top = score(best + (0, 0, 0, 0), OBJECTIVE)
    for alt in (start, (0, 0)):                 # never fewer pairs than the start or than no motion
        if alt != best:
            f = score(alt + (0, 0, 0, 0), OBJECTIVE)
            if f > top or (f == top and alt == start):
                best, top = alt, f
    return best


def search_shape(score, d, shape_prev, ratio: float, B: int):
    """Six parameters that pair the most events, from the translation ``d``. See ``ec.affine.fit_affine``."""
    def stretched(q, k):
        return (q[0], q[1], q[2] + k, q[3], q[4], q[5] + k)

    def bumped(q, i, k):
        return tuple(v + (k if j == i else 0) for j, v in enumerate(q))

    moves = [stretched] + [lambda q, k, i=i: bumped(q, i, k) for i in (2, 5, 3, 4, 0, 1)]
    start = (int(d[0]), int(d[1]), 0, 0, 0, 0)
    start_top = score(start, OBJECTIVE)
    best = start
    if shape_prev is not None:
        warm = (start[0], start[1]) + tuple(int(np.rint(ratio * v)) for v in shape_prev)
        if warm != start and score(warm, OBJECTIVE) > start_top:
            best = warm
    for cell, offsets, max_rounds in STAGES:
        offsets = [k for k in offsets if abs(k) <= B // 10]
        if not offsets:
            continue
        top = score(best, cell)
        for _ in range(max_rounds):
            changed = False
            for mv in moves:
                cand, ctop = best, top
                for k in offsets:
                    q = mv(best, k)
                    f = score(q, cell)
                    if f > ctop:
                        cand, ctop = q, f
                if cand != best:
                    best, top, changed = cand, ctop, True
            if not changed:
                break
    if best != start and score(best, OBJECTIVE) <= start_top:
        best = start
    return best


def fit_group(key, truths, B: int, model: str, theta_min: int, width: int, height: int, T0_us: int = T0_US) -> dict:
    """Maps of every block with at least ``theta_min`` key events, for the targets ``m`` = 1 .. len(truths).

    ``key`` = (t_rel, x, y, p) of all events of the key window, ``truths[m - 1]`` the same for window
    ``m``. Returns the block ids in fitting order (``ids``), their key counts (``counts``), ``maps`` of
    shape (blocks, targets, 6), the claimed pairs and the moved events inside the sensor per block
    and target (``claimed``, ``n_in``), and the number of scored maps (``n_eval``).
    """
    kt, kx, ky, kp = (np.asarray(a, dtype=np.int64) for a in key)
    bid = block_ids(kx, ky, B, width)
    ids, counts = np.unique(bid, return_counts=True)
    ids, counts = ids[counts >= theta_min], counts[counts >= theta_min]
    order = np.lexsort((ids, -counts))
    ids, counts = ids[order], counts[order]
    n_t = len(truths)
    maps = np.zeros((len(ids), n_t, 6), dtype=np.int64)
    claimed = np.zeros((len(ids), n_t), dtype=np.int64)
    n_in = np.zeros((len(ids), n_t), dtype=np.int64)
    ev = []
    for b in ids:
        sel = bid == b
        ev.append((kx[sel], ky[sel], time_bin(kt[sel], OBJECTIVE[1], T0_us), kp[sel], block_frame(int(b), B, width)))
    n_eval = 0
    for m in range(1, n_t + 1):
        res = Residual(*truths[m - 1], width, height, T0_us)
        for j, (sx, sy, tb, sp, frame) in enumerate(ev):
            def score(q, cell):
                nonlocal n_eval
                n_eval += 1
                ix, iy = move(sx, sy, frame, q)
                return res.matched(ix, iy, tb, sp, cell)

            q = (0, 0, 0, 0, 0, 0)
            if model != "static":
                if m == 1:
                    d0, R = (0.0, 0.0), RADIUS_FIRST
                else:
                    r = m / (m - 1.0)
                    d0 = (r * maps[j, m - 2, 0], r * maps[j, m - 2, 1])
                    R = max(3, int(math.ceil(0.3 * math.hypot(*d0))))
                d = search_translation(score, d0, R)
                q = d + (0, 0, 0, 0)
                if model == "affine":
                    prev = tuple(int(v) for v in maps[j, m - 2, 2:]) if m > 1 else None
                    q = search_shape(score, d, prev, m / (m - 1.0) if m > 1 else 1.0, B)
            maps[j, m - 1] = q
            claimed[j, m - 1], n_in[j, m - 1] = res.claim(*move(sx, sy, frame, q), tb, sp)
    return {"ids": ids, "counts": counts, "maps": maps, "claimed": claimed, "n_in": n_in, "n_eval": n_eval}


# ----------------------------------------------------------------------------------------------
# evaluation of one group

class Truth:
    """Voxel counts of the true events of one window, kept per grid. ``match`` equals ``ec.regen.voxel_f1``."""

    def __init__(self, t_us, x, y, p, w0_us: int, T0_us: int = T0_US):
        self.t, self.x, self.y, self.p, self.w0, self.T0, self._c = t_us, x, y, p, int(w0_us), int(T0_us), {}

    def _keys(self, t, x, y, p, s, k):
        bt = np.minimum(k - 1, ((np.asarray(t, dtype=np.int64) - self.w0) * k) // self.T0)
        return (((np.asarray(y, dtype=np.int64) // s) * (1 << 20) + np.asarray(x, dtype=np.int64) // s) * 64 + bt) * 2 \
            + np.asarray(p, dtype=np.int64)

    def match(self, t, x, y, p, cell) -> int:
        if len(t) == 0 or len(self.t) == 0:
            return 0
        if cell not in self._c:
            self._c[cell] = np.unique(self._keys(self.t, self.x, self.y, self.p, *cell), return_counts=True)
        kf, cf = self._c[cell]
        kp, cp = np.unique(self._keys(t, x, y, p, *cell), return_counts=True)
        _, ip, jf = np.intersect1d(kp, kf, assume_unique=True, return_indices=True)
        return int(np.minimum(cp[ip], cf[jf]).sum())


def group_fidelity(n_key: int, n_rec, n_true, match) -> float:
    """``F_K`` of the module docstring. ``n_rec`` and ``match`` hold the targets ``m`` = 1 .. ``K - 1``, ``n_true`` the windows ``m`` = 0 .. ``K - 1``."""
    den = n_key + np.sum(n_rec, dtype=np.float64) + np.sum(n_true, dtype=np.float64)
    return float(2.0 * (n_key + np.sum(match, dtype=np.float64)) / den) if den > 0 else 0.0


def baseline_bits(q: float, shares, bits, envelope: bool = True) -> float:
    """Bits of subset schemes at the share ``q``, from measured points ``(share, bits)`` and the origin.

    With ``envelope``: the cheapest mixture, the lower convex envelope of the points. Without: linear
    interpolation between neighboring points. Beyond the largest share the value of that point.
    """
    best = {0.0: 0.0}
    for s, b in zip(shares, bits):
        s, b = float(s), float(b)
        best[s] = min(b, best.get(s, b))
    pts = sorted(best.items())
    if envelope:
        hull = []
        for pt in pts:
            while len(hull) >= 2 and ((hull[-1][0] - hull[-2][0]) * (pt[1] - hull[-2][1])
                                      - (hull[-1][1] - hull[-2][1]) * (pt[0] - hull[-2][0])) <= 0:
                hull.pop()
            hull.append(pt)
        pts = hull
    return float(np.interp(q, [v[0] for v in pts], [v[1] for v in pts]))


def evaluate_group(t_us, x, y, p, w: int, w_prev: int, width: int, height: int, blocks=BLOCKS, densities=DENSITIES,
                   models=MODELS, grid_for=None, records_for=None, T0_us: int = T0_US) -> dict:
    """Everything of the group keyed at window ``w``. ``t_us`` must be nondecreasing.

    ``w_prev`` is the key window of the previous group of the stream (0 for the first group). Every
    fidelity is measured on events decoded from ``header + record``. ``grid_for`` = (B, rho) asks for
    all twelve grids of directive 002 for that configuration; the others get CELLS_MAIN. Configurations
    are keyed ``B{B}_rho{rho}`` with ``rho`` printed as a float. Fidelities
    of streams of coder Q are those of coder T on grids with one or three time bins, which is checked
    on the working grid (``q_equals_t``). ``records_for`` = (B, rho) returns the records of that
    configuration as bytes under ``records``, keyed ``model_coder_K``, for writing complete streams.
    """
    t_us = np.asarray(t_us, dtype=np.int64)
    grid_for = None if grid_for is None else (int(grid_for[0]), float(grid_for[1]))
    records_for = None if records_for is None else (int(records_for[0]), float(records_for[1]))
    edges = np.searchsorted(t_us, [(w + m) * T0_us for m in range(N_TARGETS + 2)])
    win = []
    for m in range(N_TARGETS + 1):
        a, b = edges[m], edges[m + 1]
        win.append((t_us[a:b] - (w + m) * T0_us, np.asarray(x[a:b], dtype=np.int64), np.asarray(y[a:b], dtype=np.int64),
                    np.asarray(p[a:b], dtype=np.int64)))
    truth = [Truth(t_us[edges[m]:edges[m + 1]], win[m][1], win[m][2], win[m][3], (w + m) * T0_us, T0_us)
             for m in range(N_TARGETS + 1)]
    n_true = [int(len(v[0])) for v in win]
    out = {"w": int(w), "n_true": n_true, "direct": {}, "thin": {}, "select": {}, "codec": {}, "fit": {}}

    # baselines
    u = np.random.default_rng((THIN_SEED, int(w))).random(int(edges[-1] - edges[0]))
    for coder in CODERS:
        enc = (lambda v: encode_events_T(*v)) if coder == "T" else \
              (lambda v: encode_events_Q(*v, Q_DIRECT, width, height, T0_us))
        out["direct"][coder] = [8 * len(enc(v)) for v in win]
        for chi in THIN_SHARES:
            bits, kept = [], []
            for m, v in enumerate(win):
                sel = u[edges[m] - edges[0]:edges[m + 1] - edges[0]] < chi
                bits.append(8 * len(enc(tuple(a[sel] for a in v))))
                kept.append(int(sel.sum()))
            out["thin"].setdefault(str(chi), {"n_kept": kept})[coder] = bits

    for B in blocks:                                        # select: the active blocks of every window, as they are
        bids = [block_ids(v[1], v[2], B, width) for v in win]
        for rho in densities:
            row = {"n_kept": [], "T": [], "Q": []}
            for v, bid in zip(win, bids):
                ids, cnt = np.unique(bid, return_counts=True)
                sel = np.isin(bid, ids[cnt >= threshold(B, rho)])
                kept = tuple(a[sel] for a in v)
                row["n_kept"].append(int(sel.sum()))
                row["T"].append(8 * len(encode_events_T(*kept)))
                row["Q"].append(8 * len(encode_events_Q(*kept, Q_DIRECT, width, height, T0_us)))
            out["select"][f"B{B}_rho{float(rho)}"] = row

    # the codec
    cache = {}
    for B in blocks:
        thetas = [threshold(B, rho) for rho in densities]
        fits = {model: fit_group(win[0], win[1:], B, model, min(thetas), width, height, T0_us) for model in models}
        out["fit"][str(B)] = {model: {"n_blocks": int(len(f["ids"])), "n_eval": int(f["n_eval"])} for model, f in fits.items()}
        bid0 = block_ids(win[0][1], win[0][2], B, width)
        for rho, theta in zip(densities, thetas):
            f0 = fits[models[0]]
            act = f0["counts"] >= theta                       # a prefix of the fitting order
            ids_r = np.sort(f0["ids"][act])
            ksel = np.isin(bid0, ids_r)
            key = tuple(a[ksel] for a in win[0])
            n_in_act = [int(np.isin(block_ids(v[1], v[2], B, width), ids_r).sum()) for v in win]
            cells = CELLS_ALL if grid_for == (int(B), float(rho)) else CELLS_MAIN
            row = {"theta": int(theta), "n_active": int(len(ids_r)), "n_key": int(ksel.sum()), "n_true_in_active": n_in_act,
                   "models": {}}
            for model in models:
                f = fits[model]
                pos = np.searchsorted(ids_r, f["ids"][act])   # fitting order -> raster order
                maps_r = np.zeros((len(ids_r), N_TARGETS, 6), dtype=np.int64)
                maps_r[pos] = f["maps"][act]
                r = {"bytes": {}, "claimed": f["claimed"][act].sum(0).tolist()}
                dec = {}
                for coder in CODERS:
                    for K in GROUPS:
                        hdr = encode_header(coder, model, K, width, height, B, T0_us)
                        rec = encode_group(hdr, w - w_prev, key, maps_r[:, :K - 1])
                        h, groups = decode_stream(hdr + rec, cache)
                        g = groups[0]
                        if len(groups) != 1 or g["w"] != w - w_prev or not np.array_equal(g["ids"], ids_r) \
                                or not np.array_equal(g["maps"], maps_r[:, :K - 1]):
                            raise AssertionError("the decoded group differs from the encoded one")
                        r["bytes"][f"{coder}_K{K}"] = len(rec)
                        if records_for == (int(B), float(rho)):
                            out.setdefault("records", {})[f"{model}_{coder}_K{K}"] = rec
                        if K == GROUPS[-1]:
                            g["w"] = w                          # the group is evaluated at its own window
                            dec[coder] = (h, g)
                h, g = dec["T"]
                rec_m = [reconstruct(h, g, m) for m in range(N_TARGETS + 1)]
                if len(rec_m[0][0]) != row["n_key"] or truth[0].match(*rec_m[0], OBJECTIVE) != row["n_key"]:
                    raise AssertionError("the decoded key events are not the key events")
                r["n_rec"] = [int(len(v[0])) for v in rec_m[1:]]
                for cell in cells:
                    r[f"match_s{cell[0]}_k{cell[1]}"] = [truth[m].match(*rec_m[m], cell) for m in range(1, N_TARGETS + 1)]
                hq, gq = dec["Q"]
                mq = [truth[m].match(*reconstruct(hq, gq, m), OBJECTIVE) for m in range(0, N_TARGETS + 1)]
                r["q_equals_t"] = bool(mq[0] == row["n_key"] and mq[1:] == r[f"match_s{OBJECTIVE[0]}_k{OBJECTIVE[1]}"])
                r["claim_equals_match"] = bool(r["claimed"] == r[f"match_s{OBJECTIVE[0]}_k{OBJECTIVE[1]}"])
                row["models"][model] = r
            out["codec"][f"B{B}_rho{float(rho)}"] = row
    return out


def sum_groups(groups) -> dict:
    """Sum of evaluated groups: counts and byte lengths add, the two checks are combined with ``and``."""
    def add(a, b):
        if isinstance(a, dict):
            return {k: (a[k] if k in ("w", "theta") else add(a[k], b[k])) for k in a}
        if isinstance(a, bool):
            return a and b
        if isinstance(a, list):
            return [add(u, v) for u, v in zip(a, b)]
        return a + b

    groups = [{k: v for k, v in g.items() if k != "records"} for g in groups]
    out = groups[0]
    for g in groups[1:]:
        out = add(out, g)
    out = dict(out)
    out["w"] = [int(g["w"]) for g in groups]
    return out


def evaluate_stream(buf: bytes, t_us, x, y, p, cell=OBJECTIVE) -> list:
    """The receiver's side: decode a complete stream and compare each of its windows with the true events.

    Uses the bytes of the stream and nothing of the sender. Returns one dictionary per group with
    the key window ``w`` and, for ``m`` = 0 .. ``K - 1``, ``n_rec``, ``n_true`` and ``match`` on ``cell``.
    """
    t_us = np.asarray(t_us, dtype=np.int64)
    h, groups = decode_stream(buf)
    T0, out = h["T0_us"], []
    for g in groups:
        row = {"w": int(g["w"]), "n_rec": [], "n_true": [], "match": []}
        for m in range(h["K"]):
            w0 = h["origin_us"] + (g["w"] + m) * T0
            a, b = np.searchsorted(t_us, (w0, w0 + T0))
            rec = reconstruct(h, g, m)
            row["n_rec"].append(int(len(rec[0])))
            row["n_true"].append(int(b - a))
            row["match"].append(Truth(t_us[a:b], x[a:b], y[a:b], p[a:b], w0, T0).match(*rec, cell))
        out.append(row)
    return out


def summarize(g: dict, config: str, model: str, coder: str, K: int, cell=OBJECTIVE) -> dict:
    """Fidelity, bits and the comparison with the baselines of one configuration, for a group or a sum of groups.

    ``g`` is the output of ``evaluate_group`` or of ``sum_groups``. Returns ``F``; ``q_eq = F / (2 - F)``;
    ``bits``, the bits of the records per true event; ``bits_direct``; ``bits_thin``, the bits of
    thinning at the share ``q_eq``; ``bits_base``, those of the envelope of ``thin``, of ``direct`` and
    of ``select`` with the block side of the configuration; ``gain = bits_base / bits`` and
    ``gain_thin = bits_thin / bits``; the event share ``share = n_key / n_true``; and
    ``gamma = q_eq / share``, the factor of directive 003 in events. With coder Q the comparison
    holds on grids of 2 or 4 px with one or three time bins, where the baselines pair every event.
    """
    row = g["codec"][config]
    r = row["models"][model]
    n = float(np.sum(g["n_true"][:K]))
    match = r[f"match_s{cell[0]}_k{cell[1]}"][:K - 1]
    F = group_fidelity(row["n_key"], r["n_rec"][:K - 1], g["n_true"][:K], match)
    q_eq = F / (2.0 - F)
    bits = 8.0 * r["bytes"][f"{coder}_K{K}"] / n
    direct = float(np.sum(g["direct"][coder][:K])) / n

    def points(rows):
        return ([float(np.sum(v["n_kept"][:K])) / n for v in rows] + [1.0],
                [float(np.sum(v[coder][:K])) / n for v in rows] + [direct])

    thin_pts = points([g["thin"][str(chi)] for chi in THIN_SHARES])
    side = config.split("_")[0] + "_"
    sel_pts = points([v for k, v in g["select"].items() if k.startswith(side)])
    thin = baseline_bits(q_eq, *thin_pts, envelope=False)
    base = baseline_bits(q_eq, thin_pts[0] + sel_pts[0], thin_pts[1] + sel_pts[1])
    share = row["n_key"] / n
    return {"F": F, "q_eq": q_eq, "bits": bits, "bits_direct": direct, "bits_thin": thin, "bits_base": base,
            "gain": base / bits, "gain_thin": thin / bits, "share": share,
            "gamma": q_eq / share if share > 0 else float("nan")}
```

## Appendix B. `tests/test_blockcodec_gate.py`

Normative. The executor commits this file unchanged.

```python
"""Gate for directive 007: regeneration on a fixed block grid with a complete bitstream, on synthetic scenes.

The scenes, seeds and tolerances are fixed here by the director. An executor implementation that
replaces or accelerates ``ec.blockcodec`` must pass this file unchanged.
"""
import numpy as np
import pytest

from ec import baseline, blockcodec as bc, regen, synth, synth_affine

W, H = 320, 240
T0 = bc.T0_US


def _merge(scenes, noise_per_px_window=0.0, duration_s=1.2, seed=7):
    z = [np.zeros(0, dtype=np.int64)]
    t = np.concatenate(z + [s.t for s in scenes]); x = np.concatenate(z + [s.x for s in scenes])
    y = np.concatenate(z + [s.y for s in scenes]); p = np.concatenate(z + [s.p for s in scenes])
    if noise_per_px_window > 0:
        rng = np.random.default_rng(seed)
        n = rng.poisson(noise_per_px_window * W * H * duration_s * 1e6 / T0)
        t = np.concatenate((t, rng.integers(0, int(duration_s * 1e6), n)))
        x = np.concatenate((x, rng.integers(0, W, n))); y = np.concatenate((y, rng.integers(0, H, n)))
        p = np.concatenate((p, rng.integers(0, 2, n)))
    o = np.argsort(t, kind="stable")
    return t[o].astype(np.int64), x[o].astype(np.int64), y[o].astype(np.int64), p[o].astype(np.int64)


def _scene(noise=0.01):
    a = synth.rigid_translation(width=W, height=H, n_points=400, c0=(40.0, 60.0), v=(200.0, 0.0), duration_s=1.2, seed=1)
    b = synth_affine.expanding_translation(width=W, height=H, n_points=400, c0=(100.0, 170.0), v=(60.0, 20.0),
                                           expand_rate=0.6, duration_s=1.2, seed=2)
    return _merge([a, b], noise)


@pytest.fixture(scope="module")
def ev():
    return _scene()


@pytest.fixture(scope="module")
def group(ev):
    return bc.evaluate_group(*ev, 9, 0, W, H, blocks=(40, 80), grid_for=(40, 1 / 16))


def test_uleb128_round_trip():
    v = np.array([0, 1, 127, 128, 16383, 16384, 2 ** 31, 2 ** 62 + 5])
    buf = bc.uleb_encode(v)
    assert len(buf) == 1 + 1 + 1 + 2 + 2 + 3 + 5 + 9
    out, pos = bc.uleb_decode(buf)
    assert list(out) == list(v) and pos == len(buf)
    out, pos = bc.uleb_decode(b"\xff" + buf, 3, 1)
    assert list(out) == [0, 1, 127] and pos == 4
    assert bc.uleb_encode([]) == b"" and len(bc.uleb_decode(b"")[0]) == 0


def test_coder_T_is_the_companion_transport_and_round_trips(ev):
    t, x, y, p = ev
    a, b = np.searchsorted(t, (9 * T0, 10 * T0))
    w = (t[a:b] - 9 * T0, x[a:b], y[a:b], p[a:b])
    buf = bc.encode_events_T(*w)
    assert 8 * len(buf) == baseline.payload_bits(*w)
    d = bc.decode_events_T(buf)
    o = np.lexsort((w[2], w[1], w[0]))
    assert all(np.array_equal(d[i], w[i][o]) for i in range(4))
    assert bc.encode_events_T(*(v[:0] for v in w)) == b"" and len(bc.decode_events_T(b"")[0]) == 0


def test_coder_Q_keeps_every_voxel_count_of_its_grid(ev):
    t, x, y, p = ev
    a, b = np.searchsorted(t, (9 * T0, 10 * T0))
    w = (t[a:b] - 9 * T0, x[a:b], y[a:b], p[a:b])
    for cell in ((1, 3), (2, 3), (2, 1), (1, 32)):
        d = bc.decode_events_Q(bc.encode_events_Q(*w, cell, W, H), cell, W, H)
        assert len(d[0]) == len(w[0])
        r = regen.voxel_f1(d[1], d[2], d[0], d[3], w[1], w[2], w[0], w[3], 0, T0, *cell)
        assert r["f1"] == 1.0
    # on the working grid the quantized stream is shorter than the transport, and coarser is shorter still
    q13, q23 = (len(bc.encode_events_Q(*w, c, W, H)) for c in ((1, 3), (2, 3)))
    assert q23 < q13 < len(bc.encode_events_T(*w))


def test_maps_round_trip_and_zero_maps_are_short():
    rng = np.random.default_rng(0)
    m = rng.integers(-40, 41, (7, 10, 6))
    for n_par in (2, 6):
        out = bc.decode_maps(bc.encode_maps(m, n_par), 7, 10, n_par)
        assert np.array_equal(out[:, :, :n_par], m[:, :, :n_par]) and not out[:, :, n_par:].any()
    assert len(bc.encode_maps(np.zeros((50, 10, 6), dtype=int), 6)) < 40
    assert bc.decode_maps(bc.encode_maps(np.zeros((0, 3, 6), dtype=int), 2), 0, 3, 2).shape == (0, 3, 6)


def test_the_map_with_zero_shape_parameters_is_the_translation():
    frame = bc.block_frame(9, 40, W)                       # second row, second block
    assert frame == (59.5, 59.5, 20.0)
    sx, sy = np.array([40, 50, 79]), np.array([40, 60, 79])
    ix, iy = bc.move(sx, sy, frame, (3, -2, 0, 0, 0, 0))
    assert list(ix) == [43, 53, 82] and list(iy) == [38, 58, 77]
    ix, _ = bc.move(sx, sy, frame, (0, 0, 2, 0, 0, 0))     # ia = 2: the two edges move by 2 px, outwards
    assert ix[0] == 38 and ix[-1] == 81
    assert bc.threshold(40, 1 / 16) == 100 and bc.threshold(20, 1 / 32) == 13 and bc.threshold(80, 1 / 2) == 3200
    assert bc.DENSITIES == (1 / 16, 1 / 8, 1 / 4, 1 / 2, 1.0) and bc.RADIUS_FIRST == 24


def test_the_search_never_pairs_fewer_events_than_no_motion_and_reaches_fast_objects():
    # an object at 900 px/s moves 30 px per window, beyond the first stage of a 12 px search
    a = synth.rigid_translation(width=W, height=H, n_points=300, c0=(20.0, 100.0), v=(900.0, 0.0), duration_s=0.4, seed=4)
    g = bc.evaluate_group(*_merge([a]), 1, 0, W, H, blocks=(40,), densities=(1 / 16,), models=("static", "translation"))
    r = g["codec"]["B40_rho0.0625"]["models"]
    assert r["translation"]["match_s2_k3"][0] > 0.8 * r["translation"]["n_rec"][0] > 0
    assert r["static"]["match_s2_k3"][0] < 0.4 * r["translation"]["match_s2_k3"][0]
    # a search whose window does not hold zero falls back to zero when zero pairs more
    calls = []

    def score(q, cell):
        calls.append(q)
        return 5 if q[:2] == (0, 0) else 1

    assert bc.search_translation(score, (40.0, 0.0), 3) == (0, 0)
    assert bc.search_translation(lambda q, cell: 1, (40.0, 0.0), 3) == (40, 0)


def test_a_stream_of_several_groups_decodes_from_its_bytes_alone(ev):
    t, x, y, p = ev
    hdr = bc.encode_header("T", "translation", 4, W, H, 40)
    assert len(hdr) == bc.HEADER.size == 28
    recs, sent, w_prev = [], [], 0
    for w in (9, 15, 21):
        a, b = np.searchsorted(t, (w * T0, (w + 1) * T0))
        win = (t[a:b] - w * T0, x[a:b], y[a:b], p[a:b])
        bid = bc.block_ids(win[1], win[2], 40, W)
        ids, cnt = np.unique(bid, return_counts=True)
        sel = np.isin(bid, ids[cnt >= 100])
        key = tuple(v[sel] for v in win)
        maps = np.arange(len(ids[cnt >= 100]) * 3 * 6).reshape(-1, 3, 6) % 7 - 3
        recs.append(bc.encode_group(hdr, w - w_prev, key, maps))
        sent.append((w, key, ids[cnt >= 100], maps))
        w_prev = w
    h, groups = bc.decode_stream(hdr + b"".join(recs))
    assert (h["coder"], h["model"], h["K"], h["B"], h["width"], h["height"], h["T0_us"]) == ("T", "translation", 4, 40, W, H, T0)
    assert len(groups) == 3
    for g, (w, key, ids, maps) in zip(groups, sent):
        assert g["w"] == w and np.array_equal(g["ids"], ids)
        assert np.array_equal(g["maps"][:, :, :2], maps[:, :, :2]) and not g["maps"][:, :, 2:].any()
        assert len(g["key"][0]) == len(key[0])
        r0 = bc.reconstruct(h, g, 0)
        assert r0[0].min() >= w * T0 and r0[0].max() < (w + 1) * T0
    with pytest.raises(ValueError):
        bc.decode_stream(hdr + recs[0][:-3])
    with pytest.raises(ValueError):
        bc.encode_group(hdr, 1, sent[0][1], sent[0][3][:-1])


def test_every_fidelity_comes_from_decoded_bytes_and_agrees_with_the_senders_count(group):
    for cfg, row in group["codec"].items():
        for model, r in row["models"].items():
            assert r["claim_equals_match"] and r["q_equals_t"], (cfg, model)
            assert all(0 <= a <= b for a, b in zip(r["match_s2_k3"], r["n_rec"]))
            assert all(a <= b for a, b in zip(r["match_s2_k3"], r["match_s2_k1"]))
            assert r["bytes"]["T_K2"] <= r["bytes"]["T_K4"] <= r["bytes"]["T_K8"] <= r["bytes"]["T_K11"]
            assert r["bytes"]["Q_K11"] < r["bytes"]["T_K11"] or row["n_key"] == 0
        assert row["n_key"] <= group["n_true"][0] and row["n_true_in_active"][0] == row["n_key"]
    full = group["codec"]["B40_rho0.0625"]["models"]["affine"]
    assert all(f"match_s{s}_k{k}" in full for s in (1, 2, 4) for k in (1, 3, 8, 32))
    assert all(a <= b for a, b in zip(full["match_s1_k32"], full["match_s2_k32"]))
    assert all(a <= b for a, b in zip(full["match_s2_k32"], full["match_s4_k32"]))
    assert "match_s1_k32" not in group["codec"]["B80_rho0.0625"]["models"]["affine"]


def test_match_equals_voxel_f1(ev):
    t, x, y, p = ev
    a, b, c = np.searchsorted(t, (9 * T0, 10 * T0, 11 * T0))
    tr = bc.Truth(t[b:c], x[b:c], y[b:c], p[b:c], 10 * T0)
    pt, px, py, pp = t[a:b] + T0, x[a:b] + 6, y[a:b], p[a:b]
    for cell in bc.CELLS_ALL:
        r = regen.voxel_f1(px, py, pt, pp, x[b:c], y[b:c], t[b:c], p[b:c], 10 * T0, T0, *cell)
        assert tr.match(pt, px, py, pp, cell) == round(r["f1"] * (r["n_pred"] + r["n_true"]) / 2)


def test_moving_objects_are_followed_by_the_maps_and_not_by_the_repeated_key_events(group):
    for cfg in ("B40_rho0.0625", "B80_rho0.0625"):
        s = {m: bc.summarize(group, cfg, m, "Q", 11) for m in bc.MODELS}
        assert s["translation"]["F"] > s["static"]["F"] + 0.25
        assert s["affine"]["F"] >= s["translation"]["F"] - 0.01
        # against the cheapest subset scheme the repeated key events gain nothing, the maps do
        assert s["static"]["gain"] < 1.0 and s["translation"]["gain"] > 3.0
        assert all(v["gain"] <= v["gain_thin"] for v in s.values())
        assert s["translation"]["bits"] < 0.25 * s["translation"]["bits_direct"]
    # with blocks of 80 px the growing object needs the shape parameters
    s80 = {m: bc.summarize(group, "B80_rho0.0625", m, "Q", 11) for m in bc.MODELS}
    assert s80["affine"]["F"] > s80["translation"]["F"] + 0.02
    s = bc.summarize(group, "B40_rho0.0625", "affine", "T", 4)
    assert abs(s["gamma"] - (s["F"] / (2 - s["F"])) / s["share"]) < 1e-12 and 0.15 < s["share"] < 0.25
    # a shorter group is more faithful and costs more
    a4, a11 = (bc.summarize(group, "B40_rho0.0625", "affine", "Q", K) for K in (4, 11))
    assert a4["F"] > a11["F"] and a4["bits"] > a11["bits"]


def test_thinning_is_what_its_formula_says(group):
    n = group["n_true"]
    assert bc.group_fidelity(10, [8, 6], [10, 12, 12], [4, 3]) == 2 * 17 / (10 + 14 + 34)
    for chi in bc.THIN_SHARES:
        kept = group["thin"][str(chi)]["n_kept"]
        assert abs(sum(kept) / sum(n) - chi) < 0.02
        assert all(a < b for a, b in zip(group["thin"][str(chi)]["Q"], group["direct"]["Q"]))
    # thinning costs more per kept event than sending everything: its points lie above the chord
    q = sum(group["thin"]["0.25"]["n_kept"]) / sum(n)
    assert sum(group["thin"]["0.25"]["Q"]) > q * sum(group["direct"]["Q"])


def test_the_baseline_is_the_lower_convex_envelope_of_the_subset_schemes():
    sh, b = [1.0, 0.5, 0.25], [10.0, 7.0, 4.0]                   # a concave curve, as thinning gives
    assert bc.baseline_bits(0.25, sh, b, envelope=False) == 4.0
    assert bc.baseline_bits(0.375, sh, b, envelope=False) == 5.5
    assert bc.baseline_bits(0.25, sh, b) == 2.5 and bc.baseline_bits(0.5, sh, b) == 5.0   # the chord to (1, 10)
    assert bc.baseline_bits(0.0, sh, b) == 0.0 and bc.baseline_bits(1.0, sh, b) == 10.0
    # a point under the chord enters the envelope, and the cheaper of two points at one share counts
    assert bc.baseline_bits(0.5, sh + [0.5, 0.5], b + [3.0, 9.0]) == 3.0
    assert bc.baseline_bits(0.25, sh + [0.5], b + [3.0]) == 1.5
    assert bc.baseline_bits(0.75, sh + [0.5], b + [3.0]) == 6.5


def test_select_sends_the_active_blocks_of_every_window(ev, group):
    t, x, y, p = ev
    row = group["select"]["B40_rho0.0625"]
    for m in (0, 3, 10):
        a, b = np.searchsorted(t, ((9 + m) * T0, (10 + m) * T0))
        bid = bc.block_ids(x[a:b], y[a:b], 40, W)
        ids, cnt = np.unique(bid, return_counts=True)
        sel = np.isin(bid, ids[cnt >= 100])
        assert row["n_kept"][m] == int(sel.sum())
        assert row["Q"][m] == 8 * len(bc.encode_events_Q(t[a:b][sel] - (9 + m) * T0, x[a:b][sel], y[a:b][sel], p[a:b][sel],
                                                         (2, 3), W, H))
    # in the key window select sends what the codec sends as key events
    assert row["n_kept"][0] == group["codec"]["B40_rho0.0625"]["n_key"]
    assert set(group["select"]) == set(group["codec"])


def test_one_fit_under_the_smallest_threshold_serves_the_larger_ones(ev):
    t, x, y, p = ev
    e = np.searchsorted(t, [(9 + m) * T0 for m in range(5)])
    win = [(t[a:b] - (9 + m) * T0, x[a:b], y[a:b], p[a:b]) for m, (a, b) in enumerate(zip(e[:-1], e[1:]))]
    lo = bc.fit_group(win[0], win[1:], 40, "affine", 50, W, H)
    hi = bc.fit_group(win[0], win[1:], 40, "affine", 400, W, H)
    n = len(hi["ids"])
    assert 0 < n < len(lo["ids"])
    assert np.array_equal(lo["ids"][:n], hi["ids"]) and np.array_equal(lo["maps"][:n], hi["maps"])
    assert np.array_equal(lo["claimed"][:n], hi["claimed"])
    assert list(lo["counts"]) == sorted(lo["counts"], reverse=True)
    again = bc.fit_group(win[0], win[1:], 40, "affine", 50, W, H)
    assert all(np.array_equal(lo[k], again[k]) for k in ("ids", "maps", "claimed", "n_in"))


def test_events_that_leave_the_sensor_are_dropped():
    a = synth.rigid_translation(width=W, height=H, n_points=300, c0=(250.0, 100.0), v=(300.0, 0.0), duration_s=1.2, seed=3)
    g = bc.evaluate_group(*_merge([a]), 3, 0, W, H, blocks=(40,), densities=(1 / 16,), models=("translation",))
    r = g["codec"]["B40_rho0.0625"]["models"]["translation"]
    assert r["n_rec"][0] > 0 and r["n_rec"][-1] < r["n_rec"][0] and r["claim_equals_match"]


def test_on_noise_alone_the_maps_add_almost_nothing_to_the_repeated_key_events():
    # Uniform noise pairs by chance on the working grid, and a search over displacements finds a few
    # more chance pairs. Neither amounts to a gain over the cheapest subset scheme.
    t, x, y, p = _merge([], noise_per_px_window=0.1, seed=11)
    g = bc.evaluate_group(t, x, y, p, 9, 0, W, H, blocks=(40,), densities=(1 / 16,), models=("static", "translation"))
    st, tr = (bc.summarize(g, "B40_rho0.0625", m, "Q", 11) for m in ("static", "translation"))
    assert st["F"] < 0.2 and 0.0 <= tr["F"] - st["F"] < 0.06
    assert st["gain"] < 1.0 and tr["gain"] < 1.0
    assert all(bc.summarize(g, "B40_rho0.0625", m, "Q", 4)["gain"] < 1.0 for m in ("static", "translation"))
    assert g["codec"]["B40_rho0.0625"]["models"]["translation"]["claim_equals_match"]


def test_groups_add_up(ev, group):
    other = bc.evaluate_group(*ev, 20, 9, W, H, blocks=(40, 80), grid_for=(40, 1 / 16))
    both = bc.sum_groups([group, other])
    assert both["w"] == [9, 20] and both["n_true"][0] == group["n_true"][0] + other["n_true"][0]
    a, b, c = (bc.summarize(g, "B40_rho0.0625", "affine", "Q", 4) for g in (group, other, both))
    assert min(a["F"], b["F"]) <= c["F"] <= max(a["F"], b["F"])
    assert min(a["bits"], b["bits"]) <= c["bits"] <= max(a["bits"], b["bits"])
    row = both["codec"]["B40_rho0.0625"]
    assert row["theta"] == 100 and row["models"]["affine"]["claim_equals_match"] is True
    assert row["n_key"] == group["codec"]["B40_rho0.0625"]["n_key"] + other["codec"]["B40_rho0.0625"]["n_key"]


def test_a_complete_stream_gives_the_receiver_the_numbers_of_the_sender(ev):
    cfg, B, rho = "B40_rho0.0625", 40, 1 / 16
    gs, w_prev = [], 0
    for w in (9, 20):
        gs.append(bc.evaluate_group(*ev, w, w_prev, W, H, blocks=(B,), densities=(rho,), records_for=(B, rho)))
        w_prev = w
    for model in bc.MODELS:
        for coder in bc.CODERS:
            for K in (4, 11):
                name = f"{model}_{coder}_K{K}"
                stream = bc.encode_header(coder, model, K, W, H, B) + b"".join(g["records"][name] for g in gs)
                assert len(stream) == 28 + sum(g["codec"][cfg]["models"][model]["bytes"][f"{coder}_K{K}"] for g in gs)
                rows = bc.evaluate_stream(stream, *ev)
                assert [r["w"] for r in rows] == [9, 20]
                for r, g in zip(rows, gs):
                    row = g["codec"][cfg]
                    assert r["n_true"] == g["n_true"][:K]
                    assert r["n_rec"] == [row["n_key"]] + row["models"][model]["n_rec"][:K - 1]
                    assert r["match"] == [row["n_key"]] + row["models"][model]["match_s2_k3"][:K - 1]
    assert "records" not in bc.sum_groups(gs)


def test_an_empty_key_window_is_a_valid_group():
    t, x, y, p = _merge([], noise_per_px_window=0.001, seed=5)
    g = bc.evaluate_group(t, x, y, p, 9, 0, W, H, blocks=(40,), densities=(1 / 2,))
    row = g["codec"]["B40_rho0.5"]
    assert row["n_active"] == 0 and row["n_key"] == 0
    assert bc.summarize(g, "B40_rho0.5", "affine", "T", 4)["F"] == 0.0
```
