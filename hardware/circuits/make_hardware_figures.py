"""Draw every hardware circuit diagram and its expected scope waveform.

    python hardware/circuits/make_hardware_figures.py

Schematics are drawn with schemdraw (c*.png / c*.svg). The expected waveforms
(w*.png) come from the project's own transmission-line simulator
(src/sim_tdr.py): RG-58, 5 ns system rise time, generator set to 0 -> 2 V
(so the incident step at the tee is V_inc = 1 V). Your rise time, noise and
exact delays will differ slightly; the levels and the delay formula will not.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
# optional first argument: write the figures somewhere else (used by index.py selftest)
OUT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else HERE
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import schemdraw  # noqa: E402
import schemdraw.elements as elm  # noqa: E402
import schemdraw.logic as logic  # noqa: E402

from src.config import K_END, K_SERIES, K_SHUNT, K_STEP, K_STUB, SimConfig  # noqa: E402
from src.sim_tdr import make_params, simulate  # noqa: E402

INK, INK2, GRID, SURF = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
C1, C2, C3 = "#2a78d6", "#eb6834", "#1baf7a"
VP = SimConfig().vp_nominal          # RG-58 datasheet velocity, about 1.98e8 m/s
RISE = 5e-9

schemdraw.config(fontsize=11, lw=1.4)


def save(d: schemdraw.Drawing, name: str):
    d.save(str(OUT / f"{name}.svg"))
    d.save(str(OUT / f"{name}.png"), dpi=160)


# ---------------------------------------------------------------- schematic building blocks
def generator(d, label="Function generator", src=None, vs="Vs: 0 → 2 V square\n100 kHz"):
    """Thevenin generator: square source + 50 ohm output resistance, in a dashed box.
    Leaves the drawing position at the generator's output terminal."""
    s = d.add((src or elm.SourceSquare)().at((0, 0)).up().label(vs, loc="top", ofst=0.25))
    r = d.add(elm.Resistor().right().label("Rs = 50 Ω (output)", loc="top"))
    d.add(elm.Ground().at(s.start))
    d.add(elm.EncircleBox([s, r], padx=0.5, pady=0.6).linestyle("--").color(INK2)
          .label(label, loc="top", ofst=0.25))
    d.add(elm.Line().at(r.end).right(0.7))
    return d.here


def scope_input(d, at, label="Oscilloscope CH1: 1 MΩ ∥ ~15 pF, DC"):
    """Scope input modelled as R ∥ C to ground, hanging down from ``at``."""
    d.add(elm.Line().at(at).down(0.9))
    top = d.here
    r = d.add(elm.Resistor().down().label("1 MΩ", loc="bottom"))
    d.add(elm.Ground())
    d.add(elm.Line().at(top).right(1.8))
    c = d.add(elm.Capacitor().down().label("15 pF", loc="bottom"))
    d.add(elm.Ground())
    d.add(elm.EncircleBox([r, c], padx=0.5, pady=0.35).linestyle("--").color(INK2)
          .label(label, loc="bottom", ofst=0.3))


def note(d, text):
    """Explanatory text under everything already drawn."""
    bb = d.get_bbox()
    d.add(elm.Label().at((bb.xmin, bb.ymin - 0.9)).label(text, halign="left", valign="top", color=INK2))


def coax(d, length=6.0, label="", z0=""):
    c = d.add(elm.Coax(length=length, radius=0.3).right().label(label, loc="top", ofst=0.45))
    if z0:
        d.add(elm.Label().at(c.center).label(z0, loc="bottom", ofst=0.55).color(INK2))
    return c


def tee(d, label="BNC tee\n(on CH1)"):
    dot = d.add(elm.Dot().label(label, loc="top", ofst=0.15))
    return dot


def tdr_front_end(d, lead_label="short lead ≤ 0.5 m"):
    """generator -> short lead -> tee with the scope input; leaves the position right of the tee."""
    generator(d)
    d.add(elm.Coax(length=3.0, radius=0.3).right().label(lead_label, loc="top", ofst=0.45))
    t = d.add(elm.Dot().label("BNC tee on CH1", loc="top", ofst=1.1))
    scope_input(d, t.center)
    d.add(elm.Line().at(t.center).right(1.8))
    return t


def term_open(d):
    d.add(elm.Line().right(0.4))
    d.add(elm.Dot(open=True).label("open end\nZL = ∞, Γ = +1", loc="right"))


def term_short(d):
    d.add(elm.Line().right(0.6))
    d.add(elm.Line().down(1.4))
    d.add(elm.Ground().label("shorting cap\nZL = 0, Γ = −1", loc="right", ofst=0.3))


def term_res(d, r="50 Ω", note="ZL = 50 Ω, Γ = 0"):
    d.add(elm.Line().right(0.6))
    d.add(elm.Resistor().down().label(f"{r}\nterminator", loc="bottom").label(note, loc="top", ofst=0.3))
    d.add(elm.Ground())


def cable_label(d, text):
    d.add(elm.Label().at((d.here[0] - 3.4, d.here[1] - 2.3)).label(text, color=INK2))


# ---------------------------------------------------------------- schematics
def c01_generator_check():
    with schemdraw.Drawing(show=False) as d:
        d.config(unit=2.4)
        generator(d)
        coax(d, length=2.5, label="short BNC lead")
        t = tee(d, "scope CH1")
        scope_input(d, t.center)
        d.add(elm.Line().at(t.center).right(3.2))
        d.add(elm.Switch().down().label("step (b)\nonly", loc="bottom"))
        d.add(elm.Resistor().down().label("50 Ω\nfeed-through", loc="bottom"))
        d.add(elm.Ground())
        note(d, "(a) no terminator: read V_open (1 MΩ ≈ open)    (b) 50 Ω feed-through on CH1: read V_50 and the 10-90 % rise time\n"
            "Rs = 50 Ω × (V_open / V_50 − 1)")
        save(d, "c01_generator_check")


def _tdr(name, term, text=None, lead="short lead ≤ 0.5 m", cable="cable under test, length L (RG-58)"):
    with schemdraw.Drawing(show=False) as d:
        d.config(unit=2.4)
        tdr_front_end(d, lead)
        coax(d, length=6.5, label=cable, z0="Z0 = 50 Ω, vp ≈ 0.66 c")
        term(d)
        if text:
            note(d, text)
        save(d, name)


def c02_basic():
    _tdr("c02_tdr_setup", term_open,
         "Generator EMF Vs and Rs = 50 Ω launch V_inc = Vs·Z0/(Rs+Z0) = Vs/2 into the cable.\n"
         "The tee sits directly on the scope input; the scope sees V_inc + every echo that comes back.")


def c03_open():
    _tdr("c03_open_end", term_open, "Calibration and test matrix: open end at distance L from the tee.")


def c04_short():
    _tdr("c04_short_end", term_short, "Short: BNC shorting cap (or banana adapter + short wire) at the cable end.")


def c05_matched():
    _tdr("c05_matched_end", lambda d: term_res(d, "50 Ω", "Γ = 0"), "Matched: 50 Ω BNC terminator at the cable end (V_inc reference).")


def c06_resistive():
    _tdr("c06_resistive_end",
         lambda d: term_res(d, "R_L", "R_L = 100 Ω → Γ = +0.33\nR_L = 22 Ω → Γ = −0.39"),
         "Partial mismatch at the end: resistor on a BNC-to-banana binding post (approved values only).")


def c07_series():
    with schemdraw.Drawing(show=False) as d:
        d.config(unit=2.4)
        tdr_front_end(d)
        coax(d, length=4.5, label="cable 1, length d", z0="Z0 = 50 Ω")
        d.add(elm.Line().right(0.6))
        d.add(elm.Dot())
        d.add(elm.Resistor().right().label("R_series (in a small BNC box)", loc="top", ofst=0.3))
        d.add(elm.Dot())
        coax(d, length=4.5, label="cable 2", z0="Z0 = 50 Ω")
        term_res(d, "50 Ω", "far end matched")
        note(d, "Series resistor at distance d: Γ = R/(R + 2·Z0), e.g. R = 50 Ω → Γ = +0.33 (step UP at 2d/vp).",
                                              )
        save(d, "c07_series_resistor")


def c08_shunt():
    with schemdraw.Drawing(show=False) as d:
        d.config(unit=2.4)
        tdr_front_end(d)
        coax(d, length=4.5, label="cable 1, length d", z0="Z0 = 50 Ω")
        d.add(elm.Line().right(0.6))
        j = d.add(elm.Dot().label("2nd BNC tee", loc="top", ofst=0.5))
        d.add(elm.Resistor().down().label("R_shunt\n(banana adapter)", loc="bottom"))
        d.add(elm.Ground())
        d.add(elm.Line().at(j.center).right(0.4))
        coax(d, length=4.5, label="cable 2", z0="Z0 = 50 Ω")
        term_res(d, "50 Ω", "far end matched")
        note(d, "Shunt resistor at distance d (partial short): Γ = −Z0/(Z0 + 2R), e.g. R = 50 Ω → Γ = −0.33 (step DOWN).",
                                              )
        save(d, "c08_shunt_resistor")


def c09_joint():
    with schemdraw.Drawing(show=False) as d:
        d.config(unit=2.4)
        tdr_front_end(d)
        coax(d, length=4.5, label="RG-58, length d", z0="Z0 = 50 Ω")
        d.add(elm.Line().right(0.6))
        d.add(elm.Dot().label("BNC barrel (50/75 joint)", loc="top", ofst=0.5))
        d.add(elm.Line().right(0.3))
        coax(d, length=4.5, label="RG-59 section", z0="Z0 = 75 Ω")
        term_res(d, "75 Ω", "matched to RG-59")
        note(d, "Impedance step at distance d: Γ = (75 − 50)/(75 + 50) = +0.20 (step UP at 2d/vp).",
                                              )
        save(d, "c09_75ohm_joint")


def c10_stub():
    with schemdraw.Drawing(show=False) as d:
        d.config(unit=2.4)
        tdr_front_end(d)
        coax(d, length=4.5, label="cable 1, length d", z0="Z0 = 50 Ω")
        d.add(elm.Line().right(0.6))
        j = d.add(elm.Dot().label("2nd BNC tee", loc="top", ofst=0.5))
        d.add(elm.Line().down(0.6))
        d.add(elm.Coax(length=3.2, radius=0.3).down().label("open stub\nlength ls", loc="bottom", ofst=0.5))
        d.add(elm.Dot(open=True).label("open", loc="right"))
        d.add(elm.Line().at(j.center).right(0.4))
        coax(d, length=4.5, label="cable 2", z0="Z0 = 50 Ω")
        term_res(d, "50 Ω", "far end matched")
        note(d, "Tee + open stub at distance d: dip of −V_inc/3 that lasts 2·ls/vp, then the level returns (Γ = −1/3).",
                                              )
        save(d, "c10_tee_open_stub")


def c11_low_snr():
    with schemdraw.Drawing(show=False) as d:
        d.config(unit=2.2)
        generator(d)
        d.add(elm.Line().right(1.4))
        a = d.add(elm.Dot()).center
        ser = d.add(elm.Resistor().right().label("247.5 Ω", loc="top"))
        b = d.add(elm.Dot()).center
        sh1 = d.add(elm.Resistor().at(a).down().label("61.1 Ω", loc="bottom"))
        d.add(elm.Ground())
        sh2 = d.add(elm.Resistor().at(b).down().label("61.1 Ω", loc="bottom"))
        d.add(elm.Ground())
        d.add(elm.EncircleBox([ser, sh1, sh2], padx=0.6, pady=0.5).linestyle("--").color(INK2)
              .label("optional 20 dB attenuator (50 Ω π-pad)", loc="top", ofst=0.25))
        d.add(elm.Line().at(b).right(1.6))
        d.add(elm.Coax(length=2.6, radius=0.3).right().label("short lead", loc="top", ofst=0.45))
        t = d.add(elm.Dot().label("BNC tee on CH1", loc="top", ofst=1.1))
        scope_input(d, t.center)
        d.add(elm.Line().at(t.center).right(1.8))
        coax(d, length=5.0, label="cable under test", z0="Z0 = 50 Ω")
        term_open(d)
        note(d, "Low-SNR traces: EITHER lower the generator to 0.2-0.5 V, OR insert a matched 20 dB attenuator (keeps Rs = 50 Ω).\n"
            "Same cables and loads as the test matrix; log with --notes lowSNR.")
        save(d, "c11_low_snr")


def c12_pulser():
    with schemdraw.Drawing(show=False) as d:
        d.config(unit=2.0, fontsize=10)
        # U1A: RC relaxation oscillator (R1 feedback, C1 to ground)
        n_in = (0.0, 0.0)
        ga = d.add(logic.SchmittNot().at(n_in).right().anchor("in1").label("U1A  1 → 2", loc="top", ofst=0.25))
        d.add(elm.Line().at(n_in).left(1.0))
        c_node = d.add(elm.Dot()).center
        d.add(elm.Capacitor().down().label("C1 1 nF (C0G)", loc="top"))
        d.add(elm.Ground())
        d.add(elm.Line().at(c_node).up(1.8))
        d.add(elm.Resistor().right(ga.out[0] + 0.5 - c_node[0]).label("R1 10 kΩ", loc="top"))
        d.add(elm.Line().down(1.8))
        d.add(elm.Line().at(ga.out).right(0.5))
        d.add(elm.Dot())
        d.add(elm.Line().right(0.6))
        gb = d.add(logic.SchmittNot().right().anchor("in1").label("U1B  3 → 4", loc="bottom", ofst=0.25))
        d.add(elm.Line().at(gb.out).right(0.8))
        bus = d.here
        # four parallel drivers, each with its own 180 ohm resistor
        ys = [2.4, 0.8, -0.8, -2.4]
        pins = [("5 → 6", "U1C"), ("9 → 8", "U1D"), ("11 → 10", "U1E"), ("13 → 12", "U1F")]
        outs = []
        for y, (pn, nm) in zip(ys, pins):
            d.add(elm.Line().at(bus).to((bus[0], bus[1] + y)))
            d.add(elm.Line().right(0.6))
            g = d.add(logic.SchmittNot().right().anchor("in1").label(f"{nm}  {pn}", loc="top", ofst=0.1))
            d.add(elm.Resistor().at(g.out).right().label("180 Ω", loc="bottom"))
            outs.append(d.here)
        x_out = outs[0][0] + 0.8
        for q in outs:
            d.add(elm.Line().at(q).to((x_out, q[1])))
        d.add(elm.Line().at((x_out, outs[0][1])).to((x_out, outs[-1][1])))
        mid = (x_out, (outs[0][1] + outs[-1][1]) / 2)
        d.add(elm.Dot().at(mid))
        d.add(elm.Line().at(mid).right(1.0))
        d.add(elm.CoaxConnect().right().label("BNC OUT (Rs ≈ 48 Ω)", loc="right"))
        # power supply and decoupling
        y_p = -5.2
        d.add(elm.Dot(open=True).at((-1.0, y_p)).label("+5 V", loc="left"))
        d.add(elm.Line().right(1.6))
        a = d.add(elm.Dot()).center
        d.add(elm.Capacitor().down().label("100 nF X7R", loc="top"))
        d.add(elm.Ground())
        d.add(elm.Line().at(a).right(2.2))
        b = d.add(elm.Dot()).center
        d.add(elm.Capacitor(polar=True).down().label("10 µF", loc="bottom"))
        d.add(elm.Ground())
        d.add(elm.Line().at(b).right(2.2))
        d.add(elm.Dot(open=True).label("U1 pin 14 (VCC)", loc="right"))
        d.add(elm.Dot(open=True).at((b[0] + 9.5, y_p)).label("U1 pin 7 (GND)", loc="left"))
        d.add(elm.Line().down(1.0))
        d.add(elm.Ground())
        note(d, "74AC14 (AC family, not HC). Decoupling capacitors directly at pins 14/7. Output path < 1 cm. "
                "Only with instructor approval.")
        save(d, "c12_fast_edge_pulser")


def c13_pulser_test():
    with schemdraw.Drawing(show=False) as d:
        d.config(unit=2.4)
        generator(d, label="74AC14 pulser (5 V)", vs="0 → 5 V\n≈100 kHz")
        coax(d, length=2.5, label="short BNC lead")
        t = tee(d, "scope CH1")
        scope_input(d, t.center)
        d.add(elm.Line().at(t.center).right(3.2))
        d.add(elm.Switch().down().label("step (b)\nonly", loc="bottom"))
        d.add(elm.Resistor().down().label("50 Ω\nfeed-through", loc="bottom"))
        d.add(elm.Ground())
        note(d, "Bring-up: (a) open: about 0-5 V, ≈100 kHz   (b) 50 Ω: about 2.5 V; Rs = 50 Ω × (V_open/V_50 − 1) should be 45-55 Ω.\n"
            "Then measure the 10-90 % rise time and compare with the function generator.")
        save(d, "c13_pulser_test")


# ---------------------------------------------------------------- expected waveforms
def _style():
    plt.rcParams.update({"figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
                         "axes.edgecolor": INK2, "axes.labelcolor": INK, "text.color": INK,
                         "xtick.color": INK2, "ytick.color": INK2, "axes.grid": True, "grid.color": GRID,
                         "axes.spines.top": False, "axes.spines.right": False, "lines.linewidth": 2,
                         "legend.frameon": False, "font.size": 10, "axes.titleweight": "bold"})


def trace(cls="open", d=5.0, snr=38, seed=1, **kw):
    cfg = SimConfig()
    p = make_params(cfg, cls=cls, d=d, rise=RISE, snr_db=snr, ts=0.5e-9, seed=seed, vp=VP, **kw)
    (t, v), = simulate(p, cfg)
    v = v - np.median(v[t < -10e-9])
    return t * 1e9, v / p["v_inc"][0], float(p["dt_true"][0]) * 1e9


def _finish(ax, title, xmax, fname, note=None):
    ax.set(title=title, xlabel="time after the incident edge (ns)  [scope: trigger at 0]",
           ylabel="voltage at the tee (V), V_inc = 1 V", xlim=(-20, xmax))
    ax.legend(fontsize=8, loc="best")
    if note:
        ax.text(0.01, -0.22, note, transform=ax.transAxes, fontsize=8, color=INK2, va="top")
    plt.tight_layout()
    plt.savefig(OUT / fname, dpi=150)
    plt.close()


def w_generator():
    fig, ax = plt.subplots(figsize=(8, 4))
    t = np.linspace(-30, 60, 900)
    from scipy.special import erf
    s = 0.5 * (1 + erf(t / (RISE * 1e9 / 2.5631) / np.sqrt(2)))
    ax.plot(t, 2 * s, color=C1, label="(a) no terminator: V_open ≈ 2 V")
    ax.plot(t, 1 * s, color=C2, label="(b) 50 Ω feed-through: V_50 ≈ 1 V  → Rs = 50·(2/1 − 1) = 50 Ω")
    t10, t90 = -RISE * 1e9 / 2, RISE * 1e9 / 2
    for x in (t10, t90):
        ax.axvline(x, color=INK2, ls=":", lw=1)
    ax.annotate("", xy=(t90, 0.5), xytext=(t10, 0.5), arrowprops=dict(arrowstyle="<->", color=INK2))
    ax.text(t90 + 1, 0.45, f"10-90 % rise ≈ {RISE * 1e9:.0f} ns (yours: read it)", fontsize=8, color=INK2)
    _finish(ax, "H3 expected: generator step, open vs 50 Ω load", 60, "w01_generator_check.png")


def w_ends(kind, fname, title, **kw):
    fig, ax = plt.subplots(figsize=(9, 4.4))
    for L, col in zip((2.0, 5.0, 10.0), (C1, C2, C3)):
        t, v, dt = trace(kind, d=L, **kw)
        ax.plot(t, v, color=col, lw=1.6, label=f"L = {L:g} m: echo at Δt = 2L/vp ≈ {dt:.1f} ns")
        ax.axvline(dt, color=col, ls=":", lw=1)
    _finish(ax, title, 140, fname,
            f"RG-58 (vp ≈ {VP / 1e8:.2f}×10⁸ m/s), rise time 5 ns, about 38 dB SNR. d = vp·Δt/2.")


def w_one(fname, title, curves, xmax=90, note=None):
    fig, ax = plt.subplots(figsize=(9, 4.4))
    for (lab, kw), col in zip(curves, (C1, C2, C3)):
        t, v, dt = trace(**kw)
        ax.plot(t, v, color=col, lw=1.6, label=f"{lab} (Δt ≈ {dt:.1f} ns)")
        ax.axvline(dt, color=col, ls=":", lw=1)
    _finish(ax, title, xmax, fname, note)


def w_low_snr():
    fig, ax = plt.subplots(figsize=(9, 4.4))
    for snr, col, lab in ((38, C1, "normal amplitude (≈38 dB)"), (15, C2, "low amplitude / attenuator (≈15 dB)")):
        t, v, dt = trace("open", d=5.0, snr=snr, seed=3)
        ax.plot(t, v, color=col, lw=1.2 if snr < 30 else 1.8, label=lab)
    ax.axvline(dt, color=INK2, ls=":", lw=1)
    _finish(ax, "H8 expected: same 5 m open cable, normal vs low SNR", 90, "w11_low_snr.png",
            "Low-SNR traces are noisy by design: they test the noise robustness of the baseline vs the ML models (E1).")


def w_pulser():
    fig, ax = plt.subplots(figsize=(9, 4.4))
    for rise, col, lab in ((10e-9, C1, "function generator, ~10 ns edge"), (2.5e-9, C2, "74AC14 pulser, ~2.5 ns edge")):
        cfg = SimConfig()
        p = make_params(cfg, cls="open", d=1.0, rise=rise, snr_db=45, ts=0.25e-9, seed=2, vp=VP)
        (t, v), = simulate(p, cfg)
        v = v - np.median(v[t < -10e-9])
        ax.plot(t * 1e9, v / p["v_inc"][0], color=col, label=lab)
    ax.axvline(2 * 1.0 / VP * 1e9, color=INK2, ls=":", lw=1)
    _finish(ax, "H10 expected: 1 m open cable, slow vs fast edge", 50, "w12_pulser_resolution.png",
            "With the slow edge the 1 m echo (Δt ≈ 10 ns) merges with the incident step; with the fast edge two steps are visible.")


# ---------------------------------------------------------------- pictorial wiring drawings (beginners)
def _box(ax, x, y, w, h, label, fc="#f1f0ec", ec=None, fs=9, bold=True, va="top"):
    from matplotlib.patches import FancyBboxPatch
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.12",
                                fc=fc, ec=ec or INK2, lw=1.4))
    if label:
        ax.text(x + w / 2, y + h - 0.12 if va == "top" else y + h / 2, label, ha="center", va=va,
                fontsize=fs, fontweight="bold" if bold else "normal", color=INK)


def _bnc(ax, x, y, label=None, side="below", r=0.17):
    from matplotlib.patches import Circle
    ax.add_patch(Circle((x, y), r, fc="#c9c7c0", ec=INK, lw=1.2, zorder=5))
    ax.add_patch(Circle((x, y), r * 0.35, fc=INK, ec=INK, zorder=6))
    if label:
        dy = -0.32 if side == "below" else 0.32
        ax.text(x, y + dy, label, ha="center", va="top" if side == "below" else "bottom", fontsize=7.5, color=INK2)


def _coil(ax, x0, x1, y, loops=5, amp=0.35, color="#3d3c39", lw=3.0):
    xs = np.linspace(x0, x1, 400)
    ys = y + amp * np.sin(np.linspace(0, loops * 2 * np.pi, 400)) * np.hanning(400) ** 0.3
    ax.plot(xs, ys, color=color, lw=lw, solid_capstyle="round", zorder=3)


def _lead(ax, pts, color="#3d3c39", lw=3.0, ls="-"):
    from scipy.interpolate import make_interp_spline
    pts = np.asarray(pts, float)
    if len(pts) > 2:
        tt = np.linspace(0, 1, len(pts))
        sp = make_interp_spline(tt, pts, k=2)
        pts = sp(np.linspace(0, 1, 200))
    ax.plot(pts[:, 0], pts[:, 1], color=color, lw=lw, ls=ls, solid_capstyle="round", zorder=3)


def _tee(ax, x, y, w=0.9):
    """BNC tee hanging below a front-panel connector at (x, y): stem down, two side ports."""
    ax.plot([x, x], [y, y - 0.55], color="#8d8b84", lw=7, solid_capstyle="butt", zorder=4)
    ax.plot([x - w / 2, x + w / 2], [y - 0.62, y - 0.62], color="#8d8b84", lw=9, solid_capstyle="butt", zorder=4)
    return (x - w / 2, y - 0.62), (x + w / 2, y - 0.62)


def p01_wiring():
    fig, ax = plt.subplots(figsize=(11, 5.6))
    ax.set_xlim(0, 16)
    ax.set_ylim(-0.6, 7.4)
    ax.axis("off")
    # function generator
    _box(ax, 0.3, 3.0, 3.6, 2.4, "Function generator")
    _box(ax, 0.6, 4.05, 2.2, 0.75, "", fc="#dfe9f6", ec=C1)
    ax.text(1.7, 4.43, "SQUARE 100 kHz\nLOW 0 V · HIGH 2 V", ha="center", va="center", fontsize=7.5, color=INK)
    _bnc(ax, 3.3, 3.45, None)
    ax.text(3.0, 3.45, "OUTPUT (50 Ω)", ha="right", va="center", fontsize=7.5, color=INK2)
    # oscilloscope
    _box(ax, 5.6, 2.6, 5.2, 3.9, "Oscilloscope (CH1: 1 MΩ, DC, BW limit off)")
    _box(ax, 5.95, 3.55, 3.3, 2.35, "", fc="#10202f", ec=INK)
    tt = np.linspace(0, 1, 100)
    yy = np.where(tt < 0.2, 0, np.where(tt < 0.55, 0.45, 0.95))
    ax.plot(6.1 + 3.0 * tt, 3.75 + 1.6 * yy, color="#7fd1ff", lw=1.6, zorder=6)
    ax.text(7.6, 5.75, "incident step, then echo", ha="center", fontsize=7, color="#d7e9f7", zorder=7)
    _bnc(ax, 6.6, 2.95, None)
    ax.text(6.6, 3.3, "CH1", ha="center", fontsize=7.5, color=INK2)
    for i, x in enumerate((7.5, 8.3, 9.1)):
        _bnc(ax, x, 2.95, None, r=0.13)
    ax.text(10.2, 3.1, "USB-B\n(rear)", ha="center", fontsize=7.5, color=INK2)
    # tee on CH1
    lp, rp = _tee(ax, 6.6, 2.78)
    ax.annotate("BNC tee directly on CH1\n= reference plane (d = 0)", xy=(6.6, 2.05), xytext=(4.5, 0.75),
                fontsize=8, color=INK, arrowprops=dict(arrowstyle="->", color=INK2), ha="center")
    # short lead generator -> tee left port
    _lead(ax, [(3.3, 3.28), (4.2, 1.7), (lp[0] - 0.05, lp[1])])
    ax.text(2.3, 2.15, "short lead ≤ 0.5 m", fontsize=8, color=INK2, ha="center")
    # cable under test
    _lead(ax, [(rp[0] + 0.05, rp[1]), (8.0, 1.2), (8.8, 1.15)])
    _coil(ax, 8.8, 13.2, 1.15, loops=6)
    ax.text(11.0, 0.3, "cable under test (RG-58, length L measured with tape)", ha="center", fontsize=8, color=INK)
    _bnc(ax, 13.45, 1.15, None)
    _box(ax, 13.75, 0.55, 2.0, 1.2, "", fc="#fbe9df", ec=C2)
    ax.text(14.75, 1.15, "termination / fault\nopen · short cap\n50 Ω · R · joint · stub", ha="center",
            va="center", fontsize=7.5, color=INK)
    # laptop
    _box(ax, 12.4, 4.4, 3.2, 2.0, "Laptop", fc="#eef6ef", ec=C3)
    ax.text(14.0, 5.1, "python index.py capture\n(saves CSV + lab_log.csv)", ha="center", va="center",
            fontsize=7.5, color=INK, family="monospace")
    _lead(ax, [(10.8, 3.6), (11.6, 4.3), (12.4, 5.0)], color=C3, lw=2.2, ls="--")
    ax.text(11.75, 3.55, "USB A-B (USBTMC)", fontsize=7.5, color=C3, ha="left")
    # mains
    ax.text(0.3, 6.95, "Mains (earthed sockets) to generator and scope · laptop on battery if hum appears",
            fontsize=8, color=INK2)
    ax.text(0.3, -0.45, "Echo time Δt = 2L/vp (≈ 10 ns per metre of RG-58)  →  distance d = vp·Δt/2",
            fontsize=8.5, color=INK, fontweight="bold")
    plt.tight_layout()
    plt.savefig(OUT / "p01_wiring_overview.png", dpi=150)
    plt.close()


def p02_fixtures():
    fig, axs = plt.subplots(2, 3, figsize=(12, 6.2))
    for a in axs.flat:
        a.set_xlim(0, 10)
        a.set_ylim(0, 5)
        a.axis("off")

    def cable(ax, x0, x1, y, lab=None, loops=3, col="#3d3c39"):
        _coil(ax, x0, x1, y, loops=loops, amp=0.22, color=col, lw=2.6)
        if lab:
            ax.text((x0 + x1) / 2, y - 0.55, lab, ha="center", fontsize=7.5, color=INK2)

    def resistor(ax, x0, x1, y, lab, at=None):
        xs = np.linspace(x0, x1, 9)
        ys = y + np.array([0, .18, -.18, .18, -.18, .18, -.18, .18, 0])
        ax.plot(xs, ys, color=C2, lw=2, zorder=6)
        lx, ly = at or ((x0 + x1) / 2, y + 0.3)
        ax.text(lx, ly, lab, ha="center" if at is None else "left", fontsize=8, color=C2, fontweight="bold")

    def posts(ax, x, y):
        from matplotlib.patches import Circle
        _box(ax, x - 0.2, y - 0.9, 1.6, 1.8, "", fc="#e9e7e1")
        ax.add_patch(Circle((x + 0.25, y + 0.35), 0.2, fc="#d23b3b", ec=INK, zorder=5))
        ax.add_patch(Circle((x + 0.95, y + 0.35), 0.2, fc="#222", ec=INK, zorder=5))
        ax.text(x + 1.55, y - 0.55, "red = centre\nblack = shell", ha="left", fontsize=6.5, color=INK2)
        return (x + 0.25, y + 0.35), (x + 0.95, y + 0.35)

    # (a) resistive end load
    a = axs[0, 0]
    a.set_title("H7a  resistor at the cable end", fontsize=10, loc="left")
    cable(a, 0.3, 5.0, 2.5, "5 m cable from the tee")
    _bnc(a, 5.25, 2.5)
    r, b = posts(a, 5.7, 2.5)
    xs = np.linspace(r[0], b[0], 7)
    a.plot([r[0], r[0]], [r[1], r[1] + 0.6], color=C2, lw=1.5)
    a.plot([b[0], b[0]], [b[1], b[1] + 0.6], color=C2, lw=1.5)
    resistor(a, r[0], b[0], r[1] + 0.6, "100 Ω or 22 Ω")
    a.text(0.3, 0.6, "BNC → binding-post adapter; resistor leads ≤ 5 mm.\nMeasure R with the multimeter, log the measured value (--zl).",
           fontsize=7.5, color=INK)

    # (b) series box
    a = axs[0, 1]
    a.set_title("H7b  series-resistor box (build, §8.2)", fontsize=10, loc="left")
    cable(a, 0.2, 2.6, 2.6, "3 m")
    _box(a, 2.8, 1.8, 3.4, 1.6, "metal box", fc="#dcdad3", fs=8)
    _bnc(a, 3.2, 2.6, "IN")
    _bnc(a, 5.8, 2.6, "OUT")
    resistor(a, 3.4, 5.6, 2.6, "49.9 Ω")
    cable(a, 6.4, 8.4, 2.6, "2 m")
    _box(a, 8.5, 2.25, 1.2, 0.7, "", fc="#fbe9df", ec=C2)
    a.text(9.1, 2.6, "50 Ω", ha="center", va="center", fontsize=8)
    a.text(0.2, 0.6, "Resistor between the two centre pins; the box joins the shells.\nCheck: centre-centre ≈ 49.9 Ω, shell-shell < 0.5 Ω.",
           fontsize=7.5, color=INK)

    # (c) shunt
    a = axs[0, 2]
    a.set_title("H7c  shunt resistor on a 2nd tee", fontsize=10, loc="left")
    cable(a, 0.2, 3.6, 3.2, "3 m")
    a.plot([3.7, 5.3], [3.2, 3.2], color="#8d8b84", lw=9)
    a.plot([4.5, 4.5], [3.2, 2.7], color="#8d8b84", lw=7)
    a.text(4.5, 3.55, "tee 2", ha="center", fontsize=7.5, color=INK2)
    r, b = posts(a, 3.95, 1.75)
    resistor(a, r[0], b[0], r[1] - 0.45, "49.9 Ω", at=(5.6, 2.25))
    cable(a, 5.4, 8.2, 3.2, "2 m")
    _box(a, 8.3, 2.85, 1.2, 0.7, "", fc="#fbe9df", ec=C2)
    a.text(8.9, 3.2, "50 Ω", ha="center", va="center", fontsize=8)
    a.text(0.2, 0.25, "Stem → binding-post adapter + resistor.\nEnd of the line matched, so only the shunt reflects.",
           fontsize=7.5, color=INK)

    # (d) joint
    a = axs[1, 0]
    a.set_title("H7d  50/75 Ω joint", fontsize=10, loc="left")
    cable(a, 0.2, 3.8, 2.6, "3 m RG-58 (50 Ω)")
    _box(a, 3.9, 2.3, 0.9, 0.6, "", fc="#c9c7c0")
    a.text(4.35, 3.05, "barrel", ha="center", fontsize=7.5, color=INK2)
    cable(a, 4.9, 8.0, 2.6, "2 m RG-59 (75 Ω)", col=C1)
    _box(a, 8.1, 2.25, 1.3, 0.7, "", fc="#fbe9df", ec=C2)
    a.text(8.75, 2.6, "75 Ω", ha="center", va="center", fontsize=8)
    a.text(0.2, 0.6, "Γ = (75 − 50)/(75 + 50) = +0.2 at the barrel; the 75 Ω end is matched.",
           fontsize=7.5, color=INK)

    # (e) stub
    a = axs[1, 1]
    a.set_title("H7e  open stub on a 2nd tee", fontsize=10, loc="left")
    cable(a, 0.2, 3.6, 3.4, "3 m")
    a.plot([3.7, 5.3], [3.4, 3.4], color="#8d8b84", lw=9)
    a.plot([4.5, 4.5], [3.4, 2.7], color="#8d8b84", lw=7)
    _coil(a, 4.5, 4.5 + 0.001, 2.6, loops=1, amp=0.0)
    xs = np.linspace(2.6, 1.0, 200)
    a.plot(4.5 + 0.25 * np.sin(np.linspace(0, 6 * np.pi, 200)), xs, color="#3d3c39", lw=2.6)
    a.text(4.95, 1.4, "1 m stub,\nfar end OPEN", fontsize=7.5, color=INK2)
    cable(a, 5.4, 8.2, 3.4, "2 m")
    _box(a, 8.3, 3.05, 1.2, 0.7, "", fc="#fbe9df", ec=C2)
    a.text(8.9, 3.4, "50 Ω", ha="center", va="center", fontsize=8)
    a.text(0.2, 0.25, "Dip to ≈ 0.67 V lasting 2·l_stub/vp (≈ 10 ns for 1 m).", fontsize=7.5, color=INK)

    # (f) loads
    a = axs[1, 2]
    a.set_title("End loads (S8, S9)", fontsize=10, loc="left")
    for i, (lab, txt) in enumerate((("open", "nothing on the end (Γ = +1 → 2 V)"),
                                     ("short cap", "centre tied to shell (Γ = −1 → 0 V)"),
                                     ("50 Ω terminator", "matched (Γ = 0 → flat 1 V)"))):
        y = 4.0 - 1.3 * i
        cable(a, 0.2, 3.0, y, None, loops=2)
        _bnc(a, 3.25, y)
        if i:
            _box(a, 3.5, y - 0.3, 1.0, 0.6, "", fc="#fbe9df" if i == 2 else "#c9c7c0", ec=C2 if i == 2 else INK2)
        a.text(4.8, y + 0.12, lab, fontsize=8.5, fontweight="bold", color=INK, va="center")
        a.text(4.8, y - 0.32, txt, fontsize=7.5, color=INK2, va="center")
    plt.suptitle("Fault fixtures: how each approved discontinuity is assembled (all start at tee side port 2)",
                 fontsize=11, fontweight="bold", x=0.01, ha="left")
    plt.tight_layout()
    plt.savefig(OUT / "p02_fault_fixtures.png", dpi=150)
    plt.close()


def main():
    _style()
    for f in (c01_generator_check, c02_basic, c03_open, c04_short, c05_matched, c06_resistive, c07_series,
              c08_shunt, c09_joint, c10_stub, c11_low_snr, c12_pulser, c13_pulser_test):
        f()
        print("drew", f.__name__)
    w_generator()
    w_ends("open", "w03_open_end.png", "H5/H6 expected: open end, three lengths (steps up to 2 V)")
    w_ends("short", "w04_short_end.png", "H6 expected: short, three lengths (drops to 0 V)")
    w_ends("matched", "w05_matched_end.png", "H5/H6 expected: matched 50 Ω, three lengths (flat at 1 V)", gamma=0.0)
    w_one("w06_resistive_end.png", "H7 expected: resistive end loads at 5 m",
          [("R_L = 100 Ω → 1.33 V", dict(cls="partial", d=5.0, zl=100.0)),
           ("R_L = 22 Ω → 0.61 V", dict(cls="partial", d=5.0, zl=22.0))])
    w_one("w07_series_resistor.png", "H7 expected: 50 Ω series resistor at d = 3 m (then 2 m + 50 Ω)",
          [("series 50 Ω → step up to 1.33 V", dict(cls="partial", d=3.0, kind=K_SERIES, r_fault=50.0, l2=2.0))])
    w_one("w08_shunt_resistor.png", "H7 expected: 50 Ω shunt resistor at d = 3 m (then 2 m + 50 Ω)",
          [("shunt 50 Ω → step down to 0.67 V", dict(cls="partial", d=3.0, kind=K_SHUNT, r_fault=50.0, l2=2.0))])
    w_one("w09_75ohm_joint.png", "H7 expected: RG-58 → RG-59 joint at d = 3 m",
          [("50/75 Ω joint → step up to 1.2 V", dict(cls="partial", d=3.0, kind=K_STEP, z2=75.0, l2=2.0))])
    w_one("w10_tee_open_stub.png", "H7 expected: tee with 1 m open stub at d = 3 m",
          [("open stub 1 m → dip to 0.67 V for ≈10 ns", dict(cls="partial", d=3.0, kind=K_STUB, l_stub=1.0, l2=2.0))])
    w_low_snr()
    w_pulser()
    p01_wiring()
    p02_fixtures()
    print("done ->", OUT)


if __name__ == "__main__":
    main()
