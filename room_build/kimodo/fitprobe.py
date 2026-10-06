"""python fitprobe.py clip pitch heelLift seatLift chairdz [dt]: retarget + seat/back numbers (summary)"""
import json, os, subprocess, sys
S = os.environ.get("MHV5_WORK", "..")
def run(cmd): return subprocess.run(cmd, check=True, capture_output=True, text=True, cwd=S + "/work").stdout
def measure(clip, pitch, heel, lift, dz, dt=0.5, book=None, full=False):
    o = {"seatLift": lift, "pitch": pitch, "heelLift": heel, "report": f"{S}/mh_rep/{clip}.json"}
    if book: o["book"] = book
    json.dump(o, open(f"{S}/data/o_mh_{clip}.json", "w"))
    run(["node", "mh_retarget.mjs", f"{S}/mh/{clip}.glb", f"{S}/v5f.glb", f"site/clips/mh_{clip}.glb", f"{S}/data/o_mh_{clip}.json"])
    cf = f"{S}/data/cfg_mh_{clip}.json"; c = json.load(open(cf)); c["propsLift"] = lift
    c.setdefault("chair0", c["chair"][0][1:3]); c["chair"][0][1] = round(c["chair0"][0] + dz / 0.4, 4); json.dump(c, open(cf, "w"))
    r = json.loads(run(["node", "probe.mjs", cf, f"[seatGap({dt}), backGap({dt})]"]))
    sg, bg = r
    gl = [x[1]["glute"] for x in sg if x[1] and "glute" in x[1]]; th = [x[1]["thigh"] for x in sg if x[1] and "thigh" in x[1]]
    out = {"glute": [round(min(gl), 4), round(max(gl), 4), round(sum(gl) / len(gl), 4)] if gl else None, "thighMin": round(min(th), 4) if th else None,
           "mid": round(min([x[1]["mid"] for x in sg if x[1] and "mid" in x[1]] or [9]), 4), "backMax": max(x[1] for x in bg), "backN": max(x[2] for x in bg), "n": len(sg)}
    if full: out["rows"] = {"seat": sg, "back": bg}
    return out
def measure2(clip, o, lift, dz, dt, full=False):
    o = dict(o, report=f"{S}/mh_rep/{clip}.json"); json.dump(o, open(f"{S}/data/o_mh_{clip}.json", "w"))
    run(["node", "mh_retarget.mjs", f"{S}/mh/{clip}.glb", f"{S}/v5f.glb", f"site/clips/mh_{clip}.glb", f"{S}/data/o_mh_{clip}.json"])
    cf = f"{S}/data/cfg_mh_{clip}.json"; c = json.load(open(cf)); c["propsLift"] = lift
    c.setdefault("chair0", c["chair"][0][1:3]); c["chair"][0][1] = round(c["chair0"][0] + dz / 0.4, 4); json.dump(c, open(cf, "w"))
    sg, bg = json.loads(run(["node", "probe.mjs", cf, f"[seatGap({dt}), backGap({dt})]"]))
    gl = [x[1]["glute"] for x in sg if x[1] and "glute" in x[1]]; th = [x[1]["thigh"] for x in sg if x[1] and "thigh" in x[1]]
    out = {"glute": [round(min(gl), 4), round(max(gl), 4), round(sum(gl) / len(gl), 4)] if gl else [0, 0, -0.0055], "seatedFrac": round(len(gl) / len(sg), 2), "thighMin": round(min(th), 4) if th else None,
           "backMax": max(x[1] for x in bg), "backN": max(x[2] for x in bg), "n": len(sg)}
    if full: out["rows"] = {"seat": sg, "back": bg}
    return out
if __name__ == "__main__":
    a = sys.argv[1:]; book = json.load(open(a[6])) if len(a) > 6 else None
    print(json.dumps(measure(a[0], float(a[1]), float(a[2]), float(a[3]), float(a[4]), float(a[5]) if len(a) > 5 else 0.5, book)))
