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

| row | contract | listen: base | listen: Laying_Nodding | sleep: base | sleep: Laying_Sleeping | the turn (17.4 s) |
|---|---|---|---|---|---|---|
| frames sampled | every frame | 87 (2.9 s) | 87 (2.9 s) | 102 (3.4 s) | 102 (3.4 s) | 522 (17.4 s) |
| back, hips over the mattress / quilt (cm) | −1 … +0.5 | **FAIL** +3.2 … +6.2 | **FAIL** +0.3 … +4.4 | **FAIL** +1.7 … +4.7 | **FAIL** -0.6 … +4.0 | **FAIL** -2.0 … +32.1 |
| head on the pillow (cm) | −2 … 0 | **FAIL** -6.7 … -6.7 | -1.4 … -0.9 | **FAIL** -9.6 … -9.6 | -1.8 … -0.5 | **FAIL** -3.2 … -0.4 |
| shoulders into the pillow's edge (cm) | (the page dents it) | -7.4 | -4 | -10.3 | -6.7 | -9.1 |
| toes inside the mattress end (cm) | > 0 | 13.9 | 4.1 | 13.9 | 4.2 | 0.3 |
| bed (inside the mattress less its give) | 0 | 0 | 0 | 0 | 0 | 0 |
| headboard / bed frame | 0 | 0 | 0 | 0 | 0 | 0 |
| floor | 0 | 0 | 0 | 0 | 0 | 0 |
| his hands / forearms in his own torso, thighs, head | 0 | **FAIL** 87 frames, up to 22 verts, 0.9 cm {'torso': 0.9} | 0 | **FAIL** 102 frames, up to 22 verts, 0.9 cm {'torso': 0.9} | 0 | **FAIL** 279 frames, up to 2784 verts, 4.7 cm {'torso': 1.6, 'head': 4.7} |
| headphones in his head / hair | 0 | **FAIL** 87 frames, 68 verts, 1.2 cm {'hp_cupL': 0.6, 'hp_cupR': 1, 'hp_band': 1.2} | **FAIL** 87 frames, 198 verts, 2.9 cm {'hp_cupL': 2.9, 'hp_cupR': 1, 'hp_band': 1.2} | - | - | - |
| headphones under the pillow's surface | 0 | 0 (closest 5.4 cm) | **FAIL** 26 frames, 0.5 cm {'hp_cupL': 0.3, 'hp_band': 0.5} | - | - | - |
| duvet: any of him through it | 0 | - | - | 0 | 0 | 0 |
| duvet over him: gap, mean / max (cm) | follows him | - | - | hands 1.9/9.1; arms 2.5/8.8; torso 1.7/4.4; legs 2.8/11.9; feet 5.6/18.1 | hands 1.7/4.2; arms 3/9.6; legs 2.7/18.9; torso 4.3/20.3; feet 1.9/5.2 | hands 1.7/5.2; arms 4.1/31; legs 3.5/22.5; torso 3.3/27.8; feet 2.4/12.8 |

The back, bin by bin (10 cm along the bed from the headboard; the lowest back skin's gap, min … max over the clip, cm):

| from the headboard | 50 (pillow's edge) | 60 | 70 | 80 | 90 (hip joint) | 100 (just past it) |
|---|---|---|---|---|---|---|
| asleep | +1.6 … +2.6 | +0.3 … +1.1 | −0.5 … 0 | −0.6 … −0.1 | +0.2 … +0.8 | +3.2 … +4.0 |
| awake (on the quilt) | +2.7 … +2.8 | +1.4 … +1.5 | +0.4 … +0.5 | +0.3 … +0.4 | +1.1 … +1.2 | +4.3 … +4.4 |

Sheets (page camera, zoomed onto the bed from where it stands, and fixed cameras beside it), in this folder:
- `listen.jpg`: page, page zoomed, side profile, his face with the headphones;
- `sleep.jpg`: under the duvet, page and foot;
- `sleep_no_duvet.jpg`: the same with the duvet hidden;
- `turn.jpg`, `turn_no_duvet.jpg`: the turn at 0, 1.3, 2.6, 8, 15.9 and 17.2 s.

Videos: `sleep_turn.mp4` (the turn, 17.4 s, page camera zoomed + side), `listen.mp4` (3 s, page camera zoomed + his face). `room_build/kimodo/bed_video.sh` makes them.

## Open

- **The back is not yet flush everywhere.** The small of his back and his mid back touch: −0.6…0 cm asleep, +0.3…+0.5 cm awake. Two places do not:
  - just past the hip joint, his buttocks are +3…+4.4 cm up;
  - at the pillow's edge, his shoulder blades are +1.6…+2.8 cm up.
  The fitter's own measure, on the same skin in the same frame, reports the buttocks level with the small of his back after the pelvic tilt (5.5–6.7°). The page reads 2–3 cm more there. That disagreement is not found yet. The base (main's still poses) reads +1.7…+6.2 cm on this row.
- **The headphones sit in his hair**: cups up to 2.9 cm and the band 1.2 cm into the head's skin and hair surface. The base pose reads 1.2 cm, so the head's angle in the capture adds the rest; the fit is G10d's, owner-approved. They also come up to 0.5 cm under the pillow's shown surface in 26 of 87 frames, now that the pillow gives under them.
- **The turn**:
  - In the side hold, a hand lies by his face, 4.7 cm into his head's skin (279 frames). The fitter's own head test, a polar map, does not see it.
  - Mid-roll his head goes 3.2 cm into the pillow (the contract's give is 2).
  - His lower shoulder presses 9 cm into the pillow's edge, and the page's dent shows the mattress through the pillow there (`turn_no_duvet.jpg`).
  - The duvet stands up to 28–31 cm over his rising arm mid-roll. It follows him at 30 Hz with nothing poking through, but it is a tent, not a cover.
  - The back bins at the pillow's edge and past the hips read up to +32 cm while he is on his side. A back-along-the-spine measure means little for a body on its side.
- **The duvet asleep**: up to 19–20 cm over his legs and torso, against 12 cm on the base. Nothing pokes through.
- **The joins** (`contact_pass.mjs "a>b"`, the jump row):
  - **Into sleep**: fixed (above).
  - **Out of listening**: 44 cm in the step's first frame. The base's step jumps 29.5 cm there too: the page re-places his root as the get-up begins.
  - **Into listening**: 27 cm of his legs go into the mattress for 50 frames during the lie-down (`room_bed_lie`), identical on the base.
  - **Out of sleep** (and out of listening), as he reaches the bed's edge: a 1.27 m one-frame jump. Identical on the base, so the page's, not these clips'.
- **The Mixamo-rigged path** is unverified on the real character (above).

