# Feature self-test (2026-11-09 18:42)

`python index.py selftest` ran every feature for real in a temporary data folder (1.2 min). Result: 14 Pass.

| ID | Feature | Expected | Actual | Performance | Status |
|---|---|---|---|---|---|
| F01 | Instrument discovery (capture --list) | Exit 0 and a clear 'no instrument' message (no hardware attached here) | exit 0; No instruments found (Visa Library at py). Check the USB/LAN cable, that the scope is on, its USB mode (USBTMC) and the VISA driver; see hardware/HARDWARE_GUIDE.md, H2. | 1.5 s | **Pass** |
| F02 | Capture session with logging (capture --simulate) | 28 CSV files + 28 log rows; live distance within 0.3 m of the cable length | 28 traces + log rows written; quick-check distances: 2 m open -> 2.04 m; 5 m open -> 5.07 m; 10 m open -> 10.11 m; 5 m short -> 5.06 m; 5 m partial 100 ohm -> 5.07 m; 5 m partial 22 ohm -> 5.05 m | 0.35 s per simulated capture | **Pass** |
| F03 | Read any scope CSV (inspect) | Distance within 0.3 m of 5 m, class open, PNG written | exit 0; vendor/format detected; baseline d = 5.065 m (true 5.00); plot saved = True | 2.4 s incl. Python start-up | **Pass** |
| F04 | Velocity calibration (calibrate) | vp within 1.5 % of the simulator's true vp; calibration.json + fig0 written | vp = 1.9616e+08 m/s vs simulated truth 1.9786e+08 (-0.86 %); t_offset 0.23 ns; rise 4.15 ns; resolution 0.41 m; SNR 30.5 dB | 2.6 s for 12 traces | **Pass** |
| F05 | Simulator-to-measurement fit (fit) | Converges, normalised RMSE < 0.05 | exit 0; RMSE 0.0238 (normalised); fitted vp 1.972e+08 m/s; overlay figure written | 2.3 s per fit | **Pass** |
| F06 | Lab dataset builder (lab-dataset) | data/processed/lab.csv with 28 rows and a (28, 256) Method A matrix | exit 0; 28 traces processed; Method A matrix (28, 256) | 0.05 s per trace incl. start-up | **Pass** |
| F07 | Synthetic dataset, transmission-line model (simulate) | 400 rows, X (400, 256), all 4 classes, finite values | exit 0; 400 labelled traces, X (400, 256), classes {'matched': 108, 'open': 100, 'short': 99, 'partial': 93}, raw traces saved | 6 ms per trace (simulate + preprocess + features) | **Pass** |
| F08 | Synthetic dataset, brief's simple model + lab artifacts | 200 rows written, source tagged as artifacts | exit 0; 200 rows, source column = sim_artifacts | 9 ms per trace | **Pass** |
| F09 | Physics check of the simulator | Every level within 0.03 of theory (small cable loss allowed) | final level / theory 1+Gamma: open: 1.985/2.000; short: 0.015/0.000; matched gamma=0: 1.000/1.000; partial zl=100: 1.328/1.333; partial zl=22: 0.617/0.611; partial kind=1,r_fault=50: 1.328/1.333; partial kind=2,r_fault=50: 0.672/0.667; partial kind=3,z2=75: 1.197/1.200; worst deviation 0.015; delay = 2L/vp to 0.000 ns | 8 noiseless traces in < 1 s | **Pass** |
| F10 | Classical baseline detector | At 40 dB: median distance error < 0.25 m (half the 0.4-0.5 m resolution of a 4-5 ns edge) and class accuracy > 0.9 | SNR 40 dB: median /err/ 0.17 m, mean 0.20 m, class acc 0.99, missed 1%; SNR 20 dB: median /err/ 0.16 m, mean 0.30 m, class acc 0.81, missed 21% | see F12 for per-trace latency | **Pass** |
| F16 | Error handling of the CLI | Non-zero exit (or a clear 'nothing to do' message) and no traceback | inspect missing file: exit 1, clean message; inspect garbage CSV: exit 1, clean message; capture without length: exit 2, clean message; calibrate without log: exit 2, clean message; fit missing file: exit 1, clean message; lab-dataset without log: exit 0, clean message; unknown command: exit 2, clean message |  | **Pass** |
| F17 | Hardware circuit + expected-waveform generator | 13 schematics (SVG + PNG) and 11 expected-waveform PNGs | exit 0; 13 circuit SVGs, 26 PNGs (circuits + expected waveforms) | 15 s | **Pass** |
| F18 | Unit test suite (pytest) | All tests pass | 62 passed in 17.79s | 19 s | **Pass** |
| F19 | External real-data pipeline (Zenodo 5720438) | models/zenodo_models.joblib and the Z1/Z2/Z3 tables exist | all result files present; Z1 table has 8 rows (see ML_ANALYSIS.md) |  | **Pass** |

Procedures and purposes are in `feature_tests.csv` and docs/TESTING_REPORT.md.