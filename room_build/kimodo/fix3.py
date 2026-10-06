import json, sys, fitprobe
from fitprobe import S
clip, ddz, dl = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]); f = json.load(open(f"{S}/data/fit_{clip}.json"))
dz, lift = f["hipsForward"] + ddz, f["seatLift"] + dl
o = {"seatLift": round(lift, 4), "pitch": 15, "heelLift": 0.085}
if clip.startswith("desk_") and clip != "desk_watch": o["handLift"] = 0
r = fitprobe.measure2(clip, o, round(lift, 4), round(dz, 4), 0.1, True)
f.update(r); f["hipsForward"] = round(dz, 4); f["seatLift"] = round(lift, 4); json.dump(f, open(f"{S}/data/fit_{clip}.json", "w"))
print(json.dumps({"clip": clip, **{k: v for k, v in r.items() if k != "rows"}}), flush=True)
