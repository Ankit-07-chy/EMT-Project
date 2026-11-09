"""Write docs/TESTING_REPORT.md from report/results/feature_tests.csv + the review log below.

    .venv\\Scripts\\python scripts\\make_testing_report.py

The per-feature 'actual output' column is copied from the self-test run, never typed by hand.
"""
from __future__ import annotations

import re
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "report" / "results"

# issues found while testing each feature, and what was changed (this review round, Nov 2026)
ISSUES = {
    "F01": ("`capture --list` printed nothing when no instrument was attached", "prints 'No instruments found' with the VISA backend and what to check"),
    "F02": ("relative `--out-dir`/`--log` stored paths that could not be resolved later; backslashes in the log (review #2)",
            "paths stored relative to the log folder with forward slashes, absolute if elsewhere; regression test"),
    "F03": ("one calibration V_inc normalised every trace (review #1); missing/garbage files gave tracebacks (review #12)",
            "`preprocess_measured`: V_inc per trace, calibration as reference; CLI error handler"),
    "F04": ("crash with 2–3 traces (covariance) or zero pre-edge noise (SNR None) (review #6); V_inc averaged over low-amplitude rows (review #1); test suite overwrote the real calibration figure (review #5)",
            "guarded fit and print; V_inc from normal-amplitude rows only; tests run in a temporary TDR_HOME; polluted files removed"),
    "F05": ("used the trace's own V_inc estimate only", "uses `preprocess_measured` like every other measured-trace path"),
    "F06": ("blank `channel` cells turned the column into floats and skipped files (review #4); t0 removed from Δt only (review #3)",
            "integral floats accepted as channel numbers; t0 removed from both model inputs; feature windows anchored on the incident edge"),
    "F07": ("dataset caches keyed by name and size only (review #10)", "simulation-config fingerprint in every cache name"),
    "F08": ("–", "–"),
    "F09": ("–", "–"),
    "F10": ("self-test expectation 0.15 m was stricter than the method's documented accuracy", "criterion set to half the 0.4–0.5 m resolution (0.25 m) and class accuracy > 0.9"),
    "F11": ("`--trees` not used by E2/E4 refits; `--out` bundle never read (review #9); failed traces used in training (review #7)",
            "forest size and training-set name stored in the bundle; `evaluate --bundle`; failed traces excluded"),
    "F12": ("single-trace forest and k-NN calls took 25–37 ms, dominated by thread-pool start-up (n_jobs = -1)", "`models.set_threads`: single-trace inference single-threaded (dashboard, latency test): ET-B 26 → 6.4 ms"),
    "F13": ("E2 loaded the training set by its old name after the cache rename (found by this test)", "training-set name read from the bundle"),
    "F14": ("unreadable saved trace stopped the whole app; ZL = −Z0 crashed the Γ calculator; simulated traces got the lab t0 (review #3, #12)",
            "guarded loads, ZeroDivisionError handled, t0 only for measured traces, V_inc 'Automatic (per trace)'"),
    "F15": ("–", "–"),
    "F16": ("7 wrong invocations: missing files and unparsable CSVs ended in tracebacks", "CLI-wide handler for FileNotFoundError / ValueError / PermissionError (TDR_DEBUG=1 for a traceback)"),
    "F17": ("script always wrote into hardware/circuits", "optional output folder argument; two pictorial wiring figures added"),
    "F18": ("tests wrote into the real report folder (review #5)", "conftest sets a temporary TDR_HOME; 16 regression tests added"),
    "F19": ("test noise used the same random stream as the training features (review #8)", "noise seed derived from the split name; Z1–Z3 re-evaluated with the fixed seeds"),
}

REVIEW = [
    ("1", "Every lab trace normalised by one calibration V_inc", "high", "V_inc per trace (`preprocess_measured`); calibration V_inc from normal-amplitude rows", "test_vinc_per_trace_any_amplitude (8 cases), test_calibrate_ignores_low_amplitude_rows_for_vinc", "Fixed"),
    ("2", "Capture logs relative paths later lookups cannot resolve", "high", "resolve + relative to the log folder, POSIX separators", "test_capture_relative_paths_resolve", "Fixed"),
    ("3", "Fixture offset t0 removed from Δt only", "medium", "`shifted()` removes t0 from Method A and all timing features; baseline reports corrected times; windows anchored on the incident edge", "test_t_offset_shifts_every_time_feature", "Fixed"),
    ("4", "Blank channel cell makes channel a float", "medium", "integral floats accepted; blank → first channel", "test_channel_float_from_log", "Fixed"),
    ("5", "A test overwrote real report files", "medium", "tests/conftest.py sets a temporary TDR_HOME; polluted fig0 / calibration_traces removed; dashboard shows fig0 only when calibrated", "full pytest run leaves report/ untouched", "Fixed"),
    ("6", "calibrate crashed on 2–3 traces or zero noise", "medium", "covariance only with > 3 points; SNR print guarded", "test_calibrate_two_traces_and_no_noise", "Fixed"),
    ("7", "Failed preprocessing encoded like a near-end short", "medium", "amplitude features 0 on failure; failed rows excluded from training; no prediction at test time (coverage)", "test_failed_preprocessing_is_not_a_short, test_predict_marks_failed_rows_invalid", "Fixed"),
    ("8", "Zenodo Z1 test noise identical to training noise", "medium", "noise seed per split name (trainB keeps 0); Z1–Z3 re-run", "re-run of `zenodo evaluate`: every Z1 number moved < 2 % (`zenodo_seed_check.csv`)", "Fixed"),
    ("9", "`--trees` and `--out` not carried to evaluate", "low", "bundle stores n_estimators and train_set; `evaluate --bundle`", "self-test F11/F13", "Fixed"),
    ("10", "Cached datasets ignore the config", "low", "config fingerprint in cache names", "self-test F11/F13", "Fixed"),
    ("11", "Siglent time axis ignores trigger delay", "low (plausible)", "TRDL? queried and subtracted; preprocessing falls back to a whole-record edge search", "needs a Siglent scope to confirm", "Fixed, unverified on hardware"),
    ("12", "Error paths ending in tracebacks (inspect, dashboard)", "low", "CLI handler; dashboard guards; `--averaging` help clarified", "self-test F14, F16", "Fixed"),
    ("13", "Zenodo k-NN on raw traces fitted three times (≈ 1.2 GB bundle)", "performance", "documented; shared-neighbour k-NN listed as future work", "–", "Open (documented, not a correctness issue)"),
    ("14", "Real-trace noise threshold from the synthetic blanked segment", "plausible", "measured the 16 real traces' own noise after the same high-pass: ratio to the assumed level 0.89–1.15 (median 1.00), so the threshold is right", "`scripts/zenodo_checks.py noise` → `zenodo_noise_check.csv`", "Checked: does not occur"),
]


def main():
    ft = pd.read_csv(RES / "feature_tests.csv")
    md = (RES / "feature_tests.md").read_text(encoding="utf-8")
    head = md.splitlines()[0]
    m = re.search(r"\((\d+\.\d) min\)\. Result: (.*)\.", md)
    py = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(ROOT / "tests")],
                        capture_output=True, text=True, cwd=ROOT)
    pyline = [ln for ln in py.stdout.splitlines() if "passed" in ln or "failed" in ln][-1]
    tests = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", str(ROOT / "tests")],
                           capture_output=True, text=True, cwd=ROOT).stdout.splitlines()
    per_file = {}
    for t in tests:
        if "::" in t:
            f = t.split("::")[0].replace("tests/", "").replace("tests\\", "")
            per_file[f] = per_file.get(f, 0) + 1

    cell = lambda s: str(s).replace("|", "/").replace("\n", " ")  # noqa: E731
    L = ["# Software testing report", "",
         f"Generated {time.strftime('%Y-%m-%d %H:%M')} by `scripts/make_testing_report.py` from the self-test results "
         f"({head.split('(')[-1].rstrip(')')}) and the code-review log. Every 'actual' value below is copied from a real run.", "",
         "## 1. Summary", "",
         "| Level | What runs | Result |", "|---|---|---|",
         f"| Unit + regression | `python -m pytest tests` ({sum(per_file.values())} tests) | {pyline} |",
         f"| Feature / integration / system | `python index.py selftest` ({len(ft)} features, every CLI command for real, temporary folder) | {m.group(2) if m else ''} in {m.group(1) if m else '?'} min |",
         "| Independent code review | one reviewer read every module and reproduced each finding | 14 findings: 11 fixed and pinned by tests or re-runs, 1 fixed but unverifiable without a Siglent scope, 1 size/performance item documented, 1 checked and found not to occur |",
         "| Hardware | needs the lab | **not run** (see hardware/README.md §2); the software side is rehearsed with the simulated scope |", "",
         "Status meanings: **Pass**: expected result reached. **Fail**: not reached. **Needs attention**: could not be completed in this environment, with the reason given.", "",
         "## 2. Feature-by-feature results", ""]
    for _, r in ft.iterrows():
        iss, fix = ISSUES.get(r.id, ("–", "–"))
        L += [f"### {r.id}. {r.feature}: **{r.status}**", "",
              "| | |", "|---|---|",
              f"| Purpose | {cell(r.purpose)} |",
              f"| Procedure | {cell(r.procedure)} |",
              f"| Expected | {cell(r.expected)} |",
              f"| Actual | {cell(r.actual)} |",
              f"| Performance | {cell(r.performance) if str(r.performance) != 'nan' else '–'} (check took {r.seconds:.0f} s) |",
              f"| Issues found | {iss} |",
              f"| Corrections | {fix} |",
              f"| Final status | **{r.status}** |", ""]
    L += ["## 3. Code review findings and fixes", "",
          "| # | Finding | Severity | Fix | Pinned by | Status |", "|---|---|---|---|---|---|"]
    L += [f"| {a} | {b} | {c} | {d} | {e} | {f} |" for a, b, c, d, e, f in REVIEW]
    L += ["", "## 4. Unit and regression tests", "", "| File | Tests | Covers |", "|---|---|---|"]
    covers = {"test_physics_baseline.py": "final levels vs 1 + Γ, stub return, echo delay, baseline on clean traces, matched line, V_inc estimate, feature shapes, grid alignment",
              "test_hardware_io.py": "Rigol / Tektronix / Keysight / Siglent / generic CSV dialects, voltage-only files, own-format round trip, simulated capture → calibrate, lab dataset",
              "test_models_zenodo.py": "every sklearn family × task, CNN learns a pulse position, CNN probabilities, safe unpickler (reads labels, blocks code), memmap inside a nested zip, pulse baseline",
              "test_review_fixes.py": "regression tests for review findings 1–7 (amplitudes, t0, channel, failed traces, calibration edge cases, relative paths)"}
    for f, n in sorted(per_file.items()):
        L.append(f"| tests/{f} | {n} | {covers.get(f, '')} |")
    L += ["", "## 5. What could not be tested here, and the exact next step", "",
          "| Item | Why not | Next step |", "|---|---|---|",
          "| Scope drivers on a real instrument (Rigol, Keysight, Tektronix, Siglent) | no oscilloscope connected to this laptop | lab step S5: `python index.py capture --list`, then one capture with `--repeats 1` and `inspect --plot` |",
          "| Calibration with real cables | needs the lab | lab step S8: `capture … --termination open` at ≥ 2 lengths, then `python index.py calibrate` |",
          "| E3/E4 on real lab traces | needs ≥ 20 logged lab traces | after S9: `lab-dataset`, `train --rebuild`, `evaluate` (switches from PROXY to LAB automatically) |",
          "| Fast-edge pulser | optional, needs instructor approval and a build | hardware/README.md S15 |", ""]
    out = ROOT / "docs" / "TESTING_REPORT.md"
    out.write_text("\n".join(L), encoding="utf-8")
    print("Saved", out)


if __name__ == "__main__":
    main()
