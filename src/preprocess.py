"""Trace cleaning (WP3): align, remove baseline, normalise by V_inc, denoise.

After ``preprocess`` every trace, simulated or measured, looks the same:
    * time axis shifted so the incident edge crosses 50 % at t = 0
    * pre-trigger baseline subtracted
    * divided by the incident step amplitude V_inc (incident plateau = 1,
      open -> 2, short -> 0, matched -> 1)
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.ndimage import gaussian_filter1d

from .config import GRID_DT, GRID_T


@dataclass
class Processed:
    t: np.ndarray            # aligned time axis, s (incident 50 % at t = 0)
    v: np.ndarray            # normalised trace
    v_smooth: np.ndarray     # denoised normalised trace
    ts: float                # sample interval, s
    v_inc: float             # incident step amplitude used for normalising, V
    baseline: float          # removed DC level, V
    noise_sigma: float       # pre-edge noise std, normalised units
    t_inc: float             # incident-edge time on the original axis, s
    rise_inc: float          # incident 10-90 % rise time estimate, s
    smooth_sigma: float      # Gaussian smoothing sigma used, s
    ok: bool = True
    msg: str = ""
    extra: dict = field(default_factory=dict)


def _mad_sigma(x: np.ndarray) -> float:
    if x.size < 3:
        return float("nan")
    return float(1.4826 * np.median(np.abs(x - np.median(x))))


def _crossings(x: np.ndarray, level: float, rising: bool = True) -> np.ndarray:
    """Fractional sample indices where x crosses ``level``."""
    a, b = x[:-1] - level, x[1:] - level
    idx = np.where((a < 0) & (b >= 0))[0] if rising else np.where((a > 0) & (b <= 0))[0]
    frac = a[idx] / (a[idx] - b[idx] + 1e-30)
    return idx + frac


def _interp_idx(t: np.ndarray, fidx: float) -> float:
    i = int(np.clip(np.floor(fidx), 0, len(t) - 2))
    return float(t[i] + (fidx - i) * (t[i + 1] - t[i]))


def preprocess(t: np.ndarray, v: np.ndarray, v_inc: float | None = None,
               t_hint: float = 0.0, search: float = 25e-9,
               pre_guard: float = 12e-9) -> Processed:
    """Align, baseline-correct and normalise one trace.

    t, v     : raw time (s) and voltage (V)
    v_inc    : incident step amplitude (V). Pass the calibrated value when known;
               otherwise it is estimated from the trace.
    t_hint   : where the scope trigger put the incident edge (0 for scope CSVs)
    search   : +- window around t_hint in which the incident edge is searched
    """
    t = np.asarray(t, float)
    v = np.asarray(v, float)
    order = np.argsort(t)
    t, v = t[order], v[order]
    ts = float(np.median(np.diff(t)))

    # 1. baseline from the pre-trigger region
    pre = t < (t_hint - pre_guard)
    if pre.sum() < 8:
        pre = np.zeros_like(t, bool)
        pre[: max(8, len(t) // 20)] = True
    base = float(np.median(v[pre]))
    sig_v = _mad_sigma(v[pre])
    x = v - base

    # 2. coarse smoothing for edge finding (about 1.5 ns or 1 sample)
    s0 = max(1.0, 1.5e-9 / ts)
    xs = gaussian_filter1d(x, s0)

    # 3. incident amplitude: given, or estimated from the first big rise
    msg = ""
    if v_inc is None or not np.isfinite(v_inc) or v_inc <= 0:
        win = (t > t_hint - search) & (t < t_hint + search + 60e-9)
        top = np.percentile(np.abs(xs[win]), 99) if win.any() else np.abs(xs).max()
        cand = _crossings(xs, 0.3 * top)
        cand = cand[np.abs(np.array([_interp_idx(t, c) for c in cand]) - t_hint) < search] if cand.size else cand
        if cand.size == 0:
            # trigger origin not where expected (e.g. scope trigger delay): use the
            # first big rise anywhere in the record
            top = np.percentile(np.abs(xs), 99)
            cand = _crossings(xs, 0.3 * top)
            msg = "edge outside trigger window"
        if cand.size == 0:
            return Processed(t - t_hint, x, x, ts, float("nan"), base, float("nan"),
                             t_hint, float("nan"), s0 * ts, ok=False, msg="no incident edge")
        i0 = int(cand[0])
        dx = np.gradient(xs)
        j = i0
        pk = dx[i0]
        while j < len(dx) - 1 and (dx[j] > 0.2 * pk or j < i0 + 2):
            pk = max(pk, dx[j])
            j += 1
        v_inc = float(np.median(xs[j: j + max(2, int(2e-9 / ts))]))
        msg = (msg + "; " if msg else "") + "v_inc estimated from trace"
        if v_inc <= 0:
            return Processed(t - t_hint, x, x, ts, float("nan"), base, float("nan"),
                             t_hint, float("nan"), s0 * ts, ok=False, msg="bad v_inc")

    xn = x / v_inc
    xns = xs / v_inc

    # 4. incident 50 % crossing: the rising crossing closest to the trigger hint
    cr = _crossings(xns, 0.5)
    if cr.size == 0:
        return Processed(t - t_hint, xn, xns, ts, v_inc, base, sig_v / v_inc,
                         t_hint, float("nan"), s0 * ts, ok=False, msg="no 50% crossing")
    tc = np.array([_interp_idx(t, c) for c in cr])
    near = np.abs(tc - t_hint) < search
    k = int(np.argmin(np.abs(tc - t_hint))) if near.any() else 0
    t_inc = float(tc[k])
    if not near.any() and "outside" not in msg:
        msg = (msg + "; " if msg else "") + "edge outside trigger window"

    # 5. rise time from the leading half of the edge (robust to early reflections)
    c10 = _crossings(xns, 0.1)
    c10t = np.array([_interp_idx(t, c) for c in c10]) if c10.size else np.array([])
    c10t = c10t[(c10t <= t_inc) & (c10t > t_inc - 40e-9)]
    rise = 2.0 * (t_inc - c10t[-1]) if c10t.size else float("nan")
    rise = float(np.clip(rise, ts, 40e-9)) if np.isfinite(rise) else 4 * ts

    # 6. final denoise: Gaussian, 0.3 x rise time on clean traces growing to
    #    0.9 x rise time on very noisy ones (>= 1 sample)
    nz = sig_v / v_inc if np.isfinite(sig_v) else 0.0
    sig_s = max(ts, rise * float(np.clip(0.3 + 2.0 * nz, 0.3, 0.9)))
    vsm = gaussian_filter1d(xn, sig_s / ts)

    return Processed(t=t - t_inc, v=xn, v_smooth=vsm, ts=ts, v_inc=float(v_inc),
                     baseline=base, noise_sigma=float(sig_v / v_inc), t_inc=t_inc,
                     rise_inc=rise, smooth_sigma=sig_s, ok=True, msg=msg)


def preprocess_measured(t: np.ndarray, v: np.ndarray, cal: dict | None = None,
                        v_inc: float | None = None, **kw) -> Processed:
    """``preprocess`` for measured traces: V_inc is estimated from each trace.

    The generator amplitude can change between configurations (the low-SNR
    traces are taken at 1/4-1/10 of the calibration amplitude), so one stored
    V_inc must not normalise every trace. The calibrated value is used only
    where it is the better number:
      * the estimate agrees with it within -20 / +25 % (same amplitude: the
        averaged calibration value is less noisy than one trace's plateau),
      * the estimate failed, or
      * the incident edge looks much slower than calibrated, i.e. an early echo
        merged into it and corrupted the plateau estimate.
    An explicit ``v_inc`` (e.g. typed into the dashboard) always wins.
    """
    if v_inc is not None and np.isfinite(v_inc) and v_inc > 0:
        return preprocess(t, v, v_inc=v_inc, **kw)
    cal = cal or {}
    ref = cal.get("v_inc_v") if cal.get("calibrated") else None
    ref = float(ref) if ref is not None and np.isfinite(ref) and ref > 0 else None
    est = preprocess(t, v, v_inc=None, **kw)
    if ref is None:
        return est
    rise_ref = cal.get("rise_time_s")
    use_ref = (not est.ok
               or 0.8 <= est.v_inc / ref <= 1.25
               or bool(rise_ref and np.isfinite(rise_ref) and est.rise_inc > 1.6 * float(rise_ref)))
    if not use_ref:
        est.msg = (est.msg + "; " if est.msg else "") + f"amplitude differs from calibration ({est.v_inc / ref:.2f} x)"
        return est
    out = preprocess(t, v, v_inc=ref, **kw)
    out.msg = (out.msg + "; " if out.msg else "") + "v_inc from calibration"
    return out


def shifted(proc: Processed, t_offset: float) -> Processed:
    """The same trace with the fixed fixture / trigger delay removed from its time axis.

    Measured echoes arrive at 2d/vp + t0 (t0 from calibration); the simulator and
    the models use 2d/vp. Model inputs (Method A grid, Method B timing features)
    are therefore taken on t - t0.
    """
    if not t_offset:
        return proc
    from dataclasses import replace
    return replace(proc, t=proc.t - t_offset, extra={**proc.extra, "t_offset": float(t_offset)})


def to_grid(proc: Processed, grid: np.ndarray = GRID_T) -> np.ndarray:
    """Method A input: the normalised trace on the common 256-point time grid.

    Anti-aliased when the trace is sampled faster than the grid; samples
    outside the recorded window hold the first / last value.
    """
    x = proc.v
    if proc.ts < GRID_DT * 0.75:
        x = gaussian_filter1d(x, 0.5 * GRID_DT / proc.ts)
    return np.interp(grid, proc.t, x, left=0.0, right=float(np.median(x[-5:])))
