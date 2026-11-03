"""The chair's network: the day network's wiring with adaptation and synaptic time constants, stimulated by visitors.

Same neurons, same synapses, same delays as spiking/live.py's LiveNet (wiring.py, the same seed), so this is the
same brain model with two mechanisms the plain LIF does not have, both in the equations:

  membrane      tau_m dv/dt = -v + mu + s_e - s_i - w + sigma sqrt(tau_m) xi      (mV; rest 0, threshold v_th)
  synapses      tau_e ds_e/dt = -s_e ;  a spike arriving over an excitatory synapse of weight j adds q_e j to s_e
                tau_i ds_i/dt = -s_i ;  ... inhibitory, q_i |j|   (q ~ tau_m / tau: the PSP integral equals LiveNet's jump)
  adaptation    tau_w dw/dt = a v - w ;  at a spike w += b                          (Brette & Gerstner 2005, voltage units)
  spike         v >= v_th: v = v_reset for t_ref, w += b
  stimulus      v[recruited] += amp on the steps where the pulse train is on (bounded, time-limited; see Pulse)

Why these: exponential current synapses (Brunel & Wang 2001: AMPA ~ 2-5 ms, GABA_A ~ 10 ms) give the inputs a time
course instead of instantaneous jumps; the adaptation current (the w of the adaptive exponential integrate-and-fire,
Brette & Gerstner 2005; parameter ranges from Naud et al. 2008) gives spike-frequency adaptation and recovery, so a
second shock meets a network that is still adapted from the first. The exponential term of AdEx is left out on
purpose: the fixed threshold of the existing LIF is kept, which lets dt stay at 1 ms (no stiff term) and keeps the
network comparable with the day network. Units follow spiking/config.py (mV, ms): the AdEx current w is written as
the voltage it would produce through the leak (w / g_L), so b is in mV. Brette & Gerstner's regular-spiking set has
b / g_L = 2.7 mV, a / g_L = 0.13, tau_w = 144 ms; Naud et al.'s adapting set b / g_L = 5 mV, tau_w = 300 ms. tau_w here
is 1 s with b = 1 mV: the slow after-hyperpolarisation end of the measured range (Benda & Herz 2003 review adaptation
time constants from tens of milliseconds to seconds; the slow AHP of cortical pyramidal cells is 1-2 s), chosen so that
shocks a few seconds apart meet a network still adapted from the last one. The mean w at the ~5 Hz baseline is about
5 mV either way (b x rate x tau_w), so the background drive is the same.

Integration: v and w forward Euler (dt / tau_m = 0.05, dt / tau_w = 0.003, both far inside the stable range), the
synaptic variables decay exactly (exp(-dt/tau)) with jumps at arrival, the refractory period is a counter. Nothing
in the equations can run away: inputs are bounded, spikes are limited by the refractory period, w is bounded by
b times the spikes it can collect in a few tau_w. test_chair.py checks that over minutes of stimulation.

What is measured (Measure): population rates in 20 ms bins, overall, excitatory, inhibitory, per group and per
region; the mean adaptation current; a running baseline (mean and spread of each of those in quiet time); and per
stimulus a response card: peak rate against baseline, onset latency, burst, recruitment across regions, the
undershoot after the stimulus, the time back inside the baseline band. All of it is read off the simulation.
Nothing here says what he feels; the body mapping (chair.py Drive) is an artistic reading of these numbers.
"""
import math
import time

import numpy as np

from spiking.live import LiveNet, N_NEURONS
from spiking.config import Config

# --- the mechanisms ---------------------------------------------------------------------------------------------
TAU_E, TAU_I = 5.0, 10.0          # ms, synaptic time constants (AMPA-like, GABA_A-like)
TAU_W, ADAPT_A, ADAPT_B = 1000.0, 0.10, 1.0  # ms; subthreshold a (a / g_L); spike-triggered b in mV (b / g_L)
MU_EXT = 20.0                     # mV, the background drive: raised from LiveNet's 15 to keep ~5 Hz with adaptation on
BIN_MS = 20                       # one measurement bin
SEED = 7

# --- the stimulus ------------------------------------------------------------------------------------------------
# A shock through the clamp: a pulse train on a random subset of the neurons under the electrodes. The head clamp of the
# reference image sits on the crown and the temples, so the montage weights the parcels under it; nuclei deep in the
# brain get little or nothing. This mapping from "a chair electrode" to parcels is an engineering assumption, not an
# electrophysiological model of current flow through a head.
MONTAGE = {"somatomotor": 1.0, "attention": 0.7, "salience": 0.7, "language": 0.6, "control": 0.5, "default": 0.5,
           "visual": 0.3, "limbic": 0.3, "relay": 0.2, "fear": 0.1, "reward": 0.0, "memory": 0.0}
LEVELS = {   # intensity 1-5: pulse amplitude (mV per 1 ms step while on), recruited fraction (times the montage weight), duration
    1: {"amp": 3.0, "frac": 0.10, "dur_ms": 300},
    2: {"amp": 5.0, "frac": 0.20, "dur_ms": 400},
    3: {"amp": 8.0, "frac": 0.30, "dur_ms": 600},
    4: {"amp": 12.0, "frac": 0.45, "dur_ms": 800},
    5: {"amp": 16.0, "frac": 0.60, "dur_ms": 1000},
}
PULSE_HZ, PULSE_WIDTH_MS = 50.0, 2       # the train: 50 pulses a second, each 2 ms (a common clinical range: 20-120 Hz)
# The arrest, a rule of the piece (owner, 2026-11-03), not a mechanism of any neuron: the mean adaptation current is
# averaged over the last LOAD_TAU_S (a measured "load"); when it stays above FLAT_LOAD_RATIO times its quiet level,
# which takes about ten level-5 shocks in a row from one visitor and no amount of level 3 (measured), the background
# drive is cut to zero, so the network's spontaneous activity stops: a flatline that the trace shows as it is. A shock
# of level REVIVE_LEVEL or more restores the drive before its pulse train, and the activity returns. While flat,
# nothing is measured against the baseline and the body hangs.
LOAD_TAU_S = 15.0
FLAT_LOAD_RATIO = 1.45
REVIVE_LEVEL = 3
MAX_DUR_MS = 1000                        # hard bounds the hub also enforces
MAX_AMP = 16.0


def montage_weights(net):
    """Per-region montage weight (0..1) from the group table; a region in several groups takes the largest."""
    w = np.zeros(net.reg.n)
    for g, val in MONTAGE.items():
        for r in net.reg.groups.get(g, []):
            w[r] = max(w[r], val)
    return w


class Pulse:
    """One accepted stimulus: which neurons, how hard, for how long, when the train is on."""

    def __init__(self, net, level, t0, rng):
        p = LEVELS[int(level)]
        self.level = int(level)
        self.amp = np.float32(min(MAX_AMP, p["amp"]))
        self.dur_ms = min(MAX_DUR_MS, p["dur_ms"])
        self.t0, self.t1 = int(t0), int(t0 + self.dur_ms / net.cfg.dt)
        prob = p["frac"] * montage_weights(net)[net.region_of_np]           # recruitment probability per neuron
        self.ids = np.flatnonzero(rng.random(net.n) < prob)                 # drawn once per stimulus (modelled chance)
        self.period = max(1, int(round(1000.0 / PULSE_HZ / net.cfg.dt)))
        self.width = max(1, int(round(PULSE_WIDTH_MS / net.cfg.dt)))

    def on(self, t):
        return self.t0 <= t < self.t1 and ((t - self.t0) % self.period) < self.width

    def card(self):
        return {"level": self.level, "amp_mv": float(self.amp), "dur_ms": self.dur_ms, "n_recruited": int(self.ids.size),
                "pulse_hz": PULSE_HZ, "pulse_ms": PULSE_WIDTH_MS}


class ALIFNet(LiveNet):
    """LiveNet's wiring with exponential synapses and an adaptation current (module docstring)."""

    def __init__(self, cfg=None, regions=None, tau_e=TAU_E, tau_i=TAU_I, tau_w=TAU_W, adapt_a=ADAPT_A, adapt_b=ADAPT_B,
                 mu_ext=MU_EXT, seed=SEED):
        cfg = cfg or Config(n_neurons=N_NEURONS, mu_ext=mu_ext)
        super().__init__(cfg, regions)
        dt, c = cfg.dt, cfg
        self.tau_e, self.tau_i, self.tau_w = float(tau_e), float(tau_i), float(tau_w)
        self.adapt_a, self.adapt_b = np.float32(adapt_a), np.float32(adapt_b)
        self.dec_e, self.dec_i = np.float32(math.exp(-dt / tau_e)), np.float32(math.exp(-dt / tau_i))
        # jump scale: the PSP integral (sum over steps of a * s) equals LiveNet's instantaneous jump exactly in this
        # discrete scheme: sum_k a q exp(-k dt / tau) = a q / (1 - dec) = 1  ->  q = (1 - dec) / a  (~ tau_m / tau)
        self.q_e, self.q_i = np.float32((1.0 - self.dec_e) / self.a), np.float32((1.0 - self.dec_i) / self.a)
        self.aw = np.float32(dt / tau_w)
        self.w_e = np.where(self.w > 0, self.w, 0).astype(np.float32) * self.q_e      # E synapses only (I rows are 0)
        self.w_i = np.where(self.w < 0, -self.w, 0).astype(np.float32) * self.q_i
        self.exc_ids = np.flatnonzero(self.is_exc_np)
        self.inh_ids = np.flatnonzero(~self.is_exc_np)
        self.pulse = None
        self.flat = False
        self.stim_rng = np.random.default_rng(seed + 5000)
        self._state(seed=seed)

    def _state(self, seed=0):
        super()._state(seed)
        n = self.n
        self.buf_e = np.zeros(self.D * n, dtype=np.float32)       # arrivals, by delay slot, excitatory / inhibitory
        self.buf_i = np.zeros(self.D * n, dtype=np.float32)
        self.s_e = np.zeros(n, dtype=np.float32)
        self.s_i = np.zeros(n, dtype=np.float32)
        self.w_ad = np.zeros(n, dtype=np.float32)
        self.pulse = None
        self.flat = False

    def arrest(self):
        """The rule of the piece: the background drive goes to zero; spontaneous activity stops."""
        self.mu.fill(0.0)
        self.flat = True

    def restart(self):
        """The drive is back (a strong shock while flat); the pulse train that follows restarts the activity."""
        self.mu.fill(self.cfg.mu_ext)
        self.flat = False

    def reset(self):
        """Operator reset: a fresh state on the same wiring (new seed each time so the restart is not a replay)."""
        self._state(seed=int(self.stim_rng.integers(1 << 30)))

    def _deliver_to(self, buf, spk, slot, w):
        start = self.rowptr[spk]
        cnt = self.rowptr[spk + 1] - start
        tot = int(cnt.sum())
        if tot:
            syn = np.repeat(start - np.cumsum(cnt) + cnt, cnt) + np.arange(tot)
            tgt = (self.slot_off[syn] + slot) % buf.size
            np.add.at(buf, tgt, w[syn])

    def stimulate(self, level):
        """Start a pulse train now (one at a time: a new one replaces a running one). -> its card. While flat, a train
        of REVIVE_LEVEL or more restores the drive first (the card says "revived")."""
        revived = False
        if self.flat and int(level) >= REVIVE_LEVEL:
            self.restart()
            revived = True
        self.pulse = Pulse(self, level, self.t, self.stim_rng)
        return {**self.pulse.card(), "revived": revived, "flat": self.flat}

    def stim_on(self):
        return self.pulse is not None and self.pulse.t0 <= self.t < self.pulse.t1

    def step(self):
        c, n = self.cfg, self.n
        slot = (self.t % self.D) * n
        s_e, s_i, v, w = self.s_e, self.s_i, self.v, self.w_ad
        # synaptic variables: exact decay, then the arrivals of this step
        s_e *= self.dec_e
        s_i *= self.dec_i
        ie, ii = self.buf_e[slot:slot + n], self.buf_i[slot:slot + n]
        s_e += ie
        s_i += ii
        ie.fill(0.0)
        ii.fill(0.0)
        # adaptation: Euler
        w += self.aw * (self.adapt_a * v - w)
        # membrane: Euler on the leak, drive, synaptic currents and adaptation, plus the noise
        v *= np.float32(1.0 - self.a)
        v += np.float32(self.a) * (self.mu + s_e - s_i - w)
        v += self.noise_sd * self.rng.standard_normal(n, dtype=np.float32)
        p = self.pulse
        if p is not None and p.on(self.t):
            v[p.ids] += p.amp
        refr = self.ref > 0
        if refr.any():
            v[refr] = c.v_reset
            self.ref[refr] -= 1
        spk = np.flatnonzero(v >= c.v_th)
        if spk.size:
            v[spk] = c.v_reset
            self.ref[spk] = self.n_ref
            w[spk] += self.adapt_b
            self.count[spk] += 1
            if self.row_of is not None:
                rows = self.row_of[spk]
                rows = rows[rows >= 0]
                if rows.size:
                    self.raster.append((self.t, rows))
            exc = self.is_exc_np[spk]
            if exc.any():
                self._deliver_to(self.buf_e, spk[exc], slot, self.w_e)
            if (~exc).any():
                self._deliver_to(self.buf_i, spk[~exc], slot, self.w_i)
        if p is not None and self.t >= p.t1:
            self.pulse = None
        self.t += 1
        return spk.size


# --- measurements ---------------------------------------------------------------------------------------------------
BASE_TAU_S = 20.0                 # the running baseline forgets with this time constant (quiet bins only)
WARMUP_MS = 1500                  # the first bins after a (re)start are the transient of the random initial state: not baseline
BASE_MIN_BINS = 100               # 2 s of quiet before the baseline is called ready
QUIET_AFTER_MS = 3000             # after a stimulus ends, this long before bins count as quiet again
BAND_Z, BAND_RATIO = 2.0, (0.75, 1.35)   # back in the band: within 2 spreads of the baseline and within these ratios
RECOVER_HOLD_MS = 500             # ...and staying there this long
RESPONSE_WINDOW_MS = 6000         # the response card closes at most this long after the stimulus ends
ONSET_Z, ONSET_RATIO = 3.0, 1.5
BURST_RATIO, BURST_BINS = 3.0, 3
RECRUIT_RATIO = 2.0
GROUP_KEYS = ("visual", "somatomotor", "attention", "salience", "limbic", "control", "default", "reward", "fear",
              "memory", "relay", "language")


class Baseline:
    """Running mean and spread (EWMA) of a vector signal over quiet bins."""

    def __init__(self, k, alpha):
        self.mean = np.zeros(k)
        self.var = np.zeros(k)
        self.n = 0
        self.alpha = alpha

    def add(self, x):
        x = np.asarray(x, dtype=np.float64)
        if self.n == 0:
            self.mean[:] = x
        else:
            a = max(self.alpha, 1.0 / (self.n + 1))           # a plain running mean first, the EWMA once it is long
            d = x - self.mean
            self.mean += a * d
            self.var += a * (d * d - self.var)
        self.n += 1

    @property
    def ready(self):
        return self.n >= BASE_MIN_BINS

    def sd(self):
        return np.sqrt(np.maximum(self.var, 1e-9))


class Measure:
    """Bins the spikes of an ALIFNet and keeps the baseline and the open response card (module docstring)."""

    def __init__(self, net, bin_ms=BIN_MS):
        self.net = net
        self.bin_ms = bin_ms
        self.bin_steps = int(round(bin_ms / net.cfg.dt))
        self.per_s = 1000.0 / bin_ms
        R = net.reg.n
        self.group_ids = {g: np.asarray(net.reg.groups.get(g, []), dtype=np.int64) for g in GROUP_KEYS}
        self.group_n = {g: float(net.size[ids].sum()) for g, ids in self.group_ids.items()}
        self.region_n = net.size.astype(np.float64)
        self.n_e, self.n_i = float(net.exc_ids.size), float(net.inh_ids.size)
        alpha = bin_ms / 1000.0 / BASE_TAU_S
        self.base_main = Baseline(4 + len(GROUP_KEYS), alpha)        # rate, rate_e, rate_i, w_mean, groups...
        self.base_region = Baseline(R, alpha)
        self.last_count = net.count.copy()
        self.last_stim_end = -10 ** 9                                # step
        self.response = None                                         # the open response card
        self.cards = []                                              # closed cards (newest last, at most 50)
        self.bins = []                                               # recent bins for the trace (dicts), at most 1500
        self.phase = "warming"
        self.flat_since, self.flatlines, self.revivals = None, 0, 0
        self.load = 0.0                                              # EWMA of the mean adaptation current (the rule)
        self.events = []                                             # flatline / revived, drained by the child

    # --- one bin -------------------------------------------------------------------------------------------------
    def bin(self):
        """Call after exactly bin_steps steps. -> the bin dict."""
        net = self.net
        d = (net.count - self.last_count).astype(np.float64)
        self.last_count[:] = net.count
        per_region = np.bincount(net.region_of_np, weights=d, minlength=net.reg.n) / self.region_n * self.per_s
        rate = d.sum() / net.n * self.per_s
        rate_e = d[net.exc_ids].sum() / self.n_e * self.per_s
        rate_i = d[net.inh_ids].sum() / self.n_i * self.per_s
        w_mean = float(net.w_ad.mean())
        groups = {g: float((per_region[ids] * self.region_n[ids]).sum() / self.group_n[g]) if ids.size else 0.0
                  for g, ids in self.group_ids.items()}
        stim = net.stim_on() or (net.pulse is not None and net.pulse.t0 <= net.t)
        t_ms = net.t * net.cfg.dt
        # the arrest rule (module docstring): the load is the adaptation current averaged over LOAD_TAU_S
        self.load += (self.bin_ms / 1000.0 / LOAD_TAU_S) * (w_mean - self.load)
        if not net.flat and self.base_main.ready and self.load > FLAT_LOAD_RATIO * max(self.base_main.mean[3], 1e-6):
            net.arrest()
            self.flat_since = t_ms
            self.flatlines += 1
            self.events.append({"type": "flatline", "t_ms": t_ms, "w": float(w_mean), "base_w": float(self.base_main.mean[3])})
        if net.pulse is not None and net.t >= net.pulse.t1 - 1:
            self.last_stim_end = max(self.last_stim_end, net.pulse.t1)
        quiet = (not stim) and (net.t - self.last_stim_end) * net.cfg.dt >= QUIET_AFTER_MS and t_ms >= WARMUP_MS and not net.flat
        main = np.array([rate, rate_e, rate_i, w_mean] + [groups[g] for g in GROUP_KEYS])
        if quiet and self.response is None:
            self.base_main.add(main)
            self.base_region.add(per_region)
        b = {"t_ms": float(t_ms), "rate": float(rate), "rate_e": float(rate_e), "rate_i": float(rate_i), "w": w_mean,
             "stim": bool(stim), "groups": groups, "flat": bool(net.flat)}
        if self.base_main.ready:
            m, s = self.base_main.mean, self.base_main.sd()
            b["ratio"] = float(rate / max(m[0], 1e-6))
            b["z"] = float((rate - m[0]) / max(s[0], 1e-6))
            b["recruit"] = float(np.mean(per_region > RECRUIT_RATIO * np.maximum(self.base_region.mean, 0.2)))
            b["w_rel"] = float((w_mean - m[3]) / max(m[3], 1e-6))
        self._update_response(b, per_region)
        self.phase = self._phase(b)
        self.bins.append(b)
        if len(self.bins) > 1500:
            del self.bins[:500]
        return b

    def _phase(self, b):
        if self.net.flat:
            return "flat"
        if not self.base_main.ready:
            return "warming"
        if b["stim"]:
            return "stimulated"
        if self.response is not None:
            return "responding" if not self.response.get("in_band") else "settling"
        return "quiet"

    # --- the response card ---------------------------------------------------------------------------------------
    def open(self, rid, card):
        """A stimulus starts now: open its card (closed by _update_response)."""
        net = self.net
        m = self.base_main
        if card.get("revived"):
            dead_s = (net.t * net.cfg.dt - self.flat_since) / 1000.0 if self.flat_since is not None else None
            self.revivals += 1
            self.events.append({"type": "revived", "t_ms": net.t * net.cfg.dt, "dead_s": dead_s, "level": card.get("level")})
            self.flat_since = None
        self.response = {"id": rid, **card, "t0_ms": net.t * net.cfg.dt, "t1_ms": (net.t * net.cfg.dt) + card["dur_ms"],
                         "baseline": bool(m.ready), "base_rate": float(m.mean[0]) if m.ready else None,
                         "base_w": float(m.mean[3]) if m.ready else None, "w_before": float(net.w_ad.mean()),
                         "peak_rate": 0.0, "peak_ratio": None, "peak_z": None, "peak_t_ms": None, "onset_ms": None,
                         "burst": False, "_burst_run": 0, "recruit": 0.0, "min_ratio_after": None, "w_peak": 0.0,
                         "recovered_ms": None, "_in_band_since": None, "in_band": False, "groups_peak": {},
                         "_region_sum": np.zeros(net.reg.n), "_region_bins": 0, "closed": False}
        return self.response

    def _update_response(self, b, per_region):
        r = self.response
        if r is None:
            return
        t = b["t_ms"]
        if b["rate"] > r["peak_rate"]:
            r["peak_rate"], r["peak_t_ms"], r["groups_peak"] = b["rate"], t, dict(b["groups"])
        r["w_peak"] = max(r["w_peak"], b["w"])
        if t < r["t1_ms"] + 200:                                        # recruitment: over the train and 200 ms after
            r["_region_sum"] += per_region
            r["_region_bins"] += 1
        if r["baseline"]:
            ratio, z = b["ratio"], b["z"]
            r["peak_ratio"] = float(max(r["peak_ratio"] or 0.0, ratio))
            r["peak_z"] = float(max(r["peak_z"] or 0.0, z))
            if r["onset_ms"] is None and z > ONSET_Z and ratio > ONSET_RATIO:
                r["onset_ms"] = t - r["t0_ms"]
            r["_burst_run"] = r["_burst_run"] + 1 if ratio > BURST_RATIO else 0
            if r["_burst_run"] >= BURST_BINS:
                r["burst"] = True
            if t >= r["t1_ms"]:
                r["min_ratio_after"] = float(ratio if r["min_ratio_after"] is None else min(r["min_ratio_after"], ratio))
                in_band = abs(z) <= BAND_Z and BAND_RATIO[0] <= ratio <= BAND_RATIO[1]
                if in_band:
                    if r["_in_band_since"] is None:
                        r["_in_band_since"] = t
                    r["in_band"] = True
                    if t - r["_in_band_since"] >= RECOVER_HOLD_MS and r["recovered_ms"] is None:
                        r["recovered_ms"] = r["_in_band_since"] - r["t1_ms"]
                else:
                    r["_in_band_since"], r["in_band"] = None, False
        done = (r["recovered_ms"] is not None) or (t >= r["t1_ms"] + RESPONSE_WINDOW_MS)
        if done:
            self._close(b)

    def _close(self, b):
        r = self.response
        net = self.net
        if r["_region_bins"]:
            mean_region = r["_region_sum"] / r["_region_bins"]
            if r["baseline"]:
                r["recruit"] = float(np.mean(mean_region > RECRUIT_RATIO * np.maximum(self.base_region.mean, 0.2)))
        r["w_after"] = float(net.w_ad.mean())
        r["closed"] = True
        r["distinguishable"] = bool(r["baseline"] and r["onset_ms"] is not None)
        for k in [k for k in r if k.startswith("_")]:
            del r[k]
        self.cards.append(r)
        if len(self.cards) > 50:
            del self.cards[:25]
        self.response = None

    def card(self):
        """The open card without its private fields, or None."""
        r = self.response
        if r is None:
            return None
        return {k: v for k, v in r.items() if not k.startswith("_")}

    def baseline_view(self):
        m = self.base_main
        if not m.ready:
            return {"ready": False, "bins": m.n}
        s = m.sd()
        return {"ready": True, "rate": float(m.mean[0]), "rate_sd": float(s[0]), "rate_e": float(m.mean[1]),
                "rate_i": float(m.mean[2]), "w": float(m.mean[3]),
                "groups": {g: float(m.mean[4 + i]) for i, g in enumerate(GROUP_KEYS)}}


# --- the body's reading of the measurements (artistic, documented in chair.py) -------------------------------------
def drive_from(b, base):
    """Measured bin -> the numbers the body animates from, all 0..1. tension: how far the rate is above baseline
    (log scale, 1 at 8x). slack: how far below (the undershoot after a shock). heavy: the adaptation current above its
    baseline (1 at twice the baseline w). motor: the somatomotor regions' rate above their own baseline, the same
    scale (the limbs). An artistic mapping, not a physiological claim."""
    if b.get("flat"):
        return {"tension": 0.0, "slack": 1.0, "heavy": 1.0, "motor": 0.0, "measured": True, "flat": True}
    if not base.get("ready") or "ratio" not in b:
        return {"tension": 0.0, "slack": 0.0, "heavy": 0.0, "motor": 0.0, "measured": False, "flat": False}
    ratio = max(b["ratio"], 1e-6)
    tension = min(1.0, max(0.0, math.log(ratio) / math.log(8.0)))
    slack = min(1.0, max(0.0, 1.0 - ratio)) if ratio < 1 else 0.0
    heavy = min(1.0, max(0.0, b.get("w_rel", 0.0)))
    # motor: the somatomotor regions' rate against their own quiet rate, the same log scale; the limbs follow it,
    # the trunk and the head follow the whole network (missing in a bin without groups: the whole network's number)
    motor = tension
    bg, gq = (b.get("groups") or {}).get("somatomotor"), (base.get("groups") or {}).get("somatomotor")
    if bg is not None and gq:
        motor = min(1.0, max(0.0, math.log(max(bg / max(gq, 1e-6), 1e-6)) / math.log(8.0)))
    return {"tension": round(float(tension), 3), "slack": round(float(slack), 3), "heavy": round(float(heavy), 3),
            "motor": round(float(motor), 3), "measured": True, "flat": False}


def bench(n=N_NEURONS, seconds=2.0):
    """Wall time per simulated second (module check)."""
    net = ALIFNet(Config(n_neurons=n, mu_ext=MU_EXT))
    net.run(200)
    t0 = time.time()
    net.run(seconds * 1000)
    return (time.time() - t0) / seconds


# --- the child process: one owner of the simulation, paced to the wall clock -----------------------------------------
# Protocol (one JSON object per line on stdin/stdout, like spiking/live.py's):
#   {"type": "stim", "id": "c-12", "level": 3}  -> {"type": "delivered", "id", "t_ms", "level", "amp_mv", "dur_ms", "n_recruited", ...}
#                                                  later {"type": "measured", "id", ... the closed response card}
#                                                  or {"type": "refused", "id", "why": "busy|level"}
#   {"type": "resume"} / {"type": "pause"}       -> {"type": "state", "running": bool}
#   {"type": "reset", "id"}                      -> {"type": "reset_done", "id"}       (operator: a fresh state, same wiring)
#   {"type": "status", "id"}                     -> {"type": "status", "id", ...}
#   {"type": "stop"}                             -> {"type": "stopped"}
# Unasked while running: {"type": "trace", "t_ms", "bins": [[t_ms, rate, somatomotor, w, stim, ratio], ...], "phase",
#   "drive", "baseline", "card", "running", "lag_ms"} every TRACE_EVERY bins. Paused: nothing moves and nothing is sent.
TRACE_EVERY = 10                  # bins (200 ms)
MAX_BEHIND_MS = 500               # the process stalled longer than this: re-anchor instead of catching up (lag counted)


def _trace(M, bins, running, lag_ms):
    base = M.baseline_view()
    last = bins[-1] if bins else None
    return {"type": "trace", "t_ms": float(M.net.t * M.net.cfg.dt), "running": running, "lag_ms": round(lag_ms, 1),
            "bins": [[round(b["t_ms"]), round(b["rate"], 2), round(b["groups"]["somatomotor"], 2), round(b["w"], 2),
                      int(b["stim"]), round(b.get("ratio", 0.0), 3), int(b.get("flat", False))] for b in bins],
            "phase": M.phase, "flat": bool(M.net.flat), "flatlines": M.flatlines, "revivals": M.revivals,
            "load": round(M.load / max(M.base_main.mean[3], 1e-6), 3) if M.base_main.ready else None,
            "drive": drive_from(last, base) if last else None, "baseline": base, "card": M.card()}


def serve(net, M, fd_in, out, pace=True):
    """Answer requests until stdin closes; while running, advance the network in BIN_MS bins paced to the wall clock."""
    import json as _json
    import os as _os
    import select as _select

    def send(obj):
        out.write(_json.dumps(obj) + "\n")
        out.flush()

    state = {"running": False, "M": M}
    anchor = {"wall": None, "sim": 0.0, "lag": 0.0}
    send({"type": "ready", "n_neurons": net.n, "n_synapses": net.n_syn, "build_s": round(net.build_s, 2),
          "bin_ms": M.bin_ms, "tau_w": net.tau_w, "tau_e": net.tau_e, "tau_i": net.tau_i})
    pending, buf = [], b""

    def handle(line):
        M = state["M"]
        try:
            msg = _json.loads(line)
        except ValueError:
            return None
        kind, rid = msg.get("type"), msg.get("id")
        if kind == "stim":
            level = msg.get("level")
            if level not in LEVELS:
                send({"type": "refused", "id": rid, "why": "level"})
            elif net.stim_on() or M.response is not None and not M.response.get("closed") and net.t * net.cfg.dt < M.response["t1_ms"]:
                send({"type": "refused", "id": rid, "why": "busy"})
            elif not state["running"]:
                send({"type": "refused", "id": rid, "why": "paused"})
            else:
                card = net.stimulate(level)
                M.open(rid, card)
                send({"type": "delivered", "id": rid, "t_ms": float(net.t * net.cfg.dt), **card})
                while M.events:                                   # "revived" goes out right after its delivery
                    send(M.events.pop(0))
        elif kind == "resume":
            if not state["running"]:
                state["running"] = True
                anchor["wall"], anchor["sim"] = time.monotonic(), net.t * net.cfg.dt
            send({"type": "state", "running": True})
        elif kind == "pause":
            state["running"] = False
            send({"type": "state", "running": False})
        elif kind == "reset":
            net.reset()
            state["M"] = Measure(net, M.bin_ms)
            anchor["wall"], anchor["sim"] = time.monotonic(), net.t * net.cfg.dt
            send({"type": "reset_done", "id": rid})
        elif kind == "status":
            send({"type": "status", "id": rid, "running": state["running"], "t_ms": float(net.t * net.cfg.dt),
                  "n_neurons": net.n, "phase": M.phase, "baseline": M.baseline_view(), "cards": len(M.cards),
                  "lag_ms": round(anchor["lag"], 1), "cpu_s": round(time.process_time(), 2)})
        elif kind == "stop":
            send({"type": "stopped"})
            return "stop"
        return None

    while True:
        M = state["M"]
        timeout = None
        if state["running"] and pace:
            behind = (time.monotonic() - anchor["wall"]) * 1000.0 - (net.t * net.cfg.dt - anchor["sim"])
            if behind > MAX_BEHIND_MS:                       # stalled (a slow box): keep the clock honest, count the lag
                anchor["lag"] += behind - M.bin_ms
                anchor["wall"] = time.monotonic() - M.bin_ms / 1000.0
                anchor["sim"] = net.t * net.cfg.dt
                behind = M.bin_ms
            timeout = max(0.0, (M.bin_ms - behind) / 1000.0)
        elif state["running"]:
            timeout = 0.0
        ready, _, _ = _select.select([fd_in], [], [], timeout)
        if ready:
            chunk = _os.read(fd_in, 1 << 16)
            if not chunk:
                return
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                if line.strip() and handle(line) == "stop":
                    return
            continue
        if not state["running"]:
            continue
        M = state["M"]
        n_cards = len(M.cards)
        for _ in range(M.bin_steps):
            net.step()
        pending.append(M.bin())
        if len(M.cards) > n_cards:
            send({"type": "measured", **M.cards[-1]})
        while M.events:
            send(M.events.pop(0))
        if len(pending) >= TRACE_EVERY:
            send(_trace(M, pending, True, anchor["lag"]))
            pending = []


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="the chair's network (child process of live_server.py)")
    ap.add_argument("--neurons", type=int, default=N_NEURONS)
    ap.add_argument("--no-pace", action="store_true", help="run as fast as possible (tests)")
    a = ap.parse_args(argv)
    net = ALIFNet(Config(n_neurons=a.neurons, mu_ext=MU_EXT))
    serve(net, Measure(net), 0, __import__("sys").stdout, pace=not a.no_pace)


if __name__ == "__main__":
    main()
