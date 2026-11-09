"""Automated TDR capture from a bench oscilloscope over USB / LAN (PyVISA).

The scope model is detected from ``*IDN?`` and a matching driver is used
(Rigol DS/MSO1000Z family, Tektronix TBS/TDS/MDO/MSO, Keysight InfiniiVision,
Siglent SDS1000X-E/2000X legacy command set). Every repeat is saved as a
self-describing CSV and appended to the lab log, and a quick baseline check
is printed so a bad setup is noticed immediately.

Examples
    python -m src.capture --list
    python -m src.capture --simulate --repeats 3 --cable RG-58 --length 5 --termination open
    python -m src.capture --resource "USB0::0x1AB1::0x04CE::DS1ZA0000::INSTR" \
        --channel 1 --repeats 20 --cable RG-58 --cable-id C2 --length 5.02 \
        --length-meas 5.01 5.02 5.03 --termination open --operator AB

NOTE: the SCPI command sets follow the vendors' programming manuals but have
not been run on your specific scope. Test with ``--repeats 1`` first and
compare the saved CSV with the scope screen. If the driver fails, export
CSV files from the scope menu instead: ``src.scope_io`` reads those directly.
"""
from __future__ import annotations

import argparse
import csv
import re
import time
from datetime import datetime
from pathlib import Path

import numpy as np

from .config import CABLES, LAB_LOG, RAW_DIR, SimConfig, load_calibration
from .scope_io import save_waveform

LOG_COLUMNS = [
    "file", "date", "time", "operator", "cable_type", "cable_id", "cable_length_m",
    "length_meas_1_m", "length_meas_2_m", "length_meas_3_m", "termination", "fault_kind",
    "fault_position_m", "zl_ohm", "discontinuity_desc", "channel", "gen_model",
    "gen_waveform", "gen_amplitude_v", "gen_period_s", "gen_load_setting", "scope_model",
    "scope_input_impedance", "scope_bw_limit", "sample_interval_s", "averaging",
    "repeat_idx", "notes",
]
TERMINATIONS = ("open", "short", "matched", "partial")
FAULT_KINDS = ("end", "series_R", "shunt_R", "impedance_step", "open_stub")


def _f(s: str) -> float:
    """First float in a SCPI reply such as '5.00E-01V' or 'C1:VDIV 5.00E-01V'."""
    m = re.search(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", s)
    if not m:
        raise ValueError(f"no number in reply {s!r}")
    return float(m.group(0))


# ---------------------------------------------------------------- drivers
class ScopeDriver:
    vendor = "generic"

    def __init__(self, inst):
        self.inst = inst

    def w(self, cmd: str):
        self.inst.write(cmd)

    def q(self, cmd: str) -> str:
        return self.inst.query(cmd).strip()

    def run(self):
        pass

    def stop(self):
        pass

    def read(self, ch: int):
        raise NotImplementedError

    def acquire(self, ch: int, settle: float):
        """Let the scope run for ``settle`` s, freeze it, read one waveform."""
        self.run()
        time.sleep(settle)
        self.stop()
        time.sleep(0.05)
        t, v = self.read(ch)
        return np.asarray(t, float), np.asarray(v, float)


class Rigol(ScopeDriver):
    vendor = "Rigol"

    def run(self):
        self.w(":RUN")

    def stop(self):
        self.w(":STOP")

    def read(self, ch):
        self.w(f":WAV:SOUR CHAN{ch}")
        self.w(":WAV:MODE NORM")
        self.w(":WAV:FORM BYTE")
        pre = [float(x) for x in self.q(":WAV:PRE?").split(",")]
        xinc, xorig, xref, yinc, yorig, yref = pre[4:10]
        raw = self.inst.query_binary_values(":WAV:DATA?", datatype="B", container=np.array)
        v = (raw.astype(float) - yorig - yref) * yinc
        t = (np.arange(len(v)) - xref) * xinc + xorig
        return t, v


class Keysight(ScopeDriver):
    vendor = "Keysight"

    def run(self):
        self.w(":RUN")

    def stop(self):
        self.w(":STOP")

    def read(self, ch):
        self.w(f":WAVeform:SOURce CHANnel{ch}")
        self.w(":WAVeform:FORMat BYTE")
        self.w(":WAVeform:UNSigned ON")
        self.w(":WAVeform:POINts:MODE NORMal")
        pre = [float(x) for x in self.q(":WAVeform:PREamble?").split(",")]
        xinc, xorig, xref, yinc, yorig, yref = pre[4:10]
        raw = self.inst.query_binary_values(":WAVeform:DATA?", datatype="B", container=np.array)
        v = (raw.astype(float) - yref) * yinc + yorig
        t = (np.arange(len(v)) - xref) * xinc + xorig
        return t, v


class Tektronix(ScopeDriver):
    vendor = "Tektronix"

    def run(self):
        self.w("ACQUIRE:STATE RUN")

    def stop(self):
        self.w("ACQUIRE:STATE STOP")

    def read(self, ch):
        self.w("HEADER OFF")
        self.w(f"DATA:SOURCE CH{ch}")
        self.w("DATA:ENCDG RIBINARY")
        self.w("DATA:WIDTH 1")
        self.w("DATA:START 1")
        self.w("DATA:STOP 10000000")
        pref = "WFMOUTPRE"
        try:
            xincr = _f(self.q(f"{pref}:XINCR?"))
        except Exception:
            pref = "WFMPRE"
            xincr = _f(self.q(f"{pref}:XINCR?"))
        xzero = _f(self.q(f"{pref}:XZERO?"))
        ptoff = _f(self.q(f"{pref}:PT_OFF?"))
        ymult = _f(self.q(f"{pref}:YMULT?"))
        yzero = _f(self.q(f"{pref}:YZERO?"))
        yoff = _f(self.q(f"{pref}:YOFF?"))
        raw = self.inst.query_binary_values("CURVE?", datatype="b", is_big_endian=True, container=np.array)
        v = (raw.astype(float) - yoff) * ymult + yzero
        t = xzero + (np.arange(len(v)) - ptoff) * xincr
        return t, v


class Siglent(ScopeDriver):
    """Legacy SDS1000X-E / SDS2000X command set (``C1:WF? DAT2``).

    Newer Siglent HD models use a different binary preamble; export CSV from
    the scope for those. Run/stop is left to the scope (trigger mode NORMAL)
    and a delay separates repeats.
    """
    vendor = "Siglent"
    grid_div = 14  # horizontal divisions on the X-E series

    def read(self, ch):
        self.w("CHDR OFF")
        vdiv = _f(self.q(f"C{ch}:VDIV?"))
        ofst = _f(self.q(f"C{ch}:OFST?"))
        tdiv = _f(self.q("TDIV?"))
        sara = _f(self.q("SARA?"))
        self.w("WFSU SP,0,NP,0,FP,0")
        self.w(f"C{ch}:WF? DAT2")
        raw = self.inst.read_raw()
        i = raw.find(b"#9")
        n = int(raw[i + 2:i + 11])
        code = np.frombuffer(raw[i + 11:i + 11 + n], dtype=np.int8).astype(float)
        v = code * (vdiv / 25.0) - ofst
        try:   # trigger delay moves the trigger point away from the screen centre
            trdl = _f(self.q("TRDL?"))
        except Exception:
            trdl = 0.0
        t = -(tdiv * self.grid_div / 2) - trdl + np.arange(n) / sara
        return t, v


class SimScope(ScopeDriver):
    """Fake scope that returns simulated traces of the labelled setup."""
    vendor = "Simulated"

    def __init__(self, cable: str, length: float, termination: str, fault_kind: str,
                 fault_pos: float | None, zl: float | None, seed: int = 0):
        from .sim_tdr import make_params
        from .config import K_END, K_SERIES, K_SHUNT, K_STEP, K_STUB
        kinds = {"end": K_END, "series_R": K_SERIES, "shunt_R": K_SHUNT,
                 "impedance_step": K_STEP, "open_stub": K_STUB}
        self.cfg = SimConfig(cable=cable if cable in CABLES else "RG-58")
        kind = kinds.get(fault_kind, K_END)
        self.kw = dict(cls=termination, d=fault_pos or length, kind=kind,
                       l2=max(length - (fault_pos or length), 0.5), rise=4e-9,
                       snr_db=32.0, ts=0.5e-9)
        if zl is not None:
            key = {K_END: "zl", K_SERIES: "r_fault", K_SHUNT: "r_fault", K_STEP: "z2"}.get(kind)
            if key:
                self.kw[key] = zl
        if termination == "matched" and zl is None:
            self.kw["gamma"] = 0.0
        self.make = make_params
        self.seed = seed
        self.inst = None

    def acquire(self, ch, settle):
        from .sim_tdr import simulate
        self.seed += 1
        # same cable and generator on every repeat: only noise and trigger jitter change
        p = self.make(self.cfg, seed=self.seed, vp=self.cfg.vp_nominal, **self.kw)
        p["vs"][:] = 2.0
        p["v_inc"][:] = p["v_inc_ref"][:] = 2.0 * p["z0"] / (p["rs"] + p["z0"])
        p["drift_amp"][:] *= 0.25
        p["jitter"][:] = np.random.default_rng(self.seed).uniform(-1e-9, 1e-9)
        (t, v), = simulate(p, self.cfg)
        return t, v


DRIVERS = {"rigol": Rigol, "tektronix": Tektronix, "keysight": Keysight,
           "agilent": Keysight, "siglent": Siglent}


def connect(resource: str | None, timeout_ms: int = 10000):
    import pyvisa
    rm = pyvisa.ResourceManager()
    if resource is None:
        res = [r for r in rm.list_resources() if r.startswith(("USB", "TCPIP"))]
        if not res:
            raise SystemExit("No USB/LAN instrument found. Check the cable, VISA driver and scope USB mode.")
        resource = res[0]
    inst = rm.open_resource(resource)
    inst.timeout = timeout_ms
    inst.chunk_size = 1024 * 1024
    idn = inst.query("*IDN?").strip()
    drv = next((cls for key, cls in DRIVERS.items() if key in idn.lower()), None)
    if drv is None:
        print(f"Unknown vendor in IDN '{idn}', trying the Keysight-style :WAVeform commands")
        drv = Keysight
    return drv(inst), idn, resource


# ---------------------------------------------------------------- logging
def append_log(log_path: Path, row: dict):
    log_path.parent.mkdir(parents=True, exist_ok=True)
    new = not log_path.exists()
    with open(log_path, "a", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=LOG_COLUMNS, extrasaction="ignore")
        if new:
            wr.writeheader()
        wr.writerow({k: row.get(k, "") for k in LOG_COLUMNS})


def quick_check(t, v, cal: dict) -> str:
    from .features import process_one
    pr, b, _, _ = process_one(t, v, float(cal["vp_m_per_s"]), CABLES.get(cal.get("cable_type"), None),
                              t_offset=float(cal.get("t_offset_s", 0.0)), cal=cal)
    if not pr.ok:
        return f"preprocess failed: {pr.msg}"
    if not b.found:
        return f"no reflection found (V_inc {pr.v_inc:.3f} V, rise {pr.rise_inc * 1e9:.1f} ns) -> matched?"
    return (f"dt {b.dt * 1e9:7.2f} ns  d {b.distance:6.2f} m  amp {b.amp:+.3f}  class {b.cls:8s} "
            f"rise {pr.rise_inc * 1e9:.1f} ns  noise {pr.noise_sigma:.4f}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true", help="list VISA instruments and exit")
    ap.add_argument("--resource", help="VISA resource string (default: first USB/LAN instrument)")
    ap.add_argument("--simulate", action="store_true", help="use a simulated scope (no hardware)")
    ap.add_argument("--channel", type=int, default=1)
    ap.add_argument("--repeats", type=int, default=20)
    ap.add_argument("--settle", type=float, default=0.3, help="s the scope runs before each capture")
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--log", type=Path, default=LAB_LOG)
    ap.add_argument("--cable", default="RG-58")
    ap.add_argument("--cable-id", default="")
    ap.add_argument("--length", type=float, required=False, help="cable length in m (mean of tape readings)")
    ap.add_argument("--length-meas", type=float, nargs="*", default=[], help="the 3 tape readings, m")
    ap.add_argument("--termination", choices=TERMINATIONS)
    ap.add_argument("--fault-kind", choices=FAULT_KINDS, default="end")
    ap.add_argument("--fault-position", type=float, default=None, help="m from the tee (default: cable end)")
    ap.add_argument("--zl", type=float, default=None, help="load / fault resistor in ohm, if any")
    ap.add_argument("--desc", default="", help="discontinuity description")
    ap.add_argument("--gen-model", default="")
    ap.add_argument("--gen-waveform", default="square")
    ap.add_argument("--gen-amplitude", default="")
    ap.add_argument("--gen-period", default="")
    ap.add_argument("--gen-load", default="", help="HighZ or 50ohm (generator output setting)")
    ap.add_argument("--scope-input", default="1M")
    ap.add_argument("--bw-limit", default="off")
    ap.add_argument("--averaging", default="1", help="averaging count you set ON THE SCOPE (logged only, not sent)")
    ap.add_argument("--operator", default="")
    ap.add_argument("--notes", default="")
    a = ap.parse_args(argv)

    if a.list:
        import pyvisa
        rm = pyvisa.ResourceManager()
        found = rm.list_resources()
        if not found:
            print(f"No instruments found ({rm.visalib}). Check the USB/LAN cable, that the scope is on, "
                  "its USB mode (USBTMC) and the VISA driver; see hardware/HARDWARE_GUIDE.md, H2.")
        for r in found:
            try:
                inst = rm.open_resource(r)
                inst.timeout = 2000
                print(f"{r}  ->  {inst.query('*IDN?').strip()}")
            except Exception as exc:
                print(f"{r}  ->  (no reply: {exc})")
        return
    if a.length_meas:
        a.length = float(np.mean(a.length_meas))
    if a.length is None or a.termination is None:
        ap.error("--length (or --length-meas) and --termination are required for a capture")
    fault_pos = a.fault_position if a.fault_position is not None else a.length
    if a.simulate:
        drv, idn, res = SimScope(a.cable, a.length, a.termination, a.fault_kind, fault_pos, a.zl), "SIMULATED,TDR,0,1", "sim"
        if a.out_dir is None:
            a.out_dir = RAW_DIR / "simulated_session"
        if a.log == LAB_LOG:
            a.log = a.out_dir / "lab_log.csv"
    else:
        drv, idn, res = connect(a.resource)
    out_dir = a.out_dir or RAW_DIR / datetime.now().strftime("session_%Y-%m-%d")
    print(f"Instrument: {idn} ({res})\nSaving to {out_dir}, log {a.log}")
    cal = load_calibration()
    if not cal["calibrated"]:
        print("(no calibration.json yet: distances use the datasheet vp)")
    lm = (a.length_meas + [None, None, None])[:3]
    stamp = datetime.now().strftime("%H%M%S")
    for r in range(a.repeats):
        t, v = drv.acquire(a.channel, a.settle)
        ts = float(np.median(np.diff(t)))
        name = f"{a.cable}_{a.length:.2f}m_{a.termination}_{a.fault_kind}_{fault_pos:.2f}m_{stamp}_r{r:02d}.csv"
        now = datetime.now()
        row = {"file": "", "date": now.strftime("%Y-%m-%d"), "time": now.strftime("%H:%M:%S"),
               "operator": a.operator, "cable_type": a.cable, "cable_id": a.cable_id,
               "cable_length_m": a.length, "length_meas_1_m": lm[0], "length_meas_2_m": lm[1],
               "length_meas_3_m": lm[2], "termination": a.termination, "fault_kind": a.fault_kind,
               "fault_position_m": fault_pos, "zl_ohm": a.zl if a.zl is not None else "",
               "discontinuity_desc": a.desc, "channel": a.channel, "gen_model": a.gen_model,
               "gen_waveform": a.gen_waveform, "gen_amplitude_v": a.gen_amplitude,
               "gen_period_s": a.gen_period, "gen_load_setting": a.gen_load, "scope_model": idn,
               "scope_input_impedance": a.scope_input, "scope_bw_limit": a.bw_limit,
               "sample_interval_s": ts, "averaging": a.averaging, "repeat_idx": r, "notes": a.notes}
        path = save_waveform(out_dir / name, t, v, row)
        # path relative to the log's folder (portable), absolute if it lives elsewhere
        try:
            row["file"] = Path(path).resolve().relative_to(a.log.resolve().parent).as_posix()
        except ValueError:
            row["file"] = Path(path).resolve().as_posix()
        append_log(a.log, row)
        print(f"[{r + 1:2d}/{a.repeats}] {name}: {quick_check(t, v, cal)}")
    print("Done.")


if __name__ == "__main__":
    main()
