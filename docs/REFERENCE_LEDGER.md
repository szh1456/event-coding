# Reference ledger

Sources used up to the phase 1 brief are listed, with their verification status,
at the end of `docs/brief/event_coding_brief.md` and in
`docs/brief/references.bib` (94 verified entries, 11 unverified items listed
separately). This ledger holds sources first used after the brief, in the format
of the companion project.

### `papoulis1977gse`

| field | value |
|---|---|
| claim supported | a bandlimited signal can be recovered from the outputs of M linear systems, each sampled at 1/M of the Nyquist rate; delayed copies and derivatives are special cases |
| source | A. Papoulis, "Generalized sampling expansion," IEEE Transactions on Circuits and Systems, vol. 24, no. 11, pp. 652-654, 1977, DOI 10.1109/TCS.1977.1084284 |
| source type | primary (journal article) |
| used in | `README.md`, directive 001 Section 1 (motivation only) |
| version / conditions | bibliographic record confirmed in Crossref on 2026-10-08; the article itself was not re-read |
| status | `PARTIAL`: citation verified, content stated from general knowledge |
| does not support | any statement about non-uniform, signal-dependent (level-crossing) sampling, about noise, or about bits |

### `brown1991wellposed`

| field | value |
|---|---|
| claim supported | the generalized sampling expansion can be ill-posed, so reconstruction error can grow with the number of channels |
| source | J. L. Brown, S. D. Cabrera, "On well-posedness of the Papoulis generalized sampling expansion," IEEE Transactions on Circuits and Systems, vol. 38, no. 5, pp. 554-556, 1991, DOI 10.1109/31.76494 |
| source type | primary (journal article) |
| used in | not yet used in a result; background for the limit on usable redundancy |
| version / conditions | bibliographic record seen in a Crossref query result on 2026-10-08 |
| status | `PARTIAL`: citation verified, content not read |
| does not support | any quantitative noise-amplification law |

### `papoulis1966error`

| field | value |
|---|---|
| claim supported | bounds on reconstruction error of bandlimited signals under sampling-time jitter |
| source | A. Papoulis, "Error analysis in sampling theory," Proceedings of the IEEE, 1966 |
| source type | primary (journal article) |
| used in | not used |
| version / conditions | cited from memory; the Crossref lookup was rate-limited |
| status | `UNRESOLVED`: volume, pages and DOI not confirmed |
| does not support | anything, until verified |

### `scene_bandwidth_baseline_code`

| field | value |
|---|---|
| claim supported | the transport baseline is canonical AER40 records, U2 layout (bit-packed 22-bit addresses, ULEB128 time deltas), zstd level 1, one payload per 50 ms tile |
| source | `szh1456/scene-bandwidth`, files `sim/workload.py`, `sim/representations.py`, `sim/etram.py`, `sim/scene_bandwidth/payload.py`, at the commit in `vendor/scene_bandwidth/SOURCE.json` |
| source type | primary (project code) |
| used in | `ec/baseline.py`, brief Section 7.7 |
| version / conditions | three modules vendored verbatim with SHA-256; `payload_bits` re-expressed in `ec/baseline.py` and tested against the vendored encoder |
| status | `VERIFIED` against the source files |
| does not support | the companion project's results, which are not reproduced here |

### `etram_eight_class_annotations`

| field | value |
|---|---|
| claim supported | 30 Hz boxes with a persistent `track_id` exist for all 112 train recordings; fields `t, x, y, w, h, class_id, track_id, class_confidence` |
| source | companion ledger `docs/REFERENCE_LEDGER_SBC.md`, entry of the same name, and its directive report 005 |
| source type | secondary (the companion project's record of the dataset authors' distribution) |
| used in | `ec/annotations.py`, directive 001 |
| version / conditions | eTraM 1.1, downloaded by the companion project on 2026-10-08 |
| status | `PARTIAL`: the box corner convention, the time origin and the class mapping are not documented there; directive 001 checks the first two on data |
| does not support | completeness of the labels, or the integer-to-name mapping of `class_id` |
