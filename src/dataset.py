"""Build, save and load labelled datasets (simulated and lab).

A dataset is a dict with
    X     : (n, 256) float32  Method A input (normalised trace on GRID_T)
    F     : DataFrame         Method B features (FEATURES_B)
    B     : DataFrame         baseline outputs (base_dt, base_d, base_cls ...)
    meta  : DataFrame         labels + acquisition settings (see docs/data_dictionary.md)
    raw   : list[(t, v)]      optional raw traces
"""
from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pandas as pd

from .config import (CABLES, DEFAULT_CABLE, LAB_LOG, SIM_DIR, SimConfig,
                     load_calibration)
from .features import FEATURES_B, process_traces
from .sim_tdr import params_to_frame, sample_params, simulate


def build_sim(n: int, cfg: SimConfig, seed: int, keep_raw: bool = False,
              verbose: bool = True, **sample_kw) -> dict:
    """Simulate ``n`` traces and run the full processing chain on them."""
    rng = np.random.default_rng(seed)
    t0 = time.time()
    p = sample_params(n, cfg, rng, **sample_kw)
    traces = simulate(p, cfg)
    X, F, B = process_traces(traces, p["v_inc_ref"], vp=cfg.vp_nominal, preset=cfg.preset)
    meta = params_to_frame(p)
    meta["source"] = "sim_artifacts" if cfg.artifacts else f"sim_{cfg.model}"
    meta["vp_cal"] = cfg.vp_nominal
    if verbose:
        print(f"  built {n} traces (seed {seed}) in {time.time() - t0:.1f}s")
    return {"X": X, "F": F, "B": B, "meta": meta, "raw": traces if keep_raw else None}


def subset(ds: dict, mask) -> dict:
    mask = np.asarray(mask, bool)
    out = {"X": ds["X"][mask],
           "F": ds["F"][mask].reset_index(drop=True),
           "B": ds["B"][mask].reset_index(drop=True),
           "meta": ds["meta"][mask].reset_index(drop=True),
           "raw": None}
    if ds.get("raw") is not None:
        out["raw"] = [tr for tr, m in zip(ds["raw"], mask) if m]
    return out


def concat(*dss: dict) -> dict:
    return {"X": np.concatenate([d["X"] for d in dss]),
            "F": pd.concat([d["F"] for d in dss], ignore_index=True),
            "B": pd.concat([d["B"] for d in dss], ignore_index=True),
            "meta": pd.concat([d["meta"] for d in dss], ignore_index=True),
            "raw": None}


# ---------------------------------------------------------------- save / load
def save(ds: dict, name: str, folder: Path = SIM_DIR) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    np.save(folder / f"{name}_X.npy", ds["X"])
    table = pd.concat([ds["meta"], ds["B"], ds["F"]], axis=1)
    table.to_csv(folder / f"{name}.csv", index=False)
    if ds.get("raw") is not None:
        ts = np.array([tr[0][1] - tr[0][0] for tr in ds["raw"]])
        t0 = np.array([tr[0][0] for tr in ds["raw"]])
        nmax = max(len(tr[1]) for tr in ds["raw"])
        V = np.full((len(ds["raw"]), nmax), np.nan, np.float32)
        for i, (_, v) in enumerate(ds["raw"]):
            V[i, :len(v)] = v
        np.savez_compressed(folder / f"{name}_raw.npz", t0=t0, ts=ts, V=V)
    return folder / f"{name}.csv"


def load(name: str, folder: Path = SIM_DIR) -> dict:
    table = pd.read_csv(folder / f"{name}.csv")
    X = np.load(folder / f"{name}_X.npy")
    bcols = [c for c in table.columns if c.startswith("base_")] + ["prep_ok"]
    fcols = FEATURES_B
    mcols = [c for c in table.columns if c not in set(bcols) | set(fcols)]
    raw = None
    rp = folder / f"{name}_raw.npz"
    if rp.exists():
        z = np.load(rp)
        raw = []
        for t0, ts, v in zip(z["t0"], z["ts"], z["V"]):
            v = v[~np.isnan(v)].astype(float)
            raw.append((t0 + ts * np.arange(len(v)), v))
    return {"X": X, "F": table[fcols].astype(float), "B": table[bcols],
            "meta": table[mcols], "raw": raw}


# ---------------------------------------------------------------- lab data
def build_lab(log_csv: Path | str = LAB_LOG, calibration: dict | None = None,
              keep_raw: bool = True) -> dict | None:
    """Load every trace listed in the lab log and process it like sim data.

    The log is ``hardware/lab_log_template.csv`` filled in during the session.
    Paths in the ``file`` column are relative to the log's folder.
    """
    from .scope_io import load_waveform
    log_csv = Path(log_csv)
    if not log_csv.exists():
        return None
    log = pd.read_csv(log_csv)
    log = log[log["file"].notna() & log["termination"].notna()]
    if log.empty:
        return None
    cal = calibration or load_calibration()
    cable = cal.get("cable_type", DEFAULT_CABLE)
    preset = CABLES.get(cable, CABLES[DEFAULT_CABLE])
    vp = float(cal["vp_m_per_s"])
    traces, rows = [], []
    for _, r in log.iterrows():
        path = Path(r["file"])
        if not path.is_absolute():
            path = log_csv.parent / path
        ch = r.get("channel") if "channel" in r else None
        if ch is not None and (pd.isna(ch) or str(ch).strip() == ""):
            ch = None
        elif isinstance(ch, float) and float(ch).is_integer():
            ch = int(ch)   # a blank cell elsewhere makes pandas read the column as float
        try:
            wf = load_waveform(path, channel=ch)
        except Exception as exc:  # keep going, report the bad file
            print(f"  skip {path.name}: {exc}")
            continue
        traces.append((wf.t, wf.v))
        L = float(r.get("cable_length_m", np.nan))
        d = float(r["fault_position_m"]) if pd.notna(r.get("fault_position_m")) else L
        rows.append({"cls": str(r["termination"]).strip().lower(), "d": d, "l_total": L,
                     "dt_true": 2 * d / vp, "kind_name": r.get("fault_kind", "end"),
                     "has_fault": str(r["termination"]).strip().lower() != "matched",
                     "ts": wf.ts, "file": str(path), "source": "lab", "vp_cal": vp,
                     "cable_type": r.get("cable_type", cable),
                     "repeat_idx": r.get("repeat_idx", np.nan),
                     "config_id": f"{r.get('cable_type', '')}_{L:.2f}_{r['termination']}_{d:.2f}"})
    if not traces:
        return None
    # V_inc chosen per trace: the generator amplitude may differ between configurations
    X, F, B = process_traces(traces, None, vp=vp, preset=preset,
                             t_offset=float(cal.get("t_offset_s", 0.0)), cal=cal)
    return {"X": X, "F": F, "B": B, "meta": pd.DataFrame(rows),
            "raw": traces if keep_raw else None}
