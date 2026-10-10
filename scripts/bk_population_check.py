"""Directive 007, Sections 4 and 6: event file names of the population and the two subsets.

  python3 scripts/bk_population_check.py OUT.json

Builds no annotation path. Stats the constructed event paths only; opens, lists and hashes nothing.
"""
import datetime
import json
import os
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ec import mp  # noqa: E402


def subsets(ids):
    day = sorted(i for i in ids if mp.lighting(i) == "day")
    night = sorted(i for i in ids if mp.lighting(i) == "night")
    tuning = [lst[k] for lst in (day, night) for k in (0, 10, 20, 30, 40, 50)]
    return tuning, sorted(set(ids) - set(tuning))


def main(out):
    ids, d = mp.load_population()
    files = [{"recording_id": r, "event_file": mp.event_path(r).name, "event_found": os.path.isfile(mp.event_path(r))}
             for r in ids]
    tuning, reporting = subsets(ids)
    outside = [f["event_file"] for f in files if f["event_file"].startswith(mp.FORBIDDEN_PREFIXES)
               or f["event_file"] != f["recording_id"] + ".h5"]
    res = {"directive": "007", "host": socket.gethostname(),
           "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
           "commit": (mp.REPO / "COMMIT").read_text().strip() if (mp.REPO / "COMMIT").exists() else "UNKNOWN",
           "population": "config/population.yaml", "ids_sorted_sha256": mp.ids_sha256(ids),
           "ids_sorted_sha256_expected": d["ids_sorted_sha256"], "n_recordings": len(ids),
           "event_dir": str(mp.EVENT_DIR), "annotation_paths_built": 0,
           "method": "event paths constructed from the identifiers and checked with os.path.isfile; no directory "
                     "listed, no file opened or hashed; no annotation path built",
           "n_event_found": sum(f["event_found"] for f in files), "names_outside_population": outside,
           "statement": "every event file name belongs to a recording of config/population.yaml; none starts with "
                        "val_ or test_" if not outside else "NAMES OUTSIDE THE POPULATION: BLOCKED",
           "tuning_subset": tuning, "reporting_subset": reporting,
           "subset_rule": "sorted day ids and sorted night ids; tuning = positions 0, 10, 20, 30, 40, 50 of each",
           "files": files}
    Path(out).write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps({k: v for k, v in res.items() if k not in ("files", "reporting_subset")}, indent=1))
    return 0 if not outside and res["n_event_found"] == 112 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
