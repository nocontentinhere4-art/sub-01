"""Tests for twin/fit.py (fit of the twin model to the recorded resting-state fMRI) and its committed results.

    python -m pytest tests/test_fit.py -q            (~60-80 s on one core)

A digital twin model of one real person's brain structure and recorded activity; not a mind, not the person.
"""
import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from twin import fit as F  # noqa: E402
from twin.model import TwinBrain, isp_refine, load_connectome, simulate_bold  # noqa: E402

SCORE = json.loads((ROOT / "web" / "twin_score.json").read_text())
PARAMS = json.loads((ROOT / "twin" / "params.json").read_text())


# ---------------------------------------------------------------------------------------------------------- split
@pytest.mark.parametrize("rule", ["interleave", "chronological"])
def test_split_disjoint_by_session_and_complete(rule):
    runs = F.kept_runs()
    qc = json.loads((ROOT / "out" / "rest" / "qc.json").read_text())
    assert len(runs) == sum(v["kept"] for v in qc.values()) == 131
    sp = F.split(runs, rule)
    assert sorted(sp["fit"] + sp["heldout"]) == sorted(runs)              # every kept run, exactly once
    assert not set(sp["fit"]) & set(sp["heldout"])
    fs = {F._session(r) for r in sp["fit"]}
    hs = {F._session(r) for r in sp["heldout"]}
    assert not fs & hs                                                     # disjoint by session
    assert fs == set(sp["fit_sessions"]) and hs == set(sp["heldout_sessions"])
    assert abs(len(fs) - len(hs)) <= 1
    assert F.split(runs, rule) == sp                                       # deterministic
    d = F.session_dates()
    if rule == "interleave":                                               # both halves span the whole year
        year = [s for s in F.sessions_by_date(runs) if d[s] < "2015"]
        for half in (fs, hs):
            dates = sorted(d[s] for s in half if s in year)
            assert dates[0] < "2012-11-01" and dates[-1] > "2014-02-01"
    else:
        assert max(d[s] for s in fs) <= min(d[s] for s in hs)


def test_committed_split_matches_code():
    sp = F.split()
    assert SCORE["split"]["fit_sessions"] == sp["fit_sessions"]
    assert SCORE["split"]["heldout_sessions"] == sp["heldout_sessions"]
    assert SCORE["heldout"]["n_runs"] == len(sp["heldout"])
    assert SCORE["fit"]["n_runs"] == len(sp["fit"])


def test_multi_echo_files_are_one_acquisition():
    runs = [r for r in F.kept_runs() if "echo" in r]
    acqs = F.load_acquisitions(runs)
    assert len(runs) == 3 * len(acqs)
    for a in acqs:
        assert len(a["files"]) == 3 and np.allclose(a["ts"].std(0), 1, atol=1e-6)


# ---------------------------------------------------------------------------------------------------------- metrics
def test_preprocess_matches_process_rest_steps():
    rng = np.random.default_rng(0)
    x = np.cumsum(rng.standard_normal((518, 3)), 0) + 5.0 * np.arange(518)[:, None]
    y = F.preprocess(x, 1.16)
    assert y.shape == (513, 3)
    assert np.allclose(y.mean(0), 0, atol=1e-9) and np.allclose(y.std(0), 1, atol=1e-5)
    f = np.fft.rfftfreq(len(y), 1.16)
    P = (np.abs(np.fft.rfft(y, axis=0)) ** 2).mean(1)
    assert P[(f > 0.01) & (f < 0.1)].sum() / P.sum() > 0.85                # band-limited to 0.01-0.1 Hz


def test_fc_fisher_ks_sanity():
    rng = np.random.default_rng(1)
    s = rng.standard_normal((400, 1))
    x = np.hstack([s + 0.5 * rng.standard_normal((400, 1)) for _ in range(4)])
    fc = F.fc_matrix(x)
    assert np.allclose(np.diag(fc), 1) and np.allclose(fc, fc.T) and (fc[np.triu_indices(4, 1)] > 0.6).all()
    v = fc[np.triu_indices(4, 1)]
    assert np.allclose(F.fisher_mean([v, v, v]), v, atol=1e-6)
    assert abs(F.fisher_mean([np.array([0.5]), np.array([-0.5])])[0]) < 1e-9
    a = rng.standard_normal(5000)
    assert F.ks(a, a) == 0.0 and F.ks(a, a + 100) == 1.0 and F.ks(a, rng.standard_normal(5000)) < 0.05


def test_fcd_values():
    rng = np.random.default_rng(2)
    T, n = 513, 20
    noise = rng.standard_normal((T, n))
    v = F.fcd_values(noise, 1.16)
    w = int(round(60 / 1.16))
    starts = np.arange(0, T - w + 1, int(round(6 / 1.16)))
    i, j = np.triu_indices(len(starts), 1)
    assert len(v) == int(((starts[j] - starts[i]) >= w).sum())             # only non-overlapping window pairs
    assert abs(np.mean(v)) < 0.05                                          # independent windows: FCD ~ 0
    mix = rng.standard_normal((n, n))                                      # fixed correlation structure: FCD high
    v2 = F.fcd_values(rng.standard_normal((T, n)) @ mix, 1.16)
    assert np.mean(v2) > 0.5
    rec = F.load_acquisitions([F.kept_runs()[5]])[0]                       # recorded run: positive, < 1
    v3 = F.fcd_values(rec["ts"], rec["tr"])
    assert 0.0 < np.median(v3) < 0.9 and v3.max() <= 1.0


def test_sim_series_cuts_runs_like_the_recordings():
    bold = np.random.default_rng(3).standard_normal((3 * 518 + 7, 5)).cumsum(0)
    segs = F.sim_series(bold)
    assert len(segs) == 3 and all(s.shape == (513, 5) for s in segs)
    assert np.allclose(segs[1], F.preprocess(bold[518:1036], 1.16))


# ---------------------------------------------------------------------------------------------------------- baselines
def test_shuffled_connectome_keeps_distributions():
    z = np.load(ROOT / "out" / "connectome.npz")
    C, L = z["weights"].astype(float), z["lengths"].astype(float)
    W, Ls = F.shuffled_connectome(0)
    W0 = load_connectome()[0]
    iu = np.triu_indices(len(C), 1)
    assert np.allclose(W, W.T) and np.allclose(Ls, Ls.T)
    assert (W[iu] > 0).sum() == (C[iu] > 0).sum()                         # same density
    assert np.allclose(np.sort(Ls[iu][W[iu] > 0]), np.sort(L[iu][C[iu] > 0]))   # same fibre lengths
    assert abs(np.max(np.linalg.eigvalsh(W)) - 1) < 1e-9                   # same normalisation as the model
    assert np.corrcoef(W[iu], W0[iu])[0, 1] < 0.05                         # wiring destroyed
    assert not np.allclose(F.shuffled_connectome(1)[0], W)


def test_old_model_batch_matches_brain_sim():
    import brain_sim
    _, amp = F.simulate_sl_bold([{}, {"g": 5.0}], 4.0, seed=1, burn=2.0, return_amp=True)
    b = brain_sim.Brain(seed=1)
    b.run(2.0)
    ref = np.mean([b.step(10) is not None and np.abs(b.buf[b.t % b.hist]).mean() for _ in range(400)])
    assert abs(amp.mean() - ref) / ref < 0.05


def test_isp_refine_batch_matches_model():
    p = {"G": 3.0, "isp_frac": 0.5}
    a = F.isp_refine_batch([p], seconds=1.0, seed=4)[0]
    b = isp_refine(p, seconds=1.0, seed=4)
    assert np.allclose(a, b, atol=1e-10)


# ---------------------------------------------------------------------------------------------------------- results
def test_heldout_score_beats_both_baselines():
    h, bl = SCORE["heldout"], SCORE["baselines"]
    for name in ("shuffled_connectome", "old_model"):
        b = bl[name]
        assert h["fc_r"] - h["fcd_ks"] > b["fc_r"] - b["fcd_ks"], name     # the objective
        assert h["fc_r"] > b["fc_r"], name                                 # static FC alone
    assert h["fc_r"] < bl["test_retest_ceiling_r"]
    assert 0 < h["fc_r_sd"] < 0.1 and h["n_sessions"] >= 40


def test_params_json_loaded_by_twin_and_realtime():
    p = PARAMS["params"]
    b = TwinBrain(seed=0)                                                  # default params path = twin/params.json
    assert b.G0 == pytest.approx(p["G"]) and b.sigma0 == pytest.approx(p["noise"])
    assert b.p["velocity"] == pytest.approx(p["velocity"])
    assert SCORE["params"] == p
    assert SCORE["params_check"]["realtime_s_per_sim_s_1thread"] < 0.3
    assert all(c["ok"] for c in SCORE["search"]["live_check"][-1:])
    assert F.realtime_cost(seconds=2.0) < 0.3


def test_quick_recompute_with_fitted_params():
    """Short simulation with twin/params.json -> FC r against the held-out mean FC in a sane range."""
    sp = F.split()
    acqs = F.load_acquisitions(sp["heldout"])
    iu = F.triu(214)
    emp = F.fisher_mean([F.fc_matrix(a["ts"])[iu] for a in acqs])
    bold = simulate_bold([PARAMS["params"]], 518 * F.SIM_TR + 0.5, F.SIM_TR, seed=123, params_path=None)[0]
    feat = F.features(F.sim_series(bold), F.SIM_TR)
    r = F.pearson(feat["fc"], emp)
    one_run = SCORE["heldout"]["fc_r_vs_simulated_runs"]["1"]
    assert 0.0 < r < 0.6
    assert abs(r - one_run) < 0.08                                         # agrees with the committed 1-run value
    assert np.isfinite(feat["fcd"]).all() and len(feat["fcd"]) > 1000


def test_quick_search_machinery(tmp_path):
    """Grid -> CMA-ES -> replication on a tiny budget (40-volume runs): checkpointing and selection work."""
    cfg = dict(F.QUICK, seg_vols=40, grid_take=2, cma_gens=1, cma_pop=2, top=1, rep_seeds=1)
    T = {"fc": SCORE_FIT_FC(), "fcd": np.array([0.3, 0.4], np.float32)}
    res = F.search("twin", cfg, T, tmp_path, log=lambda s: None)
    assert res["evaluations"] == 2 + 2 + 1
    assert all(r["params"]["G"] <= F.G_LIVE_MAX for r in res["records"] if r["stage"] != "grid")
    assert res["best"] == res["replication"][0]["params"] and res["replication"][0]["n"] >= 2
    n_files = len(list((tmp_path / "evals").glob("*.npz")))
    again = F.search("twin", cfg, T, tmp_path, log=lambda s: None)           # resumes from the cache
    assert again["records"] == res["records"] and len(list((tmp_path / "evals").glob("*.npz"))) == n_files


def SCORE_FIT_FC():
    rng = np.random.default_rng(0)
    return rng.uniform(-0.2, 0.8, 214 * 213 // 2).astype(np.float32)
