"""Shared constants, paths, cable presets and simulation defaults.

Every number that a lab measurement can replace lives here or in
``data/calibration.json``. ``load_calibration()`` merges the two, so the rest of
the code never needs to know whether the setup has been calibrated yet.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

C0 = 299_792_458.0  # speed of light, m/s
NP_PER_DB = 1.0 / 8.685889638  # nepers per dB

# ---------------------------------------------------------------- paths
import os

CODE_ROOT = Path(__file__).resolve().parents[1]
# TDR_HOME moves every data / model / report folder somewhere else (the
# integration tests use it to run the whole pipeline in a temporary folder
# without touching the real results). Code is always read from CODE_ROOT.
ROOT = Path(os.environ.get("TDR_HOME") or CODE_ROOT).resolve()
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
SIM_DIR = DATA_DIR / "sim"
LAB_LOG = RAW_DIR / "lab_log.csv"
CALIBRATION_FILE = DATA_DIR / "calibration.json"
MODELS_DIR = ROOT / "models"
REPORT_DIR = ROOT / "report"
FIG_DIR = REPORT_DIR / "figures"
RESULTS_DIR = REPORT_DIR / "results"

for _d in (RAW_DIR, PROCESSED_DIR, SIM_DIR, MODELS_DIR, FIG_DIR, RESULTS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------- labels
CLASSES = ["open", "short", "matched", "partial"]

# Fault geometry codes used by the simulator
K_END, K_SERIES, K_SHUNT, K_STEP, K_STUB = 0, 1, 2, 3, 4
KIND_NAMES = {K_END: "end", K_SERIES: "series_R", K_SHUNT: "shunt_R",
              K_STEP: "impedance_step", K_STUB: "open_stub"}


# ---------------------------------------------------------------- cables
@dataclass(frozen=True)
class CablePreset:
    """Typical datasheet values. Replace with your cable's datasheet when known.

    Attenuation is modelled as alpha(f) = alpha_dc + k_skin*sqrt(f) + k_diel*f
    (Np/m), fitted through the two datasheet points at 100 MHz and 1 GHz.
    """
    name: str
    z0: float                 # characteristic impedance, ohm
    vf: float                 # velocity factor vp / c
    db100m_100mhz: float      # attenuation, dB per 100 m at 100 MHz
    db100m_1ghz: float        # attenuation, dB per 100 m at 1 GHz
    r_dc: float               # loop DC resistance, ohm per m

    @property
    def vp(self) -> float:
        return self.vf * C0

    @property
    def alpha_dc(self) -> float:
        return max(self.r_dc / (2 * self.z0), 1e-5)

    @property
    def k_skin_diel(self) -> tuple[float, float]:
        a1 = self.db100m_100mhz / 100 * NP_PER_DB
        a2 = self.db100m_1ghz / 100 * NP_PER_DB
        m = np.array([[np.sqrt(1e8), 1e8], [np.sqrt(1e9), 1e9]])
        ks, kd = np.linalg.solve(m, [a1, a2])
        return float(max(ks, 0.0)), float(max(kd, 0.0))

    def alpha(self, f: float | np.ndarray) -> float | np.ndarray:
        ks, kd = self.k_skin_diel
        return self.alpha_dc + ks * np.sqrt(f) + kd * f


CABLES: dict[str, CablePreset] = {
    "RG-58": CablePreset("RG-58", 50.0, 0.66, 16.0, 66.0, 0.050),
    "RG-174": CablePreset("RG-174", 50.0, 0.66, 29.0, 105.0, 0.33),
    "RG-316": CablePreset("RG-316", 50.0, 0.695, 27.0, 90.0, 0.30),
    "RG-59": CablePreset("RG-59", 75.0, 0.66, 11.0, 40.0, 0.12),
}
DEFAULT_CABLE = "RG-58"


# ---------------------------------------------------------------- time grid (Method A input)
GRID_T0 = -16e-9      # s, start of the common grid (incident edge is at t = 0)
GRID_DT = 1e-9        # s, 1 ns spacing
GRID_N = 256          # samples -> covers -16 ns ... +239 ns (about 23 m of RG-58)
GRID_T = GRID_T0 + GRID_DT * np.arange(GRID_N)


# ---------------------------------------------------------------- simulation defaults
@dataclass
class SimConfig:
    """Parameter ranges for synthetic traces (WP4 table).

    Ranges are centred on calibration values when ``data/calibration.json``
    exists, otherwise on wide priors that cover typical student lab gear.
    """
    cable: str = DEFAULT_CABLE
    d_min: float = 0.5                  # m
    d_max: float = 20.0                 # m
    vp_rel_spread: float = 0.03         # +-3 % around calibrated vp
    atten_scale: tuple = (0.7, 1.3)     # datasheet +-30 %
    rise_time: tuple = (2e-9, 10e-9)    # s, system (generator + scope) 10-90 %
    snr_db: tuple = (10.0, 40.0)        # 20*log10(V_inc / sigma_noise)
    rs_rel: tuple = (0.92, 1.08)        # generator output impedance / Z0
    scope_c: tuple = (8e-12, 20e-12)    # scope input capacitance at the tee
    scope_r: float = 1e6
    ts_choices: tuple = (0.5e-9, 1e-9, 2e-9)   # scope sample intervals
    t_pre: float = 50e-9                # record starts 50 ns before trigger
    t_post: float = 262e-9              # record ends 262 ns after trigger
    jitter: float = 2e-9                # trigger position uncertainty (+-)
    drift_max: float = 0.02             # baseline drift, fraction of V_inc
    adc_bits: int = 8
    v_inc_cal_err: float = 0.01         # relative error of the V_inc reference
    gamma_partial: tuple = (0.05, 0.70)  # |Gamma| range for the partial class
    matched_tol: float = 0.05           # ZL within +-5 % of Z0
    l2_range: tuple = (1.0, 8.0)        # m of cable after a mid-cable joint
    stub_len: tuple = (0.3, 3.0)        # m, open stub on a tee
    model: str = "tline"                # "tline" (frequency domain) or "simple"
    artifacts: bool = False             # lab-like artifacts (proxy lab set)
    vp_nominal: float = field(default=0.0)

    def __post_init__(self):
        if self.vp_nominal <= 0:
            self.vp_nominal = CABLES[self.cable].vp

    @property
    def preset(self) -> CablePreset:
        return CABLES[self.cable]


def cfg_tag(cfg: "SimConfig") -> str:
    """Short fingerprint of a simulation config, used in dataset cache names so a
    cached set is never reused after the calibration (and so the config) changed."""
    import hashlib
    txt = json.dumps({k: v for k, v in sorted(vars(cfg).items())}, default=str)
    return hashlib.md5(txt.encode()).hexdigest()[:6]


def load_calibration(path: Path | str | None = None) -> dict:
    """Return calibration values, falling back to datasheet defaults."""
    path = Path(path) if path else CALIBRATION_FILE
    cal = {
        "calibrated": False,
        "cable_type": DEFAULT_CABLE,
        "z0_ohm": CABLES[DEFAULT_CABLE].z0,
        "vp_m_per_s": CABLES[DEFAULT_CABLE].vp,
        "rise_time_s": 5e-9,
        "t_offset_s": 0.0,
        "v_inc_v": None,
    }
    if path.exists():
        with open(path, encoding="utf-8") as fh:
            cal.update(json.load(fh))
        cal["calibrated"] = True
    return cal


def sim_config_from_calibration(cal: dict | None = None, **overrides) -> SimConfig:
    """SimConfig centred on the lab calibration (if any)."""
    cal = cal or load_calibration()
    kw: dict = {}
    if cal.get("cable_type") in CABLES:
        kw["cable"] = cal["cable_type"]
    if cal.get("calibrated"):
        kw["vp_nominal"] = float(cal["vp_m_per_s"])
        tr = float(cal["rise_time_s"])
        kw["rise_time"] = (0.7 * tr, 1.3 * tr)
    kw.update(overrides)
    return SimConfig(**kw)
