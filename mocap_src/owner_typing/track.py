"""Track both hands in a video with MediaPipe HandLandmarker (VIDEO mode). Writes per-frame landmarks:
image-space (x, y in 0..1, z relative) and world-space (metres, origin at the hand's centre) for each hand.
Usage: track.py VIDEO MODEL OUT.json [ROTATE_DEG]"""
import json, sys
import cv2
import mediapipe as mp

video, model, out = sys.argv[1:4]
rot = int(sys.argv[4]) if len(sys.argv) > 4 else 0
V = mp.tasks.vision
opts = V.HandLandmarkerOptions(base_options=mp.tasks.BaseOptions(model_asset_path=model),
                               running_mode=V.RunningMode.VIDEO, num_hands=2,
                               min_hand_detection_confidence=0.4, min_tracking_confidence=0.4)
cap = cv2.VideoCapture(video)
fps = cap.get(cv2.CAP_PROP_FPS) or 30
frames = []
with V.HandLandmarker.create_from_options(opts) as lm:
    i = 0
    while True:
        ok, img = cap.read()
        if not ok:
            break
        if rot == 90: img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
        elif rot == 180: img = cv2.rotate(img, cv2.ROTATE_180)
        elif rot == 270: img = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
        size = [img.shape[1], img.shape[0]]
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        r = lm.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), int(i * 1000 / fps))
        hands = []
        for k, h in enumerate(r.hand_landmarks):
            hands.append({"side": r.handedness[k][0].category_name, "score": round(r.handedness[k][0].score, 3),
                          "img": [[round(p.x, 4), round(p.y, 4), round(p.z, 4)] for p in h],
                          "world": [[round(p.x, 4), round(p.y, 4), round(p.z, 4)] for p in r.hand_world_landmarks[k]]})
        frames.append({"t": round(i / fps, 4), "hands": hands})
        i += 1
json.dump({"video_fps": fps, "size": size if frames else None, "frames": frames}, open(out, "w"))
n2 = sum(1 for f in frames if len(f["hands"]) == 2)
print(f"{len(frames)} frames, both hands in {n2}, one in {sum(1 for f in frames if len(f['hands']) == 1)}")
