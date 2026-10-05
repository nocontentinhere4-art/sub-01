"""Align a repainted head view to the rendered view it was made from:  python align_paint.py <view>
Reads work/views/<view>.png (the unlit render, black background, white eye openings) and work/views/<view>_gen.png (the
photoreal repaint from the image model), finds MediaPipe Face Mesh landmarks on both, warps the repaint onto the render's
landmarks (piecewise affine over the landmarks + the frame corners, so the hair and the background stay roughly put),
and writes work/views/<view>_paint.png at the render's size with the render's alpha (the character's silhouette).
The eye openings of the render are white: they are filled with a flat skin tone before detection so the detector sees
a face, and the repaint's eyes are irrelevant (the openings are holes in the skin atlas)."""
import os, sys
import numpy as np
from PIL import Image
from scipy import ndimage as ndi
from skimage.transform import PiecewiseAffineTransform, warp
import mediapipe as mp

HERE = os.path.dirname(os.path.abspath(__file__)); V = os.path.join(HERE, "work", "views")
view = sys.argv[1]
src = np.asarray(Image.open(os.path.join(V, view + ".png")).convert("RGBA")).astype(np.float32) / 255
gen = np.asarray(Image.open(os.path.join(V, view + "_gen.png")).convert("RGB")).astype(np.float32) / 255
H, W = src.shape[:2]
if gen.shape[:2] != (H, W): gen = np.asarray(Image.fromarray((gen * 255).astype(np.uint8)).resize((W, H), Image.LANCZOS)).astype(np.float32) / 255

MODEL = os.path.join(HERE, "work", "face_landmarker.task")          # MediaPipe's face_landmarker (Apache-2.0), downloaded by hand (README)
def landmarks(rgb):
    from mediapipe.tasks import python as mpp
    from mediapipe.tasks.python import vision
    opts = vision.FaceLandmarkerOptions(base_options=mpp.BaseOptions(model_asset_path=MODEL), num_faces=1, min_face_detection_confidence=0.2, min_face_presence_confidence=0.2)
    with vision.FaceLandmarker.create_from_options(opts) as fl:
        img = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray((rgb * 255).astype(np.uint8)))
        res = fl.detect(img)
    if not res.face_landmarks: return None
    lm = res.face_landmarks[0]
    return np.array([[p.x * rgb.shape[1], p.y * rgb.shape[0]] for p in lm])[:468]

# the render for detection: white eye openings filled with skin, the alpha composited on black
rgb = src[:, :, :3].copy(); a = src[:, :, 3]
white = (rgb.min(2) > 0.85) & (a > 0.5); skin_fill = np.array([0.85, 0.66, 0.60]); rgb[ndi.binary_dilation(white, iterations=2)] = skin_fill
L_src = landmarks(rgb); L_gen = landmarks(gen)
print(view, "landmarks: render", None if L_src is None else len(L_src), "repaint", None if L_gen is None else len(L_gen))
if L_src is None or L_gen is None: sys.exit("no face found: cannot align " + view)
# warp: repaint landmarks -> render landmarks; frame corners and edge midpoints pinned so the rest moves little
pin = np.array([[0, 0], [W / 2, 0], [W - 1, 0], [0, H / 2], [W - 1, H / 2], [0, H - 1], [W / 2, H - 1], [W - 1, H - 1]], float)
tf = PiecewiseAffineTransform(); tf.estimate(np.vstack([L_src, pin]), np.vstack([L_gen, pin]))     # inverse map: output (render) -> input (repaint)
out = warp(gen, tf, output_shape=(H, W), order=1, mode="edge")
d = np.linalg.norm(L_src - L_gen, axis=1); print("mean landmark offset before warp %.1f px, max %.1f px" % (d.mean(), d.max()))
rgba = np.concatenate([out, a[:, :, None]], 2)
Image.fromarray(np.clip(rgba * 255 + 0.5, 0, 255).astype(np.uint8), "RGBA").save(os.path.join(V, view + "_paint.png")); print("wrote", view + "_paint.png")
