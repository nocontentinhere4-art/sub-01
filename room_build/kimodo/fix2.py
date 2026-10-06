import json, sys, fitprobe
from fitprobe import S
clip = sys.argv[1]; f = json.load(open(f"{S}/data/fit_{clip}.json"))
dz = f["hipsForward"] + f["backMax"] - 0.007
o = {"seatLift": f["seatLift"], "pitch": 15, "heelLift": 0.085}
r = fitprobe.measure2(clip, o, f["seatLift"], round(dz, 4), 0.1, True)
f.update({k: v for k, v in r.items()}); f["hipsForward"] = round(dz, 4); json.dump(f, open(f"{S}/data/fit_{clip}.json", "w"))
print(json.dumps({"clip": clip, "hipsForward": round(dz, 4), **{k: v for k, v in r.items() if k != "rows"}}), flush=True)
