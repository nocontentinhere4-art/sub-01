"""Reproduce the numbers in docs/twin/model.md (1 BLAS thread): real-time cost, batched throughput, sleep-stage
dynamics, stimulus reactivity, hemodynamic response, resting FC vs the recorded data, driven BOLD.

    OMP_NUM_THREADS=1 python -m twin.bench_model [--fc-seconds 900] [--out twin/data/model_bench.json]

A digital twin model of one real person's brain structure and recorded activity; not a mind, not the person.
"""
import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import argparse
import glob
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
from scipy.signal import butter, sosfiltfilt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import sleep  # noqa: E402
from twin.model import DEFAULTS, Balloon, TwinBrain, load_connectome, simulate_bold  # noqa: E402

STAGES = {"AWAKE": sleep.AWAKE, "NREM_LIGHT": sleep.NREM_LIGHT, "NREM_DEEP": sleep.NREM_DEEP, "REM": sleep.REM}


def brain(seed=0, **kw):
    return TwinBrain(params=kw, params_path=None, seed=seed)


def stage(b, name):
    p = STAGES[name]
    b.set_rhythm(p["f_hz"], p["coupling"], p["noise"])
    b.a = p["a"]


def realtime():
    out = {}
    for name in ("AWAKE", "NREM_DEEP"):
        b = brain(1)
        stage(b, name)
        b.run(1.0, every=50)
        t0 = time.perf_counter()
        for tick in range(100):                    # 5 s of model time, driven like live_server.run_brain
            stage(b, name)
            b.drive = np.zeros(b.n)
            if tick % 10 == 0:
                b.stimulate("reward", 6.0)
            acc = np.zeros(b.n)
            for _ in range(10):
                acc += np.abs(b.step(5))
            b.state()
        out[name] = round((time.perf_counter() - t0) / 5.0, 4)
    return {"wall_s_per_sim_s": out, "dt_s": DEFAULTS["dt"]}


def throughput():
    out = {}
    for B in (1, 8):
        t0 = time.perf_counter()
        simulate_bold([{}] * B, 30, 1.0, burn=0, params_path=None)
        w = time.perf_counter() - t0
        out[f"B{B}"] = {"sim_s_per_wall_s_per_set": round(30 / w, 2), "aggregate": round(30 * B / w, 2)}
    return out


def stage_stats():
    out = {}
    for name in STAGES:
        b = brain(2)
        stage(b, name)
        b.run(3.0, every=50)
        E, ab, sy = [], [], []
        for i in range(2000):                       # 10 s at 5 ms
            x = b.step(5)
            E.append(b.E.copy())
            ab.append(np.abs(x).mean())
            if i % 10 == 0:
                sy.append(b.state()["sync"])
        E = np.array(E)
        f = np.fft.rfftfreq(len(E), 0.005)
        P = (np.abs(np.fft.rfft(E - E.mean(0), axis=0)) ** 2).mean(1)
        m = E.mean(1)
        Pg = np.abs(np.fft.rfft(m - m.mean())) ** 2
        sel = f > 0.2
        out[name] = {"mean_E": round(float(E.mean()), 3), "sd_E": round(float(E.std(0).mean()), 3),
                     "peak_hz_region": round(float(f[sel][P[sel].argmax()]), 1),
                     "peak_hz_global": round(float(f[sel][Pg[sel].argmax()]), 1),
                     "slow_power_frac_lt4hz": round(float(P[sel & (f < 4)].sum() / P[sel].sum()), 2),
                     "sync": round(float(np.mean(sy)), 2), "display_abs_x": round(float(np.mean(ab)), 2),
                     "up_state_frac": round(float((E > 0.3).mean()), 2)}
    return out


def reactivity(amount=8.0, trials=10):
    out = {}
    for name in STAGES:
        b = brain(3)
        stage(b, name)
        b.run(3.0, every=50)
        g = np.array(b.group_idx["reward"])
        o = np.setdiff1d(np.arange(b.n), g)
        spec, disp = [], []
        for _ in range(trials):
            pre = [b.step(10) is not None and (b.E.copy(), np.abs(b._x[g]).mean()) for _ in range(50)]
            b.stimulate("reward", amount)
            post = [b.step(10) is not None and (b.E.copy(), np.abs(b._x[g]).mean()) for _ in range(100)]
            d = np.mean([q[0] for q in post], 0) - np.mean([q[0] for q in pre], 0)
            spec.append(d[g].mean() - d[o].mean())
            disp.append(np.mean([q[1] for q in post]) - np.mean([q[1] for q in pre]))
            b.run(4.0, every=100)
        out[name] = {"specific_dE": round(float(np.mean(spec)), 4), "sem": round(float(np.std(spec) / math.sqrt(trials)), 4),
                     "display_delta": round(float(np.mean(disp)), 3)}
    return {"stimulus": f"reward group, {amount} units, 0-1 s window", **out}


def hrf():
    h = Balloon(1)
    dt = 0.01
    t = np.arange(0, 40, dt)
    y = np.array([h.step(np.array([1.0 if tk < 0.5 else 0.0]), dt) or h.bold()[0] for tk in t])
    return {"input": "u = 1 for 0.5 s", "peak_s": round(float(t[y.argmax()]), 2), "peak_pct": round(float(y.max()), 3),
            "undershoot_pct": round(float(y.min()), 3), "undershoot_s": round(float(t[y.argmin()]), 1)}


def empirical_fc():
    qc = json.loads((ROOT / "out" / "rest" / "qc.json").read_text())
    fcs = []
    for f in sorted(glob.glob(str(ROOT / "out" / "rest" / "*.npz"))):
        if not qc.get(Path(f).stem, {}).get("kept", True):
            continue
        fcs.append(np.corrcoef(np.nan_to_num(np.load(f)["ts"]).T))
    return np.nanmean(fcs, 0), len(fcs)


def resting_fc(seconds):
    emp, nrun = empirical_fc()
    W = load_connectome()[0]
    iu = np.triu_indices(W.shape[0], 1)
    x = simulate_bold([{}], seconds, 1.0, seed=2, burn=20, params_path=None)[0]
    sos = butter(2, [0.01, 0.1], btype="band", fs=1.0, output="sos")
    x = sosfiltfilt(sos, x, axis=0)
    fc = np.corrcoef(x.T)[iu]
    h = len(x) // 2
    f1, f2 = np.corrcoef(x[:h].T)[iu], np.corrcoef(x[h:].T)[iu]
    r = lambda a, b: round(float(np.corrcoef(a, b)[0, 1]), 3)
    return {"sim_seconds": seconds, "empirical_runs": nrun, "emp_mean_fc": round(float(emp[iu].mean()), 3),
            "sim_mean_fc": round(float(fc.mean()), 3), "r_simFC_empFC": r(fc, emp[iu]),
            "r_SC_empFC": r(W[iu], emp[iu]), "r_simFC_SC": r(fc, W[iu]), "split_half_r_simFC": r(f1, f2),
            "bold_sd_pct": round(float(x.std(0).mean()), 4)}


def driven(seconds=300.0):
    """Drive the model with one recorded run (as the live server does) and correlate its BOLD with the recording."""
    from real_baseline import RealBaseline
    b = brain(4)
    rb = RealBaseline(b.names, str(ROOT / "out" / "rest"), seed=1)
    sim, rec = [], []
    for k in range(int(seconds / 0.05)):
        sig = rb.advance(0.05)
        b.drive = 1.6 * np.clip(sig, -2.0, 3.0)
        b.step(50)
        if k % 20 == 19:                          # 1 s samples
            sim.append(b.bold())
            rec.append(sig.copy())
    sim, rec = np.array(sim)[30:], np.array(rec)[30:]
    best = {}
    for lag in range(0, 9):                       # BOLD lags the drive by the hemodynamic delay
        a, c = sim[lag:], rec[:len(rec) - lag]
        rr = [np.corrcoef(a[:, i], c[:, i])[0, 1] for i in range(b.n)]
        best[lag] = float(np.nanmean(rr))
    lag = max(best, key=best.get)
    return {"seconds": seconds, "run": rb.run.split("_")[1], "best_lag_s": lag,
            "mean_region_r_bold_vs_recording": round(best[lag], 3), "bold_sd_pct": round(float(sim.std(0).mean()), 3)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fc-seconds", type=float, default=900.0)
    ap.add_argument("--out", default=str(ROOT / "twin" / "data" / "model_bench.json"))
    a = ap.parse_args()
    res = {"note": "digital twin model of one person's brain structure and recorded activity; not a mind",
           "threads": 1}
    for name, fn in [("realtime", realtime), ("throughput", throughput), ("stages", stage_stats),
                     ("reactivity", reactivity), ("hrf", hrf), ("driven", driven),
                     ("resting_fc", lambda: resting_fc(a.fc_seconds))]:
        t0 = time.time()
        res[name] = fn()
        print(name, json.dumps(res[name]), f"({time.time() - t0:.0f} s)", flush=True)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
