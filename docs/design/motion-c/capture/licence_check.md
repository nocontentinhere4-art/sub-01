# Markerless capture: is there a chain whose code and weights are both permissive? (45-minute check)

**Yes: Google MediaPipe Pose Landmarker (BlazePose GHUM 3D).**

## Licences
- **Code:** google-ai-edge/mediapipe, Apache License 2.0 (`LICENSE`, checked).
- **Weights:** `pose_landmark_{lite,full,heavy}.tflite` and `pose_detection.tflite` (storage.googleapis.com/mediapipe-assets).
  - The BlazePose GHUM 3D model card (https://mediapipe.page.link/blazepose-mc, PDF, 8 pages) states "LICENSED UNDER
    Apache License, Version 2.0".
  - It was trained on Google's own captures, including "consented images (30K)" from a mobile AR app.
  - No SMPL, no Human3.6M, no account, no data-use agreement.
- **Output:** `pose_world_landmarks`, 33 landmarks per frame, "real-world 3D coordinates in meters with the origin at the
  center between hips", plus visibility. It runs on CPU, so no GPU is needed.

## Caveats, from the model card and its design
- Its out-of-scope list includes "applications requiring metric accurate depth". Depth is the weak axis: a single camera
  sees front-to-back motion least well. A side-on camera turns lean-back / lean-forward into the image plane, where it is measured best.
- 33 points carry no bone twist (forearm / spine roll) and only three points per hand. Rotations are solved by IK on the
  v5 rig from positions, not copied from a body model.
- It tracks one person; it is sensitive to face position, scale and orientation; it degrades in poor light.
- Expect it to be weaker on subtle idle motion than on large gestures. That is to be measured, not assumed.

## Not usable (checked)
- GVHMR and WHAM: SMPL/SMPL-X body models, which need a sign-up and are licensed for non-commercial research only.
- MotionBERT: Apache code, but its weights are trained on Human3.6M (research-only) and it uses AlphaPose for 2D (own non-commercial terms).
