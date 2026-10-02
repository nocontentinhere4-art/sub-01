"""His spiking neurons in the day: a small spiking network on the server CPU takes part in his real choices (#55).

A small simulated spiking network (20,000 neurons by default) built on the same wiring as the nightly 1M-neuron
network (the same construction and seed: spiking/wiring.py) runs in its own child process, like browse_service.py, so
the 50 ms brain tick never waits for it. It is a decision server: the main process sends the labels of the options
on offer, the network gets them as cues, its striatal action pools race (spiking/choice.py, #39), and it answers with
its pick, every pool's rate and the simulated decision time. brain_vote.vote adds the pool rates as one small term
(SPIKING_W) next to the rate model's value, the taste and the novelty; the rate model stays the main decider.

Why numpy and not spiking/net.py: torch is not in the server image (it would add ~700 MB), and at 20k neurons an
event-driven numpy step is fast enough (~0.3 ms per simulated ms on one core, measured in docs/spiking/live.md).
net.py and this file share the numpy construction (wiring.py), so the synapses are identical; the dynamics are the
same LIF equations, without the recorded resting-state drive (the day network idles between decisions and gets the
plain background drive).

Cues = real option labels. A label's content words (spiking/words.py, at most LABEL_WORDS) are each hashed exactly
as memory.py hashes words (wiring.word_neurons, the same sha256 seed) at WORD_FRAC of the excitatory neurons of every
parcel; the visual and language parcels are kept. The same word lands on the same neurons in every label, so what is
learned about "bread" in one label carries over to another label with "bread" in it. Action pools: the excitatory
neurons of the striatum, split among the offered labels by a hashed affinity (choice.py's, averaged over the label's
words and rank-normalised so that a label's word count does not change its pool size). Any 2-6 options, any labels.

Learning (the #39 rule, live): when he leaves a page, the tastes response of the stay (tastes.PageWatch, its
reward-prediction error from Tastes.learn) becomes dopamine for the decision that led to the page:
    dw += eta_t * da * pre * post,  da = clip(DA_GAIN * delta, -1, 1),
pre = clamp((cue-neuron rate in the decision window - 5 Hz) / 40 Hz, 0, 1) and post = +1 on the pool of the option
that was followed, -1/(K-1) on the other offered pools (zero-sum), tagged at the decision. Only the cue -> striatum
synapses learn; w = clamp(w0 + dw, 0, w_max). The stability fix named in docs/spiking/choice.md: a decaying learning
rate, eta_t = ETA / (1 + n / ETA_HALF), never below ETA_FLOOR x ETA, so a preference settles instead of flipping.
The learned dw is saved to /data/spiking/live_weights.npz (atomic write) and loaded at start.

A frozen twin (the same network with no learning, the same offers and the same noise) runs every decision too, so
the page can compare: how often its pick matched the option that later paid off, against the twin and chance.
Wording: a small simulated spiking network built on the same wiring takes part in his choices and learns from a
simulated reward. Never "he thinks / understands / wants".

Protocol (one JSON object per line on stdin / stdout):
    {"id": 1, "op": "decide", "labels": [...]} -> {"id": 1, "pick", "pool_rates", "decision_ms", "timeout",
                                                    "twin_pick", "twin_rates", "cpu_ms", "n_neurons"}
    {"id": 2, "op": "learn", "decision": 1, "followed": 0, "delta": 0.3} -> {"id": 2, "ok", "eta", "n_learn"}
    {"id": 3, "op": "status"} -> {"id": 3, "cpu_s", "uptime_s", "n_decisions", "n_learn", ...}
The child exits when its stdin closes (the server died) or on {"op": "stop"}.

    python -m spiking.live --data-dir /data --neurons 20000
"""
import argparse
import hashlib
import json
import math
import os
import sys
import time
from pathlib import Path

import numpy as np

from spiking.config import Config
from spiking.regions import Regions
from spiking.wiring import Layout, input_regions, synapse_lists, word_neurons
from spiking.words import words

HERE = Path(__file__).resolve().parent.parent
N_NEURONS = 20_000
CUE_GROUPS = ("visual", "language")
ACTION_GROUP = "reward"           # striatum: caudate, putamen, accumbens
LABEL_WORDS = 4                   # content words of a label used as its cue
WORD_FRAC = 0.08                  # per word (a 4-word label covers ~28 % of the cue space, one word 8 %)
FRAC_HC = 0.005                   # memory.py's default (only keeps the hashing identical; hippocampus is not a cue)
CUE_AMP = 8.0                     # mV on the cue neurons while the options are on offer (choice.py)
SETTLE_MS = 100                   # background only, before the cues come on
CHECK_MS, MIN_MS, TIMEOUT_MS = 10, 50, 250
THR_Z = 2.0
ETA = 0.6                         # mV per unit dopamine (choice.py)
ETA_HALF = 50.0                   # learning-rate decay: eta halves after 50 learned decisions...
ETA_FLOOR = 0.25                  # ...and never goes below a quarter
DA_GAIN = 2.0                     # tastes' prediction errors are mostly within +-0.5; x2 brings them to choice.py's +-1
MAX_OPTIONS = 6
PENDING = 8                       # decisions kept for a late dopamine (the next page's decision comes first)
VERSION = 1
CALIB_LABELS = ("apple", "river", "cloud", "stone", "lamp", "bird", "salt", "rope")


# --- labels -> cues and pools (torch-free; spiking/choice.py uses the same functions at night) ---------------------
def label_words(label):
    ws = words(str(label or ""), max_words=LABEL_WORDS)
    return ws or [str(label or "").strip().lower()[:40] or "nothing"]


def label_cue(net, label, cue_space, regions=None, frac=WORD_FRAC):
    """Cue neurons of a label: the union of its words' neurons (memory.py hashing) inside the cue space."""
    ids = [word_neurons(net, w, frac, FRAC_HC, regions) for w in label_words(label)]
    return np.intersect1d(np.unique(np.concatenate(ids)), cue_space)


def _word_affinity(word, n):
    h = hashlib.sha256(("sub01-choice-pool:" + word).encode()).digest()       # choice.py's hash
    return np.random.default_rng(int.from_bytes(h[:8], "little")).random(n)


def label_affinity(label, n):
    """Affinity of each of n action neurons for a label: the mean of its words' hashed affinities, rank-normalised to
    (0, 1) so labels with more words do not get smaller pools."""
    a = np.mean([_word_affinity(w, n) for w in label_words(label)], axis=0)
    r = np.empty(n)
    r[np.argsort(a, kind="stable")] = np.arange(n)
    return (r + 0.5) / n


def label_pools(action, affinities):
    """Disjoint pools: each action neuron goes to the offered label it has the highest affinity for."""
    owner = np.argmax(np.stack(affinities), axis=0)
    return [action[owner == k] for k in range(len(affinities))]


def lean(rates, scale_hz=2.0):
    """Pool rates -> a lean per option in -1..1 (0 = no preference): tanh((rate - mean) / 2 Hz)."""
    r = np.asarray(rates, dtype=float)
    return np.tanh((r - r.mean()) / scale_hz)


# --- the numpy network ---------------------------------------------------------------------------------------------
class LiveNet(Layout):
    """LIF network with net.py's construction (wiring.py) in numpy, float32, one CPU core, event-driven delays."""

    def __init__(self, cfg=None, regions=None):
        self.cfg = cfg = cfg or Config(n_neurons=N_NEURONS)
        self.reg = regions or Regions()
        t0 = time.time()
        self._layout()
        src_l, dst_l, w_l, d_l, _, _ = synapse_lists(self)
        src = np.concatenate(src_l)
        order = np.argsort(src, kind="stable")                 # the CSR order of net.py (stable sort by source)
        src = src[order]
        self.dst = np.concatenate(dst_l)[order]
        self.w = np.concatenate(w_l)[order]
        delay = np.concatenate(d_l)[order]
        self.D = int(delay.max()) + 1
        self.rowptr = np.zeros(self.n + 1, dtype=np.int64)
        self.rowptr[1:] = np.cumsum(np.bincount(src, minlength=self.n))
        self.slot_off = delay.astype(np.int64) * self.n + self.dst      # where a spike's input lands, from slot 0
        self.src = src
        self.n_syn = len(src)
        self.a = cfg.dt / cfg.tau_m
        self.n_ref = int(round(cfg.t_ref / cfg.dt))
        self.noise_sd = np.float32(cfg.sigma_ext * math.sqrt(self.a))
        self.build_s = time.time() - t0
        self._state()

    def _state(self, seed=0):
        c = self.cfg
        rng = np.random.default_rng(self.cfg.seed + 2000 + seed)
        self.v = (rng.random(self.n) * (c.v_th - c.v_reset) + c.v_reset).astype(np.float32)
        self.ref = np.zeros(self.n, dtype=np.int16)
        self.buf = np.zeros(self.D * self.n, dtype=np.float32)
        self.count = np.zeros(self.n, dtype=np.int64)
        self.mu = np.full(self.n, c.mu_ext, dtype=np.float32)
        self.t = 0
        self.rng = np.random.default_rng(self.cfg.seed + 1000 + seed)

    def twin(self):
        """A copy with its own state and weights, sharing the fixed synapse arrays (a frozen control)."""
        tw = object.__new__(LiveNet)
        tw.__dict__.update(self.__dict__)
        tw.w = self.w.copy()
        tw._state(seed=1)
        return tw

    def drive(self, ids=None, amp=0.0):
        self.mu.fill(self.cfg.mu_ext)
        if ids is not None and len(ids):
            self.mu[ids] += np.float32(amp)

    def step(self):
        c, n = self.cfg, self.n
        slot = (self.t % self.D) * n
        inp = self.buf[slot:slot + n]
        v = self.v
        v *= np.float32(1.0 - self.a)
        v += np.float32(self.a) * self.mu
        v += self.noise_sd * self.rng.standard_normal(n, dtype=np.float32)
        v += inp
        inp.fill(0.0)
        refr = self.ref > 0
        if refr.any():
            v[refr] = c.v_reset
            self.ref[refr] -= 1
        spk = np.flatnonzero(v >= c.v_th)
        if spk.size:
            v[spk] = c.v_reset
            self.ref[spk] = self.n_ref
            self.count[spk] += 1
            start = self.rowptr[spk]
            cnt = self.rowptr[spk + 1] - start
            tot = int(cnt.sum())
            if tot:
                syn = np.repeat(start - np.cumsum(cnt) + cnt, cnt) + np.arange(tot)
                tgt = (self.slot_off[syn] + slot) % self.buf.size
                np.add.at(self.buf, tgt, self.w[syn])
        self.t += 1
        return spk.size

    def run(self, ms):
        for _ in range(int(round(ms / self.cfg.dt))):
            self.step()


# --- one decision on one network -------------------------------------------------------------------------------------
class Chooser:
    """Cues, pools and the race (choice.py's) on one LiveNet."""

    def __init__(self, net):
        self.net = net
        reg = net.reg
        cue_regions = sorted(set(sum((reg.groups[g] for g in CUE_GROUPS), [])))
        self.cue_space = np.concatenate([net.region_neurons(r, exc_only=True) for r in cue_regions])
        self.action = net.group_neurons(ACTION_GROUP, exc_only=True)
        self.regions = input_regions(net)
        self._cue, self._aff = {}, {}
        is_cue = np.zeros(net.n, bool)
        is_cue[self.cue_space] = True
        is_act = np.zeros(net.n, bool)
        is_act[self.action] = True
        src = net.src
        self.pidx = np.flatnonzero(is_cue[src] & is_act[net.dst] & (net.w > 0))   # plastic cue -> striatum E -> E
        self.pre, self.post = src[self.pidx], net.dst[self.pidx]
        self.w0 = net.w[self.pidx].copy()
        self.w_max = net.cfg.w_max_ctx
        self.thr_hz = None
        self.timeout_ms = TIMEOUT_MS

    def cue(self, label):
        if label not in self._cue:
            self._cue[label] = label_cue(self.net, label, self.cue_space, self.regions)
            self._aff[label] = label_affinity(label, len(self.action))
        return self._cue[label]

    def present(self, labels, seed):
        """Drive the offered labels' cues and run the race. -> (pick, pool rates Hz, decision ms, timeout,
        pre factor per plastic synapse, option of each plastic synapse's post neuron (-1: none))."""
        net = self.net
        cues = [self.cue(lb) for lb in labels]
        pools = label_pools(self.action, [self._aff[lb] for lb in labels])
        sizes = np.array([max(1, len(p)) for p in pools], dtype=float)
        net.rng = np.random.default_rng(seed)                  # the same noise for the network and its twin
        net.drive()
        net.run(SETTLE_MS)
        c0 = net.count.copy()
        net.drive(np.unique(np.concatenate(cues)), CUE_AMP)
        pick, ms, timeout, rates = None, None, True, None
        try:
            for t in range(self.timeout_ms // CHECK_MS):
                net.run(CHECK_MS)
                ms = (t + 1) * CHECK_MS
                d = net.count - c0
                rates = np.array([d[p].sum() for p in pools]) / sizes / (ms / 1000.0)
                if self.thr_hz is not None and ms >= MIN_MS and (rates > self.thr_hz).any():
                    pick, timeout = int(np.argmax(rates)), False
                    break
            if pick is None:
                pick = int(np.argmax(rates))
            pre_rate = (net.count[self.pre] - c0[self.pre]) / (ms / 1000.0)
        finally:
            net.drive()
        pre = np.clip((pre_rate - 5.0) / 40.0, 0.0, 1.0).astype(np.float32)
        opt = np.full(net.n, -1, dtype=np.int8)
        for k, p in enumerate(pools):
            opt[p] = k
        return pick, rates, ms, timeout, pre, opt[self.post]

    def calibrate(self, presentations=12, seed=0):
        """Threshold = mean + THR_Z sd of the pool rates at 100 ms (4 random calibration words, no race)."""
        rng = np.random.default_rng(seed)
        thr, self.thr_hz, rates = self.thr_hz, None, []
        keep, self.timeout_ms = self.timeout_ms, 100
        try:
            for i in range(presentations):
                labels = list(rng.choice(CALIB_LABELS, size=4, replace=False))
                _, r, _, _, _, _ = self.present(labels, seed=10_000 + i)
                rates.extend(r.tolist())
        finally:
            self.timeout_ms = keep
        self.thr_hz = float(np.mean(rates) + THR_Z * np.std(rates)) if thr is None else thr
        return {"pool_rate_mean_hz": round(float(np.mean(rates)), 2), "pool_rate_sd_hz": round(float(np.std(rates)), 2),
                "threshold_hz": round(self.thr_hz, 2)}


# --- the network that learns, and its frozen twin -------------------------------------------------------------------
def _save_npz_atomic(path, **arrays):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        with open(tmp, "wb") as f:
            np.savez(f, **arrays)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise


class LiveBrain:
    def __init__(self, n_neurons=N_NEURONS, weights=None, regions=None, twin=True, log=print):
        self.cfg = Config(n_neurons=n_neurons)
        self.net = LiveNet(self.cfg, regions)
        self.ch = Chooser(self.net)
        self.tw = Chooser(self.net.twin()) if twin else None
        if self.tw is not None:
            self.tw.pidx, self.tw.pre, self.tw.post = self.ch.pidx, self.ch.pre, self.ch.post
        self.dw = np.zeros(len(self.ch.pidx), dtype=np.float32)
        self.n_learn, self.n_decisions = 0, 0
        self.path = Path(weights) if weights else None
        self.pending = {}
        self.log = log
        self.t_start = time.time()
        self.calib = None
        self.load()
        if self.ch.thr_hz is None:
            dw, self.dw = self.dw, np.zeros_like(self.dw)
            self._apply()
            self.calib = self.ch.calibrate()                  # on the untrained network, as in #39
            self.dw = dw
            self._apply()
            self.save()
        if self.tw is not None:
            self.tw.thr_hz = self.ch.thr_hz

    # --- weights ---------------------------------------------------------------------------------------------------
    def _apply(self):
        w = np.clip(self.ch.w0 + self.dw, 0.0, self.ch.w_max)
        self.dw = (w - self.ch.w0).astype(np.float32)
        self.net.w[self.ch.pidx] = w

    def save(self):
        if self.path is None:
            return
        _save_npz_atomic(self.path, dw=self.dw, n_learn=self.n_learn, n_decisions=self.n_decisions,
                         thr_hz=np.nan if self.ch.thr_hz is None else self.ch.thr_hz,
                         config_hash=self.cfg.config_hash(), n_neurons=self.cfg.n_neurons, version=VERSION,
                         n_plastic=len(self.dw))

    def load(self):
        if self.path is None or not self.path.exists():
            return False
        try:
            with np.load(self.path) as z:
                if str(z["config_hash"]) != self.cfg.config_hash() or int(z["n_plastic"]) != len(self.dw):
                    self.log(f"spiking live: {self.path.name} is for another network, starting fresh")
                    return False
                self.dw = z["dw"].astype(np.float32)
                self.n_learn, self.n_decisions = int(z["n_learn"]), int(z["n_decisions"])
                thr = float(z["thr_hz"])
                self.ch.thr_hz = thr if math.isfinite(thr) else None
        except Exception as e:                                # torn or corrupt: keep it aside, start fresh
            aside = self.path.with_name(f"{self.path.name}.corrupt-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}")
            try:
                os.replace(self.path, aside)
            except OSError:
                pass
            self.log(f"spiking live: {self.path.name} unreadable ({type(e).__name__}), kept as {aside.name}; starting fresh")
            self.dw[:] = 0
            return False
        self._apply()
        return True

    def eta(self):
        return ETA * max(ETA_FLOOR, 1.0 / (1.0 + self.n_learn / ETA_HALF))

    # --- the protocol ----------------------------------------------------------------------------------------------
    def decide(self, labels, did=None):
        t0 = time.process_time()
        labels = [str(x)[:120] for x in list(labels)[:MAX_OPTIONS]]
        if len(labels) < 2:
            raise ValueError("need 2-6 options")
        self.n_decisions += 1
        seed = self.n_decisions * 7919 + 17
        pick, rates, ms, timeout, pre, post = self.ch.present(labels, seed)
        out = {"pick": pick, "pool_rates": [round(float(r), 3) for r in rates], "decision_ms": ms,
               "timeout": bool(timeout), "n_neurons": self.net.n, "threshold_hz": round(self.ch.thr_hz, 3)}
        if self.tw is not None:
            tp, tr, _, _, _, _ = self.tw.present(labels, seed)
            out.update(twin_pick=tp, twin_rates=[round(float(r), 3) for r in tr])
        act = pre > 0
        self.pending[did if did is not None else self.n_decisions] = (np.flatnonzero(act), pre[act], post[act], len(labels))
        while len(self.pending) > PENDING:
            self.pending.pop(next(iter(self.pending)))
        out["cpu_ms"] = round((time.process_time() - t0) * 1000, 1)
        return out

    def learn(self, did, followed, delta):
        """Dopamine for decision `did`: the option that was followed and the tastes prediction error of its stay."""
        tag = self.pending.pop(did, None)
        if tag is None:
            return {"ok": False, "why": "unknown or too old decision"}
        q, pre, post, k = tag
        try:
            delta, followed = float(delta), int(followed)
        except (TypeError, ValueError):
            return {"ok": False, "why": "bad delta"}
        if not math.isfinite(delta) or not 0 <= followed < k:
            return {"ok": False, "why": "bad delta"}
        da = max(-1.0, min(1.0, DA_GAIN * delta))
        p = np.where(post == followed, 1.0, np.where(post >= 0, -1.0 / max(1, k - 1), 0.0)).astype(np.float32)
        eta = self.eta()
        self.dw[q] += np.float32(eta * da) * pre * p
        self._apply()
        self.n_learn += 1
        self.save()
        return {"ok": True, "eta": round(eta, 4), "da": round(da, 4), "n_learn": self.n_learn,
                "dw_abs_mean": round(float(np.abs(self.dw).mean()), 5)}

    def status(self):
        return {"n_neurons": self.net.n, "n_synapses": self.net.n_syn, "n_plastic": len(self.dw),
                "n_decisions": self.n_decisions, "n_learn": self.n_learn, "eta": round(self.eta(), 4),
                "threshold_hz": None if self.ch.thr_hz is None else round(self.ch.thr_hz, 3),
                "dw_abs_mean": round(float(np.abs(self.dw).mean()), 5), "calibration": self.calib,
                "cpu_s": round(time.process_time(), 2), "uptime_s": round(time.time() - self.t_start, 1),
                "build_s": round(self.net.build_s, 2), "twin": self.tw is not None}


def serve(brain, inp, out):
    """Answer one JSON line per request until stdin closes."""
    def send(obj):
        out.write(json.dumps(obj) + "\n")
        out.flush()
    send({"op": "ready", **brain.status()})
    for line in inp:
        try:
            msg = json.loads(line)
            op, rid = msg.get("op"), msg.get("id")
            if op == "decide":
                send({"id": rid, **brain.decide(msg.get("labels") or [], did=rid)})
            elif op == "learn":
                send({"id": rid, **brain.learn(msg.get("decision"), msg.get("followed"), msg.get("delta"))})
            elif op == "status":
                send({"id": rid, **brain.status()})
            elif op == "stop":
                send({"id": rid, "ok": True})
                return
            else:
                send({"id": rid, "error": "unknown op"})
        except Exception as e:                                # one bad request never kills the network
            send({"id": (msg.get("id") if isinstance(locals().get("msg"), dict) else None),
                  "error": f"{type(e).__name__}: {str(e)[:120]}"})


def synthetic(brain, trials=100, seed=0, follow=0.7, vocab=None, probs=None, alpha=0.1, kmin=2, kmax=6):
    """A synthetic reward stream for checks (tests, docs/spiking/live.md): `vocab` labels with hidden reward
    probabilities; each decision offers a random 2-6 of them; the option followed is the network's pick with
    probability `follow` (else a random offered one, standing in for the rate model); reward ~ Bernoulli(p); dopamine
    = r - V[label], V += alpha (r - V) (a slow value estimate, like the tastes' prediction). Scored: the network's
    pick == the best offered option, for the learning network and its frozen twin on the same offers and noise."""
    vocab = list(vocab or ["read about bread", "tokyo parks", "train timetable", "cat videos", "jazz records", "old maps"])
    probs = np.asarray(probs if probs is not None else [0.8, 0.2, 0.3, 0.4, 0.2, 0.3], dtype=float)
    rng = np.random.default_rng(seed)
    V = {lb: 0.5 for lb in vocab}
    rows = []
    for t in range(trials):
        k = int(rng.integers(kmin, kmax + 1))
        off = [int(i) for i in rng.choice(len(vocab), size=k, replace=False)]
        labels = [vocab[i] for i in off]
        d = brain.decide(labels, did=("synthetic", t))
        fol = d["pick"] if rng.random() < follow else int(rng.integers(k))
        r = float(rng.random() < probs[off[fol]])
        delta = r - V[labels[fol]]
        V[labels[fol]] += alpha * delta
        brain.learn(("synthetic", t), fol, delta / DA_GAIN)    # da = r - V, in choice.py's units
        best = int(np.argmax(probs[off]))
        rows.append((int(d["pick"] == best), int(d.get("twin_pick") == best), 1.0 / k))
    a = np.array(rows, dtype=float)
    blk = lambda col: [round(float(a[i:i + 25, col].mean()), 3) for i in range(0, trials, 25)]
    return {"trials": trials, "seed": seed, "learned": round(float(a[:, 0].mean()), 3), "twin": round(float(a[:, 1].mean()), 3),
            "chance": round(float(a[:, 2].mean()), 3), "learned_last50": round(float(a[-50:, 0].mean()), 3),
            "twin_last50": round(float(a[-50:, 1].mean()), 3), "curve": blk(0), "twin_curve": blk(1)}


# --- the server side: starts the child, asks it, feeds it dopamine, keeps the day's log ------------------------------
CARD = ("A small simulated spiking network ({n} neurons) built on the same wiring takes part in his choices and learns "
        "from simulated reward.")
NOTE = ("Its lean is one small term in the vote (weight {w}); the rate model stays the main decider. \"Paid off\" = the "
        "stay on the chosen page raised his brain model's reward/attention activity above its recent average. Its lean "
        "also nudges which option is followed, so a match is a little more likely for it than for the frozen twin even "
        "without learning; the not-paid-off column shows how much.")


def _today(t=None):
    from datetime import datetime
    from sleep import TZ
    return datetime.fromtimestamp(time.time() if t is None else t, TZ).date().isoformat()


def score(rows, block=10):
    """Learning curve from logged decisions with an outcome: among the decisions whose followed option paid off, how
    often the network's pick was that option (learned, frozen twin, chance = mean 1/K); in blocks of `block`."""
    rows = [r for r in rows if isinstance(r, dict) and r.get("response") is not None and r.get("k")]
    paid = [r for r in rows if r["response"] > 0]
    unpaid = [r for r in rows if r["response"] <= 0]
    m = lambda rs, key: round(float(np.mean([r.get(key) == r["followed"] for r in rs])), 3) if rs else None
    chance = lambda rs: round(float(np.mean([1.0 / r["k"] for r in rs])), 3) if rs else None
    curve = [{"n": len(paid[i:i + block]), "learned": m(paid[i:i + block], "pick"), "twin": m(paid[i:i + block], "twin_pick"),
              "chance": chance(paid[i:i + block])} for i in range(0, len(paid), block)]
    return {"decisions_with_outcome": len(rows), "paid_off": len(paid),
            "matched_paid_off": {"learned": m(paid, "pick"), "twin": m(paid, "twin_pick"), "chance": chance(paid)},
            "matched_not_paid_off": {"learned": m(unpaid, "pick"), "twin": m(unpaid, "twin_pick"), "chance": chance(unpaid)},
            "curve": curve, "block": block}


class LiveClient:
    """The server's handle on the child process (asyncio). decide() never waits more than `timeout` seconds."""

    def __init__(self, data_dir, n_neurons=N_NEURONS, timeout=2.0, python=sys.executable, twin=True):
        self.dir = Path(data_dir) / "spiking"
        self.data_dir = Path(data_dir)
        self.log_path = self.dir / "live_choices.jsonl"
        self.n_neurons, self.timeout, self.python, self.twin = n_neurons, timeout, python, twin
        self.proc, self.ready, self.info = None, False, {}
        self.futs, self.next_id = {}, 0
        self.pending = None                  # the decision whose page he is on: learns when he leaves it
        self.last = None                     # the last decision, for the card
        self.slow, self.restarts, self.errors = 0, 0, 0
        self.cpu = {}
        self._reader_task = None
        self._stopping = False

    # --- the child process ---------------------------------------------------------------------------------------
    async def start(self):
        import asyncio
        env = {k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "LANG", "TZ", "SUB01_TZ", "PYTHONPATH")}
        env.update(OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", PYTHONUNBUFFERED="1")
        args = [self.python, "-m", "spiking.live", "--data-dir", str(self.data_dir), "--neurons", str(self.n_neurons)]
        if not self.twin:
            args.append("--no-twin")
        self.ready = False
        self.proc = await asyncio.create_subprocess_exec(*args, stdin=asyncio.subprocess.PIPE,
                                                         stdout=asyncio.subprocess.PIPE, env=env, cwd=str(HERE),
                                                         limit=1 << 20)
        self._reader_task = asyncio.get_running_loop().create_task(self._read(self.proc))

    def alive(self):
        return self.proc is not None and self.proc.returncode is None

    async def _read(self, proc):
        try:
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                try:
                    msg = json.loads(line)
                except ValueError:
                    continue
                if msg.get("op") == "ready":
                    self.info, self.ready = msg, True
                    print(f"spiking live: ready, {msg.get('n_neurons')} neurons, {msg.get('n_learn')} learned decisions",
                          flush=True)
                    continue
                fut = self.futs.pop(msg.get("id"), None)
                if fut is not None and not fut.done():
                    fut.set_result(msg)                   # an answer after its timeout finds no future: dropped
        finally:
            self.ready = False
            for f in self.futs.values():
                if not f.done():
                    f.set_result(None)
            self.futs.clear()

    def _send(self, msg):
        if not self.alive():
            return False
        try:
            self.proc.stdin.write((json.dumps(msg) + "\n").encode())
            return True
        except (BrokenPipeError, ConnectionResetError, RuntimeError):
            return False

    async def call(self, op, timeout=None, **kw):
        import asyncio
        if not self.ready:
            return None
        self.next_id += 1
        rid = self.next_id
        fut = asyncio.get_running_loop().create_future()
        self.futs[rid] = fut
        if not self._send({"id": rid, "op": op, **kw}):
            self.futs.pop(rid, None)
            return None
        try:
            return await asyncio.wait_for(fut, self.timeout if timeout is None else timeout)
        except asyncio.TimeoutError:
            self.futs.pop(rid, None)
            return None

    async def run(self, every=60.0):
        """Keep the child running (restart with a backoff) and sample its CPU use."""
        import asyncio
        backoff = 5.0
        while not self._stopping:
            if not self.alive():
                if self.proc is not None:
                    self.restarts += 1
                    print(f"spiking live: process exited ({self.proc.returncode}); restarting in {backoff:.0f} s", flush=True)
                    await asyncio.sleep(backoff)
                    backoff = min(600.0, backoff * 2)
                try:
                    await self.start()
                except OSError as e:
                    print("spiking live: could not start:", repr(e)[:120], flush=True)
            await asyncio.sleep(every)
            st = await self.call("status", timeout=10.0)
            if st and "cpu_s" in st:
                prev, now = self.cpu.get("_sample"), (time.time(), st["cpu_s"])
                self.cpu = {"_sample": now, "cpu_s": st["cpu_s"], "uptime_s": st.get("uptime_s"),
                            "avg_pct": round(100 * st["cpu_s"] / max(1.0, st.get("uptime_s") or 1.0), 2)}
                if prev:
                    self.cpu["recent_pct"] = round(100 * (now[1] - prev[1]) / max(1.0, now[0] - prev[0]), 2)
                self.info.update({k: st[k] for k in ("n_decisions", "n_learn", "eta", "dw_abs_mean") if k in st})
                backoff = 5.0

    async def stop(self):
        import asyncio
        self._stopping = True
        if self.alive():
            self._send({"op": "stop"})
            try:
                self.proc.stdin.close()
                await asyncio.wait_for(self.proc.wait(), 5)
            except (asyncio.TimeoutError, OSError):
                self.proc.kill()
                await self.proc.wait()

    # --- one choice ---------------------------------------------------------------------------------------------
    async def decide(self, labels):
        """The network's answer for these option labels, or {"why": ...} when it is down or too slow (the vote then
        skips the term)."""
        labels = [str(x) for x in labels][:MAX_OPTIONS]
        if len(labels) < 2:
            return {"why": "fewer than 2 options"}
        if not self.ready:
            return {"why": "spiking network offline"}
        t0 = time.perf_counter()
        ans = await self.call("decide", labels=labels)
        if ans is None:
            self.slow += 1
            return {"why": f"spiking network slower than {self.timeout:g} s"}
        if "error" in ans or len(ans.get("pool_rates") or []) != len(labels):
            self.errors += 1
            return {"why": "spiking network error"}
        ans["wall_ms"] = round((time.perf_counter() - t0) * 1000)
        ans["labels"] = labels
        return ans

    def followed(self, ans, chosen):
        """The vote followed option `chosen`: remember it until he leaves the page (then it learns)."""
        self.pending = None
        if not ans or "pool_rates" not in ans:
            return
        ln = lean(ans["pool_rates"])
        self.pending = {"id": ans["id"], "labels": ans["labels"], "pick": ans["pick"], "twin_pick": ans.get("twin_pick"),
                        "followed": int(chosen), "k": len(ans["labels"]), "t": time.time()}
        self.last = {"labels": ans["labels"], "lean": [round(float(x), 3) for x in ln], "pick": ans["pick"],
                     "twin_pick": ans.get("twin_pick"), "followed": int(chosen), "decision_ms": ans.get("decision_ms"),
                     "cpu_ms": ans.get("cpu_ms"), "t": round(time.time())}

    def outcome(self, response=None, delta=None):
        """He left the page the pending decision led to: its tastes response / prediction error (None if the stay was
        too short to measure) is logged, and the prediction error is the dopamine of that decision."""
        from state_io import append_jsonl
        p, self.pending = self.pending, None
        if p is None:
            return
        ok = delta is not None and math.isfinite(float(delta))
        if ok:
            self.next_id += 1
            self._send({"id": self.next_id, "op": "learn", "decision": p["id"], "followed": p["followed"],
                        "delta": float(delta)})
        row = {"t": round(p["t"]), "day": _today(p["t"]), "labels": [" ".join(label_words(x)) for x in p["labels"]],
               "k": p["k"], "pick": p["pick"], "twin_pick": p["twin_pick"], "followed": p["followed"],
               "response": round(float(response), 4) if ok and response is not None else None,
               "delta": round(float(delta), 4) if ok else None}
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            append_jsonl(self.log_path, row)
        except OSError as e:
            print("spiking live: could not log:", repr(e)[:120], flush=True)

    # --- the card -----------------------------------------------------------------------------------------------
    def view(self):
        from state_io import read_jsonl
        rows = read_jsonl(self.log_path, last=5000)
        today = _today()
        n = self.info.get("n_neurons") or self.n_neurons
        last = None
        if self.last:
            L = self.last
            top = int(np.argmax(L["lean"]))
            last = {**L, "leaned_to": L["labels"][top], "pick_label": L["labels"][L["pick"]],
                    "followed_label": L["labels"][L["followed"]]}
        w = float(os.environ.get("SUB01_SPIKING_W", 0.3))
        return {"state": "live" if self.ready else ("starting" if self.alive() else "offline"),
                "n_neurons": n, "card": CARD.format(n=f"{n:,}"), "note": NOTE.format(w=w), "weight": w,
                "decisions_today": sum(1 for r in rows if r.get("day") == today),
                "learned_today": sum(1 for r in rows if r.get("day") == today and r.get("delta") is not None),
                "n_decisions": self.info.get("n_decisions"), "n_learn": self.info.get("n_learn"), "eta": self.info.get("eta"),
                "last": last, "score": score(rows), "today": score([r for r in rows if r.get("day") == today]),
                "cpu": {k: v for k, v in self.cpu.items() if not k.startswith("_")},
                "slow": self.slow, "restarts": self.restarts, "timeout_s": self.timeout}


def day_choices(data_dir, day, cap=150):
    """The day's decisions with an outcome, for the night's GPU session (pod_manager): offered labels (as their cue
    words), the option followed and its prediction error; the newest `cap`."""
    from state_io import read_jsonl
    rows = [r for r in read_jsonl(Path(data_dir) / "spiking" / "live_choices.jsonl", last=5000)
            if r.get("day") == day and r.get("delta") is not None and 2 <= len(r.get("labels") or []) <= MAX_OPTIONS
            and isinstance(r.get("followed"), int) and 0 <= r["followed"] < len(r["labels"])]
    return [{"labels": [str(x)[:80] for x in r["labels"]], "followed": r["followed"], "delta": r["delta"],
             "response": r.get("response")} for r in rows[-cap:]]


def attach(app, client):
    """GET /api/spiking/live: the card on /brain (behind the site's password gate like every /api/ path)."""
    from aiohttp import web

    async def get(request):
        return web.json_response(client.view() if client else {"state": "off"})
    app.router.add_get("/api/spiking/live", get)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--neurons", type=int, default=N_NEURONS)
    ap.add_argument("--no-twin", action="store_true")
    a = ap.parse_args(argv)
    proto = sys.stdout
    sys.stdout = sys.stderr                                   # only protocol lines go to the parent's pipe
    log = lambda *x: print(*x, file=sys.stderr, flush=True)
    brain = LiveBrain(a.neurons, Path(a.data_dir) / "spiking" / "live_weights.npz", twin=not a.no_twin, log=log)
    log(f"spiking live: {brain.net.n:,} neurons, {brain.net.n_syn:,} synapses, {len(brain.dw):,} plastic, "
        f"threshold {brain.ch.thr_hz:.2f} Hz, built in {brain.net.build_s:.1f} s")
    serve(brain, sys.stdin, proto)


if __name__ == "__main__":
    main()
