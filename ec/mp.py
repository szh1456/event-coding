"""Population and file paths for directive 001 (track ``mp``) on the execution host.

Paths are built from the recording identifiers of ``config/population.yaml`` and
checked with ``os.path.isfile`` only. No data or annotation directory is ever
listed or globbed, so no file outside the population is named, opened or hashed.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
POPULATION_YAML = REPO / "config" / "population.yaml"

# docs/DATA.md, first event location (companion directive report 004)
EVENT_DIR = Path.home() / "prjs" / "sbu_full_staging" / "data"
# docs/DATA.md; the train archive was unpacked into this subdirectory by the companion project
ANN_DIR = Path.home() / "prjs" / "sbc_run" / "etram_annotations" / "train" / "eight_class_annotations_train"

FORBIDDEN_PREFIXES = ("val_", "test_")


def ids_sha256(ids) -> str:
    """SHA-256 of the sorted identifiers joined by newlines (the encoding of ``ids_sorted_sha256``)."""
    return hashlib.sha256("\n".join(sorted(ids)).encode()).hexdigest()


def load_population(path=POPULATION_YAML) -> tuple[list[str], dict]:
    d = yaml.safe_load(Path(path).read_text())
    ids = sorted(d["development"])
    if len(ids) != d["n_development"] or ids_sha256(ids) != d["ids_sorted_sha256"]:
        raise ValueError("population.yaml: identifier list does not match its count or hash")
    bad = [i for i in ids if i.startswith(FORBIDDEN_PREFIXES) or not i.startswith("train_")]
    if bad:
        raise ValueError(f"population.yaml names recordings outside the train set: {bad}")
    return ids, d


def lighting(recording_id: str) -> str:
    if recording_id.startswith("train_day_"):
        return "day"
    if recording_id.startswith("train_night_"):
        return "night"
    raise ValueError(recording_id)


def event_path(recording_id: str) -> Path:
    return EVENT_DIR / f"{recording_id}.h5"


def annotation_path(recording_id: str) -> Path:
    stem = recording_id[:-3] if recording_id.endswith("_td") else recording_id
    return ANN_DIR / f"{stem}_bbox.npy"


def resolve(ids) -> list[dict]:
    """Constructed paths and whether each is a regular file. Never lists a directory."""
    return [{"recording_id": r, "event_file": event_path(r).name, "event_found": os.path.isfile(event_path(r)),
             "annotation_file": annotation_path(r).name, "annotation_found": os.path.isfile(annotation_path(r))}
            for r in ids]
