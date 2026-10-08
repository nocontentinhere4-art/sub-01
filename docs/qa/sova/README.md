# SovaSims "Phone Animations" on our character: evaluation (G23)

**Internal evaluation only.** SovaSims' public terms forbid converting the animations to other games and redistributing
them without permission, and the owner is dealing with the author (`mocap_src/sova/README.md`). Until the author's OK
is confirmed, nothing here goes into `web/`, onto main or online, and this branch (`preview/sova-phone-src`) is never merged.

Evaluated source: `SovaSims_-_Phone_Animations.package` (Ver. 8, 46 clips). The newer Phone V12 package that landed
on this branch afterwards (it adds IN BED 04) was not evaluated here; `run_all.sh` takes the package path in one place.

Files:
- `sova_best4.glb` (4.3 MB): char_v5 (`char_mixamo.glb`, 65-joint `mixamorig:*`) with 4 animations: `set_38`, `set_39`, `set_45`, `set_4`.
  - Textures are reduced to 512 px WebP and the file is meshopt-compressed.
  - Two nodes, `phone_Left` and `phone_Right`, form a generic unbranded slab (7.2 × 15 × 0.8 cm, dark body, pale screen).
  - Each animation sets the phone's grip and hides the unused one (scale 0).
- `sova_in_bed.jpg`: the 7 IN BED clips. 8 frames each, front and side, with the mattress top drawn under his torso (tan).
- `sova_watching_couch_texting.jpg`: WATCHING A VIDEO A/B (landscape/portrait), TYPING, ON THE COUCH reading/typing, TEXTING.
- `sova_best4_closeup.jpg`: head and phone close-ups of the 4 clips in the GLB.
- `contact_pass.jsonl`: the raw whole-clip numbers for all 18 clips evaluated.
- The code is in `room_build/sova/`, run with `sh run_all.sh <work dir>`. It runs on CPU in about 10 minutes; no GPU was used.

## Method

### 1. Decoding (own Python code; no proprietary tools)
- `s4clip.py` reads the DBPF 2.1 index and the zlib entries.
- It decodes the CLIP resources' S3 codec (`_pilC3S_`) from the public format description: the s3pi/s4pi `S3CLIP` reader (GPL, read for the format only; no code copied).
  - Header: tick length, frame count, curve table, indexed-float palette.
  - Curves: position = Float3, 10-bit packed per axis. Orientation = Float4, 12-bit packed per component (xyzw). Values are `value × scale + offset`, with the sign in the frame flags.
  - All 46 clips parse byte-exact to the end of the resource.
  - Every clip has 179 bones, each with a position and an orientation curve, at 30 fps.
- Bone hashes are FNV-32 of the **lowercased** bone name. The whole body matches public TS4 names:
  - `b__ROOT_bind__`, `b__Pelvis__`, `b__Spine0..2__`, `b__Neck__`, `b__Head__`
  - clavicle, upper arm, forearm, hand, and 5 fingers × 3 per side
  - thigh, calf, foot, toe
  - `b__L/R_Prop__` and the hand-dangle slots
  - The 108 unmatched bones are face, twist and helper bones; they are not used.
- Names: `set_N` maps to the English name via the snippet's `pose_display_name` keys into the locale-00 STBL.
- `dst_icons.py` decodes the pose icons (DST5 = Sims' shuffled DXT5). They were used only to read what each pose is meant to be.

### 2. Skeleton: no EA files
- **Rest offsets come from the clip itself.** The position channels are the full local translations (constant per bone), so the bone lengths are the Sims' own.
- The hierarchy is the public TS4 one. The ambiguity was where Spine0 hangs; I settled it geometrically:
  - With Spine0 under `b__ROOT_bind__`, TEXTING (set_10) stands as a human: feet 0.11 m, hips 1.01 m, head 1.66 m, facing +Z, his left at +X.
  - With Spine0 under Pelvis, the torso points into the ground.
- Axis convention found in the data:
  - Every Sims bone points along local +X.
  - The spine chain has Y = forward and Z = his left.
  - Elbow, knee and finger hinges are local ±Z, estimated from the motion data (spread ≤ 2–5° for knees and fingers, 15–20° p50 for elbows).
  - Thumbs have their own data-estimated axis.

### 3. Retarget (`retarget.py`): per-bone world-rotation transfer through anatomical frames
- Each bone gets a frame on both skeletons: primary = the bone's direction to its child, secondary = its hinge or lateral axis.
  - Sims side: constant in each bone's local frame.
  - Mixamo side: measured on the GLB's T-pose node rest. Arms are along ±X, palms down, the elbow flexes forward and the knee hinge is +X. Finger hinges are mapped through the hand's palm frame.
  - Note: the GLB's bind pose (IBM) is an A-pose. Only the node rest is used for the frames, which is correct because skinning uses joint transforms relative to the IBMs.
- Trunk and head use world up rather than the joint chain. Mixamo's Head→HeadTop leans 19° forward, and using it tipped his face back.
- Then `R_mixamo(t) = R_sims(t) · A_sims · A_mixamoᵀ · R_rest`.
- Half of the wrist twist goes into the forearm (Mixamo has no twist bones). An A/B of 0, 0.5 and 1 showed no visible difference.
- Hips:
  - The Sims hip-joint centre is scaled by k = 0.833 (hip height 0.842 m vs 1.008 m).
  - Mixamo's Hips-to-UpLeg offset is re-added through the hips rotation.
  - Fingers are retargeted (thumb, index, middle, ring, pinky; 3 joints each).
- Checked: the Python FK used for measurement matches three.js' world transforms exactly (same GLB, same frame).

### 4. Phone (generic rectangle, no brand)
- The `b__L/R_Prop__` slots are baked in world space but ride rigidly 12 cm off their hand: the std of the hand-relative offset is ≤ 0.3 mm.
- Hand choice: the slot nearest his line of sight, or the slot at the cheek for calls. The result is the left hand in every bed and watching clip, and the right hand on the couch.
- Orientation, learned from the data:
  - In all portrait viewing clips, his head's up axis lies along slot +Z and his eyes lie in a fixed direction from the slot.
  - The phone is fixed in the slot frame: long axis = slot Z (turned 90° for LANDSCAPE), screen = toward the eyes.
  - The back sits 1.2 cm off the slot, on the fingers.
- Calls (IN BED 01/02, IN A CALL): a 15 cm phone at the slot cut 2.5–3 cm into his head. `fit_phone.py` slides it back along its normal until it clears the head mesh on every sampled frame.

### 5. Measurement (`measure.py`), like the thighs gate
- It runs over the whole clip: every 2nd frame (every 4th for clips over 600 frames) and every 2nd skin vertex, with LBS skinning of the real mesh (including the hoodie, slides and socks).
- **Hands/fingers in his body:** each hand vertex is tested against the nearest torso, head, leg or other-arm vertex and its normal. Depth over 1 cm counts, and is reported per region.
- **Phone in his head/face:** head vertices inside the phone box.
- **Fingers in the phone:** hand vertices inside the box.
- **Eye → screen:** the distance, and the angle off the screen normal. The eye point is 3.5 cm above and 3 cm behind the mesh's nose tip.
- **Mattress** (lying clips): a fixed plane at his lowest torso point over the clip.
  - Reported: the torso support range over time, and the legs relative to the plane.
  - `fit_support.py` lowers the hips per frame (smoothed over 0.5 s) so that whatever he rests on touches the same plane.
  - Our body is thicker than the Sims one: lying on the hood/back vs sitting on the buttocks differed by **11–16 cm** in set_14/15/5.
- **Motion amplitude:** the head and hand path range, and the finger joint rotation range (98th percentile around the median).

## Numbers (whole clip, after the phone and support fits)

| clip | what it is | len | phone hand | eye→screen | phone in face | hands in body (> 1 cm) | free-hand fingers | motion (head / phone hand) | mattress |
|---|---|---|---|---|---|---|---|---|---|
| **set_38** WATCHING A VIDEO A, landscape | reclined on his back, knees up, phone over the face | 6.7 s | L | 26 cm, 6° | 0 (gap 9.2 cm) | R hand resting on the belly: 2.3 cm into the hoodie | 6° / 12° | 0.1 / 0.5 cm | torso constant; legs 1 cm above |
| **set_39** … A, portrait | same pose, portrait | 6.7 s | L | 25 cm, 15° | 0 (9.7) | same 2.3 cm | 6° / 12° | 0.1 / 0.8 cm | same |
| set_40/41/42 … B (landscape / happy / upset) | same, R hand **behind his head** | 6.7 s | L | 25 cm, 7–15° | 0 (8.2–8.5) | R hand **8.8 cm into the back of the head** | 0.4° / 7.5° | 1 / 0.6–0.9 cm | same |
| **set_45** TYPING | same, the right thumb types on the phone | 6.7 s | L | 25 cm, 15° | 0 (9.7) | R hand 1.9 cm (16 of 100 frames) | **26° / 44°** | 0.1 / 0.8 cm (typing hand 16.6 cm) | same |
| **set_4** IN BED 03 A | lying back **across** the bed, feet on the floor; lifts the phone over the face, lowers it to his side | 18.3 s | L | 21–68 cm, 28° median | 0 (8.3) | R hand 3.6 cm into the torso, 10 of 275 frames | 89° / 102° | 0.4 / 39.7 cm | support 0.3 cm (fit 2.2 cm); **calves hang 31–33 cm below the mattress top** |
| set_5 IN BED 03 B | lies back, sits up on the edge, texts, lies back (47 s) | 46.7 s | L | 20–68 cm, 26° | 0 (4.9) | L 4.1 cm (40/351 frames), R 2.6–3.5 cm | 47° / 61° | 62 / 81 cm | fit lowers the hips up to **15.7 cm** when he sits; calves 28–44 cm below |
| set_11/12/13 IN BED 01 idle/talk A/B | lying across the bed, phone **at the ear** (a call) | 10 s | L | (call) | 0 after a 3 cm fit | R hand on the belly **7.6 cm into the hoodie**, every frame | 0° (13: 28° / 49°) | 0.1 / 0.7 cm | calves 34 cm below |
| set_14/15 IN BED 02 idle/talk | lying back → sits up on the edge, a call | 7.7 s | L | (call) | 0 after a 2.5 cm fit | R 7.5 cm, 9 frames | 47° / 61° | 50 / 53 cm | fit up to 11.1 cm; calves 34–44 cm below |
| set_18/20 ON THE COUCH reading/typing | reclined on a couch, L hand behind the head | 6.7 s | R | 38 cm, 25° | 0 (23.5) | L hand **4.9 cm into the head**, every frame | 3° / 6° | 0.1 / 0.4 cm | n/a (no couch) |
| set_10 TEXTING | standing | 6.7 s | L | 29 cm, 32° | 0 (16.1) | 0 | 1° (L thumb 74° max) | 0.7 / 0.6 cm | n/a |
| set_35/43 IN A CALL A/B | reclined, a call | 6.7 s | L | (call) | 0 after a 2.5–3 cm fit | L 3.4–3.8 cm in the torso; set_43 R 8.3 cm in the head | 6° / 12° | ≤ 1 cm | legs 1 cm above |

Other measurements:
- Fingers through the phone: ≤ 0.4 cm in every clip, i.e. the fingertips lie on its sides.
- **The phone hand's fingers never move:** 0.0–0.1° median, 0.2° max, in every clip. The grip is frozen.

## Verdict (honest)

### Natural?
- **The watching / typing set (38–42, 45) is the motion we're missing: the boy lying on his back in bed with the phone over his face.**
  - The phone sits 25 cm from his eyes with the screen square to them (6–15°).
  - He looks at it with his head and eyes in a believable relation: his face points about 20° above the phone.
  - No phone touches the face.
- **But these are held poses, not animations.** Over the 6.7 s loop his head moves 1 mm and the phone hand under 1 cm.
  - They read as a still with breathing at most.
  - Usable as a target pose that our own idle layer breathes on top of, not as a living clip.
  - set_45 TYPING is the exception: the right thumb really types (fingers 26°/44°, hand 17 cm).
- **The IN BED clips are a different bed scenario.**
  - IN BED 01/03 lie back *across* the bed with the knees at the edge and the feet on the floor (calves 30–44 cm below the mattress top).
  - IN BED 02 sits up on the edge.
  - Our mattress top is 0.82 m, so his feet can't reach the floor. Only the upper body transfers unless the legs are re-posed.
  - IN BED 01/02 are phone *calls* at the ear, not watching.
  - set_4 is the best of them: real motion over 18 s, lifting the phone over his face and lowering it.
  - set_5 is a rich 47 s sequence, but its sit-up needs the hips moved 16 cm by the support fit, a sign that our bulkier body doesn't sit where the Sims body does.

### Fingers alive?
- The free hand is alive in set_45, set_4, set_5, set_13–15.
- The phone hand is frozen in every clip (≤ 0.2°). The Sims pack holds the grip static; it's not a retarget loss.
- The poses' finger shapes are good: the curls wrap the phone, and the fingertips lie on its edges (≤ 4 mm overlap).

### Stuff through stuff?
- Phone vs face: clear in every clip. The calls need their phone backed off 2.5–3 cm (done).
- **Hands vs body is the real problem**, both from the Sims body being slimmer than his baggy hoodie:
  - The resting hand on his belly sinks 2–8 cm into the hoodie: 2.3 cm in the watching set, 7.6 cm in IN BED 01.
  - Hands tucked behind the head go 5–9 cm into the back of the head/hair: watching VER B, the couch, set_43.
- The sleeve cuff bunches when the elbow is flexed past ~120° (the resting arm). That is this character's skin; it shows even with the wrist held straight.
- Mattress: the torso support is constant within 0.3 cm in the reclined clips. The across-the-bed clips' legs leave the mattress by design.

## Worth the most
1. **set_38 / set_39** (WATCHING A VIDEO VER. A, landscape/portrait). These are the exact "in bed watching his phone" pose and the cleanest numbers (only the 2.3 cm resting hand). Both are poses, not motion.
2. **set_45 TYPING**: the same lying pose with a typing thumb. It's the only one with living fingers on the phone.
3. **set_4 IN BED 03 A**: real 18 s motion (lifts the phone over the face). Its legs need re-posing for our 0.82 m bed.

Not recommended:
- VER B (set_40–42): hand inside the head.
- IN BED 01/02: calls, with a hand 7.6 cm in the hoodie.
- The couch clips: hand in the head, and no couch.
