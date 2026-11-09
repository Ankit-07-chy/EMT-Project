"""Regression tests for the issues found in the Nov 2026 code review (docs/TESTING_REPORT.md §3)."""
import numpy as np
import pandas as pd
import pytest

from src.config import SimConfig
from src.features import FEATURES_B, extract_features, process_one
from src.preprocess import Processed, preprocess_measured
from src.sim_tdr import make_params, simulate

CFG = SimConfig()
# a calibration made at the normal amplitude (V_inc = 1 V at the tee)
CAL = {"calibrated": True, "v_inc_v": 1.0, "rise_time_s": 4e-9, "vp_m_per_s": CFG.vp_nominal,
       "t_offset_s": 0.0, "cable_type": "RG-58"}


def trace(cls, d=5.0, scale=1.0, **kw):
    p = make_params(CFG, cls=cls, d=d, snr_db=40, rise=4e-9, seed=3, **kw)
    (t, v), = simulate(p, CFG)
    v = v / p["v_inc"][0] * scale          # incident step = `scale` volts
    return t, v


@pytest.mark.parametrize("scale", [0.25, 0.6, 1.0, 1.5])
@pytest.mark.parametrize("cls", ["open", "short"])
def test_vinc_per_trace_any_amplitude(cls, scale):
    """Finding 1: traces at another generator amplitude than the calibration."""
    t, v = trace(cls, scale=scale)
    pr, b, _, _ = process_one(t, v, CFG.vp_nominal, CFG.preset, cal=CAL)
    assert pr.ok
    assert abs(pr.v_inc - scale) / scale < 0.1
    assert b.cls == cls
    assert abs(b.distance - 5.0) < 0.3


def test_vinc_uses_calibration_when_consistent():
    t, v = trace("open", scale=1.05)
    pr = preprocess_measured(t, v, CAL)
    assert pr.v_inc == pytest.approx(1.0)
    assert "calibration" in pr.msg


def test_t_offset_shifts_every_time_feature():
    """Finding 3: the fixture offset must come off the baseline AND both model inputs."""
    t, v = trace("open")
    _, b0, x0, f0 = process_one(t, v, CFG.vp_nominal, CFG.preset, v_inc=1.0)
    t0 = 2e-9
    _, b1, x1, f1 = process_one(t + 0, v, CFG.vp_nominal, CFG.preset, v_inc=1.0, t_offset=t0)
    for k in ("delta_t_ns", "t_dpeak_ns", "t_cross50_ns", "dev_centroid_ns"):
        assert f0[k] - f1[k] == pytest.approx(2.0, abs=0.05), k
    # Method A: the echo moves 2 ns (2 grid samples) earlier
    lag = np.argmax(np.correlate(np.diff(x0), np.diff(x1), "full")) - (len(x0) - 2)
    assert lag == 2


def test_channel_float_from_log():
    """Finding 4: a blank cell makes pandas read the channel column as float (1.0)."""
    from src.scope_io import _pick_col
    names = ["time", "CH1", "CH2"]
    assert _pick_col(names, [1, 2], 1.0) == 1
    assert _pick_col(names, [1, 2], 2.0) == 2
    assert _pick_col(names, [1, 2], float("nan")) == 1


def test_failed_preprocessing_is_not_a_short():
    """Finding 7: a failed trace must not look like a strong negative echo."""
    from src.baseline import BaselineResult
    bad = Processed(np.zeros(5), np.zeros(5), np.zeros(5), 1e-9, float("nan"), 0, float("nan"),
                    0, float("nan"), 1e-9, ok=False, msg="no incident edge")
    f = extract_features(bad, BaselineResult())
    assert f["refl_found"] == -1.0
    for k in ("refl_amp_ratio", "polarity", "gamma_est", "second_amp"):
        assert f[k] == 0.0


def test_predict_marks_failed_rows_invalid():
    from sklearn.dummy import DummyClassifier, DummyRegressor
    from src.train import predict
    X = np.zeros((3, 256), np.float32)
    F = pd.DataFrame(np.zeros((3, len(FEATURES_B))), columns=FEATURES_B)
    B = pd.DataFrame({"prep_ok": [True, False, True]})
    reg = DummyRegressor(strategy="constant", constant=50.0).fit(X, [50.0] * 3)
    clf = DummyClassifier(strategy="constant", constant="open").fit(X, ["open"] * 3)
    bundle = {"models": {("reg", "A", "RF"): reg, ("cls", "A", "RF"): clf}, "vp_cal": 2e8}
    out = predict(bundle, {"X": X, "F": F, "B": B, "meta": None})
    assert np.isnan(out["RF-A_d"][1]) and np.isfinite(out["RF-A_d"][0])
    assert list(out["RF-A_cls"]) == ["open", "invalid", "open"]


def test_calibrate_two_traces_and_no_noise():
    """Finding 6: 2 lengths x 1 repeat (no covariance) and zero pre-edge noise must not crash."""
    from src.calibrate import solve
    df = pd.DataFrame({"length_m": [2.0, 5.0], "dt_s": [20.4e-9, 50.9e-9], "amp": [0.97, 0.93],
                       "rise_s": [4e-9, 4.1e-9], "v_inc_v": [1.0, 1.0], "noise_v": [0.0, 0.0],
                       "ts_s": [5e-10, 5e-10]})
    cal = solve(df, "RG-58")
    assert 1.9e8 < cal["vp_m_per_s"] < 2.1e8
    assert cal["snr_db"] is None


def test_calibrate_ignores_low_amplitude_rows_for_vinc():
    from src.calibrate import solve
    n = 12
    df = pd.DataFrame({"length_m": [2.0] * 6 + [5.0] * 6, "dt_s": [20.4e-9] * 6 + [50.9e-9] * 6,
                       "amp": [0.95] * n, "rise_s": [4e-9] * n,
                       "v_inc_v": [1.0] * 10 + [0.2, 0.2], "noise_v": [0.003] * n, "ts_s": [5e-10] * n})
    cal = solve(df, "RG-58")
    assert cal["v_inc_v"] == pytest.approx(1.0)
    assert cal["n_traces_v_inc"] == 10


def test_capture_relative_paths_resolve(tmp_path, monkeypatch):
    """Finding 2: relative --out-dir / --log must still give a loadable lab log."""
    from src import capture, dataset
    monkeypatch.chdir(tmp_path)
    capture.main(["--simulate", "--length", "5", "--termination", "open", "--repeats", "2",
                  "--out-dir", "sess", "--log", "logs/lab_log.csv"])
    log = pd.read_csv(tmp_path / "logs" / "lab_log.csv")
    assert "\\" not in log.file.iloc[0]
    ds = dataset.build_lab(tmp_path / "logs" / "lab_log.csv", calibration=dict(CAL, calibrated=False))
    assert ds is not None and len(ds["meta"]) == 2
