import numpy as np
import pytest

from src.baseline import detect
from src.config import K_END, K_SERIES, K_SHUNT, K_STEP, K_STUB, SimConfig
from src.features import FEATURES_B, process_traces
from src.preprocess import preprocess, to_grid
from src.sim_tdr import make_params, sample_params, simulate

CFG = SimConfig()


def norm_trace(**kw):
    p = make_params(CFG, **kw)
    (t, v), = simulate(p, CFG, noiseless=True)
    return t, v / p["v_inc"][0], p


@pytest.mark.parametrize("cls,kw,final", [
    ("open", {}, 2.0), ("short", {}, 0.0), ("matched", {"gamma": 0.0}, 1.0),
    ("partial", {"zl": 100.0}, 4 / 3), ("partial", {"kind": K_SERIES, "r_fault": 50.0}, 4 / 3),
    ("partial", {"kind": K_SHUNT, "r_fault": 50.0}, 2 / 3), ("partial", {"kind": K_STEP, "z2": 75.0}, 1.2),
])
def test_final_levels(cls, kw, final):
    t, vn, _ = norm_trace(cls=cls, d=5.0, **kw)
    assert abs(vn[-1] - final) < 0.03            # small DC/skin-effect loss allowed
    assert abs(vn[(t > 10e-9) & (t < 30e-9)].mean() - 1.0) < 0.01   # incident plateau


def test_stub_returns_to_line():
    t, vn, p = norm_trace(cls="partial", d=5.0, kind=K_STUB, l_stub=1.0)
    tau = p["dt_true"][0]
    dip = vn[(t > tau + 2e-9) & (t < tau + 8e-9)].min()
    assert dip < 0.75                              # Gamma = -1/3 dip
    assert abs(vn[-1] - 1.0) < 0.03                # open stub is invisible at DC


@pytest.mark.parametrize("d", [2.0, 5.0, 10.0])
def test_reflection_delay(d):
    t, vn, p = norm_trace(cls="open", d=d, rise=3e-9)
    pr = preprocess(t, vn * p["v_inc"][0], v_inc=p["v_inc"][0])
    b = detect(pr, p["vp"][0])
    assert b.found and b.cls == "open"
    assert abs(b.dt - p["dt_true"][0]) < 1.5e-9    # 50 %-to-50 %, dispersion adds < 1.5 ns


@pytest.mark.parametrize("cls,kw", [("open", {}), ("short", {}), ("partial", {"zl": 150.0}),
                                    ("partial", {"kind": K_SHUNT, "r_fault": 30.0})])
@pytest.mark.parametrize("d", [3.0, 12.0])
def test_baseline_clean(cls, kw, d):
    p = make_params(CFG, cls=cls, d=d, snr_db=45, rise=4e-9, **kw)
    (t, v), = simulate(p, CFG)
    pr = preprocess(t, v, v_inc=p["v_inc_ref"][0])
    b = detect(pr, p["vp"][0], CFG.preset)
    assert b.found
    assert abs(b.distance - d) < 0.3
    assert b.cls == cls


def test_baseline_matched_has_no_fault():
    p = make_params(CFG, cls="matched", d=6.0, gamma=0.0, snr_db=40)
    (t, v), = simulate(p, CFG)
    b = detect(preprocess(t, v, v_inc=p["v_inc_ref"][0]), p["vp"][0])
    assert b.cls == "matched"


def test_estimated_v_inc_close_to_true():
    p = make_params(CFG, cls="open", d=8.0, snr_db=40)
    (t, v), = simulate(p, CFG)
    pr = preprocess(t, v)                          # no V_inc given
    assert pr.ok
    assert abs(pr.v_inc / p["v_inc"][0] - 1) < 0.05


def test_process_traces_shapes():
    p = sample_params(40, CFG, np.random.default_rng(0))
    tr = simulate(p, CFG)
    X, F, B = process_traces(tr, p["v_inc_ref"], vp=CFG.vp_nominal, preset=CFG.preset)
    assert X.shape == (40, 256)
    assert list(F.columns) == FEATURES_B
    assert np.isfinite(F.to_numpy()).all()
    assert len(B) == 40


def test_grid_is_aligned():
    p = make_params(CFG, cls="matched", d=5.0, gamma=0.0, snr_db=60, ts=0.5e-9)
    (t, v), = simulate(p, CFG)
    g = to_grid(preprocess(t, v, v_inc=p["v_inc"][0]))
    assert abs(g[16] - 0.5) < 0.1                 # grid index 16 is t = 0 (incident 50 %)
    assert abs(g[-1] - 1.0) < 0.05
