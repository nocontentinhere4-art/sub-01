import sys, glob, json, numpy as np
names = json.load(open('/workspace/soma77.json'))['joints']; I = {n: i for i, n in enumerate(names)}
for d in sys.argv[1:]:
    for f in sorted(glob.glob(f'/workspace/out/{d}/*.npz')):
        z = np.load(f); p = z['posed_joints']; c = z['foot_contacts']
        hy = p[:, 0, 1]; h = p[:, 0, [0, 2]]
        sk = 0
        for j, ci in [('LeftFoot', 0), ('RightFoot', 2)]:
            v = np.linalg.norm(np.diff(p[:, I[j], [0, 2]], axis=0), axis=1) * 30; on = c[1:, ci] > 0.5; sk += (v * on).sum() / max(1, on.sum())
        jerk = np.abs(np.diff(p, 3, axis=0)).mean() * 30 ** 3
        s = ' '.join(f"{t:.0f}s:y{hy[min(len(p)-1,int(t*30))]:.2f}" for t in np.arange(0, len(p) / 30, 1.5))
        print(f"{d}/{f.split('/')[-1]} T={len(p)} skate {sk:.3f} jerk {jerk:.1f} end xz {h[-1].round(2)} heading-ish | {s} | LH {p[-1, I['LeftHand']].round(2)} RH {p[-1, I['RightHand']].round(2)}")
