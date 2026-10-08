# event-coding

Information coding of event-camera streams: how many bits an event stream needs, and how much of
that a motion model can remove.

The working hypothesis is a sampling-theoretic one. Under rigid image-plane motion, neighboring
pixels observe delayed copies of the same signal, which is the delay case of Papoulis's generalized
sampling expansion. The events of a moving object are then redundant by about the number of pixels
each edge crosses, and the part that a decoder cannot predict is the timing jitter of each pixel,
new scene content, and noise. The project measures these three parts on real traffic recordings.

## Layout

| path | content |
|---|---|
| `docs/brief/` | phase 1 research brief (literature map, gap, problem statements, pilot) and its verified bibliography |
| `docs/directives/` | how experimental work is assigned and reported; one file per directive |
| `docs/DATA.md` | which recordings this project may read, and where they are |
| `docs/REFERENCE_LEDGER.md` | sources first used after the brief |
| `ec/` | code: baseline (`baseline.py`), code-length models (`coders.py`, `arith.py`), annotations, motion predictability (`motion.py`), synthetic fixture (`synth.py`) |
| `vendor/scene_bandwidth/` | verbatim, hash-pinned copies of the companion project's reader and U2 layout |
| `config/population.yaml` | the 112 development recordings |
| `tests/` | unit tests and the gate of directive 001 |
| `archive/pilot_2026-10-08/` | the pilot of the brief (scripts and raw outputs), frozen |
| `results/` | one directory per directive |

## Relation to `szh1456/scene-bandwidth`

That project studies uplink resource allocation for the same sensor and dataset. This project
shares its compute hosts, its copy of eTraM, and its transport baseline (U2 + zstd-1), and nothing
else. It never writes into that repository or its directories, and it never reads the recordings
that project holds out (see `docs/DATA.md`).

## Running the tests

```
python3 -m pytest -q
```

Needs numpy, scipy, zstandard, and numba (the coder tests skip without numba).
