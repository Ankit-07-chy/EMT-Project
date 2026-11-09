# Hardware report: everything left to do in the lab

> **New to the hardware part? Start with [README.md](README.md)**: the beginner's step-by-step manual (parts list, connection tables, power, assembly, ordered steps S1–S15, troubleshooting). This file is one of its companions.

**Project:** TDR cable fault detection with physics-informed machine learning
**Status (Nov 2026):** the software is complete and runs without any hardware:
- simulator, baseline, five model families (RF, Extra Trees, KNN, MLP, 1-D CNN), evaluation and dashboard;
- validated on simulated data and on 16 real measured traces from the literature (Zenodo, `report/results/zenodo_summary.md`).

**What remains is the hardware part:** measure our own cable, calibrate it, and record a labelled set of real traces. Every step below ends in a file the software already knows how to read.

Related documents:
- [HARDWARE_GUIDE.md](HARDWARE_GUIDE.md): **every task with its circuit diagram, the expected scope picture and the expected numbers** (diagrams in [circuits/](circuits/)).
- [LAB_PROCEDURE.md](LAB_PROCEDURE.md): bench-side instructions (settings tables, troubleshooting, printable log sheet).
- [fast_edge_pulser.md](fast_edge_pulser.md): optional 74AC14 step source.
- [../docs/theory_sheet.md](../docs/theory_sheet.md): the physics.

---

## 1. Summary: the whole job on one page

| # | Task | When | Output (deliverable) | Done when |
|---|---|---|---|---|
| H1 | Confirm cables, terminations, approved discontinuities and voltage limits with the instructor | before the lab | answers to §3 | all 6 questions answered |
| H2 | Install software and a VISA driver on the lab laptop; rehearse with the simulated scope | before the lab | `python index.py check` passes | rehearsal capture + calibrate run |
| H3 | Equipment discovery: models, bandwidth, rise times, cable markings | lab, first 15 min | table §5.1 filled | every row has a value |
| H4 | Build the TDR setup (generator → tee on scope CH1 → cable) | lab | setup photo + diagram | incident step visible, clean plateau |
| H5 | Calibration: 20 open-circuit traces on ≥ 2 cable lengths, plus 10 matched | lab | `data/calibration.json`, `fig0_calibration.png` | VF in the expected range, σ(vp)/vp < 1 % |
| H6 | Test matrix: open / short / 50 Ω on 3 lengths, 20 repeats each | lab | ≈ 180 traces in `data/raw/`, logged | log complete, spot checks pass (§7) |
| H7 | Partial mismatch with an approved discontinuity, 20 repeats | lab | ≈ 20–60 traces | position measured with a tape |
| H8 | Low-SNR variants (lower amplitude / no averaging) | lab, if time | 40–60 traces | logged with `--notes lowSNR` |
| H9 | Process the lab data and close the loop | after the lab | E3/E4 on real data, Figure 5, report §3/§6 | `python index.py evaluate` shows `LAB` |
| H10 | Optional: build and test the fast-edge pulser (needs approval) | if Δd_min > 0.5 m | rise-time comparison | Rs within 45–55 Ω |

**Minimum viable session (fallback, about 1 hour):** H3, H4, H5 on two lengths, and open/short/matched on those two lengths (≈ 120 traces). That alone unlocks the real-data E3/E4 and the calibration deliverable.

---

## 2. How hardware and software connect

```
 lab bench                          laptop                                   outputs
 ─────────                          ──────                                   ───────
 generator ─► tee ─► cable    ─►   python index.py capture  (USB, PyVISA)  ─► data/raw/<session>/*.csv
 scope CH1 at the tee              or scope "Save CSV" + USB stick         ─► data/raw/lab_log.csv (labels)
                                    python index.py inspect <file>          ─► sanity check per file
                                    python index.py calibrate               ─► data/calibration.json, fig0
                                    python index.py fit --file ...          ─► fig5 (sim vs measured)
                                    python index.py train --rebuild         ─► simulator re-centred on our cable
                                    python index.py evaluate                ─► E3/E4 on LAB data, report tables
                                    python index.py dashboard               ─► live demo with real traces
```

The software needs exactly two things from the lab:
1. **Waveform files.** Any of the supported scope CSV formats (Rigol, Tektronix, Keysight, Siglent, generic), or the files written by `capture`.
2. **One log row per file** with the ground truth: cable type and measured length, termination, fault kind and position, and settings.

`capture` writes both automatically. Everything else (alignment, normalisation, features, models) is automatic.

---

## 3. Before the lab (H1, H2)

### 3.1 Questions for the instructor
1. Which coaxial cables and lengths can we use (type printed on the jacket, connectors)?
2. Which terminations are available: 50 Ω terminator, shorting cap, other resistor values, 75 Ω?
3. Which discontinuities are approved: a BNC tee with an open stub, a resistor load, a 50/75 Ω joint?
4. What are the generator's maximum amplitude, the scope's input limits and the lab safety rules?
5. May we connect a laptop to the scope over USB/LAN? If not, may we export CSV to a USB stick?
6. Is the optional fast-edge pulser allowed? What report format and demo are expected?

### 3.2 Laptop preparation
```powershell
cd D:\EMT
.venv\Scripts\python index.py check                 # packages, VISA, models
.venv\Scripts\python index.py capture --simulate --length 5 --termination open --repeats 5
.venv\Scripts\python index.py calibrate --log data\raw\simulated_session\lab_log.csv --out %TEMP%\cal_test.json
```
- Install **NI-VISA** (or Keysight IO Libraries) so `capture --list` can see a USB scope.
- Print [LAB_PROCEDURE.md](LAB_PROCEDURE.md) §9 (log sheet) as a paper backup.
- Charge the laptop and bring the USB-B cable.

### 3.3 Team roles (3 people)
| Role | Does |
|---|---|
| Operator | generator and scope settings, runs `capture`, watches the quick check printed after each trace |
| Cable handler | measures cable lengths (3 tape readings), changes terminations, reconnects every 5 repeats |
| Logger | fills the paper log, checks file names, photographs the setup, watches the time plan |

---

## 4. Equipment and materials

### 4.1 Required
| Item | Qty | Notes |
|---|---|---|
| Function generator, 50 Ω output, square/pulse | 1 | edge time from the datasheet goes into §5.1 |
| Digital oscilloscope, ≥ 100 MHz preferred, ≥ 500 MSa/s | 1 | 1 MΩ input, BNC; USB for capture |
| Coaxial cables, same type, ≥ 2 different lengths (target 2 m, 5 m, 10 m) | 3 | RG-58 assumed; the type sets Z0 and the velocity |
| BNC T-adapter | 1 (+1 for the stub) | sits directly on scope CH1 |
| Short BNC lead (≤ 0.5 m), generator to tee | 1 | keeps secondary echoes away |
| 50 Ω BNC feed-through or end terminator | 1 | the "matched" load |
| BNC shorting cap, or BNC-to-banana adapter + short wire | 1 | the "short" load |
| Tape measure | 1 | 3 readings per cable |
| Laptop with the project, USB cable | 1 | or a USB stick for CSV export |

### 4.2 For the partial mismatch (choose what the instructor approves)
| Option | Parts | Expected Γ (Z0 = 50 Ω) | `capture` flags |
|---|---|---|---|
| Resistor load at the cable end | BNC-to-banana binding post + 100 Ω (or 22 Ω) resistor | +0.33 (or −0.39) | `--termination partial --fault-kind end --zl 100` |
| 50/75 Ω joint | BNC barrel + a 2–5 m RG-59 piece + 75 Ω terminator | +0.20 | `--termination partial --fault-kind impedance_step --zl 75 --fault-position <m>` |
| Tee with open stub | BNC tee mid-line + 0.5–2 m open stub | −0.33 dip | `--termination partial --fault-kind open_stub --fault-position <m> --desc "stub 1.0 m"` |

### 4.3 Optional
| Item | Why |
|---|---|
| 74AC14 fast-edge pulser ([fast_edge_pulser.md](fast_edge_pulser.md)) | about 2 ns edge for better resolution on short cables (needs approval) |
| Extra cable of a different type (RG-174, RG-59) | shows how vp and attenuation change; the presets already exist in the software |

---

## 5. Lab session (H3–H8)

Suggested 3-hour plan (shorten with the fallback in §1):

| Time | Step |
|---|---|
| 0:00–0:15 | H3 discovery, fill §5.1; safety check |
| 0:15–0:30 | H4 wiring and settings (§5.2), first test capture, photo |
| 0:30–1:10 | H5 calibration (§5.3) |
| 1:10–2:20 | H6 test matrix (§5.4) |
| 2:20–2:45 | H7 partial mismatch (§5.5) |
| 2:45–2:55 | H8 low-SNR variants (§5.6) |
| 2:55–3:00 | copy `data/raw` to a second place; pack up |

### 5.1 Equipment discovery (fill in on the day)
| Quantity | Value | Used for |
|---|---|---|
| Scope model / bandwidth / max sample rate | | resolution limit, driver choice |
| Scope `*IDN?` (from `capture --list`) | | driver choice |
| Generator model / square-wave edge time | | resolution limit |
| Cable type (jacket print) and lengths | | Z0, vp, attenuation preset |
| System rise time t_r = √(t_gen² + (0.35/BW)²) | | Δd_min = vp·t_r/2 |

**Decision:** if Δd_min > 0.5 m, use cables ≥ 2 m only, and consider the pulser (H10).

### 5.2 Setup and settings
Wire as in [LAB_PROCEDURE.md §3](LAB_PROCEDURE.md#3-wiring): tee directly on CH1, short lead to the generator.
- **Generator:** square wave, 100 kHz, 0 V → 2 V. Note whether it is set to High-Z or 50 Ω.
- **Scope:** 1 MΩ input, DC coupling, bandwidth limit off, trigger on the rising edge at about 0.5 V in Normal mode, trigger 1–2 divisions from the left, other channels off. Use Average 16 for calibration only.

Timebase per cable length: see [LAB_PROCEDURE.md §4](LAB_PROCEDURE.md#4-instrument-settings).

**Check before going on:**
- The incident step plateau is flat.
- The open-end reflection steps up to about 2·V_inc at t ≈ 2L/vp.
- The quick check printed by `capture` gives d within about 10% of the tape length.

### 5.3 Calibration (H5)
```powershell
# repeat for each cable length; three tape readings in --length-meas
python index.py capture --cable RG-58 --cable-id C1 --length-meas 2.01 2.02 2.01 --termination open `
    --repeats 20 --averaging 16 --gen-model "<model>" --gen-amplitude 2 --gen-period 1e-5 --gen-load HighZ --operator AB
python index.py capture --cable RG-58 --cable-id C1 --length-meas 2.01 2.02 2.01 --termination matched --zl 50 --repeats 10 --averaging 16
python index.py calibrate
```
**Acceptance:**
- velocity factor 0.64–0.68 for solid PE (0.78–0.85 for foam);
- σ(vp)/vp < 1%;
- |t_offset| < 3 ns;
- rise time and Δd_min printed and copied into §5.1.

### 5.4 Test matrix (H6)
Acquisition **Normal**, 20 repeats. Reconnect the load every 5 repeats.

| Config | Cable | Termination | Command tail (plus `--cable-id`, `--length-meas`, `--operator`) |
|---|---|---|---|
| 1–3 | L1 ≈ 2 m | open, short, 50 Ω | `--termination open` / `short` / `matched --zl 50` |
| 4–6 | L2 ≈ 5 m | open, short, 50 Ω | same |
| 7–9 | L3 ≈ 10 m | open, short, 50 Ω | same |

### 5.5 Partial mismatch (H7)
Use the approved option from §4.2. Measure the **distance from the tee to the discontinuity** with the tape (3 readings) and pass it as `--fault-position`. Take 20 repeats per configuration. If time allows, do two different positions for the same discontinuity.

### 5.6 Low-SNR variants (H8)
Lower the generator to 0.2–0.5 V (or switch off averaging if it was on) and repeat 2–3 configurations with `--notes lowSNR`. These are the most valuable traces for the noise experiment (E1) on real data.

### 5.7 Safety (always)
- Generator ≤ 5 V; an open end doubles the voltage.
- Never use the scope's 50 Ω input above its rating.
- Discharge long cables before connecting.
- Output off while changing loads.
- Only approved modifications; follow the instrument manuals and the lab rules.

---

## 6. If USB capture is not possible

1. Save each waveform as CSV from the scope menu to a USB stick, e.g. names like `C2_5m_open_01.csv`.
2. Write one row per file in `data/raw/lab_log.csv`, using the columns of [lab_log_template.csv](lab_log_template.csv). Minimum fields: `file, cable_type, cable_length_m, termination, fault_kind, fault_position_m, zl_ohm, repeat_idx`.
3. Check that the format is understood: `python index.py inspect data\raw\<file>.csv --plot`
4. Continue with §8. The rest of the pipeline is identical.

---

## 7. Data quality checks before leaving the lab

| Check | How | Pass if |
|---|---|---|
| Every file is logged | compare the folder with the log | same count |
| Same setup gives the same Δt | quick check printed by `capture` | spread < 1 ns over the 20 repeats |
| V_inc is stable | `inspect` on the first and last file | within 2% |
| Noise level | `inspect` prints noise σ (normalised) | < 0.03 (better than 30 dB) for normal traces |
| Matched load is flat | `inspect` says "no reflection" | yes |
| Backup | copy `data/raw` to a USB stick or cloud | done |

---

## 8. After the lab (H9)

```powershell
python index.py lab-dataset          # all logged traces -> data/processed/lab.csv (+ baseline result per trace)
python index.py fit --file data\raw\<session>\<an open trace>.csv --length <L> --termination open
python index.py train --rebuild      # simulator ranges re-centred on calibration.json, models retrained
python index.py evaluate             # E3/E4 switch from PROXY to LAB automatically (>= 20 lab traces)
python index.py dashboard            # "Saved trace" source shows the lab files with all model predictions
```
Then update the report:
- §3: equipment table §5.1, calibration table, Figure 0, setup photo and diagram, resolution.
- §6.4: E3/E4 tables (now LAB instead of PROXY), Figure 5 (fitted simulation vs measured).
- §7: compare the real gap with the proxy, and with the Zenodo sim-to-real result. Measured on the 16 real Zenodo traces (65–143 m cables, `report/results/zenodo_z3_real_per_trace.csv`): the matched-filter baseline reads cable lengths a median 3.2 % long (+0.8 % to +145 % when it locks onto a wrong echo), while the best ML model (ET-B, trained on simulation) stays within −2.1 % to +1.2 % (MAE 0.61 m). Small velocity and dispersion differences between real and simulated cables show up as exactly this kind of length bias, which is why H5 calibration matters.

---

## 9. Results to report from the hardware work

| Quantity | Symbol | Source |
|---|---|---|
| Propagation velocity ± σ, velocity factor | vp, VF | `calibration.json` |
| Fixture / trigger offset | t0 | `calibration.json` |
| System rise time, resolution | t_r, Δd_min | `calibration.json` |
| Incident amplitude, noise, SNR | V_inc, σ | `calibration.json` |
| Velocity from the full simulator fit (phase velocity) | vp_fit | `fit` output |
| Simulator parameters fitted to our cable | rise, attenuation scale, scope C, Rs | `fit` output |
| Distance error per configuration: baseline vs each model | MAE, RMSE | `report/results/e3_e4_sim_to_lab.csv` |
| Classification on real traces | accuracy, F1 | `e3_e4_classification.csv` |

---

## 10. Risks during the hardware work

| Risk | Sign | Mitigation |
|---|---|---|
| Generator edge too slow | rise time > 8 ns, short-cable reflections merge | use ≥ 2 m cables; fast-edge pulser (H10) |
| Wrong input impedance | plateau at half the expected level | scope 1 MΩ; note the generator load setting |
| Secondary echoes | extra steps at 2× the lead length | short lead, tee directly on CH1 |
| USB capture fails | `capture --list` empty or read error | CSV export (§6) |
| Time runs out | behind the §5 plan | fallback session (§1) |
| Lost data | — | copy `data/raw` before leaving |
| Mislabelled traces | Δt does not match the tape length | `capture` prints d for every repeat: stop and fix immediately |

---

## 11. Optional: fast-edge pulser (H10)

If §5.1 gives Δd_min > 0.5 m and the instructor approves:
1. Build the 74AC14 circuit ([fast_edge_pulser.md](fast_edge_pulser.md)), at a cost of under 10 USD.
2. Run its bring-up test: frequency, Rs = 45–55 Ω.
3. Repeat H5 with the pulser in place of the generator, with `--gen-model "74AC14 pulser"`.
4. Report the rise time and Δd_min with the generator and with the pulser.
