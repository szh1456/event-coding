"""eTraM eight-class box annotations: loading, tracks, box interpolation.

File format (``*_bbox.npy``, structured array, read with ``allow_pickle=False``):
fields ``t, x, y, w, h, class_id, track_id, class_confidence``; 30 Hz; ``t`` in
microseconds. A track is one ``track_id`` within one recording. Nothing is
re-tracked or merged.

The box convention assumed here is ``(x, y)`` = top-left corner, in pixels, on the
event clock with zero offset. Directive 001 checks both assumptions on data before
anything else uses them.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

FRAME_US = 1_000_000 / 30.0


def find_annotation(ann_dir, recording_id: str):
    """``train_day_0001_td`` -> ``ann_dir/train_day_0001_bbox.npy``. ``ann_dir`` is the directory that holds the
    file (the train subdirectory of ``docs/DATA.md``); nothing is searched or listed."""
    stem = recording_id[:-3] if recording_id.endswith("_td") else recording_id
    path = Path(ann_dir) / f"{stem}_bbox.npy"
    if not path.is_file():
        raise FileNotFoundError(f"{recording_id}: {path} not found")
    return str(path)


def load_boxes(path) -> np.ndarray:
    return np.load(path, allow_pickle=False)


@dataclass(frozen=True)
class Track:
    track_id: int
    class_id: int
    t: np.ndarray     # int64, strictly increasing, microseconds
    x: np.ndarray     # float64, top-left
    y: np.ndarray
    w: np.ndarray
    h: np.ndarray

    @property
    def t_first(self) -> int:
        return int(self.t[0])

    @property
    def t_last(self) -> int:
        return int(self.t[-1])

    def box(self, t_us):
        """Linearly interpolated ``(x, y, w, h)`` at times inside the track's life."""
        tq = np.asarray(t_us, dtype=np.float64)
        tt = self.t.astype(np.float64)
        return tuple(np.interp(tq, tt, a) for a in (self.x, self.y, self.w, self.h))

    def center(self, t_us):
        x, y, w, h = self.box(t_us)
        return x + 0.5 * w, y + 0.5 * h

    def velocity(self, t_us: float, span_us: float):
        """Mean center velocity over ``[t - span, t]`` in px/s, from the interpolated boxes."""
        t0 = max(float(self.t_first), float(t_us) - span_us)
        cx1, cy1 = self.center(float(t_us))
        cx0, cy0 = self.center(t0)
        d = (float(t_us) - t0) * 1e-6
        if d <= 0:
            return 0.0, 0.0
        return (float(cx1) - float(cx0)) / d, (float(cy1) - float(cy0)) / d


def tracks(boxes: np.ndarray) -> list[Track]:
    """One ``Track`` per ``track_id``. Duplicate timestamps inside a track keep the first box."""
    out = []
    if len(boxes) == 0:
        return out
    tid = boxes["track_id"].astype(np.int64)
    for k in np.unique(tid):
        b = boxes[tid == k]
        o = np.argsort(b["t"].astype(np.int64), kind="stable")
        b = b[o]
        t = b["t"].astype(np.int64)
        keep = np.concatenate(([True], np.diff(t) > 0))
        b, t = b[keep], t[keep]
        cls = np.bincount(b["class_id"].astype(np.int64)).argmax()
        out.append(Track(int(k), int(cls), t, b["x"].astype(np.float64), b["y"].astype(np.float64),
                         b["w"].astype(np.float64), b["h"].astype(np.float64)))
    return out


def in_box_mask(track: Track, t_us, x, y, margin_px: float = 0.0) -> np.ndarray:
    """Events inside the interpolated box of ``track`` (dilated by ``margin_px``) and inside its life."""
    t_us = np.asarray(t_us, dtype=np.int64)
    alive = (t_us >= track.t_first) & (t_us <= track.t_last)
    bx, by, bw, bh = track.box(t_us)
    xf = np.asarray(x, dtype=np.float64)
    yf = np.asarray(y, dtype=np.float64)
    return (alive & (xf >= bx - margin_px) & (xf <= bx + bw + margin_px)
            & (yf >= by - margin_px) & (yf <= by + bh + margin_px))
