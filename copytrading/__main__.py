"""Replay observed or synthetic feeds; --resume reconstructs from the saved journal."""
import argparse
from contextlib import contextmanager
import fcntl
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import platform

from state_io import load_json, save_json
from .engine import PaperConfig, PaperEngine, feed_hash, validate_feed
from spiking.profiles import neurons_for


def implementation_hash():
    import numpy as np
    root = Path(__file__).resolve().parents[1]
    digest = hashlib.sha256()
    files = sorted((root / "copytrading").glob("*.py")) + sorted((root / "spiking").glob("*.py"))
    files += [root / "spiking/region_volumes.json", root / "out/connectome.npz"]
    for path in files:
        digest.update(str(path.relative_to(root)).encode())
        digest.update(path.read_bytes())
    digest.update((platform.python_version() + np.__version__).encode())
    return digest.hexdigest()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--feed", type=Path, required=True, help="Strict chronological JSONL import")
    ap.add_argument("--data-dir", type=Path, default=Path("data"))
    ap.add_argument("--task", choices=("simple", "trading"), default="trading")
    ap.add_argument("--neurons", type=int, help="default: 100k simple / 500k trading")
    ap.add_argument("--backend", choices=("auto", "numpy", "torch"), default="auto")
    ap.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    ap.add_argument("--diagnostic-small-network", action="store_true")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--controller-only", action="store_true", help="External learner, no native LIF component")
    ap.add_argument("--resume", action="store_true", help="Append new events and replay the complete journal")
    a = ap.parse_args(argv)
    a.neurons = a.neurons if a.neurons is not None else neurons_for(a.task)
    if not 5000 <= a.neurons <= 1000000:
        ap.error("supported network range: 5000-1000000")
    if not a.controller_only and a.neurons < neurons_for(a.task) and not a.diagnostic_small_network:
        ap.error("smaller networks require --diagnostic-small-network")
    backend = ("torch" if a.neurons > 100000 else "numpy") if a.backend == "auto" else a.backend
    device = ("cuda" if a.neurons > 100000 else "cpu") if a.device == "auto" else a.device
    if backend == "numpy" and device != "cpu" and not a.controller_only:
        ap.error("numpy backend requires --device cpu")
    with writer_lock(a.data_dir / "copytrading" / ".writer.lock"):
        return run(a, backend, device)


@contextmanager
def writer_lock(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("another paper importer is running") from None
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def run(a, backend, device):
    cfg = PaperConfig(seed=a.seed)
    path = a.data_dir / "copytrading" / "paper.json"
    events = [json.loads(line) for line in a.feed.read_text().splitlines() if line.strip()]
    run_config = dict(neurons=a.neurons, seed=a.seed, controller_only=a.controller_only,
                      implementation=implementation_hash(), paper=asdict(cfg), task=a.task,
                      backend=backend, device=device, diagnostic=a.diagnostic_small_network)
    if backend == "torch" and not a.controller_only:
        import torch
        run_config.update(torch_version=torch.__version__, cuda_version=torch.version.cuda)
    if a.resume:
        previous = load_json(path)
        if previous is None or previous.get("run_config") != run_config or previous.get("version") != 1:
            raise ValueError("resume requires an intact snapshot with matching configuration")
        if feed_hash(previous["events"]) != previous.get("feed_hash"):
            raise ValueError("saved journal hash mismatch")
        events = previous["events"] + events
    elif path.exists():
        raise ValueError("snapshot exists; use --resume or a separate data directory")
    validate_feed(events)
    if len({e["source"] for e in events}) > 1:
        raise ValueError("do not mix observed and synthetic sources in one run")
    brain = None
    if not a.controller_only:
        from .native import NativeBrain, TorchBrain
        brain = TorchBrain(a.neurons, a.seed, device) if backend == "torch" else NativeBrain(a.neurons, a.seed)
    result = PaperEngine(cfg, brain).replay(events)
    if a.resume:
        # GPU reductions need not be bit-identical on every device. Never rewrite
        # previously published decisions/outcomes if journal reconstruction drifts.
        old_report = previous["report"]
        if result["decisions"][:len(old_report["decisions"])] != old_report["decisions"]:
            raise ValueError("replay changed historical decisions; snapshot kept intact")
        prior_ids = {row["id"] for row in old_report["closed"]}
        if [row for row in result["closed"] if row["id"] in prior_ids] != old_report["closed"]:
            raise ValueError("replay changed historical outcomes; snapshot kept intact")
    result["source"] = events[0]["source"] if events else None
    result["requested_neurons"] = a.neurons
    result["profile"] = a.task
    result["diagnostic_small_network"] = a.diagnostic_small_network
    snapshot = dict(version=1, run_config=run_config, events=events, feed_hash=feed_hash(events), report=result)
    path.parent.mkdir(parents=True, exist_ok=True)
    save_json(path, snapshot, allow_nan=False)
    print(json.dumps({k: result[k] for k in ("mode", "source", "cash", "realized_pnl", "shadow_pending")}, indent=2))
    return result


if __name__ == "__main__":
    main()
