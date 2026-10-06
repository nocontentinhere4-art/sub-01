import json, subprocess, sys
S = "/tmp/claude-0/-home-user-sub-01/781de1f5-2090-5ea7-a75f-f2fe43b467c8/scratchpad"
ZL = {"desk_type_ik": -0.006, "desk_mouse_ik": -0.006, "desk_watch": -0.05, "room_read": -0.043, "room_phone": -0.10, "room_phone_scroll": -0.10, "room_eat": -0.123}
HOME = (-1.13, -0.735)
def run(c): return subprocess.run(c, check=True, capture_output=True, text=True, cwd=S + "/work").stdout
for clip in sys.argv[1:]:
    cf = f"{S}/data/cfg_mh_{clip}.json"; c = json.load(open(cf)); c["propsLift"] = 0; c["propsFile"] = "props_v5.json"
    dur = json.load(open(f"{S}/mh_rep/{clip}.json"))["frames"] / 30; t = round(dur * 0.5, 2)
    c["chair"] = [[0, 0, 0, 0, 0]]; json.dump(c, open(f"{S}/data/ps_{clip}.json", "w"))
    hip = json.loads(run(["node", "probe.mjs", f"{S}/data/ps_{clip}.json", f"bones({t},['Hip'])"]))["Hip"]
    c["chair"] = [[0, 0, round(hip[0] - HOME[0], 4), round(hip[2] - ZL[clip] - HOME[1], 4), 0]]; json.dump(c, open(f"{S}/data/ps_{clip}.json", "w"))
    cam = [{"pos": [hip[0] + 1.25, 0.95, hip[2] + 0.05], "at": [hip[0], 0.75, hip[2] - 0.05], "fov": 50}]
    run(["node", "stills.mjs", f"{S}/data/ps_{clip}.json", f"{S}/stills/{clip}_side.png", str(t), json.dumps(cam), "640", "480"])
    print(clip, t, hip, flush=True)
