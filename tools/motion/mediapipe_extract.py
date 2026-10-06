# MediaPipe Pose Landmarker (BlazePose GHUM 3D, Apache-2.0 weights) over a video stretch -> world landmarks per frame (JSON)
import json, sys, cv2, numpy as np, mediapipe as mp
from mediapipe.tasks import python as mpt
from mediapipe.tasks.python import vision
src, t0, t1, out = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4]
opt = vision.PoseLandmarkerOptions(base_options=mpt.BaseOptions(model_asset_path="pose_landmarker_heavy.task"), running_mode=vision.RunningMode.VIDEO, num_poses=1)
det = vision.PoseLandmarker.create_from_options(opt)
cap = cv2.VideoCapture(src); fps = cap.get(cv2.CAP_PROP_FPS); frames = []
i = 0
while True:
    ok, img = cap.read()
    if not ok: break
    t = i / fps; i += 1
    if t < t0 or t > t1: continue
    r = det.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(img, cv2.COLOR_BGR2RGB)), int(t * 1000))
    if not r.pose_world_landmarks: frames.append(None); continue
    w = [[l.x, l.y, l.z, l.visibility] for l in r.pose_world_landmarks[0]]; im = [[l.x, l.y, l.z] for l in r.pose_landmarks[0]]
    frames.append({"t": round(t - t0, 4), "world": w, "image": im})
json.dump({"fps": fps, "t0": t0, "t1": t1, "frames": frames}, open(out, "w"))
ok = sum(1 for f in frames if f); print("frames", len(frames), "detected", ok)
