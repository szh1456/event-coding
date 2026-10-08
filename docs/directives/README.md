# Directives

How work is handed from the director to the executor in this repository, and how
results come back. The scheme is the one used in `szh1456/scene-bandwidth`.

## Roles

| role | who | owns |
|---|---|---|
| Author | Zihang | every scientific decision; authorizes by merging |
| Director | the Claude session that writes directives and, later, the manuscript | `docs/directives/*.md`, `docs/brief/`, `papers/` |
| Executor | the coding agent with access to the compute hosts | `ec/`, `scripts/`, `tests/`, `config/`, `results/`, `docs/directives/reports/` |

Each side writes only inside its own paths. If a task seems to need a file on the
other side, say so in a report or a directive and let the owner change it.

One exception is declared here. The director seeded `ec/`, `tests/` and `config/`
in the first commit, including a reference implementation of the measurement of
directive 001 and its gate. From then on they belong to the executor, with one
restriction: a test file that a directive names as a gate is changed only by an
amendment to that directive.

## Life cycle of a directive

1. The director opens a pull request that adds `docs/directives/NNN_<slug>.md`.
   At this point the directive is a proposal and nothing may be run from it.
2. The author merges the pull request. A directive is authorized if and only if
   it is on `main`. Open author decisions listed in the directive are settled by
   the merge: each one states a default, and merging accepts the defaults unless
   the author edited them first.
3. The executor pulls `main`, executes every open directive, lowest number first,
   and pushes code, results and a report to `main`. A directive is open when it
   has no report, or when its report is `BLOCKED` and the directive has gained an
   amendment since that report was written.
4. The director reads the report. A `DONE` report leads to the next directive. A
   `BLOCKED` report is answered by an amendment: a numbered section appended to
   the same directive file, merged like any other change. An amendment overrides
   the text it names and nothing else.

## What the executor does with a directive

- Execute exactly what the directive specifies. Its grids, populations, metrics
  and rules are fixed before any number is seen, so do not add, drop or tune any
  of them after a run has started.
- Choose the implementation freely where the directive is silent: module layout,
  parallelism, host and scheduling are yours.
- Stop and report `BLOCKED` when the directive is ambiguous, when it conflicts
  with `CLAUDE.md` or `docs/DATA.md`, when an acceptance check fails for a reason
  you cannot explain, or when a step would need a recording outside the
  population the directive names. Do not improvise around any of these. A blocked
  report with a precise question is a good outcome.
- Each directive names the `results/` directory it writes to. Write nowhere else
  under `results/`.
- The data rules of `docs/DATA.md`, the compute rules of `CLAUDE.md` and the
  reference ledger rule apply to every directive.

## The report

One file per directive, `docs/directives/reports/NNN.md`, beginning with:

```
directive: NNN
status: DONE | BLOCKED
executed_commit: <sha of the code that produced the results>
results: <paths>
```

followed by:

1. what ran, on which host, and the wall time;
2. each acceptance check from the directive, with its outcome;
3. the result tables the directive asks for, each value traceable to a committed
   JSON file and pointer;
4. deviations and incidents, including anything rerun and why;
5. questions for the director or the author.
