"""Calibration (WP2): vp, fixture offset, rise time, resolution, V_inc, noise.

Uses the open-circuit traces in the lab log (termination = open, fault_kind = end):

    python -m src.calibrate                         # data/raw/lab_log.csv
    python -m src.calibrate --log data/raw/simulated_session/lab_log.csv
    python -m src.calibrate --files a.csv b.csv --lengths 2.01 5.02 --cable RG-58

For every trace: dt = 50 %-to-50 % delay between incident and reflected edge.
    single length : vp = 2L / dt              (mean +- std over repeats)
    >= 2 lengths  : fit dt = (2/vp) L + t0    (t0 = tee / adapter / trigger offset)
Rise time is the 10-90 % time of the incident edge; resolution d_min = vp t_r / 2.
Writes data/calibration.json, report/results/calibration_traces.csv and
report/figures/fig0_calibration.png.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.ndimage import gaussian_filter1d

from .baseline import detect
from .config import (CABLES, CALIBRATION_FILE, DEFAULT_CABLE, FIG_DIR, LAB_LOG,
                     RESULTS_DIR)
from .preprocess import _crossings, _interp_idx, preprocess
from .scope_io import load_waveform


def rise_10_90(pr) -> float:
    """Full 10-90 % rise time of the incident edge (needs a plateau before the reflection)."""
    x = gaussian_filter1d(pr.v, 0.7)
    c10 = [_interp_idx(pr.t, c) for c in _crossings(x, 0.1)]
    c90 = [_interp_idx(pr.t, c) for c in _crossings(x, 0.9)]
    t10 = max([c for c in c10 if c <= 0], default=np.nan)
    t90 = min([c for c in c90 if c >= 0], default=np.nan)
    return float(t90 - t10)


def measure(entries, cable: str, channel=None) -> pd.DataFrame:
    preset = CABLES.get(cable, CABLES[DEFAULT_CABLE])
    rows = []
    for path, L in entries:
        try:
            wf = load_waveform(path, channel=channel)
        except Exception as exc:
            print(f"  skip {Path(path).name}: {exc}")
            continue
        pr = preprocess(wf.t, wf.v)
        if not pr.ok:
            print(f"  skip {Path(path).name}: {pr.msg}")
            continue
        b = detect(pr, preset.vp, preset)
        if not b.found or b.polarity < 0:
            print(f"  skip {Path(path).name}: no positive (open-circuit) reflection")
            continue
        rows.append({"file": str(path), "length_m": float(L), "dt_s": b.dt, "amp": b.amp,
                     "rise_s": rise_10_90(pr), "v_inc_v": pr.v_inc,
                     "noise_v": pr.noise_sigma * pr.v_inc, "ts_s": pr.ts})
    return pd.DataFrame(rows)


def solve(df: pd.DataFrame, cable: str) -> dict:
    if df.empty:
        raise SystemExit("No usable open-circuit traces.")
    df = df.assign(vp_each=2 * df.length_m / df.dt_s)
    per = (df.groupby("length_m")
             .agg(n=("dt_s", "size"), dt_mean_s=("dt_s", "mean"), dt_std_s=("dt_s", "std"),
                  vp_mean=("vp_each", "mean"), amp_mean=("amp", "mean"))
             .reset_index())
    out = {"created": datetime.now().isoformat(timespec="seconds"), "cable_type": cable,
           "z0_ohm": CABLES.get(cable, CABLES[DEFAULT_CABLE]).z0, "n_traces": int(len(df)),
           "per_length": per.to_dict(orient="records")}
    if len(per) >= 2:
        if len(df) > 3:   # the covariance needs more points than parameters + 1
            (slope, t0), cov = np.polyfit(df.length_m, df.dt_s, 1, cov=True)
            sd_slope, sd_t0 = float(np.sqrt(cov[0, 0])), float(np.sqrt(cov[1, 1]))
        else:
            slope, t0 = np.polyfit(df.length_m, df.dt_s, 1)
            sd_slope = sd_t0 = float("nan")
            print("  note: only 2-3 traces, no uncertainty on vp (take >= 10 repeats per length)")
        vp = 2.0 / slope
        vp_std = 2.0 / slope**2 * sd_slope
        out.update(method="two-length fit dt = (2/vp) L + t0", vp_m_per_s=float(vp),
                   vp_std=float(vp_std), t_offset_s=float(t0), t_offset_std_s=sd_t0)
        amp = per.amp_mean.clip(1e-3)
        if (amp > 0).all():
            a_slope = np.polyfit(2 * per.length_m, np.log(amp), 1)[0]
            out["alpha_eff_np_per_m"] = float(max(-a_slope, 0.0))
    else:
        out.update(method="single length: vp = 2L/dt", vp_m_per_s=float(df.vp_each.mean()),
                   vp_std=float(df.vp_each.std(ddof=1)) if len(df) > 1 else float("nan"),
                   t_offset_s=0.0)
    out["velocity_factor"] = out["vp_m_per_s"] / 299_792_458.0
    r = df.rise_s.dropna()
    out["rise_time_s"] = float(r.mean())
    out["rise_time_std_s"] = float(r.std(ddof=1)) if len(r) > 1 else float("nan")
    out["resolution_m"] = out["vp_m_per_s"] * out["rise_time_s"] / 2
    # V_inc / noise from the traces at the session's normal amplitude only: open-end
    # rows taken at reduced amplitude (low-SNR set) still give valid delays above,
    # but must not drag the stored V_inc down
    med = float(df.v_inc_v.median())
    main = df[(df.v_inc_v > 0.8 * med) & (df.v_inc_v < 1.25 * med)]
    out["v_inc_v"] = float(main.v_inc_v.mean())
    out["v_inc_std_v"] = float(main.v_inc_v.std(ddof=1)) if len(main) > 1 else float("nan")
    out["n_traces_v_inc"] = int(len(main))
    out["noise_sigma_v"] = float(main.noise_v.mean())
    out["noise_sigma_norm"] = out["noise_sigma_v"] / out["v_inc_v"]
    out["snr_db"] = float(20 * np.log10(1 / out["noise_sigma_norm"])) if out["noise_sigma_norm"] > 0 else None
    out["sample_interval_s"] = float(df.ts_s.median())
    return out


def plot(df: pd.DataFrame, cal: dict, path: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(6.5, 4))
    ax.scatter(df.length_m, df.dt_s * 1e9, s=14, color="#2a78d6", alpha=0.6, label="open-circuit traces")
    L = np.linspace(0, df.length_m.max() * 1.1, 50)
    ax.plot(L, (2 * L / cal["vp_m_per_s"] + cal["t_offset_s"]) * 1e9, color="#52514e", lw=2,
            label=f"vp = {cal['vp_m_per_s'] / 1e8:.4f}e8 m/s (VF {cal['velocity_factor']:.3f})")
    ax.set(xlabel="cable length (m)", ylabel="round-trip delay (ns)", title="Calibration: delay vs length")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(color="#e4e3df")
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def entries_from_log(log: Path):
    df = pd.read_csv(log)
    kind = df.get("fault_kind", pd.Series(["end"] * len(df))).fillna("end")
    sel = df[(df.termination.str.lower() == "open") & (kind == "end")]
    out = []
    for _, r in sel.iterrows():
        p = Path(r["file"])
        out.append((p if p.is_absolute() else log.parent / p, float(r["cable_length_m"])))
    cable = str(sel.cable_type.mode().iloc[0]) if len(sel) and "cable_type" in sel else DEFAULT_CABLE
    return out, cable


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--log", type=Path, default=LAB_LOG)
    ap.add_argument("--files", nargs="*", type=Path)
    ap.add_argument("--lengths", nargs="*", type=float)
    ap.add_argument("--cable", default=None)
    ap.add_argument("--channel", default=None)
    ap.add_argument("--out", type=Path, default=CALIBRATION_FILE)
    a = ap.parse_args(argv)
    if a.files:
        if not a.lengths or len(a.lengths) not in (1, len(a.files)):
            ap.error("--lengths: give one length, or one per file")
        lengths = a.lengths * len(a.files) if len(a.lengths) == 1 else a.lengths
        entries, cable = list(zip(a.files, lengths)), a.cable or DEFAULT_CABLE
    else:
        if not a.log.exists():
            ap.error(f"{a.log} not found. Capture open-circuit traces first (src.capture) or pass --files.")
        entries, cable = entries_from_log(a.log)
        cable = a.cable or cable
    print(f"Calibrating from {len(entries)} open-circuit traces ({cable})")
    df = measure(entries, cable, a.channel)
    cal = solve(df, cable)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(cal, indent=2, default=float), encoding="utf-8")
    df.to_csv(RESULTS_DIR / "calibration_traces.csv", index=False)
    plot(df, cal, FIG_DIR / "fig0_calibration.png")
    print(f"vp = {cal['vp_m_per_s']:.5g} +- {cal['vp_std']:.2g} m/s  (VF {cal['velocity_factor']:.4f}, {cal['method']})")
    print(f"t_offset = {cal['t_offset_s'] * 1e9:.2f} ns   rise = {cal['rise_time_s'] * 1e9:.2f} ns   "
          f"resolution = {cal['resolution_m']:.3f} m")
    snr = f"{cal['snr_db']:.1f} dB" if cal.get("snr_db") is not None else "n/a (no measurable pre-edge noise)"
    print(f"V_inc = {cal['v_inc_v']:.4f} V   noise = {cal['noise_sigma_v'] * 1e3:.2f} mV   SNR = {snr}")
    print(f"Saved {a.out}")


if __name__ == "__main__":
    main()
