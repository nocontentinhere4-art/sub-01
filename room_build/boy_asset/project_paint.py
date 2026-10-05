"""Project aligned repainted views back into an atlas:
    python project_paint.py            the head views (work/views, cameras from bl_views.py) -> work/skin_projected.png
    python project_paint.py --body     the body views (work/body, cameras from bl_body_views.py) -> work/cloth_projected.png
                                       (the cloth atlas) and work/skin_body_projected.png (the skin atlas: hands, neck)
Per atlas texel (world position and normal from the Blender bakes), per camera: the texel is projected with the camera's
pinhole model, kept only if it is the surface the camera sees there (its depth within a tolerance of the rendered depth
map), weighted by facing^2 and the paint's alpha; the paint is sampled bilinearly. Writes the blend and a 0..1 confidence
mask (a single well-facing view already counts as full confidence)."""
import os, sys, json
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

HERE = os.path.dirname(os.path.abspath(__file__))
BODY = "--body" in sys.argv
V = os.path.join(HERE, "work", "body" if BODY else "views")
meta = json.load(open(os.path.join(V, "cameras.json")))
CAMS = {k: v for k, v in meta.items() if isinstance(v, dict) and "matrix_world" in v}

def project(P, N, out_name, depth_tol, min_facing=0.0):
    P = P[::-1]; N = N[::-1]; S = P.shape[0]                               # Blender images are bottom-up; PIL arrays top-down
    N = N / np.maximum(np.linalg.norm(N, axis=2, keepdims=True), 1e-6)
    acc = np.zeros((S, S, 3)); wsum = np.zeros((S, S))
    for name, cam in CAMS.items():
        paint_f = os.path.join(V, name + "_paint.png")
        if not os.path.exists(paint_f): print("no repaint for", name); continue
        paint = np.asarray(Image.open(paint_f).convert("RGBA")).astype(np.float64) / 255; R = paint.shape[0]
        depth = np.load(os.path.join(V, "depth_" + name + ".npy")).astype(np.float64)
        M = np.array(cam["matrix_world"]); Minv = np.linalg.inv(M); f = cam["lens"] / cam["sensor"]
        hom = np.concatenate([P, np.ones((S, S, 1))], 2) @ Minv.T; x, y, z = hom[:, :, 0], hom[:, :, 1], hom[:, :, 2]
        front = z < -0.05
        u = 0.5 + f * x / np.where(front, -z, 1); v = 0.5 - f * y / np.where(front, -z, 1)
        inside = front & (u > 0.002) & (u < 0.998) & (v > 0.002) & (v < 0.998)
        px = np.clip(u * R, 0, R - 1); py = np.clip(v * R, 0, R - 1)
        dmap = ndi.map_coordinates(depth, [py, px], order=1, mode="nearest")
        visible = inside & (np.abs(-z - dmap) < depth_tol)
        cam_pos = M[:3, 3]; view = cam_pos[None, None, :] - P; view /= np.maximum(np.linalg.norm(view, axis=2, keepdims=True), 1e-6)
        facing = np.clip((N * view).sum(2), 0, 1); facing = np.where(facing > min_facing, facing, 0)
        col = np.stack([ndi.map_coordinates(paint[:, :, k], [py, px], order=1, mode="nearest") for k in range(3)], 2)
        alpha = ndi.map_coordinates(paint[:, :, 3], [py, px], order=1, mode="nearest")
        # the paint's silhouette edge is the least reliable part (the repaint's outline is never exactly the mesh's): fade it
        edge = ndi.map_coordinates(ndi.distance_transform_edt(paint[:, :, 3] > 0.5), [py, px], order=1, mode="nearest")
        w = visible * facing ** 2 * alpha * np.clip(edge / 12.0, 0, 1)
        acc += col * w[:, :, None]; wsum += w
        print("%s -> %s: visible texels %d, weight %.0f" % (name, out_name, int(visible.sum()), w.sum()))
    res = acc / np.maximum(wsum, 1e-9)[:, :, None]; mask = np.clip(wsum / 0.6, 0, 1)
    Image.fromarray(np.clip(res * 255 + 0.5, 0, 255).astype(np.uint8)).save(os.path.join(HERE, "work", out_name + ".png"))
    Image.fromarray(np.clip(mask * 255 + 0.5, 0, 255).astype(np.uint8)).save(os.path.join(HERE, "work", out_name + "_mask.png"))
    print("wrote work/%s.png: %.1f%% of the atlas painted" % (out_name, 100 * (mask > 0.5).mean()))

if BODY:
    project(np.load(os.path.join(V, "wpos_cloth.npy")), np.load(os.path.join(V, "wnrm_cloth.npy")), "cloth_projected", depth_tol=0.008, min_facing=0.25)
    project(np.load(os.path.join(V, "wpos_skin.npy")), np.load(os.path.join(V, "wnrm_skin.npy")), "skin_body_projected", depth_tol=0.008, min_facing=0.25)
else:
    project(np.load(os.path.join(V, "wpos.npy")), np.load(os.path.join(V, "wnrm.npy")), "skin_projected", depth_tol=0.004)
