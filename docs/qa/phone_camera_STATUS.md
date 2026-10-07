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
