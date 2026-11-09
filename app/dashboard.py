"""TDR Fault Locator dashboard (WP8).

    python index.py dashboard          (or: streamlit run app/dashboard.py)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import plotly.graph_objects as go  # noqa: E402
import streamlit as st  # noqa: E402

from src.baseline import detect  # noqa: E402
from src.config import (CABLES, CLASSES, FIG_DIR, K_END, K_SERIES, K_SHUNT,  # noqa: E402
                        K_STEP, K_STUB, LAB_LOG, RAW_DIR, RESULTS_DIR, ROOT as HOME,
                        SimConfig, load_calibration)
from src.features import FEATURES_B, process_one  # noqa: E402
from src.scope_io import load_waveform, parse_text  # noqa: E402
from src.sim_tdr import make_params, simulate  # noqa: E402
from src.train import DEFAULT_BUNDLE, load_bundle  # noqa: E402

from src.models import FAMILIES, FAMILY_NAME  # noqa: E402

BLUE, ORANGE, GRAY, INK = "#2a78d6", "#eb6834", "#7a7975", "#52514e"
# same encoding as the report figures: hue = model family, solid = features (B), dashed = raw samples (A)
FAM_COLOR = {"RF": "#2a78d6", "ET": "#eb6834", "KNN": "#1baf7a", "MLP": "#eda100", "CNN": "#e87ba4"}
ALL_KEYS = [f"{f}-{m}" for f in FAMILIES for m in ("A", "B")]


def mstyle(k):
    if k == "Baseline":
        return GRAY, "solid"
    fam, m = k.split("-")
    return FAM_COLOR[fam], "solid" if m == "B" else "dash"


def mname(k):
    if k == "Baseline":
        return "Baseline (threshold + peak)"
    fam, m = k.split("-")
    return f"{FAMILY_NAME[fam]}, {'features (B)' if m == 'B' else 'raw samples (A)'}"

st.set_page_config(page_title="TDR Fault Locator", page_icon=":material/cable:", layout="wide")


# ---------------------------------------------------------------- cached resources
@st.cache_resource(show_spinner="Loading trained models ...")
def get_bundle():
    if not DEFAULT_BUNDLE.exists():
        return None
    b = load_bundle(DEFAULT_BUNDLE)
    from src.models import set_threads
    for m in b["models"].values():   # one trace at a time: single-threaded is ~4x faster
        set_threads(m, 1)
    return b


@st.cache_data
def get_results():
    out = {}
    for f in RESULTS_DIR.glob("*.csv"):
        out[f.stem] = pd.read_csv(f)
    sj = RESULTS_DIR / "summary.json"
    out["summary"] = json.loads(sj.read_text()) if sj.exists() else {}
    return out


def analyze(t, v, v_inc, vp, preset, t_offset=0.0, cal=None):
    """Same chain as the datasets: ``cal`` given = measured trace (V_inc per trace,
    fixture offset removed from the model inputs)."""
    pr, b, grid, fb = process_one(t, v, vp, preset, v_inc=v_inc, t_offset=t_offset, cal=cal)
    out = {"proc": pr, "base": b, "ml": {}}
    bundle = get_bundle()
    if bundle is None or not pr.ok:
        return out
    xa = grid[None, :]
    xb = np.array([[fb[k] for k in FEATURES_B]], np.float32)
    out["features"] = fb
    out["grid"] = xa[0]
    for (task, method, algo), m in bundle["models"].items():
        key = f"{algo}-{method}"
        X = xa if method == "A" else xb
        r = out["ml"].setdefault(key, {})
        if task == "reg":
            r["dt"] = float(m.predict(X)[0]) * 1e-9
            r["d"] = vp * r["dt"] / 2
        else:
            pr_ = m.predict_proba(X)[0]
            r["proba"] = dict(zip(m.classes_, pr_))
            r["cls"] = m.classes_[int(np.argmax(pr_))]
    return out


# ---------------------------------------------------------------- sidebar
cal = load_calibration()
st.sidebar.title("TDR Fault Locator")
st.sidebar.caption("Calibrated setup" if cal["calibrated"] else "Not calibrated yet: datasheet values in use")
cable = st.sidebar.selectbox("Cable", list(CABLES), index=list(CABLES).index(cal["cable_type"]) if cal["cable_type"] in CABLES else 0)
preset = CABLES[cable]
vp_default = float(cal["vp_m_per_s"]) if cal["calibrated"] else preset.vp
vp = st.sidebar.number_input("Propagation velocity vp (m/s)", value=vp_default, format="%.4e", step=1e6)
st.sidebar.caption(f"Velocity factor {vp / 299_792_458:.3f}")
source = st.sidebar.radio("Trace source", ["Simulate", "Upload scope CSV", "Saved trace"], horizontal=False)

truth = None
trace = None
v_inc_in = cal.get("v_inc_v")

if source == "Simulate":
    st.sidebar.subheader("Simulated setup")
    fault = st.sidebar.selectbox("Fault", ["Open end", "Short end", "Matched (Z0 load)", "Resistive load ZL",
                                           "Series resistor", "Shunt resistor (partial short)",
                                           "Impedance step (joint)", "Open stub on a tee"])
    d = st.sidebar.slider("Fault distance d (m)", 0.5, 22.0, 5.0, 0.1)
    kw = dict(d=d)
    if fault == "Open end":
        kw.update(cls="open")
    elif fault == "Short end":
        kw.update(cls="short")
    elif fault == "Matched (Z0 load)":
        kw.update(cls="matched", gamma=0.0)
    elif fault == "Resistive load ZL":
        zl = st.sidebar.number_input("ZL (ohm)", 0.0, 10000.0, 100.0, 1.0)
        kw.update(cls="partial", zl=zl)
    elif fault == "Series resistor":
        r = st.sidebar.number_input("R series (ohm)", 0.0, 10000.0, 50.0, 1.0)
        kw.update(cls="partial", kind=K_SERIES, r_fault=r)
    elif fault == "Shunt resistor (partial short)":
        r = st.sidebar.number_input("R shunt (ohm)", 0.1, 100000.0, 50.0, 1.0)
        kw.update(cls="partial", kind=K_SHUNT, r_fault=r)
    elif fault == "Impedance step (joint)":
        z2 = st.sidebar.number_input("Z of following section (ohm)", 10.0, 200.0, 75.0, 1.0)
        kw.update(cls="partial", kind=K_STEP, z2=z2)
    else:
        ls = st.sidebar.slider("Stub length (m)", 0.2, 5.0, 1.0, 0.1)
        kw.update(cls="partial", kind=K_STUB, l_stub=ls)
    snr = st.sidebar.slider("SNR (dB)", 5, 60, 30)
    rise = st.sidebar.slider("System rise time (ns)", 1.0, 15.0, 4.0, 0.5)
    ts = st.sidebar.select_slider("Scope sample interval (ns)", [0.25, 0.5, 1.0, 2.0, 4.0], value=1.0)
    model = st.sidebar.selectbox("Physics model", ["tline", "simple"],
                                 help="tline: frequency-domain transmission line; simple: the brief's analytic model")
    artifacts = st.sidebar.checkbox("Lab artifacts (adapter, ringing, 1/f noise)", False)
    seed = st.sidebar.number_input("Noise seed", 0, 10**6, 1)
    cfg = SimConfig(cable=cable, model=model, vp_nominal=vp)
    p = make_params(cfg, rise=rise * 1e-9, snr_db=float(snr), ts=ts * 1e-9, seed=int(seed),
                    vp=vp, artifacts=artifacts, **kw)
    p["model"][:] = model
    (t, v), = simulate(p, cfg)
    trace = (t, v)
    v_inc_in = float(p["v_inc_ref"][0])
    truth = {"d": d, "dt": float(p["dt_true"][0]), "cls": kw["cls"], "gamma": float(p["gamma_true"][0])}

elif source == "Upload scope CSV":
    up = st.sidebar.file_uploader("Scope export (.csv / .txt)", type=["csv", "txt"])
    ch = st.sidebar.text_input("Channel (blank = first)", "")
    if up is not None:
        try:
            wf = parse_text(up.getvalue().decode("utf-8-sig", errors="replace"), channel=ch or None, source=up.name)
            trace = (wf.t, wf.v)
            st.sidebar.success(wf.summary())
        except Exception as exc:
            st.sidebar.error(f"Could not read the file: {exc}")
else:
    files = sorted(RAW_DIR.rglob("*.csv"))
    files = [f for f in files if f.name != "lab_log.csv"]
    if files:
        pick = st.sidebar.selectbox("File", files, format_func=lambda f: str(f.relative_to(RAW_DIR)))
        try:
            wf = load_waveform(pick)
        except Exception as exc:  # one unreadable file must not stop the whole app
            st.sidebar.error(f"Could not read {pick.name}: {exc}")
            wf = None
        if wf is not None:
            trace = (wf.t, wf.v)
        m = wf.meta if wf is not None else {}
        if m.get("fault_position_m"):
            try:
                dd = float(m["fault_position_m"])
                truth = {"d": dd, "dt": 2 * dd / vp, "cls": m.get("termination", "?"), "gamma": None}
            except ValueError:
                pass
    else:
        st.sidebar.info("No saved traces in data/raw yet.")

if source != "Simulate":
    mode = st.sidebar.radio("V_inc for normalising", ["Automatic (per trace)", "Manual"],
                            help="Automatic: estimated from each trace; the calibrated V_inc is used when the "
                                 "estimate agrees with it or fails (see preprocess_measured).")
    if mode == "Manual":
        v_inc_in = st.sidebar.number_input("V_inc (V)", 0.001, 50.0, float(cal.get("v_inc_v") or 1.0))
    else:
        v_inc_in = None
# measured traces carry the fixture offset found by calibration; simulated ones do not
measured = source != "Simulate"
t_off = float(cal.get("t_offset_s", 0.0)) if (cal["calibrated"] and measured) else 0.0

# ---------------------------------------------------------------- tabs
tab_an, tab_cmp, tab_real, tab_cal, tab_phys = st.tabs(["Analyze trace", "Model comparison", "Real data (Zenodo)", "Calibration & lab", "Physics"])
bundle = get_bundle()
res = get_results()
best = res["summary"].get("best_regressor", "ET-B")
best_c = res["summary"].get("best_classifier", "ET-B")

with tab_an:
    if trace is None:
        st.info("Choose a trace source in the sidebar.")
    else:
        out = analyze(trace[0], trace[1], v_inc_in, vp, preset, t_off, cal if measured else None)
        pr, b = out["proc"], out["base"]
        if not pr.ok:
            st.error(f"Preprocessing failed: {pr.msg}")
        else:
            if bundle is None:
                st.warning("No trained models found. Run `python index.py train` first.")
            c = st.columns(5)
            c[0].metric("Baseline distance", f"{b.distance:.2f} m" if b.found else "no reflection",
                        f"{b.distance - truth['d']:+.2f} m vs true" if (truth and b.found and truth['cls'] != 'matched') else None,
                        delta_color="off")
            if out["ml"]:
                mr = out["ml"].get(best, {})
                c[1].metric(f"ML distance ({best})", f"{mr.get('d', float('nan')):.2f} m",
                            f"{mr['d'] - truth['d']:+.2f} m vs true" if (truth and truth['cls'] != 'matched' and 'd' in mr) else None,
                            delta_color="off")
                mc = out["ml"].get(best_c, {})
                c[2].metric(f"ML class ({best_c})", mc.get("cls", "-"), f"{max(mc.get('proba', {0: 0}).values()):.0%} confidence",
                            delta_color="off")
            c[3].metric("Baseline class / Gamma", f"{b.cls}", f"Gamma ~ {b.gamma_est:+.2f}" if b.found else None, delta_color="off")
            if truth:
                c[4].metric("Ground truth", f"{truth['d']:.2f} m", f"{truth['cls']}" + (f", Gamma {truth['gamma']:+.2f}" if truth.get("gamma") is not None else ""),
                            delta_color="off")
            if out["ml"] and out["ml"].get(best_c, {}).get("cls") == "matched":
                st.caption("The classifier reports a matched line: the distance estimate has no physical meaning in that case.")

            # waveform
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=pr.t * 1e9, y=pr.v, name="normalised trace", line=dict(color=GRAY, width=1),
                                     hovertemplate="%{x:.1f} ns, %{y:.3f}<extra></extra>"))
            fig.add_trace(go.Scatter(x=pr.t * 1e9, y=pr.v_smooth, name="denoised", line=dict(color=BLUE, width=2),
                                     hovertemplate="%{x:.1f} ns, %{y:.3f}<extra></extra>"))
            ymax = float(np.nanmax(pr.v_smooth)) + 0.15
            marks = [("incident edge", 0.0, INK, "dot")]
            if b.found:
                marks.append(("baseline", b.dt + t_off, GRAY, "dash"))
            if out["ml"] and "dt" in out["ml"].get(best, {}):
                marks.append((f"ML {best}", out["ml"][best]["dt"] + t_off, ORANGE, "dash"))
            if truth and truth["cls"] != "matched":
                marks.append(("true", truth["dt"] + t_off, INK, "solid"))
            for i, (name, tt, col, dash) in enumerate(marks):
                fig.add_vline(x=tt * 1e9, line=dict(color=col, dash=dash, width=1.5))
                fig.add_annotation(x=tt * 1e9, y=ymax - 0.12 * i, text=name, showarrow=False, xanchor="left",
                                   font=dict(size=11, color=col), bgcolor="rgba(0,0,0,0)")
            tmax = min(float(pr.t[-1]) * 1e9, max(60.0, 1.5 * (truth["dt"] if truth else (b.dt if b.found else 1e-7)) * 1e9 + 30))
            fig.update_layout(height=430, margin=dict(l=10, r=10, t=40, b=10), hovermode="x unified",
                              xaxis=dict(title="time after incident edge (ns)", range=[-15, tmax]),
                              yaxis=dict(title="V / V_inc"),
                              legend=dict(orientation="h", y=1.08, x=0),
                              title=dict(text=f"Distance axis: d = vp * t / 2  (1 ns = {vp * 0.5e-9 * 100:.1f} cm)", font=dict(size=12)))
            st.plotly_chart(fig, width="stretch")

            # all methods
            rows = [{"method": mname("Baseline"), "dt (ns)": b.dt * 1e9 if b.found else np.nan,
                     "distance (m)": b.distance if b.found else np.nan, "class": b.cls, "confidence": np.nan}]
            for k in ALL_KEYS:
                if k in out["ml"]:
                    r = out["ml"][k]
                    rows.append({"method": mname(k), "dt (ns)": r.get("dt", np.nan) * 1e9, "distance (m)": r.get("d", np.nan),
                                 "class": r.get("cls", "-"), "confidence": max(r.get("proba", {0: np.nan}).values())})
            tab = pd.DataFrame(rows)
            if truth and truth["cls"] != "matched":
                tab["error (m)"] = tab["distance (m)"] - truth["d"]
            st.dataframe(tab.style.format({c_: "{:.3f}" for c_ in tab.columns if c_ not in ("method", "class")}, na_rep="-"),
                         hide_index=True, width="stretch")
            with st.expander("Details: preprocessing, Method B features, Method A input"):
                st.write(f"V_inc = {pr.v_inc:.4g} V, baseline = {pr.baseline:.4g} V, noise sigma = {pr.noise_sigma:.4f} (normalised), "
                         f"incident rise ~ {pr.rise_inc * 1e9:.2f} ns, Ts = {pr.ts * 1e9:.3g} ns. "
                         f"{b.note}")
                if "features" in out:
                    st.dataframe(pd.DataFrame([out["features"]]).T.rename(columns={0: "value"}), width="stretch")
                    g = go.Figure(go.Scatter(x=bundle["grid_t"] * 1e9, y=out["grid"], line=dict(color=BLUE, width=2)))
                    g.update_layout(height=250, margin=dict(l=10, r=10, t=30, b=10), title="Method A input (256 samples)",
                                    xaxis_title="ns", yaxis_title="V / V_inc")
                    st.plotly_chart(g, width="stretch")

with tab_cmp:
    if "e1_snr_sweep" not in res:
        st.info("No evaluation results yet. Run `python index.py evaluate`.")
    else:
        s = res["summary"]
        st.caption(f"Results from {s.get('created', '?')}. E3/E4 data: {s.get('e3_e4_data', '?')}.")
        e1 = res["e1_snr_sweep"]
        plot_keys = s.get("plot_keys") or ["Baseline"] + [k for k in ALL_KEYS if k in set(e1.method)]
        st.caption("Charts show the baseline and each model family on its better input; the tables list every model.")
        c1, c2 = st.columns(2)
        for col, ycol, title, ylab in ((c1, "MAE_m_on_base_detected", "E1: distance error vs SNR (same traces for all)", "MAE (m)"),
                                       (c2, "coverage", "Share of faulty traces given a distance", "share")):
            f = go.Figure()
            for k in plot_keys:
                sub = e1[e1.method == k].sort_values("snr_db")
                colr, dash = mstyle(k)
                f.add_trace(go.Scatter(x=sub.snr_db, y=sub[ycol], name=mname(k), mode="lines+markers",
                                       line=dict(color=colr, dash=dash, width=2), marker=dict(size=8)))
            f.update_layout(title=title, height=380, xaxis_title="SNR (dB)", yaxis_title=ylab, hovermode="x unified",
                            margin=dict(l=10, r=10, t=50, b=10), legend=dict(orientation="v", x=1.02, xanchor="left", y=1, yanchor="top"))
            col.plotly_chart(f, width="stretch")
        if "e5_soft_faults" in res:
            e5 = res["e5_soft_faults"]
            f = go.Figure()
            for k in plot_keys:
                sub = e5[e5.method == k].sort_values("gamma_abs")
                colr, dash = mstyle(k)
                f.add_trace(go.Scatter(x=sub.gamma_abs, y=sub.detection_rate, name=mname(k), mode="lines+markers",
                                       line=dict(color=colr, dash=dash, width=2), marker=dict(size=8)))
            f.update_layout(title="E5: soft faults detected at 30 dB", height=360, xaxis_type="log",
                            xaxis_title="|Gamma|", yaxis_title="detection rate", hovermode="x unified",
                            margin=dict(l=10, r=10, t=50, b=10), legend=dict(orientation="v", x=1.02, xanchor="left", y=1, yanchor="top"))
            st.plotly_chart(f, width="stretch")
        st.subheader("Mixed test set")
        if "mixed_regression" in res:
            st.dataframe(res["mixed_regression"].drop(columns=["experiment"]).round(3), hide_index=True, width="stretch")
        if "classification" in res:
            st.dataframe(res["classification"].drop(columns=["experiment"]).round(3), hide_index=True, width="stretch")
        st.subheader("Report figures")
        figs = sorted(FIG_DIR.glob("fig*.png"))
        for i in range(0, len(figs), 2):
            cols = st.columns(2)
            for colm, fp in zip(cols, figs[i:i + 2]):
                colm.image(str(fp), caption=fp.stem, width="stretch")

with tab_cal:
    st.subheader("Calibration")
    if cal["calibrated"]:
        k = st.columns(4)
        k[0].metric("vp", f"{cal['vp_m_per_s']:.4e} m/s", f"VF {cal.get('velocity_factor', 0):.3f}", delta_color="off")
        k[1].metric("Rise time", f"{cal.get('rise_time_s', 0) * 1e9:.2f} ns")
        k[2].metric("Resolution vp*t_r/2", f"{cal.get('resolution_m', 0):.3f} m")
        k[3].metric("Fixture offset", f"{cal.get('t_offset_s', 0) * 1e9:.2f} ns")
        st.json(cal, expanded=False)
    else:
        st.info("No data/calibration.json yet. Capture 20 open-circuit traces on two cable lengths, then run "
                "`python index.py calibrate`. Until then the datasheet vp of the selected cable is used.")
        st.write(f"Datasheet {cable}: Z0 = {preset.z0:.0f} ohm, VF = {preset.vf}, vp = {preset.vp:.4e} m/s, "
                 f"loss {preset.db100m_100mhz} dB/100 m at 100 MHz.")
    if cal["calibrated"] and (FIG_DIR / "fig0_calibration.png").exists():
        st.image(str(FIG_DIR / "fig0_calibration.png"), width=520)
    st.subheader("Lab log")
    if LAB_LOG.exists():
        st.dataframe(pd.read_csv(LAB_LOG), width="stretch")
    else:
        st.caption(f"{LAB_LOG.relative_to(HOME)} does not exist yet (created by `python index.py capture`).")

with tab_phys:
    st.subheader("Reflection coefficient")
    cA, cB = st.columns(2)
    z0 = cA.number_input("Z0 (ohm)", 1.0, 300.0, float(preset.z0))
    zl_txt = cA.text_input("ZL (ohm, or 'inf' for open)", "100")
    try:
        zl = float("inf") if zl_txt.strip().lower() in ("inf", "open") else float(zl_txt)
        g = 1.0 if np.isinf(zl) else (zl - z0) / (zl + z0)
        cB.metric("Gamma = (ZL - Z0) / (ZL + Z0)", f"{g:+.3f}")
        cB.metric("Final level V / V_inc = 1 + Gamma", f"{1 + g:.3f}")
    except (ValueError, ZeroDivisionError):
        cB.error("ZL must be a number or 'inf' (and ZL = -Z0 has no meaning)")
        g = 0.0
    st.subheader("Bounce (lattice) diagram")
    cC, cD = st.columns([1, 2])
    L = cC.number_input("Line length (m)", 0.5, 50.0, 5.0)
    rs = cC.number_input("Source resistance Rs (ohm)", 0.0, 500.0, 50.0)
    nb = cC.slider("Bounces", 1, 8, 4)
    gs = (rs - z0) / (rs + z0)
    tr = L / vp * 1e9
    f = go.Figure()
    amp, x0, t0 = 1.0, 0.0, 0.0
    for k in range(nb * 2):
        x1 = L if x0 == 0 else 0.0
        f.add_trace(go.Scatter(x=[x0, x1], y=[t0, t0 + tr], mode="lines", line=dict(color=BLUE if x1 == L else ORANGE, width=2),
                               showlegend=False, hovertemplate=f"wave amplitude {amp:+.3f} V_inc<extra></extra>"))
        f.add_annotation(x=(x0 + x1) / 2, y=t0 + tr / 2, text=f"{amp:+.3f}", showarrow=False, font=dict(size=11),
                         xshift=14)
        amp *= g if x1 == L else gs
        x0, t0 = x1, t0 + tr
        if abs(amp) < 1e-3:
            break
    f.update_layout(height=420, xaxis_title="position (m): tee at 0, load at L", yaxis_title="time (ns)",
                    yaxis_autorange="reversed", margin=dict(l=10, r=10, t=20, b=10))
    cD.plotly_chart(f, width="stretch")
    cC.caption(f"Gamma_source = {gs:+.3f}, Gamma_load = {g:+.3f}. Round trip 2L/vp = {2 * tr:.2f} ns. "
               f"With Rs = Z0 the source absorbs the first reflection and only one bounce is seen.")
    st.latex(r"d = \frac{v_p\,\Delta t}{2}\qquad \Gamma=\frac{Z_L-Z_0}{Z_L+Z_0}\qquad \Delta d_{min}\approx\frac{v_p\,t_r}{2}")


with tab_real:
    st.subheader("Real measured traces from the literature")
    st.caption("Scarpetta et al. 2021, doi:10.5281/zenodo.5720438 (CC BY 4.0): pulse TDR on RG-58, 1M simulated "
               "and 16 measured traces with capacitive faults. Models are trained on the simulated traces only; "
               "the 16 real traces are never seen in training. Targets: distance to the first discontinuity, "
               "cable length, and class of the first discontinuity.")
    zres = {k: res.get(k) for k in ("zenodo_z1_heldout_sim", "zenodo_z2_noise", "zenodo_z3_real", "zenodo_z3_real_per_trace")}
    if zres["zenodo_z3_real_per_trace"] is None:
        st.info("No Zenodo results yet. Run `python index.py zenodo all` (downloads 4.18 GB on first use).")
    else:
        per = zres["zenodo_z3_real_per_trace"]
        keys = [k for k in ["Baseline"] + ALL_KEYS if f"{k}_d_first" in per]
        i = st.slider("Real trace #", 0, len(per) - 1, 12)
        try:
            from src import zenodo as Z

            @st.cache_data
            def _real():
                X, lab = Z.real_traces()
                _, s0 = Z.load_baseline()
                return Z.preprocess_real(X, s0), lab, Z.load_baseline()[0].lin["open"]

            Xr, labr, (a_, b_) = _real()
            dist = a_ * np.arange(Xr.shape[1]) + b_
            f = go.Figure(go.Scatter(x=dist, y=Xr[i], line=dict(color=BLUE, width=1.5), name="measured trace",
                                     hovertemplate="%{x:.1f} m, %{y:.4f}<extra></extra>"))
            f.add_vline(x=per.d_first[i], line=dict(color=INK, dash="dot"))
            f.add_vline(x=per.length[i], line=dict(color=INK, dash="dash"))
            for k in keys:
                colr, dash = mstyle(k)
                f.add_trace(go.Scatter(x=[per[f"{k}_d_first"][i], per[f"{k}_length"][i]], y=[0, 0], mode="markers",
                                       marker=dict(color=colr, size=11, symbol="triangle-up"), name=mname(k),
                                       hovertemplate=f"{k}: %{{x:.1f}} m<extra></extra>"))
            f.update_layout(height=380, xaxis=dict(title="distance from the TDR (m)", range=[-5, 170]),
                            yaxis_title="amplitude", margin=dict(l=10, r=10, t=40, b=10),
                            title=dict(text=f"Faults at {per.positions[i]} m, cable {per.length[i]:.0f} m "
                                            "(dotted: first discontinuity, dashed: open end; triangles: predictions)",
                                       font=dict(size=12)), legend=dict(orientation="v", x=1.02, xanchor="left", y=1, yanchor="top"))
            st.plotly_chart(f, width="stretch")
        except Exception as exc:
            st.warning(f"Trace view unavailable: {exc}")
        rows = []
        for k in keys:
            rows.append({"method": mname(k), "first discontinuity (m)": per[f"{k}_d_first"][i],
                         "error (m)": per[f"{k}_d_first"][i] - per.d_first[i],
                         "cable length (m)": per[f"{k}_length"][i], "length error (m)": per[f"{k}_length"][i] - per.length[i]})
        st.dataframe(pd.DataFrame(rows).round(2), hide_index=True, width="stretch")
        for name, title in (("zenodo_z3_real", "Z3: all 16 real traces"), ("zenodo_z1_heldout_sim", "Z1: 20,000 held-out simulated traces"),
                            ("zenodo_z2_noise", "Z2: noise sweep")):
            if zres[name] is not None:
                st.markdown(f"**{title}**")
                st.dataframe(zres[name].drop(columns=["experiment"], errors="ignore").round(3), hide_index=True, width="stretch")
        for fp in sorted(FIG_DIR.glob("zfig*.png")):
            st.image(str(fp), caption=fp.stem, width="stretch")
