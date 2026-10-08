"""A standing clip's upper body on a seated base (the Action & Reactions clips are all standing; at the desk he sits):
hips and legs from the base (looped to the clip's length), the spine's WORLD orientation from the standing clip with its
yaw taken out (so his torso stays as upright as the performer's, whatever the seated pelvis tilt), then the standing
clip's own local rotations from Spine1 up (spine, neck, head, shoulders, arms, fingers).
python3 -I layer_seated.py <base.json> <upper.json> <out.json> [arms=base]
(arms=base: the shoulders, arms and hands from the seated base too, for clips whose content is the head and torso)"""
import json, sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from s4skel import qmul, qnorm, qrot
qinv = lambda q: q * np.array([-1, -1, -1, 1.])
base, up = json.load(open(sys.argv[1])), json.load(open(sys.argv[2])); n = up['frames']
idx = np.arange(n) % base['frames']
out = dict(up); out['rot'] = {}; out['hips'] = np.array(base['hips'])[idx].tolist()
ARMS_BASE = len(sys.argv) > 4 and sys.argv[4] == 'arms=base'
LOW = ('Hips', 'LeftUpLeg', 'LeftLeg', 'LeftFoot', 'LeftToeBase', 'RightUpLeg', 'RightLeg', 'RightFoot', 'RightToeBase')
for k, v in up['rot'].items():
    b = k.split(':')[1]
    arm = any(x in b for x in ('Shoulder', 'Arm', 'Hand'))
    out['rot'][k] = (np.array(base['rot'][k])[idx] if b in LOW or (ARMS_BASE and arm) else np.array(v)).tolist()
def yaw_q(q):                                    # the heading part of a world rotation (facing +Z at rest)
    f = qrot(q, np.array([0, 0, 1.])); a = np.arctan2(f[:, 0], f[:, 2])
    return np.stack([np.zeros(n), np.sin(a / 2), np.zeros(n), np.cos(a / 2)], 1)
hb, hu = np.array(base['rot']['mixamorig:Hips'])[idx], np.array(up['rot']['mixamorig:Hips'])
su = np.array(up['rot']['mixamorig:Spine'])
spine_w = qmul(hu, su)                                            # the standing spine in the world
spine_w = qmul(qmul(yaw_q(hb), qinv(yaw_q(hu))), spine_w)         # turned to the seated base's heading
sp = qnorm(qmul(qinv(hb), spine_w))
for i in range(1, n):
    if np.dot(sp[i], sp[i - 1]) < 0: sp[i] = -sp[i]
out['rot']['mixamorig:Spine'] = sp.round(6).tolist()
out['source'] = up.get('source', []) + [('spine, neck and head' if ARMS_BASE else 'upper body') + ' on ' + base['set'] + "'s seated " + ('hips, legs and arms' if ARMS_BASE else 'hips and legs')]
json.dump(out, open(sys.argv[3], 'w')); print(os.path.basename(sys.argv[3]), n, 'frames')
