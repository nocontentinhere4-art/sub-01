"""Tests for life.py: needs, routes, route + progress while walking, opening hours, requests, snapshot schema.

    /home/user/sub-01/.venv/bin/python -m pytest tests/test_life.py -q
"""
import random
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

import life
from life import ACTIVITIES, LABEL, PLACES, WALK_SPEED, Life, route
from sleep import ROME


def at(h, m=0, day=1):
    return datetime(2026, 10, day, h, m, tzinfo=ROME).timestamp()


def make(seed=1, **state):
    return Life(state or None, rng=random.Random(seed))


def tick(lf, t, stage="AWAKE", n=1, dt=0.05, pressure=0.2, rel=None):
    for _ in range(n):
        lf.update(t, dt, dt * 60, stage, rel or {}, 0.0, pressure)


# ---- world / routes ---------------------------------------------------------------------------------------
def test_every_place_reaches_every_other():
    names = list(PLACES)
    for a in names:
        for b in names:
            p = route(a, b)
            assert p[0] == a and p[-1] == b
            assert all(any(x == q or y == q for x, y in life.EDGES for q in (y,)) for _ in p)   # only known places
            for u, v in zip(p, p[1:]):
                assert (u, v) in life.EDGES or (v, u) in life.EDGES


def test_route_to_bakery_goes_through_the_street():
    p = route("bed", "counter")
    assert p == ["bed", "door_in", "door_out", "street_home", "street_bakery", "bakery_door", "bakery_in", "counter"]


def test_activity_places_exist():
    assert all(ACTIVITIES[a][0] in PLACES for a in ACTIVITIES) and set(LABEL) == set(ACTIVITIES)


# ---- needs --------------------------------------------------------------------------------------------------
def test_hunger_rises_with_simulated_time():
    lf = make(hunger=0.0, activity="window")
    lf.until = 1e18
    for i in range(50):
        lf.update(at(12), 0.05, 3600 / 50, "AWAKE", {}, 0.0, 0.1)
    assert 0.15 < lf.hunger < 0.25                       # one sim hour ~ 1/5


def test_boredom_falls_on_the_phone_and_rises_at_the_window():
    lf = make(boredom=0.5, activity="phone", place="bed")
    lf.until = 1e18
    lf.update(at(12), 0.05, 1800, "AWAKE", {}, 0.0, 0.1)
    assert lf.boredom < 0.5
    lf = make(boredom=0.5, activity="window", place="window")
    lf.until = 1e18
    lf.update(at(12), 0.05, 1800, "AWAKE", {}, 0.0, 0.1)
    assert lf.boredom > 0.5


def test_energy_is_one_minus_sleep_pressure_and_clamped():
    lf = make()
    tick(lf, at(12), pressure=0.3)
    assert lf.snapshot()["energy"] == pytest.approx(0.7)
    tick(lf, at(12), pressure=1.6)
    assert lf.snapshot()["energy"] == 0.0
    tick(lf, at(12), pressure=-0.2)
    assert lf.snapshot()["energy"] == 1.0


def test_brain_stage_puts_it_to_bed():
    lf = make(activity="window", place="window")
    lf.until = 1e18
    tick(lf, at(23, 30), stage="NREM", n=1)
    assert lf.activity == "sleep"


# ---- walking: route + progress --------------------------------------------------------------------------------
def test_not_walking_has_empty_route_and_zero_progress():
    lf = make(place="window", activity="window")
    s = lf.snapshot()
    assert s["route"] == [] and s["progress"] == 0.0 and not s["walking"]


def test_route_and_progress_advance_while_walking_to_the_bakery():
    lf = make(activity="window", place="bed", hunger=0.9)
    lf.until = 1e18
    ok, why = lf.request("buy_bread", at(9), "hungry")
    assert ok, why
    s = lf.snapshot()
    assert s["walking"] and s["route"][0] == "bed" and s["route"][-1] == "counter"
    assert s["route"] == route("bed", "counter")
    assert s["progress"] == 0.0
    total = life.path_length(s["route"])
    last, seen = 0.0, []
    t = at(9)
    for i in range(3000):
        tick(lf, t)
        snap = lf.snapshot()
        if not snap["walking"]:
            break
        assert snap["progress"] >= last - 1e-9           # never goes backwards
        last = snap["progress"]
        seen.append(last)
        assert snap["route"] == s["route"]                # the route of one walk does not change
    assert not lf.path and lf.place == "counter"
    assert 0.9 < seen[-1] <= 1.0 and seen[len(seen) // 2] == pytest.approx(0.5, abs=0.05)
    end = lf.snapshot()
    assert end["route"] == [] and end["progress"] == 0.0
    steps = len(seen) + 1                                # timing unchanged: WALK_SPEED, a step per waypoint rounded up
    lo = total / (WALK_SPEED * 0.05)
    assert lo <= steps <= lo + len(s["route"])


def test_request_while_walking_continues_along_the_edge_without_jumping():
    lf = make(activity="window", place="bed")
    lf.until = 1e18
    lf.request("buy_bread", at(9), "hungry")
    tick(lf, at(9), n=60)                                # a few metres into the walk
    x, z = lf.x, lf.z
    ok, _ = lf.request("park", at(9, 5), "bored")
    assert ok and (lf.x, lf.z) == (x, z)
    tick(lf, at(9, 5))
    assert abs(lf.x - x) + abs(lf.z - z) < 0.2
    snap = lf.snapshot()
    assert snap["route"][-1] == "bench"
    tick(lf, at(9, 5), n=5000)
    assert lf.place == "bench" and not lf.path


def test_turning_back_to_the_start_of_the_edge():
    lf = make(activity="window", place="bed")
    lf.until = 1e18
    lf.request("buy_bread", at(9), "hungry")
    tick(lf, at(9), n=8)                                 # just left the bed
    ok, _ = lf.request("window", at(9), "x")
    assert ok
    tick(lf, at(9), n=400)
    assert lf.place == "window" and not lf.path


def test_restored_mid_activity_elsewhere_walks_there_with_a_route():
    lf = make(activity="buy_bread", place="bed")
    s = lf.snapshot()
    assert s["walking"] and s["route"][-1] == "counter"


# ---- requests: opening hours, sleep, constraints ---------------------------------------------------------------
def test_bakery_closed_at_21_with_a_reason_and_open_at_08():
    lf = make(activity="window", place="window")
    lf.until = 1e18
    ok, why = lf.request("buy_bread", at(21), "hungry")
    assert not ok and "closed" in why and "07:00" in why and "20:00" in why
    assert lf.activity == "window"                       # nothing started
    ok, why = lf.request("buy_bread", at(8), "hungry")
    assert ok and lf.activity == "buy_bread"


def test_bakery_hours_edges():
    lf = make()
    assert not lf.request("buy_bread", at(6, 59), "")[0]
    assert lf.request("buy_bread", at(7, 0), "")[0]
    lf = make()
    assert lf.request("buy_bread", at(19, 45), "")[0]
    lf = make()
    ok, why = lf.request("buy_bread", at(19, 59), "")
    assert not ok and "about to close" in why            # no point setting off a minute before closing
    lf = make()
    assert not lf.request("buy_bread", at(20, 0), "")[0]


def test_park_is_daylight_only():
    lf = make()
    assert not lf.request("park", at(21), "")[0]
    assert "dark" in lf.request("park", at(21), "")[1]
    assert lf.request("park", at(18, 0), "")[0]
    lf = make()
    ok, why = lf.request("park", at(18, 40), "")               # sunset ~18:48: no margin left
    assert not ok and "dark" in why
    lf = make()
    assert not lf.request("park", at(6, 30), "")[0]
    lf = make()
    assert lf.request("park", at(10), "")[0] and lf.activity == "park"


def test_asleep_declines_everything():
    lf = make(activity="sleep", place="bed")
    tick(lf, at(3), stage="NREM")
    for act in ("buy_bread", "park", "phone", "chart", "window", "eat"):
        ok, why = lf.request(act, at(3), "x")
        assert not ok and "asleep" in why
    tick(lf, at(3), stage="REM")
    assert not lf.request("phone", at(3), "x")[0]


def test_has_bread_eats_instead_of_buying():
    lf = make(activity="window", place="window", bread=2, hunger=0.7)
    lf.until = 1e18
    ok, why = lf.request("buy_bread", at(10), "hungry")
    assert not ok and "bread" in why and "eat" in why
    assert lf.activity == "eat"                          # ...and it does eat


def test_has_bread_and_not_hungry_just_declines():
    lf = make(activity="window", place="window", bread=2, hunger=0.05)
    lf.until = 1e18
    ok, why = lf.request("buy_bread", at(10), "x")
    assert not ok and lf.activity == "window" and "not hungry" in why


def test_very_tired_declines_the_park_only():
    lf = make(activity="window", place="window")
    lf.until = 1e18
    tick(lf, at(15), pressure=0.9)                       # energy 0.1
    ok, why = lf.request("park", at(15), "bored")
    assert not ok and "tired" in why
    assert lf.request("phone", at(15), "bored")[0]


def test_already_doing_it_and_unknown_and_sleep_requests():
    lf = make(activity="window", place="window")
    assert lf.request("window", at(10), "")[1] == "already doing that" and not lf.request("window", at(10), "")[0]
    assert not lf.request("teleport", at(10), "")[0]
    assert not lf.request("sleep", at(10), "")[0]


def test_eat_needs_bread_and_hunger():
    lf = make(activity="window", place="window", bread=0, hunger=0.9)
    assert not lf.request("eat", at(10), "")[0]
    lf = make(activity="window", place="window", bread=1, hunger=0.9)
    assert lf.request("eat", at(10), "")[0] and lf.activity == "eat"


def test_decline_reasons_map_to_mind_templates():
    """The reasons are read by mind.DECLINE: closed / dark / has bread / full / tired / asleep / busy."""
    import re
    import mind
    def key(why):
        return next((k for pat, k in mind.DECLINE if re.search(pat, why.lower())), "no_other")
    lf = make(activity="window", place="window")
    lf.until = 1e18
    assert key(lf.request("buy_bread", at(21), "")[1]) == "no_closed"
    assert key(lf.request("park", at(21), "")[1]) == "no_dark"
    assert key(lf.request("window", at(10), "")[1]) == "no_busy"
    lf2 = make(activity="window", place="window", bread=1, hunger=0.05)
    assert key(lf2.request("buy_bread", at(10), "")[1]) == "no_has_bread"
    assert key(lf2.request("eat", at(10), "")[1]) == "no_full"
    tick(lf, at(15), pressure=0.95)
    assert key(lf.request("park", at(15), "")[1]) == "no_tired"
    tick(lf, at(3), stage="NREM")
    assert key(lf.request("phone", at(3), "")[1]) == "no_asleep"


# ---- snapshot schema + compatibility --------------------------------------------------------------------------
OLD_KEYS = {"x", "z", "heading", "walking", "activity", "doing", "pose", "place", "hunger", "boredom", "bread",
            "phone", "say", "log"}


def test_snapshot_schema():
    lf = make()
    tick(lf, at(12))
    s = lf.snapshot()
    assert OLD_KEYS <= set(s)                            # backwards compatible
    assert {"route", "progress", "energy", "open", "npc"} <= set(s)
    assert isinstance(s["route"], list) and 0.0 <= s["progress"] <= 1.0 and 0.0 <= s["energy"] <= 1.0
    assert set(s["open"]) == {"bakery", "park"} and all(isinstance(v, bool) for v in s["open"].values())
    assert set(s["npc"]["baker"]) == {"present", "pose"}
    import json
    json.dumps(s)


def test_snapshot_open_follows_the_clock():
    lf = make()
    tick(lf, at(12))
    assert lf.snapshot()["open"] == {"bakery": True, "park": True}
    assert lf.snapshot()["npc"]["baker"]["present"] is True
    tick(lf, at(19, 15))
    assert lf.snapshot()["open"] == {"bakery": True, "park": False}     # 1 Oct: sunset about 18:50
    tick(lf, at(20, 15))
    assert lf.snapshot()["open"] == {"bakery": False, "park": False}
    assert lf.snapshot()["npc"]["baker"]["present"] is False
    tick(lf, at(22))
    assert lf.snapshot()["open"] == {"bakery": False, "park": False}


def test_saved_state_round_trips_and_old_state_loads():
    lf = make(activity="park", place="bench", hunger=0.6, bread=1)
    lf2 = Life(lf.to_dict(), rng=random.Random(2))
    assert (lf2.activity, lf2.place, lf2.bread) == ("park", "bench", 1)
    old = {"place": "bed", "activity": "window", "until": 0.0, "hunger": 0.4, "boredom": 0.3, "bread": 0,
           "desires": {}, "log": []}                      # the state written before route/progress existed
    assert Life(old).snapshot()["route"] != None


def test_desire_from_chat_still_works():
    lf = make(activity="window", place="window")
    lf.hear("vado a comprare il pane", at(10))
    assert lf.desire("buy_bread", at(10)) > 0.5


# ---- review fixes: daylight, closed on arrival, repeated requests, turn-back route, baker pose ---------------
def test_park_daylight_is_seasonal():
    from datetime import datetime as D
    summer, winter = D(2026, 6, 21, 12, tzinfo=ROME).timestamp(), D(2026, 12, 21, 12, tzinfo=ROME).timestamp()
    assert 20.0 < life.sun_hours(summer)[1] < 21.5 and 16.0 < life.sun_hours(winter)[1] < 17.3
    assert life.is_open("park", D(2026, 6, 21, 20, 15, tzinfo=ROME).timestamp())
    assert not life.is_open("park", D(2026, 12, 21, 17, 30, tzinfo=ROME).timestamp())


def test_request_for_the_activity_already_under_way_leaves_the_plan_alone():
    lf = make(activity="window", place="window", hunger=0.9)
    lf.until = 1e18
    assert lf.request("buy_bread", at(10), "hungry")[0]
    until, log, route_, path = lf.until, list(lf.log), list(lf.route), list(lf.path)
    tick(lf, at(10), n=20)
    ok, why = lf.request("buy_bread", at(10, 1), "still hungry")
    assert ok and why == "already on the way"
    assert lf.until == until and lf.log == log and lf.route == route_


def test_buy_bread_request_while_eating_does_not_restart_eating():
    lf = make(activity="eat", place="table", bread=1, hunger=0.8)
    lf.until = 1e18
    until = lf.until
    ok, why = lf.request("buy_bread", at(10), "hungry")
    assert not ok and "eating" in why and lf.until == until and len(lf.log) == 0


def test_arriving_after_closing_buys_no_bread():
    lf = make(activity="buy_bread", place="counter", hunger=0.8)
    lf.until = 0.0
    tick(lf, at(20, 5))
    assert lf.bread == 0


def test_baker_is_only_serving_when_present():
    lf = make(activity="buy_bread", place="counter")
    tick(lf, at(20, 30))
    b = lf.snapshot()["npc"]["baker"]
    assert b == {"present": False, "pose": "away"}
    tick(lf, at(12))
    assert lf.snapshot()["npc"]["baker"]["pose"] in ("serving", "standing")


def test_turn_back_route_reports_the_half_edge_walk():
    lf = make(activity="window", place="bed")
    lf.until = 1e18
    lf.path = ["street_bakery"]                       # walking street_home -> street_bakery, a third of the way
    lf.place = "street_home"
    lf.x, lf.z = 4.0 + 17.0 / 3, 10.0
    lf._walk_to("street_park")                        # the park is behind: turn back
    assert lf.route[:3] == ["street_bakery", "street_home", "street_park"]
    s = lf.snapshot()
    assert s["walking"] and 0.0 < s["progress"] < 0.5


def test_short_activities_are_finished_before_another_request_takes_over():
    lf = make()
    lf.start("eat", at(12), "eats")
    lf.path, lf.route = [], []
    ok, why = lf.request("phone", at(12, 2), "")
    assert not ok and why.startswith("busy")
    assert lf.request("phone", at(13), "")[0]                   # after it is over
