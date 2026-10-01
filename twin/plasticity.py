"""Toy bounded Hebbian plasticity and "one memory a day" for the SUB-01 digital twin model.

A digital twin model of one real person's brain structure and recorded activity; not a mind, not
conscious, not the person. This is a deliberately simple toy version of plasticity.

Rule (see docs/twin/plasticity.md): during wake only,
    dW_ij = eta * (a_i - <a_i>) (a_j - <a_j>) * dt  -  (dt / tau) * (W_ij - W0_ij)
on EXISTING structural edges only (W0_ij > 0), kept symmetric, with a per-edge cap
|W - W0| <= c * W0 and a total cap ||W - W0||_F / ||W0||_F <= total_cap.
The first term is the covariance form of Hebb's postulate (Hebb 1949; Sejnowski 1977, J Math Biol 4:303).
Hard bounds replace the weight normalisation of Oja (1982, J Math Biol 15:267), which is NOT implemented; the decay
to W0 is only loosely inspired by homeostatic synaptic scaling (Turrigiano 2008, Cell 135:422), which is
multiplicative and activity-set, unlike this term. The numbers here are not fitted to any data.
"""
from __future__ import annotations

import hashlib
import json
import os
import uuid
import warnings
from pathlib import Path

import numpy as np


def _atomic_write(path: Path, writer):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp")
    try:
        with open(tmp, "wb") as f:
            writer(f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    try:                                    # make the rename itself durable (POSIX); best effort elsewhere
        fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError:
        pass


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
        self._last_rec = None       # last memory record, also kept in weights.npz (crash repair)
        self._consumed = []         # ids of the pending responses consumed by that consolidation
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
                    if "last_rec" in z.files and str(z["last_rec"]):
                        self._last_rec = json.loads(str(z["last_rec"]))
                        self._consumed = [str(x) for x in z["consumed"]] if "consumed" in z.files else []
                else:                       # connectome changed: restart from the original, keep the old log aside
                    if self.memories_path.exists():
                        os.replace(self.memories_path, self.memories_path.with_name(
                            f"memories.old-{str(z['w0_hash'])[:8]}.json"))
                    if self.pending_path.exists():
                        self.pending_path.unlink()
            except Exception as e:
                warnings.warn(f"plasticity: could not load {p} ({e!r}); starting from W0")
        if self.pending_path.exists():
            try:
                pend = json.loads(self.pending_path.read_text())
                self.pending = [r for r in pend if isinstance(r, dict)] if isinstance(pend, list) else []
            except Exception:
                self.pending = []
        self._repair()

    def _repair(self):
        """weights.npz is the commit point of a consolidation. If a crash happened after it was written but before
        memories.json / pending_responses.json were updated, finish those two writes now (idempotent)."""
        rec = self._last_rec
        if rec is None:
            return
        mem = self._read_memories()
        if not any(m.get("n") == rec["n"] and m.get("sha256") == rec["sha256"] for m in mem):
            mem.append(rec)
            _atomic_write(self.memories_path, lambda f: f.write(json.dumps(mem, indent=1).encode()))
        used = set(self._consumed)
        if any(r.get("id") in used for r in self.pending):
            self.pending = [r for r in self.pending if r.get("id") not in used]
            self._save_pending()

    def save(self):
        """Atomically persist W (with the hash of W0) to data/weights.npz."""
        abar = self.abar if self.abar is not None else np.zeros(0)
        last = json.dumps(self._last_rec) if self._last_rec is not None else ""
        _atomic_write(self.weights_path, lambda f: np.savez(
            f, W=self.W, w0_hash=np.array(self.W0_hash), abar=abar, last_rec=np.array(last),
            consumed=np.array(self._consumed, dtype=str)))

    def _save_pending(self):
        _atomic_write(self.pending_path, lambda f: f.write(json.dumps(self.pending).encode()))

    # --- bounds --------------------------------------------------------------------
    def _enforce(self, W):
        D = np.where(self.mask, W - self.W0, 0.0)
        D = np.where(np.isfinite(D), D, 0.0)          # never let a NaN/inf through the caps
        lim = self.edge_cap * self.W0
        D = np.clip(D, -lim, lim)
        rel = np.linalg.norm(D) / self._w0_norm
        if rel > self.total_cap:
            D *= self.total_cap / rel
        return self.W0 + D

    # --- wake-time Hebbian rule ----------------------------------------------------
    def hebbian(self, act, dt, stage="AWAKE"):
        """One wake-time update from the activity vector act (n,) over dt seconds. No-op unless stage == AWAKE."""
        a = np.abs(np.asarray(act)).astype(float)    # abs before the cast keeps |z| for complex activity
        dt = float(dt)
        if stage != "AWAKE" or a.shape != (self.n,) or not np.all(np.isfinite(a)) or not (np.isfinite(dt) and dt > 0):
            return self.W                             # sleep, or invalid input: no update
        if self.abar is None:
            self.abar = a.copy()
        c = a - self.abar
        k = min(1.0, dt / self.mean_tau)
        self.abar += k * (a - self.abar)
        dW = self.eta * dt * np.outer(c, c) - min(1.0, dt / self.tau) * (self.W - self.W0)
        dW = 0.5 * (dW + dW.T)
        self.W = self._enforce(self.W + np.where(self.mask, dW, 0.0))
        return self.W

    # --- one memory a day -------------------------------------------------------------
    def record_response(self, t, text, regions, strength):
        """Remember an accepted chat message's brain response until tonight's REM. regions: names or indices of
        the co-activated regions. Nothing about the sender is stored (the caller must not pass it)."""
        idx = [self._index(r) for r in regions]
        s = float(strength)
        self.pending.append({"id": uuid.uuid4().hex, "t": float(t), "message": str(text),
                             "regions": sorted(set(idx)), "strength": s if np.isfinite(s) else 0.0})
        self._save_pending()

    def _index(self, r):
        if isinstance(r, (int, np.integer)) and not isinstance(r, (bool, np.bool_)):
            i = int(r)
            if not 0 <= i < self.n:
                raise ValueError(f"region index {i} out of range 0..{self.n - 1}")
            return i
        return self.names.index(str(r))

    def consolidate(self, day):
        """REM, once per night: strengthen existing edges among the strongest response's regions by a small
        fixed relative amount, append a record to data/memories.json. Returns the record or None.
        At most one memory per `day`: a second call for a day that already has one returns None and keeps the
        pending responses for the next night. Crash safety: weights.npz (holding the new W, the record and the
        ids of the consumed responses) is written first and is the commit point; _repair() finishes the
        memories / pending writes on the next start if the process died in between."""
        mem = self._read_memories()
        if any(m.get("day") == str(day) for m in mem):
            return None
        pend = list(self.pending)
        if not pend:
            return None
        win = max(pend, key=lambda r: r["strength"])
        idx = np.array(win["regions"], dtype=int)
        sel = np.zeros((self.n, self.n), dtype=bool)
        if idx.size:
            sel[np.ix_(idx, idx)] = True
        sel &= self.mask
        self.W = self._enforce(np.where(sel, self.W * (1.0 + self.delta), self.W))
        rec = {"n": len(mem) + 1, "day": str(day), "message": win["message"],
               "regions": [self.names[i] for i in idx], "delta": self.delta, "sha256": weights_sha256(self.W)}
        self._last_rec, self._consumed = rec, [str(r.get("id")) for r in pend if r.get("id")]
        self.save()                                       # commit point
        mem.append(rec)
        _atomic_write(self.memories_path, lambda f: f.write(json.dumps(mem, indent=1).encode()))
        used = {id(r) for r in pend}
        self.pending = [r for r in self.pending if id(r) not in used]
        self._save_pending()
        self.publish_hash(rec)
        return rec

    def _read_memories(self):
        if not self.memories_path.exists():
            return []
        try:
            mem = json.loads(self.memories_path.read_text())
            if isinstance(mem, list):
                return mem
        except Exception:
            pass
        bad = self.memories_path.with_name(f"memories.unreadable-{uuid.uuid4().hex[:8]}.json")
        os.replace(self.memories_path, bad)          # never silently overwrite an unreadable log
        warnings.warn(f"plasticity: {self.memories_path} was unreadable, moved to {bad.name}")
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
