# var_seat_leanback: sitting back into the chair (seat context)

`web/room/mh_v5/var_seat_leanback.glb` is a 7.5 s v5 clip in the room clips' format, breathing-free. It starts with the
torso leaning forward over the desk, as if just looking up from the keys, and ends with the back resting on the backrest.

## Where the motion comes from (real human movement, nothing keyed)
1. **Reference:** Pexels video 8939327, "A tired man taking a rest after folding his laptop", Mikhail Nilov, Pexels license.
   - Side view; 3.0-8.9 s of the original. He closes the laptop and sits back into his chair.
   - The video is not in the repo. `reference_pexels_8939327_anon.jpg` shows 5 frames with his head pixelated.
2. **Measured with MediaPipe Pose Landmarker** (BlazePose GHUM 3D, Apache-2.0 code and weights; see
   `../../capture/licence_check.md`), 148/148 frames tracked.
   - Torso pitch (hip midpoint -> shoulder midpoint, in the image plane where a side view measures best) goes from 13.6 deg
     forward to 9.8 deg back. Half-way is at 3.83 s.
   - `measured_torso_pitch.json` holds the smoothed curve and its normalised 0-1 shape.
   - Leg landmarks were unusable (knee / ankle jitter 74 / 115 m/s^2, hips occluded by the desk and chair), so the legs are not taken from the video.
3. **Body:** a near-still seated Kimodo take (i_lean2 seed 5 #0, prompt "A person sits upright on an office chair..."),
   retargeted onto v5 (`tools/motion/kimodo_retarget.mjs`) with relaxed photo-referenced hands.
   - The measured pitch curve drives the torso (`leanCurve`). The head keeps 80 % of its gaze (`leanHead`).
4. **Scaled to our chair:** the reference's chair reclines; the owner's chair does not.
   - The measured shape and timing are kept; the amplitude is scaled so the lean ends with his back on the pad (spine 9.2 deg forward -> 2.0 deg back).
   - Shape error against the reference: RMS 0.017 on the normalised 0-1 curve. Half-way at 3.90 s vs 3.83 s measured (`error_vs_reference.json`).

## Gate (G14's render scene, the chair where the page puts it in watch mode)

| check | result |
|---|---|
| penetration every 0.1 s, desk / keyboard / bed | 0 / 0 / 0 |
| penetration every 0.1 s, chair | 52 samples, max 1.0 cm, 12 frames (cushion give at the end of the lean) |
| foot slide | 0.98 cm (feet planted) |
| knees | 82-85 deg |
| elbows | 90-102 deg, no hyperextension |
| loop seam | none: a one-shot variant that starts and ends near the seated base pose, for the scheduler's cross-fade |
| looked at | `result_side_1s.jpg`, side view, frames at 0.5 / 2 / 3.5 / 5 / 6 / 7.2 s |

- The right hand is held 4.5 cm back over the last 2 s (a hip-relative IK target), so its fingers clear the desk's front edge.
- **Not yet gated in the page itself.** Watch mode currently places him 6 cm low and 7 cm back of mouse mode (G10d is on it).
  Re-gate in the page over the whole clip once that lands.
