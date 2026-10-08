"""Reversible event-data layouts applied before the generic lossless codec (R0).

The eventual coding action is ``c = (u, l)``: a representation ``u`` chosen here,
then one of the existing generic codec levels ``l``. R0 defines the byte formats
and proves reversibility. It adds nothing to the controller, measures nothing and
changes no result.

Every mode is a bijection on canonical AER40 blobs. ``decode(encode(b)) == b``
byte for byte -- not "the same events in some order", the same bytes. No event is
dropped, reordered, quantized or retimed.

The canonical record is the one and only definition in :mod:`sim.workload`:
40 bits, ``x`` at bits 0..10, ``y`` at 11..20, ``pol`` at 21, ``t_us`` at 22..39,
stored little-endian across 5 bytes. Because the four fields tile all 40 bits,
*every* 5-byte string is a field-legal record; the only semantic precondition on a
canonical blob is that ``t_us`` is nondecreasing, which the acquisition path
guarantees (``pack_records`` orders by ``(t, x, y)`` and ``read_events`` applies a
running-maximum clamp).

Which mode is active is signalled out of band, through the same policy metadata
that already tells the receiver the codec and controller configuration. There is
no representation-ID byte in the payload.

Modes:

    U0  AER40_INTERLEAVED  identity; payload is the input, 5N bytes
    U1  AER40_SOA          field-separated fixed width, 40N bits = 5N bytes
    U2  AER40_SOA_DT       field-separated addresses + exact ULEB128 time deltas
"""
from __future__ import annotations

from enum import Enum
from math import ceil

import numpy as np

from .workload import (POL_BITS, RECORD_BITS, RECORD_BYTES, T_BITS, T_MAX_US,
                       X_BITS, Y_BITS, pack_array, unpack_array)


class RepresentationError(ValueError):
    """A malformed canonical blob, or a malformed or non-canonical payload."""


class RepresentationMode(Enum):
    AER40_INTERLEAVED = "aer40_interleaved"
    AER40_SOA = "aer40_soa"
    AER40_SOA_DT = "aer40_soa_dt"


# U2 framing widths, in bits.
U2_COUNT_BITS = 24
U2_T0_BITS = 24
U2_ADDR_BITS = X_BITS + Y_BITS + POL_BITS          # 22
U2_MAX_EVENTS = (1 << U2_COUNT_BITS) - 1
#: A delta cannot exceed the 18-bit timestamp range, so it never needs more than
#: ceil(18/7) ULEB128 bytes. A longer sequence is rejected as overlong.
U2_MAX_DELTA_LEB_BYTES = ceil(T_BITS / 7)          # 3

assert X_BITS + Y_BITS + POL_BITS + T_BITS == RECORD_BITS == 8 * RECORD_BYTES


# --------------------------------------------------------------------------
# canonical blob handling


def canonical_event_count(blob: bytes) -> int:
    """``N`` for a canonical blob; raises if the length is not a whole record."""
    if len(blob) % RECORD_BYTES:
        raise RepresentationError(
            f"canonical blob of {len(blob)} bytes is not a multiple of {RECORD_BYTES}")
    return len(blob) // RECORD_BYTES


def validate_canonical_blob(blob: bytes) -> int:
    """Full precondition check: whole records, and nondecreasing timestamps.

    Field ranges need no check: the four fields tile all 40 bits, so every 5-byte
    string is field-legal. Timestamp order is the only semantic precondition, and
    U2 depends on it because its deltas are unsigned.
    """
    n = canonical_event_count(blob)
    if n > 1:
        t, _, _, _ = unpack_array(blob)
        if np.any(np.diff(t) < 0):
            i = int(np.argmax(np.diff(t) < 0))
            raise RepresentationError(
                f"timestamp inversion at event {i + 1}: t={int(t[i + 1])} follows "
                f"t={int(t[i])}; a canonical blob must be nondecreasing in t")
    return n


def _unpack_checked(blob: bytes):
    """Unpack a canonical blob, enforcing the nondecreasing-timestamp precondition."""
    n = canonical_event_count(blob)
    if n == 0:
        z = np.zeros(0, dtype=np.int64)
        return z, z, z, z
    t, x, y, p = unpack_array(blob)
    if n > 1 and np.any(np.diff(t) < 0):
        i = int(np.argmax(np.diff(t) < 0))
        raise RepresentationError(
            f"timestamp inversion at event {i + 1}: t={int(t[i + 1])} follows "
            f"t={int(t[i])}; a canonical blob must be nondecreasing in t")
    if n and (int(t.max()) > T_MAX_US or int(t.min()) < 0):
        raise RepresentationError("timestamp outside the 18-bit range")
    return t, x, y, p


# --------------------------------------------------------------------------
# MSB-first bit packing


def _bits_msb_first(vals: np.ndarray, width: int) -> np.ndarray:
    """``len(vals) * width`` bits, each value most-significant bit first."""
    if vals.size == 0:
        return np.zeros(0, dtype=np.uint8)
    shifts = np.arange(width - 1, -1, -1, dtype=np.uint64)
    return (((vals.astype(np.uint64)[:, None] >> shifts) & np.uint64(1))
            .astype(np.uint8).ravel())


def _from_bits_msb_first(bits: np.ndarray, n: int, width: int) -> np.ndarray:
    """Inverse of :func:`_bits_msb_first`."""
    if n == 0:
        return np.zeros(0, dtype=np.int64)
    weights = (np.uint64(1) << np.arange(width - 1, -1, -1, dtype=np.uint64))
    return bits.reshape(n, width).astype(np.uint64).dot(weights).astype(np.int64)


# --------------------------------------------------------------------------
# canonical unsigned LEB128
#
# Base 128, little-endian groups of seven bits, continuation bit 0x80 set on
# every byte but the last. Canonical means shortest: a multi-byte sequence whose
# final byte is zero encodes a value that fits in fewer bytes and is rejected.


def uleb128_encode(value: int) -> bytes:
    if value < 0:
        raise RepresentationError(f"ULEB128 is unsigned, got {value}")
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def uleb128_decode(buf: bytes, pos: int, *, max_bytes: int = U2_MAX_DELTA_LEB_BYTES):
    """Return ``(value, next_pos)``. Rejects truncated, overlong and non-canonical."""
    value = 0
    shift = 0
    start = pos
    while True:
        if pos >= len(buf):
            raise RepresentationError(
                f"truncated ULEB128 starting at byte {start}: continuation bit set "
                f"on the last byte of the payload")
        byte = buf[pos]
        pos += 1
        n_read = pos - start
        if n_read > max_bytes:
            raise RepresentationError(
                f"overlong ULEB128 at byte {start}: more than {max_bytes} bytes, "
                f"which cannot be needed for an {T_BITS}-bit delta")
        value |= (byte & 0x7F) << shift
        if not (byte & 0x80):
            if n_read > 1 and byte == 0x00:
                raise RepresentationError(
                    f"non-canonical ULEB128 at byte {start}: {n_read} bytes ending "
                    f"in 0x00 is not the shortest encoding of {value}")
            return value, pos
        shift += 7


# --------------------------------------------------------------------------
# U0


def _encode_u0(blob: bytes) -> bytes:
    """Identity. Only the O(1) length check runs, so the transform does no
    per-event work, consistent with the level-0 convention that fixes its cost to
    zero. The nondecreasing-timestamp precondition is not re-checked here; call
    :func:`validate_canonical_blob` explicitly if it is in doubt."""
    canonical_event_count(blob)
    return bytes(blob)


def _decode_u0(payload: bytes) -> bytes:
    canonical_event_count(payload)
    return bytes(payload)


# --------------------------------------------------------------------------
# U1


def _encode_u1(blob: bytes) -> bytes:
    t, x, y, p = _unpack_checked(blob)
    if t.size == 0:
        return b""
    bits = np.concatenate((_bits_msb_first(x, X_BITS),
                           _bits_msb_first(y, Y_BITS),
                           _bits_msb_first(p, POL_BITS),
                           _bits_msb_first(t, T_BITS)))
    # 40N bits is a whole number of bytes, so packbits adds no padding.
    return np.packbits(bits).tobytes()


def _decode_u1(payload: bytes) -> bytes:
    n_bits = 8 * len(payload)
    if n_bits % RECORD_BITS:
        raise RepresentationError(
            f"U1 payload of {len(payload)} bytes is {n_bits} bits, not a multiple "
            f"of {RECORD_BITS}")
    n = n_bits // RECORD_BITS
    if n == 0:
        return b""
    bits = np.unpackbits(np.frombuffer(payload, dtype=np.uint8))
    o1, o2, o3 = X_BITS * n, (X_BITS + Y_BITS) * n, U2_ADDR_BITS * n
    x = _from_bits_msb_first(bits[:o1], n, X_BITS)
    y = _from_bits_msb_first(bits[o1:o2], n, Y_BITS)
    p = _from_bits_msb_first(bits[o2:o3], n, POL_BITS)
    t = _from_bits_msb_first(bits[o3:], n, T_BITS)
    if n > 1 and np.any(np.diff(t) < 0):
        raise RepresentationError(
            "U1 payload decodes to a timestamp inversion; no encoder output can "
            "contain one")
    return pack_array(t, x, y, p, presorted=True)


# --------------------------------------------------------------------------
# U2


def _encode_u2(blob: bytes) -> bytes:
    t, x, y, p = _unpack_checked(blob)
    n = int(t.size)
    if n == 0:
        return b""
    if n > U2_MAX_EVENTS:
        raise RepresentationError(
            f"U2 count field is {U2_COUNT_BITS} bits, so N must be at most "
            f"{U2_MAX_EVENTS}, got {n}")
    out = bytearray(n.to_bytes(U2_COUNT_BITS // 8, "big"))
    addr = np.concatenate((_bits_msb_first(x, X_BITS),
                           _bits_msb_first(y, Y_BITS),
                           _bits_msb_first(p, POL_BITS)))
    # packbits zero-fills the final byte, which is exactly the required padding.
    out += np.packbits(addr).tobytes()
    out += int(t[0]).to_bytes(U2_T0_BITS // 8, "big")
    if n > 1:
        deltas = np.diff(t)
        out += b"".join(uleb128_encode(int(d)) for d in deltas)
    return bytes(out)


def _decode_u2(payload: bytes) -> bytes:
    if len(payload) == 0:
        return b""
    n_count = U2_COUNT_BITS // 8
    n_t0 = U2_T0_BITS // 8
    if len(payload) < n_count:
        raise RepresentationError(
            f"U2 payload of {len(payload)} bytes is shorter than the "
            f"{n_count}-byte count field")
    n = int.from_bytes(payload[:n_count], "big")
    if n == 0:
        raise RepresentationError(
            "U2 encodes N = 0 as the empty payload, so a stored count of zero is "
            "malformed")
    addr_bytes = ceil(U2_ADDR_BITS * n / 8)
    need = n_count + addr_bytes + n_t0
    if len(payload) < need:
        raise RepresentationError(
            f"U2 payload of {len(payload)} bytes is truncated: N={n} needs at least "
            f"{need} bytes for the count, address block and first timestamp")
    raw = np.frombuffer(payload[n_count:n_count + addr_bytes], dtype=np.uint8)
    bits = np.unpackbits(raw)
    used = U2_ADDR_BITS * n
    if np.any(bits[used:]):
        raise RepresentationError(
            f"U2 address block has a nonzero padding bit; the {len(bits) - used} "
            f"bits after the {used} address bits must be zero")
    o1, o2 = X_BITS * n, (X_BITS + Y_BITS) * n
    x = _from_bits_msb_first(bits[:o1], n, X_BITS)
    y = _from_bits_msb_first(bits[o1:o2], n, Y_BITS)
    p = _from_bits_msb_first(bits[o2:used], n, POL_BITS)

    pos = n_count + addr_bytes
    t0 = int.from_bytes(payload[pos:pos + n_t0], "big")
    pos += n_t0
    if t0 > T_MAX_US:
        raise RepresentationError(
            f"U2 first timestamp {t0} exceeds the {T_BITS}-bit range 0..{T_MAX_US}")

    t = np.empty(n, dtype=np.int64)
    t[0] = t0
    cur = t0
    for i in range(1, n):
        delta, pos = uleb128_decode(payload, pos)
        cur += delta
        if cur > T_MAX_US:
            raise RepresentationError(
                f"U2 timestamp reconstruction overflows at event {i}: {cur} exceeds "
                f"the {T_BITS}-bit range 0..{T_MAX_US}")
        t[i] = cur
    if pos != len(payload):
        raise RepresentationError(
            f"U2 payload has {len(payload) - pos} trailing bytes after {n} events")
    return pack_array(t, x, y, p, presorted=True)


# --------------------------------------------------------------------------
# public API

_ENCODERS = {RepresentationMode.AER40_INTERLEAVED: _encode_u0,
             RepresentationMode.AER40_SOA: _encode_u1,
             RepresentationMode.AER40_SOA_DT: _encode_u2}
_DECODERS = {RepresentationMode.AER40_INTERLEAVED: _decode_u0,
             RepresentationMode.AER40_SOA: _decode_u1,
             RepresentationMode.AER40_SOA_DT: _decode_u2}


def encode_representation(canonical_blob: bytes, mode: RepresentationMode) -> bytes:
    """Apply representation ``mode`` to a canonical AER40 blob."""
    if not isinstance(mode, RepresentationMode):
        raise RepresentationError(f"unknown representation mode {mode!r}")
    return _ENCODERS[mode](bytes(canonical_blob))


def decode_representation(payload: bytes, mode: RepresentationMode) -> bytes:
    """Invert :func:`encode_representation`, returning canonical AER40 bytes."""
    if not isinstance(mode, RepresentationMode):
        raise RepresentationError(f"unknown representation mode {mode!r}")
    return _DECODERS[mode](bytes(payload))


def encoded_length(n_events: int, mode: RepresentationMode,
                   delta_leb_bytes: int | None = None) -> int:
    """Payload length in bytes. ``delta_leb_bytes`` is the summed ULEB128 length of
    the ``N-1`` deltas, which U2 alone needs and which is data dependent."""
    n = n_events
    if mode in (RepresentationMode.AER40_INTERLEAVED, RepresentationMode.AER40_SOA):
        return RECORD_BYTES * n
    if n == 0:
        return 0
    if delta_leb_bytes is None:
        raise RepresentationError("U2 length needs the summed ULEB128 delta length")
    return (U2_COUNT_BITS // 8) + ceil(U2_ADDR_BITS * n / 8) \
        + (U2_T0_BITS // 8) + delta_leb_bytes
