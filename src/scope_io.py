"""Oscilloscope waveform import / export (hardware side).

``load_waveform(path)`` reads the CSV exports of the common bench scopes
without knowing the model in advance:

* this project's own format (written by ``src.capture``): ``# key: value``
  header lines, then ``time_s,voltage_v``
* Rigol DS1000Z / MSO1000Z: ``X,CH1,Start,Increment`` header, sample index column
* Tektronix TBS1000 / TDS2000 (legacy): 6 columns, header key/values in
  columns 1-2, time/volts in columns 4-5
* Tektronix MSO/MDO, Keysight InfiniiVision, Siglent, Rigol DHO and any other
  "header lines + numeric columns" CSV (time column auto-detected)
* a bare 1- or 2-column numeric file (pass ``ts=`` for voltage-only files)

Times are returned in seconds and volts in volts. The first scope session
should check one exported file with ``python index.py inspect <file>``.
"""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

VENDOR_PATTERNS = {
    "Rigol": r"rigol|ds1\d{3}z|dho\d|mso[58]\d{3}",
    "Tektronix": r"tektronix|\btbs\d|\btds\d|\bmdo\d|\bmso[2-6]\d?\b",
    "Keysight": r"keysight|agilent|dsox|msox|infiniivision",
    "Siglent": r"siglent|\bsds\d",
}
UNIT_SCALE = {"s": 1.0, "ms": 1e-3, "us": 1e-6, "µs": 1e-6, "ns": 1e-9, "ps": 1e-12,
              "v": 1.0, "mv": 1e-3, "uv": 1e-6, "kv": 1e3}


@dataclass
class Waveform:
    t: np.ndarray
    v: np.ndarray
    ts: float
    meta: dict = field(default_factory=dict)
    fmt: str = ""
    vendor: str = "unknown"
    source: str = ""

    def summary(self) -> str:
        return (f"{self.source}: {len(self.t)} samples, Ts = {self.ts * 1e9:.4g} ns, "
                f"t = {self.t[0] * 1e9:.1f} .. {self.t[-1] * 1e9:.1f} ns, "
                f"v = {self.v.min():.3g} .. {self.v.max():.3g} V, format = {self.fmt}, vendor = {self.vendor}")


def _num(s: str) -> float | None:
    try:
        return float(s.strip())
    except (ValueError, AttributeError):
        return None


def _guess_vendor(text: str) -> str:
    low = text.lower()
    for name, pat in VENDOR_PATTERNS.items():
        if re.search(pat, low):
            return name
    return "unknown"


def _unit_from_name(name: str, default: float = 1.0) -> float:
    m = re.search(r"[\(\[]\s*([a-zµ]+)\s*[\)\]]", name.lower())
    if m and m.group(1) in UNIT_SCALE:
        return UNIT_SCALE[m.group(1)]
    return default


def _finish(t, v, meta, fmt, text, source) -> Waveform:
    t = np.asarray(t, float)
    v = np.asarray(v, float)
    ok = np.isfinite(t) & np.isfinite(v)
    t, v = t[ok], v[ok]
    if t.size < 10:
        raise ValueError("fewer than 10 valid samples")
    if np.any(np.diff(t) <= 0):
        o = np.argsort(t, kind="stable")
        t, v = t[o], v[o]
    dt = np.diff(t)
    ts = float(np.median(dt))
    if ts <= 0:
        raise ValueError("time column is not increasing")
    if np.std(dt) > 0.05 * ts:
        meta["warning"] = "non-uniform sampling"
    vendor = meta.get("vendor") or _guess_vendor(text)
    return Waveform(t, v, ts, meta, fmt, vendor, source)


def parse_text(text: str, channel: int | str | None = None, ts: float | None = None,
               source: str = "") -> Waveform:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        raise ValueError("empty file")
    meta: dict = {}

    # ---- own format
    if lines[0].startswith("#"):
        body = []
        for ln in lines:
            if ln.startswith("#"):
                if ":" in ln:
                    k, val = ln[1:].split(":", 1)
                    meta[k.strip()] = val.strip()
            else:
                body.append(ln)
        rows = list(csv.reader(body))
        data = np.array([[float(x) for x in r[:2]] for r in rows if _num(r[0]) is not None])
        return _finish(data[:, 0], data[:, 1], meta, "tdr-csv", text, source)

    rows = list(csv.reader(io.StringIO("\n".join(lines))))

    # ---- Rigol DS1000Z style: X,CH1,...,Start,Increment / Sequence,Volt,<start>,<inc>
    head = [c.strip().lower() for c in rows[0]]
    if head and head[0] == "x" and "start" in head and "increment" in head and len(rows) > 2:
        names = [c.strip() for c in rows[0]]
        i_start, i_inc = head.index("start"), head.index("increment")
        start, inc = _num(rows[1][i_start]), _num(rows[1][i_inc])
        ch_cols = [i for i, n in enumerate(names) if n.upper().startswith(("CH", "D", "MATH")) and i not in (0, i_start, i_inc)]
        col = _pick_col(names, ch_cols, channel)
        data = [(r[0], r[col]) for r in rows[2:] if len(r) > col and _num(r[0]) is not None]
        idx = np.array([float(a) for a, _ in data])
        v = np.array([_num(b) if _num(b) is not None else np.nan for _, b in data])
        meta.update({"Start": start, "Increment": inc, "channel": names[col], "vendor": "Rigol"})
        return _finish(start + idx * inc, v, meta, "rigol-xstart", text, source)

    # ---- Tektronix legacy 6-column
    if rows[0] and rows[0][0].strip().lower() == "record length" and len(rows[0]) >= 5:
        for r in rows[:30]:
            if r and r[0].strip():
                meta[r[0].strip()] = r[1].strip() if len(r) > 1 else ""
        data = [(r[3], r[4]) for r in rows if len(r) >= 5 and _num(r[3]) is not None and _num(r[4]) is not None]
        arr = np.array(data, float)
        meta["vendor"] = "Tektronix"
        return _finish(arr[:, 0], arr[:, 1], meta, "tek-6col", text, source)

    # ---- generic: header block followed by a numeric block
    numeric = [sum(_num(c) is not None for c in r) >= 1 and _num(r[0]) is not None for r in rows]
    start = len(rows)
    for i in range(len(rows) - 1, -1, -1):
        if numeric[i]:
            start = i
        else:
            break
    if start >= len(rows):
        raise ValueError("no numeric data block found")
    for r in rows[:start]:
        if len(r) >= 2 and r[0].strip():
            meta[r[0].strip()] = ",".join(c.strip() for c in r[1:] if c.strip())
    names = [c.strip() for c in rows[start - 1]] if start > 0 else []
    ncol = max(len(r) for r in rows[start:start + 20])
    arr = np.full((len(rows) - start, ncol), np.nan)
    for i, r in enumerate(rows[start:]):
        for j, c in enumerate(r[:ncol]):
            x = _num(c)
            if x is not None:
                arr[i, j] = x
    good = [j for j in range(ncol) if np.isfinite(arr[:, j]).mean() > 0.9]
    if not good:
        raise ValueError("no usable numeric columns")
    if len(good) == 1 or ts is not None:          # voltage only
        if ts is None:
            ts = _ts_from_meta(meta)
        if ts is None:
            raise ValueError("voltage-only file: pass ts= (sample interval in s)")
        vcol = good[-1] if channel is None else _pick_col(names, good, channel)
        v = arr[:, vcol]
        return _finish(ts * np.arange(len(v)), v, meta, "voltage-only", text, source)
    tcol = _time_col(arr, good, names)
    vcols = [j for j in good if j != tcol]
    vcol = _pick_col(names, vcols, channel)
    t = arr[:, tcol]
    if _looks_like_index(t):
        ts_meta = _ts_from_meta(meta)
        if ts_meta:
            t = t * ts_meta
    tname = names[tcol] if tcol < len(names) else ""
    vname = names[vcol] if vcol < len(names) else ""
    t = t * _unit_from_name(tname)
    v = arr[:, vcol] * _unit_from_name(vname)
    meta.update({"time_column": tname, "channel": vname})
    return _finish(t, v, meta, "generic-csv", text, source)


def _pick_col(names, cols, channel):
    if not cols:
        raise ValueError("no channel column")
    if channel is None or (isinstance(channel, float) and np.isnan(channel)) or str(channel).strip() == "":
        return cols[0]
    if isinstance(channel, (float, np.floating)) and float(channel).is_integer():
        channel = int(channel)   # "1.0" from a float log column
    if isinstance(channel, (int, np.integer)) or str(channel).isdigit():
        want = int(channel)
        for c in cols:
            if c < len(names) and re.search(rf"(ch|c|channel)\s*{want}\b", names[c].lower()):
                return c
        return cols[min(want - 1, len(cols) - 1)]
    for c in cols:
        if c < len(names) and names[c].lower() == str(channel).lower():
            return c
    raise ValueError(f"channel {channel!r} not found in {names}")


def _time_col(arr, good, names):
    for j in good:
        if j < len(names) and re.search(r"time|second|^s$|x-axis|^x$", names[j].lower()):
            return j
    for j in good:
        col = arr[:, j]
        if np.all(np.diff(col[np.isfinite(col)]) > 0):
            return j
    return good[0]


def _looks_like_index(t):
    return np.allclose(t, np.round(t)) and np.allclose(np.diff(t), 1)


def _ts_from_meta(meta):
    for k, v in meta.items():
        if re.search(r"sample interval|increment|xinc|horizontal.*(interval|scale)|^ts$", k.lower()):
            x = _num(str(v).split(",")[0])
            if x and x > 0:
                return x
    return None


def load_waveform(path: str | Path, channel=None, ts: float | None = None) -> Waveform:
    path = Path(path)
    if path.suffix.lower() in (".npz",):
        z = np.load(path)
        return _finish(z["t"], z["v"], {}, "npz", "", str(path))
    raw = path.read_bytes()
    text = raw.decode("utf-8-sig", errors="replace")
    return parse_text(text, channel=channel, ts=ts, source=str(path))


def save_waveform(path: str | Path, t, v, meta: dict | None = None) -> Path:
    """Write the project's own CSV format (lossless, self-describing)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        fh.write("# format: tdr-csv v1\n")
        for k, val in (meta or {}).items():
            fh.write(f"# {k}: {str(val).replace(chr(10), ' ')}\n")
        fh.write("time_s,voltage_v\n")
        for a, b in zip(t, v):
            fh.write(f"{a:.6e},{b:.6e}\n")
    return path
