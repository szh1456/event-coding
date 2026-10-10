# CLAUDE.md

## Directives

Experimental work is assigned through `docs/directives/`. Read
`docs/directives/README.md` first. On each sync, execute every open directive on
`main`, lowest number first, and push code, results and the report back to
`main`. A directive is open when it has no report in
`docs/directives/reports/`, or when its report is `BLOCKED` and the directive has
been amended since. Run nothing that no directive authorizes, and do not edit the
directive files, `docs/brief/`, `archive/` or `vendor/`.

## Data

Read `docs/DATA.md` before opening any recording. In short: this project reads
the 112 eTraM Static train recordings listed in `config/population.yaml` and
their annotations, read-only, and nothing else. The eTraM val and test
recordings belong to the held-out and sealed sets of `szh1456/scene-bandwidth`.
Never open, hash, count or copy them from this project, on any host.

Never write inside a directory of the companion project (`~/prjs/sbu_full_staging`,
`~/prjs/sbc_run`, `~/prjs/adaptive_comm_comp_event`, or its repository checkout).
This project's files on a compute host live under `~/prjs/event_coding/`. The
files of the second dataset, and what is computed from them, live under
`/data/<user>/event_coding/` on `cnt`, as `docs/DATA.md` states.

## Cluster

Compute resources and remote-run discipline live in
`~/.claude/compute-resources.md`. Read it before any work that is not seconds of
laptop time. Never run data-heavy or compute-heavy work on the laptop. Datasets
live on the remote machine and every run that uses them runs there. A laptop run
is a pipeline test, never a reference.

## References

Whenever an external source is used, or a source-backed value is frozen, update
`docs/REFERENCE_LEDGER.md` in the same commit. Record the exact claim it
supports, the citation or URL, the source type, where the project uses it, the
version or conditions, the verification status, and what stronger claim it does
not support. Never invent missing metadata, and never use a secondary source
where a primary one exists. An unverifiable entry stays `UNRESOLVED` with the gap
stated. Sources already listed in `docs/brief/event_coding_brief.md` keep the
status given there.

## Vendored baseline

`vendor/scene_bandwidth/` holds verbatim copies of four modules of the companion
project, pinned by `SOURCE.json` and checked by `tests/test_vendor_pinned.py`.
Do not edit them. To move to a newer companion commit, replace the files and
`SOURCE.json` together in one commit that a directive authorizes.
