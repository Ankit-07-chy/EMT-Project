# Which ML models and neural networks, and why

The five papers in the reading list (`docs/literature.md`) plus the Zenodo dataset's paper point to a small set of model types. All of them are implemented in `src/models.py` and trained on both data sources:
- our step-TDR simulator (experiments E1–E6, `python index.py train` / `evaluate`);
- the Zenodo pulse-TDR dataset, including 16 real measured traces (experiments Z1–Z3, `python index.py zenodo all`).

## From the literature to the model zoo

| Paper | What they used | What we take from it | Implemented as |
|---|---|---|---|
| Shin et al., IEEE TIM 2005 | Time-frequency reflectometry with **cross-correlation** time-of-flight, compared with a commercial TDR on coax | The conventional reference should be a *matched filter*, not just a threshold | Step data: derivative-peak baseline (`src/baseline.py`), i.e. correlation with the step's derivative. Pulse data: Gaussian / derivative-of-Gaussian **matched filter** (`PulseBaseline` in `src/zenodo.py`), calibrated on training traces only |
| Smail et al., IEEE TMAG 2011 | **Neural network (MLP)** inverse model, trained on a physics simulation (RLCG + FDTD), checked on experiments | Train on physics simulation, invert with a neural network | **MLP** (scikit-learn, scaled inputs and targets) on raw samples (A) and features (B) |
| Slimani et al., AUTOTESTCON 2024 / IEEE I&M Mag. 2025 | **KNN vs 1D-CNN** on compressed TDR of simulated RG58; KNN localised better than the CNN | A simple instance-based model is a serious contender; evaluate per SNR | **KNN** (distance-weighted, scaled inputs); per-SNR evaluation (E1, Z2) |
| Scarpetta et al., Sensors 2021 (the Zenodo dataset) | **1D-CNN** on raw pulse-TDR traces for multiple capacitive faults, trained on 1M simulated traces, tested on real ones | A CNN on the raw sequence, trained on a large simulation, tested on real measurements | **1-D CNN** (PyTorch): `CNN1D` on our 256-sample traces; multi-task `ZenodoCNN` (first-fault distance, cable length, first-discontinuity class) streamed over all 800k Zenodo training traces |
| Chang & Park, IEEE TIE 2019 | **2-D CNN on Wigner–Ville time-frequency images**, automotive wiring | CNNs work on reflectometry; compare against a stored healthy reference | Not implemented as 2-D images: a 1-D CNN on the raw trace is the cheaper equivalent for step/pulse TDR without a chirp. The "healthy reference" idea becomes calibration + matched-load reference (hardware report H5) |
| Project brief | **Random Forest / Extra Trees** | Robust tabular baselines, feature importances | RF and Extra Trees on A and B |

## Input representations

- **Method A (raw samples):** the aligned, normalised trace. 256 samples on a 1 ns grid for our data; the 1,024 README-preprocessed samples for Zenodo. Every family can use it, and the CNN uses only this.
- **Method B (physics features):** quantities produced by the conventional method: delay, amplitude, polarity, settled level, rise time, threshold-crossing times, window energies, and second-reflection features. For Zenodo: matched-filter event positions and types, the open-end candidate, and energies.
  - 23 features for our data (`src/features.py`), 23 for Zenodo (`FEATURES_Z`).
  - These are the "physics-informed" inputs of the project title.

## Training protocol

- **Our data:** 20,000 training and 4,000 validation traces. A small hyper-parameter grid per family is chosen on validation only. The test sets are separate seeds.
- **Zenodo data:** the README split (first 800,000 training, last 200,000 validation). Test traces come from the validation block and are never used for fitting or early stopping:
  - Z1: rows 800,000–819,999
  - Z2: rows 820,000–844,999, at 1, 3, 10 and 30 × the README noise
  - CNN early stopping: rows 980,000–999,999

  Subsets for the scikit-learn families keep their time and memory practical: 200,000 traces for features, 100,000 for raw samples. The CNN streams all 800,000. The 16 real traces are never used in training.
- **Targets:** distance-type outputs are regressed in physical units (Δt in ns for our data; metres for Zenodo). Distance for our data uses the calibrated vp, which keeps calibration error separate from model error.

## Results in short

### Our step-TDR simulation (`report/results/summary.md`)

Validation choices: RF, ET, KNN, MLP and CNN were each tuned on the 4,000-trace validation set (`report/results/validation_grid.csv`; final run of 6 Nov 2026, after the code review). The CNN had the lowest validation Δt error: 2.64 ns, against 2.78 ns for RF and Extra Trees on features. Selected settings, model sizes and parameter counts: `report/results/analysis_model_config.csv`.

Mixed test set (6,000 traces, SNR 10–40 dB). "Fair MAE" means the error on exactly the faults the baseline located.

| Model | Input | Fair MAE (m) | MAE over all faults (m) | Classification accuracy |
|---|---|---|---|---|
| Baseline | – | 0.261 | 0.261 (84.8% located) | 86.1 % |
| Extra Trees | B | **0.187** | 0.369 | 97.8 % |
| Random Forest | B | 0.190 | 0.370 | 97.6 % |
| 1-D CNN | A | 0.214 | **0.315** | **98.3 %** |
| MLP | B / A | 0.240 / 0.265 | 0.508 / 0.439 | 96.8 / 97.1 % |
| KNN | A / B | 0.256 / 0.365 | 0.482 / 0.752 | 95.5 / 94.7 % |
| Extra Trees / RF | A | 0.249 / 0.287 | 0.471 / 0.526 | 96.8 / 96.8 % |

What this says about the literature's choices:
- **CNN (Scarpetta, Slimani):** the most capable single model. It is best at low SNR (0.30 m fair MAE at 10 dB vs 0.51 m for the baseline), best on soft faults (96% detected at |Γ| = 0.08, baseline 9%), best of the learned models inside a held-out distance gap (0.29 m; the baseline gets 0.12 m there), and best at classification. It is also the **worst at extrapolation**: 6.5 m MAE beyond the trained distance range.
- **KNN (Slimani: KNN beat the CNN):** not reproduced here. KNN is mid-pack on raw samples and the weakest on features, where scaled heterogeneous features distort its distances.
- **MLP (Smail):** mid-pack in accuracy, with more outliers on features than the trees (RMSE 1.28 m vs 1.06 m for Extra Trees). But the MLP **on features** extrapolates far better than trees or the CNN: 1.4 m vs 3.5–6.5 m beyond the training range. It learns a smooth, almost linear map from the measured Δt. On raw samples it is no better than the trees (3.5 m).
- **Physics features (Method B) vs raw samples (A):** on distance, B wins clearly for RF and ET and slightly for the MLP; A wins for KNN. The CNN on raw samples comes close to the trees on features, because it learns its own features.
- **Baseline:** still best outside the training range (0.38 m beyond 14 m) and on clean traces it can locate. That supports a hybrid design.
- **Detection:** the CNN finds 98.1 % of faults with 1.2 % false alarms; the baseline finds 84.6 % with 1.5 %. All learned models detect faults with 2–3× smaller |Γ| than the threshold method.

The complete analysis, with error percentiles, worst cases, breakdowns by condition, confusion matrices, misses and false alarms, and latency, is in [ML_ANALYSIS.md](ML_ANALYSIS.md).

### Zenodo pulse-TDR data, including 16 real traces

**Measured** (Z1: 20,000 held-out simulated traces; Z3: 16 real traces; models trained on simulation only):
- **Best on real traces, first-fault distance:** 1-D CNN, MAE 1.23 m (median 0.95 m), against 8.64 m for the matched-filter baseline.
- **Best on real traces, cable length:** Extra Trees on features, MAE 0.61 m (−2.1 to +1.2 %), against 13.2 m for the baseline.
- **Type of first fault (real):** every feature model and the CNN 100 %, against 56 % for the baseline.
- **Held-out simulation (Z1):** Extra Trees on features, 1.23 m / 0.50 m / 99.6 %.
- **k-NN on raw pulse traces fails at the first fault** (24 m): similarity is dominated by the large open-end echo.

This supports the literature mapping above:
- Tree ensembles on physics features are the most reliable all-rounders.
- The CNN learns the position of small echoes well.
- Raw-input k-NN (Slimani) works for strong single reflections but not for weak first echoes in multi-echo traces.

Full tables: `report/results/zenodo_summary.md` and `zenodo_results_all_models.csv`; discussion in report §6.8.
