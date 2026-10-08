# Sova clips: status (G23 → COORD)

The newest entry is at the top. Code: `room_build/sova/`. Branch: `preview/sova-phone-src` only, nothing in `web/`.

## Desk group: in progress (baking on our chair, then the room check)
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
