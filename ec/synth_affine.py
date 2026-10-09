"""Synthetic expanding rigid object, for the gate of directive 004.

As ``ec.synth.rigid_translation``, with one addition: the object grows at a constant
rate. A scene point at offset ``o`` from the center sits at
``c0 + v t + (1 + expand_rate * t) o``, so it moves at its own constant velocity
``v + expand_rate * o``, and the box grows by the factor ``1 + expand_rate * t``.
This is an object that approaches the camera. Between two times the motion of the
points is a translation and a scale about the box center, an affine map.
"""
from __future__ import annotations

import numpy as np

from .synth import BOX_DTYPE, FRAME_US, SynthScene, _crossings


def expanding_translation(width=320, height=240, n_points=400, box_wh=(60.0, 40.0), c0=(40.0, 120.0),
                          v=(200.0, 0.0), expand_rate=0.0, duration_s=1.0, jitter_us=0.0, seed=0,
                          track_id=1, class_id=1) -> SynthScene:
    rng = np.random.default_rng(seed)
    w, h = box_wh
    ox = rng.uniform(-w / 2 + 1, w / 2 - 1, n_points)
    oy = rng.uniform(-h / 2 + 1, h / 2 - 1, n_points)
    pol = rng.integers(0, 2, n_points)
    T, X, Y, P, S = [], [], [], [], []
    eps = 1e-9
    for k in range(n_points):
        px0, py0 = c0[0] + ox[k], c0[1] + oy[k]
        vx, vy = v[0] + expand_rate * ox[k], v[1] + expand_rate * oy[k]
        tc = np.concatenate((_crossings(px0, vx, duration_s), _crossings(py0, vy, duration_s)))
        if tc.size == 0:
            continue
        xs = np.rint(px0 + vx * (tc + eps * np.sign(vx or 1.0))).astype(np.int64)
        ys = np.rint(py0 + vy * (tc + eps * np.sign(vy or 1.0))).astype(np.int64)
        tt = tc * 1e6 + (rng.normal(0.0, jitter_us, tc.size) if jitter_us > 0 else 0.0)
        T.append(tt); X.append(xs); Y.append(ys)
        P.append(np.full(tc.size, pol[k])); S.append(np.full(tc.size, k))
    t = np.rint(np.concatenate(T)).astype(np.int64)
    x = np.concatenate(X); y = np.concatenate(Y); p = np.concatenate(P); s = np.concatenate(S)
    ok = (x >= 0) & (x < width) & (y >= 0) & (y < height) & (t >= 0) & (t < int(duration_s * 1e6))
    t, x, y, p, s = t[ok], x[ok], y[ok], p[ok], s[ok]
    o = np.argsort(t, kind="stable")
    n_frames = int(np.floor(duration_s * 1e6 / FRAME_US)) + 1
    boxes = np.zeros(n_frames, dtype=BOX_DTYPE)
    tf = np.arange(n_frames) * FRAME_US
    g = 1.0 + expand_rate * tf * 1e-6
    boxes["t"] = np.rint(tf).astype(np.uint64)
    boxes["x"] = c0[0] + v[0] * tf * 1e-6 - g * w / 2
    boxes["y"] = c0[1] + v[1] * tf * 1e-6 - g * h / 2
    boxes["w"], boxes["h"] = g * w, g * h
    boxes["class_id"], boxes["track_id"], boxes["class_confidence"] = class_id, track_id, 1.0
    return SynthScene(t[o], x[o].astype(np.int32), y[o].astype(np.int32), p[o].astype(np.uint8),
                      s[o].astype(np.int32), boxes, width, height, tuple(v), float(jitter_us))
