"""event-coding: information coding of event-camera streams.

Modules
    baseline   the companion project's reader and U2 + zstd-1 payload (pinned copies), plus generic layouts
    coders     prequential code-length models (time, rate map, context coder C1)
    arith      second implementation of C1 with a real arithmetic coder, for validity checks
    synth      synthetic rigid-translation event generator with known ground truth (gates)
    annotations  eTraM box annotations: loading, tracks, box interpolation
    motion     motion predictability of in-box events (template, warp, coverage, timing residual)
"""
