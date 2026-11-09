"""Gather every number the presentation shows into presentation/deck_data.json.

All values are read from report/results/* (written by evaluate, analyze,
selftest and zenodo); nothing is typed in by hand.

    .venv\\Scripts\\python presentation\\collect_data.py
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
import os
RES = Path(os.environ.get("DECK_RESULTS") or ROOT / "report" / "results")


def rd(name):
    p = RES / name
    return pd.read_csv(p) if p.exists() else None


def clean(o):
    if isinstance(o, float):
        return None if math.isnan(o) or math.isinf(o) else round(o, 5)
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items()}
    if isinstance(o, list):
        return [clean(v) for v in o]
    if hasattr(o, "item"):
        return clean(o.item())
    return o


def records(df, cols=None):
    if df is None:
        return []
    df = df if cols is None else df[[c for c in cols if c in df.columns]]
    return df.to_dict(orient="records")


def main():
    D = {}
    sj = RES / "summary.json"
    D["summary"] = json.loads(sj.read_text()) if sj.exists() else {}
    aj = RES / "analysis_summary.json"
    D["analysis"] = json.loads(aj.read_text()) if aj.exists() else {}
    D["mixed"] = records(rd("mixed_regression.csv"), ["method", "n", "coverage", "MAE_m", "RMSE_m", "MedAE_m", "MAE_m_on_base_detected"])
    D["cls"] = records(rd("classification.csv"), ["method", "accuracy", "precision", "recall", "F1"])
    loc = rd("analysis_localization.csv")
    if loc is not None:
        D["loc_all"] = records(loc[~loc.subset.str.startswith("faults")])
        D["loc_fair"] = records(loc[loc.subset.str.startswith("faults")])
    D["det"] = records(rd("analysis_detection_binary.csv"))
    pc = rd("analysis_detection_per_class.csv")
    if pc is not None:
        D["per_class"] = records(pc.pivot_table(index="method", columns="cls", values="F1").reset_index())
        D["per_class_full"] = records(pc)
    D["fnfp"] = records(rd("analysis_fn_fp.csv"))
    D["lat"] = records(rd("analysis_latency.csv"))
    D["cfg"] = records(rd("analysis_model_config.csv"), ["task", "key", "params", "val_score", "size_MB", "detail"])
    w = rd("analysis_worst_cases.csv")
    D["worst"] = records(w.head(8)) if w is not None else []
    br = rd("analysis_localization_breakdown.csv")
    D["breakdown"] = records(br) if br is not None else []
    e1 = rd("e1_snr_sweep.csv")
    if e1 is not None:
        D["e1_fair"] = records(e1.pivot_table(index="snr_db", columns="method", values="MAE_m_on_base_detected").reset_index())
        D["e1_f1"] = records(e1.pivot_table(index="snr_db", columns="method", values="F1").reset_index())
        D["e1_cov"] = records(e1.pivot_table(index="snr_db", columns="method", values="coverage").reset_index())
    D["e2"] = records(rd("e2_heldout_distances.csv"), ["band", "method", "n", "MAE_m", "MAE_m_on_base_detected"])
    D["e34"] = records(rd("e3_e4_sim_to_lab.csv"), ["experiment", "data", "method", "MAE_m", "coverage", "MAE_m_on_base_detected"])
    D["e34c"] = records(rd("e3_e4_classification.csv"), ["experiment", "data", "method", "accuracy", "F1"])
    D["e5"] = records(rd("e5_soft_faults.csv"), ["gamma_abs", "method", "detection_rate", "MAE_m"])
    D["e6"] = records(rd("e6_method_a_vs_b.csv"))
    D["val"] = records(rd("validation_grid.csv"))
    ft = rd("feature_tests.csv")
    D["features"] = records(ft)
    for k, f in (("z1", "zenodo_z1_heldout_sim.csv"), ("z1n", "zenodo_z1_by_fault_count.csv"), ("z2", "zenodo_z2_noise.csv"),
                 ("z3", "zenodo_z3_real.csv"), ("zlog", "zenodo_training_log.csv"), ("zcnn", "zenodo_cnn_history.csv")):
        D[k] = records(rd(f))
    D["zall"] = records(rd("zenodo_results_all_models.csv"))
    zs = RES / "zenodo_summary.md"
    D["zenodo_summary_md"] = zs.read_text(encoding="utf-8") if zs.exists() else ""
    out = Path(__file__).resolve().parent / "deck_data.json"
    out.write_text(json.dumps(clean(D), indent=1), encoding="utf-8")
    print(f"Saved {out} ({out.stat().st_size / 1e3:.0f} kB): " + ", ".join(f"{k}={len(v) if isinstance(v, list) else 'obj'}" for k, v in D.items()))


if __name__ == "__main__":
    main()
