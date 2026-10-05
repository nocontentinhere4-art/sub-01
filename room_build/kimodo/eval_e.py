import sys, glob, json, numpy as np
names = json.load(open('/workspace/soma77.json'))['joints']; I = {n: i for i, n in enumerate(names)}
d = sys.argv[1]; spec = json.load(open(f'/workspace/out/{d}/done.json'))['spec']
for f in sorted(glob.glob(f'/workspace/out/{d}/*.npz')):
    z = np.load(f); p = z['posed_joints']; c = z['foot_contacts']; err = []
    for e in spec.get('ee', []):
        for j, tg in e.get('targets', {}).items():
            for fr, t in zip(e['frames'], tg): err.append(np.linalg.norm(p[fr, I[j]] - np.array(t)))
        for fr, r in zip(e['frames'], e.get('root') or []): err.append(abs(p[fr, 0, 1] - r[1]))
        if e.get('place'):
            for fr in e['frames']: err.append(np.linalg.norm(p[fr, 0] - np.array(e['place']['root'])))
    for cs in spec.get('constraints', []):
        if cs['type'] == 'root2d':
            for fr, xy in zip(cs['frame_indices'], cs['smooth_root_2d']): err.append(np.linalg.norm(p[fr, 0, [0, 2]] - np.array(xy)))
    sk = 0
    for j, ci in [('LeftFoot', 0), ('RightFoot', 2)]:
        v = np.linalg.norm(np.diff(p[:, I[j], [0, 2]], axis=0), axis=1) * 30; on = c[1:, ci] > 0.5; sk += (v * on).sum() / max(1, on.sum())
    jerk = np.abs(np.diff(p, 3, axis=0)).mean() * 30 ** 3
    print(f"{f.split('/')[-1]} cons err mean {np.mean(err):.3f} max {np.max(err):.3f} | skate {sk:.3f} jerk {jerk:.1f} | hipsY " + ' '.join(f"{p[min(len(p)-1,int(t*30)),0,1]:.2f}" for t in range(0, int(len(p)/30)+1)))
