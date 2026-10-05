"""Kimodo NPZ -> compact JSON for the retarget (global rotations as quaternions xyzw, joint positions, foot contacts)."""
import json, sys
import numpy as np
from scipy.spatial.transform import Rotation as Rot

def conv(src, dst, fps=30):
    d = np.load(src)
    G = d["global_rot_mats"]; T, J = G.shape[:2]
    q = Rot.from_matrix(G.reshape(-1, 3, 3)).as_quat().reshape(T, J, 4)
    out = {"fps": fps, "T": int(T), "quat": np.round(q, 5).tolist(), "pos": np.round(d["posed_joints"], 4).tolist(),
           "contacts": d["foot_contacts"].astype(float).tolist() if "foot_contacts" in d else None}
    json.dump(out, open(dst, "w"))

if __name__ == "__main__":
    conv(sys.argv[1], sys.argv[2], float(sys.argv[3]) if len(sys.argv) > 3 else 30)
