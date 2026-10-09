# Directive 005. Where the fidelity is lost: counts against placement, time against distance

| | |
|---|---|
| track | `diagnosis`, short name `dg` |
| population | the rows of directives 003 and 004. No recording and no annotation is opened |
| results directory | `results/dg/` |
| report | `docs/directives/reports/005.md` |
| runs after | directive 004 (`DONE`, report at `963bcc9`) |

## 1. Why

**What directives 003 and 004 found.** Rule D-004-4 keeps the translation as the
codec's motion model and gives GO for the codec. The affine map helps, and less
than on the synthetic object: `gamma` at `K` = 11 rises from 4.16 to 5.01 by day
and from 4.47 to 4.98 by night. It removes 0.40 of the fall of the fidelity with
the lead by day and 0.33 by night. In stratum H at the headline cell, `F1` under the affine map
still falls from 0.68 (day) and 0.69 (night) at the first target to 0.51 and
0.53 at the tenth.

Two facts narrow the cause. The fall is the same at the frame cell (0.78 to 0.62
by day), which has one time bin, so it is not a timing error inside the window.
And the fidelity of a group of 11 windows is nearly the same in every speed bin
of vehicles above 20 px/s (0.54 to 0.59 in directive 003), although the distance
covered differs by more than ten times.

**What this directive measures.** Three decompositions of the loss, from the rows
that already exist. No event is read.

1. *Counts against placement.* A regenerated window can differ from the true one
   in how many events it holds and in where they are. The count ceiling is the
   `F1` that a perfect placement would reach with the given counts.
2. *Growth.* An object that grows by a factor `s` has edges `s` times longer that
   move `s` times faster, so its event rate grows as `s^2`. Moved key events keep
   their number. The ratio of the true count to the key count should follow the
   growth of the label box area.
3. *Time against distance.* Whether the loss follows the lead or the
   displacement.

The answers decide what the next codec changes: the number of regenerated events,
the regions, or the group length.

## 2. Disclosure

Before this directive was written the director had read reports 001 to 004 and
the committed aggregates of all four. The per-row files are on the host and were
not seen.

## 3. Author decisions

**D-005-1, default: authorized.** The per-row files of Stage C of directive 003
and of Stage A of directive 004 on `cnt` are read. Nothing else is read.

**D-005-2, default: accepted.** The outcome of D-004-4 stands as measured. The
paper reports the affine map by lighting and by speed bin, with the translation
next to it, and makes no claim for the affine map beyond those numbers on this
population.

## 4. Isolation

No event file and no annotation file is opened, listed or hashed.
`results/dg/population_check.json` states this and lists the per-row files read,
with their SHA-256 from the two provenance files. Write only under
`~/prjs/event_coding/` on the host and `results/dg/` in the repository.

## 5. Definitions

For a scored row (instant and target `m`), a model in {`aligned`, `affine`} and a
cell in {headline (2 px, `k` = 3), frame (2 px, `k` = 1)}, with `n_pred` of that
model, `n_true = n_future` and `F1` of that model and cell:

```
match      = F1 (n_pred + n_true) / 2
precision  = match / n_pred
recall     = match / n_true
ceiling    = 2 min(n_pred, n_true) / (n_pred + n_true)
placement  = match / min(n_pred, n_true)            so that F1 = ceiling x placement
rho        = n_true / n_source
```

`rho` uses the key count before any event leaves the support. For the instant,
`growth` is the label box area ratio of directive 004, Section 6, as a number.
`disp` is the length in px of `(aligned_dx, aligned_dy)` of the row.

A row with `n_pred` = 0 has `match` = 0 and no `placement`. Count such rows.

## 6. Tables for the report

Stratum H unless stated, by lighting. Aggregation is that of directive 001,
Section 6, with bootstrap seed 20261012, and the row as the instance.

1. **Counts against placement, by target.** For `m` = 1 to 10 and both models, at
   the headline cell: `F1`, `ceiling`, `placement`, `precision`, `recall`. The same
   at the frame cell for `m` = 1, 4 and 10.
2. **Counts.** For `m` = 1, 4 and 10: the 10%, 50% and 90% quantiles of `rho` over
   the pooled rows, and of `n_pred / n_true` for both models.
3. **Growth.** For `m` = 10, rows binned by `growth` in [0, 0.8), [0.8, 0.9),
   [0.9, 1.1), [1.1, 1.25), [1.25, inf): the number of rows, the median `growth`,
   the median `rho`, and the median `ceiling` and `placement` of both models at the
   headline cell.
4. **Time against distance.** At the headline cell, for both models, `F1` and
   `placement`:
   (a) at `m` = 4 and at `m` = 10, rows binned by `disp` in [0, 2), [2, 5), [5, 10),
   [10, 20), [20, 40), [40, inf) px;
   (b) for rows with `disp` in [5, 10) px, by `m` = 1 to 10, with the number of rows
   in each.
   Use all isolated vehicle instants here, not only stratum H, so that slow
   objects reach the long leads.
5. **Key size.** At `m` = 1 and `m` = 10, rows binned by `n_source` in [50, 200),
   [200, 1000), [1000, 5000), [5000, inf): `ceiling` and `placement` of `aligned`
   at the headline cell.

## 7. Predictions

Written by the director before any of these numbers existed. Stratum H, headline
cell, the same range by day and by night. There is no decision rule: this
directive informs the design of the next codec and decides nothing by itself.

| quantity | predicted |
|---|---|
| `ceiling`, `aligned`, `m` = 1 | 0.90 to 0.97 |
| `ceiling`, `aligned`, `m` = 10 | 0.80 to 0.92 |
| `placement`, `affine`, `m` = 1 | 0.70 to 0.78 |
| `placement`, `affine`, `m` = 10 | 0.52 to 0.66 |
| share of the fall of `F1(affine)` from `m` = 1 to 10 that the fall of `ceiling` accounts for | under one third |
| median `rho` at `m` = 10 in the `growth` bins | under 0.9 in [0, 0.8), above 1.15 in [1.25, inf) |
| Table 4(a), `placement` of `affine` at `m` = 10 | varies by under 0.10 across the `disp` bins from 2 to 40 px |
| Table 4(b), `placement` of `affine` | falls by more than 0.10 from `m` = 1 to `m` = 10 |

The last two rows state that the loss follows the lead more than the distance.
If they fail, the loss follows the distance, and the cause is to be sought in
what the object passes over.

## 8. Acceptance checks

1. Every scored row of directive 003 appears once, with the `affine` row of
   directive 004 joined to it by recording, track, instant and target. Report the
   number of rows, which must equal that of directive 004.
2. For every row, model and cell, `ceiling x placement` equals `F1` to 1e-12, and
   `precision`, `recall`, `ceiling` and `placement` lie in [0, 1].
3. The medians of `F1` in Table 1 equal those of Table 2 of reports 003 and 004
   to the printed digits.
4. `results/dg/population_check.json` exists and names no event or annotation
   file.

## 9. Outputs

| file | content |
|---|---|
| `results/dg/population_check.json` | Section 4 |
| `results/dg/report.json` | every table of Section 6 |
| `results/dg/provenance.json` | commit, host, versions, wall time |

## 10. Cost

A join and a reduction over 656,260 rows: minutes on one core. Run it on `cnt`,
where the files are.

## 11. Answers to the questions of report 004

1. **Per lighting.** Yes. D-005-2 fixes it: the paper reports the affine map by
   lighting and by speed bin. The rule is not read again per lighting.
2. **Where the affine map pays.** Noted. Its cost is negligible, so the question
   is one of the rule and of what the paper claims, and D-005-2 answers it.
3. **Subset.** Noted: the two stretch parameters carry most of it. No directive
   follows from this before the next codec is specified.
