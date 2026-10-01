"""Whole-brain model of the MyConnectome brain.

Each region is a Stuart-Landau (Hopf) oscillator near its bifurcation, coupled
through the subject's structural connectome with conduction delays from fibre
lengths. External stimuli (e.g. market events) are injected into named groups
of regions. This simulates large-scale activity rhythms only - not thoughts,
memories or consciousness.

Two layers:
- fast (this class): ~10 Hz delayed Stuart-Landau oscillators, for the live display. On its own it does NOT reproduce
  the subject's functional connectivity (held-out FC r ~ 0.02, same as randomised wiring; docs/real_wiring_report.md).
- slow (twin/hopf.py SlowLayer, on by default when twin/data/slow_layer.npz exists): the BOLD-band Hopf model fitted
  on half of the subject's resting-state runs (global coupling, then effective connectivity on his anatomical +
  homotopic edges) and scored on the other half. It generates the spontaneous slow fluctuations and modulates the fast
  layer's excitability, the role that replaying the recorded fMRI (real_baseline.py, now optional) used to play.
"""
import copy
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent

# Schaefer 7-network groups + subcortical nuclei used as stimulus targets
GROUPS = {
    "visual": ["_Vis_"],
    "somatomotor": ["_SomMot_"],
    "attention": ["_DorsAttn_"],
    "salience": ["_SalVentAttn_"],
    "limbic": ["_Limbic_"],
    "control": ["_Cont_"],
    "default": ["_Default_"],
    "reward": ["Accumbens", "Caudate", "Putamen"],
    "fear": ["Amygdala"],
    "insula": ["_SalVentAttn_FrOperIns"],   # anterior insula / frontal operculum proxy (interoception, twin/body.py)
    "memory": ["Hippocampus"],
    "relay": ["Thalamus"],
}
# chat messages: left-hemisphere temporal + frontal-operculum parcels (language proxy)
LANGUAGE = lambda nm: "_LH_" in nm and ("Temp" in nm or "FrOper" in nm)


SLOW_DRIVE = 1.6       # excitability per z-unit of the slow layer (same scale as the replayed recording used)


class Brain:
    def __init__(self, path=HERE / "out" / "connectome.npz", f_hz=10.0, a=-5.0, g=5.0,
                 velocity_m_s=6.0, noise=0.5, dt=1e-3, seed=0, slow=True):
        z = np.load(path, allow_pickle=True)
        W = z["weights"].astype(float)
        n0 = min(W.shape[0], len(z["names"]))
        keep = np.where(W[:n0, :n0].sum(1) > 0)[0]      # drop regions no fibre reached (signal dropout)
        W = W[np.ix_(keep, keep)]
        W = np.log1p(W)                      # compress streamline counts
        W /= W.sum(1).mean()                 # normalise mean in-strength to 1
        self.W = W
        self.names = [str(z["names"][i]) for i in keep]
        self.centroids = z["centroids"][keep]
        self.n = len(self.names)
        L = z["lengths"][np.ix_(keep, keep)]
        L = np.where(L > 0, L, np.nanmean(L[L > 0]))
        self.delay = np.round(L / 1000.0 / velocity_m_s / dt).astype(int)  # mm -> steps
        self.hist = int(self.delay.max()) + 1
        self.dt, self.a, self.g, self.noise = dt, a, g, noise
        self.g0 = g
        rng = np.random.default_rng(seed)
        self.rng = rng
        # small per-region frequency spread around f_hz (5 %, i.e. 0.5 Hz at 10 Hz)
        self.df = rng.normal(0, 0.05, self.n)
        self.f_hz = f_hz
        self.omega = 2 * np.pi * f_hz * (1 + self.df)
        self.buf = (rng.normal(0, 0.1, (self.hist, self.n)) + 1j * rng.normal(0, 0.1, (self.hist, self.n)))
        self.t = 0
        self.stim = np.zeros(self.n)
        self.drive = np.zeros(self.n)        # slow drive from recorded real activity (RealBaseline), not decayed
        self.group_idx = {k: [i for i, nm in enumerate(self.names) if any(p in nm for p in pats)]
                          for k, pats in GROUPS.items()}
        self.group_idx["language"] = [i for i, nm in enumerate(self.names) if LANGUAGE(nm)]
        self._cols = np.arange(self.n)[None, :]
        # slow layer: spontaneous BOLD-band activity from the fitted Hopf model (None if not fitted / disabled)
        self.slow, self.slow_gain = None, 1.0
        self.slow_x = np.zeros(self.n)
        self.neuromod = np.zeros(self.n)     # excitability from neuromodulator levels x receptor maps (twin/neurochem.py)
        if slow and (HERE / "twin" / "data" / "slow_layer.npz").exists():
            from twin.hopf import SlowLayer
            self.slow = SlowLayer(seed=seed)
            pos = {nm: i for i, nm in enumerate(self.slow.names)}
            self._slow_idx = np.array([pos[nm] for nm in self.names])
        self.slow_on = self.slow is not None

    def stimulate(self, group, amount):
        """Add drive to a group of regions; it decays with a ~2 s time constant."""
        self.stim[self.group_idx[group]] += amount

    def set_rhythm(self, f_hz, coupling=1.0, noise=None):
        """Change the global rhythm (used by the sleep engine): frequency, coupling x baseline, noise."""
        self.f_hz = f_hz
        self.omega = 2 * np.pi * f_hz * (1 + self.df)
        self.g = self.g0 * coupling
        if noise is not None:
            self.noise = noise

    def step(self, k=1):
        dt = self.dt
        for _ in range(k):
            now = self.t % self.hist
            z = self.buf[now]
            zd = self.buf[(self.t - self.delay) % self.hist, self._cols]      # z_j(t - tau_ij)
            coupling = self.g * ((self.W * zd).sum(1) - self.W.sum(1) * z)
            if self.slow_on and self.t % 100 == 0:                     # slow layer: every 100 steps (0.1 s)
                self.slow_x = SLOW_DRIVE * self.slow_gain * np.clip(
                    self.slow.advance(100 * dt)[self._slow_idx], -2.0, 3.0)
            a_eff = self.a + self.stim + self.drive + self.slow_x + self.neuromod                 # stimulus pushes toward oscillation
            # exponential integrator for the local dynamics (explicit Euler would
            # inflate the fast rotation), coupling and noise added explicitly
            local = np.exp((a_eff + 1j * self.omega - np.abs(z) ** 2) * dt)
            noise = self.noise * np.sqrt(dt) * (self.rng.normal(size=self.n) + 1j * self.rng.normal(size=self.n))
            self.t += 1
            self.buf[self.t % self.hist] = z * local + dt * coupling + noise
            self.stim *= np.exp(-dt / 2.0)
        return self.buf[self.t % self.hist]

    def run(self, seconds, every=10):
        """Simulate and return real part (EEG-like signal) sampled every `every` steps."""
        out = []
        for _ in range(int(seconds / self.dt / every)):
            out.append(self.step(every).real.copy())
        return np.array(out)

    def clone(self):
        """Independent copy of the dynamic state (history buffer, stimulus, drives, slow layer, random stream) that
        shares the fixed wiring arrays: used to try out a stimulus without touching the live brain (brain_vote.py)."""
        self.lag_coupling()                                   # built once on the live brain, shared read-only
        c = copy.copy(self)
        c.buf, c.stim, c.drive, c.slow_x = self.buf.copy(), self.stim.copy(), self.drive.copy(), self.slow_x.copy()
        c.neuromod = self.neuromod.copy()
        c.omega = self.omega.copy()
        c.rng = copy.deepcopy(self.rng)
        c.slow = copy.deepcopy(self.slow) if self.slow is not None else None
        return c

    def lag_coupling(self):
        """Sparse M with coupling_i = sum_j W_ij z_j(t - d_ij) = M @ H.ravel(), H[d] = z(t - d): the same delayed
        coupling as step(), as one sparse product that many clones can share (built once, ~46k entries)."""
        if getattr(self, "_lagM", None) is None:
            import scipy.sparse as sp
            n = self.n
            rows, cols = np.repeat(np.arange(n), n), np.tile(np.arange(n), n)
            self._lagM = sp.csr_matrix((self.W.reshape(-1), (rows, self.delay.reshape(-1) * n + cols)),
                                       shape=(n, self.hist * n))
        return self._lagM

    def use_slow_layer(self, on):
        """Switch the fitted slow layer on/off (off while replaying a real recorded session through `drive`)."""
        self.slow_on = bool(on) and self.slow is not None
        if not self.slow_on:
            self.slow_x = np.zeros(self.n)

    def state(self):
        z = self.buf[self.t % self.hist]
        amp = np.abs(z)
        sync = float(np.abs(np.mean(np.exp(1j * np.angle(z)))))
        return {k: float(amp[i].mean()) for k, i in self.group_idx.items()} | {"sync": sync}


if __name__ == "__main__":
    b = Brain()
    print(f"{b.n} regions, max delay {b.hist} ms")
    for g in b.group_idx:
        print(f"  {g:12s} {len(b.group_idx[g])} regions")
    base = b.run(5)
    s0 = b.state()
    b.stimulate("reward", 12)
    b.stimulate("visual", 8)
    after = b.run(2)
    s1 = b.state()
    print("baseline -> after 'buy' stimulus (mean amplitude)")
    for k in s0:
        print(f"  {k:12s} {s0[k]:.3f} -> {s1[k]:.3f}")
