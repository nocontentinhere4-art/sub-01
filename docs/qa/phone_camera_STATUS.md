# Phone camera (preview/phone-camera, worker G25) — status

Defect (coordinator A, live, 16:03): on a 390×844 phone, asleep in bed, the follow camera framed the room and left him
out (the bed off the left edge); at 1280 he was in frame.

## Milestone 1 — failing test on main: done
`tests/visual/test_phone_camera.py` + `tests/visual/phone_camera.js`. Headless Chromium (SwiftShader), the existing
harness and fake server; the page's follow camera stepped as `frame()` steps it (goal, 1.2/s lerp, keepClear). Each
frame: his projected bounding box (all visible skinned meshes, CPU-skinned) and his head (12 cm sphere). The frame is the
3D canvas less the header (`#top`) that lies over its top on phones. Hard on 390×844, 360×780, 430×932: in bed (asleep,
on his side, music, phone in bed, getting in, getting out) ≥ 80 % of the box in frame and the head in frame every frame;
standing and walking the same; at the desk (the monitor shot, 54 % of him at 1280 by design) the head.

Numbers on main (b851745), worst share of his box in frame / frames with his head cut (90 frames per steady mode;
into bed 690, out of bed 750):

| mode | 390×844 | 360×780 | 430×932 | 1280×800 |
|---|---|---|---|---|
| asleep | 0.917 / 90 | 0.914 / 90 | 0.914 / 90 | 1.0 / 0 |
| on his side | 0.917 / 90 | 0.914 / 90 | 0.914 / 90 | 1.0 / 0 |
| lying, music | 0.915 / 90 | 0.912 / 90 | 0.912 / 90 | 1.0 / 0 |
| phone in bed | 0.915 / 90 | 0.822 / 90 | 0.912 / 90 | 1.0 / 0 |
| into bed (door → lying) | 0.63 / 495 | 0.532 / 546 | 0.745 / 335 | 1.0 / 0 |
| out of bed (→ desk) | 0 / 645 | 0 / 645 | 0 / 645 | 0 / 538 |
| desk (monitor shot) | 0.387 / 25 | 0.373 / 31 | 0.402 / 17 | 0.548 / 0 |
| standing (door) | 0.884 / 90 | 0.817 / 90 | 0.963 / 0 | 1.0 / 0 |
| walking | 0.757 / 90 | 0.685 / 90 | 0.842 / 20 | 1.0 / 0 |

On the phones the overview (fixed at (5.2, 5, 6) → (0, 0.6, 0), vertical FOV 30° on a 0.74-aspect canvas) puts his
head ~11 px from the left edge and the bed past it. Out of bed the monitor shot starts as soon as the desk tick arrives,
while he is still getting up from the bed (at 1280 too: 538/750 frames; left as it is, 1280 must not change).

## Milestone 2 — the fix: done (web/room.html, camera logic only)
- Phones (`camera.aspect < 1`, he is in the room): instead of the fixed overview, the follow camera keeps the overview's
  angle but frames him: a 1.05 m sphere round his hips (lying: him and the bed; standing: head to feet) fitted into the
  band of the canvas under the header (`#top`, read twice a second), so the distance follows the aspect ratio and the
  header's height; his hips sit in the middle of that band. The goal follows his hips continuously and the page's 1.2/s
  lerp moves the camera, so there is no jump between asleep / on his side / awake / getting in or out.
- Phones: the monitor shot waits until he is at the desk (at main it started as soon as the desk tick arrived, with him
  still in bed); at the desk it is the same shot (angle, distance) slid up under the header so his head is not under it.
- The camera's spring arm no longer collides with `shadow_shell` (the invisible slabs that only close the cut-open room
  for the sun's shadow map: no colour, no depth): near the door it pulled the phone camera into his back.
- 1280×800 / desktop: the same code path as before (`aspect ≥ 1`): camera positions identical, 1280 shots pixel-equal
  (max diff 8/255, SwiftShader noise), the desk camera unchanged. 1280's numbers equal main's, including the out-of-bed
  frames where the monitor shot comes in early (538/750, not touched: desktop must not change).

After the fix (worst share in frame / frames with the head cut):

| mode | 390×844 | 360×780 | 430×932 | 1280×800 |
|---|---|---|---|---|
| asleep | 1.0 / 0 | 1.0 / 0 | 1.0 / 0 | 1.0 / 0 |
| on his side | 1.0 / 0 | 1.0 / 0 | 1.0 / 0 | 1.0 / 0 |
| lying, music | 1.0 / 0 | 1.0 / 0 | 1.0 / 0 | 1.0 / 0 |
| phone in bed | 1.0 / 0 | 1.0 / 0 | 1.0 / 0 | 1.0 / 0 |
| into bed (door → lying, 630 frames) | 1.0 / 0 | 1.0 / 0 | 1.0 / 0 | 1.0 / 0 |
| desk (monitor shot) | 0.327 / 0 | 0.319 / 0 | 0.335 / 0 | 0.548 / 0 |
| standing (door) | 1.0 / 0 | 1.0 / 0 | 1.0 / 0 | 1.0 / 0 |
| walking | 1.0 / 0 | 1.0 / 0 | 1.0 / 0 | 1.0 / 0 |

Out of bed (on the way, until he is at the desk anchor; then the monitor shot, head only): re-measured in the full run
below (the test's arrival check now runs every frame).

Sheet: `docs/qa/phone_camera_before_after.jpg` (390×844 asleep, awake in bed with music, at the desk, walking, before /
after; 1280×800 asleep before / after).

## Milestone 3 — full suite: running
