"""A stand-in bakery street as a 3D Gaussian Splatting .ply, in the same layout as Lyra 1's output, so the walk page
(web/walk_scene.html) can be built and tested before the real scene exists.

    python walk_scenes/placeholder.py /tmp/bakery_placeholder.ply
    npx @playcanvas/splat-transform --spz-version 3 -w /tmp/bakery_placeholder.ply web/walk/bakery_placeholder.spz

Lyra 1 writes its Gaussians in the first camera's OpenCV frame (x right, y down, z forward, camera at the origin about
1.6 m above the street), standard 3DGS fields: position, f_dc (SH degree 0), opacity (logit), log scale, rotation
quaternion. This file uses the same frame and fields, so web/walk/<scene>.json applies one transform to both. It is
deliberately crude (flat-coloured boxes): it only checks scale, placement and the boy's path, not looks.
"""
import sys

import numpy as np

SH0 = 0.28209479177387814
rng = np.random.default_rng(1)
parts = []
DENSITY = 0.4                                                  # of the counts below: ~120k splats, ~1 MB as .spz


def box(x0, x1, y0, y1, z0, z1, color, n, jitter=0.06, size=0.08):
    """n splats on the surface of an axis-aligned box (OpenCV frame: y down), colour with a little noise."""
    n = int(n * DENSITY)
    dims = np.array([x1 - x0, y1 - y0, z1 - z0])
    areas = np.array([dims[1] * dims[2], dims[1] * dims[2], dims[0] * dims[2], dims[0] * dims[2],
                      dims[0] * dims[1], dims[0] * dims[1]])
    face = rng.choice(6, n, p=areas / areas.sum())
    p = rng.random((n, 3)) * dims + [x0, y0, z0]
    axis = face // 2
    side = face % 2
    lo, hi = np.array([x0, y0, z0]), np.array([x1, y1, z1])
    p[np.arange(n), axis] = np.where(side == 0, lo[axis], hi[axis])
    c = np.clip(np.array(color) + rng.normal(0, jitter, (n, 3)), 0, 1)
    parts.append((p, c, np.full(n, size)))


def plane_y(x0, x1, z0, z1, y, color, n, jitter=0.05, size=0.09):
    n = int(n * DENSITY)
    p = np.column_stack([rng.uniform(x0, x1, n), np.full(n, y), rng.uniform(z0, z1, n)])
    c = np.clip(np.array(color) + rng.normal(0, jitter, (n, 3)), 0, 1)
    parts.append((p, c, np.full(n, size)))


GROUND = 1.6                                                   # camera height: the street is 1.6 m below it (+y)
plane_y(-3.0, 3.0, 0.5, 26, GROUND, (0.33, 0.33, 0.35), 90000)              # asphalt
plane_y(-2.9, -2.75, 0.5, 26, GROUND - 0.005, (0.85, 0.85, 0.82), 3000, 0.02, 0.03)   # white edge lines
plane_y(2.75, 2.9, 0.5, 26, GROUND - 0.005, (0.85, 0.85, 0.82), 3000, 0.02, 0.03)
box(-9, -3.2, -4.5, GROUND, 2, 11, (0.78, 0.74, 0.66), 30000)               # houses, left
box(-9, -3.2, -3.5, GROUND, 12, 24, (0.62, 0.66, 0.70), 30000)
box(3.2, 9, -4.0, GROUND, 2, 9, (0.70, 0.70, 0.72), 25000)                  # right, before the shop
box(3.2, 9, -3.2, GROUND, 9, 15, (0.55, 0.38, 0.24), 30000)                 # the bakery: wooden front
box(3.15, 3.25, -0.6, 1.1, 10.2, 13.8, (0.92, 0.82, 0.55), 12000, 0.04, 0.04)   # lit display window
box(2.2, 3.2, -1.05, -0.95, 9.4, 14.6, (0.18, 0.28, 0.42), 9000, 0.03, 0.05)    # awning
box(3.2, 9, -4.2, GROUND, 15.5, 24, (0.80, 0.78, 0.74), 25000)              # right, after the shop
for z in (6, 18):                                                            # utility poles
    box(-3.0, -2.75, -6.5, GROUND, z, z + 0.25, (0.55, 0.55, 0.52), 2500, 0.03, 0.04)
plane_y(-40, 40, 0, 40, -18, (0.62, 0.76, 0.92), 30000, 0.03, 0.9)            # sky dome stand-in

p = np.concatenate([a for a, _, _ in parts]).astype(np.float32)
c = np.concatenate([b for _, b, _ in parts]).astype(np.float32)
s = np.concatenate([d for _, _, d in parts]).astype(np.float32)
n = len(p)
f_dc = (c - 0.5) / SH0
opacity = np.full(n, 4.0, np.float32)                                         # logit: ~0.98
scale = np.log(np.repeat(s[:, None], 3, 1))
rot = np.tile(np.array([1, 0, 0, 0], np.float32), (n, 1))
fields = ["x", "y", "z", "nx", "ny", "nz", "f_dc_0", "f_dc_1", "f_dc_2", "opacity",
          "scale_0", "scale_1", "scale_2", "rot_0", "rot_1", "rot_2", "rot_3"]
data = np.column_stack([p, np.zeros((n, 3), np.float32), f_dc, opacity, scale, rot]).astype("<f4")
out = sys.argv[1] if len(sys.argv) > 1 else "bakery_placeholder.ply"
with open(out, "wb") as f:
    f.write(("ply\nformat binary_little_endian 1.0\nelement vertex %d\n" % n).encode())
    f.write("".join(f"property float {k}\n" for k in fields).encode())
    f.write(b"end_header\n")
    f.write(data.tobytes())
print(out, n, "splats")
