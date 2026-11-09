import io
import os
import pickle
import zipfile

import numpy as np
import pytest

from src import zenodo as Z
from src.models import CNN1D, make_model


# ---------------------------------------------------------------- model zoo
@pytest.mark.parametrize("family", ["RF", "ET", "KNN", "MLP"])
@pytest.mark.parametrize("task", ["reg", "cls"])
def test_sklearn_families_fit_predict(family, task):
    rng = np.random.default_rng(0)
    X = rng.normal(size=(300, 12))
    y = X[:, 0] * 3 + 0.1 * rng.normal(size=300) if task == "reg" else np.where(X[:, 0] > 0, "open", "short")
    m = make_model(task, family, {"n_neighbors": 5} if family == "KNN" else {}, n_estimators=20)
    m.fit(X, y)
    p = m.predict(X[:10])
    assert len(p) == 10
    if task == "cls":
        assert m.predict_proba(X[:5]).shape == (5, 2)


def test_cnn_learns_pulse_position():
    rng = np.random.default_rng(1)
    n, L = 600, 128
    pos = rng.uniform(20, 100, n)
    t = np.arange(L)
    X = np.exp(-0.5 * ((t[None, :] - pos[:, None]) / 3) ** 2) + 0.05 * rng.normal(size=(n, L))
    m = CNN1D(task="reg", channels=(8, 16), epochs=25, patience=8, batch=64).fit(X[:500], pos[:500])
    err = np.abs(m.predict(X[500:]) - pos[500:]).mean()
    assert err < 8.0          # a constant guess would be about 20


def test_cnn_classifier_proba():
    rng = np.random.default_rng(2)
    X = rng.normal(size=(200, 64))
    y = np.where(X[:, :32].mean(1) > 0, "a", "b")
    m = CNN1D(task="cls", channels=(8,), epochs=3).fit(X, y)
    pr = m.predict_proba(X[:7])
    assert pr.shape == (7, 2) and np.allclose(pr.sum(1), 1)


# ---------------------------------------------------------------- zenodo: safe loading
def _npy_object_bytes(payload: bytes) -> bytes:
    buf = io.BytesIO()
    np.lib.format.write_array_header_1_0(buf, {"descr": "|O", "fortran_order": False, "shape": (1,)})
    return buf.getvalue() + payload


def test_safe_unpickler_reads_labels(tmp_path):
    p = tmp_path / "ok.npz"
    lab = np.empty(2, dtype=object)
    lab[0] = [(10.5, 0, 1e-10), (30.0, 1, float("inf"))]
    lab[1] = [(20.0, 1, float("inf"))]
    np.savez(p, samples=np.zeros((2, 4), np.float32), labels=lab)
    out = Z.load_npz_safe(p)
    assert out["labels"][0][1][2] == float("inf")
    assert out["samples"].shape == (2, 4)


def test_safe_unpickler_blocks_code(tmp_path):
    p = tmp_path / "evil.npz"
    payload = pickle.dumps(os.getcwd)            # any global function reference must be refused
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("labels.npy", _npy_object_bytes(payload))
    with pytest.raises(pickle.UnpicklingError):
        Z.load_npz_safe(p)


def test_memmap_inside_nested_zip(tmp_path, monkeypatch):
    rng = np.random.default_rng(3)
    S = rng.normal(size=(7, Z.N_SAMPLES)).astype(np.float32)
    inner = tmp_path / "dataset.npz"
    np.savez(inner, samples=S, min_length=np.float64(10))
    outer = tmp_path / "outer.zip"
    with zipfile.ZipFile(outer, "w", compression=zipfile.ZIP_STORED) as z:
        z.write(tmp_path / "dataset.npz", "dataset.npz")
    monkeypatch.setattr(Z, "ZIP", outer)
    mm = Z.samples()
    assert mm.shape == S.shape and np.array_equal(np.asarray(mm), S)


# ---------------------------------------------------------------- zenodo: matched-filter baseline
def _synthetic_trace(fault_idx, end_idx, tau=1.5, noise=0.0004, seed=0):
    t = np.arange(Z.N_SAMPLES, dtype=float)
    g = lambda c: np.exp(-0.5 * ((t - c) / 2.0) ** 2)
    x = 0.45 * g(25.0)                                       # transmitted pulse
    x += -tau * 0.05 * np.gradient(g(fault_idx))             # parallel capacitor: -tau * dV/dt
    x += 0.2 * g(end_idx)                                    # open end
    x += np.random.default_rng(seed).normal(0, noise, x.size)
    return x.astype(np.float32)


def test_pulse_baseline_finds_fault_and_end():
    tt = np.arange(23, dtype=float)
    base = Z.PulseBaseline(0.45 * np.exp(-0.5 * ((tt - 11) / 2.0) ** 2))
    # README preprocessing adds the noise the baseline measures its threshold from
    x = Z.preprocess_sim(_synthetic_trace(150.0, 400.0, noise=0.0)[None, :], s0=0.0, noise=Z.NOISE)[0]
    r = base.analyse(x)
    assert r["found"] and r["first_kind"] == "partial"
    assert abs(r["first_idx"] - 150) < 1.5
    assert abs(r["len_idx"] - 400) < 1.0
    f, _ = Z.features(base, x)
    assert set(Z.FEATURES_Z) <= set(f)
