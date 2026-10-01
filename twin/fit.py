"""Fit the twin model (twin/model.py) to the person's recorded resting-state fMRI, with a session-wise held-out test.

A digital twin model of one real person's brain structure and recorded activity (MyConnectome, OpenNeuro
ds000031, CC0 / public domain); not a mind, not conscious, not the person. Full write-up: docs/twin/fit.md.

Pipeline (each stage checkpoints to the cache directory, so an interrupted run resumes):

    python -m twin.fit all [--workers 3]          # split -> targets -> grids -> CMA-ES -> held-out -> outputs
    python -m twin.fit all --quick                # tiny version of the same pipeline (tests, smoke runs)
    python -m twin.fit split | targets            # print the split / the empirical reference numbers
    python -m twin.fit write                      # (re)write twin/params.json, web/twin_score.json, figures

Data. The 131 QC-kept runs of out/rest/ (process_rest.py: drop 5 volumes, linear detrend, 2nd-order Butterworth
band-pass 0.01-0.1 Hz with filtfilt, z-score; no nuisance or global-signal regression). The four multi-echo runs of
ses-2022 are stored as three files each (echo 1-3 of one acquisition); they are merged into one time series per
acquisition (mean of the z-scored echoes, z-scored again) so one acquisition counts once.

Split. Sessions (BIDS ses-*) sorted by scan date (sub-01_sessions.tsv) and assigned alternately to fit / held-out
("interleave"); robustness check: first half / second half of the sessions by date ("chronological").
Nothing from held-out sessions enters the targets, the search or any normalisation.

Targets and objective. FC = Fisher-z average of per-acquisition Pearson FC (214 x 214). FCD = correlations between
upper-triangle FC vectors of 60 s sliding windows (step ~6 s), only pairs of non-overlapping windows, pooled over
runs. Score = r(sim FC, emp FC) - KS(sim FCD, emp FCD) (equal weights). Simulated BOLD is sampled at TR 1.16 s (the
main protocol), cut into 518-volume "runs" and processed with exactly the same steps as the recorded runs.

Search: G, conduction velocity and noise of the twin (grid -> CMA-ES -> replication with new seeds), with G limited
to <= G_LIVE_MAX so that the sleep stages still behave in the live server (live_check). Baselines with the same
search: the same model on a shuffled connectome, and the old Stuart-Landau model (brain_sim.Brain) read out through
the same Balloon-Windkessel BOLD. Held-out evaluation with fixed parameters and fresh seeds.
"""
from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import argparse
import hashlib
import json
import math
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import signal, stats

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from twin.model import (Balloon, _DelayNet, balance, heun_step, load_connectome,  # noqa: E402
                        load_params, simulate_bold)

REST = ROOT / "out" / "rest"
CONNECTOME = ROOT / "out" / "connectome.npz"
CACHE = Path(os.environ.get("SUB01_FITCACHE", "/home/user/fitcache"))
DATES = HERE / "data" / "session_dates.json"
PARAMS_OUT = HERE / "params.json"
SCORE_OUT = ROOT / "web" / "twin_score.json"
FIGS = ROOT / "docs" / "twin"

DROP = 5            # volumes dropped at the start of every run (scanner warm-up in process_rest.py)
SIM_TR = 1.16       # s, TR of the main protocol (ses-013 ... ses-104, Siemens Skyra, multiband 4)
SEG_VOLS = 513      # volumes kept per main-protocol run (518 acquired - 5 dropped)
WINDOW_S = 60.0     # FCD window (s)
STEP_S = 6.0        # FCD window step (s)
BURN = 20.0         # s of simulation discarded before the first volume (hemodynamic transient)
NOTE = "digital twin model of one real person's brain structure and recorded activity; not a mind, not the person"


# =============================================================================================================
# data, split
# =============================================================================================================
def _session(name):
    return re.search(r"ses-([^_]+)", name).group(1)


def _acq(name):
    return re.sub(r"_echo-\d+", "", name)


def kept_runs(rest=REST):
    """Names of the QC-kept runs (out/rest/qc.json kept = true) that exist in out/rest/."""
    qc = json.loads((Path(rest) / "qc.json").read_text())
    return sorted(k for k, v in qc.items() if v.get("kept") and (Path(rest) / f"{k}.npz").exists())


def session_dates():
    return json.loads(DATES.read_text())["dates"]


def sessions_by_date(runs):
    """Sessions of the given runs, sorted by scan date (then by name)."""
    d = session_dates()
    ses = sorted({_session(r) for r in runs}, key=lambda s: (d.get(s, "9999"), s))
    missing = [s for s in ses if s not in d]
    if missing:
        raise ValueError(f"no scan date for sessions {missing}")
    return ses


def split(runs=None, rule="interleave"):
    """Deterministic session-wise split -> {"fit": [runs], "heldout": [runs], "fit_sessions", "heldout_sessions"}.

    interleave: sessions sorted by date, even positions -> fit, odd -> held-out (both halves span all dates).
    chronological: first half of the sessions by date -> fit, second half -> held-out."""
    runs = kept_runs() if runs is None else list(runs)
    ses = sessions_by_date(runs)
    if rule == "interleave":
        fit_s = ses[0::2]
    elif rule == "chronological":
        fit_s = ses[:(len(ses) + 1) // 2]
    else:
        raise ValueError(rule)
    fit_s = set(fit_s)
    held_s = [s for s in ses if s not in fit_s]
    return {"rule": rule,
            "fit": [r for r in runs if _session(r) in fit_s],
            "heldout": [r for r in runs if _session(r) not in fit_s],
            "fit_sessions": [s for s in ses if s in fit_s], "heldout_sessions": held_s}


def load_acquisitions(runs, rest=REST):
    """Time series per acquisition: [{"acq", "session", "tr", "ts" (T, n) float64, "files"}]; echoes merged."""
    groups = defaultdict(list)
    for r in runs:
        groups[_acq(r)].append(r)
    out = []
    for acq, files in sorted(groups.items()):
        tss, trs = [], []
        for f in sorted(files):
            z = np.load(Path(rest) / f"{f}.npz")
            tss.append(z["ts"].astype(np.float64))
            trs.append(float(z["tr"]))
        assert len(set(trs)) == 1 and len({t.shape for t in tss}) == 1, acq
        ts = np.mean(tss, 0)
        if len(tss) > 1:                                   # multi-echo: mean of z-scored echoes, z-scored again
            ts = (ts - ts.mean(0)) / (ts.std(0) + 1e-12)
        out.append({"acq": acq, "session": _session(acq), "tr": trs[0], "ts": ts, "files": sorted(files)})
    return out


# =============================================================================================================
# processing and metrics (identical for recorded and simulated BOLD)
# =============================================================================================================
def preprocess(x, tr, drop=DROP):
    """The process_rest.py steps after region averaging: drop warm-up volumes, linear detrend, Butterworth order-2
    band-pass 0.01-0.1 Hz (filtfilt, b/a form), z-score per region. x: (T, n)."""
    x = np.asarray(x, np.float64)[drop:]
    x = signal.detrend(x, axis=0)
    b, a = signal.butter(2, [0.01 * 2 * tr, min(0.1 * 2 * tr, 0.99)], btype="band")
    x = signal.filtfilt(b, a, x, axis=0)
    return (x - x.mean(0)) / (x.std(0) + 1e-6)


def triu(n):
    return np.triu_indices(n, 1)


def fc_matrix(ts):
    return np.corrcoef(np.asarray(ts, np.float64).T)


def fisher_mean(fcs):
    """Fisher-z average of correlation matrices / vectors (r clipped to +-0.999999 before arctanh)."""
    z = np.mean([np.arctanh(np.clip(f, -0.999999, 0.999999)) for f in fcs], 0)
    return np.tanh(z)


def fcd_values(ts, tr, window_s=WINDOW_S, step_s=STEP_S):
    """FCD: Pearson r between the upper-triangle FC vectors of sliding windows (window_s long, step_s apart).
    Only pairs of windows that do not overlap are kept (overlapping windows share samples). Returns 1-D array."""
    ts = np.asarray(ts, np.float64)
    T, n = ts.shape
    w = int(round(window_s / tr))
    s = max(1, int(round(step_s / tr)))
    starts = np.arange(0, T - w + 1, s)
    if len(starts) < 2:
        return np.zeros(0)
    win = np.stack([ts[a:a + w] for a in starts])                 # (nw, w, n)
    win = win - win.mean(1, keepdims=True)
    win /= np.sqrt((win ** 2).sum(1, keepdims=True)) + 1e-12
    iu = triu(n)
    vec = np.matmul(win.transpose(0, 2, 1), win)[:, iu[0], iu[1]]  # window FC, (nw, n(n-1)/2)
    m = np.corrcoef(vec)
    i, j = np.triu_indices(len(starts), 1)
    keep = (starts[j] - starts[i]) >= w
    return m[i[keep], j[keep]]


def ks(a, b):
    """Two-sample Kolmogorov-Smirnov distance (0 = same distribution, 1 = disjoint)."""
    if len(a) == 0 or len(b) == 0:
        return 1.0
    return float(stats.ks_2samp(a, b).statistic)


def pearson(a, b):
    return float(np.corrcoef(a, b)[0, 1])


def features(series, tr):
    """FC upper triangle (Fisher mean), pooled FCD values and per-run FC vectors for preprocessed series."""
    n = series[0].shape[1]
    iu = triu(n)
    fcs = [fc_matrix(x)[iu] for x in series]
    fcd = np.concatenate([fcd_values(x, tr) for x in series])
    return {"fc": fisher_mean(fcs).astype(np.float32), "fcd": fcd.astype(np.float32),
            "run_fc": np.array(fcs, np.float32)}


def empirical(acqs):
    """Targets from recorded acquisitions (already preprocessed by process_rest.py)."""
    n = acqs[0]["ts"].shape[1]
    iu = triu(n)
    fcs = [fc_matrix(a["ts"])[iu] for a in acqs]
    fcd = np.concatenate([fcd_values(a["ts"], a["tr"]) for a in acqs])
    return {"fc": fisher_mean(fcs).astype(np.float32), "fcd": fcd.astype(np.float32),
            "run_fc": np.array(fcs, np.float32), "acq": [a["acq"] for a in acqs],
            "tr": [a["tr"] for a in acqs], "sessions": sorted({a["session"] for a in acqs})}


def sim_series(bold, tr=SIM_TR, seg_vols=SEG_VOLS, drop=DROP):
    """Cut one simulated BOLD record (T, n) into run-length segments (drop + seg_vols volumes each) and preprocess
    each segment exactly like a recorded run."""
    L = seg_vols + drop
    k = bold.shape[0] // L
    return [preprocess(bold[i * L:(i + 1) * L], tr, drop) for i in range(k)]


def score(feat, target):
    """r(FC), KS(FCD), objective r - KS, and the mean FC levels."""
    r = pearson(feat["fc"], target["fc"])
    d = ks(feat["fcd"], target["fcd"])
    return {"fc_r": r, "fcd_ks": d, "score": r - d, "mean_fc": float(np.mean(feat["fc"])),
            "mean_fc_target": float(np.mean(target["fc"]))}


# =============================================================================================================
# connectomes for the baselines
# =============================================================================================================
def shuffled_connectome(seed=0, path=CONNECTOME, sc_power=1.0):
    """Null connectome: the (streamline count, fibre length) pairs of all region pairs i < j are permuted jointly
    over the pairs (zero-count pairs included), then mirrored. Same weight and length distributions, same density,
    random wiring. Returns model-space W (same degree normalisation as load_connectome) and lengths L (mm)."""
    z = np.load(path, allow_pickle=True)
    C = z["weights"].astype(float)
    np.fill_diagonal(C, 0.0)
    L = z["lengths"].astype(float)
    n = len(C)
    iu = triu(n)
    perm = np.random.default_rng(seed).permutation(len(iu[0]))
    Cs, Ls = np.zeros_like(C), np.zeros_like(L)
    Cs[iu] = C[iu][perm]
    Ls[iu] = L[iu][perm]
    Cs, Ls = Cs + Cs.T, Ls + Ls.T
    Cs = Cs ** sc_power
    s = Cs.sum(1)
    s = np.where(s > 0, s, 1.0)
    W = Cs / np.sqrt(np.outer(s, s))
    Ls = np.where(Ls > 0, Ls, np.nanmean(L[L > 0]))
    return W, Ls


def old_model_weights(path=CONNECTOME):
    """brain_sim.Brain weights: log1p(streamline counts), mean in-strength normalised to 1 (all regions have fibres,
    so none is dropped). Lengths in mm."""
    z = np.load(path, allow_pickle=True)
    W = np.log1p(z["weights"].astype(float))
    np.fill_diagonal(W, 0.0)
    assert (W.sum(1) > 0).all()
    W /= W.sum(1).mean()
    L = z["lengths"].astype(float)
    L = np.where(L > 0, L, np.nanmean(L[L > 0]))
    return W, L


# =============================================================================================================
# simulators
# =============================================================================================================
def simulate_twin(params_list, seconds, seed, W=None, L=None, tr=SIM_TR, burn=BURN):
    """twin.model.simulate_bold (batched Wilson-Cowan + Balloon) at awake rest. W: model-space weights (default
    the person's connectome). With other fibre lengths L (shuffled connectome) the pair (W, L) is written once to a
    private connectome file in the cache, because simulate_bold reads the lengths from a file."""
    if L is None:
        return simulate_bold(params_list, seconds, tr, seed=seed, W=W, burn=burn, params_path=None)
    # shuffled lengths: write a private connectome file once per (W, L) and point simulate_bold at it
    z = np.load(CONNECTOME, allow_pickle=True)
    key = hashlib.sha1(np.ascontiguousarray(W).tobytes() + np.ascontiguousarray(L).tobytes()).hexdigest()[:16]
    f = CACHE / "tmp" / f"conn_{key}.npz"
    if not f.exists():
        f.parent.mkdir(parents=True, exist_ok=True)
        tmp = f.with_suffix(".part.npz")
        np.savez(tmp, weights=W, lengths=L, names=z["names"], centroids=z["centroids"])
        os.replace(tmp, f)
    p0 = load_params(None, params_list[0])
    assert p0["sc_power"] == 1.0
    return simulate_bold(params_list, seconds, tr, seed=seed, W=None, burn=burn, path=f, params_path=None)


def isp_refine_batch(params_list, seconds=60.0, seed=0, W=None, L=None):
    """twin.model.isp_refine for B parameter sets at once (same rule, schedule and averaging): inhibitory synaptic
    plasticity dc_IE/dt = -eta I (E - rho) (Vogels et al. 2011) simulated at awake rest from the analytic balance,
    eta for the first half and eta/4 for the second, c_IE averaged over the last quarter. Returns (B, n).

    The fit uses it to put every region's time-averaged rate at rho in the noisy, oscillating network for each
    candidate (G, velocity, noise, isp_frac) - the analytic fixed point alone leaves the network far from rho
    when isp_frac < 1. The result is a derived quantity (homeostasis), not a free parameter."""
    ps = [load_params(None, q) for q in params_list]
    p = ps[0]
    B = len(ps)
    W0, L0, names, _ = load_connectome(CONNECTOME, p["sc_power"])
    W = W0 if W is None else np.asarray(W, float)
    L = L0 if L is None else np.asarray(L, float)
    n = len(names)
    dt, rho = float(p["dt"]), p["rho"]
    bal = [balance(q, W, q["G"], np.zeros(n)) for q in ps]
    cie = np.stack([b[0] for b in bal])
    base = p["P"] + np.stack([b[2] for b in bal])
    G = np.array([q["G"] for q in ps])[:, None]
    sq = np.array([q["noise"] for q in ps])[:, None] * math.sqrt(dt)
    eta = np.array([q["isp_eta"] for q in ps])[:, None]
    rng = np.random.default_rng(seed)
    E = rho + 0.01 * rng.standard_normal((B, n))
    I = np.full((B, n), bal[0][1])
    A = np.full((B, n), rho)
    net = _DelayNet(W, L, [q["velocity"] for q in ps], dt, B, init=E)
    steps = int(round(seconds / dt))
    avg = np.zeros((B, n))
    k_avg = 0
    for it in range(steps):
        if it % 1000 == 0:
            noise = rng.standard_normal((1000, B, n))
        E, I, A = heun_step(E, I, A, base + G * net.delayed_input(), sq * noise[it % 1000], p["beta"], cie,
                            p["b_wake"], p, dt)
        net.push(E)
        e = eta * (1.0 if it < steps // 2 else 0.25)
        cie = np.minimum(cie - dt * e * I * (E - rho), 0.0)
        if it >= 3 * steps // 4:
            avg += cie
            k_avg += 1
    return avg / max(k_avg, 1)


def live_check(params, seed=0, settle=3.0, seconds=6.0, stim_seconds=20.0):
    """Does a parameter set keep the live behaviour sane? TwinBrain with these parameters is driven through the sleep
    engine's stages (as live_server does) and through heavy random stimulation (as tests/test_twin_model.py does).
    Returns per-stage statistics, the recovery after stimulation and an overall "ok" flag:
    AWAKE and REM: mean E in [0.03, 0.35] and < 5 % of samples in an up state (E > 0.5);
    NREM_DEEP: slow (< 4 Hz) power > 50 % (slow oscillation kept); recovery: mean E back within 0.03 of rest."""
    import sleep
    from twin.model import TwinBrain
    stages = {"AWAKE": sleep.AWAKE, "NREM_LIGHT": sleep.NREM_LIGHT, "NREM_DEEP": sleep.NREM_DEEP, "REM": sleep.REM}

    def apply(b, name):
        q = stages[name]
        b.set_rhythm(q["f_hz"], q["coupling"], q["noise"])
        b.a = q["a"]

    out = {}
    for name in stages:
        b = TwinBrain(params=params, params_path=None, seed=seed)
        apply(b, name)
        b.run(settle, every=50)
        E = np.array([b.step(5) is not None and b.E.copy() for _ in range(int(seconds / 0.005))])
        f = np.fft.rfftfreq(len(E), 0.005)
        P = (np.abs(np.fft.rfft(E - E.mean(0), axis=0)) ** 2).mean(1)
        sel = f > 0.2
        out[name] = {"mean_E": round(float(E.mean()), 3), "up_frac": round(float((E > 0.5).mean()), 3),
                     "slow_frac": round(float(P[sel & (f < 4)].sum() / max(P[sel].sum(), 1e-30)), 2)}
    b = TwinBrain(params=params, params_path=None, seed=seed + 1)
    rng = np.random.default_rng(seed)
    rest0 = np.mean([b.step(10) is not None and b.E.mean() for _ in range(300)])
    groups = list(b.group_idx)
    for k in range(int(stim_seconds / 0.1)):
        for g in rng.choice(groups, 2):
            b.stimulate(g, float(rng.uniform(0, 15)))
        b.drive = 1.6 * np.clip(rng.standard_normal(b.n), -2, 3)
        b.step(100)
    peak = float(b.E.mean())
    b.drive[:] = 0.0
    b.run(10.0, every=100)
    after = float(np.mean([b.step(10) is not None and b.E.mean() for _ in range(300)]))
    out["recovery"] = {"rest": round(float(rest0), 3), "stimulated": round(peak, 3), "after_10s": round(after, 3)}
    ok = all(0.03 <= out[s]["mean_E"] <= 0.35 and out[s]["up_frac"] < 0.05 for s in ("AWAKE", "REM"))
    ok &= out["NREM_DEEP"]["slow_frac"] > 0.5 and abs(after - rest0) < 0.03
    out["ok"] = bool(ok)
    return out


class SharedDelay:
    """Delayed network input when all columns (parameter sets) share the same delays: buffer (2H, n, cols), each
    sample written twice so the last H samples are one contiguous view, and one sparse (n x H n) by dense
    (H n x cols) product per step. Same indexing as twin.model._DelayNet, but the columns ride along contiguously,
    which is several times faster than a block-diagonal mat-vec for B sets."""

    def __init__(self, W, L, velocity, dt, cols, init=0.0):
        from scipy import sparse
        n = W.shape[0]
        d = np.maximum(np.round(L / 1000.0 / velocity / dt).astype(int), 1)
        self.H = H = int(d[W != 0].max()) + 1
        i, j = np.nonzero(W)
        self.M = sparse.csr_matrix((W[i, j], (i, (H - 1 - d[i, j]) * n + j)), shape=(n, H * n))
        self.n, self.cols = n, cols
        self.buf = np.empty((2 * H, n, cols))
        self.buf[:] = init
        self.pos = 0

    def delayed_input(self):
        s = self.pos + 1
        return self.M @ self.buf[s:s + self.H].reshape(self.H * self.n, self.cols)

    def push(self, x):
        self.pos = (self.pos + 1) % self.H
        self.buf[self.pos] = x
        self.buf[self.pos + self.H] = x


SL_DEFAULTS = dict(g=5.0, noise=0.5, f_hz=10.0, a=-5.0, velocity=6.0, dt=1e-3, bold_gain=0.25)


def simulate_sl_bold(params_list, seconds, tr=SIM_TR, seed=0, burn=BURN, W=None, L=None, return_amp=False):
    """The OLD model (brain_sim.Brain: delayed Stuart-Landau oscillators, same equations and integrator) for B
    parameter sets at once (they must share one conduction velocity), read out through the same
    Balloon-Windkessel model as the twin. Returns BOLD (B, T, n) sampled every tr after the burn-in.

    Brain.step: z <- z exp((a + i w - |z|^2) dt) + dt g (sum_j W_ij z_j(t - d_ij) - s_i z) + noise sqrt(dt) (xi + i eta),
    w_i = 2 pi f (1 + 0.05 N(0,1)) (brain_sim draws the spread with seed 0), W = log1p(counts) / mean strength.
    Delays of 0 steps in brain_sim (fibres < 3 mm at 6 m/s) become 1 step here.
    Neural input to the balloon: u = bold_gain (|z| / <|z|> - 1), the fractional change of the oscillation
    amplitude, with <|z|> the per-region mean amplitude over the first half of the burn-in (the old model has no
    firing rate); the balloon runs from then on, so it has settled before the first volume."""
    ps = [{**SL_DEFAULTS, **q} for q in params_list]
    B = len(ps)
    vel = {float(q["velocity"]) for q in ps}
    assert len(vel) == 1, "simulate_sl_bold: one velocity per batch"
    if W is None:
        W, L = old_model_weights()
    n = W.shape[0]
    dt = ps[0]["dt"]
    rng = np.random.default_rng(seed)
    df = np.random.default_rng(0).normal(0, 0.05, n)
    om = np.stack([2 * np.pi * q["f_hz"] * (1 + df) for q in ps], 1)          # state layout (n, B)
    g = np.array([q["g"] for q in ps])[None, :]
    a = np.array([q["a"] for q in ps])[None, :]
    sq = np.array([q["noise"] for q in ps])[None, :] * math.sqrt(dt)
    s = W.sum(1)[:, None]
    z = rng.normal(0, 0.1, (n, B)) + 1j * rng.normal(0, 0.1, (n, B))
    net = SharedDelay(W, L, vel.pop(), dt, 2 * B, init=np.concatenate([z.real, z.imag], 1))
    hemo = Balloon((n, B))
    m = 10
    step_tr = tr / dt
    n_burn = int(round(burn / dt))
    n_ref = max(1, n_burn // 2)                                  # amplitude reference: first half of the burn-in
    assert n_burn >= 2, "burn must be > 0 for the old model (amplitude reference)"
    T = int(seconds // tr)
    n_total = n_burn + int(math.ceil(T * step_tr))
    out = np.empty((B, T, n), np.float32)
    acc = np.zeros((n, B))
    amp_mean = np.zeros((n, B))
    amp_post = np.zeros((n, B))
    ref = None
    k_out = 0
    lin = (a + 1j * om) * dt
    chunk = 500
    for c0 in range(0, n_total, chunk):
        nn = min(chunk, n_total - c0)
        noise = rng.standard_normal((nn, 2, n, B))
        for k in range(nn):
            it = c0 + k
            d = net.delayed_input()
            zd = d[:, :B] + 1j * d[:, B:]
            z = z * np.exp(lin - (z.real ** 2 + z.imag ** 2) * dt) + dt * g * (zd - s * z) \
                + sq * (noise[k, 0] + 1j * noise[k, 1])
            net.push(np.concatenate([z.real, z.imag], 1))
            amp = np.abs(z)
            if it < n_ref:
                amp_mean += amp
            elif it == n_ref:
                ref = amp_mean / n_ref
            if it >= n_burn:
                amp_post += amp
            acc += amp
            if (it + 1) % m == 0:
                if ref is not None:
                    hemo.step(ps[0]["bold_gain"] * (acc / (m * ref) - 1.0), m * dt)
                acc[:] = 0.0
            if it >= n_burn and k_out < T and (it + 1 - n_burn) >= round((k_out + 1) * step_tr):
                out[:, k_out] = hemo.bold().T
                k_out += 1
    if return_amp:
        return out, (amp_post / max(1, n_total - n_burn)).T
    return out


# =============================================================================================================
# search
# =============================================================================================================
# Largest global coupling for which the fitted model still behaves in the live server: the sleep engine multiplies
# G by 2 (light NREM) and 3 (deep NREM) while the inhibitory balance stays at the resting value, and for G >= 4
# deep NREM saturates (mean E 0.97-1.0, no slow oscillation; live_check). G = 3.5 passes (deep NREM up/down states,
# slow power 93 %), so the twin's search box ends there. The grid still covers larger G to show what is lost.
G_LIVE_MAX = 3.5
# log-uniform search boxes (CMA-ES works on log(x) scaled to [0, 1])
SPACES = {
    "twin": {"G": (0.5, G_LIVE_MAX), "velocity": (2.0, 20.0), "noise": (0.01, 0.3)},
    "shuffled": {"G": (0.5, 20.0), "velocity": (2.0, 20.0), "noise": (0.01, 0.3)},
    "old": {"g": (0.5, 60.0), "noise": (0.1, 2.0)},              # velocity of the old model: grid only
}
GRIDS = {
    "twin": {"G": [1.0, 2.0, 3.5, 6.0, 10.0, 16.0], "velocity": [3.0, 8.0], "noise": [0.02, 0.06, 0.15]},
    "shuffled": {"G": [1.0, 2.0, 3.5, 6.0, 10.0, 16.0], "velocity": [3.0, 8.0], "noise": [0.02, 0.06, 0.15]},
    "old": {"g": [1.0, 2.5, 5.0, 10.0, 20.0, 40.0], "velocity": [3.0, 8.0], "noise": [0.25, 0.5, 1.0]},
}
FULL = dict(name="full", eval_seg=2, seg_vols=SEG_VOLS, cma_gens=4, cma_pop=12, top=4, rep_seeds=3,
            final_reps=5, final_seg=6, runs=None, grid_take=None)
QUICK = dict(name="quick", eval_seg=1, seg_vols=120, cma_gens=1, cma_pop=2, top=1, rep_seeds=1,
             final_reps=2, final_seg=1, runs=10, grid_take=2)
SEEDS = dict(grid=1, cma=100, rep=1000, final=5000, chrono=7000)


def _grid_points(model, take=None):
    g = GRIDS[model]
    keys = list(g)
    pts = [dict(zip(keys, v)) for v in np.array(np.meshgrid(*[g[k] for k in keys], indexing="ij")).reshape(len(keys), -1).T]
    pts = [{k: float(v) for k, v in p.items()} for p in pts]
    if take:                                             # quick mode: a few points spread over the grid
        pts = [pts[i] for i in np.linspace(0, len(pts) - 1, take).round().astype(int)]
    return pts


def _encode(model, p):
    return np.array([(math.log(p[k]) - math.log(lo)) / (math.log(hi) - math.log(lo))
                     for k, (lo, hi) in SPACES[model].items()])


def _decode(model, x, fixed=None):
    out = {k: float(round(math.exp(math.log(lo) + float(np.clip(v, 0, 1)) * (math.log(hi) - math.log(lo))), 5))
           for v, (k, (lo, hi)) in zip(x, SPACES[model].items())}
    return {**out, **(fixed or {})}


class EvalCache:
    """Simulated features per (model, parameters, length, seed, shuffle); one small .npz per evaluation."""

    def __init__(self, root):
        self.root = Path(root) / "evals"
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def key(model, params, nseg, seed, slot, shuffle, seg_vols):
        p = {k: (round(float(v), 6) if np.isscalar(v) else v) for k, v in sorted(params.items())}
        s = json.dumps([model, p, nseg, seed, slot, shuffle, seg_vols], sort_keys=True)
        return hashlib.sha1(s.encode()).hexdigest()[:20]

    def get(self, k):
        f = self.root / f"{k}.npz"
        if not f.exists():
            return None
        z = np.load(f)
        return {"fc": z["fc"], "fcd": z["fcd"].astype(np.float32), "run_fc": z["run_fc"].astype(np.float32)}

    def put(self, k, feat):
        f = self.root / f"{k}.npz"
        tmp = self.root / f"{k}.part.npz"
        np.savez(tmp, fc=feat["fc"], fcd=feat["fcd"].astype(np.float16), run_fc=feat["run_fc"].astype(np.float16))
        os.replace(tmp, f)


def _simulate(model, plist, nseg, seed, seg_vols, shuffle=0):
    secs = (nseg * (seg_vols + DROP) + 0.5) * SIM_TR
    if model == "twin":
        return simulate_twin(plist, secs, seed)
    if model == "shuffled":
        W, L = shuffled_connectome(shuffle)
        return simulate_twin(plist, secs, seed, W=W, L=L)
    if model == "old":
        out = np.empty((len(plist), int(secs // SIM_TR), 214), np.float32)
        for v in sorted({p["velocity"] for p in plist}):     # one velocity per batch (shared delays)
            idx = [i for i, p in enumerate(plist) if p["velocity"] == v]
            out[idx] = simulate_sl_bold([plist[i] for i in idx], secs, SIM_TR, seed=seed)
        return out
    raise ValueError(model)


def evaluate(model, plist, cfg, cache, seed, nseg=None, shuffle=0):
    """Features for a batch of parameter sets (one simulate call for the ones not cached). Slot i of a batch gets
    its own noise realisation, so the slot index is part of the cache key."""
    nseg = nseg or cfg["eval_seg"]
    keys = [cache.key(model, p, nseg, seed, i, shuffle, cfg["seg_vols"]) for i, p in enumerate(plist)]
    feats = [cache.get(k) for k in keys]
    todo = [i for i, f in enumerate(feats) if f is None]
    if todo:
        bold = _simulate(model, [plist[i] for i in todo], nseg, seed, cfg["seg_vols"], shuffle)
        for j, i in enumerate(todo):
            feats[i] = features(sim_series(bold[j], seg_vols=cfg["seg_vols"]), SIM_TR)
            cache.put(keys[i], feats[i])
    return feats


def search(model, cfg, target, cache_dir, log=print):
    """Coarse grid -> CMA-ES (Hansen 2016, pip 'cma') -> replication of the best candidates with new seeds.
    Objective: maximise score = r(FC) - KS(FCD) against the fit-half targets only. Checkpointed via the cache."""
    import cma
    cache = EvalCache(cache_dir)
    recs = []

    def run(plist, seed, stage):
        t0 = time.time()
        feats = evaluate(model, plist, cfg, cache, seed)
        out = []
        for i, (p, f) in enumerate(zip(plist, feats)):
            sc = score(f, target)
            out.append({"stage": stage, "seed": seed, "params": p, "key": cache.key(model, p, cfg["eval_seg"], seed, i, 0,
                                                                                       cfg["seg_vols"]),
                        **{k: round(v, 4) for k, v in sc.items()}})
        recs.extend(out)
        best = max(out, key=lambda r: r["score"])
        log(f"[{model}] {stage}: {len(plist)} sets, {time.time() - t0:.0f} s, best score {best['score']:.3f} "
            f"(r {best['fc_r']:.3f}, KS {best['fcd_ks']:.3f}) at {best['params']}")
        return out

    def inside(p):
        return all(lo - 1e-9 <= p[k] <= hi + 1e-9 for k, (lo, hi) in SPACES[model].items())

    grid = _grid_points(model, cfg["grid_take"])
    run(grid, SEEDS["grid"], "grid")
    best = max([r for r in recs if inside(r["params"])], key=lambda r: r["score"])
    fixed = {"velocity": best["params"]["velocity"]} if model == "old" else None
    es = cma.CMAEvolutionStrategy(list(_encode(model, best["params"])), 0.2,
                                  {"bounds": [0, 1], "popsize": cfg["cma_pop"], "seed": 7, "verbose": -9})
    for gen in range(cfg["cma_gens"]):
        xs = es.ask()
        plist = [_decode(model, x, fixed) for x in xs]
        out = run(plist, SEEDS["cma"] + gen, f"cma{gen}")
        es.tell(xs, [-r["score"] for r in out])
    # replication: the best distinct candidates with fresh seeds (reduces the winner's curse of a noisy objective)
    seen, top = set(), []
    for r in sorted([r for r in recs if inside(r["params"])], key=lambda r: -r["score"]):
        k = json.dumps(r["params"], sort_keys=True)
        if k not in seen:
            seen.add(k)
            top.append(r["params"])
        if len(top) == cfg["top"]:
            break
    for s in range(cfg["rep_seeds"]):
        run(top, SEEDS["rep"] + s, f"rep{s}")
    reps = []
    for p in top:
        rr = [r for r in recs if r["params"] == p]
        reps.append({"params": p, "n": len(rr), "score_mean": round(float(np.mean([r["score"] for r in rr])), 4),
                     "score_sd": round(float(np.std([r["score"] for r in rr], ddof=1)) if len(rr) > 1 else 0.0, 4),
                     "fc_r_mean": round(float(np.mean([r["fc_r"] for r in rr])), 4),
                     "fc_r_sd": round(float(np.std([r["fc_r"] for r in rr], ddof=1)) if len(rr) > 1 else 0.0, 4),
                     "fcd_ks_mean": round(float(np.mean([r["fcd_ks"] for r in rr])), 4)})
    reps.sort(key=lambda r: -r["score_mean"])
    return {"model": model, "records": recs, "replication": reps, "best": reps[0]["params"],
            "evaluations": len(recs), "sim_seconds": round(len(recs) * cfg["eval_seg"] * (cfg["seg_vols"] + DROP) * SIM_TR + len(recs) * BURN)}


def _search_job(args):
    model, cfg, target, cache_dir = args
    f = Path(cache_dir) / f"search_{model}.json"
    if f.exists():
        return json.loads(f.read_text())
    res = search(model, cfg, target, cache_dir, log=lambda s: print(s, flush=True))
    f.write_text(json.dumps(res))
    return res


# =============================================================================================================
# targets, held-out evaluation, orchestration
# =============================================================================================================
def _subset_runs(runs, n):
    """Quick mode: the runs of the first n sessions by date (still split by session)."""
    ses = sessions_by_date(runs)[:n]
    return [r for r in runs if _session(r) in ses]


def build_targets(cfg, cache_dir, rule):
    """Split + empirical targets for both halves (cached). FC from all acquisitions of a half; FCD from the
    main-protocol acquisitions (TR 1.16 s, 513 volumes) only, because the FCD distribution depends on TR, run length
    and scanner (see docs) and the simulation is sampled like the main protocol."""
    import pickle
    f = Path(cache_dir) / f"targets_{rule}.pkl"
    if f.exists():
        return pickle.loads(f.read_bytes())
    runs = kept_runs()
    if cfg["runs"]:
        runs = _subset_runs(runs, cfg["runs"])
    sp = split(runs, rule)
    out = {"split": sp}
    for half in ("fit", "heldout"):
        acqs = load_acquisitions(sp[half])
        e = empirical(acqs)
        main = [a for a in acqs if a["tr"] == SIM_TR and len(a["ts"]) == SEG_VOLS]
        e["fcd_main"] = empirical(main)["fcd"] if main else e["fcd"]
        e["n_main"] = len(main)
        e["n_runs"] = len(sp[half])
        out[half] = e
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    f.write_bytes(pickle.dumps(out))
    return out


def target_of(e):
    return {"fc": e["fc"], "fcd": e["fcd_main"]}


def references(T):
    """Reference numbers on the held-out half: direct SC-FC correlations and the test-retest ceiling."""
    z = np.load(CONNECTOME, allow_pickle=True)
    C = z["weights"].astype(float)
    iu = triu(len(C))
    c = C[iu]
    eh, ef = T["heldout"], T["fit"]
    rr = np.corrcoef(eh["run_fc"].astype(np.float64))
    return {"sc_fc_direct_r": round(pearson(np.log1p(c), eh["fc"]), 3),
            "sc_fc_direct_r_connected_pairs_log": round(pearson(np.log(c[c > 0]), eh["fc"][c > 0]), 3),
            "test_retest_ceiling_r": round(pearson(ef["fc"], eh["fc"]), 3),
            "run_to_run_r_mean": round(float(rr[np.triu_indices(len(rr), 1)].mean()), 3),
            "fit_mean_vs_heldout_run_r_mean": round(float(np.mean([pearson(ef["fc"], x) for x in eh["run_fc"]])), 3),
            "fcd_ks_fit_vs_heldout": round(ks(ef["fcd_main"], eh["fcd_main"]), 3),
            "mean_fc_fit": round(float(ef["fc"].mean()), 3), "mean_fc_heldout": round(float(eh["fc"].mean()), 3)}


def _final_job(args):
    model, params, cfg, cache_dir, seed, shuffle, nrep = args
    return evaluate(model, [params] * nrep, cfg, EvalCache(cache_dir), seed, nseg=cfg["final_seg"], shuffle=shuffle)


def summarise(feats, target, fit_target=None, rng_seed=0):
    """Held-out (or fit) scores of one model: per-replicate FC r and FCD KS (mean, sd), pooled-FC r, the r against
    single runs, and r as a function of the simulated length."""
    sc = [score(f, target) for f in feats]
    seg_fc = np.concatenate([f["run_fc"] for f in feats]).astype(np.float64)
    pooled = fisher_mean(seg_fc)
    out = {"fc_r": float(np.mean([s["fc_r"] for s in sc])),
           "fc_r_sd": float(np.std([s["fc_r"] for s in sc], ddof=1)) if len(sc) > 1 else 0.0,
           "fcd_ks": float(np.mean([s["fcd_ks"] for s in sc])),
           "fcd_ks_sd": float(np.std([s["fcd_ks"] for s in sc], ddof=1)) if len(sc) > 1 else 0.0,
           "score": float(np.mean([s["score"] for s in sc])),
           "mean_fc": float(np.mean([s["mean_fc"] for s in sc])),
           "fc_r_pooled": pearson(pooled, target["fc"]),
           "replicates": len(feats), "segments_per_replicate": int(len(seg_fc) // max(1, len(feats)))}
    if fit_target is not None:
        out["fit"] = {"fc_r": float(np.mean([pearson(f["fc"], fit_target["fc"]) for f in feats])),
                      "fcd_ks": float(np.mean([ks(f["fcd"], fit_target["fcd"]) for f in feats]))}
    rng = np.random.default_rng(rng_seed)
    curve = {}
    for k in sorted({1, 2, 4, 8, 16, len(seg_fc)}):
        if k <= len(seg_fc):
            draws = [pearson(fisher_mean(seg_fc[rng.choice(len(seg_fc), k, replace=False)]), target["fc"])
                     for _ in range(10 if k < len(seg_fc) else 1)]
            curve[str(k)] = round(float(np.mean(draws)), 3)
    out["fc_r_vs_simulated_runs"] = curve
    return out, pooled, np.concatenate([f["fcd"] for f in feats])


def per_run(pooled, seg_fc, e):
    """Held-out per-run comparison: pooled simulated FC vs each single recorded run, one simulated 10-min run vs one
    recorded run, and recorded run vs recorded run."""
    runs = e["run_fc"].astype(np.float64)
    sim_vs_run = np.array([pearson(pooled, x) for x in runs])
    seg_vs_run = np.array([[pearson(s, x) for x in runs] for s in seg_fc[:6]])
    rr = np.corrcoef(runs)[np.triu_indices(len(runs), 1)]
    q = lambda a: {"mean": round(float(np.mean(a)), 3), "sd": round(float(np.std(a)), 3),
                   "p10": round(float(np.percentile(a, 10)), 3), "p90": round(float(np.percentile(a, 90)), 3)}
    return {"sim_pooled_vs_single_run": q(sim_vs_run), "sim_run_vs_single_run": q(seg_vs_run.ravel()),
            "run_to_run": q(rr), "n_runs": len(runs)}, sim_vs_run, rr


def choose_twin(res, cfg, log=print):
    """Best replicated twin candidate that also keeps the live behaviour sane (live_check)."""
    checks = []
    for cand in res["replication"]:
        if not cfg.get("live_check", True):
            return cand, checks
        lc = live_check(cand["params"])
        checks.append({"params": cand["params"], "ok": lc["ok"], "detail": lc})
        log(f"[twin] live check {cand['params']}: ok={lc['ok']}")
        if lc["ok"]:
            return cand, checks
    return None, checks


def realtime_cost(params_path=PARAMS_OUT, seconds=5.0):
    """Wall seconds per simulated second for TwinBrain loaded from params.json, driven like live_server
    (step(5) x 10 per 50 ms tick + state(), stimuli every 0.5 s), on the current thread settings."""
    from twin.model import TwinBrain
    b = TwinBrain(params_path=params_path, seed=1)
    b.run(1.0, every=50)
    t0 = time.perf_counter()
    for tick in range(int(seconds / 0.05)):
        b.drive = np.zeros(b.n)
        if tick % 10 == 0:
            b.stimulate("reward", 6.0)
        for _ in range(10):
            b.step(5)
        b.state()
    return (time.perf_counter() - t0) / seconds


def run_all(cfg, cache_dir, out_root, workers=3, log=print):
    import pickle
    from multiprocessing import Pool
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    t_start = time.time()
    T = build_targets(cfg, cache_dir, "interleave")
    TC = build_targets(cfg, cache_dir, "chronological")
    log(f"targets: fit {T['fit']['n_runs']} runs / {len(T['split']['fit_sessions'])} sessions, held-out "
        f"{T['heldout']['n_runs']} runs / {len(T['split']['heldout_sessions'])} sessions ({time.time() - t_start:.0f} s)")
    tf = target_of(T["fit"])
    models = ["twin", "shuffled", "old"]
    with Pool(min(workers, 3)) as pool:
        res = dict(zip(models, pool.map(_search_job, [(m, cfg, tf, str(cache_dir)) for m in models])))
    best_twin, checks = choose_twin(res["twin"], cfg, log)
    if best_twin is None:
        raise SystemExit("no twin candidate passed the live check")
    best = {"twin": best_twin["params"], "shuffled": res["shuffled"]["best"], "old": res["old"]["best"]}
    # chronological robustness: grid-only selection on the chronological fit half (the CMA path was guided by the
    # interleaved fit half, which overlaps the chronological held-out half, so it is not used here)
    tcf = target_of(TC["fit"])
    cache = EvalCache(cache_dir)
    grid_recs = [r for r in res["twin"]["records"] if r["stage"] == "grid"]
    chrono_scores = [(score(cache.get(r["key"]), tcf)["score"], r["params"]) for r in grid_recs]
    chrono_inside = [x for x in chrono_scores if x[1]["G"] <= G_LIVE_MAX + 1e-9]
    chrono_best = max(chrono_inside, key=lambda x: x[0])[1]
    unconstrained = max(grid_recs, key=lambda r: r["score"])["params"]       # best grid point, any G
    nrep = cfg["final_reps"]
    jobs = [("twin", best["twin"], cfg, str(cache_dir), SEEDS["final"], 0, nrep),
            ("old", best["old"], cfg, str(cache_dir), SEEDS["final"], 0, nrep),
            ("twin", chrono_best, cfg, str(cache_dir), SEEDS["chrono"], 0, nrep),
            ("twin", unconstrained, cfg, str(cache_dir), SEEDS["final"] + 100, 0, nrep)]
    jobs += [("shuffled", best["shuffled"], cfg, str(cache_dir), SEEDS["final"] + k, k, 1) for k in range(nrep)]
    log(f"final held-out runs: twin {best['twin']}, old {best['old']}, shuffled {best['shuffled']}, "
        f"chronological {chrono_best}, unconstrained {unconstrained}")
    with Pool(workers) as pool:
        outs = pool.map(_final_job, jobs)
    feats = {"twin": outs[0], "old": outs[1], "chrono": outs[2], "unconstrained": outs[3],
             "shuffled": [o[0] for o in outs[4:]]}
    th = target_of(T["heldout"])
    final = {"cfg": cfg, "best": best, "chrono_best": chrono_best, "live_checks": checks,
             "search": {m: {k: v for k, v in res[m].items() if k != "records"} for m in models},
             "records": {m: res[m]["records"] for m in models}, "refs": references(T), "refs_chrono": references(TC),
             "split": T["split"], "split_chrono": TC["split"], "n": {}}
    for m in ("twin", "shuffled", "old"):
        s, pooled, fcd = summarise(feats[m], th, tf)
        final[m] = s
        final[f"{m}_pooled_fc"] = pooled.astype(np.float32)
        final[f"{m}_fcd"] = fcd
    seg_fc = np.concatenate([f["run_fc"] for f in feats["twin"]]).astype(np.float64)
    final["per_run"], final["per_run_sim"], final["per_run_rr"] = per_run(final["twin_pooled_fc"], seg_fc, T["heldout"])
    s, _, _ = summarise(feats["chrono"], target_of(TC["heldout"]), tcf)
    final["chrono"] = s
    s, _, _ = summarise(feats["unconstrained"], th, tf)
    final["unconstrained"] = {**s, "params": unconstrained}
    final["emp_heldout_fc"] = T["heldout"]["fc"]
    final["emp_fit_fc"] = T["fit"]["fc"]
    final["emp_heldout_fcd"] = T["heldout"]["fcd_main"]
    final["emp_fit_fcd"] = T["fit"]["fcd_main"]
    final["n"] = {"heldout_runs": T["heldout"]["n_runs"], "heldout_acq": len(T["heldout"]["acq"]),
                  "heldout_main": T["heldout"]["n_main"], "fit_runs": T["fit"]["n_runs"],
                  "fit_acq": len(T["fit"]["acq"]), "fit_main": T["fit"]["n_main"]}
    final["wall_s"] = round(time.time() - t_start)
    (cache_dir / "final.pkl").write_bytes(pickle.dumps(final))
    write_outputs(final, out_root, log)
    final["realtime_s_per_sim_s"] = realtime_cost(Path(out_root) / "twin" / "params.json")
    (cache_dir / "final.pkl").write_bytes(pickle.dumps(final))
    write_outputs(final, out_root, log)
    return final


# =============================================================================================================
# outputs: twin/params.json, web/twin_score.json, figures
# =============================================================================================================
COLORS = {"emp": "#52514e", "twin": "#2a78d6", "shuffled": "#eb6834", "old": "#1baf7a"}
LABELS = {"emp": "recorded (held-out)", "twin": "twin model", "shuffled": "shuffled connectome", "old": "old model (Stuart-Landau)"}


def _r(x, k=3):
    return None if x is None else round(float(x), k)


def write_outputs(final, out_root=ROOT, log=print):
    out_root = Path(out_root)
    cfg = final["cfg"]
    best = final["best"]
    th, n = final["twin"], final["n"]
    params = {k: _r(v, 4) for k, v in best["twin"].items()}
    pfile = out_root / "twin" / "params.json"
    pfile.parent.mkdir(parents=True, exist_ok=True)
    pfile.write_text(json.dumps({
        "note": NOTE,
        "source": "python -m twin.fit all (twin/fit.py); see docs/twin/fit.md",
        "fitted_to": "interleaved fit half of the QC-kept MyConnectome resting runs (ds000031, CC0); "
                     "objective r(FC) - KS(FCD); all other model parameters are the defaults of twin/model.py",
        "params": params,
    }, indent=1) + "\n")
    search_evals = sum(final["search"][m]["evaluations"] for m in ("twin", "shuffled", "old"))
    seg_s = (cfg["seg_vols"] + DROP) * SIM_TR
    final_s = 5 * cfg["final_reps"] * (cfg["final_seg"] * seg_s + BURN)
    sim_s = sum(final["search"][m]["sim_seconds"] for m in ("twin", "shuffled", "old")) + final_s
    rep_tw = final["search"]["twin"]["replication"]
    chosen = next((r for r in rep_tw if r["params"] == best["twin"]), rep_tw[0])

    def block(m, extra=None):
        s = final[m]
        d = {"fc_r": _r(s["fc_r"]), "fc_r_sd": _r(s["fc_r_sd"]), "fcd_ks": _r(s["fcd_ks"]),
             "fcd_ks_sd": _r(s["fcd_ks_sd"]), "fc_r_pooled": _r(s["fc_r_pooled"]), "mean_fc": _r(s["mean_fc"]),
             "params": {k: _r(v, 4) for k, v in best[m].items()},
             "search_evaluations": final["search"][m]["evaluations"]}
        return {**d, **(extra or {})}

    refs = final["refs"]
    score = {
        "label": "similarity to his real brain (held-out)",
        "what": "a digital twin model of one real person's brain structure and recorded activity; not a mind, "
                "not conscious, not the person",
        "heldout": {"fc_r": _r(th["fc_r"]), "fc_r_sd": _r(th["fc_r_sd"]), "fcd_ks": _r(th["fcd_ks"]),
                    "fcd_ks_sd": _r(th["fcd_ks_sd"]), "fc_r_pooled": _r(th["fc_r_pooled"]),
                    "mean_fc_sim": _r(th["mean_fc"]), "mean_fc_recorded": refs["mean_fc_heldout"],
                    "n_runs": n["heldout_runs"], "n_acquisitions": n["heldout_acq"],
                    "n_runs_fcd": n["heldout_main"], "n_sessions": len(final["split"]["heldout_sessions"]),
                    "replicates": th["replicates"], "simulated_runs_per_replicate": th["segments_per_replicate"],
                    "fc_r_vs_simulated_runs": th["fc_r_vs_simulated_runs"]},
        "fit": {"fc_r": _r(th["fit"]["fc_r"]), "fcd_ks": _r(th["fit"]["fcd_ks"]),
                "search_score_mean": chosen["score_mean"], "search_score_sd_over_seeds": chosen["score_sd"],
                "search_fc_r_sd_over_seeds": chosen["fc_r_sd"], "search_seeds": chosen["n"],
                "n_runs": n["fit_runs"], "n_acquisitions": n["fit_acq"], "n_runs_fcd": n["fit_main"],
                "n_sessions": len(final["split"]["fit_sessions"])},
        "baselines": {"shuffled_connectome": block("shuffled"), "old_model": block("old"),
                      "sc_fc_direct_r": refs["sc_fc_direct_r"],
                      "sc_fc_direct_r_connected_pairs_log": refs["sc_fc_direct_r_connected_pairs_log"],
                      "test_retest_ceiling_r": refs["test_retest_ceiling_r"]},
        "per_run": final["per_run"],
        "params": params,
        "split": {"rule": "sessions sorted by scan date (sub-01_sessions.tsv), alternately fit / held-out; "
                          "multi-echo files of one acquisition merged",
                  "fit_sessions": final["split"]["fit_sessions"],
                  "heldout_sessions": final["split"]["heldout_sessions"]},
        "search": {"method": f"grid ({len(_grid_points('twin', cfg['grid_take']))} points) then CMA-ES "
                             f"({cfg['cma_gens']} generations x {cfg['cma_pop']}) on log-scaled parameters, then the "
                             f"best {cfg['top']} candidates re-run with {cfg['rep_seeds']} new seeds; same procedure "
                             f"for each baseline; every evaluation {cfg['eval_seg']} simulated runs of "
                             f"{cfg['seg_vols'] + DROP} volumes at TR {SIM_TR} s",
                   "objective": "r(simulated FC, recorded FC) - KS(simulated FCD, recorded FCD), fit half only",
                   "evaluations": search_evals, "sim_seconds": int(round(sim_s, -2)),
                   "live_check": [{"params": c["params"], "ok": c["ok"]} for c in final["live_checks"]]},
        "robustness": {"chronological_split": {
            "rule": "first half of the sessions by date -> fit, second half -> held-out; parameters chosen from the "
                    "grid only (the CMA-ES path used the interleaved fit half)",
            "params": {k: _r(v, 4) for k, v in final["chrono_best"].items()},
            "fc_r": _r(final["chrono"]["fc_r"]), "fc_r_sd": _r(final["chrono"]["fc_r_sd"]),
            "fcd_ks": _r(final["chrono"]["fcd_ks"]),
            "fit_sessions": len(final["split_chrono"]["fit_sessions"]),
            "heldout_sessions": len(final["split_chrono"]["heldout_sessions"]),
            "test_retest_ceiling_r": final["refs_chrono"]["test_retest_ceiling_r"],
            "sc_fc_direct_r": final["refs_chrono"]["sc_fc_direct_r"]},
            "without_live_constraint": {
                "rule": f"best grid point with any G (the fitted model is limited to G <= {G_LIVE_MAX} so that the "
                        "sleep stages still work in the live server); same held-out protocol",
                "params": {k: _r(v, 4) for k, v in final["unconstrained"]["params"].items()},
                "fc_r": _r(final["unconstrained"]["fc_r"]), "fc_r_sd": _r(final["unconstrained"]["fc_r_sd"]),
                "fcd_ks": _r(final["unconstrained"]["fcd_ks"]), "fcd_ks_sd": _r(final["unconstrained"]["fcd_ks_sd"]),
                "mean_fc": _r(final["unconstrained"]["mean_fc"])}},
        "notes": "",
    }
    if "realtime_s_per_sim_s" in final:
        score["params_check"] = {"realtime_s_per_sim_s_1thread": _r(final["realtime_s_per_sim_s"], 3),
                                 "budget": 0.3}
    score["notes"] = notes(final)
    sfile = out_root / "web" / "twin_score.json"
    sfile.parent.mkdir(parents=True, exist_ok=True)
    sfile.write_text(json.dumps(score, indent=1) + "\n")
    figures(final, out_root / "docs" / "twin")
    log(f"wrote {pfile}, {sfile}, figures in {out_root / 'docs' / 'twin'}")
    return score


def notes(final):
    """Plain-language caveats that travel with the numbers."""
    t, sh, old, refs = final["twin"], final["shuffled"], final["old"], final["refs"]
    return (
        "Digital twin model of one real person's brain structure and recorded activity; not a mind, not conscious, "
        "not the person. Scores compare simulated resting-state fMRI with recordings from sessions never used in the "
        f"fit (split by session). fc_r: correlation over {214 * 213 // 2} region pairs between simulated FC "
        f"(each replicate {t['segments_per_replicate']} simulated 10-min runs) and the held-out mean FC; fcd_ks: "
        "Kolmogorov-Smirnov distance between FC-dynamics distributions (0 = identical, 1 = disjoint). "
        f"The twin reaches r = {t['fc_r']:.2f}, "
        f"{'below' if t['fc_r'] < refs['sc_fc_direct_r'] else 'above'} what the log connectome weights alone give "
        f"(r = {refs['sc_fc_direct_r']:.2f}) and far below the test-retest ceiling of the recordings themselves "
        f"(r = {refs['test_retest_ceiling_r']:.2f}). Same held-out data: shuffled connectome r = {sh['fc_r']:.2f}, "
        f"old Stuart-Landau model r = {old['fc_r']:.2f}. Typical published whole-brain "
        "fits reach r ~ 0.3-0.6, mostly with group-average connectomes. The fit is limited to coupling G <= "
        f"{G_LIVE_MAX} so that sleep stages still behave in the live model. Simulated mean FC "
        f"({t['mean_fc']:.2f}) is lower than recorded ({refs['mean_fc_heldout']:.2f}). FCD is compared on the "
        "main-protocol runs (TR 1.16 s) only.")


def _square(v, n=214):
    m = np.eye(n)
    iu = triu(n)
    m[iu] = v
    m[iu[1], iu[0]] = v
    return m


def figures(final, d):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    d = Path(d)
    d.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.size": 8, "axes.spines.top": False, "axes.spines.right": False,
                         "axes.edgecolor": "#8a8984", "axes.labelcolor": "#0b0b0b", "xtick.color": "#52514e",
                         "ytick.color": "#52514e"})
    emp, sim = final["emp_heldout_fc"].astype(float), final["twin_pooled_fc"].astype(float)
    # 1. FC matrices + scatter
    fig, ax = plt.subplots(1, 3, figsize=(10, 3.3), dpi=90, gridspec_kw={"width_ratios": [1, 1, 1.05]})
    for a, v, t in ((ax[0], emp, "recorded FC (held-out half)"), (ax[1], sim, "twin model FC (simulated)")):
        lim = np.percentile(np.abs(v), 99)
        im = a.imshow(_square(v), cmap="RdBu_r", vmin=-lim, vmax=lim, interpolation="nearest")
        a.set_title(t)
        a.set_xticks([0, 100, 200])
        a.set_yticks([0, 100, 200])
        a.set_xlabel("region (Schaefer-200 + 14 subcortical)")
        plt.colorbar(im, ax=a, fraction=0.046, pad=0.03, label="Pearson r")
    ax[2].hexbin(emp, sim, gridsize=60, cmap="Blues", mincnt=1, bins="log")
    ax[2].set_xlabel("recorded FC (held-out)")
    ax[2].set_ylabel("simulated FC")
    ax[2].set_title(f"r = {pearson(emp, sim):.2f} over {len(emp)} region pairs")
    fig.tight_layout()
    fig.savefig(d / "fit_fc.png")
    plt.close(fig)
    # 2. FCD distributions
    fig, ax = plt.subplots(figsize=(5.2, 3.2), dpi=100)
    bins = np.linspace(-0.4, 1.0, 71)
    for k, v in (("emp", final["emp_heldout_fcd"]), ("twin", final["twin_fcd"]), ("shuffled", final["shuffled_fcd"]),
                 ("old", final["old_fcd"])):
        lab = LABELS[k] if k == "emp" else f"{LABELS[k]} (KS {ks(v, final['emp_heldout_fcd']):.2f})"
        ax.hist(np.asarray(v, float), bins=bins, density=True, histtype="step", lw=2 if k != "emp" else 2.5,
                color=COLORS[k], label=lab)
    ax.set_xlabel("FCD value: r between FC of two non-overlapping 60 s windows")
    ax.set_ylabel("density")
    ax.set_title("FC dynamics, held-out half")
    ax.legend(frameon=False, fontsize=7)
    fig.tight_layout()
    fig.savefig(d / "fit_fcd.png")
    plt.close(fig)
    # 3. search landscape of the twin model (grid: G x noise, best over velocity) + all CMA-ES evaluations
    recs = final["records"]["twin"]
    grid = [r for r in recs if r["stage"] == "grid"]
    Gs = sorted({r["params"]["G"] for r in grid})
    Ns = sorted({r["params"]["noise"] for r in grid})
    fig, ax = plt.subplots(1, 2, figsize=(9, 3.4), dpi=100)
    for a, key, t in ((ax[0], "score", "score = r(FC) - KS(FCD)"), (ax[1], "fc_r", "r(FC)")):
        M = np.full((len(Ns), len(Gs)), np.nan)
        for r in grid:
            i, j = Ns.index(r["params"]["noise"]), Gs.index(r["params"]["G"])
            M[i, j] = np.nanmax([M[i, j], r[key]])
        im = a.imshow(M, origin="lower", aspect="auto", cmap="viridis")
        a.set_xticks(range(len(Gs)))
        a.set_xticklabels([f"{g:g}" for g in Gs])
        a.set_yticks(range(len(Ns)))
        a.set_yticklabels([f"{v:g}" for v in Ns])
        lim = sum(g <= G_LIVE_MAX for g in Gs) - 0.5
        a.axvline(lim, color="white", lw=1.5, ls="--")
        a.text(lim - 0.05, len(Ns) - 0.55, "live-safe | ", ha="right", va="top", color="white", fontsize=6.5)
        a.set_xlabel("global coupling G")
        a.set_ylabel("noise sigma")
        a.set_title(f"grid, fit half: {t}\n(best over velocity)")
        plt.colorbar(im, ax=a, fraction=0.046, pad=0.03)
        for i in range(len(Ns)):
            for j in range(len(Gs)):
                if np.isfinite(M[i, j]):
                    a.text(j, i, f"{M[i, j]:.2f}", ha="center", va="center", fontsize=6.5,
                           color="white" if M[i, j] < np.nanmean(M) else "black")
    fig.tight_layout()
    fig.savefig(d / "fit_landscape.png")
    plt.close(fig)
    # 4. held-out scores vs baselines
    fig, ax = plt.subplots(1, 2, figsize=(9, 3.2), dpi=100)
    ms = ["twin", "shuffled", "old"]
    x = np.arange(len(ms))
    ax[0].bar(x, [final[m]["fc_r"] for m in ms], yerr=[final[m]["fc_r_sd"] for m in ms], width=0.6,
              color=[COLORS[m] for m in ms], capsize=3)
    for xx, m in zip(x, ms):
        ax[0].text(xx, final[m]["fc_r"] + final[m]["fc_r_sd"] + 0.01, f"{final[m]['fc_r']:.2f}", ha="center")
    refs = final["refs"]
    for v, lab, ls in ((refs["sc_fc_direct_r"], "connectome itself vs FC", "--"),
                       (refs["test_retest_ceiling_r"], "fit-half vs held-out recording (ceiling)", ":")):
        ax[0].axhline(v, color="#52514e", ls=ls, lw=1)
        ax[0].text(len(ms) - 0.5, v + 0.01, f"{lab}: {v:.2f}", ha="right", fontsize=7, color="#52514e")
    ax[0].set_xticks(x)
    ax[0].set_xticklabels([LABELS[m] for m in ms], fontsize=7)
    ax[0].set_ylabel("r(simulated FC, held-out FC)")
    ax[0].set_ylim(0, 1.05)
    ax[0].set_title("static FC (higher is better)")
    ax[1].bar(x, [final[m]["fcd_ks"] for m in ms], yerr=[final[m]["fcd_ks_sd"] for m in ms], width=0.6,
              color=[COLORS[m] for m in ms], capsize=3)
    for xx, m in zip(x, ms):
        ax[1].text(xx, final[m]["fcd_ks"] + final[m]["fcd_ks_sd"] + 0.01, f"{final[m]['fcd_ks']:.2f}", ha="center")
    ax[1].axhline(refs["fcd_ks_fit_vs_heldout"], color="#52514e", ls=":", lw=1)
    ax[1].text(len(ms) - 0.5, refs["fcd_ks_fit_vs_heldout"] + 0.01,
               f"fit-half vs held-out recording: {refs['fcd_ks_fit_vs_heldout']:.2f}", ha="right", fontsize=7,
               color="#52514e")
    ax[1].set_xticks(x)
    ax[1].set_xticklabels([LABELS[m] for m in ms], fontsize=7)
    ax[1].set_ylabel("KS distance of FCD distributions")
    ax[1].set_ylim(0, 1.05)
    ax[1].set_title("FC dynamics (lower is better)")
    fig.suptitle("held-out half: mean +- sd over independent simulations", fontsize=8)
    fig.tight_layout()
    fig.savefig(d / "fit_scores.png")
    plt.close(fig)
    try:                                                 # keep the committed PNGs small (256-colour palette)
        from PIL import Image
        for f in ("fit_fc.png", "fit_fcd.png", "fit_landscape.png", "fit_scores.png"):
            Image.open(d / f).convert("RGB").quantize(256).save(d / f, optimize=True)
    except ImportError:
        pass


# =============================================================================================================
# CLI
# =============================================================================================================
def main(argv=None):
    import pickle
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("cmd", choices=["all", "split", "targets", "write"])
    ap.add_argument("--quick", action="store_true", help="tiny pipeline (10 sessions, short runs, few evaluations)")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--cache", default=None, help=f"checkpoint directory (default {CACHE}/<full|quick>)")
    ap.add_argument("--out", default=None, help="root for params.json / twin_score.json / figures (default: repo; "
                                                "--quick default: <cache>/out)")
    a = ap.parse_args(argv)
    cfg = dict(QUICK if a.quick else FULL)
    if a.quick:
        cfg["live_check"] = False
    cache_dir = Path(a.cache) if a.cache else CACHE / cfg["name"]
    out_root = Path(a.out) if a.out else (cache_dir / "out" if a.quick else ROOT)
    if a.cmd == "split":
        runs = kept_runs()
        for rule in ("interleave", "chronological"):
            sp = split(runs, rule)
            print(f"{rule}: fit {len(sp['fit'])} runs / {len(sp['fit_sessions'])} sessions, held-out "
                  f"{len(sp['heldout'])} runs / {len(sp['heldout_sessions'])} sessions")
            print("  fit:", " ".join(sp["fit_sessions"]))
            print("  held-out:", " ".join(sp["heldout_sessions"]))
        return
    if a.cmd == "targets":
        for rule in ("interleave", "chronological"):
            print(rule, json.dumps(references(build_targets(cfg, cache_dir, rule))))
        return
    if a.cmd == "write":
        final = pickle.loads((cache_dir / "final.pkl").read_bytes())
        write_outputs(final, out_root)
        return
    run_all(cfg, cache_dir, out_root, a.workers)


if __name__ == "__main__":
    main()
