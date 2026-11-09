"""Follow-up checks on the Zenodo study (code review findings 8 and 14).

1. Seed check: run 1 (`zenodo all`) drew the Z1 test noise from the same random
   stream as the training features, so test row i carried training row i's noise.
   Run 2 (`zenodo evaluate` after the fix) uses a split-specific seed. This
   compares the two Z1 tables model by model -> zenodo_seed_check.csv.
2. All-models table: run 2 evaluates the models stored in the bundle; the large
   raw-input forests (RF-A, ET-A) were only in run 1's memory. Their Z2 and Z3
   rows are reused from run 1 (identical inputs: Z2/Z3 noise seeds did not
   change); their Z1 rows are marked as shared-noise -> zenodo_results_all_models.csv.
3. Noise check: the matched-filter baseline sets its threshold from the noise in
   the blanked pulse region, which for the 16 real traces is synthetic (README
   noise level). Here the real traces' own noise is measured after the same
   high-pass, on the last quarter of the record -> zenodo_noise_check.csv.

    .venv\\Scripts\\python -I scripts\\zenodo_checks.py [noise|seed|merge]
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.config import RESULTS_DIR  # noqa: E402

COLS = ["MAE_d_first_m", "MedAE_d_first_m", "MAE_length_m", "acc_first_cls", "coverage"]


def mad(x):
    return 1.4826 * float(np.median(np.abs(x - np.median(x))))


def seed_check():
    old = pd.read_csv(RESULTS_DIR / "zenodo_z1_heldout_sim_run1.csv")
    new = pd.read_csv(RESULTS_DIR / "zenodo_z1_heldout_sim.csv")
    m = old[["method"] + COLS].merge(new[["method"] + COLS], on="method", suffixes=("_shared_noise", "_independent_noise"))
    for c in COLS:
        m[f"{c}_change"] = m[f"{c}_independent_noise"] - m[f"{c}_shared_noise"]
    m.to_csv(RESULTS_DIR / "zenodo_seed_check.csv", index=False)
    print(m[["method", "MAE_d_first_m_shared_noise", "MAE_d_first_m_independent_noise", "acc_first_cls_shared_noise",
             "acc_first_cls_independent_noise"]].round(3).to_string(index=False))


def merge():
    rows = []
    for exp, f in (("Z1", "zenodo_z1_heldout_sim"), ("Z2", "zenodo_z2_noise"), ("Z3", "zenodo_z3_real")):
        new = pd.read_csv(RESULTS_DIR / f"{f}.csv").assign(source="run 2 (independent noise)")
        old = pd.read_csv(RESULTS_DIR / f"{f}_run1.csv")
        extra = old[~old.method.isin(new.method)].copy()
        extra["source"] = ("run 1: Z1 noise shared with training (see seed check)" if exp == "Z1"
                           else "run 1 (inputs identical to run 2)")
        rows.append(pd.concat([new, extra], ignore_index=True).assign(set=exp))
    out = pd.concat(rows, ignore_index=True)
    out.to_csv(RESULTS_DIR / "zenodo_results_all_models.csv", index=False)
    print(out[["set", "method", "MAE_d_first_m", "acc_first_cls", "source"]].round(3).to_string(index=False))


def noise_check():
    from src import zenodo as Z
    Xr, _ = Z.real_traces()
    rng = np.random.default_rng(1)
    ref = np.array([mad(Z.PulseBaseline.highpass(rng.standard_normal(Z.N_SAMPLES) * Z.NOISE)[-256:]) for _ in range(200)])
    rows = []
    for i, x in enumerate(np.asarray(Xr, float)):
        hp = Z.PulseBaseline.highpass(x)
        rows.append({"trace": i, "noise_after_pulse_mad": mad(hp[Z.PULSE_END + 4:]), "noise_last_quarter_mad": mad(hp[-256:])})
    df = pd.DataFrame(rows)
    df["ratio_to_readme_noise"] = df.noise_last_quarter_mad / float(np.median(ref))
    df.to_csv(RESULTS_DIR / "zenodo_noise_check.csv", index=False)
    print(f"README noise level after the same high-pass: {np.median(ref):.6f}")
    print(f"16 real traces, last quarter: median {df.noise_last_quarter_mad.median():.6f}; ratio to README level "
          f"{df.ratio_to_readme_noise.min():.2f}-{df.ratio_to_readme_noise.max():.2f} (median {df.ratio_to_readme_noise.median():.2f})")


if __name__ == "__main__":
    what = sys.argv[1:] or ["noise", "seed", "merge"]
    for w in what:
        {"noise": noise_check, "seed": seed_check, "merge": merge}[w]()
