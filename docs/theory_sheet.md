# TDR theory sheet (one page)

**Transmission line.** A coaxial cable has a characteristic impedance Z0 = √(L′/C′): 50 Ω for RG-58, RG-174 and RG-316, and 75 Ω for RG-59. A wave travels along it at

  vp = c / √εr = VF · c,  with VF ≈ 0.66 for solid polyethylene (vp ≈ 1.98×10⁸ m/s ≈ 0.2 m/ns).

**Incident step.** The generator (EMF Vs, source resistance Rs) drives the cable through the tee. The cable initially looks like a resistor Z0, so the incident step at the tee is

  V_inc = Vs · Z0 / (Rs + Z0)  = Vs / 2 when Rs = Z0.

**Reflection at a discontinuity.** When the wave reaches an impedance ZL, part of it is reflected:

  Γ = V_refl / V_inc = (ZL − Z0) / (ZL + Z0),  −1 ≤ Γ ≤ +1

| Load | ZL | Γ | Level at the tee after the reflection returns |
|---|---|---|---|
| open | ∞ | +1 | 2 · V_inc |
| short | 0 | −1 | 0 |
| matched | Z0 | 0 | V_inc (no reflection) |
| resistor R | R | (R−Z0)/(R+Z0) | (1 + Γ) · V_inc |
| series R mid-line | R + Z0 | R/(R + 2Z0) | step up by Γ |
| shunt R mid-line | R ∥ Z0 | −Z0/(Z0 + 2R) | step down by \|Γ\| |
| 50→75 Ω joint | 75 Ω | +0.2 | step up by 0.2 V_inc |
| tee with open stub | Z0 ∥ Z0 (initially) | −1/3 | dip lasting 2·l_stub / vp |

The **polarity** of the reflected step tells high-impedance faults (opens, series breaks: up) from low-impedance faults (shorts, insulation damage: down).

**Distance.** The reflection returns after the round trip Δt = 2d / vp, so

  **d = vp · Δt / 2**

Δt is measured 50%-to-50%: from the 50% point of the incident edge to the 50% point of the reflected edge.

**Bounce diagram.** Each time the wave hits an end, it is multiplied by that end's Γ: Γ_L at the load, Γ_S = (Rs − Z0)/(Rs + Z0) at the source. The tee voltage is the running sum of all waves that have arrived. With Rs = Z0 (Γ_S = 0) the first reflection is absorbed by the generator and only one echo appears. A mismatched source produces a decaying train of echoes every 2d/vp. The dashboard's *Physics* tab draws this diagram.

**Losses and dispersion.** Real cables attenuate as

  α(f) = α_dc + k_s √f (skin effect) + k_d f (dielectric).

The reflected step is therefore smaller, about Γ · e^(−2αd), and slower than the incident one. Skin effect also adds a phase term that delays the 50% point slightly, more on long cables. So timing-based vp calibration reads about 0.5–1% low, unless the model includes dispersion (`src/fit_sim.py` does).

**Resolution.** Two edges closer than about the system rise time merge. With t_r = √(t_gen² + t_scope²) and t_scope ≈ 0.35 / BW:

  Δd_min ≈ vp · t_r / 2  (≈ 0.1 m per ns of rise time on RG-58).

Faults closer than Δd_min to the tee, or to each other, cannot be separated by edge timing.

**Signal-to-noise.** In this project SNR = 20 log10(V_inc / σ_noise). Small |Γ| ("soft faults"), long lossy cables and low SNR all shrink the reflected edge relative to the noise. That is where detection fails first, and where learned models are expected to help most.

**Simulation model used (src/sim_tdr.py).** It computes the input reflection coefficient Γ_in(f) = Γ_fault(f) · e^(−2γd) with γ = α + jβ. It then forms V_tee/Vs = Z_in∥Z_scope / (Rs + Z_in∥Z_scope), applies a Gaussian rise-time filter, and inverse-FFTs to the step response. Multiple reflections, source mismatch and scope input capacitance are included automatically. The brief's simpler model (delayed, scaled and smoothed copy of the incident edge) is kept as `model="simple"` for comparison.

**Calibration and normalisation in practice (`src/calibrate.py`, `src/preprocess.py`).**
- **Calibration.** Open-circuit traces on at least two cable lengths give a straight line Δt = (2/vp)·L + t0. The slope gives vp. The intercept t0 is the fixed delay of the tee, adapters and trigger. It is removed from every measured delay and from the model inputs, so an echo from distance d sits at 2d/vp exactly as in the simulator.
- **Normalisation.** Each measured trace is divided by its own incident step V_inc, estimated from the plateau after the first rise. The calibrated V_inc is used only when it agrees with that estimate. This keeps the open = 2, short = 0, matched = 1 levels correct when the generator amplitude changes between configurations (e.g. low-SNR traces).
- **Distance.** It is always d = vp·Δt/2 with the calibrated vp. The ML models predict Δt, not d, so a calibration update changes the metres without retraining.
