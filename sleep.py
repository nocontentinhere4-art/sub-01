"""Sleep/wake engine for SUB-01: circadian clock, NREM/REM cycles, arousal, sleep debt, memory replay.

Pure bookkeeping on a (possibly accelerated) Europe/Rome clock; live_server.py feeds it
stimuli and applies `engine.params` to the Stuart-Landau model every tick. No language
model and no generated text: replay re-applies stored stimulus patterns, nothing more.

Rules (all times Rome local, sim clock):
- awake ~08:00-00:00, asleep 00:00-08:00; falls asleep early (after 20:00) if sleep pressure >= 1
- asleep: ~90 min NREM -> REM cycles; early cycles deeper NREM, later cycles longer REM
- stimuli add to an arousal accumulator (decays over minutes); crossing WAKE_THRESHOLD wakes it,
  it falls asleep again after QUIET_S without stimuli
- sleep debt (hours): +1 per hour awake during the night, +0.25 per wake-up; repaid slowly by
  sleep and faster by going to bed early. Debt makes the waking brain less reactive and noisier.
"""
import json
import math
import random
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROME = ZoneInfo("Europe/Rome")

# Stuart-Landau parameters per stage: f_hz, coupling (x baseline g), noise, a (bifurcation), stimulus gain
AWAKE = dict(f_hz=10.0, coupling=1.0, noise=0.5, a=-5.0, gain=1.0)
NREM_LIGHT = dict(f_hz=3.0, coupling=2.0, noise=0.3, a=-2.0, gain=0.25)
NREM_DEEP = dict(f_hz=1.0, coupling=3.0, noise=0.25, a=0.0, gain=0.08)     # slow, synchronous
REM = dict(f_hz=6.0, coupling=0.6, noise=0.9, a=-5.0, gain=0.4)             # theta-like, noisy
KEYS = tuple(AWAKE)

CYCLE_S = 90 * 60
WAKE_HOUR, BED_HOUR, EARLY_BED_HOUR = 8, 0, 20
TRANSITION_S = 30.0          # exponential glide time constant (sim s): ~95 % after 90 s
TRANSITION_REAL_S = 1.0      # ...but never faster than this in real seconds (high --time-scale)
AROUSAL_TAU_S = 5 * 60
WAKE_THRESHOLD = 3.0
SLEEP_OK = 1.0               # arousal must be below this to fall asleep
QUIET_S = 10 * 60            # no stimuli for this long before falling (back) asleep
DEBT_PER_WAKEUP = 0.25
DEBT_REPAY_PER_H = 0.05      # while asleep
REPLAY_MEAN_S = 4 * 60       # mean interval between REM replays
BIG_TRADE_USD = 5000


def local(t):
    return datetime.fromtimestamp(t, ROME)


def hhmm(t):
    return local(t).strftime("%H:%M")


def stamp(t):
    return local(t).strftime("%Y-%m-%dT%H:%M")


def night_date(t):
    """A night is named after the evening it starts on (00:00-08:00 belongs to the day before)."""
    return (local(t) - timedelta(hours=12)).date().isoformat()


def lerp(p, q, x):
    return {k: p[k] + (q[k] - p[k]) * x for k in KEYS}


class Clock:
    """Rome sim clock. scale=60 -> one sim hour per real minute. `start` = sim epoch to start at."""

    def __init__(self, scale=1.0, start=None):
        self.scale = scale
        self.real0 = time.time()
        self.sim0 = self.real0 if start is None or scale == 1 else start

    def now(self):
        return self.sim0 + (time.time() - self.real0) * self.scale


class Memory:
    """Accepted chat messages: time, stage when received, stimulus pattern and emotional tag."""

    EMO_WEIGHT = {"threat": 3.0, "positive": 2.5, "neutral": 1.0}

    def __init__(self, items=None, cap=2000):
        self.items = list(items or [])
        self.cap = cap

    def add(self, t, text, stage, stimulus, emotion, networks):
        m = {"t": t, "text": text, "stage": stage, "stimulus": stimulus, "emotion": emotion,
             "networks": networks, "asleep": stage != "AWAKE"}
        self.items.append(m)
        del self.items[:-self.cap]
        return m

    def weight(self, m, t, night_start, replayed=0):
        recency = math.exp(-max(0.0, t - m["t"]) / (24 * 3600))
        tonight = 4.0 if night_start is not None and m["t"] >= night_start else 1.0
        return recency * self.EMO_WEIGHT.get(m["emotion"], 1.0) * tonight / (1 + replayed)   # habituation

    def pick(self, t, night_start, rng=random, replayed=None):
        """Weighted by recency, emotion and 'arrived tonight'; `replayed` = {received stamp: count} tonight."""
        cand = [m for m in self.items if m["t"] <= t]
        if not cand:
            return None
        replayed = replayed or {}
        w = [self.weight(m, t, night_start, replayed.get(stamp(m["t"]), 0)) for m in cand]
        return rng.choices(cand, weights=w)[0]


class SleepEngine:
    def __init__(self, now, rng=None):
        self.rng = rng or random.Random()
        self.t = now
        self.asleep = False
        self.stage = "AWAKE"
        self.depth = 0.0                   # NREM depth 0..1
        self.onset = None                  # current sleep onset
        self.k_base = 0                    # cycles already slept tonight before this onset
        self.awake_since = now             # last morning wake-up (drives sleep pressure)
        self.arousal = 0.0
        self.arousal_log = []              # recent [t, amount, kind, usd]
        self.last_stim = -1e18
        self.debt = 0.0
        self.night = None                  # current night record (see open_night)
        self.last_night = None             # summary of the previous closed night
        self.next_replay = None
        self.params = self.stage_params()

    # --- derived quantities ------------------------------------------------------
    @property
    def tired(self):
        return min(1.0, self.debt / 4.0)

    @property
    def gain(self):
        return self.params["gain"]

    def pressure(self, t=None):
        t = self.t if t is None else t
        return (t - self.awake_since) / 3600 / 16 + 0.08 * self.debt

    def in_night(self, t):
        return BED_HOUR <= local(t).hour < WAKE_HOUR

    def cycle_stage(self, t):
        """(stage, depth, cycle index) for time t while asleep."""
        s = max(0.0, t - self.onset)
        k = self.k_base + int(s // CYCLE_S)
        pos = s % CYCLE_S
        rem_frac = min(0.45, 0.12 + 0.08 * k)
        nrem_len = CYCLE_S * (1 - rem_frac)
        if pos >= nrem_len:
            return "REM", 0.0, k
        peak = max(0.1, 1.0 - 0.25 * k)                       # early cycles reach deeper NREM
        return "NREM", peak * math.sin(math.pi * pos / nrem_len) ** 0.5, k

    def stage_params(self):
        if self.stage == "REM":
            return dict(REM)
        if self.stage == "NREM":
            return lerp(NREM_LIGHT, NREM_DEEP, self.depth)
        p = dict(AWAKE)                                       # tired: less reactive, noisier
        p["gain"] *= 1 - 0.5 * self.tired
        p["noise"] *= 1 + self.tired
        return p

    # --- inputs --------------------------------------------------------------------
    def stimulus(self, t, kind, usd=0.0):
        """Register a chat message ('message') or trade ('trade') for arousal. Returns the current gain."""
        amount = 0.0
        if kind == "message":
            amount = 1.0 if self.stage != "NREM" else 1.0 - 0.4 * self.depth
        elif kind == "trade" and usd >= BIG_TRADE_USD:
            amount = min(1.5 * WAKE_THRESHOLD, usd / BIG_TRADE_USD)     # >= ~$15k wakes it on its own
        if amount > 0:
            self.arousal += amount
            self.last_stim = t
            self.arousal_log.append([t, amount, kind, usd])
        return self.gain

    # --- clock ---------------------------------------------------------------------
    def update(self, t, dt_real=None):
        """Advance to sim time t. Returns a list of events (dicts with 'type' and 'text')."""
        dt = max(0.0, t - self.t)
        self.t = t
        ev = []
        # people type in real time: with an accelerated clock, arousal builds up during sleep by decaying
        # at most 3x faster than real time (awake, it settles on the sim clock as usual)
        decay_dt = dt if dt_real is None or not self.asleep else min(dt, 3 * dt_real)
        self.arousal *= math.exp(-decay_dt / AROUSAL_TAU_S)
        if self.arousal < 0.3:
            self.arousal_log = []              # episode over: the next wake-up cause starts fresh
        del self.arousal_log[:-200]
        hour = local(t).hour
        if self.night is None and self.in_night(t):
            self.open_night(t)                 # awake at midnight: the night (and lost sleep) starts anyway

        # sleep debt bookkeeping
        if self.asleep:
            repay = DEBT_REPAY_PER_H + (1.0 if hour >= EARLY_BED_HOUR else 0.0)   # early night repays more
            self.debt = max(0.0, self.debt - repay * dt / 3600)
        elif self.in_night(t) and self.night is not None:
            self.debt += dt / 3600                                                  # lost sleep

        if self.asleep:
            if WAKE_HOUR <= hour < EARLY_BED_HOUR:
                ev.append(self.wake(t, f"woke up at {hhmm(t)}", natural=True))
            elif self.arousal >= WAKE_THRESHOLD:
                ev.append(self.wake(t, f"woken at {hhmm(t)} by {self.cause(t)}"))
        else:
            if self.night is not None and WAKE_HOUR <= hour < EARLY_BED_HOUR:
                self.awake_since = t                                                # stayed up until morning
                self.close_night(t)
            sleepy = self.in_night(t) or (hour >= EARLY_BED_HOUR and self.pressure(t) >= 1.0)
            if sleepy and self.arousal < SLEEP_OK and t - self.last_stim >= QUIET_S:
                ev.append(self.fall_asleep(t))

        if self.asleep:
            stage, self.depth, _ = self.cycle_stage(t)
            if stage != self.stage:
                self.stage = stage
                self.night["timeline"].append({"t": stamp(t), "stage": stage})
            if stage == "REM":
                if self.next_replay is None:
                    self.next_replay = t + self.rng.expovariate(1 / REPLAY_MEAN_S)
                if t >= self.next_replay:
                    self.next_replay = t + self.rng.expovariate(1 / REPLAY_MEAN_S)
                    ev.append({"type": "replay", "text": "replay"})           # live_server picks the memory
            else:
                self.next_replay = None
        else:
            self.depth = 0.0

        # glide parameters toward the stage target (never jump)
        x = dt / TRANSITION_S
        if dt_real is not None:
            x = min(x, dt_real / TRANSITION_REAL_S)
        self.params = lerp(self.params, self.stage_params(), 1 - math.exp(-x))
        return ev

    def cause(self, t):
        recent = self.arousal_log              # everything since arousal was last near zero
        trades = [e for e in recent if e[2] == "trade"]
        if trades and sum(e[1] for e in trades) >= 0.5 * sum(e[1] for e in recent):
            return f"a large trade (${max(e[3] for e in trades):,.0f})"
        n = sum(1 for e in recent if e[2] == "message")
        return f"{n} message{'s' * (n != 1)}"

    # --- transitions ---------------------------------------------------------------
    def open_night(self, t):
        self.night = {"date": night_date(t), "timezone": "Europe/Rome", "sleep_onset": None, "woke_up": None,
                      "timeline": [], "wakeups": [], "sleep_debt": {"start": round(self.debt, 2), "end": None},
                      "replays": []}

    def fall_asleep(self, t):
        if self.night is None:
            self.open_night(t)
        n = self.night
        if n["sleep_onset"] is None:
            n["sleep_onset"] = stamp(t)
            self.k_base = 0
        else:                                  # back to sleep after a wake-up: keep the night's cycle count
            first = datetime.fromisoformat(n["sleep_onset"]).replace(tzinfo=ROME).timestamp()
            self.k_base = int((t - first) // CYCLE_S)
        self.asleep, self.onset = True, t
        self.stage, self.depth, _ = self.cycle_stage(t)
        n["timeline"].append({"t": stamp(t), "stage": self.stage})
        return {"type": "sleep", "text": f"fell asleep at {hhmm(t)}"}

    def wake(self, t, text, natural=False):
        self.asleep, self.stage, self.depth = False, "AWAKE", 0.0
        self.night["timeline"].append({"t": stamp(t), "stage": "AWAKE"})
        if natural:
            self.awake_since = t
            self.close_night(t)
        else:
            self.debt += DEBT_PER_WAKEUP
            self.night["wakeups"].append({"t": stamp(t), "cause": text.split(" by ", 1)[-1]})
        self.last_stim = t                     # needs a quiet period before sleeping again
        return {"type": "wake", "text": text, "natural": natural}

    def close_night(self, t):
        n = self.night
        n["woke_up"] = stamp(t)
        n["sleep_debt"]["end"] = round(self.debt, 2)
        self.last_night = n
        self.night = None

    def record_replay(self, t, m):
        self.night["replays"].append({"t": stamp(t), "text": m["text"], "emotion": m["emotion"],
                                      "networks": m["networks"], "received": stamp(m["t"]),
                                      "received_stage": m["stage"]})

    def replay_counts(self):
        counts = {}
        for r in (self.night or {}).get("replays", []):
            counts[r["received"]] = counts.get(r["received"], 0) + 1
        return counts

    def night_start(self):
        """Sim epoch of tonight's first sleep onset (None if not in a night)."""
        if self.night is None or self.night["sleep_onset"] is None:
            return None
        return datetime.fromisoformat(self.night["sleep_onset"]).replace(tzinfo=ROME).timestamp()

    def status(self):
        return {"stage": self.stage, "clock": hhmm(self.t), "date": local(self.t).strftime("%a %d %b"),
                "debt": round(self.debt, 2), "tired": round(self.tired, 2), "depth": round(self.depth, 2),
                "gain": round(self.gain, 3), "arousal": round(self.arousal, 2),
                "woken_tonight": len(self.night["wakeups"]) if self.night else 0}

    # --- persistence ---------------------------------------------------------------
    STATE_KEYS = ("t", "asleep", "stage", "depth", "onset", "k_base", "awake_since", "arousal", "arousal_log",
                  "last_stim", "debt", "night", "last_night", "params")

    def to_dict(self):
        return {k: getattr(self, k) for k in self.STATE_KEYS}

    @classmethod
    def from_dict(cls, d, rng=None):
        e = cls(d["t"], rng)
        for k in cls.STATE_KEYS:
            if k in d:
                setattr(e, k, d[k])
        return e


class Store:
    """data/state.json (engine + memory) and data/nights/YYYY-MM-DD.json."""

    def __init__(self, root):
        self.root = Path(root)
        (self.root / "nights").mkdir(parents=True, exist_ok=True)

    def load(self):
        f = self.root / "state.json"
        if not f.exists():
            return None, None
        d = json.loads(f.read_text())
        return d["engine"], d["memory"]

    def save(self, engine, memory):
        self._write(self.root / "state.json", {"engine": engine.to_dict(), "memory": memory.items})
        for n in (engine.night, engine.last_night):
            if n is not None:
                self._write(self.root / "nights" / f"{n['date']}.json", n)

    @staticmethod
    def _write(path, obj):
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(obj, indent=1, ensure_ascii=False))
        tmp.replace(path)
