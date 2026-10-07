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

This re-bakes every row of `room_build/kimodo/standing_clips.json` (about 4 min for all nine; `MOCAP_DIR=<dir>` reads
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
  torso 9.2 cm into the bed as he stepped back.

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

### Hands: phone and sockets

- **Texting and Texting_While_Standing carry the page's phone on the right hand:** its rounded body and its screen,
  with a plain made-up feed on the glass. The rigid gripping-hand mesh made for the finger-less rig is not used.
  - It sits on a frame in his right palm, taken from his own finger bones.
  - As the page does for its own phone, it is lifted just enough that no skin of his right hand is inside it or over its
    screen, measured over the whole clip.
  - So it rests on his curled fingers. It is not wrapped in a grip, because the captured hand is a loose fist.
- **Measured on this rig, the names have the hands the other way round:**
  - Texting is one-handed: the right hand is at the chest from 0.8 to 17 s, the left hand down.
  - Texting_While_Standing is two-handed: both hands are at the chest from 2 to 20.6 s, about 20 cm apart. The phone is
    on the right hand as asked, so the left hand texts beside it, not on it.
- **Tablet and Gaming: a socket only.** `socket_R` / `socket_L` are empty Object3D in each palm, on every clip.
  - The page has no tablet prop.
  - The page's controller (`room/controller.glb`) stays on the desk. Attaching it to both hands is a follow-up.

## Contact table

Measured in the room as the preview places each clip, every frame of the whole clip:
- `CLIP=<Clip> node room_build/kimodo/contact_pass.mjs <port> x clip`, with the page served from `web/` with `?debug`;
- `node room_build/kimodo/standing_selfcontact.mjs web/room/char_mixamo.glb web/room/mx_standing <out.json>`.

The JSON is in `contact/`.

CONTACT_TABLE

How to read it:
- **Furniture, walls, floor** counts any vertex more than 1 cm inside, the page's own margin. In clip mode the pass
  tests every visible mesh in the room except his own, the chair (tested separately in its own frame), the floor and
  the walls (tested by their planes).
- **Supporting sole** is the lower of his two soles each frame, measured against what is under it: the floor, the rug's
  top, or a solid's top.
- **Hands in thighs** is the normal-based test from `rig/autorig/qa.html`: a hand vertex behind the nearest thigh
  vertex's normal by more than 5 mm. It is not contact_pass's capsule, which is sized from his baggy trousers (radius
  12–17 cm) and so reads a hand hanging beside the hip, or on the hoodie's hem, as 2000 vertices 8 cm deep.
- **Arm in torso** is shown three ways:
  - As the pair. It saturates at the instrument's 2.5 cm in every frame of every clip, with hundreds of vertices.
  - Away from the armpit (more than 15 cm from the shoulder joint): just as high.
  - **Sleeve only**: arm vertices further out than the shoulder joint in the T-pose rest. This leaves out the hoodie
    vertices on his flanks that the rig binds to the arm bones (G23's review of preview/mixamo-pipeline, item 1: 4,792
    torso vertices with ≥ 10 % arm weight, down to the waist), which follow the arm into his side in any arms-down
    pose, whatever the clip.
  - The sleeve-only column is what the clips themselves do. The rest is the rig's, and G20's weights are where it gets
    fixed.

## Render sheet

`sheet.jpg`: each clip at 10 %, 50 % and 90 % of its length, from the front and the side (the camera kept inside the
room). Made by `room_build/kimodo/standing_sheet.mjs <port> docs/design/standing-clips/sheet.jpg`.
