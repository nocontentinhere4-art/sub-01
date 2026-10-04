"""Project the aligned photoreal repaints (work/views/<view>_paint.png) into the skin atlas:  python project_paint.py
Per atlas texel (world position and normal from bl_views.py's bakes), per camera (cameras.json): the texel is projected
with the camera's pinhole model, kept only if it is the surface the camera sees there (its depth within 4 mm of the
rendered depth map), weighted by facing^2 and by the distance from the view's edge; the paint is sampled bilinearly.
Writes work/skin_projected.png (the blend of the views) and work/skin_projected_mask.png (0..1 confidence)."""
import os, json
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

HERE = os.path.dirname(os.path.abspath(__file__)); V = os.path.join(HERE, "work", "views")
meta = json.load(open(os.path.join(V, "cameras.json")))
P = np.load(os.path.join(V, "wpos.npy"))[::-1]; N = np.load(os.path.join(V, "wnrm.npy"))[::-1]; S = P.shape[0]     # Blender images are bottom-up; PIL arrays top-down
N = N / np.maximum(np.linalg.norm(N, axis=2, keepdims=True), 1e-6)
covered = np.abs(np.linalg.norm(np.load(os.path.join(V, "wnrm.npy")) * 2 - 0, axis=2)) > 0      # (all texels; the bake margin extends the islands)
acc = np.zeros((S, S, 3)); wsum = np.zeros((S, S))
for name, cam in meta.items():
    paint_f = os.path.join(V, name + "_paint.png")
    if not os.path.exists(paint_f): print("no repaint for", name); continue
    paint = np.asarray(Image.open(paint_f).convert("RGBA")).astype(np.float64) / 255; R = paint.shape[0]
    depth = np.load(os.path.join(V, "depth_" + name + ".npy")).astype(np.float64)      # top-down, metres along the camera axis
    M = np.array(cam["matrix_world"]); Minv = np.linalg.inv(M); f = cam["lens"] / cam["sensor"]      # focal length in sensor widths
    # world -> camera: Blender cameras look down -Z, +Y up
    hom = np.concatenate([P, np.ones((S, S, 1))], 2) @ Minv.T; x, y, z = hom[:, :, 0], hom[:, :, 1], hom[:, :, 2]
    front = z < -0.05
    u = 0.5 + f * x / np.where(front, -z, 1); v = 0.5 - f * y / np.where(front, -z, 1)                  # 0..1 across the square frame, v down
    inside = front & (u > 0.002) & (u < 0.998) & (v > 0.002) & (v < 0.998)
    px = np.clip(u * R, 0, R - 1); py = np.clip(v * R, 0, R - 1)
    dmap = ndi.map_coordinates(depth, [py, px], order=1, mode="nearest")
    visible = inside & (np.abs(-z - dmap) < 0.004)                                                       # the surface the camera sees here
    cam_pos = M[:3, 3]; view = cam_pos[None, None, :] - P; view /= np.maximum(np.linalg.norm(view, axis=2, keepdims=True), 1e-6)
    facing = np.clip((N * view).sum(2), 0, 1)
    col = np.stack([ndi.map_coordinates(paint[:, :, k], [py, px], order=1, mode="nearest") for k in range(3)], 2)
    alpha = ndi.map_coordinates(paint[:, :, 3], [py, px], order=1, mode="nearest")
    w = visible * facing ** 2 * alpha
    acc += col * w[:, :, None]; wsum += w
    print("%s: visible texels %d, weight %.0f" % (name, int(visible.sum()), w.sum()))
res = acc / np.maximum(wsum, 1e-9)[:, :, None]
mask = np.clip(wsum / 0.6, 0, 1)                                 # one well-facing view already counts as full confidence
Image.fromarray(np.clip(res * 255 + 0.5, 0, 255).astype(np.uint8)).save(os.path.join(HERE, "work", "skin_projected.png"))
Image.fromarray(np.clip(mask * 255 + 0.5, 0, 255).astype(np.uint8)).save(os.path.join(HERE, "work", "skin_projected_mask.png"))
print("wrote work/skin_projected.png: %.1f%% of the atlas painted" % (100 * (mask > 0.5).mean()))
