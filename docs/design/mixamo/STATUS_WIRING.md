# G21: `room.html?char=mixamo` wiring: status

Branch `preview/mixamo-wiring` (off `origin/preview/mixamo-pipeline`). The raw Mixamo FBX stay in scratch (from
`claude/loving-davinci-6hqmjx:mocap_src/mixamo/`); nothing raw is committed.

## State (2026-10-07, live)
- [x] 2. Armpit weights in autorig. Desk clips ≤ 0.6 cm on the raw Mixamo captures, every frame (numbers below).
- [~] 1. `?char=mixamo`: page wiring done (room.html, boy_mh.js env, char_mixamo.js ROOM). The clips are baking.
- [ ] 3. rig_change.mjs: the 6 PENDING items; contact_pass.mjs over every frame
- [ ] 4. `wiring_sheet.jpg`
- [ ] 5. full pytest + visual hard_failures

## 2. Weights (rig/autorig/fit.py, write.mjs, extract.mjs)
All measured every frame at 30 fps, all vertices, with qa.html's test (an arm vertex more than 5 mm behind the nearest
hoodie vertex's normal, within 2.5 cm).
- **Bound as modelled, not in the T-pose.** Each bone's inverse bind is now its T-pose placement taken back through the
  rigid T-posing map of the v5 joint it stands for. Rigid parts pose exactly as before. A vertex shared by two bones is
  no longer T-posed by a blend first: linear blending is not invertible where the maps differ.
- **The arm part is the arm.** v5's own (Tripo) skin gives the upper arm 0.9 of patches of the hoodie's back and chest,
  medial to the shoulder joint (x 0.15 against the joint's 0.20). With the arms forward to type, those patches sank into
  the torso. Now skin is "arm" only within 13 cm of the arm's bind axis (shoulder → elbow → wrist). At 9 or 11 cm, real
  sleeve was excluded (out to x 0.43 / 0.30); at 13 cm only the 733 / 758 patch vertices go, all at x ≤ 0.21.
- **Sleeve and hoodie as two parts.** More than 7 cm from the shoulder joint, the sleeve takes no spine weight and the
  hoodie no arm weight. Under the shoulder (6 cm), the sleeve takes no clavicle weight; the hoodie keeps it.
- **Span rule.** A limb bone only weights skin within its own span along the limb (±6 cm elbow, ±4 cm wrist, ±7 cm knee,
  ±5 cm ankle). v5's skin put 0.18 of the forearm on the armpit.
- **Legs only below the hips** (+10 cm): v5's skin put up to 0.2 of the thigh on the chest. **A side's bones on its own
  side** (±4 cm): the left sleeve carried 0.07 of the right clavicle.
- **His size kept.** fit.py assumed 0.875 m per bind unit (1.78 m with the slides). It now reads the source's own scale
  (extract.mjs: v5 0.8508), so char_mixamo is 1.731 m like v5 in the page, the size the chair and desk fits were made
  for.

| raw Mixamo clip on the rig | before (G20) L / R | after L / R |
|---|---|---|
| Seated_Idle | 2.4 / 2.4 cm (532 / 373 verts) | 0 / 0.6 cm (0 / 2 verts) |
| Typing | 2.3 / 2.0 cm (113 / 64) | 0 / 0.6 cm (0 / 5, 3 of 495 frames) |
| Sit_To_Type | – | 0 / 0 |
| Type_To_Sit | – | 0 / 0 |
| Stand_To_Sit, Sit_To_Stand, Sitting, Sitting_1, Sitting_Rubbing_Arm | – | 1.1–2.5 cm: his arms hang at his sides or rest on his lap, against a slimmer performer's body |

The clips that still go in hold the arms against the body, so their bake (kimodo/mx_fit.py) moves the arms out: the
elbow swings out about the shoulder–wrist line (the wrist stays), then the arm abducts at the shoulder if needed; per
frame, the least that clears, then smoothed.

Tried and measured, not kept: re-centring the shoulder joint on the sleeve's cross-section (right side worse); welding
sleeve and hoodie weights across the seam; ramps instead of cuts; a pose-driven pass that hands the sleeve's weights
to the hoodie where they collide (diverged: 154k → 500k hits over 12 rounds). An earlier note here said the rest was
the pose, not the weights. That was wrong: the "rigid" test behind it took the arm part from the same mislabelled
skin.

## 1. Wiring (in progress)
- `room.html?char=mixamo` loads `room/char_mixamo.glb` with `room/char_mixamo.js`. Without the flag the page is as on
  main (v5).
- Desk, on the Mixamo skeleton, nothing retargeted (`kimodo/mx_fit.py` via `kimodo/mx_build.sh`, rows in
  `kimodo/mx_clips.json`):
  - watching: Seated_Idle
  - typing: Typing, with Sit_To_Type / Type_To_Sit on the way in and out (G12's chain and its 0.8 s links)
  - sitting down / standing up: Stand_To_Sit / Sit_To_Stand
  - G12's chair fit is ported to this skeleton: the hip joints at 0.68 m, 4.5 cm forward, the cushion stop, planted
    feet with the soles +0.2 cm over the floor (slides included), hands riding up with him, then handUp / keys.
- No Mixamo capture exists for the mouse, walking, standing, the bed, eating, the door or the window. Those are v5's
  room clips carried onto the Mixamo skeleton (`kimodo/mx_convert.mjs`): each bone moves as the v5 joint it was fitted
  from, plus position tracks where the skeletons' joints differ. Measured against v5: median skin offset 2–3 mm. The
  larger offsets are v5's own skin defects that the new weights don't repeat (its armpit carries 0.2–0.3 of the forearm).
