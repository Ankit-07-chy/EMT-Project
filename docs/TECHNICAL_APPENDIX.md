# Technical appendix

The supporting detail that does not fit on slides: formulas, every configuration value, file formats, the full command reference and a map from each claim to the file that supports it.

---

## A. Formulas

### A.1 Transmission line and TDR
| Quantity | Formula | Notes |
|---|---|---|
| Propagation velocity | vp = c/√εr = VF·c | RG-58 VF ≈ 0.66 → vp ≈ 1.98×10⁸ m/s ≈ 0.2 m/ns |
| Incident step at the tee | V_inc = Vs·Z0/(Rs + Z0) | = Vs/2 when Rs = Z0 |
| Reflection coefficient | Γ = (ZL − Z0)/(ZL + Z0) | +1 open, −1 short, 0 matched |
| Series R mid-line | Γ = R/(R + 2Z0) | line after the fault matched |
| Shunt R mid-line | Γ = −Z0/(Z0 + 2R) | |
| Open stub on a tee | Γ = −1/3 for 2·l_stub/vp | Z0 ∥ Z0 seen first |
| Level after the echo | V = (1 + Γ)·V_inc | |
| Distance | d = vp·Δt/2 | Δt measured 50 %-to-50 % |
| Calibration | Δt = (2/vp)·L + t0 | least squares over ≥ 2 lengths; t0 = fixture/trigger delay |
| Resolution | Δd_min ≈ vp·t_r/2 | t_r = 10–90 % system rise time |
| Attenuation | α(f) = α_dc + k_s√f + k_d·f (Np/m), α_dc = R_dc/(2Z0) | fitted to datasheet dB/100 m at 100 MHz and 1 GHz |
| Loss-compensated Γ | Γ ≈ amp·e^(2·α(0.1/t_r)·d) | baseline, clipped to ±1.5 |
| Source mismatch | Γ_S = (Rs − Z0)/(Rs + Z0) | re-reflections every 2d/vp if ≠ 0 |

### A.2 Preprocessing and baseline
| Step | Formula / rule |
|---|---|
| Robust noise | σ = 1.4826 · median(\|x − median(x)\|) over the pre-trigger samples (MAD) |
| Normalisation | x_n = (v − median(pre-trigger)) / V_inc |
| V_inc (measured trace) | plateau after the first big rise; the calibrated value is used if the estimate lies within −20/+25 % of it, fails, or the edge is > 1.6 × slower than calibrated |
| Alignment | t = 0 at the incident 50 % crossing |
| Rise estimate | t_r ≈ 2·(t50 − t10) (leading half only) |
| Denoise | Gaussian, σ_s = max(ts, t_r · clip(0.3 + 2·σ_n, 0.3, 0.9)) |
| Detection threshold | thr = max(0.03 · peak incident slope, 4.5 · σ(dv/dt)) |
| Lobe | contiguous run of \|dv/dt\| above thr after the incident lobe; lobes with \|area\| < 0.02 are skipped |
| Class rules | \|amp\| < 0.035 → matched; Γ ≥ 0.82 → open; Γ ≤ −0.82 → short; else partial |
| Merged edge | incident lobe area > 1.3 → same-polarity echo merged; dt from the lobe centroid c: dt = c·(1 + a)/a |

### A.3 Metrics
| Metric | Definition | Meaning |
|---|---|---|
| MAE | (1/n)·Σ\|d̂ᵢ − dᵢ\| | average distance error in metres |
| RMSE | √((1/n)·Σ(d̂ᵢ − dᵢ)²) | punishes large errors more |
| MedAE, P90, P95, P99, max | percentiles of \|d̂ − d\| | typical, bad-case and worst-case error |
| Bias | (1/n)·Σ(d̂ᵢ − dᵢ) | systematic over/under-estimate |
| Coverage | located faults / all faulted traces | the baseline may give no distance; ML always does unless preprocessing failed |
| Fair MAE | MAE on the faults the baseline located | the same traces for every method |
| Accuracy | correct / all | 4-class |
| Precision, recall | TP/(TP + FP), TP/(TP + FN) | per class, or binary (fault vs matched) |
| F1 | 2·P·R/(P + R); macro-F1 = mean over the 4 classes | |
| False-alarm rate | FP/(FP + TN) | matched lines called faulty |
| Miss rate | FN/(FN + TP) | faults called matched |
| Latency | wall time per trace, single call and batched | measured on the project laptop's CPU |

mAP and IoU are object-detection metrics for boxes in images. They do not apply to a 1-D signal with one label per trace.

---

## B. Configuration values

### B.1 Cable presets (`src/config.py`)
| Cable | Z0 (Ω) | VF | dB/100 m @100 MHz | dB/100 m @1 GHz | R_dc (Ω/m, loop) |
|---|---|---|---|---|---|
| RG-58 (default) | 50 | 0.66 | 16 | 66 | 0.050 |
| RG-174 | 50 | 0.66 | 29 | 105 | 0.33 |
| RG-316 | 50 | 0.695 | 27 | 90 | 0.30 |
| RG-59 | 75 | 0.66 | 11 | 40 | 0.12 |

### B.2 Simulation ranges (`SimConfig`)
| Parameter | Value |
|---|---|
| distance d | 0.5–20 m |
| vp | nominal (datasheet or calibrated) ±3 % |
| attenuation scale | 0.7–1.3 × datasheet |
| system rise time (10–90 %) | 2–10 ns |
| SNR | 10–40 dB (20·log10(V_inc/σ)) |
| generator Rs / Z0 | 0.92–1.08 |
| scope input | 1 MΩ ∥ 8–20 pF |
| sample interval | 0.5, 1 or 2 ns |
| record | −50 ns … +262 ns around the trigger |
| trigger jitter | ±2 ns |
| baseline drift | ≤ 2 % of V_inc |
| ADC | 8 bit |
| V_inc reference error | 1 % |
| partial \|Γ\| | 0.05–0.70 |
| matched tolerance | ZL within ±5 % of Z0 |
| cable after a mid-line fault | 1–8 m |
| open stub | 0.3–3 m |
| Method A grid | 256 points, 1 ns, −16 … +239 ns |

### B.3 Model grids (`src/train.py`)
| Family | Grid |
|---|---|
| RF / ET regression, A | max_features ∈ {sqrt, 0.3} × min_samples_leaf ∈ {2, 5} |
| RF / ET regression, B | max_features ∈ {0.5, 1.0} × min_samples_leaf ∈ {2, 5} |
| RF / ET classification | max_features ∈ {sqrt, 0.3} (A) or {sqrt, 0.5} (B), leaf 1 |
| KNN | k ∈ {5, 15}, distance weights, StandardScaler |
| MLP | hidden (128, 64) or (256, 128), α = 1e-4, early stopping (12 epochs), ≤ 300 iterations |
| CNN | channels (16, 32, 64, 64), kernel 7, dropout 0.2, AdamW lr 2e-3, weight decay 1e-4, batch 256, ≤ 40 epochs, patience 6, ReduceLROnPlateau ×0.5 |
| Forest size | 100 trees (`--trees`), stored in the bundle and reused by E2/E4 refits |

### B.4 Zenodo pipeline (`src/zenodo.py`)
| Item | Value |
|---|---|
| Archive | Zenodo record 5720438 (Scarpetta et al. 2021), 4.18 GB |
| Trace | 1024 samples, Ts = 4 ns; transmitted pulse blanked over samples 0–37 |
| Noise added | σ = 0.000437 (README value) × {1, 3, 10, 30} in Z2 |
| Splits | trainB 0–200 k, trainA 0–100 k, CNN train 0–800 k, CNN val 980 k–1 M, test 800–820 k, noise 820–845 k, 16 real traces |
| Baseline | matched filter on Gaussian g and g′ after a σ = 12-sample high-pass; events above 6σ |
| sklearn settings | RF max_features sqrt, leaf 5 · ET max_features 0.5, leaf 5 · KNN k 7, distance · MLP (256, 128), α 1e-4 |
| CNN | 4 blocks (16/32/48/64 channels; kernels 9/7/7/5) → 128 → heads: 2 regression (first-fault distance, cable length) + 2-class first-fault type; time budget 100 min |
| Safety | restricted unpickler (numpy/pandas whitelist), memory-map inside the zip, archive's TensorFlow model never loaded |

---

## C. File formats

### C.1 Trace CSV written by `capture` (our format)
```
# key: value            ← one line per label (all LOG_COLUMNS + scope settings)
time_s,voltage_v
-5.0e-08,0.0012
...
```
The universal reader (`src/scope_io.py`) also reads Rigol DS1000Z, Tektronix legacy 6-column, Keysight, Siglent and generic CSVs (units in headers, channel selection).

### C.2 `data/raw/lab_log.csv` (28 columns, one row per trace)
`file, date, time, operator, cable_type, cable_id, cable_length_m, length_meas_1_m, length_meas_2_m, length_meas_3_m, termination, fault_kind, fault_position_m, zl_ohm, discontinuity_desc, channel, gen_model, gen_waveform, gen_amplitude_v, gen_period_s, gen_load_setting, scope_model, scope_input_impedance, scope_bw_limit, sample_interval_s, averaging, repeat_idx, notes`

`file` is relative to the log's folder, with forward slashes. `termination` ∈ open / short / matched / partial. `fault_kind` ∈ end / series_R / shunt_R / impedance_step / open_stub.

### C.3 `data/calibration.json`
`created, cable_type, z0_ohm, n_traces, per_length[], method, vp_m_per_s, vp_std, t_offset_s, t_offset_std_s, alpha_eff_np_per_m, velocity_factor, rise_time_s, rise_time_std_s, resolution_m, v_inc_v, v_inc_std_v, n_traces_v_inc, noise_sigma_v, noise_sigma_norm, snr_db, sample_interval_s`

### C.4 Datasets (`data/sim/<name>.csv` + `<name>_X.npy` [+ `<name>_raw.npz`])
- **Labels:** cls, kind, d, l_total, dt_true, gamma_true, vp, rise, snr_db, ts, rs, scope_c, atten_scale, v_inc, v_inc_ref, l2, l_stub, r_fault, z2, model, kind_name, has_fault, artifacts, source, vp_cal.
- **Baseline outputs:** base_found, base_dt, base_d, base_cls, base_gamma, base_amp, base_merged, prep_ok.
- **The 23 Method B features.**
- **`_X.npy`:** the Method A matrix (n × 256, float32).

### C.5 Model bundle (`models/tdr_models.joblib`)
`models{(task, method, algo): estimator}, val_table, features_B, grid_t, classes, vp_cal, cable, n_train, n_estimators, train_set, sim_config, importances_B, created`

---

## D. Command reference (`python index.py <command>`)

| Command | Purpose | Main options |
|---|---|---|
| `check` | packages, VISA backends, calibration, models | – |
| `simulate` | labelled synthetic dataset | `--n --seed --name --snr --model tline/simple --artifacts --raw` |
| `train` | simulate train/val, grid search, save bundle | `--n-train 20000 --n-val 4000 --trees 100 --rebuild --out --families` |
| `evaluate` | E1–E6, tables, ten figures | `--quick --rebuild --bundle` |
| `analyze` | localization/detection/latency analysis | `--quick --bundle` |
| `dashboard` | Streamlit app | Streamlit options |
| `capture` | scope capture + labelled log | `--list --simulate --resource --repeats --length/--length-meas --termination --fault-kind --fault-position --zl --cable --cable-id --notes …` |
| `inspect` | read any scope CSV and run the baseline | `<file> --channel --ts --plot` |
| `calibrate` | vp, t0, rise, resolution, V_inc, noise | `--log --files --lengths --cable --out` |
| `fit` | fit the simulator to a measured trace | `--file --length --termination --fault-kind --fault-position --zl` |
| `lab-dataset` | logged lab traces → model inputs | `--log` |
| `zenodo` | external real-data pipeline | `download / prepare / train / evaluate / all --cnn-minutes` |
| `selftest` | run every feature end to end in a temp folder | `--fast --keep --home` |

Environment: `TDR_HOME` moves data/models/report folders; `TDR_DEBUG=1` shows full tracebacks.

Helper scripts (not CLI commands):

| Script | Purpose |
|---|---|
| `scripts/make_testing_report.py` | writes `docs/TESTING_REPORT.md` from `feature_tests.csv` + the review log (runs pytest) |
| `scripts/zenodo_checks.py [noise\|seed\|merge]` | real-trace noise check, run-1 vs run-2 seed check, all-models Zenodo table (run with `python -I`) |
| `hardware/circuits/make_hardware_figures.py [out_dir]` | schematics c01–c13, expected waveforms w01–w12, wiring pictures p01–p02 |
| `presentation/make_diagrams.py`, `collect_data.py`, `build_deck.js`, `export_pdf.ps1`, `screenshots.py` | diagrams, deck data, deck, PDF export, dashboard screenshots (see `presentation/README.md`) |

---

## E. Source references (where each claim comes from)

| Topic | Source of truth |
|---|---|
| Physics model, fault kinds | `src/sim_tdr.py`, `docs/theory_sheet.md`, tests `tests/test_physics_baseline.py` |
| Baseline algorithm | `src/baseline.py` |
| Features (23) | `src/features.py` (`FEATURES_B`), `docs/data_dictionary.md` |
| Model definitions and grids | `src/models.py`, `src/train.py` |
| Selected hyper-parameters, sizes | `report/results/validation_grid.csv`, `report/results/analysis_model_config.csv` |
| Simulation results E1–E6 | `report/results/summary.md` and the `e*_*.csv` tables; figures `report/figures/fig1–fig10` |
| Localization / detection analysis | `report/results/ml_analysis_summary.md`, `analysis_*.csv`, figures `a1–a6` |
| Latency | `report/results/analysis_latency.csv` |
| Real-data results | `report/results/zenodo_summary.md`, `zenodo_z1/z2/z3*.csv`, `zenodo_results_all_models.csv`, checks `zenodo_seed_check.csv` / `zenodo_noise_check.csv`, figures `zfig1–3` |
| Feature tests | `report/results/feature_tests.md` / `.csv` (`index.py selftest`) |
| Unit tests | `tests/` (62 tests) |
| Review findings and fixes | `docs/TESTING_REPORT.md` §3 |
| Hardware | `hardware/README.md`, `HARDWARE_GUIDE.md`, `LAB_PROCEDURE.md`, `circuits/` |
| Literature | `docs/literature.md`, `docs/model_selection.md` |
| Status | `docs/PROJECT_STATUS.md` |
| Presentation | `presentation/TDR_Cable_Fault_Detection.pptx` / `.pdf`; every number from `presentation/deck_data.json` |

## F. Literature (full entries in [docs/literature.md](literature.md) and [docs/zenodo_check.md](zenodo_check.md))
- Scarpetta, M., Spadavecchia, M., Adamo, F., Ragolia, M. A., Giaquinto, N. (2021). *Detection and Characterization of Multiple Discontinuities in Cables with Time Domain Reflectometry and Convolutional Neural Networks*. Sensors 21(23):8032, doi:10.3390/s21238032. Data: Zenodo, doi:10.5281/zenodo.5720438.
- Slimani, H., Gargouri, Y., Ngolè Mboula, F. M., Ravot, N. (2024). *Detection, Localization and Characterization of Fault in Cable via Machine Learning Approach Based on Compressed Sensing TDR*. IEEE AUTOTESTCON, doi:10.1109/AUTOTESTCON47465.2024.10697515. Magazine version: IEEE I&M Magazine 28(7), 2025, doi:10.1109/MIM.2025.11198883.
- Smail, M. K., Hacib, T., Pichon, L., Loete, F. (2011). *Detection and Location of Defects in Wiring Networks Using TDR and Neural Networks*. IEEE Trans. Magnetics 47(5), doi:10.1109/TMAG.2010.2089503.
- Shin, Y.-J. et al. (2005). *Application of Time-Frequency Domain Reflectometry for Detection and Localization of a Fault on a Coaxial Cable*. IEEE TIM 54(6), doi:10.1109/TIM.2005.858115.
- Chang, S. J., Park, J. B. (2019). *Wire Mismatch Detection Using a CNN and Fault Localization Based on Time–Frequency-Domain Reflectometry*. IEEE TIE 66(3), doi:10.1109/TIE.2018.2835386.
