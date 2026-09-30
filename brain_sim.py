"""Whole-brain model of the MyConnectome brain.

Each region is a Stuart-Landau (Hopf) oscillator near its bifurcation, coupled
through the subject's structural connectome with conduction delays from fibre
lengths. External stimuli (e.g. market events) are injected into named groups
of regions. This simulates large-scale activity rhythms only - not thoughts,
memories or consciousness.
"""
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
    "memory": ["Hippocampus"],
    "relay": ["Thalamus"],
}


class Brain:
    def __init__(self, path=HERE / "out" / "connectome.npz", f_hz=10.0, a=-5.0, g=5.0,
                 velocity_m_s=6.0, noise=0.5, dt=1e-3, seed=0):
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
        rng = np.random.default_rng(seed)
        self.rng = rng
        # small per-region frequency spread around f_hz
        self.omega = 2 * np.pi * (f_hz + rng.normal(0, 0.5, self.n))
        self.buf = (rng.normal(0, 0.1, (self.hist, self.n)) + 1j * rng.normal(0, 0.1, (self.hist, self.n)))
        self.t = 0
        self.stim = np.zeros(self.n)
        self.group_idx = {k: [i for i, nm in enumerate(self.names) if any(p in nm for p in pats)]
                          for k, pats in GROUPS.items()}
        self._cols = np.arange(self.n)[None, :]

    def stimulate(self, group, amount):
        """Add drive to a group of regions; it decays with a ~2 s time constant."""
        self.stim[self.group_idx[group]] += amount

    def step(self, k=1):
        dt = self.dt
        for _ in range(k):
            now = self.t % self.hist
            z = self.buf[now]
            zd = self.buf[(self.t - self.delay) % self.hist, self._cols]      # z_j(t - tau_ij)
            coupling = self.g * ((self.W * zd).sum(1) - self.W.sum(1) * z)
            a_eff = self.a + self.stim                                           # stimulus pushes toward oscillation
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
