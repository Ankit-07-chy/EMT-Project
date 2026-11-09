"""Transmission-line TDR simulator (WP4).

Two physics models produce the noiseless step response at the BNC tee:

``tline`` (default)
    Frequency-domain model. The input reflection coefficient of the cable is
    built from the far end back to the tee, using a lossy propagation constant

        gamma(f) = alpha(f) + j*beta(f)
        alpha(f) = alpha_dc + k_skin*sqrt(f) + k_diel*f
        beta(f)  = 2*pi*f/vp + k_skin*sqrt(f)   (skin-effect phase -> dispersion)

    and the tee voltage is V_tee/V_s = Z_in || Z_scope / (R_s + Z_in || Z_scope).
    Multiple reflections, source mismatch, scope input capacitance and
    frequency-dependent loss all come out of this automatically.

``simple``
    The analytic model from the project brief: the incident edge, plus a
    copy delayed by 2d/vp and scaled by Gamma*exp(-2*alpha*d), both smoothed
    by the same Gaussian rise-time filter.

Both models are then sampled like a scope (random trigger offset, chosen Ts)
and corrupted with white/pink noise, baseline drift, offset and 8-bit ADC
quantisation.

Fault geometry (single main discontinuity at distance d from the tee):
    K_END     cable terminated at d with load Gamma (open/short/matched/resistor)
    K_SERIES  series resistor at d, cable continues l2 m to a ~matched end
    K_SHUNT   shunt resistor at d (partial short), cable continues l2 m
    K_STEP    impedance step at d (e.g. 50/75 ohm joint), continues l2 m
    K_STUB    BNC tee at d with an open stub of length l_stub
"""
from __future__ import annotations

import numpy as np
from scipy.special import erf

from .config import (CLASSES, K_END, K_SERIES, K_SHUNT, K_STEP, K_STUB,
                     KIND_NAMES, SimConfig)

DT_SIM = 0.2e-9      # internal time step of the physics model
N_FFT = 8192         # 1.64 us frame -> long enough for all reflections to decay
T0_SIM = 40e-9       # incident edge position inside the FFT frame
RISE_TO_SIGMA = 2.5631  # 10-90 % rise time of a Gaussian edge = 2.5631 sigma


# ---------------------------------------------------------------- parameters
def sample_params(n: int, cfg: SimConfig, rng: np.random.Generator,
                  classes: list[str] | np.ndarray | None = None,
                  snr_db: float | None = None,
                  d_range: tuple[float, float] | None = None,
                  gamma_abs: float | None = None) -> dict[str, np.ndarray]:
    """Draw ``n`` random, labelled trace configurations.

    classes   : class per trace, or None for balanced random classes
    snr_db    : fix the SNR (E1 sweep) instead of drawing it from cfg.snr_db
    d_range   : override the fault-distance range (E2 held-out distances)
    gamma_abs : force partial faults with this |Gamma| (E5 soft-fault sweep)
    """
    pre = cfg.preset
    u = lambda lo_hi, size=n: rng.uniform(lo_hi[0], lo_hi[1], size)

    if classes is None:
        cls = rng.choice(CLASSES, n)
    else:
        cls = np.asarray(classes, dtype=object)
        if cls.size == 1:
            cls = np.repeat(cls, n)
    cls = cls.astype("<U8")

    z0 = np.full(n, pre.z0)
    d = u(d_range or (cfg.d_min, cfg.d_max))
    kind = np.full(n, K_END)
    gamma_end = np.zeros(n)
    gamma_true = np.zeros(n)
    r_fault = np.full(n, np.inf)
    z2 = z0.copy()
    l2 = np.ones(n)          # dummy for K_END (unused but keeps maths finite)
    l_stub = np.ones(n)

    for i in range(n):
        c = cls[i]
        if c == "open":
            gamma_end[i] = gamma_true[i] = 1.0
        elif c == "short":
            gamma_end[i] = gamma_true[i] = -1.0
        elif c == "matched":
            zl = pre.z0 * rng.uniform(1 - cfg.matched_tol, 1 + cfg.matched_tol)
            gamma_end[i] = gamma_true[i] = (zl - pre.z0) / (zl + pre.z0)
        else:  # partial
            g = gamma_abs if gamma_abs is not None else rng.uniform(*cfg.gamma_partial)
            choices = [K_END, K_SERIES, K_SHUNT, K_STEP] + ([K_STUB] if gamma_abs is None else [])
            probs = np.array([0.5, 0.15, 0.15, 0.12, 0.08][:len(choices)])
            k = rng.choice(choices, p=probs / probs.sum())
            kind[i] = k
            if k == K_END:
                gamma_end[i] = gamma_true[i] = g * rng.choice([-1.0, 1.0])
                continue
            l2[i] = rng.uniform(*cfg.l2_range)
            gamma_end[i] = rng.uniform(-0.03, 0.03)  # imperfect far-end terminator
            if k == K_SERIES:
                r_fault[i] = 2 * pre.z0 * g / (1 - g)
                gamma_true[i] = g
            elif k == K_SHUNT:
                r_fault[i] = pre.z0 * (1 / g - 1) / 2
                gamma_true[i] = -g
            elif k == K_STEP:
                gs = min(g, 0.5) * rng.choice([-1.0, 1.0])
                z2[i] = pre.z0 * (1 + gs) / (1 - gs)
                gamma_true[i] = gs
            else:  # open stub on a tee: Gamma = -1/3 for a same-impedance stub
                l_stub[i] = rng.uniform(*cfg.stub_len)
                gamma_true[i] = -1.0 / 3.0

    vp = cfg.vp_nominal * (1 + rng.uniform(-cfg.vp_rel_spread, cfg.vp_rel_spread, n))
    ks, kd = pre.k_skin_diel
    rise = u(cfg.rise_time)
    rs = pre.z0 * u(cfg.rs_rel)
    vs = rng.uniform(1.0, 5.0, n)                   # generator EMF, V
    v_inc = vs * pre.z0 / (rs + pre.z0)             # incident step at the tee
    snr = np.full(n, float(snr_db)) if snr_db is not None else u(cfg.snr_db)
    l_total = np.where(kind == K_END, d, d + l2)

    p = {
        "cls": cls, "kind": kind, "d": d, "l2": l2, "l_stub": l_stub,
        "gamma_end": gamma_end, "gamma_true": gamma_true,
        "r_fault": np.where(np.isfinite(r_fault), r_fault, 1e12), "z2": z2,
        "z0": z0, "vp": vp, "alpha_dc": np.full(n, pre.alpha_dc) * u((0.7, 1.3)),
        "k_skin": np.full(n, ks), "k_diel": np.full(n, kd),
        "atten_scale": u(cfg.atten_scale), "rise": rise, "rs": rs,
        "scope_c": u(cfg.scope_c), "scope_r": np.full(n, cfg.scope_r),
        "ts": rng.choice(np.asarray(cfg.ts_choices), n), "snr_db": snr,
        "jitter": rng.uniform(-cfg.jitter, cfg.jitter, n),
        "vs": vs, "v_inc": v_inc,
        "v_inc_ref": v_inc * (1 + rng.normal(0, cfg.v_inc_cal_err, n)),
        "drift_amp": rng.uniform(0, cfg.drift_max, n) * v_inc,
        "drift_slope": rng.uniform(-1, 1, n),
        "drift_period": rng.uniform(0.5e-6, 5e-6, n),
        "drift_phase": rng.uniform(0, 2 * np.pi, n),
        "offset": rng.uniform(-0.1, 0.1, n) * v_inc,
        "noise_seed": rng.integers(0, 2**31 - 1, n),
        "l_total": l_total, "dt_true": 2 * d / vp,
        "t_pre": np.full(n, cfg.t_pre), "t_post": np.full(n, cfg.t_post),
        "model": np.full(n, cfg.model, dtype="<U6"),
        # lab-like artifacts (used for the proxy lab set, off for training)
        "adapter_len": u((0.03, 0.12)) if cfg.artifacts else np.zeros(n),
        "adapter_z": pre.z0 * u((1.1, 1.4)) if cfg.artifacts else z0.copy(),
        "ring_zeta": u((0.45, 0.8)) if cfg.artifacts else np.zeros(n),
        "ring_fn": u((1.0, 2.0)) * 0.35 / rise if cfg.artifacts else np.zeros(n),
        "pink_frac": u((0.3, 0.7)) if cfg.artifacts else np.zeros(n),
    }
    return p


def make_params(cable_cfg: SimConfig, cls: str = "open", d: float = 5.0,
                kind: int = K_END, gamma: float | None = None, zl: float | None = None,
                r_fault: float | None = None, z2: float | None = None,
                l2: float = 3.0, l_stub: float = 1.0, rise: float = 4e-9,
                snr_db: float = 30.0, ts: float = 1e-9, rs_rel: float = 1.0,
                scope_c: float = 12e-12, vp: float | None = None,
                atten_scale: float = 1.0, seed: int = 0,
                artifacts: bool = False) -> dict[str, np.ndarray]:
    """Build a single, fully specified configuration (dashboard / tests)."""
    rng = np.random.default_rng(seed)
    p = sample_params(1, cable_cfg, rng, classes=[cls], snr_db=snr_db)
    z0 = cable_cfg.preset.z0
    p["d"][:] = d
    p["kind"][:] = kind
    if kind == K_END:
        if zl is not None:
            g = 1.0 if np.isinf(zl) else (zl - z0) / (zl + z0)
        elif gamma is not None:
            g = gamma
        else:
            g = {"open": 1.0, "short": -1.0, "matched": 0.0}.get(cls, 0.3)
        p["gamma_end"][:] = p["gamma_true"][:] = g
        p["l2"][:] = 1.0
    else:
        p["l2"][:] = l2
        p["gamma_end"][:] = 0.0
        if kind == K_SERIES:
            r = r_fault if r_fault is not None else 50.0
            p["r_fault"][:] = r
            p["gamma_true"][:] = r / (r + 2 * z0)
        elif kind == K_SHUNT:
            r = r_fault if r_fault is not None else 50.0
            p["r_fault"][:] = r
            p["gamma_true"][:] = -z0 / (z0 + 2 * r)
        elif kind == K_STEP:
            zz = z2 if z2 is not None else 75.0
            p["z2"][:] = zz
            p["gamma_true"][:] = (zz - z0) / (zz + z0)
        elif kind == K_STUB:
            p["l_stub"][:] = l_stub
            p["gamma_true"][:] = -1.0 / 3.0
    p["rise"][:] = rise
    p["ts"][:] = ts
    p["rs"][:] = z0 * rs_rel
    p["scope_c"][:] = scope_c
    p["atten_scale"][:] = atten_scale
    p["alpha_dc"][:] = cable_cfg.preset.alpha_dc
    if vp is not None:
        p["vp"][:] = vp
    p["jitter"][:] = 0.0
    p["v_inc"][:] = p["vs"] * z0 / (p["rs"] + z0)
    p["v_inc_ref"][:] = p["v_inc"]
    p["l_total"][:] = d if kind == K_END else d + l2
    p["dt_true"][:] = 2 * d / p["vp"]
    if artifacts:
        p["adapter_len"][:] = 0.08
        p["adapter_z"][:] = z0 * 1.25
        p["ring_zeta"][:] = 0.6
        p["ring_fn"][:] = 1.5 * 0.35 / rise
        p["pink_frac"][:] = 0.5
    return p


# ---------------------------------------------------------------- physics
def transfer_function(p: dict, sl: slice, f: np.ndarray) -> np.ndarray:
    """V_tee / V_s for traces ``sl`` at frequencies ``f`` -> (B, F) complex."""
    g = lambda k: np.asarray(p[k][sl], dtype=float)[:, None]
    F = f[None, :]
    sq = np.sqrt(F)
    z0, vp, a = g("z0"), g("vp"), g("atten_scale")
    ks, kd = g("k_skin"), g("k_diel")
    alpha = g("alpha_dc") + a * (ks * sq + kd * F)
    beta = 2 * np.pi * F / vp + a * ks * sq
    gam = alpha + 1j * beta

    kind = np.asarray(p["kind"][sl])[:, None]
    d, l2, ls = g("d"), g("l2"), g("l_stub")
    rf, z2, ge = g("r_fault"), g("z2"), g("gamma_end")

    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        zseg = np.where(kind == K_STEP, z2, z0)
        ga = ge * np.exp(-2 * gam * l2)
        za = zseg * (1 + ga) / (1 - ga)          # impedance looking into far section
        gs = np.exp(-2 * gam * ls)
        zst = z0 * (1 + gs) / (1 - gs)           # open stub input impedance
        zb = np.where(kind == K_SERIES, za + rf, za)
        zb = np.where(kind == K_SHUNT, za * rf / (za + rf), zb)
        zb = np.where(kind == K_STUB, za * zst / (za + zst), zb)
        gb = (zb - z0) / (zb + z0)
        gb = np.where(kind == K_END, ge + 0j, gb)
        gin = gb * np.exp(-2 * gam * d)          # reflection coefficient at the tee
        zref = z0
        la = g("adapter_len")
        if np.any(la > 0):                        # short off-impedance adapter at the tee
            zad = g("adapter_z")
            zx = z0 * (1 + gin) / (1 - gin)
            g1 = (zx - zad) / (zx + zad)
            gin = np.where(la > 0, g1 * np.exp(-2 * gam * la), gin)
            zref = np.where(la > 0, zad, z0)
        rs = g("rs")
        y_sc = 1.0 / g("scope_r") + 1j * 2 * np.pi * F * g("scope_c")
        num = zref * (1 + gin)
        h = num / (num * (1 + rs * y_sc) + rs * (1 - gin))
    return np.nan_to_num(h)


def tline_step_frames(p: dict, sl: slice) -> np.ndarray:
    """Noiseless step response (unit generator EMF) on the internal grid."""
    f = np.fft.rfftfreq(N_FFT, DT_SIM)
    h = transfer_function(p, sl, f)
    sigma = np.asarray(p["rise"][sl], float)[:, None] / RISE_TO_SIGMA
    F = f[None, :]
    h = h * np.exp(-0.5 * (2 * np.pi * F * sigma) ** 2) * np.exp(-2j * np.pi * F * T0_SIM)
    fn = np.asarray(p["ring_fn"][sl], float)[:, None]
    if np.any(fn > 0):                             # generator edge overshoot / ringing
        z = np.asarray(p["ring_zeta"][sl], float)[:, None]
        x = np.where(fn > 0, F / np.where(fn > 0, fn, 1.0), 0.0)
        ring = np.where(fn > 0, 1.0 / (1 - x**2 + 2j * z * x), 1.0)
        h = h * ring
    imp = np.fft.irfft(h, n=N_FFT, axis=1)
    return np.cumsum(imp, axis=1)


def _phi(x):
    return 0.5 * (1 + erf(x / np.sqrt(2)))


def simple_step(p: dict, i: int, t: np.ndarray, preset_alpha) -> np.ndarray:
    """Brief's analytic model for trace ``i`` at times ``t`` (unit EMF)."""
    sig = p["rise"][i] / RISE_TO_SIGMA
    vp, d = p["vp"][i], p["d"][i]
    k_inc = p["z0"][i] / (p["rs"][i] + p["z0"][i])
    a_eff = preset_alpha(0.35 / p["rise"][i]) * p["atten_scale"][i]
    tau = 2 * d / vp
    g = p["gamma_true"][i]
    v = _phi(t / sig) + g * np.exp(-2 * a_eff * d) * _phi((t - tau) / sig)
    kind = p["kind"][i]
    if kind == K_STUB:   # stub end reflection restores the line after 2*l_stub/vp
        tau2 = tau + 2 * p["l_stub"][i] / vp
        v = v - g * np.exp(-2 * a_eff * (d + p["l_stub"][i])) * _phi((t - tau2) / sig)
    elif kind != K_END:  # weak far-end reflection seen through the joint
        L = d + p["l2"][i]
        v = v + (1 - g**2) * p["gamma_end"][i] * np.exp(-2 * a_eff * L) * _phi((t - 2 * L / vp) / sig)
    return k_inc * v


# ---------------------------------------------------------------- scope model
def _vdiv_125(span: float) -> float:
    """Smallest 1-2-5 volts/div that fits ``span`` in 6 divisions."""
    target = max(span, 1e-6) / 6
    k = np.floor(np.log10(target))
    for m in (1, 2, 5, 10):
        if m * 10**k >= target:
            return m * 10**k
    return 10 ** (k + 1)


def _pink(n: int, rng: np.random.Generator) -> np.ndarray:
    x = np.fft.rfft(rng.standard_normal(n))
    f = np.arange(x.size)
    x[1:] /= np.sqrt(f[1:])
    x[0] = 0
    y = np.fft.irfft(x, n=n)
    return y / (y.std() + 1e-12)


def simulate(p: dict, cfg: SimConfig | None = None, batch: int = 128,
             noiseless: bool = False) -> list[tuple[np.ndarray, np.ndarray]]:
    """Return a list of (t [s], v [V]) traces as a scope would record them."""
    from .config import CABLES
    n = len(p["d"])
    out: list[tuple[np.ndarray, np.ndarray]] = [None] * n  # type: ignore
    t_frame = np.arange(N_FFT) * DT_SIM - T0_SIM
    preset_alpha = (cfg.preset if cfg else CABLES["RG-58"]).alpha

    for b0 in range(0, n, batch):
        sl = slice(b0, min(n, b0 + batch))
        use_tline = np.any(p["model"][sl] == "tline")
        frames = tline_step_frames(p, sl) if use_tline else None
        for j, i in enumerate(range(sl.start, sl.stop)):
            ts = float(p["ts"][i])
            nk = int(round((p["t_pre"][i] + p["t_post"][i]) / ts))
            t = -p["t_pre"][i] + ts * np.arange(nk)
            tq = t - p["jitter"][i]
            if p["model"][i] == "tline":
                s = np.interp(tq, t_frame, frames[j])
            else:
                s = simple_step(p, i, tq, preset_alpha)
            v = p["vs"][i] * s
            if noiseless:
                out[i] = (t, v)
                continue
            rng = np.random.default_rng(int(p["noise_seed"][i]))
            span = t[-1] - t[0]
            v = v + p["offset"][i] + p["drift_amp"][i] * (
                p["drift_slope"][i] * (t - t[0]) / span
                + np.sin(2 * np.pi * t / p["drift_period"][i] + p["drift_phase"][i]))
            sigma = p["v_inc"][i] / 10 ** (p["snr_db"][i] / 20)
            noise = rng.standard_normal(nk)
            pf = p["pink_frac"][i]
            if pf > 0:
                noise = np.sqrt(1 - pf) * noise + np.sqrt(pf) * _pink(nk, rng)
            v = v + sigma * noise
            lsb = _vdiv_125(v.max() - v.min()) / 25.0     # 8-bit scope: 25 LSB / div
            v = np.round(v / lsb) * lsb
            out[i] = (t, v.astype(np.float64))
    return out


def params_to_frame(p: dict):
    """Labels and simulation settings as a pandas DataFrame (data dictionary)."""
    import pandas as pd
    cols = ["cls", "kind", "d", "l_total", "dt_true", "gamma_true", "vp", "rise",
            "snr_db", "ts", "rs", "scope_c", "atten_scale", "v_inc", "v_inc_ref",
            "l2", "l_stub", "r_fault", "z2", "model"]
    df = pd.DataFrame({c: p[c] for c in cols})
    df["kind_name"] = [KIND_NAMES[int(k)] for k in p["kind"]]
    df["has_fault"] = df["cls"] != "matched"
    df["artifacts"] = np.asarray(p["adapter_len"]) > 0
    return df
