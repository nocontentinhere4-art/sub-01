"""python final2.py clip left_m: final.py + the page's re-centring: hips/feet (and hands, props) shifted 6 cm back (the page's
chair rolls 6 cm further in, boy_mh.js SEAT_IN) and `left` m to his left (the page sat him off-centre: his thighs
reached the arm pads); type / mouse keep their hands' lateral place (keys, mouse)."""
import json, sys, fitprobe
from fitprobe import S
clip, left = sys.argv[1], float(sys.argv[2]); BACK = 0.06
f = json.load(open(f"{S}/data/fit_{clip}.json"))
fixed = clip in ("desk_type_ik", "desk_mouse_ik")
o = {"seatLift": f["seatLift"], "pitch": 15, "heelLift": 0.085, "forward": f["hipsForward"], "shift": [-BACK, left], "handShift": [0, 0] if fixed else [-BACK, left]}
if fixed: o.update(handLift=0, handForward=False)
# room-v5 desk_14_1280 (test_visual): the page pins his seated hips to its own height and lifts him off the floor when
# his feet would sink: the hips 1.5 cm higher over the feet raise him 1.5 cm on the seat (cushion); the left forearm,
# resting low over the desk's front edge in the mouse pose, swung up 4 cm at the elbow
if clip in ("desk_type_ik", "desk_mouse_ik"): o["seatLift"] = round(o["seatLift"] + 0.021, 4); o["elbowUp"] = {"L": 0.04}; o["feetForward"] = 0.025; o["leftFootForward"] = 0.02   # (calves clear of the seat front)
if clip == "room_read": o["book"] = json.load(open(f"{S}/data/book_read.json"))
if clip in ("room_phone", "room_phone_scroll", "room_eat"):
    import fcntl
    with open(f"{S}/work/site/props_v5.lock", "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        pv = json.load(open(f"{S}/work/site/props_v5.json")); g2 = json.load(open(f"{S}/work/site/props_g2.json"))
        e = json.loads(json.dumps(g2[clip]))
        for w in e.get("world", []): w["pos"] = [round(w["pos"][0] + left, 5), round(w["pos"][1] + f["seatLift"], 5), round(w["pos"][2] + f["hipsForward"] - BACK, 5)]
        pv[clip] = e; json.dump(pv, open(f"{S}/work/site/props_v5.json", "w"), indent=1)
json.dump(dict(o, report=f"{S}/mh_rep/{clip}.json"), open(f"{S}/data/o2_mh_{clip}.json", "w"))
print(fitprobe.run(["node", "mh_retarget.mjs", f"{S}/mh/{clip}.glb", f"{S}/v5f.glb", f"site/clips/mh_{clip}.glb", f"{S}/data/o2_mh_{clip}.json"]).strip()[-200:])
