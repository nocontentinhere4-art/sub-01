"""Join two Kimodo takes into one clip: the second is turned (yaw) and moved so its first frame's hips heading and ground
position match the first take's last frame, then the seam is crossfaded over K frames (rotations slerped per joint, joint
positions lerped). Writes the retarget's JSON (as npz2json.py)."""
import json, sys
import numpy as np
from scipy.spatial.transform import Rotation as Rot, Slerp
args = sys.argv[1:]; K = int(args.pop()) if args[-1].isdigit() else 8; out = args.pop(); takes = [dict(np.load(f)) for f in args]
names = json.load(open(__file__.rsplit('/', 1)[0] + '/soma77.json'))['joints']; I = {n: i for i, n in enumerate(names)}
def heading(p): d = p[I['RightLeg']] - p[I['LeftLeg']]; return np.arctan2(d[2], -d[0])
def join2(a, b):
  Pa, Ga, Pb, Gb = a['posed_joints'], a['global_rot_mats'], b['posed_joints'].copy(), b['global_rot_mats'].copy()
  yaw = heading(Pa[-1]) - heading(Pb[0]); Ry = Rot.from_euler('y', yaw).as_matrix()
  r0 = Pb[0, 0].copy(); Pb = (Pb - r0) @ Ry.T + r0; Gb = np.einsum('ij,tkjl->tkil', Ry, Gb)
  d = Pa[-1, 0] - Pb[0, 0]; d[1] = 0; Pb += d
  T = len(Pa) + len(Pb) - K; P = np.zeros((T, 77, 3)); G = np.zeros((T, 77, 3, 3))
  P[:len(Pa) - K], G[:len(Pa) - K] = Pa[:-K], Ga[:-K]; P[len(Pa):], G[len(Pa):] = Pb[K:], Gb[K:]
  for k in range(K):
      w = (k + 1) / (K + 1); w = w * w * (3 - 2 * w); t = len(Pa) - K + k
      P[t] = Pa[-K + k] * (1 - w) + Pb[k] * w
      for j in range(77):
          s = Slerp([0, 1], Rot.from_matrix([Ga[-K + k, j], Gb[k, j]])); G[t, j] = s([w]).as_matrix()[0]
  C = np.concatenate([a['foot_contacts'][:-K], b['foot_contacts']]).astype(float)
  print('joined', len(Pa), '+', len(Pb), '->', T, 'yaw', round(float(yaw), 3), 'shift', d.round(3))
  return {'posed_joints': P, 'global_rot_mats': G, 'foot_contacts': C}
m = takes[0]
for t in takes[1:]: m = join2(m, t)
P, G, C = m['posed_joints'], m['global_rot_mats'], m['foot_contacts']; T = len(P)
q = Rot.from_matrix(G.reshape(-1, 3, 3)).as_quat().reshape(T, 77, 4)
json.dump({"fps": 30, "T": int(T), "quat": np.round(q, 5).tolist(), "pos": np.round(P, 4).tolist(), "contacts": C.tolist()}, open(out, "w"))

