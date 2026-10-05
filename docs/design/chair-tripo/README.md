# Office chair made by the owner on Tripo (preview/chair-tripo, G10d): preview only, nothing live

Based on preview/room-upgrade (fc52140). The owner's chair replaces the code-built one by default; `?chair=code` brings
the code-built chair back for comparison.

`chair_owner_raw.fbx`: the owner's Tripo export (79.9k tris, one mesh). Its textures are external files that were not
included. `raw_clay.jpg`: six views in neutral grey. `owner_marked_defects.jpg`: the owner circled the letter-shaped holes
and dents on the backrest, the headrest and the back of the frame; those must go.

## Sheets
- `defects_before_after.jpg`: the backrest close up from the front, the back, 3/4 front and 3/4 back. Top: as exported.
  Bottom: repaired.
- `chair_in_room.jpg`: the room at 14:00. The chair by the desk, from behind, from the side, and in the wide view.
- `chair_seated.jpg`: him in it, at the desk (typing and mouse) and in room_read, from two cameras each.

## The repair (geometry)
`room_build/fbx2ply.mjs` (FBX -> PLY, three.js FBXLoader), then `room_build/chair_owner_repair.py`. Both are deterministic:
running them again gives the same file byte for byte.

The letters are real holes through the cushions, with inverted, non-manifold walls, so cutting them out and capping them
does not hold. Each area is covered over instead:
1. a smooth surface (a thin-plate spline) is fitted to the cushion's outer envelope, leaving out the letters' pits;
2. the raised fringes that stick out past that surface are deleted, only where the new surface will cover them;
3. a new surface is laid 1.2 mm over the old one. Over its last 2.2 cm it follows the original surface and tucks 0.8 mm
   under it, so there is no step at the edge;
4. it gets texture coordinates from the faces under it, ready for the textures.

Nothing outside the four areas is changed.

| area | faces deleted | new faces | fit residual |
|---|---|---|---|
| backrest, front (upper) | 204 | 4986 | 0.09 mm |
| back of the mesh frame | 222 | 3602 | 0.17 mm |
| lumbar pad | 33 | 2544 | 0.12 mm |
| headrest | 0 (dents only) | 1064 | 0.16 mm |

79,893 -> 91,630 faces before the decimation.

Left as it is: a few small rough patches near the left and right edges of the mesh panel's back. They are in the original,
outside the marked areas, and are not letters.

## In the room
`room_build/build_chair_owner.mjs` -> `web/room/chair_owner.glb`:
- scaled x1.278, so the seat cushion's top is 0.52 m. The chair is 1.25 m tall with the headrest;
- turned 180° (Tripo's model faces +z; the sitter in the room's chair faces -z);
- the gas lift on the pivot of the room's `chair` node, then moved 5 cm back.

Then it is welded, decimated a little (the texture seams are kept) and compressed: 50.4k triangles, 613 KB, one mesh. The
page puts it into the room's own `chair` node, so CHAIR, chairHome, pulling, swivelling, riding and getting up are
unchanged.

**Why 5 cm back:** his skin was recorded in the chair's frame across every seated clip and tested against the chair. With
the gas lift exactly on the pivot, his reclined back in room_phone and room_read went through the backrest. From 5 cm back,
every seated clip is clear. The cost: the chair turns about a point 5 cm in front of its gas lift when it swivels. In the
typing pose he sits forward, so his back is a few centimetres off the backrest.

## Contacts (vertex by vertex, G2's body, every 2nd frame, 2 mm tolerance)
`python -m tests.visual.contacts --chair-sdf <sdf.npz>`. The chair is tested through a 5 mm signed-distance grid
(`tests/visual/chair_sdf.py`), because the Tripo mesh is not closed.

| scenario | frames | chair | keyboard / mouse (hands) |
|---|---|---|---|
| desk typing | 150 | 0 | 0 |
| desk mouse | 120 | 0 | 0 |
| room_read | 262 | 1 thigh vertex, 3 mm (at the grid's resolution) | 2 fingertips, 1 frame, 4.9 mm |
| room_phone | 326 | 0 | 0 |
| room_phone_scroll | 326 | 0 | 0 |
| eating at the desk | 120 | 1 back vertex 4 mm, 3 thigh vertices 6 mm | right hand, 24 frames, 14 mm |
| bedtime: stretch, get up, to bed | 330 | **head and neck into the headrest: 842 vertices, 39 frames, 13 mm**; thighs 9 mm and a foot 15 mm on the way up | left hand pushing off, 6 frames, 14 mm |
| getting up to the window | 180 | feet and calves over a base leg 19 mm, right forearm on the armrest 11 mm, 2–4 frames | left hand pushing off, 1 frame, 14 mm |
| sitting down at the desk | 240 | forearms and hands on the armrests, up to 16 mm, 6 frames | mouse: right hand arriving, 2 frames, 17.6 mm |

The keyboard and mouse contacts are the clips' own and match the earlier report. The chair contacts in the transitions
(sitting down, getting up) come from the owner's armrests and base, where the code-built chair had none. They last a few
frames each.

**The headrest in the bedtime stretch:** he leans his head back through the headrest by 13 mm. Moving the chair further
back does not help. Tilting the backrest and headrest back 10° clears it, but that changes the owner's model, so it is not
done here. It is an option if the owner wants it.

## Textures (pending)
The textures were not in the FBX. When they arrive: `node room_build/build_chair_owner.mjs <repaired.ply>
web/room/chair_owner.glb <folder>` takes base, normal and mr (png/jpg/webp). The same four areas will be painted out in the
texture too, so no letters remain there either.
