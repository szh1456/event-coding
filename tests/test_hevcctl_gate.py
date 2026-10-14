"""Gate for directive 021: the controls of ``ec.hevcctl`` on synthetic counts and on the model of directive 019."""
import numpy as np
import pytest

from ec import hevcctl as hc
from ec import hevcdiag as hd

W, H = 96, 64


def test_specs():
    assert hc.spec("lossless") == {"intra": False, "scale": 1, "cmax": 15, "qp": None}
    assert hc.spec("lossless_intra")["intra"] and hc.spec("lossless_intra")["qp"] is None
    assert hc.spec("lossless_x16")["scale"] == 16 and hc.spec("lossless_c255")["cmax"] == 255
    assert hc.spec("qp20") == {"intra": False, "scale": 16, "cmax": 15, "qp": 20}
    assert hc.spec("qp20_intra") == {"intra": True, "scale": 16, "cmax": 15, "qp": 20}
    assert hc.spec("qp46_s4") == {"intra": False, "scale": 4, "cmax": 63, "qp": 34}
    assert hc.spec("qp46_s4c15") == {"intra": False, "scale": 4, "cmax": 15, "qp": 34}
    for bad in ("qp8_s4", "qp20_x", "lossy"):
        with pytest.raises(ValueError):
            hc.spec(bad)
    for m in hc.FINE_MODES + hc.COARSE_MODES:          # every listed mode parses, and its luma fits 8 bits
        if not m.startswith("sparse"):
            sp = hc.spec(m)
            assert sp["scale"] * sp["cmax"] <= 255


def test_count_errors_by_construction():
    key = np.array([1, 2, 3, 5, 8, 9])
    cnt = np.array([1, 3, 1, 2, 1, 4])
    dkey = np.array([2, 3, 4, 8, 9])
    dcnt = np.array([1, 2, 2, 1, 6])
    e = hc.count_errors(key, cnt, dkey, dcnt)
    assert e["removed1"] == 1 and e["removed2"] == 2                    # voxel 1 (count 1), voxel 5 (count 2)
    assert e["kept"] == 3 + 1 + 1 + 4 and e["lowered"] == 2 and e["raised"] == 1 + 2
    assert e["added"] == 2 and e["added_vox"] == 1
    assert e["in_events"] == 12 and e["out_events"] == 12
    assert e["in_vox1"] == 3 and e["in_vox2"] == 3


def _random_counts(rng, n_frames, fh, fw, cmax, density=0.05):
    keys = np.flatnonzero(rng.random(n_frames * fh * fw) < density)
    return keys, rng.integers(1, cmax + 1, len(keys))


@pytest.mark.parametrize("mode", ["lossless", "lossless_intra", "lossless_x16", "lossless_c255"])
def test_lossless_modes_return_the_counts(mode, tmp_path):
    rng = np.random.default_rng(1)
    nx, ny, fh, fw = hd.dims(1, W, H)
    sp = hc.spec(mode)
    key, cnt = _random_counts(rng, 6, fh, fw, sp["cmax"])
    col, row = key % fw, (key // fw) % fh
    ok = (col % (fw // 2) < nx) & (row < ny)
    key, cnt = key[ok], cnt[ok]
    r = hc.x265_code(key, cnt, 6, fh, fw, sp, str(tmp_path), valid=(nx, ny))
    assert np.array_equal(r["key"], key) and np.array_equal(r["cnt"], cnt)
    types = [hc._kind(f) for f in r["frames"]]
    assert types == (["I"] * 6 if sp["intra"] else ["I"] + ["P"] * 5)
    assert r["bits"] > 0 and r["padding_counts"] == 0


def test_scale4_keeps_counts_above_15(tmp_path):
    rng = np.random.default_rng(2)
    nx, ny, fh, fw = hd.dims(1, W, H)
    key, cnt = _random_counts(rng, 4, fh, fw, 80, density=0.02)
    col, row = key % fw, (key // fw) % fh
    ok = (col % (fw // 2) < nx) & (row < ny)
    key, cnt = key[ok], cnt[ok]
    r = hc.x265_code(key, np.minimum(cnt, 63), 4, fh, fw, hc.spec("qp14_s4"), str(tmp_path), valid=(nx, ny))
    e = hc.count_errors(key, np.minimum(cnt, 63), r["key"], r["cnt"])
    assert e["in_events"] == int(np.minimum(cnt, 63).sum()) and cnt.max() > 63
    assert e["out_events"] > 0.9 * e["in_events"]
    assert r["cnt"].max() > 15                                         # the clip at 15 is gone
    assert all(f["qp"] == 2 for f in r["frames"])


_MODEL = {}


def model():
    if not _MODEL:
        ev = hd.edge_scene(W, H, 6, 1000.0, 3, 0.05, 40, 6, 1)
        _MODEL["win"] = hd.windows_of(ev, 1, hd.K_WIN)
    return _MODEL["win"]


def test_controls_match_directive_019_on_the_model(tmp_path):
    win = model()
    modes = ("lossless", "sparse", "qp20")
    a = hd.code_counts(win, 1, 1, 12, W, H, modes, 1.0, 0.0, workdir=str(tmp_path))
    b = hc.code_controls(win, 1, 1, 12, W, H, modes + ("lossless_intra", "qp20_intra"), 1.0, 0.0,
                         workdir=str(tmp_path))
    for m in modes:                                    # same encoder, settings and counts: the same bits
        assert b["modes"][m]["bits"] == a["modes"][m]["bits"]
    assert b["modes"]["qp20"]["fid"] == a["modes"]["qp20"]["fid"]
    assert b["clip_fid"]["15"] == a["clip_fid"] and b["clipped"]["15"] == a["clipped_events"]
    s = b["modes"]["lossless_intra"]["summary"]
    assert s["n_I"] == hd.K_WIN * 12 and s["n_P"] == 0
    s = b["modes"]["lossless"]["summary"]
    assert s["n_I"] == 1 and s["n_P"] == hd.K_WIN * 12 - 1
    e = b["modes"]["qp20"]["errors"]
    assert e["in_events"] == sum(b["n_true"]) - b["clipped"]["15"]


def test_controls_are_deterministic(tmp_path):
    win = model()
    modes = ("lossless_intra", "lossless_x16", "qp28_intra", "qp28_s4")
    a = hc.code_controls(win, 1, 2, 3, W, H, modes, 1.0, 0.0, workdir=str(tmp_path))
    b = hc.code_controls(win, 1, 2, 3, W, H, modes, 1.0, 0.0, workdir=str(tmp_path))
    for m in modes:
        assert a["modes"][m]["bits"] == b["modes"][m]["bits"]
        assert a["modes"][m]["fid"] == b["modes"][m]["fid"]


def test_coarse_controls_clip_and_unclipped_list(tmp_path):
    rng = np.random.default_rng(3)
    t = np.sort(rng.integers(hd.T0, 5 * hd.T0, 6000))                 # one hot pixel with many events per voxel
    x = np.where(rng.random(6000) < 0.5, 7, rng.integers(0, W, 6000))
    y = np.where(x == 7, 9, rng.integers(0, H, 6000))
    p = rng.integers(0, 2, 6000)
    o = np.argsort(t, kind="stable")
    ev = tuple(a[o].astype(np.int64) for a in (t, x, y, p))
    win = hd.windows_of(ev, 1, hd.K_WIN)
    r = hc.code_controls(win, 1, 2, 1, W, H, ("lossless_c255", "sparse_raw", "sparse", "qp28", "qp28_s4"), 1.0, 0.0,
                         workdir=str(tmp_path))
    assert r["raw_max"] > 63 and r["clipped"]["15"] > r["clipped"]["63"] > r["clipped"]["255"] >= 0
    assert r["clip_fid"]["255"]["F"] >= r["clip_fid"]["63"]["F"] >= r["clip_fid"]["15"]["F"]
    assert r["modes"]["sparse_raw"]["bits"] >= r["modes"]["sparse"]["bits"]
    assert r["modes"]["qp28_s4"]["errors"]["in_events"] == r["raw_events"] - r["clipped"]["63"]


def test_s4_modes_differ_only_in_the_clip(tmp_path):
    win = model()
    r = hc.code_controls(win, 1, 2, 3, W, H, ("qp28_s4", "qp28_s4c15"), 1.0, 0.0, workdir=str(tmp_path))
    assert r["raw_max"] <= 15                                          # nothing to clip on the model
    a, b = r["modes"]["qp28_s4"], r["modes"]["qp28_s4c15"]
    assert a["bits"] == b["bits"] and a["fid"] == b["fid"] and a["errors"] == b["errors"]


def test_tasks_run_at_both_placements(tmp_path):
    class Tasks:
        def run(self, ev):
            return {"n": int(sum(len(e[0]) for e in ev)), "t0": int(ev[0][0].min()) if len(ev[0][0]) else -1}
    win = model()
    r = hc.code_controls(win, 1, 1, 3, W, H, ("qp20", "lossless"), 1.0, 0.0, tasks=Tasks(), task_modes=("qp20",),
                         workdir=str(tmp_path))
    t = r["modes"]["qp20"]["tasks"]
    assert set(t) == set(hd.PLACEMENTS) and t["start"]["n"] == t["center"]["n"]
    assert t["start"]["t0"] < t["center"]["t0"] and "tasks" not in r["modes"]["lossless"]
