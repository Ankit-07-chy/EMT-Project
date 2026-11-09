# ML / NN performance analysis: localization and detection

**Every number here is measured** by the project's own scripts on held-out data. Each section names its source file. The labels are:
- **[sim]:** simulated test traces.
- **[real]:** the 16 measured traces of Zenodo 5720438.
- **[proxy]:** simulation with lab-like artifacts. It stands in for our own lab traces, which are **not yet measured** (pending the lab session).

Reproduce with `python index.py evaluate`, then `python index.py analyze` (tables in `report/results/analysis_*.csv` and `ml_analysis_summary.md`, figures `report/figures/a1–a6`), and `python index.py zenodo evaluate`.

---

## 1. Set-up

| Item | Value |
|---|---|
| Task | from one TDR trace, predict **distance to the fault** (localization) and **class** (detection): open, short, matched (no fault), partial |
| Inputs | Method A: normalised trace, 256 samples at 1 ns (−16…239 ns). Method B: 23 physics features (8 from the baseline detector) |
| Models | Random Forest, Extra Trees (100 trees), k-NN (k = 5/15, distance-weighted), MLP ((128, 64) or (256, 128)), 1-D CNN (4 conv blocks 16/32/64/64, dense 128): 18 stored models |
| Reference | classical baseline: derivative-lobe threshold, d = vp·Δt/2, rules on Γ |
| Training data | 20 000 simulated traces (seed 1); validation 4 000 (seed 2) used **only** for hyper-parameter selection |
| Test data [sim] | mixed set 6 000 traces (seed 3): 4 513 with a fault, 1 487 matched; d 0.5–20 m, SNR 10–40 dB, rise 2–10 ns, all fault kinds. E1: 7 × 1 200 at fixed SNR. E5: 8 × 600 weak faults |
| Regression target | Δt (ns), converted with the calibrated vp: d = vp·Δt/2 |
| Preprocessing failures | 2 of 4 513 faulted test traces (no incident edge) get no ML prediction and count against coverage |
| Selected hyper-parameters, sizes | `report/results/analysis_model_config.csv` (e.g. ET-B regression: max_features 1.0, min_samples_leaf 2) |

Metric definitions:
- **MAE** = mean |d̂ − d|; **RMSE** = √mean(d̂ − d)²; **P95** = 95th percentile of |error|; **bias** = mean(d̂ − d).
- **Coverage** = share of faulted traces that got a distance.
- **"Fair"** = scored only on the faults the baseline located, so every method answers the same traces.
- **Precision** = TP/(TP+FP); **recall** = TP/(TP+FN); **F1** = 2PR/(P+R); **macro-F1** = mean of the four per-class F1.
- **mAP and IoU** do not apply: there are no boxes in a 1-D signal.

---

## 2. Localization

### 2.1 Accuracy and error distribution [sim] (`analysis_localization.csv`, Figure a1)

| Method | Coverage | MAE (m) | Median (m) | RMSE (m) | P90 (m) | P95 (m) | Max (m) | Bias (m) | ≤ 0.25 m | ≤ 0.5 m | > 1 m | **Fair MAE (m)** | Fair P95 (m) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Baseline | **84.8 %** | 0.261 | 0.146 | 0.756 | 0.47 | 0.61 | 15.6 | +0.096 | 69.5 % | 91.2 % | 1.4 % | 0.261 | 0.61 |
| RF, raw (A) | 100 % | 0.526 | 0.171 | 1.321 | 1.15 | 2.68 | 11.9 | −0.008 | 63.5 % | 82.5 % | 10.7 % | 0.287 | 0.84 |
| RF, features (B) | 100 % | 0.370 | 0.160 | 1.035 | 0.55 | 1.27 | 17.3 | −0.020 | 67.2 % | 88.2 % | 5.7 % | 0.190 | 0.47 |
| ET, raw (A) | 100 % | 0.471 | 0.163 | 1.223 | 0.90 | 2.13 | 12.1 | −0.009 | 65.6 % | 84.9 % | 9.2 % | 0.249 | 0.63 |
| **ET, features (B)** | 100 % | 0.369 | 0.156 | 1.060 | 0.53 | 1.23 | 17.1 | −0.017 | 68.3 % | 89.1 % | 5.7 % | **0.187** | **0.46** |
| k-NN, raw (A) | 100 % | 0.482 | 0.169 | 1.322 | 0.75 | 2.05 | 15.8 | +0.004 | 64.3 % | 85.1 % | 8.3 % | 0.256 | 0.62 |
| k-NN, features (B) | 100 % | 0.752 | 0.277 | 1.705 | 1.58 | 3.78 | 13.9 | +0.008 | 46.2 % | 70.0 % | 14.9 % | 0.365 | 1.05 |
| MLP, raw (A) | 100 % | 0.439 | 0.200 | 1.049 | 0.77 | 1.47 | 12.3 | −0.029 | 58.0 % | 82.0 % | 7.6 % | 0.265 | 0.69 |
| MLP, features (B) | 100 % | 0.508 | 0.197 | 1.284 | 0.86 | 2.07 | 16.3 | +0.009 | 58.8 % | 81.8 % | 8.8 % | 0.240 | 0.64 |
| **1-D CNN, raw (A)** | 100 % | **0.315** | 0.188 | **0.830** | **0.51** | **0.70** | 17.3 | −0.044 | 65.1 % | 89.6 % | **2.9 %** | 0.214 | 0.54 |

Reading the table:
- **On the same traces** (fair columns), Extra Trees and Random Forest on physics features cut the baseline's error by about 28 % (0.26 → 0.19 m), and the 95th percentile from 0.61 to 0.46 m.
- **On every fault.** The baseline gives no distance for 15 % of faults. The models answer all of them, and those harder traces raise their averages. Among the models, the **1-D CNN** has the lowest all-trace error (MAE 0.32 m, P95 0.70 m, only 2.9 % of answers off by more than 1 m).
- **No method is biased:** |bias| ≤ 0.1 m everywhere. The worst cases are > 10 m (§2.4), which is why the median and P95 matter more than the maximum.

### 2.2 Noise (E1) [sim] (`e1_snr_sweep.csv`, Figure 1)

| SNR (dB) | Baseline coverage | Baseline fair MAE | ET-B fair MAE | CNN fair MAE | RF-A fair MAE |
|---|---|---|---|---|---|
| 10 | 44 % | 0.51 | 0.34 | 0.30 | 0.89 |
| 15 | 71 % | 0.36 | 0.23 | 0.24 | 0.40 |
| 20 | 86 % | 0.33 | 0.18 | 0.21 | 0.25 |
| 30 | 96 % | 0.19 | 0.15 | 0.19 | 0.22 |
| 40 | 99 % | 0.20 | 0.17 | 0.19 | 0.21 |

At low SNR the baseline both **misses** more faults (it locates 44 % at 10 dB) and is **less accurate** on the ones it finds. The best models stay at or below 0.35 m and answer every trace. Not every model is robust: RF on raw samples is worse than the baseline at 10 dB.

### 2.3 Conditions that affect localization [sim] (`analysis_localization_breakdown.csv`, Figures a2, a3, 3)

Fair MAE (m), i.e. the same traces for every method; "baseline finds" is the baseline's coverage in that group:

| Group | Baseline finds | Baseline | ET-B | RF-B | CNN | k-NN A |
|---|---|---|---|---|---|---|
| end: open | 95 % | 0.24 | 0.17 | 0.17 | 0.20 | 0.17 |
| end: short | 95 % | 0.24 | 0.16 | 0.16 | 0.22 | 0.17 |
| end: partial load | 64 % | 0.25 | 0.21 | 0.22 | 0.22 | 0.32 |
| series resistor | 58 % | 0.28 | 0.21 | 0.21 | 0.19 | 0.37 |
| shunt resistor | 63 % | 0.29 | 0.20 | 0.21 | 0.22 | 0.36 |
| impedance step | 64 % | 0.46 | 0.31 | 0.29 | 0.21 | 0.34 |
| **open stub** | 65 % | **0.77** | 0.55 | 0.74 | **0.50** | 2.46 |
| \|Γ\| < 0.1 | **14 %** | 0.58 | 0.64 | 0.86 | 0.56 | 1.96 |
| \|Γ\| 0.1–0.3 | 44 % | 0.38 | 0.33 | 0.33 | **0.23** | 0.57 |
| \|Γ\| ≥ 0.6 | 95 % | 0.24 | 0.17 | 0.17 | 0.21 | 0.17 |
| distance 2–5 m | 87 % | 0.12 | 0.09 | 0.10 | 0.16 | 0.16 |
| distance 15–20 m | 83 % | 0.41 | 0.29 | 0.28 | 0.30 | 0.37 |
| rise 2–4 ns | 84 % | 0.24 | 0.17 | 0.17 | 0.21 | 0.24 |
| rise 8–10 ns | 85 % | 0.30 | 0.20 | 0.21 | 0.21 | 0.28 |

What affects accuracy, in order of size:
1. **Fault strength |Γ|.** Below 0.1 every method is poor, and the baseline locates only 14 % of these faults.
2. **Fault geometry.** Stubs produce a dip-and-return, not a step; impedance steps are smaller.
3. **Distance.** Loss and dispersion slow and shrink the echo, so the error roughly triples from 2–5 m to 15–20 m.
4. **SNR** (§2.2).
5. **Rise time.** Within 2–10 ns it matters little, but it sets the minimum resolvable distance vp·t_r/2 (§5).

### 2.4 Failure cases (`analysis_worst_cases.csv`)

The 15 largest errors of ET-B (8.7–17.1 m) are:
- weak partial loads (|Γ| 0.07–0.38) at 10–30 dB;
- open stubs;
- weak shunts.

In **14 of the 15 the baseline found no echo either**: the trace carries almost no usable information. The regressor then falls back to a value in the middle of the trained range (8–14 m). A confidence threshold, or the hybrid rule (ML inside its range, baseline outside), would flag these cases.

### 2.5 Generalisation (E2) [sim] and the sim-to-real gap [proxy] [real]

**E2: models retrained without 4–6 m and without > 14 m** (`e2_heldout_distances.csv`, Figure 6):

| Band | Baseline | ET-B | CNN | MLP-B |
|---|---|---|---|---|
| in range | 0.22 | 0.29 | 0.25 | 0.43 |
| gap 4–6 m (interpolation) | 0.12 | 0.56 | 0.29 | 0.45 |
| beyond 14 m (extrapolation) | **0.38** | 3.57 | 6.48 | 1.44 |

Learned models interpolate acceptably but **cannot extrapolate**. The baseline has no training range.

**E3/E4 on the proxy set** (1 351 test traces with adapter reflections, ringing and 1/f noise; `e3_e4_sim_to_lab.csv`, Figure 8):
- Every method gets worse (baseline 0.70 m).
- On the faults the baseline locates, the models stay at 0.25–0.38 m (ET-B 0.26, RF-B 0.25; k-NN B 0.54).
- Fine-tuning with 149 labelled proxy traces (E4) changes MAE by ≤ 0.05 m. It **does not close the gap**.

**Real traces, Zenodo Z3** (16 measured traces, 65–143 m cables, models trained on that dataset's simulations only; `zenodo_results_all_models.csv`):

| Model | First fault, MAE (median) | Cable length, MAE | Length error range |
|---|---|---|---|
| Matched-filter baseline | 8.64 m (1.39) | 13.16 m | +0.8 … +145 % |
| **1-D CNN, raw** | **1.23 m (0.95)** | 4.22 m | −5.3 … +14.8 % |
| Extra Trees, raw | 1.98 m | 0.90 m | – |
| **Extra Trees, features** | 5.62 m (4.80) | **0.61 m** | **−2.1 … +1.2 %** |
| MLP, raw | 4.53 m (3.73) | 2.34 m | −5.9 … +3.3 % |
| k-NN, raw | 32.7 m | 1.58 m | – |

On real measurements the learned models beat the classical baseline by a wide margin. Which model is best depends on the target: the CNN for the first fault, Extra Trees on features for the cable length. With only 16 traces these are indicative, not definitive.

---

## 3. Detection

### 3.1 Is there a fault? (binary; matched = no fault) [sim] (`analysis_detection_binary.csv`)

| Method | TP | FP | FN | TN | Precision | Recall | F1 | False-alarm rate | Miss rate | Accuracy |
|---|---|---|---|---|---|---|---|---|---|---|
| Baseline | 3 820 | 22 | **693** | 1 465 | 0.994 | 0.846 | 0.914 | 1.5 % | **15.4 %** | 0.881 |
| RF-B | 4 412 | 36 | 101 | 1 451 | 0.992 | 0.978 | 0.985 | 2.4 % | 2.2 % | 0.977 |
| ET-B | 4 409 | 26 | 104 | 1 461 | 0.994 | 0.977 | 0.986 | 1.7 % | 2.3 % | 0.978 |
| k-NN B | 4 291 | 72 | 222 | 1 415 | 0.984 | 0.951 | 0.967 | 4.8 % | 4.9 % | 0.951 |
| MLP-A | 4 407 | 57 | 106 | 1 430 | 0.987 | 0.977 | 0.982 | 3.8 % | 2.4 % | 0.973 |
| **CNN-A** | 4 429 | **18** | **84** | 1 469 | **0.996** | **0.981** | **0.989** | **1.2 %** | **1.9 %** | **0.983** |

The baseline is precise (few false alarms) but **misses 15 % of faults**. The 1-D CNN misses 1.9 % with even fewer false alarms.

### 3.2 Which class? (4-class) [sim] (`classification.csv`, `analysis_detection_per_class.csv`, Figure a5)

| Method | Accuracy | Macro-F1 | F1 open | F1 short | F1 matched | F1 partial |
|---|---|---|---|---|---|---|
| Baseline | 0.861 | 0.860 | 0.958 | 0.947 | 0.804 | 0.730 |
| RF-B | 0.976 | 0.976 | 0.998 | 0.999 | 0.956 | 0.951 |
| ET-B | 0.978 | 0.978 | 0.999 | 0.999 | 0.958 | 0.954 |
| k-NN A | 0.955 | 0.954 | 0.999 | 0.999 | 0.917 | 0.900 |
| MLP-A | 0.971 | 0.970 | 0.996 | 0.998 | 0.947 | 0.939 |
| **CNN-A** | **0.983** | **0.983** | 1.000 | 0.999 | 0.967 | 0.964 |

**Confusion matrices** (rows true, columns predicted; open/short/matched/partial):
- **Baseline:**
  - Its dominant error: **539 of 1 461 partial faults called matched**, because the echo sat below its threshold.
  - Opens: 76 called matched, 47 called partial. Shorts: 78 called matched, 72 called partial.
- **CNN:**
  - 82 partial faults called matched and 18 matched lines called partial.
  - Opens and shorts are essentially perfect.

### 3.3 False negatives and false positives (`analysis_fn_fp.csv`, Figure a4)

| Condition | Baseline miss rate | CNN miss rate | Baseline false alarms | CNN false alarms |
|---|---|---|---|---|
| \|Γ\| < 0.1 | 87 % | 34 % | | |
| \|Γ\| 0.1–0.3 | 56 % | 4.2 % | | |
| \|Γ\| ≥ 0.6 | 5.7 % | 0.1 % | | |
| SNR 10–15 dB | 40 % | 5.5 % | 1.6 % | 5.2 % |
| SNR 30–40 dB | 3.5 % | 0.3 % | 0.6 % | 0.0 % |

- **False negatives (misses)** come from weak echoes, either small |Γ| or low SNR.
- **False positives** are rare for both methods. The CNN's 5.2 % at 10–15 dB is the price of its higher sensitivity; a probability threshold can trade it back.

### 3.4 Weak faults (E5) [sim] (`e5_soft_faults.csv`, Figure 7)

Detection rate of partial faults at 30 dB:

| \|Γ\| | 0.03 | 0.05 | 0.08 | 0.12 | 0.20 |
|---|---|---|---|---|---|
| Baseline | 2 % | 2 % | 9 % | 35 % | 78 % |
| ET-B | 8 % | 39 % | 88 % | 100 % | 100 % |
| CNN | 6 % | 55 % | **96 %** | 100 % | 100 % |
| MLP-A | 11 % | 57 % | 93 % | 100 % | 100 % |

The learned models detect faults with **about 2–3× smaller |Γ|** than the threshold method (≈ 90 % detection at |Γ| = 0.08, where the baseline needs about 0.2). Below |Γ| ≈ 0.03, nothing is detected reliably at 30 dB.

### 3.5 Real traces [real] (Zenodo Z3)

Type of the first discontinuity (capacitive fault vs open end):
- every feature model and the CNN: **16/16**;
- matched-filter baseline: **9/16** (56 %);
- k-NN on raw traces: 8/16.

---

## 4. Raw samples (A) vs physics features (B): E6 [sim] (`e6_method_a_vs_b.csv`, Figure 10)

| Family | A: fair MAE | B: fair MAE | A: macro-F1 | B: macro-F1 |
|---|---|---|---|---|
| Random Forest | 0.34 | **0.21** | 0.961 | **0.971** |
| Extra Trees | 0.28 | **0.20** | 0.965 | **0.974** |
| k-NN | **0.27** | 0.40 | **0.952** | 0.944 |
| MLP | 0.29 | **0.27** | 0.965 | 0.964 |
| 1-D CNN | 0.22 | – | 0.980 | – |

Physics features help the tree ensembles most. k-NN prefers raw samples, because unscaled feature distances mix units. The CNN learns its own features from raw samples and matches the trees.

---

## 5. Speed and resources

Measured on this laptop's CPU (16 logical cores) with nothing else running (`analysis_latency.csv`, Figure a6).
- **Single trace** = one call per trace, the way the dashboard runs. Forests and k-NN are run single-threaded here, which is 4× faster for one trace than a thread pool: 26 → 6.4 ms for ET-B, measured. The dashboard now does the same.
- **Batched** = the cost per trace when 200 traces go through in one call.

| Stage | Single trace (ms) | Batched (ms per trace) |
|---|---|---|
| Front end: preprocess + baseline + 23 features | 0.75 | 0.75 |
| Extra Trees (distance / class), features | 6.7 / 6.7 | 0.10 / 0.09 |
| Random Forest (distance / class), features | 8.7 / 8.1 | 0.18 / 0.20 |
| k-NN raw (distance / class) | 7.4 / 8.7 | 0.12 / 0.16 |
| MLP (distance / class), features | 1.1 / 0.8 | 0.008 / 0.008 |
| 1-D CNN (distance / class) | 1.9 / 2.5 | 0.16 / 0.10 |

**End to end for one trace:**
- front end + best regressor (ET-B) + best classifier (CNN): **about 10 ms**;
- all 18 models, as the dashboard table shows: about 90 ms.

**Throughput in batch mode:** well over 1 000 traces per second for any single model.

Model files are listed in `analysis_model_config.csv`:
- forests: 1.4–33 MB each;
- k-NN: up to 19 MB (it stores the training traces);
- MLP: 0.2–1.9 MB;
- CNN: about 0.9 MB.

The whole simulation bundle is 157 MB. The Zenodo bundle is 1.5 GB, almost all of it k-NN on 100 k raw traces (review finding 13).

Training times:
- all 18 simulation models: 44 min wall time on 16 cores while sharing the CPU (about 20 min of model fitting);
- the Zenodo CNN: 6 epochs over 800 k traces in 100 min;
- evaluation E1–E6: 31 min.

---

## 6. Reliability, limitations and improvements

| Topic | Measured behaviour | Improvement |
|---|---|---|
| Weak faults | \|Γ\| < 0.05 at 30 dB unreliable for every method | averaging, faster edge (pulser), matched-load reference subtraction |
| Extrapolation | ML fails beyond the trained distances (E2) | train on the full range; hybrid rule; confidence threshold |
| Sim-to-lab | proxy gap not closed by 149 fine-tuning traces | domain randomisation (train with artifacts); real lab traces (pending) |
| Noise robustness on pulse data | raw-input models collapse at Zenodo noise ×3 | noise augmentation during training |
| Worst cases | mid-range guesses when the trace has no echo | report confidence; abstain below a threshold |
| k-NN on raw pulse traces | fails on small first echoes (Zenodo) | feature scaling per sample; prefer trees or CNN |
| Real data volume | 16 real traces (Zenodo); our own lab data pending | lab session S1–S12 |

**What is still to be measured:** every [proxy] number above must be repeated on our own lab traces, along with calibration accuracy, the real resolution limit and real-instrument latency. The pipeline switches to LAB automatically once the log has ≥ 20 traces (`hardware/README.md`, S13).
