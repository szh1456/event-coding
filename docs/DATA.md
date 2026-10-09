# Data

## Population

The 112 official eTraM Static **train** recordings, listed in
`config/population.yaml` (61 day, 51 night). The list is copied from
`config/split.yaml` (key `calibration`) of `szh1456/scene-bandwidth` at the commit
recorded in that file's header. A directive may name a subset. No directive may
name a recording outside this list.

## What is off limits, and why

| set | recordings | status in the companion project | rule here |
|---|---|---|---|
| eTraM Static val | 25 (`val_day_*`, `val_night_*`) | held-out, gated | never opened |
| eTraM Static test | the remaining Static recordings | sealed, to be read once by its directive 006 | never opened |

The companion project's confirmatory claims rest on those recordings having been
read only under its own protocol. A second project that reads them, even for an
unrelated quantity, weakens that. The execution host `cnt` holds the train
recordings only, so running there keeps this rule by construction.

One exposure exists and is recorded here. The pilot of the brief used a 5 s
excerpt of `val_night_011` taken from a public third-party sample repository,
before the companion repository had been read. No pilot output entered the
companion project. The excerpt is not used again.

## Locations (from the companion project's reports and ledger; verify in the preflight)

| item | host | path | source of this statement |
|---|---|---|---|
| events, 112 train recordings, HDF5 `/events/{x,y,p,t}`, `t` in microseconds | `cnt` | `~/prjs/sbu_full_staging/data` | companion directive report 004 |
| events, same | `cnt` | `~/prjs/adaptive_comm_comp_event/data/etram/h5` | companion `archive/SCENE_BANDWIDTH_SB1.md` |
| eight-class annotations, `*_bbox.npy` | `cnt` | `~/prjs/sbc_run/etram_annotations/` | companion `docs/REFERENCE_LEDGER_SBC.md`, entry `etram_eight_class_annotations` |
| the same, train files only | `cnt` | `~/prjs/sbc_run/etram_annotations/train/eight_class_annotations_train/` | directive report 001, Section 4, item 1 |

The annotation root also holds the val files (`val/`), the test files
(`test_count/`, downloaded there once to count boxes) and `zips/`. Build each
annotation path from the train subdirectory above and a recording identifier of
`config/population.yaml`. Do not list any directory under the annotation root.

Both data directories are read-only for this project. Do not copy the corpus. If
a derived cache is needed, write it under `~/prjs/event_coding/cache/` on the
same host.

## Reading

Use `ec.baseline.read_events` (the companion reader, vendored). It folds polarity
to `{0, 1}`, clamps decreasing timestamps to their predecessor, and clears a
flipped bit 15 in two known coordinates. It returns the counts of both repairs.
Report nonzero counts. Only HDF5 is available on the hosts. The RAW (EVT) files
were not kept.
