"""Neurogenesis: the day spiking network grows a few thousand neurons each waking day (numpy only, no torch).

The owner wants the brain cultivated, not fixed: it starts at its base size (SUB01_SPIKING_LIVE_NEURONS) and gains
SUB01_GROW_PER_DAY neurons (5,000) once a day, at his confirmed wake-up (the server sends {"type": "grow"} to the
day network when the sleep engine says AWAKE; never while he sleeps), up to SUB01_NEURONS_MAX (1,000,000): memory and
cost never jump without the owner's decision. More neurons never mean understanding or consciousness: it stays a
simulated network, only bigger. Wording for the page: "neurons: 505,000 (+5,000 today)".

Where the new neurons go. The daily step is split among the 214 regions in proportion to the connectome's regional
volumes (the same largest-remainder allocation as the base layout, wiring.allocate with minimum 0), so the atlas
proportions are kept; 80 % of a region's new neurons are excitatory. They are appended after the existing neurons
(wiring.Layout.grow_layout): the base layout, its synapses, memory.py's word hashing and the learned-weight files
are untouched, so what was learned survives a growth step.

Innate synapses (`innate_synapses`). A new neuron gets the base network's fixed in-degree from the statistics of its
own region: k_e_local excitatory and k_i_local inhibitory sources uniform in its region (base and grown neurons
alike, no autapses), k_long excitatory sources from other regions drawn with probability proportional to the
streamline count into its region (the connectome), with the fibre-length delays, and the hippocampal collaterals
where the region has them, i.e. exactly wiring.synapse_lists' rules for one more neuron. New neurons start with no
outgoing synapses: like adult-born neurons they listen first, and gain outputs as later blocks draw them as sources
(a region's neuron is drawn by every neuron born after it) and through the activity rule below. Keeping every in-degree
at the base budget keeps the inhibition-dominated regime, so the rates stay in range at any size (checked in tests).
The innate wiring is deterministic from (config seed, block index, the ledger of per-region additions), so the
state file stores the ledger, not the synapses.

Activity-dependent rule (`Growth.activity`, applied every ACT_EVERY_MS = 2,000 ms of simulated time, over the
spike counts of that window):
  - active = neurons whose rate in the window was >= ACT_HZ (15 Hz; the background is ~5 Hz, so a Poisson neuron
    crosses it by chance with p ~ 1e-7 in a 2 s window: in practice cue-driven and strongly driven neurons);
  - formation: up to FORM_PER_RUN (200) new synapses between co-active neurons, presynaptic excitatory, drawn with
    weight YOUNG_BIAS (4) for grown neurons (young neurons are the more plastic ones), initial weight FORM_W
    (0.25 mV = j_e / 2), delay as the wiring rule (1-2 ms in the region, fibre length / 6 m/s across);
    a pair that already has a formed synapse is reinforced by FORM_W instead of duplicated;
  - reinforcement: every formed synapse whose pre and post are both active gains REINF_W (0.1 mV), up to W_MAX
    (1.0 mV = 2 j_e);
  - decay and pruning: formed weights decay with TAU_DECAY_S (3,600 s of simulated time); a formed synapse is pruned
    when weak (w < W_MIN = 0.05 mV: never reinforced for ~1.6 simulated hours) or unused (its presynaptic neuron
    silent for PRUNE_SILENT_S = 600 s);
  - budget: a neuron receives at most EXTRA_BUDGET (10) formed synapses on top of its innate in-degree (the base
    budget of ~100, ~300 in the hippocampus); when full, the weakest formed synapse onto it is replaced. So the total
    synapse count per neuron stays within budget + 10 % whatever happens, and formed synapses number <= 10 n.
  The innate synapses are never pruned (they are the regenerable fixed in-degree); only formed ones are stored.

State: <data>/spiking/growth.npz (atomic write): version, the base config hash and size, the ledger (blocks x regions
int32, with each block's Tokyo day), the formed synapses (src/dst int32, w float16, delay uint8) and a small JSON
meta (last growth day, today's addition, refusals, history). On load, a file for another base network, an unknown
version or an unreadable file falls back to the base network and is kept aside, logged once.

Cost guard (`fit_reason`): before a step, the network's own memory (RSS, scaled by the new size, with 30 % for the
rebuild) must fit the room left under the container's memory limit (cgroup v2 / v1, else MemAvailable) at MEM_FRAC
(75 %), and a decision at the new size (settle + race, learner and twin, from the measured ms of wall per simulated
ms) must stay under TIME_FRAC (80 %) of the parent's deadline (SUB01_SPIKING_LIVE_TIMEOUT_S). A refusal is logged
once a day with its reason and shown in the status. `gpu_fit_reason` is the same guard for the GPU pod types from the
measured 1M-neuron numbers (docs/spiking/live.md: 5.7 GB, 1.24x real time on an A4000): the GPU network itself is
fixed at 1M = the default cap today (its learned weights are tied to its size); the function is ready for when it grows.
"""
import json
import math
import os
import time
from pathlib import Path

import numpy as np

from .wiring import allocate

VERSION = 1
GROW_PER_DAY = int(os.environ.get("SUB01_GROW_PER_DAY") or 5000)       # neurons a waking day (0: no growth)
NEURONS_MAX = int(os.environ.get("SUB01_NEURONS_MAX") or 1_000_000)     # the cap: never past it without the owner
# --- the activity rule --------------------------------------------------------------------------------------------
ACT_EVERY_MS = 2000                 # simulated ms between two applications
ACT_HZ = 15.0                       # a neuron is "active" in a window at or above this rate
FORM_PER_RUN = 200                  # at most this many synapses formed per application
FORM_W = 0.25                       # mV, a formed synapse's initial weight (j_e / 2)
REINF_W = 0.1                       # mV per co-active window
W_MAX = 1.0                         # mV, bound of a formed weight (2 j_e)
W_MIN = 0.05                        # mV, below this a formed synapse is pruned (weak)
TAU_DECAY_S = 3600.0                # simulated seconds, decay of formed weights
PRUNE_SILENT_S = 600.0              # a formed synapse whose source was silent this long is pruned (unused)
EXTRA_BUDGET = 10                   # formed synapses a neuron may receive on top of its innate in-degree
YOUNG_BIAS = 4.0                    # grown neurons are drawn this many times more often as pre and post
# --- the cost guard ------------------------------------------------------------------------------------------------
MEM_FRAC = 0.75                     # of the container's memory limit the network may fill
GROW_MEM_MARGIN = 1.3               # rebuild temporaries (sorting the new CSR, copying the state)
TIME_FRAC = 0.8                     # of the parent's decision deadline a projected decision may take
GPU_BYTES_PER_NEURON = 5.7e9 / 1e6  # measured: 1M neurons, 101M synapses, 5.7 GB (docs/spiking/live.md)
GPU_MEM_GB = {"NVIDIA RTX A4000": 16, "NVIDIA RTX A4500": 20, "NVIDIA RTX A5000": 24, "NVIDIA RTX 4000 Ada Generation": 20,
              "NVIDIA A40": 48, "NVIDIA GeForce RTX 4090": 24, "NVIDIA L40": 48, "NVIDIA L4": 24}
GPU_REALTIME_X_1M = {"NVIDIA RTX A4000": 1.24, "NVIDIA RTX A4500": 1.3, "NVIDIA RTX A5000": 1.45,       # free-running
                     "NVIDIA RTX 4000 Ada Generation": 1.35, "NVIDIA A40": 1.52, "NVIDIA GeForce RTX 4090": 1.5,
                     "NVIDIA L40": 1.5, "NVIDIA L4": 0.04}
HISTORY_KEEP = 60


# --- the daily step ----------------------------------------------------------------------------------------------
def split_by_region(amount, reg, hc_scale=1.0):
    """`amount` new neurons per region, proportional to the regions' volumes (the base layout's rule, minimum 0)."""
    if amount <= 0:
        return np.zeros(reg.n, dtype=np.int64)
    vol = reg.volumes.copy()
    vol[reg.groups["memory"]] *= hc_scale
    return allocate(int(amount), vol, 0)


def innate_synapses(net, blk, seed):
    """The fixed in-degree of one grown block's neurons from their regions' statistics (module doc), as numpy arrays
    (src, dst, w, delay) sorted by src. Sources are drawn among all neurons of the source region, base and grown."""
    c, reg, R = net.cfg, net.reg, net.reg.n
    rng = np.random.default_rng(c.seed + 7_000_003 + 1009 * int(seed))
    delay_long = np.maximum(1, np.round(reg.lengths / c.velocity_mm_ms / c.dt)).astype(np.int64)
    P = reg.W / reg.W.sum(0, keepdims=True)
    cdf = np.cumsum(P, axis=0)
    d0, d1 = c.delay_local
    n_e, n_i = net.region_n_exc(), net.region_size() - net.region_n_exc()
    E = [net.region_neurons(r, exc_only=True) for r in range(R)]
    I = []
    for r in range(R):                                                     # each population is E first, then I
        ids = net.region_neurons(r)
        I.append(ids[~net.is_exc_np[ids]])
    e_off = np.concatenate([[0], np.cumsum(n_e)[:-1]])
    allE = np.concatenate(E)
    src_l, dst_l, w_l, d_l = [], [], [], []
    i32 = lambda a: np.asarray(a, dtype=np.int32).ravel()
    u8 = lambda a: np.asarray(a, dtype=np.uint8).ravel()

    def local(targets, pool, k, tgt_pos):
        """k uniform sources from `pool` for each target; a self-draw moves to the next neuron of the pool."""
        idx = rng.integers(0, len(pool), size=(len(targets), k))
        if tgt_pos is not None:
            hit = idx == tgt_pos[:, None]
            idx[hit] = (idx[hit] + 1) % len(pool)
        return pool[idx]

    for r in np.flatnonzero(blk["size"]):
        sz, ne = int(blk["size"][r]), int(blk["n_exc"][r])
        tgt = np.arange(blk["off"][r], blk["off"][r] + sz, dtype=np.int64)
        te, ti = tgt[:ne], tgt[ne:]
        pos_e = np.arange(n_e[r] - ne, n_e[r])                        # the block's E are the last of the region's E list
        pos_i = np.arange(n_i[r] - (sz - ne), n_i[r])
        # local excitatory (no autapses)
        s = np.concatenate([local(te, E[r], c.k_e_local, pos_e), local(ti, E[r], c.k_e_local, None)]) if ne else \
            local(ti, E[r], c.k_e_local, None)
        src_l.append(i32(s)); dst_l.append(i32(np.repeat(tgt, c.k_e_local)))
        w_l.append(np.full(s.size, c.j_e, np.float32)); d_l.append(u8(rng.integers(d0, d1 + 1, size=s.size)))
        # local inhibitory
        if n_i[r]:
            s = np.concatenate([local(te, I[r], c.k_i_local, None), local(ti, I[r], c.k_i_local, pos_i)]) if sz > ne else \
                local(te, I[r], c.k_i_local, None)
            src_l.append(i32(s)); dst_l.append(i32(np.repeat(tgt, c.k_i_local)))
            w_l.append(np.full(s.size, -c.g_i * c.j_e, np.float32)); d_l.append(u8(rng.integers(d0, d1 + 1, size=s.size)))
        # long-range excitatory: source region ~ streamline counts into r, source neuron uniform among its E
        m = sz * c.k_long
        sr = np.minimum(np.searchsorted(cdf[:, r], rng.random(m) * cdf[-1, r], side="right"), R - 1)
        s = allE[e_off[sr] + np.floor(rng.random(m) * n_e[sr]).astype(np.int64)]
        src_l.append(i32(s)); dst_l.append(i32(np.repeat(tgt, c.k_long)))
        w_l.append(np.full(m, c.j_e, np.float32)); d_l.append(u8(delay_long[sr, r]))
        # hippocampal recurrent collaterals
        if r in net.hc_regions and c.k_hc_rec > 0 and ne:
            s = local(te, E[r], c.k_hc_rec, pos_e)
            src_l.append(i32(s)); dst_l.append(i32(np.repeat(te, c.k_hc_rec)))
            w_l.append(np.full(s.size, c.j_hc_rec, np.float32)); d_l.append(u8(rng.integers(d0, d1 + 1, size=s.size)))
        if r in net.hc_regions and c.k_hc_rec_i > 0 and sz > ne:
            s = local(ti, E[r], c.k_hc_rec_i, None)
            src_l.append(i32(s)); dst_l.append(i32(np.repeat(ti, c.k_hc_rec_i)))
            w_l.append(np.full(s.size, c.j_hc_ei, np.float32)); d_l.append(u8(rng.integers(d0, d1 + 1, size=s.size)))
    if not src_l:
        return (np.zeros(0, np.int32), np.zeros(0, np.int32), np.zeros(0, np.float32), np.zeros(0, np.uint8))
    src = np.concatenate(src_l)
    order = np.argsort(src, kind="stable")
    return src[order], np.concatenate(dst_l)[order], np.concatenate(w_l)[order], np.concatenate(d_l)[order]


# --- the cost guard ------------------------------------------------------------------------------------------------
def _read_int(path):
    try:
        s = Path(path).read_text().strip()
        return None if s in ("max", "") else int(s)
    except (OSError, ValueError):
        return None


def mem_room_bytes():
    """Bytes this process may still take: MEM_FRAC of the container's limit minus what the container uses (cgroup v2,
    then v1), else MEM_FRAC of the host's MemAvailable. None when nothing can be read."""
    lim, used = _read_int("/sys/fs/cgroup/memory.max"), _read_int("/sys/fs/cgroup/memory.current")
    if lim is None:
        lim, used = _read_int("/sys/fs/cgroup/memory/memory.limit_in_bytes"), _read_int("/sys/fs/cgroup/memory/memory.usage_in_bytes")
        if lim is not None and lim > 1 << 60:                 # v1's "unlimited" is a huge number
            lim = None
    if lim is not None and used is not None:
        return MEM_FRAC * lim - used
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemAvailable:"):
                return MEM_FRAC * int(line.split()[1]) * 1024
    except (OSError, ValueError, IndexError):
        pass
    return None


def own_rss_bytes():
    try:
        return int(Path("/proc/self/statm").read_text().split()[1]) * os.sysconf("SC_PAGE_SIZE")
    except (OSError, ValueError, IndexError):
        return None


def fit_reason(n_now, n_new, rss=None, room=None, ms_per_ms=None, deadline_s=None, twin=True, decision_ms=350):
    """None when a network of n_new neurons fits (memory and decision time), else the reason (one line).
    rss: the network process's resident bytes now; room: bytes it may still take (mem_room_bytes); ms_per_ms: wall ms
    per simulated ms measured now; deadline_s: the parent's decision deadline; decision_ms: simulated ms a decision
    takes (settle + race). Unknown measurements are not held against the step."""
    if n_new <= n_now:
        return None
    scale = n_new / max(1, n_now)
    if rss is not None and room is not None:
        need = rss * (scale - 1.0) * GROW_MEM_MARGIN
        if need > room:
            return (f"memory: {n_new:,} neurons need ~{need / 1e6:.0f} MB more, {max(0.0, room) / 1e6:.0f} MB left under "
                    f"{int(MEM_FRAC * 100)} % of the limit")
    if ms_per_ms is not None and deadline_s:
        proj = decision_ms * ms_per_ms * scale * (2 if twin else 1) / 1000.0
        if proj > TIME_FRAC * float(deadline_s):
            return (f"time: a decision at {n_new:,} neurons would take ~{proj:.2f} s (learner + twin), over "
                    f"{int(TIME_FRAC * 100)} % of the {float(deadline_s):g} s deadline")
    return None


def gpu_fit_reason(n_new, gpu, mem_frac=0.8, min_realtime_x=0.5):
    """The guard for a GPU pod type (docs/spiking/live.md measurements at 1M): None when n_new neurons fit its memory
    at `mem_frac` and still run at >= min_realtime_x real time, else the reason. Unknown type: memory check only."""
    mem = GPU_MEM_GB.get(gpu)
    if mem is not None and n_new * GPU_BYTES_PER_NEURON > mem_frac * mem * 1e9:
        return f"memory: {n_new:,} neurons need ~{n_new * GPU_BYTES_PER_NEURON / 1e9:.1f} GB, {gpu} has {mem} GB"
    x = GPU_REALTIME_X_1M.get(gpu)
    if x is not None and x * 1e6 / n_new < min_realtime_x:
        return f"time: {gpu} would run {n_new:,} neurons at ~{x * 1e6 / n_new:.2f}x real time (minimum {min_realtime_x})"
    return None


# --- the state ------------------------------------------------------------------------------------------------------
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


class Growth:
    """The ledger of grown neurons and the formed synapses of one network (module doc). Torch-free; the network
    (spiking/live.py's LiveNet, or any wiring.Layout) applies the blocks with grow_layout + innate_synapses."""

    def __init__(self, cfg, reg, n_base, per_day=None, cap=None, log=print):
        self.cfg, self.reg, self.n_base = cfg, reg, int(n_base)
        self.per_day = GROW_PER_DAY if per_day is None else int(per_day)
        self.cap = NEURONS_MAX if cap is None else int(cap)
        self.log = log
        self.blocks = np.zeros((0, reg.n), dtype=np.int64)              # neurons added per block and region
        self.days = []                                                  # the Tokyo day of each block
        self.formed = self._empty()
        self.meta = {"last_day": None, "grow_today": 0, "refused": None, "refused_day": None, "formed_total": 0,
                     "pruned_total": 0, "history": []}
        self.silent_ms = None                                           # per neuron: simulated ms without a spike
        self.delay_long = np.maximum(1, np.round(reg.lengths / cfg.velocity_mm_ms / cfg.dt)).astype(np.int64)
        self.dirty = False
        self._warned = False

    @staticmethod
    def _empty():
        return {"src": np.zeros(0, np.int32), "dst": np.zeros(0, np.int32), "w": np.zeros(0, np.float32),
                "delay": np.zeros(0, np.uint8)}

    @property
    def grown(self):
        return int(self.blocks.sum())

    @property
    def n(self):
        return self.n_base + self.grown

    def identity(self):
        return f"{self.cfg.config_hash()}:{self.n_base}:v{VERSION}"

    # --- the daily step ---------------------------------------------------------------------------------------------
    def plan(self, day, fits=None):
        """(add per region, None) for today's step, or (None, why) when nothing grows: already grown today, growth
        off, at the cap, or the cost guard's reason (`fits(n_new) -> reason | None`). Refusals are logged once a day."""
        if self.per_day <= 0:
            return None, "growth off (SUB01_GROW_PER_DAY=0)"
        if self.meta.get("last_day") == day:
            return None, "already grown today"
        amount = min(self.per_day, self.cap - self.n)
        if amount <= 0:
            why = f"at the cap ({self.n:,} of SUB01_NEURONS_MAX={self.cap:,})"
        else:
            why = fits(self.n + amount) if fits is not None else None
        if why:
            if self.meta.get("refused_day") != day or self.meta.get("refused") != why:
                self.log(f"spiking growth: no growth today: {why}")
            self.meta.update(refused=why, refused_day=day, grow_today=0)
            self.dirty = True
            return None, why
        return split_by_region(amount, self.reg, self.cfg.hc_scale), None

    def record(self, day, add):
        """Book a block that the network applied (the ledger's row; the next block index is len(self.days))."""
        add = np.asarray(add, dtype=np.int64)
        self.blocks = np.vstack([self.blocks, add[None, :]])
        self.days.append(str(day))
        self.meta.update(last_day=str(day), grow_today=int(add.sum()), refused=None, refused_day=None)
        self.meta["history"] = (self.meta.get("history") or [])[-(HISTORY_KEEP - 1):] + \
            [{"day": str(day), "added": int(add.sum()), "n": self.n}]
        self.dirty = True
        return len(self.days) - 1

    def grow_today(self, net, day, fits=None):
        """Apply today's step to `net` (a LiveNet-like with grow(add, seed) -> n_syn added). -> what happened."""
        add, why = self.plan(day, fits)
        if add is None:
            return {"added": 0, "why": why, "n": net.n}
        b = len(self.days)
        n_syn = net.grow(add, b)
        self.record(day, add)
        self.log(f"spiking growth: +{int(add.sum()):,} neurons ({n_syn:,} innate synapses) on {day}: "
                 f"{net.n:,} neurons, {self.grown:,} grown since {self.days[0]}")
        return {"added": int(add.sum()), "why": None, "n": net.n, "synapses_added": int(n_syn)}

    def replay(self, net):
        """Rebuild the grown layout on a freshly built base network (at start): every block, in order."""
        for b, add in enumerate(self.blocks):
            net.grow(add, b)
        self.silent_ms = None

    def status(self, day=None):
        m = self.meta
        return {"grown": self.grown, "grow_today": int(m.get("grow_today") or 0) if (day is None or m.get("last_day") == day) else 0,
                "cap": self.cap, "grow_per_day": self.per_day, "n_base": self.n_base,
                "growth": {"last_day": m.get("last_day"), "blocks": len(self.days), "formed": int(len(self.formed["src"])),
                           "formed_total": int(m.get("formed_total") or 0), "pruned_total": int(m.get("pruned_total") or 0),
                           "refused": m.get("refused") if m.get("refused_day") in (None, day) else None,
                           "history": list(m.get("history") or [])[-7:]}}

    # --- the activity rule -----------------------------------------------------------------------------------------
    def activity(self, net, counts, window_ms, rng):
        """Formation, reinforcement, decay and pruning of formed synapses from the spike counts of a window (module
        doc). Returns the stats and sets self.formed; the caller gives the arrays to the network (LiveNet.set_formed)."""
        n = net.n
        counts = np.asarray(counts)
        if self.silent_ms is None or len(self.silent_ms) != n:
            self.silent_ms = np.zeros(n, dtype=np.int64)
        self.silent_ms[counts > 0] = 0
        self.silent_ms[counts == 0] += int(window_ms)
        f = self.formed
        if len(f["src"]) and (f["dst"] >= n).any():                        # never: the blocks are replayed before
            f = self.formed = self._empty()
        win_s = window_ms / 1000.0
        act = np.flatnonzero(counts >= ACT_HZ * win_s)
        is_act = np.zeros(n, dtype=bool)
        is_act[act] = True
        stats = {"active": int(len(act)), "formed": 0, "reinforced": 0, "pruned": 0}
        src, dst, w, delay = f["src"].astype(np.int64), f["dst"].astype(np.int64), f["w"].astype(np.float32), f["delay"]
        # reinforcement of co-active formed synapses, then decay
        if len(src):
            co = is_act[src] & is_act[dst]
            w[co] += REINF_W
            stats["reinforced"] = int(co.sum())
            w *= np.float32(math.exp(-win_s / TAU_DECAY_S))
        # formation between co-active neurons (pre excitatory), young neurons favoured
        pre_c = act[net.is_exc_np[act]]
        if len(pre_c) and len(act) >= 2:
            pw = np.where(pre_c >= net.n_base, YOUNG_BIAS, 1.0)
            qw = np.where(act >= net.n_base, YOUNG_BIAS, 1.0)
            i = rng.choice(pre_c, size=FORM_PER_RUN, p=pw / pw.sum())
            j = rng.choice(act, size=FORM_PER_RUN, p=qw / qw.sum())
            keep = i != j
            i, j = i[keep], j[keep]
            key = np.unique(i * n + j)                                   # one per pair per window
            i, j = key // n, key % n
            if len(src):
                have = np.isin(i * n + j, src * n + dst)
                if have.any():                                           # already formed: reinforce instead
                    hk = np.isin(src * n + dst, (i * n + j)[have])
                    w[hk] += FORM_W
                i, j = i[~have], j[~have]
            if len(i):
                ri, rj = net.region_of_np[i], net.region_of_np[j]
                d = np.where(ri == rj, rng.integers(self.cfg.delay_local[0], self.cfg.delay_local[1] + 1, size=len(i)),
                             self.delay_long[ri, rj])
                src, dst = np.concatenate([src, i]), np.concatenate([dst, j])
                w = np.concatenate([w, np.full(len(i), FORM_W, np.float32)])
                delay = np.concatenate([delay, d.astype(np.uint8)])
                stats["formed"] = int(len(i))
                self.meta["formed_total"] = int(self.meta.get("formed_total") or 0) + int(len(i))
        if len(src):
            np.minimum(w, W_MAX, out=w)
            # pruning: weak, or the source silent for PRUNE_SILENT_S
            keep = (w >= W_MIN) & (self.silent_ms[src] < PRUNE_SILENT_S * 1000)
            # the budget: at most EXTRA_BUDGET formed synapses onto one neuron (the strongest stay)
            order = np.lexsort((-w, dst))                                # by post, strongest first
            rank = np.arange(len(order)) - np.searchsorted(dst[order], dst[order], side="left")
            over = np.zeros(len(order), dtype=bool)
            over[order] = rank >= EXTRA_BUDGET
            keep &= ~over
            stats["pruned"] = int((~keep).sum())
            self.meta["pruned_total"] = int(self.meta.get("pruned_total") or 0) + stats["pruned"]
            src, dst, w, delay = src[keep], dst[keep], w[keep], delay[keep]
            order = np.argsort(src, kind="stable")
            src, dst, w, delay = src[order], dst[order], w[order], delay[order]
        self.formed = {"src": src.astype(np.int32), "dst": dst.astype(np.int32), "w": w.astype(np.float32),
                       "delay": np.asarray(delay, dtype=np.uint8)}
        self.dirty = self.dirty or bool(stats["formed"] or stats["reinforced"] or stats["pruned"])
        return stats

    # --- the file --------------------------------------------------------------------------------------------------
    def save(self, path):
        f = self.formed
        _save_npz_atomic(path, version=VERSION, identity=self.identity(), blocks=self.blocks.astype(np.int32),
                         days=np.array(self.days, dtype="U10"), f_src=f["src"], f_dst=f["dst"],
                         f_w=f["w"].astype(np.float16), f_delay=f["delay"], meta=json.dumps(self.meta))
        self.dirty = False

    def load(self, path):
        """Load the ledger and the formed synapses. False (and the base network stays) when there is no file, the
        file is for another base network or version (kept aside as .other-*), or it is unreadable (.corrupt-*)."""
        path = Path(path)
        if not path.exists():
            return False
        try:
            with np.load(path, allow_pickle=False) as z:
                if int(z["version"]) != VERSION or str(z["identity"]) != self.identity():
                    aside = path.with_name(f"{path.name}.other-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}")
                    os.replace(path, aside)
                    self._say(f"spiking growth: {path.name} is for another base network ({str(z['identity'])[:40]}), "
                              f"kept as {aside.name}; starting from the base network")
                    return False
                blocks = z["blocks"].astype(np.int64).reshape(-1, self.reg.n)
                days = [str(d) for d in z["days"]]
                formed = {"src": z["f_src"].astype(np.int32), "dst": z["f_dst"].astype(np.int32),
                          "w": z["f_w"].astype(np.float32), "delay": z["f_delay"].astype(np.uint8)}
                meta = json.loads(str(z["meta"]))
                if len(days) != len(blocks) or (blocks < 0).any() or not isinstance(meta, dict) \
                        or len({len(v) for v in formed.values()}) != 1 or (formed["dst"] >= self.n_base + blocks.sum()).any():
                    raise ValueError("inconsistent growth file")        # (a cap lowered under the size only stops growth)
        except Exception as e:                                           # torn or corrupt: keep it aside, start from base
            aside = path.with_name(f"{path.name}.corrupt-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}")
            try:
                os.replace(path, aside)
            except OSError:
                pass
            self._say(f"spiking growth: {path.name} unreadable ({type(e).__name__}), kept as {aside.name}; "
                      "starting from the base network")
            return False
        self.blocks, self.days, self.formed, self.meta = blocks, days, formed, {**self.meta, **meta}
        self.dirty = False
        return True

    def _say(self, msg):
        if not self._warned:
            self._warned = True
            self.log(msg)
