"""Architecture / flow diagrams for the presentation and docs (presentation/diagrams/*.png).

    .venv\\Scripts\\python presentation\\make_diagrams.py

Every box names a real module, file, command or setting of this project.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
OUT = HERE / "diagrams"
OUT.mkdir(exist_ok=True)

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle  # noqa: E402

NAVY, INK, INK2 = "#14213D", "#1B1B1B", "#555B66"
KIND = {"hw": ("#B85C24", "#F9ECE2"), "sw": ("#1F7A8C", "#E2F1F4"), "ml": ("#5E48B8", "#ECE8F8"),
        "data": ("#5F6670", "#F0F1F3"), "out": ("#2E7D32", "#E6F2E7"), "warn": ("#B26A00", "#FFF3DC")}
plt.rcParams.update({"font.family": "DejaVu Sans", "figure.facecolor": "white", "savefig.facecolor": "white"})


def canvas(w=16, h=9, size=(13.33, 7.5)):
    fig, ax = plt.subplots(figsize=size)
    ax.set_xlim(0, w)
    ax.set_ylim(0, h)
    ax.axis("off")
    fig.subplots_adjust(0.005, 0.005, 0.995, 0.995)
    return fig, ax


def box(ax, x, y, w, h, title, body=None, kind="sw", ts=11.5, bs=9, align="center"):
    ec, fc = KIND[kind]
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.0,rounding_size=0.14", fc=fc, ec=ec, lw=1.7, zorder=2))
    if body is None:  # title-only box: centre the title
        ax.text(x + w / 2, y + h / 2, title, ha="center", va="center", fontsize=ts, fontweight="bold", color=ec, zorder=3)
    else:
        ax.text(x + w / 2, y + h - 0.16, title, ha="center", va="top", fontsize=ts, fontweight="bold", color=ec, zorder=3)
    if body:
        if align == "left":
            ax.text(x + 0.15, y + h - 0.55, body, ha="left", va="top", fontsize=bs, color=INK, zorder=3, linespacing=1.35)
        else:
            ax.text(x + w / 2, y + h - 0.55, body, ha="center", va="top", fontsize=bs, color=INK, zorder=3, linespacing=1.35)
    return {"l": (x, y + h / 2), "r": (x + w, y + h / 2), "t": (x + w / 2, y + h), "b": (x + w / 2, y),
            "c": (x + w / 2, y + h / 2), "x": x, "y": y, "w": w, "h": h}


def band(ax, x, y, w, h, label, kind="data"):
    ec, fc = KIND[kind]
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.0,rounding_size=0.2", fc=fc, ec="none", alpha=0.55, zorder=0))
    ax.text(x + 0.15, y + h - 0.12, label, ha="left", va="top", fontsize=10, fontweight="bold", color=ec, zorder=1)


def arrow(ax, p0, p1, label=None, color=INK2, rad=0.0, lw=1.6, ls="-", lpos=0.5, loff=(0, 0.13), fs=8.5, both=False):
    a = FancyArrowPatch(p0, p1, arrowstyle="<|-|>" if both else "-|>", mutation_scale=13, lw=lw, color=color, ls=ls,
                        connectionstyle=f"arc3,rad={rad}", zorder=4, shrinkA=2, shrinkB=2)
    ax.add_patch(a)
    if label:
        mx, my = p0[0] + (p1[0] - p0[0]) * lpos + loff[0], p0[1] + (p1[1] - p0[1]) * lpos + loff[1]
        ax.text(mx, my, label, ha="center", va="center", fontsize=fs, color=color, zorder=5,
                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.9))


def save(fig, name):
    fig.savefig(OUT / name, dpi=150)
    plt.close(fig)
    print("drew", name)


# =====================================================================================
def d01_tdr_principle():
    from src.config import SimConfig
    from src.sim_tdr import make_params, simulate
    fig = plt.figure(figsize=(13.33, 7.5))
    ax = fig.add_axes([0, 0.52, 1, 0.48])
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 4.2)
    ax.axis("off")
    g = box(ax, 0.3, 1.4, 2.4, 1.5, "Generator", "step source\nRs = 50 Ω", "hw")
    t = box(ax, 3.4, 1.55, 1.3, 1.2, "Tee", "scope\nCH1", "hw", ts=10)
    ax.add_patch(Rectangle((4.7, 1.95), 8.0, 0.4, fc="#3D3C39", ec="none", zorder=2))
    ax.text(8.7, 2.15, "coaxial cable, Z0 = 50 Ω, length L, wave speed vp ≈ 0.66·c ≈ 2×10⁸ m/s", ha="center",
            va="center", color="white", fontsize=10, zorder=3)
    f = box(ax, 12.9, 1.4, 2.8, 1.5, "Fault at distance d", "impedance ZL ≠ Z0\nopen · short · R · joint", "warn", ts=10.5)
    arrow(ax, (4.9, 2.9), (12.6, 2.9), "1  incident step travels along the cable (V_inc)", color="#1F7A8C", lw=2.2, loff=(0, 0.3), fs=10)
    arrow(ax, (12.6, 1.4), (4.9, 1.4), "2  part of it reflects back: V_refl = Γ·V_inc,  Γ = (ZL − Z0)/(ZL + Z0)", color="#B85C24", lw=2.2, loff=(0, -0.3), fs=10)
    arrow(ax, g["r"], t["l"])
    ax.text(0.3, 3.95, "Time-domain reflectometry (TDR): send a step, time its echo", fontsize=15, fontweight="bold", color=NAVY, va="top")
    ax.text(0.3, 0.55, "3  the scope at the tee sees the step and, Δt later, the echo:   d = vp · Δt / 2   (the signal travels to the fault and back)",
            fontsize=11, color=INK)
    # waveform
    ax2 = fig.add_axes([0.07, 0.09, 0.56, 0.42])
    cfg = SimConfig()
    cols = {"open": "#B85C24", "short": "#1F7A8C", "matched": "#5F6670"}
    for cls, kw in (("open", {}), ("short", {}), ("matched", {"gamma": 0.0})):
        p = make_params(cfg, cls=cls, d=5.0, rise=4e-9, snr_db=60, ts=0.5e-9, seed=1, **kw)
        (tt, v), = simulate(p, cfg, noiseless=True)
        v = (v - np.median(v[tt < -10e-9])) / p["v_inc"][0]
        ax2.plot(tt * 1e9, v, lw=2.2, color=cols[cls], label={"open": "open end (Γ = +1) → 2·V_inc",
                                                              "short": "short (Γ = −1) → 0",
                                                              "matched": "matched 50 Ω (Γ = 0) → no echo"}[cls])
        dt = float(p["dt_true"][0]) * 1e9
    ax2.annotate("", xy=(dt, 1.4), xytext=(0, 1.4), arrowprops=dict(arrowstyle="<->", color=INK))
    ax2.text(dt / 2, 1.46, f"Δt = 2L/vp ≈ {dt:.1f} ns for 5 m", ha="center", va="bottom", fontsize=9)
    ax2.set(xlim=(-20, 110), ylim=(-0.15, 2.25), xlabel="time after the incident edge (ns)", ylabel="V / V_inc")
    ax2.spines[["top", "right"]].set_visible(False)
    ax2.grid(color="#E4E3DF")
    ax2.legend(frameon=False, fontsize=9, loc="upper left")
    ax3 = fig.add_axes([0.665, 0.07, 0.32, 0.45])
    ax3.axis("off")
    rows = [("Load ZL", "Γ", "level after echo"), ("open (∞)", "+1", "2.0 V_inc"), ("short (0)", "−1", "0"),
            ("50 Ω (matched)", "0", "1.0 V_inc"), ("100 Ω", "+0.33", "1.33 V_inc"), ("22 Ω", "−0.39", "0.61 V_inc"),
            ("75 Ω joint", "+0.20", "1.2 V_inc")]
    for i, r in enumerate(rows):
        y = 0.92 - i * 0.13
        for j, (txt, x) in enumerate(zip(r, (0.0, 0.44, 0.62))):
            ax3.text(x, y, txt, fontsize=10.5, fontweight="bold" if i == 0 else "normal", color=NAVY if i == 0 else INK,
                     transform=ax3.transAxes)
    ax3.text(0, 0.0, "Resolution limit: Δd_min ≈ vp · t_rise / 2\n(4 ns edge → ≈ 0.4 m)", fontsize=10, color="#B26A00",
             transform=ax3.transAxes)
    save(fig, "d01_tdr_principle.png")


def d02_system_block():
    fig, ax = canvas()
    band(ax, 0.1, 5.05, 15.8, 3.85, "LAB HARDWARE", "hw")
    band(ax, 0.1, 2.6, 15.8, 2.3, "ONLINE SOFTWARE (laptop)", "sw")
    band(ax, 0.1, 0.1, 15.8, 2.35, "OFFLINE SOFTWARE", "ml")
    g = box(ax, 0.4, 6.9, 2.5, 1.45, "Function generator", "50 Ω source\nsquare 0→2 V, 100 kHz", "hw")
    t = box(ax, 3.65, 6.9, 2.2, 1.45, "BNC tee", "on scope CH1\nreference plane d = 0", "hw")
    c = box(ax, 6.8, 6.9, 2.4, 1.45, "Coaxial cable", "RG-58: Z0 50 Ω\nvp ≈ 0.66 c", "hw")
    f = box(ax, 9.7, 6.9, 2.75, 1.45, "Fault / termination", "open · short · 50 Ω\nR · 50/75 joint · stub", "warn")
    s = box(ax, t["c"][0] - 1.3, 5.25, 2.6, 1.2, "Oscilloscope", "1 MΩ input, 8-bit ADC\n≥ 500 MSa/s", "hw")
    z = box(ax, 13.0, 6.2, 2.7, 2.15, "External real data", "Zenodo 5720438\n1 M simulated +\n16 measured pulse-\nTDR traces\n(src/zenodo.py)", "data", bs=8.8)
    arrow(ax, g["r"], t["l"], "step")
    arrow(ax, t["r"], c["l"], "incident")
    arrow(ax, c["r"], f["l"])
    arrow(ax, (f["x"] + 0.4, f["y"] + f["h"]), (t["x"] + t["w"] - 0.3, t["y"] + t["h"]), "echo Γ·V_inc", rad=0.16, color="#B85C24", loff=(0, 0.33))
    arrow(ax, t["b"], (t["b"][0], s["y"] + s["h"]), "V(t)", loff=(0.3, 0.0))
    cap = box(ax, 0.4, 2.78, 2.4, 1.42, "capture.py", "PyVISA · SCPI\nRigol/Keysight/Tek/Siglent", "sw", bs=8.3)
    raw = box(ax, 3.1, 2.78, 2.2, 1.42, "data/raw", "CSV + header\nlab_log.csv", "data")
    pre = box(ax, 5.6, 2.78, 2.4, 1.42, "preprocess.py", "align · baseline\nnormalise · denoise", "sw")
    bf = box(ax, 8.3, 2.78, 2.5, 1.42, "baseline + features", "Δt, Γ, class\n23 features · 256-pt grid", "sw", bs=8.6)
    ml = box(ax, 11.1, 2.78, 2.2, 1.42, "ML / NN models", "RF · ET · KNN\nMLP · 1-D CNN", "ml")
    res = box(ax, 13.95, 2.78, 1.8, 1.42, "Result", "distance (m)\nclass +\nconfidence", "out")
    arrow(ax, (s["x"] + 0.3, s["y"]), (cap["x"] + cap["w"] - 0.45, cap["y"] + cap["h"]), "USB (USBTMC)", rad=-0.2, loff=(1.25, 0.13))
    for a, b in ((cap, raw), (raw, pre), (pre, bf), (bf, ml), (ml, res)):
        arrow(ax, a["r"], b["l"])
    sim = box(ax, 0.4, 0.35, 2.6, 1.55, "sim_tdr.py", "frequency-domain\ntransmission line", "sw")
    ds = box(ax, 3.3, 0.35, 2.4, 1.55, "data/sim", "train 20k · val 4k\ntest sets E1–E6", "data")
    tr = box(ax, 6.0, 0.35, 2.5, 1.55, "train.py", "grid search on\nvalidation set", "ml")
    bu = box(ax, 8.8, 0.35, 2.3, 1.55, "models/", "tdr_models.joblib\n18 models", "data")
    ev = box(ax, 11.4, 0.35, 2.4, 1.55, "evaluate / analyze", "E1–E6, metrics,\nlatency", "sw", ts=10.5)
    db = box(ax, 14.1, 0.35, 1.65, 1.55, "Dashboard", "Streamlit +\nPlotly · report", "out")
    for a, b in ((sim, ds), (ds, tr), (tr, bu), (bu, ev), (ev, db)):
        arrow(ax, a["r"], b["l"])
    arrow(ax, bu["t"], (ml["x"] + 0.4, ml["y"]), "loads", rad=0.0)
    arrow(ax, (raw["x"] + 0.5, raw["y"]), (sim["x"] + sim["w"] - 0.3, sim["y"] + sim["h"]), "calibrate → vp, t0, V_inc", rad=0.0, loff=(1.1, 0.0))
    xv = 13.6  # external-validation drop: between ML/NN and Result, onto evaluate / analyze
    arrow(ax, (xv, z["y"]), (xv, ev["y"] + ev["h"]), None, color="#5F6670")
    ax.text(xv - 0.12, 4.97, "external validation", ha="right", va="center", fontsize=8.5, color="#5F6670")
    save(fig, "d02_system_block.png")


def d03_software_architecture():
    fig, ax = canvas()
    band(ax, 0.1, 7.0, 15.8, 1.9, "ENTRY POINTS", "out")
    band(ax, 0.1, 4.55, 15.8, 2.3, "PIPELINES (one per command, src/)", "sw")
    band(ax, 0.1, 2.15, 15.8, 2.25, "CORE LIBRARY (src/)", "ml")
    band(ax, 0.1, 0.1, 15.8, 1.9, "STORAGE (files on disk; TDR_HOME can move all of it)", "data")
    box(ax, 0.4, 7.2, 4.6, 1.3, "index.py (CLI)", "check · simulate · train · evaluate · analyze · dashboard\ncapture · inspect · calibrate · fit · lab-dataset · zenodo · selftest", "out", bs=8)
    box(ax, 5.3, 7.2, 3.4, 1.3, "app/dashboard.py", "Streamlit + Plotly, 5 tabs:\nanalyze · compare · Zenodo · lab · physics", "out", bs=8.2)
    box(ax, 9.0, 7.2, 3.1, 1.3, "tests/ (pytest)", "62 unit + regression tests\n(isolated TDR_HOME)", "out", bs=8.3)
    box(ax, 12.4, 7.2, 3.3, 1.3, "hardware/circuits/", "make_hardware_figures.py\nschematics + expected traces", "out", bs=8.3)
    pipes = [("capture.py", "scope → CSV + log"), ("calibrate.py", "vp, t0, rise, V_inc"), ("fit_sim.py", "sim ↔ measured fit"),
             ("dataset.py", "build / save / load"), ("train.py", "grid search, bundle"), ("evaluate.py", "E1–E6 + 10 figs"),
             ("analysis.py", "errors, P/R/F1,\nlatency"), ("zenodo.py", "real-data pipeline"), ("selftest.py", "every feature,\nsandbox")]
    for i, (n, b) in enumerate(pipes):
        box(ax, 0.3 + i * 1.73, 4.75, 1.56, 1.6, n, b, "sw", ts=9.2, bs=7.6)
    core = [("config.py", "paths, cable presets,\nSimConfig, calibration"), ("sim_tdr.py", "transmission-line\nsimulator + scope model"),
            ("scope_io.py", "universal CSV reader\n(Rigol/Tek/Keysight/…)"), ("preprocess.py", "align, normalise,\ndenoise, V_inc"),
            ("baseline.py", "threshold + lobe\nreflection detector"), ("features.py", "Method A grid +\n23 Method B features"),
            ("models.py", "RF·ET·KNN·MLP\n+ PyTorch 1-D CNN")]
    for i, (n, b) in enumerate(core):
        box(ax, 0.35 + i * 2.23, 2.35, 2.05, 1.6, n, b, "ml", ts=10, bs=7.8)
    stores = [("data/raw/", "lab CSVs + lab_log.csv"), ("data/sim/", "simulated sets (cached)"), ("data/processed/", "lab.csv features"),
              ("data/calibration.json", "vp, t0, V_inc, noise"), ("data/external/", "Zenodo (read-only)"), ("models/", "*.joblib bundles"),
              ("report/", "results/*.csv, figures/")]
    for i, (n, b) in enumerate(stores):
        box(ax, 0.35 + i * 2.23, 0.3, 2.05, 1.3, n, b, "data", ts=9.2, bs=7.6)
    for x in (6.0, 9.6, 13.2):  # clear of the band titles at the left
        arrow(ax, (x, 7.2), (x, 6.38), color=INK2)
        arrow(ax, (x, 4.75), (x, 3.98), color=INK2)
        arrow(ax, (x, 2.35), (x, 1.63), color=INK2)
    save(fig, "d03_software_architecture.png")


def d04_signal_pipeline():
    fig, ax = canvas()
    ax.text(0.3, 8.75, "Inside one trace: from raw samples to model inputs (src/preprocess.py, baseline.py, features.py)",
            fontsize=13, fontweight="bold", color=NAVY, va="top")
    steps = [("1  Raw trace", "(t, v) from scope CSV\nor simulator", "data"),
             ("2  Baseline", "median of pre-trigger\nsamples subtracted", "sw"),
             ("3  V_inc", "incident step height:\nper trace, calibration\nas reference", "sw"),
             ("4  Normalise", "v / V_inc: plateau 1,\nopen 2, short 0", "sw"),
             ("5  Align", "incident 50 % crossing\n→ t = 0", "sw"),
             ("6  Denoise", "Gaussian σ = 0.3–0.9 ×\nrise time (by noise)", "sw")]
    prev = None
    for i, (n, b, k) in enumerate(steps):
        bx = box(ax, 0.3 + i * 2.6, 6.0, 2.35, 1.9, n, b, k, ts=10.5, bs=8.6)
        if prev:
            arrow(ax, prev["r"], bx["l"])
        prev = bx
    bl = box(ax, 0.3, 2.7, 5.0, 2.6, "Baseline detector (classical)",
             "• derivative of the denoised trace\n• threshold = max(3 % of incident slope,\n   4.5 × MAD noise of the derivative)\n"
             "• first lobe after the incident edge\n• 50 % crossing → Δt;  lobe area → Γ\n• class rules: |amp| < 0.035 matched,\n   Γ ≥ 0.82 open, ≤ −0.82 short, else partial", "sw", bs=8.5, align="left")
    ma = box(ax, 5.6, 2.7, 4.8, 2.6, "Method A input (raw samples)",
             "normalised trace resampled on a fixed grid:\n256 points, 1 ns apart, −16 … 239 ns\n(anti-aliased, fixture offset t0 removed)\n\n→ used by RF, ET, KNN, MLP and the 1-D CNN",
             "ml", bs=8.6, align="left")
    mb = box(ax, 10.7, 2.7, 5.0, 2.6, "Method B input (23 physics features)",
             "Δt, reflected amplitude, polarity, final level,\nreflection rise, noise σ, sample interval,\nfound/merged flags, slope ratio, Γ estimate,\n"
             "incident rise, 10/25/50 % crossing times,\nsecond echo, 4 energy windows, centroid\n(8 of them come from the baseline detector)\n→ used by RF, ET, KNN, MLP", "ml", bs=8.4, align="left")
    bus = 5.62
    ax.plot([prev["b"][0], prev["b"][0]], [prev["b"][1], bus], color=INK2, lw=1.6, zorder=4)
    ax.plot([bl["x"] + 2.5, prev["b"][0]], [bus, bus], color=INK2, lw=1.6, zorder=4)
    for tx in (bl["x"] + 2.5, ma["t"][0], mb["x"] + 2.5):
        arrow(ax, (tx, bus), (tx, 5.3))
    ax.text(8.0, bus + 0.12, "the same processed trace feeds all three", ha="center", va="bottom", fontsize=8.5, color=INK2,
            bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none"))
    o = box(ax, 3.8, 0.25, 8.4, 1.5, "Outputs per trace", "baseline: Δt, d, Γ, class   ·   models: Δt̂ (ns) → d̂ = vp·Δt̂/2, class + probability\n"
            "if preprocessing fails (no incident edge): no prediction, counted as not covered", "out", bs=9)
    arrow(ax, bl["b"], (o["x"] + 1.0, o["y"] + o["h"]))
    arrow(ax, ma["b"], o["t"])
    arrow(ax, mb["b"], (o["x"] + o["w"] - 1.0, o["y"] + o["h"]))
    save(fig, "d04_signal_pipeline.png")


def d05_ml_architecture(cfgtab=None):
    fig, ax = canvas()
    ax.text(0.3, 8.8, "The five model families (same scikit-learn interface; selected by validation grid search)",
            fontsize=13, fontweight="bold", color=NAVY, va="top")
    # CNN
    band(ax, 0.2, 4.55, 15.6, 3.75, "1-D CNN (PyTorch, Method A only) — src/models.py CNN1D", "ml")
    layers = [("input", "1 × 256"), ("block 1", "2×Conv k7\n+ BN + ReLU\n16 ch, MaxPool\n→ 16×128"), ("block 2", "32 ch → 32×64"),
              ("block 3", "64 ch → 64×32"), ("block 4", "64 ch → 64×16"), ("flatten", "1024\n(keeps position)"),
              ("dense", "Dropout 0.2 →\n128, ReLU"), ("output", "1 (Δt) or\n4 class logits")]
    prev = None
    for i, (n, b) in enumerate(layers):
        hgt = [1.0, 2.6, 2.2, 1.8, 1.5, 2.2, 1.6, 1.2][i]
        bx = box(ax, 0.45 + i * 1.92, 6.4 - hgt / 2, 1.65, hgt, n, b, "ml", ts=9.5, bs=7.6)
        if prev:
            arrow(ax, prev["r"], bx["l"])
        prev = bx
    ax.text(0.45, 4.75, "Training: AdamW (lr 2e-3, wd 1e-4), smooth-L1 loss (regression) or cross-entropy (classes), batch 256, "
            "ReduceLROnPlateau, early stopping (patience 6, ≤ 40 epochs), inputs standardised.", fontsize=8.6, color=INK)
    # three classical
    t = box(ax, 0.2, 0.85, 5.1, 3.45, "Random Forest / Extra Trees", "", "sw")
    for j in range(3):
        cx = 1.1 + j * 1.65
        ax.plot([cx, cx - 0.4, cx + 0.4, cx], [3.45, 2.75, 2.75, 3.45], color="#1F7A8C", lw=1.4)
        for xx in (cx - 0.4, cx + 0.4):
            ax.plot([xx, xx - 0.22, xx + 0.22, xx], [2.75, 2.15, 2.15, 2.75], color="#1F7A8C", lw=1.2)
        ax.text(cx, 3.6, f"tree {j + 1 if j < 2 else 'n'}", ha="center", fontsize=8)
    ax.text(0.4, 1.85, "100 trees on bootstrap samples (RF) or random\nsplit points (ET); average Δt / majority vote.\n"
            "Inputs A (256) or B (23). Gives feature importance.", fontsize=8.4, va="top", color=INK)
    k = box(ax, 5.5, 0.85, 5.1, 3.45, "k-nearest neighbours", "", "sw")
    rng = np.random.default_rng(3)
    pts = rng.normal(size=(40, 2)) * [0.9, 0.5] + [8.0, 2.75]
    pts = pts[(np.abs(pts[:, 0] - 8.05) <= 2.1) & (pts[:, 1] >= 2.1) & (pts[:, 1] <= 3.65)]  # keep the cloud inside its box
    ax.scatter(pts[:, 0], pts[:, 1], s=10, color="#9AA0A8", zorder=3)
    q = np.array([8.1, 2.8])
    nn_ = pts[np.argsort(((pts - q) ** 2).sum(1))[:5]]
    ax.scatter(nn_[:, 0], nn_[:, 1], s=22, color="#1F7A8C", zorder=4)
    ax.scatter(*q, marker="*", s=140, color="#B85C24", zorder=5)
    ax.text(5.7, 1.85, "Standardise inputs; find the k most similar\ntraining traces (k = 5/15, by validation);\naverage their Δt / vote their class.",
            fontsize=8.4, va="top", color=INK)
    m = box(ax, 10.8, 0.85, 5.0, 3.45, "MLP neural network", "", "sw")
    xs = [11.4, 12.7, 14.0, 15.2]
    ns = [6, 5, 4, 1]
    for li, (x, n_) in enumerate(zip(xs, ns)):
        ys = np.linspace(2.3, 3.6, n_) if n_ > 1 else [2.95]
        for yv in ys:
            ax.scatter(x, yv, s=30, color="#1F7A8C", zorder=4)
            if li < 3:
                ys2 = np.linspace(2.3, 3.6, ns[li + 1]) if ns[li + 1] > 1 else [2.95]
                for y2 in ys2:
                    ax.plot([x, xs[li + 1]], [yv, y2], color="#B9D7DE", lw=0.6, zorder=3)
    ax.text(11.0, 1.85, "StandardScaler → hidden (128, 64) or (256, 128),\nReLU, Adam, early stopping → Δt or class.\n"
            "Target also standardised for regression.", fontsize=8.4, va="top", color=INK)
    if cfgtab is not None:
        import textwrap
        ax.text(0.3, 0.1, textwrap.fill("Selected settings: " + cfgtab, 185, max_lines=3, placeholder=" …"), fontsize=7.5,
                color=INK2, va="bottom")
    save(fig, "d05_ml_architecture.png")


def d06_localization_flow():
    fig, ax = canvas()
    ax.text(0.3, 8.8, "Localization: how a distance is produced (and learned)", fontsize=13, fontweight="bold", color=NAVY, va="top")
    a = box(ax, 0.35, 6.6, 3.45, 1.6, "Measured / simulated trace", "V(t) at the tee", "data", ts=11)
    b = box(ax, 4.35, 6.6, 2.85, 1.6, "Preprocess", "normalise by V_inc,\nalign, denoise", "sw")
    arrow(ax, a["r"], b["l"])
    c1 = box(ax, 7.8, 7.0, 3.6, 1.55, "Classical path", "first derivative lobe above\nthreshold → 50 % crossing → Δt", "sw", bs=8.6)
    c2 = box(ax, 7.8, 5.15, 3.6, 1.55, "ML path", "Method A (256) or B (23) →\nregressor predicts Δt̂ (ns)", "ml", bs=8.6)
    arrow(ax, b["r"], c1["l"], rad=-0.15)
    arrow(ax, b["r"], c2["l"], rad=0.15)
    d = box(ax, 12.2, 5.9, 3.5, 2.0, "Distance", "d = vp · Δt / 2\nvp from calibration\n(datasheet until calibrated)", "out", bs=9)
    arrow(ax, c1["r"], d["l"], rad=-0.1)
    arrow(ax, c2["r"], d["l"], rad=0.1)
    # training branch
    band(ax, 0.2, 0.2, 15.6, 4.5, "Training the regressors (offline)", "ml")
    s = box(ax, 0.5, 2.0, 3.0, 1.7, "Simulator", "random d 0.5–20 m, fault\ntype, Γ, rise 2–10 ns,\nSNR 10–40 dB, scope", "sw", bs=8.4)
    lab = box(ax, 4.0, 2.0, 3.0, 1.7, "Label", "Δt_true = 2d / vp\n(target in ns; only\ntraces with a fault)", "data", bs=8.6)
    g = box(ax, 7.5, 2.0, 3.6, 1.7, "Grid search", "fit on train (20 000),\npick by validation MAE\n(4 000), never on test", "ml", bs=8.6)
    o = box(ax, 11.6, 2.0, 4.0, 1.7, "Test on held-out sets", "MAE, RMSE, median, P95, max,\nbias; by SNR, distance, type,\nrise time, |Γ|", "out", bs=8.4)
    for p, q in ((s, lab), (lab, g), (g, o)):
        arrow(ax, p["r"], q["l"])
    ax.text(0.5, 0.75, "Why regress Δt and not d?  Δt is what the trace actually contains; converting with the *calibrated* vp means a model trained on "
            "datasheet vp still gives correct metres once the cable is calibrated.\nMetrics: MAE = mean |d̂ − d|,  RMSE = √mean (d̂ − d)²,  "
            "P95 = 95th percentile of |error|,  coverage = share of faulted traces that got a distance.", fontsize=8.6, color=INK, va="bottom")
    save(fig, "d06_localization_flow.png")


def d07_detection_flow():
    fig, ax = canvas()
    ax.text(0.3, 8.8, "Detection: is there a fault, and what kind?  (4 classes: open · short · matched · partial)",
            fontsize=13, fontweight="bold", color=NAVY, va="top")
    r = box(ax, 4.0, 6.1, 5.2, 2.0, "Baseline rules (baseline.py)",
            "amp = area of first reflection lobe\nΓ ≈ amp · $e^{2\\alpha d}$ (cable loss compensated)\n"
            "|amp| < 0.035 → matched (no fault)\nΓ ≥ 0.82 → open · Γ ≤ −0.82 → short\notherwise → partial", "sw", bs=8.4, align="left")
    m = box(ax, 4.0, 3.65, 5.2, 2.0, "ML classifier (RF/ET/KNN/MLP/CNN)",
            "input: Method A grid or Method B features\noutput: probability for each class\n→ class = argmax, confidence = max prob.",
            "ml", bs=8.6, align="left")
    ymid = (r["c"][1] + m["c"][1]) / 2
    a = box(ax, 0.4, ymid - 0.8, 2.8, 1.6, "Preprocessed trace", "normalised, aligned", "data")
    arrow(ax, a["r"], r["l"], rad=-0.12)
    arrow(ax, a["r"], m["l"], rad=0.12)
    o = box(ax, 10.0, ymid - 1.1, 2.6, 2.2, "Decision", "class + confidence\nfault present =\nclass ≠ matched", "out", bs=9)
    arrow(ax, r["r"], o["l"], rad=-0.1)
    arrow(ax, m["r"], o["l"], rad=0.1)
    u = box(ax, 13.2, ymid - 1.1, 2.5, 2.2, "Used by", "dashboard card,\ncapture quick check,\nE1–E6 tables", "data", bs=8.8)
    arrow(ax, o["r"], u["l"])
    band(ax, 0.2, 0.6, 15.6, 2.7, "How detection is scored (src/analysis.py)", "out")
    ax.text(0.5, 2.76, "Binary view (fault present?)", fontsize=10.5, fontweight="bold", color="#2E7D32", va="top")
    ax.text(0.5, 2.34, "TP: fault and detected   FP: matched line called a fault (false alarm)\nFN: fault called matched (miss)   TN: matched and called matched\n"
            "precision = TP/(TP+FP)   recall = TP/(TP+FN)\nF1 = 2·P·R/(P+R)   false-alarm rate = FP/(FP+TN)", fontsize=9.5, va="top", color=INK, linespacing=1.6)
    ax.text(8.3, 2.76, "Four-class view", fontsize=10.5, fontweight="bold", color="#2E7D32", va="top")
    ax.text(8.3, 2.34, "accuracy = correct / all;  per-class precision, recall, F1;\nmacro-F1 = mean of the four F1 (each class counts equally)\n"
            "confusion matrix: rows = true class, columns = predicted\nmAP / IoU do not apply (no bounding boxes: 1-D signal)", fontsize=9.5, va="top", color=INK, linespacing=1.6)
    save(fig, "d07_detection_flow.png")


def d08_sequence_capture():
    fig, ax = canvas()
    ax.text(0.3, 8.8, "Capture session: sequence of one repeat (src/capture.py)", fontsize=13, fontweight="bold", color=NAVY, va="top")
    lanes = [("Operator", "out"), ("index.py capture", "sw"), ("PyVISA driver", "sw"), ("Oscilloscope", "hw"), ("Files", "data"), ("Quick check", "ml")]
    xs = [1.4 + i * 2.64 for i in range(len(lanes))]
    for x, (n, k) in zip(xs, lanes):
        box(ax, x - 1.1, 7.6, 2.2, 0.75, n, None, k, ts=10)
        ax.plot([x, x], [0.6, 7.6], color="#C7CBD1", lw=1.2, ls="--", zorder=1)
    msgs = [(0, 1, "--length 5.02 --termination open --repeats 20"), (1, 2, "connect(): open first USB/LAN resource"),
            (2, 3, "*IDN?  → vendor → driver class"), (1, 2, "acquire(ch, settle)"), (2, 3, ":RUN · wait settle · :STOP"),
            (2, 3, ":WAV:SOUR CHAN1 · :WAV:PRE? · :WAV:DATA?"), (3, 2, "preamble + 8-bit samples"),
            (2, 1, "t, v in seconds / volts (scaled by preamble)"), (1, 4, "save CSV with # header (all labels)"),
            (1, 4, "append row to lab_log.csv"), (1, 5, "preprocess + baseline (calibration)"), (5, 0, "prints dt, d, amp, class per repeat")]
    y = 7.1
    for a_, b_, lab in msgs:
        arrow(ax, (xs[a_], y), (xs[b_], y), None, color="#1F7A8C" if b_ > a_ else "#B85C24")
        ax.text((xs[a_] + xs[b_]) / 2, y + 0.12, lab, ha="center", va="bottom", fontsize=8.2, color=INK,
                bbox=dict(boxstyle="round,pad=0.1", fc="white", ec="none"))
        y -= 0.56
    ax.text(0.3, 0.15, "SimScope replaces the VISA driver for rehearsal (--simulate): same files, same log, same quick check.", fontsize=9, color=INK2)
    save(fig, "d08_sequence_capture.png")


def d09_end_to_end():
    fig, ax = canvas()
    ax.text(0.3, 8.8, "End-to-end run: from power-on to a located fault", fontsize=13, fontweight="bold", color=NAVY, va="top")
    steps = [("1 Power on & set", "generator 0→2 V 100 kHz\nscope 1 MΩ, trigger 0.5 V", "hw"),
             ("2 index.py check", "packages, VISA backend,\ncalibration, models", "sw"),
             ("3 Connect", "*IDN? → driver\n(Rigol/Keysight/…)", "sw"),
             ("4 Acquire", "RUN/STOP, read\nwaveform + preamble", "hw"),
             ("5 Save + log", "CSV + header,\nlab_log.csv row", "data"),
             ("6 Quick check", "baseline d, class\nprinted per repeat", "sw"),
             ("7 Calibrate", "Δt vs L fit →\nvp, t0, rise, V_inc", "sw"),
             ("8 Lab dataset", "same preprocessing\n+ features as sim", "data"),
             ("9 Train", "simulator centred on\ncalibration, 18 models", "ml"),
             ("10 Evaluate", "E1–E6 + analysis\n(LAB once ≥ 20 traces)", "ml"),
             ("11 Dashboard", "load bundle, analyze\nany trace live", "out"),
             ("12 Report", "tables, figures,\nmeasured limits", "out")]
    for i, (n, b, k) in enumerate(steps):
        row, col = divmod(i, 6)
        x = 0.35 + col * 2.62 if row == 0 else 0.35 + (5 - col) * 2.62
        y = 5.55 if row == 0 else 2.3
        bx = box(ax, x, y, 2.3, 1.8, n, b, k, ts=10.5, bs=9)
        if i:
            if i == 6:
                arrow(ax, (prev["x"] + prev["w"] / 2, prev["y"]), (bx["x"] + bx["w"] / 2, bx["y"] + bx["h"]))
            elif row == 0:
                arrow(ax, prev["r"], bx["l"])
            else:
                arrow(ax, prev["l"], bx["r"])
        prev = bx
    ax.text(0.35, 1.2, "Steps 1–6 repeat for every configuration (H5–H8); 7–12 run once after the session. "
            "Steps 2–12 are tested end to end with the simulated scope (index.py selftest).", fontsize=9.5, color=INK)
    save(fig, "d09_end_to_end.png")


def d10_timeline():
    fig, ax = canvas()
    ax.text(0.3, 8.8, "Development journey (milestones in the order they were built)", fontsize=13, fontweight="bold", color=NAVY, va="top")
    ms = [("M1", "Brief + research", "TDR theory, literature,\nwork packages WP1–WP8", "data"),
          ("M2", "Simulator", "frequency-domain t-line,\nscope + noise model", "sw"),
          ("M3", "Baseline", "threshold + lobe detector,\nunit tests vs theory", "sw"),
          ("M4", "Features + datasets", "Method A grid,\n23 Method B features", "sw"),
          ("M5", "ML models", "RF/ET, then KNN, MLP,\nPyTorch 1-D CNN", "ml"),
          ("M6", "Evaluation", "E1–E6, 10 figures,\nsummary", "ml"),
          ("M7", "Hardware software", "PyVISA capture, CSV reader,\ncalibration, sim fit", "hw"),
          ("M8", "Dashboard", "Streamlit + Plotly,\n5 tabs", "out"),
          ("M9", "Real data (Zenodo)", "safe download/parse,\n1 M traces, CNN", "data"),
          ("M10", "Hardware docs", "procedure, 13 circuits,\nexpected waveforms", "hw"),
          ("M11", "Review + testing", "independent review,\n14 fixes, selftest", "warn"),
          ("M12", "Analysis + deck", "ML analysis, docs,\npresentation", "out")]
    x0, x1, yl, bh = 1.25, 14.75, 4.75, 1.9  # first/last milestone centre, timeline height, box height
    ax.plot([x0 - 0.35, x1 + 0.35], [yl, yl], color="#C7CBD1", lw=3, zorder=1)
    for i, (k, n, b, kind) in enumerate(ms):
        x = x0 + i * (x1 - x0) / 11
        ec, fc = KIND[kind]
        ax.scatter(x, yl, s=260, color=ec, zorder=3)
        ax.text(x, yl, k[1:], ha="center", va="center", color="white", fontsize=8, fontweight="bold", zorder=4)
        up = i % 2 == 0
        y0 = yl + 0.75 if up else yl - 0.75 - bh
        box(ax, x - 1.1, y0, 2.2, bh, n, b, kind, ts=9.8, bs=8.2)
        ax.plot([x, x], [yl + 0.25, y0] if up else [y0 + bh, yl - 0.25], color=ec, lw=1.2)
    ax.text(0.3, 1.2, "Started 2026-11-05 from the project brief; software, simulation and real-data results complete; "
            "lab measurements (hardware steps S1–S14) pending lab access.", fontsize=9.5, color=INK)
    save(fig, "d10_timeline.png")


def d11_datasets():
    fig, ax = canvas()
    ax.text(0.3, 8.8, "Data used for training and testing (all labels exact by construction)", fontsize=13, fontweight="bold", color=NAVY, va="top")
    band(ax, 0.2, 4.65, 15.6, 3.7, "Our simulated data (src/sim_tdr.py, data/sim/) — separate random seeds per set", "sw")
    sets = [("train", "20 000 traces\nseed 1", "ml"), ("validation", "4 000\nseed 2 (model\nselection only)", "ml"),
            ("test mixed", "6 000, seed 3\nSNR 10–40 dB", "out"), ("E1 SNR sets", "7 × 1 200\n10…40 dB", "out"),
            ("E5 soft faults", "8 × 600\n|Γ| 0.01–0.3", "out"), ("proxy lab", "1 500 with lab\nartifacts", "warn")]
    for i, (n, b, k) in enumerate(sets):
        box(ax, 0.45 + i * 2.58, 5.85, 2.35, 1.9, n, b, k, ts=10.5, bs=9)
    ax.text(0.45, 5.55, "Random per trace: distance 0.5–20 m · class open/short/matched/partial · fault kind (end R, series R, shunt R, "
            "impedance step, open stub) · |Γ| · rise 2–10 ns ·\nSNR 10–40 dB · sample interval · generator Rs ±8 % · scope C 8–20 pF · cable loss · "
            "trigger jitter · baseline drift · 8-bit ADC.  E2 retrains with 4–6 m and > 14 m removed (interpolation / extrapolation test).",
            fontsize=8.8, color=INK, va="top")
    band(ax, 0.2, 0.62, 15.6, 3.53, "External data: Zenodo 5720438 (Scarpetta et al. 2021), 4.18 GB, parsed with a restricted unpickler", "data")
    zs = [("Baseline / RF-B", "trainB: 0–200 k", "ml"), ("A-input models", "trainA: 0–100 k", "ml"), ("CNN", "800 k train\n20 k val (980 k–1 M)", "ml"),
          ("Z1 test", "800 k–820 k\nheld out", "out"), ("Z2 noise", "820 k–845 k\nnoise ×1, 3, 10, 30", "out"), ("Z3 real", "16 measured\ntraces", "warn")]
    for i, (n, b, k) in enumerate(zs):
        box(ax, 0.45 + i * 2.58, 1.65, 2.35, 1.9, n, b, k, ts=10.5, bs=9)
    ax.text(0.45, 1.35, "1 000 000 simulated pulse-TDR traces (1024 samples, 4 ns), up to 4 faults each; we use the first fault "
            "(distance + type) and the cable length — our single-fault targets.", fontsize=8.8, color=INK, va="top")
    save(fig, "d11_datasets.png")


def d12_integration():
    fig, ax = canvas()
    ax.text(0.3, 8.8, "Hardware ↔ software integration, layer by layer", fontsize=13, fontweight="bold", color=NAVY, va="top")
    layers = [("Physical signal", "step + echo on 50 Ω coax; BNC tee at CH1 defines d = 0", "hw", "tee directly on CH1, short lead, 1 MΩ input"),
              ("Instrument", "scope samples CH1 (8-bit, ≥ 500 MSa/s), holds the record", "hw", "trigger Normal at 50 %, BW limit off, other channels off"),
              ("Transport", "USB-TMC (or LAN/VXI-11) through VISA: NI-VISA or pyvisa-py", "sw", "capture --list shows the *IDN? string"),
              ("Command set", "SCPI per vendor: Rigol :WAV, Keysight :WAVeform, Tek CURVE?, Siglent WF?", "sw", "preamble → volts and seconds; unknown vendor → Keysight style"),
              ("Data contract", "CSV with # header (labels) + lab_log.csv (28 columns) + calibration.json", "data", "universal reader also parses scope-exported CSVs"),
              ("Consumers", "calibrate · lab-dataset · fit · train · evaluate · analyze · dashboard", "ml", "selftest runs this whole chain with SimScope")]
    for i, (n, b, k, chk) in enumerate(layers):
        y = 7.3 - i * 1.3
        box(ax, 0.4, y, 3.0, 0.9, n, None, k, ts=11.5)
        ax.text(3.75, y + 0.6, b, fontsize=10.5, color=INK, va="center")
        ax.text(3.75, y + 0.26, "check: " + chk, fontsize=9, color=INK2, va="center", style="italic")
        if i:
            arrow(ax, (1.9, y + 0.9 + 0.4), (1.9, y + 0.9), both=True)
    ax.text(0.4, 0.25, "Synchronisation: the scope's trigger defines t = 0; software re-aligns every trace on the incident 50 % crossing, "
            "so trigger jitter and delay do not bias Δt.", fontsize=9.5, color=INK)
    save(fig, "d12_integration.png")


def main():
    for f in (d01_tdr_principle, d02_system_block, d03_software_architecture, d04_signal_pipeline, d06_localization_flow,
              d07_detection_flow, d08_sequence_capture, d09_end_to_end, d10_timeline, d11_datasets, d12_integration):
        f()
    import pandas as pd
    cfg = ROOT / "report" / "results" / "analysis_model_config.csv"
    txt = None
    if cfg.exists():
        t = pd.read_csv(cfg)
        sel = t[t.task == "reg"]
        txt = " · ".join(f"{r.key}: {r.params}" for r in sel.itertuples())  # wrapped to ≤ 3 lines in d05
    d05_ml_architecture(txt)


if __name__ == "__main__":
    main()
