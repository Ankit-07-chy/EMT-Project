"""In-depth performance analysis of localization and detection: ``python index.py analyze``.

Uses the trained bundle and the *same* cached test sets as ``evaluate`` (run that
first), so every number here is measured on held-out simulated traces:

Localization (distance regression)
    error distribution per model (MAE, RMSE, median, P90/P95/P99, worst case,
    bias, share within 0.1 / 0.25 / 0.5 / 1 m), and MAE / P95 broken down by
    fault type, distance, SNR, system rise time and |Gamma|; the 15 worst
    predictions of the best model with their conditions.
Detection (fault present? which class?)
    binary fault detection (TP/FP/FN/TN, precision, recall, F1, false-alarm and
    miss rates), per-class precision / recall / F1, confusion matrices, misses
    by |Gamma| and SNR, detection vs SNR on the E1 sets.
Speed
    front-end and per-model inference latency (single trace and batched),
    model size and parameter counts.

Outputs: report/results/analysis_*.csv, report/results/ml_analysis_summary.md,
report/figures/a1..a6_*.png.
"""
from __future__ import annotations

import argparse
import io
import json
import time

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.metrics import confusion_matrix, precision_recall_fscore_support  # noqa: E402

from . import evaluate as E  # noqa: E402
from .config import CLASSES, FIG_DIR, KIND_NAMES, RESULTS_DIR, sim_config_from_calibration  # noqa: E402
from .models import set_threads  # noqa: E402
from .train import DEFAULT_BUNDLE, inputs, load_bundle, predict, valid  # noqa: E402

KIND_LABEL = {"end": "end of cable", "series_R": "series resistor", "shunt_R": "shunt resistor",
              "impedance_step": "impedance step", "open_stub": "open stub"}


# ---------------------------------------------------------------- helpers
def fault_type(meta: pd.DataFrame) -> np.ndarray:
    kind = meta["kind"].map(KIND_NAMES).fillna("end").to_numpy()
    cls = meta["cls"].astype(str).to_numpy()
    out = np.where(kind == "end", np.char.add("end: ", cls.astype(str)), [KIND_LABEL.get(k, k) for k in kind])
    return out


def loc_stats(err: np.ndarray, n_faults: int) -> dict:
    a = np.abs(err)
    if a.size == 0:
        return dict(n=0, coverage=0.0)
    return dict(n=int(a.size), coverage=a.size / max(n_faults, 1), MAE_m=a.mean(), RMSE_m=np.sqrt(np.mean(err ** 2)),
                MedAE_m=np.median(a), P90_m=np.percentile(a, 90), P95_m=np.percentile(a, 95),
                P99_m=np.percentile(a, 99), max_m=a.max(), bias_m=err.mean(),
                within_0_1m=np.mean(a <= 0.1), within_0_25m=np.mean(a <= 0.25),
                within_0_5m=np.mean(a <= 0.5), within_1m=np.mean(a <= 1.0), gross_gt_1m=np.mean(a > 1.0))


def binary_detection(y_cls: np.ndarray, p_cls: np.ndarray, found: np.ndarray) -> dict:
    fault = y_cls != "matched"
    det = (p_cls != "matched") & (p_cls != "invalid") & found
    tp, fp = int(np.sum(det & fault)), int(np.sum(det & ~fault))
    fn, tn = int(np.sum(~det & fault)), int(np.sum(~det & ~fault))
    prec = tp / max(tp + fp, 1)
    rec = tp / max(tp + fn, 1)
    return dict(TP=tp, FP=fp, FN=fn, TN=tn, precision=prec, recall=rec,
                F1=2 * prec * rec / max(prec + rec, 1e-12), false_alarm_rate=fp / max(fp + tn, 1),
                miss_rate=fn / max(fn + tp, 1), accuracy=(tp + tn) / len(y_cls))


def band(values, edges, labels):
    return pd.cut(values, edges, labels=labels, include_lowest=True, right=False)


def model_size(m) -> dict:
    buf = io.BytesIO()
    joblib.dump(m, buf, compress=3)
    out = {"size_MB": buf.tell() / 1e6}
    core = getattr(m, "regressor_", m)            # TransformedTargetRegressor (MLP regression)
    est = getattr(core, "steps", None)
    core = est[-1][1] if est else core
    if hasattr(core, "estimators_"):
        out["detail"] = f"{len(core.estimators_)} trees, {sum(t.tree_.node_count for t in core.estimators_):,} nodes"
    elif hasattr(core, "coefs_"):
        out["detail"] = f"{sum(w.size + b.size for w, b in zip(core.coefs_, core.intercepts_)):,} weights, layers {core.hidden_layer_sizes}"
    elif hasattr(core, "n_samples_fit_"):
        out["detail"] = f"stores {core.n_samples_fit_:,} training traces, k = {core.n_neighbors}"
    elif getattr(core, "net_", None) is not None:
        out["detail"] = f"{sum(p.numel() for p in core.net_.parameters()):,} weights (1-D CNN)"
    return out


# ---------------------------------------------------------------- analysis
def run(bundle_path=None, quick: bool = False):
    E._style()
    bundle = load_bundle(bundle_path or DEFAULT_BUNDLE)
    E.set_keys(bundle)
    cfg = sim_config_from_calibration()
    scale = 0.35 if quick else 1.0
    N = lambda k: max(150, int(k * scale))  # noqa: E731 (same sizes as evaluate)
    test = E.cached(f"test_mixed_{N(6000)}", N(6000), cfg, 3)
    pt = predict(bundle, test)
    meta = test["meta"]
    outs = E.method_outputs(test, pt)
    fault = meta["has_fault"].to_numpy(bool)
    d_true = meta["d"].to_numpy(float)
    y_cls = meta["cls"].astype(str).to_numpy()
    base_found = outs["Baseline"][2]
    summary = {"n_test": int(len(meta)), "n_faults": int(fault.sum())}

    # ---- localization: overall
    rows = []
    for name, (d, _, found, _) in outs.items():
        m = fault & found & np.isfinite(d)
        _errors_cache[name] = np.abs(d[m] - d_true[m])
        rows.append(dict(method=name, subset="every trace it gave a distance for", **loc_stats(d[m] - d_true[m], fault.sum())))
        mf = m & base_found
        rows.append(dict(method=name, subset="faults the baseline located (fair)", **loc_stats(d[mf] - d_true[mf], (fault & base_found).sum())))
    loc = pd.DataFrame(rows)
    loc.to_csv(RESULTS_DIR / "analysis_localization.csv", index=False)
    fair = loc[loc.subset.str.startswith("faults")]
    best_reg = fair[fair.method != "Baseline"].sort_values("MAE_m").iloc[0]["method"]
    summary["best_regressor"] = best_reg

    # ---- localization: breakdowns
    ftype = fault_type(meta)
    gabs = np.abs(meta["gamma_true"].to_numpy(float))
    factors = {
        "fault type": ftype,
        "distance (m)": band(d_true, [0.5, 2, 5, 10, 15, 20.01], ["0.5-2", "2-5", "5-10", "10-15", "15-20"]),
        "SNR (dB)": band(meta["snr_db"].to_numpy(float), [10, 15, 20, 30, 40.01], ["10-15", "15-20", "20-30", "30-40"]),
        "rise time (ns)": band(meta["rise"].to_numpy(float) * 1e9, [2, 4, 6, 8, 10.01], ["2-4", "4-6", "6-8", "8-10"]),
        "|Gamma|": band(gabs, [0, 0.1, 0.3, 0.6, 1.01], ["<0.1", "0.1-0.3", "0.3-0.6", ">=0.6"]),
    }
    br = []
    for fname, groups in factors.items():
        g = pd.Series(groups).astype(str).to_numpy()
        for level in pd.unique(g[fault]):
            sel = fault & (g == level)
            for name, (d, _, found, _) in outs.items():
                m = sel & found & np.isfinite(d)
                a = np.abs(d[m] - d_true[m])
                af = np.abs(d[m & base_found] - d_true[m & base_found])
                br.append(dict(factor=fname, level=level, method=name, n_faults=int(sel.sum()), coverage=m.sum() / max(sel.sum(), 1),
                               baseline_coverage=(sel & base_found).sum() / max(sel.sum(), 1),
                               MAE_m=a.mean() if a.size else np.nan, P95_m=np.percentile(a, 95) if a.size else np.nan,
                               MAE_fair_m=af.mean() if af.size else np.nan))
    br = pd.DataFrame(br)
    br.to_csv(RESULTS_DIR / "analysis_localization_breakdown.csv", index=False)

    # ---- worst cases of the best model
    d_b = outs[best_reg][0]
    m = fault & np.isfinite(d_b)
    err = np.where(m, d_b - d_true, np.nan)
    worst_idx = np.argsort(-np.nan_to_num(np.abs(err), nan=-1))[:15]
    worst = pd.DataFrame({"true_d_m": d_true[worst_idx], "pred_d_m": d_b[worst_idx], "error_m": err[worst_idx],
                          "fault": ftype[worst_idx], "gamma_true": meta["gamma_true"].to_numpy()[worst_idx],
                          "snr_db": meta["snr_db"].to_numpy()[worst_idx], "rise_ns": meta["rise"].to_numpy()[worst_idx] * 1e9,
                          "baseline_d_m": outs["Baseline"][0][worst_idx], "baseline_found": base_found[worst_idx]})
    worst.to_csv(RESULTS_DIR / "analysis_worst_cases.csv", index=False)

    # ---- detection
    det_rows, cls_rows, cms = [], [], {}
    for name, (_, _, found, c) in outs.items():
        if c is None:
            continue
        det_rows.append(dict(method=name, **binary_detection(y_cls, c, found if name == "Baseline" else np.ones_like(found))))
        p, r, f, s = precision_recall_fscore_support(y_cls, c, labels=CLASSES, zero_division=0)
        for k, lab in enumerate(CLASSES):
            cls_rows.append(dict(method=name, cls=lab, precision=p[k], recall=r[k], F1=f[k], support=int(s[k])))
        cms[name] = confusion_matrix(y_cls, c, labels=CLASSES)
    det = pd.DataFrame(det_rows)
    det.to_csv(RESULTS_DIR / "analysis_detection_binary.csv", index=False)
    per_cls = pd.DataFrame(cls_rows)
    per_cls.to_csv(RESULTS_DIR / "analysis_detection_per_class.csv", index=False)
    macro = per_cls.groupby("method").F1.mean()
    best_cls = macro.drop("Baseline").idxmax()
    summary["best_classifier"] = best_cls
    cm_rows = []
    for name, cm in cms.items():
        for i, t in enumerate(CLASSES):
            cm_rows.append(dict(method=name, true=t, **{f"pred_{p}": int(cm[i, j]) for j, p in enumerate(CLASSES)}))
    pd.DataFrame(cm_rows).to_csv(RESULTS_DIR / "analysis_confusion_matrices.csv", index=False)

    # misses (false negatives) by |Gamma| and SNR, false alarms by SNR
    fn_rows = []
    for name in ("Baseline", best_cls):
        _, _, found, c = outs[name]
        det_ = (c != "matched") & (c != "invalid") & (found if name == "Baseline" else True)
        for fname in ("|Gamma|", "SNR (dB)"):
            g = pd.Series(factors[fname]).astype(str).to_numpy()
            for level in sorted(pd.unique(g[fault])):
                sel = fault & (g == level)
                fn_rows.append(dict(method=name, kind="miss rate (fault called matched)", factor=fname, level=level,
                                    n=int(sel.sum()), rate=float(np.mean(~det_[sel]))))
        g = pd.Series(factors["SNR (dB)"]).astype(str).to_numpy()
        for level in sorted(pd.unique(g[~fault])):
            sel = ~fault & (g == level)
            fn_rows.append(dict(method=name, kind="false-alarm rate (matched called fault)", factor="SNR (dB)", level=level,
                                n=int(sel.sum()), rate=float(np.mean(det_[sel]))))
    fnfp = pd.DataFrame(fn_rows)
    fnfp.to_csv(RESULTS_DIR / "analysis_fn_fp.csv", index=False)

    # detection vs SNR on the E1 sets
    dsnr = []
    for snr in (10, 15, 20, 25, 30, 35, 40):
        ds = E.cached(f"test_e1_snr{snr}_{N(1200)}", N(1200), cfg, 100 + snr, snr_db=snr)
        o = E.method_outputs(ds, predict(bundle, ds))
        y = ds["meta"]["cls"].astype(str).to_numpy()
        for name, (_, _, found, c) in o.items():
            if c is not None:
                dsnr.append(dict(snr_db=snr, method=name, **binary_detection(y, c, found if name == "Baseline" else np.ones_like(found))))
    dsnr = pd.DataFrame(dsnr)
    dsnr.to_csv(RESULTS_DIR / "analysis_detection_vs_snr.csv", index=False)

    # ---- latency and size
    lat = latency(bundle, cfg)
    lat.to_csv(RESULTS_DIR / "analysis_latency.csv", index=False)

    # ---- configuration
    vt = bundle["val_table"]
    sel = vt[vt.metric == "SELECTED"][["task", "method", "algo", "params", "val_score"]].copy()
    sel["key"] = sel.algo + "-" + sel.method
    sizes = {f"{a}-{m}|{t}": model_size(mdl) for (t, m, a), mdl in bundle["models"].items()}
    sel["size_MB"] = [sizes[f"{k}|{t}"]["size_MB"] for k, t in zip(sel.key, sel.task)]
    sel["detail"] = [sizes[f"{k}|{t}"].get("detail", "") for k, t in zip(sel.key, sel.task)]
    sel.to_csv(RESULTS_DIR / "analysis_model_config.csv", index=False)

    figures(loc, br, det, dsnr, cms, lat, best_reg, best_cls)
    write_md(summary, loc, br, worst, det, per_cls, fnfp, dsnr, lat, sel, best_reg, best_cls, bundle)
    (RESULTS_DIR / "analysis_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Saved analysis tables and figures (best regressor {best_reg}, best classifier {best_cls})")


def latency(bundle, cfg, n=300) -> pd.DataFrame:
    from .features import process_traces
    from .sim_tdr import sample_params, simulate
    rng = np.random.default_rng(11)
    p = sample_params(n, cfg, rng)
    tr = simulate(p, cfg)
    t0 = time.perf_counter()
    X, F, B = process_traces(tr, p["v_inc_ref"], vp=cfg.vp_nominal, preset=cfg.preset)
    front = (time.perf_counter() - t0) / n * 1e3
    ds = {"X": X, "F": F, "B": B}
    rows = [dict(stage="front end: preprocess + baseline + 23 features", model="(all)", task="-",
                 single_ms=front, batch_ms_per_trace=front)]
    for (task, m_, a), mdl in bundle["models"].items():
        Xi = inputs(ds, m_)
        f = mdl.predict if task == "reg" else mdl.predict_proba
        f(Xi[:2])
        t0 = time.perf_counter()
        f(Xi)
        batch = (time.perf_counter() - t0) / len(Xi) * 1e3
        set_threads(mdl, 1)              # single trace: as the dashboard runs it
        f(Xi[:1])
        t0 = time.perf_counter()
        for i in range(40):
            f(Xi[i:i + 1])
        single = (time.perf_counter() - t0) / 40 * 1e3
        set_threads(mdl, -1)
        rows.append(dict(stage="model", model=f"{a}-{m_}", task="distance" if task == "reg" else "class",
                         single_ms=single, batch_ms_per_trace=batch))
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- figures
def _save(fig, name):
    fig.tight_layout()
    fig.savefig(FIG_DIR / name, dpi=150)
    plt.close(fig)


def figures(loc, br, det, dsnr, cms, lat, best_reg, best_cls):
    # best input per family from the localization table (same rule as evaluate)
    fair = loc[loc.subset.str.startswith("faults")]
    ml = fair[fair.method != "Baseline"].assign(fam=lambda x: x.method.str.split("-").str[0])
    keys = ["Baseline"] + list(ml.sort_values("MAE_m").groupby("fam").head(1).sort_values("fam", key=lambda s: s.map(
        {f: i for i, f in enumerate(E.FAMILIES)})).method)

    # a1: CDF of absolute error, each method on the traces it located
    fig, ax = plt.subplots(figsize=(7.5, 4.6))
    from .evaluate import label, style
    test_errs = _errors_cache
    for k in keys:
        a = np.sort(test_errs[k])
        st = style(k)
        cov = loc[(loc.method == k) & ~loc.subset.str.startswith("faults")].coverage.iloc[0]
        ax.plot(a, np.arange(1, a.size + 1) / a.size, color=st["color"], ls=st["ls"], lw=2,
                label=f"{label(k)} (gives a distance for {cov:.0%})")
    ax.set(xlim=(0, 1.5), ylim=(0, 1.01), xlabel="absolute distance error (m)",
           ylabel="share of located faults with error ≤ x", title="Localization error distribution (mixed test set)")
    ax.legend(fontsize=7.5, loc="lower right")
    _save(fig, "a1_error_cdf.png")

    # a2: MAE by fault type (dot plot)
    sub = br[br.factor == "fault type"]
    levels = sorted(sub.level.unique())
    cov = sub[sub.method == "Baseline"].set_index("level").reindex(levels).baseline_coverage
    fig, ax = plt.subplots(figsize=(8, 4.4))
    for j, k in enumerate(keys):
        s = sub[sub.method == k].set_index("level").reindex(levels)
        st = style(k)
        ax.scatter(s.MAE_fair_m, np.arange(len(levels)) + (j - len(keys) / 2) * 0.1, color=st["color"], marker=st["marker"],
                   s=42, label=label(k), zorder=3, edgecolor="white", linewidth=0.6)
    ax.set_yticks(range(len(levels)), [f"{lv}\n(baseline finds {c:.0%})" for lv, c in zip(levels, cov)], fontsize=8)
    ax.set(xlabel="MAE (m) on the faults the baseline located (same traces for every method)",
           title="Localization error by fault type")
    ax.legend(fontsize=7, loc="lower right")
    _save(fig, "a2_mae_by_fault_type.png")

    # a3: MAE vs rise time and vs |Gamma| (small multiples, same y-unit)
    fig, axs = plt.subplots(1, 2, figsize=(10, 4.2), sharey=True)
    for ax, fac, xl in ((axs[0], "rise time (ns)", "system rise time (ns)"), (axs[1], "|Gamma|", "|Γ| of the fault")):
        sub = br[br.factor == fac]
        lv = [x for x in factors_order[fac] if x in set(sub.level)]
        cov = sub[sub.method == "Baseline"].set_index("level").reindex(lv).baseline_coverage
        for k in keys:
            s = sub[sub.method == k].set_index("level").reindex(lv)
            st = style(k)
            ax.plot(range(len(lv)), s.MAE_fair_m, color=st["color"], ls=st["ls"], marker=st["marker"], label=label(k))
        ax.set_xticks(range(len(lv)), [f"{x}\nbaseline {c:.0%}" for x, c in zip(lv, cov)], fontsize=8)
        ax.set(xlabel=xl, title=f"MAE vs {xl.split(' (')[0]}")
    axs[0].set_ylabel("MAE (m), faults the baseline located")
    axs[1].legend(fontsize=7)
    _save(fig, "a3_mae_vs_rise_and_gamma.png")

    # a4: detection vs SNR (small multiples: misses, false alarms)
    fig, axs = plt.subplots(1, 2, figsize=(10, 4.2), sharey=False)
    for k in keys:
        s = dsnr[dsnr.method == k].sort_values("snr_db")
        st = style(k)
        axs[0].plot(s.snr_db, s.miss_rate * 100, color=st["color"], ls=st["ls"], marker=st["marker"], label=label(k))
        axs[1].plot(s.snr_db, s.false_alarm_rate * 100, color=st["color"], ls=st["ls"], marker=st["marker"])
    axs[0].set(xlabel="SNR (dB)", ylabel="missed faults (%)", title="Missed faults vs SNR")
    axs[1].set(xlabel="SNR (dB)", ylabel="false alarms on matched lines (%)", title="False alarms vs SNR")
    axs[0].legend(fontsize=7)
    _save(fig, "a4_detection_vs_snr.png")

    # a5: confusion matrices, baseline vs best classifier (row-normalised)
    fig, axs = plt.subplots(1, 2, figsize=(9.5, 4.2))
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list("seq", E.SEQ)
    for ax, k in zip(axs, ("Baseline", best_cls)):
        cm = cms[k].astype(float)
        cn = cm / cm.sum(1, keepdims=True)
        ax.imshow(cn, cmap=cmap, vmin=0, vmax=1)
        for i in range(4):
            for j in range(4):
                ax.text(j, i, f"{cn[i, j]:.0%}\n({int(cm[i, j])})", ha="center", va="center", fontsize=8,
                        color="white" if cn[i, j] > 0.6 else E.INK)
        ax.set_xticks(range(4), CLASSES)
        ax.set_yticks(range(4), CLASSES)
        ax.set(xlabel="predicted", ylabel="true", title=label(k))
        ax.grid(False)
    _save(fig, "a5_confusion_baseline_vs_best.png")

    # a6: latency per model (single trace), log scale
    mod = lat[lat.stage == "model"].copy()
    mod["fam"] = mod.model.str.split("-").str[0]
    mod = mod.sort_values("single_ms")
    fig, ax = plt.subplots(figsize=(7.5, 5))
    ylab = [f"{m}  {t}" for m, t in zip(mod.model, mod.task)]
    for i, (_, r) in enumerate(mod.iterrows()):
        st = style(r.model)
        ax.hlines(i, 1e-3, r.single_ms, color=st["color"], lw=2, ls=st["ls"])
        ax.scatter(r.single_ms, i, color=st["color"], marker=st["marker"], s=40, zorder=3)
    front = lat[lat.stage != "model"].single_ms.iloc[0]
    ax.axvline(front, color=E.GRAY, ls=":", lw=1.5)
    ax.text(front * 1.08, len(mod) - 0.6, f"front end {front:.1f} ms", color=E.INK2, fontsize=8)
    ax.set_xscale("log")
    ax.set_yticks(range(len(mod)), ylab, fontsize=8)
    ax.set(xlabel="time for one trace (ms, log scale)", title="Inference latency per model (this laptop's CPU)")
    _save(fig, "a6_latency.png")


_errors_cache: dict = {}
factors_order = {"rise time (ns)": ["2-4", "4-6", "6-8", "8-10"], "|Gamma|": ["<0.1", "0.1-0.3", "0.3-0.6", ">=0.6"]}


def write_md(summary, loc, br, worst, det, per_cls, fnfp, dsnr, lat, cfgtab, best_reg, best_cls, bundle):
    f3 = lambda x: f"{x:.3f}" if isinstance(x, (float, np.floating)) and np.isfinite(x) else str(x)  # noqa: E731
    pc = lambda x: f"{x:.1%}"  # noqa: E731

    def table(df, cols, fmt=None):
        fmt = fmt or {}
        out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
        for _, r in df.iterrows():
            out.append("| " + " | ".join(fmt.get(c, f3)(r[c]) for c in cols) + " |")
        return "\n".join(out)

    allm = loc[~loc.subset.str.startswith("faults")]
    fair = loc[loc.subset.str.startswith("faults")]
    txt = [f"# ML / NN analysis tables ({time.strftime('%Y-%m-%d %H:%M')})", "",
           f"Mixed simulated test set: {summary['n_test']} traces, {summary['n_faults']} with a fault "
           f"(SNR 10–40 dB, rise 2–10 ns, 0.5–20 m, all fault types). Bundle trained {bundle.get('created')} on "
           f"{bundle.get('n_train')} traces. Best regressor (fair MAE): **{best_reg}**; best classifier (macro-F1): **{best_cls}**.", "",
           "## Localization: every trace each method gave a distance for", "",
           table(allm, ["method", "n", "coverage", "MAE_m", "RMSE_m", "MedAE_m", "P90_m", "P95_m", "max_m", "bias_m",
                        "within_0_25m", "within_0_5m", "gross_gt_1m"],
                 {"coverage": pc, "within_0_25m": pc, "within_0_5m": pc, "gross_gt_1m": pc, "n": str}), "",
           "## Localization: faults the baseline located (same traces for every method)", "",
           table(fair, ["method", "n", "MAE_m", "MedAE_m", "P95_m", "max_m", "within_0_25m"], {"within_0_25m": pc, "n": str}), ""]
    for fac in ("fault type", "distance (m)", "SNR (dB)", "rise time (ns)", "|Gamma|"):
        sub = br[br.factor == fac]
        cols = ["Baseline"] + [c for c in E.ML_KEYS if c in set(sub.method)]
        cov = sub[sub.method == "Baseline"].set_index("level").baseline_coverage
        for val, what in (("MAE_fair_m", "faults the baseline located (same traces for all)"),
                          ("MAE_m", "every fault each method gave a distance for")):
            piv = sub.pivot_table(index="level", columns="method", values=val)[cols]
            piv.insert(0, "baseline finds", cov.reindex(piv.index).values)
            piv = piv.reset_index()
            txt += [f"### MAE (m) by {fac}: {what}", "",
                    table(piv, ["level", "baseline finds"] + cols, {"baseline finds": pc}), ""]
    txt += [f"## 15 worst predictions of {best_reg}", "",
            table(worst, list(worst.columns), {"baseline_found": str, "fault": str}), "",
            "## Detection: is there a fault? (matched = no fault)", "",
            table(det, ["method", "TP", "FP", "FN", "TN", "precision", "recall", "F1", "false_alarm_rate", "miss_rate", "accuracy"],
                  {c: str for c in ("TP", "FP", "FN", "TN")} | {"false_alarm_rate": pc, "miss_rate": pc}), "",
            "## Detection: per class", ""]
    piv = per_cls.pivot_table(index="method", columns="cls", values="F1").reset_index()
    txt += ["F1 per class:", "", table(piv, ["method"] + CLASSES), ""]
    txt += [f"## Misses and false alarms (Baseline vs {best_cls})", "",
            table(fnfp, ["method", "kind", "factor", "level", "n", "rate"], {"n": str, "rate": pc}), "",
            "## Detection vs SNR (E1 sets)", ""]
    piv = dsnr.pivot_table(index="snr_db", columns="method", values="miss_rate").reset_index()
    txt += ["Miss rate:", "", table(piv, ["snr_db"] + [c for c in piv.columns if c != "snr_db"], {"snr_db": lambda v: f"{v:g}"}), ""]
    piv = dsnr.pivot_table(index="snr_db", columns="method", values="false_alarm_rate").reset_index()
    txt += ["False-alarm rate:", "", table(piv, ["snr_db"] + [c for c in piv.columns if c != "snr_db"], {"snr_db": lambda v: f"{v:g}"}), "",
            "## Latency (ms per trace, this laptop)", "",
            table(lat, ["stage", "model", "task", "single_ms", "batch_ms_per_trace"]), "",
            "## Selected configuration of every model (validation grid search)", "",
            table(cfgtab, ["task", "key", "params", "val_score", "size_MB", "detail"], {"params": str, "detail": str}), ""]
    (RESULTS_DIR / "ml_analysis_summary.md").write_text("\n".join(txt), encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bundle", default=None)
    ap.add_argument("--quick", action="store_true", help="use the quick evaluate test-set sizes")
    a = ap.parse_args(argv)
    run(a.bundle, a.quick)


if __name__ == "__main__":
    main()
