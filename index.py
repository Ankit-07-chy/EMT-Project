"""TDR cable fault detection: one entry point for every step of the project.

    python index.py check                      environment, VISA, calibration and model status
    python index.py simulate --n 2000          build a labelled synthetic dataset (WP4)
    python index.py train                      simulate train/val sets and fit RF / ET (WP6)
    python index.py evaluate [--quick]         experiments E1-E6, tables and figures (WP7)
    python index.py analyze                    in-depth localization / detection / latency analysis (after evaluate)
    python index.py dashboard                  Streamlit dashboard (WP8)
    python index.py selftest [--fast]          run every feature end to end in a temp folder -> report/results/feature_tests.md

  external real data (Scarpetta et al. 2021, Zenodo 5720438, 4.18 GB)
    python index.py zenodo download|prepare|train|evaluate|all

  lab side
    python index.py capture --list             list oscilloscopes on USB / LAN
    python index.py capture --simulate ...     rehearse a capture session without hardware
    python index.py capture --length 5.02 --termination open --repeats 20 ...
    python index.py inspect <scope.csv>        read any scope CSV and run the baseline on it
    python index.py calibrate                  vp, offset, rise time, resolution -> data/calibration.json
    python index.py fit --file <csv> --length 5.02 --termination open
    python index.py lab-dataset                process every logged lab trace -> data/processed/lab.csv

Run any command with -h for its options. Set TDR_DEBUG=1 to see full Python tracebacks.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def cmd_check(_args):
    import importlib
    ok = True
    for pkg in ("numpy", "scipy", "pandas", "matplotlib", "sklearn", "joblib", "streamlit", "plotly", "pyvisa", "torch"):
        try:
            m = importlib.import_module(pkg)
            print(f"  [ok] {pkg} {getattr(m, '__version__', '')}")
        except ImportError:
            ok = False
            print(f"  [missing] {pkg}  -> pip install -r requirements.txt")
    try:
        import pyvisa
        for backend in ("", "@py"):
            try:
                rm = pyvisa.ResourceManager(backend)
                res = rm.list_resources()
                print(f"  [ok] VISA backend {backend or 'system (NI/Keysight)'}: {len(res)} resource(s) {res}")
            except Exception as exc:
                print(f"  [--] VISA backend {backend or 'system (NI/Keysight)'}: {type(exc).__name__}: {str(exc)[:80]}")
    except ImportError:
        pass
    from src.config import CALIBRATION_FILE, LAB_LOG, load_calibration
    from src.config import ROOT as HOME
    from src.train import DEFAULT_BUNDLE
    cal = load_calibration()
    print(f"  calibration: {'yes, vp = %.4e m/s' % cal['vp_m_per_s'] if cal['calibrated'] else 'not yet (' + str(CALIBRATION_FILE.relative_to(HOME)) + ')'}")
    print(f"  lab log    : {'yes' if LAB_LOG.exists() else 'not yet'} ({LAB_LOG.relative_to(HOME)})")
    print(f"  models     : {'yes' if DEFAULT_BUNDLE.exists() else 'not trained yet'} ({DEFAULT_BUNDLE.relative_to(HOME)})")
    return 0 if ok else 1


def cmd_simulate(argv):
    import argparse
    from src import dataset as D
    from src.config import sim_config_from_calibration
    ap = argparse.ArgumentParser(prog="index.py simulate")
    ap.add_argument("--n", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--name", default=None)
    ap.add_argument("--snr", type=float, default=None, help="fixed SNR in dB (default: random 10-40)")
    ap.add_argument("--model", choices=["tline", "simple"], default="tline")
    ap.add_argument("--artifacts", action="store_true", help="add lab-like artifacts")
    ap.add_argument("--raw", action="store_true", help="also store the raw traces")
    a = ap.parse_args(argv)
    cfg = sim_config_from_calibration(model=a.model, artifacts=a.artifacts)
    ds = D.build_sim(a.n, cfg, a.seed, keep_raw=a.raw, snr_db=a.snr)
    name = a.name or f"sim_{a.model}{'_art' if a.artifacts else ''}_{a.n}_s{a.seed}"
    print(f"Saved {D.save(ds, name)}")


def cmd_inspect(argv):
    import argparse
    from src.config import CABLES, FIG_DIR, load_calibration
    from src.features import process_one
    from src.scope_io import load_waveform
    ap = argparse.ArgumentParser(prog="index.py inspect")
    ap.add_argument("file", type=Path)
    ap.add_argument("--channel", default=None)
    ap.add_argument("--ts", type=float, default=None, help="sample interval (s) for voltage-only files")
    ap.add_argument("--plot", action="store_true", help="save a PNG of the processed trace")
    a = ap.parse_args(argv)
    wf = load_waveform(a.file, channel=a.channel, ts=a.ts)
    print(wf.summary())
    for k, v in list(wf.meta.items())[:12]:
        print(f"    {k}: {v}")
    cal = load_calibration()
    pr, b, _, _ = process_one(wf.t, wf.v, float(cal["vp_m_per_s"]), CABLES.get(cal["cable_type"]),
                              t_offset=float(cal.get("t_offset_s", 0)), cal=cal)
    if not pr.ok:
        print(f"  preprocess failed: {pr.msg}")
        return
    if pr.msg:
        print(f"  note: {pr.msg}")
    print(f"  V_inc {pr.v_inc:.4g} V, rise ~{pr.rise_inc * 1e9:.2f} ns, noise {pr.noise_sigma:.4f} (norm)")
    if b.found:
        print(f"  baseline: dt {b.dt * 1e9:.2f} ns -> d {b.distance:.3f} m, amp {b.amp:+.3f}, Gamma ~{b.gamma_est:+.2f}, class {b.cls}")
    else:
        print(f"  baseline: {b.note} -> class {b.cls}")
    if a.plot:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.plot(pr.t * 1e9, pr.v, color="#7a7975", lw=1, label="normalised")
        ax.plot(pr.t * 1e9, pr.v_smooth, color="#2a78d6", lw=2, label="denoised")
        if b.found:
            ax.axvline((b.dt + float(cal.get("t_offset_s", 0))) * 1e9, color="#eb6834", ls="--", label=f"reflection, d = {b.distance:.2f} m")
        ax.set(xlabel="time after incident edge (ns)", ylabel="V / V_inc", title=a.file.name)
        ax.legend(frameon=False)
        out = FIG_DIR / f"inspect_{a.file.stem}.png"
        fig.tight_layout()
        fig.savefig(out, dpi=130)
        print(f"  plot: {out}")


def cmd_lab_dataset(argv):
    import argparse
    from src import dataset as D
    from src.config import LAB_LOG, PROCESSED_DIR
    ap = argparse.ArgumentParser(prog="index.py lab-dataset")
    ap.add_argument("--log", type=Path, default=LAB_LOG)
    a = ap.parse_args(argv)
    ds = D.build_lab(a.log)
    if ds is None:
        print(f"No usable lab traces in {a.log}")
        return
    print(f"Saved {D.save(ds, 'lab', PROCESSED_DIR)} ({len(ds['meta'])} traces)")


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print(__doc__)
        return
    cmd, rest = sys.argv[1], sys.argv[2:]
    try:
        dispatch(cmd, rest)
    except (FileNotFoundError, ValueError, PermissionError) as exc:
        # bad input files / arguments: one clear line instead of a traceback
        if os.environ.get("TDR_DEBUG"):
            raise
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)


def dispatch(cmd: str, rest: list[str]):
    if cmd == "check":
        sys.exit(cmd_check(rest))
    elif cmd == "simulate":
        cmd_simulate(rest)
    elif cmd == "train":
        from src.train import main as m
        m(rest)
    elif cmd == "evaluate":
        from src.evaluate import main as m
        m(rest)
    elif cmd == "dashboard":
        sys.exit(subprocess.call([sys.executable, "-m", "streamlit", "run", str(ROOT / "app" / "dashboard.py"), *rest]))
    elif cmd == "capture":
        from src.capture import main as m
        m(rest)
    elif cmd == "calibrate":
        from src.calibrate import main as m
        m(rest)
    elif cmd == "fit":
        from src.fit_sim import main as m
        m(rest)
    elif cmd == "inspect":
        cmd_inspect(rest)
    elif cmd == "lab-dataset":
        cmd_lab_dataset(rest)
    elif cmd == "zenodo":
        from src.zenodo import main as m
        m(rest)
    elif cmd == "analyze":
        from src.analysis import main as m
        m(rest)
    elif cmd == "selftest":
        from src.selftest import main as m
        sys.exit(m(rest))
    else:
        print(f"Unknown command {cmd!r}\n{__doc__}")
        sys.exit(2)


if __name__ == "__main__":
    main()
