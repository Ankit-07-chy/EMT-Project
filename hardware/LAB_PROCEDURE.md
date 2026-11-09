# TDR lab procedure

> **New to the hardware part? Start with [README.md](README.md)**: the beginner's step-by-step manual (parts list, connection tables, power, assembly, ordered steps S1–S15, troubleshooting). This file is one of its companions.

This covers work packages WP2 (setup and calibration) and WP3 (data collection). Bring this file, the printed log sheet (Section 9) and a laptop with the project installed (`python index.py check` passes).

The instrument manuals and the lab safety rules come first. If anything here contradicts them, follow the manuals and the lab staff.

---

## 0. Before the first session

Ask the instructor (brief, Section 13):

1. Which cables, lengths, connectors and terminations can we use?
2. Which discontinuities are approved: a tee with an open stub, a series or shunt resistor, a 50/75 Ω joint?
3. What are the generator and scope limits, including the safe output amplitude and the scope input rating?
4. Can we connect the scope to a laptop over USB or LAN? Python capture saves a lot of time.
5. Is the fast-edge pulser (`fast_edge_pulser.md`) allowed if the generator edge is too slow?

What to bring:
- a BNC tee (T-adapter)
- a 50 Ω BNC terminator
- a BNC shorting cap, or a BNC-to-banana adapter plus a short wire
- one short BNC lead (≤ 0.5 m)
- a tape measure
- a USB cable for the scope
- this sheet

---

## 1. Equipment discovery (first 15 minutes, once)

Write these down. The code needs them, and so does the report's "limitations" section.

| Item | Where to find it | Value |
|---|---|---|
| Scope make and model | front panel / `*IDN?` | |
| Scope bandwidth (MHz) | model number / datasheet | |
| Max sample rate with **one** channel on | datasheet | |
| Scope input impedance options | channel menu (1 MΩ, maybe 50 Ω) | |
| Max input voltage on 1 MΩ | label next to the BNC | |
| Generator make and model | front panel | |
| Generator square or pulse rise time | datasheet ("rise/fall time") | |
| Generator output impedance | datasheet (normally 50 Ω) | |
| Cable type printed on the jacket | e.g. "RG-58 C/U", "RG-174" | |
| Cable lengths available | label / tape | |

**Quick resolution estimate.** The system rise time is t_r ≈ √(t_gen² + t_scope²), with t_scope ≈ 0.35 / BW. The smallest fault distance you can separate from the incident edge is

  Δd_min ≈ vp · t_r / 2 ≈ 0.1 m per ns of rise time (for RG-58).

Example: a 100 MHz scope (3.5 ns) with a 10 ns generator gives t_r ≈ 10.6 ns, so Δd_min ≈ 1 m. If the result is above ~0.5 m, use cables ≥ 2 m. Then consider the fast-edge pulser.

---

## 2. Safety

- **Low voltage only.** Keep the generator at ≤ 5 V peak (2 V is plenty). An open cable doubles the voltage at the tee.
- **Scope input rating.** Never use the scope's 50 Ω input setting with more than its rated voltage (often only 5 Vrms). This procedure uses the 1 MΩ input.
- **Discharge long cables** before connecting them: touch the centre pin to the shell or to the shorting cap. Cables can hold static charge.
- **No improvised modifications.** Do not cut, crimp or modify cables, and do not add anything to the line without instructor approval. Every discontinuity must be approved (brief, Section 2.4).
- **Generator output off** while changing the setup.

---

## 3. Wiring

```
                         short BNC lead (<= 0.5 m)
 Function generator  ───────────────────────────┐
   (50 Ω output)                                │
                                           ┌────┴────┐
                                           │ BNC tee │  sits directly on the scope CH1 input
                                           └────┬────┘
                                                │ (scope CH1, 1 MΩ, DC)
                                                │
              cable under test  ────────────────┘ ─────────────────────────  [termination]
              (length L, measured)                                 open / short cap / 50 Ω / approved fault
```

- The tee goes **directly on the CH1 BNC**. No extra cable between the tee and the scope.
- The generator lead should be short. With a 50 Ω generator it absorbs the returning reflection, so only one echo appears. A long or mismatched lead causes secondary echoes.
- **Reference plane:** distances are measured from the tee. The few centimetres of the tee itself are absorbed by the fitted offset `t_offset` during calibration.

---

## 4. Instrument settings

### Function generator
| Setting | Value | Why |
|---|---|---|
| Waveform | **Square** (or Pulse with the minimum edge time) | the rising edge is the TDR step |
| Frequency | **100 kHz** (high time 5 µs) | the step must stay high much longer than the longest round trip (20 m ≈ 200 ns) |
| Levels | **low 0 V, high 2 V** (or 2 Vpp with offset +1 V) | low voltage; the trace starts at 0 V |
| Output load setting | note **High-Z** or **50 Ω** in the log | only changes the displayed amplitude, not the real 50 Ω source |
| Edge time (pulse mode) | minimum | sharper edge, better resolution |

### Oscilloscope (CH1)
| Setting | Value |
|---|---|
| Coupling | DC |
| Input impedance | **1 MΩ** (do not use the 50 Ω setting, it loads the tee) |
| Bandwidth limit | **OFF** |
| Probe ratio | 1X (direct BNC) |
| Vertical | 500 mV/div, offset so 0–4 V fits on screen (an open end doubles the voltage) |
| Trigger | Edge, rising, CH1, DC, level ≈ half the incident step (about 0.5 V), mode **Normal** |
| Horizontal position | trigger 1–2 divisions from the left, so at least 50 ns are recorded before the edge |
| Other channels | **off** (maximum sample rate on CH1) |
| Acquisition | **Normal** for the dataset. **Average 16** only for calibration traces (note it in the log) |

### Timebase per cable length (RG-58, vp ≈ 2×10⁸ m/s)
| L | Round trip 2L/vp | Timebase | Window |
|---|---|---|---|
| 2 m | 20 ns | 10 ns/div | about 120 ns |
| 5 m | 50 ns | 20 ns/div | about 240 ns |
| 10 m | 100 ns | 20–50 ns/div | about 300–600 ns |
| 20 m | 200 ns | 50 ns/div | about 600 ns |

The window must contain the whole reflected edge plus ≥ 30 ns after it. Check the effective sample interval after a test export: it should be ≤ 1 ns (≥ 1 GSa/s if possible).

**What you should see** (incident plateau = V_inc):
```
 open     ___/‾‾‾‾‾‾‾‾‾‾/‾‾‾‾‾‾‾‾‾   steps up to 2·V_inc at t = 2L/vp
 short    ___/‾‾‾‾‾‾‾‾‾‾\_________   drops to ~0 at t = 2L/vp
 matched  ___/‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾   flat at V_inc
 partial  ___/‾‾‾‾‾‾‾‾‾‾/‾‾‾‾‾‾‾‾‾   step of Γ·V_inc (up if ZL > Z0, down if ZL < Z0)
 stub     ___/‾‾‾‾‾‾‾‾‾‾\__/‾‾‾‾‾‾   dip of -V_inc/3 lasting 2·l_stub/vp
```

---

## 5. Connecting the laptop (USB capture)

1. Install a VISA driver. **NI-VISA** or **Keysight IO Libraries** is easiest on Windows. Alternatively use `pyvisa-py` with `pyusb` and libusb.
2. Connect the scope over USB (rear "USB Device" port). Some scopes need the USB mode set to **USBTMC** in the Utility menu.
3. `python index.py capture --list` should print the scope's `*IDN?` string.
4. Do a test capture with `--repeats 1` and compare the saved CSV with the screen:
   ```
   python index.py capture --length 2.00 --termination open --repeats 1 --notes "test"
   python index.py inspect data/raw/session_<date>/<file>.csv --plot
   ```
5. **If USB capture does not work, don't lose the session.** Export CSVs from the scope menu to a USB stick, and log each file by hand in `data/raw/lab_log.csv` (columns as in `lab_log_template.csv`). `python index.py inspect <file>` checks that the format is understood.

Rehearse the whole session at home with the simulated scope:
```
python index.py capture --simulate --length 5 --termination open --repeats 5
```

---

## 6. Calibration (WP2)

1. **Measure each cable 3 times** with the tape, connector tip to connector tip, and use the mean. Pass all three readings to `--length-meas` so they are logged.
2. **Open circuit, cable L1:** 20 repeats, with the scope in **Average 16** for calibration.
   ```
   python index.py capture --cable RG-58 --cable-id C1 --length-meas 2.01 2.02 2.01 \
       --termination open --repeats 20 --averaging 16 --gen-model "<model>" \
       --gen-amplitude 2 --gen-period 1e-5 --gen-load HighZ --operator <initials>
   ```
3. **Open circuit, cable L2** (and L3 if available): same command. Two different lengths are the minimum, because the fit `Δt = (2/vp)·L + t0` separates vp from the fixture delay t0.
4. **Matched trace:** put on the 50 Ω terminator, 10 repeats. It should be flat at V_inc. Its level is the V_inc reference.
5. Run the calibration:
   ```
   python index.py calibrate
   ```
   This writes `data/calibration.json` and `report/figures/fig0_calibration.png`, and prints vp ± σ, the velocity factor, t0, the rise time, Δd_min, V_inc and the noise level.
6. **Sanity checks:**
   - Solid-PE RG-58/RG-174 gives a velocity factor of 0.64–0.68. Foam-dielectric cables give 0.78–0.85.
   - |t0| should be under a few ns.
   - σ(vp)/vp should be under 1%.

   Note: vp from 50% edge timing on a lossy cable reads about 0.5–1% low, because skin-effect dispersion slows the reflected edge. `python index.py fit` models this and gives the phase-velocity estimate. Report both values.
7. Photograph the setup (deliverable) and sketch it in the log.

---

## 7. Data collection (WP3)

Minimum test matrix (brief, Section 6), 20 repeats each, acquisition **Normal**:

| Cable | Termination | Command (add `--cable-id`, `--operator`, generator fields) |
|---|---|---|
| L1 ≈ 2 m | open | `capture --length <L1> --termination open` |
| L1 | short | `capture --length <L1> --termination short` |
| L1 | 50 Ω | `capture --length <L1> --termination matched --zl 50` |
| L2 ≈ 5 m | open, short, 50 Ω | same three commands with `<L2>` |
| L3 ≈ 10 m | open, short, 50 Ω | same three commands with `<L3>` |
| L2 + approved discontinuity | partial | see below |

**Partial mismatch.** Record **the distance from the tee to the discontinuity** as `--fault-position`.
- Resistor termination (e.g. 100 Ω or 22 Ω at the cable end): `--termination partial --fault-kind end --zl 100`
- 50/75 Ω joint (75 Ω cable section after a barrel): `--termination partial --fault-kind impedance_step --zl 75 --fault-position <m> --desc "RG-59 2 m section"`. Terminate the far end with 75 Ω if one is available.
- Tee with open stub at position x: `--termination partial --fault-kind open_stub --fault-position <x> --desc "stub 1.0 m"`

**Good practice:**
- Disconnect and reconnect the termination every 5 repeats, so connector repeatability is part of the data.
- Keep the generator and scope settings identical within a configuration.
- If you change a setting, note it in `--notes`.
- If time allows, record a few configurations at lower generator amplitude (e.g. 0.5 V). These lower-SNR lab traces are very valuable for E1/E3.
- Never put the "true distance" anywhere except the log label.

**Fallback (brief):** if time is short, do one validation session: open, short and matched on 2 cable lengths, 20 repeats each (≈ 120 traces, about 30 min with USB capture).

---

## 8. After the session

```
python index.py lab-dataset          # process all logged traces -> data/processed/lab.csv
python index.py fit --file <one open trace> --length <L> --termination open    # sim-vs-lab overlay (plot 5)
python index.py train --rebuild      # re-centre the simulation on the calibration, retrain
python index.py evaluate             # E3/E4 now use the real lab data automatically (>= 20 traces)
```
The lab traces are never used for training, except for the small E4 fine-tune split. That split is chosen by **configuration**, so repeats of one setup never sit on both sides.

---

## 9. Printable log sheet

| # | Cable / ID | L readings (m) | Termination | Fault kind | Fault pos (m) | ZL / R / Z2 (Ω) | Gen settings | Scope settings | Avg | Repeats | Files / time | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | | / / | | | | | | | | | | |
| 2 | | / / | | | | | | | | | | |
| 3 | | / / | | | | | | | | | | |
| 4 | | / / | | | | | | | | | | |
| 5 | | / / | | | | | | | | | | |
| 6 | | / / | | | | | | | | | | |

---

## 10. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Plateau at half the expected level | scope input set to 50 Ω, or generator Load = 50 Ω while you expected High-Z | set scope to 1 MΩ; note the generator setting |
| Reflection merges with the incident edge | cable shorter than Δd_min | use a longer cable, a faster edge (pulser) or a faster timebase |
| Extra echoes after the main reflection | long or mismatched generator lead, tee not on the scope input | short lead, tee directly on CH1 |
| Ringing / overshoot after the incident edge | generator edge overshoot, poor connectors | tighten BNCs; record a matched trace as reference |
| No reflection visible | timebase too short, or trigger point too far right | widen the window; the round trip is 2L/vp |
| Trace jumps between captures | trigger mode Auto, or level too close to noise | trigger mode Normal, level at about 50% of V_inc |
| `capture --list` shows nothing | no VISA driver / wrong USB mode | install NI-VISA, set USBTMC, try another USB port |
| `capture` errors on read | driver/model mismatch | export CSVs from the scope menu and log them by hand |
