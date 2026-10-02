"""Tastes: what kinds of pages have paid off before, learned from the brain model's own response.

A per-topic preference table. A page's topics are the networks of the option that led to it ("net:reward") and up to
5 keywords of its label and title ("kw:bread"). While he stays on a page the live server measures how strongly the
brain responded (value of reward / attention / fear activity relative to his recent average, squashed to -1..1); when
he leaves, the prediction error  delta = response - predict(topics)  moves each topic's preference by ALPHA * delta
(a reward-prediction-error rule). Preferences decay toward 0 with time constant TAU_DAYS, so unvisited tastes fade.
The first PageWatch.SKIP_S (10 s) of a stay are not counted: the chosen option's own stimulus (2 s decay) is gone by
then, so a choice does not confirm itself (checked: same response with and without it, within 0.003). The model has
no other input from the page, so the stay response also carries whatever else drives the brain meanwhile (chat,
trades, readings, its own slow activity): tastes are a slow, noisy average, not a judgement of the page.

The interface is three methods, kept small so the spiking brain (feature/spiking-brain) can replace the table with
dopamine-modulated synapses later:  topics(option, title) -> [str],  predict(topics) -> float in [-1, 1],
learn(topics, response) -> delta. Nothing here is enjoyment: it is a running average of simulated activity.
"""
import json
import math
import time
from pathlib import Path

from research import keywords

ALPHA = 0.2
TAU_DAYS = 7.0
CAP = 400                     # topics kept (the weakest are dropped)
MIN_ABS = 0.01


class Tastes:
    def __init__(self, path=None, clock=time.time):
        self.path = Path(path) if path else None
        self.clock = clock
        self.pref, self.seen, self.last = {}, {}, clock()
        if self.path and self.path.exists():
            try:
                d = json.loads(self.path.read_text())
                self.pref, self.seen, self.last = d.get("pref", {}), d.get("seen", {}), d.get("last", self.last)
            except (OSError, ValueError):
                pass

    # --- the interface ---------------------------------------------------------------------------------------------
    @staticmethod
    def topics(option, title=""):
        nets = sorted(option.get("networks", {}).items(), key=lambda kv: -kv[1])
        out = [f"net:{g}" for g, w in nets if w >= 0.2][:3]
        out += [f"kw:{w}" for w in keywords(option.get("label", ""), title or "", n=5)]
        return out

    def predict(self, topics):
        vals = [self.pref[t] for t in topics if t in self.pref]
        return sum(vals) / len(vals) if vals else 0.0

    def learn(self, topics, response):
        """Reward-prediction-error update; `response` in [-1, 1]. Returns the prediction error."""
        if not topics:
            return 0.0
        response = float(response)
        if not math.isfinite(response):                       # a broken measurement teaches nothing
            return 0.0
        self.decay()
        response = max(-1.0, min(1.0, response))
        delta = response - self.predict(topics)
        now = self.clock()
        for t in topics:
            self.pref[t] = max(-1.0, min(1.0, self.pref.get(t, 0.0) + ALPHA * delta))
            self.seen[t] = now
        if len(self.pref) > CAP:
            for t in sorted(self.pref, key=lambda k: abs(self.pref[k]))[:len(self.pref) - CAP]:
                self.pref.pop(t, None)
                self.seen.pop(t, None)
        self.save()
        return delta

    # --- housekeeping ------------------------------------------------------------------------------------------------
    def decay(self):
        now = self.clock()
        k = math.exp(-max(0.0, now - self.last) / (TAU_DAYS * 86400))
        self.last = now
        if k < 1.0:
            for t in list(self.pref):
                self.pref[t] *= k
                if abs(self.pref[t]) < MIN_ABS:
                    self.pref.pop(t)
                    self.seen.pop(t, None)

    def save(self):
        if not self.path:
            return
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"pref": self.pref, "seen": self.seen, "last": self.last}))
        tmp.replace(self.path)

    def top(self, n=12):
        self.decay()
        items = sorted(self.pref.items(), key=lambda kv: -kv[1])
        fmt = lambda kv: {"topic": kv[0].split(":", 1)[1], "kind": "network" if kv[0].startswith("net:") else "word",
                          "pref": round(kv[1], 3)}
        return {"favoured": [fmt(kv) for kv in items[:n] if kv[1] > 0],
                "avoided": [fmt(kv) for kv in items[::-1][:n] if kv[1] < 0], "topics": len(self.pref),
                "rule": f"prediction error x {ALPHA}, decay {TAU_DAYS:g} days",
                "note": "Learned from the brain model's simulated response to pages; not enjoyment or understanding."}


class PageWatch:
    """Measures the brain's response while he stays on a page (fed every tick with the relative group activity)."""

    SKIP_S = 10.0             # the chosen option's own stimulus (2 s decay) must be gone, or every choice "pays off"
    SCALE = 0.5               # response units -> tanh
    BASE_TAU_S = 600.0        # running baseline of the same measure

    def __init__(self):
        self.base, self.cur = None, None

    @staticmethod
    def measure(rel):
        return rel.get("reward", 1.0) + 0.6 * rel.get("attention", 1.0) - 0.8 * rel.get("fear", 1.0)

    def start(self, topics, t):
        self.cur = {"topics": list(topics), "t0": t, "sum": 0.0, "n": 0}

    def feed(self, rel, t, dt):
        v = self.measure(rel)
        self.base = v if self.base is None else self.base + (v - self.base) * min(1.0, dt / self.BASE_TAU_S)
        c = self.cur
        if c is not None and t - c["t0"] >= self.SKIP_S:
            c["sum"] += v - self.base
            c["n"] += 1

    def finish(self):
        """-> (topics, response in -1..1) of the page he is leaving, or None if it was too short to measure."""
        c, self.cur = self.cur, None
        if not c or c["n"] < 20:
            return None
        return c["topics"], math.tanh(c["sum"] / c["n"] / self.SCALE)
