# TDR cable fault detection with physics-informed machine learning

*Technical report: draft. Sections 3 and 6.4 will be completed after the lab session. Sections 6.1–6.7 are simulation results from `python index.py evaluate` (`report/results/summary.md`); §6.8 is measured on 16 real traces (Zenodo). The in-depth localization/detection analysis is in `docs/ML_ANALYSIS.md`, the testing evidence in `docs/TESTING_REPORT.md`.*

## 1. Introduction

Time-domain reflectometry (TDR) locates a cable fault from the delay of its echo. A fast step is launched into the cable, any impedance discontinuity reflects part of it, and the round-trip delay Δt gives the distance d = vp·Δt/2.

Conventional TDR reads Δt with thresholds and edge detection. This works well on clean traces with strong reflections. It degrades with noise, weak ("soft") faults, lossy cables and closely spaced edges.

This project builds a calibrated TDR setup and a transmission-line simulator. It then compares a conventional baseline with Random Forest and Extra Trees models trained on simulated traces, and measures how well the models transfer to lab data.

## 2. Theory

See `docs/theory_sheet.md`. The key relations are:
- Γ = (ZL − Z0)/(ZL + Z0): the reflected step equals Γ·V_inc, so the polarity separates high-impedance faults from low-impedance ones.
- d = vp·Δt/2.
- Attenuation α(f) = α_dc + k_s√f + k_d f, which makes the reflected edge smaller and slower.
- Resolution limit Δd_min ≈ vp·t_r/2.

## 3. Experimental setup and calibration

*To be completed with the lab session* (`hardware/LAB_PROCEDURE.md`): instruments, cable, wiring photo and diagram, generator and scope settings, the calibration table (`data/calibration.json`), Figure 0 (Δt vs L) and the measured resolution.

**Method validation before the lab.** The whole lab chain was rehearsed on a simulated scope: capture → CSV → log → calibration. With open-circuit traces on 2, 5 and 10 m of simulated RG-58 (true vp = 1.979×10⁸ m/s), the two-length 50%-timing fit returned vp = 1.961×10⁸ ± 0.001×10⁸ m/s, which is **0.9% low**. Fitting the full simulator to one trace (`src/fit_sim.py`) returned 1.983×10⁸ m/s (0.2% off).

The bias of the timing method is physical. Skin-effect dispersion delays the 50% point of the reflected edge more on longer cables, which inflates the Δt-vs-L slope. On real cables we expect the same effect, so both estimates will be reported.

## 4. Simulation model (WP4)

`src/sim_tdr.py` computes the step response at the tee in the frequency domain:
- The input reflection coefficient Γ_in(f) = Γ_fault(f)·e^(−2γ(f)d) is built from the far end back to the tee, with γ = α(f) + jβ(f).
- The skin-effect term appears in both α and β, so the model is dispersive.
- The tee voltage is V_s·Z_in∥Z_scope/(R_s + Z_in∥Z_scope). This includes generator mismatch, the scope's input capacitance and all multiple reflections.
- A Gaussian filter sets the system rise time. An inverse FFT gives the step response.
- The result is then "measured" by a scope model: trigger jitter, sample interval 0.5/1/2 ns, white noise at a set SNR, baseline drift and offset, and 8-bit quantisation.

Fault geometries:
- end loads (open, short, matched, resistor)
- a series resistor or shunt resistor mid-line
- an impedance step (50/75 Ω joint)
- a tee with an open stub

Physics checks (`tests/test_physics_baseline.py`):
- final levels 2, 0, 1 and 1+Γ for the end loads
- Γ = ±1/3 for 50 Ω series and shunt resistors
- Γ = 0.2 for a 75 Ω joint
- a −1/3 dip for a stub that returns to the line level at DC
- Δt within 1.5 ns of 2d/vp

The brief's simpler analytic model is kept as `model="simple"`. It ignores the frequency dependence of the loss, so it under-predicts the settled level of a 5 m open (1.84 vs 1.97·V_inc; Figure 5).

Parameter ranges (centred on the calibration once it exists):

| Parameter | Range |
|---|---|
| Fault distance | 0.5–20 m |
| Classes | open / short / matched / partial, balanced |
| Partial \|Γ\| | 0.05–0.70 (end resistor, series R, shunt R, impedance step, open stub) |
| vp | nominal ± 3% |
| Attenuation | datasheet × 0.7–1.3 |
| Rise time | 2–10 ns (prior; calibrated ± 30% after the lab) |
| SNR | 10–40 dB, defined as 20·log10(V_inc/σ) |
| Generator R_s | Z0 × 0.92–1.08 |
| Scope C | 8–20 pF |

## 5. Methods

**Preprocessing (`src/preprocess.py`).** Every trace is processed the same way:
1. Subtract the median of the pre-trigger region.
2. Divide by V_inc (from calibration, or estimated from the trace).
3. Shift the time axis so the incident edge's 50% crossing is at t = 0.
4. Denoise with a Gaussian whose width grows with the measured noise (0.3–0.9 × rise time).

**Baseline (`src/baseline.py`).**
- The threshold on dv/dt is max(3% of the incident slope, 4.5 × robust noise of dv/dt).
- The first lobe after the incident edge with an amplitude of at least 2% is the reflection. Δt is taken 50%-to-50% between the levels before and after the lobe.
- Γ is the lobe amplitude, compensated for loss. The class comes from Γ: |amp| < 0.035 → matched, |Γ| ≥ 0.82 → open or short, otherwise partial.
- Same-polarity reflections that merge with the incident edge are flagged and timed from the lobe centroid.

**Inputs to the models.**
- Method A: the normalised trace on a common 256-point, 1 ns grid.
- Method B: 23 engineered features, listed in `docs/data_dictionary.md`. They include the baseline's Δt, amplitude, polarity, the settled level, the reflected rise time, noise, Ts, threshold-crossing times, window energies and second-reflection features.

No label or simulation-only quantity is used as an input.

**Models (`src/train.py`, `src/models.py`).** Five families, chosen from the reading list (`docs/model_selection.md`):
- Random Forest and Extra Trees (100 trees), from the brief;
- k-nearest neighbours (Slimani et al.);
- an MLP neural network (Smail et al.);
- a 1-D CNN in PyTorch on the raw trace (Scarpetta et al.; Slimani et al.).

RF, ET, KNN and MLP are trained on both Method A and Method B; the CNN on Method A only.
- Regression target: Δt in ns, on faulty traces only. Distance is then vp_cal·Δt/2, which keeps calibration error separate from model error.
- Classification target: the four classes.
- Hyper-parameters were chosen on a separate 4,000-trace validation set (`report/results/validation_grid.csv`). Training used 20,000 traces.

Test sets use separate random seeds and are never used for tuning.

**Experiments.**

| # | Question | Set-up |
|---|---|---|
| E1 | Does ML beat the baseline in noise? | 7 SNR levels × 1,200 traces |
| E2 | Interpolation and extrapolation over distance | retrain on 0.5–4 m and 6–14 m only; test on the 4–6 m gap and on > 14 m |
| E3 | How large is the sim-to-real gap? | train on simulation, test on the lab set |
| E4 | Does a little real data help? | add 10% of the lab set (weight 5) to training, test on the rest |
| E5 | Where do soft faults fail? | \|Γ\| from 0.01 to 0.3 at 30 dB |
| E6 | Do physics features help? | Method A vs Method B |

Until the lab data exists, E3/E4 use a **proxy lab set**: simulated traces with artifacts absent from training. These are a 3–12 cm off-impedance adapter at the tee, generator overshoot and ringing, and 1/f noise.

**Metrics.**
- Distance: MAE, RMSE and median absolute error in metres and in % of the cable length, plus Δt MAE in ns.
- Coverage: the share of faulty traces that receive a distance at all. The baseline can return "no reflection"; the models always answer.
- For a fair comparison, models are also scored **on exactly the traces the baseline located**.
- Classification: accuracy, macro precision, recall and F1, and confusion matrices.

## 6. Results

All results are on simulated RG-58 test sets that were never used for training or tuning. Full tables: `report/results/summary.md` and the CSV files beside it. Figures: `report/figures/`.

### 6.1 Mixed test set (6,000 traces, SNR 10–40 dB, all classes)

| Method | Faults given a distance | MAE (m) | RMSE (m) | Median AE (m) | MAE on the traces the baseline located (m) |
|---|---|---|---|---|---|
| Baseline | 84.8 % | 0.261 | 0.756 | 0.146 | 0.261 |
| RF, raw samples (A) | 100 % | 0.526 | 1.321 | 0.171 | 0.287 |
| Extra Trees, raw (A) | 100 % | 0.471 | 1.223 | 0.163 | 0.249 |
| RF, features (B) | 100 % | 0.370 | 1.035 | 0.160 | 0.190 |
| Extra Trees, features (B) | 100 % | 0.369 | 1.060 | 0.156 | **0.187** |

On the traces the baseline can locate, the feature-based models reduce MAE by about 28% (0.26 → 0.19 m). They also return a distance for the 15% of faults the baseline misses. Those are the hardest traces, which is why their all-trace MAE is higher. Figure 2 shows predicted vs true distance, and Figure 3 shows error vs distance.

**Classification** (Figure 4):

| Method | Accuracy | Macro F1 |
|---|---|---|
| Baseline | 86.1 % | 0.860 |
| RF / Extra Trees, raw (A) | 96.9 % | 0.968 |
| RF / Extra Trees, features (B) | 97.6 / 97.8 % | 0.976 / 0.978 |

The baseline's main error is labelling 37% of partial faults as "matched". These are weak reflections below its threshold.

### 6.2 E1: noise (Figure 1)

MAE (m), each method scored on the same traces (the faults the baseline located):

| SNR (dB) | 10 | 15 | 20 | 25 | 30 | 35 | 40 |
|---|---|---|---|---|---|---|---|
| Baseline located | 44 % | 71 % | 86 % | 89 % | 96 % | 98 % | 99 % |
| Baseline | 0.512 | 0.359 | 0.329 | 0.241 | 0.192 | 0.201 | 0.195 |
| Extra Trees, raw (A) | 0.654 | 0.299 | 0.219 | 0.214 | 0.201 | 0.170 | 0.190 |
| Extra Trees, features (B) | **0.344** | **0.233** | **0.176** | **0.179** | **0.153** | **0.168** | **0.158** |

On all faulty traces, ET-B reaches MAE 1.12 m at 10 dB, 0.33 m at 20 dB and 0.17 m at 40 dB.

### 6.3 E2: held-out distances (Figure 6)

The models were retrained on 0.5–4 m and 6–14 m only.

| Band | Baseline | ET-A | ET-B |
|---|---|---|---|
| In range | 0.22 | 0.35 | 0.29 |
| Gap 4–6 m (interpolation) | 0.12 | 0.46 | 0.56 |
| Beyond 14 m (extrapolation) | 0.38 | 4.93 | 3.57 |

### 6.4 E3/E4: sim-to-lab gap (Figure 8). PROXY data until the lab session

The proxy set has an adapter discontinuity, generator ringing and 1/f noise; 1,351 test traces.

| Method | Located | E3 MAE, all located (m) | E3 MAE on the traces the baseline located (m) | E4 MAE, +149 traces fine-tune (m) | E3 accuracy |
|---|---|---|---|---|---|
| Baseline | 81 % | 0.700 | 0.700 | – | 81.2 % |
| Extra Trees, raw (A) | 100 % | 0.669 | 0.330 | 0.671 | 94.4 % |
| RF, features (B) | 100 % | 0.677 | 0.253 | 0.669 | 93.6 % |

6% of the faults the baseline located are off by more than 1 m. 48 of these 54 gross errors are placed too early, at about 1–1.5 m, on small (2–8%) lobes from the generator's ringing and the adapter echo.

### 6.5 E5: soft faults at 30 dB (Figure 7)

| \|Γ\| | 0.03 | 0.05 | 0.08 | 0.12 | 0.2 | 0.3 |
|---|---|---|---|---|---|---|
| Baseline detects | 2 % | 2 % | 9 % | 35 % | 78 % | 94 % |
| RF, features (B) detects | 9 % | 45 % | 89 % | 99.5 % | 100 % | 100 % |

### 6.6 E6: raw samples (A) vs physics features (B)

Averaged over the E1 sweep:

| Input | MAE (m) | RMSE (m) | Macro F1 |
|---|---|---|---|
| Raw samples (A) | 0.50 (ET) / 0.56 (RF) | 1.03 / 1.12 | 0.965 / 0.961 |
| Features (B) | **0.39** (ET) / 0.40 (RF) | 0.89 / 0.88 | **0.974** / 0.971 |

The most important features are timing features, followed by window energy (Figure 9):
- **Extra Trees:** dv/dt-peak time 0.19, baseline Δt 0.18, 25% crossing time 0.17, energy in the 60–120 ns window 0.16.
- **Random Forest:** the 60–120 ns window energy leads with 0.32.

### 6.7 Model families from the literature (KNN, MLP, 1-D CNN)

Mixed test set; "fair MAE" means the error on the faults the baseline located (Figures 1, 7 and 10):

| Model | Fair MAE (m) | MAE over all faults (m) | Accuracy | Fair MAE at 10 dB (m) | Detected at \|Γ\| = 0.08 | E2 MAE beyond 14 m (m) |
|---|---|---|---|---|---|---|
| Baseline | 0.261 | 0.261 (84.8% located) | 86.1 % | 0.512 | 9 % | **0.38** |
| Extra Trees, features | **0.187** | 0.369 | 97.8 % | 0.344 | 88 % | 3.57 |
| 1-D CNN, raw | 0.214 | **0.315** | **98.3 %** | **0.297** | **96 %** | 6.48 |
| MLP, raw / features | 0.265 / 0.240 | 0.439 / 0.508 | 97.1 / 96.8 % | 0.517 / 0.483 | 93 / 63 % | 3.48 / 1.44 |
| KNN, raw / features | 0.256 / 0.365 | 0.482 / 0.752 | 95.5 / 94.7 % | 0.441 / 0.738 | 31 / 42 % | 4.00 / 4.14 |

### 6.8 External real data (Zenodo, pulse TDR)

**Measured.** Every model is trained only on the dataset's simulated traces, then tested three ways:
- **Z1:** 20,000 held-out simulated traces.
- **Z2:** the same task with noise ×1, ×3, ×10 and ×30.
- **Z3:** **the 16 real measured traces** (65–143 m cables, 1–4 capacitive faults plus the open end).

Targets: the distance to the first discontinuity, the cable length, and the type of the first discontinuity. Sources: `report/results/zenodo_summary.md`, `zenodo_results_all_models.csv` and Figure Z3.

| Model | Z1 MAE first fault (m) | Z1 MAE length (m) | Z1 type accuracy | **Z3 real**: MAE first fault (m) | **Z3 real**: MAE length (m) | **Z3 real**: type accuracy |
|---|---|---|---|---|---|---|
| Matched-filter baseline | 4.41 | 8.35 | 0.814 | 8.64 | 13.16 | 0.56 |
| Extra Trees, features | **1.23** | **0.50** | 0.996 | 5.62 | **0.61** | 1.00 |
| Random Forest, features | 1.35 | 0.63 | 0.996 | 5.60 | 1.09 | 1.00 |
| MLP, raw | 5.32 | 0.55 | 0.937 | 4.53 | 2.34 | 1.00 |
| Extra Trees, raw (run 1) | 2.82 | 0.47 | 1.000 | 1.98 | 0.90 | 1.00 |
| 1-D CNN, raw (multi-task) | 3.22 | 2.63 | **1.000** | **1.23** | 4.22 | 1.00 |
| k-NN, raw | 23.84 | 0.92 | 0.744 | 32.73 | 1.58 | 0.50 |

**Findings:**
- **On real measurements, ML beats the classical baseline by a wide margin.** First-fault error is 1.2 m (CNN) instead of 8.6 m. The cable length comes within 0.6 m on 65–143 m cables (ET-B, −2.1 to +1.2 %), against 13 m for the baseline.
- **There is a sim-to-real gap**, and it depends on the model. On ET-B's first-fault distance the error grows from 1.2 m to 5.6 m, while the CNN improves (3.2 → 1.2 m) on the 16 real traces. The real set is small, so the CNN's advantage there must be read with care.
- **Noise (Z2), all models trained at noise ×1:**
  - At ×3 the raw-input models already collapse: CNN 13.4 m, RF-A 27.6 m, ET-A 19.6 m, MLP-A 19.4 m first-fault error.
  - Extra Trees on features degrades gracefully: 1.2 → 2.3 → 5.0 → 15.9 m.
  - At ×10 and ×30 the matched-filter baseline is the best first-fault locator (3.4 and 12.3 m).
  - Training with noise augmentation is the obvious next step.
- **k-NN on raw pulse traces fails at the first-fault distance (24 m).** It finds traces of similar overall shape, which are dominated by the large open-end echo, so it can't place the small first echo. Its length estimate is fine (0.9 m).
- **Checks:**
  - Re-running Z1 with independent noise changed every number by less than about 2 % (`zenodo_seed_check.csv`).
  - The real traces' own noise matches the noise level the baseline's threshold assumes (ratio 0.89–1.15, `zenodo_noise_check.csv`).
  - The CNN trained 6 epochs (100 min budget); validation MAE fell from 5.4 to 2.9 m.

## 7. Discussion

**Which literature model to use.**
- **1-D CNN** (Scarpetta, Slimani): the strongest single model whenever the test conditions are inside the training distribution. It has the best all-trace accuracy, low-SNR accuracy, soft-fault detection and classification. It is also the most fragile outside that distribution, with the worst extrapolation (6.5 m). On the proxy artifacts it has the lowest all-trace error (0.63 m), but it is worse than the feature trees on the traces the baseline locates (0.35 vs 0.25 m).
- **KNN:** its reported advantage (Slimani et al.) is not reproduced on step TDR.
- **MLP on physics features** (Smail-style inverse model): extrapolates best of all learned models (1.4 m), but has outliers.
- **Overall:** a practical system would combine a CNN or Extra Trees inside the trained range, the physics baseline as a fallback outside it, and the MLP's smoother behaviour for range checks.

**The brief's hypothesis holds.** In clean conditions (≥ 30 dB) the baseline is nearly as good as ML on the faults it finds: 0.19–0.20 m vs 0.15–0.17 m. Part of the remaining error is shared by every method. Distances are converted with the calibrated vp, while each simulated cable's true vp varies by ±3%, which alone is about ±0.3 m at 10 m.

ML adds most where the brief expected:
- **Noise.** At 10–20 dB the feature models are 33–47% more accurate on the same traces, and they still answer when the baseline finds nothing. Those extra answers are rough: ≈ 1.1 m MAE at 10 dB.
- **Soft faults.** The detection limit at 30 dB drops from |Γ| ≈ 0.15 (baseline, 50% detection) to |Γ| ≈ 0.055 (RF-B).
- **Classification.** 98% vs 86% accuracy.
- **Systematic bias.** On faults beyond 12 m, the 50% timing rule over-estimates Δt by +1.07 ns on average (+0.10 m) because of dispersion. ET-B's mean bias is −0.27 ns (−0.04 m): the models learn the dispersion delay.

**Physics features beat raw samples (E6).** Method B is better at every SNR. Method A on 256 raw samples is *worse* than the baseline at 10 dB (0.65 vs 0.51 m). The engineered Δt, amplitude and crossing times carry the physics in a form that trees use efficiently. This supports the "physics-informed" design.

**Trees do not extrapolate (E2).** Beyond the trained distance range the error explodes to 3.6–5.3 m, while the baseline, being pure physics, stays at 0.38 m. Inside a 2 m gap the models interpolate with 1.3–1.9× their in-range error. Deployment therefore needs training ranges that cover the real cables. A hybrid is safest: trust the baseline when its Δt lies outside the training range.

**Sim-to-real (E3/E4, proxy).** Plausible artifacts that are absent from training hurt every method, but the baseline most:
- **Baseline:** it locates only 81% of faults, and its MAE rises from 0.26 to 0.70 m. Most of that increase comes from false early detections on the generator's ringing and the adapter echo. A matched-load reference subtraction would remove these.
- **ML on the same traces:** the feature models stay at 0.25 m and the raw-sample models at 0.33 m, so they are far more robust to these artifacts. Their all-trace MAE (0.67–0.75 m) is dominated by the hard traces the baseline cannot locate at all.
- **Classification:** 93–94% vs 81%.

Adding 10% of the target-domain traces (149 traces, weight 5) to 20,000 simulated ones did not measurably help, which is a negative result. The likely reasons are that the fine-tune set is too small and too lightly weighted against the simulated majority, and that trees cannot adapt features they never saw. The more promising routes are:
- fitting the simulator to the lab (`fit_sim`), then retraining;
- domain randomisation, i.e. training with artifacts switched on;
- subtracting a reference (matched-load) trace to cancel the generator's own ringing.

These conclusions must be re-checked on the real lab data.

## 8. Limitations

- **Simulation-only so far.** Apart from the rehearsal, every number comes from the simulator. The E3/E4 proxy measures robustness to *plausible* artifacts; it is not a measurement of the real gap.
- **Single discontinuity.** Training and evaluation assume one main discontinuity. Multiple faults, or a strong far-end echo behind a weak fault, are out of scope.
- **Tree models cannot extrapolate** beyond the distances, rise times, cable types and SNRs they were trained on (E2). The training ranges must cover the deployment conditions; retrain after calibration.
- **Resolution.** Faults closer than Δd_min ≈ vp·t_r/2 to the tee merge with the incident edge. This is ≈ 0.4 m at 4 ns and ≈ 1 m at 10 ns. Neither method resolves them reliably.
- **Cable model.** The RG-58/174/316/59 presets use typical datasheet attenuation. vp and attenuation of the actual cable come from calibration. Temperature, bending and connector wear are not modelled.
- **Velocity calibration.** 50%-timing calibration is biased ≈ 0.5–1% low by dispersion (Section 3). This is a systematic distance error of ≈ 5–10 cm at 10 m, unless the fitted simulator value is used.
- **Classification of near-matched loads.** Partial faults with |Γ| < 0.05 are physically close to "matched". The class boundary is a convention, not a measurement.
- **Instrument bandwidth.** Scope bandwidth and the generator edge set t_r. The fast-edge pulser (`hardware/fast_edge_pulser.md`) is a possible mitigation, subject to approval.
- **External data.** The Zenodo dataset (10.5281/zenodo.5720438) was checked against the go/no-go list and rated PARTIAL. It uses Gaussian pulses, multi-fault lab traces and capacitive/open labels only, so it is cited as related work (`docs/zenodo_check.md`).

## 9. Next steps

1. Lab session: calibration, then the test matrix (`hardware/LAB_PROCEDURE.md`).
2. Re-centre the simulator on the calibration and on the `fit_sim` results, then retrain.
3. Run E3/E4 on real data, and update Sections 3, 6 and 7.
4. Optional:
   - domain randomisation (train with artifacts switched on);
   - matched-load reference subtraction in the baseline;
   - a hybrid ML + baseline decision outside the training range;
   - multi-fault outputs on the Zenodo data.

The full done / pending list is in `docs/PROJECT_STATUS.md`.

## References

See `docs/literature.md` for full entries and summaries.
- S. J. Chang, J. B. Park, IEEE TIE 66(3), 2019. doi:10.1109/TIE.2018.2835386
- Y.-J. Shin et al., IEEE TIM 54(6), 2005. doi:10.1109/TIM.2005.858115
- M. K. Smail et al., IEEE TMAG 47(5), 2011. doi:10.1109/TMAG.2010.2089503
- H. Slimani et al., IEEE AUTOTESTCON 2024. doi:10.1109/AUTOTESTCON47465.2024.10697515
- H. Slimani et al., IEEE I&M Magazine 28(7), 2025. doi:10.1109/MIM.2025.11198883
- M. Scarpetta et al., Zenodo, 2021. doi:10.5281/zenodo.5720438 (CC BY 4.0)
