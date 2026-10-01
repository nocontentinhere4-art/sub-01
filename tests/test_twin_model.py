"""Tests for twin/model.py (TwinBrain: delayed Wilson-Cowan E/I network + Balloon-Windkessel BOLD).

    python -m pytest tests/test_twin_model.py -q        (~40-60 s on one core)
"""
import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import brain_sim  # noqa: E402
import sleep  # noqa: E402
from twin.model import DEFAULTS, Balloon, TwinBrain, _DelayNet, balance, isp_refine, load_connectome, simulate_bold  # noqa: E402

TICK = 0.05          # live_server.TICK
BASELINE_DRIVE = 1.6  # live_server.BASELINE_DRIVE
STAGES = {"AWAKE": sleep.AWAKE, "NREM_LIGHT": sleep.NREM_LIGHT, "NREM_DEEP": sleep.NREM_DEEP, "REM": sleep.REM}


def brain(seed=0, **params):
    return TwinBrain(params=params, params_path=None, seed=seed)     # defaults, independent of a fitted params.json


def apply_stage(b, stage):
    p = STAGES[stage]
    b.set_rhythm(p["f_hz"], p["coupling"], p["noise"])
    b.a = p["a"]


# --- interface ----------------------------------------------------------------------------------------------
def test_interface_matches_brain_sim():
    b = brain()
    assert b.n == 214 and len(b.names) == 214 and b.centroids.shape == (214, 3)
    assert b.W.shape == (214, 214) and b.W0.shape == (214, 214) and np.allclose(b.W, b.W.T)
    assert np.all(np.diag(b.W) == 0) and np.isclose(np.linalg.eigvalsh(b.W).max(), 1.0)
    assert set(brain_sim.GROUPS) | {"language"} <= set(b.group_idx)
    assert all(len(v) > 0 for v in b.group_idx.values())
    assert isinstance(b.t, int) and b.dt == 0.001
    for name in ("stimulate", "step", "run", "state", "set_rhythm", "set_gain", "set_weights", "bold"):
        assert callable(getattr(b, name))
    x = b.step(5)
    assert x.shape == (214,) and np.isrealobj(x) and b.t == 5
    st = b.state()
    assert set(st) == set(b.group_idx) | {"sync"} and 0.0 <= st["sync"] <= 1.0
    r = b.run(0.1, every=10)
    assert r.shape == (10, 214)
    assert b.bold().shape == (214,)


def test_make_brain_factory(monkeypatch):
    monkeypatch.delenv("SUB01_MODEL", raising=False)
    assert isinstance(brain_sim.make_brain(params_path=None), TwinBrain)
    assert isinstance(brain_sim.make_brain("sl"), brain_sim.Brain)
    monkeypatch.setenv("SUB01_MODEL", "sl")
    assert isinstance(brain_sim.make_brain(), brain_sim.Brain)
    with pytest.raises(ValueError):
        brain_sim.make_brain("hopf")


def test_params_json_and_overrides(tmp_path):
    f = tmp_path / "params.json"
    ex = np.linspace(-0.01, 0.01, 214)
    f.write_text(json.dumps({"params": {"G": 2.5, "velocity": 8.0, "excitability": ex.tolist(), "junk": 1}}))
    b = TwinBrain(params_path=f)
    assert b.G0 == 2.5 and b.p["velocity"] == 8.0 and np.allclose(b.excitability, ex) and "junk" not in b.p
    b2 = TwinBrain(params_path=f, params={"G": 1.0})
    assert b2.G0 == 1.0
    assert TwinBrain(params_path=tmp_path / "missing.json").G0 == DEFAULTS["G"]


def test_headless_live_loop():
    """Drive the model exactly like live_server.run_brain + sleep_tick for a few ticks per stage."""
    b = brain(seed=1)
    steps = int(TICK / b.dt)
    gidx = {k: v for k, v in b.group_idx.items() if v}
    rng = np.random.default_rng(0)
    rest = sorted((ROOT / "out" / "rest").glob("*.npz"))
    if rest:
        from real_baseline import RealBaseline
        baseline = RealBaseline(b.names, str(ROOT / "out" / "rest"))
    else:
        baseline = None
    for stage in ("AWAKE", "NREM_LIGHT", "NREM_DEEP", "REM", "AWAKE"):
        for tick in range(40):
            p = STAGES[stage]
            b.set_rhythm(p["f_hz"], p["coupling"], p["noise"])
            b.a = p["a"]
            if stage == "REM" and tick % 20 == 0:
                b.stimulate("relay", 4.0)
                b.stimulate("visual", 3.0)
            gain = {"AWAKE": 1.0, "REM": 0.7}.get(stage, 0.3)
            sig = baseline.advance(TICK) if baseline else rng.standard_normal(b.n)
            b.drive = BASELINE_DRIVE * gain * np.clip(sig, -2.0, 3.0)
            if tick % 7 == 0:                                   # a trade (live_server.apply)
                s = p["gain"] * min(15.0, 2.0 + 3.0 * math.log10(1.0 + 500.0))
                b.stimulate("reward", s)
                b.stimulate("visual", 0.5 * s)
            acc = np.zeros(b.n)
            for _ in range(steps // 5):
                z = b.step(5)
                acc += np.abs(z)
            act = acc / (steps // 5)
            wave = {k: float(z.real[i].mean()) for k, i in gidx.items()}
            st = b.state()
            assert np.all(np.isfinite(act)) and act.min() >= 0.0 and act.max() <= 2.0
            assert all(abs(v) <= 2.0 for v in wave.values())
            assert 0.0 <= st["sync"] <= 1.0
            json.dumps({"act": np.round(act, 3).tolist(), "wave": wave, "sync": round(st["sync"], 3)})
    assert np.all(np.isfinite(b.bold()))


# --- dynamics -------------------------------------------------------------------------------------------------
def test_resting_display_range_and_ei_balance():
    b = brain(seed=2)
    b.run(2.0)
    E, ab, exc, inh, x = [], [], [], [], []
    for _ in range(400):                                 # 4 s
        z = b.step(10)
        c = b.currents()
        E.append(b.E.copy()); ab.append(np.abs(z).mean()); exc.append(c["exc"]); inh.append(c["inh"])
    E, exc, inh = np.array(E), np.array(exc), np.array(inh)
    rho = b.p["rho"]
    assert abs(E.mean() - rho) < 0.03                    # E near the balance target (noise/oscillation lower it a bit)
    assert np.all(np.abs(E.mean(0) - rho) < 0.05)        # every region, not just the average
    assert 0.05 < E.std(0).mean() < 0.15                 # fluctuating, neither silent nor saturated
    assert E.max() < 0.9
    # inhibition cancels a large share of excitation in every region; on average the net drive sits near the
    # balanced sigmoid argument (the time average is lower than at the fixed point because the sigmoid is convex here)
    x_star = b.p["theta"] + math.log(rho / (1 - rho)) / b.p["beta"]
    net = (exc + inh).mean(0)
    assert np.abs(net - x_star).mean() < 0.12
    share = -inh.mean(0) / exc.mean(0)
    assert np.all((share > 0.4) & (share < 0.9))
    assert 0.25 < np.mean(ab) < 0.6                      # display baseline like the old amplitude (~0.3-0.6)


def test_isp_refinement_moves_rates_to_target():
    """Simulated Vogels inhibitory plasticity: fixed point <I (E - rho)> = 0, closer to rho than the analytic one."""
    c = isp_refine({}, seconds=12.0, seed=1)
    assert c.shape == (214,) and np.all(c <= 0) and np.all(np.isfinite(c))
    means = []
    for cc in (None, c):
        b = brain(seed=5, **({} if cc is None else {"c_ie": cc}))
        b.run(1.0, every=50)
        means.append(np.mean([b.step(10) is not None and b.E.mean() for _ in range(500)]))
    rho = DEFAULTS["rho"]
    assert abs(means[1] - rho) < abs(means[0] - rho) and abs(means[1] - rho) < 0.02


def test_stability_long_run_with_stimuli():
    b = brain(seed=3)
    rng = np.random.default_rng(1)
    rest0 = np.mean([b.step(10) is not None and b.E.mean() for _ in range(300)])
    groups = list(b.group_idx)
    for k in range(400):                                # 40 s of heavy, random stimulation + stage changes
        if k % 100 == 0:
            apply_stage(b, ["AWAKE", "NREM_DEEP", "REM", "AWAKE"][k // 100])
        for g in rng.choice(groups, 2):
            b.stimulate(g, float(rng.uniform(0, 15)))
        b.drive = BASELINE_DRIVE * np.clip(rng.standard_normal(b.n), -2, 3)
        x = b.step(100)
        assert np.all(np.isfinite(x)) and np.all(np.abs(x) <= 2.0)
        assert np.all((b.E >= 0) & (b.E <= 1)) and np.all(np.isfinite(b.I)) and np.all(np.isfinite(b.bold()))
        assert np.abs(b.bold()).max() < 30.0
    b.drive[:] = 0.0
    apply_stage(b, "AWAKE")
    b.run(10.0, every=100)                              # quiet: back to the resting state, no runaway
    after = np.mean([b.step(10) is not None and b.E.mean() for _ in range(300)])
    assert abs(after - rest0) < 0.02
    assert np.abs(b.stim).max() < 0.1


def test_heun_step_size_converged():
    def stats(dt):
        b = brain(seed=4, dt=dt, bold_every=int(round(0.01 / dt)))
        b.run(1.0, every=50)
        E = np.array([b.step(int(round(0.005 / dt))) is not None and b.E.copy() for _ in range(1200)])
        f = np.fft.rfftfreq(len(E), 0.005)
        P = (np.abs(np.fft.rfft(E - E.mean(0), axis=0)) ** 2).mean(1)
        return E.mean(), E.std(0).mean(), f[1:][P[1:].argmax()]
    m1, s1, f1 = stats(0.001)
    m2, s2, f2 = stats(0.0005)
    assert abs(m1 - m2) < 0.01 and abs(s1 - s2) / s2 < 0.15 and abs(f1 - f2) < 3.0


def _specific_response(stage, amount=8.0, trials=6, seed=5):
    """Mean rate increase in the stimulated group minus the rest of the brain, 0-1 s after the stimulus."""
    b = brain(seed=seed)
    apply_stage(b, stage)
    b.run(3.0, every=50)
    g = np.array(b.group_idx["reward"])
    o = np.setdiff1d(np.arange(b.n), g)
    out = []
    for _ in range(trials):
        pre = np.mean([b.step(10) is not None and b.E.copy() for _ in range(50)], 0)
        b.stimulate("reward", amount)
        post = np.mean([b.step(10) is not None and b.E.copy() for _ in range(100)], 0)
        d = post - pre
        out.append(d[g].mean() - d[o].mean())
        b.run(3.0, every=100)
    return float(np.mean(out))


def test_nrem_less_reactive_than_awake():
    awake = _specific_response("AWAKE")
    deep = _specific_response("NREM_DEEP")
    light = _specific_response("NREM_LIGHT")
    assert awake > 0.03                                 # a visible, specific response when awake
    assert deep < 0.5 * awake and light < awake


def test_nrem_slow_synchronous_dynamics():
    b = brain(seed=6)
    apply_stage(b, "NREM_DEEP")
    b.run(2.0, every=50)
    E, sync = [], []
    for i in range(1200):                                # 6 s at 5 ms
        b.step(5)
        E.append(b.E.mean())
        if i % 10 == 0:
            sync.append(b.state()["sync"])
    E = np.array(E)
    f = np.fft.rfftfreq(len(E), 0.005)
    P = np.abs(np.fft.rfft(E - E.mean())) ** 2
    assert P[(f > 0.1) & (f < 4)].sum() / P[f > 0.1].sum() > 0.7   # slow (<4 Hz) global fluctuations dominate
    b2 = brain(seed=6)
    b2.run(2.0, every=50)
    s_awake = np.mean([b2.step(50) is not None and b2.state()["sync"] for _ in range(100)])
    assert np.mean(sync) > s_awake + 0.3


# --- hooks ----------------------------------------------------------------------------------------------------
def test_set_gain_ones_is_neutral():
    a, b = brain(seed=7), brain(seed=7)
    b.set_gain(np.ones(214))
    for _ in range(50):
        xa, xb = a.step(10), b.step(10)
    assert np.array_equal(xa, xb) and np.array_equal(a.E, b.E)
    c = brain(seed=7)
    c.set_gain(np.full(214, 1.3))
    for _ in range(50):
        c.step(10)
    assert not np.allclose(c.E, a.E)


def test_set_weights():
    a, b = brain(seed=8), brain(seed=8)
    b.set_weights(b.W0.copy())
    for _ in range(50):
        a.step(10); b.step(10)
    assert np.allclose(a.E, b.E)
    W = b.W0.copy()
    i, j = b.group_idx["reward"][0], b.group_idx["visual"][0]
    W[i, j] = W[j, i] = W[i, j] + 0.05
    b.set_weights(W)
    assert np.allclose(b.W, W) and not np.allclose(b.W, b.W0) and np.allclose(a.W0, b.W0)
    for _ in range(50):
        a.step(10); b.step(10)
    assert not np.allclose(a.E, b.E) and np.all(np.isfinite(b.E))
    with pytest.raises((AssertionError, ValueError)):
        b.set_weights(np.zeros((3, 3)))


# --- BOLD -----------------------------------------------------------------------------------------------------
def test_balloon_impulse_response():
    h = Balloon(1)
    dt = 0.01
    t = np.arange(0, 40, dt)
    y = np.empty(len(t))
    for k, tk in enumerate(t):
        h.step(np.array([1.0 if tk < 0.5 else 0.0]), dt)
        y[k] = h.bold()[0]
    peak = t[y.argmax()]
    assert 4.0 <= peak <= 6.0, peak
    assert y.max() > 0.1                                 # percent signal change
    assert y.min() < 0 and abs(y.min()) < 0.5 * y.max()  # post-stimulus undershoot, smaller than the peak
    assert abs(y[t > 35]).max() < 0.1 * y.max()          # back to baseline


def test_model_bold_follows_stimulus_and_fluctuates_slowly():
    b = brain(seed=9)
    b.run(20.0, every=100)
    g = b.group_idx["visual"]
    o = np.setdiff1d(np.arange(b.n), g)
    rest = []
    for _ in range(30):
        b.step(100)
        rest.append(b.bold())
    b.stimulate("visual", 10.0)
    ev = []
    for _ in range(150):                                  # 15 s at 100 ms
        b.step(100)
        ev.append(b.bold())
    rest, ev = np.array(rest), np.array(ev)
    d = ev[:, g].mean(1) - ev[:, o].mean(1) - (rest[:, g].mean() - rest[:, o].mean())
    tpk = 0.1 * (d.argmax() + 1)
    assert 3.0 <= tpk <= 9.0 and d.max() > 0.1           # delayed hemodynamic response in the stimulated group
    # resting BOLD: slow fluctuations (most variance below 0.1 Hz, like recorded BOLD)
    x = simulate_bold([{}], 240, 1.0, seed=3, burn=20, params_path=None)[0]
    assert x.std(0).mean() > 0.005                       # small without the recorded drive (see docs)
    f = np.fft.rfftfreq(len(x), 1.0)
    P = (np.abs(np.fft.rfft(x - x.mean(0), axis=0)) ** 2).mean(1)
    assert P[(f > 0) & (f < 0.1)].sum() / P[f > 0].sum() > 0.7


# --- batched simulator ----------------------------------------------------------------------------------------
def test_batched_matches_single():
    secs = 60
    bold, rates = simulate_bold([{}, {}], secs, 1.0, seed=11, burn=20, params_path=None, return_rates=True)
    assert bold.shape == (2, secs, 214) and bold.dtype == np.float32 and np.all(np.isfinite(bold))
    b = brain(seed=12)
    b.run(20.0, every=100)
    Es, bs = [], []
    for _ in range(secs):
        for _ in range(10):
            b.step(100)
            Es.append(b.E.copy())
        bs.append(b.bold())
    Es, bs = np.array(Es), np.array(bs)
    assert abs(rates.mean() - Es.mean()) < 0.005
    assert np.allclose(rates.mean(1), rates.mean(), atol=0.005)             # both batch members alike
    s_single, s_batch = bs.std(0).mean(), bold.std(1).mean()
    assert 0.6 < s_batch / s_single < 1.6
    assert abs(bs.mean() - bold.mean()) < 0.3
    # different parameter sets really differ (and each set sees its own delays / coupling)
    b2 = simulate_bold([{"G": 1.0, "velocity": 3.0}, {"G": 5.0, "velocity": 12.0, "noise": 0.03}], 30, 2.0,
                       seed=1, burn=5, params_path=None)
    assert b2.shape == (2, 15, 214) and not np.allclose(b2[0], b2[1])


# --- performance ------------------------------------------------------------------------------------------------
def test_realtime_budget_single_thread():
    """Live settings (dt 1 ms, BOLD on, step(5) x 10 per 50 ms tick): <= 0.3 s wall per simulated second."""
    b = brain(seed=13)
    b.step(5)
    t0 = time.perf_counter()
    for tick in range(40):                                  # 2 s of model time
        b.set_rhythm(10.0, 1.0, 0.5)
        b.a = -5.0
        b.drive = np.zeros(b.n)
        if tick % 5 == 0:
            b.stimulate("reward", 6.0)
        acc = np.zeros(b.n)
        for _ in range(10):
            acc += np.abs(b.step(5))
        b.state()
    per_s = (time.perf_counter() - t0) / 2.0
    print(f"wall per simulated second: {per_s:.3f} s")
    assert per_s <= 0.3


# --- review additions: delay indexing, balance, refined c_IE kept by set_weights -------------------------------
@pytest.mark.parametrize("B", [1, 3])
def test_delay_ring_buffer_matches_brute_force(B):
    """Every edge reads exactly E_j(t - d_ij steps) (d = round(L / v / dt) >= 1), also after the ring wraps."""
    W, L, _, _ = load_connectome()
    n, dt = len(W), 0.001
    vel = [6.0, 4.0, 9.0][:B]
    net = _DelayNet(W, L, vel if B > 1 else 6.0, dt, B, init=0.0)
    dd = [np.maximum(np.round(L / 1000.0 / v / dt).astype(int), 1) for v in vel]
    ii, jj = np.nonzero(W)
    rng = np.random.default_rng(0)
    hist = []
    for _ in range(net.H + 40):                     # more than one full wrap of the buffer
        out = net.delayed_input()
        ref = np.zeros((B, n))
        for b in range(B):
            idx = len(hist) - 1 - dd[b][ii, jj]     # the newest pushed sample is delay 0
            val = np.array([hist[k][b, j] if k >= 0 else 0.0 for k, j in zip(idx, jj)])
            np.add.at(ref[b], ii, W[ii, jj] * val)
        assert np.abs(out - ref).max() < 1e-12
        x = rng.random((B, n))
        net.push(x)
        hist.append(x)


def test_ei_balance_fixed_point_is_at_target():
    """balance(): with the returned c_IE the deterministic node (no noise) sits exactly at E = rho, I = I*."""
    from twin.model import sigmoid
    W, _, _, _ = load_connectome()
    p = dict(DEFAULTS)
    for G in (1.0, 3.0):
        c, i_star, home = balance(p, W, G)
        rho = p["rho"]
        x_e = p["c_ee"] * rho + c * i_star + p["P"] + home + G * W.sum(1) * rho
        assert np.allclose(sigmoid(x_e, p["beta"], p["theta"]), rho, atol=1e-9)
        assert np.isclose(sigmoid(p["c_ei"] * rho + p["c_ii"] * i_star + p["Q"], p["beta"], p["theta"]), i_star, atol=1e-9)


def test_set_weights_keeps_refined_cie_and_negative_edges():
    rng = np.random.default_rng(1)
    refine = rng.normal(0.0, 0.05, 214)
    base = brain(seed=3)
    c0 = base.c_ie + refine
    b = brain(seed=3, c_ie=c0)
    assert np.allclose(b.c_ie, c0)
    b.set_weights(b.W0.copy())                       # identical weights: the fitted c_IE must survive
    assert np.allclose(b.c_ie, c0)
    W = b.W0.copy()
    i, j = b.group_idx["reward"][0], b.group_idx["visual"][0]
    W[i, j] = -0.02                                  # a (non-physical) negative edge still gets its delay
    b.set_weights(W)
    b.step(50)
    assert np.all(np.isfinite(b.E))
