# Pilot of the phase 1 brief (frozen)

Scripts and raw outputs behind Section 7 of `docs/brief/event_coding_brief.md`,
as run on October 8, 2026 on three public sample recordings. Kept for the record.
Not maintained and not imported by `ec/`.

- `run_pilot.py`, `coders.py`, `io_events.py`, `posthoc.py`, `roundtrip_check.py`: Sections 7.1 to 7.6.
  `coders.py` here still contains the U2 layout that was assumed before the companion code was read.
- `real_u2.py`: Section 7.7, the companion project's actual U2 + zstd-1.
- `out/`: JSON outputs and round-trip logs.
- `event_coding_brief_prepilot_*.md`: the brief as it stood before any event file was opened.
- `make_refs.py`: generator of the bibliography and the reference list.

The eTraM excerpt used here is 5 s of `val_night_011`, a held-out recording of
the companion project. See `docs/DATA.md`.
