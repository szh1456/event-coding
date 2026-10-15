"""Gate for directive 024: the three reconstructions of ``ec.tolerance_demo`` on constructed events and on the
model, and the figure script on their output."""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

from ec import blockcodec as bc
from ec import phase as ph
from ec import tolerance_demo as td

T0 = bc.T0_US
W, H = 320, 240
ROOT = Path(__file__).resolve().parent.parent


def _ev(rows):
    t = np.array([r[0] for r in rows], dtype=np.int64)
    x, y, p = (np.array([r[i] for r in rows], dtype=np.int64) for i in (1, 2, 3))
    o = np.argsort(t, kind="stable")
    return tuple(a[o] for a in (t, x, y, p))


def test_crop_and_box():
    assert td.crop_of((10.5, 20.0, 30.0, 40.0), W, H) == (0, 4, 57, 76)
    assert td.crop_of((300.0, 230.0, 30.0, 40.0), W, H) == (284, 214, 320, 240)
    assert td.clip_box((0.0, 0.0, 480.0, 200.0)) == (120.0, 10.0, 240, 180)
    assert td.clip_box((5.0, 6.0, 50.0, 60.0)) == (5.0, 6.0, 50.0, 60.0)


def test_every_event_keeps_every_event_in_its_bin():
    rng = np.random.default_rng(0)
    w1 = 6 * T0
    n = 3000
    crop = (40, 30, 140, 110)
    true = _ev(list(zip(w1 + rng.integers(0, T0, n), rng.integers(40, 140, n), rng.integers(30, 110, n),
                        rng.integers(0, 2, n))))
    ev, bits = td.every_event(true, crop, w1)
    assert len(ev[0]) == n and bits > 0
    f = td.fidelity(true, ev, crop, w1)
    assert f["k256"] == 1.0 and f["k32"] == 1.0
    assert np.all((ev[0] >= w1) & (ev[0] < w1 + T0))


def test_pixel_offsets_by_construction():
    true = _ev([(1000 + 2000 * k, 5, 5, 1) for k in range(3)] + [(4000, 6, 5, 1)])
    pred = _ev([(1500 + 2000 * k, 5, 5, 1) for k in range(3)] + [(9000, 7, 5, 1), (4300, 6, 5, 1)])
    out, sym = td.pixel_offsets(pred, true, W)
    step = td.OFFSET_STEP
    assert len(sym) == 3 and (sym == td.DELETE).sum() == 1
    t5 = np.sort(out[0][out[1] == 5])
    assert np.array_equal(t5, 1500 + 2000 * np.arange(3) + round(-500 / step) * step)
    assert not np.any(out[1] == 7)
    assert np.array_equal(out[0][out[1] == 6], [4300 + round(-300 / step) * step])


def test_frames():
    crop = (10, 10, 20, 15)
    s0 = T0 // 2 - td.N_FRAMES * td.FRAME_US // 2
    ev = _ev([(T0 + s0 + 10, 11, 12, 1), (T0 + s0 + 20, 11, 12, 0), (T0 + s0 + td.FRAME_US + 5, 12, 12, 1),
              (T0 + 5, 13, 12, 1)])
    img, starts = td.frames(ev, crop, T0)
    assert img.shape == (1 + td.N_FRAMES, 5, 10) and starts[0] == s0
    assert img[1, 2, 1] == 0 and img[2, 2, 2] == 1 and img[1:].sum() == 1  # the event before the slices is out
    assert img[0].sum() == 2 and img[0, 2, 3] == 1                         # the whole window holds all four


def test_the_ladder_on_the_model():
    for shared in (False, True):
        ev = ph.edge_scene_v(W, H, 6.5, 2000.0, 3, 0.05, 40, 8, 1, shared)
        d = td.demo(ev, 5, W, H, (100.0, 60.0, 120.0, 100.0))
        r = d["recs"]
        assert r["recorded"]["F"]["k256"] == 1.0
        assert r["every"]["F"]["k32"] == 1.0
        assert r["every"]["bits_per_event"] > r["pixel"]["bits_per_event"] > r["motion"]["bits_per_event"] > 0
        if shared:
            assert r["motion"]["F"]["k32"] > 0.75
        else:
            assert r["motion"]["F"]["k32"] < 0.6 < r["pixel"]["F"]["k32"] < 0.95


def test_save_and_figure(tmp_path):
    ev = ph.edge_scene_v(W, H, 6.5, 2000.0, 3, 0.05, 40, 8, 1, False)
    d = td.demo(ev, 5, W, H, (100.0, 60.0, 120.0, 100.0))
    td.save({"day": d}, tmp_path)
    meta = json.loads((tmp_path / "demo.json").read_text())
    assert meta["day"]["recs"]["pixel"]["bits_per_event"] == d["recs"]["pixel"]["bits_per_event"]
    subprocess.run([sys.executable, str(ROOT / "scripts" / "fig_tolerance.py"), "--demo", str(tmp_path), "--out",
                    str(tmp_path)], check=True)
    fig = json.loads((tmp_path / "fig_tolerance.json").read_text())
    assert fig["day"]["recs"]["motion"]["F"] == d["recs"]["motion"]["F"]
    for ext in ("pdf", "png"):
        assert (tmp_path / f"fig_tolerance.{ext}").stat().st_size > 0


def test_eligible_boxes():
    assert td.eligible((50.0, 50.0, 100.0, 80.0), (40.0, 50.0, 100.0, 80.0), W, H)
    assert not td.eligible((10.0, 50.0, 100.0, 80.0), (0.0, 50.0, 100.0, 80.0), W, H)        # near the edge
    assert not td.eligible((50.0, 50.0, 100.0, 80.0), (48.0, 50.0, 100.0, 80.0), W, H)       # too slow
    assert not td.eligible((40.0, 40.0, 250.0, 80.0), (30.0, 40.0, 250.0, 80.0), 400, 300)   # too wide
    assert not td.eligible((50.0, 50.0, 100.0, 80.0), None, W, H)


def test_same_window_fit_on_the_model():
    for v in (6.5, 13.3):
        ev = ph.edge_scene_v(W, H, v, 2000.0, 3, 0.05, 40, 8, 1, False)
        c = td.demo(ev, 5, W, H, (100.0, 60.0, 120.0, 100.0))
        s = td.demo(ev, 5, W, H, (100.0, 60.0, 120.0, 100.0), fit="same")
        assert s["fit"] == "same" and c["fit"] == "causal"
        assert s["recs"]["motion"]["F"]["k32"] >= c["recs"]["motion"]["F"]["k32"] - 0.01
        assert s["recs"]["motion"]["F"]["k32"] < 0.6 < s["recs"]["pixel"]["F"]["k32"]           # independent phases
    ev = ph.edge_scene_v(W, H, 6.5, 2000.0, 3, 0.05, 40, 8, 1, True)
    s = td.demo(ev, 5, W, H, (100.0, 60.0, 120.0, 100.0), fit="same")
    assert s["recs"]["motion"]["F"]["k32"] > 0.75                                              # shared phases
