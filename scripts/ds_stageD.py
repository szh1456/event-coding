"""Directive 009, Stage D: the list of sequences, the download, the format check and the inventory.

  python3 scripts/ds_stageD.py list PAGE.html OUT.yaml          # step 1, from the saved download page
  python3 scripts/ds_stageD.py popcheck POP.yaml OUT.json        # step 2, before any event file is opened
  python3 scripts/ds_stageD.py recheck POP.yaml OUT.json         # Amendment 1, A1.3
  python3 scripts/ds_stageD.py space POP.yaml [PATH]              # step 3 (A1.2: on /data)
  python3 scripts/ds_stageD.py download POP.yaml DATADIR LOG.json # step 4
  python3 scripts/ds_stageD.py format POP.yaml DATADIR OUT.json   # steps 5 and 6

Only ``https://download.ifi.uzh.ch/rpg/DSEC/train/<seq>/<seq>_events_left.zip`` is downloaded. Each
archive is unpacked into ``DATADIR/<seq>/``; the left event file is kept and every other member is
deleted and listed in the log.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import yaml

PAGE_URL = "https://dsec.ifi.uzh.ch/dsec-datasets/download/"
PATTERN = re.compile(r"https://download\.ifi\.uzh\.ch/rpg/DSEC/train/([a-z0-9_]+)/\1_events_left\.zip")
DATA_DIR = Path("/data") / os.environ.get("USER", "") / "event_coding" / "dsec"   # Amendment 1, A1.1
KEEP = "events.h5"                          # the left event file inside the archive (verified in step 4)


def head_size(url):
    out = subprocess.run(["curl", "-sSIL", "--max-time", "60", url], capture_output=True, text=True, check=True).stdout
    sizes = re.findall(r"(?im)^content-length:\s*(\d+)", out)
    codes = re.findall(r"(?m)^HTTP/\S+\s+(\d+)", out)
    return (int(sizes[-1]) if sizes else None), (int(codes[-1]) if codes else None)


def cmd_list(page, out):
    html = Path(page).read_text(errors="replace")
    seqs = sorted(set(PATTERN.findall(html)))
    rows = []
    for s in seqs:
        url = f"https://download.ifi.uzh.ch/rpg/DSEC/train/{s}/{s}_events_left.zip"
        size, code = head_size(url)
        rows.append({"name": s, "url": url, "size_bytes": size, "http_status": code})
    lic = re.findall(r"(?is)(licen[cs]e[^<]{0,400})", re.sub(r"<[^>]+>", " ", html))
    doc = {"dataset": "DSEC", "split": "train", "camera": "left event camera",
           "page": PAGE_URL, "page_retrieved_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
           "page_sha256": hashlib.sha256(Path(page).read_bytes()).hexdigest(),
           "rule": "every sequence of the training split that the page offers as <seq>_events_left.zip",
           "size_source": "Content-Length of a HEAD request to the official host",
           "n_sequences": len(rows), "total_bytes": sum(r["size_bytes"] or 0 for r in rows),
           "license_text_on_page": [" ".join(x.split())[:400] for x in lic[:3]],
           "sequences": rows}
    Path(out).write_text(yaml.safe_dump(doc, sort_keys=False, width=200))
    print(len(rows), "sequences,", doc["total_bytes"] / 1e9, "GB;", sum(r["http_status"] != 200 for r in rows), "not 200")


def cmd_popcheck(pop, out):
    d = yaml.safe_load(Path(pop).read_text())
    names = [s["name"] for s in d["sequences"]]
    res = {"directive": "009", "population": "config/population_dsec.yaml", "n_sequences": len(names),
           "names_sorted": names == sorted(names), "statement": "no event file of DSEC has been opened; no file of "
           "eTraM is opened by this directive; the files to be downloaded are the left-camera event archives of the "
           "training split listed in config/population_dsec.yaml, from the official host",
           "all_urls_on_official_host": all(s["url"].startswith("https://download.ifi.uzh.ch/rpg/DSEC/train/")
                                            for s in d["sequences"]),
           "none_right_camera_or_test": not any(("right" in s["url"]) or ("/test" in s["url"]) for s in d["sequences"]),
           "sequences": names,
           "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")}
    Path(out).write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps({k: v for k, v in res.items() if k != "sequences"}, indent=1))


def cmd_space(pop, where=None):
    """Step 3 (Amendment 1, A1.2: measured on the filesystem that holds ``where``)."""
    d = yaml.safe_load(Path(pop).read_text())
    total = sum(s["size_bytes"] for s in d["sequences"])
    where = Path(where) if where else Path.home() / "prjs" / "event_coding"
    free = shutil.disk_usage(where).free
    need = 2 * total + 100e9
    print(json.dumps({"path": str(where), "total_bytes": total, "free_bytes": free, "needed_bytes": need,
                      "pass": free > need}))


def cmd_recheck(pop, out):
    """Amendment 1, A1.3: ask the server again for the size of every listed file; any difference stops."""
    d = yaml.safe_load(Path(pop).read_text())
    rows, diff = [], []
    for s in d["sequences"]:
        size, code = head_size(s["url"])
        rows.append({"name": s["name"], "listed": s["size_bytes"], "now": size, "http_status": code})
        if size != s["size_bytes"] or code != 200:
            diff.append(rows[-1])
    res = {"utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"), "n": len(rows),
           "n_differ": len(diff), "differ": diff, "rows": rows, "pass": not diff}
    Path(out).write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps({k: v for k, v in res.items() if k != "rows"}))


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def cmd_download(pop, datadir, log):
    d = yaml.safe_load(Path(pop).read_text())
    datadir = Path(datadir)
    datadir.mkdir(parents=True, exist_ok=True)
    out = json.loads(Path(log).read_text()) if Path(log).exists() else {}
    for s in d["sequences"]:
        name = s["name"]
        if name in out and out[name].get("kept"):
            continue
        sd = datadir / name
        sd.mkdir(exist_ok=True)
        z = sd / f"{name}_events_left.zip"
        subprocess.run(["curl", "-sSL", "--fail", "--retry", "3", "--max-time", "7200", "-o", str(z), s["url"]], check=True)
        zsize, zsha = z.stat().st_size, sha256(z)
        with zipfile.ZipFile(z) as zf:
            members = [m for m in zf.infolist() if not m.is_dir()]
            names = [m.filename for m in members]
            ev = [m for m in members if Path(m.filename).name == KEEP]
            if len(ev) != 1:
                raise SystemExit(f"{name}: expected one {KEEP} in the archive, found {names}")
            with zf.open(ev[0]) as src, open(sd / "events.h5", "wb") as dst:
                shutil.copyfileobj(src, dst, 1 << 22)
        deleted = [n for n in names if Path(n).name != KEEP]
        z.unlink()
        kept = sd / "events.h5"
        out[name] = {"url": s["url"], "archive_bytes": zsize, "archive_bytes_listed": s["size_bytes"],
                     "archive_sha256": zsha, "archive_members": names,
                     "members_not_kept": deleted, "archive_deleted_after_unpacking": True,
                     "kept": {"path": str(kept), "bytes": kept.stat().st_size, "sha256": sha256(kept)}}
        Path(log).write_text(json.dumps(out, indent=1) + "\n")
        print(name, zsize, "->", out[name]["kept"]["bytes"], "deleted:", deleted, flush=True)
    print("DONE", len(out), flush=True)


def cmd_format(pop, datadir, out):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from ec import dsec
    import h5py
    try:
        import hdf5plugin
        hv = hdf5plugin.version
    except ImportError:
        hv = None
    d = yaml.safe_load(Path(pop).read_text())
    names = [s["name"] for s in d["sequences"]]
    first = Path(datadir) / names[0] / "events.h5"
    res = {"h5py": h5py.__version__, "hdf5plugin": hv, "describe_first_file": {"sequence": names[0],
                                                                                "describe": dsec.describe(first)},
           "inventory": {}, "errors": {}}
    T0, NPIX = 33_333, 640 * 480
    for s in names:
        try:
            t, x, y, p, info = dsec.read_events(Path(datadir) / s / "events.h5")
        except ValueError as e:
            res["errors"][s] = str(e)
            continue
        dur = (info["t_last_us"] - info["t_first_us"]) * 1e-6
        res["inventory"][s] = info | {"duration_s": dur, "events_per_s": info["n_events"] / dur if dur > 0 else None,
                                      "events_per_pixel_and_window": info["n_events"] / NPIX / (dur * 1e6 / T0)}
        print(s, info["n_events"], round(dur, 1), "s", flush=True)
    Path(out).write_text(json.dumps(res, indent=1) + "\n")
    print("errors:", res["errors"])


if __name__ == "__main__":
    {"list": cmd_list, "popcheck": cmd_popcheck, "space": cmd_space, "recheck": cmd_recheck, "download": cmd_download,
     "format": cmd_format}[sys.argv[1]](*sys.argv[2:])
