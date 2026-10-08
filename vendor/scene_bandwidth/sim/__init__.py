"""Adaptive computing and communication for wireless event-based sensors.

Scope of this package at M0: the controller, the radio/ARQ model, the baseline
action sets, the 40-bit record codec, and the synthetic fixtures needed by the
M0 gate tests of SIMULATION_PLAN.md Sec. 4.14.4.

Not implemented at M0: eTraM ingestion and batching, compression profiling,
channel draws, link selection, tuning, metrics, plotting.
"""

__all__ = ["workload", "radio", "controller", "baselines", "simulator", "synthetic"]
