"""SUB-01 v2 neural mass model: delayed Wilson-Cowan E/I network on one person's connectome + BOLD.

This is a digital twin *model* of one real person's brain structure and recorded activity (MyConnectome,
OpenNeuro ds000031, public domain). It simulates population firing rates of 214 regions; it is not a mind,
not conscious and not the person. Full write-up: docs/twin/model.md.

Local dynamics (one excitatory E_k and one inhibitory I_k population per region k), Wilson & Cowan (1972,
Biophys J 12:1-24) in the form used for whole-brain MEG modelling by Abeysuriya et al. (2018, PLoS Comput
Biol 14:e1006007), plus a slow spike-frequency-adaptation variable A_k that is weak in wakefulness and grows
in NREM sleep (low acetylcholine unblocks K+ adaptation currents; McCormick 1992, Prog Neurobiol 39:337):

    tau_E dE_k/dt = -E_k + S_E( c_EE E_k + c_IE,k I_k - b_A A_k + P + p_k + h_k + dP(a)
                               + G sum_j W_kj E_j(t - L_kj / v) + gate(a) u_k(t) )  + tau_E sigma xi_k(t)
    tau_I dI_k/dt = -I_k + S_I( c_EI E_k + c_II I_k + Q )
    tau_A dA_k/dt = -A_k + E_k
    S_X(x) = 1 / (1 + exp(-beta g_k (x - theta)))            g_k = set_gain() vector (1 = baseline)

(xi: unit white noise; in code dE gets + sigma sqrt(dt) N(0,1) per step. Integration: stochastic Heun, dt = 1 ms.)

Local E/I balance: c_IE,k is set so that every region sits at the target excitatory rate rho at rest, i.e. the
fixed point that the inhibitory synaptic plasticity rule of Vogels et al. (2011, Science 334:1569),
dc_IE/dt = eta I (E - rho), converges to (Hellyer et al. 2016, PLoS Comput Biol 12:e1004720; Abeysuriya 2018).
It is solved analytically instead of simulated (no warm-up cost). Option isp_frac < 1 leaves part of the mean
long-range input to a homeostatic intrinsic offset h_k instead (default isp_frac = 1, h_k = 0).

Sleep / live inputs: the sleep engine's a (-5 awake/REM ... 0 deep NREM) sets depth d = (a + 5) / 5, which scales
an excitability offset dP = p_nrem d, the adaptation strength b_A = b_wake + (b_nrem - b_wake) d and a thalamic
gate on external input gate = 1 - (1 - gate_nrem) d. set_rhythm(f, coupling, noise) multiplies G by coupling and
scales sigma by noise / 0.5; f is not imposed (rhythms are emergent). u_k = stimuli (decay 2 s) + recorded drive.

Hemodynamics: Balloon-Windkessel model (Buxton et al. 1998; Friston et al. 2000, NeuroImage 12:466) with the
revised BOLD output equation and parameter values of Stephan et al. (2007, NeuroImage 38:387) as implemented in
SPM12 (spm_fx_fmri.m / spm_gx_fmri.m): kappa=0.64/s, gamma=0.32/s, tau=2 s, alpha=0.32, E0=0.4, V0=4 %,
epsilon=1, nu0=40.3/s, r0=25/s, TE=0.04 s; states integrated in log space (Stephan et al. 2008, NeuroImage
42:649). Neural input u = bold_gain (E / rho - 1), averaged over 10 ms (the fractional change of the rate).

Conduction delays: L_kj (mm, tractography streamline length) / v (m/s), rounded to dt. The delayed coupling is one
sparse mat-vec per step over a "doubled" ring buffer, so every delay window is a contiguous view and each of the
20k fibre edges keeps its own delay (no delay binning, no per-region Python loops).

What is not realistic is listed in docs/twin/model.md (lumped populations, one E/I pair per parcel, no thalamic
nucleus dynamics, sleep and neuromodulation as parameter changes, display transform, ...).
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path

import numpy as np
from scipy import sparse

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PARAMS_PATH = HERE / "params.json"

# ---------------------------------------------------------------------------------------------------------
# parameters (units in comments). Local E/I values: Abeysuriya et al. 2018 (Table 1); see docs/twin/model.md
# ---------------------------------------------------------------------------------------------------------
DEFAULTS = dict(
    # local Wilson-Cowan node
    tau_e=0.010,        # s, excitatory time constant
    tau_i=0.020,        # s, inhibitory time constant
    c_ee=3.5,           # E->E local coupling (dimensionless)
    c_ei=3.75,          # E->I local coupling
    c_ii=-1.0,          # I->I local coupling
    P=0.31,             # constant background input to E
    Q=0.0,              # constant background input to I
    beta=4.0,           # sigmoid slope
    theta=1.0,          # sigmoid threshold
    rho=0.14,           # target excitatory rate at rest (0..1); Abeysuriya 2018 used 0.15, see docs
    isp_frac=1.0,       # share of the mean long-range input balanced by inhibition (rest: intrinsic excitability)
    isp_seconds=0.0,    # >0: refine c_IE at construction by simulating the Vogels 2011 rule for this long (awake rest)
    isp_eta=300.0,      # learning rate of that rule, dc_IE/dt = -eta I (E - rho)  (1/s, rate units)
    # slow adaptation (small in wake, strong in deep NREM)
    tau_a=0.25,         # s, adaptation time constant
    b_wake=0.0,         # adaptation strength when awake (a = -5)
    b_nrem=3.0,         # adaptation strength in deep NREM (a = 0)
    p_nrem=-0.15,       # excitability offset in deep NREM (lower ACh/NE tone), input units
    # network
    sc_power=1.0,       # streamline counts ** sc_power before the symmetric degree normalisation
    G=3.0,              # global long-range coupling (on the degree-normalised weights, leading eigenvalue 1)
    velocity=6.0,       # m/s conduction velocity
    noise=0.06,         # sigma of the E noise, rate units / sqrt(s) (awake reference; set_rhythm scales it)
    # inputs from the live server
    stim_gain=0.08,     # input units per old-model stimulus unit
    stim_max=20.0,      # old-model stimulus units where the stimulus input saturates (tanh)
    stim_tau=2.0,       # s, decay of stimuli (same as brain_sim)
    drive_gain=0.08,    # input units per old-model drive unit (live server: 1.6 per z-unit of recorded signal)
    gate_nrem=0.5,      # fraction of external input that still reaches cortex in deep NREM (thalamic gating)
    # integration / display
    dt=0.001,           # s, stochastic Heun step
    bold_every=10,      # hemodynamics updated every this many steps (10 ms)
    act_rest=0.75,      # display activity at the resting rate rho
    bold_gain=0.25,     # neurovascular input per unit fractional rate change (u = bold_gain (E - rho) / rho)
)
# Balloon-Windkessel / BOLD constants (SPM12 spm_fx_fmri.m + spm_gx_fmri.m; Stephan et al. 2007)
HEMO = dict(kappa=0.64, gamma=0.32, tau=2.0, alpha=0.32, E0=0.4, V0=4.0, eps=1.0, nu0=40.3, r0=25.0, TE=0.04)
SLEEP_NOISE_REF = 0.5   # sleep.py AWAKE noise; set_rhythm(noise=x) -> sigma = noise_param * x / 0.5


def load_params(path=PARAMS_PATH, overrides=None):
    """DEFAULTS <- twin/params.json (when present; written by the fit) <- overrides."""
    p = dict(DEFAULTS)
    path = Path(path) if path else None
    if path is not None and path.exists():
        try:
            d = json.loads(path.read_text())
            d = d.get("params", d) if isinstance(d, dict) else {}
            p.update({k: v for k, v in d.items() if k in DEFAULTS or k in ("excitability", "c_ie")})
        except (OSError, ValueError):
            pass
    if overrides:
        p.update(overrides)
    return p


def load_connectome(path=ROOT / "out" / "connectome.npz", sc_power=None):
    """Model-space weights from streamline counts C (all 214 regions kept, zero diagonal):

        W = C**sc_power / sqrt(s_i s_j),   s_i = sum_j C_ij**sc_power

    symmetric degree normalisation (leading eigenvalue exactly 1; W stays symmetric). See docs/twin/model.md for
    why this and not brain_sim's log1p + mean in-strength (it keeps more of the connectome's structure)."""
    z = np.load(path, allow_pickle=True)
    p = DEFAULTS["sc_power"] if sc_power is None else sc_power
    C = z["weights"].astype(float)
    np.fill_diagonal(C, 0.0)
    C = C ** p
    s = C.sum(1)
    s = np.where(s > 0, s, 1.0)
    W = C / np.sqrt(np.outer(s, s))
    L = z["lengths"].astype(float)
    L = np.where(L > 0, L, np.nanmean(L[L > 0]))
    return W, L, [str(x) for x in z["names"]], np.asarray(z["centroids"], float)


def sigmoid(x, beta, theta):
    return 1.0 / (1.0 + np.exp(-beta * (x - theta)))


def heun_step(E, I, A, net, dn, bg, cie, ba, p, dt):
    """One stochastic-Heun step of the local E/I/A equations (any array shape).

    net: everything entering the E sigmoid besides local terms (background + delayed long-range + external);
    it is held fixed over the step (all conduction delays are >= 1 step). dn: additive noise increment."""
    ce, ci, cii, Q, th = p["c_ee"], p["c_ei"], p["c_ii"], p["Q"], p["theta"]
    ke, ki, ka = dt / p["tau_e"], dt / p["tau_i"], dt / p["tau_a"]
    fe = 1.0 / (1.0 + np.exp(-bg * (ce * E + cie * I - ba * A + net - th))) - E
    fi = 1.0 / (1.0 + np.exp(-bg * (ci * E + cii * I + Q - th))) - I
    fa = E - A
    E1 = E + ke * fe + dn
    I1 = I + ki * fi
    A1 = A + ka * fa
    fe1 = 1.0 / (1.0 + np.exp(-bg * (ce * E1 + cie * I1 - ba * A1 + net - th))) - E1
    fi1 = 1.0 / (1.0 + np.exp(-bg * (ci * E1 + cii * I1 + Q - th))) - I1
    E = np.clip(E + 0.5 * ke * (fe + fe1) + dn, 0.0, 1.0)
    I = I + 0.5 * ki * (fi + fi1)
    A = A + 0.5 * ka * (fa + E1 - A1)
    return E, I, A


def phase_scale(p, c_ie, i_star):
    """|v_E| / |v_I| of the oscillatory eigenvector of the local Jacobian at rest (for a round E/I phase plane)."""
    rho, beta = p["rho"], p["beta"]
    de, di = beta * rho * (1 - rho), beta * i_star * (1 - i_star)
    J = np.array([[(-1 + de * p["c_ee"]) / p["tau_e"], de * float(np.mean(c_ie)) / p["tau_e"]],
                  [di * p["c_ei"] / p["tau_i"], (-1 + di * p["c_ii"]) / p["tau_i"]]])
    w, v = np.linalg.eig(J)
    v = v[:, int(np.argmax(w.imag))]
    return float(abs(v[0]) / max(abs(v[1]), 1e-12)) if abs(w.imag).max() > 0 else 1.0


def balance(p, W, G, excitability=0.0, b_a=None):
    """Inhibitory weights c_IE (per region) that put E at rho with I at its matching fixed point.

    Steady state of Vogels et al. 2011 inhibitory plasticity (E -> rho) for the deterministic system at rest.
    G may be an array broadcasting against the region axis (batched)."""
    rho, beta, th = p["rho"], p["beta"], p["theta"]
    b_a = p["b_wake"] if b_a is None else b_a
    lo, hi = 0.0, 1.0                            # I* = S(c_EI rho + c_II I* + Q): monotone, bisection
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if mid - sigmoid(p["c_ei"] * rho + p["c_ii"] * mid + p["Q"], beta, th) > 0:
            hi = mid
        else:
            lo = mid
    i_star = 0.5 * (lo + hi)
    x_star = th + math.log(rho / (1 - rho)) / beta
    net = G * W.sum(1) * rho                     # mean long-range input at rest (n,)
    phi = p["isp_frac"]                          # share of it compensated by inhibition (rest: intrinsic offset)
    c_ie = (x_star - p["c_ee"] * rho - p["P"] - excitability - phi * net + b_a * rho) / i_star
    return np.minimum(c_ie, 0.0), i_star, -(1.0 - phi) * net


class _DelayNet:
    """Delayed network input for B parameter sets at once: one sparse mat-vec per step.

    Ring buffer of length 2H (each sample written twice), so the last H samples are always the contiguous view
    buf[s:s+H]; column index of edge (b, i<-j) = (H-1-d_bij) * (B n) + b n + j is then time independent."""

    def __init__(self, W, L, velocity, dt, B=1, init=0.0):
        n = W.shape[-1]
        Ws = np.broadcast_to(W, (B, n, n))
        v = np.broadcast_to(np.asarray(velocity, float), (B,))
        d = [np.maximum(np.round(L / 1000.0 / v[b] / dt).astype(int), 1) for b in range(B)]
        self.H = H = int(max(dd[Ws[b] > 0].max() if (Ws[b] > 0).any() else 1 for b, dd in enumerate(d))) + 1
        rows, cols, vals = [], [], []
        for b in range(B):                       # B iterations at construction only
            i, j = np.nonzero(Ws[b])
            rows.append(b * n + i)
            cols.append((H - 1 - d[b][i, j]) * (B * n) + b * n + j)
            vals.append(Ws[b][i, j])
        self.M = sparse.csr_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))),
                                   shape=(B * n, H * B * n))
        self.delays = d
        self.B, self.n = B, n
        self.buf = np.empty((2 * H, B * n))
        self.buf[:] = np.asarray(init, float).reshape(-1) if np.ndim(init) else init
        self.pos = 0                             # index of the newest sample

    def delayed_input(self):
        s = self.pos + 1                         # window rows s..s+H-1 = times now-H+1 .. now
        return (self.M @ self.buf[s:s + self.H].reshape(-1)).reshape(self.B, self.n)

    def push(self, e):
        self.pos = (self.pos + 1) % self.H
        flat = e.reshape(-1)
        self.buf[self.pos] = flat
        self.buf[self.pos + self.H] = flat


class Balloon:
    """Balloon-Windkessel hemodynamics in log space (SPM12 / Stephan 2007-2008), any array shape."""

    def __init__(self, shape, h=HEMO):
        self.h = dict(h)
        self.s = np.zeros(shape)
        self.lf = np.zeros(shape)
        self.lv = np.zeros(shape)
        self.lq = np.zeros(shape)
        h = self.h
        self.k1 = 4.3 * h["nu0"] * h["E0"] * h["TE"]
        self.k2 = h["eps"] * h["r0"] * h["E0"] * h["TE"]
        self.k3 = 1.0 - h["eps"]

    def step(self, u, dt):
        h = self.h
        f, v, q = np.exp(self.lf), np.exp(self.lv), np.exp(self.lq)
        fv = v ** (1.0 / h["alpha"])
        ff = (1.0 - (1.0 - h["E0"]) ** (1.0 / f)) / h["E0"]
        ds = u - h["kappa"] * self.s - h["gamma"] * (f - 1.0)
        self.lf += dt * self.s / f
        self.lv += dt * (f - fv) / (h["tau"] * v)
        self.lq += dt * (ff * f - fv * q / v) / (h["tau"] * q)
        self.s += dt * ds
        for x in (self.lf, self.lv, self.lq):          # keep far outside the physiological range from diverging
            np.clip(x, -3.0, 3.0, out=x)

    def bold(self):
        v, q = np.exp(self.lv), np.exp(self.lq)
        return self.h["V0"] * (self.k1 * (1 - q) + self.k2 * (1 - q / v) + self.k3 * (1 - v))   # percent


class TwinBrain:
    """Drop-in for brain_sim.Brain driven by live_server.py (see docs/twin_contracts.md)."""

    def __init__(self, path=ROOT / "out" / "connectome.npz", params=None, seed=0, params_path=PARAMS_PATH, **kw):
        p = load_params(params_path, {**(params or {}), **kw})
        self.p = p
        W, L, names, cen = load_connectome(path, p["sc_power"])
        self.W0 = W.copy()
        self.W = W.copy()
        self.L = L
        self.names, self.centroids, self.n = names, cen, len(names)
        self.dt = float(p["dt"])
        self.t = 0
        self.rng = np.random.default_rng(seed)
        from brain_sim import GROUPS, LANGUAGE   # same stimulus groups as the old model (+ language)
        self.group_idx = {k: [i for i, nm in enumerate(self.names) if any(s in nm for s in pats)]
                          for k, pats in GROUPS.items()}
        self.group_idx["language"] = [i for i, nm in enumerate(self.names) if LANGUAGE(nm)]
        ex = p.get("excitability")
        self.excitability = np.zeros(self.n) if ex is None else np.asarray(ex, float).reshape(self.n)
        self.G0 = float(p["G"])
        self.G = self.G0
        self.sigma0 = float(p["noise"])
        self.sigma = self.sigma0
        self.f_hz = 10.0
        self.gain = np.ones(self.n)
        self.stim = np.zeros(self.n)
        self.drive = np.zeros(self.n)
        self._a = -5.0
        self._depth = 0.0
        self.c_ie, self.i_star, self.p_home = balance(p, self.W, self.G0, self.excitability)
        if p.get("c_ie") is not None:                           # precomputed (e.g. refined by the fit)
            self.c_ie = np.asarray(p["c_ie"], float).reshape(self.n)
        elif p["isp_seconds"] > 0:
            self.c_ie = isp_refine(p, self.W, p["isp_seconds"], seed=seed, path=path)
        rho = p["rho"]
        self.E = np.full(self.n, rho) + 0.01 * self.rng.standard_normal(self.n)
        self.I = np.full(self.n, self.i_star)
        self.A = np.full(self.n, rho)
        self.net = _DelayNet(self.W, L, p["velocity"], self.dt, 1, init=self.E)
        self.hemo = Balloon(self.n)
        self._u_acc = np.zeros(self.n)
        self._u_k = 0
        self.E_slow = self.E.copy()
        self.I_slow = self.I.copy()
        self._x = np.zeros(self.n)
        self._noise = np.empty((0, self.n))
        self._ni = 0
        self._stim_decay = math.exp(-self.dt / p["stim_tau"])
        self._iscale = phase_scale(p, self.c_ie, self.i_star)
        self._slow_a = self.dt / 1.0                               # 1 s low-pass for the display phase centre
        self.a = -5.0

    # --- sleep engine / neuromodulation hooks --------------------------------------------------------------
    @property
    def a(self):
        return self._a

    @a.setter
    def a(self, value):
        """Sleep engine value (-5 awake/REM ... 0 deep NREM) -> depth d in 0..1 -> excitability offset + adaptation."""
        self._a = float(value)
        d = min(1.0, max(0.0, (self._a + 5.0) / 5.0))
        self._depth = d
        self.b_a = self.p["b_wake"] + (self.p["b_nrem"] - self.p["b_wake"]) * d
        self.p_off = self.p["p_nrem"] * d
        self.gate = 1.0 - (1.0 - self.p["gate_nrem"]) * d

    def set_rhythm(self, f_hz, coupling=1.0, noise=None):
        """coupling multiplies G; noise sets sigma relative to the awake reference (0.5 in sleep.py).
        f_hz is stored but not imposed: rhythms emerge from the E/I time constants and adaptation."""
        self.f_hz = f_hz
        self.G = self.G0 * coupling
        if noise is not None:
            self.sigma = self.sigma0 * noise / SLEEP_NOISE_REF

    def set_gain(self, g):
        """Per-region multiplicative gain on the sigmoid slope (neuromodulatory gain); ones = fitted baseline."""
        self.gain = np.clip(np.broadcast_to(np.asarray(g, float), (self.n,)).copy(), 0.05, 10.0)

    def set_weights(self, W, rebalance=True):
        """Replace model-space weights (same normalisation as self.W). rebalance=True re-solves the inhibitory
        balance at the baseline coupling (slow homeostatic plasticity assumed converged)."""
        W = np.asarray(W, float)
        assert W.shape == (self.n, self.n)
        self.W = W.copy()
        hist = self.net.buf.copy()
        pos = self.net.pos
        self.net = _DelayNet(self.W, self.L, self.p["velocity"], self.dt, 1)
        if self.net.H * 2 == hist.shape[0]:
            self.net.buf[:] = hist
            self.net.pos = pos
        else:
            self.net.buf[:] = self.E
        if rebalance:
            self.c_ie, _, self.p_home = balance(self.p, self.W, self.G0, self.excitability)

    def stimulate(self, group, amount):
        """Add drive to a group of regions; it decays with a ~2 s time constant (like brain_sim)."""
        self.stim[self.group_idx[group]] += amount

    # --- integration ----------------------------------------------------------------------------------------
    def _noise_row(self):
        if self._ni >= len(self._noise):
            self._noise = self.rng.standard_normal((1000, self.n))
            self._ni = 0
        r = self._noise[self._ni]
        self._ni += 1
        return r

    def _external(self):
        p = self.p
        sm = p["stim_max"]
        return self.gate * (p["stim_gain"] * sm * np.tanh(self.stim / sm) + p["drive_gain"] * self.drive)

    def step(self, k=1):
        """Advance k steps of dt; returns the display signal x (n,) (see docs: |x| ~ activity, x oscillates)."""
        p = self.p
        dt = self.dt
        bg = p["beta"] * self.gain
        sq = self.sigma * math.sqrt(dt)
        base = p["P"] + self.excitability + self.p_home + self.p_off + self._external()  # constant in a call
        E, I, A = self.E, self.I, self.A
        cie, ba, G = self.c_ie, self.b_a, self.G
        for _ in range(k):
            net = base + G * self.net.delayed_input()[0]
            E, I, A = heun_step(E, I, A, net, sq * self._noise_row(), bg, cie, ba, p, dt)
            self.net.push(E)
            self._u_acc += E
            self._u_k += 1
            if self._u_k == p["bold_every"]:
                self.hemo.step(p["bold_gain"] * (self._u_acc / (self._u_k * p["rho"]) - 1.0), self._u_k * dt)
                self._u_acc[:] = 0.0
                self._u_k = 0
            self.t += 1
        self.E, self.I, self.A = E, I, A
        self.stim *= self._stim_decay ** k
        sa = min(1.0, self._slow_a * k)
        self.E_slow += sa * (E - self.E_slow)
        self.I_slow += sa * (I - self.I_slow)
        self._x = self.display()
        return self._x

    # --- read-outs ------------------------------------------------------------------------------------------
    def activity(self):
        """Display activity: excitatory rate relative to rest (act_rest at E = rho), soft-limited to < 2."""
        a = self.p["act_rest"] * self.E / self.p["rho"]
        return 2.0 * np.tanh(a / 2.0)

    def phase(self):
        """Phase of the E/I oscillation around its 1 s running mean."""
        return np.angle((self.E - self.E_slow) + 1j * (self.I - self.I_slow) * self._iscale)

    def display(self):
        """x = activity * cos(E/I phase): |x| follows the rate, x.real oscillates with the model's own rhythm."""
        return self.activity() * np.cos(self.phase())

    def run(self, seconds, every=10):
        """Simulate and return the display signal sampled every `every` steps."""
        return np.array([self.step(every).copy() for _ in range(int(seconds / self.dt / every))])

    def state(self):
        act = self.activity()
        sync = float(np.abs(np.mean(np.exp(1j * self.phase()))))
        return {k: float(act[i].mean()) if i else 0.0 for k, i in self.group_idx.items()} | {"sync": sync}

    def bold(self):
        """Current simulated BOLD signal (percent signal change, n,)."""
        return self.hemo.bold()

    def rates(self):
        return {"E": self.E.copy(), "I": self.I.copy(), "A": self.A.copy()}

    def currents(self):
        """Excitatory and inhibitory input to the E populations now (n,): local E + long-range + background,
        and local inhibition c_IE I (negative); their sum minus adaptation is the sigmoid argument."""
        p = self.p
        exc = p["c_ee"] * self.E + self.G * self.net.delayed_input()[0] + p["P"] + self.excitability + self.p_home
        return {"exc": exc, "inh": self.c_ie * self.I, "adapt": -self.b_a * self.A,
                "external": self.p_off + self._external()}


def isp_refine(p, W=None, seconds=30.0, seed=0, path=ROOT / "out" / "connectome.npz"):
    """Simulate inhibitory synaptic plasticity (Vogels et al. 2011; as in Hellyer 2016 / Abeysuriya 2018),
    tau-free form dc_IE/dt = -eta I (E - rho) with c_IE <= 0 (more inhibition when E is above target), at awake
    rest starting from the analytic balance. Learning rate is annealed (eta, then eta/4 for the second half) and
    c_IE is averaged over the last quarter. Returns c_IE (n,). The noisy, oscillating network has a lower mean
    rate than its fixed point, so this removes the ~15 % shortfall of the analytic balance."""
    p = load_params(None, p)
    W0, L, names, _ = load_connectome(path, p["sc_power"])
    W = W0 if W is None else np.asarray(W, float)
    n = len(names)
    ex = np.zeros(n) if p.get("excitability") is None else np.asarray(p["excitability"], float)
    c_ie, i_star, home = balance(p, W, p["G"], ex)
    dt, rho = float(p["dt"]), p["rho"]
    rng = np.random.default_rng(seed)
    E = rho + 0.01 * rng.standard_normal(n)
    I = np.full(n, i_star)
    A = np.full(n, rho)
    net = _DelayNet(W, L, p["velocity"], dt, 1, init=E)
    base = p["P"] + ex + home
    sq = p["noise"] * math.sqrt(dt)
    steps = int(round(seconds / dt))
    avg = np.zeros(n)
    k_avg = 0
    for it in range(steps):
        if it % 1000 == 0:
            noise = rng.standard_normal((1000, n))
        E, I, A = heun_step(E, I, A, base + p["G"] * net.delayed_input()[0], sq * noise[it % 1000], p["beta"],
                            c_ie, p["b_wake"], p, dt)
        net.push(E)
        eta = p["isp_eta"] * (1.0 if it < steps // 2 else 0.25)
        c_ie = np.minimum(c_ie - dt * eta * I * (E - rho), 0.0)
        if it >= 3 * steps // 4:
            avg += c_ie
            k_avg += 1
    return avg / max(k_avg, 1)


# -------------------------------------------------------------------------------------------------------------
# batched offline simulator for fitting
# -------------------------------------------------------------------------------------------------------------
def simulate_bold(params_list, seconds, tr, seed=0, W=None, burn=20.0, path=ROOT / "out" / "connectome.npz",
                  params_path=PARAMS_PATH, return_rates=False, dtype=np.float32):
    """Simulate B parameter sets together and return BOLD sampled every `tr` s: array (B, T, n), T = seconds // tr.

    params_list: list of dicts overriding the defaults (+ twin/params.json when present), e.g.
    {"G": 0.9, "velocity": 6, "noise": 0.06, "excitability": (n,) array}. Keys that must be shared by all sets
    (time constants, local couplings, dt) are taken from the first set. W: model-space weights (n, n) or
    (B, n, n); default the connectome. `burn` seconds are simulated first and discarded (hemodynamic transient).
    Awake resting state (a = -5, no stimuli, no drive). No per-region Python loops: one sparse mat-vec per step.
    """
    ps = [load_params(params_path, q) for q in params_list]
    p = ps[0]
    B = len(ps)
    W0, L, names, _ = load_connectome(path, p["sc_power"])
    n = len(names)
    Wb = np.broadcast_to(W0 if W is None else np.asarray(W, float), (B, n, n))
    dt = float(p["dt"])
    rng = np.random.default_rng(seed)
    G = np.array([q["G"] for q in ps], float)[:, None]
    sig = np.array([q["noise"] for q in ps], float)[:, None] * math.sqrt(dt)
    ex = np.stack([np.zeros(n) if q.get("excitability") is None else np.asarray(q["excitability"], float)
                   for q in ps])
    bal = [balance(q, Wb[b], q["G"], ex[b]) for b, q in enumerate(ps)]
    cie = np.stack([np.asarray(q["c_ie"], float) if q.get("c_ie") is not None else x[0] for q, x in zip(ps, bal)])
    i_star = bal[0][1]
    base = p["P"] + ex + np.stack([x[2] for x in bal])
    rho = p["rho"]
    E = rho + 0.01 * rng.standard_normal((B, n))
    I = np.full((B, n), i_star)
    A = np.full((B, n), rho)
    net = _DelayNet(Wb if W is not None and np.ndim(W) == 3 else Wb[0], L, [q["velocity"] for q in ps], dt, B,
                    init=E)
    hemo = Balloon((B, n))
    beta = p["beta"]
    b_a = p["b_wake"]
    m = int(p["bold_every"])
    step_tr = tr / dt
    n_burn = int(round(burn / dt))
    T = int(seconds // tr)
    n_total = n_burn + int(math.ceil(T * step_tr))
    out = np.empty((B, T, n), dtype)
    rates = np.zeros((B, n)) if return_rates else None
    acc = np.zeros((B, n))
    k_out = 0
    chunk = 500
    for c0 in range(0, n_total, chunk):
        noise = rng.standard_normal((min(chunk, n_total - c0), B, n))
        for s in range(len(noise)):
            it = c0 + s
            E, I, A = heun_step(E, I, A, base + G * net.delayed_input(), sig * noise[s], beta, cie, b_a, p, dt)
            net.push(E)
            acc += E
            if (it + 1) % m == 0:
                hemo.step(p["bold_gain"] * (acc / (m * rho) - 1.0), m * dt)
                acc[:] = 0.0
            if it >= n_burn:
                if rates is not None:
                    rates += E
                if k_out < T and (it + 1 - n_burn) >= round((k_out + 1) * step_tr):
                    out[:, k_out] = hemo.bold()
                    k_out += 1
    if return_rates:
        return out, rates / max(1, n_total - n_burn)
    return out
