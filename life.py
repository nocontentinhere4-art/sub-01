"""SUB-01's simulated life: a character in a small world whose choices come from needs + the brain model.

Server-authoritative: one agent, one world, everyone sees the same life. Needs (hunger, boredom, energy from
the sleep engine) rise over simulated time; every time an activity ends, a utility score picks the next one.
The brain model tilts the scores (reward -> goes out, fear -> stays in, salience -> checks the chart) and chat
messages add short-lived desires ("vai a comprare il pane"). Walking happens in real time along a waypoint
graph, so what viewers see is continuous. It is a simulation driven by a brain model, not a person.
"""
import heapq
import math
import random
import re

from sleep import local

# ---- the world (metres; x east, z south). Sent to the client, which builds the 3D scene from it. ----------
PLACES = {
    "bed": (1.6, 1.3), "window": (4.0, 0.9), "table": (6.3, 4.2), "desk": (6.5, 1.6),
    "door_in": (4.0, 5.4), "door_out": (4.0, 6.9), "street_home": (4.0, 10.0),
    "street_bakery": (21.0, 10.0), "bakery_door": (21.0, 13.0), "bakery_in": (21.0, 15.2),
    "counter": (21.0, 16.4), "street_park": (-13.0, 10.0), "park_gate": (-13.0, 13.4), "bench": (-13.0, 17.4),
}
EDGES = [("bed", "window"), ("bed", "table"), ("bed", "desk"), ("bed", "door_in"), ("window", "table"),
         ("window", "desk"), ("window", "door_in"), ("table", "desk"), ("table", "door_in"), ("desk", "door_in"),
         ("door_in", "door_out"), ("door_out", "street_home"), ("street_home", "street_bakery"),
         ("street_home", "street_park"), ("street_bakery", "bakery_door"), ("bakery_door", "bakery_in"),
         ("bakery_in", "counter"), ("street_park", "park_gate"), ("park_gate", "bench")]
WORLD = {"places": PLACES, "edges": EDGES,
         "apartment": [0, 0, 8, 6], "bakery": [17, 14, 25, 20], "park": [-19, 13, -7, 23],
         "street": [-22, 8.5, 30, 11.5]}

WALK_SPEED = 1.3            # m / real second
ACTIVITIES = {              # place, pose, (min, max) simulated minutes
    "sleep": ("bed", "lying", (0, 0)),
    "phone": ("bed", "lying_phone", (12, 40)),
    "eat": ("table", "sitting", (8, 15)),
    "buy_bread": ("counter", "standing", (2, 4)),
    "chart": ("desk", "sitting_desk", (10, 25)),
    "window": ("window", "standing", (3, 8)),
    "park": ("bench", "sitting", (20, 45)),
}
LABEL = {"sleep": "sleeping", "phone": "in bed scrolling the phone", "eat": "eating bread at the table",
         "buy_bread": "buying bread", "chart": "watching the chart at the desk", "window": "looking out of the window",
         "park": "sitting on the park bench"}
DESIRES = [  # chat words -> short-lived desire
    (r"\b(pane|bread|fame|hungry|mangia|eat|colazione|breakfast)\b", "buy_bread"),
    (r"\b(tiktok|telefono|phone|scroll|social|video)\b", "phone"),
    (r"\b(parco|park|fuori|outside|passeggia|walk|aria)\b", "park"),
    (r"\b(grafico|chart|candele|candles|prezzo|price|pump|dump)\b", "chart"),
    (r"\b(finestra|window|guarda fuori|look outside)\b", "window"),
]


def graph():
    g = {k: [] for k in PLACES}
    for a, b in EDGES:
        d = math.dist(PLACES[a], PLACES[b])
        g[a].append((b, d))
        g[b].append((a, d))
    return g


GRAPH = graph()


def route(a, b):
    """Shortest waypoint path a -> b (Dijkstra)."""
    q, seen, prev = [(0.0, a)], {a: 0.0}, {}
    while q:
        d, n = heapq.heappop(q)
        if n == b:
            break
        for m, w in GRAPH[n]:
            if d + w < seen.get(m, 1e9):
                seen[m], prev[m] = d + w, n
                heapq.heappush(q, (d + w, m))
    path = [b]
    while path[-1] != a:
        path.append(prev[path[-1]])
    return path[::-1]


class Life:
    def __init__(self, state=None, rng=None):
        s = state or {}
        self.rng = rng or random.Random()
        self.place = s.get("place", "bed")
        self.x, self.z = PLACES[self.place]
        self.heading = 0.0
        self.path = []                         # remaining waypoints while walking
        self.activity = s.get("activity", "window")
        self.until = s.get("until", 0.0)       # sim time when the activity ends
        self.hunger = s.get("hunger", 0.4)
        self.boredom = s.get("boredom", 0.3)
        self.bread = s.get("bread", 0)
        self.desires = s.get("desires", {})    # activity -> (strength, sim time)
        self.phone_app = "chart"
        self.log = s.get("log", [])            # recent events for the page
        self.say = ""
        target = ACTIVITIES[self.activity][0]
        if target != self.place:                          # restored mid-activity somewhere else: walk there
            self.path = route(self.place, target)[1:]

    # --- inputs ---------------------------------------------------------------------------------
    def hear(self, text, t):
        low = text.lower()
        for pat, act in DESIRES:
            if re.search(pat, low):
                w = self.desires.get(act, [0, t])[0]
                self.desires[act] = [min(1.5, w + 0.6), t]

    def desire(self, act, t):
        w, t0 = self.desires.get(act, [0.0, t])
        return w * 0.5 ** ((t - t0) / 3600)            # halves every sim hour

    # --- decision ---------------------------------------------------------------------------------
    def choose(self, t, stage, rel, market_hot, pressure):
        h = local(t).hour + local(t).minute / 60
        if stage != "AWAKE":
            return "sleep"
        open_bakery = 7 <= h < 20
        day = 8 <= h < 20
        r = self.rng.random
        s = {
            "eat": (1.3 * self.hunger + 0.2 + (0.6 if self.hunger > 0.35 else 0)) if self.bread else 0.0,
            "buy_bread": (1.1 * self.hunger + self.desire("buy_bread", t)) if (not self.bread and open_bakery) else 0.0,
            "phone": 0.7 * self.boredom + (0.5 if h >= 22.5 or h < 1 else 0) + 0.25 * pressure
                     + self.desire("phone", t) + 0.2 * max(0, rel.get("salience", 1) - 1),
            "chart": 0.35 * market_hot + 0.4 * max(0, rel.get("salience", 1) - 1) + self.desire("chart", t) + 0.1,
            "park": (0.5 * self.boredom + 0.8 * max(0, rel.get("reward", 1) - 1) + self.desire("park", t))
                    if day and rel.get("fear", 1) < 1.3 else 0.0,
            "window": 0.2 + 0.15 * max(0, rel.get("fear", 1) - 1) + self.desire("window", t),
        }
        if self.activity in s:
            s[self.activity] *= 0.4                     # avoid doing the same thing twice in a row
        return max(s, key=lambda k: s[k] + 0.15 * r())

    def start(self, act, t, why):
        self.activity = act
        place, _, (a, b) = ACTIVITIES[act]
        self.until = t + 60 * self.rng.uniform(a, b)
        if place != self.place or (self.x, self.z) != PLACES[place]:
            self.path = route(self.place, place)[1:]
        if act == "phone":
            self.phone_app = self.rng.choice(["chart", "chat", "tiktok", "chart"])
        self.desires.pop(act, None)
        self.say = why
        self.log = (self.log + [{"t": t, "what": why}])[-30:]

    # --- per tick -----------------------------------------------------------------------------------
    def update(self, t, dt_real, dt_sim, stage, rel, market_hot, pressure):
        self.hunger = min(1.0, self.hunger + dt_sim / (5 * 3600))
        if self.activity in ("window", "chart"):
            self.boredom = min(1.0, self.boredom + dt_sim / (2 * 3600))
        if self.activity == "phone":
            self.boredom = max(0.0, self.boredom - dt_sim / (40 * 60))
        if self.activity == "park":
            self.boredom = max(0.0, self.boredom - dt_sim / (30 * 60))
            self.hunger = min(1.0, self.hunger + dt_sim / (8 * 3600))
        # walking (real time, so viewers see continuous motion)
        if self.path:
            tx, tz = PLACES[self.path[0]]
            dx, dz = tx - self.x, tz - self.z
            d = math.hypot(dx, dz)
            step = WALK_SPEED * dt_real
            self.heading = math.atan2(dx, dz)
            if d <= step:
                self.x, self.z = tx, tz
                self.place = self.path.pop(0)
            else:
                self.x += dx / d * step
                self.z += dz / d * step
            return
        # arrived: effects of finishing the activity, then pick the next one
        if self.activity == "sleep" and stage != "AWAKE":
            return                                        # asleep: nothing to decide until the brain wakes up
        must_sleep = stage != "AWAKE"
        woke = stage == "AWAKE" and self.activity == "sleep"
        if t >= self.until or must_sleep or woke:
            if self.activity == "buy_bread" and self.place == "counter":
                self.bread += 2
            if self.activity == "eat" and self.bread:
                self.bread -= 1
                self.hunger = max(0.0, self.hunger - 0.6)
            nxt = self.choose(t, stage, rel, market_hot, pressure)
            why = {
                "sleep": "falls asleep" if self.place == "bed" else "goes to bed",
                "eat": "hungry: eats some bread", "buy_bread": "hungry and no bread left: goes to the bakery",
                "phone": "bored: picks up the phone", "chart": "the market is moving: checks the chart",
                "park": "feels good: goes out to the park", "window": "looks out of the window",
            }[nxt]
            if woke:
                why = "wakes up"
            self.start(nxt, t, why)

    def snapshot(self):
        return {"x": round(self.x, 2), "z": round(self.z, 2), "heading": round(self.heading, 2),
                "walking": bool(self.path), "activity": self.activity, "doing": LABEL[self.activity],
                "pose": "walking" if self.path else ACTIVITIES[self.activity][1], "place": self.place,
                "hunger": round(self.hunger, 2), "boredom": round(self.boredom, 2), "bread": self.bread,
                "phone": self.phone_app if self.activity == "phone" and not self.path else None,
                "say": self.say, "log": [{"t": e["t"], "what": e["what"]} for e in self.log[-8:]]}

    def to_dict(self):
        return {"place": self.place, "activity": self.activity, "until": self.until, "hunger": self.hunger,
                "boredom": self.boredom, "bread": self.bread, "desires": self.desires, "log": self.log}
