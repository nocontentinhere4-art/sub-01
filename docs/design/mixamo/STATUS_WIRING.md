# G21: `room.html?char=mixamo` wiring: status

Branch `preview/mixamo-wiring` (off `origin/preview/mixamo-pipeline`). The raw Mixamo FBX stayed in scratch (taken from
`claude/loving-davinci-6hqmjx:mocap_src/mixamo/`); none is committed, only the clips baked for our skeleton. No RunPod
pod, no Tripo credits used. Method and pipeline: `README.md`, last section.

## State (2026-10-07)
- [x] 1. `room.html?char=mixamo` loads `room/char_mixamo.glb` with `room/char_mixamo.js` and plays the Mixamo clips on
  their own skeleton (`room/mh_mx/`, nothing retargeted to the old rig). Without the flag the page is as on main.
  - Desk: Seated_Idle (watching), Typing with Sit_To_Type / Type_To_Sit in and out, Stand_To_Sit / Sit_To_Stand.
  - Sitting, Sitting_1, Sitting_Rubbing_Arm and Sitting_Talking are baked, but no page slot plays them yet.
  - G12's chair fit is ported (`kimodo/mx_fit.py`). He sits on our chair, fingertips over our keyboard, soles +0.2 cm
    on the floor.
- [x] 2. Armpit weights fixed in autorig, so every re-run produces them. Arm in torso ≤ 0.6 cm on the raw desk clips
  and ≤ 0.8 cm on every frame of the baked desk clips (gate 1.2).
- [x] 3. `rig_change.mjs`: the 6 PENDING items are measured in the room, none left PENDING (1 PASS, 2 FAIL, 3 FAIL,
  4 PASS, 5 MEASURED, 6 FAIL). The contact pass ran over every frame. → `rig_change_v5.md`
- [x] 4. `wiring_sheet.jpg`: main (v5) above, `?char=mixamo` below; watching and typing; page camera and his right side.
- [x] 5. Full pytest and visual: see "Tests".

## 2. Weights (rig/autorig/fit.py, write.mjs, extract.mjs)
All measured every frame at 30 fps, all vertices, with qa.html's test (an arm vertex more than 5 mm behind the nearest
hoodie vertex's normal, within 2.5 cm).

| raw Mixamo clip on the rig | before (G20) L / R | after L / R |
|---|---|---|
| Seated_Idle | 2.4 / 2.4 cm (532 / 373 verts) | 0 / 0.6 cm (0 / 2 verts) |
| Typing | 2.3 / 2.0 cm (113 / 64) | 0 / 0 |
| Sit_To_Type, Type_To_Sit | – | 0 / 0 |
| Stand_To_Sit, Sit_To_Stand, Sitting, Sitting_1, Sitting_Rubbing_Arm | – | 1.1–2.5 cm. The arms hang at his sides or rest on his lap against a slimmer performer's body; the bake moves them out (table below) |

qa.mjs (G20's QA, every 0.1 s, every 2nd vertex): Seated_Idle 0 / 0.5 cm, Typing 0 / 0, the 0.8 s blends both ways
0 / 0. The arms-down rest is 0 (G20: 8 / 15 verts, ≤ 1.2 cm).

What changed, and why:
- **Bound as modelled, not in the T-pose.** Each bone's inverse bind is its T-pose placement taken back through the rigid
  T-posing map of the v5 joint it stands for (fit.py `bindmap`, write.mjs). Rigid parts pose exactly as before.
  Linear blending is not invertible where two maps differ, so a T-posed bind never came back at the armpit.
- **The arm part is the arm.** v5's own (Tripo) skin gives the upper arm 0.9–1.0 of patches of the hoodie's back and
  chest, medial to the shoulder joint. With the arms forward to type, those patches sank 2.4 cm into the torso. Now skin
  is "arm" only within 13 cm of the arm's bind axis and no more than 2.5 cm medial of the shoulder joint.
- **Sleeve and hoodie as two parts** more than 7 cm from the shoulder joint, and **no clavicle on the sleeve** under
  the shoulder. The hoodie keeps the clavicle: without it the hoodie went 2.5 cm into the sleeve instead.
- **Span rule** (v5's skin put 0.18 of the forearm on the armpit), **legs only below the hips** (0.2 of the thigh on the
  chest), **each side's bones on its own side** (0.07 of the right clavicle on the left sleeve).
- **His size kept:** fit.py assumed 0.875 m per bind unit (1.78 m). It now reads the source's own scale (0.8508), so
  char_mixamo is 1.731 m, like v5 in the page. The chair and desk fits were made for that size.
- Tried and measured, not kept: re-centring the shoulder joint; welding the seam; ramps instead of cuts; a pose-driven
  weight hand-over (it diverged).
- **Known cost: raised arms leave a web.** With the arm raised high (the T-pose), the back of the armpit stays behind:
  10,010 vertices end more than 5 cm (max 19.5 cm) from where v5's own skin puts them. Without the 7 cm cut that drops to
  29 vertices, but seated the sleeves go 2.3 cm into the hoodie again. The desk clips keep the arms down. The clips that
  raise them are room_bedtime's stretch, Standing_Clap and the window. The fix for both is an arm-raise corrective
  shape; not made.

## 1. The baked clips (`kimodo/mx_build.sh`, `mx_fit.py` report, every frame)

| clip | frames | arm in torso before the clearance, L / R cm | after | elbow swing ° L / R | abduction ° L / R | soles cm L / R | knees m |
|---|---|---|---|---|---|---|---|
| Seated_Idle | 126 | 0.3 / 0.0 | 0.3 / 0.0 | 0 / 0 | 0 / 0 | 0.2…0.2 / 0.2…0.2 | 0.59 / 0.57 |
| Typing | 495 | 0.0 / 1.8 | 0.0 / 0.8 | 0 / 14 | 0 / 0 | 0.2 / 0.2 | 0.60 / 0.57 |
| Sit_To_Type | 37 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0.2 / 0.2 | 0.60 / 0.57 |
| Type_To_Sit | 29 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0.2 / 0.2 | 0.60 / 0.57 |
| Stand_To_Sit | 68 | 2.5 / 2.5 | 0 / 0 | 24 / 30 | 20 / 24 | 0.2…0.8 / 0.2…2.0 | 0.60 / 0.56 |
| Sit_To_Stand | 63 | 2.5 / 2.5 | 0 / 0 | 30 / 28 | 20 / 18 | 0.2…0.7 / 0.2…1.2 | 0.59 / 0.57 |
| Sitting_1 | 36 | 1.1 / 2.5 | 0.7 / 0.5 | 2 / 14 | 0 / 0 | 0.2 / 0.2 | 0.59 / 0.58 |
| Sitting_Rubbing_Arm | 240 | 2.2 / 2.5 | 0.8 / 0.7 | 28 / 30 | 0 / 22 | 0.2 / 0.2 | 0.55 / 0.59 |
| Sitting_Talking | 1323 | 2.5 / 2.5 | 0.8 / 0.8 | 30 / 30 | 12 / 18 | 0.2 / 0.2 | 0.60 / 0.57 |
| **Sitting** | 134 | 2.5 / 2.5 | **1.6 / 1.6** (12 / 9 frames over) | 30 / 25 | 24 / 22 | 0.2…1.1 / 0.2…0.9 | 0.58 / 0.57 |
| **Scared** (rare) | 303 | 2.5 / 2.5 | **1.2 / 2.2** (7 / 34 frames over) | 30 / 26 | 16 / 20 | 0.2…1.4 / 0.2…2.2 | 0.58 / 0.57 |
| Angry_Gesture (rare) | 176 | 2.5 / 2.5 | 0.6 / 0.7 | 30 / 26 | 14 / 18 | 0.2 / 0.2 | 0.59 / 0.56 |
| Standing_Clap (rare) | 144 | 2.5 / 2.5 | 0.7 / 0.0 | 30 / 16 | 10 / 24 | 0.2…1.0 / 0.2…0.6 | 0.58 / 0.58 |

Sitting and Scared still go over 1.2 cm (all the reach of the swing and abduction used). Neither is played by a page
slot; the rare events are not accepted on v5 either (README).

The fit, briefly:
- Hip joints at 0.68 m, 4.5 cm forward; the cushion stops the hips.
- His own wrists, ridden up with him; typing `keys` −11 cm puts his fingertips over our key tops (0.86 m).
- Knees at 0.55 m. Our chair is high for him: with the feet flat his thighs went 3–8 cm through the cushion's front edge,
  so his heels come up 7–8 cm, as on v5.
- Feet planted with the soles +0.2 cm; sleeves off the hoodie.

## 3. In the room (`kimodo/mx_room.sh`: contact_pass.mjs over every frame, ?char=mixamo against v5 on the same page)

| | ?char=mixamo | v5 (the page without the flag) |
|---|---|---|
| watching (8 s) | chair, desk, other furniture, floor clear; seat lowest gap −0.6…+4.1 cm; soles 0.2 cm (*); hands in thighs 0 frames | clear; seat −0.1…+4.6; soles 0.1…4.8 / −0.2…4.5; hands in thighs 20 frames, 0.5 cm |
| typing (6 s) | all clear; seat −0.2…+4.4; soles 0.2 (*); fingertips over the keys 178/180 frames, never below the key tops, touching (≤ 5 mm) 5 frames, gap 0…11.3 cm | chair legs 1 cm (4 verts); fingertips over 216 frames, touching 17, −2.5…+3.9 cm (5 frames into the keys); soles 9.2…14.1 / 5.7…10.7 cm |
| mouse (8 s) | v5's clip carried over: all clear; palm 7.6 cm from the mouse's centre, 8.5–9.3 cm over its top; soles 7.4…12.2 / 4.1…9.3 cm | the same: palm 7.7 / 8.5–9.3; soles 9.1…13.9 / 5.3…10.4 |
| sit-down (Stand_To_Sit, 4 s) | chair legs 1.4 cm (70 verts, 18 frames); seat −1.4 | chair legs 1.2 cm (50 verts, 2 frames); seat −1.2 |
| stand-up (Sit_To_Stand, 4 s) | chair legs 3.4 cm (28 verts, 4 frames), **feet 4.1 cm (188 verts, 5 frames)**; seat −0.4; sole −3 cm on the hand-over to the walk | chair legs 3.8 cm (30 verts, 8 frames); seat −0.9 |
| step away (8 s) | as the stand-up, plus feet 6.8 / legs 5 cm in the furniture by the chair while walking (v5's walk) | the same furniture contact: feet 6.6 / legs 5 cm |
| rare: scared / angry / clap | rides back 39 / 0 / 34 cm; chair legs 2.5 cm (156 verts, 5 frames) / clear / 3.5 cm (546 verts, 77 frames); desk clear | 33 / 20 / 31 cm; chair clear |

(*) The soles read up to 4.8–4.9 cm only in the first 0.5 s after he is placed: the page's floor lift eases down from
the settle (v5 the same). From then on they hold at 0.2 cm.

Seat points (boy_mh.js SEAT_AT, swept with `kimodo/seat_sweep.mjs`): clear of the chair at watching −0.05…−0.12 m,
typing −0.06…−0.12, mouse −0.04…−0.12. Used −0.065 / −0.075 / −0.055 (`char_mixamo.js` ROOM.seatAt).

The checklist's six (`rig_change_v5.md`):
1. **Sit-down landing: PASS.** No deeper than v5 (1.4 against 1.2 cm, within 3 mm), seat −1.4 cm.
2. **Rising: FAIL.** A foot goes 4.1 cm into the chair's base for 5 frames (188 vertices; v5: none) as he steps off.
3. **First step away: FAIL.** The same foot frames. The walk itself matches v5's.
4. **Seat points: PASS.**
5. **Rare events' chair ride: MEASURED.** Angry_Gesture's ride is 0 here (v5 20 cm): his baked hips sit 27 cm to one
   side (the performer sat off-centre), so backFor() finds nothing in front.
6. **Mouse-mode body: FAIL**, the same as v5. There is no Mixamo mouse capture, so the mouse plays v5's clip carried
   over: palm 7.6 cm off the mouse, feet hovering. Typing as the mouse body is no better without a resolver: its right
   palm wanders 12 cm sideways (sd).

Contact contract (docs/qa/contact.md), still open:
- fingertips touching the keys through the whole clip (5/180 frames; G14's resolver);
- the mouse (item 6);
- the stand-up's foot in the chair base.

## Tests (this branch, 2026-10-07)
- `set -o pipefail; python -m pytest 2>&1 | tail; echo "pytest exit $?"`: **1287 passed, 27 skipped, pytest exit 0**
  (10 min 28 s).
- First run: 1 failed, 1286 passed, 27 skipped. The failure was `test_boy_motion.py::test_licences_recorded`, which
  asserts CREDITS.md never names Mixamo; my credits section did. **For the coordinator:** CREDITS now points to this
  folder's README ("Sources and licences", G12's) instead of naming the source, as main's `mh_v5/` desk clips already
  do. Whether that guard should stay is a policy call. I did not edit the test.
- `tests/visual/out/results.json`: `hard_failures == []` (both runs).
