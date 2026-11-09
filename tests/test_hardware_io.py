import json

import numpy as np
import pytest

from src.scope_io import load_waveform, parse_text, save_waveform

TS = 1e-9
T = -50e-9 + TS * np.arange(300)
V = np.where(T >= 0, 1.0, 0.0) + np.where(T >= 50e-9, 1.0, 0.0)


def _check(wf, ts=TS, n=300):
    assert len(wf.t) == n
    assert wf.ts == pytest.approx(ts, rel=1e-3)
    assert wf.t[0] == pytest.approx(-50e-9, abs=1e-12)
    assert wf.v.max() == pytest.approx(2.0)


def test_rigol_ds1000z():
    lines = ["X,CH1,Start,Increment,", f"Sequence,Volt,{T[0]:.6e},{TS:.6e},"]
    lines += [f"{i},{v:.4e}," for i, v in enumerate(V)]
    wf = parse_text("\n".join(lines))
    _check(wf)
    assert wf.vendor == "Rigol" and wf.fmt == "rigol-xstart"


def test_tektronix_legacy_6col():
    head = ["Record Length,3.000000e+02", "Sample Interval,1.000000e-09", "Trigger Point,5.0e+01",
            "Source,CH1", "Model Number,TBS1052B"]
    lines = []
    for i, (t, v) in enumerate(zip(T, V)):
        k = head[i].split(",") if i < len(head) else ["", ""]
        lines.append(f"{k[0]},{k[1]},,{t:.12f},{v:.4f},")
    wf = parse_text("\n".join(lines))
    _check(wf)
    assert wf.vendor == "Tektronix"


def test_keysight():
    lines = ["x-axis,1", "second,Volt"] + [f"{t:.6e},{v:.4e}" for t, v in zip(T, V)]
    _check(parse_text("\n".join(lines)))


def test_siglent_style_header():
    lines = ["Record Length,Analog:300", "Sample Interval,1.00E-09", "Vertical Units,V",
             "Second,Volt"] + [f"{t:.6E},{v:.4E}" for t, v in zip(T, V)]
    wf = parse_text("\n".join(lines))
    _check(wf)


def test_generic_units_and_channel_pick():
    lines = ["Time (ns),CH1 (mV),CH2 (mV)"] + [f"{t * 1e9:.3f},{v * 1e3:.2f},{-v * 1e3:.2f}" for t, v in zip(T, V)]
    wf = parse_text("\n".join(lines), channel=1)
    _check(wf)
    wf2 = parse_text("\n".join(lines), channel=2)
    assert wf2.v.min() == pytest.approx(-2.0)


def test_voltage_only_needs_ts():
    txt = "\n".join(f"{v:.3f}" for v in V)
    with pytest.raises(ValueError):
        parse_text(txt)
    wf = parse_text(txt, ts=TS)
    assert wf.ts == pytest.approx(TS)


def test_own_format_roundtrip(tmp_path):
    p = save_waveform(tmp_path / "x.csv", T, V, {"termination": "open", "cable_length_m": 5.0})
    wf = load_waveform(p)
    _check(wf)
    assert wf.meta["termination"] == "open"


def test_simulated_capture_then_calibrate(tmp_path):
    from src import calibrate, capture
    out = tmp_path / "session"
    for L in (3.0, 8.0):
        capture.main(["--simulate", "--repeats", "4", "--length", str(L), "--termination", "open",
                      "--out-dir", str(out), "--log", str(out / "lab_log.csv")])
    capture.main(["--simulate", "--repeats", "2", "--length-meas", "4.0", "4.1", "3.9", "--termination", "partial",
                  "--fault-kind", "series_R", "--fault-position", "2.0", "--zl", "100",
                  "--out-dir", str(out), "--log", str(out / "lab_log.csv")])
    log = (out / "lab_log.csv").read_text().splitlines()
    assert len(log) == 1 + 10
    cal_path = tmp_path / "cal.json"
    calibrate.main(["--log", str(out / "lab_log.csv"), "--out", str(cal_path)])
    cal = json.loads(cal_path.read_text())
    assert cal["vp_m_per_s"] == pytest.approx(1.9786e8, rel=0.02)
    assert 2e-9 < cal["rise_time_s"] < 8e-9


def test_lab_dataset_from_log(tmp_path):
    from src import capture
    from src.dataset import build_lab
    out = tmp_path / "s"
    for term in ("open", "short"):
        capture.main(["--simulate", "--repeats", "3", "--length", "5", "--termination", term,
                      "--out-dir", str(out), "--log", str(out / "lab_log.csv")])
    ds = build_lab(out / "lab_log.csv")
    assert ds is not None and len(ds["meta"]) == 6
    assert ds["X"].shape == (6, 256)
    assert (np.abs(ds["B"]["base_d"] - 5.0) < 0.4).all()
