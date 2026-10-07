# The owner's own typing, as hand landmarks

The owner filmed his own hands typing on a laptop, from straight above, so that the typing on the desk follows how a
real person types rather than the Mixamo performer's clawed hands. **The video is not here and never will be.** It
stays on the coordinator's machine, by the owner's rule. What is here is only numbers taken from it.

- `overhead_landmarks.json`: MediaPipe HandLandmarker (VIDEO mode, `hand_landmarker.task` float16), the video turned
  90° clockwise so that he sits at the bottom of the frame. 198 frames at 30 fps (6.6 s), with both hands found in
  every frame. For each hand, per frame:
  - `img`: the 21 landmarks in image space (x, y 0..1 of a 1920×1072 frame, after the turn; z relative);
  - `world`: the same 21 landmarks in metres, centred on the hand (MediaPipe's world landmarks);
  - `side`: Left or Right, checked against an overlay. His left hand is on the left of the frame.
- `track.py`: the script that made it. Usage: `track.py VIDEO MODEL OUT.json 90`.

Landmark order (MediaPipe): 0 wrist; thumb 1–4; index 5–8; middle 9–12; ring 13–16; little 17–20.

Joint flexion measured from `world` over the whole take (degrees of bend, median, with p10–p90 in brackets):

| joint | left index | left middle | left ring | right index | right middle | right ring |
|---|---|---|---|---|---|---|
| MCP (knuckle) | 43 (35–52) | 45 (41–51) | 50 (45–57) | 48 (43–54) | 51 (45–57) | 46 (41–53) |
| PIP | 63 (58–68) | 61 (54–67) | 59 (52–67) | 42 (37–45) | 31 (24–36) | 40 (27–46) |
| DIP | 17 (12–23) | 9 (5–12) | 16 (10–21) | 18 (11–26) | 24 (20–28) | 29 (23–34) |

What the take shows: the hands are low and flat over the keys, the palms just above the laptop's palm rest, the
fingers lightly curved (the last joint almost straight), the two hands angled slightly toward each other, and they
travel little. The owner asked for the motion **a little slower than his own**.

The owner also sent a second take, filmed from the side. It is not used: one hand is in view at a time, and the
handedness flips.
