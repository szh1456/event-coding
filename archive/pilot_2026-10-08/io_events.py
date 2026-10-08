"""Event file readers for the pilot. Read-only. Returns t (int64, microseconds), x, y (int32), p (uint8)."""
import numpy as np


def load_evt2(path):
    """Prophesee EVT 2.0 raw file: ASCII header lines starting with '%', then little-endian 32-bit words.
    Word layout (vendor documentation): bits 31-28 type, CD events: bits 27-22 time low (6 bits),
    21-11 x, 10-0 y. Type 0x0 = CD OFF, 0x1 = CD ON, 0x8 = TIME_HIGH (28-bit payload)."""
    with open(path, "rb") as f:
        raw = f.read()
    pos = 0
    header = []
    while pos < len(raw) and raw[pos:pos + 1] == b"%":
        end = raw.index(b"\n", pos)
        header.append(raw[pos:end].decode("ascii", "replace"))
        pos = end + 1
    nwords = (len(raw) - pos) // 4
    w = np.frombuffer(raw, dtype="<u4", count=nwords, offset=pos)
    typ = w >> 28
    is_th = typ == 0x8
    is_cd = typ <= 0x1
    th_val = (w & 0x0FFFFFFF).astype(np.int64)
    idx = np.where(is_th, np.arange(nwords), -1)
    np.maximum.accumulate(idx, out=idx)
    has_th = idx >= 0
    th = np.where(has_th, th_val[np.maximum(idx, 0)], 0)
    keep = is_cd & has_th
    wc = w[keep]
    t = (th[keep] << 6) | ((wc >> 22) & 0x3F).astype(np.int64)
    x = ((wc >> 11) & 0x7FF).astype(np.int32)
    y = (wc & 0x7FF).astype(np.int32)
    p = (wc >> 28).astype(np.uint8)
    info = dict(header=header, nwords=int(nwords), n_cd=int(is_cd.sum()), n_time_high=int(is_th.sum()),
                n_other=int((~is_cd & ~is_th).sum()), n_cd_before_first_time_high=int((is_cd & ~has_th).sum()),
                payload_bytes=int(nwords * 4))
    return t, x, y, p, info


def load_txt(path):
    """ECD text format: 't[s] x y p' per line."""
    a = np.loadtxt(path, dtype=np.float64)
    t = np.round(a[:, 0] * 1e6).astype(np.int64)
    return t, a[:, 1].astype(np.int32), a[:, 2].astype(np.int32), a[:, 3].astype(np.uint8), dict(nlines=int(a.shape[0]))


def load_h5(path):
    import h5py
    with h5py.File(path, "r") as f:
        names = []
        f.visit(names.append)
        g = f["events"] if "events" in f else f
        keys = list(g.keys()) if hasattr(g, "keys") else []
        def pick(*c):
            for k in c:
                if k in g:
                    return g[k][...]
            raise KeyError(c)
        t = pick("t", "ts", "timestamp").astype(np.int64)
        x = pick("x").astype(np.int32)
        y = pick("y").astype(np.int32)
        p = pick("p", "polarity").astype(np.int64)
        info = dict(names=names[:40], keys=keys, attrs={k: str(v) for k, v in f.attrs.items()})
    p = (p > 0).astype(np.uint8)
    return t, x, y, p, info
