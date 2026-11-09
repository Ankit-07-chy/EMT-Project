"""Conventional baseline (WP5): threshold + derivative-peak detection.

On a preprocessed trace (incident 50 % crossing at t = 0, incident plateau = 1):

1. Differentiate the smoothed trace. The incident edge is the first big
   positive peak of dv/dt at t ~ 0.
2. Detection threshold = max(3 % of the incident slope, 4.5 x noise of dv/dt
   measured before the edge).
3. After the incident lobe has ended (and after a short blanking time), the
   first dv/dt lobe that exceeds the threshold is the reflection. Its sign is the
   polarity, its area is the reflected step amplitude, and the time where the
   trace crosses the midpoint between the levels before and after the lobe is
   the round-trip delay dt (50 % to 50 %, same convention as the incident).
4. d = vp * dt / 2. Gamma = amplitude * exp(2*alpha*d) (loss compensated).
5. Class: |amp| below the matched threshold -> matched, |Gamma| >= 0.82 -> open
   or short by sign, otherwise partial.

If the reflection overlaps the incident edge (fault closer than about
vp*t_rise/2) and has the same polarity, the two lobes merge; the result is then
flagged ``merged`` and dt is estimated from the lobe centroid.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from .config import CABLES, DEFAULT_CABLE, CablePreset
from .preprocess import Processed


@dataclass
class BaselineResult:
    found: bool = False
    dt: float = float("nan")          # round-trip delay, s
    distance: float = float("nan")    # m
    amp: float = 0.0                  # reflected step / incident step (signed)
    gamma_est: float = 0.0            # loss-compensated reflection coefficient
    cls: str = "matched"
    polarity: int = 0
    t_peak: float = float("nan")      # time of the dv/dt peak of the reflection, s
    refl_rise: float = float("nan")   # 10-90 % rise time of the reflected edge, s
    slope_ratio: float = 0.0          # reflection |dv/dt| peak / incident peak
    second_amp: float = 0.0
    second_t: float = float("nan")
    v_final: float = float("nan")
    merged: bool = False
    threshold: float = float("nan")   # dv/dt detection threshold (1/s)
    note: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


def _mad(x):
    return 1.4826 * float(np.median(np.abs(x - np.median(x)))) if x.size > 3 else float("nan")


def _cross_time(t, x, level, i0, i1, rising):
    seg = x[i0:i1 + 1] - level
    if seg.size < 2:
        return float("nan")
    s = np.sign(seg)
    idx = np.where(s[:-1] * s[1:] <= 0)[0]
    if rising is not None:
        idx = [k for k in idx if (seg[k + 1] > seg[k]) == rising]
    if len(idx) == 0:
        return float("nan")
    k = idx[0]
    a, b = seg[k], seg[k + 1]
    fr = a / (a - b) if a != b else 0.0
    return float(t[i0 + k] + fr * (t[i0 + k + 1] - t[i0 + k]))


def _lobe(t, vs, ds, j, sign, thr, rise, ts, lo_min=0):
    """Describe the dv/dt lobe that first exceeds the threshold at index j."""
    n = len(ds)
    m = max(2, int(np.ceil(1.5 * rise / ts)))
    seg = sign * ds[j: min(n, j + m)]
    stop = np.where(seg <= 0)[0]
    if stop.size:
        seg = seg[: stop[0]]
    k = j + int(np.argmax(seg)) if seg.size else j
    peak = sign * ds[k]
    lo = k
    while lo > lo_min and sign * ds[lo - 1] > 0.1 * peak:
        lo -= 1
    hi = k
    while hi < n - 1 and sign * ds[hi + 1] > 0.1 * peak:
        hi += 1
    before, after = vs[lo], vs[hi]
    amp = float(after - before)
    t50 = _cross_time(t, vs, before + 0.5 * amp, lo, hi, sign > 0)
    t10 = _cross_time(t, vs, before + 0.1 * amp, lo, hi, sign > 0)
    t90 = _cross_time(t, vs, before + 0.9 * amp, lo, hi, sign > 0)
    # parabolic refinement of the derivative peak
    tp = t[k]
    if 0 < k < n - 1:
        y0, y1, y2 = ds[k - 1], ds[k], ds[k + 1]
        den = y0 - 2 * y1 + y2
        if den != 0:
            tp = t[k] + 0.5 * (y0 - y2) / den * ts
    if not np.isfinite(t50):
        t50 = tp
    return dict(lo=lo, hi=hi, k=k, peak=peak, amp=amp, t50=t50, tp=tp,
                rise=(t90 - t10) if np.isfinite(t10) and np.isfinite(t90) else float("nan"))


def detect(proc: Processed, vp: float, preset: CablePreset | None = None,
           t_offset: float = 0.0, thr_frac: float = 0.03, k_sigma: float = 4.5,
           matched_amp: float = 0.035, hard: float = 0.82,
           blank: float | None = None, min_amp: float = 0.02) -> BaselineResult:
    """Run the baseline on a preprocessed trace. ``vp`` in m/s."""
    preset = preset or CABLES[DEFAULT_CABLE]
    res = BaselineResult()
    if not proc.ok:
        res.note = proc.msg or "preprocessing failed"
        return res
    t, vs, ts = proc.t, proc.v_smooth, proc.ts
    n = len(t)
    rise = proc.rise_inc if np.isfinite(proc.rise_inc) else 4 * ts
    res.v_final = float(np.median(proc.v[-max(5, n // 12):]))
    ds = np.gradient(vs, ts)

    near0 = np.abs(t) <= max(rise, 2 * ts)
    if not near0.any():
        res.note = "no samples near t=0"
        return res
    i_inc = int(np.where(near0)[0][np.argmax(ds[near0])])
    pk_inc = float(ds[i_inc])
    if pk_inc <= 0:
        res.note = "no incident slope"
        return res

    pre = t < -(0.5 * rise + 4e-9)
    tail = ds[-max(8, n // 6):]
    sig_pre = _mad(ds[pre]) if pre.sum() > 8 else float("nan")
    sig_ds = np.nanmax([sig_pre, _mad(tail), 0.0])
    thr = max(thr_frac * pk_inc, k_sigma * sig_ds)
    res.threshold = thr

    # incident lobe: everything around t = 0 where the slope is above threshold
    i_s, i_e = i_inc, i_inc
    while i_s > 0 and ds[i_s - 1] > thr:
        i_s -= 1
    while i_e < n - 1 and ds[i_e + 1] > thr:
        i_e += 1
    inc_area = float(vs[i_e] - vs[i_s])

    blank = 0.6 * rise if blank is None else blank
    start = max(i_e + 1, int(np.searchsorted(t, blank)))

    if inc_area > 1.3:  # same-polarity reflection merged into the incident edge
        w = ds[i_s:i_e + 1].clip(min=0)
        c = float(np.sum(t[i_s:i_e + 1] * w) / np.sum(w))
        a = inc_area - 1.0
        res.found, res.merged, res.amp, res.polarity = True, True, a, 1
        res.dt = max(c * (1 + a) / a, 0.0)
        res.t_peak = res.dt
        res.slope_ratio = 1.0
        res.note = "reflection merged with incident edge"
    else:
        # walk through threshold crossings; skip tiny lobes (noise / ADC steps)
        lb, pos = None, start
        while pos < n - 2:
            h = np.where(np.abs(ds[pos:]) > thr)[0]
            if not h.size:
                break
            j = pos + int(h[0])
            cand = _lobe(t, vs, ds, j, 1 if ds[j] > 0 else -1, thr, rise, ts, lo_min=pos)
            if abs(cand["amp"]) >= min_amp:
                lb = cand
                break
            pos = cand["hi"] + 1
        hits = [lb] if lb is not None else []
    if not res.merged and hits:
        sign = 1 if lb["amp"] > 0 else -1
        res.found, res.polarity, res.amp = True, sign, lb["amp"]
        res.dt, res.t_peak, res.refl_rise = lb["t50"], lb["tp"], lb["rise"]
        res.slope_ratio = float(lb["peak"] / pk_inc)
        # second lobe (re-reflection, stub return, far end ...)
        nxt = lb["hi"] + max(1, int(rise / ts))
        if nxt < n - 2:
            h2 = np.where(np.abs(ds[nxt:]) > thr)[0]
            if h2.size:
                j2 = nxt + int(h2[0])
                lb2 = _lobe(t, vs, ds, j2, 1 if ds[j2] > 0 else -1, thr, rise, ts, lo_min=nxt)
                res.second_amp, res.second_t = lb2["amp"], lb2["t50"]
    elif not res.merged:
        res.note = "no reflection above threshold"

    if res.found:
        # every reported time is on the fixture-corrected axis (echo at 2d/vp)
        res.dt = res.dt - t_offset
        res.t_peak = res.t_peak - t_offset
        res.second_t = res.second_t - t_offset
        res.distance = vp * res.dt / 2
        # the settled step height is set by the low-frequency loss (~0.1 / t_rise),
        # not by the 0.35 / t_rise knee that shapes the edge itself
        a_eff = float(preset.alpha(0.1 / rise))
        res.gamma_est = float(np.clip(res.amp * np.exp(2 * a_eff * max(res.distance, 0.0)), -1.5, 1.5))
        if abs(res.amp) < matched_amp:
            res.cls = "matched"
        elif res.gamma_est >= hard:
            res.cls = "open"
        elif res.gamma_est <= -hard:
            res.cls = "short"
        else:
            res.cls = "partial"
    return res
