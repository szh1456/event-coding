"""Workload: the 40-bit packed event record and the window validity guard.

M0 implements only the parts that need no data: the record codec (gate test
T-01) and ``validate_window`` (test T-02).  Batching, splitting and workload
statistics are M1.

Record layout, SIMULATION_PLAN.md Sec. 4.3 -- 5 bytes, little-endian, exactly
40 bits per event::

    field   bits  offset  range
    x        11      0    0..2047
    y        10     11    0..1023
    pol       1     21    0/1
    t_us     18     22    0..262143   (microseconds since the window start)

Records are sorted by ``(t_us, x, y)``.  There is no per-batch header, so the
packed size is exactly ``5 * N`` bytes and ``B_k = 40 * N_k`` holds exactly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, NamedTuple, Sequence

RECORD_BYTES = 5
RECORD_BITS = 40

X_BITS, Y_BITS, POL_BITS, T_BITS = 11, 10, 1, 18
X_OFF, Y_OFF, POL_OFF, T_OFF = 0, 11, 21, 22

X_MAX = (1 << X_BITS) - 1
Y_MAX = (1 << Y_BITS) - 1
T_MAX_US = (1 << T_BITS) - 1

#: Largest window length the 18-bit timestamp field can represent, in seconds.
MAX_W_S = (T_MAX_US + 1) / 1e6  # 0.262144 s


class Event(NamedTuple):
    """One event, already expressed relative to its window start."""

    t_us: int
    x: int
    y: int
    pol: int


class RecordRangeError(ValueError):
    """An event does not fit the 40-bit record layout."""


class WindowConfigError(ValueError):
    """A (W, D, L) triple violates the frozen timing constraints."""


def validate_window(W_s: float, D_s: float, L_s: float, max_W_s: float = MAX_W_S) -> None:
    """Raise ``WindowConfigError`` unless the timing configuration is admissible.

    Enforces the formulation's Eq. (1), ``W + D <= L`` and ``D <= W``, and the
    brief's 18-bit timestamp guard ``W <= 262 ms``.
    """
    if W_s <= 0 or D_s <= 0 or L_s <= 0:
        raise WindowConfigError(f"W, D, L must be positive, got W={W_s}, D={D_s}, L={L_s}")
    if W_s > max_W_s:
        raise WindowConfigError(
            f"W={W_s} s exceeds the 18-bit timestamp validity {max_W_s} s; "
            "no 48-bit record variant is run"
        )
    if W_s + D_s > L_s:
        raise WindowConfigError(f"W + D = {W_s + D_s} s exceeds L = {L_s} s")
    if D_s > W_s:
        raise WindowConfigError(f"D = {D_s} s exceeds W = {W_s} s, which allows backlog")


def sort_events(events: Iterable[Event]) -> list[Event]:
    """Sort by ``(t_us, x, y)``, the canonical record order."""
    return sorted(events, key=lambda e: (e.t_us, e.x, e.y))


def _encode(e: Event) -> int:
    if not (0 <= e.x <= X_MAX):
        raise RecordRangeError(f"x={e.x} outside 0..{X_MAX}")
    if not (0 <= e.y <= Y_MAX):
        raise RecordRangeError(f"y={e.y} outside 0..{Y_MAX}")
    if e.pol not in (0, 1):
        raise RecordRangeError(f"pol={e.pol} must be 0 or 1")
    if not (0 <= e.t_us <= T_MAX_US):
        raise RecordRangeError(f"t_us={e.t_us} outside 0..{T_MAX_US}")
    return (e.x << X_OFF) | (e.y << Y_OFF) | (e.pol << POL_OFF) | (e.t_us << T_OFF)


def _decode(word: int) -> Event:
    return Event(
        t_us=(word >> T_OFF) & T_MAX_US,
        x=(word >> X_OFF) & X_MAX,
        y=(word >> Y_OFF) & Y_MAX,
        pol=(word >> POL_OFF) & 1,
    )


def pack_records(events: Sequence[Event], *, presorted: bool = False) -> bytes:
    """Pack events into the canonical 5-byte-per-event blob.

    Events are sorted by ``(t_us, x, y)`` unless ``presorted`` is set.  Raises
    ``RecordRangeError`` if any field is out of range.
    """
    ordered = list(events) if presorted else sort_events(events)
    out = bytearray(RECORD_BYTES * len(ordered))
    for i, e in enumerate(ordered):
        out[i * RECORD_BYTES : (i + 1) * RECORD_BYTES] = _encode(e).to_bytes(
            RECORD_BYTES, "little"
        )
    return bytes(out)


def unpack_records(blob: bytes) -> list[Event]:
    """Inverse of :func:`pack_records`."""
    if len(blob) % RECORD_BYTES:
        raise RecordRangeError(
            f"blob length {len(blob)} is not a multiple of {RECORD_BYTES} bytes"
        )
    return [
        _decode(int.from_bytes(blob[i : i + RECORD_BYTES], "little"))
        for i in range(0, len(blob), RECORD_BYTES)
    ]


def raw_bits(n_events: int, b_bits: int = RECORD_BITS) -> int:
    """``B_k = b * N_k``, exact by construction."""
    return b_bits * n_events


# ==========================================================================
# Vectorized codec and batching (M1a)
# ==========================================================================
def pack_array(
    t_us: "np.ndarray", x: "np.ndarray", y: "np.ndarray", p: "np.ndarray",
    *, presorted: bool = False,
) -> bytes:
    """Vectorized :func:`pack_records` for whole windows.

    ``t_us`` must already be relative to the window start.  Byte order is
    little-endian and is built explicitly, so the blob does not depend on the
    host's endianness.
    """
    import numpy as np

    t = np.asarray(t_us, dtype=np.int64)
    x = np.asarray(x, dtype=np.int64)
    y = np.asarray(y, dtype=np.int64)
    p = np.asarray(p, dtype=np.int64)
    if not (t.size == x.size == y.size == p.size):
        raise RecordRangeError("field arrays have mismatched lengths")
    if t.size == 0:
        return b""
    if x.min() < 0 or x.max() > X_MAX:
        raise RecordRangeError(f"x outside 0..{X_MAX}")
    if y.min() < 0 or y.max() > Y_MAX:
        raise RecordRangeError(f"y outside 0..{Y_MAX}")
    if p.min() < 0 or p.max() > 1:
        raise RecordRangeError("pol must be 0 or 1")
    if t.min() < 0 or t.max() > T_MAX_US:
        raise RecordRangeError(f"t_us outside 0..{T_MAX_US}")

    if not presorted:
        order = np.lexsort((y, x, t))          # primary t, then x, then y
        t, x, y, p = t[order], x[order], y[order], p[order]

    w = (x.astype(np.uint64)
         | (y.astype(np.uint64) << np.uint64(Y_OFF))
         | (p.astype(np.uint64) << np.uint64(POL_OFF))
         | (t.astype(np.uint64) << np.uint64(T_OFF)))
    out = np.empty((t.size, RECORD_BYTES), dtype=np.uint8)
    for i in range(RECORD_BYTES):
        out[:, i] = ((w >> np.uint64(8 * i)) & np.uint64(0xFF)).astype(np.uint8)
    return out.tobytes()


def unpack_array(blob: bytes):
    """Vectorized :func:`unpack_records`; returns ``(t_us, x, y, p)`` arrays."""
    import numpy as np

    if len(blob) % RECORD_BYTES:
        raise RecordRangeError(
            f"blob length {len(blob)} is not a multiple of {RECORD_BYTES} bytes"
        )
    arr = np.frombuffer(blob, dtype=np.uint8).reshape(-1, RECORD_BYTES)
    w = np.zeros(arr.shape[0], dtype=np.uint64)
    for i in range(RECORD_BYTES):
        w |= arr[:, i].astype(np.uint64) << np.uint64(8 * i)
    return (
        ((w >> np.uint64(T_OFF)) & np.uint64(T_MAX_US)).astype(np.int64),
        ((w >> np.uint64(X_OFF)) & np.uint64(X_MAX)).astype(np.uint16),
        ((w >> np.uint64(Y_OFF)) & np.uint64(Y_MAX)).astype(np.uint16),
        ((w >> np.uint64(POL_OFF)) & np.uint64(1)).astype(np.uint8),
    )


@dataclass(frozen=True)
class BatchRow:
    """One row of artifact group A1, before the split is assigned."""

    recording_id: str
    window_index: int
    start_time_us: int
    W_s: float
    N: int
    raw_bits: int
    payload: bytes

    @property
    def batch_id(self) -> str:
        return f"{self.recording_id}:{self.window_index:06d}"


@dataclass(frozen=True)
class IngestAudit:
    """Per-recording ingest bookkeeping, artifact group A1."""

    recording_id: str
    n_events_read: int
    n_events_dropped_range: int
    n_events_in_kept_windows: int
    n_windows_total: int
    n_windows_kept: int
    n_windows_empty: int
    n_windows_dropped_incomplete: int
    n_events_dropped_incomplete: int
    t_origin_us: int
    W_s: float
    lossless: bool


def batch_events(
    events, recording_id: str, W_s: float, *,
    drop_incomplete_final: bool = True, keep_empty_windows: bool = True,
) -> tuple[list[BatchRow], IngestAudit]:
    """Cut normalized events into fixed windows of ``W_s`` and pack each one.

    Windows are half-open ``[t0 + kW, t0 + (k+1)W)`` with ``t0`` the first event
    time of the recording, so window 0 is never empty.  Empty windows in the
    interior are kept with ``N = 0`` and are excluded from the coverage
    denominator later (SIMULATION_PLAN Sec. 4.3).

    The final window is dropped as incomplete: the event stream alone does not
    say where the recording ended, so the last window is only partly observed.
    """
    import numpy as np

    if W_s <= 0 or W_s > MAX_W_S:
        raise WindowConfigError(f"W={W_s} s outside (0, {MAX_W_S}]")
    W_us = int(round(W_s * 1e6))

    t, x, y, p = events.t_us, events.x, events.y, events.p
    n_read = int(t.size)
    if n_read == 0:
        return [], IngestAudit(recording_id, 0, 0, 0, 0, 0, 0, 0, 0, 0, W_s, True)

    in_range = (x <= X_MAX) & (y <= Y_MAX) & (p <= 1)
    n_dropped_range = int(np.count_nonzero(~in_range))
    if n_dropped_range:
        t, x, y, p = t[in_range], x[in_range], y[in_range], p[in_range]

    t0 = int(t[0])
    widx = ((t - t0) // W_us).astype(np.int64)
    n_windows_total = int(widx[-1]) + 1
    n_keep = n_windows_total - 1 if drop_incomplete_final else n_windows_total

    n_dropped_incomplete = int(np.count_nonzero(widx >= n_keep))
    bounds = np.searchsorted(widx, np.arange(n_keep + 1))

    rows: list[BatchRow] = []
    n_empty = 0
    n_in_kept = 0
    for k in range(n_keep):
        lo, hi = int(bounds[k]), int(bounds[k + 1])
        n = hi - lo
        if n == 0:
            n_empty += 1
            if not keep_empty_windows:
                continue
            payload = b""
        else:
            start = t0 + k * W_us
            payload = pack_array(t[lo:hi] - start, x[lo:hi], y[lo:hi], p[lo:hi])
        n_in_kept += n
        rows.append(BatchRow(
            recording_id=recording_id, window_index=k, start_time_us=t0 + k * W_us,
            W_s=W_s, N=n, raw_bits=raw_bits(n), payload=payload,
        ))

    audit = IngestAudit(
        recording_id=recording_id,
        n_events_read=n_read,
        n_events_dropped_range=n_dropped_range,
        n_events_in_kept_windows=n_in_kept,
        n_windows_total=n_windows_total,
        n_windows_kept=len(rows),
        n_windows_empty=n_empty,
        n_windows_dropped_incomplete=n_windows_total - n_keep,
        n_events_dropped_incomplete=n_dropped_incomplete,
        t_origin_us=t0,
        W_s=W_s,
        lossless=(n_in_kept + n_dropped_incomplete + n_dropped_range == n_read),
    )
    return rows, audit


def verify_lossless(rows, events, W_s: float) -> dict:
    """Unpack every batch and check the events come back exactly.

    Compares the multiset of ``(absolute t_us, x, y, p)`` recovered from the
    packed blobs against the events that fall in the kept windows.  Exact
    equality is required: the representation is lossless by construction and a
    mismatch is a bug, not a tolerance question.
    """
    import numpy as np

    W_us = int(round(W_s * 1e6))
    rec_t, rec_x, rec_y, rec_p = [], [], [], []
    for r in rows:
        if r.N == 0:
            assert r.payload == b""
            continue
        t_rel, x, y, p = unpack_array(r.payload)
        if t_rel.max() >= W_us:
            raise RecordRangeError(f"{r.batch_id}: relative timestamp outside the window")
        rec_t.append(t_rel.astype(np.int64) + r.start_time_us)
        rec_x.append(x); rec_y.append(y); rec_p.append(p)

    got = _sorted_view(rec_t, rec_x, rec_y, rec_p)
    kept_hi = rows[-1].start_time_us + W_us if rows else events.t_us[0]
    sel = (events.t_us >= rows[0].start_time_us) & (events.t_us < kept_hi) if rows else slice(0, 0)
    want = _sorted_view([events.t_us[sel]], [events.x[sel]], [events.y[sel]], [events.p[sel]])

    return {
        "n_recovered": int(got.shape[0]),
        "n_expected": int(want.shape[0]),
        "count_match": got.shape[0] == want.shape[0],
        "exact_match": got.shape[0] == want.shape[0] and bool(np.array_equal(got, want)),
        "timestamps_match": got.shape[0] == want.shape[0]
                            and bool(np.array_equal(got[:, 0], want[:, 0])),
    }


def _sorted_view(ts, xs, ys, ps):
    import numpy as np

    if not ts or sum(a.size for a in ts) == 0:
        return np.zeros((0, 4), dtype=np.int64)
    m = np.stack([
        np.concatenate(ts).astype(np.int64),
        np.concatenate(xs).astype(np.int64),
        np.concatenate(ys).astype(np.int64),
        np.concatenate(ps).astype(np.int64),
    ], axis=1)
    return m[np.lexsort((m[:, 3], m[:, 2], m[:, 1], m[:, 0]))]


def workload_stats(rows, W_s: float) -> list[dict]:
    """Table I part A: percentiles of ``N`` and of the raw rate, over non-empty windows.

    Denominators are explicit: ``N`` and ``raw_rate_bps`` are over non-empty
    windows only; ``frac_empty`` is over all kept windows.
    """
    import numpy as np

    n = np.array([r.N for r in rows], dtype=np.int64)
    nz = n[n > 0]
    rate = RECORD_BITS * nz / W_s
    out = []
    pcts = [1, 5, 10, 25, 50, 75, 90, 95, 99]
    for label, q in [(f"p{p:02d}", p) for p in pcts]:
        out.append({"statistic": label,
                    "N": float(np.percentile(nz, q)) if nz.size else float("nan"),
                    "raw_rate_bps": float(np.percentile(rate, q)) if nz.size else float("nan")})
    for label, fn in [("mean", np.mean), ("max", np.max)]:
        out.append({"statistic": label,
                    "N": float(fn(nz)) if nz.size else float("nan"),
                    "raw_rate_bps": float(fn(rate)) if nz.size else float("nan")})
    for row in out:
        row["frac_empty"] = float((n == 0).sum() / n.size) if n.size else float("nan")
        row["n_windows"] = int(nz.size)
        row["n_windows_all"] = int(n.size)
    return out
