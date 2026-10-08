"""eTraM reader and format probe (M1a).

Authoritative facts, from the eTraM dataset documentation (Beta, 20 Apr 2024)
and the dataset's own RVT baseline in ``rvt_eTram/``:

* sensor: Prophesee EVK4 HD, **1280 x 720** px; ``config/dataset/etrap.yaml``
  carries ``resolution_hw: [720, 1280]``;
* sequences are provided in RAW (Prophesee EVT) and **HDF5**; the HDF5 layout is
  ``/events/{x,y,p,t}`` with optional ``/events/{height,width}`` scalars;
* ``t`` is in **microseconds** (the baseline converts its millisecond settings
  with ``* 1000`` before comparing against ``t``);
* recordings are cut into 3-5 minute chunks; the RAW set is about 150 GB;
* polarity may be stored as ``{0,1}`` or as ``{-1,1}``: the baseline applies
  ``np.clip(p, a_min=0)``, which folds ``-1`` onto ``0``;
* ``t`` is **not** guaranteed nondecreasing: the baseline clamps each decreasing
  timestamp to its predecessor.

This module reads the file, reports what it actually found, and normalizes only
what it can normalize losslessly.  Anything it cannot is counted and surfaced,
never silently repaired.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

import numpy as np

#: Nominal eTraM sensor geometry; verified per file, never assumed.
ETRAM_WIDTH = 1280
ETRAM_HEIGHT = 720

EVENTS_GROUP = "events"
REQUIRED_KEYS = ("x", "y", "p", "t")


class EtramFormatError(ValueError):
    """The file does not match the documented eTraM HDF5 layout."""


@dataclass(frozen=True)
class EtramProbe:
    """What one recording actually contains.  Every field is measured."""

    path: str
    n_events: int
    width: int
    height: int
    width_source: str            # "file" or "assumed"
    height_source: str
    dtypes: dict[str, str]
    t_first_us: int
    t_last_us: int
    duration_s: float
    t_nondecreasing: bool
    n_time_inversions: int
    polarity_values: list[int]
    polarity_encoding: str       # "0/1", "-1/1", "single", or "unexpected"
    x_min: int
    x_max: int
    y_min: int
    y_max: int
    n_x_over_11_bits: int
    n_y_over_10_bits: int
    fits_frozen_record: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Events:
    """Normalized events: ``t`` in microseconds, ``p`` in ``{0, 1}``."""

    t_us: np.ndarray   # int64, nondecreasing
    x: np.ndarray      # uint16
    y: np.ndarray      # uint16
    p: np.ndarray      # uint8, 0 or 1
    n_time_inversions_clamped: int
    n_coord_msb_repaired: int = 0     # bit-15 flips cleared; see read_events

    def __len__(self) -> int:
        return int(self.t_us.size)


def _open(path: Path):
    import h5py

    if path.suffix != ".h5":
        raise EtramFormatError(f"{path}: expected an .h5 file; RAW is not read at M1a")
    f = h5py.File(str(path), "r")
    if EVENTS_GROUP not in f:
        f.close()
        raise EtramFormatError(f"{path}: no '/{EVENTS_GROUP}' group")
    grp = f[EVENTS_GROUP]
    missing = [k for k in REQUIRED_KEYS if k not in grp]
    if missing:
        f.close()
        raise EtramFormatError(f"{path}: '/{EVENTS_GROUP}' is missing {missing}")
    return f, grp


def probe(path: str | Path, *, sample: int | None = None) -> EtramProbe:
    """Measure one recording without committing to any interpretation.

    ``sample`` limits the number of leading events inspected for the range and
    polarity statistics; timestamps are always read in full, because the
    monotonicity question concerns the whole file.
    """
    path = Path(path)
    f, grp = _open(path)
    try:
        n = int(grp["t"].shape[0])
        t = np.asarray(grp["t"][:], dtype=np.int64)
        inversions = int(np.count_nonzero(np.diff(t) < 0)) if n > 1 else 0

        m = n if sample is None else min(n, sample)
        x = np.asarray(grp["x"][:m])
        y = np.asarray(grp["y"][:m])
        p = np.asarray(grp["p"][:m])

        w, w_src = (int(grp["width"][()]), "file") if "width" in grp else (ETRAM_WIDTH, "assumed")
        h, h_src = (int(grp["height"][()]), "file") if "height" in grp else (ETRAM_HEIGHT, "assumed")

        vals = sorted(int(v) for v in np.unique(p))
        if vals == [0, 1]:
            enc = "0/1"
        elif vals == [-1, 1]:
            enc = "-1/1"
        elif len(vals) == 1:
            enc = "single"
        else:
            enc = "unexpected"

        n_x_over = int(np.count_nonzero(x.astype(np.int64) > 2047))
        n_y_over = int(np.count_nonzero(y.astype(np.int64) > 1023))

        return EtramProbe(
            path=str(path),
            n_events=n,
            width=w, height=h, width_source=w_src, height_source=h_src,
            dtypes={k: str(grp[k].dtype) for k in REQUIRED_KEYS},
            t_first_us=int(t[0]) if n else 0,
            t_last_us=int(t[-1]) if n else 0,
            duration_s=float(t[-1] - t[0]) / 1e6 if n else 0.0,
            t_nondecreasing=(inversions == 0),
            n_time_inversions=inversions,
            polarity_values=vals,
            polarity_encoding=enc,
            x_min=int(x.min()) if m else 0, x_max=int(x.max()) if m else 0,
            y_min=int(y.min()) if m else 0, y_max=int(y.max()) if m else 0,
            n_x_over_11_bits=n_x_over, n_y_over_10_bits=n_y_over,
            fits_frozen_record=(n_x_over == 0 and n_y_over == 0),
        )
    finally:
        f.close()


def read_events(path: str | Path, *, clamp_time: bool = True,
                 repair_msb: bool = True) -> Events:
    """Read one recording into normalized arrays.

    Polarity is mapped to ``{0, 1}``: ``-1`` becomes ``0``, matching the eTraM
    baseline's ``np.clip(p, a_min=0)``.  This is lossless, since the two
    encodings carry the same one bit.

    Decreasing timestamps are clamped to their predecessor when ``clamp_time``
    is set, which is what the eTraM baseline does.  **The clamp is lossy in the
    timestamp** and the number of affected events is returned, so a nonzero
    count is always visible rather than absorbed.

    ``repair_msb`` clears bit 15 of a coordinate that is out of the sensor's
    range only because that bit is set.  Two events in the 112-recording
    calibration corpus need it -- 2 of 23,631,099,558, in
    ``train_day_0024_td`` (y=33014=0x80F6, index 312,613,395) and
    ``train_night_0021_td`` (y=32886=0x8076, index 438,753,811).  Both are a
    single set MSB over an otherwise valid coordinate (246 and 118), with
    ordinary neighbours on both sides, which is a bit flip and not a geometry
    the model should be widened for.  The repair is **lossy in the coordinate**
    and its count is returned for the same reason the time clamp's is: a
    nonzero count must stay visible.  Set ``repair_msb=False`` to refuse it
    instead.  A coordinate still out of range after clearing bit 15 is a
    different fault and always raises.
    """
    path = Path(path)
    f, grp = _open(path)
    try:
        t = np.asarray(grp["t"][:], dtype=np.int64)
        x = np.asarray(grp["x"][:], dtype=np.uint16)
        y = np.asarray(grp["y"][:], dtype=np.uint16)
        p_raw = np.asarray(grp["p"][:], dtype=np.int16)
    finally:
        f.close()

    if not (t.size == x.size == y.size == p_raw.size):
        raise EtramFormatError(f"{path}: event arrays have mismatched lengths")

    p = np.clip(p_raw, 0, None).astype(np.uint8)
    if not np.all(np.isin(p, (0, 1))):
        raise EtramFormatError(f"{path}: polarity outside {{0,1}} after normalization")

    n_msb = 0
    for name, arr, limit in (("x", x, ETRAM_WIDTH - 1), ("y", y, ETRAM_HEIGHT - 1)):
        # DEFERRED (2026-09-18): `if int(arr.max()) <= limit: continue` is the
        # cheaper guard -- one reduction and no allocation, where this builds a
        # full-length bool array per coordinate. Measured on 100M events and
        # scaled: 473ms against 328ms for the 970M-event recording, which is
        # 0.03% of that recording's 1484s, so the time is noise. The reason to
        # make the change is the ~2GB of transient bool arrays it avoids on the
        # largest recording, and that 110 of 112 recordings would exit on a
        # reduction instead of an allocation. Not applied during the full Q1
        # run: a mid-run edit would split one artifact set across two code
        # revisions for a 0.03% gain, which is not a trade worth making.
        over = arr > limit
        if not over.any():
            continue
        repairable = over & ((arr & np.uint16(0x7FFF)) <= limit) & (arr >= np.uint16(0x8000))
        if not repair_msb:
            raise EtramFormatError(
                f"{path}: {int(over.sum())} events with {name} > {limit} and repair_msb=False")
        if not np.array_equal(over, repairable):
            bad = int((over & ~repairable).sum())
            raise EtramFormatError(
                f"{path}: {bad} events with {name} out of 0..{limit} for a reason "
                f"other than a set bit 15 -- not repairable, refusing to guess")
        arr[repairable] &= np.uint16(0x7FFF)
        n_msb += int(repairable.sum())

    n_inv = int(np.count_nonzero(np.diff(t) < 0)) if t.size > 1 else 0
    if n_inv and clamp_time:
        t = np.maximum.accumulate(t)
    elif n_inv:
        raise EtramFormatError(f"{path}: {n_inv} decreasing timestamps and clamp_time=False")

    return Events(t_us=t, x=x, y=y, p=p,
                  n_time_inversions_clamped=n_inv if clamp_time else 0,
                  n_coord_msb_repaired=n_msb)
