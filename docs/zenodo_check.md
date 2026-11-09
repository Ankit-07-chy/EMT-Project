# Zenodo dataset check: record 5720438

Checked on 2026-11-06. Only metadata was read: the Zenodo REST API record, the files endpoint and Zenodo's zip preview listing. **No data archive was downloaded.**
Physical details (cable, sampling, labels) come from the companion open-access paper (Sensors 2021, CC BY 4.0), which the record's authors cite as the source of this data. Wherever an answer relies on the paper rather than the Zenodo metadata, it says so.

## 1. Metadata summary

| Field | Value | Source |
|---|---|---|
| Title | Supplementary material for the paper "Detection and Characterization of Multiple Discontinuities in Cables with Time Domain Reflectometry and Convolutional Neural Networks" | API `metadata.title` |
| Authors | Marco Scarpetta, Maurizio Spadavecchia, Francesco Adamo, Mattia Alessandro Ragolia, Nicola Giaquinto (all Polytechnic University of Bari) | API `metadata.creators` |
| Year / publication date | 2021 (`publication_date: 2021-11-23`; record created 2021-11-30) | API |
| Version | 1.0 (only version; `is_last: true`) | API `metadata.version`, `relations.version` |
| DOI | 10.5281/zenodo.5720438 (concept DOI 10.5281/zenodo.5720437) | API `doi`, `conceptdoi` |
| Resource type | Dataset | API `metadata.resource_type` |
| Access / license | `access_right: open`, `license.id: cc-by-4.0` | API |
| Keywords | time domain reflectometry; distributed sensing; fault detection; convolutional neural network; time-domain analysis | API `metadata.keywords` |
| Description (verbatim) | "dataset of labeled simulated TDR signals (1 million samples); dataset of labeled experimental signals (16 samples); trained convolutional neural network model" | API `metadata.description` |
| Total size | **4,180,670,194 bytes (about 4.18 GB / 3.89 GiB)** in a single zip; md5 `6b6f041215f266cdeb3e1aef0ca913f6` | API `files[0]` |
| Companion paper | Scarpetta et al., *Sensors* 21(23):8032, 2021, doi:10.3390/s21238032 (its Data Availability Statement points to this record) | Crossref, Europe PMC PMC8659911 |

### File list

There is one file at the record level: `dataset_tdr_2021.zip` (4.18 GB, `application/zip`). According to Zenodo's zip preview (https://zenodo.org/records/5720438/preview/dataset_tdr_2021.zip), it contains:

| Path inside zip | Size (as shown by Zenodo preview) |
|---|---|
| `README.md` | 4.3 kB |
| `dataset.npz` | 4.2 GB (the 1,000,000 simulated signals, per the record description) |
| `experimental_signals.npz` | 132.8 kB (the 16 lab signals, per the record description) |
| `saved_model/saved_model.pb` | 256.2 kB |
| `saved_model/variables/variables.data-00000-of-00001` | 5.4 MB |
| `saved_model/variables/variables.index` | 1.3 kB |

**README not read.** The README exists only inside the zip. Zenodo's per-entry endpoint (`/api/records/5720438/files/dataset_tdr_2021.zip/container[/README.md]`) returned **HTTP 403**. Reading it, or even the 133 kB experimental file, would require downloading the whole 4.18 GB archive, which was not done. As a result, the array names, label encoding and any time vector inside the `.npz` files are **Unknown**.

## 2. Checklist

| # | Question | Answer | Evidence |
|---|---|---|---|
| 1 | Time-domain reflection data? | **Yes** (Gaussian **pulse**, not a step) | Zenodo: "dataset of labeled simulated TDR signals"; "dataset of labeled experimental signals". Paper §2.1: Gaussian pulse stimulus with σ = 8.1 ns, t0 = 100 ns, from an Agilent 33250A AWG, acquired on a LeCroy WaveRunner LT262. Paper §2.3.3: the simulated signals were "processed to remove the transmitted pulse" and Gaussian noise was added. Whether the experimental traces still contain the incident pulse is Unknown. |
| 2 | Distance label per trace? | **Yes**, but the format is Unknown | Zenodo: "labeled". Paper §2.3: each sample comes with "a label containing information about the faults in the cable and the cable length". In the paper, labels are encoded for the CNN: S = 32 cells, with a normalized position inside each cell. Whether the `.npz` stores raw metres or this cell encoding is Unknown because the README was not readable. |
| 3 | Fault-type label? | **Yes, but the classes don't match ours** | Paper §2.2/§2.3.3 has only 2 classes: "capacitive fault" (a parallel capacitor on a T-junction) and "line termination" (open). Fault size is labelled as **capacitance in pF**, not Γ. There are **no short, matched or resistive/partial classes.** |
| 4 | Sampling interval / time axis given? | **Yes in the paper; No in the Zenodo metadata** | Paper §2.1: "a sampling frequency of 250 MHz was used … N = 1024 … ~4 μs". That gives Ts = 4 ns, or about 0.4 m of fault distance per sample at vp ≈ 2×10^8 m/s. Whether a time vector is stored in the files is Unknown. |
| 5 | Cable type and vp known? | **Yes (from the paper), approximately** | Paper §2.1: "RG58-CU coaxial cables"; "the velocity of EM waves in RG-58CU cables is ~2 × 10^8 m/s". Table 1 gives calibrated R(ω) and L(ω) parameters (R0 = 0.022 Ω/m, R1 = 6.7×10⁻⁵, L0 = 2.3×10⁻⁷ H/m, L1 = 7.5×10⁻⁵). The Zenodo metadata itself does not state the cable or vp. Z0 is not stated explicitly in the text that was read. |
| 6 | Single discontinuity per trace? | **No** | The dataset was designed for *multiple* discontinuities. Paper Table 2 (simulated): 0–4 faults, at least 10 m apart, cable length 10–200 m, C = 50–500 pF, and **every trace includes the open-end reflection**. In the experimental traces (paper Tables 4–7), every trace has 1–4 capacitive faults plus the open end, so 2–5 reflections. Only simulated traces with N_F = 0 (open end only) would be single-discontinuity, and filtering them depends on the unknown label format. |
| 7 | Real or simulated? | **Both** | Zenodo: 1,000,000 simulated + 16 experimental. The simulations used the LineLab transmission-line simulator with an RG58-CU model calibrated by stepped-frequency waveform reflectometry. The paper reports that calibration cut the sim-vs-measurement RMSE from 0.098 V to 0.044 V. |
| 8 | Open license (which exact license)? | **Yes: CC BY 4.0** | API: `"license": {"id": "cc-by-4.0"}`, `"access_right": "open"`. Attribution is required. |
| 9 | File format(s) and sizes? | **NumPy `.npz` + TensorFlow SavedModel, inside one 4.18 GB zip** | See the file list above. Individual files cannot be downloaded separately (container endpoint returns 403), so the whole 4.18 GB zip must be fetched even to get the 133 kB experimental file. |
| 10 | Large enough, several distances? | **Simulated: Yes. Real: No** | Simulated: 10⁶ traces, lengths 10–200 m (enough for training, but it is *their* simulator, not real data). Real: only **16 traces**. Per paper Tables 4–7: 6 single-fault (fault always at **50 m**, 65 m cable, C = 107–450 pF), 6 two-fault (15 m and 65 m, 81 m cable), 2 three-fault (131 m cable), 2 four-fault (143 m cable). That gives only 4 distinct cable lengths (65/81/131/143 m) and 5 distinct fault positions (15/50/65/115/131 m). Mapping these tables onto `experimental_signals.npz` is inferred from the matching count of 16 and is not verified. |

## 3. Verdict: **PARTIAL (restricted use)**

Not usable as a general external test set for E3, and **not suitable for fine-tuning in E4**. It is usable only as a small, optional supplementary real-data check of **distance localization**, plus related work.

Decisive reasons:
1. **The real data is tiny and multi-reflection.** There are 16 lab traces, all with 2–5 discontinuities (capacitive faults plus the open end), covering only 4 cable lengths and 5 fault positions. Every single-fault trace has its fault at 50 m. That is too few traces and too few distances for E4 fine-tuning or a statistically meaningful E3 test, and it conflicts with our single-discontinuity assumption.
2. **The label space doesn't match ours.** The only classes are capacitive fault and open termination, with fault size labelled in pF rather than Γ. There are no short, matched or resistive/partial cases, so it cannot test the open/short/matched/partial classifier or Γ regression.
3. **The stimulus and access don't match.** It uses a Gaussian pulse (σ = 8.1 ns) at 250 MS/s rather than a fast step, so models trained on step responses won't transfer without adaptation. The incident pulse is removed from the simulated traces. The data is reachable only through a monolithic 4.18 GB zip, and the README, which holds the label format, is not readable remotely.

What is missing for a PASS: step-stimulus traces; real single-discontinuity traces at many distances; open/short/matched/partial labels or Γ labels; a documented time axis and label format that can be checked without the 4.18 GB download.

If used at all (optional): download once, keep only `experimental_signals.npz`, and evaluate the first-reflection or open-end distance error of the threshold baseline against the RF/ET models in pulse mode on these 16 RG-58 traces. Report it as a qualitative cross-lab sanity check, not as a headline E3 metric. If the pipeline cannot handle pulse-stimulus or multi-reflection traces, treat this record as **FAIL**, meaning related work only.

Also useful as related work (theory/sim-to-real), independent of the data: the companion paper's calibration of a physics-based RG58 transmission-line model from SFWR measurements before generating training data. It is a direct precedent for our physics-informed simulation and sim-to-real gap discussion.

## 4. Suggested citation

Dataset (APA-style):
> Scarpetta, M., Spadavecchia, M., Adamo, F., Ragolia, M. A., & Giaquinto, N. (2021). *Supplementary material for the paper "Detection and Characterization of Multiple Discontinuities in Cables with Time Domain Reflectometry and Convolutional Neural Networks"* (Version 1.0) [Data set]. Zenodo. https://doi.org/10.5281/zenodo.5720438

Dataset (IEEE-style):
> M. Scarpetta, M. Spadavecchia, F. Adamo, M. A. Ragolia, and N. Giaquinto, "Supplementary material for the paper 'Detection and Characterization of Multiple Discontinuities in Cables with Time Domain Reflectometry and Convolutional Neural Networks'," Zenodo, v1.0, 2021, doi: 10.5281/zenodo.5720438. License: CC BY 4.0.

Companion paper (cite alongside the dataset):
> M. Scarpetta, M. Spadavecchia, F. Adamo, M. A. Ragolia, and N. Giaquinto, "Detection and Characterization of Multiple Discontinuities in Cables with Time-Domain Reflectometry and Convolutional Neural Networks," *Sensors*, vol. 21, no. 23, Art. no. 8032, Dec. 2021, doi: 10.3390/s21238032.

## Sources checked
- https://zenodo.org/api/records/5720438 (HTTP 200: full metadata)
- https://zenodo.org/api/records/5720438/files (HTTP 200: one file entry, no README at record level)
- https://zenodo.org/records/5720438/preview/dataset_tdr_2021.zip (HTTP 200: zip table of contents only)
- https://zenodo.org/api/records/5720438/files/dataset_tdr_2021.zip/container and `.../container/README.md` (**HTTP 403**: README not accessible)
- https://api.crossref.org/works?query.bibliographic=... (found companion paper doi:10.3390/s21238032, CC BY 4.0)
- https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=DOI:"10.3390/s21238032" and `.../PMC8659911/fullTextXML` (abstract and full text of the companion paper)

---

## 5. Update (6 Nov 2026): how the dataset is now used

The project lead asked for the dataset to be downloaded and used to make the software side independent of our own hardware. The PARTIAL verdict above still holds for the *original* plan (an external test set for our step-TDR models). The dataset is instead used as a **second, self-contained domain** with its own training and its own real test traces:

| Item | Done |
|---|---|
| Download | `python index.py zenodo download`: resumable, 4,180,670,194 bytes, all CRCs verified |
| Safe loading | labels are pickled objects. They are read with a restricted unpickler that only allows numbers, lists, tuples, dicts and numpy arrays, never `allow_pickle=True`. The archive's TensorFlow model is **not** loaded. |
| Access | the 1M × 1024 float32 array is memory-mapped directly inside the zip (no 4 GB extraction, no full load into RAM) |
| Label facts found | every trace has exactly one termination and it is **open**. 0–4 capacitive faults (27% have none), 49–501 pF, cables 10–200 m, discontinuities ≥ 9.8 m apart. Real traces: 65–143 m, 1–4 faults. |
| Time axis | fitted from the data: 2.539 samples/m and pulse at sample 24.7. With 4 ns sampling, vp = 1.9686×10⁸ m/s (VF 0.657) |
| Targets used | reduced to the project's single-fault framing: distance to the first discontinuity, cable length (open end), and class of the first discontinuity (capacitive fault = "partial", or "open"). A termination class would be constant, because every termination is open. |
| Baseline | matched filter (Gaussian and derivative-of-Gaussian templates), calibrated on 5,000 training traces |
| Models | RF/ET/KNN/MLP (features: 200k traces; raw: 100k traces); multi-task 1-D CNN on all 800k training traces |
| Tests | Z1 on 20k held-out simulated traces; Z2 noise sweep at 1/3/10/30 × the README noise; **Z3 on the 16 real measured traces, never used in training** |

### Run history and checks
- **Run 1** (`zenodo all`): trained every model, including the CNN (6 epochs in the 100-minute budget; validation MAE 5.4 → 2.9 m). It wrote the Z1–Z3 tables, then stopped at the figure step: the code had been edited while it ran. Those tables are kept as `zenodo_*_run1.csv`.
- **Code review finding 8:** run 1 drew the Z1 test noise from the same random stream as the training features. Every split now draws its own noise.
- **Run 2** (`zenodo evaluate`, fixed code): re-evaluated every model stored in `models/zenodo_models.joblib` and wrote the tables, figures and summary.
- **Seed check:** every Z1 number changed by less than about 2 % between run 1 and run 2 (`zenodo_seed_check.csv`). The raw-input forests RF-A and ET-A are only in run 1 and are reported from there. Their Z2/Z3 inputs are identical in both runs.
- **Noise check (review finding 14):** the 16 real traces' own noise, after the baseline's high-pass, is 0.89–1.15 × the README noise level that the baseline's threshold assumes (median 1.00). So the threshold is set correctly (`zenodo_noise_check.csv`).
- **Model bundle:** 1.5 GB, almost all of it k-NN on 100 k raw traces, stored once per target (review finding 13, documented).

### Results (`report/results/zenodo_summary.md`, `zenodo_results_all_models.csv`)

| Model | Z1 sim: first fault / length MAE (m) | **Z3 real: first fault MAE (m)** | **Z3 real: length MAE (m)** | **Z3 real: type correct** |
|---|---|---|---|---|
| Matched-filter baseline | 4.40 / 8.35 | 8.64 | 13.16 | 9/16 |
| Extra Trees, features | **1.23 / 0.50** | 5.62 | **0.61** | 16/16 |
| Random Forest, features | 1.35 / 0.63 | 5.60 | 1.09 | 16/16 |
| 1-D CNN, raw (multi-task) | 3.22 / 2.63 | **1.23** | 4.22 | 16/16 |
| Extra Trees, raw (run 1) | 2.82 / 0.47 | 1.98 | 0.90 | 16/16 |
| MLP, raw | 5.32 / 0.55 | 4.53 | 2.34 | 16/16 |
| k-NN, raw | 23.84 / 0.92 | 32.73 | 1.58 | 8/16 |

What these results mean:
- **On the real traces, learned models beat the matched filter by a wide margin.** The CNN is best for the first fault and Extra Trees on features for the cable length (−2.1 … +1.2 % on 65–143 m).
- **Noise (Z2).** Raw-input models collapse at 3× the training noise. Extra Trees on features degrades gracefully. At 10–30× noise the matched filter is the most robust first-fault locator.
- **k-NN on raw pulse traces fails at the first fault:** similarity is dominated by the large open-end echo.

Discussion: report §6.8 and `docs/ML_ANALYSIS.md` §2.5 / §3.5.

**Citation:** M. Scarpetta, M. Spadavecchia, F. Adamo, M. A. Ragolia, N. Giaquinto, Zenodo, 2021, doi:10.5281/zenodo.5720438, CC BY 4.0.
