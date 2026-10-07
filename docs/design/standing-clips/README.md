# Standing and in-between clips on the Mixamo-rigged character (G22)

Nine Mixamo captures, baked for `web/room/char_mixamo.glb` (v5 on the Mixamo Standard Skeleton, G20) and placed in the
room: Texting_While_Standing, Standing_Using_Touchscreen_Tablet, Texting, Standing_Clap, Angry_Gesture, Scared,
Stand_To_Sit, Sit_To_Stand, Gaming. The desk clips (G21) and the bed clips (G17) are not touched.

- Clips: `web/room/mx_standing/<Clip>.glb` (2.8 MB in all). Each is an animation-only GLB on the character's own
  skeleton (`mixamorig:*`, the same node names, hierarchy and rest): 52 bone rotations including the fingers, plus the
  hips' translation. Nothing else travels, so bone lengths stay his.
- The fit of each clip: `web/room/mx_standing/standing_clips.meta.json` (soles, seat, planted feet, reach, extents).
- No raw capture is committed. The FBX are read from `claude/loving-davinci-6hqmjx` (`mocap_src/mixamo/`) into a temp
  dir by the re-bake, which deletes it afterwards.

## See them in the page

`room.html?char=mixamo&clip=<Clip>` (add `&debug` for the probes). This shows the clip in a loop on the Mixamo-rigged
character, in the room, and frames the camera on him once. The entry is `web/room/standing_preview.js`, plus one marked
block at the end of `room.html` (`// ===== G22`).
- With these parameters, the page's own day is off: the v5 body is taken out of the scene and the planner is not
  stepped.
- Without `clip`, nothing in the block runs and the module is never loaded. The default page is unchanged.
- The clip name must match `[A-Za-z_]+`.

## Re-bake: one command

```
room_build/kimodo/standing_rebake.sh <character.glb> [Clip ...]
```

This re-bakes every row of `room_build/kimodo/standing_clips.json` (about 20 min for all nine on 4 cores, most of it the hands test on the three long standing clips; `MOCAP_DIR=<dir>` reads
the FBX from a folder instead of the branch). The pipeline for each clip:
- `kimodo/mixamo_glb.mjs` turns the FBX into a GLB;
- `kimodo/standing_exp.mjs` exports the clip and the character, with the slides, his second skinned mesh;
- `kimodo/standing_bake.py` does the fit below;
- `kimodo_g12/writeclip.mjs` writes the GLB.

### The fit (`standing_bake.py`)

- **No retarget.** The capture's local rotations play by bone name: the rig's rest rotations are Mixamo's (G20).
- **Hips' travel scaled by hip height.** The scale is 0.893 (his 0.92 m over the performer's), the same as
  `char_mixamo.js` `fixClip`.
- **Standing frames.** The hips move up or down so that his lowest sole (the slides' underside) is 0.4 cm over the
  floor. The contract range is 0…+1 cm.
- **Seated frames** use G12's fit (`kimodo_g12/post.py`), redone on this rig:
  - One lift for the whole seated stretch: his thighs and buttocks rest on OUR cushion, the lowest of that skin 0.4 cm
    into its top (0.505 m over the floor).
  - The cushion stops him: while his hips are over the seat they never go under the seated height. This matters when
    he lands on the seat or pushes off it.
  - The seated hips end at 0.708–0.728 m over the floor. G12's v5 fit used 0.70.
  - The rows with `seatOrigin` put the seated hips at the clip's origin, and the page places that origin on the chair.
- **Transitions blend the two fits** by how low the hips are.
- **Feet:**
  - A planted stance (the performer's ankle low and slow for 0.3 s or more) is held on one spot.
  - Every sole is put on the floor by two-bone leg IK: the knee stays in its own bend plane and the foot keeps its world
    rotation.
  - A lifted foot keeps its lift over the stance level, and no sole ever goes under the floor.
  - Planted ankle drift after the fit: 0.00 cm in every clip, except Standing_Clap's left foot at 0.07 cm.
  - The supporting sole: where the performer has a foot down but both of his soles are over 1 cm (a stance between two
    planted ones, as he rises or turns), the lower one goes down onto the floor. Where the performer has both feet up
    (a jump: Scared, 7 frames) they stay up.
- **Hands off his thighs**, by the same test as the self-contact pass (a hand vertex behind the nearest thigh vertex by
  more than 5 mm along its normal):
  - there the wrist moves out along that normal by the depth + 5 mm (held 0.2 s either side, smoothed), and the arm is
    re-solved by two-bone IK with the hand keeping its world rotation;
  - it changed two stretches and nothing else: Texting_While_Standing's right hand, 69 frames up to 2.49 cm into the
    front of his trousers as both hands come down (20.6–23 s), and Texting's left hand, hanging at his side, 10 frames
    at 0.56 cm. Both are 0 after.

### Where each plays (`standing_preview.js`, `standing_clips.json` `spot` / `seatAt`)

- **Standing (Texting, Texting_While_Standing, Tablet): `rug`.** He stands in the open middle of the room, on the rug,
  facing the window. His soles are measured against the rug's top.
  - The first spot by the door put his feet on a skateboard. It is part of a merged props mesh (`tripo_props2`) that
    the contact pass did not test then, so the clip mode now tests every visible mesh.
- **Gaming and Angry_Gesture: `chair`.** He plays them at the desk. The chair is rolled back by the clip's own reach
  plus 3 cm (capped at 0.60 m by the bed behind it) and moved 0.28 m to the side. Rolled straight back, it would sit
  his left leg in the plant and the things on the floor beside the desk (x < −1.30, z −0.60…−0.10).
- **Stand_To_Sit and Sit_To_Stand: `out`.** The chair is where the page itself has it for his sit-down and stand-up:
  `chairAt(1)`, pulled out 0.40 m and turned 90°. These clips need 0.76 / 0.81 m in front of the seat. At the desk the
  stand-up's arms ran 4.1 cm into the desk and his hips 9.2 cm into his bottle on its edge.
- **Scared and Standing_Clap: `open`.** The chair stands out in the middle of the room, on the rug. Scared jumps up and
  steps back, and Standing_Clap rises with his arms overhead. Their reach (0.82 / 0.92 m forward) needs more roll-back
  than the bed allows at the desk. Rolled 0.60 m there, Scared measured feet 8.4 cm into the desk, and his legs and
  torso 9.2 cm into the furniture behind the chair (the pass's "other" region) as he stepped back.

**The seat point (`seatAt`, metres in the chair's frame, forward −z; the cushion's front edge is at −0.27)** was swept
per clip in the room. Each value is the first one where no skin is more than 1 cm inside the chair's frame:
- Angry_Gesture −0.18
- Scared and Gaming −0.20
- Stand_To_Sit and Standing_Clap −0.22
- Sit_To_Stand −0.24

That puts him on the front of the seat, as people sit when they sit down, stand up, or lean in to game or gesture.
Further back, the seat pan's front edge runs 2–4 cm into his thighs.

Why: with the foot flat, his knee joint is 0.49 m over the floor, under the cushion's 0.505 m top. So his thighs slope
down to the knee (the trouser cloth hangs 12–15 cm under the thigh bone), and further back on the seat the front edge
meets them. The sweep (vertices more than 1 cm inside, deepest):
- Stand_To_Sit: 3.8 cm at −0.10; 1.4 cm at −0.20; 0 at −0.22.
- Scared: 2.6 cm into the frame by the torso at −0.10 (12.7 cm at G12's −0.055); 0 at −0.20.

**For the page's wiring (G21 / G10d):** these seat points differ from the seated loop's. G12's `SEAT_AT` for
Seated_Idle was 5.5 cm. A sit-down that ends at −0.22 joins a loop seated further back, so the page should slide him
back on the seat during the cross-fade (as people do), or take the loop's seat point from the same sweep.

### Hands: what he holds

Each palm has a socket, an empty Object3D (`socket_R` / `socket_L`), built from his own finger bones on the clip's first
frame. What he holds:
- **Texting and Texting_While_Standing: the page's phone on the right hand.** That is its rounded body and its screen,
  with a plain made-up feed on the glass. The rigid gripping-hand mesh made for the finger-less rig is not used.
  - Its screen is turned towards his eyes: their direction in the palm's frame, averaged over the clip. Its long side
    runs along his fingers as far as that allows.
  - As the page does for its own phone, it is lifted just enough that no skin of his right hand is inside it or over
    its screen, over the whole clip. So it rests on his curled fingers. It is not wrapped in a grip: the captured hand
    is a loose fist.
  - Measured on this rig, the names have the hands the other way round. Texting is one-handed: the right hand is at
    the chest from 0.8 to 17 s, the left hand down. Texting_While_Standing is two-handed: both hands are at the chest
    from 2 to 20.6 s, about 20 cm apart. The phone is on the right hand as asked, so the left hand taps beside it.
- **Gaming: the page's controller** (`room/controller.glb`, a second instance; the one on the desk stays).
- **Standing_Using_Touchscreen_Tablet: a plain tablet.** The page has none, so this is a rounded slab 25 × 17 × 0.7 cm
  with a made-up screen, built in code, with no brand.
- The controller and the tablet are held in both hands. Every frame they are placed between his palms, running across
  from his left palm to his right, with their face (the buttons, the screen) turned towards his eyes as far as that
  allows.

How well each faces him and how far his hand is inside it are in the table (the "held prop" column). Most frames where
a phone turns away are the start and end of the clip, when that hand hangs at his side.

## Contact table

Measured in the room as the preview places each clip, every frame of the whole clip:
- `CLIP=<Clip> node room_build/kimodo/contact_pass.mjs <port> x clip`, with the page served from `web/` with `?debug`;
- `node room_build/kimodo/standing_selfcontact.mjs web/room/char_mixamo.glb web/room/mx_standing <out.json>`.

The JSON is in `contact/`.

<!-- table -->
| clip | frames | furniture, walls, floor (> 1 cm inside) | supporting sole, cm (frames outside 0…+1) | soles L / R, cm | seat: lowest thigh / buttock gap to the cushion, cm | held prop: hand skin inside its box; its face to his eyes (mean, frames within 30°) | hands in thighs (bake: before → after the fix) | hands in thighs, surface test (normal-based) | hands in thighs, contact_pass's capsule (overstates: radius from the baggy trousers) | sleeve in torso, away from the armpit, L / R | arm in torso (the pair, rig included) L / R | leg in leg | planted ankle drift, cm |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Texting_While_Standing | 708 | **0** | 0.34…0.34 (0) | 0.4…0.4 / 0.3…0.3 | — | phone: 0.4 cm (2 fr); 22.7°, 78 % | R 69 fr 2.49 cm → 0 fr | 0 | 10.2 cm (106 fr, ≤3084 v) | 2.5 cm (708 fr, ≤714 v) / 2.5 cm (708 fr, ≤790 v) | 2.5 cm (708 fr, ≤826 v) / 2.5 cm (708 fr, ≤1020 v) | 0.8 cm (708 fr, ≤4 v) | 0.0 / 0.0 |
| Standing_Using_Touchscreen_Tablet | 995 | **0** | 0.36…0.36 (0) | 0.5…0.5 / 0.4…0.4 | — | tablet: 0.3 cm (923 fr); 12.9°, 92 % | 0 | 0 | 7.2 cm (56 fr, ≤755 v) | 2.5 cm (995 fr, ≤836 v) / 2.5 cm (995 fr, ≤886 v) | 2.5 cm (995 fr, ≤904 v) / 2.5 cm (995 fr, ≤1126 v) | 0.7 cm (995 fr, ≤4 v) | 0.0 / 0.0 |
| Texting | 557 | **0** | 0.38…0.39 (0) | 0.4…0.5 / 0.4…0.4 | — | phone: 0; 11.2°, 91 % | L 10 fr 0.56 cm → 0 fr | 0 | 7.9 cm (557 fr, ≤2054 v) | 2.5 cm (557 fr, ≤745 v) / 2.5 cm (557 fr, ≤654 v) | 2.5 cm (557 fr, ≤826 v) / 2.5 cm (557 fr, ≤667 v) | 0.6 cm (375 fr, ≤2 v) | 0.0 / 0.0 |
| Standing_Clap | 144 | **0** | 0.44…0.58 (0) | 0.4…0.9 / 0.5…1.5 | -0.6…46.5 (0 fr > 1 cm under) | — | 0 | 0 | 3.7 cm (5 fr, ≤549 v) | 2.5 cm (144 fr, ≤537 v) / 2.5 cm (144 fr, ≤355 v) | 2.5 cm (144 fr, ≤590 v) / 2.5 cm (144 fr, ≤429 v) | 1.5 cm (144 fr, ≤33 v) | 0.07 / 0.0 |
| Angry_Gesture | 176 | **0** | 0.4…0.4 (0) | 0.4…0.4 / 0.4…0.4 | -0.3…1.8 (0 fr > 1 cm under) | — | 0 | 0 | 0 | 2.5 cm (176 fr, ≤622 v) / 2.5 cm (174 fr, ≤540 v) | 2.5 cm (176 fr, ≤660 v) / 2.5 cm (176 fr, ≤623 v) | 1.4 cm (176 fr, ≤32 v) | 0.0 / 0.0 |
| Scared | 303 | **0** | 0.45…3.26 (3) | 0.5…3.3 / 0.4…4.3 | -0.7…51.9 (0 fr > 1 cm under) | — | 0 | 0 | 2.5 cm (28 fr, ≤256 v) | 2.5 cm (303 fr, ≤927 v) / 2.5 cm (298 fr, ≤596 v) | 2.5 cm (303 fr, ≤965 v) / 2.5 cm (298 fr, ≤634 v) | 1.8 cm (303 fr, ≤51 v) | 0.0 / 0.0 |
| Stand_To_Sit | 68 | **0** | 0.33…0.78 (0) | 0.3…1.6 / 0.8…1 | -0.1…40.8 (0 fr > 1 cm under) | — | 0 | 0 | 8.2 cm (27 fr, ≤3067 v) | 2.5 cm (68 fr, ≤657 v) / 2.5 cm (56 fr, ≤390 v) | 2.5 cm (68 fr, ≤734 v) / 2.5 cm (58 fr, ≤589 v) | 2.1 cm (68 fr, ≤41 v) | 0.0 / 0.0 |
| Sit_To_Stand | 63 | **0** | 0.32…1.15 (3) | 0.3…1.6 / 0.5…1.2 | 0.4…40.9 (0 fr > 1 cm under) | — | 0 | 0 | 8.5 cm (17 fr, ≤2013 v) | 2.5 cm (55 fr, ≤724 v) / 2.5 cm (39 fr, ≤437 v) | 2.5 cm (55 fr, ≤817 v) / 2.5 cm (59 fr, ≤471 v) | 1.8 cm (63 fr, ≤31 v) | 0.0 / 0.0 |
| Gaming | 152 | **0** | 0.4…0.4 (0) | 0.4…0.4 / 0.4…0.4 | -0.3…0.3 (0 fr > 1 cm under) | controller: 2.8 cm (152 fr); 1.4°, 100 % | 0 | 0 | 0 | 2 cm (152 fr, ≤24 v) / 2 cm (152 fr, ≤60 v) | 2 cm (152 fr, ≤33 v) / 2 cm (152 fr, ≤68 v) | 1.7 cm (152 fr, ≤39 v) | 0.0 / 0.0 |

Baseline, the same instrument on the character with no clip, the T-pose rest: hands in thighs 0 v ≤ 0 cm, left arm in torso 0 v ≤ 0 cm, right arm in torso 2 v ≤ 0.8 cm, left leg in right leg 2 v ≤ 0.8 cm, left hand in right hand 0 v ≤ 0 cm.

Baseline, the same instrument on the character with no clip, the arms 63° down (as v5 was modelled): hands in thighs 0 v ≤ 0 cm, left arm in torso 8 v ≤ 0.7 cm, right arm in torso 15 v ≤ 1.2 cm, left leg in right leg 2 v ≤ 0.8 cm, left hand in right hand 0 v ≤ 0 cm.

Baseline, the same instrument on the character with no clip, the arms 80° down, at his sides: hands in thighs 0 v ≤ 0 cm, left arm in torso 45 v ≤ 1.4 cm, right arm in torso 44 v ≤ 1.7 cm, left leg in right leg 2 v ≤ 0.8 cm, left hand in right hand 0 v ≤ 0 cm.
<!-- /table -->

How to read it:
- **Furniture, walls, floor** counts any vertex more than 1 cm inside, the page's own margin. In clip mode the pass
  tests every visible mesh in the room except his own, the chair (tested separately in its own frame), the floor and
  the walls (tested by their planes).
- **Supporting sole** is the lower of his two soles each frame, measured against what is under it: the floor, the rug's
  top, or a solid's top.
- **Held prop** counts his hand skin more than 2 mm inside the prop's box: the phone's and the tablet's slab, and the
  controller's bounding box. The controller's rounded grips don't fill its box, so the 2.8 cm there is his fingers
  round the grips, not through the controller. Its face is the phone's or tablet's screen, or the controller's
  buttons: the angle to his eyes, averaged over the clip every 0.25 s, and the share of those samples within 30°.
- **Hands in thighs** is the normal-based test from `rig/autorig/qa.html`: a hand vertex behind the nearest thigh
  vertex's normal by more than 5 mm. It is not contact_pass's capsule, which is sized from his baggy trousers (radius
  12–17 cm) and so reads a hand hanging beside the hip, or on the hoodie's hem, as 2000 vertices 8 cm deep.
- **Arm in torso** is shown two ways:
  - As the pair. It saturates at the instrument's 2.5 cm in every frame of every clip, with hundreds of vertices. That
    includes the hoodie vertices on his flanks that the rig binds to the arm bones (G23's review of
    preview/mixamo-pipeline, item 1: 4,792 torso vertices with ≥ 10 % arm weight, down to the waist).
  - **Sleeve only, away from the armpit**: arm vertices further out than the shoulder joint in the T-pose rest, and
    more than 15 cm from the shoulder joint as posed. This is still high, 2.5 cm (the cap) with 350–900 vertices in
    every frame of the eight clips with his arms at his sides or at his chest. It drops to 2 cm and 24–68 vertices in
    Gaming, where the arms are forward.

### What is not clean, and why

- **Sleeve in torso (all nine clips).** The performer's arms hang against a slimmer body. On this character the baggy
  sleeve and the baggy hoodie, both skinned by linear blending, overlap where the arm meets his side. With no clip and
  the arms 80° down, the same instrument gives 44–45 vertices at ≤ 1.7 cm; the clips put the arms closer in than that.
  - I tried a clip-side fix: turning each upper arm out about the chest's forward axis, only where the sleeve is
    inside, at most 15°. On Gaming that only took the depth (measured with a 5 cm search) from 4.06 / 4.29 cm to
    3.59 / 2.62 cm, and at 15° the arms visibly stand out from his body. So it is not baked: it bends the performance
    and does not clear it.
  - The fix belongs to the character: the shoulder and flank weights (G20; G23's items 1 and 3) or a cloth collision.
    It is reported here rather than hidden. From the outside the sleeve lies against his side in every render
    (`sheet.jpg`); the overlap is inside the cloth.
- **Scared, the supporting sole over 1 cm in 3 frames (up to 3.26 cm).** These fall inside the 7 frames where the
  performer has both feet in the air: the startle's jump. The bake keeps a jump a jump.
- **Sit_To_Stand, the supporting sole at 1.0–1.15 cm in 3 frames.** At the page's sit-down chair pose his feet are on
  the rug's edge. On the bake's flat floor his lower sole never exceeds 0.45 cm. In the room, the edge of the 1.3 cm rug
  under his feet changes what the sole stands on.
- **Leg in leg, 0.6–2.1 cm, ≤ 51 vertices.** The two baggy trouser legs touching at the inner knee (baseline with no
  clip: 2 vertices at 0.8 cm). It is the same cloth overlap as the sleeves, much smaller.

## Render sheet

`sheet.jpg`: each clip at 10 %, 50 % and 90 % of its length, from the front and the side (the camera kept inside the
room). Made by `room_build/kimodo/standing_sheet.mjs <port> docs/design/standing-clips/sheet.jpg`.
