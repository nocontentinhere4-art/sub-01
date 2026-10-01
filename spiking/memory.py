"""Memory in the synapses: chat messages -> sparse patterns -> hippocampal assemblies -> REM consolidation.

- Pattern: every content word of an (already filtered) chat message is hashed (sha256) to a fixed random 2 %
  of the excitatory neurons of each language / visual / default-network parcel, and to 0.5 % of the excitatory
  neurons of each hippocampus. The hippocampal part stands in for the entorhinal input layer, which this atlas
  does not contain (cortex -> hippocampus fibres here are too few, at 30 long-range synapses per neuron, to give
  a pattern-specific hippocampal response; measured: cos 0.47 same vs 0.58 different message). A message = the
  union of its words. Deterministic: the same word always lands on the same neurons, in every session.
- Encoding (awake, fast): the pattern is driven for 500 ms while the ENC modulator is on. The three-factor rule
  with a high hippocampal learning rate binds the co-active neurons on the CA3-like recurrent collaterals (100
  extra E->E synapses per hippocampal neuron); cortical synapses among the same neurons learn ~50x slower.
- Recall test (plasticity frozen): cue = the first half of the message's words (cortical + hippocampal parts).
  Completion score, separately in hippocampus and cortex:
      (rate of the uncued words' neurons - rate of other neurons in the same regions) during the cue
      / (the same difference when all words are driven)
  Lures (word sets never stored) go through the identical procedure and give the null distribution; a message
  counts as recalled when its score exceeds the lures' mean + 3 sd.
- REM replay: a brief excitability burst in the hippocampus; the stored assembly whose hippocampal neurons respond
  most wins (decayed or overwritten assemblies win less). Its pattern is then reinstated at 35 % of the waking
  drive while CONS is on, so cortical synapses among its words slowly strengthen (complementary learning
  systems). Simplification: hippocampus -> neocortex fibres carry < 2 % of cortical long-range input in this
  connectome, too few to reinstate a pattern on their own, so the cortical reinstatement is applied as an input
  selected by the hippocampal competition.
- Forgetting: hippocampal learned weights decay between sessions (tau 3 days), cortical ones slowly (60 days),
  and the zero-sum update makes each new encoding take a little from synapses of inactive assemblies.
"""
import hashlib
import re

import numpy as np
import torch

INPUT_GROUPS = ("language", "visual", "default")
STOP = set("""a an the and or but if of to in on at by for with from as is are was were be been am it its this that
these those there here i me my we our you your he she they them his her their what which who whom do does did
not no so than too very can will just il lo la le gli i un una e o di da in con su per tra fra che non è sono
mi ti si ci vi del della dei delle al alla ai alle""".split())


def words(text, max_words=12):
    toks = re.findall(r"[^\W\d_]{2,}", (text or "").lower())
    seen, out = set(), []
    content = [w for w in toks if w not in STOP] or toks
    for w in content:
        if w not in seen:
            seen.add(w)
            out.append(w)
    return out[:max_words]


class MemorySystem:
    def __init__(self, net, frac=0.02, frac_hc=0.005, amp=8.0, enc_ms=500, cue_ms=500, gap_ms=300,
                 replay_amp=0.35, cap=50, cons_theta=6.0):
        self.net, self.frac, self.frac_hc, self.amp = net, frac, frac_hc, amp
        self.enc_ms, self.cue_ms, self.gap_ms, self.replay_amp, self.cap = enc_ms, cue_ms, gap_ms, replay_amp, cap
        self.cons_theta = cons_theta       # replay drives at 35 %: lower Hebbian threshold
        reg = net.reg
        self.input_regions = sorted(set(sum((reg.groups[g] for g in INPUT_GROUPS), [])))
        self.hc_e = np.concatenate([net.region_neurons(r, exc_only=True) for r in reg.groups["memory"]])
        in_e = np.concatenate([net.region_neurons(r, exc_only=True) for r in self.input_regions])
        self.input_e = in_e
        self.hc_drive = np.zeros(reg.n)
        self.hc_drive[reg.groups["memory"]] = 2.0
        self.registry = []
        self._cache = {}

    # --- patterns -----------------------------------------------------------------------------------------------
    def word_neurons(self, word):
        if word not in self._cache:
            h = hashlib.sha256(("sub01-spiking:" + word).encode()).digest()
            rng = np.random.default_rng(int.from_bytes(h[:8], "little"))
            ids = []
            for r in self.input_regions + self.net.reg.groups["memory"]:
                ne = int(self.net.n_exc[r])
                k = max(1, int(round((self.frac_hc if r in self.net.hc_regions else self.frac) * ne)))
                ids.append(self.net.off[r] + rng.choice(ne, size=k, replace=False))
            self._cache[word] = np.sort(np.concatenate(ids))
        return self._cache[word]

    def pattern(self, ws):
        return np.unique(np.concatenate([self.word_neurons(w) for w in ws])) if ws else np.zeros(0, np.int64)

    def split(self, ids):
        """(hippocampal part, cortical part) of a set of neuron ids."""
        hc = np.isin(ids, self.hc_e)
        return ids[hc], ids[~hc]

    # --- primitives ---------------------------------------------------------------------------------------------
    def _present(self, ids, ms, amp):
        """Drive neurons `ids` for ms; return (hippocampal E rates, snapshot) over the window."""
        net = self.net
        net.set_neuron_drive("memory", ids, amp)
        snap = net.snapshot()
        net.run(ms)
        h = net.rates_since(snap, self.hc_e)
        net.set_neuron_drive("memory", None)
        return h, snap

    def _rest(self, ms=None):
        snap = self.net.snapshot()
        self.net.run(ms or self.gap_ms)
        return snap

    # --- encoding ----------------------------------------------------------------------------------------------
    def encode(self, text, day=None):
        ws = words(text)
        if not ws:
            return None
        net, p = self.net, self.net.plast
        ids = self.pattern(ws)
        base = self._rest()
        r0 = net.rates_since(base)
        h, snap = self._present(ids, self.enc_ms, self.amp)
        if p is not None:                  # fast Hebbian, expressed after the window (no runaway feedback)
            p.hebbian(net.rates_since(snap) - r0, "enc", self.enc_ms / 1000.0)
        drive_rate = float(net.rates_since(snap, ids).mean())
        index = self.split(ids)[0]
        self._rest()
        rec = {"text": text, "words": ws, "day": day, "index": index.astype(int).tolist(), "drive_rate": drive_rate}
        self.registry = [m for m in self.registry if m["text"] != text] + [rec]
        del self.registry[:-self.cap]
        return rec

    # --- recall test ---------------------------------------------------------------------------------------------
    def _probe(self, ws):
        """Frozen-weight probe of one word list: all words driven, then the first half as a cue."""
        net = self.net
        half = max(1, len(ws) // 2)
        cue_ids = self.pattern(ws[:half])
        all_ids = self.pattern(ws)
        tgt = np.setdiff1d(all_ids, cue_ids)
        out = {"cue": ws[:half]}
        snap_full = self._present(all_ids, self.cue_ms, self.amp)[1]
        r_full = net.rates_since(snap_full)
        self._rest()
        snap_cue = self._present(cue_ids, self.cue_ms, self.amp)[1]
        r_cue = net.rates_since(snap_cue)
        self._rest()
        for part, pool in (("hc", self.hc_e), ("ctx", self.input_e)):
            t = np.intersect1d(tgt, pool)
            o = np.setdiff1d(pool, all_ids)
            if len(t) == 0 or len(o) == 0:
                out[part] = 0.0
                continue
            ti = torch.as_tensor(t, device=net.device)
            oi = torch.as_tensor(o, device=net.device)
            full = float(r_full[ti].mean() - r_full[oi].mean())
            cue = float(r_cue[ti].mean() - r_cue[oi].mean())
            out[part] = cue / max(1e-6, full)
            out[part + "_hz"] = round(cue, 2)
        return out

    def test(self, day=None, lures=6, items=None):
        """Pattern-completion test of stored messages vs lures, plasticity frozen."""
        net, p = self.net, self.net.plast
        was = p.frozen if p is not None else None
        if p is not None:
            p.frozen = True
        items = [m for m in (items if items is not None else self.registry) if len(m["words"]) >= 2]
        res = []
        for m in items:
            res.append({"text": m["text"], **self._probe(m["words"])})
        lure_res = []
        for i in range(lures):
            n_w = max(2, int(np.median([len(m["words"]) for m in items])) if items else 6)
            ws = [f"lure{day or ''}x{i}w{j}" for j in range(n_w)]
            lure_res.append(self._probe(ws))
        if p is not None:
            p.frozen = was
        lc = np.array([r["hc"] for r in lure_res]) if lure_res else np.zeros(1)
        lx = np.array([r["ctx"] for r in lure_res]) if lure_res else np.zeros(1)
        thr_hc = float(lc.mean() + 3 * lc.std() + 1e-3)
        thr_ctx = float(lx.mean() + 3 * lx.std() + 1e-3)
        scores, recalled = [], []
        for r in res:
            s = {"text": r["text"], "hc": round(r["hc"], 4), "ctx": round(r["ctx"], 4),
                 "hc_hz": r.get("hc_hz"), "ctx_hz": r.get("ctx_hz"),
                 "hc_recalled": bool(r["hc"] > thr_hc), "ctx_recalled": bool(r["ctx"] > thr_ctx)}
            scores.append(s)
            if s["hc_recalled"] or s["ctx_recalled"]:
                recalled.append(r["text"])
        return {"kind": "memory_test", "day": day, "cues": [" ".join(r["cue"]) for r in res],
                "recalled": recalled, "scores": scores,
                "control_scores": [{"hc": round(r["hc"], 4), "ctx": round(r["ctx"], 4)} for r in lure_res],
                "thresholds": {"hc": round(thr_hc, 4), "ctx": round(thr_ctx, 4)}, "n_stored": len(self.registry)}

    # --- REM replay -------------------------------------------------------------------------------------------
    def replay_once(self, rng=None, burst_ms=100, replay_ms=300):
        """Spontaneous hippocampal reactivation picks a memory; its pattern is reinstated with CONS on."""
        if not self.registry:
            return None
        net, p = self.net, self.net.plast
        rng = rng or np.random.default_rng()
        snap = net.snapshot()
        net.set_region_drive("hc_state", self.hc_drive * 1.5)
        net.run(burst_ms)
        net.set_region_drive("hc_state", None)
        r = net.rates_since(snap)
        act = np.array([float(r[torch.as_tensor(m["index"], device=net.device)].mean()) for m in self.registry])
        z = (act - act.max()) / max(1e-6, act.std() + 1.0)
        prob = np.exp(3 * z)
        prob /= prob.sum()
        m = self.registry[int(rng.choice(len(self.registry), p=prob))]
        base = self._rest(200)
        r0 = net.rates_since(base)
        snap = self._present(self.pattern(m["words"]), replay_ms, self.amp * self.replay_amp)[1]
        if p is not None:
            p.hebbian(net.rates_since(snap) - r0, "cons", replay_ms / 1000.0, theta=self.cons_theta)
        return {"text": m["text"], "hc_activation": round(float(act.max()), 2)}

    # --- persistence (stored with the learned weights) ------------------------------------------------------
    def to_meta(self):
        return {"memories": self.registry}

    def from_meta(self, meta):
        self.registry = list(meta.get("memories", []))


def sleep_block(net, mem, minutes, cycles=2, rem_frac=0.4, replay_every_s=3.0, rng=None, on_tick=None):
    """A compressed night: NREM (global ~0.8 Hz up/down drive, recorded drive damped) then REM (noisier, replay).

    Stage parameters follow sleep.py qualitatively (NREM: slow and synchronous, low input gain; REM: noisy,
    hippocampal replay); a real night's cycles are compressed into `minutes` of simulated time.
    Returns the list of replays.
    """
    rng = rng or np.random.default_rng(0)
    replays = []
    total_ms = int(minutes * 60_000)
    cyc_ms = total_ms // max(1, cycles)
    base_gain, base_noise = net.baseline_gain, net.noise_gain
    chunk = 50
    for k in range(cycles):
        nrem_ms = int(cyc_ms * (1 - rem_frac))
        net.baseline_gain = base_gain * 0.3
        for t in range(0, nrem_ms, chunk):
            net.mu_offset = -1.0 + 2.5 * np.sin(2 * np.pi * 0.8 * (net.t * net.cfg.dt / 1000.0))
            net._dirty = True
            net.run(chunk)
            if on_tick:
                on_tick("NREM")
        net.mu_offset = 0.0
        net._dirty = True
        net.baseline_gain, net.noise_gain = base_gain * 0.7, base_noise * 1.2
        t_rem, next_replay = 0, rng.exponential(replay_every_s * 1000)
        while t_rem < cyc_ms - nrem_ms:
            if t_rem >= next_replay and mem.registry:
                r = mem.replay_once(rng)
                if r:
                    replays.append(r)
                t_rem += 100 + 200 + 300
                next_replay = t_rem + rng.exponential(replay_every_s * 1000)
            else:
                net.run(chunk)
                t_rem += chunk
            if on_tick:
                on_tick("REM")
        net.baseline_gain, net.noise_gain = base_gain, base_noise
    return replays
