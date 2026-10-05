"""python seatfit.py <clip.json> <opts.json> <cfg.json> <out.glb> [target]: fit the per-frame Hip height so the deepest
buttock skin point is `target` (m, default -0.015) into the seat top, by measuring in the scene and retargeting again
(twice); prints the gap statistics before and after."""
import json, subprocess, sys
clip, opts, cfg, out = sys.argv[1:5]; target = float(sys.argv[5]) if len(sys.argv) > 5 else -0.015
def run(): subprocess.run(["node", "retarget.mjs", clip, "site/char.glb", out, opts], check=True, capture_output=True)
def gaps(): return json.loads(subprocess.run(["node", "seatgap.mjs", cfg, "0.1"], check=True, capture_output=True, text=True).stdout)
def stats(g):
    v = [x[1]["glute"] for x in g if x[1] and "glute" in x[1]]
    return {"n": len(v), "min": round(min(v), 4), "max": round(max(v), 4), "mean": round(sum(v) / len(v), 4)} if v else {"n": 0}
o = json.load(open(opts)); o.pop("hipDY", None); json.dump(o, open(opts, "w")); run(); g0 = gaps(); print("before", stats(g0))
dy = [0.0] * len(g0); g = g0
for it in range(2):
    raw = [max(-0.08, min(0.08, target - x[1]["glute"])) if x[1] and "glute" in x[1] else None for x in g]
    # samples off the seat keep the nearest correction; then a 0.5 s smoothing so the hips don't bob
    last = 0.0; fill = []
    for r in raw: last = r if r is not None else last; fill.append(last)
    sm = [sum(fill[max(0, k - 2):k + 3]) / len(fill[max(0, k - 2):k + 3]) for k in range(len(fill))]
    dy = [round(a + b, 4) for a, b in zip(dy, sm)]
    o["hipDY"] = dy; json.dump(o, open(opts, "w")); run(); g = gaps(); print(f"pass {it + 1}", stats(g))
json.dump({"before": stats(g0), "after": stats(g), "gaps": g}, open(out.replace(".glb", "_seat.json"), "w"))
