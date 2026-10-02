"""A K-armed choice task for the spiking network: the model learns, from dopamine alone, to pick the rewarded cue.

Task (one trial):
- K options are offered (default: all of them). Each option is a cue: its label (a word) is hashed exactly as in
  memory.py (MemorySystem.word_neurons, same sha256 seed) to a fixed random fraction of the excitatory neurons of
  every parcel, of which the visual and language parcels are kept. Real option labels can be cues later.
- Action pools: the excitatory neurons of the striatum ("reward" group of regions.py: caudate, putamen,
  accumbens, both hemispheres) are split among the offered options. Each striatal neuron has a hashed affinity
  for every label and belongs to the offered option with the highest affinity: disjoint pools, the same pool for
  the same label set in every session. Why the striatum: cortico-striatal synapses are the classic site of
  dopamine-gated (three-factor) plasticity, and the real wiring gives a usable pathway: at 20k neurons ~2.3 of the
  30 long-range E inputs of a striatal neuron come from visual + language parcels; with all four cues driven and
  every cue -> pool-0 synapse set to w_max, pool 0 rises from ~6 to ~9 Hz (cue fraction 0.1) or from ~7.5 to
  ~15.6 Hz (cue fraction 0.3), noise sd < 1 Hz per 200 ms, the other pools stay within ~2 Hz of their baseline
  (measured, docs/spiking/choice.md). Salience parcels receive ~4x more cue input, the somatomotor ones about the
  same as the striatum; the striatum is chosen for the biology, not because it is the easiest.
- Decision = a race: the cues are driven (cue_amp mV); every 10 ms each pool's mean rate since cue onset is
  compared with a threshold (calibrated on the untrained network: pool-rate mean + thr_z sd at 100 ms). The first
  pool to cross it wins (after min_ms). At the timeout the pool with the highest rate is taken (a forced choice,
  flagged "timeout"), so learning never stalls. The cue is switched off at the decision; an inter-trial gap
  follows.
- Reward: Bernoulli with a hidden probability per option. Dopamine = reward prediction error
  delta = r - V[chosen option], V[k] += alpha * delta (a running estimate per cue). Reversal: halfway through the
  run the hidden probabilities are reversed (best <-> worst), which tests unlearning.

Learning rule (only on cue -> action synapses; the connectome weights w0 are never changed, all learning is in dw):
    tag_ij = pre_i * post_j, set at decision time (eligibility tagged at the decision, no 1 s trace to bridge):
        pre_i  = clamp((rate of cue neuron i during the decision window - 5 Hz) / 40 Hz, 0, 1)
        post_j = +1 if j is in the chosen pool, -1 / (K_offered - 1) if j is in another offered pool (zero-sum)
    dw_ij += eta_trial * delta * tag_ij, then w = clamp(w0 + dw, 0, w_max) as everywhere (plasticity.py).
eta_trial = eta (mV per unit delta) times an optional per-trial factor; an optional exploration bonus adds
bonus_mv / sqrt(1 + n_chosen_k) mV to the drive of each offered pool k (a count-based bonus, applied in training
only). The three-factor STDP of plasticity.py is not used here (its 1 s trace and spike-timing noise are what made
Pong slow); this rule is a rate-based three-factor rule with the eligibility set at the moment of the decision.

Controls (in every report): the same network with plasticity frozen (identical trials, no weight change), a
random chooser (no network), and the reversal phase. Criterion: `crit_correct` correct of the last `crit_window`
trials (default 14 of 20 = 70 %); "correct" = the option with the highest current reward probability.

The task logic (schedule, race, criterion, random chooser) is pure numpy so it is tested without torch.
"""
import hashlib
import math

import numpy as np

CUE_GROUPS = ("visual", "language")
ACTION_GROUP = "reward"
DEFAULT_LABELS = ("apple", "river", "cloud", "stone", "lamp", "bird", "salt", "rope")


# --- pure task logic (no torch) -------------------------------------------------------------------------------
class RewardSchedule:
    """Hidden reward probability per option; reversed (best <-> worst, order of the rest reversed too) at trial
    `reversal_at` (None: never)."""

    def __init__(self, probs, reversal_at=None, seed=0):
        self.p0 = np.asarray(probs, dtype=float)
        self.reversal_at = reversal_at
        self.rng = np.random.default_rng(seed)

    def probs(self, trial):
        if self.reversal_at is not None and trial >= self.reversal_at:
            order = np.argsort(self.p0, kind="stable")
            p = np.empty_like(self.p0)
            p[order] = self.p0[order[::-1]]                       # the k-th best gets the k-th worst probability
            return p
        return self.p0.copy()

    def best(self, trial, offered=None):
        p = self.probs(trial)
        idx = np.arange(len(p)) if offered is None else np.asarray(offered)
        return int(idx[np.argmax(p[idx])])

    def reward(self, trial, option):
        return float(self.rng.random() < self.probs(trial)[option])


def race(cum_counts, sizes, dt_ms, thr_hz, min_ms=0):
    """Decision race over one trial. cum_counts: (T, K) spike counts of each pool since cue onset, one row per
    check (every dt_ms). Returns (winner, decision_ms, timeout): the first check at or after min_ms where a pool's
    mean rate is above thr_hz (ties -> the higher rate); otherwise the highest rate at the last check."""
    cum = np.asarray(cum_counts, dtype=float)
    sizes = np.maximum(1, np.asarray(sizes, dtype=float))
    for t in range(cum.shape[0]):
        ms = (t + 1) * dt_ms
        if ms < min_ms:
            continue
        r = cum[t] / sizes / (ms / 1000.0)
        if (r > thr_hz).any():
            return int(np.argmax(r)), ms, False
    r = cum[-1] / sizes / (cum.shape[0] * dt_ms / 1000.0)
    return int(np.argmax(r)), cum.shape[0] * dt_ms, True


def trials_to_criterion(correct, window=20, need=14, start=0):
    """Number of trials from `start` until `need` of the last `window` are correct (None if never)."""
    c = np.asarray(correct[start:], dtype=int)
    if len(c) < window:
        return None
    s = np.convolve(c, np.ones(window, dtype=int), mode="valid")
    hit = np.nonzero(s >= need)[0]
    return int(hit[0] + window) if hit.size else None


def curve(correct, block=20):
    c = np.asarray(correct, dtype=float)
    return [round(float(c[i:i + block].mean()), 3) for i in range(0, len(c) - block + 1, block)]


def random_chooser(schedule, trials, k, seed=0, window=20, need=14):
    """The chance baseline: uniform choices on the same schedule (no network)."""
    rng = np.random.default_rng(seed)
    ch = rng.integers(0, k, size=trials)
    correct = [int(ch[t] == schedule.best(t)) for t in range(trials)]
    rewards = [schedule.reward(t, int(ch[t])) for t in range(trials)]
    return summarize(correct, rewards, schedule.reversal_at, window, need)


def summarize(correct, rewards, reversal_at, window=20, need=14):
    n = len(correct)
    rev = reversal_at if reversal_at is not None and reversal_at < n else None
    pre = correct[:rev] if rev is not None else correct
    out = {"trials": n, "frac_correct": round(float(np.mean(correct)), 4) if n else None,
           "reward_rate": round(float(np.mean(rewards)), 4) if n else None,
           "trials_to_criterion": trials_to_criterion(pre, window, need),
           "frac_correct_last20_before_reversal": round(float(np.mean(pre[-20:])), 4) if len(pre) else None,
           "curve": curve(correct)}
    if rev is not None:
        post = correct[rev:]
        out.update(reversal_at=rev, trials_to_criterion_after_reversal=trials_to_criterion(post, window, need),
                   frac_correct_after_reversal=round(float(np.mean(post)), 4),
                   frac_correct_last20=round(float(np.mean(post[-20:])), 4))
    return out


def _affinity(label, n):
    """Hashed affinity of every action neuron for a label (deterministic, the same in every session)."""
    h = hashlib.sha256(("sub01-choice-pool:" + label).encode()).digest()
    return np.random.default_rng(int.from_bytes(h[:8], "little")).random(n)


# --- the task on a SpikingNet ---------------------------------------------------------------------------------
class ChoiceTask:
    """K-armed choice on a SpikingNet (see the module doc). mode of run(): 'train' (learning) or 'exam' (frozen)."""

    def __init__(self, net, labels=None, k=4, probs=None, cue_frac=0.15, cue_amp=8.0, check_ms=10, min_ms=50,
                 timeout_ms=250, iti_ms=150, thr_z=2.0, eta=0.6, alpha=0.1, v0=0.5, bonus_mv=0.0,
                 eta_decay=0.0, seed=0):
        import torch
        from .memory import MemorySystem
        self.torch = torch
        self.net, self.k = net, k
        self.labels = list(labels or DEFAULT_LABELS[:k])
        assert len(self.labels) == k
        self.probs = list(probs if probs is not None else np.linspace(0.8, 0.2, k).round(3))
        self.cue_amp, self.check_ms, self.min_ms, self.timeout_ms, self.iti_ms = cue_amp, check_ms, min_ms, timeout_ms, iti_ms
        self.thr_z, self.eta, self.alpha, self.v0, self.bonus_mv, self.eta_decay = thr_z, eta, alpha, v0, bonus_mv, eta_decay
        self.seed = seed
        reg = net.reg
        cue_regions = sorted(set(sum((reg.groups[g] for g in CUE_GROUPS), [])))
        cue_space = np.concatenate([net.region_neurons(r, exc_only=True) for r in cue_regions])
        mem = MemorySystem(net, frac=cue_frac)                       # the memory.py hashing, at the cue density
        self.cues = [np.intersect1d(mem.word_neurons(w), cue_space) for w in self.labels]
        self.action = net.group_neurons(ACTION_GROUP, exc_only=True)
        self.aff = np.stack([_affinity(w, len(self.action)) for w in self.labels])       # (K, n_action)
        p = net.plast
        self.syn = None
        if p is not None:                                            # plastic cue -> action synapses (ids into dw)
            is_cue = np.zeros(net.n, bool)
            is_cue[np.concatenate(self.cues)] = True
            is_act = np.zeros(net.n, bool)
            is_act[self.action] = True
            psrc, pdst = p.psrc.long().cpu().numpy(), p.pdst.long().cpu().numpy()
            q = np.nonzero(is_cue[psrc] & is_act[pdst])[0]
            self.syn = {"q": torch.as_tensor(q, device=net.device), "pre": psrc[q], "post": pdst[q]}
        self.V = np.full(k, v0)
        self.n_chosen = np.zeros(k)
        self.thr_hz = None
        self.trial = 0                                               # trials of training so far (schedule clock)
        self.log = []
        self.last = None                                             # last trial (for the live frame)

    # --- pools ------------------------------------------------------------------------------------------------
    def pools(self, offered):
        owner = np.asarray(offered)[np.argmax(self.aff[list(offered)], axis=0)]
        return [self.action[owner == o] for o in offered]

    def synapse_count(self):
        """Plastic cue -> pool synapses per (cue, pool) for the full offer (a pathway exists only if > 0)."""
        if self.syn is None:
            return None
        pools = self.pools(range(self.k))
        out = np.zeros((self.k, self.k), dtype=int)
        for i, c in enumerate(self.cues):
            m = np.isin(self.syn["pre"], c)
            for j, pl in enumerate(pools):
                out[i, j] = int((m & np.isin(self.syn["post"], pl)).sum())
        return out.tolist()

    # --- one trial ------------------------------------------------------------------------------------------------
    def _present(self, offered, learn):
        """Drive the offered cues, run the race; returns (winner option, decision ms, timeout, cue rates)."""
        torch, net = self.torch, self.net
        pools = self.pools(offered)
        sizes = np.array([len(pl) for pl in pools])
        pool_t = [torch.as_tensor(pl, device=net.device) for pl in pools]
        cue_ids = np.unique(np.concatenate([self.cues[o] for o in offered]))
        net.set_neuron_drive("choice_cue", cue_ids, self.cue_amp)
        bonus = [f"choice_bonus{o}" for o in offered] if (learn and self.bonus_mv > 0) else []
        for name, pl, o in zip(bonus, pools, offered):                 # count-based exploration bonus
            net.set_neuron_drive(name, pl, self.bonus_mv / math.sqrt(1 + self.n_chosen[o]))
        snap = net.snapshot()
        c0 = net.count
        base = [float(c0[pt].sum()) for pt in pool_t]
        cum = []
        winner = None
        n_checks = int(self.timeout_ms // self.check_ms)
        try:
            for t in range(n_checks):
                net.run(self.check_ms)
                row = [float(net.count[pt].sum()) - b for pt, b in zip(pool_t, base)]
                cum.append(row)
                ms = (t + 1) * self.check_ms
                if self.thr_hz is not None and ms >= self.min_ms:
                    r = np.array(row) / sizes / (ms / 1000.0)
                    if (r > self.thr_hz).any():
                        winner = (int(np.argmax(r)), ms, False)
                        break
            if winner is None:
                w, _, _ = race(cum[-1:], sizes, len(cum) * self.check_ms, float("inf"))
                winner = (w, len(cum) * self.check_ms, True)
            pre = net.rates_since(snap, self.syn["pre"]) if (learn and self.syn is not None) else None
        finally:
            net.set_neuron_drive("choice_cue", None)
            for name in bonus:
                net.set_neuron_drive(name, None)
        w, ms, to = winner
        return offered[w], ms, to, pre, pools, np.asarray(cum)

    def _learn(self, chosen, offered, pools, pre_rates, delta):
        p = self.net.plast
        if p is None or p.frozen or self.syn is None or delta == 0.0:
            return 0.0
        torch = self.torch
        post = np.zeros(self.net.n, dtype=np.float32)
        ko = len(offered)
        for o, pl in zip(offered, pools):
            post[pl] = 1.0 if o == chosen else -1.0 / max(1, ko - 1)
        pre = ((pre_rates - 5.0) / 40.0).clamp(0.0, 1.0)
        tag = pre * torch.as_tensor(post[self.syn["post"]], device=self.net.device)
        eta = self.eta / (1.0 + self.eta_decay * self.trial)
        q = self.syn["q"]
        p.dw.index_add_(0, q, eta * delta * tag)
        p._apply()
        return float((eta * delta * tag).abs().sum())

    def calibrate(self, presentations=12):
        """Threshold = mean + thr_z sd of the pool rates at 100 ms, on the network as it is (plasticity frozen)."""
        p = self.net.plast
        was = p.frozen if p is not None else None
        if p is not None:
            p.frozen = True
        rates = []
        thr, self.thr_hz = self.thr_hz, None
        try:
            for _ in range(presentations):
                offered = list(range(self.k))
                _, _, _, _, pools, cum = self._present(offered, learn=False)
                i = min(len(cum), max(1, 100 // self.check_ms)) - 1
                rates.extend((cum[i] / np.array([len(pl) for pl in pools]) / ((i + 1) * self.check_ms / 1000)).tolist())
                self.net.run(self.iti_ms)
        finally:
            if p is not None:
                p.frozen = was
        self.thr_hz = float(np.mean(rates) + self.thr_z * np.std(rates)) if thr is None else thr
        self.calib = {"pool_rate_mean_hz": round(float(np.mean(rates)), 2), "pool_rate_sd_hz": round(float(np.std(rates)), 2),
                      "threshold_hz": round(self.thr_hz, 2)}
        return self.calib

    def run(self, trials, schedule, mode="train", offered=None, on_trial=None):
        """Play `trials` trials on `schedule` (its clock is self.trial in training, the trial index in exams)."""
        if self.thr_hz is None:
            self.calibrate()
        p = self.net.plast
        was = p.frozen if p is not None else None
        if p is not None and mode != "train":
            p.frozen = True
        correct, rewards, timeouts, rts = [], [], [], []
        try:
            for i in range(trials):
                clock = self.trial if mode == "train" else i
                off = list(offered if offered is not None else range(self.k))
                chosen, ms, to, pre, pools, _ = self._present(off, learn=(mode == "train"))
                r = schedule.reward(clock, chosen)
                delta = 0.0
                if mode == "train":
                    delta = r - self.V[chosen]
                    self.V[chosen] += self.alpha * delta
                    self.n_chosen[chosen] += 1
                    self._learn(chosen, off, pools, pre, delta)
                    self.trial += 1
                ok = int(chosen == schedule.best(clock, off))
                correct.append(ok)
                rewards.append(r)
                timeouts.append(int(to))
                rts.append(ms)
                self.last = {"trial": clock, "chosen": self.labels[chosen], "correct": bool(ok), "reward": r,
                             "dopamine": round(delta, 3), "rt_ms": ms, "timeout": bool(to), "mode": mode}
                if on_trial:
                    on_trial(self.last)
                self.net.run(self.iti_ms)
        finally:
            if p is not None:
                p.frozen = was
        return {"correct": correct, "rewards": rewards, "timeout_frac": round(float(np.mean(timeouts)), 3) if timeouts else None,
                "mean_rt_ms": round(float(np.mean(rts)), 1) if rts else None}

    def train(self, trials, schedule, on_trial=None):
        res = self.run(trials, schedule, "train", on_trial=on_trial)
        self.log.extend(res["correct"])
        return res

    def exam(self, trials, probs=None):
        """Frozen test on the current hidden probabilities (no reward-driven change)."""
        sch = RewardSchedule(probs if probs is not None else self.probs, None, seed=self.seed + 99)
        res = self.run(trials, sch, "exam")
        return {"trials": trials, "frac_correct": round(float(np.mean(res["correct"])), 4),
                "reward_rate": round(float(np.mean(res["rewards"])), 4), "timeout_frac": res["timeout_frac"],
                "mean_rt_ms": res["mean_rt_ms"]}

    def dw_stats(self):
        """Learned cue -> pool weight per (cue, pool) for the full offer (mean dw, mV)."""
        if self.syn is None:
            return None
        p = self.net.plast
        dw = p.dw[self.syn["q"]].cpu().numpy()
        pools = self.pools(range(self.k))
        out = np.zeros((self.k, self.k))
        for i, c in enumerate(self.cues):
            m = np.isin(self.syn["pre"], c)
            for j, pl in enumerate(pools):
                s = m & np.isin(self.syn["post"], pl)
                out[i, j] = float(dw[s].mean()) if s.any() else 0.0
        return np.round(out, 4).tolist()


def experiment(net, trials=160, k=4, probs=None, reversal=True, seed=0, frozen_net=None, window=20, need=14,
               on_trial=None, **task_kw):
    """Train on the schedule (reversal halfway) and run the controls on identical trials/rewards:
    - frozen: `frozen_net` (a twin of `net`, or None: `net` itself before training, with plasticity frozen);
    - random chooser. Returns a report dict (all numbers, whatever they are)."""
    probs = list(probs if probs is not None else np.linspace(0.8, 0.2, k).round(3))
    rev = trials // 2 if reversal else None
    out = {"k": k, "probs": probs, "trials": trials, "reversal_at": rev,
           "criterion": f"{need} of the last {window} trials correct"}
    task = ChoiceTask(net, k=k, probs=probs, seed=seed, **task_kw)
    out["calibration"] = task.calibrate()
    out["cue_pool_synapses"] = task.synapse_count()
    out["pool_sizes"] = [len(pl) for pl in task.pools(range(k))]
    out["cue_sizes"] = [len(c) for c in task.cues]
    # frozen control first (same network, no learning), on its own copy of the same reward stream
    ctrl_net = frozen_net if frozen_net is not None else net
    ctrl = ChoiceTask(ctrl_net, k=k, probs=probs, seed=seed, **task_kw)
    ctrl.thr_hz = task.thr_hz
    r = ctrl.run(trials, RewardSchedule(probs, rev, seed=seed), mode="exam")
    out["frozen"] = {**summarize(r["correct"], r["rewards"], rev, window, need), "timeout_frac": r["timeout_frac"]}
    res = task.train(trials, RewardSchedule(probs, rev, seed=seed), on_trial=on_trial)
    out["learned"] = {**summarize(res["correct"], res["rewards"], rev, window, need),
                      "timeout_frac": res["timeout_frac"], "mean_rt_ms": res["mean_rt_ms"]}
    out["random"] = random_chooser(RewardSchedule(probs, rev, seed=seed), trials, k, seed=seed + 1,
                                   window=window, need=need)
    out["dw_cue_pool_mean_mv"] = task.dw_stats()
    out["task"] = task
    return out


# --- real labels, variable offers: the live decisions (#58) ------------------------------------------------------
LIVE_WORDS = 3                   # content words of a label that become its cue
LIVE_WORD_FRAC = 0.05            # per word: 3 words ~ the 15 % cue of one ChoiceTask label
MAX_LIVE_LABELS = 4096           # per-label value estimates kept (least recently used dropped)


def label_key(label):
    """The label as the network sees it: its first content words (case, punctuation and stop words dropped)."""
    from .words import words
    ws = words(str(label))[:LIVE_WORDS]
    return " ".join(ws) if ws else str(label).strip().lower()[:80]


class LiveChooser:
    """Decisions among real option labels (2-6 of them, any text) on a SpikingNet: the ChoiceTask race and its
    dopamine rule, with cues and pools built per decision.

    - Cue of a label: the union of its first LIVE_WORDS content words, each hashed as in memory.py at
      LIVE_WORD_FRAC of the excitatory neurons of every visual and language parcel; labels that share a word
      share part of their cue. Pools: the striatal neurons split among the offered labels by hashed affinity.
    - decide() runs the race and returns the pick, the pool rates and an eligibility tag set at the decision
      (pre = cue-neuron rate in the window, post = +1 chosen pool, -1/(K-1) other offered pools).
    - reward() applies dw += eta_l * delta * tag with delta = value - V[label] (the #39 rule). Stability fix
      (docs/spiking/choice.md: preferences flipped back and forth): a slow value estimate (alpha 0.05 instead of
      0.1) and a learning rate that decays with the number of rewards a label has had,
      eta_l = max(eta_min, eta / sqrt(1 + n_label / eta_tau)). `value` may be a reward-prediction error already
      (the tastes signal, mean ~0) or an outcome (chess: +1 / 0 / -1); V absorbs a constant offset either way.
    """

    def __init__(self, net, cue_amp=8.0, check_ms=10, min_ms=50, timeout_ms=250, thr_z=2.0, eta=0.6,
                 eta_min=0.15, eta_tau=20.0, alpha=0.05, word_frac=LIVE_WORD_FRAC):
        import torch
        from .memory import MemorySystem
        self.torch, self.net = torch, net
        self.cue_amp, self.check_ms, self.min_ms, self.timeout_ms = cue_amp, check_ms, min_ms, timeout_ms
        self.thr_z, self.eta, self.eta_min, self.eta_tau, self.alpha = thr_z, eta, eta_min, eta_tau, alpha
        reg = net.reg
        cue_regions = sorted(set(sum((reg.groups[g] for g in CUE_GROUPS), [])))
        self.cue_space = np.concatenate([net.region_neurons(r, exc_only=True) for r in cue_regions])
        self.mem = MemorySystem(net, frac=word_frac)
        self.action = net.group_neurons(ACTION_GROUP, exc_only=True)
        self._cues, self._aff = {}, {}
        self.V, self.n = {}, {}
        self.thr_hz, self.calib = None, None
        self.syn = None
        p = net.plast
        if p is not None:
            in_cue = np.zeros(net.n, bool)
            in_cue[self.cue_space] = True
            is_act = np.zeros(net.n, bool)
            is_act[self.action] = True
            psrc, pdst = p.psrc.long().cpu().numpy(), p.pdst.long().cpu().numpy()
            q = np.nonzero(in_cue[psrc] & is_act[pdst])[0]
            self.syn = {"q": q, "pre": psrc[q], "post": pdst[q]}

    # --- cues and pools -----------------------------------------------------------------------------------------
    def cue(self, label):
        key = label_key(label)
        if key not in self._cues:
            from .words import words
            ws = words(key) or [key]
            ids = np.unique(np.concatenate([self.mem.word_neurons(w) for w in ws]))
            self._cues[key] = np.intersect1d(ids, self.cue_space)
        return self._cues[key]

    def affinity(self, label):
        key = label_key(label)
        if key not in self._aff:
            self._aff[key] = _affinity(key, len(self.action))
        return self._aff[key]

    def pools(self, labels):
        """Disjoint striatal pools for the offered labels (a repeated label gets an empty pool: it cannot win)."""
        aff = np.stack([self.affinity(lb) for lb in labels])
        owner = np.argmax(aff, axis=0)
        return [self.action[owner == i] for i in range(len(labels))]

    # --- one decision -------------------------------------------------------------------------------------------
    def decide(self, labels, learn=True, force=None):
        """Race among `labels`. Returns {pick, pool_rates, sim_ms, timeout, elig}; elig (for reward()) is None
        without plasticity or when learn is False. `force`: tag that option as chosen (night replay of a real
        decision) while still reporting the network's own pick."""
        torch, net = self.torch, self.net
        labels = [str(x) for x in labels]
        if len(labels) < 2:
            raise ValueError("a decision needs at least two options")
        pools = self.pools(labels)
        sizes = np.array([max(1, len(pl)) for pl in pools])
        pool_t = [torch.as_tensor(pl, device=net.device) for pl in pools]
        cue_ids = np.unique(np.concatenate([self.cue(lb) for lb in labels]))
        net.set_neuron_drive("live_cue", cue_ids, self.cue_amp)
        snap = net.snapshot()
        base = [float(net.count[pt].sum()) for pt in pool_t]
        row, winner, ms = None, None, 0
        try:
            for t in range(int(self.timeout_ms // self.check_ms)):
                net.run(self.check_ms)
                ms = (t + 1) * self.check_ms
                row = np.array([float(net.count[pt].sum()) - b for pt, b in zip(pool_t, base)])
                if self.thr_hz is not None and ms >= self.min_ms:
                    r = row / sizes / (ms / 1000.0)
                    if (r > self.thr_hz).any():
                        winner = int(np.argmax(r))
                        break
            rates = row / sizes / (ms / 1000.0)
            timeout = winner is None
            if timeout:
                winner = int(np.argmax(rates))
            elig = None
            if learn and self.syn is not None:
                sel = np.isin(self.syn["pre"], cue_ids)
                if sel.any():
                    pre = net.rates_since(snap, self.syn["pre"][sel])
                    chosen = winner if force is None else int(force)
                    post = np.zeros(net.n, dtype=np.float32)
                    for i, pl in enumerate(pools):
                        post[pl] = 1.0 if i == chosen else -1.0 / max(1, len(labels) - 1)
                    tag = ((pre - 5.0) / 40.0).clamp(0.0, 1.0) * torch.as_tensor(post[self.syn["post"][sel]],
                                                                                    device=net.device)
                    elig = {"q": torch.as_tensor(self.syn["q"][sel], device=net.device), "tag": tag,
                            "label": label_key(labels[chosen])}
        finally:
            net.set_neuron_drive("live_cue", None)
        return {"pick": winner, "pool_rates": [round(float(x), 3) for x in rates], "sim_ms": float(ms),
                "timeout": bool(timeout), "elig": elig}

    def eta_for(self, key):
        return max(self.eta_min, self.eta / math.sqrt(1.0 + self.n.get(key, 0) / self.eta_tau))

    def reward(self, elig, value):
        """Dopamine for one decision: delta = value - V[chosen label]; returns {delta, eta, dw_abs}."""
        if elig is None:
            return {"delta": 0.0, "eta": 0.0, "dw_abs": 0.0}
        key = elig["label"]
        value = float(np.clip(float(value), -1.0, 1.0))
        v = self.V.pop(key, 0.0)
        delta = value - v
        self.V[key] = v + self.alpha * delta                           # re-inserted last: LRU order
        eta = self.eta_for(key)
        self.n[key] = self.n.get(key, 0) + 1
        while len(self.V) > MAX_LIVE_LABELS:
            old = next(iter(self.V))
            self.V.pop(old)
            self.n.pop(old, None)
        p = self.net.plast
        if p is None or p.frozen or delta == 0.0:
            return {"delta": round(delta, 4), "eta": round(eta, 4), "dw_abs": 0.0}
        d = eta * delta * elig["tag"]
        p.dw.index_add_(0, elig["q"], d)
        p._apply()
        return {"delta": round(delta, 4), "eta": round(eta, 4), "dw_abs": round(float(d.abs().sum()), 4)}

    def calibrate(self, presentations=12, iti_ms=150, labels=DEFAULT_LABELS[:4]):
        """Threshold = mean + thr_z sd of the pool rates at 100 ms (no learning), as ChoiceTask.calibrate."""
        p = self.net.plast
        was = p.frozen if p is not None else None
        if p is not None:
            p.frozen = True
        rates = []
        self.thr_hz = None
        i = min(int(self.timeout_ms // self.check_ms), max(1, 100 // self.check_ms))
        try:
            for _ in range(presentations):
                to, self.timeout_ms = self.timeout_ms, i * self.check_ms
                try:
                    rates.extend(self.decide(list(labels), learn=False)["pool_rates"])
                finally:
                    self.timeout_ms = to
                self.net.run(iti_ms)
        finally:
            if p is not None:
                p.frozen = was
        self.thr_hz = float(np.mean(rates) + self.thr_z * np.std(rates))
        self.calib = {"pool_rate_mean_hz": round(float(np.mean(rates)), 2), "pool_rate_sd_hz": round(float(np.std(rates)), 2),
                      "threshold_hz": round(self.thr_hz, 2), "thr_z": self.thr_z}
        return self.calib

    # --- persistence (kept in the learned-weights meta) ----------------------------------------------------------
    def to_meta(self):
        return {"V": {k: round(v, 5) for k, v in self.V.items()}, "n": dict(self.n)}

    def from_meta(self, meta):
        meta = meta or {}
        self.V = {str(k): float(v) for k, v in (meta.get("V") or {}).items()}
        self.n = {str(k): int(v) for k, v in (meta.get("n") or {}).items()}


def replay_fit(decisions, picks):
    """How well a network's own picks agree with the outcome of real decisions: for each rewarded decision
    (value > 0) a hit when it picks the real pick, for each punished one (value < 0) a hit when it picks another
    option. Returns (fit fraction or None, n)."""
    hits = n = 0
    for d, mine in zip(decisions, picks):
        v = d.get("reward")
        if v is None or v == 0:
            continue
        n += 1
        hits += int((mine == d["pick"]) if v > 0 else (mine != d["pick"]))
    return (round(hits / n, 4) if n else None), n
