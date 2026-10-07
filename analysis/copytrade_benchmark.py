"""Reproducible synthetic checks, not market backtests or evidence of profitability."""
import argparse
from dataclasses import replace
import json
from pathlib import Path
import platform
import subprocess
import sys
import time

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from copytrading import PaperConfig, PaperEngine
from copytrading.native import NativeBrain
from spiking.live import LiveBrain, synthetic


def fixture(seed=1, rounds=100):
    rng = np.random.default_rng(seed)
    events = []
    for i in range(rounds):
        t = i * 90.0
        means = (0.08, -0.025, -0.08) if i < rounds // 2 else (-0.08, -0.025, 0.08)
        events.append(dict(id=f"q{i}a", t=t, type="quote", source="synthetic", prices={a: 100.0 for a in "ABC"}))
        events.append(dict(id=f"o{i}", t=t + 1, type="offer", source="synthetic",
                           signals=[dict(trader=tr, asset=a, side="buy") for tr, a in zip(("alpha", "bravo", "charlie"), "ABC")]))
        events.append(dict(id=f"q{i}b", t=t + 61, type="quote", source="synthetic",
                           prices={a: 100 * (1 + float(rng.normal(mu, .025))) for a, mu in zip("ABC", means)}))
    return events


def paper_check(seeds=range(12), native=False):
    rows = []
    for seed in seeds:
        events = fixture(seed)
        for policy in ("adaptive", "random", "fixed", "cash"):
            cfg = PaperConfig(seed=seed, exploration=.05)
            brain = NativeBrain(40000, seed + 1) if native and policy == "adaptive" else None
            t = time.perf_counter()
            report = PaperEngine(cfg, brain, policy).replay(events)
            choices = report["decisions"]
            row = dict(seed=seed, policy=policy, native=bool(brain), realized_pnl=report["realized_pnl"],
                       copied=sum(r["pick"] != "cash" for r in choices),
                       early_best_last20=sum(r["pick"] == "alpha" for r in choices[30:50]) / 20,
                       reversed_best_last20=sum(r["pick"] == "charlie" for r in choices[80:100]) / 20,
                       unresolved=len(report["unresolved"]), wall_s=time.perf_counter()-t,
                       learned=sum(r.get("ok", False) for r in report["learning"]))
            rows.append(row)
            print(json.dumps(row), flush=True)
    return rows


def neuron_check(seeds=(1, 2, 3)):
    rows = []
    for seed in seeds:
        for n in (20000, 40000, 80000):
            t = time.perf_counter()
            brain = LiveBrain(n, twin=True, seed=seed, log=lambda *a: None)
            build = time.perf_counter()-t
            t = time.perf_counter()
            result = synthetic(brain, trials=100, seed=918 + seed)
            rows.append(dict(neurons=n, network_seed=seed, build_s=build,
                             run_s=time.perf_counter()-t, synapses=brain.net.n_syn, result=result))
            print(json.dumps(rows[-1]), flush=True)
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--neurons", action="store_true")
    ap.add_argument("--native", action="store_true")
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--fixture", type=Path)
    a = ap.parse_args()
    if a.fixture:
        a.fixture.write_text("".join(json.dumps(e)+"\n" for e in fixture()), encoding="utf-8")
    data = dict(python=platform.python_version(), numpy=np.__version__,
                base_commit=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
                source="synthetic", notice="Deliberately constructed regime reversal, not exchange data.",
                rows=neuron_check() if a.neurons else paper_check(range(3) if a.native else range(12), a.native))
    a.output.write_text(json.dumps(data, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
