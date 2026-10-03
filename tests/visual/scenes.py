"""Scenes, times, sizes and close-ups of the visual QA suite (issue #98, G8).

A scene is the `life` part of a websocket tick (life.py's snapshot) plus how the page should be driven into it: a
scene to start from (`before`), the simulated seconds to run after the switch (`settle_s`) and what the page's
`pose()` must then report (`at`, `clip`), which is the "did he get there" check. Hours are the Tokyo clock the page
previews with `?debug&hour=H`; the fake server also writes the matching `sleep.clock`.
"""

VITALS = {"hr_bpm": 66, "resp_per_min": 14, "glucose_mg_dl": 92}
READING = {"title": "Inokashira Park", "url": "https://en.wikipedia.org/wiki/Inokashira_Park", "host": "en.wikipedia.org",
           "kind": "wiki", "why": "visual QA fixture",
           "extract": "Inokashira Park straddles Musashino and Mitaka in western Tokyo. The park's pond feeds the Kanda River; "
                      "rowing boats, a small zoo and the Ghibli Museum sit at its edges, and in spring the cherry trees around "
                      "the water draw crowds from Kichijōji station a few minutes' walk away."}


def life(activity, place, doing, **extra):
    d = {"x": 0, "z": 0, "heading": 0, "walking": False, "activity": activity, "doing": doing, "pose": "standing",
         "place": place, "hunger": 0.3, "vitals": VITALS, "boredom": 0.2, "bread": 0, "phone": None, "geo": None,
         "say": "", "music": None, "food": 0, "food_items": [], "eating": None, "order": None, "courier": None, "log": []}
    d.update(extra)
    return d


# name -> (life, sleep stage, before-scene or None, settle seconds, expected pose() at, expected clip substring)
SCENES = {
    "desk":     (life("research", "desk", "reading at the computer", reading=READING), "AWAKE", None, 1.0, "desk", "Chair_Sit"),
    # (the page eats on top of the seated clip: arm IK, chopsticks, the dish; the eat clip itself is not played)
    "eating":   (life("eat", "table", "eating ramen from the delivery", eating="ramen", food=1, hunger=0.7), "AWAKE", None, 3.6, "desk", "Chair_Sit"),
    "sleeping": (life("sleep", "bed", "sleeping"), "NREM", None, 1.0, "bedlie", "Sleep"),
    # the phone in bed: from lying asleep the page keeps him lying and brings the phone up (phone_lie)
    "phone":    (life("phone", "bed", "in bed scrolling the phone", phone="shorts", boredom=0.6), "AWAKE", "sleeping", 2.5, "bedlie", "phone_lie"),
    # standing just inside the door (an activity the page does not know, at the door place: it stands him there)
    "door":     (life("home", "door_in", "just in at the door"), "AWAKE", None, 1.0, "door", "stand"),
    # walking: from the door to the desk; the harness stops mid-walk (see harness.walk_until). As the server sends it:
    # `walking` true and no `path` (life.py's snapshot has no path field), so the page treats him as already at the desk
    "walking":  (life("research", "desk", "walking to the desk", reading=READING, walking=True), "AWAKE", "door", None, None, "Walk"),
    "window":   (life("window", "window", "looking out of the window"), "AWAKE", None, 1.5, "sill", "stand"),
}
# the hour each scene is shot at in the core set, and the full matrix
NATURAL_HOUR = {"desk": 14, "eating": 19, "sleeping": 23, "phone": 23, "door": 8, "walking": 8, "window": 19}
HOURS = (8, 14, 19, 23)
SIZES = {"1280": (1280, 800, False), "390": (390, 844, True)}

# close-ups: name -> (scene to take it in, hour, JS camera recipe name in page_checks.js)
CLOSEUPS = {
    "face":  ("walking", 14, "face"),       # mid-room, lit from the window, nothing in front of him
    "hands": ("desk", 14, "hands"),         # over his shoulder: hands on the keyboard and the armrests
    "grip":  ("phone", 14, "grip"),         # the phone hand (hand_phone.glb) in bed by day
    "feet":  ("door", 14, "feet"),
    "socks": ("window", 14, "socks"),       # the laundry hanger's socks and towel
    "desk":  ("desk", 19, "desk"),          # the desk at dusk, lamp on
    "bed":   ("sleeping", 14, "bed"),       # him on the bed by day (the pose and the duvet's drape)
    "duvet": ("window", 14, "duvet"),       # the empty bed: duvet, pillow, sheet
    "night": ("sleeping", 23, "bed"),       # the same bed at night: what the dark room shows
}
CORE_SHOTS = [(s, NATURAL_HOUR[s], "1280") for s in SCENES] + [("desk", 14, "390"), ("sleeping", 23, "390")]
FULL_SHOTS = [(s, h, z) for s in SCENES for h in HOURS for z in SIZES]


def clock(hour):
    h = int(hour) % 24
    return f"{h:02d}:{int(round((hour - int(hour)) * 60)) % 60:02d}"


def tick(name, hour):
    lf, stage, *_ = SCENES[name]
    return {"type": "tick", "life": lf, "sleep": {"stage": stage, "clock": clock(hour)},
            "neuro": {"DA": 1.0, "5HT": 1.0, "NE": 0.9, "ACh": 1.1}, "events": [], "trades": [], "groups": {}}
