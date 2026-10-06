"""python final.py clip: the fitted clip baked for the page: hips forward (and lift) inside the clip, the chair where the page
puts it (no roll-back), lifted/forward world props written to site/props_v5.json; verified every 0.1 s."""
import json, sys, fitprobe
from fitprobe import S
clip = sys.argv[1]; f = json.load(open(f"{S}/data/fit_{clip}.json"))
fixed = clip in ("desk_type_ik", "desk_mouse_ik")   # hands stay on keyboard / mouse
o = {"seatLift": f["seatLift"], "pitch": 15, "heelLift": 0.085, "forward": f["hipsForward"]}
if fixed: o.update(handLift=0, handForward=False)
if clip == "room_read": o["book"] = json.load(open(f"{S}/data/book_read.json"))
if clip in ("room_phone", "room_phone_scroll", "room_eat"):
    import fcntl
    with open(f"{S}/work/site/props_v5.lock", "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        pv = json.load(open(f"{S}/work/site/props_v5.json")); g2 = json.load(open(f"{S}/work/site/props_g2.json"))
        e = json.loads(json.dumps(g2[clip]))
        for w in e.get("world", []): w["pos"] = [round(w["pos"][0], 5), round(w["pos"][1] + f["seatLift"], 5), round(w["pos"][2] + f["hipsForward"], 5)]
        pv[clip] = e; json.dump(pv, open(f"{S}/work/site/props_v5.json", "w"), indent=1)
cf = f"{S}/data/cfg_mh_{clip}.json"; c = json.load(open(cf)); c["propsFile"] = "props_v5.json"; json.dump(c, open(cf, "w"))
r = fitprobe.measure2(clip, o, 0.0, 0.0, 0.1, True)     # propsLift 0 (baked), chair at the page's place
f2 = dict(f, final=o, **{k: v for k, v in r.items()}); json.dump(f2, open(f"{S}/data/final_{clip}.json", "w"))
print(json.dumps({"clip": clip, **{k: v for k, v in r.items() if k != "rows"}}), flush=True)
