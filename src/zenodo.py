"""External dataset: Scarpetta et al. 2021, Zenodo 10.5281/zenodo.5720438 (CC BY 4.0).

Pulse TDR on RG-58 (Gaussian pulse, sigma ~ 8 ns, sampled every 4 ns, 1024
samples). 1,000,000 simulated traces with 0-4 parallel capacitive faults
(49-501 pF) on 10-200 m cables (always open-ended), plus 16 real measured
traces (65-143 m, 1-4 capacitive faults).

Following the project brief we reduce every trace to the single-fault targets:
    d_first   distance to the first discontinuity (fault or open end), m
    length    cable length = position of the open end, m
    first_cls class of the first discontinuity: "partial" (capacitive fault) or "open"
(The termination is open in every trace, so a termination class would be constant.)

Security: the label arrays are pickled Python objects. They are read with a
restricted unpickler that only rebuilds plain numbers, lists, tuples, dicts and
numpy arrays, never ``allow_pickle=True``. The authors' TensorFlow model in the
archive is not loaded.

    python index.py zenodo download     # resumable 4.18 GB download (+ size check)
    python index.py zenodo prepare      # labels -> compact arrays, time-axis + baseline calibration
    python index.py zenodo train        # baseline features + RF/ET/KNN/MLP + multi-task 1-D CNN
    python index.py zenodo evaluate     # Z1 held-out sim, Z2 noise sweep, Z3 the 16 real traces
"""
from __future__ import annotations

import argparse
import io
import json
import pickle
import struct
import time
import zlib
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.ndimage import gaussian_filter1d

from .config import DATA_DIR, FIG_DIR, MODELS_DIR, RESULTS_DIR

ZDIR = DATA_DIR / "external" / "zenodo_5720438"
ZIP = ZDIR / "dataset_tdr_2021.zip"
EXP = ZDIR / "experimental_signals.npz"
URL = "https://zenodo.org/records/5720438/files/dataset_tdr_2021.zip?download=1"
ZIP_SIZE = 4_180_670_194
CACHE = ZDIR / "derived"
BUNDLE = MODELS_DIR / "zenodo_models.joblib"

TS = 4e-9                 # sample interval (250 MSa/s, Scarpetta et al.)
PULSE_END = 38            # README: samples [0, 38) hold the transmitted pulse
NOISE = 0.000437          # README: Gaussian noise added to simulated traces
N_TOTAL, N_SAMPLES = 1_000_000, 1024
TRAIN_END = 800_000       # README: first 800k train, last 200k validation
CLASSES_Z = ["open", "partial"]


# ---------------------------------------------------------------- safe pickle
class SafeUnpickler(pickle.Unpickler):
    ALLOWED = {("numpy.core.multiarray", "_reconstruct"), ("numpy._core.multiarray", "_reconstruct"),
               ("numpy", "ndarray"), ("numpy", "dtype"), ("numpy.core.multiarray", "scalar"),
               ("numpy._core.multiarray", "scalar"), ("builtins", "list"), ("builtins", "tuple"),
               ("builtins", "dict"), ("builtins", "float"), ("builtins", "int")}

    def find_class(self, module, name):
        if (module, name) in self.ALLOWED:
            return super().find_class(module, name)
        raise pickle.UnpicklingError(f"blocked unpickling of {module}.{name}")


def _npy_header(fh):
    ver = np.lib.format.read_magic(fh)
    rd = np.lib.format.read_array_header_1_0 if ver == (1, 0) else np.lib.format.read_array_header_2_0
    return rd(fh)


def load_npz_safe(path_or_file) -> dict:
    """np.load replacement for small .npz files with object arrays (restricted unpickling)."""
    out = {}
    with zipfile.ZipFile(path_or_file) as z:
        for n in z.namelist():
            with z.open(n) as fh:
                shape, fortran, dtype = _npy_header(fh)
                if dtype.hasobject:
                    out[n[:-4]] = SafeUnpickler(fh).load()
                else:
                    a = np.frombuffer(fh.read(), dtype=dtype)
                    out[n[:-4]] = a.reshape(shape, order="F" if fortran else "C")
    return out


# ---------------------------------------------------------------- download / access
def download(retries: int = 60):
    """Resumable download of the 4.18 GB archive (HTTP range requests)."""
    ZDIR.mkdir(parents=True, exist_ok=True)
    for attempt in range(retries):
        have = ZIP.stat().st_size if ZIP.exists() else 0
        if have >= ZIP_SIZE:
            break
        try:
            req = urllib.request.Request(URL, headers={"Range": f"bytes={have}-"})
            with urllib.request.urlopen(req, timeout=120) as r, open(ZIP, "ab") as f:
                while chunk := r.read(1 << 20):
                    f.write(chunk)
        except Exception as exc:
            print(f"  attempt {attempt + 1}: {exc}; resuming")
            time.sleep(5)
    size = ZIP.stat().st_size
    print(f"{ZIP} : {size:,d} / {ZIP_SIZE:,d} bytes {'OK' if size == ZIP_SIZE else 'INCOMPLETE'}")
    if not EXP.exists() and size == ZIP_SIZE:
        with zipfile.ZipFile(ZIP) as z:
            EXP.write_bytes(z.read("experimental_signals.npz"))
    return size == ZIP_SIZE


class _Sub(io.RawIOBase):
    """A window [start, start+size) of an open binary file, as its own file."""

    def __init__(self, f, start, size):
        self.f, self.start, self.size, self.pos = f, start, size, 0

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, off, whence=0):
        self.pos = off if whence == 0 else (self.pos + off if whence == 1 else self.size + off)
        return self.pos

    def read(self, n=-1):
        n = self.size - self.pos if n is None or n < 0 else min(n, self.size - self.pos)
        self.f.seek(self.start + self.pos)
        b = self.f.read(n)
        self.pos += len(b)
        return b

    def readinto(self, b):
        d = self.read(len(b))
        b[:len(d)] = d
        return len(d)


def _data_offset(f, header_offset):
    f.seek(header_offset)
    h = f.read(30)
    if h[:4] != b"PK\x03\x04":
        raise ValueError("bad zip local header")
    n, e = struct.unpack("<HH", h[26:30])
    return header_offset + 30 + n + e


def _locate(member: str):
    """(absolute offset, shape, dtype) of an array inside dataset.npz inside the zip."""
    f = open(ZIP, "rb")
    zi = zipfile.ZipFile(f).getinfo("dataset.npz")
    if zi.compress_type != 0:
        raise ValueError("dataset.npz is compressed; extract it first")
    npz0 = _data_offset(f, zi.header_offset)
    sub = _Sub(f, npz0, zi.file_size)
    ii = zipfile.ZipFile(sub).getinfo(member)
    if ii.compress_type != 0:
        raise ValueError(f"{member} is compressed")
    start = _data_offset(sub, ii.header_offset)
    sub.seek(start)
    shape, fortran, dtype = _npy_header(sub)
    return f, sub, npz0 + sub.tell(), shape, dtype


def samples() -> np.memmap:
    """All 1,000,000 x 1024 simulated traces, memory-mapped straight from the zip."""
    f, _, off, shape, dtype = _locate("samples.npy")
    f.close()
    return np.memmap(ZIP, dtype=dtype, mode="r", offset=off, shape=shape)


def labels() -> pd.DataFrame:
    """Compact per-trace labels (cached in data/external/.../derived/labels.npz)."""
    CACHE.mkdir(parents=True, exist_ok=True)
    cp = CACHE / "labels.npz"
    if not cp.exists():
        f, sub, off, shape, dtype = _locate("labels.npy")      # sub is positioned at the data
        raw = SafeUnpickler(io.BufferedReader(sub, buffer_size=1 << 22)).load()
        f.close()
        n = len(raw)
        pos = np.full((n, 5), np.nan, np.float32)
        typ = np.full((n, 5), -1, np.int8)
        cap = np.full((n, 5), np.nan, np.float32)
        for i, lab in enumerate(raw):
            for j, (p, t, v) in enumerate(sorted(lab)):
                pos[i, j], typ[i, j] = p, t
                if t == 0:
                    cap[i, j] = v
        np.savez_compressed(cp, pos=pos, typ=typ, cap=cap)
    z = np.load(cp)
    pos, typ, cap = z["pos"], z["typ"], z["cap"]
    length = np.nanmax(np.where(typ == 1, pos, np.nan), axis=1)
    df = pd.DataFrame({"d_first": pos[:, 0], "length": length,
                       "first_cls": np.where(typ[:, 0] == 0, "partial", "open"),
                       "n_faults": (typ == 0).sum(1),
                       "first_cap_pF": cap[:, 0] * 1e12})
    return df


def real_traces():
    """The 16 measured traces and their labels mapped to our targets."""
    z = load_npz_safe(EXP)
    X = np.asarray(z["samples"], np.float32)
    rows = []
    for lab in z["labels"]:
        p = sorted(lab["position"])
        rows.append({"d_first": float(p[0]) if p else float(lab["length"]), "length": float(lab["length"]),
                     "first_cls": "partial" if p else "open", "n_faults": len(p),
                     "first_cap_pF": float(np.asarray(lab["capacity"])[np.argmin(lab["position"])]) * 1e12 if p else np.nan,
                     "positions": ", ".join(f"{q:g}" for q in p)})
    return X, pd.DataFrame(rows)


# ---------------------------------------------------------------- preprocessing (README)
def s0_constant(S=None) -> float:
    cp = CACHE / "calibration.json"
    if cp.exists():
        return json.loads(cp.read_text())["s0"]
    S = samples() if S is None else S
    return float(np.mean(S[:20000, PULSE_END]))


def preprocess_sim(X, s0: float, noise: float = NOISE, rng=None) -> np.ndarray:
    """README: blank the transmitted pulse with sample 38's mean, add Gaussian noise."""
    rng = rng or np.random.default_rng(0)
    X = np.array(X, dtype=np.float32, copy=True)
    X[:, :PULSE_END] = s0
    X += rng.standard_normal(X.shape, dtype=np.float32) * np.float32(noise)
    return X


def preprocess_real(X, s0: float, rng=None) -> np.ndarray:
    rng = rng or np.random.default_rng(0)
    X = np.array(X, dtype=np.float32, copy=True)
    X[:, :PULSE_END] = s0 + rng.standard_normal((len(X), PULSE_END)).astype(np.float32) * np.float32(NOISE)
    return X


# ---------------------------------------------------------------- conventional baseline
class PulseBaseline:
    """Matched-filter TDR (cross-correlation, cf. Shin et al. 2005), calibrated on training traces.

    Correlates the trace with the incident Gaussian pulse g (open end: positive
    copy of g) and with its derivative g' (parallel capacitor: -tau * g'). The
    first correlation lobe above 6 sigma of the noise is the first discontinuity;
    its type is whichever template fits better. The open end is the positive
    g-lobe with the largest attenuation-compensated amplitude. Event times are
    mapped to metres by a straight line fitted per event type on training data.
    """

    def __init__(self, pulse: np.ndarray, k_sigma: float = 6.0):
        g = pulse - pulse.min()
        g = g / np.linalg.norm(g)
        d = np.gradient(g)
        self.g, self.d = g[::-1].copy(), (d / np.linalg.norm(d))[::-1].copy()
        self.k_sigma = k_sigma
        self.lin = {"open": (1 / 2.539, -24.70 / 2.539), "partial": (1 / 2.539, -24.70 / 2.539)}
        self.beta = 0.0     # attenuation per sample of the open-end pulse
        self.amp0 = 1.0
        self.open_min_score = 0.4

    def _corr(self, x):
        cg = np.convolve(x, self.g, mode="same")
        cd = np.convolve(x, self.d, mode="same")
        return cg, cd

    @staticmethod
    def _refine(y, j):
        if 0 < j < len(y) - 1:
            a, b, c = y[j - 1], y[j], y[j + 1]
            den = a - 2 * b + c
            if den != 0:
                return j + 0.5 * (a - c) / den
        return float(j)

    @staticmethod
    def highpass(x):
        """Remove the slow tail of the transmitted pulse; reflected pulses (~5 samples) survive."""
        return x - gaussian_filter1d(x, 12.0, mode="nearest")

    def events(self, x):
        x = self.highpass(x)
        sig = 1.4826 * np.median(np.abs(x[:PULSE_END] - np.median(x[:PULSE_END]))) + 1e-9
        cg, cd = self._corr(x)
        thr = self.k_sigma * sig
        act = np.maximum(np.abs(cg), np.abs(cd)) > thr
        act[:PULSE_END + 4] = False
        ev = []
        i, n = 0, len(x)
        while i < n:
            if not act[i]:
                i += 1
                continue
            j = i
            while j < n - 1 and act[j + 1]:
                j += 1
            seg = slice(i, j + 1)
            jg = i + int(np.argmax(cg[seg]))
            jd = i + int(np.argmin(cd[seg]))
            eg, ed = cg[jg], cd[jd]
            if eg > 0 and eg >= abs(ed):
                ev.append(("open", self._refine(cg, jg), eg, ed))
            elif ed < 0:
                ev.append(("partial", self._refine(-cd, jd), eg, ed))
            else:                          # negative pulse: treat as fault-like
                ev.append(("partial", float(i + np.argmin(x[seg])), eg, ed))
            i = j + 1
        return ev, sig, cg, cd

    def to_m(self, kind, idx):
        a, b = self.lin[kind]
        return a * idx + b

    def analyse(self, x) -> dict:
        ev, sig, cg, cd = self.events(x)
        r = {"found": bool(ev), "n_events": len(ev), "noise": sig}
        if not ev:
            return r
        k, idx, eg, ed = ev[0]
        r.update(first_kind=k, first_idx=idx, first_m=self.to_m(k, idx), first_eg=eg, first_ed=ed)
        opens = [e for e in ev if e[0] == "open"]
        if opens:
            # an open end reflects everything (|Gamma| = 1): its amplitude should match the
            # attenuation curve. Take the first open-type pulse that does; later look-alikes
            # are multiple echoes.
            score = [e[2] * np.exp(self.beta * (e[1] - 24.7)) / self.amp0 for e in opens]
            ok = [i for i, s in enumerate(score) if s >= self.open_min_score]
            i = ok[0] if ok else int(np.argmax(score))
            e = opens[i]
            r.update(len_idx=e[1], len_m=self.to_m("open", e[1]), len_eg=e[2], len_score=score[i])
        else:
            e = ev[-1]
            r.update(len_idx=e[1], len_m=self.to_m(e[0], e[1]), len_eg=e[2], len_score=0.0)
        if len(ev) > 1:
            r.update(second_kind=ev[1][0], second_m=self.to_m(ev[1][0], ev[1][1]))
        r["last_m"] = self.to_m(ev[-1][0], ev[-1][1])
        return r

    def calibrate(self, X, lab: pd.DataFrame):
        """Fit idx -> metres per event type, and the open-end amplitude decay."""
        idx = {"open": [], "partial": []}
        tgt = {"open": [], "partial": []}
        amp_i, amp_v = [], []
        for x, (_, row) in zip(X, lab.iterrows()):
            ev = self.events(x)[0]
            if not ev:
                continue
            k, i0, eg, _ = ev[0]
            if k == row.first_cls:
                idx[k].append(i0)
                tgt[k].append(row.d_first)
            if row.n_faults == 0 and k == "open":
                amp_i.append(i0)
                amp_v.append(eg)
        for k in idx:
            if len(idx[k]) > 20:
                a, b = np.polyfit(idx[k], tgt[k], 1)
                self.lin[k] = (float(a), float(b))
        if len(amp_i) > 20:
            slope, inter = np.polyfit(np.asarray(amp_i) - 24.7, np.log(np.maximum(amp_v, 1e-9)), 1)
            self.beta, self.amp0 = float(-slope), float(np.exp(inter))
        return self


FEATURES_Z = ["first_m", "first_is_open", "first_eg", "first_ed", "first_ratio", "n_events",
              "len_m", "len_eg", "len_score", "second_m", "second_is_open", "last_m", "noise",
              "max_cg_m", "max_cg", "min_cd_m", "min_cd",
              "energy_0", "energy_1", "energy_2", "energy_3", "energy_4", "energy_5"]


def features(base: PulseBaseline, x) -> tuple[dict, dict]:
    r = base.analyse(x)
    xs = base.highpass(x)
    cg, cd = base._corr(xs)
    cg[:PULSE_END + 4] = 0
    cd[:PULSE_END + 4] = 0
    f = dict.fromkeys(FEATURES_Z, -1.0)
    f["noise"] = r["noise"]
    f["n_events"] = r["n_events"]
    if r["found"]:
        f.update(first_m=r["first_m"], first_is_open=float(r["first_kind"] == "open"),
                 first_eg=r["first_eg"], first_ed=r["first_ed"],
                 first_ratio=abs(r["first_eg"]) / (abs(r["first_ed"]) + 1e-12),
                 len_m=r["len_m"], len_eg=r["len_eg"], len_score=r["len_score"], last_m=r["last_m"])
        if "second_m" in r:
            f.update(second_m=r["second_m"], second_is_open=float(r["second_kind"] == "open"))
    jg, jd = int(np.argmax(cg)), int(np.argmin(cd))
    f.update(max_cg_m=base.to_m("open", jg), max_cg=cg[jg], min_cd_m=base.to_m("partial", jd), min_cd=cd[jd])
    for k, seg in enumerate(np.array_split(xs[PULSE_END:], 6)):
        f[f"energy_{k}"] = float(np.mean(seg ** 2) / (r["noise"] ** 2 + 1e-18))
    return f, r


def process(base: PulseBaseline, X) -> tuple[pd.DataFrame, pd.DataFrame]:
    feats, outs = [], []
    for x in X:
        f, r = features(base, np.asarray(x, np.float64))
        feats.append(f)
        outs.append({"base_found": r["found"], "base_d_first": r.get("first_m", np.nan),
                     "base_length": r.get("len_m", np.nan),
                     "base_cls": r.get("first_kind", "none")})
    return pd.DataFrame(feats, columns=FEATURES_Z).astype(np.float32), pd.DataFrame(outs)


# ---------------------------------------------------------------- multi-task 1-D CNN
class ZenodoCNN:
    """Shared 1-D conv trunk with three heads: d_first, length (regression) and first_cls.

    Trains on the full 800k simulated traces, streamed from the memory map in
    contiguous chunks; the README preprocessing (pulse blanking + noise) is
    applied to every chunk on the fly, so each epoch sees fresh noise.
    """

    def __init__(self, epochs=12, batch=256, lr=2e-3, patience=3, chunk=40000, max_minutes=120, seed=0):
        self.epochs, self.batch, self.lr, self.patience = epochs, batch, lr, patience
        self.chunk, self.max_minutes, self.seed = chunk, max_minutes, seed
        self.y_scale = 200.0

    def _net(self, torch):
        nn = torch.nn

        def block(ci, co, k):
            return [nn.Conv1d(ci, co, k, padding=k // 2), nn.BatchNorm1d(co), nn.ReLU(), nn.MaxPool1d(2)]
        trunk = nn.Sequential(*block(1, 16, 9), *block(16, 32, 7), *block(32, 48, 7), *block(48, 64, 5),
                              nn.Flatten(), nn.Linear(64 * (N_SAMPLES // 16), 128), nn.ReLU(), nn.Dropout(0.2))
        return nn.ModuleDict({"trunk": trunk, "reg": nn.Linear(128, 2), "cls": nn.Linear(128, 2)})

    def _x(self, torch, X):
        return torch.from_numpy(((X - self.mu) / self.sd).astype(np.float32)).unsqueeze(1)

    def fit(self, S, lab: pd.DataFrame, s0: float, train_rows, val_rows, verbose=True):
        from .models import _torch
        torch = _torch()
        torch.manual_seed(self.seed)
        rng = np.random.default_rng(self.seed)
        probe = preprocess_sim(S[train_rows[0]:train_rows[0] + 5000], s0, rng=rng)
        self.mu, self.sd = float(probe.mean()), float(probe.std() + 1e-8)
        Y = np.c_[lab.d_first.to_numpy(np.float32), lab.length.to_numpy(np.float32)] / self.y_scale
        C = (lab.first_cls.to_numpy() == "partial").astype(np.int64)
        net = self._net(torch)
        opt = torch.optim.AdamW(net.parameters(), lr=self.lr, weight_decay=1e-4)
        sched = torch.optim.lr_scheduler.ReduceLROnPlateau(opt, factor=0.5, patience=1)
        vs, ve = val_rows
        Xv = self._x(torch, preprocess_sim(S[vs:ve], s0, rng=np.random.default_rng(99)))
        Yv, Cv = torch.from_numpy(Y[vs:ve]), torch.from_numpy(C[vs:ve])
        ts, te = train_rows
        best, best_state, bad, t0 = np.inf, None, 0, time.time()
        self.history = []
        for ep in range(self.epochs):
            net.train()
            tot = cnt = 0
            for s in rng.permutation(np.arange(ts, te, self.chunk)):
                e = min(te, s + self.chunk)
                Xc = preprocess_sim(S[s:e], s0, rng=rng)
                p = rng.permutation(e - s)
                for b in range(0, len(p), self.batch):
                    j = p[b:b + self.batch]
                    xb = self._x(torch, Xc[j])
                    h = net["trunk"](xb)
                    loss = (torch.nn.functional.smooth_l1_loss(net["reg"](h), torch.from_numpy(Y[s + j]), beta=0.01)
                            + 0.05 * torch.nn.functional.cross_entropy(net["cls"](h), torch.from_numpy(C[s + j])))
                    opt.zero_grad()
                    loss.backward()
                    opt.step()
                    tot += float(loss.detach()) * len(j)
                    cnt += len(j)
                if time.time() - t0 > 60 * self.max_minutes:
                    break
            net.eval()
            with torch.no_grad():
                hv = torch.cat([net["trunk"](Xv[i:i + 2048]) for i in range(0, len(Xv), 2048)])
                rv = net["reg"](hv)
                vloss = float(torch.mean(torch.abs(rv - Yv))) * self.y_scale
                vacc = float((net["cls"](hv).argmax(1) == Cv).float().mean())
            sched.step(vloss)
            self.history.append({"epoch": ep + 1, "train_loss": tot / max(cnt, 1), "val_MAE_m": vloss,
                                 "val_acc": vacc, "minutes": (time.time() - t0) / 60})
            if verbose:
                print(f"    CNN epoch {ep + 1}: val MAE (both targets) {vloss:.3f} m, val acc {vacc:.4f}, "
                      f"{(time.time() - t0) / 60:.1f} min", flush=True)
            if vloss < best - 1e-4:
                best, bad = vloss, 0
                best_state = {k: v.detach().clone() for k, v in net.state_dict().items()}
            else:
                bad += 1
                if bad >= self.patience:
                    break
            if time.time() - t0 > 60 * self.max_minutes:
                break
        net.load_state_dict(best_state)
        net.eval()
        self.net = net
        return self

    def predict(self, X) -> pd.DataFrame:
        from .models import _torch
        torch = _torch()
        out_r, out_c, out_p = [], [], []
        with torch.no_grad():
            for i in range(0, len(X), 2048):
                h = self.net["trunk"](self._x(torch, np.asarray(X[i:i + 2048], np.float32)))
                out_r.append(self.net["reg"](h).numpy() * self.y_scale)
                pr = torch.softmax(self.net["cls"](h), 1).numpy()
                out_p.append(pr[:, 1])
        r = np.concatenate(out_r)
        p = np.concatenate(out_p)
        return pd.DataFrame({"d_first": r[:, 0], "length": r[:, 1],
                             "first_cls": np.where(p > 0.5, "partial", "open"), "conf": np.maximum(p, 1 - p)})


# ---------------------------------------------------------------- prepare / train / evaluate
SPLITS = {"cal": (0, 5000), "trainB": (0, 200_000), "trainA": (0, 100_000),
          "cnn_train": (0, TRAIN_END), "cnn_val": (980_000, 1_000_000),
          "test": (800_000, 820_000), "noise": (820_000, 845_000)}
SK_FAMILIES = ("RF", "ET", "KNN", "MLP")
SK_PARAMS = {"RF": {"max_features": "sqrt", "min_samples_leaf": 5},
             "ET": {"max_features": 0.5, "min_samples_leaf": 5},
             "KNN": {"n_neighbors": 7, "weights": "distance"},
             "MLP": {"hidden_layer_sizes": (256, 128), "alpha": 1e-4}}


def _rows(name):
    return slice(*SPLITS[name])


def prepare(verbose=True):
    """Compact labels, s0 constant, pulse template, baseline calibration."""
    S = samples()
    lab = labels()
    s0 = float(np.mean(S[:20000, PULSE_END]))
    raw = np.asarray(S[:2000], np.float32)
    pulse = raw[:, 14:37].mean(0)
    base = PulseBaseline(pulse)
    Xc = preprocess_sim(S[_rows("cal")], s0, rng=np.random.default_rng(1))
    base.calibrate(Xc, lab.iloc[_rows("cal")])
    CACHE.mkdir(parents=True, exist_ok=True)
    cal = {"s0": s0, "pulse": pulse.tolist(), "lin": base.lin, "beta": base.beta, "amp0": base.amp0,
           "ts_s": TS, "samples_per_m_open": 1 / base.lin["open"][0],
           "vp_open_m_per_s": 2 * base.lin["open"][0] / TS}
    (CACHE / "calibration.json").write_text(json.dumps(cal, indent=2))
    if verbose:
        print(f"  s0 = {s0:.5f}; open-end mapping d = {base.lin['open'][0]:.5f}*idx + {base.lin['open'][1]:.3f} "
              f"(vp = {cal['vp_open_m_per_s']:.4e} m/s); fault mapping d = {base.lin['partial'][0]:.5f}*idx + "
              f"{base.lin['partial'][1]:.3f}; attenuation beta = {base.beta:.5f}/sample")
    return base, s0


def load_baseline():
    cal = json.loads((CACHE / "calibration.json").read_text())
    b = PulseBaseline(np.asarray(cal["pulse"], np.float32))
    b.lin = {k: tuple(v) for k, v in cal["lin"].items()}
    b.beta, b.amp0 = cal["beta"], cal["amp0"]
    return b, cal["s0"]


def build(name, base, s0, noise=NOISE, seed=None, keep_X=True):
    """Preprocessed traces + features + baseline outputs + labels for one split (cached).

    Every split draws its own noise: the seed comes from the split name (trainB
    keeps 0, the seed its cached features were built with), so no test trace
    carries the same noise realisation as a training trace.
    """
    if seed is None:
        seed = 0 if name == "trainB" else zlib.crc32(name.encode()) & 0x7FFFFFFF
    tag = f"{name}_n{noise:.6f}_s{seed}"
    cp = CACHE / f"{tag}.npz"
    lab = labels().iloc[_rows(name)].reset_index(drop=True)
    if cp.exists():
        z = np.load(cp, allow_pickle=False)
        F = pd.DataFrame(z["F"], columns=FEATURES_Z)
        B = pd.read_csv(CACHE / f"{tag}_base.csv")
        X = np.load(CACHE / f"{tag}_X.npy", mmap_mode="r") if keep_X else None
        return {"X": X, "F": F, "B": B, "lab": lab}
    S = samples()
    s, e = SPLITS[name]
    X = np.empty((e - s, N_SAMPLES), np.float32)
    rng = np.random.default_rng(seed)
    for a in range(s, e, 50000):
        b = min(e, a + 50000)
        X[a - s:b - s] = preprocess_sim(S[a:b], s0, noise, rng)
    t0 = time.time()
    F, B = process(base, X)
    print(f"  {name}: {e - s} traces processed in {time.time() - t0:.0f}s")
    np.savez(cp, F=F.to_numpy(np.float32))
    B.to_csv(CACHE / f"{tag}_base.csv", index=False)
    np.save(CACHE / f"{tag}_X.npy", X)
    return {"X": X if keep_X else None, "F": F, "B": B, "lab": lab}


def _inputs(ds, method):
    return np.asarray(ds["X"], np.float32) if method == "A" else ds["F"].to_numpy(np.float32)


def train(cnn_minutes: float = 120, verbose=True):
    import joblib

    from .models import make_model
    if not (CACHE / "calibration.json").exists():
        prepare()
    base, s0 = load_baseline()
    dsB = build("trainB", base, s0)
    dsA = {"X": dsB["X"][:SPLITS["trainA"][1]], "F": dsB["F"].iloc[:SPLITS["trainA"][1]],
           "lab": dsB["lab"].iloc[:SPLITS["trainA"][1]]}
    models, log = {}, []
    for method, ds in (("B", dsB), ("A", dsA)):
        X = _inputs(ds, method)
        for fam in SK_FAMILIES:
            for target in ("d_first", "length", "first_cls"):
                t0 = time.time()
                task = "cls" if target == "first_cls" else "reg"
                m = make_model(task, fam, SK_PARAMS[fam], n_estimators=60)
                m.fit(X, ds["lab"][target].to_numpy())
                models[(target, method, fam)] = m
                log.append({"model": f"{fam}-{method}", "target": target, "n_train": len(X), "fit_s": time.time() - t0})
                if verbose:
                    print(f"  {fam}-{method} {target}: fit on {len(X)} in {time.time() - t0:.0f}s", flush=True)
    if verbose:
        print("  multi-task 1-D CNN on the full 800k training traces")
    S = samples()
    lab = labels()
    cnn = ZenodoCNN(max_minutes=cnn_minutes).fit(S, lab, s0, SPLITS["cnn_train"], SPLITS["cnn_val"], verbose)
    pd.DataFrame(log).to_csv(RESULTS_DIR / "zenodo_training_log.csv", index=False)
    pd.DataFrame(cnn.history).to_csv(RESULTS_DIR / "zenodo_cnn_history.csv", index=False)
    # deployment bundle: compact models only (large tree ensembles stay in memory for evaluate)
    keep = {k: v for k, v in models.items() if k[2] in ("KNN", "MLP") or k[1] == "B"}
    joblib.dump({"models": keep, "cnn": cnn, "features": FEATURES_Z,
                 "created": time.strftime("%Y-%m-%d %H:%M")}, BUNDLE, compress=3)
    return models, cnn


def _predict_all(models, cnn, ds) -> dict:
    out = {"Baseline": pd.DataFrame({"d_first": ds["B"].base_d_first, "length": ds["B"].base_length,
                                     "first_cls": ds["B"].base_cls, "found": ds["B"].base_found})}
    for (target, method, fam), m in models.items():
        key = f"{fam}-{method}"
        out.setdefault(key, pd.DataFrame(index=range(len(ds["lab"]))))
        out[key][target] = m.predict(_inputs(ds, method))
        out[key]["found"] = True
    if cnn is not None:
        p = cnn.predict(ds["X"])
        p["found"] = True
        out["CNN-A"] = p
    return out


def _score(lab, preds, **tags) -> list[dict]:
    rows = []
    for name, p in preds.items():
        f = p["found"].to_numpy(bool)
        r = dict(tags, method=name, coverage=float(f.mean()))
        for t in ("d_first", "length"):
            e = (p[t].to_numpy(float) - lab[t].to_numpy(float))[f]
            r[f"MAE_{t}_m"] = float(np.nanmean(np.abs(e))) if f.any() else np.nan
            r[f"RMSE_{t}_m"] = float(np.sqrt(np.nanmean(e ** 2))) if f.any() else np.nan
            r[f"MedAE_{t}_m"] = float(np.nanmedian(np.abs(e))) if f.any() else np.nan
        r["acc_first_cls"] = float(np.mean(p["first_cls"].astype(str).to_numpy()[f] == lab.first_cls.to_numpy()[f])) if f.any() else np.nan
        rows.append(r)
    return rows


def evaluate(models=None, cnn=None):
    import joblib
    base, s0 = load_baseline()
    if models is None:
        bundle = joblib.load(BUNDLE)
        models, cnn = bundle["models"], bundle["cnn"]
    res = {}
    # Z1 held-out simulated traces (README validation block)
    test = build("test", base, s0)
    p1 = _predict_all(models, cnn, test)
    z1 = pd.DataFrame(_score(test["lab"], p1, experiment="Z1 held-out sim"))
    # breakdown by number of faults for the CNN and baseline
    brk = []
    for nf in range(5):
        m = test["lab"].n_faults.to_numpy() == nf
        for name in ("Baseline", "ET-B", "KNN-A", "CNN-A"):
            if name in p1:
                brk += _score(test["lab"][m].reset_index(drop=True),
                              {name: p1[name][m].reset_index(drop=True)}, n_faults=nf)
    # Z2 noise sweep
    z2 = []
    for mult in (1, 3, 10, 30):
        ds = build("noise", base, s0, noise=NOISE * mult, seed=10 + mult)
        z2 += _score(ds["lab"], _predict_all(models, cnn, ds), experiment="Z2 noise", noise_x=mult)
    z2 = pd.DataFrame(z2)
    # Z3 the 16 real measured traces
    Xr, lab_r = real_traces()
    Xr = preprocess_real(Xr, s0)
    Fr, Br = process(base, Xr)
    real = {"X": Xr, "F": Fr, "B": Br, "lab": lab_r}
    p3 = _predict_all(models, cnn, real)
    z3 = pd.DataFrame(_score(lab_r, p3, experiment="Z3 real measured (16)"))
    per = lab_r[["length", "positions", "d_first"]].copy()
    for name, p in p3.items():
        per[f"{name}_d_first"] = p["d_first"].to_numpy(float)
        per[f"{name}_length"] = p["length"].to_numpy(float)
    z1.to_csv(RESULTS_DIR / "zenodo_z1_heldout_sim.csv", index=False)
    pd.DataFrame(brk).to_csv(RESULTS_DIR / "zenodo_z1_by_fault_count.csv", index=False)
    z2.to_csv(RESULTS_DIR / "zenodo_z2_noise.csv", index=False)
    z3.to_csv(RESULTS_DIR / "zenodo_z3_real.csv", index=False)
    per.to_csv(RESULTS_DIR / "zenodo_z3_real_per_trace.csv", index=False)
    figures(test, p1, z2, real, p3, s0)
    write_summary(z1, pd.DataFrame(brk), z2, z3, per)
    res.update(z1=z1, z2=z2, z3=z3)
    return res


# ---------------------------------------------------------------- figures / summary
def figures(test, p1, z2, real, p3, s0):
    from .evaluate import FAM_COLOR, GRAY, INK2, _save, _style, label, style
    import matplotlib.pyplot as plt
    _style()
    keys = [k for k in ("Baseline", "RF-B", "ET-B", "KNN-A", "MLP-B", "CNN-A") if k in p1]
    base, _ = load_baseline()
    # zfig1: example traces with labels
    fig, ax = plt.subplots(2, 1, figsize=(11, 6.5), sharex=True)
    lab = test["lab"]
    i_sim = int(np.argmax((lab.n_faults == 2).to_numpy()))
    m_of = lambda i: base.to_m("open", i)
    xm = np.array([m_of(i) for i in range(N_SAMPLES)])
    for a, x, lb, title in ((ax[0], test["X"][i_sim], lab.iloc[i_sim], "Simulated trace (2 capacitive faults + open end)"),
                            (ax[1], real["X"][12], real["lab"].iloc[12], "Real measured trace #12")):
        a.plot(xm, x, color=FAM_COLOR["RF"], lw=1.4)
        a.axvline(lb.d_first, color=INK2, ls=":", lw=1.2)
        a.axvline(lb.length, color=INK2, ls="--", lw=1.2)
        a.set(title=title, ylabel="amplitude")
        a.text(0.99, 0.92, f"first discontinuity {lb.d_first:.1f} m (dotted), open end {lb.length:.1f} m (dashed)",
               transform=a.transAxes, ha="right", fontsize=8, color=INK2)
    ax[1].set(xlabel="distance from the TDR (m)", xlim=(-5, 220))
    _save(fig, "zfig1_zenodo_traces.png")
    # zfig2: noise sweep
    fig, ax = plt.subplots(1, 3, figsize=(16, 4.4))
    for k in keys:
        s = z2[z2.method == k].sort_values("noise_x")
        for a, col in zip(ax, ("MAE_d_first_m", "MAE_length_m", "acc_first_cls")):
            a.plot(s.noise_x, s[col], label=label(k), **style(k))
    for a, t, yl in zip(ax, ("First discontinuity", "Cable length", "First-discontinuity class"),
                        ("MAE (m)", "MAE (m)", "accuracy")):
        a.set(title=f"Z2. {t} vs noise", xlabel="noise (x README sigma 0.000437)", ylabel=yl, xscale="log")
    ax[0].legend(fontsize=8)
    _save(fig, "zfig2_zenodo_noise.png")
    # zfig3: real traces, predicted vs true
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.6))
    for a, t in zip(ax, ("d_first", "length")):
        tv = real["lab"][t].to_numpy()
        for k in keys:
            st = style(k)
            a.scatter(tv, p3[k][t].to_numpy(float), s=36, color=st["color"], marker=st["marker"],
                      label=label(k), alpha=0.85, edgecolors="none")
        lim = (0, 160)
        a.plot(lim, lim, color=GRAY, lw=1, ls=":")
        a.set(xlim=lim, ylim=lim, xlabel=f"true {t.replace('_', ' ')} (m)", ylabel="predicted (m)",
              title=f"Z3. 16 real traces: {'first discontinuity' if t == 'd_first' else 'cable length'}")
    ax[0].legend(fontsize=7)
    _save(fig, "zfig3_zenodo_real.png")


def write_summary(z1, brk, z2, z3, per):
    from .evaluate import md_table
    cols = ["method", "coverage", "MAE_d_first_m", "RMSE_d_first_m", "MAE_length_m", "RMSE_length_m", "acc_first_cls"]
    txt = ["# Zenodo dataset results (Scarpetta et al. 2021, doi:10.5281/zenodo.5720438)\n",
           "Targets reduced to the project's single-fault framing: distance to the first discontinuity, "
           "cable length (open end), and class of the first discontinuity (capacitive fault = partial, or open).\n",
           "## Z1: held-out simulated traces (20,000 from the README validation block)\n", md_table(z1[cols]),
           "\n\n### Z1 by number of capacitive faults\n",
           md_table(brk[["n_faults", "method", "MAE_d_first_m", "MAE_length_m", "acc_first_cls"]]),
           "\n\n## Z2: noise sweep (25,000 traces per level)\n",
           md_table(z2[["noise_x", "method", "coverage", "MAE_d_first_m", "MAE_length_m", "acc_first_cls"]]),
           "\n\n## Z3: the 16 real measured traces (models trained on simulation only)\n", md_table(z3[cols]),
           "\n\n### Z3 per trace (m)\n", md_table(per), "\n"]
    (RESULTS_DIR / "zenodo_summary.md").write_text("\n".join(txt), encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("step", choices=["download", "prepare", "train", "evaluate", "all"])
    ap.add_argument("--cnn-minutes", type=float, default=120, help="time budget for the CNN")
    a = ap.parse_args(argv)
    if a.step in ("download", "all"):
        if not download():
            raise SystemExit("download incomplete; run again to resume")
    if a.step in ("prepare", "all"):
        prepare()
    if a.step in ("train", "all"):
        models, cnn = train(a.cnn_minutes)
        if a.step == "all":
            evaluate(models, cnn)
            return
    if a.step == "evaluate":
        evaluate()


if __name__ == "__main__":
    main()
