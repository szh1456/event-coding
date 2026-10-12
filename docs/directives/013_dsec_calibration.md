# Directive 013. DSEC calibrated on its own tuning subset

| | |
|---|---|
| track | `DSEC tuned`, short name `dt` |
| population | the 41 DSEC sequences of `config/population_dsec.yaml`, read as directive 009 read them. Nothing of eTraM is read |
| results directories | `results/dt/`, and `results/paper/` for Section 9 |
| report | `docs/directives/reports/013.md` |
| runs after | directive 012 |

## 1. Why

On eTraM the block side `B` and the threshold `rho` were tuned on 12
recordings and frozen before the other 100 were evaluated (directive 007,
Sections 6 and 8). On DSEC, directive 009 reused that frozen configuration
(20, 1) and evaluated all 41 sequences. The author decided that each dataset
is calibrated on itself, as a deployed codec would be, with the same
protocol on both: a tuning subset fixed by position in the sorted list, the
criterion `J` of directive 007, a freeze, and the tables over the other
sequences only.

The two datasets then follow one protocol. This directive authorizes runs on
DSEC after D-010-2 and overrides it for this purpose only.

## 2. Disclosure

Before this directive was written the director had read report 009. It knows
the gain of every density at `B` = 20 over all 41 sequences: `rho` = 1 is the
largest of the five there (Table 4 of report 009). No result at `B` = 40 or
80 exists for DSEC. The tuning subset below is fixed by position, as on eTraM,
and was not chosen from any result.

## 3. Author decisions

**D-013-1, default: as stated in Sections 4 and 6.** The subsets, the
criterion and the freeze.

**D-013-2, default: authorized.** If the frozen configuration is (20, 1), the
per-group files and the streams of Stage R of directive 009 for the reporting
sequences are the Stage R of this directive, after the check of Section 5,
P4. No group of a reporting sequence is evaluated again.

**D-013-3, default: the affine map.** D-009-3 settled the map of the paper's
codec (REMAKE). It is not decided again here, and Stage R reports the
translation next to it.

**D-013-4, default: authorized.** Section 9 regenerates Fig. 3, Fig. 4 and
the DSEC row of Fig. 5 from the tables of this directive. The eTraM parts of
the three figures stay as directive 012 left them.

## 4. Definitions

As directive 009, Section 7, with the spacing `S` = 60 that directive 009
chose, and these additions.

**Subsets.** Sort the 41 names. The *tuning subset* is the positions 0, 10,
20, 30 and 40 of the sorted list, five sequences: `interlaken_00_c`,
`zurich_city_01_c`, `zurich_city_04_a`, `zurich_city_08_a` and
`zurich_city_11_c`. The *reporting subset* is the other 36. Write both lists
into `results/dt/population_check.json` and commit it before Stage T
evaluates a group.

**Strata.** Over the reporting subset: `all`, and one stratum per location
with at least five entering sequences (`zurich_city_`, 31 sequences;
`interlaken_` keeps 4 and is reported only inside `all`).

**Host paths.** Everything this directive computes and keeps on the host goes
to `/data/<user>/event_coding/ds/dt/`, inside the directory that `docs/DATA.md`
assigns to what is computed from DSEC.

## 5. Stage P: preflight

A failed check is a `BLOCKED` report with the evidence.

**P1. Environment.** The versions equal those of `results/ds/provenance.json`.

**P2. Code.** `ec/blockcodec.py`, `ec/dsec.py` and their gates have the
SHA-256 of directives 007 and 009. `python3 -m pytest -q -p no:anyio` passes
with no skipped test.

**P3. Data.** The 41 event files have the size and the SHA-256 recorded in
`results/ds/provenance.json#/downloaded_files`.

**P4. Kept results of directive 009.** The per-group files and the stream
files of the reporting sequences have the size and the SHA-256 recorded in
`results/ds/provenance.json`. Needed only for D-013-2; if a file differs,
Stage R evaluates that sequence again and the report says so.

## 6. Stage T: tuning

**Run.** Every group of the five tuning sequences with
`evaluate_group(..., 640, 480)`, the default blocks (20, 40 and 80 px), the
five densities and the three models, `grid_for=None`, `records_for=None`.
Fifteen configurations `(B, rho)`.

**Criterion.** As directive 007, Section 8: for a sequence and a
configuration, with `s = summarize(sum, config, "affine", "Q", 4)`,

    J = (s["bits_base"] - s["bits"]) / s["bits_direct"].

`J(B, rho)` is the median over the five tuning sequences.

**Freeze.** The configuration `(B*, rho*)` with the largest `J`. On a tie,
the larger `B`, then the larger `rho`. Commit `results/dt/tuning.json`, with
`J` and the medians of `F`, `bits`, `bits_base` and `gain` for all fifteen
configurations and the frozen one, before Stage R evaluates or reads a group
of the reporting subset. Give the commit hash in the report. The frozen
configuration is not changed afterwards.

## 7. Stage R: the reporting subset

**If `(B*, rho*)` = (20, 1).** D-013-2. The sums of the reporting sequences
are those of `results/ds/per_recording.json`. Nothing is evaluated.

**Otherwise.** Every group of the 36 reporting sequences with `blocks=(B*,)`,
the five densities, the three models and `grid_for = records_for = (B*,
rho*)`. For every sequence, the eight complete streams of `affine` and the
eight of `translation`, each scored by `evaluate_stream` in a separate
process, as directive 009, Section 9. Record the size and the SHA-256 of every
stream and per-group file.

## 8. Tables

`results/dt/report.json` has the layout of `results/ds/report.json`, over the
reporting subset and the strata of Section 4, so that
`scripts/bk_figure.py` and `scripts/paper_figures.py` read it. Tables 1 to 12
of directive 009, Section 10, with these changes:

- **Table 4** is the density sweep at `B*`.
- **Table 9** is the census at `B*`, from the evaluated groups.
- **Table 11** is replaced by **Table T**: `J` and the medians of `F`,
  `bits`, `bits_base` and `gain` of the fifteen configurations on the tuning
  subset, as Table 1 of report 007.
- **Table 13, new.** Coder Q, `K` = 4 and 11, model `affine`: `F`, `bits`,
  `gain` and the share of events sent, for the frozen configuration over the
  reporting subset, next to the same rows of report 009 over all 41
  sequences, copied and marked as copied.

## 9. Figures

Keep the figures of directive 012: before writing anything under
`results/paper/`, copy every file of that directory as it is at the commit of
report 012, except `v011/`, to `results/paper/v012/`.

Then, for Fig. 5, select the DSEC group by the rule of directive 012,
Section 3, over the entering reporting sequences, with `(B*, rho*)` and the
stream `affine_Q_K11` of that configuration. The eTraM groups stay those of
directive 012. Then run

```
python3 scripts/paper_figures.py results/bk/report.json results/dt/report.json results/paper results/paper
```

## 10. Predictions

Written before any group at `B` = 40 or 80 was evaluated.

| quantity | predicted |
|---|---|
| `B*` | 20 or 40 |
| `rho*` | 1 |
| `J(B*, rho*) - J(20, 1)` on the tuning subset | below 0.03 |
| `gain` of `affine`, coder Q, `K` = 4, stratum `all` | 1.25 to 1.45 |
| `gain` of `affine`, coder Q, `K` = 11, stratum `all` | 2.4 to 3.2 |

There is no decision rule. The frozen configuration and its tables are the
DSEC result of the paper, whatever they show.

## 11. Cost

Stage T has 122 groups at three block sides. At `B` = 20 directive 009 spent
467 s per group on average, so that side costs about 16 CPU-hours; the other
two have fewer blocks. Stage R, if it runs, has about 1,190 groups at one
block side.

**Limits.** After the first ten groups of Stage T, project it from their
times. If the projection exceeds 80 CPU-hours, stop and report `BLOCKED` with
the times. After the freeze, if Stage R must run, project it from the Stage T
times at `B*`, scaled by the number of groups. If the projection exceeds 200
CPU-hours, stop with `tuning.json` committed and report `BLOCKED` with the
projection. A run that then costs more than projected is let finish, and both
numbers are reported. Read one sequence at a time, with the memory guard of
report 009, Section 6. Do not compete with a companion-project job on `cnt`.

## 12. Acceptance checks

1. P1 to P3 pass; P4 passes, or the report names the sequences that Stage R
   evaluated again.
2. `results/dt/population_check.json` was committed before Stage T evaluated
   a group, and `results/dt/tuning.json` before Stage R evaluated or read a
   group of the reporting subset. The report gives both hashes.
3. `claim_equals_match` and `q_equals_t` are true for every group,
   configuration and model of Stages T and R.
4. If Stage R ran: for every stream, the receiver's numbers equal those of
   `evaluate_group`, and the file length is 28 plus the sum of its records.
5. No sequence of the tuning subset enters a table of `results/dt/report.json`
   other than Table T, and none is selected for Fig. 5.
6. `results/paper/v012/` equals `results/paper/` at the commit of report 012.
   The eTraM entries of `fig_bits_all.json`, `fig_limits.json` and
   `recon_selection.json` equal those of directive 012.
7. No file of eTraM was opened. Nothing under `results/bk/` or `results/ds/`
   changed.
8. The suite passes at the executed commit.

## 13. Outputs

| file | content |
|---|---|
| `results/dt/population_check.json` | the two subsets |
| `results/dt/preflight.json` | P1 to P4 |
| `results/dt/tuning.json` | Section 6 |
| `results/dt/per_recording.json` | the sums of every tuning sequence for the fifteen configurations, and of every reporting sequence for the frozen one |
| `results/dt/report.json` | every table of Section 8 |
| `results/dt/fig_bits.pdf`, `.png`, `.json` | `python3 scripts/bk_figure.py results/dt/report.json results/dt/fig_bits.pdf all` |
| `results/dt/provenance.json` | commit, host, versions, wall time, CPU time, and the path, size and SHA-256 of every per-group and stream file used |
| `results/paper/` | Section 9, with `v012/` |

## 14. What comes next

The director writes the DSEC protocol of Section VI-A as calibration on a
disjoint tuning subset, takes the DSEC rows of Table I and the figures from
this directive, and sends the rebuilt manuscript to the author.
