import numpy as np

from ec import annotations as A, synth


def test_tracks_and_box_interpolation():
    sc = synth.rigid_translation(v=(90.0, 30.0), duration_s=1.0, n_points=20, seed=3)
    (tr,) = A.tracks(sc.boxes)
    assert tr.track_id == 1 and tr.t_first == 0
    cx, cy = tr.center(500_000)
    assert abs(float(cx) - (40.0 + 45.0)) < 1e-3 and abs(float(cy) - (120.0 + 15.0)) < 1e-3
    vx, vy = tr.velocity(600_000, 100_000)
    assert abs(vx - 90.0) < 1e-2 and abs(vy - 30.0) < 1e-2


def test_in_box_mask_selects_object_events_and_few_noise_events():
    sc = synth.rigid_translation(v=(200.0, 0.0), duration_s=1.0, n_points=80, noise_rate_hz=5.0, seed=4)
    (tr,) = A.tracks(sc.boxes)
    m = A.in_box_mask(tr, sc.t, sc.x, sc.y, margin_px=2.0)
    alive = sc.t <= tr.t_last
    assert m[(sc.src >= 0) & alive].mean() > 0.99
    assert m[sc.src < 0].mean() < 0.1


def test_find_annotation_maps_the_recording_id(tmp_path):
    d = tmp_path / "train" ; d.mkdir()
    np.save(d / "train_day_0001_bbox.npy", np.zeros(0, dtype=synth.BOX_DTYPE))
    assert A.find_annotation(tmp_path, "train_day_0001_td").endswith("train_day_0001_bbox.npy")
