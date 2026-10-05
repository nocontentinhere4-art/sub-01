"""Align a repainted body view to its render by dense optical flow:  python align_body.py <view>
Reads work/body/<view>.png (unlit render, transparent background) and work/body/<view>_gen.png (the repaint), computes
Farneback flow from the render's luminance to the repaint's at 768 px, smooths it, warps the repaint onto the render and
writes work/body/<view>_paint.png with the render's alpha. The image model keeps the silhouette within a few percent;
the flow takes out the residual so the seams of the hoodie, the stripe and the cuffs land on the mesh's."""
import os, sys
import numpy as np
import cv2
from PIL import Image
from scipy import ndimage as ndi

HERE = os.path.dirname(os.path.abspath(__file__)); V = os.path.join(HERE, "work", "body")
view = sys.argv[1]
src = np.asarray(Image.open(os.path.join(V, view + ".png")).convert("RGBA")).astype(np.float32) / 255
gen = np.asarray(Image.open(os.path.join(V, view + "_gen.png")).convert("RGB")).astype(np.float32) / 255
H, W = src.shape[:2]
if gen.shape[:2] != (H, W): gen = cv2.resize(gen, (W, H), interpolation=cv2.INTER_AREA)
a = src[:, :, 3]
def lum(x): return cv2.GaussianBlur((x.mean(2) * 255).astype(np.uint8), (0, 0), 2)
# silhouettes first: the repaint's background is black, the render's is transparent (composited on black)
ls = lum(src[:, :, :3] * a[:, :, None]); lg = lum(gen)
# a global similarity (scale + shift) from the silhouettes' bounding boxes, then dense flow for the rest
ys, xs = np.nonzero(a > 0.5); yg, xg = np.nonzero(gen.mean(2) > 0.06)
if len(yg) < 100: sys.exit("repaint has no subject: " + view)
sy = (ys.max() - ys.min()) / max(1, yg.max() - yg.min()); sx = (xs.max() - xs.min()) / max(1, xg.max() - xg.min()); sc = (sy + sx) / 2
cy_s, cx_s = (ys.max() + ys.min()) / 2, (xs.max() + xs.min()) / 2; cy_g, cx_g = (yg.max() + yg.min()) / 2, (xg.max() + xg.min()) / 2
M = np.array([[sc, 0, cx_s - sc * cx_g], [0, sc, cy_s - sc * cy_g]], np.float32)
gen_s = cv2.warpAffine(gen, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
print("%s: silhouette scale %.3f, shift (%.0f, %.0f) px" % (view, sc, M[0, 2], M[1, 2]))
# dense flow render -> repaint at half resolution
D = 768; s_ = cv2.resize(ls, (D, D)); g_ = cv2.resize(lum(gen_s), (D, D))
flow = cv2.calcOpticalFlowFarneback(s_, g_, None, 0.5, 5, 41, 5, 7, 1.5, cv2.OPTFLOW_FARNEBACK_GAUSSIAN)
flow = cv2.GaussianBlur(flow, (0, 0), 6) * (W / D)
flow = cv2.resize(flow, (W, H))
mag = np.linalg.norm(flow, axis=2); print("flow: median %.1f px, p90 %.1f px" % (np.median(mag[a > 0.5]), np.percentile(mag[a > 0.5], 90)))
gy, gx = np.mgrid[0:H, 0:W].astype(np.float32)
out = cv2.remap(gen_s, gx + flow[:, :, 0], gy + flow[:, :, 1], cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
rgba = np.concatenate([out, a[:, :, None]], 2)
Image.fromarray(np.clip(rgba * 255 + 0.5, 0, 255).astype(np.uint8), "RGBA").save(os.path.join(V, view + "_paint.png")); print("wrote", view + "_paint.png")
