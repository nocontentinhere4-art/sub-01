"""One inhabited home, stepped by the live brain server, never by viewers.

The home maps existing life activities onto collision-free 3D waypoints. Rooms,
Pong, notes and the phone persist with the same server state as the character.
Physiology and consciousness are not inferred from this simulation.
"""

import heapq
import math
import random

# xyz = walking-eye positions in the rendered house, metres.
NODES = {
    "desk": (2, 1.65, -0.75),
    "aisle": (1.3, 1.65, -0.75),
    "back": (1.3, 1.65, -2.2),
    "kitchen_gate": (-0.5, 1.65, -2.2),
    "kitchen": (-1.8, 1.65, -1.8),
    "sofa": (-0.45, 1.65, 1.85),
    "front": (1.3, 1.65, 3.2),
    "stair_approach": (0.3, 1.65, 3.2),
    "stair_bottom": (0.3, 1.65, 2.55),
    "stair_top": (0.3, 4.65, -1.7),
    "landing": (0.3, 4.65, -2.1),
    "loft": (-0.5, 4.65, -2.1),
    "bed": (-1.2, 4.65, -2.9),
    "bath_aisle": (-0.5, 4.65, -0.2),
    "bath_door": (-0.5, 4.65, 1.35),
    "bathroom": (-1.5, 4.65, 1.35),
    "balcony_gate": (-0.5, 4.65, 3.2),
    "balcony_door": (-2.2, 4.65, 3.2),
    "balcony": (-2.2, 4.65, 4.4),
    "door": (2, 1.65, 3.2),
    "outside": (2, 1.65, 5.25),
}
EDGES = [
    ("desk", "aisle"),
    ("aisle", "back"),
    ("back", "kitchen_gate"),
    ("kitchen_gate", "kitchen"),
    ("front", "sofa"),
    ("aisle", "front"),
    ("front", "stair_approach"),
    ("stair_approach", "stair_bottom"),
    ("stair_bottom", "stair_top"),
    ("stair_top", "landing"),
    ("landing", "loft"),
    ("loft", "bed"),
    ("bed", "bath_aisle"),
    ("loft", "bath_aisle"),
    ("bath_aisle", "bath_door"),
    ("bath_door", "bathroom"),
    ("bath_door", "balcony_gate"),
    ("balcony_gate", "balcony_door"),
    ("balcony_door", "balcony"),
    ("front", "door"),
    ("door", "outside"),
]
DESTINATIONS = {
    "sleep": "bed",
    "phone": "bed",
    "listen_music": "bed",
    "order_food": "bed",
    "eat": "kitchen",
    "use_bathroom": "bathroom",
    "play_console": "sofa",
    "watch_tv": "sofa",
    "window": "balcony",
    "park": "outside",
    "buy_bread": "outside",
    "buy_konbini": "outside",
    "get_delivery": "door",
    "research": "desk",
    "chart": "desk",
    "chat": "desk",
    "watch_video": "desk",
    "play_chess": "desk",
    "use_computer": "desk",
}
LOOKS = {
    "desk": (2, 1.16, -3.3),
    "sofa": (-3.85, 1.65, 0.1),
    "kitchen": (-2.2, 1.2, -3.5),
    "bed": (0, 4.1, 0),
    "bathroom": (-3.5, 4, 1.1),
    "balcony": (10, 6, 24),
    "outside": (10, 6, 24),
    "door": (2, 1.4, 4.2),
}


def route(a, b):
    graph = {k: [] for k in NODES}
    for x, y in EDGES:
        cost = math.dist(NODES[x], NODES[y])
        graph[x].append((y, cost))
        graph[y].append((x, cost))
    queue = [(0, a, [])]
    seen = set()
    while queue:
        cost, node, path = heapq.heappop(queue)
        if node == b:
            return path + [node]
        if node in seen:
            continue
        seen.add(node)
        for nxt, d in graph[node]:
            heapq.heappush(queue, (cost + d, nxt, path + [node]))
    raise ValueError("unreachable home destination")


class Pong:
    """The left paddle uses the brain's live motor/attention signals and a learned response gain.

    This is a sensor/motor controller, not proof that the brain understands Pong.
    The right paddle can be challenged by viewers. Without input it is a simple opponent.
    """

    def __init__(self, state=None):
        s = state if isinstance(state, dict) else {}
        self.left = self.right = 0.5
        self.x = self.y = 0.5
        self.vx = 0.28
        self.vy = 0.17
        self.score = list(s.get("score", [0, 0]))
        self.gain = float(s.get("gain", 0.55))
        self.rally = 0
        self.clock = 0
        self.user_until = 0
        self.user_direction = 0
        self.opponent_target = .5
        self.opponent_next = 0
        self.matches = int(s.get("matches", 0))
        self.reward = 0
        self.last_result = ""
        self.active = False

    def input(self, direction):
        self.user_direction = max(-1, min(1, float(direction)))
        self.user_until = self.clock + 0.35

    def update(self, dt, rel, active):
        self.active = active
        if not active:
            return
        self.clock += dt
        self.reward = 0
        attention = max(0.2, min(2, rel.get("attention", 1)))
        motor = max(0.2, min(2, rel.get("somatomotor", rel.get("motor", 1))))
        target = self.y + self.vy * 0.16 * attention
        error = target - self.left
        self.left = max(
            0.105,
            min(
                0.895,
                self.left
                + max(
                    -0.7 * dt,
                    min(0.7 * dt, error * self.gain * motor * attention * dt * 5),
                ),
            ),
        )
        if self.clock >= self.opponent_next:
            # A finite reaction interval makes the opponent beatable, rather than a perfect tracker.
            self.opponent_target = self.y
            self.opponent_next = self.clock + .38
        direction = (
            self.user_direction
            if self.clock < self.user_until
            else max(-1, min(1, (self.opponent_target - self.right) * 7))
        )
        self.right = max(0.105, min(0.895, self.right + direction * 0.42 * dt))
        self.x += self.vx * dt
        self.y += self.vy * dt
        if self.y < 0.025:
            self.y = 0.025
            self.vy = abs(self.vy)
        if self.y > 0.975:
            self.y = 0.975
            self.vy = -abs(self.vy)
        for px, paddle, sign in ((0.045, self.left, 1), (0.955, self.right, -1)):
            if (
                self.vx * sign < 0
                and (self.x <= px if sign == 1 else self.x >= px)
                and abs(self.y - paddle) < 0.115
            ):
                self.x = px
                self.vx = sign * min(0.7, abs(self.vx) * 1.035)
                self.vy = (self.y - paddle) * 3.4
                if abs(self.vy) < 0.22:
                    self.vy = 0.24 * (1 if self.rally % 2 else -1)
                self.rally += 1
                if sign == 1:
                    self.reward = 0.02
                    self.gain = min(1.4, self.gain + 0.002)
        if self.x < 0 or self.x > 1:
            won = self.x > 1
            self.score[0 if won else 1] += 1
            self.matches += 1
            self.reward = 0.12 if won else -0.08
            self.last_result = "won a point" if won else "missed the ball"
            self.gain = min(1.4, max(0.2, self.gain + (0.008 if won else 0.02)))
            self.x = self.y = 0.5
            self.vx = 0.28 if won else -0.28
            self.vy = 0.16 * (1 if self.matches % 2 else -1)
            self.rally = 0

    def view(self):
        return {
            "ball": [round(self.x, 4), round(self.y, 4)],
            "paddles": [round(self.left, 4), round(self.right, 4)],
            "score": self.score,
            "rally": self.rally,
            "active": self.active,
            "gain": round(self.gain, 3),
            "matches": self.matches,
            "last_result": self.last_result,
        }


class HomeWorld:
    def __init__(self, state=None):
        s = state if isinstance(state, dict) else {}
        self.settings = {"lamp": True, "curtain": False, **s.get("settings", {})}
        self.node = s.get("node", "desk") if s.get("node") in NODES else "desk"
        self.position = list(NODES[self.node])
        self.target = self.node
        self.path = []
        self.activity = "research"
        self.look = list(LOOKS.get(self.node, LOOKS["desk"]))
        self.speed = 0
        self.seated = max(0, min(1, float(s.get("seated", 0))))
        self.time = float(s.get("time", 0))
        self.sequence = int(s.get("sequence", 0))
        if (
            s.get("path")
            and all(n in NODES for n in s["path"])
            and s.get("target") in NODES
            and len(s.get("position", [])) == 3
            and all(
                isinstance(v, (int, float)) and math.isfinite(v) for v in s["position"]
            )
        ):
            self.position = list(s["position"])
            self.path = list(s["path"])
            self.target = s["target"]
            self.activity = s.get("activity", "research")
        self.bladder = max(0, min(1, float(s.get("bladder", 0.1))))
        self.last_bathroom = s.get("last_bathroom", 0)
        self.pong = Pong(s.get("pong"))
        self.notes = list(s.get("notes", []))[-100:]
        self.memories = list(s.get("memories", []))[-100:]
        self.last_activity = ""
        self.last_game_matches = self.pong.matches
        self.memories = self.memories[-100:]
        self.phone = {
            "app": s.get("phone_app", "home"),
            "battery": int(s.get("battery", 100)),
        }
        self.phone_elapsed = 0

    def desired(self, activity):
        return DESTINATIONS.get(activity, "desk")

    def update(self, dt, sim_dt, life, rel):
        self.time += dt
        activity = life.get("activity", "research")
        target = self.desired(activity)
        self.bladder = min(1, self.bladder + max(0, sim_dt) / 18000)
        if target != self.target:
            # Finish current edge before replanning; no teleports through furniture.
            origin = self.path[0] if self.path else self.node
            self.path = ([origin] if self.path else []) + route(origin, target)[1:]
            self.target = target
            self.sequence += 1
        self.activity = activity
        if self.path and self.seated > 0:
            # Finish getting up at a human pace before the first walking edge.
            self.seated = max(0, self.seated - dt * 0.55)
            self.speed = 0
        elif self.path:
            self.speed = min(1.25, self.speed + dt * 1.15)
            n = self.path[0]
            end = NODES[n]
            distance = math.dist(self.position, end)
            step = self.speed * dt
            if distance <= step:
                self.position = list(end)
                self.node = n
                self.path.pop(0)
            else:
                self.position = [
                    p + (q - p) * step / distance for p, q in zip(self.position, end)
                ]
            self.look = [end[0], self.position[1], end[2]]
        else:
            self.speed = max(0, self.speed - dt * 1.8)
            self.look = list(LOOKS.get(self.node, LOOKS["desk"]))
            self.seated = (
                min(1, self.seated + dt * 0.65)
                if self.node in ("desk", "sofa", "bed")
                else 0
            )
            if self.node == "bathroom":
                self.bladder = max(0, self.bladder - dt * 0.06)
                self.last_bathroom = self.time
            if activity != self.last_activity:
                self.memories.append(
                    {
                        "at": round(self.time, 1),
                        "activity": activity,
                        "place": self.node,
                    }
                )
                self.memories = self.memories[-100:]
                self.last_activity = activity
        self.pong.update(
            min(dt, 0.05), rel, activity == "play_console" and not self.path
        )
        if self.pong.matches != self.last_game_matches:
            self.memories.append(
                {
                    "at": round(self.time, 1),
                    "activity": "play_console",
                    "what": self.pong.last_result,
                    "score": list(self.pong.score),
                }
            )
            self.last_game_matches = self.pong.matches
            self.memories = self.memories[-100:]
        self.phone_elapsed += dt
        if self.phone_elapsed >= 60:
            self.phone_elapsed = 0
            self.phone["battery"] = max(
                1, min(100, self.phone["battery"] + (-1 if activity == "phone" else 2))
            )
        screen = life.get("screen") or {}
        self.phone["app"] = (
            screen.get("kind", "browser") if activity == "phone" else self.phone["app"]
        )

    def add_note(self, text):
        text = str(text).strip()[:2000]
        if not text:
            return False
        self.notes.append(
            {"id": self.sequence, "at": round(self.time, 1), "text": text}
        )
        self.sequence += 1
        self.notes = self.notes[-100:]
        return True

    def view(self, compact=False):
        p = list(self.position)
        if self.node == "desk":
            p[1] -= 0.42 * self.seated
            p[2] -= 1.15 * self.seated
        if self.node == "sofa":
            p[1] -= 0.35 * self.seated
            p[0] -= 1.55 * self.seated
        if self.node == "bed":
            p[1] -= 0.6 * self.seated
            p[0] -= 1.2 * self.seated
            p[2] += 0.3 * self.seated
        privacy = (
            self.position[1] > 3
            and -3.78 < self.position[0] < -0.85
            and 0.5 < self.position[2] < 2.7
        )
        return {
            "version": 1,
            "position": [round(v, 4) for v in p],
            "look": self.look,
            "entry_position": [round(v, 4) for v in self.position],
            "walking": bool(self.path) and self.seated == 0,
            "speed": round(self.speed, 3),
            "activity": self.activity,
            "place": self.node,
            "destination": self.target,
            "privacy": privacy,
            "seated": round(self.seated, 3),
            "sequence": self.sequence,
            "door_open": self.position[1] < 3
            and math.hypot(self.position[0] - 2, self.position[2] - 3.9) < 1.8,
            "settings": dict(self.settings),
            "phone": dict(self.phone),
            "pong": self.pong.view(),
            "notes": self.notes[-10:] if not compact else [],
            "memories": self.memories[-20:] if not compact else [],
        }

    def to_dict(self):
        return {
            "node": self.node,
            "position": self.position,
            "path": self.path,
            "target": self.target,
            "activity": self.activity,
            "seated": self.seated,
            "time": self.time,
            "sequence": self.sequence,
            "bladder": self.bladder,
            "last_bathroom": self.last_bathroom,
            "pong": {
                "score": self.pong.score,
                "gain": self.pong.gain,
                "matches": self.pong.matches,
            },
            "settings": dict(self.settings),
            "notes": self.notes,
            "memories": self.memories[-100:],
            "phone_app": self.phone["app"],
            "battery": self.phone["battery"],
        }
