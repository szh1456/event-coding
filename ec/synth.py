"""Synthetic rigid-translation events with known ground truth, for gates.

A rigid object carries ``n_points`` scene points. Its center moves at constant
velocity ``v`` (px/s). A point emits one event each time its position enters a new
pixel along either axis, at the crossing time plus Gaussian timing jitter, at the
pixel it enters. Uniform Poisson noise events can be added. Box annotations are
produced at 30 Hz in the eTraM field layout, optionally with label noise.

This is a geometry fixture, not a sensor model: no contrast threshold, no
refractory period, no bandwidth. It fixes what "ideal translation" means so that an
estimator can be checked against known velocity, jitter and noise share.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

BOX_DTYPE = np.dtype([("t", "<u8"), ("x", "<f4"), ("y", "<f4"), ("w", "<f4"), ("h", "<f4"),
                      ("class_id", "u1"), ("track_id", "<u4"), ("class_confidence", "<f4")])
FRAME_US = 1_000_000 / 30.0


@dataclass(frozen=True)
class SynthScene:
    t: np.ndarray        # int64 microseconds, nondecreasing
    x: np.ndarray        # int32
    y: np.ndarray        # int32
    p: np.ndarray        # uint8
    src: np.ndarray      # int32, scene point index, or -1 for a noise event
    boxes: np.ndarray    # BOX_DTYPE
    width: int
    height: int
    v: tuple
    jitter_us: float


def _crossings(p0: float, va: float, duration_s: float):
    """Times at which ``p0 + va t`` crosses a half-integer, for t in (0, duration)."""
    if va == 0.0:
        return np.zeros(0)
    a, b = p0, p0 + va * duration_s
    lo, hi = (a, b) if a < b else (b, a)
    n = np.arange(np.ceil(lo - 0.5), np.floor(hi - 0.5) + 1)
    tc = (n + 0.5 - p0) / va
    return tc[(tc > 0) & (tc < duration_s)]


def rigid_translation(width=320, height=240, n_points=400, box_wh=(60.0, 40.0), c0=(40.0, 120.0),
                      v=(200.0, 0.0), duration_s=1.0, jitter_us=0.0, noise_rate_hz=0.0,
                      label_noise_px=0.0, seed=0, track_id=1, class_id=1) -> SynthScene:
    rng = np.random.default_rng(seed)
    w, h = box_wh
    ox = rng.uniform(-w / 2 + 1, w / 2 - 1, n_points)
    oy = rng.uniform(-h / 2 + 1, h / 2 - 1, n_points)
    pol = rng.integers(0, 2, n_points)
    T, X, Y, P, S = [], [], [], [], []
    eps = 1e-9
    for k in range(n_points):
        px0, py0 = c0[0] + ox[k], c0[1] + oy[k]
        tc = np.concatenate((_crossings(px0, v[0], duration_s), _crossings(py0, v[1], duration_s)))
        if tc.size == 0:
            continue
        xs = np.rint(px0 + v[0] * (tc + eps * np.sign(v[0] or 1.0))).astype(np.int64)
        ys = np.rint(py0 + v[1] * (tc + eps * np.sign(v[1] or 1.0))).astype(np.int64)
        tt = tc * 1e6 + (rng.normal(0.0, jitter_us, tc.size) if jitter_us > 0 else 0.0)
        T.append(tt); X.append(xs); Y.append(ys)
        P.append(np.full(tc.size, pol[k])); S.append(np.full(tc.size, k))
    t = np.concatenate(T); x = np.concatenate(X); y = np.concatenate(Y)
    p = np.concatenate(P); s = np.concatenate(S)
    if noise_rate_hz > 0:
        n_noise = rng.poisson(noise_rate_hz * width * height * duration_s)
        t = np.concatenate((t, rng.uniform(0, duration_s * 1e6, n_noise)))
        x = np.concatenate((x, rng.integers(0, width, n_noise)))
        y = np.concatenate((y, rng.integers(0, height, n_noise)))
        p = np.concatenate((p, rng.integers(0, 2, n_noise)))
        s = np.concatenate((s, np.full(n_noise, -1)))
    t = np.rint(t).astype(np.int64)
    ok = (x >= 0) & (x < width) & (y >= 0) & (y < height) & (t >= 0) & (t < int(duration_s * 1e6))
    t, x, y, p, s = t[ok], x[ok], y[ok], p[ok], s[ok]
    o = np.argsort(t, kind="stable")
    n_frames = int(np.floor(duration_s * 1e6 / FRAME_US)) + 1
    boxes = np.zeros(n_frames, dtype=BOX_DTYPE)
    tf = np.arange(n_frames) * FRAME_US
    jit = rng.normal(0.0, label_noise_px, (n_frames, 2)) if label_noise_px > 0 else np.zeros((n_frames, 2))
    boxes["t"] = np.rint(tf).astype(np.uint64)
    boxes["x"] = c0[0] + v[0] * tf * 1e-6 - w / 2 + jit[:, 0]
    boxes["y"] = c0[1] + v[1] * tf * 1e-6 - h / 2 + jit[:, 1]
    boxes["w"], boxes["h"] = w, h
    boxes["class_id"], boxes["track_id"], boxes["class_confidence"] = class_id, track_id, 1.0
    return SynthScene(t[o], x[o].astype(np.int32), y[o].astype(np.int32), p[o].astype(np.uint8),
                      s[o].astype(np.int32), boxes, width, height, tuple(v), float(jitter_us))
