import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from twin.plasticity import Plasticity, weights_sha256  # noqa: E402


def w0():
    z = np.load(ROOT / "out" / "connectome.npz", allow_pickle=True)
    W = z["weights"].astype(float)
    n0 = min(W.shape[0], len(z["names"]))
    keep = np.where(W[:n0, :n0].sum(1) > 0)[0]
    W = np.log1p(W[np.ix_(keep, keep)])
    W /= W.sum(1).mean()
    return W, [str(z["names"][i]) for i in keep]


def fresh(tmp, **kw):
    W, names = w0()
    return Plasticity(W, tmp, names=names, **kw), W


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def test_bounded_adversarial(tmp_path):
    p, W0 = fresh(tmp_path, eta=1e-5, tau=1e9)      # absurdly fast rates, tiny decay: caps must still hold
    rng = np.random.default_rng(0)
    for i in range(1500):
        a = rng.random(p.n) * 2 * (rng.random(p.n) < 0.5) if i % 2 else rng.random(p.n) * 2
        p.hebbian(a, 10.0)
    d = p.drift()
    D = p.W - W0
    assert d["rel_frobenius"] <= p.total_cap + 1e-9
    assert np.all(np.abs(D) <= p.edge_cap * W0 + 1e-12)
    assert np.all(D[W0 == 0] == 0)                  # no new edges
    assert np.allclose(W0, W0.T) and np.allclose(p.W, p.W.T)
    assert d["rel_frobenius"] > 0.5 * p.total_cap   # the test really pushed against the cap


def test_typical_day_is_small(tmp_path):
    p, _ = fresh(tmp_path)
    rng = np.random.default_rng(1)
    for _ in range(8640):                            # one day at 10 s steps
        p.hebbian(0.45 + 0.1 * rng.standard_normal(p.n), 10.0)
    assert p.drift()["rel_frobenius"] < 0.002


def test_wake_only_and_reset(tmp_path):
    p, W0 = fresh(tmp_path, eta=1e-6)
    rng = np.random.default_rng(2)
    for st in ("NREM", "REM"):
        for _ in range(50):
            p.hebbian(rng.random(p.n), 10.0, stage=st)
    assert np.array_equal(p.W, W0)
    for _ in range(50):
        p.hebbian(rng.random(p.n), 10.0)
    assert not np.array_equal(p.W, W0)
    p.reset()
    assert np.array_equal(p.W, W0)


def test_consolidation(tmp_path):
    p, W0 = fresh(tmp_path)
    assert p.consolidate("2026-01-01") is None       # no messages, no memory
    assert not p.memories_path.exists()
    a, b = [i for i in range(p.n) if p.mask[i].sum() > 5][:2], list(range(5, 12))
    p.record_response(1.0, "weak one", a, 0.2)
    p.record_response(2.0, "strong one", b, 0.9)
    rec = p.consolidate("2026-01-02")
    assert rec["message"] == "strong one" and rec["n"] == 1 and rec["day"] == "2026-01-02"
    assert rec["regions"] == [p.names[i] for i in b]
    assert set(rec) == {"n", "day", "message", "regions", "delta", "sha256"}
    assert rec["sha256"] == hashlib.sha256(p.W.astype("<f4").tobytes()).hexdigest()
    sel = np.zeros((p.n, p.n), bool)
    sel[np.ix_(b, b)] = True
    changed = (p.W != W0)
    assert changed.any() and not (changed & ~(sel & p.mask)).any()
    assert np.allclose(p.W[changed] / W0[changed], 1 + p.delta)
    assert json.loads(p.memories_path.read_text())[0] == rec
    assert p.consolidate("2026-01-03") is None       # pending cleared
    p.record_response(3.0, "next", b, 0.5)
    assert p.consolidate("2026-01-04")["n"] == 2
    assert p.drift()["rel_frobenius"] <= p.total_cap + 1e-12


def test_persistence_and_hash_change(tmp_path):
    p, W0 = fresh(tmp_path)
    p.record_response(1.0, "hi", [3, 4, 5, 6], 1.0)
    p2 = Plasticity(W0, tmp_path, names=p.names)     # pending survives a restart
    assert len(p2.pending) == 1
    p2.consolidate("d")
    p3 = Plasticity(W0, tmp_path, names=p.names)
    assert np.array_equal(p3.W, p2.W) and not np.array_equal(p3.W, W0)
    p4 = Plasticity(W0 * 1.01, tmp_path, names=p.names)   # connectome changed -> restart from original
    assert np.array_equal(p4.W, W0 * 1.01)


def test_connectome_untouched(tmp_path):
    f = ROOT / "out" / "connectome.npz"
    h = sha(f)
    p, _ = fresh(tmp_path)
    p.hebbian(np.random.default_rng(3).random(p.n), 10.0)
    p.record_response(1.0, "x", [1, 2, 3], 1.0)
    p.consolidate("d")
    p.reset()
    assert sha(f) == h


def test_drift_metrics_and_hook(tmp_path):
    p, W0 = fresh(tmp_path)
    assert p.drift() == {"rel_frobenius": 0.0, "edges_changed": 0, "max_edge_rel": 0.0}
    i, j = np.argwhere(p.mask)[0]
    p.W[i, j] *= 1.03
    p.W[j, i] *= 1.03
    d = p.drift()
    assert d["edges_changed"] == 1 and abs(d["max_edge_rel"] - 0.03) < 1e-9 and d["rel_frobenius"] > 0
    assert p.publish_hook_ok() if hasattr(p, "publish_hook_ok") else p.publish_hash({}) is None
