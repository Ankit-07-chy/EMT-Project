# Data dictionary

Datasets are saved by `src/dataset.py` as three files sharing one name:

| File | Content |
|---|---|
| `<name>.csv` | one row per trace: labels, settings, baseline outputs and Method B features |
| `<name>_X.npy` | float32 array (n, 256): Method A input, the normalised trace on the common time grid |
| `<name>_raw.npz` | optional raw traces: `t0` (s), `ts` (s), `V` (n × max_len, NaN-padded volts) |

Simulated sets live in `data/sim/`, the processed lab set in `data/processed/lab.csv`, and the raw lab traces plus `lab_log.csv` in `data/raw/`.

**Cache names.** `train` and `evaluate` cache their simulated sets as `<set>_<n>_<fingerprint>`, e.g. `train_20000_54cb16`. The six-character fingerprint is a hash of the simulation config (`config.cfg_tag`), so a set simulated before a calibration change is never reused afterwards. `simulate --name` writes exactly the name given. `TDR_HOME` moves `data/`, `models/` and `report/` to another folder; the tests and `index.py selftest` use this to run in a temporary folder.

**Common time grid (Method A):** 256 samples, 1 ns apart, from −16 ns to +239 ns relative to the incident edge's 50% crossing (`src/config.py`: `GRID_T`). That covers faults up to about 23 m on RG-58. Change `GRID_*` if your cables are longer.

## Labels and acquisition settings (`meta`)

| Column | Unit | Meaning | Allowed as ML input? |
|---|---|---|---|
| `cls` | – | class: open / short / matched / partial | target |
| `d` | m | distance from the tee to the main discontinuity | **no** (label) |
| `dt_true` | s | true round trip 2d/vp (regression target, in ns) | **no** (label) |
| `has_fault` | bool | `cls != matched` (regression is trained only on these) | no |
| `l_total` | m | total cable length (used for "% of length" errors) | no |
| `gamma_true` | – | true reflection coefficient (sim only) | **no** (sim-only value) |
| `kind`, `kind_name` | – | geometry: end / series_R / shunt_R / impedance_step / open_stub | no |
| `vp` | m/s | true velocity of this trace (sim: calibrated ±3%) | no |
| `vp_cal` | m/s | calibrated/nominal velocity used to convert Δt to metres | – |
| `rise` | s | system 10–90% rise time used by the simulator | no (sim-only) |
| `snr_db` | dB | 20·log10(V_inc/σ_noise) | no (sim-only) |
| `ts` | s | sample interval of the raw trace | yes (as feature `ts_ns`) |
| `rs`, `scope_c` | Ω, F | generator output resistance, scope input capacitance | no (sim-only) |
| `atten_scale` | – | attenuation multiplier vs datasheet | no (sim-only) |
| `v_inc`, `v_inc_ref` | V | true incident step; reference value used for normalising (±1%) | no |
| `l2`, `l_stub`, `r_fault`, `z2` | m, m, Ω, Ω | geometry of mid-line faults | no |
| `model` | – | `tline` or `simple` physics model | no |
| `artifacts` | bool | lab-like artifacts added (proxy lab set) | no |
| `source` | – | `sim_tline`, `sim_simple`, `sim_artifacts`, `lab` (or `zenodo`) | no |
| lab only: `file`, `config_id`, `repeat_idx`, `cable_type` | | origin of the trace; `config_id` groups repeats of one setup (E4 splits by it) | no |

**Measured traces (lab).** V_inc is estimated from each trace. The calibrated `v_inc_v` is used only when the estimate agrees with it (−20 / +25 %), when the estimate fails, or when the incident edge is corrupted by an early echo (`preprocess.preprocess_measured`). The fixture offset `t_offset_s` from calibration is removed from `base_dt` and from every model input (grid and timing features), so lab rows sit on the same time base as simulated ones.

## Baseline outputs (`B`)

| Column | Meaning |
|---|---|
| `base_found` | a reflection above threshold was found |
| `base_dt` | measured 50%-to-50% delay (s), after subtracting the calibrated fixture offset |
| `base_d` | vp_cal · base_dt / 2 (m) |
| `base_cls` | baseline class from amplitude and polarity |
| `base_gamma` | loss-compensated Γ estimate |
| `base_amp` | reflected step / incident step (signed) |
| `base_merged` | reflection merged with the incident edge (fault inside the resolution limit) |
| `prep_ok` | preprocessing succeeded (an incident edge was found). Rows with `False` are excluded from training and get no ML prediction: distance NaN, class `invalid`. They count against coverage |

## Method B features (`F`, computed by `src/features.py`)

| Feature | Unit | Meaning |
|---|---|---|
| `delta_t_ns` | ns | baseline delay between incident and reflected 50% points (−1 if none) |
| `refl_amp_ratio` | – | reflected step / incident step ≈ Γ·e^(−2αd) |
| `polarity` | – | +1 / −1 / 0 (none) |
| `v_final_ratio` | – | settled level / V_inc (1 + Γ for end loads) |
| `refl_rise_ns` | ns | 10–90% rise time of the reflected edge |
| `noise_sigma` | – | pre-edge noise std (normalised) |
| `ts_ns` | ns | sampling interval |
| `refl_found`, `merged` | 0/1 | detection flags |
| `slope_ratio` | – | peak \|dv/dt\| of the reflection / incident |
| `t_dpeak_ns` | ns | time of the reflection's dv/dt peak |
| `gamma_est` | – | loss-compensated Γ estimate |
| `inc_rise_ns` | ns | incident edge rise-time estimate (system bandwidth) |
| `t_cross10/25/50_ns` | ns | first time \|v − 1\| exceeds 0.1 / 0.25 / 0.5 after the incident edge |
| `second_amp`, `second_t_ns` | –, ns | second reflection (stub return, far end, re-reflection) |
| `energy_0_60` … `energy_180_240` | – | mean (v − 1)² in four time windows |
| `dev_centroid_ns` | ns | centroid of \|dv/dt\| above threshold after the incident edge |

Missing values are encoded as −1 (times) or 0 (amplitudes). If preprocessing failed, `refl_found` = −1 marks the row, amplitude-type features and energies are 0, and time features are −1. No feature uses a label or a simulation-only value (brief, Section 7.5).

---

## Lab log (`data/raw/lab_log.csv`, written by `index.py capture`; template `hardware/lab_log_template.csv`)

One row per saved trace. The same values are also written as `# key: value` header lines inside each trace CSV.

| Column | Meaning |
|---|---|
| `file` | trace file, relative to the log's folder, forward slashes (absolute if stored elsewhere) |
| `date`, `time`, `operator` | when and by whom |
| `cable_type`, `cable_id` | e.g. RG-58, C2 |
| `cable_length_m`, `length_meas_1_m` … `_3_m` | mean and the three tape readings |
| `termination` | open / short / matched / partial |
| `fault_kind`, `fault_position_m`, `zl_ohm`, `discontinuity_desc` | end / series_R / shunt_R / impedance_step / open_stub; distance from the tee; **measured** resistor or Z2; free text |
| `channel` | scope channel (blank = first channel) |
| `gen_model`, `gen_waveform`, `gen_amplitude_v`, `gen_period_s`, `gen_load_setting` | generator settings (load setting High-Z / 50 Ω) |
| `scope_model`, `scope_input_impedance`, `scope_bw_limit`, `sample_interval_s`, `averaging` | scope settings (`*IDN?` string; averaging is logged, not sent) |
| `repeat_idx`, `notes` | repeat number; free text (e.g. `lowSNR`) |

## Calibration (`data/calibration.json`, written by `index.py calibrate`)

| Key | Meaning |
|---|---|
| `vp_m_per_s`, `vp_std`, `velocity_factor` | propagation velocity from the Δt-vs-length fit, its standard error, vp/c |
| `t_offset_s`, `t_offset_std_s` | fixture / trigger delay t0 (intercept of Δt = 2L/vp + t0) |
| `rise_time_s`, `rise_time_std_s`, `resolution_m` | system 10–90 % rise time; vp·t_r/2 |
| `v_inc_v`, `v_inc_std_v`, `n_traces_v_inc` | incident step from the normal-amplitude traces only, and how many were used |
| `noise_sigma_v`, `noise_sigma_norm`, `snr_db` | pre-edge noise; `snr_db` is null when the noise is unmeasurable (heavily averaged traces) |
| `alpha_eff_np_per_m` | effective loss from the open-echo amplitude vs length |
| `cable_type`, `z0_ohm`, `n_traces`, `per_length`, `method`, `sample_interval_s`, `created` | bookkeeping |

## Result files (`report/results/`)

| File | Written by | Content |
|---|---|---|
| `summary.md` / `summary.json` | `evaluate` | all E1–E6 tables; best models; E3/E4 data source (PROXY or LAB) |
| `mixed_regression.csv`, `classification.csv` | `evaluate` | per method: n, coverage, MAE, RMSE, MedAE, MAE % of length, MAE Δt, fair MAE / accuracy, precision, recall, F1 |
| `e1_snr_sweep.csv`, `e2_heldout_distances.csv`, `e3_e4_sim_to_lab.csv`, `e3_e4_classification.csv`, `e5_soft_faults.csv`, `e6_method_a_vs_b.csv` | `evaluate` | one row per experiment × method (× SNR / band / \|Γ\|) |
| `validation_grid.csv` | `train` | every hyper-parameter candidate with its validation score; `SELECTED` rows are the stored models |
| `calibration_traces.csv` | `calibrate` | per open-circuit trace: length, Δt, amplitude, rise, V_inc, noise |
| `analysis_localization.csv` | `analyze` | error distribution per method: MAE, RMSE, median, P90/95/99, max, bias, shares within 0.1/0.25/0.5/1 m (all traces and fair subset) |
| `analysis_localization_breakdown.csv` | `analyze` | MAE, P95, fair MAE and baseline coverage by fault type, distance, SNR, rise time, \|Γ\| |
| `analysis_worst_cases.csv` | `analyze` | the 15 largest errors of the best regressor with their conditions |
| `analysis_detection_binary.csv`, `analysis_detection_per_class.csv`, `analysis_confusion_matrices.csv`, `analysis_fn_fp.csv`, `analysis_detection_vs_snr.csv` | `analyze` | TP/FP/FN/TN, precision, recall, F1, false-alarm and miss rates; per-class P/R/F1; confusion counts; misses by \|Γ\| and SNR; detection vs SNR |
| `analysis_latency.csv`, `analysis_model_config.csv`, `analysis_summary.json`, `ml_analysis_summary.md` | `analyze` | ms per trace (single / batched); selected parameters, size and weight/node counts per model; all of it as markdown |
| `feature_tests.csv` / `.md` | `selftest` | per feature: purpose, procedure, expected, actual, performance, seconds, status |
| `zenodo_summary.md`, `zenodo_z1_heldout_sim.csv`, `zenodo_z1_by_fault_count.csv`, `zenodo_z2_noise.csv`, `zenodo_z3_real.csv`, `zenodo_z3_real_per_trace.csv` | `zenodo evaluate` | MAE / RMSE / MedAE of first-fault distance and cable length, first-fault type accuracy, coverage |
| `zenodo_*_run1.csv` | first `zenodo all` run | kept for the raw-input forests (RF-A, ET-A), which only that run evaluated |
| `zenodo_results_all_models.csv` | `scripts/zenodo_checks.py merge` | Z1–Z3 for every model with a `source` column (run 2, or run 1 for RF-A/ET-A) |
| `zenodo_seed_check.csv`, `zenodo_noise_check.csv` | `scripts/zenodo_checks.py` | Z1 with shared vs independent noise; real-trace noise vs the README level |
| `zenodo_training_log.csv`, `zenodo_cnn_history.csv` | `zenodo train` | fit time per model; CNN loss / validation MAE / accuracy per epoch |

---

## Zenodo pulse-TDR data (`src/zenodo.py`)

Raw archive: `data/external/zenodo_5720438/dataset_tdr_2021.zip`. Derived files are in `data/external/zenodo_5720438/derived/`:

| File | Content |
|---|---|
| `labels.npz` | `pos` (n × 5, m, sorted, NaN-padded), `typ` (0 = capacitive fault, 1 = termination, −1 = empty), `cap` (F) |
| `calibration.json` | `s0` (pulse-blanking constant), pulse template, idx→metre lines per event type, open-end attenuation, vp |
| `<split>_n<noise>_s<seed>.npz` / `_base.csv` / `_X.npy` | Method B features, baseline outputs and README-preprocessed traces for one split. Every split draws its own noise: `trainB` seed 0 (`trainA` = its first 100 k rows), `test` a seed derived from the split name, `noise` sets seed 10 + multiplier |

Splits (row ranges of the 1M simulated traces):
- `trainB` 0–200k
- `trainA` 0–100k
- `cnn_train` 0–800k
- `cnn_val` 980k–1M
- `test` 800k–820k
- `noise` 820k–845k

Targets per trace:

| Column | Unit | Meaning |
|---|---|---|
| `d_first` | m | position of the first discontinuity (capacitive fault or open end) |
| `length` | m | cable length (position of the open end) |
| `first_cls` | – | `partial` (first discontinuity is a capacitive fault) or `open` |
| `n_faults` | – | number of capacitive faults (0–4); used only to break the results down |
| `first_cap_pF` | pF | capacitance of the first fault; used only to break the results down |

Pulse features (`FEATURES_Z`, 23):
- first event: position, type, matched-filter amplitudes and their ratio;
- event count;
- open-end candidate: position, amplitude and attenuation-normalised score;
- second and last event;
- noise;
- positions and values of the largest Gaussian-template response and of the most negative derivative-template response;
- energy in six windows.

Missing values are encoded as −1.
