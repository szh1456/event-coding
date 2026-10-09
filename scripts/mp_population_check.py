"""Directive 001, Section 4: resolve the population's file names before any event file is opened.

Runs on the execution host. Stats constructed paths only; opens, lists and hashes nothing.
Usage: python3 scripts/mp_population_check.py OUT.json [DIRECTIVE]  (default 001; also used by directive 002)
"""
import datetime
import json
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ec import mp  # noqa: E402


def main(out, directive="001"):
    ids, d = mp.load_population()
    rows = mp.resolve(ids)
    names = [r["event_file"] for r in rows] + [r["annotation_file"] for r in rows]
    outside = [n for n in names if n.startswith(mp.FORBIDDEN_PREFIXES)
               or not any(n.startswith(i[:-3] if i.endswith("_td") else i) for i in ids)]
    res = {
        "directive": directive,
        "host": socket.gethostname(),
        "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "commit": (Path(__file__).resolve().parent.parent / "COMMIT").read_text().strip()
        if (Path(__file__).resolve().parent.parent / "COMMIT").exists() else "UNKNOWN",
        "population": "config/population.yaml",
        "ids_sorted_sha256": mp.ids_sha256(ids),
        "ids_sorted_sha256_expected": d["ids_sorted_sha256"],
        "n_recordings": len(ids),
        "event_dir": str(mp.EVENT_DIR),
        "annotation_dir": str(mp.ANN_DIR),
        "method": "paths constructed from the identifiers and checked with os.path.isfile; no directory listed, "
                  "no file opened or hashed",
        "n_event_found": sum(r["event_found"] for r in rows),
        "n_annotation_found": sum(r["annotation_found"] for r in rows),
        "names_outside_population": outside,
        "names_starting_val_or_test": [n for n in names if n.startswith(mp.FORBIDDEN_PREFIXES)],
        "statement": "every resolved event and annotation file name belongs to a recording of config/population.yaml; "
                     "none starts with val_ or test_" if not outside else "NAMES OUTSIDE THE POPULATION: BLOCKED",
        "files": rows,
    }
    Path(out).write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps({k: v for k, v in res.items() if k != "files"}, indent=1))
    return 0 if not outside else 1


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:3]))
