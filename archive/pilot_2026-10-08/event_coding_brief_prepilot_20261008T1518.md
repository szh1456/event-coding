# Information coding of event-camera streams: phase 1 research brief

Date: October 8, 2026. Status: literature map, gap, problem statements, pilot plan, and risks. Sections 1 to 6 were written before any event file was opened. Section 7 reports a small pilot that was run afterwards.

Conventions. "bpe" is bits per event. "CR" is the compression ratio relative to the raw size stated in the cited paper (64, 40, or 32 bits per event, so CRs from different papers are not comparable). A dagger (†) marks a number I derived from a reported one, for example bpe = 64/CR. "Second-hand" means the number comes from the survey [brites2025], not from the primary paper. Citation keys match `references.bib`. The reference list at the end gives the verification status of every entry.

## 0. Summary

1. No paper gives an entropy rate or a rate-distortion function for real event streams. The theory needed for one exists (entropy rate of a point process with a conditional intensity, and the rate-distortion function of a Poisson process under a timing-fidelity distortion) but has not been applied to event-camera data.
2. No paper compares a predictive or motion-compensated lossless event coder with Zstandard or LZMA on a delta-encoded columnar layout. Published "gains over generic compressors" are measured against byte-level or raw-file inputs with unstated settings. On noisy night sequences, LZMA already matches or beats the event-specific coders in the two studies where both numbers exist [bi2018, bairagi2022].
3. No paper reports the bit cost of noise events. A one-line calculation says it should dominate: under a Poisson model, an event from a pixel that fires at 0.1 to 1 Hz costs 21 to 25 bits at 1 µs timestamps, which is more than the best published lossless coders spend per event on average (12.58 bpe on DSEC [schiopu2023cvprw]).
4. Recommended story: a bit budget for event streams. Split the lossless bit cost into timing precision, unpredictable events (noise and object onsets), and predictable motion events, with closed-form reference values for the first two and a simple causal context coder for the third. The decisive baseline is U2 + zstd (levels 1 and 19) and xz on the same layout.
5. The largest risk is that a well-laid-out generic compressor is already close to the context coder. The pilot in Section 4 tests exactly that on a few recordings.

## 1. Literature map

### 1.1 Lossless coding of raw asynchronous events (full timestamps kept)

| Ref | What is coded | Baselines as run | Reported result | Dataset | Code |
|---|---|---|---|---|---|
| [bi2018] | (x, y, t, p), 64-bit raw. Cube partition, address-prior and time-prior modes, context-adaptive entropy coding, differential timestamps | LZ77, LZMA. Settings and input layout not stated | CR 19.52 average vs 12.64 (LZMA). Outdoor 17.23 vs 8.82. LZMA wins on night-roadside (5.96 vs 5.44), night-traffic (4.80 vs 3.87), and game (5.22 vs 4.50). Table 1, full text | PKU-DVS, 13 static-camera sequences | None found |
| [dong2019] | Same, with octree cubes and an inter-cube prediction mode | LZ77, LZMA | Second-hand: CR 2.65 average, 2.64 with inter-cube prediction, 1.24x over LZMA | DDD17 (driving) | None found |
| [khan2020], [iqbal2020] | Raw 64-bit events. Benchmark study | Spike coding, LZMA, Zstd, Brotli, Zlib, LZ4, Huffman, Sprintz variants, fast integer coders. Seven 1-byte columns, column-major. No delta step stated for the generic coders. No levels stated | Static sensor: LZMA best (about 17.1†, inferred from a stated 79.14% drop), spike coding 14.35. Moving sensor: spike coding 3.99, LZMA 3.57, Zstd 3.16 (the last from Table II of [khan2021talven]) | PKU-DVS (static), DAVIS 240C (moving) | None found |
| [schiopu2022sensors] | (x, y, p, t), 64-bit raw. Same-timestamp subsequences, spatial prediction residuals (LLC-ARES) | Bzip2, LZMA, ZLIB | Average improvement 5.49%, 11.45%, 35.57% (abstract) | DSEC (second-hand) | None found |
| [schiopu2023cvprw] | Same representation, adaptive Markov models (ELC-ARES). Temporal prediction only for the event count per timestamp | ZLIB 1.2.3, LZMA SDK, Bzip2 1.0.5, LLC-ARES. No levels. Input layout for the generic coders not stated. No Zstd | 12.58 bpe vs LZMA 16.80, Bzip2 15.91, LLC-ARES 14.82, ZLIB 20.32 (Table 3, full text) | DSEC, 82 sequences, first 100 s each, 640x480 | None found |
| [martini2022] | Events as an (x, y, t) point cloud per polarity, G-PCC geometry coding | Spike coding, LZMA | "Up to 30%" higher CR (abstract). 49.4% over LZMA (second-hand) | DAVIS 240C | None found |
| [huang2023icip] | (x, y, t) point cloud, G-PCC octree | Baseline numbers copied from [khan2020], not re-run | CR 4.889 vs 4.00 for the best baseline, LZMA 3.59 (Table 1, full text) | DAVIS 240C, 8 sequences | None found |
| [sezavar2024vcip] | Per-polarity octree occupancy with a learned hyperprior and arithmetic coding (LLEC) | lz4, bzip2, 7z applied to EVT2 files (JPEG XE anchors). No settings | 9.71 to 23.34 bpe over 11 sequences. Traffic_monitoring: 20.96 vs 7z 23.55, bzip2 25.44, lz4 32.78 (Tables II and III, arXiv full text) | JPEG XE reference set plus Prophesee samples | None found |
| [sezavar2024ism] | One coding unit per timestamp, quadtree occupancy, small network predicts symbol PMFs from past units, Rice coding, polarity sent raw (LC-LLEC) | Same anchors | 11.09 to 25.41 bpe vs 7z 12.32 to 27.90 over 9 sequences | Same | None found |
| [sezavar2025spie] | Adaptive octree plus hyperprior | Not in abstract | No numbers in abstract | Not in abstract | None found |
| [wang2023jsen] | Character-like event representation, then Zip | Spike coding | 17.93% and 14.92% CR gain (second-hand) | Four self-recorded DAVIS346 sequences | Not checked |
| [ding2024iscas] | Hardware lossless coder | Content not read | Not confirmed | Not confirmed | Not checked |

### 1.2 Lossless coding of aggregated event frames (timing inside the window is discarded)

| Ref | What is coded | Baselines | Reported result | Dataset | Code |
|---|---|---|---|---|---|
| [khan2021talven] | Per-polarity event-count frames over 1 to 50 ms, lossless HEVC (x265) | Spike coding, LZMA, Brotli on raw events | Boxes: CR 9.72 at 1 ms, 21.74 at 10 ms, 77.28 at 50 ms. No intra vs inter ablation | DAVIS 240C, 10 sequences | None found |
| [adhuran2024] | Time-aggregated events as a point cloud with a count attribute, G-PCC lossless | TALVEN, spike coding | Shapes at 20 ms: 34.34 vs 29.21 (TALVEN). Better above 5 ms, worse below | DAVIS 240C | None found |
| [schiopu2022spl], [schiopu2022lsens], [schiopu2023electronics], [schiopu2024cadett] | Ternary event frames (context modeling, low-complexity and fixed-length variants) | HEVC, VVC, CALIC, FLIF (second-hand) | Numbers not confirmed in the primaries | DSEC | None found |

### 1.3 Standard and formats

| Item | Content | Source |
|---|---|---|
| JPEG XE, ISO/IEC 26112, ITU-T T.841.x | Part 1 (core coding system, lossless, low complexity) has its final text after DIS approval and publication is requested. Parts 2 and 3 (profiles, reference software) are at DIS. Part 2 has an embedded lossless constrained profile aligned with the MIPI CSI-2 v4.2 Event Stream Protocol. Lossy coding is future work. Anchors in the common test conditions are lz4, bzip2, and 7z on EVT2 (second-hand, via [sezavar2024vcip]). The common test conditions documents could not be read | [jpegxe2026press] |
| Prophesee EVT 2.0 and EVT 3.0 | EVT 2.0: one 32-bit word per event plus time-high words. EVT 3.0: 16-bit words, row, time, and polarity sent on change, vector words for up to 12 events in a row | [prophesee_evt] |
| Prophesee ECF (HDF5 filter) | Lossless: 4-bit timestamp deltas with run counts, run-length y and polarity, masked or bit-packed x. No entropy coder. No published ratios | [prophesee_ecf] |
| DSEC storage | HDF5, separate x, y, p, t datasets, Blosc with the Zstd codec. No delta step documented | [dsec_format] |

### 1.4 Lossy coding, rate reduction, and quality or task metrics

| Ref | What is coded and what is lost | Metric | Reported result | Dataset | Code |
|---|---|---|---|---|---|
| [banerjee2021icip] | Events binned in time, thinned by Poisson disk sampling inside a quadtree derived from intensity frames | PSNR and SSIM on event images, timestamp error | CR 39.65 to 3331 from binning alone (Table 1) | DAVIS sequences | None found |
| [banerjee2024tnnls] | Joint bit allocation between intensity frames and events under a bandwidth cap | Tracking accuracy (MOTA) | Operating points at 1 and 1.5 Mbps (arXiv version) | Simulated events (ESIM) | None found |
| [seleem2025access], [seleem2026ojsp] | Events as point clouds, learned lossy geometry coding, timestamps scaled and merged | PSNR adapted from point clouds, classification accuracy | BD-rate -61.30% vs lossy G-PCC at equal Top-1 accuracy (Table I of the first paper) | N-Caltech101, CIFAR10-DVS, DVS Gesture | None found |
| [stumpp2024] | See 1.5 | Temporal error, kernel spike-train distance [li2023astsm] | See 1.5 | See 1.5 | None found |
| [rezaee2026] | Count frames with JPEG 2000, point clouds with G-PCC | Five occupancy-frame scores vs four tasks (reconstruction, detection, flow, tracking) | Proposed scores reach rank correlation of at least 0.80 with task loss. Event-level distances ([li2023astsm], point-cloud PSNR) fall below 0.80 in most cases | ECD, Gen1, MVSEC | None found |
| [hamara2024] | Events dropped to meet a bandwidth or latency target (Media over QUIC) | Detection mAP (RVT) | mAP drop 0.37 at 5 Mbps and 0.06 at 100 Mbps (Table 1). Raw event is 16 bytes | 10-video eTraM subset | None found |
| [araghi2025] | Six event subsampling rules | Area under accuracy vs log event count | Causal density-based rule best on N-Caltech101 (0.723 vs 0.708 random) | N-Caltech101, DVS-Gesture, N-Cars | Public (GitHub) |
| [ogden2026] | Contrast threshold swept in simulation | Rate is events per pixel per frame, distortion is MS-SSIM of reconstructed frames | Empirical curves only. No closed form, no noise | UVG video (simulated events) | None found |
| [khan2019bandwidth] | Event-rate model, not a codec | Fit quality | Rate is linear in speed and exponential in mean Sobel gradient, R² = 0.99 | DAVIS 240C | None found |
| [prophesee_esp] | On-sensor event rate controller, anti-flicker filter, trail filter (IMX636, GenX320) | None | The event rate controller drops events to hold a target rate and degrades signal quality when active | Sensor documentation | n/a |

No agreed distortion measure for lossy event coding exists. [seleem2026ojsp] and [rezaee2026] both say so.

### 1.5 Predictive and motion-compensated coding

| Ref | Method | Baselines | Reported result | Dataset | Code |
|---|---|---|---|---|---|
| [stumpp2024] | Lossy. On-sensor optical flow. During a prediction period, events with a valid flow are not sent and the receiver extrapolates them. Events without flow are sent as plain 64-bit events. No residual is sent | None re-run. Spike coding numbers quoted from [khan2020]. LZMA used only as a second stage | CR 2.81 average at a 30 ms prediction period, median temporal error 0.48 ms. With LZMA: 10.45 to 17.24. About half of the events of Indoor Flying 1 had no valid flow | Shapes, Slider Far, Outdoor Day 1, Indoor Flying 1, Bar-Square | None found |
| [bairagi2022] | Lossless. Event-based flow (eight directions) predicts events, the remainder is spike-coded, flow is arithmetic-coded | Spike coding only, with numbers that equal Table 1 of [bi2018] after rounding | CR change vs spike coding between -8% and +24%†. "Does not always improve". Against the LZMA column of [bi2018]†: night-roadside 6.34 vs 5.96, night-traffic 4.71 vs 4.80, game 5.25 vs 5.22 | PKU-DVS | None found |
| [dong2019] | Inter-cube prediction inside spike coding | See 1.1 | No gain (2.64 vs 2.65, second-hand) | DDD17 | None found |
| [khan2021talven] | HEVC inter prediction on count frames | See 1.2 | Inter vs intra not reported | DAVIS 240C | None found |
| [delbruck2022csdvs] | Hardware: center-surround pixel that subtracts the local spatial average before change detection | Standard DVS pixel (simulation) | About 60% fewer events on a flashing spot | Simulation | n/a |
| [gallego2018cmax], [gallego2019focus], [shiba2022secrets] | Motion compensation by contrast maximization. [gallego2019focus] includes an entropy-of-warped-image loss | n/a | None of them links the objective to a coding cost in bits | n/a | [shiba2022secrets] public |

No sensor or readout that emits events only on the error of a motion predictor was found.

### 1.6 Entropy, rate, and rate-distortion analyses

| Ref | Result | Relevance |
|---|---|---|
| [khan2020] | Zeroth-order entropy of x, y, and delta timestamps for two DAVIS sequences. Address entropies "close to" the uniform maximum, delta-timestamp entropy "very low". Values only in a figure | The only field-level entropy numbers found. No conditional entropies |
| [mcfadden1965], [papangelou1978] | Entropy of a point process and its limit under time discretization | Basis of Eq. (1) below |
| [shende2022] | Distortion-rate function with feedforward for general point processes with intensity Λ: a term of the form E[Λ - Λ ln Λ] per unit time | Covers history-dependent intensities, not only Poisson |
| [daley2004] | Information gain per unit time of a point-process forecast is bounded by the entropy rate | Defines the coding gain of a predictor over a Poisson reference |
| [verdu1996], [coleman2008], [lapidoth2015], [shen2021itw] | Poisson process of rate λ: R(D) = -λ log(λD) when inter-arrival times are reproduced to within D [verdu1996, as stated in coleman2008], and -λ log D for queueing and covering distortions | Closed-form cost of timing precision for unpredictable events, Eq. (5) |
| [rubin1974], [gallager1976] | Earlier information rates for Poisson processes and for message arrival times | Background. Formulas not confirmed here |
| [guo2022wiener] | For the Wiener process, sampling when the innovation crosses ±sqrt(1/R) and sending a 1-bit sign achieves D = 1/(6R), against 5/(6R) for uniform sampling | An ideal event pixel (send-on-delta plus polarity) is rate-distortion optimal when timing is free |
| [miskowicz2006] | Mean report rate of send-on-delta sampling: mean absolute slope divided by the threshold | Event-rate law. No bits |
| [mark1981], [guan2007ciss] | Bit-level coding of level-crossing times, with a predictive variant in [mark1981]. Information-theoretic argument for level crossing of bursty signals | Early one-dimensional precedents |
| [koliander2018] | Rate-distortion bounds for finite point patterns | Applies to the address field of a time slice |
| [strong1998], [paninski2003], [kennel2005] | Entropy-rate estimation for spike trains (direct method, bias analysis, context-tree weighting with confidence intervals) | Estimators that have not been applied to event-camera data |
| [ogden2026] | See 1.4 | Closest "rate-distortion of an event camera" paper. Rate is an event count |

### 1.7 Point-process and generative models of event generation

| Ref | Model | Usable as a coding model |
|---|---|---|
| [lichtsteiner2008], [gallego2022survey] | Ideal pixel: event when log intensity changes by the contrast threshold. Threshold 10% to 50%, pixel bandwidth about 3 kHz in bright light and about 300 Hz at 1000 times lower intensity | Deterministic core. No likelihood |
| [lin2022voltmeter] | Pixel voltage as Brownian motion with drift. Inter-event time is inverse Gaussian (Lévy at zero drift), parameters tied to brightness and its slope | Yes. Closed-form inter-event law that covers signal and noise |
| [gu2021stppp] | Spatio-temporal Poisson point process after motion alignment. Product-of-Poisson likelihood, negative binomial marginal | Count model per window. No timing inside the window |
| [hashimoto2026] | History-dependent marked point process with a softplus conditional intensity around the threshold and a floor rate. Standard log-likelihood with compensator. Synthetic data only | Yes. The most direct conditional-intensity model found |
| [baldwin2020] | Bernoulli event probability per pixel from intensity gradient and motion | Needs intensity frames and IMU |
| [hu2021v2e], [joubert2021], [graca2025model] | Simulators. v2e draws noise as per-pixel Poisson (1 to 10 Hz in dark presets, leak about 0.1 Hz). [joubert2021] uses a measured inter-event-interval distribution. [graca2025model] uses first-passage times of an Ornstein-Uhlenbeck process | Noise sub-models |

No Hawkes or neural temporal point process model of event-camera streams was found.

### 1.8 Noise events

| Ref | Finding |
|---|---|
| [gallego2022survey] | Stationary noise 0.05 to 0.1 events per pixel per second for DVS128, DAVIS240, DAVIS346 at 25 °C (Table 1) |
| [mcreynolds2025amos] | IMX636 near 1 mlux: about 0.03 events per pixel per second at default biases, about 1 at sensitivity-tuned biases. About 2% of pixels (hot pixels) produce over 99% of excess events in one recording |
| [mcreynolds2023pairs] | Shot-noise events dominate below about 10 lux. Over 90% of consecutive noise events at a pixel have opposite polarity, so noise is not memoryless. Bias changes cut noise by 50% and 80% |
| [graca2023tutorial], [graca2023limits] | Noise rate falls exponentially with threshold and rises with bandwidth. Random ON/OFF shot noise in the dark, mostly ON leak events in bright scenes |
| [riosnavarro2023] | Low-light surveillance scene: a denoiser cuts the data rate from 10 MB/s to 100 kB/s, removes more than 100x of the noise, and blocks about 25% of signal events (Fig. 1 caption) |
| [cao2025noise2image] | Noise-event rate depends on static illuminance, so noise events carry scene information. Per-pixel counts are overdispersed relative to Poisson |
| [oliver2025] | Noise rate of a Prophesee Gen4 sensor peaks near 4 to 5 lux. A 6.6 °C temperature change moved it by nearly an order of magnitude |
| [mcreynolds2024scurve] | IMX636 (EVK4): ON threshold about 0.25 in log contrast, low-light cutoff about 80 mlux |
| [guo2023denoise] | DND21 denoising benchmark. Full text not read. A companion paper tests at 5 Hz per pixel shot noise [riosnavarro2023] |
| [shiba2025noise] | Joint motion and noise estimation by contrast maximization. The intrinsic noise share of real recordings is stated as unknown |
| [zhao2025date] | "Denoising and compression" filter. Compression means the share of discarded events (30% to 68%), not bits |

No paper reports the fraction of events that are noise in a real night traffic scene, and none converts a noise share into bits.

### 1.9 Neuromorphic and spike coding links

| Ref | Content |
|---|---|
| [lazar2004], [martineznuevo2019] | Time encoding of bandlimited signals. [martineznuevo2019] treats a level-crossing (delta-ramp) encoder as time encoding |
| [adam2022], [adam2022events] | Event pixels as integrate-and-fire time encoding machines. Video recovery needs enough spikes relative to the degrees of freedom. A count condition, with no bits and no timing quantization |
| [naaman2021quant] | Quantized time encoding: MSE bound that decays as 2^(-2N) with N bits per inter-firing interval, plus firing-rate bounds. The only bit-level time-encoding result found. No bits-per-second expression |
| [boahen2000] | Address-event representation |
| [chen2023tccn], [ke2024dib] | Neuromorphic wireless links with DVS input. The traded quantity is spike rate or channel uses against accuracy, not the bit rate of the event stream |

### 1.10 Datasets

| Ref | Sensor and resolution | Content | Notes |
|---|---|---|---|
| [verma2024etram] eTraM | Prophesee EVK4 HD, 1280x720, static, about 6 m high | 10 h, day, night, twilight. Over 2 million boxes with track IDs, 8 classes, 30 Hz | About 30 times fewer events than 1 Mpx and DSEC over 60 s. Bias and event-rate-controller settings not stated. A spatiotemporal filter was applied when building label frames. License statements are inconsistent across paper, site, and repository (CC BY-NC-SA in the dataset documentation) |
| [gehrig2021dsec] DSEC | Two Prophesee Gen3.1, 640x480, on a car | 53 sequences, 3193 s, day and night | Used by [schiopu2023cvprw]. CC BY-SA 4.0. Sensitivity was changed between day and night |
| [detournemire2020] Gen1 | 304x240, on a car | 39.32 h, 255,781 boxes | Rate mostly below 200 kev/s |
| [perot2020] 1 Mpx | 1280x720, on a car | 14.65 h, about 25 million boxes | Daytime |
| [mueggler2017] ECD | DAVIS 240C, 240x180, hand-held | 27 sequences | Bias settings tabulated. Used by most lossless papers |
| [chaney2023m3ed] M3ED | Two EVK4 (IMX636), 1280x720 | 57 sequences, car, drone, legged robot | Same bias in all sequences, event rate controller removed. CC BY-SA 4.0 |
| [zhu2018mvsec] MVSEC | Stereo DAVIS 346, 346x260 | Car, drone, hand-held | CC BY-SA 4.0 |

## 2. The gap

**(a) Bounds.** Not found: an entropy-rate estimate or a rate-distortion function for real event streams. The closest items are zeroth-order field entropies for two DAVIS sequences [khan2020] and simulated rate-distortion curves in which rate is an event count and noise is excluded [ogden2026]. The best available numbers are coder outputs, which are upper bounds on the entropy rate: 12.58 bpe on DSEC [schiopu2023cvprw] and 9.71 to 23.34 bpe on JPEG XE sequences [sezavar2024vcip].

**(b) Motion-compensated prediction against strong generic baselines.** Not found. The only lossless motion-compensated coder is a thesis that compares with spike-coding numbers copied from [bi2018] on static-camera scenes [bairagi2022]. The flow-based coder of [stumpp2024] is lossy and re-runs no baseline. Inter-cube prediction gave no gain on driving data according to the survey [dong2019]. No paper pairs Zstd or LZMA with delta timestamps, per-field columns, and stated levels on driving or traffic data. The generic baselines in print are byte columns without a delta step [khan2020], unspecified inputs [bi2018, schiopu2023cvprw], or EVT2 files [sezavar2024vcip]. U2 + zstd-1 is therefore a stronger baseline than anything published, and its distance from the event-specific coders is unknown.

**(c) Bit cost of noise.** Not found. Indirect evidence points one way: night sequences are where LZMA beats event-specific coders [bi2018], low-light data volume can be about 99% noise [riosnavarro2023], and half of the events in one sequence had no usable flow and were sent uncompressed [stumpp2024].

**(d) Two further gaps.** First, "lossless" is not defined consistently: some coders keep the order of events that share a timestamp and some do not, and raw sizes of 64, 40, and 32 bits are all in use. Second, no public software reproduces any of the event-specific coders [brites2025], so every comparison in a new paper must be built from scratch or run against the JPEG XE reference software once Part 3 is available.

### Working model used in Sections 3 to 5

Treat the stream as a marked point process on pixels u with timestamp resolution δ and conditional intensity λ_u(t) given the past. For λ_u δ ≪ 1, the entropy rate without polarity is

$$ h_\delta = \sum_u \mathbb{E}\big[\lambda_u(t)\,\big(1-\ln(\lambda_u(t)\,\delta)\big)\big] \quad \text{nats/s}. \tag{1} $$

Eq. (1) follows from the per-slot Bernoulli entropy and matches the discretization limit in [papangelou1978] and the intensity functional in [shende2022]. Three consequences follow.

An event from a pixel with constant rate λ (noise, or any event the coder cannot anticipate) costs

$$ b(\lambda,\delta) = \frac{1-\ln(\lambda\delta)}{\ln 2} \quad \text{bits}, \tag{2} $$

plus at most 1 bit of polarity. The same number is obtained in the event-list view as the cost of the global time difference plus the cost of the address.

| Pixel rate λ | δ = 1 µs | 10 µs | 100 µs | 1 ms |
|---|---|---|---|---|
| 0.03 Hz | 26.4 | 23.1 | 19.8 | 16.5 |
| 0.1 Hz | 24.7 | 21.4 | 18.1 | 14.7 |
| 1 Hz | 21.4 | 18.1 | 14.7 | 11.4 |
| 5 Hz | 19.1 | 15.7 | 12.4 | 9.1 |

An event whose pixel and time are predicted from its neighbors up to a timing density with differential entropy h_τ costs

$$ b_{\mathrm{pred}} = \frac{h_\tau-\ln\delta}{\ln 2} = \log_2\frac{\sigma\sqrt{2\pi e}}{\delta} \quad \text{bits for Gaussian jitter } \sigma, \tag{3} $$

which is 5.4, 8.7, and 12.0 bits at δ = 1 µs for σ = 10 µs, 100 µs, and 1 ms. Perfect motion knowledge does not remove this term. The pixel bandwidth figures in [gallego2022survey] (time constants from about 50 µs to about 0.5 ms) suggest σ in the range 0.1 to 1 ms outside bright, high-contrast scenes. This value of σ is an assumption to be measured, not a cited result.

If the stream is the superposition of a signal process S and an independent noise process N, then

$$ H(S\cup N) \ge H(S\cup N \mid S) = H(N), \tag{4} $$

so the entropy of the noise process is a lower bound for any lossless coder. With a noise share f of the events, the bound is f·b(λ_noise, δ) bits per event: 2.6 bpe at f = 0.1 and 12.9 bpe at f = 0.5 for 0.1 Hz noise at 1 µs. The bound is strict only for the true noise entropy. Poisson is the maximum-entropy case at a given rate, and real noise has pair structure [mcreynolds2023pairs], so the Poisson value must be checked on object-free segments.

Finally, coarser timing is cheap to analyze for the unpredictable part. With timestamps reproduced to within Δ, the Poisson rate-distortion function [verdu1996, coleman2008] is

$$ R(\Delta) = -\lambda \ln(\lambda\Delta) \quad \text{nats/s}, \qquad 0<\lambda\Delta\le 1, \tag{5} $$

so each factor of 10 in timing precision costs log2(10) = 3.32 bits per unpredictable event.

Eqs. (2) and (3) also say that bits per event rise as a scene gets sparser, while bits per second fall. Both must be reported.

## 3. Candidate problem statements

**P1 (recommended). A bit budget for event streams.** Claim: under lossless coding at microsecond resolution, the cost of a traffic-monitoring stream is dominated by two terms that no predictor can remove, namely events that are unpredictable in space (noise and object onsets, Eq. (2)) and timing jitter of predictable events (Eq. (3)). A causal context model on the time since the last event at the same and neighboring pixels captures most of the remaining structure, and explicit motion compensation adds little on top. Method: prequential (adaptive, causal) code lengths under a nested family of point-process models (uniform Poisson, Poisson with a rate map, rate map with a time-varying global rate, spatiotemporal context model), each realizable with arithmetic coding, together with the closed-form references of Eqs. (2) to (5). Decisive experiment: on eTraM day and night recordings, report bits per event and bits per second for AER40, U2 + zstd-1, U2 + zstd-19, U2 + xz, and each model, with the cost split by field (time, address, polarity) and by class (events inside annotated boxes, events outside all boxes, object-free intervals). Baseline to beat: U2 + zstd-1 as the transport reference, and U2 + zstd-19 and xz as the honest generic ceiling. Kill result: the context coder is within 15% of U2 + zstd-19 or xz in bits per second on both day and night recordings. In that case no coding contribution exists, and what remains is a shorter analysis paper stating that a delta-encoded columnar layout plus a generic compressor is near the limit set by noise and timing.

**P2. What timing precision costs: a rate-distortion view.** Claim: when timestamps are reproduced to within Δ, the rate of the unpredictable part follows Eq. (5), and the rate of the whole stream falls by close to log2(Δ/δ) bits per event until Δ reaches the timing jitter of the motion events, after which the saving saturates. Task accuracy stays flat well beyond that point. Method: requantize timestamps, treat events that share a timestamp as an unordered set, measure code length against Δ for the baselines and the context coder, and compare with Eq. (5) driven by measured rates. Decisive experiment: rate against Δ from 1 µs to 10 ms on eTraM, next to detection accuracy of a standard detector and one timing-sensitive task such as optical flow on DSEC. Baseline to beat: U2 + zstd-1 applied to the same requantized stream, since requantization helps generic compressors too. Kill result: the measured curve departs from Eq. (5) by more than about 1 bit per event in the sparse regime (the Poisson reference is then not informative), or the only available task model bins time at several milliseconds, which makes the accuracy result true by construction. The second outcome is likely for detection on eTraM, so P2 is better as a section of P1 than as a paper.

**P3. Does motion compensation pay?** Claim: on real scenes, predicting the firing time of a pixel from a local velocity estimate reduces the cost of motion events by less than the timing-jitter term of Eq. (3) allows, and gives less than 10% over a context model without explicit motion. This would explain the weak or absent gains in [dong2019] and [bairagi2022]. Method: add to the P1 coder a local plane fit on the time surface that predicts the firing time of each candidate pixel, and code the residual with an adaptive distribution. Decisive experiment: bits per event of in-box events against object speed (speed comes from eTraM track IDs), for no context, time-surface context, and motion-compensated timing, together with the residual spread σ that enters Eq. (3). Baseline to beat: the P1 context coder, then U2 + zstd-19. Kill result for the negative claim: motion compensation gives more than 20% over the context coder on in-box events, in which case P3 becomes the headline coder of P1. Either outcome is usable, so P3 is an ablation inside P1.

One story covers all three: P1 as the paper, the timing sweep of P2 as one section, and the motion ablation of P3 as another. A first result for DCC or ICASSP needs only the P1 decisive experiment. A journal version adds Eq. (4) as a stated bound with its noise-model conditions, the Δ sweep, and a second dataset with a moving camera.

## 4. Pilot plan

### 4.1 Data

Full pilot: six eTraM recordings from the train split (three day, three night), a 60 s window each, plus one object-free window of at least 10 s per condition, read from the raw EVT3 files so that no dataset-side filtering is involved. One DSEC sequence as a moving-camera contrast and as a link to the 12.58 bpe of [schiopu2023cvprw].

Available in this workspace today, from a public repository of sample data: one eTraM night recording (val_night_011, raw and HDF5), one Prophesee EVT2 sample (80_balls), and one DAVIS 240C text file (slider_depth). These three are enough to test the pipeline and the main risk. They do not support the day and night comparison or the class split.

### 4.2 What is measured

"Lossless" means that the multiset of (t, x, y, p) is preserved at the native timestamp resolution. The order of events that share a timestamp is not information. All sizes are reported as bits per event and bits per second.

1. **AER40.** 40 bits per event by definition.
2. **U2 + zstd-1.** Structure of arrays with delta timestamps, then zstd level 1. The companion implementation must be used for the real comparison. For the pilot I re-implement it as four arrays (Δt as uint32, x as uint16, y as uint16, p as uint8), concatenated, compressed in one block and in 1 MB chunks, in stream order and in canonical order (sorted by t, y, x). Also reported: zstd-19 and xz -9 on the same arrays, as the generic ceiling.
3. **Context coder C1.** Events are coded in stream order. All probabilities come from adaptive counts with a Krichevsky-Trofimov prior, updated after each event, so the code length is prequential, needs no training data, and is achievable by an arithmetic coder to within a few bits per file.
   - Time: the bucket ⌊log2(Δt + 1)⌋ is coded given the previous bucket, and the offset inside the bucket is coded uniformly.
   - Address: each pixel has a class c(u) = (age bucket of its own last event, age bucket of the most recent event among its 8 neighbors), with 7 logarithmic age buckets from under 4 ms to over 1 s. The model is P(u) = π_c(u) / N_c(u), where π_c is the adaptive probability that the next event falls in class c and N_c is the current number of pixels in that class. Ages are refreshed every 4 ms, and a new event moves its own pixel and its neighbors to the youngest bucket at once.
   - Polarity: adaptive binary model given the last polarity at the pixel, its age bucket, and the polarity of the most recent neighbor event.
   - Validity checks: at random event indices the address probabilities are summed over all pixels and must equal 1, and an arithmetic encoder and decoder that use the same model must round-trip a short segment with a size that matches the summed code length.
4. **Point-process entropy estimates,** computed the same way with poorer address models: M0, uniform over pixels (Eq. (2) with the measured mean rate); M1, a static rate map learned adaptively per pixel; M1*, the same with the empirical rate map of the whole recording (an optimistic order-0 entropy, not achievable causally); M2, self-age context only. The gap between M1 and C1 is the information gain of the temporal context in the sense of [daley2004].
5. **Diagnostics.** Event rate, fraction of events that share a timestamp, histogram of Δt, share of events and bits in the top 0.1% of pixels (hot pixels), and the cost split by field.

### 4.3 Expected outcome (written before any data were opened)

| Quantity | Sparse static scene (eTraM, night) | Dense motion (80_balls) | Moving camera, small sensor (slider_depth) |
|---|---|---|---|
| U2 + zstd-1 | 18 to 24 bpe | 8 to 14 bpe | 14 to 18 bpe |
| zstd-19 or xz, same layout | 10% to 25% below zstd-1 | same | same |
| M1 (static rate map) | within 3 bits of U2 + zstd-1, either side | above zstd-1 | above zstd-1 |
| C1 | 15% to 40% below U2 + zstd-1 | 25% to 45% below | 20% to 35% below |
| C1 against the generic ceiling | 5% to 25% below | 10% to 30% below | 10% to 25% below |
| Polarity cost in C1 | 0.5 to 0.9 bit | 0.3 to 0.8 bit | 0.3 to 0.8 bit |

Reasons. For a 1280x720 sensor at 0.1 to 1 million events per second, Eq. (2) gives 21 to 25 bits per event for a uniform Poisson stream, and published generic results on comparable material are 23.55 bpe (7z on the EVT2 Traffic_monitoring file [sezavar2024vcip]) and 16.80 bpe (LZMA on DSEC [schiopu2023cvprw]). A byte-oriented compressor sees x and y as nearly incompressible low bytes, so its output should sit near the rate-map entropy. The context coder should gain where pixels re-fire or follow neighbors (edges, flicker, hot pixels) and should gain little on isolated noise events. For the night recording I expect the low end of the C1 range unless flicker or hot pixels are present, in which case self-age contexts will give the high end. In the field split, I expect the address to carry more than two thirds of the C1 bits on the sparse scene. I expect that requantizing timestamps to 1 ms would remove 6 to 10 bits per event on the sparse scene and much less on the dense one.

Decision rule from the pilot. Continue with P1 as a coding paper if C1 is at least 15% below the generic ceiling on the eTraM recording. If C1 is within 15%, treat P1 as an analysis paper and move the effort to the bit budget and the noise bound. If M1 is already within 10% of C1, temporal context carries little and P3 is not worth building.

## 5. Risks and early checks

| Risk | Why the gain could be small | Early check |
|---|---|---|
| Noise floor | By Eq. (4), noise events cost about 21 to 25 bits each at 1 µs and cannot be predicted. At night they may be most of the stream | Code object-free windows alone and compare with Eq. (2) evaluated on the measured per-pixel rates. Report the share of bits outside all boxes. If the context coder lands well under the Poisson value, the noise has structure (polarity pairs, hot pixels) and that is a gain, not a floor |
| Timing jitter of signal events | By Eq. (3), a motion event costs 9 to 12 bits at 1 µs if jitter is 0.1 to 1 ms, whatever the motion model | Fit a local plane to the time surface on in-box events and measure the residual spread. Run the Δ sweep on one recording |
| Polarity entropy | Bounded by 1 bit per event, so it matters only once the rest is under about 5 bpe (coarse timing). Noise polarity alternates [mcreynolds2023pairs], which helps | Read the polarity line of the field split |
| Timestamp resolution and readout | Readout may assign the same timestamp to many events or reorder them, which changes both the generic baseline and the meaning of Eq. (1). An active event rate controller removes events and breaks the point-process model | Tie fraction and Δt histogram per recording. Compare raw EVT3 with the HDF5 export. Look for rate plateaus at a round target value |
| Sensor bias settings | Threshold and bandwidth biases move the noise rate by orders of magnitude [graca2023tutorial]. eTraM does not state its biases, and DSEC changed sensitivity between day and night. Results may not transfer between datasets | Report measured background rates per recording. Use M3ED (fixed bias, no rate controller) as a second dataset. State all results conditional on the measured noise rate |
| Hot pixels | A few pixels can produce most events [mcreynolds2025amos]. They are cheap to code and can inflate an apparent gain | Report results with and without the top 0.1% of pixels |
| Generic baseline closer than expected | zstd-19 or xz on a columnar delta layout may already capture bursts and row structure | This is the pilot. Apply the kill rule of P1 |
| Baseline mismatch | My U2 re-implementation may differ from the companion code in field widths or chunking | Run the companion code on the same windows before any claim |
| JPEG XE as the expected comparison | Part 1 is final. Reviewers will ask for it once the reference software is available | Track Part 3. Until then, use EVT3 and ECF sizes as the low-complexity reference |
| Dataset preprocessing and license | eTraM applied a filter when building label frames, and its license statements disagree | Use raw files. Confirm the license with the authors before redistributing derived data |
| Class split quality | Boxes at 30 Hz miss unlabeled movers (vegetation, shadows, reflections), which would be counted as noise | Hand-check a few windows. Use object-free intervals as the clean noise reference |

## 6. Inputs needed

1. The exact U2 specification or code, and its measured bits per event on the eTraM windows used in the companion project.
2. Access to raw eTraM train recordings with labels, and the list of recordings used in the companion project, so that the same windows are coded.
3. Confirmation that lossless may mean the multiset of events, with free order inside a timestamp.

## References and verification status

Status codes. **V**: title, authors, venue, year, and DOI or arXiv ID confirmed on a primary page (Crossref record, arXiv, publisher, CVF, or institutional repository). **V-bib**: same, but the content was not read in a primary source, so any number attributed to it here is from its abstract or second-hand. **U**: not verified, with the missing fields named. Only V and V-bib entries are in `references.bib`.

<!-- REFS-BEGIN -->
- **[bi2018]** Z. Bi, S. Dong, Y. Tian, T. Huang, "Spike Coding for Dynamic Vision Sensors," 2018 Data Compression Conference (DCC), pp. 117-126, 2018. DOI 10.1109/DCC.2018.00020. **V.** Crossref and author-hosted full text. Table 1 re-read for this brief.
- **[dong2019]** S. Dong, Z. Bi, Y. Tian, T. Huang, "Spike Coding for Dynamic Vision Sensor in Intelligent Driving," IEEE Internet of Things Journal, vol. 6, no. 1, pp. 60-71, 2019. DOI 10.1109/JIOT.2018.2872984. **V-bib.** Crossref. Primary full text not obtained. Content is second-hand via brites2025.
- **[khan2020]** N. Khan, K. Iqbal, M. G. Martini, "Lossless Compression of Data From Static and Mobile Dynamic Vision Sensors-Performance and Trade-Offs," IEEE Access, vol. 8, pp. 103149-103163, 2020. DOI 10.1109/ACCESS.2020.2996661. **V.** Crossref and publisher PDF in the Kingston repository (full text).
- **[iqbal2020]** K. Iqbal, N. Khan, M. G. Martini, "Performance Comparison of Lossless Compression Strategies for Dynamic Vision Sensor Data," ICASSP 2020 - IEEE International Conference on Acoustics, Speech and Signal Processing, pp. 4427-4431, 2020. DOI 10.1109/ICASSP40776.2020.9053178. **V-bib.** Crossref. Abstract level only.
- **[khan2021talven]** N. Khan, K. Iqbal, M. G. Martini, "Time-Aggregation-Based Lossless Video Encoding for Neuromorphic Vision Sensor Data," IEEE Internet of Things Journal, vol. 8, no. 1, pp. 596-609, 2021. DOI 10.1109/JIOT.2020.3007866. **V.** Crossref and accepted manuscript (full text).
- **[martini2022]** M. Martini, J. Adhuran, N. Khan, "Lossless Compression of Neuromorphic Vision Sensor Data Based on Point Cloud Representation," IEEE Access, vol. 10, pp. 121352-121364, 2022. DOI 10.1109/ACCESS.2022.3222330. **V-bib.** Crossref and DOAJ. Abstract level. The 49.4% figure is second-hand.
- **[adhuran2024]** J. Adhuran, N. Khan, M. G. Martini, "Lossless Encoding of Time-Aggregated Neuromorphic Vision Sensor Data Based on Point-Cloud Compression," Sensors, vol. 24, no. 5, art. 1382, 2024. DOI 10.3390/s24051382. **V.** Crossref and MDPI page (full text).
- **[schiopu2022spl]** I. Schiopu, R. C. Bilcu, "Lossless Compression of Event Camera Frames," IEEE Signal Processing Letters, vol. 29, pp. 1779-1783, 2022. DOI 10.1109/LSP.2022.3196599. **V-bib.** Crossref. Content second-hand.
- **[schiopu2022lsens]** I. Schiopu, R. C. Bilcu, "Low-Complexity Lossless Coding for Memory-Efficient Representation of Event Camera Frames," IEEE Sensors Letters, vol. 6, no. 11, pp. 1-4, 2022. DOI 10.1109/LSENS.2022.3216894. **V-bib.** Crossref. Content second-hand.
- **[schiopu2022sensors]** I. Schiopu, R. C. Bilcu, "Low-Complexity Lossless Coding of Asynchronous Event Sequences for Low-Power Chip Integration," Sensors, vol. 22, no. 24, art. 10014, 2022. DOI 10.3390/s222410014. **V.** Crossref and MDPI page. Abstract and method read. Experimental section not visible.
- **[schiopu2023cvprw]** I. Schiopu, R. C. Bilcu, "Entropy Coding-based Lossless Compression of Asynchronous Event Sequences," 2023 IEEE/CVF Conference on Computer Vision and Pattern Recognition Workshops (CVPRW), pp. 3923-3930, 2023. DOI 10.1109/CVPRW59228.2023.00407. **V.** Crossref and CVF open-access PDF (full text). Table 3 re-read for this brief.
- **[schiopu2023electronics]** I. Schiopu, R. C. Bilcu, "Memory-Efficient Fixed-Length Representation of Synchronous Event Frames for Very-Low-Power Chip Integration," Electronics, vol. 12, no. 10, art. 2302, 2023. DOI 10.3390/electronics12102302. **V.** Crossref and MDPI page (abstract).
- **[schiopu2024cadett]** I. Schiopu, R. C. Bilcu, "CADeTT: Context-Adaptive Deep-Trinary-Tree Lossless Compression of Event Camera Frames," IEEE Signal Processing Letters, vol. 31, pp. 3149-3153, 2024. DOI 10.1109/LSP.2024.3493801. **V-bib.** Crossref. Content not read.
- **[huang2023icip]** B. Huang, T. Ebrahimi, "Event Data Stream Compression Based on Point Cloud Representation," 2023 IEEE International Conference on Image Processing (ICIP), pp. 3120-3124, 2023. DOI 10.1109/ICIP49359.2023.10222287. **V.** Crossref and author PDF at EPFL (full text).
- **[wang2023jsen]** C. Wang, X. Wang, C. Yan, K. Ma, "Feature Representation and Compression Methods for Event-Based Data," IEEE Sensors Journal, vol. 23, no. 5, pp. 5109-5123, 2023. DOI 10.1109/JSEN.2023.3237754. **V-bib.** Crossref. Content second-hand.
- **[ding2024iscas]** Z. Ding, S. Wang, Y. Cai, X. Zeng, W. Li, M. Wang, "A Lossless Compression Algorithm with Hardware Implementation for Dynamic Vision Sensor," 2024 IEEE International Symposium on Circuits and Systems (ISCAS), pp. 1-5, 2024. DOI 10.1109/ISCAS58744.2024.10558375. **V-bib.** Crossref. Content not read.
- **[sezavar2024vcip]** A. Sezavar, C. Brites, J. Ascenso, "Learning-based Lossless Event Data Compression," 2024 IEEE International Conference on Visual Communications and Image Processing (VCIP), pp. 1-5, 2024. DOI 10.1109/VCIP63160.2024.10849853. arXiv:2411.03010. **V.** Crossref and arXiv (full text, Tables II and III).
- **[sezavar2024ism]** A. Sezavar, C. Brites, J. Ascenso, "Low Complexity Learning-based Lossless Event-based Compression," 2024 IEEE International Symposium on Multimedia (ISM), pp. 85-92, 2024. DOI 10.1109/ISM63611.2024.00018. arXiv:2411.07155. **V.** Crossref and arXiv (full text, Tables III and IV).
- **[sezavar2025spie]** A. Sezavar, C. Brites, J. Ascenso, T. Ebrahimi, "A learning-based lossless event data compression for computer vision applications," Applications of Digital Image Processing XLVIII, Proc. SPIE, vol. 13605, 2025. DOI 10.1117/12.3068095. **V-bib.** Crossref and EPFL Infoscience record. Abstract only.
- **[brites2025]** C. Brites, J. Ascenso, "Neuromorphic Vision Data Coding: Classifying and Reviewing the Literature," IEEE Access, vol. 13, pp. 14626-14657, 2025. DOI 10.1109/ACCESS.2025.3528375. arXiv:2405.07050. **V.** Crossref and arXiv (about 100k of 121k characters read).
- **[stumpp2024]** Daniel C. Stumpp, Himanshu Akolkar, Alan D. George, Ryad B. Benosman, "Flow-Based Visual Stream Compression for Event Cameras," IEEE Internet of Things Journal, vol. 11, no. 24, pp. 40229-40243, 2024. DOI 10.1109/JIOT.2024.3450428. arXiv:2403.08086. **V.** Crossref (re-checked for this brief). Technical details from the arXiv v1 full text.
- **[bairagi2022]** Arnob Kumar Bairagi, "Motion compensated compression for event-based cameras," University of Lethbridge, 2022. https://hdl.handle.net/10133/6444 **V.** University repository record and thesis PDF (full text, Tables 5.11 and 5.12 re-read for this brief). No DOI.
- **[delbruck2022csdvs]** T. Delbruck, C. Li, R. Graca, B. McReynolds, "Utility and Feasibility of a Center Surround Event Camera," 2022 IEEE International Conference on Image Processing (ICIP), pp. 381-385, 2022. DOI 10.1109/ICIP46576.2022.9897354. arXiv:2202.13076. **V.** Crossref and arXiv 2202.13076 (full text).
- **[gallego2018cmax]** G. Gallego, H. Rebecq, D. Scaramuzza, "A Unifying Contrast Maximization Framework for Event Cameras, With Applications to Motion, Depth, and Optical Flow Estimation," Proc. IEEE Conference on Computer Vision and Pattern Recognition (CVPR), pp. 3867-3876, 2018.  **V.** CVF open-access page (abstract). No DOI on that page.
- **[gallego2019focus]** G. Gallego, M. Gehrig, D. Scaramuzza, "Focus Is All You Need: Loss Functions for Event-Based Vision," Proc. IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR), pp. 12280-12289, 2019.  **V.** CVF open-access page (full text checked for any coding link). No DOI on that page.
- **[shiba2022secrets]** S. Shiba, Y. Aoki, G. Gallego, "Secrets of Event-Based Optical Flow," Computer Vision - ECCV 2022, Lecture Notes in Computer Science, pp. 628-645, 2022. DOI 10.1007/978-3-031-19797-0_36. arXiv:2207.10022. **V.** Crossref and arXiv 2207.10022 (abstract). Code repository fetched.
- **[banerjee2021icip]** S. Banerjee, Z. W. Wang, H. H. Chopp, O. Cossairt, A. K. Katsaggelos, "Lossy Event Compression Based on Image-Derived Quad Trees and Poisson Disk Sampling," 2021 IEEE International Conference on Image Processing (ICIP), pp. 2154-2158, 2021. DOI 10.1109/ICIP42928.2021.9506546. arXiv:2005.00974. **V.** Crossref and arXiv (ar5iv full text, comparison section cut off).
- **[banerjee2024tnnls]** Srutarshi Banerjee, Henry H. Chopp, Jianping Zhang, Zihao W. Wang, Peng Kang, Oliver Cossairt, Aggelos Katsaggelos, "A Joint Intensity-Neuromorphic Event Imaging System With Bandwidth-Limited Communication Channel," IEEE Transactions on Neural Networks and Learning Systems, vol. 35, no. 5, pp. 7216-7230, 2024. DOI 10.1109/TNNLS.2022.3214779. **V.** Crossref (checked for this brief). Content from the arXiv preprint 2105.14164, which has a different title.
- **[seleem2025access]** Abdelrahman Seleem, Andre F. R. Guarda, Nuno M. M. Rodrigues, Fernando Pereira, "A Double Deep Learning-Based Solution for Efficient Event Data Coding and Classification," IEEE Access, vol. 13, pp. 48703-48719, 2025. DOI 10.1109/ACCESS.2025.3551073. arXiv:2407.15531. **V.** Crossref and arXiv 2407.15531 (full text).
- **[seleem2026ojsp]** Abdelrahman Seleem, Andre F. R. Guarda, Nuno M. M. Rodrigues, Fernando Pereira, "Deep Learning-Based Event Data Coding: A Joint Spatiotemporal and Polarity Solution," IEEE Open Journal of Signal Processing, vol. 7, pp. 222-237, 2026. DOI 10.1109/OJSP.2026.3656104. arXiv:2502.03285. **V.** Crossref (checked for this brief). Content from arXiv 2502.03285 v2.
- **[rezaee2026]** Zahra Rezaee, Catarina Brites, Joao Ascenso, "Lossy Event Compression: From Event Stream Distortion to Task Performance," arXiv preprint arXiv:2608.28429, 2026.  **V.** arXiv page (re-checked for this brief) and full text. Preprint.
- **[li2023astsm]** Jianing Li, Yihua Fu, Siwei Dong, Zhaofei Yu, Tiejun Huang, Yonghong Tian, "Asynchronous Spatiotemporal Spike Metric for Event Cameras," IEEE Transactions on Neural Networks and Learning Systems, vol. 34, no. 4, pp. 1742-1753, 2023. DOI 10.1109/TNNLS.2021.3061122. **V-bib.** Crossref (checked for this brief). Content not read. Described through stumpp2024 and rezaee2026.
- **[hamara2024]** A. Hamara, B. Kilpatrick, A. Baratta, B. Kofink, A. C. Freeman, "Low-Latency Scalable Streaming for Event-Based Vision," arXiv preprint arXiv:2412.07889, 2024.  **V.** arXiv page and full text. Preprint, venue not stated.
- **[araghi2025]** H. Araghi, J. van Gemert, N. Tomen, "Making Every Event Count: Balancing Data Efficiency and Accuracy in Event Camera Subsampling," Proc. IEEE/CVF Conference on Computer Vision and Pattern Recognition Workshops (CVPRW), pp. 5044-5054, 2025. arXiv:2505.21187. **V.** CVF open-access page and arXiv 2505.21187 (full text). Code repository fetched.
- **[ogden2026]** Ronald Ogden, David Fridovich-Keil, Takashi Tanaka, "Rate-Distortion Analysis of Optically Passive Vision Compression," arXiv preprint arXiv:2602.02768, 2026.  **V.** arXiv page (re-checked for this brief) and full text. Preprint.
- **[khan2019bandwidth]** N. Khan, M. G. Martini, "Bandwidth Modeling of Silicon Retinas for Next Generation Visual Sensor Networks," Sensors, vol. 19, no. 8, art. 1751, 2019. DOI 10.3390/s19081751. **V.** MDPI page and publisher PDF (full text).
- **[miskowicz2006]** M. Miskowicz, "Send-On-Delta Concept: An Event-Based Data Reporting Strategy," Sensors, vol. 6, no. 1, pp. 49-63, 2006. DOI 10.3390/s6010049. **V.** MDPI page (full text).
- **[mark1981]** J. Mark, T. Todd, "A Nonuniform Sampling Approach to Data Compression," IEEE Transactions on Communications, vol. 29, no. 1, pp. 24-32, 1981. DOI 10.1109/TCOM.1981.1094872. **V-bib.** Institutional record with abstract.
- **[guan2007ciss]** K. M. Guan, A. C. Singer, "Opportunistic Sampling of Bursty Signals by Level-Crossing: An Information Theoretical Approach," 2007 41st Annual Conference on Information Sciences and Systems (CISS), pp. 701-707, 2007. DOI 10.1109/CISS.2007.4298396. **V-bib.** Institutional record with abstract.
- **[guo2022wiener]** Nian Guo, Victoria Kostina, "Optimal Causal Rate-Constrained Sampling of the Wiener Process," IEEE Transactions on Automatic Control, vol. 67, no. 4, pp. 1776-1791, 2022. DOI 10.1109/TAC.2021.3071953. arXiv:1909.01317. **V.** Caltech repository record and arXiv 1909.01317 (abstract re-read for this brief).
- **[rubin1974]** I. Rubin, "Information Rates and Data-Compression Schemes for Poisson Processes," IEEE Transactions on Information Theory, vol. 20, no. 2, pp. 200-210, 1974. DOI 10.1109/TIT.1974.1055195. **V-bib.** Crossref. Formula not confirmed.
- **[gallager1976]** R. Gallager, "Basic Limits on Protocol Information in Data Communication Networks," IEEE Transactions on Information Theory, vol. 22, no. 4, pp. 385-398, 1976. DOI 10.1109/TIT.1976.1055588. **V-bib.** Crossref. Formula not confirmed.
- **[verdu1996]** S. Verdu, "The Exponential Distribution in Information Theory," Problemy Peredachi Informatsii, vol. 32, no. 1, pp. 100-111, 1996. https://www.mathnet.ru/eng/ppi324 **V-bib.** Math-Net.Ru record (no DOI shown). The formula used here is as stated in coleman2008.
- **[coleman2008]** T. P. Coleman, N. Kiyavash, V. G. Subramanian, "The Rate-Distortion Function of a Poisson Process with a Queueing Distortion Measure," 2008 Data Compression Conference (DCC), pp. 63-72, 2008. DOI 10.1109/DCC.2008.92. **V.** Institutional record and author PDF (full text, Theorem 3.1 re-read for this brief).
- **[lapidoth2015]** A. Lapidoth, A. Malar, L. Wang, "Covering Point Patterns," IEEE Transactions on Information Theory, vol. 61, no. 9, pp. 4521-4533, 2015. DOI 10.1109/TIT.2015.2453946. arXiv:1102.3080. **V.** Crossref and arXiv 1102.3080 (abstract).
- **[shen2021itw]** H.-A. Shen, S. M. Moser, J.-P. Pfister, "Rate-Distortion Problems of the Poisson Process: a Group-Theoretic Approach," 2021 IEEE Information Theory Workshop (ITW), 2021. DOI 10.1109/ITW48936.2021.9611405. **V.** Author-hosted PDF. Pages not printed.
- **[shende2022]** Nirmal V. Shende, Aaron B. Wagner, "Functional Covering of Point Processes," arXiv preprint arXiv:2204.09188, 2022.  **V.** arXiv page (re-checked for this brief) and PDF. Preprint, journal version not confirmed.
- **[mcfadden1965]** J. A. McFadden, "The Entropy of a Point Process," Journal of the Society for Industrial and Applied Mathematics, vol. 13, no. 4, pp. 988-994, 1965. DOI 10.1137/0113066. **V-bib.** Crossref. Content as quoted in coleman2008.
- **[papangelou1978]** F. Papangelou, "On the Entropy Rate of Stationary Point Processes and Its Discrete Approximation," Zeitschrift fur Wahrscheinlichkeitstheorie und Verwandte Gebiete, vol. 44, no. 3, pp. 191-211, 1978. DOI 10.1007/BF00534210. **V-bib.** Springer page. Abstract not available. Content from general knowledge of the result.
- **[daley2004]** D. J. Daley, D. Vere-Jones, "Scoring Probability Forecasts for Point Processes: the Entropy Score and Information Gain," Journal of Applied Probability, vol. 41, no. A, pp. 297-312, 2004. DOI 10.1239/jap/1082552206. **V.** Cambridge page (abstract).
- **[koliander2018]** G. Koliander, D. Schuhmacher, F. Hlawatsch, "Rate-Distortion Theory of Finite Point Processes," IEEE Transactions on Information Theory, 2018. DOI 10.1109/TIT.2018.2829161. arXiv:1704.05758. **V-bib.** arXiv 1704.05758 with the DOI shown on the arXiv page. Volume and pages not confirmed.
- **[strong1998]** S. P. Strong, R. Koberle, R. R. de Ruyter van Steveninck, W. Bialek, "Entropy and Information in Neural Spike Trains," Physical Review Letters, vol. 80, no. 1, pp. 197-200, 1998. DOI 10.1103/PhysRevLett.80.197. **V-bib.** Crossref. Content from general knowledge of the method.
- **[paninski2003]** L. Paninski, "Estimation of Entropy and Mutual Information," Neural Computation, vol. 15, no. 6, pp. 1191-1253, 2003. DOI 10.1162/089976603321780272. **V-bib.** Crossref. Content from general knowledge of the method.
- **[kennel2005]** M. B. Kennel, J. Shlens, H. D. I. Abarbanel, E. J. Chichilnisky, "Estimating Entropy Rates with Bayesian Confidence Intervals," Neural Computation, vol. 17, no. 7, pp. 1531-1576, 2005. DOI 10.1162/0899766053723050. **V-bib.** Crossref. Content from general knowledge of the method.
- **[lichtsteiner2008]** P. Lichtsteiner, C. Posch, T. Delbruck, "A 128x128 120 dB 15 us Latency Asynchronous Temporal Contrast Vision Sensor," IEEE Journal of Solid-State Circuits, vol. 43, no. 2, pp. 566-576, 2008. DOI 10.1109/JSSC.2007.914337. **V-bib.** Crossref. Full text not read.
- **[gallego2022survey]** G. Gallego, T. Delbruck, G. Orchard, C. Bartolozzi, B. Taba, A. Censi, S. Leutenegger, A. J. Davison, J. Conradt, K. Daniilidis, D. Scaramuzza, "Event-Based Vision: A Survey," IEEE Transactions on Pattern Analysis and Machine Intelligence, vol. 44, no. 1, pp. 154-180, 2022. DOI 10.1109/TPAMI.2020.3008413. arXiv:1904.08405. **V.** Crossref and arXiv 1904.08405 (full text).
- **[hu2021v2e]** Y. Hu, S.-C. Liu, T. Delbruck, "v2e: From Video Frames to Realistic DVS Events," 2021 IEEE/CVF Conference on Computer Vision and Pattern Recognition Workshops (CVPRW), pp. 1312-1321, 2021. DOI 10.1109/CVPRW53098.2021.00144. arXiv:2006.07722. **V.** Crossref and arXiv 2006.07722 (full text). Code repository fetched.
- **[lin2022voltmeter]** S. Lin, Y. Ma, Z. Guo, B. Wen, "DVS-Voltmeter: Stochastic Process-Based Event Simulator for Dynamic Vision Sensors," Computer Vision - ECCV 2022, Lecture Notes in Computer Science, pp. 578-593, 2022. DOI 10.1007/978-3-031-20071-7_34. **V.** Crossref and ECVA PDF (full text). Code repository fetched.
- **[gu2021stppp]** C. Gu, E. Learned-Miller, D. Sheldon, G. Gallego, P. Bideau, "The Spatio-Temporal Poisson Point Process: A Simple Model for the Alignment of Event Camera Data," Proc. IEEE/CVF International Conference on Computer Vision (ICCV), pp. 13495-13504, 2021. DOI 10.1109/ICCV48922.2021.01324. arXiv:2106.06887. **V.** CVF page and arXiv 2106.06887 (full text). Code repository fetched.
- **[hashimoto2026]** K. Hashimoto, K. Serizawa, M. Kishida, "Receding-Horizon Maximum-Likelihood Estimation of Neural-ODE Dynamics and Thresholds from Event Cameras," arXiv preprint arXiv:2603.05011, 2026.  **V.** arXiv page and PDF. Preprint.
- **[baldwin2020]** R. W. Baldwin, M. Almatrafi, V. Asari, K. Hirakawa, "Event Probability Mask (EPM) and Event Denoising Convolutional Neural Network (EDnCNN) for Neuromorphic Cameras," Proc. IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR), pp. 1701-1710, 2020. arXiv:2003.08282. **V.** CVF page and arXiv 2003.08282 (full text). DOI not confirmed.
- **[joubert2021]** D. Joubert, A. Marcireau, N. Ralph, A. Jolley, A. van Schaik, G. Cohen, "Event Camera Simulator Improvements via Characterized Parameters," Frontiers in Neuroscience, vol. 15, art. 702765, 2021. DOI 10.3389/fnins.2021.702765. **V.** Crossref and Frontiers full text. Code repository fetched.
- **[graca2025model]** R. Graca, T. Delbruck, "Towards a Physically Realistic Computationally Efficient DVS Pixel Model," arXiv preprint arXiv:2505.07386, 2025.  **V.** arXiv page and PDF. Workshop DOI not confirmed.
- **[guo2023denoise]** S. Guo, T. Delbruck, "Low Cost and Latency Event Camera Background Activity Denoising," IEEE Transactions on Pattern Analysis and Machine Intelligence, vol. 45, no. 1, pp. 785-795, 2023. DOI 10.1109/TPAMI.2022.3152999. **V-bib.** Crossref. Full text not read.
- **[riosnavarro2023]** A. Rios-Navarro, S. Guo, G. Abarajithan, K. Vijayakumar, A. Linares-Barranco, T. Aarrestad, R. Kastner, T. Delbruck, "Within-Camera Multilayer Perceptron DVS Denoising," 2023 IEEE/CVF Conference on Computer Vision and Pattern Recognition Workshops (CVPRW), pp. 3933-3942, 2023. DOI 10.1109/CVPRW59228.2023.00409. arXiv:2304.07543. **V.** DOI metadata and arXiv 2304.07543 (full text).
- **[mcreynolds2023pairs]** Brian McReynolds, Rui Graca, Tobi Delbruck, "Exploiting Alternating DVS Shot Noise Event Pair Statistics to Reduce Background Activity," arXiv preprint arXiv:2304.03494, 2023.  **V.** arXiv page (re-checked for this brief) and PDF. The 90% figure is from the full text (Sec. III), not the abstract.
- **[graca2023tutorial]** R. Graca, B. McReynolds, T. Delbruck, "Shining Light on the DVS Pixel: A Tutorial and Discussion about Biasing and Optimization," 2023 IEEE/CVF Conference on Computer Vision and Pattern Recognition Workshops (CVPRW), pp. 4045-4053, 2023. DOI 10.1109/CVPRW59228.2023.00423. **V.** Crossref and CVF PDF (full text).
- **[graca2023limits]** R. Graca, B. McReynolds, T. Delbruck, "Optimal Biasing and Physical Limits of DVS Event Noise," 2023 International Image Sensor Workshop (IISW), 2023. DOI 10.60928/dlpf-irjd. arXiv:2304.04019. **V.** IISS page and arXiv 2304.04019 (full text).
- **[cao2025noise2image]** R. Cao, D. Galor, A. Kohli, J. L. Yates, L. Waller, "Noise2Image: Noise-Enabled Static Scene Recovery for Event Cameras," Optica, vol. 12, no. 1, art. 46, 2025. DOI 10.1364/OPTICA.538916. arXiv:2404.01298. **V.** arXiv 2404.01298 (authors, DOI, full text) and DOI metadata. End page not confirmed.
- **[mcreynolds2025amos]** B. McReynolds, R. Oliver, P. McMahon-Crabtree, M. Zolnowski, T. Delbruck, "Bias and Denoising Techniques to Improve Dim RSO Detection by up to 2.9x with an Event-based Vision Sensor," Advanced Maui Optical and Space Surveillance Technologies Conference (AMOS), 2025. https://amostech.com/TechnicalPapers/2025/SDA_Systems-and-Instrumentation/McReynolds1.pdf **V.** Conference PDF. No DOI exists.
- **[mcreynolds2024scurve]** B. McReynolds, R. Graca, L. Kulesza, P. McMahon-Crabtree, "Re-Interpreting the Step-Response Probability Curve to Extract Fundamental Physical Parameters of Event-based Vision Sensors," arXiv preprint arXiv:2404.07656, 2024.  **V.** arXiv page and PDF. Venue not confirmed.
- **[oliver2025]** R. Oliver, B. McReynolds, D. Savransky, "Event-Based Sensor Noise Modeling for Space-Based Space Domain Awareness," The Journal of the Astronautical Sciences, vol. 72, no. 5, art. 46, 2025. DOI 10.1007/s40295-025-00523-5. **V.** Springer open-access page (full text).
- **[zhao2025date]** Q. Zhao, Y. Ji, J. Wang, J. Wu, G. Shi, "Simultaneous Denoising and Compression for DVS with Partitioned Cache-Like Spatiotemporal Filter," 2025 Design, Automation and Test in Europe Conference (DATE), pp. 1-7, 2025. DOI 10.23919/DATE64628.2025.10992696. **V.** Crossref and author PDF.
- **[shiba2025noise]** S. Shiba, Y. Aoki, G. Gallego, "Simultaneous Motion And Noise Estimation with Event Cameras," arXiv preprint arXiv:2504.04029, ICCV 2025, 2025.  **V.** arXiv page (lists ICCV 2025) and full text. Proceedings pages not confirmed.
- **[lazar2004]** A. A. Lazar, L. T. Toth, "Perfect Recovery and Sensitivity Analysis of Time Encoded Bandlimited Signals," IEEE Transactions on Circuits and Systems I: Regular Papers, vol. 51, no. 10, pp. 2060-2073, 2004. DOI 10.1109/TCSI.2004.835026. **V-bib.** Crossref. Full text not read.
- **[martineznuevo2019]** P. Martinez-Nuevo, H.-Y. Lai, A. V. Oppenheim, "Delta-Ramp Encoder for Amplitude Sampling and Its Interpretation as Time Encoding," IEEE Transactions on Signal Processing, vol. 67, no. 10, pp. 2516-2527, 2019. DOI 10.1109/TSP.2019.2904027. arXiv:1802.04672. **V.** arXiv 1802.04672 and DOI metadata (abstract).
- **[adam2022]** K. Adam, A. Scholefield, M. Vetterli, "Asynchrony Increases Efficiency: Time Encoding of Videos and Low-Rank Signals," IEEE Transactions on Signal Processing, vol. 70, pp. 105-116, 2022. DOI 10.1109/TSP.2021.3133709. arXiv:2104.14511. **V.** arXiv 2104.14511 and DOI metadata (abstract).
- **[adam2022events]** K. Adam, A. Scholefield, M. Vetterli, "How Asynchronous Events Encode Video," arXiv preprint arXiv:2206.04341, 2022.  **V.** arXiv page and PDF. Preprint, venue not confirmed.
- **[naaman2021quant]** H. Naaman, N. I. Bernardo, A. Cohen, Y. C. Eldar, "Time Encoding Quantization of Bandlimited and Finite-Rate-of-Innovation Signals," arXiv preprint arXiv:2110.01928, 2021.  **V.** arXiv page and v2 PDF. Journal version not confirmed.
- **[boahen2000]** K. A. Boahen, "Point-to-Point Connectivity Between Neuromorphic Chips Using Address Events," IEEE Transactions on Circuits and Systems II: Analog and Digital Signal Processing, vol. 47, no. 5, pp. 416-434, 2000. DOI 10.1109/82.842110. **V-bib.** DOI metadata. Content not read.
- **[chen2023tccn]** J. Chen, N. Skatchkovsky, O. Simeone, "Neuromorphic Wireless Cognition: Event-Driven Semantic Communications for Remote Inference," IEEE Transactions on Cognitive Communications and Networking, vol. 9, no. 2, pp. 252-265, 2023. DOI 10.1109/TCCN.2023.3236940. arXiv:2206.06047. **V.** arXiv 2206.06047 and DOI metadata (abstract).
- **[ke2024dib]** Y. Ke, Z. Utkovski, M. Heshmati, O. Simeone, J. Dommel, S. Stanczak, "Neuromorphic Wireless Device-Edge Co-Inference via the Directed Information Bottleneck," arXiv preprint arXiv:2404.01804, 2024.  **V.** arXiv page (abstract). Preprint.
- **[verma2024etram]** Aayush Atul Verma, Bharatesh Chakravarthi, Arpitsinh Vaghela, Hua Wei, Yezhou Yang, "eTraM: Event-based Traffic Monitoring Dataset," Proc. IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR), pp. 22637-22646, 2024. arXiv:2403.19976. **V.** CVF page, arXiv 2403.19976 (re-checked for this brief), project site, and dataset documentation. No DOI on the CVF page.
- **[gehrig2021dsec]** M. Gehrig, W. Aarents, D. Gehrig, D. Scaramuzza, "DSEC: A Stereo Event Camera Dataset for Driving Scenarios," IEEE Robotics and Automation Letters, vol. 6, no. 3, pp. 4947-4954, 2021. DOI 10.1109/LRA.2021.3068942. arXiv:2103.06011. **V.** arXiv 2103.06011, DOI metadata, dataset site (full text).
- **[detournemire2020]** P. de Tournemire, D. Nitti, E. Perot, D. Migliore, A. Sironi, "A Large Scale Event-based Detection Dataset for Automotive," arXiv preprint arXiv:2001.08499, 2020.  **V.** arXiv page and PDF, dataset page.
- **[perot2020]** E. Perot, P. de Tournemire, D. Nitti, J. Masci, A. Sironi, "Learning to Detect Objects with a 1 Megapixel Event Camera," Advances in Neural Information Processing Systems 33 (NeurIPS 2020), pp. 16639-16652, 2020. arXiv:2009.13436. **V.** NeurIPS proceedings page and arXiv 2009.13436 (full text). No DOI.
- **[mueggler2017]** E. Mueggler, H. Rebecq, G. Gallego, T. Delbruck, D. Scaramuzza, "The Event-Camera Dataset and Simulator: Event-based Data for Pose Estimation, Visual Odometry, and SLAM," The International Journal of Robotics Research, vol. 36, no. 2, pp. 142-149, 2017. DOI 10.1177/0278364917691115. arXiv:1610.08336. **V.** arXiv 1610.08336, DOI metadata, dataset page (full text).
- **[chaney2023m3ed]** K. Chaney, F. Cladera, Z. Wang, A. Bisulco, M. A. Hsieh, C. Korpela, V. Kumar, C. J. Taylor, K. Daniilidis, "M3ED: Multi-Robot, Multi-Sensor, Multi-Environment Event Dataset," Proc. IEEE/CVF Conference on Computer Vision and Pattern Recognition Workshops (CVPRW), pp. 4016-4023, 2023.  **V.** CVF page and PDF, dataset site. DOI not confirmed.
- **[zhu2018mvsec]** A. Z. Zhu, D. Thakur, T. Ozaslan, B. Pfrommer, V. Kumar, K. Daniilidis, "The Multivehicle Stereo Event Camera Dataset: An Event Camera Dataset for 3D Perception," IEEE Robotics and Automation Letters, vol. 3, no. 3, pp. 2032-2039, 2018. DOI 10.1109/LRA.2018.2800793. arXiv:1801.10202. **V.** arXiv 1801.10202, DOI metadata, dataset site.
- **[jpegxe2026press]** JPEG Committee, "112th Meeting - Leiria, Portugal - JPEG XE becomes an International Standard," Press release, October 7, 2026, 2026. https://jpeg.org/items/20261007_press.html **V.** Web page fetched October 8, 2026 (re-read for this brief).
- **[prophesee_evt]** Prophesee, "Metavision SDK Documentation: EVT 2.0 and EVT 3.0 Encoding Formats," Online documentation, 2026. https://docs.prophesee.ai/stable/data/encoding_formats/evt3.html **V.** Vendor documentation pages fetched October 8, 2026 (EVT 2.0 and EVT 3.0).
- **[prophesee_esp]** Prophesee, "Metavision SDK Documentation: Event Signal Processing," Online documentation, 2026. https://docs.prophesee.ai/stable/hw/manuals/esp.html **V.** Vendor documentation page fetched October 8, 2026.
- **[prophesee_ecf]** Prophesee, "HDF5 ECF Codec (Event Compression Format)," Software repository, 2026. https://github.com/prophesee-ai/hdf5_ecf **V.** Repository and codec source fetched October 8, 2026.
- **[dsec_format]** Robotics, University of Zurich Perception Group, "DSEC Data Format," Online documentation, 2026. https://dsec.ifi.uzh.ch/data-format/ **V.** Dataset documentation page fetched October 8, 2026.

### Not verified (not in `references.bib`)

- **U.** A. S. Bedekar, "On the information about message arrival times required for in-order decoding," Proc. IEEE ISIT, p. 227. Year not confirmed (printed with a typo in coleman2008). Not used for any number.
- **U.** T. Finateu et al., "A 1280x720 Back-Illuminated Stacked Temporal Contrast Event-Based Vision Sensor with 4.86 um Pixels, 1.066 GEPS Readout, Programmable Event-Rate Controller and Compressive Data-Formatting Pipeline," ISSCC 2020. Seen only on an index page. DOI not confirmed (a Crossref title query returned unrelated records).
- **U.** B. Huang, D. Lazzarotto, T. Ebrahimi, "Evaluation of the impact of lossy compression on event camera-based computer vision tasks," Proc. SPIE 12674, 2023. Publisher page not reachable. DOI 10.1117/12.2676419 seen only on the EPFL repository record.
- **U.** M. Martini et al., "Comparison of point-cloud construction strategies for the lossless compression of event camera data," TechRxiv, 2025, DOI 10.36227/techrxiv.174535660.05715604/v1. Bibliographic record seen in Crossref. Content not accessible.
- **U.** A. Junco de Haas, "Event Camera Lossless Compression for Satellite Applications," Master's thesis, TU Munich. Year unclear (2024 or 2025), no DOI.
- **U.** Hasssan et al., 2022, low-precision sparse autoencoder for DVS compression. Known only through brites2025. Title, authors, and venue not confirmed.
- **U.** G. Cohen et al., "Spatial and Temporal Downsampling in Event-Based Visual Classification," IEEE TNNLS, 2018. Seen only on a university portal.
- **U.** JPEG XE Common Test Conditions (WG1 N100827, N100891, N101324) and Call for Proposals (N100888). Listed on jpeg.org. The documents could not be opened, so the anchor list (lz4, bzip2, 7z) is second-hand.
- **U.** Inter-cube prediction result of dong2019 (CR 2.64 vs 2.65 on DDD17). Second-hand from brites2025. The primary full text was not obtained.
- **U.** Entropy values in Fig. 9 of khan2020. Only the surrounding text was readable.
- **U.** Rate and noise statements about the IMX636 readout (timestamp granularity, event rate controller behavior under load). Not found in a primary source. Treated as an open check in Section 5.
<!-- REFS-END -->
