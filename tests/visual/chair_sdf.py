"""A signed distance grid of a chair mesh in the room chair node's frame, for tests/visual/contacts.py (--chair-sdf):
5 mm cells, millimetres as int8 (clipped to +-40 mm; past 40 mm from the surface: outside). The distance is to the
nearest surface sample; the sign is a vote of the 16 nearest samples (which side of each one the cell lies on, weighted by
nearness), which tolerates the holes and loose pieces a generated mesh has (no ray parity) and one sample's odd normal
at an edge.

    python -m tests.visual.chair_sdf <repaired.ply> out.npz   (the owner's chair: room_build/build_chair_owner.mjs's transform)"""
import sys
import numpy as np
from scipy.spatial import cKDTree

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "room_build"))
import chair_owner_repair as R                                    # noqa: E402

S, LIFT, BACK, STEP = 0.52 / 0.407, (0.0, -0.013), 0.05, 0.005


def main(src, out):
    C = R.load_ply(src); P = C[:, :, :3].copy(); N = C[:, :, 3:6].mean(1)
    P[..., 0] = -(P[..., 0] - LIFT[0]) * S; P[..., 1] *= S; P[..., 2] = -(P[..., 2] - LIFT[1]) * S + BACK
    N[:, 0] *= -1; N[:, 2] *= -1; N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-9)
    area = np.linalg.norm(np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]), axis=1) / 2
    rng = np.random.default_rng(1); n = 1500000; f = rng.choice(len(P), n, p=area / area.sum())
    u, v = rng.random(n), rng.random(n); m = u + v > 1; u[m], v[m] = 1 - u[m], 1 - v[m]
    Q = P[f, 0] + u[:, None] * (P[f, 1] - P[f, 0]) + v[:, None] * (P[f, 2] - P[f, 0]); NQ = N[f]
    lo = Q.min(0) - 0.03; hi = Q.max(0) + 0.03; dims = np.ceil((hi - lo) / STEP).astype(int) + 1
    gx, gy, gz = [lo[k] + np.arange(dims[k]) * STEP for k in range(3)]
    G = np.stack(np.meshgrid(gx, gy, gz, indexing="ij"), -1).reshape(-1, 3)
    d, i = cKDTree(Q).query(G, k=16, distance_upper_bound=0.04, workers=-1); ok = np.isfinite(d[:, 0])
    sd = np.full(len(G), 40.0); dk, ik = d[ok], i[ok]; fin = np.isfinite(dk); ik = np.where(fin, ik, 0)
    side = np.sign(((G[ok][:, None, :] - Q[ik]) * NQ[ik]).sum(-1)) * fin / np.maximum(dk, 1e-4)
    sd[ok] = np.where(side.sum(1) < 0, -1, 1) * dk[:, 0] * 1000
    sd = np.clip(np.round(sd), -40, 40).astype(np.int8).reshape(dims)
    np.savez_compressed(out, sd=sd, lo=lo, step=STEP)
    print(out, dims, "cells", "inside", int((sd < 0).sum()))


if __name__ == "__main__":
    main(*sys.argv[1:3])
