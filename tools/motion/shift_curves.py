"""Measured weight shift (Pexels 5125886, MediaPipe) -> sideCurve/rollCurve options for retarget.mjs: python mkshift.py k out.json"""
import json, sys, numpy as np
import os
S = os.environ.get("MOTION_SCRATCH", ".")
k, out = float(sys.argv[1]), sys.argv[2]
o = np.load(f"{S}/capture/shift_series.npy"); t = o[:, 0]
sm = lambda x, n=7: np.convolve(np.pad(x, n // 2, mode="edge"), np.ones(n) / n, "valid")
lat = sm(o[:, 2])
T0, T1, AT = 14.3, 19.3, 0.8                      # reference window -> clip time AT
m = (t >= T0) & (t <= T1)
base = np.median(lat[(t >= 13.6) & (t <= 14.5)]); peak = np.median(lat[(t >= 15.6) & (t <= 18.4)])
n = np.clip((lat[m] - base) / (peak - base), 0, None); n[0] = 0; n[-1] = 0
# the ends eased to 0 over 0.3 s (the reference goes straight on into another action)
e = int(0.3 * 30); w = np.ones_like(n); w[:e] = np.linspace(0, 1, e); w[-e:] = np.linspace(1, 0, e); n = n * w
SIDE, ROLL = 0.062, np.radians(5.5)              # full-scale split: pelvis slide + torso lean = 0.33 shoulder widths
tc = (t[m] - T0 + AT)
P = json.load(open(f"{S}/idle_out/o_lean_sb.json")); P.pop("leanCurve"); P.pop("hands", None); P["lean"] = float(sys.argv[3]) if len(sys.argv) > 3 else 0.57; P["leanHead"] = 0.8
P["sideCurve"] = [[0, 0]] + [[round(a, 4), round(float(b) * SIDE * k, 5)] for a, b in zip(tc, n)]
P["rollCurve"] = [[0, 0]] + [[round(a, 4), round(float(b) * ROLL * k, 5)] for a, b in zip(tc, n)]
P["rollHead"] = 0.6
json.dump(P, open(out, "w")); json.dump({"t": tc.round(4).tolist(), "n": n.round(4).tolist(), "base": base, "peak": peak}, open(f"{S}/capture/shift_shape.json", "w"))
print("base %.3f peak %.3f amp %.3f sw, k %.2f -> side %.1f cm roll %.1f deg" % (base, peak, peak - base, k, SIDE * k * 100, 5.5 * k))
