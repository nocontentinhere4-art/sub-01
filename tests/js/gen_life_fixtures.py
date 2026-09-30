"""Regenerates tests/js/fixtures/life_walks.json: real life.py snapshots at 20 Hz for the re-plan cases travel.js must survive.
Run: python tests/js/gen_life_fixtures.py"""
import json, os, random, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import life as L

HZ = 20


def compact(snaps):
    """Route tables + rows [walking, routeIdx, progress, place, activity, pose] keep the file small."""
    routes, rows = [], []
    for s in snaps:
        if s["route"] not in routes:
            routes.append(s["route"])
        rows.append([s["walking"], routes.index(s["route"]), s["progress"], s["place"], s["activity"], s["pose"]])
    return {"routes": routes, "rows": rows}


def run(start_place, start_act, script, seconds):
    lf = L.Life({"place": start_place, "activity": start_act, "until": 1e12}, rng=random.Random(7))
    out, t0 = [], 12 * 3600.0
    for k in range(int(seconds * HZ)):
        now = k / HZ
        for when, act in script:
            if abs(now - when) < 1e-9:
                lf.request(act, t0 + now, "fixture")
        lf.update(t0 + now, 1 / HZ, 1 / HZ, "AWAKE", {}, False, 0.0)
        s = lf.snapshot()
        out.append({k2: s[k2] for k2 in ("walking", "route", "progress", "place", "activity", "pose")})
    return compact(out)


cases = {
    "buy_bread": run("bed", "window", [(1.0, "buy_bread")], 60),
    "turn_back_to_park": run("bed", "window", [(1.0, "buy_bread"), (13.0, "park")], 70),
    "redirect_third": run("window", "window", [(1.0, "buy_bread"), (4.0, "chart")], 60),
    "intra_home": run("bed", "window", [(1.0, "phone"), (8.0, "chart"), (16.0, "window"), (24.0, "chart")], 40),
}
with open(os.path.join(os.path.dirname(__file__), "fixtures", "life_walks.json"), "w") as f:
    json.dump(cases, f, separators=(",", ":"))
for k, v in cases.items():
    print(k, len(v["rows"]), [r for r in v["routes"] if r])
