# Optional: fast-edge step generator (74AC14)

> **New to the hardware part? Start with [README.md](README.md)**: the beginner's step-by-step manual (parts list, connection tables, power, assembly, ordered steps S1–S15, troubleshooting). This file is one of its companions.

**Status: optional, needs instructor approval before use** (brief, Section 2.4). Build it only if calibration shows a system rise time that is too slow for your cable lengths, for example Δd_min > 0.5 m.

## Why

Resolution is set by the edge speed: Δd_min ≈ vp · t_r / 2. A typical lab function generator has a square-wave edge of about 8–15 ns, which on RG-58 means about 0.8–1.5 m. A 74AC-family logic gate switches in about 1.5–3 ns. That brings the generator's share of t_r down to 0.15–0.3 m, so the scope bandwidth becomes the limit instead.

| Generator edge | Scope | System t_r | Δd_min (RG-58) |
|---|---|---|---|
| 10 ns (function generator) | 100 MHz (3.5 ns) | 10.6 ns | ≈ 1.05 m |
| 2.5 ns (this pulser) | 100 MHz (3.5 ns) | 4.3 ns | ≈ 0.43 m |
| 2.5 ns (this pulser) | 200 MHz (1.75 ns) | 3.1 ns | ≈ 0.30 m |

## Circuit

One 74AC14 (hex Schmitt-trigger inverter), 5 V supply:
- **U1A** is an RC oscillator at about 100 kHz. Its high time of about 5 µs is much longer than any round trip.
- **U1B** buffers and sharpens the edge.
- **U1C–U1F** are four gates in parallel. Each drives the output through its own 180 Ω resistor. Four branches of (180 Ω + about 12 Ω gate output resistance) in parallel give a source impedance of about 48 Ω. That matches the 50 Ω cable, so returning reflections are absorbed exactly as with a 50 Ω generator.

```
                       R1 10 kΩ
                 ┌─────/\/\/\─────┐
                 │                │
   pin 1 ────────┴───|>o──────────┴── pin 2 ──── pin 3 ──|>o── pin 4 ──┬── pin 5  ─|>o─ pin 6  ──[180 Ω]──┐
     │               U1A                              U1B              ├── pin 9  ─|>o─ pin 8  ──[180 Ω]──┤
    ═══ C1 1 nF (C0G)                                                  ├── pin 11 ─|>o─ pin 10 ──[180 Ω]──┼──► BNC centre (OUT)
     │                                                                 └── pin 13 ─|>o─ pin 12 ──[180 Ω]──┘
    GND                                                                        U1C ... U1F           BNC shell ── GND

   +5 V ──┬──────┬───── pin 14 (VCC)        Decoupling as close to pins 14/7 as possible:
          ═ 100n ═ 10µ                      100 nF ceramic (X7R) + 10 µF
   GND ───┴──────┴───── pin 7  (GND)
```

74AC14 pinout (DIP-14): 1A=1 → 1Y=2, 2A=3 → 2Y=4, 3A=5 → 3Y=6, GND=7, 4Y=8 ← 4A=9, 5Y=10 ← 5A=11, 6Y=12 ← 6A=13, VCC=14.

**Output levels:**
- Into a 50 Ω (matched) cable the incident step is ≈ 5 V × 50 / (48 + 50) ≈ 2.5 V.
- An open cable end doubles that to ≈ 5 V at the tee. Within the 1 MΩ scope input rating, but use 1 V/div.
- Per-gate current is about 13 mA into 50 Ω and about 26 mA peak into a shorted cable, against the 74AC 24 mA DC rating. That's fine at 50% duty for lab use. If you want margin, use 220 Ω resistors: source ≈ 58 Ω, Γ_source ≈ +0.07, which the simulator handles via `rs_rel`.

## Bill of materials

| Qty | Part | Note |
|---|---|---|
| 1 | 74AC14 (e.g. SN74AC14N, DIP-14) + socket | **AC**, not HC: 74HC14 edges are about 6–10 ns |
| 4 | 180 Ω 1 % resistor | short leads, or 0805 SMD soldered flat |
| 1 | 10 kΩ resistor | oscillator |
| 1 | 1 nF C0G/NP0 capacitor | oscillator, stable |
| 1 | 100 nF X7R ceramic | decoupling at pin 14 |
| 1 | 10 µF capacitor | bulk decoupling |
| 1 | BNC female, PCB or panel mount | output |
| 1 | 5 V supply: USB breakout board, or 7805 + 9 V battery clip | the lab bench supply also works |
| 1 | single-sided copper-clad board, about 5 × 5 cm | ground plane, Manhattan / dead-bug build |

Approximate cost: under 10 USD.

## Build notes

- Use the **copper side as a continuous ground plane**. Solder the BNC shell, pin 7 and the decoupling capacitors straight to it.
- Keep the gate-output → resistor → BNC path **under 1 cm**. Every centimetre of loose wire is inductance that slows and rings the edge.
- Mount the BNC jack at the edge of the board, so the BNC tee on the scope connects with the shortest possible lead (or directly).
- Tie no inputs to anything else. All six gates are used.
- Do **not** build avalanche-transistor sub-nanosecond pulsers. They need about 100 V supplies and fall outside "low-voltage pulse" and lab safety.

## Bring-up test

1. **Power only.** The supply current should be about 5–10 mA with no load. If it's hot or drawing much more, switch off and check for solder bridges.
2. **Output open (scope directly, 1 MΩ).** You should see a square wave of about 0–5 V at about 100 kHz (measure it; the RC frequency depends on the chip's hysteresis).
3. **Source impedance.** Put a 50 Ω terminator on the tee and read the plateau V_50. Then Rs = 50 Ω × (V_open / V_50 − 1). It should be 45–55 Ω.
4. **Rise time.** Use a short open cable (about 2 m), measure 10–90% of the incident edge, and compare it with the function generator.
5. Then run the normal calibration (`LAB_PROCEDURE.md`, Section 6) with the pulser in place of the generator. Write `gen_model = "74AC14 pulser"` in the log.
