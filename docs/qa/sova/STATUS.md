# Sova clips: status (G23 → COORD)

The newest entry is at the top. Code: `room_build/sova/`. Branch: `preview/sova-phone-src` only, nothing in `web/`.


## Videos
- **`sova_quick.mp4`** (commit ba8d006): 38 s, 640x360, 24 fps, H.264, 0.4 MB. Six clips:
  1. Scrivania – guarda a destra
  2. Scrivania – si gira a guardare dietro
  3. Reazione – pensa
  4. Reazione – distratto, poi sorride
  5. A letto col telefono – video orizzontale
  6. Dorme – si gira sulla schiena
- **`sova_montage.mp4`** (this commit; its SHA is the one this STATUS.md is committed with): 2 min 18 s, 1280x720, 30 fps, H.264, 4.4 MB, 21 clips.
  - Scrivania ×5: attende, guarda a destra, guarda giù poi a destra, guarda avanti poi a sinistra, si gira a guardare dietro.
  - Reazioni ×6: pensa, distratto poi sorride, frustrato, si guarda intorno, si stira il collo, distoglie lo sguardo.
  - A letto col telefono ×4: video orizzontale, video verticale, scrive, alza il telefono sul viso (×2).
  - Sonno ×6: si siede e si sdraia (×3), sul fianco, si gira sulla schiena (×2), sulla schiena, si sveglia e si riaddormenta (×2), si alza dal letto (×2).
- Both videos:
  - one 3/4-front camera per clip, a key light on his face, neutral background;
  - the desk clips sit on a plain grey block at his seat height (0.58 m), not the room chair;
  - the bed clips lie on a plain mattress block at the measured support height;
  - "×2/×3" = played faster to keep the long transitions short;
  - the desk clips in the videos are the 0cd8768 bake (before the arm smoothing below).

## Desk: hands on the thighs — DONE (COORD's note, G14's finding)
**For G14: `docs/qa/sova/desk/*.glb` (this commit) are the final bake; pull them.** `desk/index.json` lists all 19 clips with their hand heights, mesh test and room numbers.

The cause:
- The chair fit's sleeve clearance swung the arms out from the shoulder (up to its 24° cap) and lifted the hands.
- In the dedda57 bake the hands sat at 0.92 m (body frame), against `room_seated_idle`'s 0.78. In the page that put them on the desk's front edge and into the bottle.

Now, per frame:
1. The chair fit swings an arm out at most 8°; the sleeves are allowed 1.5 cm on the hoodie (cloth on cloth).
2. After it, each resting hand goes across to over the top of his thigh and down onto the trousers (`fit_rest.py`; in the idle/look clips both hands always rest).
3. Then any of the hand still inside him is pushed out along the surface (`fit_hands.py`).
4. Two-bone IK throughout, the hand keeps its orientation, smoothed; nothing moves where it isn't needed.

Results:
- **Idle / look clips** (desk_look_behind, neutral_1/3/5, look_* ×4, seat_looking_* ×5, neck stretching), whole clip, every 2nd frame:
  - hands at **0.74–0.80 m** (reference 0.78);
  - **0 vertices of either hand inside his body** (trouser/hoodie mesh test);
  - room: chair **0**, desk **0**, other furniture **0**, floor **0**, seat gap +0.2…5.0 cm (never under), soles 0.2–4.8 cm on the floor.
- **Gestures** (performer arms):
  - thinking (hand to the chin, 1.21 m): 1 frame of 125 at 1.2 cm.
  - frustrated V1 (hand at the hip, 0.87 m): 0.
  - frustrated V2: the left hand 1.9 cm into the hoodie at the hip, 76 of 113 frames.
  - distracted-then-smile (arms crossed, 1.06 m): each hand 3.8–5 cm into the other sleeve, every frame (crossed arms in baggy sleeves).
  - Room: all 0 / clear.
  - These raised hands can still meet the desk edge if the page plays them close to it.
- desk_start_01 (the sit-down): not measured in the room as a loop; it belongs to the stand→sit step.
- The room pass's "hands in thighs" row reads 100–350 frames at 10–13 cm for every clip now: its capsule (radius up to 15 cm, sized from the baggy trousers) counts a hand resting ON the cloth as inside, as its README warns. The mesh test above is the honest one.

Sheets: `sova_desk_seated.jpg`, `sova_desk_reactions.jpg` (front + side, 8 frames each).

## Desk group: seated set done (`desk/*.glb`, `desk/index.json`, `sova_desk_seated.jpg`)
- Measured **in the room** with the room's own `contact_pass.mjs`: each clip played as the desk-watching clip, in a local symlinked copy of `web/` (nothing in `web/` changes), over the whole clip, every frame.
- Every clip went through the shin fit + our chair's fit.

| clip | len | chair | desk | other furniture | floor | seat gap (cm) | soles (cm) | hands in thighs | sleeves in hoodie (fit) |
|---|---|---|---|---|---|---|---|---|---|
| desk_look_behind | 9.2 s | 0 | 0 | 0 | 0 | 0.2…4.8 | 0.2–4.8 | 0 | 0.6–0.7 cm |
| neutral_1 / _3 / _5 | 6.7 s | 0 | 0 | 0 | 0 | 0.3…4.9 | 0.2–4.8 | 0 | 0.6–0.7 |
| look_right_idle | 6.7 s | 0 | 0 | 0 | 0 | 0.3…4.9 | 0.2–4.8 | 0 | 0.9 (65 frames over 0.8) |
| look_left_idle | 6.7 s | 0 | 0 | 0 | 0 | 0.4…5.0 | 0.2–4.8 | 0 | 1.0 (20 frames over) |
| look_down_to_right | 10 s | 0 | 0 | 0 | 0 | 0.3…4.9 | 0.2–4.8 | 0 | 1.1 (R, 300 frames over) |
| look_front_to_left | 10 s | 0 | 0 | 0 | 0 | 0.4…5.0 | 0.2–4.8 | 0 | 0.8 |
| desk_start_01 | 6.0 s | sit-down transition: not measured as a loop (it is the stand→sit step) | | | | | | | 0.5–0.7 |

- Baseline, Mixamo's own `room_seated_idle` in the same pass: chair 0, desk 0, seat −0.5…4.1 cm, soles 0.2–4.8 cm.

Verdict (seated):
- **Clean on our chair and desk.** Upright, feet planted, loops seamless.
- But they are pose-pack loops: they breathe and turn the head, they don't act.
- The hands rest over the thighs with the elbows a little out (the sleeves kept off the hoodie).
- Suggested slots (`desk/index.json`): idle_a/b/c = neutral_1/3/5, attend = look_right_idle, gesture_a/b = look_down_to_right / look_front_to_left (or desk_look_behind).

Action & Reactions (standing, laid on the seated base):
- First bake: the performers' standing arms hung at his sides, swung out by the sleeve fit (a scarecrow on a chair; that was also where the chair contacts came from: hands 1.2–3.4 cm into the chair in looking_away / looking_right).
- They are being rebaked:
  - the look clips get their arms from the seated base;
  - the gesture clips (thinking chin, frustrated, distracted smile) keep the performer's arms;
  - all are tipped 10° forward (they leaned back).
- The numbers follow.

## Sleep group: first pass done (`sova_sleep.jpg`, `contact_sleep.jsonl`)
Clips:
- **Machinima bed scene.** Identified from the motion (the filter did not keep the names):
  - SITTING and LYING ON BED (24.4 s): sits on the edge, then lies down curled on his side; it ends exactly on V1's pose.
  - SLEEPING LOOP V1 (6.7 s): on his side, knees drawn up.
  - V1 TO V2 (14.4 s): rolls onto his back. It starts exactly on V1 and ends within 8° of V2.
  - SLEEPING LOOP V2 (6.7 s): on his back, an arm up.
  - The bed-object clips (9–41 channels, no body) are not retargeted.
- **Animation Pack #7:**
  - [01] sleeping idle (6 s loop, on his back);
  - [02] wakes up, sits up and lies back down (12 s, returns to the start pose);
  - [03] wakes up, swings his legs off and stands (15 s).
- All the loops are seamless (first = last frame within 0.2°).

Measured over the whole clip (mattress = his lowest torso point; resting hands cleared with `fit_hands.py`):

| clip | torso on the mattress | legs vs the mattress | hands in his body after the fit |
|---|---|---|---|
| sleeping_loop_v1 | constant (0 cm range) | 2.5 cm under (his knees) | 0 |
| sleeping_loop_v1_to_v2 | 1.1 cm range | −2.1…+1.4 cm | 0 |
| sleeping_loop_v2 | constant | 0.7–1.0 cm over | 0 |
| sleeping_idle (P7 01) | constant | 0.4 cm over | 1.6 cm (L hand on his thigh) |
| wake_up_and_sleep_again (P7 02) | 1.0 cm range | 0.2–1.5 cm over | 3.6 cm (L hand pushing on his thigh as he sits up) |
| sitting_and_lying_on_bed | sits up 41 cm, lies back down | feet on the floor while seated | 1.7 cm |
| wake_up_and_leave_bed (P7 03) | gets up | feet on the floor at the end | 5.2 cm (L hand pushing on his thigh to stand) |

- The "hand on the thigh" residues are the pushes when he sits up or stands (as in the Mixamo transitions).
- No support fit was applied to the two clips with a standing part: pinning the torso to the mattress put the standing part 43 cm through the floor.
- The bed placement in the room (our mattress top is 0.82 m, the Sims bed was lower) is the page's step, like the existing bed clips.
- **Worth the most:** the two machinima loops + V1→V2 (a real side → back roll), and Pack 7 [03] (a full get-up).

## Desk group: method
Pipeline:
1. Retarget, with the phone Ver. 8 calibration.
2. **Shins turned forward under the knees** (`fit_shins.py`, new).
3. Our chair's fit (`kimodo/mx_fit.py`, seated defaults + `seatOrigin`), written as `mh_mx` GLBs.
4. The room's own `contact_pass.mjs`, with each clip as the desk-watching clip in a local symlinked copy of `web/` (nothing in `web/` changes).

Found on the first clip:
- The Sims performers tuck their feet back under the seat (ankles 9–22 cm behind the knees), and on our chair the calves went 3.7 cm into it (426 vertices, every frame).
- With the shins turned forward to 3 cm behind the knee (the Mixamo seated idle has 2.4 cm), DESK - LOOK BEHIND measures: chair **0**, desk **0**, other furniture **0**, floor **0**, seat gap +0.2…4.8 cm, soles 0.2–4.8 cm on the floor, hands in thighs **0**.

Clip set:
- **Seated (Sitting V6):** DESK START 01 (sit-down transition, plays once), DESK LOOK BEHIND, Neutral [1]/[3]/[5], LOOK RIGHT/LEFT idle, LOOK DOWN→RIGHT, LOOK FRONT→LEFT.
  - Neutral 1≈2, 3≈4, 5≈6 (1–3°), and Bored N = Neutral N (face only).
  - The three are one seated body with the head straight / turned ±65° and small arm moves.
- **Action & Reactions:** all standing (hips 1.0 m). Their upper body is laid on Neutral 1's seated hips and legs (`layer_seated.py`; the torso keeps the performer's upright world orientation).
  - Clips: [MOCAP] looking away, looking around V1/V2, looking left/right, neck stretching; thinking (chin), frustrated V1/V2, distracted then smile.
  - "LAUGH SIT" is in CLIP_NAMES.txt but not among the package's 28 clips.
- 19 clips are rebaking now; the room numbers and the sheet come next.

## Phone V12
- V12 holds every Ver. 8 clip with **identical curve data**, renumbered: Ver. 8 set_N = V12 set_(N+9), e.g. WATCHING A/B = V12 set_47–51, TYPING = 54, IN BED 03 A = 13. All Ver. 8 results stand.
- New in V12:
  - ANNOYING BUSYBODY A/B, SHOWING PHONE ×4, HANDING THE PHONE ×2: two-person scenes, not used.
  - **IN BED 04 - IN A CALL** (16.7 s). Measured: legs 50–52 cm below the torso's support (feet on the floor, like IN BED 01/03), phone at the ear.
  - → **discarded** by your rule for the feet-on-the-floor bed clips.

## Bed / phone (0428596, then 4e862ec)
- `sova_best4.glb` now carries the **resting-hand clearance** (`fit_hands.py`): where a resting hand is more than 5 mm inside his body, the wrist moves out along the body normal by the depth + 5 mm (two-bone IK, hand orientation kept, smoothed); nothing moves elsewhere.

| clip | resting hand before → after | moved |
|---|---|---|
| set_38 WATCHING A landscape | 2.3 → **0** cm | 2.8 cm |
| set_39 WATCHING A portrait | 2.3 → **0** | 2.8 |
| set_45 TYPING | 1.9 → **0** (47 frames moved) | 2.4 |
| set_4 IN BED 03 A | 3.6 → **0** (60 frames) | 4.1 |

- Phone vs face is still clear (gap 8.3–9.7 cm); eye→screen unchanged (25–26 cm, 6–15°).
- Not fixable this way:
  - The hand tucked *under the head* (WATCHING B set_40–42, IN A CALL B set_43): moving it along the normal made it worse (8.8 → 9.5 cm after moving 13–18 cm), so those keep the unfitted arm. They stay "not recommended".
  - IN BED 03 B (set_5): 3.5 → 2.9 cm.
- Dropped by your rule: IN BED 01/02/03-across, i.e. set_11–15 and set_5 (feet on the floor); IN BED 04 too.
- Kept: set_4 (IN BED 03 A), set_38/39 (WATCHING A), set_45 (TYPING).
