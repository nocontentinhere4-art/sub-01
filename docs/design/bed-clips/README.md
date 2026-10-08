# The bed clips on v5, ready to re-bake (G17)

These are the three captures for the bed, fitted to our 1.90 m bed and wired into the page:
- lying awake with the music, the headphones on;
- asleep;
- now and then, the turn onto his side and back.

After the Mixamo re-rig, one command re-bakes them:

```
room_build/kimodo/bed_rebake.sh <character.glb> [work dir]
```

That command does all of this:
1. reads the raw captures (`$MIXAMO_SRC`, or the scratch branch, into the work dir; never committed);
2. puts them on the character;
3. fits them to the bed (the rows in `room_build/kimodo/mixamo_clips.json` `"bed"`);
4. composes the turn;
5. writes `web/room/mh_v5/room_laying_nodding.glb`, `room_laying_sleeping.glb` and `room_sleep_turn.glb` (`$OUTDIR` to write elsewhere);
6. runs `contact_pass.mjs` over every frame of the three, and prints the table below (`kimodo/bed_table.py`).

It serves `web/` itself while it runs. The clips on this branch were written by it: `bed_rebake.sh web/room/char_v5.glb`.

## The clips

| clip | what | length |
|---|---|---|
| `room_laying_nodding` | Laying_Nodding: on his back on the quilt, hands resting on his chest, a slow nod. Lying awake with the music, headphones on. | 1.43 s loop |
| `room_laying_sleeping` | Laying_Sleeping: on his back under the duvet, breathing, hands on his chest. The sleep loop. | 1.70 s loop |
| `room_sleep_turn` | from the sleep loop's first frame, he rolls onto his side over 2.6 s, stays there (Sleeping_Idle's quiet side-lying stretch, 10.0–11.33 s, ×9), and rolls back onto the loop's first frame | 17.2 s, once |

- The turn begins and ends on the sleep loop's first frame, within 0.11°. It starts at the loop's wrap and hands back at time 0, so nothing steps.
- His lowest skin stays at the loop's level through the whole turn (hips moved −1.7…+1.2 cm). The page's lift, measured once a second, never steps.
- Laying_Sleeping has no turn of its own. The whole Sleeping_Idle take is not used: it tosses over 140° of heading, and its head leaves the pillow by 33 cm (G12). Only its stretch on its side is kept.

## In the page (`web/room/boy_mh.js`, `web/room.html`)

- `EXTRA` loads the three clips.
- **Lying awake with the music ("listen")**:
  - Laying_Nodding fades in over his lying pose (0.8 s).
  - The headphones are G10d's Tripo pair, built onto the Head bone (on `preview/bed-music`, owner-approved). They show while a track plays, and the page plays its music card as before.
  - Getting up: the step runs as it does from the plain lying pose, and the music pose fades out over it (0.3 s). Before this, the fade back held the step and then snapped his head 64 cm. That path had never run live, because bed-music's `EXTRA` was empty.
- **Asleep**:
  - The captured loop replaces the still of `room_bedtime`'s end.
  - The turn (`sleepTurn()`): the first one 1–2 min after he falls asleep, then every 2–5 min, always at the loop's wrap.
  - If he is woken mid-turn, the turn fades back into the loop over 0.8 s while the get-up waits.
  - While he turns, the duvet is reshaped at 30 Hz instead of 10, so it follows his arm (`env.bedMoving`).
- **Barefoot in bed**: lying on the bed, his slides are parked by it, as before (socks on).
- **The captured clips rest ON the bed** (`capBed`): his lowest skin goes to the bed's top down as well as up. Every other pose is still only lifted out of it.
- **The headphones dent the pillow and the quilt**, as his skin does (`quiltDent`).
- `?nobedcap` turns the captured clips off (what main shows); the "base" columns below are measured that way.
- **The joins**:
  - Into sleep, the lie-down step (`room_bedtime`) ends on its own last pose, and the sleep loop takes over at the same lift: 0.216 → 0.219 m. After the walk his head never moves more than 1 cm in a frame, and his lowest skin rests at 0.801–0.809 (the bed's top in the page: 0.805).
  - Out of sleep and into or out of listening, see the open items.

## The fit: `room_build/kimodo_g12/bed_clip.py` (replaces `bed_fit.py` for these)

It works on the skin of the body the page shows, in the room's frame. Heights are measured from his lowest skin, because the page puts that on the bed. The same constant turns go on every frame, so the capture's own motion stays.

0. **Slide**: the clip moves 4 cm toward the headboard. His head comes nearer the pillow's centre, and his toes sit 4 cm inside the mattress's end with his legs as captured. The side pose moves 6 cm toward the foot instead (`slide` in its row), because his lower shoulder otherwise lay 12 cm into the pillow's edge. The roll then carries him 10 cm down the bed.
1. **Level**: the whole body is turned about his side axis, at the hips (12.6–13.7°), until the lowest back skin under the hips and under the shoulder blades are level. The captures lie V-shaped, hips highest: head and heels are 6° below the hips, on the performer's bed with no pillow.
1b. **Pelvis**: the pelvis and legs turn about the hip joint while the waist turns back, so the upper body stays put (5.5–6.7°). This continues until his buttocks lie as low as the small of his back.
2. **Pillow**: neck and head bend about the side axis until the back of his head is 1.1 cm into the pillow's top. The pillow's rest surface comes from the room's own sheet mesh, read from the page (`kimodo/bed_surface.mjs`). The bend is solved again on the final legs and arms.
3. **Heels**: the legs turn at the hips until the legs' lowest skin is on the mattress. On his side they turn about the bed's axis instead, the upper knee coming up off the lower. If his toes still reached past 3 cm short of the mattress's end, the knees would bend; with the slide they don't.
4. **Hands**: each wrist is moved by two-bone IK (the elbow bends and the hand keeps its turn), straight up first and then other ways. It stops once his hands and the wrist half of his forearms are out of his torso and head, plus 6 mm. v5's hoodie stands 12 cm over the hip joint, and the performer's hands rested about 10 cm lower, so as captured his fingers were inside his belly. Lifted: 9.6–12.6 cm.
5. **Hold**: frame by frame, the hips move up or down so his back's lowest skin stays at one height.
5b. **Height**: then the whole clip moves until his lowest skin is at the reference pose's. The reference is `room_bedtime`'s end asleep, `room_bed_lie`'s awake; the page's lie-down step ends on it, so the lift is the same on both sides of the join. Without this he rose 13 cm at the end of the lie-down, then dropped in one frame.
6. **Loop**: with `--loop`, the last frames are eased onto the first.

**Retarget (v5 rig)**: `mh_retarget.mjs` with the pins off, `{"scale":"hip","hands":false,"feet":false}`. The pins aim the wrists and ankles at the source's positions *unscaled*, while the hips are scaled. Lying on the performer's bed 1.03 m up, that raised his fists in front of his face and lifted his legs 11–19 cm, which is why G10d rejected the retargeted Laying_Nodding.

**The turn**: `kimodo_g12/bed_turn.py`:
- every joint's local turn is eased between the sleep loop's first frame and the side pose;
- mid-roll, the head is kept on the pillow (the neck bent);
- each elbow is kept within 4 cm of the line between its two end heights, by a swing of the upper arm about the shoulder–wrist line. The plain blend flung the right elbow 28 cm over his chest.

**The Mixamo-rigged character**: `bed_rebake.sh` sees mixamorig bones and takes the other branch:
- `kimodo/mixamo_glb.mjs` turns each capture into a GLB on its own skeleton;
- `kimodo_g12/bed_src.py` puts it on the character's skeleton by bone name, nothing retargeted, the hips' travel scaled by hip height;
- `bedrig.py` maps Mixamo's names onto the fit's.

It runs end to end on G12's box test body. The fit numbers there mean nothing, because the box has the performer's proportions and no back surface. Two things to check on the real character (it is v5's mesh, so the fit's landmark windows should carry over):
- the heading convention between the two clip frames (90°, marked TO VERIFY in `bed_clip.py`);
- the output folder the page loads that character's clips from (`OUTDIR`).

## Contacts: docs/qa/contact.md, every frame, on the mesh

`contact_pass.mjs` gained the bed rows. Lying (sleep / listen_music) it measures, every frame and every 2nd vertex:
- **back**: along the spine, in 10 cm bins along the bed, each bin's lowest skin against the bed's rest surface under it, over the mattress (or the quilt, awake). The torso and pelvis count, and so do the buttocks (thigh-weighted skin up to 6 cm past the hip joint, not the backs of his thighs).
- **shoulders**: where they lie at the pillow's edge, apart.
- **head**: against the pillow's rest top.
- **toes**: against the mattress's end (x 0.05: the 1.90 m bed; the pass had −0.20).
- **bed frame**: the headboard and frame.
- **duvet**: from his highest skin in each 3 cm cell, a ray up to the duvet's underside (the gap), and anything of him over its top (poke-through).
- **self**: his hands and wrists inside his torso or thighs (a polar map of their skin, not a capsule), or inside his head (behind the nearest skin's surface, by its normal).
- **headphones**: the same test against his head and hair, and against the pillow's shown (dented) surface.
- **jump**: his skin's largest move between two frames, which catches pops at the joins.

"base" = `?nobedcap` (main's still poses on this branch's bed and page).

Measured on **main's character** (`char_v5.glb` of 0ac47f8: the hood collar, the socks and slides as their own meshes), on the clips `bed_rebake.sh` baked onto it. On this character "head" is his head itself (the `owner_head` material): the hood is weighted to the Head bone too, and a hand against the hood used to read as a hand in his head.

| row | contract | listen: base | listen: Laying_Nodding | sleep: base | sleep: Laying_Sleeping | the turn (17.4 s) |
|---|---|---|---|---|---|---|
| frames sampled | every frame | 87 (2.9 s) | 87 (2.9 s) | 102 (3.4 s) | 102 (3.4 s) | 522 (17.4 s) |
| back, hips over the mattress / quilt (cm) | −1 … +0.5 | **FAIL** +3.2 … +6.2 | **FAIL** +0.3 … +4.4 | **FAIL** +1.7 … +4.7 | **FAIL** -0.6 … +4.0 | **FAIL** -1.9 … +34.3 |
| head on the pillow (cm) | −2 … 0 | **FAIL** +0.5 … +0.5 | **FAIL** +2.5 … +3.7 | **FAIL** -2.4 … -2.4 | -1.7 … -0.5 | **FAIL** -2.1 … +1.1 |
| shoulders into the pillow's edge (cm) | (the page dents it) | -7.4 | -4 | -10.3 | -6.7 | -9 |
| toes inside the mattress end (cm) | > 0 | 14.6 | 3.3 | 14.6 | 3.4 | 2.8 |
| bed (inside the mattress less its give) | 0 | 0 | 0 | 0 | 0 | 0 |
| headboard / bed frame | 0 | 0 | 0 | 0 | 0 | 0 |
| floor | 0 | 0 | 0 | 0 | 0 | 0 |
| his hands / forearms in his own torso, thighs, head | 0 | **FAIL** 87 frames, up to 20 verts, 0.9 cm {'torso': 0.9} | 0 | **FAIL** 102 frames, up to 20 verts, 0.9 cm {'torso': 0.9} | 0 | **FAIL** 36 frames, up to 116 verts, 3 cm {'torso': 3} (his face: 0) |
| headphones in his head / hair | 0 | **FAIL** 87 frames, 35 verts, 1.8 cm {'hp_cupL': 1.8, 'hp_cupR': 1} | **FAIL** 87 frames, 1 vert, 0.2 cm {'hp_cupR': 0.2} (target ≤ 0.5) | - | - | - |
| headphones under the pillow's surface | 0 | 0 (closest 5.4 cm) | 0 (closest 6 cm) | - | - | - |
| duvet: any of him through it | 0 | - | - | 0 | 0 | 0 |
| duvet over him: gap, mean / max (cm) | follows him | - | - | hands 1.9/9.1; arms 2.5/8.5; legs 2.8/11.2; torso 1.7/4.5; feet 4.1/10.5 | hands 1.7/3.7; arms 3/9.6; torso 4.3/20.2; legs 2.7/18.9; feet 1.6/4.7 | hands 1.8/7.4; arms 4.1/25.5; torso 3.2/26.6; legs 3.5/22.7; feet 2/10.4 |

The back, bin by bin (10 cm along the bed from the headboard; the lowest back skin's gap, min … max over the clip, cm):

| from the headboard | 50 (pillow's edge) | 60 | 70 | 80 | 90 (hip joint) | 100 (just past it) |
|---|---|---|---|---|---|---|
| asleep | +1.5 … +2.6 | +0.4 … +1.1 | −0.5 … 0 | −0.6 … −0.1 | +0.2 … +0.8 | +3.2 … +4.0 |
| awake (on the quilt) | +2.7 … +2.8 | +1.4 … +1.5 | +0.4 … +0.5 | +0.3 … +0.4 | +1.1 … +1.2 | +4.2 … +4.4 |

Sheets (page camera, zoomed onto the bed from where it stands, and fixed cameras beside it), in this folder:
- `listen.jpg`: page, page zoomed, side profile, his face with the headphones;
- `sleep.jpg`: under the duvet, page and foot;
- `sleep_no_duvet.jpg`: the same with the duvet hidden;
- `turn.jpg`, `turn_no_duvet.jpg`: the turn at 0, 1.3, 2.6, 8, 15.9 and 17.2 s;
- `headphones.jpg`: beside his head on both sides and from above his face, lying awake.

Videos: `sleep_turn.mp4` (the turn, 17.4 s, page camera zoomed + side) and `listen.mp4` (3 s, page camera zoomed + his face), recorded on main's character with the clips of this commit. `room_build/kimodo/bed_video.sh` makes them.

`owner.jpg`: one sheet for the owner, before (0908653) and after for each of C's fixes, then six frames each of LISTEN and SLEEP from the page's camera (zoomed onto the bed from where it stands).

## Main's character (0ac47f8): what changed

- Merged main. `char_v5.glb` is main's (the hood collar, G19's socks and slides).
- `room.html`: `contacts()` and `penetration()` take his body mesh by name (`bodyMesh()`). `skinMesh()` returns the last skinned mesh, which on this character is the socks. The page's own slides code (`slidesInit` / `setSlides`) is for a body of one mesh; v5's separate `slides` mesh is parked by boy_mh.js's `bedThings`, as before.
- The fit saw only the first skinned mesh, and on this character his feet are the socks mesh. `room_build/kimodo/bed_exp.mjs` exports every part except the slides, each with its own joint slots (gltfpack folds each part's dequantization into its own inverse bind matrices).
- **Headphones round the neck, through the hood**: Laying_Nodding's performer lies with his head turned 57° to his side, which puts the lower cup at his jaw, in the hood's collar. Lying awake, the fit now turns his head back to within 20° (9° here). Both cups sit on his ears with the band over his head (`headphones.jpg`), and nothing of them goes under the pillow's surface (it was 0.5 cm).
- **The turn**:
  - each wrist is capped mid-roll, but never into his chest (a straight cap put his hands 16 cm into it);
  - the duvet over his arm: 25.5 cm, was 31;
  - his toes are held 2.8 cm inside the mattress's end while he rolls (his socks are longer: they went 0.4 cm past).
- **Instruments**: the head test in the contact pass and in the fit is now the same rule (behind the nearest head-skin point, seen from the head's centre), and the hood is not his head.

## C #8: the sink, the straight legs, the duvet

Re-measured with the clips of this commit, every frame (`contact/`). This supersedes the back, head and duvet numbers above where they differ.

| row | C's pass | listen | sleep | the turn |
|---|---|---|---|---|
| buttocks (bin 100, just past the hip joint) | ≤ +1 cm | +0.9 | +0.9 | – |
| back, lowest | ≥ −2.5 cm | −2.1 | −2.4 | −2.8 (mid-roll) |
| head on the pillow | −2 … 0 | −1.7 … −0.5 | −1.8 … −0.4 | −2.1 … +1.1 |
| toes inside the mattress end | ≤ 3.5 cm | 0.8 | 0.8 | 0.4 |
| bed (less its give) / bed frame / floor | 0 | 0 | 0 | 0 |
| hands in his body | his face: 0 | 0 | 0 | chest 2.7 cm, 32 frames; face 0 |
| duvet's top over his legs | ≤ 15 cm | – | 23.9–30.2 (32–40 next to his hips) | – |

- **The sink** (`bed_clip.py` BED_SINK, `boy_mh.js` BED_SINK, per row in `mixamo_clips.json`): the mattress gives under his back and hips. The fit lowers them by `sink` (2.0 cm awake, 1.65 cm asleep) and fits his heels and the back of his head for that height. The page rests his lowest skin, now his back, `sink − BACK_UP` under the bed's top (1.8 / 0.65 cm). Only the mattress takes it: the head is fitted to the pillow as before, and nothing reaches the bed frame or the floor.
- **Straight legs** (`flat`: 1.0): the hips' and knees' bend blended all the way to straight before the fit, and the toes allowed to within 0.8 cm of the mattress end (`toe_in`). At 40–70% the knees stayed up and the buttocks gap stayed at 1.2–1.6 cm. The heel step no longer counts his buttocks as legs: they are the back's, and counting them made the heels impossible to set above his back.
- **The head on the pillow** is fitted by his head itself (`owner_head`), as the contact pass measures it. With his neck straighter, the hood touched the pillow first and his skull rode 2–7 cm over it.
- **The duvet** (`room.html`): it bridges less (DRAPE 12/8 → 6/4 cm) and is thinner (5 → 3.5 cm). With his knees flat, the tent over them is gone. His legs themselves are 19–26 cm deep (the baggy track pants), so the duvet's top cannot come under 15 cm above the mattress without going through them.

## C's fixes (#6, #7)

- **Hands off his face mid-roll** (`bed_turn.py`): on every frame of the roll where a hand or forearm is in his face (his head's own skin, measured from the head's axis as the contact pass does), the wrist is moved by two-bone IK, 2 cm at a time. It takes the first direction that clears his face, keeps the hand no deeper in his chest than before and keeps it above his own lowest skin. The directions: level toward his hip, out from his head, up, and up-and-toward his hip. A straight move toward the hip put the hand 11 cm into his chest and under him, and lifted his whole body 11 cm. Result: his face 0, on every frame (was 8 cm, 78 frames); 56 frames moved, up to 20 cm. Left over: up to 3 cm of hand in his chest on 36 frames, worst at 0.47 s, from the wrist cap.
- **Cups out of his hair** (`boy_mh.js`, the bed clips only): lying, the pair is widened by `HP.BED_OUT` (0.8 cm per side, out along the ear's axis), blended in with his weight on the bed. Standing and at the desk the fit is G10d's, untouched. Cups in his hair: 1.9 → 0.2 cm.
- **Neck rest clear of the hood** (C #6): his head is turned back to within 20° lying awake (9° here; the performer's was 57°). Standing and at the desk, the cups are 0 cm into the hood over every frame (with the lining, on b2593d7's v5). Lying awake, the lower cup's rim still touches the hood's edge on its outside, about 1.0 cm deep. Raising the pair 2.4–2.8 cm clears it (0.4 → 0 cm), but puts the cups back 0.7–0.8 cm into his hair. I kept the hair target, so this one is open (below).
- **Buttocks ≤ +1 cm: not met in #7** (met in #8, above). A buttocks step after the heels (`BED_BUTTOCKS=1`, off by default) tilts the pelvis again and bends the knees to keep the heels down. Measured on main's v5, it takes the buttocks from +3.2…+4.4 to +2.4…+2.9 cm. But the backs of his thighs then become his lowest skin, and the page rests that on the bed, so his whole back floats: +0.2…+0.6 cm asleep and +1.8…+4.0 cm awake, with his knees bent 35–50°. The small of his back and mid back would leave the contract to get the buttocks part way, so the step stays off. Getting to ≤ +1 cm needs legs that lie flatter than either capture.

## Open

- **The back**: the small of his back and his mid back touch, −0.6…0 cm asleep and +0.3…+0.5 cm awake. Two places do not:
  - just past the hip joint his buttocks are +3.2…+4.4 cm up;
  - at the pillow's edge his shoulder blades are +1.5…+2.8 cm up.
  The buttocks are not fixed (see C's fixes above). The pelvic tilt levels them, then the heel step turns his thighs at the hips (9–16°) and lifts them again. Solving the two in turn diverges, because with the legs as captured, heels down and buttocks down conflict. The base reads +1.7…+6.2 cm on this row.
- **His head awake**: the hood rests on the pillow, and the back of his skull sits +2.5…+3.7 cm above the pillow's top through it. Asleep: −1.7…−0.5 cm, in the contract.
- **The cups against the hood, lying awake**: about 1.0 cm at the lower cup's rim (above). Standing and at the desk: 0.
- **The turn**:
  - mid-roll, up to 3 cm of a hand in his chest (36 frames); his face is clear;
  - his head goes 2.1 cm into the pillow (the give is 2), and rises 1.1 cm off it;
  - his lower shoulder presses 9 cm into the pillow's edge in the side hold, and the dent shows the mattress through the pillow (`turn_no_duvet.jpg`);
  - the duvet is a 25–27 cm tent over his arm and torso mid-roll, though nothing pokes through;
  - the back bins read up to +34 cm while he is on his side (a back-along-the-spine measure means little there).
- **The duvet asleep**: up to 19–20 cm over his legs and torso, against 11 cm on the base. Nothing pokes through.
- **The joins** (`contact/join_*.json`):
  - **Into sleep**: clean; nothing above the walk's 22 cm/frame.
  - **Out of listening**: the worst move in the get-up's first second is now 26.8 cm/frame (was 44; the base's step jumps 29.5 cm on its first frame).
  - **Into listening**: during `room_bed_lie`'s lie-down his legs go 27 cm into the mattress for 46 frames, the same on the base.
  - **At the bed's edge** (out of sleep or listening): a 1.27 m one-frame jump, identical on the base, so the page's.
- **The Mixamo-rigged path** is unverified on the real character (above).
