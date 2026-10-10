# Directive 009. The frozen block codec on a car-mounted dataset (DSEC)

| | |
|---|---|
| track | `second dataset`, short name `ds` |
| population | the left-camera event files of the training split of DSEC, as listed by its official download page. Nothing else of DSEC, and no recording of eTraM |
| results directory | `results/ds/` |
| report | `docs/directives/reports/009.md` |
| runs after | directive 008 |

## 1. Why

Directive 007 measured the block codec on a static camera, where objects move
and the background does not. The paper's theory is for an affine flow, and its
second case is a camera on a car: the whole scene moves, and the edges of the
road and what stands next to it approach and grow. Rule D-007-6 gave GO, and
its consequence is this directive: the codec, with the block side and the
threshold that were frozen on eTraM, on a dataset recorded from a moving car.

Nothing is tuned here. The configuration is `B` = 20 px and `rho` = 1 event per
pixel of the key window, read from `results/bk/tuning.json`. The other four
densities at `B` = 20 are run next to it, as in Stage R of directive 007,
because the density acts as a rate control and the paper reports the sweep.
The sensor is another one, 640 x 480 against 1280 x 720, so an unchanged
configuration is a test of how far it carries, not a best case.

The run also settles which map the paper's codec sends per block. On eTraM the
translation and the affine map are within 1% of each other in gain, the
translation ahead with coder Q. On a moving camera the scale changes more.

## 2. Disclosure

Before this directive was written the director had:

- read report 007 and the committed files of `results/bk/`;
- read no event of DSEC. Its knowledge of the dataset is the entry
  `dsec_dataset_and_format` of the ledger: the paper as recorded in the brief,
  and the page on the data format, read on 2026-10-10. The download page could
  not be read from the director's side, so the list of sequences, the sizes of
  the archives, the types of the datasets in a file and the package that reads
  the compression are not verified. Stage D verifies them;
- developed `ec/dsec.py` and its gate on files written by the gate itself, in
  the documented layout.

## 3. Author decisions

**D-009-1, default: authorized.** The second dataset is DSEC, left event camera,
training split. The executor downloads those event files, and nothing else,
from the official host to `~/prjs/event_coding/data/dsec/` on `cnt`, under the
rules that this pull request adds to `docs/DATA.md`. If `h5py` cannot read the
compression of the files, the package `hdf5plugin` is installed for the user
that runs the directive. Nothing else is installed.

**D-009-2, default: as stated in Section 11.** The rule of replication.

**D-009-3, default: as stated in Section 11.** The map of the paper's codec.
D-007-1 stays in force until this directive has reported. After it: if the gain
of the translation exceeds that of the affine map with coder Q at `K` = 4 on
this dataset, as it does on eTraM by day and by night, the paper's codec sends
one translation per block and reports the affine map as a variant. Otherwise
the affine map stays. In both cases the motion model of the paper is the
affine flow of its theory, which a field of block translations approximates
with an error that grows with the block side.

**D-009-4, default: authorized.** The executor adds `ec/dsec.py` and
`tests/test_dsec_gate.py` with the content of Appendices A and B, unchanged.

## 4. Isolation

- This directive opens no recording and no annotation of eTraM and writes
  nothing under `results/bk/`.
- It writes under `~/prjs/event_coding/data/dsec/` (the files as downloaded),
  under `~/prjs/event_coding/ds/` (everything it computes) and under
  `results/ds/`.
- Commit `config/population_dsec.yaml` and
  `results/ds/population_check.json` before the first event file is opened
  (Stage D, step 2).

## 5. Stage P: preflight

A failed check is a `BLOCKED` report with the evidence.

**P1. Environment.** The versions equal those of `results/bk/preflight.json`.
Record the versions of `h5py` and, if it is installed, `hdf5plugin`.

**P2. Files.** `ec/blockcodec.py` and `tests/test_blockcodec_gate.py` have the
SHA-256 of directive 007, Section 14. `ec/dsec.py` and
`tests/test_dsec_gate.py` have those of Section 13.

**P3. Gates.** `python3 -m pytest -q -p no:anyio` passes with no skipped test.

**P4. Frozen configuration.** `results/bk/tuning.json` names `B` = 20 and
`rho` = 1.0, at the commit `b29393f` or a descendant in which the file is
unchanged.

## 6. Stage D: the data

1. **List.** From the official download page of DSEC
   (https://dsec.ifi.uzh.ch/dsec-datasets/download/), take every sequence of
   the training split that offers the events of the left camera. Write the
   sorted names to `config/population_dsec.yaml`, with the URL of the page, the
   date, the URL of each file and its size as the page or the server states
   it. If the page does not separate a training split, or does not offer the
   left camera by itself, stop and report what it offers.
2. **Commit** the population file and `results/ds/population_check.json`.
3. **Space.** The free space under `~/prjs/event_coding/` must exceed twice the
   total size of the files plus 100 GB. Otherwise stop and report both numbers.
4. **Download** the listed files, and only those, from the official host. If
   the host offers the left camera only inside an archive that also holds
   other data, download the archive, keep the left event files, delete the
   rest, and say so in the report. Record the size and the SHA-256 of every
   kept event file.
5. **Format.** Call `ec.dsec.describe` on the first file and commit its output
   in `results/ds/preflight.json`. Then read every file once with
   `ec.dsec.read_events`. A `ValueError` is a `BLOCKED` report with the message
   and the output of `describe`: the file then differs from the
   documentation, and the director amends the reader. Do not edit the reader.
6. **Inventory.** For every sequence: number of events, first and last stored
   time, duration, events per second, the mean number of events per pixel and
   window (`T0` = 33,333 us, 307,200 pixels), `t_offset`, and the number of
   clamped time inversions.
7. **Ledger.** Update the entry `dsec_dataset_and_format` of
   `docs/REFERENCE_LEDGER.md` in the same commit with what steps 1 and 5
   verified: the list of sequences, the license statement of the page, the
   types and the compression.

## 7. Definitions

As in directive 007, Section 6, with these changes.

**Sensor.** 640 x 480.

**Windows.** `T0` = 33,333 us and origin 0 on the stored times that
`ec.dsec.read_events` returns. Window `w` is `[w T0, (w + 1) T0)`.

**Groups.** With `w_first` the window that holds the first event of the
sequence, the key windows are `w_j = w_first + 30 + S j`, `j` = 0, 1, ..., for as
long as `(w_j + 11) T0` does not exceed the time of the last event. `w_prev` is
`w_(j-1)`, and 0 for `j` = 0. The spacing is `S` = 30 windows (1 s) unless
Section 12 changes it. The sequences of this dataset are shorter than the
recordings of eTraM, which is why the spacing is shorter.

**Configuration.** `blocks=(20,)`, the five densities of `ec.blockcodec`, the
three models, `grid_for=(20, 1.0)`, `records_for=(20, 1.0)`.

**Unit and aggregation.** The unit is the sequence. A sequence enters a table
with at least 10 groups at `S` = 30, 5 at `S` = 60 and 3 at `S` = 90. Strata:
`all`, every sequence together, which is the stratum of the rule; and one
stratum per location, the name of the sequence up to its first digit, for
every location with at least five entering sequences. Bootstrap seed 20261013.

**Acceleration and timing.** As in directive 007, Section 6.

## 8. Stage 0: one complete pass on two sequences

As directive 007, Section 7, on the first and the middle sequence of the sorted
list, groups `j` = 0 to 4, with the configuration of Section 7 of this
directive and the 24 streams of (20, 1.0) per sequence. The receiver is a
separate process that is given the stream files, and the events only to score.
The census counts, for every key window of every sequence, the active blocks
at `B` = 20 for the five densities. All checks of that section apply.

## 9. Stage R: all sequences

Every group of every sequence, with the configuration of Section 7. For every
sequence, the eight complete streams of the model `affine` and the eight of the
model `translation`, each scored by `evaluate_stream` in a separate process.
Record the size and the SHA-256 of every stream file.

## 10. Tables for the report

`results/ds/report.json` has the layout of `results/bk/report.json`, with the
strata of Section 7 in place of `day` and `night`, so that
`scripts/bk_figure.py` reads it. Coder Q and the working grid unless stated.

1. **Inventory.** Stage D, step 6, per sequence, and the totals.
2. **Headline.** As Table 2 of report 007, for every stratum, with coder Q and
   with coder T, and with the ratio of `gain` of `affine` to that of
   `translation`.
3. **Events.** `share` and `gamma` of the three models for the four `K`.
4. **Thresholds.** As Table 4 of report 007.
5. **Windows.** As Table 5 of report 007.
6. **Grids.** As Table 6 of report 007.
7. **Bytes.** As Table 7 of report 007, for `affine` and for `translation`.
8. **Baselines.** As Table 8 of report 007.
9. **Census.** As Table 9 of report 007, for `B` = 20.
10. **Maps.** For the frozen configuration and the model `affine`, over the
    blocks of all groups, at `m` = 1, 4 and 10: the 10%, 50% and 90% quantiles of
    the length of the displacement `(dx, dy)` in px, and the share of blocks
    with a nonzero shape parameter. These come from the map arrays of the
    decoded streams.
11. **Next to eTraM.** The rows of Table 2 at `K` = 4 and `K` = 11 for `affine`
    and `translation`, coder Q, stratum `all`, next to the same rows of report
    007 by day and by night, copied and marked as copied.
12. **Fit and checks.** As Tables 10 and 11 of report 007.

Then draw the figure:

```
python3 scripts/bk_figure.py results/ds/report.json results/ds/fig_bits.pdf all
```

and commit `results/ds/fig_bits.pdf`, `.png` and `.json`.

## 11. Predictions and rules

Written by the director before any event of DSEC was read. Stratum `all`,
frozen configuration, working grid, medians over sequences.

| quantity | predicted |
|---|---|
| events per pixel and window, median sequence | 0.1 to 1 (eTraM: 0.04) |
| share of the key-window events that are key events | 0.3 to 0.8 |
| `bits_direct`, coder Q | 0.8 to 2.5 bits per event |
| `F` at `K` = 4, model `affine` | 0.40 to 0.70 |
| `gain` of `affine`, coder Q, `K` = 4 | 1.1 to 1.8 |
| `gain` of `affine`, coder Q, `K` = 11 | 1.5 to 3.5 |
| `gain` of `static`, coder Q, `K` = 4 | 0.4 to 0.8, lower than on eTraM because nothing stands still |
| `gain(affine) / gain(translation)`, coder Q, `K` = 4 | 0.97 to 1.05 |
| `F(affine) - F(translation)` at `K` = 11 | 0 to 0.04 |
| median displacement at `m` = 10 | 5 to 40 px |

**Rule of replication (D-009-2).** Stratum `all`, frozen configuration, working
grid, coder Q, `K` = 4, with the better of the models `affine` and
`translation`:

- **REPLICATED** if `gain` is at least 1.25 and at least 1.10 times `gain` of
  the model `static`. These are the thresholds of D-007-6.
- **NOT REPLICATED** otherwise. Nothing is tuned on this dataset in response.
  The paper then reports the result as measured, with the sweep of the
  densities, as the limit of a region scheme whose threshold was set on a
  static camera.

**Map of the paper's codec (D-009-3).** Stratum `all`, coder Q, `K` = 4: if
`gain` of `translation` exceeds `gain` of `affine`, the paper's codec sends a
translation per block. Otherwise it sends the affine map.

## 12. Cost

The director does not know the event rate of the dataset. Windows with several
hundred thousand events make the time outside the fits, which is mostly the
coding of events in the reference implementation, a large part of the cost.

**Projection.** As in directive 007, Section 15, with one block side: `c_20`
and `c_0` from the ten groups of Stage 0, the blocks at the smallest density
from the census.

**Spacing.** If the projection for Stage R exceeds 150 CPU-hours at `S` = 30,
use `S` = 60. If it still does, use `S` = 90. If it still does, stop after
Stage 0 and report the census, the times and the projection. The spacing is
chosen once and is not changed afterwards. Do not compete with a
companion-project job on `cnt`.

## 13. Files

SHA-256 of the file content, which is the text between the fence lines of its
appendix, ending in one newline.

| file | SHA-256 |
|---|---|
| `ec/dsec.py` | `8d6d5baad01e7da4607e3108684578c280d7fdc9b95c6eb0319d549340437fb6` |
| `tests/test_dsec_gate.py` | `d23276bc29229fbe79bb3fd986a4b3a1b47952fcf96b756bb74a04d93ef151c0` |

## 14. Acceptance checks

1. P1 to P4 pass.
2. `config/population_dsec.yaml` and `results/ds/population_check.json` were
   committed before the first event file was opened. The report gives the
   hashes.
3. Only the listed files were kept from the download, and each has its
   recorded SHA-256.
4. Every file was read by `ec.dsec.read_events` without an error, and the
   inventory is complete.
5. Every check of Stage 0 passes.
6. `claim_equals_match` and `q_equals_t` are true for every group,
   configuration and model.
7. For every stream of Stage R, the receiver's numbers equal those of
   `evaluate_group`, and the file length is 28 plus the sum of its records.
8. Every group of Section 7 is evaluated.
9. No file of eTraM was opened, and nothing was written under `results/bk/`.
10. The suite passes at the executed commit.

## 15. Outputs

| file | content |
|---|---|
| `config/population_dsec.yaml` | Stage D, step 1 |
| `results/ds/population_check.json` | Section 4 |
| `results/ds/preflight.json` | P1 to P4, the output of `describe`, the inventory |
| `results/ds/stage0.json`, `results/ds/census.json` | Stage 0 |
| `results/ds/per_recording.json` | for every sequence, the output of `sum_groups` |
| `results/ds/report.json` | every table of Section 10 |
| `results/ds/fig_bits.pdf`, `.png`, `.json` | the figure |
| `results/ds/provenance.json` | commit, host, versions, spacing, wall time, and the path, size and SHA-256 of every downloaded, stream and per-group file |

## 16. What comes next

The director writes Sections V and VI of the manuscript from reports 007 and
009, with the map that D-009-3 selects, and verifies the abstract against both.

## Appendix A. `ec/dsec.py`

Normative. The executor commits this file unchanged.

```python
"""Reader for the event files of DSEC (directive 009).

An event file of DSEC is an HDF5 file with the datasets ``/events/x`` (column), ``/events/y`` (row),
``/events/t`` (microseconds) and ``/events/p`` (polarity), and with ``/t_offset``, the offset in
microseconds between the stored times and the clock of the other sensors (documentation of the
dataset, https://dsec.ifi.uzh.ch/data-format/). The files are compressed with Blosc, so ``h5py``
needs the filter that the package ``hdf5plugin`` registers. The events are those of the sensor,
640 x 480, not rectified.

``read_events`` returns the stored times as they are, without the offset. It checks what the
project relies on and raises ``ValueError`` on anything else, so that a file that differs from the
documentation stops the run instead of being read wrongly. A decreasing time is clamped to its
predecessor, as the reader of the first dataset does, and counted.
"""
from __future__ import annotations

import numpy as np

WIDTH, HEIGHT = 640, 480
FIELDS = ("x", "y", "t", "p")


def describe(path) -> dict:
    """Names, shapes, types and filters of every dataset of the file, without reading the events."""
    import h5py
    try:
        import hdf5plugin  # noqa: F401  (registers the Blosc filter)
    except ImportError:
        pass
    out = {}
    with h5py.File(path, "r") as f:
        def visit(name, obj):
            if isinstance(obj, h5py.Dataset):
                out["/" + name] = {"shape": list(obj.shape), "dtype": str(obj.dtype), "compression": str(obj.compression),
                                   "filters": {str(k): str(v) for k, v in obj._filters.items()}}
        f.visititems(visit)
    return out


def read_events(path):
    """Events of one file: ``t_us`` (int64, nondecreasing), ``x``, ``y``, ``p`` (int64), and a dictionary of facts."""
    import h5py
    try:
        import hdf5plugin  # noqa: F401  (registers the Blosc filter)
    except ImportError:
        pass
    with h5py.File(path, "r") as f:
        if "events" not in f or any(k not in f["events"] for k in FIELDS):
            raise ValueError(f"{path}: /events/{{x, y, t, p}} not found")
        g = f["events"]
        dtypes = {k: str(g[k].dtype) for k in FIELDS}
        x, y, t, p = (np.asarray(g[k][:]).astype(np.int64) for k in FIELDS)
        t_offset = int(np.asarray(f["t_offset"][()]).reshape(-1)[0]) if "t_offset" in f else None
    n = len(t)
    if not (len(x) == len(y) == len(p) == n) or t.ndim != 1:
        raise ValueError(f"{path}: the four event datasets differ in length or are not one-dimensional")
    if n == 0:
        raise ValueError(f"{path}: no events")
    if x.min() < 0 or x.max() >= WIDTH or y.min() < 0 or y.max() >= HEIGHT:
        raise ValueError(f"{path}: coordinates outside {WIDTH} x {HEIGHT}: x {x.min()}..{x.max()}, y {y.min()}..{y.max()}")
    if not np.isin(np.unique(p), (0, 1)).all():
        raise ValueError(f"{path}: polarity values {np.unique(p).tolist()} are not a subset of (0, 1)")
    if t.min() < 0:
        raise ValueError(f"{path}: negative time")
    n_inv = int((np.diff(t) < 0).sum())
    if n_inv:
        t = np.maximum.accumulate(t)
    info = {"n_events": int(n), "t_first_us": int(t[0]), "t_last_us": int(t[-1]), "t_offset_us": t_offset,
            "n_time_inversions_clamped": n_inv, "dtypes": dtypes,
            "x_max": int(x.max()), "y_max": int(y.max()), "share_p1": float(p.mean())}
    return t, x, y, p, info
```

## Appendix B. `tests/test_dsec_gate.py`

Normative. The executor commits this file unchanged.

```python
"""Gate for directive 009: the reader of DSEC event files, on files written here in the documented layout."""
import h5py
import numpy as np
import pytest

from ec import blockcodec as bc, dsec


def _write(path, t, x, y, p, t_offset=1_000_000, dtypes=("uint16", "uint16", "uint32", "uint8")):
    with h5py.File(path, "w") as f:
        for k, v, dt in zip(("x", "y", "t", "p"), (x, y, t, p), dtypes):
            f.create_dataset(f"events/{k}", data=np.asarray(v).astype(dt), compression="gzip")
        if t_offset is not None:
            f.create_dataset("t_offset", data=np.int64(t_offset))
        f.create_dataset("ms_to_idx", data=np.arange(3, dtype=np.uint64))


def _events(n=5000, seed=0):
    rng = np.random.default_rng(seed)
    return (np.sort(rng.integers(0, 400_000, n)), rng.integers(0, dsec.WIDTH, n), rng.integers(0, dsec.HEIGHT, n),
            rng.integers(0, 2, n))


def test_a_file_in_the_documented_layout_is_read_as_it_is(tmp_path):
    t, x, y, p = _events()
    _write(tmp_path / "events.h5", t, x, y, p)
    rt, rx, ry, rp, info = dsec.read_events(tmp_path / "events.h5")
    assert all(a.dtype == np.int64 for a in (rt, rx, ry, rp))
    assert np.array_equal(rt, t) and np.array_equal(rx, x) and np.array_equal(ry, y) and np.array_equal(rp, p)
    assert info["n_events"] == 5000 and info["t_offset_us"] == 1_000_000 and info["n_time_inversions_clamped"] == 0
    assert info["t_first_us"] == t[0] and info["t_last_us"] == t[-1] and info["dtypes"]["t"] == "uint32"
    d = dsec.describe(tmp_path / "events.h5")
    assert d["/events/t"]["shape"] == [5000] and d["/events/x"]["dtype"] == "uint16" and "/t_offset" in d
    assert (dsec.WIDTH, dsec.HEIGHT) == (640, 480) and 640 % 20 == 0 and 480 % 20 == 0


def test_the_stored_times_are_returned_without_the_offset_and_a_missing_offset_is_reported(tmp_path):
    t, x, y, p = _events()
    _write(tmp_path / "a.h5", t, x, y, p, t_offset=None)
    rt, *_, info = dsec.read_events(tmp_path / "a.h5")
    assert info["t_offset_us"] is None and rt[0] == t[0]


def test_decreasing_times_are_clamped_and_counted(tmp_path):
    t, x, y, p = _events()
    t = t.copy()
    t[100], t[2000] = t[99] - 5, t[1999] - 1
    _write(tmp_path / "a.h5", t, x, y, p)
    rt, *_, info = dsec.read_events(tmp_path / "a.h5")
    assert info["n_time_inversions_clamped"] == 2 and (np.diff(rt) >= 0).all()
    assert rt[100] == t[99] and rt[2000] == t[1999]


def test_a_file_that_differs_from_the_documentation_stops_the_run(tmp_path):
    t, x, y, p = _events()
    with h5py.File(tmp_path / "no_events.h5", "w") as f:
        f.create_dataset("x", data=x)
    with pytest.raises(ValueError):
        dsec.read_events(tmp_path / "no_events.h5")
    bad = x.copy(); bad[3] = 640
    _write(tmp_path / "x.h5", t, bad, y, p)
    with pytest.raises(ValueError):
        dsec.read_events(tmp_path / "x.h5")
    bad = y.copy(); bad[3] = 480
    _write(tmp_path / "y.h5", t, x, bad, p)
    with pytest.raises(ValueError):
        dsec.read_events(tmp_path / "y.h5")
    _write(tmp_path / "p.h5", t, x, y, p * 2)
    with pytest.raises(ValueError):
        dsec.read_events(tmp_path / "p.h5")
    _write(tmp_path / "len.h5", t[:-1], x[:-1], y[:-1], p[:-1])
    with h5py.File(tmp_path / "len.h5", "a") as f:
        del f["events/p"]
        f.create_dataset("events/p", data=p.astype("uint8"))
    with pytest.raises(ValueError):
        dsec.read_events(tmp_path / "len.h5")


def test_the_codec_runs_on_the_sensor_of_the_second_dataset(tmp_path):
    # a dense moving bar on 640 x 480, read back through the reader and coded at the frozen configuration
    rng = np.random.default_rng(1)
    n = 60_000
    t = np.sort(rng.integers(0, 12 * bc.T0_US, n))
    x = (300 + 150e-6 * t + rng.integers(0, 40, n)).astype(np.int64) % dsec.WIDTH
    y = rng.integers(200, 240, n)
    p = rng.integers(0, 2, n)
    _write(tmp_path / "bar.h5", t, x, y, p)
    rt, rx, ry, rp, _ = dsec.read_events(tmp_path / "bar.h5")
    g = bc.evaluate_group(rt, rx, ry, rp, 0, 0, dsec.WIDTH, dsec.HEIGHT, blocks=(20,), densities=(1.0,),
                          models=("static", "translation"), records_for=(20, 1.0))
    row = g["codec"]["B20_rho1.0"]
    assert row["n_active"] > 0 and all(r["claim_equals_match"] and r["q_equals_t"] for r in row["models"].values())
    stream = bc.encode_header("Q", "translation", 4, dsec.WIDTH, dsec.HEIGHT, 20) + g["records"]["translation_Q_K4"]
    rec = bc.evaluate_stream(stream, rt, rx, ry, rp)[0]
    assert rec["match"] == [row["n_key"]] + row["models"]["translation"]["match_s2_k3"][:3]
    assert bc.decode_header(stream)["width"] == 640 and bc.decode_header(stream)["height"] == 480
```
