"""python fitall.py clip: one deterministic seat/backrest fit per seated clip.
Pass 1 (pitch 15 deg, heel lift 8.5 cm on the seated clips' standard pose): measure buttock gap g and backrest depth b; then
  hips forward along the seat by (b - 0.007) (the chair rolled back under him; his world position and the desk contacts stay),
  seat lift corrected by (-0.0055 - g); pass 2 = verification at 0.1 s, written to data/fit_<clip>.json."""
import json, sys
from fitprobe import measure, S
clip = sys.argv[1]
book = json.load(open(f"{S}/data/book_read.json")) if clip == "room_read" else None
cf = f"{S}/data/cfg_mh_{clip}.json"; c = json.load(open(cf))
if "chair0" not in c: c["chair0"] = c["chair"][0][1:3]; c["lift0"] = c["propsLift"]; json.dump(c, open(cf, "w"))
DESK = clip in ("desk_type_ik", "desk_mouse_ik")
lift0, pitch, heel = c["lift0"], 15, 0.085
def m(lift, dz, dt, full=False):
    import fitprobe, json as j
    o = {"seatLift": lift, "pitch": pitch, "heelLift": heel}
    if DESK: o["handLift"] = 0
    if book: o["book"] = book
    return fitprobe.measure2(clip, o, lift, dz, dt, full)
r1 = m(lift0, 0.0, 0.5)
dz = max(0.0, r1["backMax"] - 0.007) if r1["backMax"] > 0.010 else 0.0
lift = lift0 + (-0.0055 - r1["glute"][2])
r2 = m(round(lift, 4), round(dz, 4), 0.1, True)
res = {"clip": clip, "pitch": pitch, "heelLift": heel, "seatLift": round(lift, 4), "hipsForward": round(dz, 4), "pass1": r1, **{k: v for k, v in r2.items() if k != "rows"}}
json.dump({**res, "rows": r2["rows"]}, open(f"{S}/data/fit_{clip}.json", "w"))
print(json.dumps(res), flush=True)
