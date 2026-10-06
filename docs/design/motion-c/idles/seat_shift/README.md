# var_seat_shift: seated weight shift, measured from a real video

**Clip:** `web/room/mh_v5/var_seat_shift.glb` (6.47 s, 30 fps, seat context). It starts and ends in the desk_watch base pose: hips matched with `hipTo`, spine at −9.3°.

## Reference
Pexels video 5125886 ("An unmotivated man working", by james, Pexels License). The window used is 14.3–19.3 s: he shifts his weight to his left, holds for about 3.5 s, then shifts back. The camera is frontal, three-quarter, upper body only. The source video stays out of git. `reference_pexels_5125886_anon.jpg` shows frames 1 s apart, with each face pixelated using the tracked head landmarks.

## Measurement (MediaPipe Pose Landmarker heavy, Apache-2.0)
- Per frame, the shoulder midpoint's sideways position, in shoulder widths, from the image landmarks. The hips are hidden by the desk, so they are not measured.
- Event: base 2.478 → shifted 2.841, a move of **0.363 shoulder widths**, about 12 cm.
  - The shift takes about 0.4 s (14.6→15.0 s), then creeps a little further until 15.8 s.
  - It holds until 18.4 s.
  - The return takes about 0.4 s (18.4→18.8 s).
- The shoulder line tilts about 5.5° during the shift.
- `measured_shift_shape.json` holds the normalised curve n(t), 0 to 1, on the clip's time axis (reference time − 14.3 s + 0.8 s).

## Method (no keys)
- **Base:** the quietest seated Kimodo take from the shift prompt (`i_shift` seed 1, sample 0), pitched forward 0.57 rad to the desk_watch spine angle. Its own small motion is kept.
- **Measured curve applied at the same time** (`kimodo_retarget.mjs`, new `sideCurve` and `rollCurve`). The 0.363 sw full-scale shift is split into two parts:
  - The **hips slide on the seat**, 6.2 cm at full scale.
  - The **torso leans sideways**, 5.5° at full scale. This matches the measured tilt of the shoulder line. The head takes back 60% of the lean, so the gaze stays level.
- **Scale k = 0.65**, set by the chair. At k = 1.0 the hips go into the seat side by up to 1.4 cm, and at 0.8 by 1.2 cm. Both are over the 1 cm limit. At 0.65 the maximum is 0.6 cm. The reference performance is also visibly acted up.
- The ends of the curve are eased over 0.3 s. In the reference he goes straight into another action, but the clip must return to its base pose. The last 0.6 s eases into frame 0 (`loop`).
- `retarget_options.json` holds the exact options. `tools/motion/shift_curves.py` builds them from the measurement.

## Error against the reference (`error_vs_reference.json`)
| | Reference | Clip |
|---|---|---|
| Shape RMS (normalised curve) | | **0.034** |
| Half-way into the shift | 1.25 s | 1.27 s |
| Half-way back | 5.05 s | 5.07 s |
| Amplitude (shoulder widths) | 0.363 | 0.196 (k = 0.65 plus the base take's own motion) |

## Gate (my scene at the page's watch distance; `gate.json`)
1. Reference: shown above.
2. Penetration:
   - Chair: 21 samples in 13 frames, max **0.6 cm** (cushion give, under 1 cm).
   - Desk, keyboard and bed: 0.
3. Foot slide: **0.32 cm**.
4. Loop seam: worst bone jump 0.2° (NeckTwist01). The Hip jump is 0.0 cm.
5. Joint ranges: knees 90–101°, elbows 102–107°.
6. Rendered: `result_side_back_room_1s.jpg` shows clip t = 1–6 s, 1 s apart. Columns, left to right: close side view, back view, and the room camera. The shift goes to his left (−X in the room): shoulders 6.5 cm, hips 3.7 cm.

**Not yet checked in the page itself.** Watch mode puts the root lower and further back than mouse mode (the page-side issue being fixed by the page owner). The clip will be checked in the page over its whole length, in every mode, when that fix lands.

## Not copied from the reference
His right arm crosses his chest to rub his neck during the shift. That is a separate action, so it is not in this clip. The hands keep the base take's rest on the thighs and desk edge.

## TODO: raise k when the seating is fixed
**k = 0.65 is a limit set by the chair, not by the measurement.** The clip carries 54% of the real person's sideways shift because at full amplitude his hips go 1.4 cm into the seat side. That comes from how the page seats him; the performer did not move less. When the page's seating fix lands (watch-mode root height and depth), the clip must be rebuilt with the largest k that keeps chair contact under 1 cm, aiming for 1.0:

`python3 tools/motion/shift_curves.py K out.json 0.57`, then `kimodo_retarget.mjs`.

Then re-gate it and update the error table. Do not let 0.65 stand as "correct".
