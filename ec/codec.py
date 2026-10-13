"""The implementation of the block codec that the runners use for Stages T and R and for the receivers.

Directive 007, Section 6: a faster ``evaluate_group`` may be used for Stages T and R if it returns, on every
group of Stage 0, the output of the reference in every field. ``ec.blockcodec_fast`` passed that check on the
Stage 0 groups of directives 007 and 009 and on their streams (``results/fast/stage0_check.json``; authorized
by the author on 2026-10-12). It is the default. ``EC_CODEC=reference`` selects ``ec.blockcodec``. Stage 0
itself always runs the reference, since it is what the check compares with. Every runner records ``NAME``.
"""
from __future__ import annotations

import os

from . import blockcodec as bc, blockcodec_fast as fast

CHOICE = os.environ.get("EC_CODEC", "fast")
if CHOICE not in ("fast", "reference"):
    raise ValueError(f"EC_CODEC must be 'fast' or 'reference', got {CHOICE!r}")
FAST = CHOICE == "fast"
NAME = ("ec.blockcodec_fast (checked on every Stage 0 group and stream, results/fast/stage0_check.json)" if FAST
        else "ec.blockcodec (reference)")


def evaluate_group(*a, **k):
    return (fast.evaluate_group if FAST else bc.evaluate_group)(*a, **k)


def evaluate_streams(bufs, t_us, x, y, p, cell=bc.OBJECTIVE) -> list:
    """One receiver output per stream of one recording, as ``ec.blockcodec.evaluate_stream`` returns it."""
    if FAST:
        return fast.evaluate_streams(bufs, t_us, x, y, p, cell)
    return [bc.evaluate_stream(b, t_us, x, y, p, cell) for b in bufs]


def wrap_fit(wrapper_factory):
    """Install a timing wrapper around ``fit_group`` in both implementations: ``wrapper_factory(original)``."""
    bc.fit_group = wrapper_factory(bc.fit_group)
    g = fast.evaluate_group.__globals__
    g["fit_group"] = wrapper_factory(g["fit_group"])


DECODERS = "ec.blockcodec (reference)"


def use_fast_decoders():
    """Route the record decoding of modules that call ``ec.blockcodec`` directly (``decode_stream`` for coder-T
    payloads, and ``reconstruct``) through ``ec.blockcodec_fast``, whose ``decode_events_T`` and ``reconstruct``
    equal the reference on every Stage 0 stream. Does nothing under ``EC_CODEC=reference``."""
    global DECODERS
    if FAST:
        bc.decode_events_T = fast.decode_events_T
        bc.reconstruct = fast.reconstruct
        DECODERS = "ec.blockcodec_fast.decode_events_T and reconstruct (equal to the reference on every Stage 0 stream)"
    return DECODERS
