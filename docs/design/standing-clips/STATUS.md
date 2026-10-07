# G22: standing and in-between clips on the Mixamo-rigged character (status)

Branch `preview/standing-clips` (off `origin/preview/mixamo-pipeline`). No raw capture is committed: the re-bake reads
the FBX from `claude/loving-davinci-6hqmjx` into a temp dir and deletes them after. Details and the contact table:
`README.md`.

## State (2026-10-07): done; G23's review answered (below), round 3 (C / G26) below
- [x] The nine clips are baked for `web/room/char_mixamo.glb`: `web/room/mx_standing/<Clip>.glb`, plus
      `standing_clips.meta.json`.
- [x] One re-bake command: `room_build/kimodo/standing_rebake.sh <character.glb> [Clip ...]`. It covers all nine,
      including the hands-off-thighs step.
- [x] Page entry: `room.html?char=mixamo&clip=<Clip>` (`web/room/standing_preview.js`, plus the marked G22 block at
      the end of `room.html`). The default page is unchanged: without `clip`, nothing runs.
- [x] Hands: sockets `socket_R` / `socket_L` in each palm. The page's phone is on Texting's right hand, its screen
      turned to his eyes and lifted onto his curled fingers. Texting_While_Standing holds it in both hands in front of
      his chest (round 3). Gaming holds the page's
      controller and the tablet clip a plain tablet (the page has none), each between his palms every frame.
- [x] Contact in the room, every frame, every visible mesh: `CLIP=<Clip> contact_pass.mjs <port> x clip`.
- [x] Self contact, every frame: `standing_selfcontact.mjs` (`QA.selfContact`). Arm in torso is shown with and without
      the rig's flank weights.
- [x] Contact table per clip in `README.md`; the JSON in `contact/`.
- [x] Render sheet: `sheet.jpg` (each clip at 10 / 50 / 90 %, front and side, in the room).
- [x] Full pytest and the visual gate (below).

## Numbers
See `README.md`, "Contact table". In short:
- Furniture, walls, floor: 0 vertices more than 1 cm inside, all nine clips, every frame.
- Supporting sole 0…+1 cm: every frame except the ones the README lists (Scared's jump; Sit_To_Stand on the rug's
  edge).
- Hands in thighs: 0 after the bake's fix.
- Arm in torso: the rig's (G20's weights; G23's review, items 1 and 3), shown against the no-clip baselines.

## Tests
Run on 63efec3, the final clips and code, 2026-10-07:
- `set -o pipefail; python -m pytest 2>&1 | tail; echo "pytest exit $?"`: **1292 passed, 27 skipped, exit 0**
  (12 min 24 s). This includes `tests/test_standing_clips.py`: the nine clips on the character's skeleton, the fit
  recorded with hands-in-thighs 0 after the bake, no raw capture in `web/`, and the preview only with its parameters.
- `tests/visual/out/results.json`: `hard_failures == []`.
- The re-bake reproduces the committed clips byte for byte (checked on Sit_To_Stand and Stand_To_Sit, GLB and meta).

## Open, for others
- Page wiring (G21 / G10d): the seat points `seatAt` (−0.18…−0.24 m; G21's desk loops sit at −0.075) differ from the seated loop's. The join needs a
  slide back on the seat during the cross-fade, or the loop's seat point taken from the same sweep. At the desk, the
  rare events need more roll-back than the bed allows.
- Rig (G20): the arm-in-torso numbers come from the flank and armpit weights.

## Review (G23, docs/review/standing-clips.md on preview/review, of 7aec913): answers
1. **No prop for Gaming and the tablet (HIGH): fixed.**
   - Gaming holds the page's controller (`room/controller.glb`).
   - The tablet clip holds a plain 25 × 17 × 0.7 cm tablet, built in code with no brand.
   - Both are placed between his palms every frame, face to his eyes: controller 1.4° mean, 4.4° worst. Table column
     "held prop".
2. **Texting_While_Standing's phone edge-on (HIGH): fixed.** For both phone clips, the screen now turns towards his eyes
   (averaged over the clip in the palm's frame) and is lifted off his hand skin. Mean angle and the share of frames
   within 30° are in the table. The frames that miss are the start and end of each clip, with his phone hand down at
   his side.
3. **Hands in thighs (MEDIUM): it is real in two stretches, and both are fixed in the bake.**
   - contact_pass's capsule overstates it, as you suspected. Both numbers are in the table.
   - Against his trouser surface (nearest thigh vertex and its normal, `QA.selfContact`), the hands were 2.49 cm in
     for 69 frames (Texting_While_Standing, hands coming down) and 0.56 cm for 10 frames (Texting's hanging left
     hand). The bake moves the wrist out and re-solves the arm, so both are 0 now.
   - Scared, Sit_To_Stand and Stand_To_Sit are 0 by the surface test: the capsule was reading hands hanging beside the
     leg.
   - The 3–5° arm-out step you suggest does not clear the sleeves (see README, "What is not clean"): 15° only took
     Gaming from 4.3 to 2.6 cm. It is not baked.
4. **Blocked front camera (LOW): fixed.** `SP.view` takes the first direction and distance with a clear line of sight
   to him; `sheet.jpg` is re-rendered.
5. **Main's old slides: noted.** That is the rig's input (G20). After autorig re-runs on the new `char_v5.glb`,
   `standing_rebake.sh <char.glb>` re-bakes all nine in one command.

## Round 3 (C, 2026-10-07 17:57): re-baked on the one character source, Texting_While_Standing fixed
- [x] **The character.** `origin/preview/mixamo-wiring` (bc063fb: its `char_mixamo.glb` autorigged from main's
      `char_v5.glb`, b2593d7, collar + socks; G26 OK on d663a1d, and the GLB is the same at bc063fb) is merged into
      this branch. So the branch's `char_v5.glb` is main's again (the old one came with the mixamo-pipeline base), and
      the preview plays the clips on the rebuilt character.
- [x] **All nine re-baked** with `standing_rebake.sh web/room/char_mixamo.glb`. Hip scale 0.873 on this rig (0.893 on
      the old one).
- [x] **Scared's seat point re-swept** on the new rig: clear from −0.21, set to −0.22 (it was −0.20, which left 7
      vertices 1.2 cm into the chair for 8 frames). The other seat points measure clean as they are.
- [x] **Texting_While_Standing (G26 round 2, item 2): the phone at his hip → in front of his chest, screen to his eyes.**
  - The bake's new `handsUp` row option: while both hands are up (467 of 708 frames), arm IK takes the wrists to
    32 cm in front of his upper spine and 5 cm under his neck joint, 10 cm either side of his middle. The hands keep
    their world rotations.
  - The phone is held in both hands (`hold: phone2`), between his palms every frame. Its screen is 6.9° from his
    eyes on average and 19.6° at worst: 100 % of samples within 30°.
  - Hand in hand: 17 frames at ≤ 1.0 cm, while the hands come together at about 1.9 s. The wrist gap was swept:
    13 cm gave 568 frames at 2.2 cm, 17 cm gave 313 frames at 1.5 cm.
- [ ] **Gaming's open left fingers (G26 round 2, item 3, LOW): not done.** The left hand holds the controller's grip
      as the capture has it. Curling the fingers would be invented hand motion, and the mocap README rules that out
      without the owner. Left for C / the owner to decide.
- [x] The contact table, `contact/` and `sheet.jpg` are re-measured on the new rig; the numbers are in `README.md`.
- In the room, on the new rig: 0 vertices more than 1 cm inside furniture, walls or the floor, in all nine clips and
  every frame. Hands in thighs: 0. The sleeve-in-torso overlap is much smaller (0 in Gaming; 13–40 frames in the chair
  transitions); the standing clips still have it (README, "What is not clean").
