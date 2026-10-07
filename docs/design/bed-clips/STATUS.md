# Bed clips: status (G17, WIP)

Branch `preview/bed-clips`, from `preview/mixamo-g12`, with `main` and `preview/bed-music` merged in (the headphones, the music wiring, the 1.90 m bed).
Not for main yet: the final contact batch and the sheets are still running.

## What is in this push

- **Clips**, baked by `room_build/kimodo/bed_rebake.sh web/room/char_v5.glb` (the one command), in `web/room/mh_v5/`:
  - `room_laying_nodding`: lying awake on the quilt with the headphones, the music loop.
  - `room_laying_sleeping`: the sleep loop, under the duvet.
  - `room_sleep_turn`: a 17.2 s event. He rolls from the sleep loop's first frame onto his side over 2.6 s, stays there for 9 loops of Sleeping_Idle's quiet side-lying stretch (10.0–11.33 s), then rolls back. It ends on the loop's first frame (0.13° off).
- **Page** (`web/room/boy_mh.js`, `web/room.html`):
  - `EXTRA` loads the three clips. Listening plays Laying_Nodding with the headphones on (G10d's pair on the Head bone, and the music card the page already plays).
  - Asleep, the captured loop plays. Now and then (the first turn 1–2 min after he falls asleep, then every 2–5 min) the turn starts at the loop's wrap and hands back at time 0. If he is woken mid-turn, it fades back over 0.8 s while the get-up waits.
  - The captured bed clips rest their lowest skin ON the bed, down as well as up (`capBed`). Before, the page only ever lifted a lying pose, so a clip that sat high just floated.
  - The headphones now dent the pillow and the quilt, as his skin does.
  - The duvet follows him at 30 Hz while he turns (10 Hz otherwise).
  - `?nobedcap` turns the captured clips off, to measure against.
- **Pipeline**:
  - `kimodo_g12/bed_clip.py`: the fit onto our bed, measured on his skin in the room's frame.
  - `kimodo_g12/bed_turn.py`: builds the turn.
  - `kimodo_g12/bed_src.py` + `bedrig.py`: the Mixamo-rigged path, captures by bone name with no retarget.
  - `kimodo/bed_surface.mjs`: the bed's rest surface, from the page.
  - `kimodo/bed_shots.mjs`: render sheets.
  - `kimodo/bed_table.py`: the contact table.
  - The bed rows are data in `mixamo_clips.json` `"bed"`.
- **contact_pass.mjs**:
  - The bed rows of docs/qa/contact.md, every frame:
    - the back along the spine, buttocks included, over the mattress or the quilt;
    - the shoulders at the pillow's edge, apart;
    - the head against the pillow;
    - the toes against the mattress end;
    - the bed frame;
    - the duvet gap and poke-through;
    - his hands in his own torso, thighs or head;
    - the headphones in his head or hair, and under the pillow.
  - A per-frame "jump" row: his skin's largest move between two frames, which shows pops at the joins.
  - The mattress end is now 0.05, the 1.90 m bed (it was −0.20).

## Root causes found

1. **Raised fists and lifted legs (G10d's rejection of the retargeted Laying_Nodding).** `mh_retarget.mjs` scales the hips' height but IK-pins the wrists and ankles to the *unscaled* source positions. The performer's bed is 1.03 m up. Lying clips are now retargeted with the pins off.
2. **The captures lie V-shaped.** The hips are highest; head and heels are 6° below them (no pillow). The fit levels the body (12.6°), bends the neck onto the pillow, puts the heels down, and slides him 4 cm toward the headboard. His toes then sit inside the mattress end with no knee bend.
3. **His hands were inside his belly.** v5's hoodie stands 12 cm over the hip joint, and the performer's hands rested about 10 cm lower. Each wrist is lifted (two-bone IK) until the hands clear the torso skin.
4. **He floated, then dropped.** The page only lifted lying poses, and the clip's height did not match the lie-down step's end. The result was a 13 cm rise and then a one-frame drop at the join. The final fit puts his lowest skin at the reference pose's, and the page now rests the captured clips on the bed both ways. The join is being re-measured.

## Measured so far (the batch before the last fit, every frame; base = `?nobedcap`, today's still poses)

| row | contract | listen base | listen | sleep base | sleep | turn |
|---|---|---|---|---|---|---|
| back / hips over the mattress or quilt (cm) | −1 … +0.5 | +3.2 … +6.7 | +0.2 … +4.6 | +1.7 … +5.2 | −0.7 … +4.2 | −1.9 … +31.3 |
| head on the pillow (cm) | −2 … 0 | −6.7 | −0.6 … −0.2 | −9.6 | −1.4 … +0.2 | −2.7 … −0.9 |
| toes inside the mattress end (cm) | > 0 | 13.9 | 3.0 | 13.9 | 3.0 | 2.2 |
| bed / bed frame / floor | 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| hands in his own body | 0 | 0.9 cm, every frame | 0 | 0.9 cm, every frame | 0 | head 13.3 cm (old instrument) |
| headphones in head / hair | 0 | cups 2.1 cm | cups 2.8 cm | – | – | – |
| headphones under the pillow | 0 | 0 | band 0.4 cm, 12 frames | – | – | – |
| duvet through him | 0 | – | – | 0 | 0 | 0 |

The batch after the last fit changes these readings, because the instruments were fixed in between:
- The back's +4 cm max was the hip bin missing his buttocks (that skin is weighted to the thighs). They are now counted.
- The +2…+3.7 cm just below the pillow's edge was real. The fit now levels the upper back over the mattress, not the pillow.
- The cups' "2.8 cm in" is mostly the instrument: a polar map reads the ear as the head's surface around an over-ear cushion. It is now measured against the nearest skin's normal.

## Open (being worked now)

- The final contact batch on these clips, including all four joins (into and out of sleep and listening).
- **Leaving the music**: a 95 cm one-frame jump 0.6 s into the get-up (`listen_music>window`). It is not on the base, so it is this branch's: the fade-out into the get-up step.
- **Pre-existing, also on the base**:
  - In the lie-down to listen, his legs go 27 cm into the mattress over 50 frames.
  - A 1.27 m one-frame jump as the get-up reaches the bed's edge (`mh_edge`). This one is identical with and without these clips.
- **Mid-turn**:
  - The duvet stands up to 33 cm over his rising arm.
  - His head goes 0.7 cm past the pillow's give.
  - The back reading at the pillow's edge bins is not meaningful while he rolls.
- **The Mixamo-rigged path** runs end to end on G12's box test body, but its fit numbers there mean nothing: the box has the performer's proportions and no back surface. It must be checked on the real re-rigged character. The heading convention between the v5 and Mixamo clip frames (90°) is marked TO VERIFY in `bed_clip.py`.
- Sheets (page camera + side), the screen video, and docs/design/bed-clips/README.md follow.
