"""Toy bounded Hebbian plasticity and "one memory a day" for the SUB-01 digital twin model.

A digital twin model of one real person's brain structure and recorded activity; not a mind, not
conscious, not the person. This is a deliberately simple toy version of plasticity.

Rule (see docs/twin/plasticity.md): during wake only,
    dW_ij = eta * (a_i - <a_i>) (a_j - <a_j>) * dt  -  (dt / tau) * (W_ij - W0_ij)
on EXISTING structural edges only (W0_ij > 0), kept symmetric, with a per-edge cap
|W - W0| <= c * W0 and a total cap ||W - W0||_F / ||W0||_F <= total_cap.
Hebb 1949; bounded / normalised Hebbian learning (Oja 1982, J Math Biol 15:267); homeostatic synaptic
scaling (Turrigiano 2008, Cell 135:422). The numbers here are not fitted to any data.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import numpy as np


def _atomic_write(path: Path, writer):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
    with open(tmp, "wb") as f:
        writer(f)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def weights_sha256(W) -> str:
    """SHA-256 of the float32 little-endian C-order bytes of W."""
    return hashlib.sha256(np.ascontiguousarray(np.asarray(W).astype("<f4")).tobytes()).hexdigest()


class Plasticity:
    def __init__(self, W0, data_dir="data", names=None, eta=1e-9, tau=3 * 86400.0, edge_cap=0.05,
                 total_cap=0.02, mean_tau=3600.0, consolidation_delta=0.01):
        """W0: (n, n) model-space weights (as TwinBrain.W0). Units: eta in weight-units per (activity^2 s);
        tau, mean_tau in s; edge_cap, total_cap, consolidation_delta are relative (dimensionless)."""
        self.W0 = np.array(W0, dtype=float)
        self.n = self.W0.shape[0]
        self.names = [str(x) for x in names] if names is not None else [f"region_{i}" for i in range(self.n)]
        self.data_dir = Path(data_dir)
        self.eta, self.tau, self.mean_tau = float(eta), float(tau), float(mean_tau)
        self.edge_cap, self.total_cap = float(edge_cap), float(total_cap)
        self.delta = float(consolidation_delta)
        self.mask = (self.W0 > 0) & (self.W0.T > 0) & ~np.eye(self.n, dtype=bool)   # existing edges only
        self._w0_norm = float(np.linalg.norm(self.W0)) or 1.0
        self.W0_hash = hashlib.sha256(np.ascontiguousarray(self.W0.astype("<f8")).tobytes()).hexdigest()
        self.W = self.W0.copy()
        self.abar = None            # slow running mean of activity per region (<a>)
        self.pending = []           # today's accepted responses (not yet consolidated)
        self._load()

    # --- paths / persistence -----------------------------------------------------
    @property
    def weights_path(self): return self.data_dir / "weights.npz"
    @property
    def memories_path(self): return self.data_dir / "memories.json"
    @property
    def pending_path(self): return self.data_dir / "pending_responses.json"

    def _load(self):
        p = self.weights_path
        if p.exists():
            try:
                z = np.load(p, allow_pickle=False)
                if str(z["w0_hash"]) == self.W0_hash and z["W"].shape == self.W0.shape:
                    self.W = z["W"].astype(float)
                    if "abar" in z.files and z["abar"].size == self.n:
                        self.abar = z["abar"].astype(float)
                else:                       # connectome changed: restart from the original, keep the old log aside
                    if self.memories_path.exists():
                        os.replace(self.memories_path, self.memories_path.with_name(
                            f"memories.old-{str(z['w0_hash'])[:8]}.json"))
                    if self.pending_path.exists():
                        self.pending_path.unlink()
            except Exception:
                pass
        if self.pending_path.exists():
            try:
                self.pending = json.loads(self.pending_path.read_text())
            except Exception:
                self.pending = []

    def save(self):
        """Atomically persist W (with the hash of W0) to data/weights.npz."""
        abar = self.abar if self.abar is not None else np.zeros(0)
        _atomic_write(self.weights_path, lambda f: np.savez(f, W=self.W, w0_hash=np.array(self.W0_hash), abar=abar))

    def _save_pending(self):
        _atomic_write(self.pending_path, lambda f: f.write(json.dumps(self.pending).encode()))

    # --- bounds --------------------------------------------------------------------
    def _enforce(self, W):
        D = np.where(self.mask, W - self.W0, 0.0)
        lim = self.edge_cap * self.W0
        D = np.clip(D, -lim, lim)
        rel = np.linalg.norm(D) / self._w0_norm
        if rel > self.total_cap:
            D *= self.total_cap / rel
        return self.W0 + D

    # --- wake-time Hebbian rule ----------------------------------------------------
    def hebbian(self, act, dt, stage="AWAKE"):
        """One wake-time update from the activity vector act (n,) over dt seconds. No-op unless stage == AWAKE."""
        a = np.abs(np.asarray(act, dtype=float))
        if stage != "AWAKE":
            return self.W
        if self.abar is None:
            self.abar = a.copy()
        c = a - self.abar
        k = min(1.0, dt / self.mean_tau)
        self.abar += k * (a - self.abar)
        dW = self.eta * dt * np.outer(c, c) - (dt / self.tau) * (self.W - self.W0)
        dW = 0.5 * (dW + dW.T)
        self.W = self._enforce(self.W + np.where(self.mask, dW, 0.0))
        return self.W

    # --- one memory a day -------------------------------------------------------------
    def record_response(self, t, text, regions, strength):
        """Remember an accepted chat message's brain response until tonight's REM. regions: names or indices of
        the co-activated regions. Nothing about the sender is stored (the caller must not pass it)."""
        idx = [self._index(r) for r in regions]
        self.pending.append({"t": float(t), "message": str(text), "regions": sorted(set(idx)),
                             "strength": float(strength)})
        self._save_pending()

    def _index(self, r):
        return int(r) if isinstance(r, (int, np.integer)) else self.names.index(str(r))

    def consolidate(self, day):
        """REM, once per night: strengthen existing edges among the strongest response's regions by a small
        fixed relative amount, append a record to data/memories.json. Returns the record or None."""
        pend, self.pending = self.pending, []
        if self.pending_path.exists():
            self._save_pending()
        if not pend:
            return None
        win = max(pend, key=lambda r: r["strength"])
        idx = np.array(win["regions"], dtype=int)
        sel = np.zeros((self.n, self.n), dtype=bool)
        if idx.size:
            sel[np.ix_(idx, idx)] = True
        sel &= self.mask
        self.W = self._enforce(np.where(sel, self.W * (1.0 + self.delta), self.W))
        mem = self._read_memories()
        rec = {"n": len(mem) + 1, "day": str(day), "message": win["message"],
               "regions": [self.names[i] for i in idx], "delta": self.delta, "sha256": weights_sha256(self.W)}
        mem.append(rec)
        _atomic_write(self.memories_path, lambda f: f.write(json.dumps(mem, indent=1).encode()))
        self.save()
        self.publish_hash(rec)
        return rec

    def _read_memories(self):
        try:
            return json.loads(self.memories_path.read_text())
        except Exception:
            return []

    # --- metrics, reset, hook ------------------------------------------------------------
    def drift(self):
        D = self.W - self.W0
        rel = np.where(self.mask, np.abs(D) / np.where(self.W0 > 0, self.W0, 1.0), 0.0)
        return {"rel_frobenius": float(np.linalg.norm(D) / self._w0_norm),
                "edges_changed": int(np.triu(self.mask & (D != 0), 1).sum()),   # undirected edges
                "max_edge_rel": float(rel.max())}

    def reset(self):
        """Back to exactly W0 (the memory log is a history and is kept)."""
        self.W = self.W0.copy()
        self.abar = None
        self.save()
        return self.W

    def publish_hash(self, record):
        """Hook, deliberately a no-op. It could later publish record["sha256"] (a fingerprint of the weights after
        a night's consolidation) somewhere public as a tamper-evident timestamp. Nothing is implemented: no
        wallets, no transactions, no network calls."""
        return None
