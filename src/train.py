"""Model training (WP6): Random Forest / Extra Trees, Method A and Method B.

Regression target : round-trip delay dt_true in ns (only traces with a fault).
                    Distance is then d = vp_cal * dt / 2, which keeps the vp
                    calibration error separate from the model error.
Classification    : open / short / matched / partial (all traces).

Hyper-parameters are chosen on the validation set only; the test sets are
never touched here.

    python -m src.train --n-train 20000 --n-val 4000
"""
from __future__ import annotations

import argparse
import time
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, mean_absolute_error

from .config import (CLASSES, GRID_T, MODELS_DIR, RESULTS_DIR, SIM_DIR, cfg_tag,
                     SimConfig, sim_config_from_calibration)
from .features import FEATURES_B
from .models import FAMILIES, FAMILY_METHODS, SUPPORTS_WEIGHT, make_model

METHODS = ("A", "B")
_TREE = {
    ("reg", "A"): [{"max_features": mf, "min_samples_leaf": l} for mf in ("sqrt", 0.3) for l in (2, 5)],
    ("reg", "B"): [{"max_features": mf, "min_samples_leaf": l} for mf in (0.5, 1.0) for l in (2, 5)],
    ("cls", "A"): [{"max_features": mf, "min_samples_leaf": 1} for mf in ("sqrt", 0.3)],
    ("cls", "B"): [{"max_features": mf, "min_samples_leaf": 1} for mf in ("sqrt", 0.5)],
}
_KNN = [{"n_neighbors": k, "weights": "distance"} for k in (5, 15)]
_MLP = [{"hidden_layer_sizes": h, "alpha": 1e-4} for h in ((128, 64), (256, 128))]
_CNN = [{"epochs": 40, "patience": 6}]


def grid(task: str, method: str, family: str) -> list[dict]:
    """Hyper-parameter candidates, chosen on the validation set only."""
    if family in ("RF", "ET"):
        return _TREE[(task, method)]
    return {"KNN": _KNN, "MLP": _MLP, "CNN": _CNN}[family]


# kept for older imports
GRID = _TREE
ALGOS = {f: None for f in FAMILIES}
DEFAULT_BUNDLE = MODELS_DIR / "tdr_models.joblib"


def inputs(ds: dict, method: str) -> np.ndarray:
    return ds["X"] if method == "A" else ds["F"][FEATURES_B].to_numpy(np.float32)


def valid(ds: dict) -> np.ndarray:
    """Rows whose preprocessing worked (no incident edge = no model input)."""
    B = ds.get("B")
    if B is None or "prep_ok" not in B:
        return np.ones(len(ds["X"]), bool)
    return B["prep_ok"].astype(str).str.lower().isin(["true", "1", "1.0"]).to_numpy()


def targets(ds: dict):
    meta = ds["meta"]
    fault = meta["has_fault"].to_numpy(bool)
    return meta["dt_true"].to_numpy(float) * 1e9, fault, meta["cls"].astype(str).to_numpy()


def fit_xy(task, family, params, X, y, n_estimators=100, sample_weight=None):
    """Fit one model; families without sample-weight support get rows repeated."""
    m = make_model(task, family, params, n_estimators)
    if sample_weight is not None and family not in SUPPORTS_WEIGHT:
        rep = np.maximum(1, np.round(np.asarray(sample_weight)).astype(int))
        X, y, sample_weight = np.repeat(X, rep, axis=0), np.repeat(y, rep), None
    if sample_weight is None:
        m.fit(X, y)
    else:
        m.fit(X, y, sample_weight=sample_weight)
    return m


def fit(task, method, algo, params, ds, n_estimators=100, sample_weight=None):
    X = inputs(ds, method)
    y_dt, fault, y_cls = targets(ds)
    ok = valid(ds)
    rows = (fault & ok) if task == "reg" else ok
    sw = None if sample_weight is None else np.asarray(sample_weight)[rows]
    y = y_dt if task == "reg" else y_cls
    return fit_xy(task, algo, params, X[rows], y[rows], n_estimators, sw)


def combos(families=FAMILIES):
    return [(m, f) for m in METHODS for f in families if m in FAMILY_METHODS[f]]


def train_all(train: dict, val: dict, n_estimators: int = 100, verbose: bool = True,
              families=FAMILIES) -> dict:
    """Grid-search every (task, method, family) on the validation set."""
    models, rows = {}, []
    yv_dt, fv, yv_cls = targets(val)
    okv = valid(val)
    fv = fv & okv
    yv_cls = yv_cls[okv]
    for task in ("reg", "cls"):
        for method, algo in combos(families):
            Xv = inputs(val, method)
            Xv = Xv if task == "reg" else Xv[okv]
            best = None
            for params in grid(task, method, algo):
                t0 = time.time()
                m = fit(task, method, algo, params, train, n_estimators)
                if task == "reg":
                    score = mean_absolute_error(yv_dt[fv], m.predict(Xv[fv]))
                    better = best is None or score < best[0]
                else:
                    score = f1_score(yv_cls, m.predict(Xv), average="macro")
                    better = best is None or score > best[0]
                rows.append({"task": task, "method": method, "algo": algo,
                             "params": str(params), "val_score": score,
                             "metric": "MAE_dt_ns" if task == "reg" else "macro_F1",
                             "fit_s": time.time() - t0})
                if verbose:
                    print(f"  {task}-{method}-{algo} {params} -> {rows[-1]['metric']} = {score:.4f} ({rows[-1]['fit_s']:.1f}s)")
                if better:
                    best = (score, params, m)
            models[(task, method, algo)] = best[2]
            rows.append({"task": task, "method": method, "algo": algo, "params": str(best[1]),
                         "val_score": best[0], "metric": "SELECTED", "fit_s": 0.0})
    return {"models": models, "val_table": pd.DataFrame(rows)}


def make_bundle(trained: dict, cfg: SimConfig, n_train: int, n_estimators: int = 100,
                train_set: str | None = None) -> dict:
    imp = {}
    for algo in ("RF", "ET"):
        m = trained["models"].get(("reg", "B", algo))
        if m is not None:
            imp[algo] = dict(zip(FEATURES_B, m.feature_importances_.round(5).tolist()))
    return {"models": trained["models"], "val_table": trained["val_table"],
            "features_B": FEATURES_B, "grid_t": GRID_T, "classes": CLASSES,
            "vp_cal": cfg.vp_nominal, "cable": cfg.cable, "n_train": n_train,
            "n_estimators": n_estimators, "train_set": train_set or f"train_{n_train}_{cfg_tag(cfg)}",
            "sim_config": vars(cfg).copy(), "importances_B": imp,
            "created": datetime.now().isoformat(timespec="seconds")}


def predict(bundle: dict, ds: dict, vp: float | None = None) -> pd.DataFrame:
    """Predictions of every stored model: <ALGO>-<M>_dt (ns), _d (m), _cls, _conf.

    Traces whose preprocessing failed get no prediction (NaN distance, class
    "invalid"), so they count against coverage instead of producing a made-up answer.
    """
    vp = vp or bundle["vp_cal"]
    ok = valid(ds)
    out = {}
    for (task, method, algo), m in bundle["models"].items():
        X = inputs(ds, method)
        key = f"{algo}-{method}"
        if task == "reg":
            dt = np.where(ok, m.predict(X), np.nan)
            out[f"{key}_dt"] = dt
            out[f"{key}_d"] = vp * dt * 1e-9 / 2
        else:
            pr = m.predict_proba(X)
            out[f"{key}_cls"] = np.where(ok, m.classes_[pr.argmax(1)], "invalid")
            out[f"{key}_conf"] = np.where(ok, pr.max(1), 0.0)
    return pd.DataFrame(out)


def save_bundle(bundle: dict, path: Path = DEFAULT_BUNDLE) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, path, compress=3)
    return path


def load_bundle(path: Path = DEFAULT_BUNDLE) -> dict:
    return joblib.load(path)


def get_datasets(n_train: int, n_val: int, cfg: SimConfig, rebuild: bool = False):
    """Build (or reuse cached) training and validation sets."""
    from . import dataset as D
    out = []
    for name, n, seed in (("train", n_train, 1), ("val", n_val, 2)):
        tag = f"{name}_{n}_{cfg_tag(cfg)}"
        if not rebuild and (SIM_DIR / f"{tag}.csv").exists():
            print(f"  loading cached {tag}")
            out.append(D.load(tag))
        else:
            print(f"  simulating {tag}")
            ds = D.build_sim(n, cfg, seed)
            D.save(ds, tag)
            out.append(ds)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n-train", type=int, default=20000)
    ap.add_argument("--n-val", type=int, default=4000)
    ap.add_argument("--trees", type=int, default=100)
    ap.add_argument("--rebuild", action="store_true", help="re-simulate even if cached")
    ap.add_argument("--out", type=Path, default=DEFAULT_BUNDLE,
                    help="bundle path (evaluate --bundle and the dashboard read the default path)")
    ap.add_argument("--families", nargs="+", default=list(FAMILIES), choices=list(FAMILIES),
                    help="model families to train (default: all)")
    a = ap.parse_args(argv)
    cfg = sim_config_from_calibration()
    print(f"Simulation config: cable={cfg.cable} vp={cfg.vp_nominal:.4g} m/s rise={cfg.rise_time}")
    train, val = get_datasets(a.n_train, a.n_val, cfg, a.rebuild)
    t0 = time.time()
    trained = train_all(train, val, a.trees, families=a.families)
    bundle = make_bundle(trained, cfg, a.n_train, a.trees)
    p = save_bundle(bundle, a.out)
    trained["val_table"].to_csv(RESULTS_DIR / "validation_grid.csv", index=False)
    print(f"Saved {p} ({p.stat().st_size / 1e6:.1f} MB) after {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
