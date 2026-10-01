"""SUB-01's simulated life: a character in a small world whose choices come from needs + the brain model.

Server-authoritative: one agent, one world, everyone sees the same life. Needs (hunger, boredom, energy from
the sleep engine) rise over simulated time; every time an activity ends, a utility score picks the next one.
The brain model tilts the scores (reward -> goes out, fear -> stays in, salience -> checks the chart) and chat
messages add short-lived desires ("vai a comprare il pane"). Walking happens in real time along a waypoint
graph, so what viewers see is continuous. It is a simulation driven by a brain model, not a person.
"""
import heapq
import json
import math
import random
import re
from pathlib import Path

from sleep import local
from twin.body import Body

CARBS_PER_BREAD_G = 30.0    # one piece of bread: a ~60 g roll at ~50 % carbohydrate (USDA FoodData Central, white bread ~49 g/100 g)
# Eating thresholds on the body's hunger scale (design choices, not fitted): below SATED it does not eat at all,
# above EAT_AT it is meal time. With the body's ghrelin-like proxy this gives a few eating episodes per waking day
# (the old +0.2 constant and 0.35 threshold made it eat about every hour once hunger came from the body).
SATED, EAT_AT = 0.35, 0.55

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

WALK_SPEED = 1.3            # m / real second (indoors and in the 3D model)

# ---- the real streets (Kichijoji, Tokyo): outdoor legs of the 3D graph are mapped onto real walking routes ----
TOKYO = json.loads((Path(__file__).parent / "web" / "tokyo_routes.json").read_text())
OUTDOOR = {"bakery_door": ("home-bakery", ["door_out", "street_home", "street_bakery", "bakery_door"]),
           "park_gate": ("home-park", ["door_out", "street_home", "street_park", "park_gate"])}


def along(latlng, f):
    """Point and heading at fraction f of a polyline [[lat, lng], ...]."""
    seg = [math.dist(a, b) for a, b in zip(latlng, latlng[1:])]
    goal, acc = max(0.0, min(1.0, f)) * sum(seg), 0.0
    for (a, b), d in zip(zip(latlng, latlng[1:]), seg):
        if acc + d >= goal and d > 0:
            t = (goal - acc) / d
            lat, lng = a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])
            heading = math.degrees(math.atan2((b[1] - a[1]) * math.cos(math.radians(a[0])), b[0] - a[0])) % 360
            return lat, lng, heading
        acc += d
    a, b = latlng[-2], latlng[-1]
    return b[0], b[1], math.degrees(math.atan2((b[1] - a[1]) * math.cos(math.radians(a[0])), b[0] - a[0])) % 360
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
    def __init__(self, state=None, rng=None, body=None):
        """body: a twin.body.Body updated by the caller (live_server). Without one, Life makes and steps its own
        (backwards compatible); its state is then saved in to_dict()["body"]."""
        s = state or {}
        self.rng = rng or random.Random()
        self.place = s.get("place", "bed")
        self.x, self.z = PLACES[self.place]
        self.heading = 0.0
        self.path = []                         # remaining waypoints while walking
        self.activity = s.get("activity", "window")
        self.until = s.get("until", 0.0)       # sim time when the activity ends
        self.own_body = body is None
        if body is None:
            bs = s.get("body")
            if bs is None and "hunger" in s:               # legacy save: only the old hunger number
                bs = {"ghrelin": min(1.0, max(0.0, s["hunger"]))}
            body = Body(bs)
        self.body = body
        self.boredom = s.get("boredom", 0.3)
        self.bread = s.get("bread", 0)
        self.desires = s.get("desires", {})    # activity -> (strength, sim time)
        self.phone_app = "chart"
        self.log = s.get("log", [])            # recent events for the page
        self.say = ""
        self.time_scale = 1.0
        self.geo = None                        # real position in Tokyo while outside
        target = ACTIVITIES[self.activity][0]
        if target != self.place:                          # restored mid-activity somewhere else: walk there
            self.path = route(self.place, target)[1:]

    @property
    def hunger(self):
        """0..1, from the body's blood glucose and gut/ghrelin-like proxy (no rule of its own)."""
        return self.body.hunger

    def exertion(self):
        """0..1 physical effort for the body: walking about 0.3, sitting on the park bench 0.1."""
        return 0.3 if self.path else 0.1 if self.activity == "park" else 0.0

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
        hu = self.hunger                                # from the body (twin/body.py): ~0.2 just fed, ~0.6 at meal time
        s = {
            "eat": (1.3 * hu + (0.6 if hu > EAT_AT else 0.0) if hu > SATED else 0.0) if self.bread else 0.0,
            "buy_bread": ((1.1 * hu if hu > SATED else 0.0) + self.desire("buy_bread", t))
                         if (not self.bread and open_bakery) else 0.0,
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
    def update(self, t, dt_real, dt_sim, stage, rel, market_hot, pressure, levels=None, amygdala=0.0):
        if self.own_body:                                 # an external body is stepped by its owner
            self.body.update(dt_sim, levels, amygdala, stage, exertion=self.exertion())
        if self.activity in ("window", "chart"):
            self.boredom = min(1.0, self.boredom + dt_sim / (2 * 3600))
        if self.activity == "phone":
            self.boredom = max(0.0, self.boredom - dt_sim / (40 * 60))
        if self.activity == "park":
            self.boredom = max(0.0, self.boredom - dt_sim / (30 * 60))
        # walking (real time, so viewers see continuous motion)
        if self.path:
            tx, tz = PLACES[self.path[0]]
            dx, dz = tx - self.x, tz - self.z
            d = math.hypot(dx, dz)
            step = WALK_SPEED * dt_real
            out = self.outdoor_leg()
            if out:                                       # outside: take as long as the real Tokyo walk
                name, nodes, length = out
                real_s = TOKYO["routes"][name]["meters"] / WALK_SPEED / max(1.0, self.time_scale)
                step = length / real_s * dt_real
            self.heading = math.atan2(dx, dz)
            if d <= step:
                self.x, self.z = tx, tz
                self.place = self.path.pop(0)
            else:
                self.x += dx / d * step
                self.z += dz / d * step
            self.update_geo()
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
                self.body.eat(CARBS_PER_BREAD_G)
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

    def outdoor_leg(self):
        """(route name, 3D nodes, 3D length) when the current step is on the street between home and a destination."""
        here, nxt = self.place, (self.path[0] if self.path else None)
        for dest, (name, nodes) in OUTDOOR.items():
            if here in nodes and nxt in nodes:
                return name, nodes, sum(math.dist(PLACES[a], PLACES[b]) for a, b in zip(nodes, nodes[1:]))
        return None

    def update_geo(self):
        """Real Tokyo position: fraction of the way along the outdoor 3D legs -> same fraction of the real route."""
        out = self.outdoor_leg()
        if not out:
            if not self.path and self.place in ("counter", "bakery_in", "bench"):
                return                                    # inside the shop / on the bench: keep the last street point
            if not self.path or self.place in ("door_in", "bed", "table", "desk", "window"):
                self.geo = None                           # at home
            return
        name, nodes, length = out
        cum = [0.0]
        for p, q in zip(nodes, nodes[1:]):
            cum.append(cum[-1] + math.dist(PLACES[p], PLACES[q]))
        i, forward = nodes.index(self.place), nodes.index(self.path[0]) > nodes.index(self.place)
        moved = math.dist(PLACES[self.place], (self.x, self.z))
        f = (cum[i] + moved if forward else cum[i] - moved) / length
        lat, lng, hd = along(TOKYO["routes"][name]["latlng"], f)
        if not forward:
            hd = (hd + 180) % 360
        self.geo = {"lat": round(lat, 6), "lng": round(lng, 6), "heading": round(hd), "route": name, "f": round(f, 3)}

    def snapshot(self):
        return {"x": round(self.x, 2), "z": round(self.z, 2), "heading": round(self.heading, 2),
                "walking": bool(self.path), "activity": self.activity, "doing": LABEL[self.activity],
                "pose": "walking" if self.path else ACTIVITIES[self.activity][1], "place": self.place,
                "hunger": round(self.hunger, 2), "boredom": round(self.boredom, 2), "bread": self.bread,
                "phone": self.phone_app if self.activity == "phone" and not self.path else None,
                "geo": self.geo, "say": self.say, "log": [{"t": e["t"], "what": e["what"]} for e in self.log[-8:]]}

    def to_dict(self):
        d = {"place": self.place, "activity": self.activity, "until": self.until, "hunger": self.hunger,
             "boredom": self.boredom, "bread": self.bread, "desires": self.desires, "log": self.log}
        if self.own_body:
            d["body"] = self.body.to_dict()
        return d
