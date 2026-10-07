# Review: preview/standing-clips (G22)

- Reviewed: `7aec913` (2026-10-07 14:14 UTC, WIP), reviewed 2026-10-07 15:10 UTC by G23.
- Scope: 9 Mixamo clips on `char_mixamo.glb` via `room.html?char=mixamo&clip=<Clip>` (`standing_preview.js`).
- Default page: the new `room.html` block only runs with both `char=mixamo` and `clip` (code read; it returns before
  touching anything otherwise). Unchanged without the flag.

## Verdict: NOT OK (WIP). Contact is good; two clips have no prop, and one holds the phone wrong

How I checked: every clip loaded in the page through the flag (tests/visual fake server, SwiftShader). Soles measured
every frame of the whole clip (lowest skin vertex of each foot over what is under it). Shots at 10 / 45 / 80 % of each
clip (front and side from the preview's own `SP.view`, plus close-ups of the feet and hands), and Sit_To_Stand again at
75 / 90 / 99 %. `CLIP=<Clip> kimodo/contact_pass.mjs` (this branch's clip mode) on Scared, Angry_Gesture, Gaming,
Sit_To_Stand, Stand_To_Sit. Tool: `tools/clips.py`.

## Measured (mine)
| clip | kind | lowest foot over floor, cm (min–max over all frames) | frames > 1 cm | seat gap, cm | hands in thighs (contact_pass) |
|---|---|---|---|---|---|
| Texting | standing | 0.39–0.40 | 0 / 556 | – | – |
| Texting_While_Standing | standing | 0.39–0.40 | 0 / 707 | – | – |
| Standing_Using_Touchscreen_Tablet | standing | 0.40 | 0 / 994 | – | – |
| Standing_Clap | open chair | 0.22–0.40 | 0 / 143 | – | – |
| Angry_Gesture | desk chair | 0.31–0.40 | 0 / 175 | −0.3 … +1.8 | 0 |
| Gaming | desk chair | 0.39 | 0 / 151 | −0.3 … +0.3 | 0 |
| Scared | open chair | 0.12–3.23 (the jump) | 5 / 302 | −0.7 min | **28 frames, 256 verts, 2.5 cm** (t 5.07 s) |
| Sit_To_Stand | page's sit-down chair | 0.33–0.40 | 0 / 62 | +0.4 min | **17 frames, 2,013 verts, 8.5 cm** (t 2.07 s) |
| Stand_To_Sit | page's sit-down chair | 0.36–0.40 | 0 / 67 | −0.1 min | **27 frames, 2,672 verts, 7.0 cm** (t 0) |

contact_pass found nothing inside the chair, desk, walls, bed, other furniture or the floor in any of the five.

## Defects, by severity

### 1. Gaming and the tablet clip have no prop: he mimes into the air — HIGH
![no props](img/standing-clips_1_no_props.jpg)
Gaming (seated): both hands pinch an invisible controller. Standing_Using_Touchscreen_Tablet: claw hands at the belly
with nothing in them for 33 s. The owner reads this as an unnatural pose straight away.
Fix: attach `room/controller.glb` to the sockets for Gaming (both hands, grip from the clip's first frame, as the
phone). For the tablet, either a simple tablet prop (a rounded slab, 25 × 17 × 0.7 cm, on the left socket) or drop the
clip from the set until there is one.

### 2. Texting_While_Standing: the phone is edge-on, screen facing sideways — HIGH
![phone](img/standing-clips_2_phone_edge_on.jpg)
In the right hand the phone stands on its long edge, screen turned out to his right, not up toward his face. The
other hand's thumb taps at nothing. (Texting, the other phone clip, holds it right.)
Fix: in `standing_preview.js`, set the phone's orientation in the socket from the clip (screen normal toward the head
bone, averaged over the clip) instead of the palm normal on frame 0, or give this clip its own socket rotation in
`standing_clips.meta.json`. Check: the screen normal within 30° of the direction from the phone to his eyes over the clip.

### 3. Hands in thighs: Sit_To_Stand 8.5 cm, Stand_To_Sit 7.0 cm, Scared 2.5 cm — MEDIUM, needs a check
![hands thighs](img/standing-clips_3_hands_thighs.jpg)
contact_pass's leg capsules flag thousands of hand vertices in the standing part of both transitions (hands hanging at
the sides). In my renders the hands hang **beside** the trouser leg, fingers at most just touching the cloth, so the
capsule (radius 15–16 cm, from the baggy trousers) probably overstates it. Either way, say which it is: test the hand
vertices against the trouser **surface** (nearest-triangle side), not the capsule, and report that number. If it is
real, move the arms 3–5° out from the body in the bake (the arm-clearance step G21 described).

### 4. The preview's "front" camera lands inside a wall or the chair for chair clips — LOW (tooling)
![blocked](img/standing-clips_5_blocked_cam.jpg)
`SP.view("front")` for Standing_Clap, Scared, Angry_Gesture and Gaming renders a wall or the chair's back. The `side`
view is fine. Fix: also test the line of sight from the camera to his chest (raycast against the room), not only
"inside the room box".

### 5. Feet are main's old slides — note
`char_mixamo.glb` comes from main's v5: open slides with the white fringe (see Texting's feet close-up). Re-run autorig on
the G19 (+G10d) `char_v5.glb` once those land.

## What is fine
![ok](img/standing-clips_4_ok.jpg)
Feet stay planted: 0.3–0.4 cm over the floor in every standing frame. The seat holds him in the seated clips (gap
within −0.7 … +0.3 cm, nothing under the cushion). No furniture or wall penetration. Texting's phone grip looks natural.
Sit/stand at the page's own chair reads right from the side.
