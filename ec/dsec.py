"""Reader for the event files of DSEC (directive 009).

An event file of DSEC is an HDF5 file with the datasets ``/events/x`` (column), ``/events/y`` (row),
``/events/t`` (microseconds) and ``/events/p`` (polarity), and with ``/t_offset``, the offset in
microseconds between the stored times and the clock of the other sensors (documentation of the
dataset, https://dsec.ifi.uzh.ch/data-format/). The files are compressed with Blosc, so ``h5py``
needs the filter that the package ``hdf5plugin`` registers. The events are those of the sensor,
640 x 480, not rectified.

``read_events`` returns the stored times as they are, without the offset. It checks what the
project relies on and raises ``ValueError`` on anything else, so that a file that differs from the
documentation stops the run instead of being read wrongly. A decreasing time is clamped to its
predecessor, as the reader of the first dataset does, and counted.
"""
from __future__ import annotations

import numpy as np

WIDTH, HEIGHT = 640, 480
FIELDS = ("x", "y", "t", "p")


def describe(path) -> dict:
    """Names, shapes, types and filters of every dataset of the file, without reading the events."""
    import h5py
    try:
        import hdf5plugin  # noqa: F401  (registers the Blosc filter)
    except ImportError:
        pass
    out = {}
    with h5py.File(path, "r") as f:
        def visit(name, obj):
            if isinstance(obj, h5py.Dataset):
                out["/" + name] = {"shape": list(obj.shape), "dtype": str(obj.dtype), "compression": str(obj.compression),
                                   "filters": {str(k): str(v) for k, v in obj._filters.items()}}
        f.visititems(visit)
    return out


def read_events(path):
    """Events of one file: ``t_us`` (int64, nondecreasing), ``x``, ``y``, ``p`` (int64), and a dictionary of facts."""
    import h5py
    try:
        import hdf5plugin  # noqa: F401  (registers the Blosc filter)
    except ImportError:
        pass
    with h5py.File(path, "r") as f:
        if "events" not in f or any(k not in f["events"] for k in FIELDS):
            raise ValueError(f"{path}: /events/{{x, y, t, p}} not found")
        g = f["events"]
        dtypes = {k: str(g[k].dtype) for k in FIELDS}
        x, y, t, p = (np.asarray(g[k][:]).astype(np.int64) for k in FIELDS)
        t_offset = int(np.asarray(f["t_offset"][()]).reshape(-1)[0]) if "t_offset" in f else None
    n = len(t)
    if not (len(x) == len(y) == len(p) == n) or t.ndim != 1:
        raise ValueError(f"{path}: the four event datasets differ in length or are not one-dimensional")
    if n == 0:
        raise ValueError(f"{path}: no events")
    if x.min() < 0 or x.max() >= WIDTH or y.min() < 0 or y.max() >= HEIGHT:
        raise ValueError(f"{path}: coordinates outside {WIDTH} x {HEIGHT}: x {x.min()}..{x.max()}, y {y.min()}..{y.max()}")
    if not np.isin(np.unique(p), (0, 1)).all():
        raise ValueError(f"{path}: polarity values {np.unique(p).tolist()} are not a subset of (0, 1)")
    if t.min() < 0:
        raise ValueError(f"{path}: negative time")
    n_inv = int((np.diff(t) < 0).sum())
    if n_inv:
        t = np.maximum.accumulate(t)
    info = {"n_events": int(n), "t_first_us": int(t[0]), "t_last_us": int(t[-1]), "t_offset_us": t_offset,
            "n_time_inversions_clamped": n_inv, "dtypes": dtypes,
            "x_max": int(x.max()), "y_max": int(y.max()), "share_p1": float(p.mean())}
    return t, x, y, p, info
