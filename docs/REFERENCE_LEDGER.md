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
| used in | `README.md`, directive 001 Section 1 (motivation only), `docs/theory/translation_edge.tex` (remark on the relation to sampling theory, analogy only), `papers/tsp/main.tex` (introduction, as a recalled analogy) |
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

### `adam2020multichannel`

| field | value |
|---|---|
| claim supported | if single-channel time encoding can sample and perfectly reconstruct a 2Ω-bandlimited signal, M-channel time encoding with shifted integrators can do so for a signal with M times the bandwidth, without knowledge of the shifts (noiseless case) |
| source | K. Adam, A. Scholefield, M. Vetterli, "Sampling and reconstruction of bandlimited signals with multi-channel time encoding," IEEE Transactions on Signal Processing, vol. 68, pp. 1105-1119, 2020, DOI 10.1109/TSP.2020.2967182, arXiv:1907.05673 |
| source type | primary (journal article) |
| used in | `docs/theory/translation_edge.tex`, remark on the relation to sampling theory (analogy only: M pixels with different threshold phases against M integrate-and-fire channels with shifted integrators); `papers/tsp/main.tex`, introduction (the shifts make the channels complementary) |
| version / conditions | title, authors and abstract read on the arXiv record on 2026-10-09; journal volume, pages and DOI from a metadata check on 2026-10-08, not re-read today |
| status | `PARTIAL`: abstract read, body not read |
| does not support | any statement about send-on-delta (level-crossing) pixels, about noise or jitter, or about bits; the note's "typical spacing of order C/M" is the note's own statement |

### `cover2006elements`

| field | value |
|---|---|
| claim supported | textbook facts used in the proofs: the entropy of a uniformly quantized variable against its differential entropy; the Gaussian maximizes differential entropy at a given variance; the entropy power inequality; the Shannon lower bound; a normal input maximizes the mutual information across an additive normal noise channel at a given input variance |
| source | T. M. Cover, J. A. Thomas, "Elements of Information Theory," 2nd ed., John Wiley & Sons, 2006, ISBN 978-0-471-24195-9 |
| source type | secondary (textbook), used for standard results only |
| used in | `docs/theory/translation_edge.tex`, `papers/tsp/main.tex` (Sections II to IV and Appendices B and C) |
| version / conditions | title, authors, edition, publisher, publication date (September 2006) and ISBN read on the publisher's page (https://www.wiley-vch.de/de/fachgebiete/computer-und-informatik/elements-of-information-theory-978-0-471-24195-9) on 2026-10-09. Its table of contents confirms Chapter 8 (Differential Entropy), Chapter 10 (Rate Distortion Theory) and Chapter 17 (Inequalities in Information Theory). Theorem and problem numbers inside the chapters were not checked against the book |
| status | `PARTIAL`: bibliographic metadata and chapter titles verified, the book itself not opened. The mathematical statements were re-derived or checked numerically (`docs/theory/check_translation_edge.py`, `papers/tsp/checks/check_affine_passage.py`) and by independent reviews |
| does not support | anything specific to event sensors; a chapter number for the Gaussian channel, which the manuscript therefore cites without one |

### `kozachenko1987entropy`

| field | value |
|---|---|
| claim supported | a nearest-neighbor estimate of the differential entropy of a random vector from samples |
| source | L. F. Kozachenko, N. N. Leonenko, "Sample estimate of the entropy of a random vector," Problemy Peredachi Informatsii, vol. 23, no. 2, pp. 9-16, 1987; English translation in Problems of Information Transmission, vol. 23, no. 2, pp. 95-101 |
| source type | primary (journal article) |
| used in | `docs/theory/check_translation_edge.py`, function `kl_entropy` (check N2) |
| version / conditions | bibliographic record read on mathnet.ru (https://www.mathnet.ru/eng/ppi797) on 2026-10-09; the article was not read |
| status | `PARTIAL`: citation verified, content not read. The script uses the k-th neighbor form with k = 4 and a digamma correction, which is a later generalization whose source is not recorded here |
| does not support | the accuracy of the estimate at finite sample size; check N2 is a consistency check against the closed form, not a proof |

### `uniform_quantizer_high_resolution_loss`

| field | value |
|---|---|
| claim supported | an entropy-coded uniform scalar quantizer at fine resolution spends (1/2) log2(2πe/12) = 0.255 bit per sample more than the Shannon lower bound under squared error |
| source | standard high-resolution quantization result, commonly attributed to Gish and Pierce (1968); no source was opened |
| source type | not established |
| used in | `docs/theory/translation_edge.tex`, numerical check N3 (one comparison sentence) |
| version / conditions | none |
| status | `UNRESOLVED`: no primary source read. The value follows from the entropy of a uniform quantizer index, ln(1/Δ) plus the differential entropy, at distortion Δ²/12 |
| does not support | any claim at coarse resolution, where the measured excess in N3 is larger |
