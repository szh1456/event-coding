# Directive 001. Preflight, and how many bits a motion model saves on in-box events

| | |
|---|---|
| track | `motion_predictability`, short name `mp` |
| population | the 112 development recordings of `config/population.yaml`, and no other recording |
| results directory | `results/mp/` |
| report | `docs/directives/reports/001.md` |
| runs after | nothing; this is the first directive |

## 1. Why

Under rigid motion in the image plane, the pixels along an object's path see
delayed copies of the same signal. This is the delay case of the generalized
sampling expansion (`papoulis1977gse` in the ledger): the temporal derivative at a
pixel is the velocity times the spatial gradient, and a decoder that knows the
velocity obtains it from pixels it has already received. An edge that crosses M
pixels is then described M times by the event stream, and only once is needed.

What a decoder cannot predict is the timing jitter of each pixel, scene content
that enters the view, and noise. The brief's pilot found that a coder with recency
contexts gains little over a generic compressor. That leaves open whether an
explicit motion model gains much more. This directive measures it as a code
length, before any coder is built.

**The quantity.** For an object at an evaluation instant, take its events of the
last `T1` (the template) and its events of the next `T2` (the future). Score the
future events under three predictive densities built from the template:

- `static`: the template as it is. This is what recency contexts can use;
- `label`: the template warped by the annotation boxes (translation and scale);
- `cmax`: the template warped at the constant velocity that makes it sharpest.

`gain(model)` is the number of bits per future event that the model saves over
knowing only the object's box. The headline is

```
Delta = gain(cmax) - gain(static)        bits per in-box event           (1)
```

the saving that explicit motion adds to recency. All definitions are in the
docstring of `ec/motion.py`, which is part of this directive.

## 2. Disclosure

Before this directive was written the director had:

- run the pilot of the brief on three public sample recordings, one of which is a
  5 s excerpt of `val_night_011` (see `docs/DATA.md`);
- read the companion repository at commit `dc02612`, including its directive
  reports, and printed the array names and medians of
  `results/sbc/objects_per_recording.npz`;
- developed `ec/motion.py` on synthetic data from `ec/synth.py` only. The cell
  size, the bandwidth set, the search widths and the skip thresholds were fixed
  on that synthetic data.

No event or annotation of a development recording has been opened by the director.

## 3. Author decisions

**D-001-1, default: authorized.** The 112 development recordings and their
annotations are read on `cnt`, read-only, from the paths in `docs/DATA.md`.

**D-001-2, default: authorized.** Missing Python packages (numba, scipy, h5py,
zstandard) are installed into a private `--target` directory under
`~/prjs/event_coding/`, as the companion project did for zstandard. Nothing is
installed system-wide.

**D-001-3, default: as stated in Section 8.** The decision rule and its
thresholds.

## 4. Isolation

- Resolve recording paths only from `config/population.yaml`. Before the first
  event file is opened, commit `results/mp/population_check.json` with the list of
  resolved event and annotation file names and the statement that none of them is
  outside the population. A file name that starts with `val_` or `test_` anywhere
  in that list is a `BLOCKED` condition.
- Do not list, hash, or open any other file in the data or annotation
  directories.
- Write only under `~/prjs/event_coding/` on the host and `results/mp/` in the
  repository.

## 5. Stage P: preflight

Run the checks in order. A failed check is a `BLOCKED` report with the evidence.

**P1. Environment.** Record host, Python, numpy, scipy, h5py, zstandard and numba
versions, and the BLAS thread variables (one thread per process, as in the
companion project).

**P2. Inventory.** 112 of 112 event files and 112 of 112 annotation files are
found. The SHA-256 of the sorted identifier list equals `ids_sorted_sha256` in
`config/population.yaml`. For each recording record the number of events, the
duration, the counts of clamped timestamps and repaired coordinates returned by
`ec.baseline.read_events`, the number of boxes and the number of tracks.

**P3. Box convention and clock.** `ec/annotations.py` assumes that `(x, y)` is
the top-left corner and that annotation time is on the event clock with zero
offset. Test both on the first five day and the first five night recordings in
sorted order, using the first 60 s of each:

- for each time shift `s` in {-200, -100, -33, 0, 33, 100, 200} ms added to the
  annotation timestamps, and each convention `c` in {top-left, center};
- for each annotation frame at (shifted) time `tau`, count the events in
  `[tau, tau + 33.333 ms)` inside any box of that frame and outside all boxes;
- `rho(s, c)` = (events inside / total box area) / (events outside / remaining
  sensor area), pooled over the frames of the recording.

Pass: `(0, top-left)` has the largest `rho` in at least 8 of the 10 recordings
and in the pooled data. Report the full table. If the pooled maximum is at
another `(s, c)`, stop: the director will amend the annotation convention.

**P4. Tracks.** Count the tracks that live at least 1 s, by lighting and by class
group (vehicles are `class_id` in {1, 3, 4, 5, 6}, as in the companion project;
the integer-to-name mapping is unresolved there and is not used here). Report the
distribution of track duration, box area, and label speed.

**P5. Gate.** `python3 -m pytest -q` passes on the execution host with no skipped
test. `tests/test_motion_gate.py` is the gate of Stage M and is not edited.

## 6. Stage M: the measurement

Use `ec.motion.evaluate_instant` as it is. An accelerated implementation is
allowed if it passes `tests/test_motion_gate.py` unchanged and reproduces the
reference on the first 200 scored instants of `train_day_0001_td` to within 1e-6
in every output. State which one ran.

**Instants.** For every track that lives at least 1 s:
`ec.motion.evaluation_instants(track)`, that is `t_e = first + 0.3 s + k 0.5 s`
while `t_e + 0.35 s <= last`.

**Settings.** `T2` = 33,333 us. Six pairs `(T1, D)` in ms: (100, 0), (100, 33),
(100, 100), (100, 300), (50, 0), (200, 0), with 33 ms meaning 33,333 us.
`margin_px` = 2. Models: `static`, `label`, `cmax`. Sensor 1280 x 720.

**Skips.** `evaluate_instant` returns a skip reason when the template has fewer
than 200 events, the future window fewer than 50, the windows leave the track's
life, or the support leaves the sensor. Count skips by reason and stratum. Do not
change the thresholds.

**Strata**, assigned per instant:

| name | values |
|---|---|
| lighting | day, night (from the recording identifier) |
| class group | vehicles, other |
| speed | `speed_label` in [0, 20), [20, 100), [100, 300), [300, inf) px/s |
| overlap | isolated if the support rectangle meets no other track's interpolated box at `t_e`, else overlapping |

The headline stratum **H** is: vehicles, isolated, speed in [20, 300) px/s
(two speed bins pooled), setting (100, 0).

**Aggregation.** The unit is the recording. For a stratum and a setting, a
recording's value of a quantity is the median over its scored instants in that
stratum, and the recording enters only with at least 20 such instants. A table
entry is the median over recordings, with a 95% interval from 2000 bootstrap
resamples of recordings (seed 20261008), and the number of recordings and of
instants behind it.

## 7. Tables for the report

1. **Headline, stratum H, by lighting:** `Delta` of Eq. (1), `gain` of each model,
   `eps` of each model, `set_bits` of each model and `ref_set_bits`, `b_px` of
   `cmax`, the share of instants with `b_px` at the smallest bandwidth,
   `cmax_tau_eq_us`, `redundancy` of `cmax` and of `static`, `path_px_label`.
2. **Lead:** the same quantities for `cmax` and `static` at `D` in {0, 33, 100,
   300} ms with `T1` = 100 ms, stratum H, by lighting.
3. **Template length:** `T1` in {50, 100, 200} ms at `D` = 0, stratum H.
4. **Speed and class:** `Delta`, `gain(cmax)`, `eps(cmax)` for each speed bin and
   class group, isolated instants, setting (100, 0), by lighting.
5. **Overlap:** stratum H against the same stratum with overlapping instants.
6. **Velocity:** the distribution of `cmax_speed / speed_label` and of the angle
   between the two velocities, stratum H.
7. **Skips:** counts by reason, lighting and class group, and the share of
   in-box events that fall in scored instants.

## 8. Predictions and decision rule

Written by the director before any development recording was read.

| quantity, stratum H, setting (100, 0) | day | night |
|---|---|---|
| `Delta`, bits per event | 1 to 4 | 0.5 to 3 |
| `gain(static)` | 1 to 4 | 0.5 to 3 |
| `eps(cmax)` | 0.2 to 0.5 | 0.3 to 0.7 |
| share of instants with `b_px` at the minimum | under 50% | under 50% |
| `cmax_speed / speed_label` within 0.8 to 1.25 | 80% of instants | 70% of instants |
| `Delta` at `D` = 300 ms relative to `D` = 0 | under one half | under one half |

On the synthetic fixture with ideal translation and 0.3 ms jitter, `Delta` is 5.5
to 7 bits and `eps(cmax)` is under 0.05. Real objects should fall short of that
because of scale change, non-rigid parts, label noise in the event selection, and
background events inside the box.

**Rule (D-001-3).** With `Delta_day` and `Delta_night` the medians over recordings
in stratum H at setting (100, 0):

- **GO** for a motion-compensated coder if both are at least 3 bits;
- **NO-GO** if both are under 1 bit. Explicit motion then adds too little to
  recency, and the project continues as the bit-budget analysis of the brief;
- otherwise the director proposes one further measurement (a scale-aware warp or
  a finer grid), chosen from Tables 2 to 6, before any coder is built.

## 9. Acceptance checks

1. P1 to P5 pass.
2. `results/mp/population_check.json` was committed before the first event file
   was opened, and the report gives both commit hashes.
3. Every instant is either scored or counted as a skip:
   scored + skipped = generated, per recording and setting.
4. For every scored instant and model, `ref_bits` equals
   `log2(2 * support_px * 33333)` to 1e-6, and `eps` lies in [0.001, 1].
5. `gain` of the `static` model at setting (100, 300) is below its value at
   (100, 0) in the median over recordings of stratum H. If it is not, explain.
6. The suite passes at the executed commit.

## 10. Outputs

| file | content |
|---|---|
| `results/mp/population_check.json` | Section 4 |
| `results/mp/preflight.json` | P1 to P5, including the full `rho` table of P3 |
| `results/mp/per_recording.npz` | recording x setting x stratum x quantity medians and instant counts |
| `results/mp/report.json` | every table of Section 7 |
| `results/mp/provenance.json` | commit, host, versions, wall time, and the path and SHA-256 of the per-instant files kept on the host |

Per-instant files (`instants_*.npz`) stay on the host under
`~/prjs/event_coding/mp/` and are not committed.

## 11. Cost

`ec.motion` scores one model at one instant in about 0.1 to 0.3 s for a small
box on one core, and the normalizer grows with box area times speed. With about
5,400 tracks the run is expected to take tens of CPU-hours. Parallelize over
recordings. If a full pass would exceed 300 CPU-hours, stop after the preflight
and report the measured cost per instant by box area, so that the director can
amend the instant spacing.

## 12. What comes next

Directive 002 will redo the bit budget of the brief on the development recordings
with the actual baseline (`ec.baseline.tiled_sizes`) and a split of events into
in-box, out-of-box and object-free windows. It needs the box convention that P3
of this directive settles, so it is written after this report.
