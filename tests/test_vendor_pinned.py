"""The baseline modules are verbatim copies of the companion project and are never edited here."""
import hashlib
import json
import pathlib

V = pathlib.Path(__file__).resolve().parent.parent / "vendor" / "scene_bandwidth"


def test_vendored_files_match_the_recorded_hashes():
    src = json.loads((V / "SOURCE.json").read_text())
    assert src["source_repository"] == "szh1456/scene-bandwidth"
    for rel, digest in src["sha256"].items():
        assert hashlib.sha256((V / rel).read_bytes()).hexdigest() == digest, rel
    present = sorted(str(p.relative_to(V)) for p in V.rglob("*.py"))
    assert present == sorted(src["sha256"]), "a file was added to or removed from the vendored set"


def test_population_is_the_112_train_recordings():
    import re
    txt = (V.parent.parent / "config" / "population.yaml").read_text()
    ids = re.findall(r"^\s+-\s+(\S+)\s*$", txt, flags=re.M)
    assert len(ids) == len(set(ids)) == 112
    assert all(i.startswith("train_") and i.endswith("_td") for i in ids)
    assert sum(i.startswith("train_day_") for i in ids) == 61
    digest = hashlib.sha256("\n".join(sorted(ids)).encode()).hexdigest()
    assert f"ids_sorted_sha256: {digest}" in txt
