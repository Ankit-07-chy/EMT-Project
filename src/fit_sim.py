"""Fit the transmission-line simulator to a measured trace (WP4 sim-vs-lab check).

Free parameters: vp, rise time, attenuation scale, scope input capacitance,
generator output impedance, a small time shift and a gain. The fitted values
tell you how to centre the simulation ranges (SimConfig) on your real setup.

    python -m src.fit_sim --file data/raw/session/RG-58_5.02m_open_....csv \
        --length 5.02 --termination open --cable RG-58
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares

from .config import (CABLES, DEFAULT_CABLE, FIG_DIR, K_END, K_SERIES, K_SHUNT,
                     K_STEP, K_STUB, SimConfig, load_calibration)
from .preprocess import preprocess, preprocess_measured
from .scope_io import load_waveform
from .sim_tdr import make_params, simulate

KINDS = {"end": K_END, "series_R": K_SERIES, "shunt_R": K_SHUNT,
         "impedance_step": K_STEP, "open_stub": K_STUB}
NAMES = ["vp", "rise_s", "atten_scale", "scope_c_F", "rs_rel", "t_shift_s", "gain"]


def _row_get(row, k, default=None):
    try:
        v = row[k]
    except (KeyError, IndexError, TypeError):
        return default
    return default if v is None or (isinstance(v, float) and np.isnan(v)) else v


def fit_trace(t, v, row, cable: str | None = None, v_inc: float | None = None,
              window_after: float = 40e-9) -> dict:
    """``row`` needs cls (termination) and d (fault position, m); optional
    kind_name / zl_ohm. Returns aligned measured and fitted traces + params."""
    cal = load_calibration()
    cable = cable or _row_get(row, "cable_type", cal.get("cable_type", DEFAULT_CABLE))
    cfg = SimConfig(cable=cable if cable in CABLES else DEFAULT_CABLE)
    cls = str(_row_get(row, "cls", "open"))
    d = float(_row_get(row, "d"))
    kind = KINDS.get(str(_row_get(row, "kind_name", "end")), K_END)
    zl = _row_get(row, "zl_ohm")
    zl = float(zl) if zl not in (None, "") else None

    pr = preprocess_measured(t, v, cal, v_inc)
    if not pr.ok:
        raise ValueError(pr.msg)
    vp0 = float(cal["vp_m_per_s"])
    t_end = 2 * d / vp0 + window_after
    w = (pr.t > -15e-9) & (pr.t < t_end)
    tm, vm = pr.t[w], pr.v[w]

    def model(x):
        vp, rise, att, c, rs, sh, g = x
        kw = dict(cls=cls, d=d, kind=kind, rise=rise, snr_db=200, ts=0.2e-9, rs_rel=rs,
                  scope_c=c, vp=vp, atten_scale=att)
        if kind == K_END:
            kw["zl"] = zl if zl is not None else {"open": np.inf, "short": 0.0, "matched": cfg.preset.z0}.get(cls)
        elif kind in (K_SERIES, K_SHUNT):
            kw["r_fault"] = zl
        elif kind == K_STEP:
            kw["z2"] = zl
        p = make_params(cfg, **kw)
        (ts_, vs_), = simulate(p, cfg, noiseless=True)
        ps = preprocess(ts_, vs_, v_inc=p["v_inc"][0])
        return g * np.interp(tm - sh, ps.t, ps.v)

    rise0 = float(cal.get("rise_time_s", 5e-9)) if np.isfinite(pr.rise_inc) else 5e-9
    x0 = [vp0, max(pr.rise_inc, 1e-9) if np.isfinite(pr.rise_inc) else rise0, 1.0, 12e-12, 1.0, 0.0, 1.0]
    lo = [0.8 * vp0, 0.3e-9, 0.2, 1e-12, 0.7, -3e-9, 0.8]
    hi = [1.2 * vp0, 30e-9, 4.0, 60e-12, 1.4, 3e-9, 1.2]
    scale = [vp0 * 0.01, 1e-10, 0.05, 1e-12, 0.01, 1e-10, 0.01]
    res = least_squares(lambda x: model(x) - vm, x0, bounds=(lo, hi), x_scale=scale, diff_step=1e-3)
    fit = model(res.x)
    return {"t": tm, "v_meas": vm, "v_fit": fit, "params": dict(zip(NAMES, res.x.tolist())),
            "rmse": float(np.sqrt(np.mean((fit - vm) ** 2))), "success": bool(res.success)}


def plot_overlay(res: dict, path: Path, title: str = "Simulated vs measured trace"):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(8, 4.2))
    ax.plot(res["t"] * 1e9, res["v_meas"], color="#7a7975", lw=2, label="measured")
    ax.plot(res["t"] * 1e9, res["v_fit"], color="#2a78d6", lw=2, ls="--",
            label=f"fitted simulation (RMSE {res['rmse']:.3f})")
    ax.set(xlabel="time after incident edge (ns)", ylabel="V / V_inc", title=title)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(color="#e4e3df")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--file", required=True, type=Path)
    ap.add_argument("--length", type=float, required=True, help="cable length, m")
    ap.add_argument("--termination", default="open", choices=["open", "short", "matched", "partial"])
    ap.add_argument("--fault-kind", default="end", choices=list(KINDS))
    ap.add_argument("--fault-position", type=float, default=None)
    ap.add_argument("--zl", type=float, default=None, help="load / fault resistance or Z2, ohm")
    ap.add_argument("--cable", default=None)
    ap.add_argument("--channel", default=None)
    a = ap.parse_args(argv)
    wf = load_waveform(a.file, channel=a.channel)
    row = {"cls": a.termination, "d": a.fault_position or a.length, "kind_name": a.fault_kind,
           "zl_ohm": a.zl, "cable_type": a.cable}
    res = fit_trace(wf.t, wf.v, row, cable=a.cable)
    for k, v in res["params"].items():
        print(f"  {k:12s} {v:.4g}")
    print(f"  RMSE (normalised) {res['rmse']:.4f}  success={res['success']}")
    out = FIG_DIR / "fig5_sim_vs_lab_overlay.png"
    plot_overlay(res, out, f"Simulated vs measured: {a.file.name}")
    print(f"Saved {out}")


if __name__ == "__main__":
    main()
