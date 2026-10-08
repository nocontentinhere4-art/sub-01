"""The fits (kimodo/mx_fit.py's sleeve swing, fit_rest.py, fit_hands.py) work frame by frame, and their elbow solutions
can jump between frames (G14: forearms moving 5-15 cm in one frame, against room_seated_idle's 1.4 cm). The retargeted
motion itself is smooth, so only the fits' correction is smoothed: per arm bone, d(t) = q_final(t) * q_source(t)^-1,
Gaussian over time (sigma `SIG` frames; wrapped round for loops, which also closes the loop seam), then
q(t) = d_smooth(t) * q_source(t). python3 -I smooth_fit.py <source.json> <fitted.json> [loop]  (rewrites fitted.json)"""
import json, sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from s4skel import qmul, qnorm
qinv = lambda q: q * np.array([-1, -1, -1, 1.])
SIG = float(os.environ.get('SMOOTH_SIG', 6))
src, fit = json.load(open(sys.argv[1])), json.load(open(sys.argv[2])); loop = len(sys.argv) > 3 and sys.argv[3] == 'loop'
n = fit['frames']; assert src['frames'] == n, (src['frames'], n)
k = int(3 * SIG); g = np.exp(-0.5 * (np.arange(-k, k + 1) / SIG) ** 2); g /= g.sum()
def smooth(x):
    pad = np.pad(x, ((k, k), (0, 0)), mode='wrap' if loop else 'edge')
    return np.stack([np.convolve(pad[:, j], g, 'valid') for j in range(x.shape[1])], 1)
FING = [f'Hand{f}{k}' for f in ('Thumb', 'Index', 'Middle', 'Ring', 'Pinky') for k in (1, 2, 3)] if os.environ.get('SMOOTH_FINGERS') == '1' else []
for side in ('Left', 'Right'):
    for b in ['Shoulder', 'Arm', 'ForeArm', 'Hand'] + FING:
        nm = f'mixamorig:{side}{b}'
        qs, qf = np.array(src['rot'][nm]), np.array(fit['rot'][nm])
        d = qnorm(qmul(qf, qinv(qs)))
        d[d[:, 3] < 0] *= -1                                          # one hemisphere (the corrections are small)
        q = qnorm(qmul(qnorm(smooth(d)), qs))
        for i in range(1, n):
            if np.dot(q[i], q[i - 1]) < 0: q[i] = -q[i]
        fit['rot'][nm] = q.round(6).tolist()
fit['arms_smoothed'] = dict(sigma_frames=SIG, loop=loop)
json.dump(fit, open(sys.argv[2], 'w')); print(os.path.basename(sys.argv[2]), 'arms smoothed', SIG, 'loop' if loop else '')
