"""Gate for directive 009: the reader of DSEC event files, on files written here in the documented layout."""
import h5py
import numpy as np
import pytest

from ec import blockcodec as bc, dsec


def _write(path, t, x, y, p, t_offset=1_000_000, dtypes=("uint16", "uint16", "uint32", "uint8")):
    with h5py.File(path, "w") as f:
        for k, v, dt in zip(("x", "y", "t", "p"), (x, y, t, p), dtypes):
            f.create_dataset(f"events/{k}", data=np.asarray(v).astype(dt), compression="gzip")
        if t_offset is not None:
            f.create_dataset("t_offset", data=np.int64(t_offset))
        f.create_dataset("ms_to_idx", data=np.arange(3, dtype=np.uint64))


def _events(n=5000, seed=0):
    rng = np.random.default_rng(seed)
    return (np.sort(rng.integers(0, 400_000, n)), rng.integers(0, dsec.WIDTH, n), rng.integers(0, dsec.HEIGHT, n),
            rng.integers(0, 2, n))


def test_a_file_in_the_documented_layout_is_read_as_it_is(tmp_path):
    t, x, y, p = _events()
    _write(tmp_path / "events.h5", t, x, y, p)
    rt, rx, ry, rp, info = dsec.read_events(tmp_path / "events.h5")
    assert all(a.dtype == np.int64 for a in (rt, rx, ry, rp))
    assert np.array_equal(rt, t) and np.array_equal(rx, x) and np.array_equal(ry, y) and np.array_equal(rp, p)
    assert info["n_events"] == 5000 and info["t_offset_us"] == 1_000_000 and info["n_time_inversions_clamped"] == 0
    assert info["t_first_us"] == t[0] and info["t_last_us"] == t[-1] and info["dtypes"]["t"] == "uint32"
    d = dsec.describe(tmp_path / "events.h5")
    assert d["/events/t"]["shape"] == [5000] and d["/events/x"]["dtype"] == "uint16" and "/t_offset" in d
    assert (dsec.WIDTH, dsec.HEIGHT) == (640, 480) and 640 % 20 == 0 and 480 % 20 == 0


def test_the_stored_times_are_returned_without_the_offset_and_a_missing_offset_is_reported(tmp_path):
    t, x, y, p = _events()
    _write(tmp_path / "a.h5", t, x, y, p, t_offset=None)
    rt, *_, info = dsec.read_events(tmp_path / "a.h5")
    assert info["t_offset_us"] is None and rt[0] == t[0]


def test_decreasing_times_are_clamped_and_counted(tmp_path):
    t, x, y, p = _events()
    t = t.copy()
    t[100], t[2000] = t[99] - 5, t[1999] - 1
    _write(tmp_path / "a.h5", t, x, y, p)
    rt, *_, info = dsec.read_events(tmp_path / "a.h5")
    assert info["n_time_inversions_clamped"] == 2 and (np.diff(rt) >= 0).all()
    assert rt[100] == t[99] and rt[2000] == t[1999]


def test_a_file_that_differs_from_the_documentation_stops_the_run(tmp_path):
    t, x, y, p = _events()
    with h5py.File(tmp_path / "no_events.h5", "w") as f:
        f.create_dataset("x", data=x)
    with pytest.raises(ValueError):
        dsec.read_events(tmp_path / "no_events.h5")
    bad = x.copy(); bad[3] = 640
    _write(tmp_path / "x.h5", t, bad, y, p)
    with pytest.raises(ValueError):
        dsec.read_events(tmp_path / "x.h5")
    bad = y.copy(); bad[3] = 480
    _write(tmp_path / "y.h5", t, x, bad, p)
    with pytest.raises(ValueError):
        dsec.read_events(tmp_path / "y.h5")
    _write(tmp_path / "p.h5", t, x, y, p * 2)
    with pytest.raises(ValueError):
        dsec.read_events(tmp_path / "p.h5")
    _write(tmp_path / "len.h5", t[:-1], x[:-1], y[:-1], p[:-1])
    with h5py.File(tmp_path / "len.h5", "a") as f:
        del f["events/p"]
        f.create_dataset("events/p", data=p.astype("uint8"))
    with pytest.raises(ValueError):
        dsec.read_events(tmp_path / "len.h5")


def test_the_codec_runs_on_the_sensor_of_the_second_dataset(tmp_path):
    # a dense moving bar on 640 x 480, read back through the reader and coded at the frozen configuration
    rng = np.random.default_rng(1)
    n = 60_000
    t = np.sort(rng.integers(0, 12 * bc.T0_US, n))
    x = (300 + 150e-6 * t + rng.integers(0, 40, n)).astype(np.int64) % dsec.WIDTH
    y = rng.integers(200, 240, n)
    p = rng.integers(0, 2, n)
    _write(tmp_path / "bar.h5", t, x, y, p)
    rt, rx, ry, rp, _ = dsec.read_events(tmp_path / "bar.h5")
    g = bc.evaluate_group(rt, rx, ry, rp, 0, 0, dsec.WIDTH, dsec.HEIGHT, blocks=(20,), densities=(1.0,),
                          models=("static", "translation"), records_for=(20, 1.0))
    row = g["codec"]["B20_rho1.0"]
    assert row["n_active"] > 0 and all(r["claim_equals_match"] and r["q_equals_t"] for r in row["models"].values())
    stream = bc.encode_header("Q", "translation", 4, dsec.WIDTH, dsec.HEIGHT, 20) + g["records"]["translation_Q_K4"]
    rec = bc.evaluate_stream(stream, rt, rx, ry, rp)[0]
    assert rec["match"] == [row["n_key"]] + row["models"]["translation"]["match_s2_k3"][:3]
    assert bc.decode_header(stream)["width"] == 640 and bc.decode_header(stream)["height"] == 480
