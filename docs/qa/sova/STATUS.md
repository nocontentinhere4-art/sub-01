LATEST: test fixes for main 01f3a0d → commit 46f6e71 on preview/sova-phone-src (origin/main merged in first, 5fc23a0; the fix is its own commit, cause in its message). The 3 tests + test_interactive: 20 passed; smoke_demo: SMOKE OK. The patch file in docs/qa/test-fixes/ is the same change.

## Test fixes on main 01f3a0d (all 3 from the interactive merge)
- **One cause for all three:**
  - The merge put the per-connection viewer state (`viewer_fp`, `viewer_ids`, `viewer_addr`) in `Live.__init__`.
  - The tests build a Live with `init_sockets()` only (`bare_live`).
  - So `ws_handler` raised `AttributeError` (then `votes` in `audience_hello`), aiohttp closed the socket, and the client read CLOSED (257).
- **test_stream_per_viewer_under_3_kb_s:** failed the same way, timing out because its viewers never joined. **It was not the bandwidth**: with the fix it passes unchanged, `aud`/`rx` included.
- **Fix** (`live_server.py` only, no test changed, `web/room.html` untouched):
  - the three maps move to `init_sockets()`;
  - `audience_hello()` returns None without vote state, as the hello already does for music and replies.
- **Run:** test_feed + test_neurons3d + test_interactive 49 passed; smoke_demo SMOKE OK.



## MATTINA set — 0248b96
**What it is:** the exact GLBs used as MATTINA in `alive_ab.mp4`, byte for byte (taken from git at 797355c^). Same filenames as `desk/` and `bed/`; this morning's `index.json` alongside.

**Source per clip** (all had a morning version, none needed the pre-hands fallback):
- **8051d88**, the armrest fix: seat_thinking_touching_chin (v6), seat_feeling_frustrated_v1 (v5).
- **e579d71**, the chess win candidates: seat_happy, seat_smiling.
- **b578db3**, desk v3: desk_look_behind, desk_start_01, look_down_to_right, look_front_to_left, look_left_idle, look_right_idle, neutral_1, neutral_3, neutral_5, seat_feeling_frustrated_v2, seat_looking_around_v1, seat_looking_around_v2, seat_looking_away_idle, seat_looking_left, seat_looking_right, seat_neck_stretching_idle.
- **7bf7c8c**, the bed: bed_phone_lift, bed_phone_typing, bed_phone_watch_landscape, bed_phone_watch_portrait, sleep_back, sleep_back_idle, sleep_roll_to_back, sleep_side.

**Quick checks.** These are the numbers already measured on these same files; none is worse than this morning, because they *are* this morning's:
- **Hands in his body (mesh):** 0 everywhere except sleep_back_idle, left hand 1.6 cm under the head.
- **Chair, desk, room:** 0 in this morning's room passes. Thinking v6 comes within 1.4 cm of the chair on 4 frames (2 cm test); frustrated V1 v5 has nothing within 2 cm.
- **Pose:** no T-pose in this morning's montage or the A/B stills.

**Known, as this morning:**
- the fingers are the Sims retarget (the twist the owner first saw);
- in sleep_back_idle the feet are 5.6 cm past the mattress end: place that slot 6 cm toward the headboard (bed/index.json `place_note`).


## ROUND 4 "alive" — A/B/C: `alive_ab.mp4` (+ `alive_ab.jpg` stills)
The four clips: neutral_1, thinking (chin), seat_happy, bed_phone_watch_landscape.
- **MATTINA:** this morning's GLBs (before 797355c).
- **ORA:** 797355c.
- **NUOVO:** `fix_alive.py`, built on this morning's GLBs:
  - **body untouched:** no smoothing or limit beyond the morning bake (b578db3/8051d88);
  - **fingers:** the clip's **own flexion per joint**, rebuilt on Mixamo's relaxed hand as a pure curl. That removes the 23–47° roll of the left-hand fingers, nothing bends backwards (the curling branch), and the clamp is the owner's **p1–p99** only, with **no rate limit**;
  - **phone hand:** round 2's grip;
  - **wrists and forearms:** as baked, only single-frame flips undone (none found in the 4);
  - **nothing inside his body:** moved only on frames that go in, eased (fit_hands.clear).
    - In neutral_1, seat_happy and bed_phone the resting right hand's curled fingers sit 2.0–2.6 cm into the thigh/belly **on every frame**, so the push-out (2.5–3.1 cm) is on every frame there.
    - The chin hand in thinking: 89 of 250 frames.

**My look at the video:** NUOVO has the morning's body motion (same posture as MATTINA in every frame) and cleaner fingers than MATTINA. ORA's stiffened wrists are gone. The chin hand is close to MATTINA. Motion can't be judged from stills; the owner's verdict decides.


# Sova clips: status (G23 → COORD)

The newest entry is at the top. Code: `room_build/sova/`. Branch: `preview/sova-phone-src` only, nothing in `web/`.


## HANDS, round 3: all 30 deliverables — 797355c
Contact yes, inside no (COORD):
- Where the source hand touched his body within 1 cm (any frame), the wrist pulls it to 2.5 mm off along the body normal, two-bone IK.
- Anything inside is pushed out: the other arm counts as body.
- A hand that touches the face (the chin's skin follows Neck/Head) keeps **the clip's own finger flexion**, joint by joint, clamped into the owner's range and speed; all other hands take the owner's median.
- Wrist roll over 20° moves into the forearm (exactly, the hand's world turn kept): that was the lump in the sleeve.

Per clip, from the fit (`hfix` logs), left / right hand:

| clip | fingers | contact gap where the source touched him (cm, min…max; − = inside) | left inside him (cm) | launch |
|---|---|---|---|---|
| desk_look_behind | relaxed / relaxed | 0.0…0.4 / 0.2…0.5 | 0.0 / 0.0 | ok |
| desk_start_01 | relaxed / relaxed | -0.4…0.8 / -0.3…0.9 | 0.4 / 0.3 | ok |
| look_down_to_right | relaxed / relaxed | 0.0…0.5 / 0.2…0.5 | 0.0 / 0.0 | ok |
| look_front_to_left | relaxed / relaxed | 0.2…0.3 / -0.1…0.6 | 0.0 / 0.1 | ok |
| look_left_idle | relaxed / relaxed | 0.2…0.3 / 0.1…0.4 | 0.0 / 0.0 | ok |
| look_right_idle | relaxed / relaxed | 0.0…0.5 / 0.2…0.5 | 0.0 / 0.0 | ok |
| neutral_1 | relaxed / relaxed | 0.1…0.5 / -0.0…0.4 | 0.0 / 0.0 | ok |
| neutral_3 | relaxed / relaxed | 0.1…0.5 / -0.0…0.5 | 0.0 / 0.0 | ok |
| neutral_5 | relaxed / relaxed | 0.1…0.5 / -0.0…0.5 | 0.0 / 0.0 | ok |
| **seat_distracted_then_smile** | relaxed / relaxed | -3.0…-0.6 / -2.9…2.4 | 3.0 / 2.9 | **DROP for launch** |
| seat_feeling_frustrated_v1 | relaxed / relaxed | 0.2…0.5 / 0.1…1.3 | 0.0 / 0.6 | ok |
| seat_feeling_frustrated_v2 | relaxed / relaxed | 0.1…0.6 / 0.2…0.5 | 0.0 / 0.0 | ok |
| seat_happy | relaxed / relaxed | 0.0…0.5 / -0.0…0.5 | 0.0 / 0.0 | ok |
| seat_looking_around_v1 | relaxed / relaxed | -0.1…0.7 / -0.4…0.8 | 0.1 / 0.4 | ok |
| seat_looking_around_v2 | relaxed / relaxed | -0.1…0.7 / -0.1…0.7 | 0.1 / 0.1 | ok |
| seat_looking_away_idle | relaxed / relaxed | 0.0…0.6 / 0.0…0.5 | 0.0 / 0.0 | ok |
| seat_looking_left | relaxed / relaxed | 0.1…0.6 / 0.0…0.6 | 0.0 / 0.0 | ok |
| seat_looking_right | relaxed / relaxed | 0.0…0.6 / -0.5…0.7 | 0.0 / 0.5 | ok |
| seat_neck_stretching_idle | relaxed / relaxed | 0.1…0.5 / 0.2…0.4 | 0.0 / 0.0 | ok |
| seat_smiling | relaxed / relaxed | -0.0…0.6 / no contact in source | 0.0 / 0.0 | ok |
| seat_thinking_touching_chin | own curl (hand to face) / relaxed | -0.1…0.8 / 0.2…0.3 | 0.1 / 0.0 | ok |
| bed_phone_lift | phone grip (still) / relaxed | – / -0.4…1.0 | – / 0.4 | ok |
| bed_phone_typing | phone grip (still) / relaxed | – / -0.0…0.7 | – / 0.0 | ok |
| bed_phone_watch_landscape | phone grip (still) / relaxed | – / -0.0…0.5 | – / 0.0 | ok |
| bed_phone_watch_portrait | phone grip (still) / relaxed | – / -0.0…0.5 | – / 0.0 | ok |
| sleep_back | relaxed / relaxed | 0.0…0.3 / no contact in source | 0.0 / 0.0 | ok |
| sleep_back_idle | relaxed / relaxed | 0.0…0.5 / 0.1…0.5 | 0.0 / 0.0 | ok |
| sleep_roll_to_back | relaxed / relaxed | -0.3…1.0 / no contact in source | 0.3 / 0.0 | ok |
| sleep_side | relaxed / relaxed | no contact in source / no contact in source | 0.0 / 0.0 | ok |
| **sleep_wake_and_back** | relaxed / relaxed | -1.7…2.4 / -0.5…1.3 | 1.7 / 0.5 | **DROP for launch** |

Drop for launch:
- **seat_distracted_then_smile:** crossed arms. Pulled out of the other arm, the hands come apart (one hangs in the air) and stay 3 cm inside the sleeves; the original had them 4–5 cm inside each other's sleeves. It needs an arms-crossed pose built for our sleeves.
- **sleep_wake_and_back:** hands under the head still 1.7 cm inside him, and the feet 5.6 cm past the mattress end.

Borderline, kept:
- desk_start_01: 0.4 cm inside.
- seat_feeling_frustrated_v1, right hand: up to 1.3 cm off where it touched.
- bed_phone_lift, right hand: 0.4 cm inside.
- sleep_roll_to_back, left hand: 0.3 cm inside.

Looked at in the close-ups:
- thinking: the chin rests on the thumb and index, fingers curled from the clip, no sleeve lump;
- neutral / happy: relaxed hands;
- phone: the grip closes round it.

## HANDS, round 2: the owner's hands as the target — close-up before/after: `sova_hands_before_after.mp4` (+ `.jpg` frames), 1a449e5

**Target:** COORD's `docs/qa/hands/owner_hands_ref.json`. The same angles are computed on our skeleton from the joint positions (`room_build/sova/owner_cmp.py`):
- MCP / PIP / DIP flexion, each the angle between consecutive bone vectors (the wrist→knuckle vector, then each phalanx);
- side bend;
- palm spread;
- wrist bend (forearm vs wrist→middle knuckle).

**Allowed range per joint:** his p5–p95, over **both** hands pooled, because MediaPipe's left/right labels are as seen. Speed: his p95 frame-to-frame flex change.

**Fix** (`fix_hands_pose.py`, round 2):
- Every finger joint is solved to **his median flexion** (a turn about the bone's curl axis, on the curl side).
- Plus 0.3 × the clip's own curl, **clamped into his p5–p95**, and rate-limited to **his p95 speed**.
- The phone hand: Mixamo's phone grip with each joint pushed into his range, held still.
- Wrists: twist / flexion / deviation clamped as in round 1, then the bend clamped to his max (62°).
- Then the hands are cleared out of his body (`fit_hands.clear`, the IK keeps the hand's world turn) and the wrist re-clamped, twice. **Nothing is left inside him: 0.0 cm** in all four clips.

**% of frames out of his range per finger** (thumb, index, middle, ring, pinky; any joint, side bend or speed), before → after. This is also in the video, on each half:

| clip | left hand | right hand | wrist out of range, L / R | hands in his body |
|---|---|---|---|---|
| neutral_1 | 100 100 100 100 0 → **0 0 0 0 0** | 100 100 100 0 0 → **0 0 0 0 0** | 22 / 80 → **0 / 0** | 0 → 0 |
| thinking (chin) | 15 85 94 92 89 → **0 0 0 0 0** | 100 100 100 0 100 → **0 0 0 0 0** | 5 / 0 → 5 / 0 (below his min: a straighter wrist than he ever has; not clamped) | 0 → 0 |
| seat_happy (win) | 100 100 100 100 0 → **0 0 0 0 0** | 100 100 100 0 0 → **0 0 0 0 0** | 92 / 78 → **0 / 0** | 0 → 0 |
| bed_phone_watch_landscape | 100 100 100 0 0 → **0 0 0 0 0** (grip) | 100 0 0 0 0 → **0 0 0 0 0** | 0 / 0 → 0 / 0 | 0 → 0; fingers in the phone ≤ 0.4 cm |

Not fixable by a pose:
- **Palm spread is out on 100% of frames, before and after.** On our skeleton the index and pinky knuckles sit 56° (L) / 46° (R) apart as seen from the wrist joint, in the rest pose; he has 17–42°. That is the rig's proportions (the knuckle joints are fixed offsets from the hand bone), not a pose; it would take moving the joints in the skin.

Seen in the close-up:
- The resting hands relax: no claw, no splayed fingers.
- The phone hand closes round the phone.
- **Regression:** in thinking, the chin hand's fingers are now his relaxed desk median, so the index points off the chin instead of touching it. The gesture-specific shape is lost. If that matters, the chin frames need their own target (e.g. a closer curl from the clip, CURL 1.0 on that hand), not the desk median.

Next, running now: the same fix on all 30 deliverables (21 done), all of them measured (the table goes here), the GLBs replaced in `desk/` and `bed/`, and the full montage re-rendered.

## HANDS (top priority): diagnosis done, fix built — close-up before/after and montage rendering, numbers to follow in this section

Measured per frame on our character (`room_build/sova/hand_qa.py`), against Mixamo's own clips in `web/room/mh_mx` (room_seated_idle, mx_typing, phone, mx_sitting_talking). Values are median / 95th percentile / max over the clip, degrees off the rest pose, worst finger.

| | finger twist about its own axis | finger spread at the knuckle | PIP/DIP side bend | finger speed | wrist flexion | forearm roll vs upper arm |
|---|---|---|---|---|---|---|
| Mixamo references | 2–19 | 9–50 (the phone grip 35–48) | 3–21 | 56–860 °/s (they move: taps) | 3–67 | 0–27 |
| Sova desk (neutral_1, look_left, happy) | **23–31 (L hand)** | 9–17 | 5–9 | **0: frozen** | **61–76 (limp)** | **33–74** |
| Sova thinking (L) | 19–33 | **161: a finger bent backwards** | 15–22 | 156–243 | 52–61 | 48–57 |
| Sova bed (phone, sleep) | **23–47 (L)** | 12–47; **lift R 144** | 9–29 | 0 (lift R 108–175) | 1–37 | 27–83 |

Diagnosis:
- **The Sims fingers are the main fault.** The left hand's fingers are rolled 23–47° about their own axis in every clip; two clips bend a finger the wrong way at the knuckle (161°, 144°). The fingers are also frozen (0 °/s), a held claw.
- **The wrists hang**: desk clips are flexed 61–76° against 43° on Mixamo's seated hands on the thighs.
- **The forearm rolls 50–80°** against the upper arm (Mixamo 0–27). It is within a real pronation range (±80–90) but twists our elbow skin.

The fix (`room_build/sova/fix_hands_pose.py`, on the baked GLBs, nothing else in the clip changes):
- **Fingers are not retargeted any more.** Every finger bone takes Mixamo's relaxed seated hand (room_seated_idle, each bone's median), plus 0.3 × the clip's own curl about the bone's curl axis (clamped ±15°). The thumb takes the relaxed pose only.
- **The phone hand** (bed_phone_*) takes Mixamo's phone grip (room_phone, same side), still. Its wrist is left as baked, because the phone rides on it.
- **Wrists are clamped**: flexion ±60°, deviation ±40°, roll at the wrist ±45°, and forearm roll ±80°.

## COORD's three points — armrest fix, our bed, chess "win" (8051d88; bed GLBs from 7bf7c8c)

### 1. Armrest: thinking (v6) and frustrated V1 (v5) — GLBs replaced in `desk/`, G14 please re-measure
Cause, now found: in both clips, a standing performer's hand hangs **beside his hip**.
- Thinking: the right hand the whole clip, and the left one after 5.3 s, at x 0.23–0.33 m from the centre, past the thigh's outer edge (0.23), 0.70 m high, level with the hip. That is the armrest.
- `fit_rest` used to snap such a hand to the nearest thigh-top vertex, which is the hip's outer edge, so it never moved.

Fix (`fit_rest.py`, rows in `desk_rows.json`):
- `REST_FWD` 0.15: resting targets only on the thigh top at least 15 cm forward of the hip joint, so the hand goes onto the lap.
- `REST_LOW`: a hand whose lowest point drops below this rests as well (thinking 0.9 m, frustrated 0.8 m). The chin hand is at 1.2 m and is left alone.
- Then, as in v3: `fit_hands`, the arm corrections smoothed over time (`smooth_fit`), and here the fingers smoothed too.

Whole clip, 30 fps, my room pass (`contact_pass.mjs`, the clip as `room_seated_idle`):

| clip | chair / desk / other | within 2 cm of the chair (hands) | end pose | hands in his body | biggest move per frame |
|---|---|---|---|---|---|
| thinking v3 | 0 | 6 frames (5.0 s, 7.4 s) | R hand by the hip at 0.70 m | 0 | 62 mm |
| **thinking v6** | **0** | 4 frames at 7.3–7.4 s, closest 1.4 cm | **both hands on the thighs** (x 0.11–0.24, 15 cm forward) | **0** | 67 mm |
| frustrated V1 v3 | 0 | 5 frames (6.5 s) | L hand by the hip | 0 | 17 mm |
| **frustrated V1 v5** | **0** | **0** | L hand on the thigh; R on his hip (the gesture), 0.84 m | **0** | 14 mm |

The thinking fingers (G14's 62 mm/frame over 5 frames) are **not jumps**: they are the two gestures, lap→chin at 0.2–0.6 s and chin→lap at 5.2–5.4 s, each a smooth bell (frames, mm: 8 7 6 14 25 36 49 60 66 67 63 57 49 42 37 …).
- The performer's own peak is 54 mm/frame; ours is faster because on our seated body the lap↔chin path is longer.
- There is no single-frame spike left anywhere (finger smoothing is on).
- Slowing the gesture would be a time-warp of the clip; I didn't do that. Say if you want it.

I still can't reproduce G14's "90 vertices in the chair": my pass found 0 there in v3 too. **G14: please re-measure `desk/seat_thinking_touching_chin.glb` and `desk/seat_feeling_frustrated_v1.glb` at 8051d88.**

### 2. Bed and sleep on our bed — `bed/*.glb` + `bed/index.json`, `sova_bed_sheet.jpg`, `sova_bed_quick.mp4` (640×360, 37 s)
Nine slots:
- `bed_phone_watch_landscape`, `bed_phone_watch_portrait`, `bed_phone_typing`, `bed_phone_lift` (set_38/39/45/4)
- `sleep_side`, `sleep_roll_to_back`, `sleep_back`, `sleep_back_idle`, `sleep_wake_and_back` (Pack 7 SLEEPING LOOP V1 / V1→V2 / V2, idle, wake-and-back)

Fit (`bed_build.py`): his lowest torso point over the clip on the mattress top less 1.5 cm give, played as the page's lie clip (`bedPlace`: head toward the pillow, −x).

Room pass, each clip as the lie clip on a scratch copy of the page:
- **bed / floor / desk / chair / other = 0 in all 9**; resting lowest point 0.834.
- Extents in the room (index `extents_m`): inside the mattress at the head end and both sides; the wall (z 1.6) is ≥ 22 cm away.
- **Exception:** `sleep_back_idle` and `sleep_wake_and_back` have the feet **5.6 cm past the mattress end**. Fix in the page: place those two slots 6 cm toward the headboard (BED.hips x −0.06). It can't be done inside the clip, because `bedPlace` re-anchors the hips.
- The legs capsule row (74/195/361 frames in lift, back_idle and wake) is the baggy-trouser capsule; the mesh extents above are the honest test.

Hands and phone:
- Hands in his body after the fit: 0, except sleep_back_idle (L 1.6 cm) and sleep_wake_and_back (L 3.6, R 1.3 cm): hands under the head, left as they are.
- Phone clips: the phone never touches his face (gap 8.3–9.7 cm); fingers in the phone ≤ 0.4 cm; eye→screen 25–26 cm, 6–15° (lift 21–68 cm).
- The phone is **not** in the GLBs. Each phone entry in `index.json` gives its grip under `mixamorig:LeftHand`: translation (cm), rotation, scale 100, box 0.008×0.150×0.072 m, as `build_glb.mjs` builds it. The video uses GLBs with it built in.

Not fitted: `sitting_and_lying_on_bed` and `wake_up_and_leave_bed`. They are transitions, and need the page's bed-edge placement.
Not used: the IN BED 01/02 calls and IN BED 03 B (across the bed, feet on the floor), and IN BED 04.

### 3. Chess "win": two proposals (`sova_win_candidates.jpg`)
- **`desk/seat_happy`: recommended.** 4.0 s, seated, a pleased sway. Room pass 0 (nothing within 2 cm of the chair), hands in his body 0, max 7 mm/frame. Added to `desk/index.json` (slot `chess_win`).
- `desk/seat_distracted_then_smile`: the stronger "satisfied" read (a smile after looking away), but 7.5 s with the arms crossed. Use it if the win can be longer.
- Not `seat_smiling` (5.2 s): it reads as talking, not winning, with a wide right-arm gesture (fingers 41 mm/frame). Its room pass is 0 too; it is in the index for reference.

## Desk v3: elbow jumps smoothed (G14's findings) — GLBs updated, pull them
G14 measured the 0cd8768 bake per frame:
- forearms jumping 50–150 mm in a frame (`room_seated_idle`: 14 mm);
- loop seams 29–41 mm.

The cause was the fits, not the clips: the retargeted motion moves at most 0–35 mm per frame, but the chair fit's sleeve swing and the hand fits solve each frame on its own.

The fix (`smooth_fit.py`):
- only the fits' correction to each arm bone (`q_final · q_source⁻¹`) is smoothed over time: Gaussian σ = 0.2 s, wrapped round for the loops;
- then the hands are cleared out of his body again, and smoothed lightly (σ = 0.1 s).

Whole clip, every bone, 30 fps (`desk/index.json`, `desk/hands_mesh.jsonl`):

| clips | biggest move per frame | loop seam | hands (median) | hand inside his body (mesh) |
|---|---|---|---|---|
| neutral_1/3/5, look_* ×4, desk_look_behind | **4–10 mm** (was 50–132) | **0–3 mm** (was 29–41) | 0.74–0.78 m | **0** |
| seat_looking_* ×5, neck stretching | 15–34 mm, the head (the performer's mocap) | 2–39 mm, the head: these mocap clips do not loop in the source, play them once | 0.75–0.81 m | **0** |
| thinking | 62 mm, a fingertip at 0.27 s (the hand flies to the chin) | – | L 1.19 m (chin) | 0 |
| frustrated V1 / V2 | 17 / 23 mm | – | 0.79–0.87 m | 0 |
| distracted then smile | 2 mm | – | 1.06 m (crossed) | crossed arms in each other's sleeves, 3.8–5 cm |

Not fixed:
- G14's second finding, **fingers into the chair** in frustrated V1 (hands to the hips, from 0.2 s) and thinking (right hand, ~8.6 s). It is at his sides (the armrests), and my room pass does not see it (it measured 0 for the chair). Both are standing performers' hands on a seated body.
- Suggestion: keep frustrated V1 out of the desk slots (or use V2, not measured by G14 yet); for thinking, trim the end (after ~8 s) or accept it.
- I can fix them once G14's chair test (`qa.body`) is reproducible here.

## Videos
- **`sova_quick.mp4`** (commit ba8d006): 38 s, 640x360, 24 fps, H.264, 0.4 MB. Six clips:
  1. Scrivania – guarda a destra
  2. Scrivania – si gira a guardare dietro
  3. Reazione – pensa
  4. Reazione – distratto, poi sorride
  5. A letto col telefono – video orizzontale
  6. Dorme – si gira sulla schiena
- **`sova_montage.mp4`** (commit 92d7f57): 2 min 18 s, 1280x720, 30 fps, H.264, 4.4 MB, 21 clips.
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
