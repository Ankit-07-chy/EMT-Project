"""Feature extraction (WP6) and batch processing of raw traces.

Method A: the normalised trace resampled onto the common 256-point time grid.
Method B: engineered, physics-based features (below), computed automatically.

Rules followed (brief section 7.5): every trace is normalised by V_inc; the
true distance, Gamma_true and attenuation are never used as inputs.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .baseline import BaselineResult, detect
from .config import CABLES, DEFAULT_CABLE, GRID_T, CablePreset
from .preprocess import Processed, preprocess, to_grid

FEATURES_B = [
    # core list from the brief
    "delta_t_ns", "refl_amp_ratio", "polarity", "v_final_ratio",
    "refl_rise_ns", "noise_sigma", "ts_ns",
    # optional shape / timing information
    "refl_found", "merged", "slope_ratio", "t_dpeak_ns", "gamma_est", "inc_rise_ns",
    "t_cross10_ns", "t_cross25_ns", "t_cross50_ns",
    "second_amp", "second_t_ns",
    "energy_0_60", "energy_60_120", "energy_120_180", "energy_180_240",
    "dev_centroid_ns",
]


def _first_cross(t, dev, level, t_min, t_edge=None):
    m = ((t if t_edge is None else t_edge) > t_min) & (np.abs(dev) > level)
    return float(t[m][0] * 1e9) if m.any() else -1.0


def extract_features(proc: Processed, b: BaselineResult) -> dict:
    """Method B feature vector for one trace (missing values -> -1 / 0)."""
    f = dict.fromkeys(FEATURES_B, -1.0)
    f["noise_sigma"] = proc.noise_sigma if np.isfinite(proc.noise_sigma) else -1.0
    f["ts_ns"] = proc.ts * 1e9
    if not proc.ok:
        # failed preprocessing: refl_found = -1 marks it; amplitudes are 0 (unknown),
        # not -1, which would look like a strong negative (short-circuit) echo
        for k in ("refl_amp_ratio", "polarity", "slope_ratio", "gamma_est", "second_amp",
                  "energy_0_60", "energy_60_120", "energy_120_180", "energy_180_240"):
            f[k] = 0.0
        return f
    t, vs = proc.t, proc.v_smooth
    # windows that mean "after the incident edge" are anchored on the edge itself;
    # reported times are on proc.t (fixture offset removed, see preprocess.shifted)
    t_edge = t + float(proc.extra.get("t_offset", 0.0))
    rise = proc.rise_inc
    f["inc_rise_ns"] = rise * 1e9
    f["v_final_ratio"] = b.v_final if np.isfinite(b.v_final) else -1.0
    f["refl_found"] = float(b.found)
    f["merged"] = float(b.merged)
    if b.found:
        f["delta_t_ns"] = b.dt * 1e9
        f["refl_amp_ratio"] = b.amp
        f["polarity"] = float(b.polarity)
        f["refl_rise_ns"] = b.refl_rise * 1e9 if np.isfinite(b.refl_rise) else -1.0
        f["slope_ratio"] = b.slope_ratio
        f["t_dpeak_ns"] = b.t_peak * 1e9 if np.isfinite(b.t_peak) else -1.0
        f["gamma_est"] = b.gamma_est
        f["second_amp"] = b.second_amp
        f["second_t_ns"] = b.second_t * 1e9 if np.isfinite(b.second_t) else -1.0
    else:
        f["refl_amp_ratio"] = f["polarity"] = f["slope_ratio"] = 0.0
        f["gamma_est"] = f["second_amp"] = 0.0
    dev = vs - 1.0
    t_min = 0.6 * rise
    for lvl, name in ((0.1, "t_cross10_ns"), (0.25, "t_cross25_ns"), (0.5, "t_cross50_ns")):
        f[name] = _first_cross(t, dev, lvl, t_min, t_edge)
    for a, c in ((0, 60), (60, 120), (120, 180), (180, 240)):
        m = (t >= a * 1e-9) & (t < c * 1e-9) & (t_edge >= t_min)
        f[f"energy_{a}_{c}"] = float(np.mean(dev[m] ** 2)) if m.any() else 0.0
    ds = np.abs(np.gradient(vs, proc.ts))
    m = t_edge > t_min
    w = np.where(ds[m] > (b.threshold if np.isfinite(b.threshold) else 0), ds[m], 0)
    f["dev_centroid_ns"] = float(np.sum(t[m] * w) / np.sum(w) * 1e9) if w.sum() > 0 else -1.0
    return f


def process_one(t, v, vp: float, preset: CablePreset | None = None, v_inc: float | None = None,
                t_offset: float = 0.0, t_hint: float = 0.0, cal: dict | None = None):
    """preprocess -> baseline -> model inputs for one trace.

    ``cal`` marks a *measured* trace: V_inc is then chosen per trace by
    ``preprocess_measured`` (``v_inc`` still overrides). ``t_offset`` (fixture
    delay from calibration) is removed from the baseline's times and from both
    model inputs, so they sit on the simulator's time base.
    Returns (Processed, BaselineResult, grid [256], features dict).
    """
    from .preprocess import preprocess_measured, shifted
    if cal is not None:
        proc = preprocess_measured(t, v, cal, v_inc, t_hint=t_hint)
    else:
        proc = preprocess(t, v, v_inc=v_inc, t_hint=t_hint)
    b = detect(proc, float(vp), preset, t_offset=t_offset)
    pm = shifted(proc, t_offset)
    x = to_grid(pm).astype(np.float32) if proc.ok else np.zeros(len(GRID_T), np.float32)
    return proc, b, x, extract_features(pm, b)


def process_traces(traces, v_inc_refs=None, vp: float | np.ndarray = None,
                   preset: CablePreset | None = None, t_offset: float = 0.0,
                   t_hint: float = 0.0, progress: bool = False, cal: dict | None = None):
    """Run preprocess -> baseline -> features on a list of (t, v) traces.

    Returns (X_grid [n, 256], features DataFrame, baseline DataFrame).
    ``vp`` is the *calibrated / nominal* velocity used to turn dt into metres.
    Pass ``cal`` (the calibration dict) for measured traces, see ``process_one``.
    """
    preset = preset or CABLES[DEFAULT_CABLE]
    n = len(traces)
    vp_arr = np.broadcast_to(np.asarray(vp if vp is not None else preset.vp, float), (n,))
    vref = [None] * n if v_inc_refs is None else list(v_inc_refs)
    X = np.zeros((n, len(GRID_T)), np.float32)
    feats, bases = [], []
    for i, (t, v) in enumerate(traces):
        proc, b, X[i], f = process_one(t, v, float(vp_arr[i]), preset, vref[i], t_offset, t_hint, cal)
        feats.append(f)
        bases.append({"base_found": b.found, "base_dt": b.dt, "base_d": b.distance,
                      "base_cls": b.cls, "base_gamma": b.gamma_est, "base_amp": b.amp,
                      "base_merged": b.merged, "prep_ok": proc.ok})
        if progress and (i + 1) % 2000 == 0:
            print(f"  processed {i + 1}/{n}")
    F = pd.DataFrame(feats, columns=FEATURES_B).astype(float)
    return X, F, pd.DataFrame(bases)
