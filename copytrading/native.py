"""Native LIF preference and actual-outcome learning; reputation remains external."""
import hashlib
from spiking.live import LiveBrain


class NativeBrain:
    def __init__(self, neurons=100000, seed=1):
        if neurons > 100000:
            raise ValueError("large trading profiles require the CUDA backend")
        self.brain = LiveBrain(neurons, twin=False, seed=seed, log=lambda *args: None)

    def decide(self, labels, did):
        result = self.brain.decide(labels, did=did)
        result.pop("cpu_ms", None)  # wall/CPU timing is excluded from deterministic replay
        return result

    def learn(self, did, followed, delta):
        return self.brain.learn(did, followed, delta)

    def discard(self, did):
        self.brain.pending.pop(did, None)

    def status(self):
        status = self.brain.status()
        for key in ("cpu_s", "uptime_s", "build_s"):
            status.pop(key, None)
        status["learned_weights_sha256"] = hashlib.sha256(self.brain.dw.tobytes()).hexdigest()
        return status


class TorchBrain:
    """Torch LIF backend for CUDA trading profiles, with actual followed-pool credit.

    Large profiles are rejected on CPU before allocating a network. Tiny CPU runs
    exercise the same tag/credit code in tests. The external controller supplies
    the prediction error; this adapter does not invent a second reward baseline.
    """
    def __init__(self, neurons=500000, seed=1, device="cuda"):
        import numpy as np
        import torch
        from spiking.config import Config
        from spiking.net import SpikingNet
        from spiking.choice import LiveChooser
        self.np, self.torch = np, torch
        target = torch.device(device)
        if neurons > 100000 and target.type != "cuda":
            raise ValueError("trading-sized networks require CUDA; no large CPU allocation")
        if target.type == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA unavailable; use a GPU worker or --controller-only")
        self.net = SpikingNet(Config(n_neurons=neurons, seed=seed), device=str(target))
        self.chooser = LiveChooser(self.net)
        self.pending = {}
        self.n_decisions, self.n_learn = 0, 0
        self.net.run(100)
        self.chooser.calibrate()

    def decide(self, labels, did):
        p = self.net.plast
        was, p.frozen = p.frozen, True  # only explicit settled paper rewards change weights
        try:
            result = self.chooser.decide(labels)
        finally:
            p.frozen = was
        elig = result.pop("elig")
        if elig is None:
            raise RuntimeError("no native eligibility available")
        np = self.np
        posts = p.pdst[elig["q"]].cpu().numpy()
        owners = np.full(len(posts), -1, dtype=int)
        for i, pool in enumerate(self.chooser.pools(labels)):
            owners[np.isin(posts, pool)] = i
        # Recover presynaptic activity from the original chosen-pool tag.
        denominator = self.torch.as_tensor(np.where(owners == result["pick"], 1.,
                                                    1. / max(1, len(labels)-1)), dtype=elig["tag"].dtype,
                                            device=self.net.device)
        pre = elig["tag"].abs() / denominator
        self.pending[did] = (elig["q"], pre, owners, list(labels))
        self.n_decisions += 1
        return dict(result, n_neurons=self.net.n, backend="torch", device=str(self.net.device))

    def learn(self, did, followed, delta):
        import math
        if did not in self.pending:
            return dict(ok=False, why="unknown decision")
        q, pre, owners, labels = self.pending[did]
        if not isinstance(followed, int) or not 0 <= followed < len(labels) or not math.isfinite(delta):
            return dict(ok=False, why="bad reward")
        self.pending.pop(did)
        key = labels[followed]
        eta = self.chooser.eta_for(key)
        self.chooser.n[key] = self.chooser.n.get(key, 0) + 1
        da = max(-1.0, min(1.0, 2 * delta))
        signs = self.np.where(owners == followed, 1., self.np.where(owners >= 0, -1. / max(1, len(labels)-1), 0.))
        tag = pre * self.torch.as_tensor(signs, dtype=pre.dtype, device=self.net.device)
        self.net.plast.dw.index_add_(0, q, eta * da * tag)
        self.net.plast._apply()
        self.n_learn += 1
        return dict(ok=True, eta=eta, da=da, n_learn=self.n_learn)

    def discard(self, did):
        self.pending.pop(did, None)

    def status(self):
        weights = self.net.plast.dw.detach().cpu().numpy()
        return dict(n_neurons=self.net.n, n_synapses=self.net.n_syn, n_learn=self.n_learn,
                    n_decisions=self.n_decisions, backend="torch", device=str(self.net.device),
                    learned_weights_sha256=hashlib.sha256(weights.tobytes()).hexdigest())
