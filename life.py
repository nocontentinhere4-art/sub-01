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
import time

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
OPENING = {"bakery": (7.0, 20.0)}   # local (Europe/Rome) hours: bakery 07:00-20:00; the park is open in daylight (sun_hours)
PARK_DUSK_MIN = 20          # nobody sets off for the park in the last 20 minutes before sunset
LAST_ORDER_MIN = 10         # the bakery is not worth walking to in the last 10 minutes before closing
ROME_LAT, ROME_LON = 41.9, 12.5
TIRED_ENERGY = 0.2          # energy (1 - sleep pressure) below this: too tired to go to the park
HUNGRY_TO_EAT = 0.3         # "buy bread" while bread is at home turns into eating only when at least this hungry
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


def path_length(names):
    """Length in metres of the waypoint polyline `names`."""
    return sum(math.dist(PLACES[a], PLACES[b]) for a, b in zip(names, names[1:]))


def hhmm_h(t):
    lt = local(t)
    return lt.hour + lt.minute / 60


def sun_hours(t):
    """(sunrise, sunset) in local Rome hours for the date of `t`: seasonal (a December sunset is about 16:40),
    from the solar declination and the equation of time. Good to a few minutes, which is all a park gate needs."""
    lt = local(t)
    n = lt.timetuple().tm_yday
    b = math.radians(360.0 / 365.0 * (n - 81))
    decl = math.radians(23.44) * math.sin(b)
    eot_min = 9.87 * math.sin(2 * b) - 7.53 * math.cos(b) - 1.5 * math.sin(b)
    cos_h = (math.sin(math.radians(-0.83)) - math.sin(math.radians(ROME_LAT)) * math.sin(decl)) / (
        math.cos(math.radians(ROME_LAT)) * math.cos(decl))
    half = math.degrees(math.acos(max(-1.0, min(1.0, cos_h)))) / 15.0          # half the day length, hours
    off = lt.utcoffset().total_seconds() / 3600.0
    noon = 12.0 + off - ROME_LON / 15.0 - eot_min / 60.0
    return noon - half, noon + half


def is_open(what, t):
    """Opening hours on the Rome clock: 'bakery' (fixed 07:00-20:00) or 'park' (between sunrise and sunset)."""
    h = hhmm_h(t)
    if what == "park":
        a, b = sun_hours(t)
    else:
        a, b = OPENING[what]
    return a <= h < b


def bakery_reachable(t):
    """Open now and not about to close (nobody sets off for the bakery in the last minutes)."""
    return is_open("bakery", t) and hhmm_h(t) < OPENING["bakery"][1] - LAST_ORDER_MIN / 60


def fmt_h(h):
    return f"{int(h):02d}:{int(round((h % 1) * 60)):02d}"


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
        self.route = []                        # place names of the current walk, start..goal ([] when not walking)
        self.stage = "AWAKE"                   # last stage seen in update(): request() declines while asleep
        self.energy = 1.0                      # 1 - sleep pressure (clamped), set in update()
        self.t = None                          # last sim time seen in update()
        target = ACTIVITIES[self.activity][0]
        if target != self.place:                          # restored mid-activity somewhere else: walk there
            self._walk_to(target)

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
        open_bakery = bakery_reachable(t)
        day = is_open("park", t)
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

    # --- walking plan -------------------------------------------------------------------------------
    def _walk_to(self, goal):
        """Plan the walk to `goal`. While already walking, never cut across: the agent finishes the current edge
        (forward) or turns back along it, whichever is shorter, and continues on the waypoint graph from there."""
        start = self.place
        if self.path:
            a, b = self.place, self.path[0]
            pos = (self.x, self.z)
            fwd = math.dist(pos, PLACES[b]) + path_length(route(b, goal))
            back = math.dist(pos, PLACES[a]) + path_length(route(a, goal))
            first = b if fwd <= back else a
            if first == a and a != b and math.dist(pos, PLACES[a]) > 0.05:
                start = b                                  # turning back: the half-edge walk is b -> a (then on)
            self.path = [first] + route(first, goal)[1:]
        elif goal != self.place or (self.x, self.z) != PLACES[goal]:
            self.path = route(self.place, goal)[1:]
        names = [start] + self.path
        self.route = [n for i, n in enumerate(names) if i == 0 or n != names[i - 1]] if self.path else []

    def remaining(self):
        """Metres left on the current walk."""
        if not self.path:
            return 0.0
        return math.dist((self.x, self.z), PLACES[self.path[0]]) + path_length(self.path)

    def progress(self):
        """Walked fraction (0..1) of the current route (WALK_SPEED on the waypoint graph); 0 when not walking."""
        if not self.path or len(self.route) < 2:
            return 0.0
        total = path_length(self.route)
        return round(min(1.0, max(0.0, 1.0 - self.remaining() / total)) if total > 0 else 0.0, 3)

    # --- requests from the workspace ---------------------------------------------------------------------------
    def request(self, act, t, reason=""):
        """The workspace proposes `act` -> (ok, why). Accepted requests start the activity at once (walking there
        safely if needed); declines carry a reason tied to state, needs or opening hours. `t` = sim time."""
        if act not in ACTIVITIES:
            return False, f"unknown activity {act}"
        if self.stage != "AWAKE":
            return False, "asleep right now"
        if act == "sleep":
            return False, "that is not something to request"
        if act == self.activity and not self.path:
            return False, "already doing that"
        if act == self.activity and self.path:
            return True, "already on the way"                 # the plan is left alone (no re-roll, no duplicate log)
        if self.activity in ("buy_bread", "eat") and not self.path and t < self.until:
            return False, f"busy: finishing {LABEL[self.activity]}"     # short need-satisfying activity: let it end
        if act == "buy_bread":
            if self.bread:
                if self.hunger < HUNGRY_TO_EAT:
                    return False, "already has bread at home and is not hungry"
                if self.activity == "eat":
                    return False, "already has bread at home and is eating it"
                self.start("eat", t, "has bread at home: eats instead")
                return False, "already has bread at home: eats it instead"
            if not bakery_reachable(t):
                a, b = OPENING["bakery"]
                if is_open("bakery", t):
                    return False, f"the bakery is about to close (open {fmt_h(a)}-{fmt_h(b)}): too late to get there"
                return False, f"the bakery is closed now (open {fmt_h(a)}-{fmt_h(b)})"
        elif act == "eat":
            if not self.bread:
                return False, "nothing to eat at home yet"
            if self.hunger < 0.15:
                return False, "not hungry"
        elif act == "park":
            if not is_open("park", t):
                return False, "too dark for the park now (daylight only)"
            if sun_hours(t)[1] - hhmm_h(t) < PARK_DUSK_MIN / 60:
                return False, "too dark for the park soon (it is almost dusk)"
            if self.energy < TIRED_ENERGY:
                return False, f"too tired for the park (energy {self.energy:.0%})"
        self.start(act, t, reason or f"starts: {LABEL[act]}")
        return True, "ok"

    def start(self, act, t, why):
        self.activity = act
        place, _, (a, b) = ACTIVITIES[act]
        self.until = t + 60 * self.rng.uniform(a, b)
        if place != self.place or (self.x, self.z) != PLACES[place] or self.path:
            self._walk_to(place)
        if act == "phone":
            self.phone_app = self.rng.choice(["chart", "chat", "tiktok", "chart"])
        self.desires.pop(act, None)
        self.say = why
        self.log = (self.log + [{"t": t, "what": why}])[-30:]

    # --- per tick -----------------------------------------------------------------------------------
    def update(self, t, dt_real, dt_sim, stage, rel, market_hot, pressure):
        self.t, self.stage = t, stage
        self.energy = round(min(1.0, max(0.0, 1.0 - pressure)), 3)
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
                if not self.path:
                    self.route = []
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
                if is_open("bakery", t):
                    self.bread += 2
                else:
                    self.log = (self.log + [{"t": t, "what": "the bakery closed before getting there: no bread"}])[-30:]
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

    def open_now(self):
        t = self.t if self.t is not None else time.time()
        return {k: is_open(k, t) for k in ("bakery", "park")}

    def snapshot(self):
        op = self.open_now()
        return {"x": round(self.x, 2), "z": round(self.z, 2), "heading": round(self.heading, 2),
                "walking": bool(self.path), "activity": self.activity, "doing": LABEL[self.activity],
                "pose": "walking" if self.path else ACTIVITIES[self.activity][1], "place": self.place,
                "hunger": round(self.hunger, 2), "boredom": round(self.boredom, 2), "bread": self.bread,
                "phone": self.phone_app if self.activity == "phone" and not self.path else None,
                "say": self.say, "log": [{"t": e["t"], "what": e["what"]} for e in self.log[-8:]],
                "route": list(self.route) if self.path else [], "progress": self.progress(),
                "energy": self.energy, "open": op,
                "npc": {"baker": {"present": op["bakery"],
                                  "pose": ("serving" if self.place in ("counter", "bakery_in") and not self.path
                                           else "standing") if op["bakery"] else "away"}}}

    def to_dict(self):
        return {"place": self.place, "activity": self.activity, "until": self.until, "hunger": self.hunger,
                "boredom": self.boredom, "bread": self.bread, "desires": self.desires, "log": self.log}
