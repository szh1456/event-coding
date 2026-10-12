"""The gate of directive 007 (``test_blockcodec_gate.py``), unchanged, with ``bc`` bound to ``ec.blockcodec_fast``.

The gate file is loaded as a second module; its name ``bc`` is then a copy of ``ec.blockcodec`` in
which the functions of ``ec.blockcodec_fast.__all__`` replace the reference ones. Its fixtures and
tests are re-exported here under their own names.
"""
import importlib.util
import pathlib
import types

from ec import blockcodec as bc, blockcodec_fast as fast

_shim = types.ModuleType("ec.blockcodec_fast_as_bc")
_shim.__dict__.update(bc.__dict__)
_shim.__dict__.update({k: getattr(fast, k) for k in fast.__all__})
_spec = importlib.util.spec_from_file_location(
    "_blockcodec_gate_on_fast", pathlib.Path(__file__).resolve().parent / "test_blockcodec_gate.py")
_gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_gate)
_gate.bc = _shim

ev, group = _gate.ev, _gate.group
globals().update({k: v for k, v in vars(_gate).items() if k.startswith("test_")})


def test_the_gate_runs_on_the_fast_implementation():
    assert _gate.bc.evaluate_group is fast.evaluate_group and _gate.bc.fit_group is fast.fit_group
