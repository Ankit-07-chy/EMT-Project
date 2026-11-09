"""Evaluation (WP7): experiments E1-E6, result tables and report figures.

    python -m src.evaluate            # full run
    python -m src.evaluate --quick    # smaller test sets

E1  train on sim, test on sim, SNR sweep        -> does ML beat the baseline in noise?
E2  held-out distances (gap + beyond range)     -> interpolation / extrapolation
E3  train on sim, test on lab                   -> sim-to-real gap
E4  sim + small lab fine-tune, test on lab      -> does a little real data help?
E5  soft faults (small |Gamma|)                 -> where does each method fail?
E6  Method A (raw samples) vs Method B (features), for every model family

Model families: RF, Extra Trees (brief), KNN (Slimani 2024/25), MLP (Smail 2011),
1-D CNN (Scarpetta 2021, Slimani 2024). See src/models.py.

If no lab data is logged yet (data/raw/lab_log.csv), E3/E4 run on a PROXY lab
set: simulated traces with lab-like artifacts that are absent from training
(adapter discontinuity at the tee, generator overshoot/ringing, 1/f noise).
Every table and figure is marked PROXY in that case. Real measured data from
the literature is evaluated separately in src/zenodo.py.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import json
import time

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.metrics import (accuracy_score, confusion_matrix,  # noqa: E402
                             precision_recall_fscore_support)

from . import dataset as D  # noqa: E402
from .config import (CLASSES, FIG_DIR, LAB_LOG, RESULTS_DIR, SIM_DIR, cfg_tag,  # noqa: E402
                     SimConfig, sim_config_from_calibration)
from .models import FAMILIES, FAMILY_NAME  # noqa: E402
from .train import DEFAULT_BUNDLE, fit, load_bundle, predict  # noqa: E402

# ---- chart style: hue = model family (fixed palette order), line style = input, baseline = neutral
INK, INK2, GRIDC, SURF = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
GRAY = "#7a7975"
FAM_COLOR = {"RF": "#2a78d6", "ET": "#eb6834", "KNN": "#1baf7a", "MLP": "#eda100", "CNN": "#e87ba4"}
FAM_MARK = {"RF": "o", "ET": "D", "KNN": "^", "MLP": "v", "CNN": "s"}
BLUE, ORANGE = FAM_COLOR["RF"], FAM_COLOR["ET"]
SEQ = ["#fcfcfb", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]

ML_KEYS: list[str] = []          # set from the bundle by set_keys()
METHODS_ALL: list[str] = ["Baseline"]
PLOT_KEYS: list[str] = ["Baseline"]   # baseline + the better input of each family


def set_keys(bundle):
    global ML_KEYS, METHODS_ALL, PLOT_KEYS
    have = {f"{a}-{m}" for (_, m, a) in bundle["models"]}
    ML_KEYS = [f"{f}-{m}" for f in FAMILIES for m in ("A", "B") if f"{f}-{m}" in have]
    METHODS_ALL = ["Baseline"] + ML_KEYS
    PLOT_KEYS = list(METHODS_ALL)


def style(key):
    if key == "Baseline":
        return dict(color=GRAY, ls="-", marker="X")
    fam, m = key.split("-")
    return dict(color=FAM_COLOR[fam], ls="-" if m == "B" else "--", marker=FAM_MARK[fam])


def label(key):
    if key == "Baseline":
        return "Baseline (threshold + peak)"
    fam, m = key.split("-")
    return f"{FAMILY_NAME[fam]}, {'features (B)' if m == 'B' else 'raw samples (A)'}"


def _style():
    plt.rcParams.update({
        "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
        "axes.edgecolor": INK2, "axes.labelcolor": INK, "text.color": INK,
        "xtick.color": INK2, "ytick.color": INK2, "axes.grid": True,
        "grid.color": GRIDC, "grid.linewidth": 0.8, "axes.spines.top": False,
        "axes.spines.right": False, "lines.linewidth": 2, "lines.markersize": 6,
        "legend.frameon": False, "font.size": 10, "axes.titlesize": 11,
        "axes.titleweight": "bold", "figure.dpi": 110,
    })


# ---------------------------------------------------------------- metrics
def method_outputs(ds: dict, preds: pd.DataFrame) -> dict:
    """name -> (d_pred [m], dt_pred [ns], produced_estimate mask, class)."""
    B = ds["B"]
    out = {"Baseline": (B["base_d"].to_numpy(float), B["base_dt"].to_numpy(float) * 1e9,
                        B["base_found"].to_numpy(bool), B["base_cls"].astype(str).to_numpy())}
    for k in ML_KEYS:
        if f"{k}_d" in preds:
            out[k] = (preds[f"{k}_d"].to_numpy(float), preds[f"{k}_dt"].to_numpy(float),
                      np.ones(len(preds), bool),
                      preds[f"{k}_cls"].astype(str).to_numpy() if f"{k}_cls" in preds else None)
    return out


def reg_metrics(meta: pd.DataFrame, d_pred, dt_pred, found, subset=None) -> dict:
    fault = meta["has_fault"].to_numpy(bool)
    base = fault if subset is None else fault & subset
    m = base & found & np.isfinite(d_pred)
    if m.sum() == 0:
        return dict(n=0, coverage=0.0, MAE_m=np.nan, RMSE_m=np.nan, MedAE_m=np.nan,
                    MAE_pct_L=np.nan, MAE_dt_ns=np.nan)
    e = d_pred[m] - meta["d"].to_numpy(float)[m]
    edt = dt_pred[m] - meta["dt_true"].to_numpy(float)[m] * 1e9
    L = meta["l_total"].to_numpy(float)[m]
    return dict(n=int(m.sum()), coverage=float(m.sum() / max(base.sum(), 1)),
                MAE_m=float(np.mean(np.abs(e))), RMSE_m=float(np.sqrt(np.mean(e**2))),
                MedAE_m=float(np.median(np.abs(e))), MAE_pct_L=float(np.mean(np.abs(e) / L) * 100),
                MAE_dt_ns=float(np.mean(np.abs(edt))))


def score_rows(ds, preds, **tags) -> list[dict]:
    """Distance metrics for every method; ML also scored on the baseline-detected subset."""
    outs = method_outputs(ds, preds)
    base_found = outs["Baseline"][2]
    rows = []
    for name, (d, dt, found, _) in outs.items():
        r = dict(tags, method=name, **reg_metrics(ds["meta"], d, dt, found))
        r["MAE_m_on_base_detected"] = reg_metrics(ds["meta"], d, dt, found, subset=base_found)["MAE_m"]
        rows.append(r)
    return rows


def cls_rows(ds, preds, **tags) -> list[dict]:
    y = ds["meta"]["cls"].astype(str).to_numpy()
    rows = []
    for name, (_, _, _, c) in method_outputs(ds, preds).items():
        if c is None:
            continue
        p, r, f, _ = precision_recall_fscore_support(y, c, labels=CLASSES, average="macro", zero_division=0)
        rows.append(dict(tags, method=name, accuracy=accuracy_score(y, c), precision=p, recall=r, F1=f))
    return rows


def md_table(df: pd.DataFrame, floatfmt="{:.3f}") -> str:
    cols = list(df.columns)
    fmt = lambda v: floatfmt.format(v) if isinstance(v, (float, np.floating)) else str(v)
    lines = ["| " + " | ".join(str(c) for c in cols) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join(fmt(v) for v in row) + " |" for row in df.itertuples(index=False)]
    return "\n".join(lines)


# ---------------------------------------------------------------- data helpers
def cached(name: str, n: int, cfg: SimConfig, seed: int, rebuild: bool = False, **kw) -> dict:
    name = f"{name}_{cfg_tag(cfg)}"   # never reuse a set simulated under another config
    if not rebuild and (SIM_DIR / f"{name}.csv").exists():
        return D.load(name)
    ds = D.build_sim(n, cfg, seed, verbose=False, **kw)
    D.save(ds, name)
    return ds


def selected_params(bundle) -> dict:
    vt = bundle["val_table"]
    sel = vt[vt["metric"] == "SELECTED"]
    return {(r.task, r.method, r.algo): eval(r.params) for r in sel.itertuples()}  # noqa: S307 (own file)


def retrain(bundle, ds, tasks=("reg",), sample_weight=None):
    """Refit every stored model type with its selected hyper-parameters on ``ds``."""
    params = selected_params(bundle)
    out = {}
    for (task, method, algo) in bundle["models"]:
        if task in tasks:
            out[(task, method, algo)] = fit(task, method, algo, params[(task, method, algo)], ds,
                                            n_estimators=bundle.get("n_estimators", 100),
                                            sample_weight=sample_weight)
    return dict(bundle, models=out)


# ---------------------------------------------------------------- experiments
def run(quick: bool = False, rebuild: bool = False, bundle_path=None):
    global PLOT_KEYS
    _style()
    t_start = time.time()
    bundle = load_bundle(bundle_path or DEFAULT_BUNDLE)
    set_keys(bundle)
    cfg = sim_config_from_calibration()
    n_tr = bundle["n_train"]
    scale = 0.35 if quick else 1.0
    N = lambda k: max(150, int(k * scale))
    summary: dict = {"created": time.strftime("%Y-%m-%d %H:%M"), "quick": quick, "models": ML_KEYS}

    # ---------- mixed test set (random SNR, all classes) ----------
    print("Mixed test set")
    test = cached(f"test_mixed_{N(6000)}", N(6000), cfg, 3, rebuild)
    pt = predict(bundle, test)
    mixed = pd.DataFrame(score_rows(test, pt, experiment="mixed"))
    cls_tab = pd.DataFrame(cls_rows(test, pt, experiment="mixed"))
    mixed.to_csv(RESULTS_DIR / "mixed_regression.csv", index=False)
    cls_tab.to_csv(RESULTS_DIR / "classification.csv", index=False)
    # one line per family in the charts: the input (A/B) with the lower fair MAE
    ml = mixed[mixed.method != "Baseline"].assign(fam=lambda x: x.method.str.split("-").str[0])
    best_per_fam = ml.sort_values("MAE_m_on_base_detected").groupby("fam").head(1)
    PLOT_KEYS = ["Baseline"] + [k for k in ML_KEYS if k in set(best_per_fam.method)]

    # ---------- E1: SNR sweep ----------
    print("E1 SNR sweep")
    e1, e1c = [], []
    for snr in (10, 15, 20, 25, 30, 35, 40):
        ds = cached(f"test_e1_snr{snr}_{N(1200)}", N(1200), cfg, 100 + snr, rebuild, snr_db=snr)
        pr = predict(bundle, ds)
        e1 += score_rows(ds, pr, experiment="E1", snr_db=snr)
        e1c += cls_rows(ds, pr, snr_db=snr)
    e1 = pd.DataFrame(e1).merge(pd.DataFrame(e1c)[["snr_db", "method", "F1"]], on=["snr_db", "method"], how="left")
    e1.to_csv(RESULTS_DIR / "e1_snr_sweep.csv", index=False)

    # ---------- E2: held-out distances ----------
    print("E2 held-out distances")
    train = D.load(bundle.get("train_set", f"train_{n_tr}"))
    dtr = train["meta"]["d"].to_numpy()
    tr_sub = D.subset(train, (dtr < 4) | ((dtr >= 6) & (dtr < 14)))
    pe2 = predict(retrain(bundle, tr_sub, ("reg",)), test)
    dte = test["meta"]["d"].to_numpy()
    bands = {"in-range (trained)": (dte < 4) | ((dte >= 6) & (dte < 14)),
             "gap 4-6 m (interpolation)": (dte >= 4) & (dte < 6),
             "beyond 14 m (extrapolation)": dte >= 14}
    e2 = []
    for band, m in bands.items():
        e2 += score_rows(D.subset(test, m), pe2[m].reset_index(drop=True), experiment="E2", band=band)
    e2 = pd.DataFrame(e2)
    e2.to_csv(RESULTS_DIR / "e2_heldout_distances.csv", index=False)

    # ---------- E3 / E4: sim-to-lab gap ----------
    print("E3/E4 sim-to-lab")
    lab = D.build_lab(LAB_LOG) if LAB_LOG.exists() else None
    proxy = lab is None or len(lab["meta"]) < 20
    rng = np.random.default_rng(7)
    if proxy:
        lab = cached(f"proxy_lab_{N(1500)}", N(1500), sim_config_from_calibration(artifacts=True), 30, rebuild)
        ft_mask = rng.random(len(lab["meta"])) < 0.10
    else:  # split by configuration so repeats of one setup never sit on both sides
        cfgs = lab["meta"]["config_id"].unique()
        ft_cfg = set(rng.choice(cfgs, max(1, len(cfgs) // 5), replace=False))
        ft_mask = lab["meta"]["config_id"].isin(ft_cfg).to_numpy()
    tag = "PROXY (sim + artifacts)" if proxy else "LAB"
    lab_test, lab_ft = D.subset(lab, ~ft_mask), D.subset(lab, ft_mask)
    p3 = predict(bundle, lab_test)
    e34 = score_rows(lab_test, p3, experiment="E3 sim->lab", data=tag)
    c34 = cls_rows(lab_test, p3, experiment="E3 sim->lab", data=tag)
    both = D.concat(train, lab_ft)
    w = np.r_[np.ones(len(train["meta"])), np.full(len(lab_ft["meta"]), 5.0)]
    p4 = predict(retrain(bundle, both, ("reg", "cls"), sample_weight=w), lab_test)
    e34 += [r for r in score_rows(lab_test, p4, experiment="E4 sim+fine-tune", data=tag) if r["method"] != "Baseline"]
    c34 += [r for r in cls_rows(lab_test, p4, experiment="E4 sim+fine-tune", data=tag) if r["method"] != "Baseline"]
    e34, c34 = pd.DataFrame(e34), pd.DataFrame(c34)
    e34.to_csv(RESULTS_DIR / "e3_e4_sim_to_lab.csv", index=False)
    c34.to_csv(RESULTS_DIR / "e3_e4_classification.csv", index=False)
    summary.update(e3_e4_data=tag, n_finetune=int(ft_mask.sum()), n_lab_test=int((~ft_mask).sum()))

    # ---------- E5: soft faults ----------
    print("E5 soft faults")
    e5 = []
    for i, g in enumerate((0.01, 0.02, 0.03, 0.05, 0.08, 0.12, 0.2, 0.3)):
        ds = cached(f"test_e5_g{g}_{N(600)}", N(600), cfg, 200 + i, rebuild,
                    classes=["partial"], gamma_abs=g, snr_db=30.0)
        pr = predict(bundle, ds)
        for name, (d, dt, found, c) in method_outputs(ds, pr).items():
            detected = (c != "matched") & found
            e5.append(dict(experiment="E5", gamma_abs=g, method=name, detection_rate=float(detected.mean()),
                           **reg_metrics(ds["meta"], d, dt, detected)))
    e5 = pd.DataFrame(e5)
    e5.to_csv(RESULTS_DIR / "e5_soft_faults.csv", index=False)

    # ---------- E6: Method A vs B ----------
    e6 = (e1[e1.method != "Baseline"]
          .assign(input=lambda x: x.method.str.split("-").str[1], family=lambda x: x.method.str.split("-").str[0])
          .groupby(["family", "input"])[["MAE_m_on_base_detected", "MAE_m", "F1"]].mean().reset_index())
    acc = cls_tab[cls_tab.method != "Baseline"].assign(input=lambda x: x.method.str.split("-").str[1],
                                                      family=lambda x: x.method.str.split("-").str[0])
    e6 = e6.merge(acc[["family", "input", "accuracy"]], on=["family", "input"], how="left")
    e6.to_csv(RESULTS_DIR / "e6_method_a_vs_b.csv", index=False)

    # ---------- figures ----------
    print("Figures")
    best_ml = mixed[mixed.method != "Baseline"].sort_values("MAE_m_on_base_detected").iloc[0]["method"]
    best_cls = cls_tab[cls_tab.method != "Baseline"].sort_values("F1").iloc[-1]["method"]
    fig_error_vs_snr(e1)
    fig_pred_vs_true(test, pt, best_ml)
    fig_error_vs_distance(test, pt)
    fig_confusion(test, pt, best_cls)
    fig_e2(e2)
    fig_e5(e5)
    fig_e3e4(e34, tag)
    fig_importance(bundle)
    fig_e6(e6)
    fig_overlay(cfg, lab if not proxy else None)

    summary.update({"best_regressor": best_ml, "best_classifier": best_cls, "plot_keys": PLOT_KEYS,
                    "runtime_s": round(time.time() - t_start)})
    write_summary(summary, mixed, cls_tab, e1, e2, e34, c34, e5, e6)
    print(f"Done in {time.time() - t_start:.0f}s -> {RESULTS_DIR}")
    return summary


# ---------------------------------------------------------------- figures
def _save(fig, name):
    fig.tight_layout()
    fig.savefig(FIG_DIR / name, dpi=150)
    plt.close(fig)


def fig_error_vs_snr(e1):
    fig, ax = plt.subplots(1, 3, figsize=(16, 4.6))
    for m in PLOT_KEYS:
        s = e1[e1.method == m].sort_values("snr_db")
        ax[0].plot(s.snr_db, s.MAE_m_on_base_detected, label=label(m), **style(m))
        ax[1].plot(s.snr_db, s.coverage * 100, label=label(m), **style(m))
        if m != "Baseline":
            ax[2].plot(s.snr_db, s.MAE_m, label=label(m), **style(m))
    ax[0].set(title="1. Distance error vs SNR (same traces for all)", xlabel="SNR (dB)",
              ylabel="MAE (m) on faults the baseline located")
    ax[1].set(title="Faults given a distance (%)", xlabel="SNR (dB)", ylabel="share of faulty traces (%)",
              ylim=(0, 105))
    ax[2].set(title="ML error on all faulty traces", xlabel="SNR (dB)", ylabel="MAE (m)")
    for a in (ax[0], ax[2]):
        a.set_ylim(bottom=0)
    ax[0].legend(fontsize=8)
    _save(fig, "fig1_error_vs_snr.png")


def fig_pred_vs_true(test, pt, best):
    outs = method_outputs(test, pt)
    meta = test["meta"]
    fault = meta.has_fault.to_numpy(bool)
    fig, ax = plt.subplots(1, 2, figsize=(10, 4.6), sharey=True)
    for a, name in zip(ax, ["Baseline", best]):
        d, _, found, _ = outs[name]
        m = fault & found
        a.scatter(meta.d[m], d[m], s=8, alpha=0.35, color=style(name)["color"], edgecolors="none")
        lim = (0, float(meta.d.max()) * 1.05)
        a.plot(lim, lim, color=INK2, lw=1, ls=":")
        r = reg_metrics(meta, d, outs[name][1], found)
        a.set(title=f"2. {label(name)}", xlabel="true distance (m)", xlim=lim, ylim=lim)
        a.text(0.03, 0.95, f"MAE {r['MAE_m']:.2f} m   RMSE {r['RMSE_m']:.2f} m\nn = {r['n']}",
               transform=a.transAxes, va="top", fontsize=9, color=INK)
    ax[0].set_ylabel("predicted distance (m)")
    _save(fig, "fig2_pred_vs_true.png")


def fig_error_vs_distance(test, pt):
    outs = method_outputs(test, pt)
    meta = test["meta"]
    bins = np.arange(0.5, 21, 1.5)
    fig, ax = plt.subplots(figsize=(8, 4.4))
    for name in PLOT_KEYS:
        d, dt, found, _ = outs[name]
        m = meta.has_fault.to_numpy(bool) & found & outs["Baseline"][2]
        err = np.abs(d - meta.d.to_numpy())
        idx = np.digitize(meta.d.to_numpy(), bins)
        mae = [np.nanmean(err[m & (idx == k)]) if (m & (idx == k)).sum() > 5 else np.nan for k in range(1, len(bins))]
        ax.plot(0.5 * (bins[1:] + bins[:-1]), mae, label=label(name), **style(name))
    ax.set(title="3. Distance error vs fault distance (faults the baseline located)",
           xlabel="true distance (m)", ylabel="MAE (m)")
    ax.set_ylim(bottom=0)
    ax.legend(fontsize=8)
    _save(fig, "fig3_error_vs_distance.png")


def fig_confusion(test, pt, best):
    outs = method_outputs(test, pt)
    y = test["meta"].cls.astype(str).to_numpy()
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list("seq", SEQ)
    fig, ax = plt.subplots(1, 2, figsize=(10.5, 4.4))
    for a, name in zip(ax, ["Baseline", best]):
        cm = confusion_matrix(y, outs[name][3], labels=CLASSES)
        cmn = cm / cm.sum(1, keepdims=True)
        a.imshow(cmn, cmap=cmap, vmin=0, vmax=1)
        a.grid(False)
        for i in range(4):
            for j in range(4):
                a.text(j, i, f"{cm[i, j]}\n{cmn[i, j]:.0%}", ha="center", va="center", fontsize=8,
                       color="white" if cmn[i, j] > 0.55 else INK)
        a.set_xticks(range(4), CLASSES)
        a.set_yticks(range(4), CLASSES)
        acc = (outs[name][3] == y).mean()
        a.set(title=f"4. {label(name)}  (acc {acc:.1%})", xlabel="predicted", ylabel="true")
    _save(fig, "fig4_confusion_matrix.png")


def _bars(ax, groups, keys, value_of, width=0.8):
    x = np.arange(len(groups))
    w = width / len(keys)
    for k, m in enumerate(keys):
        st = style(m)
        ax.bar(x + (k - (len(keys) - 1) / 2) * w, [value_of(m, g) for g in groups], w * 0.92,
               color=st["color"], hatch="//" if st["ls"] == "--" else None, edgecolor=SURF, label=label(m))
    ax.set_xticks(x, groups)


def fig_e2(e2):
    fig, ax = plt.subplots(figsize=(10, 4.4))
    bands = list(dict.fromkeys(e2.band))
    t = e2.set_index(["method", "band"]).MAE_m
    _bars(ax, bands, PLOT_KEYS, lambda m, g: t.get((m, g), np.nan))
    ax.set(title="E2. Held-out distances (train: 0.5-4 m and 6-14 m)", ylabel="MAE (m)")
    ax.legend(fontsize=8)
    _save(fig, "fig6_e2_heldout.png")


def fig_e5(e5):
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.4))
    for m in PLOT_KEYS:
        s = e5[e5.method == m].sort_values("gamma_abs")
        ax[0].plot(s.gamma_abs, s.detection_rate * 100, label=label(m), **style(m))
        s2 = s[s.n >= 20]   # MAE of a handful of lucky detections is noise, not a result
        ax[1].plot(s2.gamma_abs, s2.MAE_m, label=label(m), **style(m))
    for a in ax:
        a.set_xscale("log")
        a.set_xlabel("|Gamma| of the fault")
    ax[0].set(title="E5. Soft faults detected (%) at 30 dB", ylabel="detected as a fault (%)", ylim=(0, 105))
    ax[1].set(title="Distance error on detected soft faults (>= 20 detected)", ylabel="MAE (m)")
    ax[1].set_ylim(bottom=0)
    ax[0].legend(fontsize=8)
    _save(fig, "fig7_e5_soft_faults.png")


def fig_e3e4(e34, tag):
    fig, ax = plt.subplots(figsize=(12, 4.4))
    x = np.arange(len(METHODS_ALL))
    for k, (g, col) in enumerate((("E3 sim->lab", BLUE), ("E4 sim+fine-tune", ORANGE))):
        s = e34[e34.experiment == g].set_index("method").reindex(METHODS_ALL)
        ax.bar(x + (k - 0.5) * 0.38, s.MAE_m_on_base_detected, 0.35, color=col, edgecolor=SURF, label=g)
    ax.set_xticks(x, METHODS_ALL, rotation=30, ha="right")
    ax.set(title=f"E3/E4. Sim-to-lab gap on {tag} data (faults the baseline located)", ylabel="MAE (m)")
    ax.legend(fontsize=8)
    _save(fig, "fig8_e3_e4_sim_to_lab.png")


def fig_importance(bundle):
    imp = bundle.get("importances_B", {}).get("ET")
    if not imp:
        return
    imp = pd.Series(imp).sort_values()
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.barh(imp.index, imp.values, color=FAM_COLOR["ET"], edgecolor=SURF)
    ax.set(title="Method B feature importance (Extra Trees, distance)", xlabel="importance")
    ax.grid(axis="y", visible=False)
    _save(fig, "fig9_feature_importance.png")


def fig_e6(e6):
    fams = [f for f in FAMILIES if f in set(e6.family)]
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.2))
    x = np.arange(len(fams))
    inputs = (("A", BLUE, "raw samples (A)", "o"), ("B", ORANGE, "features (B)", "D"))
    t = e6.set_index(["family", "input"])["MAE_m_on_base_detected"]
    for k, (inp, c, nm, _) in enumerate(inputs):      # bars: zero baseline
        ax[0].bar(x + (k - 0.5) * 0.38, [t.get((f, inp), np.nan) for f in fams], 0.35, color=c,
                  edgecolor=SURF, label=nm)
    ax[0].set(title="E6. Distance error by input", ylabel="MAE (m), E1 average")
    t = e6.set_index(["family", "input"])["F1"]
    for k, (inp, c, nm, mk) in enumerate(inputs):      # dots: F1 differences are small, axis need not start at 0
        ax[1].plot(x + (k - 0.5) * 0.2, [t.get((f, inp), np.nan) for f in fams], ls="none", marker=mk,
                   markersize=9, color=c, label=nm)
    ax[1].set(title="E6. Classification by input", ylabel="macro F1, E1 average")
    for a in ax:
        a.set_xticks(x, [FAMILY_NAME[f] for f in fams], rotation=15)
    ax[0].legend(fontsize=8)
    _save(fig, "fig10_e6_method_a_vs_b.png")


def fig_overlay(cfg, lab):
    """Figure 5: simulated vs measured trace. Until lab data exists it shows the
    brief's simple model, the full transmission-line model and the proxy-lab
    version of the same 5 m open cable."""
    from .preprocess import preprocess
    from .sim_tdr import make_params, simulate
    fig, ax = plt.subplots(figsize=(8.5, 4.4))
    if lab is not None and lab.get("raw"):
        from .fit_sim import fit_trace
        i = int(np.argmax(lab["meta"].cls.eq("open").to_numpy()))
        t, v = lab["raw"][i]
        res = fit_trace(t, v, lab["meta"].iloc[i])
        ax.plot(res["t"] * 1e9, res["v_meas"], color=GRAY, lw=2, label="measured")
        ax.plot(res["t"] * 1e9, res["v_fit"], color=BLUE, lw=2, ls="--", label="fitted simulation")
        ax.set_title("5. Simulated vs measured trace")
    else:
        for kw, lab_, st in ((dict(), "transmission-line model", dict(color=BLUE, ls="-")),
                             (dict(model="simple"), "brief's simple model", dict(color=GRAY, ls=":")),
                             (dict(artifacts=True), "with lab artifacts (proxy)", dict(color=ORANGE, ls="--"))):
            c = SimConfig(model=kw.get("model", "tline"))
            p = make_params(c, cls="open", d=5.0, rise=4e-9, snr_db=60, ts=0.5e-9,
                            artifacts=kw.get("artifacts", False))
            p["model"][:] = c.model
            (t, v), = simulate(p, c, noiseless=True)
            pr = preprocess(t, v, v_inc=p["v_inc"][0])
            ax.plot(pr.t * 1e9, pr.v, lw=2, label=lab_, **st)
        ax.set_title("5. Simulated traces, 5 m RG-58 open (no lab data yet)")
    ax.set(xlabel="time after incident edge (ns)", ylabel="V / V_inc", xlim=(-15, 90))
    ax.legend(fontsize=8)
    _save(fig, "fig5_sim_vs_lab_overlay.png")


# ---------------------------------------------------------------- summary
def write_summary(s, mixed, cls_tab, e1, e2, e34, c34, e5, e6):
    show = ["method", "n", "coverage", "MAE_m", "RMSE_m", "MedAE_m", "MAE_pct_L", "MAE_dt_ns", "MAE_m_on_base_detected"]
    piv = lambda df, idx, val: df.pivot(index=idx, columns="method", values=val)[METHODS_ALL].reset_index()
    txt = [f"# Results summary\n\nGenerated {s['created']}{' (quick run)' if s['quick'] else ''}. "
           f"Models: {', '.join(s['models'])}. Best regressor (fair MAE): **{s['best_regressor']}**, "
           f"best classifier: **{s['best_classifier']}**.\n",
           "## Mixed test set (SNR 10-40 dB, all fault types)\n", md_table(mixed[show]),
           "\n\n## Classification (mixed test set)\n", md_table(cls_tab[["method", "accuracy", "precision", "recall", "F1"]]),
           "\n\n## E1: MAE (m) vs SNR, same traces for every method (faults the baseline located)\n",
           md_table(piv(e1, "snr_db", "MAE_m_on_base_detected")),
           "\n\n## E1: MAE (m) vs SNR, each method on every trace it gave a distance for\n",
           md_table(piv(e1, "snr_db", "MAE_m")),
           "\n\n## E1: share of faulty traces given a distance\n", md_table(piv(e1, "snr_db", "coverage")),
           "\n\n## E2: held-out distances, MAE (m)\n", md_table(piv(e2, "band", "MAE_m")),
           f"\n\n## E3/E4: sim-to-lab ({s['e3_e4_data']}; fine-tune n={s['n_finetune']}, test n={s['n_lab_test']})\n",
           md_table(e34[["experiment", "method", "coverage", "MAE_m", "RMSE_m", "MAE_m_on_base_detected"]]),
           "\n\n", md_table(c34[["experiment", "method", "accuracy", "F1"]]),
           "\n\n## E5: soft faults at 30 dB (detection rate)\n", md_table(piv(e5, "gamma_abs", "detection_rate")),
           "\n\n## E6: Method A (raw) vs Method B (features), averaged over the E1 SNR sweep\n", md_table(e6),
           "\n"]
    (RESULTS_DIR / "summary.md").write_text("\n".join(txt), encoding="utf-8")
    (RESULTS_DIR / "summary.json").write_text(json.dumps(s, indent=2), encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--quick", action="store_true", help="smaller test sets")
    ap.add_argument("--rebuild", action="store_true", help="re-simulate cached test sets")
    ap.add_argument("--bundle", type=Path, default=None, help="model bundle (default models/tdr_models.joblib)")
    a = ap.parse_args(argv)
    run(a.quick, a.rebuild, a.bundle)


if __name__ == "__main__":
    main()
