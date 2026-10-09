"""Directive 005, Section 4: the per-row files read, with their SHA-256 checked against the provenance files.

  python3 scripts/dg_population_check.py GP_PROVENANCE.json AF_PROVENANCE.json OUT.json

Reads and hashes only this project's per-row files of directive 003 (Stage C) and 004 (Stage A).
No event file and no annotation file is opened, listed or hashed.
"""
import datetime
import hashlib
import json
import socket
import sys
from pathlib import Path


def main(gp_prov, af_prov, out):
    commit = (Path(__file__).resolve().parent.parent / "COMMIT").read_text().strip()
    sets = {"directive_003_stage_C": json.loads(Path(gp_prov).read_text())["per_row_files"],
            "directive_004_stage_A": json.loads(Path(af_prov).read_text())["per_row_files"]}
    res = {"directive": "005", "host": socket.gethostname(), "commit": commit,
           "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
           "statement": "no event file and no annotation file is opened, listed or hashed; only the per-row files "
                        "below are read", "files": {}}
    ok = True
    for name, files in sets.items():
        rows = []
        for f in files:
            p = Path(f["path"])
            h = hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
            rows.append({"path": f["path"], "sha256": f["sha256"], "sha256_matches": h == f["sha256"]})
        bad = [r for r in rows if not r["sha256_matches"]]
        ok &= not bad and len(rows) == 700
        res["files"][name] = {"n_files": len(rows), "n_sha256_mismatch": len(bad), "list": rows}
    names = [r["path"] for v in res["files"].values() for r in v["list"]]
    res["names_event_or_annotation_files"] = [n for n in names if n.endswith((".h5", "_bbox.npy"))]
    res["pass"] = ok and not res["names_event_or_annotation_files"]
    Path(out).write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps({k: v for k, v in res.items() if k != "files"} |
                     {"files": {k: {kk: vv for kk, vv in v.items() if kk != "list"} for k, v in res["files"].items()}},
                     indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:4])
