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
| used in | `docs/theory/translation_edge.tex`, numerical check N3 (one comparison sentence); `papers/tsp/main.tex`, Section VI-B, where the value is stated with its derivation and without a citation, next to the measured excess of 0.254 to 0.258 bit per event (report 006, Table 4) |
| version / conditions | none |
| status | `UNRESOLVED`: no primary source read. The value follows from the entropy of a uniform quantizer index, ln(1/Δ) plus the differential entropy, at distortion Δ²/12 |
| does not support | any claim at coarse resolution, where the measured excess in N3 is larger |

### `blahut1972computation`

| field | value |
|---|---|
| claim supported | the rate-distortion function of a discrete source can be computed, at a given slope, by an alternating iteration on the output distribution |
| source | R. E. Blahut, "Computation of channel capacity and rate-distortion functions," IEEE Transactions on Information Theory, vol. 18, no. 4, pp. 460-473, July 1972 |
| source type | primary (journal article) |
| used in | `ec/regimes.py`, function `blahut_arimoto` (directive 006, check R1); `papers/tsp/main.tex`, Section VI-B (the numerical rate-distortion function of Fig. 2) |
| version / conditions | title, author, journal and month read on the IEEE Information Theory Society page of the paper (https://itsoc.org/node/36671) on 2026-10-10; volume, issue and pages read on the author's dblp record (https://dblp1.uni-trier.de/pid/89/3073.html) on the same day. No DOI was confirmed, so none is given. The article was not read |
| status | `PARTIAL`: citation verified, content stated from general knowledge. The iteration in the code was written from that knowledge and is checked against a Gaussian source in `tests/test_regimes_gate.py` |
| does not support | a convergence rate, a stopping rule, or any statement about a continuous source: the code discretizes the source and repeats the computation on a second grid |

### `rate_distortion_dual_lower_bound`

| field | value |
|---|---|
| claim supported | for a discrete source `p`, a distortion `d`, a slope `beta` > 0 and any output distribution `q`, with `Z(x) = sum_y q(y) exp(-beta d(x, y))` and `c(y) = sum_x p(x) exp(-beta d(x, y)) / Z(x)`: `R(D) >= -beta D - sum_x p(x) ln Z(x) - ln max_y c(y)` for every `D` |
| source | standard lower bound of rate-distortion theory, used as the lower end of the bracket of a Blahut-Arimoto iteration; no source was opened |
| source type | not established |
| used in | `ec/regimes.py`, function `blahut_arimoto` (`R_lower`) |
| version / conditions | none |
| status | `UNRESOLVED`: no primary source read, and no theorem number is given. The statement follows from the variational bound `R(D) >= -beta D + sum_x p(x) ln lambda(x)` for any `lambda >= 0` with `sum_x p(x) lambda(x) exp(-beta d(x, y)) <= 1` for all `y`, applied to `lambda(x) = 1 / (Z(x) max_y c(y))`; that variational bound is itself stated from general knowledge. An independent review of `ec/regimes.py` on 2026-10-10 found the bracket correct |
| does not support | the rate-distortion function of the continuous source; the bound is for the discretized source with reproduction points on the same grid |

### `plug_in_entropy_bias`

| field | value |
|---|---|
| claim supported | the plug-in entropy estimate from `N` samples over `m` occupied cells is biased downward by about `(m - 1) / (2 N)` nats, and adding that term removes the bias to first order |
| source | standard result, commonly attributed to G. A. Miller (1955) and known as the Miller-Madow correction; no source was opened |
| source type | not established |
| used in | `ec/regimes.py`, function `coder_simulated` (check R3) |
| version / conditions | none |
| status | `UNRESOLVED`: no primary source read, bibliographic data not confirmed. In check R3 the correction is at most 3.7e-3 nat (14,883 cells, 2,000,000 samples), below the tolerance of 5e-3 nat, and the corrected estimate is compared with a value computed from the density |
| does not support | accuracy when many cells hold few samples |

### `dsec_dataset_and_format`

| field | value |
|---|---|
| claim supported | DSEC was recorded from a car with two event cameras of 640 x 480 pixels and holds 53 sequences. An event file is an HDF5 file with `/events/{p, t, x, y}` (polarity, time in microseconds, column, row) and `/t_offset`, the offset in microseconds to add to the stored times; the files are compressed with Blosc and the ZSTD codec; the events are not rectified |
| source | M. Gehrig, W. Aarents, D. Gehrig, D. Scaramuzza, "DSEC: A Stereo Event Camera Dataset for Driving Scenarios," IEEE Robotics and Automation Letters, vol. 6, no. 3, pp. 4947-4954, 2021, DOI 10.1109/LRA.2021.3068942 (`gehrig2021dsec` of the brief); and the dataset's documentation, "DSEC Data Format," https://dsec.ifi.uzh.ch/data-format/ (`dsec_format` of the brief) |
| source type | primary (journal article and the dataset's own documentation) |
| used in | directive 009; `ec/dsec.py`; `docs/DATA.md` |
| version / conditions | the two sources keep the status of the brief (verified there on 2026-10-08). The format page was read again on 2026-10-10, and the project page (https://dsec.ifi.uzh.ch/) on the same day: "53 sequences", "VGA-resolution event cameras" |
| status | `VERIFIED` for the training split, left camera, as read by directive 009, Stage D, on 2026-10-10: (1) the download page (https://dsec.ifi.uzh.ch/dsec-datasets/download/, saved page SHA-256 `b71c29ed9b2aa265220f2f29404e49273260539907060d022fd9c01410514573`) separates the training split and offers the left event camera of each training sequence by itself (`<seq>_events_left.zip`); 41 training sequences do, 69,344,223,481 bytes together, listed in `config/population_dsec.yaml`; each archive holds `events.h5` and `rectify_map.h5`; (2) in all 41 files `/events/x` and `/events/y` are `uint16`, `/events/t` `uint32`, `/events/p` `uint8` with values 0 and 1; the datasets carry the Blosc filter 32001 with codec ZSTD, which `h5py` 3.16.0 reads only with `hdf5plugin` (7.1.0); the stored times start at 0 or 1 us; `/t_offset` is present; (3) the download page carries no license statement (checked on the saved page above); the project page (https://dsec.ifi.uzh.ch/, read 2026-10-10, saved page SHA-256 `2dfa3e83ba338afb751f0c5646e5c35cd5f6ae59f063db62889d28fdb24a4f98`) states: "This dataset is provided to you under the Creative Commons Attribution-ShareAlike 4.0 International public license (CC BY-SA 4.0)", and links https://creativecommons.org/licenses/by-sa/4.0/legalcode. The count of 53 sequences (journal article, project page) covers both splits and was not checked against the test split, which is not read |
| does not support | which sequences are recorded at night; any property of the sensor settings; the test split. Event rates and durations of the training sequences are measured in `results/ds/preflight.json`, not stated by the sources |

### `rfc8878`

| field | value |
|---|---|
| claim supported | Zstandard is a published, general-purpose lossless compression format |
| source | Y. Collet, M. Kucherawy (Ed.), "Zstandard Compression and the 'application/zstd' Media Type," RFC 8878, February 2021, DOI 10.17487/RFC8878 |
| source type | primary (specification) |
| used in | `papers/tsp/main.tex`, Section V-C, as the reference for the compressor of both event coders and of the map payload (`ec/baseline.py`, `ec/blockcodec.py`, through the package `zstandard`) |
| version / conditions | number, title, authors, date, category (Informational) and DOI read on https://www.rfc-editor.org/rfc/rfc8878 on 2026-10-11. The text of the RFC was not read. The runs used `zstandard` 0.25.0 (reports 007 and 009) |
| status | `PARTIAL`: citation verified, content not read |
| does not support | any compression ratio or speed; that the levels 1 and 19 of the package are defined by the RFC |


### `stumpp2024`

| field | value |
|---|---|
| claim supported | The flow-based coder FBC alternates a sending state, in which every event is sent with its flow when the flow is confident, and a predicting state, in which only events without a confident flow are sent; the receiver extrapolates each flow event along a straight line and keeps pixels within a slack of 0.4 px; ST is the time in which the mean speed of the first 500 flow events moves one pixel; flows are two 12-bit values; no residual is sent |
| source | D. C. Stumpp, H. Akolkar, A. D. George, R. B. Benosman, "Flow-Based Visual Stream Compression for Event Cameras," IEEE Internet of Things Journal, vol. 11, no. 24, pp. 40229-40243, 2024, DOI 10.1109/JIOT.2024.3450428; arXiv:2403.08086 |
| source type | primary (journal article; arXiv version read) |
| used in | `ec/fbc.py` (directive 016), the motion-predictive baseline of the manuscript, Section VI |
| version / conditions | the brief's entry (status V, Crossref and arXiv v1 full text); the arXiv abstract page and its summary read on 2026-10-12 for the algorithmic details above |
| status | `PARTIAL`: citation verified (brief); algorithm details taken from the arXiv version, not from the journal version |
| does not support | that `ec/fbc.py` reproduces the authors' implementation or numbers; its flow is a plane fit, not ARMS |

### `benosman2014`

| field | value |
|---|---|
| claim supported | Visual flow can be estimated from an event stream by fitting a plane, per incoming event, to the times of the events in a local spatio-temporal neighborhood; the slopes of the plane give the velocity |
| source | R. Benosman, C. Clercq, X. Lagorce, S.-H. Ieng, C. Bartolozzi, "Event-Based Visual Flow," IEEE Transactions on Neural Networks and Learning Systems, vol. 25, no. 2, pp. 407-417, 2014, DOI 10.1109/TNNLS.2013.2273537 |
| source type | primary (journal article) |
| used in | `ec/fbc.py`, function `plane_flow` (directive 016) |
| version / conditions | metadata from the Crossref record, read on 2026-10-12. The plane-fitting statements from a copy of the paper hosted on academia.edu (record 14427547), read on 2026-10-12; the publisher's version was not read |
| status | `PARTIAL`: citation verified; method statements from a non-publisher copy |
| does not support | the robust iterative variant, its thresholds or its accuracy; `plane_flow` fits once on the latest event time per pixel and polarity |

### `gallego2018cmax`

| field | value |
|---|---|
| claim supported | Motion parameters of events can be estimated by warping the events along candidate motion and maximizing the contrast (variance) of the image of warped events |
| source | G. Gallego, H. Rebecq, D. Scaramuzza, "A Unifying Contrast Maximization Framework for Event Cameras, With Applications to Motion, Depth, and Optical Flow Estimation," Proc. IEEE/CVF CVPR, pp. 3867-3876, 2018 |
| source type | primary (conference paper) |
| used in | `ec/downstream.py`, function `cmax_velocity` (directive 016), the motion task of the manuscript, Section VI |
| version / conditions | status as in the brief (V, CVF open-access abstract page; no DOI on that page) |
| status | `PARTIAL`: citation verified (brief); the full text was not read for this use |
| does not support | the grid search, the step sizes or the event cap of `cmax_velocity`, which are this project's choices |

### `dinkelbach1967`

| field | value |
|---|---|
| claim supported | A ratio objective N(x)/D(x) with D > 0 is maximized by solving the parametric problems max N(x) - q D(x) and updating q to the attained ratio |
| source | W. Dinkelbach, "On Nonlinear Fractional Programming," Management Science, vol. 13, no. 7, pp. 492-498, 1967, DOI 10.1287/mnsc.13.7.492 |
| source type | primary (journal article) |
| used in | the planned Lagrangian codec (a directive after 018, not yet written), if its distortion is a ratio such as `F = 2 M / (N_rec + N_true)`; directives 017 and 018 do not use it |
| version / conditions | JSTOR copy (stable URL https://www.jstor.org/stable/2627691) supplied by the author as an OCR transcript on 2026-10-13 and read in full; its cover page prints Management Science, Mar. 1967, vol. 13, no. 7, Series A, pp. 492-498. The parametric theorem (Section 2) and the iteration q_{k+1} = N(x_k)/D(x_k) (Section 3) were checked in that text. The DOI is from the publisher's listing and is not printed on the JSTOR copy. Transcript kept in the claude.ai Project as `refs/dinkelbach1967.md` |
| status | `VERIFIED` for the claim and for venue, volume, issue and pages; DOI `PARTIAL` (publisher listing only) |
| does not support | convergence after one step |

### `shoham1988`

| field | value |
|---|---|
| claim supported | For any lambda >= 0, the allocation B*(lambda) that minimizes the sum of distortions plus lambda times the total rate over independently quantized units also solves the constrained problem with rate budget R_c = R(B*(lambda)) (Section III, "Theorem") |
| source | Y. Shoham, A. Gersho, "Efficient bit allocation for an arbitrary set of quantizers," IEEE Trans. Acoustics, Speech, and Signal Processing (year, volume, issue, pages and DOI not verified) |
| source type | primary (journal article) |
| used in | the planned Lagrangian codec (a directive after 018, not yet written): one multiplier for all blocks and windows; directive 018 measures additive fidelities so that this applies |
| version / conditions | full text supplied by the author as an OCR transcript on 2026-10-13 and read in full; title, authors and the theorem with its proof are in that text. The transcript does not carry the journal name, year, volume, issue or pages. Transcript kept in the claude.ai Project as `refs/shoham1988.md` |
| status | `PARTIAL`: content and authorship verified from the article text; venue, year, volume, issue, pages and DOI `UNRESOLVED` |
| does not support | the existence of a lambda that meets a given budget exactly (the paper states the theorem does not guarantee it); optimality of greedy claims, of estimated rates, or of a single pass; non-additive rates |

### `sullivan1998`

| field | value |
|---|---|
| claim supported | In video coders the encoder's choice among modes (motion-compensated prediction, coding of refreshed regions) is made by Lagrangian rate-distortion optimization |
| source | G. J. Sullivan, T. Wiegand, "Rate-distortion optimization for video compression," IEEE Signal Processing Magazine, vol. 15, no. 6, pp. 74-90 |
| source type | primary (magazine article) |
| used in | the planned Lagrangian codec (after directive 018) and the manuscript, as the precedent of the mode choice; directive 018 cites the hybrid video coder it describes as the structure of its HEVC baseline |
| version / conditions | title, authors, venue, volume, issue and pages from the authors' institutional publication page (Microsoft Research), read on 2026-10-13; the year and the DOI are not shown there. Full text supplied by the author as an OCR transcript on 2026-10-13: it confirms title, authors and the Lagrangian formulation of the encoder's choices; it does not print venue metadata. Transcript kept in the claude.ai Project as `refs/sullivan1998.md` |
| status | `PARTIAL`: year and DOI not verified |
| does not support | anything about event data |

### `wiegand2003`

| field | value |
|---|---|
| claim supported | Lagrangian mode decision per macroblock among SKIP, INTER and INTRA minimizes D + lambda R |
| source | T. Wiegand, H. Schwarz, A. Joch, F. Kossentini, G. J. Sullivan, "Rate-Constrained Coder Control and Comparison of Video Coding Standards," IEEE Trans. Circuits and Systems for Video Technology, July 2003 |
| source type | primary (journal article, author's copy) |
| used in | the planned Lagrangian codec (after directive 018) and the manuscript |
| version / conditions | title, authors, journal, month and year, and the mode decision of its Eq. (7), from the author's copy at iphome.hhi.de, read on 2026-10-13; volume, issue and pages are not printed on that copy. An OCR transcript supplied by the author on 2026-10-13 confirms J_MODE = D_REC + lambda_MODE R_REC minimized per macroblock over mode sets that contain INTRA, SKIP and INTER modes. Transcript kept in the claude.ai Project as `refs/wiegand2003.md` |
| status | `PARTIAL`: volume, issue, pages and DOI not verified |
| does not support | anything about event data |

### `everett1963`

| field | value |
|---|---|
| claim supported | If x* maximizes the Lagrangian H(x) - sum_k lambda_k C_k(x) for nonnegative lambda_k, then x* maximizes H among all x with C_k(x) <= C_k(x*); with separable payoff and cost the unconstrained problem decouples into independent cell problems, and gaps in the attainable resource levels arise where the cell payoff is not concave in the resource (Theorem 1 and its discussion) |
| source | H. Everett III, "Generalized Lagrange Multiplier Method for Solving Problems of Optimum Allocation of Resources," Operations Research, vol. 11, no. 3, pp. 399-417, 1963, DOI 10.1287/opre.11.3.399 |
| source type | primary (journal article) |
| used in | the planned Lagrangian codec (after directive 018): one multiplier shared by all blocks and windows, and the statement that budgets falling in a gap are reached only by mixing two multipliers |
| version / conditions | INFORMS copy supplied by the author as an OCR transcript on 2026-10-13 and read in full; the cover page prints the citation and DOI given here. Transcript kept in the claude.ai Project as `refs/everett1963.md` |
| status | `VERIFIED` |
| does not support | optimality for non-separable costs, such as coded rates that depend on the joint content of several blocks |

### `chou1989`

| field | value |
|---|---|
| claim supported | The generalized BFOS algorithm minimizes delta(S) + lambda I(S) over pruned subtrees S of a tree T, and pruning in order of the smallest magnitude of slope of Delta u(S_t) yields nested subtrees that trace the lower boundary of the convex hull of the achievable distortion-rate points |
| source | P. A. Chou, T. Lookabaugh, R. M. Gray, "Optimal Pruning with Applications to Tree-Structured Source Coding and Modeling," IEEE Trans. Information Theory (year, volume, issue, pages and DOI not verified) |
| source type | primary (journal article) |
| used in | the planned Lagrangian codec (after directive 018): the key events of a block as the parent of its later SKIP modes, kept or pruned by the same multiplier |
| version / conditions | full text supplied by the author as an OCR transcript on 2026-10-13; title, authors, abstract and Sections I-II read. The transcript does not carry journal metadata. Transcript kept in the claude.ai Project as `refs/chou1989.md` |
| status | `PARTIAL`: content and authorship verified from the article text; venue, year, volume, issue, pages and DOI `UNRESOLVED` |
| does not support | anything about event data; optimality when the cost of a node depends on its siblings |

### `x265_hevc`

| field | value |
|---|---|
| claim supported | x265 is an encoder for HEVC (ITU-T H.265 / ISO/IEC 23008-2), reachable from ffmpeg as `libx265`, with constant-QP rate control, a settable intra period and no B frames |
| source | the x265 project (MulticoreWare), https://x265.readthedocs.io/ ; ITU-T Recommendation H.265 |
| source type | software documentation (primary for the encoder); standard (not read) |
| used in | `ec/families.py` (directive 018): the `hevc` family |
| version / conditions | director's tests: ffmpeg 6.1.1 (Ubuntu build) with libx265 on 2026-10-13; the executor records the versions on `cnt` in `results/fm/provenance.json` |
| status | `PARTIAL`: behavior of the parameters checked on synthetic streams (one intra picture per clip, no B frames, deterministic output, the P-frame QP as set and the intra frame at the default offset); the documentation pages were not read for this entry, and H.265 was not read |
| does not support | that x265 at these settings is the best HEVC coder for count frames, or that HEVC is the best video coder for them |

### `fu2019spike`

| field | value |
|---|---|
| claim supported | a lossy coder of DVS events with inter-cube prediction was published at DCC 2019 |
| source | Y. Fu, J. Li, S. Dong, Y. Tian, T. Huang, "Spike Coding: Towards Lossy Compression for Dynamic Vision Sensor," Data Compression Conference (DCC), 2019, p. 572, DOI 10.1109/DCC.2019.00084 |
| source type | secondary (a dblp mirror at pkuscholar.onrender.com, read on 2026-10-13); the survey of C. Brites and J. Ascenso, IEEE Access, vol. 13, 2025 (arXiv 2405.07050), lists it as lossy with inter-cube prediction |
| used in | the manuscript, related work (to be added); no directive uses it |
| version / conditions | the paper itself was not read; the mirror gives the start page only |
| status | `PARTIAL`: metadata from a secondary listing; content not read. Not to be cited for any property beyond its existence until read |
| does not support | anything about its rate, its distortion measure or its performance |

### `verma2024etram` (tasks and background filter)

| field | value |
|---|---|
| claim supported | eTraM labels 2D boxes of traffic participants with object ids for detection and multi-object tracking, with RVT, RED and YOLOv8 as detection baselines and an IoU tracker; its label frames used a spatiotemporal filter that removes events without same-polarity neighbors within a 10 ms window |
| source | the citation of the brief, `docs/brief/event_coding_brief.md`, entry `[verma2024etram]`; arXiv 2403.19976v2 (HTML), read on 2026-10-13 |
| source type | primary (conference paper, arXiv version) |
| used in | directive 017, Section 1 (the tasks); directive 018, Sections 1 and 4 and `ec/families.py` (`ISO_TAU_US` = 10 ms, the neighborhood of the isolation estimate) |
| version / conditions | the brief's status stands for the citation; this entry covers the two claims above, taken from the arXiv HTML through a summarizing fetch, not from the CVF PDF |
| status | `PARTIAL`: the claims were read in a summary of the arXiv text; the filter's minimum of 2 neighbors is the paper's, ours requires 1 |
| does not support | that the filter of eTraM removes only background events, or any background rate of the sensor |

### `dsec_detection`

| field | value |
|---|---|
| claim supported | DSEC-Detection gives 2D boxes with track ids for 60 sequences of DSEC and its extension, in the distorted (unrectified) view of the left event camera, as `object_detections/left/tracks.npy` with the fields `t, x, y, h, w, class_id, class_confidence, track_id`; the labels archive is 4.7 MB at `https://download.ifi.uzh.ch/rpg/DSEC/detection/dsec-det_left_object_detections.zip` |
| source | the DSEC-Detection page, https://dsec.ifi.uzh.ch/dsec-detection/, and the README of https://github.com/uzh-rpg/dsec-det, both read on 2026-10-13 (through a summarizing fetch); the associated publication is D. Gehrig and D. Scaramuzza, Nature, 2024 (not read) |
| source type | primary (dataset page and the authors' repository) |
| used in | directives 017 and 018: the boxes and tracks of the DSEC sequences |
| version / conditions | neither page states the label rate or the time base; a reviewer read the repository's loader as matching label times to event times with `t_offset` added, which directive 017, Section 4, tests on data before use |
| status | `PARTIAL`: format, view and download verified from the two pages; the list of labeled sequences, the label rate and the time base not stated there |
| does not support | which of the 41 train sequences carry labels, or the quality of the labels |
