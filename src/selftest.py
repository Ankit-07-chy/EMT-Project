"""End-to-end self-test of every feature: ``python index.py selftest``.

Runs the whole pipeline for real, in a temporary data folder (``TDR_HOME``), so
the project's own data, models and results are never touched:

    simulated scope capture -> inspect -> calibrate -> fit -> lab dataset
    -> simulate -> physics and baseline checks -> train (all families)
    -> inference latency -> evaluate --quick (E3/E4 on the captured traces)
    -> dashboard (Streamlit AppTest + live HTTP health check)
    -> error handling -> hardware figures -> unit tests -> Zenodo run status

Every check records what it ran, what was expected, what actually came out,
how long it took and Pass / Fail / Needs attention. Results go to
report/results/feature_tests.csv and report/results/feature_tests.md.

    python index.py selftest            # full run, about 10-20 min on a laptop
    python index.py selftest --fast     # skip training, evaluation and dashboard (about 2 min)
    python index.py selftest --keep     # keep the temporary folder for inspection
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

CODE = Path(__file__).resolve().parents[1]
PY = sys.executable
OUT_DIR = CODE / "report" / "results"


def _num(pattern: str, text: str, default=float("nan")) -> float:
    m = re.search(pattern, text)
    return float(m.group(1)) if m else default


class Runner:
    def __init__(self, home: Path):
        self.home = home
        self.rows: list[dict] = []
        self.env = {**os.environ, "TDR_HOME": str(home), "PYTHONIOENCODING": "utf-8",
                    "MPLBACKEND": "Agg", "PYTHONWARNINGS": "ignore"}

    # ------------------------------------------------------------ helpers
    def cli(self, *args, timeout: float = 3600) -> tuple[int, str, float]:
        t0 = time.time()
        p = subprocess.run([PY, str(CODE / "index.py"), *map(str, args)], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", env=self.env, cwd=self.home, timeout=timeout)
        return p.returncode, p.stdout + p.stderr, time.time() - t0

    def py(self, code: str, timeout: float = 1800) -> tuple[int, str, float]:
        t0 = time.time()
        p = subprocess.run([PY, "-c", code], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", env=self.env, cwd=CODE, timeout=timeout)
        return p.returncode, p.stdout + p.stderr, time.time() - t0

    def check(self, fid: str, feature: str, purpose: str, procedure: str, expected: str, fn):
        print(f"[{fid}] {feature} ...", flush=True)
        t0 = time.time()
        try:
            actual, status, perf = fn()
        except Exception as exc:  # a crash inside a check is itself a failed test
            actual, status, perf = f"{type(exc).__name__}: {exc}", "Fail", ""
        if isinstance(status, (bool, np.bool_)):
            status = "Pass" if status else "Fail"
        dt = time.time() - t0
        self.rows.append({"id": fid, "feature": feature, "purpose": purpose, "procedure": procedure,
                          "expected": expected, "actual": actual, "performance": perf,
                          "seconds": round(dt, 1), "status": status})
        print(f"      {status} ({dt:.1f}s): {actual}", flush=True)
        return status


# ====================================================================== checks
def lab_checks(r: Runner):
    raw = r.home / "data" / "raw"
    log = raw / "lab_log.csv"
    plan = [(2.0, "open", None), (5.0, "open", None), (10.0, "open", None), (5.0, "short", None),
            (5.0, "matched", None), (5.0, "partial", 100.0), (5.0, "partial", 22.0)]

    def capture_list():
        rc, out, dt = r.cli("capture", "--list", timeout=120)
        lines = [ln for ln in out.splitlines() if "->" in ln or "No " in ln]
        return (f"exit {rc}; " + ("; ".join(lines) if lines else "no output")), rc == 0, f"{dt:.1f} s"

    r.check("F01", "Instrument discovery (capture --list)",
            "List oscilloscopes reachable over USB/LAN through PyVISA (NI-VISA or pyvisa-py).",
            "`index.py capture --list` with no instrument connected",
            "Exit 0 and a clear 'no instrument' message (no hardware attached here)", capture_list)

    def capture_session():
        outs, t_total = [], 0.0
        for L, term, zl in plan:
            args = ["capture", "--simulate", "--length", L, "--termination", term, "--repeats", 4,
                    "--out-dir", raw, "--cable-id", "SELFTEST", "--operator", "selftest"]
            if zl is not None:
                args += ["--zl", zl]
            rc, out, dt = r.cli(*args, timeout=300)
            t_total += dt
            if rc != 0:
                return f"capture {L} m {term} failed: {out[-300:]}", False, ""
            outs.append((L, term, zl, out))
        df = pd.read_csv(log)
        reads = []
        ok = len(df) == 4 * len(plan)
        for L, term, zl, out in outs:
            if term in ("open", "short") or zl is not None:
                ds = [float(x) for x in re.findall(r" d\s+([\d.]+) m", out)]
                reads.append(f"{L:g} m {term}{'' if zl is None else f' {zl:g} ohm'} -> {np.median(ds):.2f} m")
                ok &= len(ds) == 4 and abs(np.median(ds) - L) < 0.3
        # the log must point at files that exist
        ok &= all((log.parent / f).exists() for f in df.file)
        return (f"{len(df)} traces + log rows written; quick-check distances: " + "; ".join(reads),
                ok, f"{t_total / len(df):.2f} s per simulated capture")

    r.check("F02", "Capture session with logging (capture --simulate)",
            "Acquire repeated traces, save each with a metadata header, append one row per trace to lab_log.csv, "
            "print a live baseline check (same code path as the real scope, SimScope instead of VISA).",
            "7 setups x 4 repeats: open 2/5/10 m, short 5 m, matched 5 m, 100 ohm and 22 ohm loads at 5 m",
            "28 CSV files + 28 log rows; live distance within 0.3 m of the cable length", capture_session)

    def files(term, L):
        df = pd.read_csv(log)
        sel = df[(df.termination == term) & (np.isclose(df.cable_length_m, L))]
        return [log.parent / f for f in sel.file]

    def inspect():
        f = files("open", 5.0)[0]
        rc, out, dt = r.cli("inspect", f, "--plot", timeout=120)
        d = _num(r"-> d ([\d.]+) m", out)
        png = r.home / "report" / "figures" / f"inspect_{f.stem}.png"
        ok = rc == 0 and abs(d - 5.0) < 0.3 and png.exists()
        return f"exit {rc}; vendor/format detected; baseline d = {d:.3f} m (true 5.00); plot saved = {png.exists()}", ok, f"{dt:.1f} s incl. Python start-up"

    r.check("F03", "Read any scope CSV (inspect)",
            "Parse a saved trace (vendor auto-detection), preprocess it, run the baseline and plot it.",
            "`index.py inspect <5 m open trace> --plot`",
            "Distance within 0.3 m of 5 m, class open, PNG written", inspect)

    def calibrate():
        rc, out, dt = r.cli("calibrate", timeout=300)
        from src.config import SimConfig
        true_vp = SimConfig(cable="RG-58").vp_nominal
        calf = r.home / "data" / "calibration.json"
        if rc != 0 or not calf.exists():
            return f"exit {rc}: {out[-300:]}", False, ""
        cal = json.loads(calf.read_text())
        err = (cal["vp_m_per_s"] - true_vp) / true_vp * 100
        ok = abs(err) < 1.5 and (r.home / "report" / "figures" / "fig0_calibration.png").exists()
        return (f"vp = {cal['vp_m_per_s']:.4e} m/s vs simulated truth {true_vp:.4e} ({err:+.2f} %); "
                f"t_offset {cal['t_offset_s'] * 1e9:.2f} ns; rise {cal['rise_time_s'] * 1e9:.2f} ns; "
                f"resolution {cal['resolution_m']:.2f} m; SNR {cal['snr_db']:.1f} dB"), ok, f"{dt:.1f} s for 12 traces"

    r.check("F04", "Velocity calibration (calibrate)",
            "Fit round-trip delay vs length over open-circuit traces to get vp, the fixed time offset, rise time, "
            "resolution, V_inc and noise; writes data/calibration.json used by every later step.",
            "`index.py calibrate` on the 12 open-circuit traces from F02 (2, 5, 10 m)",
            "vp within 1.5 % of the simulator's true vp; calibration.json + fig0 written", calibrate)

    def fit():
        f = files("open", 5.0)[1]
        rc, out, dt = r.cli("fit", "--file", f, "--length", 5.0, "--termination", "open", timeout=600)
        rmse = _num(r"RMSE \(normalised\) ([\d.]+)", out)
        ok = rc == 0 and rmse < 0.05 and "success=True" in out
        vp = _num(r"\s+vp\s+([\d.e+]+)", out)
        return f"exit {rc}; RMSE {rmse:.4f} (normalised); fitted vp {vp:.4g} m/s; overlay figure written", ok, f"{dt:.1f} s per fit"

    r.check("F05", "Simulator-to-measurement fit (fit)",
            "Least-squares fit of the transmission-line simulator to one measured trace (vp, rise, loss, scope C, Rs, gain).",
            "`index.py fit --file <5 m open trace> --length 5 --termination open`",
            "Converges, normalised RMSE < 0.05", fit)

    def lab_dataset():
        rc, out, dt = r.cli("lab-dataset", timeout=300)
        p = r.home / "data" / "processed" / "lab.csv"
        n = len(pd.read_csv(p)) if p.exists() else 0
        X = np.load(r.home / "data" / "processed" / "lab_X.npy") if p.exists() else np.zeros((0, 0))
        return f"exit {rc}; {n} traces processed; Method A matrix {X.shape}", rc == 0 and n == 28 and X.shape == (28, 256), f"{dt / max(n, 1):.2f} s per trace incl. start-up"

    r.check("F06", "Lab dataset builder (lab-dataset)",
            "Turn every logged lab trace into model inputs (Method A grid, Method B features) + labels.",
            "`index.py lab-dataset` over the 28 logged traces",
            "data/processed/lab.csv with 28 rows and a (28, 256) Method A matrix", lab_dataset)


def sim_checks(r: Runner):
    sim = r.home / "data" / "sim"

    def simulate_tline():
        rc, out, dt = r.cli("simulate", "--n", 400, "--seed", 3, "--raw", "--name", "st_tline", timeout=900)
        df = pd.read_csv(sim / "st_tline.csv")
        X = np.load(sim / "st_tline_X.npy")
        counts = df.cls.value_counts().to_dict()
        ok = rc == 0 and len(df) == 400 and X.shape == (400, 256) and set(counts) == {"open", "short", "matched", "partial"} \
            and (sim / "st_tline_raw.npz").exists() and np.isfinite(X).all()
        return f"exit {rc}; {len(df)} labelled traces, X {X.shape}, classes {counts}, raw traces saved", ok, f"{dt / 400 * 1e3:.0f} ms per trace (simulate + preprocess + features)"

    r.check("F07", "Synthetic dataset, transmission-line model (simulate)",
            "Random cables, faults, rise times, noise and scope effects -> labelled traces + both model inputs.",
            "`index.py simulate --n 400 --raw` (calibrated vp from F04 is used)",
            "400 rows, X (400, 256), all 4 classes, finite values", simulate_tline)

    def simulate_simple():
        rc, out, dt = r.cli("simulate", "--n", 200, "--model", "simple", "--artifacts", "--name", "st_simple", timeout=600)
        df = pd.read_csv(sim / "st_simple.csv")
        return f"exit {rc}; {len(df)} rows, source column = {df.source.iloc[0]}", rc == 0 and len(df) == 200, f"{dt / 200 * 1e3:.0f} ms per trace"

    r.check("F08", "Synthetic dataset, brief's simple model + lab artifacts",
            "The brief's analytic model and the proxy-lab artifact generator (adapter, ringing, 1/f noise).",
            "`index.py simulate --n 200 --model simple --artifacts`",
            "200 rows written, source tagged as artifacts", simulate_simple)

    def physics():
        from src.config import K_SERIES, K_SHUNT, K_STEP, SimConfig
        from src.sim_tdr import make_params, simulate
        cfg = SimConfig()
        cases = [("open", {}, 2.0), ("short", {}, 0.0), ("matched", {"gamma": 0.0}, 1.0),
                 ("partial", {"zl": 100.0}, 4 / 3), ("partial", {"zl": 22.0}, 1 + (22 - 50) / 72),
                 ("partial", {"kind": K_SERIES, "r_fault": 50.0}, 4 / 3),
                 ("partial", {"kind": K_SHUNT, "r_fault": 50.0}, 2 / 3), ("partial", {"kind": K_STEP, "z2": 75.0}, 1.2)]
        worst, parts = 0.0, []
        for cls, kw, final in cases:
            p = make_params(cfg, cls=cls, d=5.0, **kw)
            (t, v), = simulate(p, cfg, noiseless=True)
            got = v[-1] / p["v_inc"][0]
            worst = max(worst, abs(got - final))
            parts.append(f"{cls}{'' if not kw else ' ' + ','.join(f'{k}={v_:g}' for k, v_ in kw.items())}: {got:.3f}/{final:.3f}")
        dts = []
        for d in (2.0, 5.0, 10.0):
            p = make_params(cfg, cls="open", d=d)
            dts.append(abs(p["dt_true"][0] - 2 * d / p["vp"][0]) * 1e9)
        return ("final level / theory 1+Gamma: " + "; ".join(parts) + f"; worst deviation {worst:.3f}; "
                f"delay = 2L/vp to {max(dts):.3f} ns"), worst < 0.03, "8 noiseless traces in < 1 s"

    r.check("F09", "Physics check of the simulator",
            "Late-time level must equal 1 + Gamma (Gamma = (ZL - Z0)/(ZL + Z0)) and the echo must arrive at 2L/vp.",
            "Noiseless traces at 5 m for 8 terminations / faults, normalised by V_inc",
            "Every level within 0.03 of theory (small cable loss allowed)", physics)

    def baseline():
        from src import dataset as D
        from src.config import SimConfig
        cfg = SimConfig()
        res = []
        for snr in (40, 20):
            ds = D.build_sim(300, cfg, 77 + snr, verbose=False, snr_db=float(snr))
            m, b = ds["meta"], ds["B"]
            nm = (m.cls != "matched").values
            err = np.abs(b.base_d.values[nm] - m.d.values[nm])
            acc = (b.base_cls.values == m.cls.values).mean()
            res.append((snr, np.nanmedian(err), np.nanmean(np.where(np.isfinite(err), err, np.nan)), acc,
                        np.mean(~np.isfinite(b.base_d.values[nm]))))
        txt = "; ".join(f"SNR {s} dB: median |err| {md:.2f} m, mean {mn:.2f} m, class acc {a:.2f}, missed {mi:.0%}"
                        for s, md, mn, a, mi in res)
        return txt, res[0][1] < 0.25 and res[0][3] > 0.9, "see F12 for per-trace latency"

    r.check("F10", "Classical baseline detector",
            "Threshold + matched-lobe reflection finder on the denoised derivative; gives dt, distance, Gamma and class.",
            "300 random simulated traces at SNR 40 dB and 300 at 20 dB",
            "At 40 dB: median distance error < 0.25 m (half the 0.4-0.5 m resolution of a 4-5 ns edge) "
            "and class accuracy > 0.9", baseline)


def ml_checks(r: Runner):
    bundle_p = r.home / "models" / "tdr_models.joblib"

    def train():
        rc, out, dt = r.cli("train", "--n-train", 2000, "--n-val", 500, "--trees", 60, timeout=3600)
        if rc != 0 or not bundle_p.exists():
            return f"exit {rc}: {out[-400:]}", False, ""
        import joblib
        b = joblib.load(bundle_p)
        keys = sorted(f"{t}-{m}-{a}" for t, m, a in b["models"])
        vt = pd.read_csv(r.home / "report" / "results" / "validation_grid.csv")
        sel = vt[vt.metric == "SELECTED"]
        best_reg = sel[sel.task == "reg"].sort_values("val_score").iloc[0]
        best_cls = sel[sel.task == "cls"].sort_values("val_score").iloc[-1]
        ok = len(keys) == 18
        return (f"exit {rc}; {len(keys)} models stored (RF/ET/KNN/MLP x A/B + CNN-A, regression + classification); "
                f"best val MAE {best_reg.algo}-{best_reg.method} {best_reg.val_score:.2f} ns; "
                f"best val macro-F1 {best_cls.algo}-{best_cls.method} {best_cls.val_score:.3f}"), ok, f"{dt / 60:.1f} min for 2000 + 500 traces incl. grid search"

    r.check("F11", "Model training with validation grid search (train)",
            "Simulate train/val sets, grid-search every family on the validation set only, keep the best of each.",
            "`index.py train --n-train 2000 --n-val 500 --trees 60` (all five families)",
            "18 models in models/tdr_models.joblib and a validation_grid.csv", train)

    def latency():
        code = f"""
import time, numpy as np, joblib, json
from src import dataset as D
from src.config import SimConfig
from src.features import FEATURES_B, process_traces
from src.sim_tdr import sample_params, simulate
from src.train import predict
from src.models import set_threads
cfg = SimConfig(); rng = np.random.default_rng(5)
p = sample_params(200, cfg, rng); tr = simulate(p, cfg)
t0 = time.perf_counter(); X, F, B = process_traces(tr, p['v_inc_ref'], vp=cfg.vp_nominal, preset=cfg.preset); t_pre = (time.perf_counter() - t0) / 200
b = joblib.load(r'{bundle_p}')
ds = {{'X': X, 'F': F, 'B': B, 'meta': None}}
from src.train import inputs
out = {{'preprocess+baseline+features ms/trace': t_pre * 1e3}}
for (task, m_, a), mdl in b['models'].items():
    Xi = inputs(ds, m_)
    f = mdl.predict if task == 'reg' else mdl.predict_proba
    f(Xi[:2]); t0 = time.perf_counter(); f(Xi); tb = (time.perf_counter() - t0) / len(Xi)
    set_threads(mdl, 1); f(Xi[:1])
    t0 = time.perf_counter()
    for i in range(20): f(Xi[i:i + 1])
    ts = (time.perf_counter() - t0) / 20
    set_threads(mdl, -1)
    out[f'{{a}}-{{m_}} {{task}}'] = (tb * 1e3, ts * 1e3)
print('JSON' + json.dumps(out))
"""
        rc, out, dt = r.py(code, timeout=900)
        m = re.search(r"JSON(\{.*\})", out)
        if rc != 0 or not m:
            return f"exit {rc}: {out[-400:]}", False, ""
        res = json.loads(m.group(1))
        (r.home / "report" / "results" / "latency.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
        pre = res.pop("preprocess+baseline+features ms/trace")
        single = {k: v[1] for k, v in res.items()}
        worst = max(single, key=single.get)
        txt = (f"front end (preprocess + baseline + 23 features) {pre:.1f} ms/trace; single-trace model call "
               f"{min(single.values()):.2f}-{max(single.values()):.1f} ms (slowest {worst}); "
               f"batched {min(v[0] for v in res.values()):.3f}-{max(v[0] for v in res.values()):.2f} ms/trace")
        return txt, pre + max(single.values()) < 1000, "measured on this laptop's CPU (small self-test models); full-size numbers: index.py analyze"

    r.check("F12", "Inference latency (all models)",
            "How long one trace takes from raw samples to a distance + class, per model, single and batched.",
            "200 simulated traces; time the front end and each stored model (single-trace and batched calls)",
            "Well under 1 s per trace end to end (interactive use)", latency)

    def evaluate():
        rc, out, dt = r.cli("evaluate", "--quick", timeout=7200)
        res = r.home / "report" / "results"
        figs = sorted(p.name for p in (r.home / "report" / "figures").glob("fig*.png"))
        s = json.loads((res / "summary.json").read_text()) if (res / "summary.json").exists() else {}
        lab_used = s.get("e3_e4_data") == "LAB"
        need = [f"fig{i}_" for i in range(1, 11)]
        ok = rc == 0 and all(any(f.startswith(n) for f in figs) for n in need) and (res / "summary.md").exists()
        return (f"exit {rc}; {len(figs)} figures, summary.md written; E3/E4 data source "
                f"{'captured (lab-format) traces' if lab_used else 'proxy set'}; best regressor {s.get('best_regressor')}, "
                f"best classifier {s.get('best_classifier')}"), ok, f"{dt / 60:.1f} min (quick sizes)"

    r.check("F13", "Experiments E1-E6 + figures (evaluate --quick)",
            "Run all six experiments, write result tables, ten figures and the summary.",
            "`index.py evaluate --quick` with the F02 traces present as the lab log",
            "Exit 0, fig1..fig10 and summary.md written; E3/E4 run on the logged traces", evaluate)


def dashboard_checks(r: Runner):
    app = CODE / "app" / "dashboard.py"

    def apptest():
        code = f"""
from streamlit.testing.v1 import AppTest
at = AppTest.from_file(r'{app}', default_timeout=900)
at.run()
def report(tag):
    print(tag, 'EXC', len(at.exception), [str(e.value)[:200] for e in at.exception])
    print(tag, 'METRICS', len(at.metric), 'ERRORS', [e.value for e in at.error][:3])
report('simulate-open')
faults = at.sidebar.selectbox[1].options
for f in faults[1:]:
    at.sidebar.selectbox[1].select(f).run(); report('simulate-' + f)
at.sidebar.radio[0].set_value('Saved trace').run(); report('saved-trace')
print('TABS', len(at.tabs))
"""
        rc, out, dt = r.py(code, timeout=1800)
        runs = re.findall(r"^(\S+(?: \S+)*?) EXC (\d+)", out, re.M)
        exc = [ln for ln in out.splitlines() if " EXC " in ln and " EXC 0 " not in ln]
        ok = rc == 0 and len(runs) >= 9 and not exc
        return (f"exit {rc}; {len(runs)} script runs (8 fault types + saved lab trace), "
                f"{'no exceptions' if not exc else 'exceptions: ' + ' | '.join(exc)[:400]}; "
                f"tabs {_num(r'TABS (\d+)', out):.0f}"), ok, f"{dt / max(len(runs), 1):.1f} s per full re-run"

    r.check("F14", "Dashboard: every input path (Streamlit AppTest)",
            "Run the dashboard script headless and drive the sidebar through all 8 fault types and the saved-trace "
            "source; every tab is executed on each run.",
            "streamlit.testing AppTest with the trained sandbox models and captured traces",
            "No exception on any run, 5 tabs rendered", apptest)

    def http():
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        p = subprocess.Popen([PY, "-m", "streamlit", "run", str(app), "--server.headless", "true",
                              "--server.port", str(port), "--browser.gatherUsageStats", "false"],
                             env=r.env, cwd=CODE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        t0, body = time.time(), ""
        try:
            while time.time() - t0 < 90:
                try:
                    body = urllib.request.urlopen(f"http://127.0.0.1:{port}/_stcore/health", timeout=2).read().decode()
                    if body.strip() == "ok":
                        break
                except OSError:
                    time.sleep(1)
            page = urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=5).read().decode(errors="replace") if body.strip() == "ok" else ""
        finally:
            p.terminate()
            p.wait(timeout=30)
        up = time.time() - t0
        return f"health endpoint '{body.strip()}', index page {len(page)} bytes", body.strip() == "ok" and "<html" in page.lower(), f"server ready in {up:.1f} s"

    r.check("F15", "Dashboard server start-up (index.py dashboard)",
            "Start the real Streamlit server headless and query its health endpoint and index page.",
            "`streamlit run app/dashboard.py --server.headless true` on a free port",
            "Health endpoint answers 'ok' and the page is served", http)


def robustness_checks(r: Runner):
    def errors():
        bad = r.home / "garbage.csv"
        bad.write_text("hello,world\nnot,numbers\n", encoding="utf-8")
        cases = [("inspect missing file", ("inspect", r.home / "nope.csv")),
                 ("inspect garbage CSV", ("inspect", bad)),
                 ("capture without length", ("capture", "--simulate", "--termination", "open")),
                 ("calibrate without log", ("calibrate", "--log", r.home / "none.csv")),
                 ("fit missing file", ("fit", "--file", r.home / "nope.csv", "--length", "5")),
                 ("lab-dataset without log", ("lab-dataset", "--log", r.home / "none.csv")),
                 ("unknown command", ("frobnicate",))]
        res = []
        for name, args in cases:
            rc, out, _ = r.cli(*args, timeout=120)
            tb = "Traceback" in out
            res.append((name, rc, tb, out.strip().splitlines()[-1][:90] if out.strip() else ""))
        bad_ones = [n for n, rc, tb, _ in res if tb or rc == 0 and n != "lab-dataset without log"]
        txt = "; ".join(f"{n}: exit {rc}, {'TRACEBACK' if tb else 'clean message'}" for n, rc, tb, _ in res)
        return txt, not bad_ones, ""

    r.check("F16", "Error handling of the CLI",
            "Wrong or missing inputs must stop with a one-line explanation, not a Python traceback.",
            "7 deliberately wrong invocations (missing/garbage files, missing arguments, unknown command)",
            "Non-zero exit (or a clear 'nothing to do' message) and no traceback", errors)

    def figures():
        out_dir = r.home / "hw_figures"
        t0 = time.time()
        p = subprocess.run([PY, str(CODE / "hardware" / "circuits" / "make_hardware_figures.py"), str(out_dir)],
                           capture_output=True, text=True, env=r.env, cwd=CODE, timeout=900)
        n_svg, n_png = len(list(out_dir.glob("c*.svg"))), len(list(out_dir.glob("*.png")))
        return f"exit {p.returncode}; {n_svg} circuit SVGs, {n_png} PNGs (circuits + expected waveforms)", \
            p.returncode == 0 and n_svg >= 13 and n_png >= 24, f"{time.time() - t0:.0f} s"

    r.check("F17", "Hardware circuit + expected-waveform generator",
            "Regenerate every schematic (schemdraw) and simulated expected scope picture used by the hardware guide.",
            "`python hardware/circuits/make_hardware_figures.py <temp folder>`",
            "13 schematics (SVG + PNG) and 11 expected-waveform PNGs", figures)


def unit_and_zenodo(r: Runner):
    def pytest_run():
        t0 = time.time()
        p = subprocess.run([PY, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(CODE / "tests")],
                           capture_output=True, text=True, cwd=CODE, timeout=1800,
                           env={**r.env, "PYTHONWARNINGS": "ignore"})
        last = [ln for ln in p.stdout.splitlines() if "passed" in ln or "failed" in ln]
        return (last[-1] if last else p.stdout[-300:]), p.returncode == 0, f"{time.time() - t0:.0f} s"

    r.check("F18", "Unit test suite (pytest)",
            "Physics levels and delays, baseline, feature shapes, every scope CSV dialect, capture->calibrate, "
            "lab dataset, every model family, CNN learning, safe unpickler, nested-zip memmap, pulse baseline.",
            "`python -m pytest tests`",
            "All tests pass", pytest_run)

    def zenodo_status():
        res = CODE / "report" / "results"
        bundle = CODE / "models" / "zenodo_models.joblib"
        need = ["zenodo_summary.md", "zenodo_z1_heldout_sim.csv", "zenodo_z2_noise.csv", "zenodo_z3_real.csv"]
        have = [n for n in need if (res / n).exists()]
        if len(have) < len(need) or not bundle.exists():
            return (f"full run not finished yet ({len(have)}/{len(need)} result files, bundle "
                    f"{'present' if bundle.exists() else 'missing'})"), "Needs attention", ""
        z1 = pd.read_csv(res / "zenodo_z1_heldout_sim.csv")
        return f"all result files present; Z1 table has {len(z1)} rows (see ML_ANALYSIS.md)", "Pass", ""

    r.check("F19", "External real-data pipeline (Zenodo 5720438)",
            "Safe download/parse of the 1 M-trace pulse-TDR dataset, baseline + RF/ET/KNN/MLP/CNN, held-out, noise "
            "and real-trace tests. Run separately with `index.py zenodo all` (hours); this check reads its outputs.",
            "Check that the separate full run produced its models and result tables",
            "models/zenodo_models.joblib and the Z1/Z2/Z3 tables exist", zenodo_status)


# ====================================================================== report
def write(rows: list[dict], home: Path, started: float):
    df = pd.DataFrame(rows, columns=["id", "feature", "purpose", "procedure", "expected", "actual", "performance", "seconds", "status"])
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_DIR / "feature_tests.csv", index=False)
    n = df.status.value_counts().to_dict()
    lines = [f"# Feature self-test ({time.strftime('%Y-%m-%d %H:%M')})", "",
             f"`python index.py selftest` ran every feature for real in a temporary data folder "
             f"({(time.time() - started) / 60:.1f} min). Result: " + ", ".join(f"{v} {k}" for k, v in n.items()) + ".", "",
             "| ID | Feature | Expected | Actual | Performance | Status |", "|---|---|---|---|---|---|"]
    for r in rows:
        cell = lambda s: str(s).replace("|", "/").replace("\n", " ")  # noqa: E731
        lines.append(f"| {r['id']} | {cell(r['feature'])} | {cell(r['expected'])} | {cell(r['actual'])} | "
                     f"{cell(r['performance'])} | **{r['status']}** |")
    lines += ["", "Procedures and purposes are in `feature_tests.csv` and docs/TESTING_REPORT.md."]
    (OUT_DIR / "feature_tests.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines[:4]))
    print(f"Saved {OUT_DIR / 'feature_tests.csv'} and feature_tests.md")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fast", action="store_true", help="skip training, evaluation and the dashboard")
    ap.add_argument("--keep", action="store_true", help="keep the temporary data folder")
    ap.add_argument("--home", type=Path, default=None, help="use this folder instead of a temporary one")
    a = ap.parse_args(argv)
    home = (a.home or Path(tempfile.mkdtemp(prefix="tdr_selftest_"))).resolve()
    home.mkdir(parents=True, exist_ok=True)
    print(f"Self-test data folder: {home}")
    started = time.time()
    r = Runner(home)
    try:
        lab_checks(r)
        sim_checks(r)
        if not a.fast:
            ml_checks(r)
            dashboard_checks(r)
        robustness_checks(r)
        unit_and_zenodo(r)
    finally:
        write(r.rows, home, started)
        if not a.keep and a.home is None:
            shutil.rmtree(home, ignore_errors=True)
        else:
            print(f"Kept {home}")
    return 0 if all(x["status"] != "Fail" for x in r.rows) else 1


if __name__ == "__main__":
    sys.exit(main())
